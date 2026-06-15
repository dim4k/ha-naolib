"""Shared real-time coordinator and per-stop formatting for Naolib.

A single :class:`NaolibGlobalCoordinator` polls the whole Naolib network once per
update interval and stores every departure indexed by quay. Each configured
stop then filters and formats the departures it cares about locally, so the
rate-limited endpoint is hit only once regardless of how many stops are set up.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NaolibApiClient
from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Map SIRI VehicleMode to the legacy line type used by the frontend card
# (1=tram, 2=busway, 3=bus, 4=navibus/ferry).
_VEHICLE_TYPE = {"tram": 1, "bus": 3, "ferry": 4}

# Map SIRI DirectionName (aller/retour) to the legacy 1/2 direction.
_DIRECTION = {"A": 1, "R": 2}


class NaolibGlobalCoordinator(DataUpdateCoordinator[dict[str, list[dict[str, Any]]]]):
    """Poll the whole network and index departures by quay."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the shared coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_global",
            # The coordinator is shared across every config entry, so it is not
            # tied to a single one; passing None silences the deprecation
            # warning without binding its lifecycle to one entry.
            config_entry=None,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.api = NaolibApiClient(async_get_clientsession(hass))
        self._intervals: dict[str, int] = {}

    def set_interval(self, entry_id: str, seconds: int) -> None:
        """Register an entry's desired update interval (shortest wins)."""
        self._intervals[entry_id] = seconds
        self._apply_interval()

    def remove_interval(self, entry_id: str) -> None:
        """Drop an entry's update interval."""
        self._intervals.pop(entry_id, None)
        self._apply_interval()

    def _apply_interval(self) -> None:
        """Use the shortest requested interval across all stops."""
        seconds = min(self._intervals.values(), default=DEFAULT_UPDATE_INTERVAL)
        self.update_interval = timedelta(seconds=seconds)

    async def _async_update_data(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch the whole network once."""
        data = await self.api.async_get_all_departures()
        if data is None:
            raise UpdateFailed("Error fetching data from the Naolib SIRI API")
        return data


def _humanize(delta_seconds: float) -> str:
    """Format a time delta the way the frontend card expects."""
    if delta_seconds <= 60:
        return "proche"
    minutes = int(delta_seconds // 60)
    if minutes < 60:
        return f"{minutes} mn"
    return f"{minutes // 60}h{minutes % 60:02d}"


def _vehicle_type(mode: str | None) -> int:
    """Map a SIRI VehicleMode to the legacy line type."""
    return _VEHICLE_TYPE.get((mode or "").lower(), 3)


def _direction(direction_name: str | None) -> int:
    """Map a SIRI DirectionName to the legacy 1/2 direction."""
    return _DIRECTION.get((direction_name or "").upper(), 1)


def build_stop_data(
    network: dict[str, list[dict[str, Any]]], quays: list[str]
) -> dict[str, Any]:
    """Build the per-stop real-time departures for the card.

    ``network`` is the global coordinator data keyed by quay; ``quays`` are the
    quays belonging to the configured stop. The full daily timetable comes from
    the embedded GTFS data instead (see ``schedules.py``).
    """
    now = dt_util.now()
    collected: list[tuple[datetime, float, dict[str, Any]]] = []

    for quay in quays:
        for raw in network.get(quay, []):
            expected = raw.get("expected")
            when = dt_util.parse_datetime(expected) if expected else None
            if when is None:
                continue
            delta = (when - now).total_seconds()
            if delta < -60:
                continue
            collected.append((when, delta, raw))

    collected.sort(key=lambda item: item[0])

    next_departures = [
        {
            "line": raw.get("line"),
            "type": _vehicle_type(raw.get("vehicle_mode")),
            "destination": raw.get("destination"),
            "time": _humanize(delta),
            "direction": _direction(raw.get("direction_name")),
            "traffic_info": False,
            "traffic_message": None,
        }
        for _when, delta, raw in collected
    ]

    return {"next_departures": next_departures}
