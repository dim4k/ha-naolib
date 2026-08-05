"""Tests for the bike GBFS client, coordinator and station formatting."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

from custom_components.naolib.bike import (
    GbfsUnavailableError,
    NaolibBikeCoordinator,
    NaolibBikeStation,
    _async_get_json,
    async_fetch_stations,
    build_station_data,
    nearby_stations,
    parse_stations,
    parse_status,
)
from custom_components.naolib.const import GBFS_STATION_INFORMATION_URL

_INFORMATION = {
    "data": {
        "stations": [
            {
                "station_id": "1",
                "name": [{"text": "PRÉFECTURE", "language": "fr"}],
                "lat": 47.21984,
                "lon": -1.554891,
                "address": "Place du Port Communeau",
                "capacity": 33,
            },
            {
                "station_id": "2",
                "name": [{"text": "COMMERCE", "language": "fr"}],
                "lat": 47.2143,
                "lon": -1.5595,
                "capacity": 20,
            },
            # Far enough to fall outside the 1 km neighbour radius.
            {
                "station_id": "3",
                "name": [{"text": "ORVAULT", "language": "fr"}],
                "lat": 47.28,
                "lon": -1.62,
                "capacity": 10,
            },
        ]
    }
}

_STATUS = {
    "data": {
        "stations": [
            {
                "station_id": "1",
                "num_vehicles_available": 7,
                "num_docks_available": 26,
                "is_installed": True,
                "is_renting": True,
                "is_returning": True,
                "last_reported": "2026-08-05T10:02:04Z",
            },
            {
                "station_id": "2",
                "num_vehicles_available": 0,
                "num_docks_available": 20,
                "is_installed": True,
                "is_renting": False,
                "is_returning": True,
                "last_reported": "2026-08-05T10:03:00Z",
            },
            {
                "station_id": "3",
                "num_vehicles_available": 4,
                "num_docks_available": 6,
                "is_installed": True,
                "is_renting": True,
                "is_returning": True,
                "last_reported": "2026-08-05T10:04:00Z",
            },
        ]
    }
}


def _station(station_id: str = "1") -> NaolibBikeStation:
    return NaolibBikeStation(id=station_id, name="PRÉFECTURE", interval=60)


def test_parse_stations_flattens_the_localized_names() -> None:
    """GBFS 3.0 wraps names in a list of localized strings."""
    stations = parse_stations(_INFORMATION)

    assert [station["id"] for station in stations] == ["1", "2", "3"]
    assert stations[0]["name"] == "Préfecture"
    assert stations[0]["address"] == "Place du Port Communeau"
    assert stations[0]["capacity"] == 33


def test_parse_stations_rewrites_the_shouty_names() -> None:
    """The feed shouts; the stop index does not, so names are aligned on it."""
    payload = {
        "data": {
            "stations": [
                {"station_id": str(i), "name": name, "lat": 47.2, "lon": -1.5}
                for i, name in enumerate(
                    [
                        "PRAIRIE AU DUC",
                        "MACHINE DE L'ÎLE",
                        "ÉCOLE D'ARCHITECTURE",
                        "BELLAMY-GUÉ MOREAU",
                        "GARE DE NANTES NORD",
                        "Quai Moncousu",
                    ]
                )
            ]
        }
    }

    assert [station["name"] for station in parse_stations(payload)] == [
        "Prairie au Duc",
        "Machine de l'Île",
        "École d'Architecture",
        "Bellamy-Gué Moreau",
        "Gare de Nantes Nord",
        # Already cased: left untouched, so an upstream fix is not undone.
        "Quai Moncousu",
    ]


def test_parse_stations_accepts_the_legacy_string_names() -> None:
    """A rollback to GBFS 2.3 must not break the parsing."""
    payload = {
        "data": {"stations": [{"station_id": "9", "name": "GARE", "lat": 1, "lon": 2}]}
    }

    assert parse_stations(payload)[0]["name"] == "Gare"


def test_parse_stations_skips_incomplete_entries() -> None:
    """A station without usable coordinates cannot be placed on a map."""
    payload = {
        "data": {
            "stations": [
                {"station_id": "1", "name": "OK", "lat": 47.2, "lon": -1.5},
                {"station_id": "2", "name": "NO LAT", "lon": -1.5},
                {"name": "NO ID", "lat": 47.2, "lon": -1.5},
                {"station_id": "4", "name": "BAD LAT", "lat": "nope", "lon": -1.5},
            ]
        }
    }

    assert [station["id"] for station in parse_stations(payload)] == ["1"]


def test_parse_status_skips_entries_without_an_id() -> None:
    """A counter that cannot be attached to a station is useless."""
    payload = {
        "data": {
            "stations": [
                {"station_id": "1", "num_vehicles_available": 3},
                {"num_vehicles_available": 9},
            ]
        }
    }

    assert list(parse_status(payload)) == ["1"]


def test_parse_status_accepts_both_counter_names() -> None:
    """GBFS 3.0 renamed the 2.3 "bikes" counters to "vehicles"."""
    payload = {
        "data": {
            "stations": [
                {"station_id": "1", "num_bikes_available": 3, "num_docks_available": 4}
            ]
        }
    }

    assert parse_status(payload)["1"]["bikes"] == 3


def test_parse_status_normalizes_an_epoch_timestamp() -> None:
    """GBFS 2.3 reported the timestamp as a POSIX integer."""
    payload = {"data": {"stations": [{"station_id": "1", "last_reported": 1754388124}]}}

    assert parse_status(payload)["1"]["last_reported"].startswith("2025-")


def test_nearby_stations_are_sorted_by_distance() -> None:
    """The closest station comes first, with its distance in meters."""
    stations = parse_stations(_INFORMATION)

    result = nearby_stations(stations, 47.2143, -1.5595)

    assert [station["id"] for station in result] == ["2", "1", "3"]
    assert result[0]["distance"] == 0


async def test_async_fetch_stations_raises_when_unreachable(
    hass: HomeAssistant,
) -> None:
    """The config flow needs to tell a network failure from an empty feed."""
    with (
        patch("custom_components.naolib.bike._async_get_json", return_value=None),
        pytest.raises(GbfsUnavailableError),
    ):
        await async_fetch_stations(object())


async def test_async_fetch_stations_returns_the_network(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """The whole station list is read from the live feed."""
    aioclient_mock.get(GBFS_STATION_INFORMATION_URL, json=_INFORMATION)

    stations = await async_fetch_stations(async_get_clientsession(hass))

    assert [station["id"] for station in stations] == ["1", "2", "3"]


async def test_get_json_swallows_an_http_error(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """A failing request is reported as no data, not as an exception."""
    aioclient_mock.get(GBFS_STATION_INFORMATION_URL, status=500)

    result = await _async_get_json(
        async_get_clientsession(hass), GBFS_STATION_INFORMATION_URL
    )

    assert result is None


def _network() -> dict:
    info = {station["id"]: station for station in parse_stations(_INFORMATION)}
    status = parse_status(_STATUS)
    return {
        station_id: {**details, **status[station_id]}
        for station_id, details in info.items()
    }


def test_build_station_data_exposes_the_counters() -> None:
    """The sensor attributes come straight from the snapshot."""
    data = build_station_data(_network(), _station("1"))

    assert data["available"] is True
    assert data["bikes"] == 7
    assert data["docks"] == 26
    assert data["capacity"] == 33
    assert data["name"] == "Préfecture"
    assert data["is_renting"] is True


def test_build_station_data_lists_the_neighbours_within_the_radius() -> None:
    """A station more than 1 km away is not a neighbour."""
    data = build_station_data(_network(), _station("1"))

    assert [station["station_id"] for station in data["nearby_stations"]] == ["2"]
    neighbour = data["nearby_stations"][0]
    assert neighbour["bikes"] == 0
    assert neighbour["is_renting"] is False
    assert neighbour["distance"] > 0


def test_build_station_data_reports_a_missing_station() -> None:
    """A station absent from the snapshot makes its entities unavailable."""
    data = build_station_data(_network(), _station("404"))

    assert data == {"available": False, "nearby_stations": []}


async def test_coordinator_merges_information_and_status(hass: HomeAssistant) -> None:
    """A poll indexes every station by id."""
    coordinator = NaolibBikeCoordinator(hass)

    with patch(
        "custom_components.naolib.bike._async_get_json",
        side_effect=[_INFORMATION, _STATUS],
    ):
        network = await coordinator._async_update_data()

    assert set(network) == {"1", "2", "3"}
    assert network["1"]["bikes"] == 7
    assert network["1"]["name"] == "Préfecture"


async def test_coordinator_caches_the_station_information(
    hass: HomeAssistant,
) -> None:
    """The descriptions are refetched at most once per TTL."""
    coordinator = NaolibBikeCoordinator(hass)

    with patch(
        "custom_components.naolib.bike._async_get_json",
        side_effect=[_INFORMATION, _STATUS],
    ):
        await coordinator._async_update_data()

    with patch(
        "custom_components.naolib.bike._async_get_json", side_effect=[_STATUS]
    ) as fetch:
        await coordinator._async_update_data()

    assert fetch.call_count == 1


async def test_coordinator_keeps_the_last_snapshot_on_failure(
    hass: HomeAssistant,
) -> None:
    """A transient outage must not flag every station unavailable."""
    coordinator = NaolibBikeCoordinator(hass)

    with patch(
        "custom_components.naolib.bike._async_get_json",
        side_effect=[_INFORMATION, _STATUS],
    ):
        first = await coordinator._async_update_data()
    coordinator.data = first

    with patch("custom_components.naolib.bike._async_get_json", return_value=None):
        second = await coordinator._async_update_data()

    assert second == first


async def test_coordinator_fails_when_it_never_succeeded(hass: HomeAssistant) -> None:
    """Without any snapshot to serve, the first failure is fatal."""
    coordinator = NaolibBikeCoordinator(hass)

    with (
        patch("custom_components.naolib.bike._async_get_json", return_value=None),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


async def test_coordinator_rejects_an_empty_station_list(hass: HomeAssistant) -> None:
    """A feed that describes no station leaves nothing to merge the counters into."""
    coordinator = NaolibBikeCoordinator(hass)

    with (
        patch(
            "custom_components.naolib.bike._async_get_json",
            side_effect=[{"data": {"stations": []}}, _STATUS],
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


async def test_coordinator_rejects_statuses_of_unknown_stations(
    hass: HomeAssistant,
) -> None:
    """Counters that match no described station cannot be served."""
    coordinator = NaolibBikeCoordinator(hass)
    orphan = {"data": {"stations": [{"station_id": "999"}]}}

    with (
        patch(
            "custom_components.naolib.bike._async_get_json",
            side_effect=[_INFORMATION, orphan],
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


async def test_coordinator_recovers_after_an_outage(hass: HomeAssistant) -> None:
    """Coming back up is logged once, like going down."""
    coordinator = NaolibBikeCoordinator(hass)

    with patch(
        "custom_components.naolib.bike._async_get_json",
        side_effect=[_INFORMATION, _STATUS],
    ):
        coordinator.data = await coordinator._async_update_data()

    with patch("custom_components.naolib.bike._async_get_json", return_value=None):
        await coordinator._async_update_data()
    assert coordinator._unavailable_logged is True

    with patch("custom_components.naolib.bike._async_get_json", side_effect=[_STATUS]):
        await coordinator._async_update_data()

    assert coordinator._unavailable_logged is False


async def test_coordinator_uses_the_shortest_interval(hass: HomeAssistant) -> None:
    """Registered stations drive the polling interval."""
    coordinator = NaolibBikeCoordinator(hass)

    coordinator.register_station("a", NaolibBikeStation(id="1", name="A", interval=120))
    coordinator.register_station("b", NaolibBikeStation(id="2", name="B", interval=30))
    assert coordinator.update_interval.total_seconds() == 30
    assert coordinator.station_by_id("2").name == "B"

    coordinator.unregister_station("b")
    assert coordinator.update_interval.total_seconds() == 120
    assert coordinator.station_by_id("2") is None
