"""Tests for the Voi feed and the retirement of the JCDecaux stations."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
import pytest

from custom_components.naolib.bike import (
    JCDECAUX_FEED,
    VOI_FEED,
    NaolibBikeCoordinator,
    NaolibBikeStation,
    async_fetch_stations,
    attach_vehicles,
    best_range,
    build_station_data,
    feed_of,
    label_spots,
    parse_stations,
    parse_vehicles,
    retired_issue_id,
    station_key,
    voi_label,
)
from custom_components.naolib.const import (
    BIKE_PROVIDER_JCDECAUX,
    BIKE_PROVIDER_VOI,
    BIKE_RETIRED_AFTER_POLLS,
    CONF_BIKE_PROVIDER,
    DOMAIN,
    VOI_STATION_INFORMATION_URL,
)

# Taken from the live feed of November 2026, trimmed to three spots.
_VOI_INFORMATION = {
    "version": "2.3",
    "data": {
        "stations": [
            {
                "station_id": "943db4cf",
                "name": "NAN_CEN_064",
                "lat": 47.217193,
                "lon": -1.554497,
                "is_virtual_station": True,
                "capacity": 8,
            },
            {
                "station_id": "5b0f2a10",
                "name": "NAN_CEN_065",
                "lat": 47.2180,
                "lon": -1.5540,
                "is_virtual_station": True,
                "capacity": 6,
            },
            # One spot of the feed has no code at all.
            {
                "station_id": "77aa01c3",
                "name": "",
                "lat": 47.30,
                "lon": -1.50,
                "is_virtual_station": True,
                "capacity": 4,
            },
        ]
    },
}

_VOI_STATUS = {
    "version": "2.3",
    "data": {
        "stations": [
            {
                "station_id": "943db4cf",
                "num_bikes_available": 2,
                "is_installed": True,
                "is_renting": True,
                "is_returning": True,
                "last_reported": 1793790530,
            },
            {
                "station_id": "5b0f2a10",
                "num_bikes_available": 1,
                "is_installed": True,
                "is_renting": True,
                "is_returning": True,
                "last_reported": 1793783603,
            },
            {
                "station_id": "77aa01c3",
                "num_bikes_available": 0,
                "is_installed": True,
                "is_renting": True,
                "is_returning": True,
                "last_reported": 1793783603,
            },
        ]
    },
}

_VOI_BIKES = {
    "version": "2.3",
    "data": {
        "bikes": [
            # Three bikes on the first spot, one of them out of order.
            {
                "bike_id": "a",
                "lat": 47.21721,
                "lon": -1.55451,
                "current_range_meters": 45200,
                "is_disabled": False,
            },
            {
                "bike_id": "b",
                "lat": 47.21718,
                "lon": -1.55448,
                "current_range_meters": 12000,
                "is_disabled": False,
            },
            {
                "bike_id": "c",
                "lat": 47.21722,
                "lon": -1.55449,
                "current_range_meters": 70000,
                "is_disabled": True,
            },
            # One on the second spot.
            {
                "bike_id": "d",
                "lat": 47.2180,
                "lon": -1.5540,
                "current_range_meters": 30000,
                "is_disabled": False,
            },
            # Parked away from every spot.
            {
                "bike_id": "e",
                "lat": 47.2250,
                "lon": -1.5400,
                "current_range_meters": 80000,
                "is_disabled": False,
            },
        ]
    },
}

_STOPS = [
    {"id": "S1", "name": "Hôtel de Ville", "lat": 47.2178, "lon": -1.5539},
    {"id": "S2", "name": "Far away", "lat": 47.40, "lon": -1.70},
]


@pytest.fixture(autouse=True)
def _stop_index():
    """Serve a tiny stop index instead of the embedded one."""
    with patch("custom_components.naolib.bike.load_stops", return_value=_STOPS):
        yield


@pytest.mark.parametrize(
    ("code", "stop", "label"),
    [
        ("NAN_CEN_064", "Hôtel de Ville", "Hôtel de Ville · Centre-ville 064"),
        ("NAN_MAL_046-3", None, "Malakoff-Saint-Donatien 046-3"),
        ("REZ_021", None, "Rezé 021"),
        # An area that is not known yet is shown as is.
        ("HER_004", "Frachon", "Frachon · HER 004"),
        ("Gare Sud", None, "Gare Sud"),
        ("", "Gare Sud", "Gare Sud"),
        ("", None, "Emplacement Voi"),
    ],
)
def test_voi_label(code: str, stop: str | None, label: str) -> None:
    """The codes are turned into names a person recognizes."""
    assert voi_label(code, stop) == label


def test_parse_stations_keeps_the_codes_of_a_coded_feed() -> None:
    """A code must not be rewritten as if it were a shouty name."""
    stations = parse_stations(_VOI_INFORMATION, coded=True)

    assert stations[0]["code"] == "NAN_CEN_064"
    assert stations[0]["name"] == "NAN_CEN_064"
    assert stations[0]["capacity"] == 8
    # An empty code still gives the station a name.
    assert stations[2]["code"] == ""
    assert stations[2]["name"] == "77aa01c3"


def test_label_spots_names_them_after_the_closest_stop() -> None:
    """Only a stop within reach lends its name."""
    spots = label_spots(parse_stations(_VOI_INFORMATION, coded=True))

    assert [spot["name"] for spot in spots] == [
        "Hôtel de Ville · Centre-ville 064",
        "Hôtel de Ville · Centre-ville 065",
        "Emplacement Voi",
    ]
    assert spots[0]["code"] == "NAN_CEN_064"


def test_parse_vehicles_keeps_the_range_and_drops_the_ids() -> None:
    """Bike ids may rotate after each trip, so nothing relies on them."""
    vehicles = parse_vehicles(_VOI_BIKES)

    assert len(vehicles) == 5
    assert vehicles[0] == {
        "lat": 47.21721,
        "lon": -1.55451,
        "range_km": 45,
        "disabled": False,
    }


def test_parse_vehicles_accepts_gbfs_3_and_skips_the_unplaced_bikes() -> None:
    """3.0 renamed the list; a bike without coordinates cannot be placed."""
    payload = {
        "data": {
            "vehicles": [
                {"lat": 47.2, "lon": -1.5},
                {"lat": None, "lon": -1.5},
                {"lon": -1.5},
            ]
        }
    }

    assert parse_vehicles(payload) == [
        {"lat": 47.2, "lon": -1.5, "range_km": None, "disabled": False}
    ]


def _voi_network() -> dict:
    stations = parse_stations(_VOI_INFORMATION, coded=True)
    return {station["id"]: {**station} for station in stations}


def test_attach_vehicles_hangs_each_bike_on_its_spot() -> None:
    """The bikes go to the spot they stand on, best range first."""
    network = _voi_network()

    attach_vehicles(network, parse_vehicles(_VOI_BIKES))

    assert network["943db4cf"]["vehicles"] == [
        {"range_km": 70, "disabled": True},
        {"range_km": 45, "disabled": False},
        {"range_km": 12, "disabled": False},
    ]
    assert network["5b0f2a10"]["vehicles"] == [{"range_km": 30, "disabled": False}]
    # The bike parked away from every spot belongs to none.
    assert network["77aa01c3"]["vehicles"] == []


def test_attach_vehicles_looks_across_the_grid_cells() -> None:
    """A bike just across a cell boundary still finds its spot."""
    network = {
        "x": {"id": "x", "lat": 47.21799, "lon": -1.55001},
    }
    vehicles = [
        {"lat": 47.21801, "lon": -1.54999, "range_km": 20, "disabled": False},
        {"lat": 47.21801, "lon": -1.54999, "range_km": None, "disabled": False},
    ]

    attach_vehicles(network, vehicles)

    assert network["x"]["vehicles"] == [
        {"range_km": 20, "disabled": False},
        {"range_km": None, "disabled": False},
    ]


def test_best_range_ignores_the_bikes_that_cannot_be_rented() -> None:
    """A disabled bike or an unknown range never counts."""
    vehicles = [
        {"range_km": 70, "disabled": True},
        {"range_km": None, "disabled": False},
        {"range_km": 45, "disabled": False},
    ]

    assert best_range(vehicles) == 45
    assert best_range([{"range_km": 70, "disabled": True}]) is None
    assert best_range([]) is None
    assert best_range(None) is None


def test_feed_of_defaults_to_jcdecaux() -> None:
    """Entries created before Voi have no provider and read JCDecaux."""
    assert feed_of({}) is JCDECAUX_FEED
    assert feed_of({CONF_BIKE_PROVIDER: BIKE_PROVIDER_VOI}) is VOI_FEED
    assert feed_of({CONF_BIKE_PROVIDER: "unknown"}) is JCDECAUX_FEED


def test_station_keys_keep_the_legacy_ids() -> None:
    """JCDecaux ids stay bare so the existing unique ids do not change."""
    assert station_key(BIKE_PROVIDER_JCDECAUX, "12") == "12"
    assert station_key(BIKE_PROVIDER_VOI, "943db4cf") == "voi_943db4cf"
    station = NaolibBikeStation(
        id="943db4cf", name="Spot", interval=60, provider=BIKE_PROVIDER_VOI
    )
    assert station.key == "voi_943db4cf"


async def test_async_fetch_stations_labels_the_voi_spots(
    hass: HomeAssistant, aioclient_mock
) -> None:
    """The config flow lists the spots under their readable names."""
    aioclient_mock.get(VOI_STATION_INFORMATION_URL, json=_VOI_INFORMATION)

    stations = await async_fetch_stations(hass, VOI_FEED)

    assert stations[0]["name"] == "Hôtel de Ville · Centre-ville 064"


async def test_voi_coordinator_places_the_bikes(hass: HomeAssistant) -> None:
    """A poll reads the spots, their counters and every bike."""
    coordinator = NaolibBikeCoordinator(hass, VOI_FEED)

    with patch(
        "custom_components.naolib.bike._async_get_json",
        side_effect=[_VOI_INFORMATION, _VOI_STATUS, _VOI_BIKES],
    ):
        network = await coordinator._async_update_data()

    spot = network["943db4cf"]
    assert spot["name"] == "Hôtel de Ville · Centre-ville 064"
    assert spot["bikes"] == 2
    assert spot["docks"] is None
    assert len(spot["vehicles"]) == 3


async def test_voi_coordinator_keeps_the_bikes_through_a_failure(
    hass: HomeAssistant,
) -> None:
    """A failed bike request reuses the last bikes instead of blanking them."""
    coordinator = NaolibBikeCoordinator(hass, VOI_FEED)
    with patch(
        "custom_components.naolib.bike._async_get_json",
        side_effect=[_VOI_INFORMATION, _VOI_STATUS, _VOI_BIKES],
    ):
        await coordinator._async_update_data()

    with patch(
        "custom_components.naolib.bike._async_get_json",
        side_effect=[_VOI_STATUS, None],
    ):
        network = await coordinator._async_update_data()

    assert len(network["943db4cf"]["vehicles"]) == 3


async def test_voi_coordinator_without_any_bike_yet(hass: HomeAssistant) -> None:
    """Until the bikes are read once, no range is reported rather than none."""
    coordinator = NaolibBikeCoordinator(hass, VOI_FEED)

    with patch(
        "custom_components.naolib.bike._async_get_json",
        side_effect=[_VOI_INFORMATION, _VOI_STATUS, None],
    ):
        network = await coordinator._async_update_data()

    station = NaolibBikeStation(
        id="943db4cf", name="Spot", interval=60, provider=BIKE_PROVIDER_VOI
    )
    data = build_station_data(network, station)
    assert data["vehicles"] is None
    assert data["best_range_km"] is None


async def test_build_station_data_reports_the_ranges(hass: HomeAssistant) -> None:
    """The spot and its neighbours carry their best range."""
    coordinator = NaolibBikeCoordinator(hass, VOI_FEED)
    with patch(
        "custom_components.naolib.bike._async_get_json",
        side_effect=[_VOI_INFORMATION, _VOI_STATUS, _VOI_BIKES],
    ):
        network = await coordinator._async_update_data()

    station = NaolibBikeStation(
        id="943db4cf", name="Spot", interval=60, provider=BIKE_PROVIDER_VOI
    )
    data = build_station_data(network, station)

    assert data["code"] == "NAN_CEN_064"
    assert data["best_range_km"] == 45
    assert data["nearby_stations"][0]["station_id"] == "5b0f2a10"
    assert data["nearby_stations"][0]["best_range_km"] == 30


# --- Retirement of the JCDecaux stations -------------------------------------

_JCD_INFORMATION = {
    "data": {
        "stations": [
            {"station_id": "1", "name": "PRÉFECTURE", "lat": 47.2198, "lon": -1.5548},
            {"station_id": "2", "name": "COMMERCE", "lat": 47.2143, "lon": -1.5595},
        ]
    }
}


def _jcd_status(*, first: bool = True, installed: bool = True) -> dict:
    stations = [{"station_id": "2", "num_vehicles_available": 3}]
    if first:
        stations.append(
            {"station_id": "1", "num_vehicles_available": 1, "is_installed": installed}
        )
    return {"data": {"stations": stations}}


def _issue(hass: HomeAssistant, key: str = "entry") -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, retired_issue_id(key))


async def _poll(coordinator: NaolibBikeCoordinator, *payloads: dict | None) -> None:
    with patch(
        "custom_components.naolib.bike._async_get_json", side_effect=list(payloads)
    ):
        coordinator.data = await coordinator._async_update_data()


async def _tracked_jcdecaux(hass: HomeAssistant) -> NaolibBikeCoordinator:
    """Return a JCDecaux coordinator tracking station 1, polled once."""
    coordinator = NaolibBikeCoordinator(hass, JCDECAUX_FEED)
    coordinator.register(
        "entry", NaolibBikeStation(id="1", name="Préfecture", interval=60)
    )
    await _poll(coordinator, _JCD_INFORMATION, _jcd_status())
    return coordinator


async def test_a_station_missing_for_a_few_polls_is_retired(
    hass: HomeAssistant,
) -> None:
    """The repair offers to move the station, starting from where it stood."""
    coordinator = await _tracked_jcdecaux(hass)

    for _ in range(BIKE_RETIRED_AFTER_POLLS - 1):
        await _poll(coordinator, _jcd_status(first=False))
    assert _issue(hass) is None

    await _poll(coordinator, _jcd_status(first=False))
    issue = _issue(hass)
    assert issue is not None
    assert issue.is_fixable
    assert issue.translation_placeholders == {"station": "Préfecture"}
    assert issue.data == {
        "entry_id": "entry",
        "latitude": 47.2198,
        "longitude": -1.5548,
    }

    # Raised once, not on every poll.
    ir.async_get(hass).async_delete(DOMAIN, retired_issue_id("entry"))
    await _poll(coordinator, _jcd_status(first=False))
    assert _issue(hass) is None


async def test_an_uninstalled_station_is_retired(hass: HomeAssistant) -> None:
    """A station still listed but uninstalled is gone just the same."""
    coordinator = await _tracked_jcdecaux(hass)

    for _ in range(BIKE_RETIRED_AFTER_POLLS):
        await _poll(coordinator, _jcd_status(installed=False))

    assert _issue(hass) is not None


async def test_a_station_back_in_service_drops_its_issue(hass: HomeAssistant) -> None:
    """A station that comes back was only closed for a while."""
    coordinator = await _tracked_jcdecaux(hass)
    for _ in range(BIKE_RETIRED_AFTER_POLLS):
        await _poll(coordinator, _jcd_status(first=False))
    assert _issue(hass) is not None

    await _poll(coordinator, _jcd_status())

    assert _issue(hass) is None


async def test_a_short_absence_raises_nothing(hass: HomeAssistant) -> None:
    """A station missing for a poll or two is not retired."""
    coordinator = await _tracked_jcdecaux(hass)

    await _poll(coordinator, _jcd_status(first=False))
    await _poll(coordinator, _jcd_status())
    for _ in range(BIKE_RETIRED_AFTER_POLLS - 1):
        await _poll(coordinator, _jcd_status(first=False))

    assert _issue(hass) is None


async def test_a_feed_down_for_a_while_retires_nothing(hass: HomeAssistant) -> None:
    """An outage is not a retirement."""
    coordinator = await _tracked_jcdecaux(hass)

    for _ in range(BIKE_RETIRED_AFTER_POLLS + 1):
        await _poll(coordinator, None, None)

    assert _issue(hass) is None


async def test_a_feed_gone_for_a_day_retires_every_station(
    hass: HomeAssistant,
) -> None:
    """The operator may switch the feed off rather than empty it."""
    coordinator = NaolibBikeCoordinator(hass, JCDECAUX_FEED)
    coordinator.register(
        "entry", NaolibBikeStation(id="1", name="Préfecture", interval=60)
    )
    coordinator.data = {}
    coordinator._failing_since = dt_util.utcnow() - timedelta(days=2)

    for _ in range(BIKE_RETIRED_AFTER_POLLS):
        await _poll(coordinator, None, None)

    issue = _issue(hass)
    assert issue is not None
    # Never described: the repair starts from the home location instead.
    assert issue.data == {"entry_id": "entry"}


async def test_voi_spots_are_never_retired(hass: HomeAssistant) -> None:
    """Only the network being dismantled is watched."""
    coordinator = NaolibBikeCoordinator(hass, VOI_FEED)
    coordinator.register(
        "entry",
        NaolibBikeStation(id="gone", name="Spot", interval=60, provider="voi"),
    )

    for _ in range(BIKE_RETIRED_AFTER_POLLS + 1):
        await _poll(coordinator, _VOI_INFORMATION, _VOI_STATUS, _VOI_BIKES)
        coordinator._info = {}

    assert _issue(hass) is None
