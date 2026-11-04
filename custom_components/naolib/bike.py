"""GBFS clients and coordinators for the Naolib bike-sharing networks.

Two operators serve Nantes Métropole. The historic stations (ex-Bicloo) are
published by JCDecaux as a keyless GBFS 3.0 feed and are dismantled by January
2027; the Voi electric bikes replacing them come as a keyless GBFS 2.3 feed.
Each operator gets one shared coordinator, so every configured station of a
network is served by a single poll.

``station_information`` barely changes and is cached for an hour, while
``station_status`` carries the live counters and is refetched on every poll.
Voi also lists every bike with its remaining range: each one is hung on the
spot it stands on. The whole network stays in the snapshot so each station can
list its neighbours without any extra request.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import math
import re
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    API_TIMEOUT,
    BIKE_FEED_GONE_AFTER,
    BIKE_NEARBY_LIMIT,
    BIKE_NEARBY_RADIUS_M,
    BIKE_PROVIDER_JCDECAUX,
    BIKE_PROVIDER_VOI,
    BIKE_RETIRED_AFTER_POLLS,
    CONF_BIKE_PROVIDER,
    DOMAIN,
    GBFS_INFO_TTL,
    GBFS_STATION_INFORMATION_URL,
    GBFS_STATION_STATUS_URL,
    VOI_APP_URL,
    VOI_FREE_BIKE_STATUS_URL,
    VOI_LABEL_STOP_RADIUS_M,
    VOI_SPOT_RADIUS_M,
    VOI_STATION_INFORMATION_URL,
    VOI_STATION_STATUS_URL,
)
from .coordinator import NaolibSharedCoordinator
from .stops import load_stops, nearest

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
        "à",
    }
)

_SEPARATORS = re.compile(r"([\s\-']+)")

# Voi names its spots with internal codes such as ``NAN_CEN_064``: the town,
# then the quarter for Nantes itself, then a number. The areas are inferred
# from the codes (Voi does not publish them); an unknown one is shown as is.
_VOI_CODE = re.compile(r"^(?P<area>[A-Z]+(?:_[A-Z]+)*)_(?P<number>\d[\w-]*)$")
_VOI_AREAS = {
    "NAN_BEL": "Bellevue-Chantenay",
    "NAN_BRE": "Breil-Barberie",
    "NAN_CEN": "Centre-ville",
    "NAN_DER": "Dervallières-Zola",
    "NAN_DOU": "Doulon-Bottière",
    "NAN_ERD": "Nantes Erdre",
    "NAN_HAU": "Hauts-Pavés-Saint-Félix",
    "NAN_ILE": "Île de Nantes",
    "NAN_MAL": "Malakoff-Saint-Donatien",
    "NAN_NOR": "Nantes Nord",
    "NAN_SUD": "Nantes Sud",
    "AIG": "Saint-Aignan-de-Grand-Lieu",
    "BOUA": "Bouaye",
    "BOUG": "Bouguenais",
    "BRA": "Brains",
    "CAR": "Carquefou",
    "CHA": "La Chapelle-sur-Erdre",
    "JEA": "Saint-Jean-de-Boiseau",
    "LUC": "Sainte-Luce-sur-Loire",
    "MON": "La Montagne",
    "PEL": "Le Pellerin",
    "REZ": "Rezé",
    "SOR": "Les Sorinières",
    "THO": "Thouaré-sur-Loire",
}
_VOI_FALLBACK_LABEL = "Emplacement Voi"

# Half-width of the box a stop must fall in before its exact distance to a Voi
# spot is computed: comfortably above VOI_LABEL_STOP_RADIUS_M at Nantes.
_STOP_BOX_DEG = 0.003

# Size of the grid cells the Voi spots are bucketed in to place the bikes:
# about 110 m by 75 m at Nantes, well above VOI_SPOT_RADIUS_M, so a bike only
# needs to be compared with the spots of its own cell and the eight around.
_CELL_DEG = 0.001


class GbfsUnavailableError(Exception):
    """Raised when the GBFS feed cannot be read."""


@dataclass(frozen=True)
class BikeFeed:
    """What tells two bike-sharing operators apart."""

    key: str
    # Names the feed in the logs.
    source: str
    information_url: str
    status_url: str
    attribution: str
    manufacturer: str
    model: str
    # Lists every bike with its remaining range.
    vehicles_url: str | None = None
    has_docks: bool = True
    # Station names are internal codes, rewritten into readable labels.
    coded_names: bool = False
    # The network is being dismantled: its stations get a repair once gone.
    retiring: bool = False
    # Opens the operator's app on the closest bike.
    app_url: str | None = None


JCDECAUX_FEED = BikeFeed(
    key=BIKE_PROVIDER_JCDECAUX,
    source="GBFS",
    information_url=GBFS_STATION_INFORMATION_URL,
    status_url=GBFS_STATION_STATUS_URL,
    attribution="Données Naolib / JCDecaux",
    manufacturer="Naolib",
    model="Station vélo",
    retiring=True,
)

VOI_FEED = BikeFeed(
    key=BIKE_PROVIDER_VOI,
    source="Voi GBFS",
    information_url=VOI_STATION_INFORMATION_URL,
    status_url=VOI_STATION_STATUS_URL,
    attribution="Données Voi",
    manufacturer="Voi",
    model="Emplacement vélo",
    vehicles_url=VOI_FREE_BIKE_STATUS_URL,
    has_docks=False,
    coded_names=True,
    app_url=VOI_APP_URL,
)

FEEDS: dict[str, BikeFeed] = {feed.key: feed for feed in (JCDECAUX_FEED, VOI_FEED)}


def feed_of(data: Mapping[str, Any]) -> BikeFeed:
    """Return the feed an entry reads; entries older than Voi read JCDecaux."""
    return FEEDS.get(
        data.get(CONF_BIKE_PROVIDER, BIKE_PROVIDER_JCDECAUX), JCDECAUX_FEED
    )


def station_key(provider: str, station_id: str) -> str:
    """Identify a station across operators.

    JCDecaux ids stay bare, so the entries created before Voi keep their unique
    ids; the others carry their operator.
    """
    if provider == BIKE_PROVIDER_JCDECAUX:
        return station_id
    return f"{provider}_{station_id}"


@dataclass
class NaolibBikeStation:
    """A configured bike station."""

    id: str
    name: str
    interval: int
    provider: str = BIKE_PROVIDER_JCDECAUX

    @property
    def key(self) -> str:
        """Identify the station in unique ids and device identifiers."""
        return station_key(self.provider, self.id)


def _localized(value: Any) -> str:
    """Return the text of a GBFS field.

    GBFS 3.0 wraps names in ``[{"text": ..., "language": ...}]`` where 2.3 used
    a plain string; both are accepted.
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


