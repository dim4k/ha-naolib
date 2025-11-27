import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_STOP_CODE, CONF_STOP_LABEL
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

    if not stop_code:
        _LOGGER.error("Stop code missing from configuration")
        return

    # Coordinator to manage updates (every 60s)
    coordinator = TanDataCoordinator(hass, stop_code)
    
    # Register coordinator for WS access
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("coordinators", {})
    hass.data[DOMAIN]["coordinators"][stop_code] = coordinator
    
    await coordinator.async_config_entry_first_refresh()

    # Create a main sensor
    async_add_entities([
        TanNextDeparturesSensor(coordinator, stop_name),
    ], True)

class TanNextDeparturesSensor(CoordinatorEntity, SensorEntity):
    """Represent the next bus at the stop."""

    def __init__(self, coordinator: TanDataCoordinator, stop_name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._stop_name = stop_name
        self._attr_unique_id = f"tan_{coordinator.stop_code}_next"
        self._attr_name = f"Tan Next - {stop_name}"
        self._attr_icon = "mdi:bus-clock"

    @property
    def native_value(self) -> str:
        """Return the time of the very first bus."""
        data = self.coordinator.data
        passages = data.get("next_departures", []) if data else []
        
        if passages and len(passages) > 0:
            return passages[0].get("time", "Indisponible")
        return "No bus"

    @property
    def extra_state_attributes(self) -> dict[str, any]:
        """Return all next passages as attributes."""
        return {
            "stop_code": self.coordinator.stop_code
        }
