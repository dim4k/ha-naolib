import logging
import asyncio
from typing import Any, Optional
import aiohttp
import async_timeout

from .const import URL_STOPS, URL_WAITING_TIME, URL_STOP_SCHEDULE

_LOGGER = logging.getLogger(__name__)

class TanApiClient:
    """API Client for Tan Nantes."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._session = session

    async def get_stops(self, lat: float, lon: float) -> Optional[list[dict[str, Any]]]:
        """Get stops around a location."""
        url = URL_STOPS.format(lat, lon)
        return await self._api_wrapper(url)

    async def get_waiting_time(self, stop_code: str) -> Optional[list[dict[str, Any]]]:
        """Get waiting times for a specific stop."""
        url = URL_WAITING_TIME.format(stop_code)
        return await self._api_wrapper(url)

    async def get_stop_schedule(self, stop_id: str, line_num: str, direction: int) -> Optional[dict[str, Any]]:
        """Get schedule and details for a specific stop/line/direction."""
        url = URL_STOP_SCHEDULE.format(stop_id, line_num, direction)
        return await self._api_wrapper(url)

    async def _api_wrapper(self, url: str) -> Any:
        """Execute the API request."""
        try:
            async with async_timeout.timeout(10):
                async with self._session.get(url) as response:
                    response.raise_for_status()
                    return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as exception:
            _LOGGER.error("Error fetching data from %s: %s", url, exception)
            return None
        except Exception as exception:
            _LOGGER.error("Unexpected error connecting to Tan API: %s", exception)
            return None