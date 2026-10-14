"""Tests for the "around me" dynamic controller."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.naolib.const import (
    AROUND_DEBOUNCE,
    CONF_ENTRY_TYPE,
    CONF_MAX_STOPS,
    CONF_RADIUS,
    CONF_SOURCE_ENTITY,
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
