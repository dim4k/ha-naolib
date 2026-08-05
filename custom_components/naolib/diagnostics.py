"""Diagnostics support for the Naolib integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import NaolibConfigEntry, _is_bike, async_frontend_diagnostics
from .bike import NaolibBikeCoordinator
from .coordinator import NaolibGlobalCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NaolibConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Nothing is redacted: an entry only holds a public stop code or station id,
    its label and the quays it serves.
    """
    coordinator = entry.runtime_data

    return {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            **(
                _bike_snapshot(coordinator)
                if _is_bike(entry)
                else _stop_snapshot(coordinator)
            ),
        },
        "frontend": await async_frontend_diagnostics(hass),
    }


def _stop_snapshot(coordinator: NaolibGlobalCoordinator) -> dict[str, Any]:
    """Report what the departures coordinator holds."""
    network = coordinator.data or {}
    return {
        "indexed_quays": len(network),
        "total_departures": sum(len(visits) for visits in network.values()),
    }


def _bike_snapshot(coordinator: NaolibBikeCoordinator) -> dict[str, Any]:
    """Report what the bike coordinator holds."""
    network = coordinator.data or {}
    return {
        "indexed_stations": len(network),
        "total_bikes_available": sum(
            station["bikes"] or 0 for station in network.values()
        ),
        "total_docks_available": sum(
            station["docks"] or 0 for station in network.values()
        ),
    }
