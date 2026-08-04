"""Tests for the embedded stops index."""

from unittest.mock import patch

from custom_components.naolib.stops import load_stops, nearby_stops, search_stops

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


def test_search_stops_matches_a_partial_name() -> None:
    """Typing part of a name is enough, and exact prefixes come first."""
    stops = search_stops("comme")

    assert stops
    assert stops[0]["name"] == "Commerce"


def test_search_stops_ignores_case_and_accents() -> None:
    """Accents and case are folded on both sides of the comparison."""
    assert search_stops("GARE DE L'ETAT")[0]["name"] == "Gare de l'État"


def test_search_stops_without_a_query() -> None:
    """A blank query matches nothing rather than the whole network."""
    assert search_stops("   ") == []
