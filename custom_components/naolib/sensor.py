from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_QUAYS,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    DOMAIN,
)
from .coordinator import NaolibGlobalCoordinator, build_stop_data

if TYPE_CHECKING:
    from . import NaolibConfigEntry

_LOGGER = logging.getLogger(__name__)

# All entities read from a single shared coordinator, so there is no per-entity
# polling to serialize.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NaolibConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors based on the config entry."""
    coordinator: NaolibGlobalCoordinator = entry.runtime_data
    stop_code = entry.data.get(CONF_STOP_CODE)
    stop_name = entry.data.get(CONF_STOP_LABEL) or stop_code
    quays = entry.data.get(CONF_QUAYS, [])

    async_add_entities(
        [NaolibNextDeparturesSensor(coordinator, stop_code, stop_name, quays)]
    )


class NaolibNextDeparturesSensor(CoordinatorEntity[NaolibGlobalCoordinator], SensorEntity):
    """Represent the next bus at the stop."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_departures"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_attribution = "Données Naolib / Okina"

    def __init__(
        self,
        coordinator: NaolibGlobalCoordinator,
        stop_code: str,
        stop_name: str,
        quays: list[str],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._stop_code = stop_code
        self._stop_name = stop_name
        self._quays = quays
        self._attr_unique_id = f"naolib_{stop_code}_next"
        self._attr_icon = "mdi:bus-clock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stop_code)},
            name=f"Arrêt {stop_name}",
            manufacturer="Naolib",
            model="Arrêt",
        )
        self._stop_data: dict[str, Any] = self._build_stop_data()

    def _build_stop_data(self) -> dict[str, Any]:
        """Build the per-stop data from the shared network data."""
        network = self.coordinator.data or {}
        return build_stop_data(network, self._quays)

    @property
    def _departures(self) -> list[dict[str, Any]]:
        """Return the cached formatted departures."""
        return self._stop_data.get("next_departures", [])

    @callback
    def _handle_coordinator_update(self) -> None:
        """Recompute the cached departures when new network data arrives."""
        self._stop_data = self._build_stop_data()
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the very next bus, or None if none."""
        return self._stop_data.get("next_departure_dt")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return next passages and stop code as attributes."""
        return {
            "stop_code": self._stop_code,
            "stop_label": self._stop_name,
            "next_departures": self._departures,
        }
