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
    CONF_EXCLUDED_STOPS,
    CONF_LOCATION,
    CONF_MAX_STOPS,
    CONF_QUAYS,
    CONF_RADIUS,
    CONF_SOURCE_ENTITY,
    CONF_STATION_ID,
    CONF_STATION_LABEL,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    CONF_UPDATE_INTERVAL,
    CONF_ZONE,
    DOMAIN,
    ENTRY_TYPE_AROUND,
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
    return await _skip_zone(hass, await _menu(hass, "stop", "by_location"))


async def _skip_zone(hass: HomeAssistant, result: dict) -> dict:
    """Leave the zone page empty, so the map opens at home."""
    return await hass.config_entries.flow.async_configure(result["flow_id"], {})


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
    assert result["step_id"] == "by_location_map"

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
    result = await _skip_zone(hass, result)
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
    result = await _skip_zone(hass, result)
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


def _around_entry(entity_id: str = "person.me") -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"around_{entity_id}",
        title=f"Autour de : {entity_id}",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_AROUND,
            CONF_SOURCE_ENTITY: entity_id,
            CONF_RADIUS: 500,
            CONF_MAX_STOPS: 5,
        },
    )


async def test_around_flow_creates_the_entry(hass: HomeAssistant) -> None:
    """Picking a tracked entity creates an "around me" entry."""
    hass.states.async_set(
        "person.me", "home", {"friendly_name": "Me", "latitude": 1.0, "longitude": 2.0}
    )

    result = await _menu(hass, "stop", "around")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "around"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SOURCE_ENTITY: "person.me", CONF_RADIUS: 600, CONF_MAX_STOPS: 3},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Autour de : Me"
    assert result["data"] == {
        CONF_ENTRY_TYPE: ENTRY_TYPE_AROUND,
        CONF_SOURCE_ENTITY: "person.me",
        CONF_RADIUS: 600,
        CONF_MAX_STOPS: 3,
        CONF_EXCLUDED_STOPS: [],
    }


_NEARBY = [
    {"id": "STOP1", "name": "Commerce", "quays": ["QUAY1"], "distance": 42},
    {"id": "STOP2", "name": "Bouffay", "quays": ["QUAY2"], "distance": 300},
    {"id": "STOP3", "name": "Duchesse Anne", "quays": ["QUAY3"], "distance": 450},
]


async def _around_with_stops(hass: HomeAssistant, flow_id: str, entity: str) -> dict:
    """Submit the first "around me" page with stops found in the radius."""
    with patch(
        "custom_components.naolib.config_flow.stops_within", return_value=_NEARBY
    ) as search:
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            {CONF_SOURCE_ENTITY: entity, CONF_RADIUS: 500, CONF_MAX_STOPS: 5},
        )
    search.assert_called_once_with(47.2143, -1.5595, 500, 15)
    return result


async def test_around_lets_the_user_remove_stops(hass: HomeAssistant) -> None:
    """The stops in the radius are offered, all ticked; unticked ones are excluded."""
    hass.states.async_set(
        "person.me",
        "home",
        {"friendly_name": "Me", "latitude": 47.2143, "longitude": -1.5595},
    )
    result = await _menu(hass, "stop", "around")
    result = await _around_with_stops(hass, result["flow_id"], "person.me")

    assert result["step_id"] == "around_stops"
    assert result["data_schema"]({}) == {"stops": ["STOP1", "STOP2", "STOP3"]}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"stops": ["STOP1", "STOP3"]}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_EXCLUDED_STOPS] == ["STOP2"]


