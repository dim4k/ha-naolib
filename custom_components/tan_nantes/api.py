"""SIRI StopMonitoring client for the Naolib / Okina real-time API.

The public (keyless) endpoint answers a StopMonitoring request without any
``MonitoringRef`` with the whole network in a single response. We fetch it once
and index every departure by its quay so each configured stop can filter the
data locally without issuing its own request (the endpoint is rate-limited to
one request every 30 seconds per IP).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from xml.etree import ElementTree as ET

import aiohttp

from homeassistant.util import dt as dt_util

from .const import (
    API_TIMEOUT,
    SIRI_NAMESPACE,
    SIRI_REQUESTOR_REF,
    SIRI_URL,
)

_LOGGER = logging.getLogger(__name__)

_NS = {"s": SIRI_NAMESPACE}


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

    e.g. ``NAOLIBORG:Line:C3:LOC`` -> ``C3``.
    """
    if not line_ref:
        return None
    parts = line_ref.split(":")
    if len(parts) >= 3:
        return parts[2]
    return line_ref


class TanApiClient:
    """Client for the Naolib SIRI StopMonitoring endpoint."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
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

    async def async_get_all_departures(self) -> dict[str, list[dict[str, Any]]] | None:
        """Fetch the whole network and index departures by quay id.

        Returns a mapping ``{quay_id: [departure, ...]}`` or ``None`` on error.
        """
        try:
            async with asyncio.timeout(API_TIMEOUT):
                async with self._session.post(
                    SIRI_URL,
                    data=self._build_request(),
                    headers={"Content-Type": "application/xml"},
                ) as response:
                    response.raise_for_status()
                    payload = await response.read()
        except aiohttp.ClientResponseError as exception:
            if exception.status == 429:
                # The public endpoint allows one request every 30 seconds.
                _LOGGER.debug("Naolib SIRI rate limit hit (429), will retry")
            else:
                _LOGGER.error("Error fetching SIRI data: %s", exception)
            return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as exception:
            _LOGGER.error("Error fetching SIRI data: %s", exception)
            return None
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error connecting to the Naolib SIRI API")
            return None

        return self._parse(payload)

    def _parse(self, payload: bytes) -> dict[str, list[dict[str, Any]]] | None:
        """Parse a SIRI StopMonitoring response into departures keyed by quay."""
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exception:
            _LOGGER.error("Failed to parse SIRI response: %s", exception)
            return None

        departures: dict[str, list[dict[str, Any]]] = {}
        for visit in root.iter(f"{{{SIRI_NAMESPACE}}}MonitoredStopVisit"):
            quay = _text(visit, "s:MonitoringRef")
            journey = visit.find("s:MonitoredVehicleJourney", _NS)
            if not quay or journey is None:
                continue

            call = journey.find("s:MonitoredCall", _NS)
            expected = _text(call, "s:ExpectedDepartureTime") or _text(
                call, "s:ExpectedArrivalTime"
            )

            departures.setdefault(quay, []).append(
                {
                    "line": _line_number(_text(journey, "s:LineRef")),
                    "line_name": _text(journey, "s:PublishedLineName"),
                    "destination": _text(journey, "s:DestinationName")
                    or _text(call, "s:DestinationDisplay"),
                    "direction_name": _text(journey, "s:DirectionName"),
                    "vehicle_mode": _text(journey, "s:VehicleMode"),
                    "expected": expected,
                    "proximity": _text(call, "s:ArrivalProximityText"),
                }
            )

        return departures