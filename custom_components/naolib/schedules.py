"""Embedded theoretical timetable helpers (offline, GTFS-derived).

The real-time SIRI API only returns the next few departures, so the full daily
timetable is generated from the GTFS feed by ``scripts/generate_stops_index.py``
and shipped with the integration. ``data/schedules.sqlite`` holds one
compressed row per station -- the whole feed is far too large to keep in
memory -- and a shared ``data/calendar.json`` describes which GTFS services run
on a given date (regular days + exceptions).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from functools import lru_cache
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any
import zlib

from .const import CALENDAR_FILE, SCHEDULES_DB

_LOGGER = logging.getLogger(__name__)

_BASE_PATH = Path(__file__).parent


@lru_cache(maxsize=1)
def load_calendar() -> dict[str, dict[str, Any]]:
    """Load the GTFS service calendar (cached).

    This performs blocking file IO and must be called from an executor.
    """
    path = _BASE_PATH / CALENDAR_FILE
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# A station's timetable is a few dozen kilobytes, and only the configured stops
# are ever asked for.
@lru_cache(maxsize=16)
def load_station_timetable(station_id: str) -> dict[str, dict[str, Any]]:
    """Return the timetable of a station, or an empty mapping if missing.

    This performs blocking file IO and must be called from an executor.
    """
    path = _BASE_PATH / SCHEDULES_DB
    if not path.exists():
        return {}
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = connection.execute(
                "SELECT payload FROM station_schedules WHERE station_id = ?",
                (station_id,),
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exception:
        _LOGGER.error("Could not read the embedded timetables: %s", exception)
        return {}

    if row is None:
        return {}
    try:
        return json.loads(zlib.decompress(row[0]))
    except (zlib.error, ValueError) as exception:
        _LOGGER.error("Corrupt timetable for station %s: %s", station_id, exception)
        return {}


@lru_cache(maxsize=8)
def active_services(today: date) -> frozenset[str]:
    """Return the set of GTFS service ids running on ``today``."""
    calendar = load_calendar()
    datestr = today.strftime("%Y%m%d")
    weekday = today.weekday()  # Monday == 0
    services: set[str] = set()

    for service_id, info in calendar.items():
        added = info.get("added", [])
        removed = info.get("removed", [])
        if datestr in removed:
            continue
        if datestr in added:
            services.add(service_id)
            continue
        days = info.get("days") or []
        start = info.get("start", "")
        end = info.get("end", "")
        if (
            len(days) == 7
            and days[weekday]
            and start
            and end
            and start <= datestr <= end
        ):
            services.add(service_id)
    return frozenset(services)


def _active_times(
    station_id: str, today: date
) -> Iterator[tuple[str, dict[str, Any], list[str]]]:
    """Yield ``(group_key, group, times)`` for the services running on ``today``.

    Groups without a single departure that day are skipped.
    """
    services = active_services(today)
    for group_key, group in load_station_timetable(station_id).items():
        times = [
            value
            for service_id, service_times in group.get("services", {}).items()
            if service_id in services
            for value in service_times
        ]
        if times:
            yield group_key, group, times


def _service_day_key(value: str) -> int:
    """Sort ``HHMM`` within the service day, small hours counting as the tail."""
    hour = int(value[:2])
    return (hour + 24 if hour < 4 else hour) * 60 + int(value[2:])


def last_departures(station_id: str, today: date) -> dict[str, str]:
    """Return the last scheduled departure (``HHMM``) of the day, per group.

    Keys are ``"{line}|{direction}"`` like the timetable group keys, so
    realtime departures can be matched directly. Hours past midnight are
    stored wrapped (``0005`` means 00:05).
    """
    return {
        group_key: max(times, key=_service_day_key)
        for group_key, _group, times in _active_times(station_id, today)
    }


def build_timetable(station_id: str, today: date) -> dict[str, dict[str, Any]]:
    """Build the full timetable of a station for the given date.

    The returned shape matches what the Lovelace card expects::

        {group_key: {"ligne": {"numLigne": line, "direction": destination},
                     "direction_label": destination,
                     "horaires": {"HH": ["MM", ...]}}}
    """
    schedules: dict[str, dict[str, Any]] = {}

    for group_key, group, times in _active_times(station_id, today):
        horaires: dict[str, list[str]] = {}
        # Several services can run the same departure; show it once.
        for value in set(times):
            horaires.setdefault(value[:2], []).append(value[2:])
        for minutes in horaires.values():
            minutes.sort()

        destination = group.get("destination") or ""
        schedules[group_key] = {
            "ligne": {"numLigne": group.get("line", ""), "direction": destination},
            "direction_label": destination or f"Sens {group.get('direction', 1)}",
            "horaires": horaires,
        }

    return schedules
