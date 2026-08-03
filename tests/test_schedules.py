"""Tests for the embedded GTFS timetables."""

from contextlib import contextmanager
from datetime import date
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from custom_components.naolib import schedules

_GROUPS = {
    "C3|1": {
        "line": "C3",
        "direction": 1,
        "destination": "Hôtel Dieu",
        "services": {"S1": ["0730", "0745"], "S2": ["2350"], "S3": ["0010"]},
    },
    "2|2": {
        "line": "2",
        "direction": 2,
        "destination": "",
        "services": {"S1": ["0800"]},
    },
}


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    """Start each test from a clean slate: the loaders are cached."""
    schedules.load_calendar.cache_clear()
    schedules.load_station_timetable.cache_clear()
    schedules.active_services.cache_clear()


@contextmanager
def _timetable(*active: str):
    """Serve the synthetic groups above, with only ``active`` running today."""
    with (
        patch.object(schedules, "load_station_timetable", return_value=_GROUPS),
        patch.object(schedules, "active_services", return_value=frozenset(active)),
    ):
        yield


def test_load_station_timetable_returns_trips() -> None:
    """A known station of the shipped database exposes its trips."""
    timetable = schedules.load_station_timetable("FR_NAOLIB:StopPlace:1")

    assert timetable
    first = next(iter(timetable.values()))
    assert {"line", "direction", "destination", "services"} <= set(first)


def test_load_station_timetable_unknown_station() -> None:
    """An unknown station yields an empty timetable rather than an error."""
    assert schedules.load_station_timetable("FR_NAOLIB:StopPlace:does-not-exist") == {}


def test_missing_data_files_are_tolerated(tmp_path) -> None:
    """A stripped-down install degrades to empty data instead of crashing."""
    with patch.object(schedules, "_BASE_PATH", tmp_path):
        assert schedules.load_calendar() == {}
        assert schedules.load_station_timetable("whatever") == {}


def test_unreadable_database_is_tolerated() -> None:
    """A database error is logged and yields an empty timetable."""
    with patch.object(sqlite3, "connect", side_effect=sqlite3.Error("boom")):
        assert schedules.load_station_timetable("whatever") == {}


def test_corrupt_payload_is_tolerated() -> None:
    """A row that is not valid compressed JSON yields an empty timetable."""
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (b"not-compressed",)
    with patch.object(sqlite3, "connect", return_value=connection):
        assert schedules.load_station_timetable("whatever") == {}


def test_active_services_are_cached_per_day() -> None:
    """The service list is computed once per date and is non-empty on a weekday."""
    services = schedules.active_services(date(2024, 1, 3))  # a Wednesday

    assert isinstance(services, frozenset)
    assert schedules.active_services(date(2024, 1, 3)) is services


def test_active_services_applies_the_calendar_rules() -> None:
    """Regular days, added dates and removed dates are all honoured."""
    calendar = {
        "REGULAR": {
            "days": [1, 1, 1, 1, 1, 0, 0],
            "start": "20240101",
            "end": "20241231",
        },
        "OUT_OF_RANGE": {
            "days": [1, 1, 1, 1, 1, 1, 1],
            "start": "20250101",
            "end": "20251231",
        },
        "REMOVED": {
            "days": [1, 1, 1, 1, 1, 1, 1],
            "start": "20240101",
            "end": "20241231",
            "removed": ["20240103"],
        },
        "ADDED": {"days": [], "added": ["20240103"]},
    }
    with patch.object(schedules, "load_calendar", return_value=calendar):
        services = schedules.active_services(date(2024, 1, 3))

    assert services == frozenset({"REGULAR", "ADDED"})


def test_last_departures_wraps_past_midnight() -> None:
    """A departure just after midnight is the tail of the service day."""
    with _timetable("S1", "S3"):
        last = schedules.last_departures("STATION", date(2024, 1, 3))

    assert last == {"C3|1": "0010", "2|2": "0800"}


def test_build_timetable_groups_departures_by_hour() -> None:
    """Times are grouped by hour, and the destination labels the group."""
    with _timetable("S1"):
        timetable = schedules.build_timetable("STATION", date(2024, 1, 3))

    assert timetable["C3|1"]["horaires"] == {"07": ["30", "45"]}
    assert timetable["C3|1"]["direction_label"] == "Hôtel Dieu"
    assert timetable["C3|1"]["ligne"] == {"numLigne": "C3", "direction": "Hôtel Dieu"}
    # No destination in the feed: fall back to the direction number.
    assert timetable["2|2"]["direction_label"] == "Sens 2"


def test_groups_without_service_today_are_skipped() -> None:
    """A line that does not run today is left out entirely."""
    with _timetable():
        assert schedules.build_timetable("STATION", date(2024, 1, 3)) == {}
        assert schedules.last_departures("STATION", date(2024, 1, 3)) == {}


def test_build_timetable_groups_by_line_and_direction() -> None:
    """Group keys follow the ``line|direction`` format used by the card."""
    timetable = schedules.build_timetable("FR_NAOLIB:StopPlace:1", date(2024, 1, 3))

    for key, group in timetable.items():
        line, direction = key.split("|")
        assert group["ligne"]["numLigne"] == line
        assert direction in {"1", "2"}
        assert group["horaires"]
