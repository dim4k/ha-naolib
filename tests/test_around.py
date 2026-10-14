"""Tests for the "around me" dynamic controller."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.naolib import async_remove_config_entry_device
from custom_components.naolib.const import (
    AROUND_DEBOUNCE,
    CONF_ENTRY_TYPE,
    CONF_EXCLUDED_STOPS,
    CONF_MAX_STOPS,
    CONF_QUAYS,
    CONF_RADIUS,
    CONF_SOURCE_ENTITY,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    DOMAIN,
    ENTRY_TYPE_AROUND,
)

# Commerce, in the centre of Nantes: several stops lie within 500 m.
_LAT, _LON = 47.2143, -1.5595
_TRACKER = "device_tracker.phone"


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Make the custom integration loadable from the repository."""


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"around_{_TRACKER}",
        title="Autour",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_AROUND,
            CONF_SOURCE_ENTITY: _TRACKER,
            CONF_RADIUS: 500,
            CONF_MAX_STOPS: 5,
        },
    )


def _at(hass: HomeAssistant, lat: float, lon: float) -> None:
    """Place the tracked entity at a location."""
    hass.states.async_set(_TRACKER, "not_home", {"latitude": lat, "longitude": lon})


def _patch_api():
    """Patch the SIRI client so setup never hits the network."""
    return patch(
        "custom_components.naolib.coordinator.NaolibApiClient.async_get_all_departures",
        return_value={},
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    with (
        _patch_api(),
        patch("custom_components.naolib.coordinator.last_departures", return_value={}),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


def _devices(hass: HomeAssistant, entry: MockConfigEntry) -> list[dr.DeviceEntry]:
    """Return the devices attached to the entry."""
    return dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)


def _own_stops(coordinator, entry: MockConfigEntry) -> list[str]:
    """Return the coordinator keys registered by this entry."""
    return [key for key in coordinator.stops if key.startswith(f"{entry.entry_id}:")]


async def test_nearby_stops_become_sensors(hass: HomeAssistant) -> None:
    """Setting up near the city centre creates a sensor per nearby stop."""
    _at(hass, _LAT, _LON)
    entry = _entry()
    await _setup(hass, entry)

    coordinator = hass.data[DOMAIN].coordinator
    keys = _own_stops(coordinator, entry)
    assert keys  # at least one stop within 500 m
    assert len(keys) <= 5

    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert len(entities) == len(keys)


async def test_moving_away_removes_the_sensors(hass: HomeAssistant) -> None:
    """Leaving the area drops the stops once the debounce elapses."""
    _at(hass, _LAT, _LON)
    entry = _entry()
    await _setup(hass, entry)

    coordinator = hass.data[DOMAIN].coordinator
    assert _own_stops(coordinator, entry)

    with _patch_api():
        _at(hass, 0.0, 0.0)
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=AROUND_DEBOUNCE + 1)
        )
        await hass.async_block_till_done()

    assert not _own_stops(coordinator, entry)
    # The devices and their entities go away too, leaving nothing stale.
    assert not _devices(hass, entry)
    assert not er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert not hass.states.async_entity_ids("sensor")


async def test_unload_unregisters_stops(hass: HomeAssistant) -> None:
    """Unloading drops every stop the entry had registered."""
    _at(hass, _LAT, _LON)
    entry = _entry()
    await _setup(hass, entry)

    coordinator = hass.data[DOMAIN].coordinator
    assert _own_stops(coordinator, entry)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not _own_stops(coordinator, entry)


async def test_devices_left_behind_while_stopped_are_removed(
    hass: HomeAssistant,
) -> None:
    """Stops that left the radius while unloaded are dropped on the next setup."""
    _at(hass, _LAT, _LON)
    entry = _entry()
    await _setup(hass, entry)
    assert _devices(hass, entry)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # The devices survive an unload, as for any integration.
    assert _devices(hass, entry)

    _at(hass, 0.0, 0.0)
    with (
        _patch_api(),
        patch("custom_components.naolib.coordinator.last_departures", return_value={}),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Let the refresh requested on setup run instead of lingering.
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert not _devices(hass, entry)


async def test_without_a_location_nothing_is_tracked(hass: HomeAssistant) -> None:
    """A missing entity or one without GPS coordinates yields no stop."""
    entry = _entry()
    await _setup(hass, entry)  # the tracked entity does not exist yet
    coordinator = hass.data[DOMAIN].coordinator
    assert not _own_stops(coordinator, entry)

    with _patch_api():
        hass.states.async_set(_TRACKER, "home", {})  # no latitude/longitude
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=AROUND_DEBOUNCE + 1)
        )
        await hass.async_block_till_done()

    assert not _own_stops(coordinator, entry)


