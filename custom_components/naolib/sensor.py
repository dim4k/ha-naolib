"""Sensor platform for the Naolib integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import NaolibGlobalCoordinator, NaolibStop, build_stop_data

if TYPE_CHECKING:
    from . import NaolibConfigEntry

# All entities read from a single shared coordinator, so there is no per-entity
# polling to serialize.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NaolibConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors based on the config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [NaolibNextDeparturesSensor(coordinator, coordinator.stops[entry.entry_id])]
    )


class NaolibNextDeparturesSensor(
    CoordinatorEntity[NaolibGlobalCoordinator], SensorEntity
):
    """Represent the next bus at the stop."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_departures"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_attribution = "Données Naolib / Okina"

    # The departures list is volatile (rebuilt on every poll); keep it out
    # of the recorder history to avoid bloating the database. It stays
    # available in the state machine for the card and automations.
    _unrecorded_attributes = frozenset({"next_departures"})

    def __init__(
        self,
        coordinator: NaolibGlobalCoordinator,
        stop: NaolibStop,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._stop = stop
        self._attr_unique_id = f"naolib_{stop.code}_next"
        self._attr_icon = "mdi:bus-clock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stop.code)},
            name=f"Arrêt {stop.name}",
            manufacturer="Naolib",
            model="Arrêt",
        )
        self._stop_data = build_stop_data(coordinator.data or {}, stop)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Recompute the cached departures when new network data arrives."""
        self._stop_data = build_stop_data(self.coordinator.data or {}, self._stop)
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the very next bus, or None if none."""
        return self._stop_data["next_departure_dt"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return next passages and stop code as attributes."""
        return {
            "stop_code": self._stop.code,
            "stop_label": self._stop.name,
            "next_departures": self._stop_data["next_departures"],
        }
