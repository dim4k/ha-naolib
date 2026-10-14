"""Follow a tracked entity and expose the stops around it.

An "around me" entry does not track a fixed stop: it watches a person, zone or
device_tracker and registers the stops within a radius on the shared
departures coordinator, creating one sensor per stop. The set is recomputed
whenever the tracked entity moves, so sensors appear and disappear on the fly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .const import AROUND_DEBOUNCE
from .coordinator import NaolibGlobalCoordinator, NaolibStop
from .sensor import NaolibAroundDeparturesSensor, around_device_identifier
from .stops import load_stops, within

if TYPE_CHECKING:
    from . import NaolibConfigEntry


class NaolibAroundController:
    """Keep the nearby-stop sensors of an "around me" entry in sync."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NaolibConfigEntry,
        coordinator: NaolibGlobalCoordinator,
        async_add_entities: AddConfigEntryEntitiesCallback,
        *,
        source_entity: str,
        radius: float,
        max_stops: int,
        interval: int,
    ) -> None:
        """Initialize the controller."""
        self._hass = hass
        self._entry = entry
        self._coordinator = coordinator
        self._async_add_entities = async_add_entities
        self._source_entity = source_entity
        self._radius = radius
        self._max_stops = max_stops
        self._interval = interval
        self._catalog: list[dict[str, Any]] = []
        # Keyed by the coordinator key ``f"{entry_id}:{stop_code}"``.
        self._stops: dict[str, NaolibStop] = {}
        self._entities: dict[str, NaolibAroundDeparturesSensor] = {}
        self._cancel_debounce: CALLBACK_TYPE | None = None

    async def async_start(self) -> None:
        """Load the catalogue, watch the entity and do a first computation."""
        self._catalog = await self._hass.async_add_executor_job(load_stops)
        self._entry.async_on_unload(
            async_track_state_change_event(
                self._hass, [self._source_entity], self._handle_move
            )
        )
        self._entry.async_on_unload(self._cleanup)
        self._refresh_nearby()

    @callback
    def _handle_move(self, _event: Event[EventStateChangedData]) -> None:
        """Debounce the tracked entity's moves before recomputing."""
        if self._cancel_debounce is not None:
            self._cancel_debounce()
        self._cancel_debounce = async_call_later(
            self._hass, AROUND_DEBOUNCE, self._debounced
        )

    @callback
    def _debounced(self, _now: Any) -> None:
        """Run the recomputation after the debounce delay."""
        self._cancel_debounce = None
        self._refresh_nearby()

    @callback
    def _coords(self) -> tuple[float, float] | None:
        """Read the tracked entity's GPS coordinates, if any."""
        state = self._hass.states.get(self._source_entity)
        if state is None:
            return None
        lat = state.attributes.get("latitude")
        lon = state.attributes.get("longitude")
        if lat is None or lon is None:
            return None
        return float(lat), float(lon)

    @callback
    def _refresh_nearby(self) -> None:
        """Add the newly nearby stops and drop the ones out of range."""
        coords = self._coords()
        if coords is None:
            return

        nearby = within(
            self._catalog, coords[0], coords[1], self._radius, self._max_stops
        )
        wanted = {f"{self._entry.entry_id}:{stop['id']}": stop for stop in nearby}

        new_entities: list[NaolibAroundDeparturesSensor] = []
        for key, stop in wanted.items():
            if key in self._stops:
                continue
            naolib_stop = NaolibStop(
                code=stop["id"],
                name=stop["name"],
                quays=stop.get("quays") or [],
                interval=self._interval,
            )
            self._stops[key] = naolib_stop
            self._coordinator.register_stop(key, naolib_stop)
            entity = NaolibAroundDeparturesSensor(
                self._coordinator, naolib_stop, self._entry.entry_id
            )
            self._entities[key] = entity
            new_entities.append(entity)

        for key in list(self._stops):
            if key in wanted:
                continue
            self._coordinator.unregister_stop(key)
            del self._stops[key]
            del self._entities[key]

        self._remove_stale_devices(
            {
                around_device_identifier(self._entry.entry_id, stop["id"])
                for stop in nearby
            }
        )

        if new_entities:
            self._async_add_entities(new_entities)
            # The snapshot only holds the quays registered when it was taken, so
            # a stop added now needs a refresh to show its departures.
            self._entry.async_create_background_task(
                self._hass,
                self._coordinator.async_request_refresh(),
                "naolib_around_refresh",
            )

    @callback
    def _remove_stale_devices(self, wanted: set[tuple[str, str]]) -> None:
        """Drop the devices of the stops that are no longer nearby.

        Removing the device also removes its entity, so a stop that left the
        radius (now or while Home Assistant was stopped) leaves nothing behind.
        """
        device_registry = dr.async_get(self._hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, self._entry.entry_id
        ):
            if not device.identifiers & wanted:
                device_registry.async_remove_device(device.id)

    @callback
    def _cleanup(self) -> None:
        """Unregister every stop and cancel any pending recomputation."""
        for key in list(self._stops):
            self._coordinator.unregister_stop(key)
        self._stops.clear()
        self._entities.clear()
        if self._cancel_debounce is not None:
            self._cancel_debounce()
            self._cancel_debounce = None
