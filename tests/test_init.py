"""Tests for the entry lifecycle and the get_departures action."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.naolib.const import (
    ATTR_CONFIG_ENTRY_ID,
    CONF_ENTRY_TYPE,
    CONF_QUAYS,
    CONF_STATION_ID,
    CONF_STATION_LABEL,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_BIKE,
    SERVICE_GET_DEPARTURES,
)
from custom_components.naolib.diagnostics import async_get_config_entry_diagnostics


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Make the custom integration loadable from the repository."""


def _entry(stop_code: str = "STOP1", quay: str = "QUAY1") -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=stop_code,
        title=f"Arrêt {stop_code}",
        data={
            CONF_STOP_CODE: stop_code,
            CONF_STOP_LABEL: f"Label {stop_code}",
            CONF_QUAYS: [quay],
        },
    )


def _network(quay: str = "QUAY1") -> dict[str, list[dict[str, str]]]:
    expected = (dt_util.now() + timedelta(minutes=5)).isoformat()
    return {
        quay: [
            {
                "line": "C3",
                "destination": "Hôtel Dieu",
                "direction_name": "A",
                "vehicle_mode": "bus",
                "expected": expected,
                "aimed": expected,
            }
        ]
    }


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.naolib.coordinator.NaolibApiClient"
            ".async_get_all_departures",
            return_value=_network(),
        ),
        patch("custom_components.naolib.coordinator.last_departures", return_value={}),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """A stop is registered on setup and dropped on unload."""
    entry = _entry()
    await _setup(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    coordinator = hass.data[DOMAIN].coordinator
    stop = coordinator.stops[entry.entry_id]
    assert stop.code == "STOP1"
    assert stop.quays == ["QUAY1"]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert coordinator.stops == {}


async def test_entries_share_one_coordinator(hass: HomeAssistant) -> None:
    """A second stop reuses the coordinator instead of polling on its own."""
    first = _entry("STOP1", "QUAY1")
    second = _entry("STOP2", "QUAY2")
    await _setup(hass, first)
    await _setup(hass, second)

    assert first.runtime_data is second.runtime_data
    assert len(first.runtime_data.stops) == 2


async def test_get_departures_action(hass: HomeAssistant) -> None:
    """The action returns the departures of the targeted entry."""
    entry = _entry()
    await _setup(hass, entry)

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DEPARTURES,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
        blocking=True,
        return_response=True,
    )

    assert response["stop_code"] == "STOP1"
    assert response["stop_label"] == "Label STOP1"
    assert [item["line"] for item in response["departures"]] == ["C3"]


async def test_sensor_exposes_the_departures(hass: HomeAssistant) -> None:
    """The sensor publishes the stop identity and its formatted departures."""
    entry = _entry()
    await _setup(hass, entry)

    states = [
        state
        for state in hass.states.async_all("sensor")
        if state.attributes.get("stop_code") == "STOP1"
    ]
    assert len(states) == 1
    assert states[0].attributes["stop_label"] == "Label STOP1"
    assert len(states[0].attributes["next_departures"]) == 1


async def test_setup_fails_without_a_stop_code(hass: HomeAssistant) -> None:
    """An entry with no stop code cannot be served."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="Broken")
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_legacy_entry_is_backfilled(hass: HomeAssistant) -> None:
    """An entry predating unique ids and quays is still set up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Legacy",
        data={CONF_STOP_CODE: "STOP1", CONF_STOP_LABEL: "Label STOP1"},
    )
    await _setup(hass, entry)

    assert entry.unique_id == "STOP1"
    assert entry.runtime_data.stops[entry.entry_id].quays == []


async def test_changing_the_options_reloads_the_entry(hass: HomeAssistant) -> None:
    """The polling interval is applied without restarting Home Assistant."""
    entry = _entry()
    await _setup(hass, entry)

    with (
        patch(
            "custom_components.naolib.coordinator.NaolibApiClient"
            ".async_get_all_departures",
            return_value=_network(),
        ),
        patch("custom_components.naolib.coordinator.last_departures", return_value={}),
    ):
        hass.config_entries.async_update_entry(
            entry, options={CONF_UPDATE_INTERVAL: 120}
        )
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.update_interval == timedelta(seconds=120)


async def test_action_rejects_an_unknown_entry(hass: HomeAssistant) -> None:
    """Targeting an entry that does not exist is a user error."""
    await _setup(hass, _entry())

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_DEPARTURES,
            {ATTR_CONFIG_ENTRY_ID: "does-not-exist"},
            blocking=True,
            return_response=True,
        )


async def test_action_rejects_an_unloaded_entry(hass: HomeAssistant) -> None:
    """Targeting a disabled entry is a user error too."""
    entry = _entry()
    await _setup(hass, entry)
    await hass.config_entries.async_unload(entry.entry_id)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_DEPARTURES,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
            blocking=True,
            return_response=True,
        )


