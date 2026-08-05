"""Embedded stop index helpers (loading and nearby search)."""

from __future__ import annotations

from functools import lru_cache
import json
import logging
import math
from pathlib import Path
from typing import Any
import unicodedata

from .const import NEARBY_STOPS_LIMIT, STOPS_INDEX_FILE

_LOGGER = logging.getLogger(__name__)

_INDEX_PATH = Path(__file__).parent / STOPS_INDEX_FILE


@lru_cache(maxsize=1)
def load_stops() -> list[dict[str, Any]]:
    """Load the embedded stop index (cached).

    This performs blocking file IO and must be called from an executor.
    """
    try:
        with _INDEX_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exception:
        _LOGGER.error("Could not read the embedded stop index: %s", exception)
        return []


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in meters between two points."""
    radius = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def nearby_stops(
    lat: float, lon: float, limit: int = NEARBY_STOPS_LIMIT
) -> list[dict[str, Any]]:
    """Return the closest stops to a location, with their distance in meters."""
    stops = load_stops()
    scored = [
        {**stop, "distance": round(haversine(lat, lon, stop["lat"], stop["lon"]))}
        for stop in stops
    ]
    scored.sort(key=lambda stop: stop["distance"])
    return scored[:limit]


def normalize(value: str) -> str:
    """Fold case and strip accents, so "Gare de l'Etat" sorts next to "l'État"."""
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))
