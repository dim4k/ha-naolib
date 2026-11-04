"""Tests for the repair moving a retired JCDecaux station to a Voi spot."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.naolib.bike import GbfsUnavailableError, retired_issue_id
from custom_components.naolib.const import (
    BIKE_PROVIDER_VOI,
    CONF_BIKE_PROVIDER,
    CONF_ENTRY_TYPE,
    CONF_LOCATION,
    CONF_STATION_ID,
    CONF_STATION_LABEL,
    DOMAIN,
    ENTRY_TYPE_BIKE,
)
from custom_components.naolib.repairs import async_create_fix_flow

_JCD_NETWORK = {
    "1": {
        "id": "1",
        "name": "Préfecture",
        "lat": 47.2198,
        "lon": -1.5548,
        "address": "Place du Port Communeau",
        "capacity": 33,
        "bikes": 7,
        "docks": 26,
        "is_installed": True,
        "is_renting": True,
        "is_returning": True,
        "last_reported": None,
    },
}

_VOI_NETWORK = {
    "v1": {
        "id": "v1",
        "name": "Préfecture · Centre-ville 012",
        "code": "NAN_CEN_012",
        "lat": 47.2197,
        "lon": -1.5550,
        "address": "",
        "capacity": 8,
        "bikes": 3,
        "docks": None,
        "is_installed": True,
        "is_renting": True,
        "is_returning": True,
        "last_reported": None,
        "vehicles": [{"range_km": 52, "disabled": False}],
    },
}

_SPOTS = [
    {
        "id": "v1",
        "name": "Préfecture · Centre-ville 012",
        "lat": 47.2197,
        "lon": -1.5550,
    },
    {
        "id": "v2",
        "name": "Cathédrale · Centre-ville 020",
        "lat": 47.2180,
        "lon": -1.5510,
    },
]

_UPDATE = "custom_components.naolib.bike.NaolibBikeCoordinator._async_update_data"
_FETCH = "custom_components.naolib.config_flow.async_fetch_stations"


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Make the custom integration loadable from the repository."""


async def _station(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a JCDecaux station, as configured before Voi."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="bike_1",
        title="Station vélo : Préfecture",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_BIKE,
            CONF_STATION_ID: "1",
            CONF_STATION_LABEL: "Préfecture",
        },
    )
    entry.add_to_hass(hass)
    with patch(_UPDATE, return_value=_JCD_NETWORK):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert await async_setup_component(hass, "repairs", {})
    return entry


def _raise(
    hass: HomeAssistant, entry_id: str, position: tuple[float, float] | None = None
) -> str:
    """Raise the repair of a retired station, as the coordinator does."""
    issue_id = retired_issue_id(entry_id)
    data: dict = {"entry_id": entry_id}
    if position:
        data["latitude"], data["longitude"] = position
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="bike_station_retired",
        translation_placeholders={"station": "Préfecture"},
        data=data,
    )
    return issue_id


def _flows(hass: HomeAssistant):
    return hass.data["repairs"]["flow_manager"]


async def _start(hass: HomeAssistant, issue_id: str) -> dict:
    # "issue_id" travels in the data on older releases, which newer ones accept.
    return await _flows(hass).async_init(DOMAIN, data={"issue_id": issue_id})


def _default_location(result: dict) -> dict:
    key = next(iter(result["data_schema"].schema))
    return key.default()


