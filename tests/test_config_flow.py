"""Tests for the config and options flows."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.naolib.bike import GbfsUnavailableError
from custom_components.naolib.const import (
    CONF_ENTRY_TYPE,
    CONF_LOCATION,
    CONF_QUAYS,
    CONF_STATION_ID,
    CONF_STATION_LABEL,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_BIKE,
    ENTRY_TYPE_STOP,
)

_LOCATION = {CONF_LOCATION: {"latitude": 47.2143, "longitude": -1.5595}}
_STOPS = [
    {"id": "STOP1", "name": "Commerce", "quays": ["QUAY1"], "distance": 42},
    {"id": "STOP2", "name": "Bouffay", "quays": ["QUAY2"], "distance": 300},
]
_STATIONS = [
    {"id": "1", "name": "PRÉFECTURE", "lat": 47.2198, "lon": -1.5548},
    {"id": "2", "name": "COMMERCE", "lat": 47.2143, "lon": -1.5595},
]


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Make the custom integration loadable from the repository."""


@pytest.fixture(autouse=True)
def _no_setup():
    """Keep the flows from actually setting the integration up."""
    with patch("custom_components.naolib.async_setup_entry", return_value=True):
        yield


def _entry(stop_code: str = "STOP1") -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=stop_code,
        title=f"Arrêt : {stop_code}",
        data={
            CONF_STOP_CODE: stop_code,
            CONF_STOP_LABEL: stop_code,
            CONF_QUAYS: ["QUAY1"],
        },
    )


