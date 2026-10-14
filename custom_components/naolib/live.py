"""Nearby stops of a moving entity, streamed to a dashboard card.

Unlike an "around me" entry, this creates no entity or device: a card
subscribes over the WebSocket API with an entity to follow, a radius and a
number of stops, and receives the nearby stops with their departures. The
stops are registered on the shared departures coordinator only while the
subscription lives, so they still cost no extra request.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .const import AROUND_DEBOUNCE, DEFAULT_UPDATE_INTERVAL
from .coordinator import NaolibGlobalCoordinator, NaolibStop, build_stop_data
from .stops import load_stops, within


class NaolibLiveAround:
    """Follow an entity and push the stops around it to one subscriber."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: NaolibGlobalCoordinator,
        key: str,
        send: Callable[[dict[str, Any]], None],
        *,
        entity_id: str,
        radius: int,
        max_stops: int,
    ) -> None:
        """Initialize the tracker; nothing happens before async_start."""
        self._hass = hass
        self._coordinator = coordinator
        # Prefix of the coordinator keys, unique to this subscription.
        self._key = key
        self._send = send
        self._entity_id = entity_id
        self._radius = radius
        self._max_stops = max_stops
        self._catalog: list[dict[str, Any]] = []
        # Coordinator key -> (stop, distance in meters).
        self._stops: dict[str, tuple[NaolibStop, int]] = {}
        self._located = False
        self._unsubscribers: list[CALLBACK_TYPE] = []
        self._cancel_debounce: CALLBACK_TYPE | None = None
        self._stopped = False

    async def async_start(self) -> None:
        """Load the stops, watch the entity and the departures, then send."""
        self._catalog = await self._hass.async_add_executor_job(load_stops)
        if self._stopped:
            # Unsubscribed while the stops were loading.
            return
        self._unsubscribers.append(
            async_track_state_change_event(
                self._hass, [self._entity_id], self._handle_move
            )
        )
        # Every poll of the shared coordinator brings fresh departures.
        self._unsubscribers.append(self._coordinator.async_add_listener(self._push))
        self._refresh_nearby()
        self._push()

    @callback
    def stop(self) -> None:
        """Release the stops and listeners (the subscriber went away)."""
        self._stopped = True
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        if self._cancel_debounce is not None:
            self._cancel_debounce()
            self._cancel_debounce = None
        for key in self._stops:
            self._coordinator.unregister_stop(key)
        self._stops.clear()

    @callback
    def _handle_move(self, _event: Event[EventStateChangedData]) -> None:
        """Debounce the entity's moves before recomputing."""
        if self._cancel_debounce is not None:
            self._cancel_debounce()
        self._cancel_debounce = async_call_later(
            self._hass, AROUND_DEBOUNCE, self._debounced
        )

    @callback
    def _debounced(self, _now: Any) -> None:
        self._cancel_debounce = None
        self._refresh_nearby()
        self._push()

    @callback
    def _coords(self) -> tuple[float, float] | None:
        state = self._hass.states.get(self._entity_id)
        if state is None:
            return None
        latitude = state.attributes.get("latitude")
        longitude = state.attributes.get("longitude")
        if latitude is None or longitude is None:
            return None
        return float(latitude), float(longitude)

    @callback
    def _refresh_nearby(self) -> None:
        """Register the stops now nearby and release the others."""
        coords = self._coords()
        self._located = coords is not None
        nearby = (
            []
            if coords is None
            else within(self._catalog, *coords, self._radius, self._max_stops)
        )
        wanted = {f"{self._key}:{stop['id']}": stop for stop in nearby}

        added = False
        for key, place in wanted.items():
            if key in self._stops:
                self._stops[key] = (self._stops[key][0], place["distance"])
                continue
            stop = NaolibStop(
                code=place["id"],
                name=place["name"],
                quays=place.get("quays") or [],
                interval=DEFAULT_UPDATE_INTERVAL,
            )
            self._coordinator.register_stop(key, stop)
            self._stops[key] = (stop, place["distance"])
            added = True

        for key in [key for key in self._stops if key not in wanted]:
            self._coordinator.unregister_stop(key)
            del self._stops[key]

        if added:
            # The snapshot only covers the quays registered when it was taken.
            self._hass.async_create_task(self._coordinator.async_request_refresh())

    @callback
    def _push(self) -> None:
        """Send the nearby stops, nearest first, with their departures."""
        network = self._coordinator.data or {}
        stops = sorted(self._stops.values(), key=lambda item: item[1])
        self._send(
            {
                "located": self._located,
                "stops": [
                    {
                        "code": stop.code,
                        "name": stop.name,
                        "distance": distance,
                        "departures": build_stop_data(network, stop)["next_departures"],
                    }
                    for stop, distance in stops
                ],
            }
        )
