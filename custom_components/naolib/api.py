"""SIRI StopMonitoring client for the Naolib / Okina real-time API.

The public (keyless) endpoint answers a StopMonitoring request without any
``MonitoringRef`` with the whole network in a single response. We fetch it once
and index every departure by its quay so each configured stop can filter the
data locally without issuing its own request (the endpoint is rate-limited to
one request every 30 seconds per IP).
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any
from xml.etree import ElementTree as ET

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    API_TIMEOUT,
    SIRI_NAMESPACE,
    SIRI_REQUESTOR_REF,
    SIRI_URL,
)

_LOGGER = logging.getLogger(__name__)

_NS = {"s": SIRI_NAMESPACE}

_VISIT_TAG = f"{{{SIRI_NAMESPACE}}}MonitoredStopVisit"


def _text(element: ET.Element | None, path: str) -> str | None:
    """Return the stripped text of a child element, or None."""
    if element is None:
        return None
    found = element.find(path, _NS)
    if found is None or found.text is None:
        return None
    return found.text.strip()


def _line_number(line_ref: str | None) -> str | None:
    """Extract the line number from a SIRI LineRef.

    e.g. ``FR_NAOLIB:Line:C3:LOC`` -> ``C3``.
    """
    if not line_ref:
        return None
    parts = line_ref.split(":")
    if len(parts) >= 3:
        return parts[2]
    return line_ref


class NaolibApiClient:
    """Client for the Naolib SIRI StopMonitoring endpoint."""

    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self._hass = hass
        self._session = session

    def _build_request(self) -> str:
        """Build the SIRI StopMonitoring request body (whole network)."""
        now = dt_util.now().isoformat()
        return (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<Siri xmlns="{SIRI_NAMESPACE}" version="2.0">'
            "<ServiceRequest>"
            f"<RequestTimestamp>{now}</RequestTimestamp>"
            f"<RequestorRef>{SIRI_REQUESTOR_REF}</RequestorRef>"
            '<StopMonitoringRequest version="2.0">'
            f"<RequestTimestamp>{now}</RequestTimestamp>"
            "<MessageIdentifier>1</MessageIdentifier>"
            "</StopMonitoringRequest>"
            "</ServiceRequest>"
            "</Siri>"
        )

    async def async_get_all_departures(
        self, quays: set[str] | None = None
    ) -> dict[str, list[dict[str, Any]]] | None:
        """Fetch the whole network and index departures by quay id.

        ``quays`` restricts the result to the quays actually served by a
        configured stop: the response covers the whole network, and building an
        object for each of its thousands of departures is pure waste.

        Returns a mapping ``{quay_id: [departure, ...]}`` or ``None`` on error.
        """
        try:
            async with (
                asyncio.timeout(API_TIMEOUT),
                self._session.post(
                    SIRI_URL,
                    data=self._build_request(),
                    headers={"Content-Type": "application/xml"},
                ) as response,
            ):
                response.raise_for_status()
                payload = await response.read()
        except aiohttp.ClientResponseError as exception:
            if exception.status == 429:
                # The public endpoint allows one request every 30 seconds.
                _LOGGER.debug("Naolib SIRI rate limit hit (429), will retry")
            elif exception.status in (502, 503, 504):
                # Transient upstream gateway errors; the coordinator retries on
                # the next cycle, so keep these out of the error log.
                _LOGGER.debug(
                    "Naolib SIRI temporarily unavailable (%s), will retry",
                    exception.status,
                )
            else:
                _LOGGER.error("Error fetching SIRI data: %s", exception)
            return None
        except (TimeoutError, aiohttp.ClientError) as exception:
            # Network hiccups and timeouts are transient; the coordinator will
            # retry on the next cycle.
            _LOGGER.debug("Naolib SIRI request failed transiently: %s", exception)
            return None

        # Parsing a whole-network response is slow enough to stall the event
        # loop on the low-end hardware Home Assistant often runs on.
        return await self._hass.async_add_executor_job(self._parse, payload, quays)

    def _parse(
        self, payload: bytes, quays: set[str] | None = None
    ) -> dict[str, list[dict[str, Any]]] | None:
        """Parse a SIRI StopMonitoring response into departures keyed by quay."""
        departures: dict[str, list[dict[str, Any]]] = {}
        try:
            # iterparse lets each visit be released as soon as it is read,
            # instead of holding the whole document tree in memory.
            for _event, visit in ET.iterparse(io.BytesIO(payload)):
                if visit.tag != _VISIT_TAG:
                    continue

                quay = _text(visit, "s:MonitoringRef")
                journey = visit.find("s:MonitoredVehicleJourney", _NS)
                if quay and journey is not None and (quays is None or quay in quays):
                    call = journey.find("s:MonitoredCall", _NS)
                    departures.setdefault(quay, []).append(
                        {
                            "line": _line_number(_text(journey, "s:LineRef")),
                            "destination": _text(journey, "s:DestinationName")
                            or _text(call, "s:DestinationDisplay"),
                            "direction_name": _text(journey, "s:DirectionName"),
                            "vehicle_mode": _text(journey, "s:VehicleMode"),
                            "expected": _text(call, "s:ExpectedDepartureTime")
                            or _text(call, "s:ExpectedArrivalTime"),
                            "aimed": _text(call, "s:AimedDepartureTime")
                            or _text(call, "s:AimedArrivalTime"),
                        }
                    )
                visit.clear()
        except ET.ParseError as exception:
            _LOGGER.error("Failed to parse SIRI response: %s", exception)
            return None

        return departures
