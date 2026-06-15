#!/usr/bin/env python3
"""Generate the embedded stop index and timetables for the Tan Nantes integration.

The Naolib real-time SIRI API only accepts ``FR_NAOLIB:Quay:*`` identifiers,
which are published exclusively in the GTFS feed. This script downloads the
current Nantes Metropole GTFS and produces, fully offline:

* ``stops_index.json`` — each station (StopPlace) mapped to its quays, used by
  the config flow for the proximity / name search.
* ``schedules.json`` — the theoretical daily timetable for every station,
  grouped by line/direction and indexed by GTFS service.
* ``calendar.json`` — the service calendar (regular days + exceptions) used at
  runtime to pick the timetable active for the current date.

These files are consumed locally so the integration never needs a network call
to look up stops or show the full timetable.

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
from collections import Counter
from pathlib import Path
from typing import Iterator

# Opendatasoft record describing the current GTFS export.
GTFS_DATASET_URL = (
    "https://data.nantesmetropole.fr/api/explore/v2.1/catalog/datasets/"
    "244400404_transports_commun_naolib_nantes_metropole_gtfs/records?limit=1"
)

_DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "tan_nantes"
    / "data"
)

OUTPUT_PATH = _DATA_DIR / "stops_index.json"
SCHEDULES_PATH = _DATA_DIR / "schedules.json"
CALENDAR_PATH = _DATA_DIR / "calendar.json"

_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def _resolve_gtfs_url() -> str:
    """Resolve the direct download URL of the current GTFS zip."""
    with urllib.request.urlopen(GTFS_DATASET_URL, timeout=60) as response:
        payload = json.load(response)
    results = payload.get("results") or []
    if not results:
        raise RuntimeError("No GTFS export found in the opendatasoft dataset")
    return results[0]["fichier"]["url"]


def _download_archive(zip_url: str) -> bytes:
    """Download the GTFS archive and return its raw bytes."""
    with urllib.request.urlopen(zip_url, timeout=120) as response:
        return response.read()


def _read_member(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    """Read a CSV member of the archive fully into a list of rows."""
    with zf.open(name) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig")
        return list(csv.DictReader(text))


def _iter_member(zf: zipfile.ZipFile, name: str) -> Iterator[dict[str, str]]:
    """Stream a (potentially large) CSV member row by row."""
    with zf.open(name) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig")
        yield from csv.DictReader(text)


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


def build_quay_to_station(rows: list[dict[str, str]]) -> dict[str, str]:
    """Map each quay id to its parent station id."""
    mapping: dict[str, str] = {}
    for row in rows:
        if row.get("location_type", "") == "0":
            parent = row.get("parent_station") or ""
            if parent:
                mapping[row["stop_id"]] = parent
    return mapping


def _hhmm(departure_time: str) -> str | None:
    """Normalize a GTFS departure time to a ``HHMM`` string (hour mod 24)."""
    parts = departure_time.split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0]) % 24
        minute = int(parts[1])
    except ValueError:
        return None
    return f"{hour:02d}{minute:02d}"


def build_schedules(
    zf: zipfile.ZipFile, quay_to_station: dict[str, str]
) -> dict[str, dict]:
    """Build per-station theoretical timetables from the GTFS feed.

    Returns ``{station_id: {group_key: {line, direction, destination,
    services: {service_id: [HHMM, ...]}}}}``.
    """
    routes = {
        row["route_id"]: (row.get("route_short_name") or row.get("route_id") or "")
        for row in _iter_member(zf, "routes.txt")
    }

    trips: dict[str, tuple[str, str, int, str]] = {}
    for row in _iter_member(zf, "trips.txt"):
        line = routes.get(row.get("route_id", ""), "")
        try:
            direction = int(row.get("direction_id") or 0) + 1
        except ValueError:
            direction = 1
        trips[row["trip_id"]] = (
            line,
            row.get("service_id", ""),
            direction,
            (row.get("trip_headsign") or "").strip(),
        )

    # station_id -> group_key -> accumulator
    stations: dict[str, dict[str, dict]] = {}

    for row in _iter_member(zf, "stop_times.txt"):
        trip = trips.get(row.get("trip_id", ""))
        if trip is None:
            continue
        station = quay_to_station.get(row.get("stop_id", ""))
        if station is None:
            continue
        time = _hhmm(row.get("departure_time") or row.get("arrival_time") or "")
        if time is None:
            continue

        line, service_id, direction, headsign = trip
        group_key = f"{line}|{direction}"
        group = stations.setdefault(station, {}).setdefault(
            group_key,
            {
                "line": line,
                "direction": direction,
                "headsigns": Counter(),
                "services": {},
            },
        )
        if headsign:
            group["headsigns"][headsign] += 1
        group["services"].setdefault(service_id, set()).add(time)

    # Finalize: pick a destination and turn time sets into sorted lists.
    result: dict[str, dict] = {}
    for station, groups in stations.items():
        out_groups: dict[str, dict] = {}
        for group_key, group in groups.items():
            headsigns: Counter = group["headsigns"]
            destination = headsigns.most_common(1)[0][0] if headsigns else ""
            out_groups[group_key] = {
                "line": group["line"],
                "direction": group["direction"],
                "destination": destination,
                "services": {
                    service_id: sorted(times)
                    for service_id, times in group["services"].items()
                },
            }
        result[station] = out_groups
    return result


def build_calendar(zf: zipfile.ZipFile) -> dict[str, dict]:
    """Build the service calendar (regular days + exceptions)."""
    calendar: dict[str, dict] = {}

    try:
        for row in _iter_member(zf, "calendar.txt"):
            service_id = row.get("service_id", "")
            if not service_id:
                continue
            calendar[service_id] = {
                "days": [int(row.get(day, "0") or 0) for day in _WEEKDAYS],
                "start": row.get("start_date", ""),
                "end": row.get("end_date", ""),
                "added": [],
                "removed": [],
            }
    except KeyError:
        # Some feeds rely solely on calendar_dates.txt.
        pass

    try:
        for row in _iter_member(zf, "calendar_dates.txt"):
            service_id = row.get("service_id", "")
            date = row.get("date", "")
            if not service_id or not date:
                continue
            entry = calendar.setdefault(
                service_id,
                {"days": [0, 0, 0, 0, 0, 0, 0], "start": "", "end": "", "added": [], "removed": []},
            )
            if row.get("exception_type", "") == "1":
                entry["added"].append(date)
            elif row.get("exception_type", "") == "2":
                entry["removed"].append(date)
    except KeyError:
        pass

    return calendar


def _write_json(path: Path, data) -> None:
    """Write compact JSON to ``path``."""
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")


def main() -> None:
    zip_url = _resolve_gtfs_url()
    archive = _download_archive(zip_url)

    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        rows = _read_member(zf, "stops.txt")
        index = build_index(rows)
        _write_json(OUTPUT_PATH, index)
        print(f"Wrote {len(index)} stations to {OUTPUT_PATH}")

        quay_to_station = build_quay_to_station(rows)
        schedules = build_schedules(zf, quay_to_station)
        calendar = build_calendar(zf)

    # Drop stations that ended up without any timetable.
    schedules = {station: groups for station, groups in schedules.items() if groups}
    _write_json(SCHEDULES_PATH, schedules)
    print(f"Wrote {len(schedules)} station timetables to {SCHEDULES_PATH}")

    _write_json(CALENDAR_PATH, calendar)
    print(f"Wrote {len(calendar)} services to {CALENDAR_PATH}")


if __name__ == "__main__":
    main()
