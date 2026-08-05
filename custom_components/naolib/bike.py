"""GBFS client and coordinator for the Naolib bike-sharing network.

The bike stations (ex-Bicloo, now Naolib) are published by JCDecaux as a
keyless GBFS 3.0 feed. ``station_information`` barely changes and is cached for
an hour, while ``station_status`` carries the live counters and is refetched on
every poll. A single coordinator serves every configured station, and the whole
network stays in the snapshot so each station can list its neighbours without
any extra request.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import re
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    API_TIMEOUT,
    BIKE_NEARBY_LIMIT,
    BIKE_NEARBY_RADIUS_M,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    GBFS_INFO_TTL,
    GBFS_STATION_INFORMATION_URL,
    GBFS_STATION_STATUS_URL,
    NEARBY_STATIONS_LIMIT,
)
from .stops import haversine

_LOGGER = logging.getLogger(__name__)

# French words that stay lowercase inside a name, unless they open it.
_PARTICLES = frozenset(
    {
        "a",
        "au",
        "aux",
        "d",
        "de",
        "des",
        "du",
        "en",
        "et",
        "l",
        "la",
        "le",
        "les",
        "sous",
        "sur",
        "\u00e0",
    }
)

_SEPARATORS = re.compile(r"([\s\-']+)")


class GbfsUnavailableError(Exception):
    """Raised when the GBFS feed cannot be read."""


@dataclass
class NaolibBikeStation:
    """A configured bike station."""

    id: str
    name: str
    interval: int


def _localized(value: Any) -> str:
    """Return the text of a GBFS field.

    GBFS 3.0 wraps names in ``[{"text": ..., "language": ...}]`` where 2.3 used
    a plain string; both are accepted so a feed rollback stays harmless.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("text"):
                return str(item["text"])
    return ""


def _last_reported(value: Any) -> str | None:
    """Normalize ``last_reported`` to an ISO timestamp.

    GBFS 3.0 sends an ISO string, 2.3 sent a POSIX timestamp.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return dt_util.utc_from_timestamp(value).isoformat()
    return None


def _titlecase(value: str) -> str:
    """Rewrite a shouty station name the way the stop index spells its stops.

    ``PRAIRIE AU DUC`` becomes ``Prairie au Duc``. Names that are not fully
    uppercase are left alone, so a future fix upstream is not undone here.
    """
    if not value or not value.isupper():
        return value

    words = []
    first = True
    for part in _SEPARATORS.split(value.lower()):
        if not part or _SEPARATORS.fullmatch(part):
            words.append(part)
            continue
        if first or part not in _PARTICLES:
            part = part[:1].upper() + part[1:]
        first = False
        words.append(part)
    return "".join(words)


def parse_stations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the stations from a ``station_information`` payload."""
    stations: list[dict[str, Any]] = []
    for raw in (payload.get("data") or {}).get("stations") or []:
        station_id = raw.get("station_id")
        lat, lon = raw.get("lat"), raw.get("lon")
        if station_id is None or lat is None or lon is None:
            continue
        try:
            coordinates = (float(lat), float(lon))
        except (TypeError, ValueError):
            continue
        stations.append(
            {
                "id": str(station_id),
                "name": _titlecase(_localized(raw.get("name"))) or str(station_id),
                "lat": coordinates[0],
                "lon": coordinates[1],
                "address": _localized(raw.get("address")),
                "capacity": raw.get("capacity"),
            }
        )
    return stations


