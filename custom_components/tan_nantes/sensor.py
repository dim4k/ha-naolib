import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_QUAYS,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    DOMAIN,
    STATE_NO_BUS,
    STATE_UNAVAILABLE,
)
from .coordinator import TanGlobalCoordinator, build_stop_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors based on the config entry."""
    coordinator: TanGlobalCoordinator = entry.runtime_data
    stop_code = entry.data.get(CONF_STOP_CODE)
    stop_name = entry.data.get(CONF_STOP_LABEL) or stop_code
    quays = entry.data.get(CONF_QUAYS, [])

    async_add_entities(
        [TanNextDeparturesSensor(coordinator, stop_code, stop_name, quays)]
    )


class TanNextDeparturesSensor(CoordinatorEntity[TanGlobalCoordinator], SensorEntity):
    """Represent the next bus at the stop."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: TanGlobalCoordinator,
        stop_code: str,
        stop_name: str,
        quays: list[str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._stop_code = stop_code
        self._stop_name = stop_name
        self._quays = quays
        self._attr_unique_id = f"tan_{stop_code}_next"
        self._attr_name = f"Tan Next - {stop_name}"
        self._attr_icon = "mdi:bus-clock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stop_code)},
            name=f"Arrêt {stop_name}",
            manufacturer="TAN",
            model="Arrêt",
        )

    def _stop_data(self) -> dict[str, Any]:
        """Build the per-stop payload from the shared network data."""
        network = self.coordinator.data or {}
        return build_stop_data(network, self._quays)

    @property
    def native_value(self) -> str:
        """Return the time of the very first bus."""
        passages = self._stop_data().get("next_departures", [])
        if passages:
            return passages[0].get("time", STATE_UNAVAILABLE)
        return STATE_NO_BUS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return next passages and stop code as attributes."""
        return {
            "stop_code": self._stop_code,
            "stop_label": self._stop_name,
            "next_departures": self._stop_data().get("next_departures", []),
        }