async def test_websocket_returns_the_departures_and_the_timetable(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """The card fetches the full timetable on demand over the WebSocket."""
    await _setup(hass, _entry())
    client = await hass_ws_client(hass)

    with patch("custom_components.naolib.build_timetable", return_value={"C3|1": {}}):
        await client.send_json_auto_id(
            {"type": "naolib/get_data", "stop_code": "STOP1"}
        )
        response = await client.receive_json()

    assert response["success"]
    assert response["result"]["schedules"] == {"C3|1": {}}
    assert len(response["result"]["next_departures"]) == 1


async def test_websocket_serves_the_timetable_of_a_following_day(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """The card browses the next days by passing a day offset."""
    await _setup(hass, _entry())
    client = await hass_ws_client(hass)

    with patch(
        "custom_components.naolib.build_timetable", return_value={}
    ) as build_timetable:
        await client.send_json_auto_id(
            {"type": "naolib/get_data", "stop_code": "STOP1", "day_offset": 2}
        )
        response = await client.receive_json()

    expected = dt_util.now().date() + timedelta(days=2)
    assert response["success"]
    assert response["result"]["schedules_date"] == expected.isoformat()
    assert build_timetable.call_args.args[1] == expected


async def test_websocket_rejects_a_day_offset_out_of_range(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """Only the days the embedded calendar covers can be requested."""
    await _setup(hass, _entry())
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "naolib/get_data", "stop_code": "STOP1", "day_offset": 30}
    )
    response = await client.receive_json()

    assert not response["success"]


async def test_websocket_rejects_an_unknown_stop(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """A stop code that is not configured is reported as an error."""
    await _setup(hass, _entry())
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "naolib/get_data", "stop_code": "NOPE"})
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "stop_not_found"


async def test_diagnostics(hass: HomeAssistant) -> None:
    """Diagnostics report the entry, the coordinator and how the card is served."""
    entry = _entry()
    await _setup(hass, entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"][CONF_STOP_CODE] == "STOP1"
    assert diagnostics["coordinator"]["indexed_quays"] == 1
    assert diagnostics["coordinator"]["total_departures"] == 1
    assert diagnostics["frontend"]["loader_url"].startswith("/naolib_static/")


_BIKE_NETWORK = {
    "1": {
        "id": "1",
        "name": "PRÉFECTURE",
        "lat": 47.21984,
        "lon": -1.554891,
        "address": "Place du Port Communeau",
        "capacity": 33,
        "bikes": 7,
        "docks": 26,
        "is_installed": True,
        "is_renting": True,
        "is_returning": True,
        "last_reported": "2026-08-05T10:02:04Z",
    },
    "2": {
        "id": "2",
        "name": "COMMERCE",
        "lat": 47.2143,
        "lon": -1.5595,
        "address": "",
        "capacity": 20,
        "bikes": 0,
        "docks": 20,
        "is_installed": True,
        "is_renting": False,
        "is_returning": True,
        "last_reported": "2026-08-05T10:03:00Z",
    },
}


def _bike_entry(station_id: str = "1") -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"bike_{station_id}",
        title=f"Station vélo : {station_id}",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_BIKE,
            CONF_STATION_ID: station_id,
            CONF_STATION_LABEL: f"Station {station_id}",
        },
    )


async def _setup_bike(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    with patch(
        "custom_components.naolib.bike.NaolibBikeCoordinator._async_update_data",
        return_value=_BIKE_NETWORK,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def test_bike_setup_and_unload(hass: HomeAssistant) -> None:
    """A station is registered on setup and dropped on unload."""
    entry = _bike_entry()
    await _setup_bike(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    coordinator = hass.data[DOMAIN].bike_coordinator
    assert coordinator.stations[entry.entry_id].id == "1"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert coordinator.stations == {}


async def test_bike_setup_fails_without_a_station_id(hass: HomeAssistant) -> None:
    """An entry with no station id cannot be served."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_BIKE}, title="Broken"
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_bike_sensors_expose_the_station(hass: HomeAssistant) -> None:
    """Both sensors publish the station identity and its counters."""
    await _setup_bike(hass, _bike_entry())

    states = [
        state
        for state in hass.states.async_all("sensor")
        if state.attributes.get("station_id") == "1"
    ]
    assert len(states) == 2

    bikes = next(state for state in states if "nearby_stations" in state.attributes)
    assert bikes.state == "7"
    assert bikes.attributes["station_label"] == "PRÉFECTURE"
    assert bikes.attributes["docks_available"] == 26
    assert bikes.attributes["capacity"] == 33
    assert [
        station["station_id"] for station in bikes.attributes["nearby_stations"]
    ] == ["2"]

    docks = next(state for state in states if "nearby_stations" not in state.attributes)
    assert docks.state == "26"
    assert docks.attributes["capacity"] == 33


async def test_bike_entries_share_one_coordinator(hass: HomeAssistant) -> None:
    """A second station reuses the coordinator instead of polling on its own."""
    first = _bike_entry("1")
    second = _bike_entry("2")
    await _setup_bike(hass, first)
    await _setup_bike(hass, second)

    assert first.runtime_data is second.runtime_data
    assert len(first.runtime_data.stations) == 2


async def test_action_rejects_a_bike_entry(hass: HomeAssistant) -> None:
    """get_departures only makes sense for a stop."""
    entry = _bike_entry()
    await _setup_bike(hass, entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_DEPARTURES,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
            blocking=True,
            return_response=True,
        )


async def test_bike_diagnostics(hass: HomeAssistant) -> None:
    """Diagnostics report the bike snapshot instead of the departures one."""
    entry = _bike_entry()
    await _setup_bike(hass, entry)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["data"][CONF_STATION_ID] == "1"
    assert diagnostics["coordinator"]["indexed_stations"] == 2
    assert diagnostics["coordinator"]["total_bikes_available"] == 7
    assert diagnostics["coordinator"]["total_docks_available"] == 46