async def test_around_reconfigure_keeps_the_exclusions(hass: HomeAssistant) -> None:
    """Reconfiguring shows past exclusions unticked and keeps far-away ones."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="around_person.me",
        title="Autour de : person.me",
        data={
            **_around_entry("person.me").data,
            CONF_EXCLUDED_STOPS: ["STOP2", "FAR_AWAY"],
        },
    )
    entry.add_to_hass(hass)
    hass.states.async_set(
        "person.me", "home", {"latitude": 47.2143, "longitude": -1.5595}
    )

    result = await entry.start_reconfigure_flow(hass)
    result = await _around_with_stops(hass, result["flow_id"], "person.me")
    assert result["data_schema"]({}) == {"stops": ["STOP1", "STOP3"]}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"stops": ["STOP1", "STOP2"]}
    )

    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_EXCLUDED_STOPS] == ["FAR_AWAY", "STOP3"]


async def test_around_with_an_unknown_entity_skips_the_stops(
    hass: HomeAssistant,
) -> None:
    """Without a state there is no position, so the entry is created directly."""
    result = await _menu(hass, "stop", "around")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SOURCE_ENTITY: "person.ghost", CONF_RADIUS: 500, CONF_MAX_STOPS: 5},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Autour de : person.ghost"
    assert result["data"][CONF_EXCLUDED_STOPS] == []


async def test_around_reconfigure_updates_the_entry(hass: HomeAssistant) -> None:
    """Reconfiguring an "around me" entry moves it to another entity."""
    entry = _around_entry("person.me")
    entry.add_to_hass(hass)
    hass.states.async_set(
        "person.other", "home", {"friendly_name": "Other", "latitude": 1.0}
    )

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "around"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SOURCE_ENTITY: "person.other", CONF_RADIUS: 400, CONF_MAX_STOPS: 2},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SOURCE_ENTITY] == "person.other"
    assert entry.unique_id == "around_person.other"


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
    result = await _skip_zone(hass, await _menu(hass, "bike", "bike_by_location"))
    assert result["step_id"] == "bike_by_location_map"

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
    result = await _skip_zone(hass, await _menu(hass, "bike", "bike_by_location"))

    with _patch_stations([]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _LOCATION
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_stations_found"}


async def test_bike_feed_failure_is_reported(hass: HomeAssistant) -> None:
    """An unreachable GBFS feed is surfaced instead of aborting the flow."""
    result = await _skip_zone(hass, await _menu(hass, "bike", "bike_by_location"))

    with _patch_stations(GbfsUnavailableError("boom")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], _LOCATION
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_already_configured_station(hass: HomeAssistant) -> None:
    """The same station cannot be added twice."""
    _bike_entry("1").add_to_hass(hass)

    result = await _skip_zone(hass, await _menu(hass, "bike", "bike_by_location"))
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
    result = await _skip_zone(hass, result)
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
    result = await _skip_zone(hass, result)
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


def _set_zone(hass: HomeAssistant, entity_id: str = "zone.home", **coords) -> None:
    """Create a zone state, centred on Bouffay unless told otherwise."""
    attributes = {"latitude": 47.2150, "longitude": -1.5530, "radius": 100}
    attributes.update(coords)
    hass.states.async_set(entity_id, "0", attributes)


async def _zone_page(hass: HomeAssistant, kind: str = "stop") -> dict:
    """Open the position page of a stop or bike flow."""
    step = "by_location" if kind == "stop" else "bike_by_location"
    return await _menu(hass, kind, step)


async def test_the_zone_page_comes_first(hass: HomeAssistant) -> None:
    """Searching around a location starts with a zone, home suggested."""
    _set_zone(hass)
    result = await _zone_page(hass)

    assert result["step_id"] == "by_location"
    key = next(iter(result["data_schema"].schema))
    assert key == CONF_ZONE
    assert key.description == {"suggested_value": "zone.home"}


async def test_a_zone_centres_the_map(hass: HomeAssistant) -> None:
    """The map opens on the centre of the zone picked before."""
    _set_zone(hass)
    result = await _zone_page(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ZONE: "zone.home"}
    )

    assert result["step_id"] == "by_location_map"
    assert result["data_schema"]({})[CONF_LOCATION] == {
        "latitude": 47.2150,
        "longitude": -1.5530,
    }


async def test_without_a_zone_the_map_opens_at_home(hass: HomeAssistant) -> None:
    """Leaving the zone empty opens the map on the home location."""
    result = await _start(hass)

    assert result["data_schema"]({})[CONF_LOCATION] == {
        "latitude": hass.config.latitude,
        "longitude": hass.config.longitude,
    }


async def test_zone_search_creates_the_entry(hass: HomeAssistant) -> None:
    """Confirming the map opened on a zone searches from the marker."""
    _set_zone(hass)
    result = await _zone_page(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ZONE: "zone.home"}
    )

    with patch(
        "custom_components.naolib.config_flow.nearby_stops", return_value=_STOPS
    ) as search:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], result["data_schema"]({})
        )
    search.assert_called_once_with(47.2150, -1.5530)
    assert result["step_id"] == "select_stop"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "Commerce (42 m)"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_STOP_CODE] == "STOP1"


@pytest.mark.parametrize("kind", ["stop", "bike"])
@pytest.mark.parametrize("attributes", [{}, None])
async def test_a_zone_without_coordinates_is_reported(
    hass: HomeAssistant, kind: str, attributes: dict | None
) -> None:
    """A zone without coordinates, or gone, keeps the user on the zone page."""
    if attributes is not None:
        hass.states.async_set("zone.nowhere", "0", attributes)
    result = await _zone_page(hass, kind)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ZONE: "zone.nowhere"}
    )

    assert result["step_id"] == (
        "by_location" if kind == "stop" else "bike_by_location"
    )
    assert result["errors"] == {"base": "zone_without_location"}


async def test_a_zone_centres_the_bike_map(hass: HomeAssistant) -> None:
    """The bike flow opens its map on the zone too."""
    _set_zone(hass)
    result = await _zone_page(hass, "bike")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ZONE: "zone.home"}
    )

    assert result["step_id"] == "bike_by_location_map"
    assert result["data_schema"]({})[CONF_LOCATION] == {
        "latitude": 47.2150,
        "longitude": -1.5530,
    }


async def test_options_show_labels_as_values(hass: HomeAssistant) -> None:
    """The picker shows the raw value once picked, so values are the labels."""
    result = await _start(hass)
    result = await _search(hass, result["flow_id"], _STOPS)

    selector = next(iter(result["data_schema"].schema.values()))
    assert [option["value"] for option in selector.config["options"]] == [
        "Commerce (42 m)",
        "Bouffay (300 m)",
    ]
    assert all(
        option["value"] == option["label"] for option in selector.config["options"]
    )


async def test_homonym_stops_get_their_number(hass: HomeAssistant) -> None:
    """Stops sharing a name are told apart by their number."""
    homonyms = [
        {"id": "FR_NAOLIB:StopPlace:152", "name": "Pinier", "quays": ["Q1"]},
        {"id": "FR_NAOLIB:StopPlace:1076", "name": "Pinier", "quays": ["Q2"]},
    ]
    with patch(
        "custom_components.naolib.config_flow.load_stops", return_value=homonyms
    ):
        result = await _menu(hass, "stop", "by_list")

    selector = next(iter(result["data_schema"].schema.values()))
    assert [option["value"] for option in selector.config["options"]] == [
        "Pinier, n°152",
        "Pinier, n°1076",
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "Pinier, n°1076"}
    )
    assert result["data"][CONF_STOP_CODE] == "FR_NAOLIB:StopPlace:1076"


async def test_the_selection_list_is_searchable(hass: HomeAssistant) -> None:
    """``custom_value`` makes the frontend render a type-to-filter picker."""
    result = await _start(hass)
    result = await _search(hass, result["flow_id"], _STOPS)

    selector = next(iter(result["data_schema"].schema.values()))
    assert selector.config["custom_value"] is True


async def test_typed_text_must_match_a_stop(hass: HomeAssistant) -> None:
    """Free text that is not one of the stops is sent back with an error."""
    result = await _start(hass)
    result = await _search(hass, result["flow_id"], _STOPS)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "Ai"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_stop"
    assert result["errors"] == {"base": "not_in_list"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STOP_CODE: "STOP2"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_typed_text_must_match_a_station(hass: HomeAssistant) -> None:
    """Free text that is not one of the stations is sent back with an error."""
    with _patch_stations(_STATIONS):
        result = await _menu(hass, "bike", "bike_by_list")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_STATION_ID: "nowhere"}
    )
    assert result["step_id"] == "select_station"
    assert result["errors"] == {"base": "not_in_list"}