async def test_bursts_of_moves_are_debounced(hass: HomeAssistant) -> None:
    """Close moves collapse into one recomputation that keeps current sensors."""
    _at(hass, _LAT, _LON)
    entry = _entry()
    await _setup(hass, entry)
    coordinator = hass.data[DOMAIN].coordinator
    before = set(_own_stops(coordinator, entry))
    entity_ids = set(hass.states.async_entity_ids("sensor"))

    with _patch_api():
        _at(hass, _LAT + 0.00001, _LON)
        _at(hass, _LAT, _LON + 0.00001)  # cancels the pending recomputation
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=AROUND_DEBOUNCE + 1)
        )
        await hass.async_block_till_done()

    assert set(_own_stops(coordinator, entry)) == before
    assert set(hass.states.async_entity_ids("sensor")) == entity_ids


async def test_unload_cancels_a_pending_recomputation(hass: HomeAssistant) -> None:
    """Unloading while a move is being debounced leaves no timer behind."""
    _at(hass, _LAT, _LON)
    entry = _entry()
    await _setup(hass, entry)

    _at(hass, 0.0, 0.0)  # schedules a debounced recomputation
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not _own_stops(hass.data[DOMAIN].coordinator, entry)


async def test_excluded_stops_are_never_shown(hass: HomeAssistant) -> None:
    """An excluded stop is skipped and its slot goes to the next closest one."""
    _at(hass, _LAT, _LON)
    reference = _entry()
    await _setup(hass, reference)
    nearest = sorted(_own_stops(hass.data[DOMAIN].coordinator, reference))
    assert await hass.config_entries.async_unload(reference.entry_id)
    await hass.async_block_till_done()
    excluded = nearest[0].split(":", 1)[1]

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="around_other",
        data={**reference.data, CONF_EXCLUDED_STOPS: [excluded]},
    )
    await _setup(hass, entry)

    codes = {
        key.split(":", 1)[1] for key in _own_stops(hass.data[DOMAIN].coordinator, entry)
    }
    assert excluded not in codes
    assert len(codes) == len(nearest)


async def test_sensors_expose_the_source_and_distance(hass: HomeAssistant) -> None:
    """Each nearby stop carries the tracked entity and its distance to it."""
    _at(hass, _LAT, _LON)
    entry = _entry()
    await _setup(hass, entry)

    states = [
        hass.states.get(entity_id)
        for entity_id in hass.states.async_entity_ids("sensor")
    ]
    assert states
    assert all(state.attributes["around_source"] == _TRACKER for state in states)
    before = {state.entity_id: state.attributes["distance"] for state in states}
    assert all(0 <= distance <= 500 for distance in before.values())

    # A small move keeps the same stops but changes their distance.
    with _patch_api():
        _at(hass, _LAT + 0.001, _LON)
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=AROUND_DEBOUNCE + 1)
        )
        await hass.async_block_till_done()

    after = {
        entity_id: hass.states.get(entity_id).attributes["distance"]
        for entity_id in before
        if hass.states.get(entity_id) is not None
    }
    assert after
    assert after != {entity_id: before[entity_id] for entity_id in after}


async def test_deleting_a_stop_device_excludes_it(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """Deleting a nearby stop's device hides that stop for good."""
    _at(hass, _LAT, _LON)
    entry = _entry()
    await _setup(hass, entry)
    device = _devices(hass, entry)[0]
    code = next(iter(device.identifiers))[1].removeprefix(f"around_{entry.entry_id}_")

    client = await hass_ws_client(hass)
    with _patch_api():
        await client.send_json_auto_id(
            {
                "type": "config/device_registry/remove_config_entry",
                "config_entry_id": entry.entry_id,
                "device_id": device.id,
            }
        )
        response = await client.receive_json()
        await hass.async_block_till_done()

    assert response["success"]
    assert entry.data[CONF_EXCLUDED_STOPS] == [code]
    coordinator = hass.data[DOMAIN].coordinator
    assert f"{entry.entry_id}:{code}" not in coordinator.stops
    assert _own_stops(coordinator, entry)  # another stop took its place


async def test_stop_devices_of_other_entries_cannot_be_deleted(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """A fixed stop is what its entry is about: its device cannot go alone."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="STOP1",
        data={CONF_STOP_CODE: "STOP1", CONF_STOP_LABEL: "A", CONF_QUAYS: ["Q1"]},
    )
    await _setup(hass, entry)
    device = _devices(hass, entry)[0]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": entry.entry_id,
            "device_id": device.id,
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert _devices(hass, entry)


async def test_a_device_without_a_stop_is_not_deleted(hass: HomeAssistant) -> None:
    """Only the nearby-stop devices of the entry can be deleted."""
    entry = _entry()
    entry.add_to_hass(hass)
    stranger = MagicMock(identifiers={(DOMAIN, "STOP1"), ("other", "x")})

    assert not await async_remove_config_entry_device(hass, entry, stranger)
