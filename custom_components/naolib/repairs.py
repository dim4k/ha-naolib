"""Repairs for the Naolib integration.

The JCDecaux bike stations (ex-Bicloo) are dismantled as the Voi spots open.
When one of them leaves the feed, its entry gets a fixable issue that moves it
to a nearby Voi spot, keeping its device and its "bikes available" entity, so
the cards and automations built on it keep working.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .bike import station_key
from .config_flow import (
    async_fetch_voi_stations,
    find_place,
    location_schema,
    selection_schema,
    voi_station_entry,
)
from .const import (
    BIKE_ID_PREFIX,
    BIKE_PROVIDER_JCDECAUX,
    BIKE_PROVIDER_VOI,
    CONF_BIKE_PROVIDER,
    CONF_LOCATION,
    CONF_STATION_ID,
    DOMAIN,
)
from .sensor import bikes_unique_id
from .stops import nearest


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the flow fixing an issue; only retired stations are fixable."""
    data = data or {}
    latitude, longitude = data.get("latitude"), data.get("longitude")
    position = (
        (float(latitude), float(longitude))
        if latitude is not None and longitude is not None
        else None
    )
    return BikeStationRetiredFlow(str(data.get("entry_id")), position)


class BikeStationRetiredFlow(RepairsFlow):
    """Move an entry from a retired JCDecaux station to a Voi spot."""

    def __init__(self, entry_id: str, position: tuple[float, float] | None) -> None:
        """Initialize the flow."""
        self._entry_id = entry_id
        self._position = position
        self._stations: list[dict[str, Any]] = []

    def _entry(self) -> ConfigEntry | None:
        """Return the entry being fixed, if it still exists."""
        return self.hass.config_entries.async_get_entry(self._entry_id)

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Start from the map."""
        if self._entry() is None:
            return self.async_abort(reason="entry_removed")
        return await self.async_step_location()

    async def async_step_location(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Pick where to look for a Voi spot: the old station, when it is known."""
        latitude, longitude = self._position or (
            self.hass.config.latitude,
            self.hass.config.longitude,
        )
        schema = location_schema(latitude, longitude)
        entry = self._entry()
        placeholders = {"station": entry.title if entry else ""}
        if user_input is None:
            return self.async_show_form(
                step_id="location",
                data_schema=schema,
                description_placeholders=placeholders,
            )

        location = user_input[CONF_LOCATION]
        stations = await async_fetch_voi_stations(self.hass)
        if stations is None:
            error = "cannot_connect"
        else:
            self._stations = nearest(
                stations, location["latitude"], location["longitude"]
            )
            if self._stations:
                return await self.async_step_select()
            error = "no_stations_found"

        return self.async_show_form(
            step_id="location",
            data_schema=schema,
            description_placeholders=placeholders,
            errors={"base": error},
        )

    async def async_step_select(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose the Voi spot replacing the station, then move the entry."""
        station = (
            None
            if user_input is None
            else find_place(self._stations, user_input[CONF_STATION_ID])
        )
        if station is None:
            return self.async_show_form(
                step_id="select",
                data_schema=selection_schema(CONF_STATION_ID, self._stations),
                errors={"base": "not_in_list"} if user_input is not None else None,
            )

        entry = self._entry()
        if entry is None:
            return self.async_abort(reason="entry_removed")
        target = voi_station_entry(station)
        if any(
            other.unique_id == target["unique_id"]
            for other in self.hass.config_entries.async_entries(DOMAIN)
            if other.entry_id != entry.entry_id
        ):
            return self.async_abort(reason="already_configured")

        _async_move_registry(
            self.hass, entry, station_key(BIKE_PROVIDER_VOI, station["id"])
        )
        # The update listener reloads the entry onto the Voi coordinator.
        self.hass.config_entries.async_update_entry(entry, **target)
        return self.async_create_entry(data={})


@callback
def _async_move_registry(hass: HomeAssistant, entry: ConfigEntry, new_key: str) -> None:
    """Hand the entry's device and "bikes available" entity over to the new spot.

    The device is re-keyed rather than recreated: removing it would take its
    entities along. The docks sensor goes, since a Voi spot has no dock.
    """
    old_key = station_key(
        entry.data.get(CONF_BIKE_PROVIDER, BIKE_PROVIDER_JCDECAUX),
        entry.data[CONF_STATION_ID],
    )
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{BIKE_ID_PREFIX}{old_key}")}
    )
    if device is not None:
        device_registry.async_update_device(
            device.id, new_identifiers={(DOMAIN, f"{BIKE_ID_PREFIX}{new_key}")}
        )

    entity_registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.unique_id == bikes_unique_id(old_key):
            entity_registry.async_update_entity(
                entity.entity_id, new_unique_id=bikes_unique_id(new_key)
            )
        else:
            entity_registry.async_remove(entity.entity_id)
