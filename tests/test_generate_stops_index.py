"""Tests for the sanity checks of the embedded data generator."""

from pathlib import Path
import sqlite3

import pytest
from scripts.generate_stops_index import (
    _write_schedules,
    check_feed,
    stored_schedules,
)

_INDEX = [{"id": str(number)} for number in range(10)]
_SCHEDULES = {str(number): {"1|1": {}} for number in range(10)}
_CALENDAR = {
    "weekdays": {"end": "20270130", "added": []},
    "holiday": {"end": "", "added": ["20270214"]},
}


def _check(
    index: list[dict] = _INDEX,
    schedules: dict[str, dict] = _SCHEDULES,
    calendar: dict[str, dict] = _CALENDAR,
    previous_stations: int = 10,
    today: str = "20261114",
) -> None:
    check_feed(
        index, schedules, calendar, previous_stations=previous_stations, today=today
    )


def test_a_sound_feed_is_accepted() -> None:
    """A feed close to the shipped one, still running, goes through."""
    _check()
    # A first generation has nothing to be compared with.
    _check(previous_stations=0)
    # The last day of the calendar is still a day with service.
    _check(today="20270214")


def test_an_empty_feed_is_refused() -> None:
    """No station at all never ships, even on a first generation."""
    with pytest.raises(RuntimeError, match="no station"):
        _check(index=[], schedules={}, previous_stations=0)


def test_a_truncated_feed_is_refused() -> None:
    """Losing a large share of the stations is taken for a broken export."""
    with pytest.raises(RuntimeError, match="truncated"):
        _check(previous_stations=100)


def test_missing_timetables_are_refused() -> None:
    """Stations without their timetables would show empty days."""
    with pytest.raises(RuntimeError, match="timetable"):
        _check(schedules={"0": {"1|1": {}}})


def test_an_expired_calendar_is_refused() -> None:
    """A calendar already over would make every day look without service."""
    with pytest.raises(RuntimeError, match="calendar ends"):
        _check(today="20270215")
    with pytest.raises(RuntimeError, match="calendar ends"):
        _check(calendar={})


_TIMETABLES = {
    "STATION": {
        "C3|1": {
            "line": "C3",
            "destination": "Hôtel Dieu",
            "services": {"weekdays": ["0805", "0835"], "sunday": ["0905"]},
        }
    }
}


def test_stored_schedules_reads_back_what_was_written(tmp_path: Path) -> None:
    """An unchanged feed compares equal to the database, despite its date."""
    path = tmp_path / "schedules.sqlite"
    _write_schedules(path, _TIMETABLES)

    assert stored_schedules(path) == _TIMETABLES


def test_stored_schedules_cannot_reuse_another_database(tmp_path: Path) -> None:
    """A missing, unreadable or differently shaped database is written again."""
    path = tmp_path / "schedules.sqlite"
    assert stored_schedules(path) is None

    path.write_bytes(b"not a database")
    assert stored_schedules(path) is None

    path.unlink()
    _write_schedules(path, _TIMETABLES)
    connection = sqlite3.connect(path)
    connection.execute("UPDATE meta SET value = '0' WHERE key = 'format_version'")
    connection.commit()
    connection.close()
    assert stored_schedules(path) is None
