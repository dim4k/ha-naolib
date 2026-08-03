"""Tests for the SIRI response parser."""

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest

from custom_components.naolib.api import NaolibApiClient
from custom_components.naolib.const import SIRI_NAMESPACE, SIRI_URL


def _visit(quay: str, line: str) -> str:
    return f"""
      <MonitoredStopVisit>
        <MonitoringRef>{quay}</MonitoringRef>
        <MonitoredVehicleJourney>
          <LineRef>FR_NAOLIB:Line:{line}:LOC</LineRef>
          <PublishedLineName>Ligne {line}</PublishedLineName>
          <DirectionName>ALLER</DirectionName>
          <DestinationName>Beaujoire</DestinationName>
          <VehicleMode>tram</VehicleMode>
          <MonitoredCall>
            <ExpectedDepartureTime>2024-01-01T10:05:00+01:00</ExpectedDepartureTime>
            <AimedDepartureTime>2024-01-01T10:00:00+01:00</AimedDepartureTime>
          </MonitoredCall>
        </MonitoredVehicleJourney>
      </MonitoredStopVisit>
    """


def _payload(*visits: str) -> bytes:
    return (
        f'<?xml version="1.0" encoding="utf-8"?>'
        f'<Siri xmlns="{SIRI_NAMESPACE}" version="2.0">'
        f"{''.join(visits)}"
        f"</Siri>"
    ).encode()


def _client() -> NaolibApiClient:
    # _parse only needs the instance, not hass nor the HTTP session.
    return NaolibApiClient(None, None)  # type: ignore[arg-type]


def test_parse_indexes_departures_by_quay() -> None:
    """Every visit is grouped under its MonitoringRef."""
    result = _client()._parse(_payload(_visit("QUAY1", "C3"), _visit("QUAY2", "2")))

    assert result is not None
    assert set(result) == {"QUAY1", "QUAY2"}
    departure = result["QUAY1"][0]
    assert departure["line"] == "C3"
    assert departure["destination"] == "Beaujoire"
    assert departure["vehicle_mode"] == "tram"
    assert departure["expected"] == "2024-01-01T10:05:00+01:00"
    assert departure["aimed"] == "2024-01-01T10:00:00+01:00"


def test_parse_drops_unwanted_quays() -> None:
    """Quays no configured stop cares about are skipped."""
    result = _client()._parse(
        _payload(_visit("QUAY1", "C3"), _visit("QUAY2", "2")), {"QUAY2"}
    )

    assert set(result) == {"QUAY2"}


def test_parse_returns_none_on_invalid_xml() -> None:
    """A truncated response is reported as a failure, not as no departure."""
    assert _client()._parse(b"<Siri><Monitored") is None


def test_parse_skips_incomplete_visits() -> None:
    """A visit without a quay or without a journey carries no departure."""
    no_quay = """
      <MonitoredStopVisit>
        <MonitoredVehicleJourney><LineRef>x</LineRef></MonitoredVehicleJourney>
      </MonitoredStopVisit>
    """
    no_journey = """
      <MonitoredStopVisit><MonitoringRef>QUAY9</MonitoringRef></MonitoredStopVisit>
    """

    assert _client()._parse(_payload(no_quay, no_journey)) == {}


def test_parse_tolerates_a_bare_journey() -> None:
    """Missing call, line and destination yield None fields, not an error."""
    bare = """
      <MonitoredStopVisit>
        <MonitoringRef>QUAY1</MonitoringRef>
        <MonitoredVehicleJourney></MonitoredVehicleJourney>
      </MonitoredStopVisit>
    """

    departure = _client()._parse(_payload(bare))["QUAY1"][0]

    assert departure == {
        "line": None,
        "destination": None,
        "direction_name": None,
        "vehicle_mode": None,
        "expected": None,
        "aimed": None,
    }


def test_parse_keeps_an_unstructured_line_ref() -> None:
    """A LineRef that is not the usual triplet is kept as-is."""
    visit = """
      <MonitoredStopVisit>
        <MonitoringRef>QUAY1</MonitoringRef>
        <MonitoredVehicleJourney><LineRef>C3</LineRef></MonitoredVehicleJourney>
      </MonitoredStopVisit>
    """

    assert _client()._parse(_payload(visit))["QUAY1"][0]["line"] == "C3"


async def test_fetch_indexes_the_whole_network(hass, aioclient_mock) -> None:
    """A successful request is parsed into departures keyed by quay."""
    aioclient_mock.post(SIRI_URL, content=_payload(_visit("QUAY1", "C3")))
    client = NaolibApiClient(hass, async_get_clientsession(hass))

    assert set(await client.async_get_all_departures()) == {"QUAY1"}


@pytest.mark.parametrize("status", [429, 503, 500])
async def test_fetch_returns_none_on_http_error(hass, aioclient_mock, status) -> None:
    """Rate limits, gateway errors and unexpected statuses all degrade to None."""
    aioclient_mock.post(SIRI_URL, status=status)
    client = NaolibApiClient(hass, async_get_clientsession(hass))

    assert await client.async_get_all_departures() is None


@pytest.mark.parametrize("error", [TimeoutError(), aiohttp.ClientError()])
async def test_fetch_returns_none_on_network_error(hass, aioclient_mock, error) -> None:
    """A network hiccup degrades to None so the coordinator can retry."""
    aioclient_mock.post(SIRI_URL, exc=error)
    client = NaolibApiClient(hass, async_get_clientsession(hass))

    assert await client.async_get_all_departures() is None
