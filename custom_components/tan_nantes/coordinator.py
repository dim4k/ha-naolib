import asyncio
from datetime import timedelta
import logging
from typing import Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .api import TanApiClient

_LOGGER = logging.getLogger(__name__)

# A schedule cache key: (codeArret, numLigne, sens)
ScheduleKey = tuple[str, str, int]


class TanDataCoordinator(DataUpdateCoordinator):
    """Manage API data retrieval."""

    def __init__(
        self,
        hass: HomeAssistant,
        stop_code: str,
        update_interval: int = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{stop_code}",
            update_interval=timedelta(seconds=update_interval),
        )
        self.stop_code = stop_code
        self.api = TanApiClient(async_get_clientsession(hass))
        self._schedules: dict[ScheduleKey, dict] = {}
        self._last_schedule_date = None

    @staticmethod
    def _extract_key(passage: dict[str, Any]) -> Optional[ScheduleKey]:
        """Build the schedule cache key for a passage, or None if incomplete."""
        stop_id = passage.get("arret", {}).get("codeArret")
        line_num = passage.get("ligne", {}).get("numLigne")
        direction = passage.get("sens")
        if stop_id and line_num and direction:
            return (stop_id, line_num, direction)
        return None

    def _reset_cache_if_stale(self) -> None:
        """Clear the schedule cache once per day."""
        today = dt_util.now().date()
        if self._last_schedule_date != today:
            self._schedules = {}
            self._last_schedule_date = today

    async def _fetch_missing_schedules(self, keys: set[ScheduleKey]) -> None:
        """Fetch and cache schedules that are not yet known."""
        missing = [key for key in keys if key not in self._schedules]
        if not missing:
            return

        results = await asyncio.gather(
            *(self.api.get_stop_schedule(*key) for key in missing),
            return_exceptions=True,
        )
        for key, result in zip(missing, results):
            if isinstance(result, dict):
                self._schedules[key] = result

    def _build_schedule_entry(self, key: ScheduleKey) -> Optional[dict]:
        """Build the frontend schedule payload for a given key."""
        sched = self._schedules.get(key)
        if not sched or not sched.get("horaires"):
            return None

        _, line_num, direction = key

        # Compress horaires to { "HH": ["mm", "mm"] } to save space
        compressed_horaires = {
            h["heure"]: h["passages"]
            for h in sched.get("horaires", [])
            if "heure" in h and "passages" in h
        }

        dir_key = f"directionSens{direction}"
        direction_label = sched.get("ligne", {}).get(dir_key) or f"Sens {direction}"

        return {
            "horaires": compressed_horaires,
            "ligne": {
                "numLigne": sched.get("ligne", {}).get("numLigne"),
                "direction": sched.get("ligne", {}).get("direction"),
            },
            "direction_label": direction_label,
        }

    def _traffic_message(self, key: ScheduleKey, has_traffic_info: bool) -> Optional[str]:
        """Return the traffic message from the cached schedule, if any."""
        if not has_traffic_info:
            return None
        sched = self._schedules.get(key)
        if not sched:
            return None
        return sched.get("ligne", {}).get("libelleTrafic") or None

    async def _async_update_data(self) -> dict:
        """Retrieve data from the Tan API."""
        try:
            data = await self.api.get_waiting_time(self.stop_code)
            if data is None:
                raise UpdateFailed("Error fetching data from Tan API")
            if not data:
                # Empty list: no buses scheduled.
                return {"next_departures": [], "schedules": {}}

            self._reset_cache_if_stale()

            # Single pass: pair each passage with its (optional) key.
            keyed = [(passage, self._extract_key(passage)) for passage in data]

            # Fetch any schedules we don't have cached yet.
            await self._fetch_missing_schedules(
                {key for _, key in keyed if key is not None}
            )

            next_departures = []
            schedules: dict[str, dict] = {}

            for passage, key in keyed:
                has_traffic_info = bool(passage.get("infotrafic"))
                traffic_message = (
                    self._traffic_message(key, has_traffic_info) if key else None
                )

                if key is not None:
                    entry = self._build_schedule_entry(key)
                    if entry is not None:
                        _, line_num, direction = key
                        schedules[f"{line_num}-{direction}"] = entry

                line_info = passage.get("ligne", {})
                next_departures.append({
                    "line": line_info.get("numLigne"),
                    "type": line_info.get("typeLigne"),
                    "destination": passage.get("terminus"),
                    "time": passage.get("temps"),
                    "direction": passage.get("sens"),
                    "traffic_info": has_traffic_info,
                    "traffic_message": traffic_message,
                })

            return {
                "next_departures": next_departures,
                "schedules": schedules,
            }
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
