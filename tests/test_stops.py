"""Tests for the embedded stops index."""

from unittest.mock import patch

from custom_components.naolib.stops import (
    load_stops,
    nearby_stops,
    normalize,
    stops_within,
    within,
)

# Commerce, in the centre of Nantes.
_LAT, _LON = 47.2143, -1.5595


def test_load_stops_is_not_empty() -> None:
    """The shipped index contains the network stops."""
    stops = load_stops()

    assert stops
    assert {"lat", "lon"} <= set(stops[0])


def test_nearby_stops_are_sorted_by_distance() -> None:
    """Results are the closest stops, nearest first, capped by ``limit``."""
    stops = nearby_stops(_LAT, _LON, limit=5)

    assert len(stops) == 5
    distances = [stop["distance"] for stop in stops]
    assert distances == sorted(distances)
    assert distances[0] < 1000


def test_unreadable_index_is_tolerated() -> None:
    """A missing or corrupt index yields no stop rather than an error."""
    load_stops.cache_clear()
    with patch("pathlib.Path.open", side_effect=OSError("boom")):
        assert load_stops() == []
    load_stops.cache_clear()


def test_normalize_folds_case_and_accents() -> None:
    """The sort key ignores case and accents, so "État" lands next to "Etat"."""
    assert normalize("Gare de l'État") == normalize("GARE DE L'ETAT")


def test_within_keeps_only_places_inside_the_radius() -> None:
    """``within`` drops places beyond the radius and sorts the rest."""
    places = [
        {"id": "near", "lat": _LAT, "lon": _LON},
        {"id": "mid", "lat": _LAT + 0.002, "lon": _LON},  # ~222 m
        {"id": "far", "lat": _LAT + 0.05, "lon": _LON},  # ~5.5 km
    ]

    result = within(places, _LAT, _LON, radius=300, limit=10)

    assert [place["id"] for place in result] == ["near", "mid"]
    assert result[0]["distance"] <= result[1]["distance"]


def test_within_caps_to_the_limit() -> None:
    """``within`` returns at most ``limit`` places."""
    places = [{"id": str(i), "lat": _LAT, "lon": _LON} for i in range(5)]

    assert len(within(places, _LAT, _LON, radius=100, limit=2)) == 2


def test_stops_within_reads_the_embedded_index() -> None:
    """``stops_within`` returns nearby real stops within the radius."""
    stops = stops_within(_LAT, _LON, radius=500, limit=10)

    assert stops
    assert all(stop["distance"] <= 500 for stop in stops)