def parse_status(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract the live counters from a ``station_status`` payload."""
    status: dict[str, dict[str, Any]] = {}
    for raw in (payload.get("data") or {}).get("stations") or []:
        station_id = raw.get("station_id")
        if station_id is None:
            continue
        status[str(station_id)] = {
            # 3.0 renamed the 2.3 "bikes" counters to "vehicles".
            "bikes": raw.get("num_vehicles_available", raw.get("num_bikes_available")),
            "docks": raw.get("num_docks_available"),
            "is_installed": bool(raw.get("is_installed", True)),
            "is_renting": bool(raw.get("is_renting", True)),
            "is_returning": bool(raw.get("is_returning", True)),
            "last_reported": _last_reported(raw.get("last_reported")),
        }
    return status


async def _async_get_json(
    session: aiohttp.ClientSession, url: str
) -> dict[str, Any] | None:
    """Fetch a GBFS document, or None when it cannot be read."""
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)
        ) as response:
            response.raise_for_status()
            return await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError) as exception:
        _LOGGER.debug("GBFS request to %s failed: %s", url, exception)
        return None


async def async_fetch_stations(
    session: aiohttp.ClientSession,
) -> list[dict[str, Any]]:
    """Return every bike station of the network.

    Used by the config flow, which needs the list before any coordinator runs.
    """
    payload = await _async_get_json(session, GBFS_STATION_INFORMATION_URL)
    if payload is None:
        raise GbfsUnavailableError(GBFS_STATION_INFORMATION_URL)
    return parse_stations(payload)


def nearby_stations(
    stations: list[dict[str, Any]],
    lat: float,
    lon: float,
    limit: int = NEARBY_STATIONS_LIMIT,
) -> list[dict[str, Any]]:
    """Return the closest stations to a location, with their distance."""
    scored = [
        {
            **station,
            "distance": round(haversine(lat, lon, station["lat"], station["lon"])),
        }
        for station in stations
    ]
    scored.sort(key=lambda station: station["distance"])
    return scored[:limit]


class NaolibBikeCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Poll the whole bike network and index stations by id."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the shared bike coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_bike",
            # Shared across config entries, like the departures coordinator.
            config_entry=None,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self._session = async_get_clientsession(hass)
        # Keyed by config entry id, so a reconfigured entry cleans up properly.
        self.stations: dict[str, NaolibBikeStation] = {}
        self._info: dict[str, dict[str, Any]] = {}
        self._info_expires: datetime | None = None
        self._unavailable_logged = False

    def register_station(self, entry_id: str, station: NaolibBikeStation) -> None:
        """Start serving a configured station."""
        self.stations[entry_id] = station
        self._apply_interval()

    def unregister_station(self, entry_id: str) -> None:
        """Stop serving a configured station."""
        self.stations.pop(entry_id, None)
        self._apply_interval()

    def station_by_id(self, station_id: str) -> NaolibBikeStation | None:
        """Return the configured station with this id, if any."""
        return next(
            (station for station in self.stations.values() if station.id == station_id),
            None,
        )

    def _apply_interval(self) -> None:
        """Use the shortest requested interval across all stations."""
        seconds = min(
            (station.interval for station in self.stations.values()),
            default=DEFAULT_UPDATE_INTERVAL,
        )
        self.update_interval = timedelta(seconds=seconds)

    async def _async_refresh_info(self) -> None:
        """Refetch the station descriptions when the cache expires."""
        now = dt_util.utcnow()
        if self._info and self._info_expires and now < self._info_expires:
            return
        payload = await _async_get_json(self._session, GBFS_STATION_INFORMATION_URL)
        if payload is None:
            return
        parsed = parse_stations(payload)
        if not parsed:
            return
        self._info = {station["id"]: station for station in parsed}
        self._info_expires = now + timedelta(seconds=GBFS_INFO_TTL)

    def _keep_last_snapshot(self) -> dict[str, dict[str, Any]]:
        """Serve the previous snapshot rather than flagging entities down."""
        if self.data is None:
            raise UpdateFailed("Error fetching data from the Naolib GBFS API")
        if not self._unavailable_logged:
            _LOGGER.warning(
                "The Naolib GBFS API is unavailable, serving the last known stations"
            )
            self._unavailable_logged = True
        return self.data

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch the whole bike network once."""
        await self._async_refresh_info()
        payload = await _async_get_json(self._session, GBFS_STATION_STATUS_URL)
        if payload is None or not self._info:
            return self._keep_last_snapshot()

        status = parse_status(payload)
        network = {
            station_id: {**info, **status[station_id]}
            for station_id, info in self._info.items()
            if station_id in status
        }
        if not network:
            return self._keep_last_snapshot()

        if self._unavailable_logged:
            _LOGGER.info("The Naolib GBFS API is available again")
            self._unavailable_logged = False
        return network


def build_station_data(
    network: dict[str, dict[str, Any]],
    station: NaolibBikeStation,
) -> dict[str, Any]:
    """Build the data of one station, with its neighbours, for the card."""
    current = network.get(station.id)
    if current is None:
        return {"available": False, "nearby_stations": []}

    neighbours = []
    for other in network.values():
        if other["id"] == station.id:
            continue
        distance = round(
            haversine(current["lat"], current["lon"], other["lat"], other["lon"])
        )
        if distance > BIKE_NEARBY_RADIUS_M:
            continue
        neighbours.append(
            {
                "station_id": other["id"],
                "name": other["name"],
                "distance": distance,
                "bikes": other["bikes"],
                "docks": other["docks"],
                "capacity": other["capacity"],
                "is_renting": other["is_renting"],
                "is_returning": other["is_returning"],
            }
        )
    neighbours.sort(key=lambda item: item["distance"])

    return {
        "available": True,
        "name": current["name"],
        "address": current["address"],
        "latitude": current["lat"],
        "longitude": current["lon"],
        "capacity": current["capacity"],
        "bikes": current["bikes"],
        "docks": current["docks"],
        "is_installed": current["is_installed"],
        "is_renting": current["is_renting"],
        "is_returning": current["is_returning"],
        "last_reported": current["last_reported"],
        "nearby_stations": neighbours[:BIKE_NEARBY_LIMIT],
    }
