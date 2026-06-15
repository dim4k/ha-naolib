"""Embedded theoretical timetable helpers (offline, GTFS-derived).

The real-time SIRI API only returns the next few departures, so the full daily
timetable is generated from the GTFS feed by ``scripts/generate_stops_index.py``
and shipped with the integration. A single ``data/schedules.json`` holds every
station's timetable and a shared ``data/calendar.json`` describes which GTFS
services run on a given date (regular days + exceptions).
"""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from .const import CALENDAR_FILE, SCHEDULES_FILE

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


@lru_cache(maxsize=1)
def load_schedules() -> dict[str, dict[str, Any]]:
    """Load every station's timetable (cached).

    This performs blocking file IO and must be called from an executor.
    """
    path = _BASE_PATH / SCHEDULES_FILE
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_station_timetable(station_id: str) -> dict[str, dict[str, Any]]:
    """Return the timetable of a station, or an empty mapping if missing."""
    return load_schedules().get(station_id, {})


def active_services(calendar: dict[str, dict[str, Any]], today: date) -> set[str]:
    """Return the set of GTFS service ids running on ``today``."""
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
    return services


def build_timetable(station_id: str, today: date) -> dict[str, dict[str, Any]]:
    """Build the full timetable of a station for the given date.

    The returned shape matches what the Lovelace card expects::

        {group_key: {"ligne": {"numLigne": line, "direction": destination},
                     "direction_label": destination,
                     "horaires": {"HH": ["MM", ...]}}}
    """
    groups = load_station_timetable(station_id)
    if not groups:
        return {}

    services = active_services(load_calendar(), today)
    schedules: dict[str, dict[str, Any]] = {}

    for group_key, group in groups.items():
        times: set[str] = set()
        for service_id, service_times in group.get("services", {}).items():
            if service_id in services:
                times.update(service_times)
        if not times:
            continue

        horaires: dict[str, list[str]] = {}
        for value in times:
            horaires.setdefault(value[:2], []).append(value[2:])
        for minutes in horaires.values():
            minutes.sort()

        line = group.get("line", "")
        direction = group.get("direction", 1)
        destination = group.get("destination") or ""
        schedules[group_key] = {
            "ligne": {"numLigne": line, "direction": destination},
            "direction_label": destination or f"Sens {direction}",
            "horaires": horaires,
        }

    return schedules
