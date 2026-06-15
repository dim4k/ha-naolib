"""Embedded stop index helpers (loading and nearby search)."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from .const import NEARBY_STOPS_LIMIT, STOPS_INDEX_FILE

_INDEX_PATH = Path(__file__).parent / STOPS_INDEX_FILE


@lru_cache(maxsize=1)
def load_stops() -> list[dict[str, Any]]:
    """Load the embedded stop index (cached).

    This performs blocking file IO and must be called from an executor.
    """
    with _INDEX_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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
        {**stop, "distance": round(_haversine(lat, lon, stop["lat"], stop["lon"]))}
        for stop in stops
    ]
    scored.sort(key=lambda stop: stop["distance"])
    return scored[:limit]


def get_stop(stop_id: str) -> dict[str, Any] | None:
    """Return a stop entry by its StopPlace id."""
    for stop in load_stops():
        if stop["id"] == stop_id:
            return stop
    return None
