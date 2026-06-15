"""Diagnostics support for the Naolib integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import NaolibConfigEntry

TO_REDACT = {"latitude", "longitude"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NaolibConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    network = coordinator.data or {}

    return {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            "indexed_quays": len(network),
            "total_departures": sum(len(visits) for visits in network.values()),
        },
    }