async def test_moving_a_retired_station_to_voi(hass: HomeAssistant) -> None:
    """The entry moves to the Voi spot and keeps its "bikes available" entity."""
    entry = await _station(hass)
    entity_registry = er.async_get(hass)
    bikes_entity = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "naolib_bike_1_bikes"
    )
    docks_entity = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "naolib_bike_1_docks"
    )
    assert bikes_entity and docks_entity
    issue_id = _raise(hass, entry.entry_id, (47.2198, -1.5548))

    result = await _start(hass, issue_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "location"
    assert result["description_placeholders"] == {"station": entry.title}
    assert _default_location(result) == {"latitude": 47.2198, "longitude": -1.5548}

    with patch(_FETCH, return_value=_SPOTS):
        result = await _flows(hass).async_configure(
            result["flow_id"],
            {CONF_LOCATION: {"latitude": 47.2198, "longitude": -1.5548}},
        )
    assert result["step_id"] == "select"

    with patch(_UPDATE, return_value=_VOI_NETWORK):
        result = await _flows(hass).async_configure(
            result["flow_id"], {CONF_STATION_ID: "v1"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.unique_id == "bike_voi_v1"
    assert entry.title == "Station vélo : Préfecture · Centre-ville 012"
    assert entry.data[CONF_BIKE_PROVIDER] == BIKE_PROVIDER_VOI
    assert entry.data[CONF_STATION_ID] == "v1"
    assert entry.runtime_data.feed.key == BIKE_PROVIDER_VOI

    # Same entity id, now fed by the Voi spot; the docks sensor is gone.
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "naolib_bike_voi_v1_bikes"
        )
        == bikes_entity
    )
    assert hass.states.get(bikes_entity).state == "3"
    assert entity_registry.async_get(docks_entity) is None
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, "naolib_bike_voi_v1_range"
    )

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "bike_voi_v1")})
    assert device is not None
    assert device.manufacturer == "Voi"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_the_map_starts_at_home_when_the_station_was_never_seen(
    hass: HomeAssistant,
) -> None:
    """Without the old position, the search starts from the home location."""
    entry = await _station(hass)
    issue_id = _raise(hass, entry.entry_id)

    result = await _start(hass, issue_id)

    assert _default_location(result) == {
        "latitude": hass.config.latitude,
        "longitude": hass.config.longitude,
    }


@pytest.mark.parametrize(
    ("fetched", "error"),
    [
        (GbfsUnavailableError("boom"), "cannot_connect"),
        ([], "no_stations_found"),
    ],
)
async def test_the_search_reports_its_failures(
    hass: HomeAssistant, fetched: list | Exception, error: str
) -> None:
    """An unreachable feed or an empty area keeps the user on the map."""
    entry = await _station(hass)
    result = await _start(hass, _raise(hass, entry.entry_id))

    kwargs = (
        {"side_effect": fetched}
        if isinstance(fetched, Exception)
        else {"return_value": fetched}
    )
    with patch(_FETCH, **kwargs):
        result = await _flows(hass).async_configure(
            result["flow_id"],
            {CONF_LOCATION: {"latitude": 47.2198, "longitude": -1.5548}},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "location"
    assert result["errors"] == {"base": error}


async def _at_selection(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    result = await _start(hass, _raise(hass, entry.entry_id))
    with patch(_FETCH, return_value=_SPOTS):
        return await _flows(hass).async_configure(
            result["flow_id"],
            {CONF_LOCATION: {"latitude": 47.2198, "longitude": -1.5548}},
        )


async def test_a_value_outside_the_list_is_rejected(hass: HomeAssistant) -> None:
    """The picker accepts free text, which is sent back with an error."""
    entry = await _station(hass)
    result = await _at_selection(hass, entry)

    result = await _flows(hass).async_configure(
        result["flow_id"], {CONF_STATION_ID: "Nowhere"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "not_in_list"}


async def test_a_spot_tracked_by_another_entry_is_refused(
    hass: HomeAssistant,
) -> None:
    """Two entries cannot end up on the same Voi spot."""
    entry = await _station(hass)
    MockConfigEntry(domain=DOMAIN, unique_id="bike_voi_v1", data={}).add_to_hass(hass)
    result = await _at_selection(hass, entry)

    result = await _flows(hass).async_configure(
        result["flow_id"], {CONF_STATION_ID: "v1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.unique_id == "bike_1"


async def test_an_entry_removed_meanwhile_aborts_the_flow(
    hass: HomeAssistant,
) -> None:
    """The station may be deleted while the repair is open."""
    entry = await _station(hass)
    result = await _at_selection(hass, entry)
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    result = await _flows(hass).async_configure(
        result["flow_id"], {CONF_STATION_ID: "v1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_removed"


async def test_an_issue_for_a_missing_entry_aborts(hass: HomeAssistant) -> None:
    """A repair left over from a deleted entry has nothing to fix."""
    await _station(hass)

    result = await _start(hass, _raise(hass, "gone"))

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_removed"


async def test_a_fix_flow_without_data_aborts(hass: HomeAssistant) -> None:
    """An issue stored without data cannot point at any entry."""
    flow = await async_create_fix_flow(hass, "whatever", None)
    flow.hass = hass

    result = await flow.async_step_init()

    assert result["type"] is FlowResultType.ABORT
