"""GBFS client and coordinator for the Naolib bike-sharing network.

The bike stations (ex-Bicloo, now Naolib) are published by JCDecaux as a
keyless GBFS 3.0 feed. ``station_information`` barely changes and is cached for
an hour, while ``station_status`` carries the live counters and is refetched on
every poll. A single coordinator serves every configured station, and the whole
network stays in the snapshot so each station can list its neighbours without
any extra request.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import re
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    API_TIMEOUT,
    BIKE_NEARBY_LIMIT,
    BIKE_NEARBY_RADIUS_M,
    GBFS_INFO_TTL,
    GBFS_STATION_INFORMATION_URL,
    GBFS_STATION_STATUS_URL,
)
from .coordinator import NaolibSharedCoordinator
from .stops import nearest

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
        async with asyncio.timeout(API_TIMEOUT), session.get(url) as response:
            response.raise_for_status()
            document: dict[str, Any] = await response.json(content_type=None)
            return document
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


# The bike network, keyed by station id.
type Stations = dict[str, dict[str, Any]]


class NaolibBikeCoordinator(NaolibSharedCoordinator[NaolibBikeStation, Stations]):
    """Poll the whole bike network and index stations by id."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the shared bike coordinator."""
        super().__init__(hass, "bike", "GBFS")
        self._session = async_get_clientsession(hass)
        self._info: Stations = {}
        self._info_expires: datetime | None = None

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

    async def _async_update_data(self) -> Stations:
        """Fetch the whole bike network once."""
        await self._async_refresh_info()
        payload = await _async_get_json(self._session, GBFS_STATION_STATUS_URL)
        if payload is None or not self._info:
            return self._serve_last_snapshot()

        status = parse_status(payload)
        network = {
            station_id: {**info, **status[station_id]}
            for station_id, info in self._info.items()
            if station_id in status
        }
        if not network:
            return self._serve_last_snapshot()

        self._mark_available()
        return network


def build_station_data(network: Stations, station: NaolibBikeStation) -> dict[str, Any]:
    """Build the data of one station, with its neighbours, for the card."""
    current = network.get(station.id)
    if current is None:
        return {"available": False, "nearby_stations": []}

    neighbours = [
        {
            "station_id": other["id"],
            "name": other["name"],
            "distance": other["distance"],
            "bikes": other["bikes"],
            "docks": other["docks"],
            "capacity": other["capacity"],
            "is_renting": other["is_renting"],
            "is_returning": other["is_returning"],
        }
        for other in nearest(
            (other for other in network.values() if other["id"] != station.id),
            current["lat"],
            current["lon"],
            limit=BIKE_NEARBY_LIMIT,
            radius=BIKE_NEARBY_RADIUS_M,
        )
    ]

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
        "nearby_stations": neighbours,
    }