def _position(raw: Mapping[str, Any]) -> tuple[float, float] | None:
    """Return the coordinates of a GBFS record, if usable."""
    try:
        return float(raw["lat"]), float(raw["lon"])
    except (KeyError, TypeError, ValueError):
        return None


def parse_stations(
    payload: dict[str, Any], *, coded: bool = False
) -> list[dict[str, Any]]:
    """Extract the stations from a ``station_information`` payload.

    ``coded`` keeps the raw name as the station ``code``, for the feeds whose
    names are internal codes rather than words.
    """
    stations: list[dict[str, Any]] = []
    for raw in (payload.get("data") or {}).get("stations") or []:
        station_id = raw.get("station_id")
        coordinates = _position(raw)
        if station_id is None or coordinates is None:
            continue
        raw_name = _localized(raw.get("name"))
        station = {
            "id": str(station_id),
            "name": (raw_name if coded else _titlecase(raw_name)) or str(station_id),
            "lat": coordinates[0],
            "lon": coordinates[1],
            "address": _localized(raw.get("address")),
            "capacity": raw.get("capacity"),
        }
        if coded:
            station["code"] = raw_name
        stations.append(station)
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


def parse_vehicles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the bikes from a ``free_bike_status`` (or 3.0 ``vehicle_status``).

    Their identifiers are dropped: GBFS lets an operator rotate them after every
    trip, and nothing here needs to follow a bike.
    """
    data = payload.get("data") or {}
    vehicles: list[dict[str, Any]] = []
    for raw in data.get("bikes") or data.get("vehicles") or []:
        coordinates = _position(raw)
        if coordinates is None:
            continue
        range_m = raw.get("current_range_meters")
        vehicles.append(
            {
                "lat": coordinates[0],
                "lon": coordinates[1],
                "range_km": (
                    round(range_m / 1000) if isinstance(range_m, (int, float)) else None
                ),
                "disabled": bool(raw.get("is_disabled", False)),
            }
        )
    return vehicles


def voi_label(code: str, stop: str | None) -> str:
    """Build a readable name for a Voi spot from its code and closest stop.

    ``NAN_CEN_064`` next to the Hôtel de Ville stop becomes
    ``Hôtel de Ville · Centre-ville 064``. The number is kept: neighbouring
    spots often share their closest stop.
    """
    match = _VOI_CODE.match(code)
    place = (
        f"{_VOI_AREAS.get(match['area'], match['area'])} {match['number']}"
        if match
        else code
    )
    return " · ".join(part for part in (stop, place) if part) or _VOI_FALLBACK_LABEL


def _stops_around(
    stops: Iterable[dict[str, Any]], lat: float, lon: float
) -> list[dict[str, Any]]:
    """Return the stops in a small box around a point, before exact distances."""
    return [
        stop
        for stop in stops
        if abs(stop["lat"] - lat) < _STOP_BOX_DEG
        and abs(stop["lon"] - lon) < _STOP_BOX_DEG
    ]


def label_spots(stations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Name the Voi spots after their closest stop and their area.

    This reads the stop index and must be called from an executor.
    """
    stops = load_stops()
    labelled = []
    for station in stations:
        closest = nearest(
            _stops_around(stops, station["lat"], station["lon"]),
            station["lat"],
            station["lon"],
            limit=1,
            radius=VOI_LABEL_STOP_RADIUS_M,
        )
        label = voi_label(station["code"], closest[0]["name"] if closest else None)
        labelled.append({**station, "name": label})
    return labelled


