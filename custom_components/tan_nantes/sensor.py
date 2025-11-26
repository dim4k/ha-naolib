import asyncio
from datetime import timedelta, datetime
import logging
import async_timeout

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_STOP_CODE, CONF_STOP_LABEL
from .api import TanApiClient

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
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
        TanScheduleSensor(coordinator, stop_name)
    ], True)

class TanDataCoordinator(DataUpdateCoordinator):
    """Manage API data retrieval."""

    def __init__(self, hass, stop_code):
        super().__init__(
            hass,
            _LOGGER,
            name="Tan API",
            update_interval=timedelta(seconds=60),
        )
        self.stop_code = stop_code
        self.api = TanApiClient(async_get_clientsession(hass))
        self._schedules = {}
        self._last_schedule_date = None

    async def _async_update_data(self):
        """Retrieve data from the Tan API."""
        try:
            data = await self.api.get_waiting_time(self.stop_code)
            if data is None:
                raise UpdateFailed("Error fetching data from Tan API")
            
            # Manage schedules cache (clear daily)
            now = datetime.now()
            if self._last_schedule_date != now.date():
                self._schedules = {}
                self._last_schedule_date = now.date()

            # Identify needed schedules
            tasks = []
            keys_to_fetch = []

            for passage in data:
                stop_id = passage.get("arret", {}).get("codeArret")
                line_num = passage.get("ligne", {}).get("numLigne")
                direction = passage.get("sens")
                
                if stop_id and line_num and direction:
                    key = (stop_id, line_num, direction)
                    if key not in self._schedules:
                        keys_to_fetch.append(key)
                        tasks.append(self.api.get_stop_schedule(*key))

            # Fetch missing schedules in parallel
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for key, result in zip(keys_to_fetch, results):
                    if isinstance(result, dict):
                        self._schedules[key] = result

            # Enrich data with traffic info from schedules and prepare for frontend
            final_schedules = {}
            next_departures = []
            
            for passage in data:
                stop_id = passage.get("arret", {}).get("codeArret")
                line_num = passage.get("ligne", {}).get("numLigne")
                direction = passage.get("sens")
                key = (stop_id, line_num, direction)
                
                # Default values
                passage["infotrafic"] = False
                passage["infotrafic_message"] = None

                if key in self._schedules:
                    sched = self._schedules[key]
                    
                    # Traffic info
                    if passage.get("infotrafic"):
                        msg = sched.get("ligne", {}).get("libelleTrafic")
                        if msg:
                            passage["infotrafic_message"] = msg
                            passage["infotrafic_type"] = "alert"
                    
                    # Prepare schedule for frontend
                    if sched.get("horaires"):
                        # Compress horaires to { "HH": ["mm", "mm"] } to save space
                        # This significantly reduces JSON size compared to list of dicts with repeated keys
                        compressed_horaires = {}
                        for h in sched.get("horaires", []):
                            if "heure" in h and "passages" in h:
                                compressed_horaires[h["heure"]] = h["passages"]

                        sched_data = {
                            "horaires": compressed_horaires,
                            "ligne": {
                                "numLigne": sched.get("ligne", {}).get("numLigne"),
                                "direction": sched.get("ligne", {}).get("direction")
                            }
                        }
                        
                        dir_key = f"directionSens{direction}"
                        if "ligne" in sched and dir_key in sched["ligne"]:
                            sched_data["direction_label"] = sched["ligne"][dir_key]
                        else:
                            sched_data["direction_label"] = f"Sens {direction}"
                            
                        final_schedules[f"{line_num}-{direction}"] = sched_data

                # Prepare next departures
                line_info = passage.get("ligne", {})
                next_departures.append({
                    "line": line_info.get("numLigne"),
                    "type": line_info.get("typeLigne"),
                    "destination": passage.get("terminus"),
                    "time": passage.get("temps"),
                    "direction": passage.get("sens"),
                    "traffic_info": passage.get("infotrafic"),
                    "traffic_message": passage.get("infotrafic_message"),
                    "traffic_type": passage.get("infotrafic_type", "alert")
                })

            return {
                "next_departures": next_departures,
                "schedules": final_schedules
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

class TanNextDeparturesSensor(SensorEntity):
    """Represent the next bus at the stop."""

    def __init__(self, coordinator, stop_name):
        self.coordinator = coordinator
        self._stop_name = stop_name
        self._attr_unique_id = f"tan_{coordinator.stop_code}_next"
        self._attr_name = f"Tan Next - {stop_name}"
        self._attr_icon = "mdi:bus-clock"

    @property
    def native_value(self):
        """Return the time of the very first bus."""
        data = self.coordinator.data
        passages = data.get("next_departures", []) if data else []
        
        if passages and isinstance(passages, list) and len(passages) > 0:
            return passages[0].get("time", "Indisponible")
        return "No bus"

    @property
    def extra_state_attributes(self):
        """Return all next passages as attributes."""
        return {
            "stop_code": self.coordinator.stop_code
        }

    async def async_update(self):
        """Update via the coordinator."""
        await self.coordinator.async_request_refresh()

class TanScheduleSensor(SensorEntity):
    """Represent the schedules at the stop."""

    def __init__(self, coordinator, stop_name):
        self.coordinator = coordinator
        self._stop_name = stop_name
        self._attr_unique_id = f"tan_{coordinator.stop_code}_schedules"
        self._attr_name = f"Tan Schedules - {stop_name}"
        self._attr_icon = "mdi:timetable"

    @property
    def native_value(self):
        """Return the number of schedules available."""
        data = self.coordinator.data
        schedules = data.get("schedules", {}) if data else {}
        return len(schedules)

    @property
    def extra_state_attributes(self):
        """Return schedules as attributes."""
        data = self.coordinator.data
        if not data:
            return {}
        
        return {
            "schedules": data.get("schedules", {})
        }

    async def async_update(self):
        """Update via the coordinator."""
        await self.coordinator.async_request_refresh()