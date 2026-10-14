"""Tests for the live "around me" subscription used by the card."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.naolib.const import (
    AROUND_DEBOUNCE,
    CONF_QUAYS,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    DOMAIN,
)
from custom_components.naolib.live import NaolibLiveAround

# Commerce, in the centre of Nantes.
_LAT, _LON = 47.2143, -1.5595
_PERSON = "person.me"


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Make the custom integration loadable from the repository."""


def _patch_api():
    return patch(
        "custom_components.naolib.coordinator.NaolibApiClient.async_get_all_departures",
        return_value={},
    )


async def _setup(hass: HomeAssistant) -> None:
    """Load the integration through any entry, as the card requires."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="STOP1",
        data={CONF_STOP_CODE: "STOP1", CONF_STOP_LABEL: "A", CONF_QUAYS: ["Q1"]},
    )
    entry.add_to_hass(hass)
    with (
        _patch_api(),
        patch("custom_components.naolib.coordinator.last_departures", return_value={}),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def _result(client) -> dict:
    """Skip pushed events until the next command result."""
    while (message := await client.receive_json())["type"] != "result":
        pass
    return message


async def _event_where(client, predicate) -> dict:
    """Skip pushed events until one matches (a refresh may push in between)."""
    while not predicate(event := (await client.receive_json())["event"]):
        pass
    return event


def _at(hass: HomeAssistant, lat: float, lon: float) -> None:
    hass.states.async_set(_PERSON, "not_home", {"latitude": lat, "longitude": lon})


def _live_keys(hass: HomeAssistant) -> list[str]:
    return [
        key for key in hass.data[DOMAIN].coordinator.stops if key.startswith("live:")
    ]


async def test_the_stops_follow_the_entity(hass: HomeAssistant, hass_ws_client) -> None:
    """Nearby stops are streamed, then change as the entity moves."""
    await _setup(hass)
    _at(hass, _LAT, _LON)
    client = await hass_ws_client(hass)

    with _patch_api():
        await client.send_json_auto_id(
            {
                "type": "naolib/around/subscribe",
                "entity_id": _PERSON,
                "radius": 500,
                "max_stops": 3,
            }
        )
        assert (await client.receive_json())["success"]
        event = (await client.receive_json())["event"]

        assert event["located"] is True
        assert len(event["stops"]) == 3
        distances = [stop["distance"] for stop in event["stops"]]
        assert distances == sorted(distances)
        assert all(stop["departures"] == [] for stop in event["stops"])
        assert len(_live_keys(hass)) == 3

        # Moving away from every stop empties the list once debounced.
        _at(hass, 0.0, 0.0)
        # Older Home Assistant versions deliver the move a loop iteration later.
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=AROUND_DEBOUNCE + 1)
        )
        await hass.async_block_till_done()
        event = await _event_where(client, lambda event: not event["stops"])

    assert event == {"located": True, "stops": []}
    assert _live_keys(hass) == []


async def test_an_entity_without_position_is_reported(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """Without coordinates the card is told the entity is not located."""
    await _setup(hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "naolib/around/subscribe", "entity_id": "person.nowhere"}
    )
    assert (await client.receive_json())["success"]
    assert (await client.receive_json())["event"] == {"located": False, "stops": []}


async def test_unsubscribing_releases_the_stops(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """Closing the subscription unregisters its stops from the coordinator."""
    await _setup(hass)
    _at(hass, _LAT, _LON)
    client = await hass_ws_client(hass)

    with _patch_api():
        await client.send_json_auto_id(
            {"type": "naolib/around/subscribe", "entity_id": _PERSON}
        )
        subscription = (await client.receive_json())["id"]
        await client.receive_json()
        assert _live_keys(hass)

        await client.send_json_auto_id(
            {"type": "unsubscribe_events", "subscription": subscription}
        )
        assert (await _result(client))["success"]
        await hass.async_block_till_done()

    assert _live_keys(hass) == []


async def test_small_moves_update_the_distances(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """Close moves are debounced together and keep the stops, at new distances."""
    await _setup(hass)
    _at(hass, _LAT, _LON)
    client = await hass_ws_client(hass)

    with _patch_api():
        await client.send_json_auto_id(
            {"type": "naolib/around/subscribe", "entity_id": _PERSON, "max_stops": 2}
        )
        await client.receive_json()
        first = (await client.receive_json())["event"]["stops"]

        _at(hass, _LAT + 0.0002, _LON)
        _at(hass, _LAT + 0.0004, _LON)  # cancels the pending recomputation
        # Older Home Assistant versions deliver the move a loop iteration later.
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=AROUND_DEBOUNCE + 1)
        )
        await hass.async_block_till_done()
        moved = await _event_where(
            client,
            lambda event: (
                [s["distance"] for s in event["stops"]]
                != [s["distance"] for s in first]
            ),
        )
        second = moved["stops"]

    assert [stop["code"] for stop in second] == [stop["code"] for stop in first]
    assert [stop["distance"] for stop in second] != [stop["distance"] for stop in first]


async def test_unsubscribing_cancels_a_pending_move(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """A move still being debounced is dropped with the subscription."""
    await _setup(hass)
    _at(hass, _LAT, _LON)
    client = await hass_ws_client(hass)

    with _patch_api():
        await client.send_json_auto_id(
            {"type": "naolib/around/subscribe", "entity_id": _PERSON}
        )
        subscription = (await client.receive_json())["id"]
        await client.receive_json()
        _at(hass, 0.0, 0.0)  # starts the debounce
        # Older Home Assistant versions deliver the move a loop iteration later.
        await hass.async_block_till_done()
        await client.send_json_auto_id(
            {"type": "unsubscribe_events", "subscription": subscription}
        )
        assert (await _result(client))["success"]
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=AROUND_DEBOUNCE + 1)
        )
        await hass.async_block_till_done()

    assert _live_keys(hass) == []


async def test_an_entity_without_coordinates_is_not_located(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """An entity that exists but has no GPS coordinates is not located."""
    await _setup(hass)
    hass.states.async_set(_PERSON, "home", {})
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {"type": "naolib/around/subscribe", "entity_id": _PERSON}
    )
    await client.receive_json()

    assert (await client.receive_json())["event"] == {"located": False, "stops": []}


async def test_stopping_before_the_start_finishes_is_clean(
    hass: HomeAssistant,
) -> None:
    """A subscription closed while its stops load leaves no listener behind."""
    await _setup(hass)
    _at(hass, _LAT, _LON)
    coordinator = hass.data[DOMAIN].coordinator
    sent: list = []
    live = NaolibLiveAround(
        hass,
        coordinator,
        "live:test",
        sent.append,
        entity_id=_PERSON,
        radius=500,
        max_stops=3,
    )

    live.stop()
    await live.async_start()

    assert sent == []
    assert _live_keys(hass) == []
