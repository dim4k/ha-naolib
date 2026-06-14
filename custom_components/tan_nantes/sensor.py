import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    DOMAIN,
    STATE_NO_BUS,
    STATE_UNAVAILABLE,
)
from .coordinator import TanDataCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors based on the config entry."""
    # Handle backward compatibility for existing entries
    stop_code = entry.data.get(CONF_STOP_CODE) or entry.data.get("code_lieu")
    stop_name = entry.data.get(CONF_STOP_LABEL) or entry.data.get("libelle")

    coordinator: TanDataCoordinator = entry.runtime_data

    # Create a main sensor
    async_add_entities([
        TanNextDeparturesSensor(coordinator, stop_name or stop_code),
    ], True)

class TanNextDeparturesSensor(CoordinatorEntity, SensorEntity):
    """Represent the next bus at the stop."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: TanDataCoordinator, stop_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._stop_name = stop_name
        self._attr_unique_id = f"tan_{coordinator.stop_code}_next"
        self._attr_name = f"Tan Next - {stop_name}"
        self._attr_icon = "mdi:bus-clock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.stop_code)},
            name=f"Arrêt {stop_name}",
            manufacturer="TAN",
            model="Arrêt",
        )

    @property
    def native_value(self) -> str:
        """Return the time of the very first bus."""
        data = self.coordinator.data
        passages = data.get("next_departures", []) if data else []

        if passages:
            return passages[0].get("time", STATE_UNAVAILABLE)
        return STATE_NO_BUS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return next passages and stop code as attributes."""
        data = self.coordinator.data or {}
        return {
            "stop_code": self.coordinator.stop_code,
            "next_departures": data.get("next_departures", []),
        }