def _cell(lat: float, lon: float) -> tuple[int, int]:
    """Return the grid cell a point falls in."""
    return math.floor(lat / _CELL_DEG), math.floor(lon / _CELL_DEG)


def attach_vehicles(network: Stations, vehicles: list[dict[str, Any]]) -> None:
    """Hang each bike on the spot it stands on, best range first.

    A bike farther than VOI_SPOT_RADIUS_M from every spot is parked elsewhere
    and belongs to none.
    """
    grid: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for station in network.values():
        station["vehicles"] = []
        grid[_cell(station["lat"], station["lon"])].append(station)

    for vehicle in vehicles:
        row, col = _cell(vehicle["lat"], vehicle["lon"])
        candidates = [
            station
            for d_row in (-1, 0, 1)
            for d_col in (-1, 0, 1)
            for station in grid.get((row + d_row, col + d_col), ())
        ]
        closest = nearest(
            candidates,
            vehicle["lat"],
            vehicle["lon"],
            limit=1,
            radius=VOI_SPOT_RADIUS_M,
        )
        if closest:
            network[closest[0]["id"]]["vehicles"].append(
                {"range_km": vehicle["range_km"], "disabled": vehicle["disabled"]}
            )

    for station in network.values():
        station["vehicles"].sort(
            key=lambda vehicle: (
                -1 if vehicle["range_km"] is None else vehicle["range_km"]
            ),
            reverse=True,
        )


def best_range(vehicles: list[dict[str, Any]] | None) -> int | None:
    """Return the longest range among the bikes that can be rented, in km."""
    return max(
        (
            vehicle["range_km"]
            for vehicle in vehicles or ()
            if not vehicle["disabled"] and vehicle["range_km"] is not None
        ),
        default=None,
    )


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


async def _async_describe_stations(
    hass: HomeAssistant, feed: BikeFeed, payload: dict[str, Any]
) -> list[dict[str, Any]]:
    """Parse a ``station_information`` payload into named stations."""
    stations = parse_stations(payload, coded=feed.coded_names)
    if feed.coded_names and stations:
        return await hass.async_add_executor_job(label_spots, stations)
    return stations


async def async_fetch_stations(
    hass: HomeAssistant, feed: BikeFeed
) -> list[dict[str, Any]]:
    """Return every station of a network.

    Used by the config and repair flows, which need the list before any
    coordinator runs.
    """
    session = async_get_clientsession(hass)
    payload = await _async_get_json(session, feed.information_url)
    if payload is None:
        raise GbfsUnavailableError(feed.information_url)
    return await _async_describe_stations(hass, feed, payload)


def retired_issue_id(entry_id: str) -> str:
    """Return the id of the repair raised when a station leaves the network."""
    return f"bike_station_retired_{entry_id}"


# A bike network, keyed by station id.
type Stations = dict[str, dict[str, Any]]


