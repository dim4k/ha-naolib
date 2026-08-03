"""Shared real-time coordinator and per-stop formatting for Naolib.

A single :class:`NaolibGlobalCoordinator` polls the whole Naolib network once per
update interval and stores every departure indexed by quay. Each configured
stop then filters and formats the departures it cares about locally, so the
rate-limited endpoint is hit only once regardless of how many stops are set up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
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


@dataclass
class NaolibStop:
    """A configured stop and the data derived from it."""

    code: str
    name: str
    quays: list[str]
    interval: int
    # Last scheduled departure of the day per "{line}|{direction}" group,
    # recomputed by the coordinator when the service day changes.
    last_times: dict[str, str] = field(default_factory=dict)
    last_times_date: date | None = None


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
        self.api = NaolibApiClient(hass, async_get_clientsession(hass))
        # Keyed by config entry id: a reconfigured entry changes stop code, so
        # only the entry id reliably identifies what to drop on unload.
        self.stops: dict[str, NaolibStop] = {}
        self._unavailable_logged = False

    def register_stop(self, entry_id: str, stop: NaolibStop) -> None:
        """Start serving a configured stop."""
        self.stops[entry_id] = stop
        self._apply_interval()

    def unregister_stop(self, entry_id: str) -> None:
        """Stop serving a configured stop."""
        self.stops.pop(entry_id, None)
        self._apply_interval()

    def stop_by_code(self, stop_code: str) -> NaolibStop | None:
        """Return the configured stop with this code, if any."""
        return next(
            (stop for stop in self.stops.values() if stop.code == stop_code), None
        )

    def _apply_interval(self) -> None:
        """Use the shortest requested interval across all stops."""
        seconds = min(
            (stop.interval for stop in self.stops.values()),
            default=DEFAULT_UPDATE_INTERVAL,
        )
        self.update_interval = timedelta(seconds=seconds)

    async def _async_update_data(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch the whole network once."""
        wanted = {quay for stop in self.stops.values() for quay in stop.quays}
        data = await self.api.async_get_all_departures(wanted or None)
        if data is None:
            if self.data is None:
                raise UpdateFailed("Error fetching data from the Naolib SIRI API")
            # Transient failure (rate limit, gateway error, timeout): keep
            # serving the last known snapshot so entities stay available
            # instead of flickering "unavailable" on every hiccup.
            if not self._unavailable_logged:
                _LOGGER.warning(
                    "The Naolib API is unavailable, serving the last known departures"
                )
                self._unavailable_logged = True
            return self.data

        if self._unavailable_logged:
            _LOGGER.info("The Naolib API is available again")
            self._unavailable_logged = False
        await self._async_refresh_last_times()
        return data

    async def _async_refresh_last_times(self) -> None:
        """Recompute each stop's last scheduled departures when the day changes.

        The "last passage of the day" flag then follows the GTFS service
        calendar automatically.
        """
        today = dt_util.now().date()
        # Snapshot: a config entry may be set up or removed while we await.
        for stop in list(self.stops.values()):
            if stop.last_times_date == today:
                continue
            stop.last_times = await self.hass.async_add_executor_job(
                last_departures, stop.code, today
            )
            stop.last_times_date = today


@dataclass
class NaolibData:
    """State shared by every config entry, stored in ``hass.data``."""

    coordinator: NaolibGlobalCoordinator
    loader_url: str = ""


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


def filter_departures(
    departures: list[dict[str, Any]],
    lines: list[str] | None = None,
    direction: int | None = None,
    walk_minutes: int = 0,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Narrow a formatted departure list down to what the caller asked for.

    ``walk_minutes`` drops the departures that cannot be reached on foot.
    ``departures`` is expected to be sorted by departure time.
    """
    wanted = {line.casefold() for line in lines} if lines else None
    earliest = dt_util.now() + timedelta(minutes=walk_minutes) if walk_minutes else None

    result: list[dict[str, Any]] = []
    for departure in departures:
        if (
            wanted is not None
            and (departure.get("line") or "").casefold() not in wanted
        ):
            continue
        if direction is not None and departure.get("direction") != direction:
            continue
        if earliest is not None:
            when = dt_util.parse_datetime(departure.get("expected_ts") or "")
            if when is None or when < earliest:
                continue
        result.append(departure)
        if limit is not None and len(result) >= limit:
            break
    return result


def build_stop_data(
    network: dict[str, list[dict[str, Any]]],
    stop: NaolibStop,
) -> dict[str, Any]:
    """Build the per-stop real-time departures for the card.

    ``network`` is the global coordinator data keyed by quay. The stop's
    ``last_times`` come from the embedded GTFS data (see
    ``schedules.last_departures``); the full daily timetable comes from
    ``schedules.build_timetable``.
    """
    now = dt_util.now()
    collected: list[tuple[datetime, float, dict[str, Any], int | None, bool]] = []

    for quay in stop.quays:
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
            if stop.last_times and aimed is not None:
                group_key = f"{raw.get('line')}|{_direction(raw.get('direction_name'))}"
                is_last = stop.last_times.get(group_key) == aimed.strftime("%H%M")
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
