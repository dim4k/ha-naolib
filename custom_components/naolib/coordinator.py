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
from .schedules import last_departures

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
            if self.data is not None:
                # Transient failure (rate limit, gateway error, timeout): keep
                # serving the last known snapshot so entities stay available
                # instead of flickering "unavailable" on every hiccup.
                _LOGGER.debug("Naolib API hiccup, serving last known data")
                return self.data
            raise UpdateFailed("Error fetching data from the Naolib SIRI API")
        await self._async_refresh_last_times()
        return data

    async def _async_refresh_last_times(self) -> None:
        """Recompute each stop's last scheduled departures when the day changes.

        The result is stored on the stop entry in ``hass.data`` and read by
        the sensors when building their departures, so the "last passage of
        the day" flag follows the GTFS service calendar automatically.
        """
        stops = self.hass.data.get(DOMAIN, {}).get("stops", {})
        today = dt_util.now().date()
        for stop_code, stop in stops.items():
            if stop.get("last_times_date") == today:
                continue
            times = await self.hass.async_add_executor_job(
                last_departures, stop_code, today
            )
            stop["last_times"] = times
            stop["last_times_date"] = today


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
    network: dict[str, list[dict[str, Any]]],
    quays: list[str],
    last_times: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the per-stop real-time departures for the card.

    ``network`` is the global coordinator data keyed by quay; ``quays`` are the
    quays belonging to the configured stop. ``last_times`` maps each
    ``"{line}|{direction}"`` group to the last scheduled departure of the day
    (from the embedded GTFS data, see ``schedules.last_departures``); the full
    daily timetable comes from ``schedules.build_timetable``.
    """
    now = dt_util.now()
    collected: list[tuple[datetime, float, dict[str, Any], int | None, bool]] = []

    for quay in quays:
        for raw in network.get(quay, []):
            expected = raw.get("expected")
            when = dt_util.parse_datetime(expected) if expected else None
            if when is None:
                continue
            delta = (when - now).total_seconds()
            if delta < -60:
                continue
            aimed_raw = raw.get("aimed")
            aimed = dt_util.parse_datetime(aimed_raw) if aimed_raw else None
            delay_minutes = (
                round((when - aimed).total_seconds() / 60)
                if aimed is not None
                else None
            )
            # Flag the departure if it is the last scheduled passage of the
            # day for its line/direction (the realtime feed does not expose
            # this, so it is derived from the theoretical timetable).
            is_last = False
            if last_times and aimed is not None:
                group_key = f"{raw.get('line')}|{_direction(raw.get('direction_name'))}"
                is_last = last_times.get(group_key) == aimed.strftime("%H%M")
            collected.append((when, delta, raw, delay_minutes, is_last))

    collected.sort(key=lambda item: item[0])

    next_departures = [
        {
            "line": raw.get("line"),
            "type": _vehicle_type(raw.get("vehicle_mode")),
            "destination": raw.get("destination"),
            "time": _humanize(delta),
            # Raw timestamp so the frontend can tick the countdown between
            # coordinator refreshes.
            "expected_ts": when.isoformat(),
            "direction": _direction(raw.get("direction_name")),
            "delay_minutes": delay_minutes,
            "is_last": is_last,
        }
        for when, delta, raw, delay_minutes, is_last in collected
    ]

    # Timestamp of the very next departure, exposed as the sensor's native
    # value (SensorDeviceClass.TIMESTAMP). ``None`` when no bus is upcoming.
    next_departure_dt = collected[0][0] if collected else None

    return {
        "next_departures": next_departures,
        "next_departure_dt": next_departure_dt,
    }
