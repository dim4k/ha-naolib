#!/usr/bin/env python3
"""Generate the embedded stop index for the Tan Nantes integration.

The Naolib real-time SIRI API only accepts ``FR_NAOLIB:Quay:*`` identifiers,
which are published exclusively in the GTFS feed. This script downloads the
current Nantes Metropole GTFS, extracts the stops, and produces a compact
``stops_index.json`` mapping each station (StopPlace) to its quays.

The generated file is consumed locally by the config flow (proximity / name
search) so the integration never needs a network call to look up stops.

Usage:
    python scripts/generate_stops_index.py

Run from the repository root. Requires only the Python standard library.
"""

from __future__ import annotations

import csv
import io
import json
import urllib.request
import zipfile
from pathlib import Path

# Opendatasoft record describing the current GTFS export.
GTFS_DATASET_URL = (
    "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/"
    "244400404_transports_commun_naolib_nantes_metropole_gtfs/records?limit=1"
)

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "tan_nantes"
    / "data"
    / "stops_index.json"
)


def _resolve_gtfs_url() -> str:
    """Resolve the direct download URL of the current GTFS zip."""
    with urllib.request.urlopen(GTFS_DATASET_URL, timeout=60) as response:
        payload = json.load(response)
    results = payload.get("results") or []
    if not results:
        raise RuntimeError("No GTFS export found in the opendatasoft dataset")
    return results[0]["fichier"]["url"]


def _download_stops(zip_url: str) -> list[dict[str, str]]:
    """Download the GTFS archive and return the parsed ``stops.txt`` rows."""
    with urllib.request.urlopen(zip_url, timeout=120) as response:
        archive = response.read()
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        with zf.open("stops.txt") as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8-sig")
            return list(csv.DictReader(text))


def build_index(rows: list[dict[str, str]]) -> list[dict]:
    """Build the station index from GTFS stop rows.

    Each entry is a station (``location_type == "1"``) with its child quays
    (``location_type == "0"``) grouped by ``parent_station``.
    """
    stations: dict[str, dict] = {}
    quays_by_parent: dict[str, list[str]] = {}

    for row in rows:
        stop_id = row["stop_id"]
        location_type = row.get("location_type", "")
        if location_type == "1":
            try:
                lat = round(float(row["stop_lat"]), 5)
                lon = round(float(row["stop_lon"]), 5)
            except (KeyError, ValueError):
                continue
            stations[stop_id] = {
                "id": stop_id,
                "name": row["stop_name"],
                "lat": lat,
                "lon": lon,
                "quays": [],
            }
        elif location_type == "0":
            parent = row.get("parent_station") or ""
            if parent:
                quays_by_parent.setdefault(parent, []).append(stop_id)

    for parent, quays in quays_by_parent.items():
        station = stations.get(parent)
        if station is not None:
            station["quays"] = sorted(quays)

    # Keep only stations that actually expose at least one quay.
    index = [s for s in stations.values() if s["quays"]]
    index.sort(key=lambda s: s["id"])
    return index


def main() -> None:
    zip_url = _resolve_gtfs_url()
    rows = _download_stops(zip_url)
    index = build_index(rows)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")

    print(f"Wrote {len(index)} stations to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
