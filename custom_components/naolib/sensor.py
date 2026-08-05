"""Sensor platform for the Naolib integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .bike import NaolibBikeCoordinator, NaolibBikeStation, build_station_data
from .const import DOMAIN
from .coordinator import NaolibGlobalCoordinator, NaolibStop, build_stop_data

if TYPE_CHECKING:
    from . import NaolibConfigEntry

# All entities read from a single shared coordinator, so there is no per-entity
# polling to serialize.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NaolibConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors based on the config entry."""
    coordinator = entry.runtime_data
    if isinstance(coordinator, NaolibBikeCoordinator):
        station = coordinator.stations[entry.entry_id]
        async_add_entities(
            [
                NaolibBikesAvailableSensor(coordinator, station),
                NaolibDocksAvailableSensor(coordinator, station),
            ]
        )
        return

    async_add_entities(
        [NaolibNextDeparturesSensor(coordinator, coordinator.stops[entry.entry_id])]
    )


class NaolibNextDeparturesSensor(
    CoordinatorEntity[NaolibGlobalCoordinator], SensorEntity
):
    """Represent the next bus at the stop."""

    _attr_has_entity_name = True
    _attr_translation_key = "next_departures"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_attribution = "Données Naolib / Okina"

    # The departures list is volatile (rebuilt on every poll); keep it out
    # of the recorder history to avoid bloating the database. It stays
    # available in the state machine for the card and automations.
    _unrecorded_attributes = frozenset({"next_departures"})

    def __init__(
        self,
        coordinator: NaolibGlobalCoordinator,
        stop: NaolibStop,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._stop = stop
        self._attr_unique_id = f"naolib_{stop.code}_next"
        self._attr_icon = "mdi:bus-clock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, stop.code)},
            name=f"Arrêt {stop.name}",
            manufacturer="Naolib",
            model="Arrêt",
        )
        self._stop_data = build_stop_data(coordinator.data or {}, stop)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Recompute the cached departures when new network data arrives."""
        self._stop_data = build_stop_data(self.coordinator.data or {}, self._stop)
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the very next bus, or None if none."""
        return self._stop_data["next_departure_dt"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return next passages and stop code as attributes."""
        return {
            "stop_code": self._stop.code,
            "stop_label": self._stop.name,
            "next_departures": self._stop_data["next_departures"],
        }


class NaolibBikeStationSensor(CoordinatorEntity[NaolibBikeCoordinator], SensorEntity):
    """Base class for the sensors of a bike station."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "vélos"
    _attr_attribution = "Données Naolib / JCDecaux"

    def __init__(
        self,
        coordinator: NaolibBikeCoordinator,
        station: NaolibBikeStation,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._station = station
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"bike_{station.id}")},
            name=f"Station vélo {station.name}",
            manufacturer="Naolib",
            model="Station vélo",
        )
        self._station_data = build_station_data(coordinator.data or {}, station)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Recompute the cached station data when new network data arrives."""
        self._station_data = build_station_data(
            self.coordinator.data or {}, self._station
        )
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Tell whether the station is present in the latest snapshot."""
        return super().available and self._station_data["available"]


class NaolibBikesAvailableSensor(NaolibBikeStationSensor):
    """Number of bikes ready to rent at the station."""

    _attr_translation_key = "bikes_available"
    _attr_icon = "mdi:bike"

    # Rebuilt on every poll and only useful to the card; keeping it out of the
    # recorder avoids bloating the database.
    _unrecorded_attributes = frozenset({"nearby_stations"})

    def __init__(
        self,
        coordinator: NaolibBikeCoordinator,
        station: NaolibBikeStation,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, station)
        self._attr_unique_id = f"naolib_bike_{station.id}_bikes"

    @property
    def native_value(self) -> int | None:
        """Return the number of available bikes."""
        return self._station_data.get("bikes")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the station details and its neighbours."""
        data = self._station_data
        return {
            "station_id": self._station.id,
            "station_label": data.get("name") or self._station.name,
            "address": data.get("address"),
            "capacity": data.get("capacity"),
            "docks_available": data.get("docks"),
            "is_installed": data.get("is_installed"),
            "is_renting": data.get("is_renting"),
            "is_returning": data.get("is_returning"),
            "last_reported": data.get("last_reported"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "nearby_stations": data["nearby_stations"],
        }


class NaolibDocksAvailableSensor(NaolibBikeStationSensor):
    """Number of free docks at the station."""

    _attr_translation_key = "docks_available"
    _attr_icon = "mdi:rhombus-outline"
    _attr_native_unit_of_measurement = "places"

    def __init__(
        self,
        coordinator: NaolibBikeCoordinator,
        station: NaolibBikeStation,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, station)
        self._attr_unique_id = f"naolib_bike_{station.id}_docks"

    @property
    def native_value(self) -> int | None:
        """Return the number of free docks."""
        return self._station_data.get("docks")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the station identity, for automations."""
        return {
            "station_id": self._station.id,
            "station_label": self._station_data.get("name") or self._station.name,
            "capacity": self._station_data.get("capacity"),
        }