class NaolibBikeCoordinator(NaolibSharedCoordinator[NaolibBikeStation, Stations]):
    """Poll a whole bike network and index stations by id."""

    def __init__(self, hass: HomeAssistant, feed: BikeFeed) -> None:
        """Initialize the shared coordinator of one operator."""
        super().__init__(hass, f"bike_{feed.key}", feed.source)
        self.feed = feed
        self._session = async_get_clientsession(hass)
        self._info: Stations = {}
        self._info_expires: datetime | None = None
        # The bikes last read, kept through a failed request so the ranges
        # do not blink on every hiccup.
        self._vehicles: list[dict[str, Any]] | None = None
        # Every position ever described, so a retired station can still be
        # located once the feed stops describing it.
        self.positions: dict[str, tuple[float, float]] = {}
        # Retirement watch: polls in a row each tracked station was missing,
        # and since when the whole feed has been failing.
        self._missing: dict[str, int] = {}
        self._failing_since: datetime | None = None

    async def _async_refresh_info(self) -> None:
        """Refetch the station descriptions when the cache expires."""
        now = dt_util.utcnow()
        if self._info and self._info_expires and now < self._info_expires:
            return
        payload = await _async_get_json(self._session, self.feed.information_url)
        if payload is None:
            return
        parsed = await _async_describe_stations(self.hass, self.feed, payload)
        if not parsed:
            return
        self._info = {station["id"]: station for station in parsed}
        self.positions.update(
            (station["id"], (station["lat"], station["lon"])) for station in parsed
        )
        self._info_expires = now + timedelta(seconds=GBFS_INFO_TTL)

    async def _async_refresh_vehicles(self, network: Stations) -> None:
        """Read the bikes and hang them on their spots."""
        if self.feed.vehicles_url is None:
            return
        payload = await _async_get_json(self._session, self.feed.vehicles_url)
        if payload is not None:
            self._vehicles = parse_vehicles(payload)
        if self._vehicles is not None:
            attach_vehicles(network, self._vehicles)

    async def _async_fetch_network(self) -> Stations | None:
        """Fetch the whole network, or None when it cannot be read."""
        await self._async_refresh_info()
        payload = await _async_get_json(self._session, self.feed.status_url)
        if payload is None or not self._info:
            return None

        status = parse_status(payload)
        network = {
            station_id: {**info, **status[station_id]}
            for station_id, info in self._info.items()
            if station_id in status
        }
        if not network:
            return None

        await self._async_refresh_vehicles(network)
        return network

    async def _async_update_data(self) -> Stations:
        """Fetch the whole bike network once."""
        network = await self._async_fetch_network()
        if self.feed.retiring:
            self._watch_retirements(network)
        if network is None:
            return self._serve_last_snapshot()

        self._mark_available()
        return network

    def _watch_retirements(self, network: Stations | None) -> None:
        """Raise a repair for each tracked station that left the network.

        A station is gone once it has been missing or uninstalled for a few
        polls in a row, or once the whole feed has been unreachable for a day:
        the operator may switch the feed off rather than empty it.
        """
        now = dt_util.utcnow()
        if network is None:
            if self._failing_since is None:
                self._failing_since = now
            if now - self._failing_since < timedelta(seconds=BIKE_FEED_GONE_AFTER):
                return
            gone = set(self.tracked)
        else:
            self._failing_since = None
            gone = {
                key
                for key, station in self.tracked.items()
                if not (network.get(station.id) or {}).get("is_installed")
            }

        for key, station in self.tracked.items():
            if key not in gone:
                if self._missing.pop(key, 0) >= BIKE_RETIRED_AFTER_POLLS:
                    ir.async_delete_issue(self.hass, DOMAIN, retired_issue_id(key))
                continue
            self._missing[key] = self._missing.get(key, 0) + 1
            if self._missing[key] == BIKE_RETIRED_AFTER_POLLS:
                self._raise_retired_issue(key, station)

    def _raise_retired_issue(self, key: str, station: NaolibBikeStation) -> None:
        """Offer to move a retired station to a nearby Voi spot."""
        _LOGGER.info("Bike station %s left the %s feed", station.name, self._source)
        data: dict[str, str | int | float | None] = {"entry_id": key}
        position = self.positions.get(station.id)
        if position is not None:
            data["latitude"], data["longitude"] = position
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            retired_issue_id(key),
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="bike_station_retired",
            translation_placeholders={"station": station.name},
            data=data,
        )


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
            "best_range_km": best_range(other.get("vehicles")),
        }
        for other in nearest(
            (other for other in network.values() if other["id"] != station.id),
            current["lat"],
            current["lon"],
            limit=BIKE_NEARBY_LIMIT,
            radius=BIKE_NEARBY_RADIUS_M,
        )
    ]

    vehicles = current.get("vehicles")
    return {
        "available": True,
        "name": current["name"],
        "code": current.get("code"),
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
        "vehicles": vehicles,
        "best_range_km": best_range(vehicles),
        "nearby_stations": neighbours,
    }