async def _menu(hass: HomeAssistant, kind: str, step: str) -> dict:
    """Open the flow and walk down the two menus to a search form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": kind}
    )
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": step}
    )


async def _start(hass: HomeAssistant) -> dict:
    """Open the flow and pick the map search for a stop."""
    return await _menu(hass, "stop", "by_location")


async def _search(hass: HomeAssistant, flow_id: str, stops: list | Exception) -> dict:
    kwargs = (
        {"side_effect": stops}
        if isinstance(stops, Exception)
        else {"return_value": stops}
    )
    with patch("custom_components.naolib.config_flow.nearby_stops", **kwargs):
        return await hass.config_entries.flow.async_configure(flow_id, _LOCATION)


async def test_user_flow_creates_the_entry(hass: HomeAssistant) -> None:
    """Picking a location then a stop creates the entry."""
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "by_location"

    result = await _search(hass, result["flow_id"], _STOPS)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_stop"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "STOP2"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Arrêt : Bouffay"
    assert result["data"] == {
        CONF_ENTRY_TYPE: ENTRY_TYPE_STOP,
        CONF_STOP_CODE: "STOP2",
        CONF_STOP_LABEL: "Bouffay",
        CONF_QUAYS: ["QUAY2"],
    }


async def test_stop_list_creates_the_entry(hass: HomeAssistant) -> None:
    """The whole network is offered in one dropdown, sorted by name."""
    unsorted = [
        {"id": "STOP2", "name": "État", "quays": ["QUAY2"]},
        {"id": "STOP1", "name": "Commerce", "quays": ["QUAY1"]},
    ]

    with patch(
        "custom_components.naolib.config_flow.load_stops", return_value=unsorted
    ):
        result = await _menu(hass, "stop", "by_list")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_stop"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "STOP1"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_STOP_LABEL] == "Commerce"


async def test_stop_list_aborts_without_an_index(hass: HomeAssistant) -> None:
    """An unreadable stop index leaves nothing to pick from."""
    with patch("custom_components.naolib.config_flow.load_stops", return_value=[]):
        result = await _menu(hass, "stop", "by_list")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_stops_found"


async def test_no_stop_nearby(hass: HomeAssistant) -> None:
    """An empty search keeps the user on the location form."""
    result = await _start(hass)
    result = await _search(hass, result["flow_id"], [])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_stops_found"}


async def test_search_failure_is_reported(hass: HomeAssistant) -> None:
    """A failing lookup is surfaced instead of aborting the flow."""
    result = await _start(hass)
    result = await _search(hass, result["flow_id"], OSError("boom"))

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_already_configured_stop(hass: HomeAssistant) -> None:
    """The same stop cannot be added twice."""
    _entry("STOP1").add_to_hass(hass)

    result = await _start(hass)
    result = await _search(hass, result["flow_id"], _STOPS)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "STOP1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_updates_the_entry(hass: HomeAssistant) -> None:
    """Reconfiguring an entry moves it to another stop."""
    entry = _entry("STOP1")
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "by_location"}
    )
    result = await _search(hass, result["flow_id"], _STOPS)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "STOP2"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_STOP_CODE] == "STOP2"
    assert entry.unique_id == "STOP2"


async def test_reconfigure_rejects_a_stop_owned_by_another_entry(
    hass: HomeAssistant,
) -> None:
    """Two entries cannot end up on the same stop."""
    entry = _entry("STOP1")
    entry.add_to_hass(hass)
    _entry("STOP2").add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "by_location"}
    )
    result = await _search(hass, result["flow_id"], _STOPS)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "STOP2"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_STOP_CODE] == "STOP1"


async def test_options_flow_sets_the_update_interval(hass: HomeAssistant) -> None:
    """The options flow stores the polling interval."""
    entry = _entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_UPDATE_INTERVAL: 120}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_UPDATE_INTERVAL: 120}


def _bike_entry(station_id: str = "1") -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"bike_{station_id}",
        title=f"Station vélo : {station_id}",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_BIKE,
            CONF_STATION_ID: station_id,
            CONF_STATION_LABEL: station_id,
        },
    )


def _patch_stations(stations: list | Exception):
    kwargs = (
        {"side_effect": stations}
        if isinstance(stations, Exception)
        else {"return_value": stations}
    )
    return patch("custom_components.naolib.config_flow.async_fetch_stations", **kwargs)


async def test_bike_flow_creates_the_entry(hass: HomeAssistant) -> None:
    """Picking a location then a station creates a bike entry."""
    result = await _menu(hass, "bike", "bike_by_location")
    assert result["step_id"] == "bike_by_location"

    with _patch_stations(_STATIONS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _LOCATION
        )
    assert result["step_id"] == "select_station"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Station vélo : PRÉFECTURE"
    assert result["data"] == {
        CONF_ENTRY_TYPE: ENTRY_TYPE_BIKE,
        CONF_STATION_ID: "1",
        CONF_STATION_LABEL: "PRÉFECTURE",
    }


async def test_bike_list_creates_the_entry(hass: HomeAssistant) -> None:
    """Every station is offered in one dropdown, sorted by name."""
    with _patch_stations(_STATIONS):
        result = await _menu(hass, "bike", "bike_by_list")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_station"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "1"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_STATION_LABEL] == "PRÉFECTURE"


async def test_bike_list_aborts_when_the_feed_is_unreachable(
    hass: HomeAssistant,
) -> None:
    """Without the feed there is no list to pick from."""
    with _patch_stations(GbfsUnavailableError("boom")):
        result = await _menu(hass, "bike", "bike_by_list")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_bike_list_aborts_on_an_empty_feed(hass: HomeAssistant) -> None:
    """A feed describing no station leaves nothing to pick from."""
    with _patch_stations([]):
        result = await _menu(hass, "bike", "bike_by_list")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_stations_found"


async def test_no_station_nearby(hass: HomeAssistant) -> None:
    """An empty search keeps the user on the location form."""
    result = await _menu(hass, "bike", "bike_by_location")

    with _patch_stations([]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _LOCATION
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_stations_found"}


async def test_bike_feed_failure_is_reported(hass: HomeAssistant) -> None:
    """An unreachable GBFS feed is surfaced instead of aborting the flow."""
    result = await _menu(hass, "bike", "bike_by_location")

    with _patch_stations(GbfsUnavailableError("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _LOCATION
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_already_configured_station(hass: HomeAssistant) -> None:
    """The same station cannot be added twice."""
    _bike_entry("1").add_to_hass(hass)

    result = await _menu(hass, "bike", "bike_by_location")
    with _patch_stations(_STATIONS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _LOCATION
        )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_keeps_the_entry_kind(hass: HomeAssistant) -> None:
    """Reconfiguring a bike entry stays on the bike branch."""
    entry = _bike_entry("1")
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "bike"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "bike_by_location"}
    )
    with _patch_stations(_STATIONS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _LOCATION
        )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "2"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_STATION_ID] == "2"
    assert entry.unique_id == "bike_2"


async def test_reconfigure_rejects_a_station_owned_by_another_entry(
    hass: HomeAssistant,
) -> None:
    """Two entries cannot end up on the same station."""
    entry = _bike_entry("1")
    entry.add_to_hass(hass)
    _bike_entry("2").add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "bike_by_location"}
    )
    with _patch_stations(_STATIONS):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _LOCATION
        )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "2"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_STATION_ID] == "1"


async def test_reconfigure_of_a_legacy_stop_stays_on_the_stop_branch(
    hass: HomeAssistant,
) -> None:
    """An entry created before the bike support is still a stop."""
    entry = _entry("STOP1")
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "stop"
