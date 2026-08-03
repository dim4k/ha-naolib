"""Tests for the config and options flows."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.naolib.const import (
    CONF_LOCATION,
    CONF_QUAYS,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)

_LOCATION = {CONF_LOCATION: {"latitude": 47.2143, "longitude": -1.5595}}
_STOPS = [
    {"id": "STOP1", "name": "Commerce", "quays": ["QUAY1"], "distance": 42},
    {"id": "STOP2", "name": "Bouffay", "quays": ["QUAY2"], "distance": 300},
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
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await _search(hass, result["flow_id"], _STOPS)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_stop"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "STOP2"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Arrêt : Bouffay"
    assert result["data"] == {
        CONF_STOP_CODE: "STOP2",
        CONF_STOP_LABEL: "Bouffay",
        CONF_QUAYS: ["QUAY2"],
    }


async def test_no_stop_nearby(hass: HomeAssistant) -> None:
    """An empty search keeps the user on the location form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _search(hass, result["flow_id"], [])

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_stops_found"}


async def test_search_failure_is_reported(hass: HomeAssistant) -> None:
    """A failing lookup is surfaced instead of aborting the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await _search(hass, result["flow_id"], OSError("boom"))

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_already_configured_stop(hass: HomeAssistant) -> None:
    """The same stop cannot be added twice."""
    _entry("STOP1").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
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
