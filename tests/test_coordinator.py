"""Tests for the shared coordinator: stop registry and per-stop formatting."""

from datetime import timedelta
import logging
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util
import pytest

from custom_components.naolib.coordinator import (
    NaolibGlobalCoordinator,
    NaolibStop,
    build_stop_data,
    filter_departures,
)


def _stop(code: str = "STOP1", **kwargs) -> NaolibStop:
    return NaolibStop(
        code=code,
        name=f"Label {code}",
        quays=kwargs.pop("quays", ["QUAY1"]),
        interval=kwargs.pop("interval", 60),
        **kwargs,
    )


def _departures() -> list[dict[str, object]]:
    now = dt_util.now()
    return [
        {
            "line": "C3",
            "direction": 1,
            "expected_ts": (now + timedelta(minutes=2)).isoformat(),
        },
        {
            "line": "2",
            "direction": 2,
            "expected_ts": (now + timedelta(minutes=8)).isoformat(),
        },
        {
            "line": "c3",
            "direction": 2,
            "expected_ts": (now + timedelta(minutes=15)).isoformat(),
        },
    ]


def test_no_filter_returns_everything() -> None:
    """Without criteria the list is returned untouched."""
    departures = _departures()
    assert filter_departures(departures) == departures


def test_line_filter_is_case_insensitive() -> None:
    """Line numbers are compared without case, as users type them freely."""
    result = filter_departures(_departures(), lines=["c3"])
    assert [item["direction"] for item in result] == [1, 2]


def test_direction_and_limit() -> None:
    """Direction narrows the list and limit truncates it."""
    result = filter_departures(_departures(), direction=2, limit=1)
    assert len(result) == 1
    assert result[0]["line"] == "2"


def test_walk_time_drops_unreachable_departures() -> None:
    """A departure that leaves before the user can walk there is dropped."""
    result = filter_departures(_departures(), walk_minutes=10)
    assert [item["line"] for item in result] == ["c3"]


async def test_stop_registry_drives_quays_and_interval(hass: HomeAssistant) -> None:
    """Registered stops define what is polled, and how often."""
    coordinator = NaolibGlobalCoordinator(hass)

    coordinator.register_stop("entry1", _stop("STOP1", quays=["Q1"], interval=120))
    assert coordinator.update_interval == timedelta(seconds=120)

    coordinator.register_stop("entry2", _stop("STOP2", quays=["Q2"], interval=30))
    assert coordinator.update_interval == timedelta(seconds=30)
    assert coordinator.stop_by_code("STOP2").quays == ["Q2"]

    coordinator.unregister_stop("entry2")
    assert coordinator.stop_by_code("STOP2") is None
    assert coordinator.update_interval == timedelta(seconds=120)


def test_build_stop_data_keeps_only_the_stop_quays() -> None:
    """Departures of the rest of the network are ignored."""
    expected = (dt_util.now() + timedelta(minutes=5)).isoformat()
    raw = {
        "line": "C3",
        "destination": "Hôtel Dieu",
        "direction_name": "A",
        "vehicle_mode": "bus",
        "expected": expected,
        "aimed": expected,
    }

    data = build_stop_data({"QUAY1": [raw], "OTHER": [raw]}, _stop())

    assert len(data["next_departures"]) == 1
    departure = data["next_departures"][0]
    assert departure["type"] == 3
    assert departure["direction"] == 1
    assert departure["is_last"] is False
    assert data["next_departure_dt"] is not None


def test_build_stop_data_flags_the_last_scheduled_passage() -> None:
    """A departure matching the last theoretical time is flagged."""
    aimed = dt_util.now() + timedelta(minutes=5)
    stop = _stop(last_times={"C3|1": aimed.strftime("%H%M")})
    network = {
        "QUAY1": [
            {
                "line": "C3",
                "destination": "Hôtel Dieu",
                "direction_name": "A",
                "vehicle_mode": "bus",
                "expected": aimed.isoformat(),
                "aimed": aimed.isoformat(),
            }
        ]
    }

    data = build_stop_data(network, stop)

    assert data["next_departures"][0]["is_last"] is True


def _raw(minutes: float | None, **extra) -> dict[str, str]:
    raw = {"line": "C3", "destination": "X", **extra}
    if minutes is not None:
        raw["expected"] = (dt_util.now() + timedelta(minutes=minutes)).isoformat()
    return raw


def test_build_stop_data_skips_departures_without_a_usable_time() -> None:
    """A missing timestamp or a bus long gone is not shown."""
    network = {"QUAY1": [_raw(None), _raw(-5)]}

    assert build_stop_data(network, _stop())["next_departures"] == []
    assert build_stop_data(network, _stop())["next_departure_dt"] is None


def test_build_stop_data_humanizes_the_delay() -> None:
    """Imminent, minute-scale and hour-scale delays each get their own label."""
    network = {"QUAY1": [_raw(0.5), _raw(20.5), _raw(65.5)]}

    data = build_stop_data(network, _stop())
    times = [item["time"] for item in data["next_departures"]]

    assert times == ["proche", "20 mn", "1h05"]


def test_build_stop_data_defaults_unknown_mode_and_direction() -> None:
    """An unmapped vehicle mode is a bus, an unmapped direction is the first one."""
    network = {"QUAY1": [_raw(5, vehicle_mode="funicular", direction_name="?")]}

    departure = build_stop_data(network, _stop())["next_departures"][0]

    assert departure["type"] == 3
    assert departure["direction"] == 1
    assert departure["delay_minutes"] is None


async def test_update_fails_when_there_is_nothing_to_serve(hass: HomeAssistant) -> None:
    """A failure on the very first fetch surfaces as an update failure."""
    coordinator = NaolibGlobalCoordinator(hass)
    coordinator.register_stop("entry1", _stop())

    with (
        patch.object(coordinator.api, "async_get_all_departures", return_value=None),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


async def test_transient_failure_serves_the_last_snapshot(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """The last snapshot is kept, and the outage is logged once per episode."""
    caplog.set_level(logging.INFO)
    coordinator = NaolibGlobalCoordinator(hass)
    coordinator.register_stop("entry1", _stop())
    snapshot = {"QUAY1": []}
    coordinator.data = snapshot

    with patch.object(coordinator.api, "async_get_all_departures", return_value=None):
        assert await coordinator._async_update_data() is snapshot
        assert await coordinator._async_update_data() is snapshot

    assert caplog.text.count("is unavailable") == 1

    with (
        patch.object(
            coordinator.api, "async_get_all_departures", return_value=snapshot
        ),
        patch(
            "custom_components.naolib.coordinator.last_departures", return_value={}
        ) as last,
    ):
        assert await coordinator._async_update_data() is snapshot

    assert "available again" in caplog.text
    assert last.called
