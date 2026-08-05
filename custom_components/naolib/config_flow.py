"""Config flow for the Naolib integration."""

import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from .bike import GbfsUnavailableError, async_fetch_stations, nearby_stations
from .const import (
    CONF_ENTRY_TYPE,
    CONF_LOCATION,
    CONF_QUAYS,
    CONF_STATION_ID,
    CONF_STATION_LABEL,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_BIKE,
    ENTRY_TYPE_STOP,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)
from .stops import load_stops, nearby_stops, normalize

_LOGGER = logging.getLogger(__name__)

# A bike station and a stop could share an identifier, so station entries get
# their own unique_id namespace.
BIKE_UNIQUE_ID_PREFIX = "bike_"


class NaolibConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Naolib."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._stops: list[dict[str, Any]] = []
        self._stations: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step: choose what to track."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["stop", "bike"],
        )

    async def async_step_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to look for a transit stop."""
        return self.async_show_menu(
            step_id="stop",
            menu_options=["by_list", "by_location"],
        )

    async def async_step_bike(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to look for a bike station."""
        return self.async_show_menu(
            step_id="bike",
            menu_options=["bike_by_list", "bike_by_location"],
        )

    def _location_schema(self) -> vol.Schema:
        """Build the map form, centred on the home location."""
        default_location = {
            "latitude": self.hass.config.latitude,
            "longitude": self.hass.config.longitude,
        }
        return vol.Schema(
            {
                vol.Required(
                    CONF_LOCATION, default=default_location
                ): LocationSelector(),
            }
        )

    async def async_step_by_list(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer every stop of the network in one searchable dropdown."""
        stops = await self.hass.async_add_executor_job(load_stops)
        if not stops:
            return self.async_abort(reason="no_stops_found")

        self._stops = sorted(stops, key=lambda stop: normalize(stop["name"]))
        return await self.async_step_select_stop()

    async def async_step_by_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search the stops around a location picked on the map."""
        schema = self._location_schema()
        if user_input is None:
            return self.async_show_form(step_id="by_location", data_schema=schema)

        location = user_input[CONF_LOCATION]
        errors: dict[str, str] = {}
        try:
            self._stops = await self.hass.async_add_executor_job(
                nearby_stops, location["latitude"], location["longitude"]
            )
        except Exception:
            _LOGGER.exception("Failed to search for Naolib stops")
            errors["base"] = "unknown"
        else:
            if self._stops:
                return await self.async_step_select_stop()
            errors["base"] = "no_stops_found"

        return self.async_show_form(
            step_id="by_location", data_schema=schema, errors=errors
        )

    async def _async_fetch_stations(self) -> list[dict[str, Any]] | None:
        """Read the live station list, or None when the feed is unreachable."""
        try:
            return await async_fetch_stations(async_get_clientsession(self.hass))
        except GbfsUnavailableError:
            _LOGGER.warning("The Naolib GBFS feed could not be reached")
            return None

    async def async_step_bike_by_list(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer every bike station in one searchable dropdown."""
        stations = await self._async_fetch_stations()
        if stations is None:
            return self.async_abort(reason="cannot_connect")
        if not stations:
            return self.async_abort(reason="no_stations_found")

        self._stations = sorted(
            stations, key=lambda station: normalize(station["name"])
        )
        return await self.async_step_select_station()

    async def async_step_bike_by_location(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search the bike stations around a location picked on the map."""
        schema = self._location_schema()
        if user_input is None:
            return self.async_show_form(step_id="bike_by_location", data_schema=schema)

        location = user_input[CONF_LOCATION]
        errors: dict[str, str] = {}
        stations = await self._async_fetch_stations()
        if stations is None:
            errors["base"] = "cannot_connect"
        else:
            self._stations = nearby_stations(
                stations, location["latitude"], location["longitude"]
            )
            if self._stations:
                return await self.async_step_select_station()
            errors["base"] = "no_stations_found"

        return self.async_show_form(
            step_id="bike_by_location", data_schema=schema, errors=errors
        )

    async def async_step_select_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a bike station among the ones just found."""
        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]
            # The selector only accepts one of the stations we just found.
            station = next(s for s in self._stations if s["id"] == station_id)
            station_label = station["name"]
            unique_id = f"{BIKE_UNIQUE_ID_PREFIX}{station_id}"

            data = {
                CONF_ENTRY_TYPE: ENTRY_TYPE_BIKE,
                CONF_STATION_ID: station_id,
                CONF_STATION_LABEL: station_label,
            }
            title = f"Station vélo : {station_label}"

            await self.async_set_unique_id(unique_id)

            if self.source == config_entries.SOURCE_RECONFIGURE:
                reconfigure_entry = self._get_reconfigure_entry()
                # Reject if another entry already uses this station.
                for entry in self._async_current_entries():
                    if (
                        entry.entry_id != reconfigure_entry.entry_id
                        and entry.unique_id == unique_id
                    ):
                        return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=title,
                    unique_id=unique_id,
                    data=data,
                )

            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=title, data=data)

        options = [
            {
                "value": station["id"],
                "label": (
                    f"{station['name']} ({station['distance']} m)"
                    if "distance" in station
                    else station["name"]
                ),
            }
            for station in self._stations
        ]
        return self.async_show_form(
            step_id="select_station",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATION_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow changing the stop or station of an existing entry.

        The entry keeps its kind: turning a stop into a bike station would
        orphan its entities instead of updating them.
        """
        entry = self._get_reconfigure_entry()
        if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_BIKE:
            return await self.async_step_bike(user_input)
        return await self.async_step_stop(user_input)

    async def async_step_select_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the second step: choose a stop among the nearby ones."""
        if user_input is not None:
            stop_code = user_input[CONF_STOP_CODE]
            # The selector only accepts one of the stops we just found.
            stop = next(s for s in self._stops if s["id"] == stop_code)
            stop_label = stop["name"]

            data = {
                CONF_ENTRY_TYPE: ENTRY_TYPE_STOP,
                CONF_STOP_CODE: stop_code,
                CONF_STOP_LABEL: stop_label,
                CONF_QUAYS: stop["quays"],
            }

            await self.async_set_unique_id(stop_code)

            if self.source == config_entries.SOURCE_RECONFIGURE:
                reconfigure_entry = self._get_reconfigure_entry()
                # Reject if another entry already uses this stop.
                for entry in self._async_current_entries():
                    if (
                        entry.entry_id != reconfigure_entry.entry_id
                        and entry.unique_id == stop_code
                    ):
                        return self.async_abort(reason="already_configured")
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=f"Arrêt : {stop_label}",
                    unique_id=stop_code,
                    data=data,
                )

            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"Arrêt : {stop_label}",
                data=data,
            )

        options = [
            {
                "value": stop["id"],
                "label": (
                    f"{stop['name']} ({stop['distance']} m)"
                    if "distance" in stop
                    else stop["name"]
                ),
            }
            for stop in self._stops
        ]
        return self.async_show_form(
            step_id="select_stop",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP_CODE): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return NaolibOptionsFlow()


class NaolibOptionsFlow(OptionsFlow):
    """Handle options (polling interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UPDATE_INTERVAL, default=current): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_UPDATE_INTERVAL,
                            max=MAX_UPDATE_INTERVAL,
                            step=10,
                            unit_of_measurement="s",
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                }
            ),
        )
