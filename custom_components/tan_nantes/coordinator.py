import asyncio
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .api import TanApiClient

_LOGGER = logging.getLogger(__name__)

class TanDataCoordinator(DataUpdateCoordinator):
    """Manage API data retrieval."""

    def __init__(self, hass: HomeAssistant, stop_code: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{stop_code}",
            update_interval=timedelta(seconds=60),
        )
        self.stop_code = stop_code
        self.api = TanApiClient(async_get_clientsession(hass))
        self._schedules: dict[tuple[str, str, int], dict] = {}
        self._last_schedule_date = None

    async def _async_update_data(self) -> dict:
        """Retrieve data from the Tan API."""
        try:
            data = await self.api.get_waiting_time(self.stop_code)
            if not data:
                # If data is None (API error), raise. If empty list, no buses.
                if data is None:
                    raise UpdateFailed("Error fetching data from Tan API")
                return {"next_departures": [], "schedules": {}}

            # Manage schedules cache (clear daily)
            now = dt_util.now()
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
            final_schedules: dict[str, dict] = {}
            next_departures = []

            for passage in data:
                stop_id = passage.get("arret", {}).get("codeArret")
                line_num = passage.get("ligne", {}).get("numLigne")
                direction = passage.get("sens")
                key = (stop_id, line_num, direction)

                # Read traffic info from API response before any override
                has_traffic_info = bool(passage.get("infotrafic"))
                traffic_message = None
                traffic_type = "alert"

                if key in self._schedules:
                    sched = self._schedules[key]

                    # Traffic info: enrich with message from schedule if flagged by API
                    if has_traffic_info:
                        msg = sched.get("ligne", {}).get("libelleTrafic")
                        if msg:
                            traffic_message = msg

                    # Prepare schedule for frontend
                    if sched.get("horaires"):
                        # Compress horaires to { "HH": ["mm", "mm"] } to save space
                        compressed_horaires = {
                            h["heure"]: h["passages"]
                            for h in sched.get("horaires", [])
                            if "heure" in h and "passages" in h
                        }

                        sched_data: dict = {
                            "horaires": compressed_horaires,
                            "ligne": {
                                "numLigne": sched.get("ligne", {}).get("numLigne"),
                                "direction": sched.get("ligne", {}).get("direction"),
                            },
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
                    "traffic_info": has_traffic_info,
                    "traffic_message": traffic_message,
                    "traffic_type": traffic_type,
                })

            return {
                "next_departures": next_departures,
                "schedules": final_schedules,
            }
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
