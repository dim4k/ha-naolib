"""Config flow for the Naolib integration."""

import logging
import math
from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    LocationSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from .bike import GbfsUnavailableError, async_fetch_stations
from .const import (
    CONF_ENTRY_TYPE,
    CONF_LOCATION,
    CONF_MAX_STOPS,
    CONF_QUAYS,
    CONF_RADIUS,
    CONF_SOURCE_ENTITY,
    CONF_STATION_ID,
    CONF_STATION_LABEL,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    CONF_UPDATE_INTERVAL,
    CONF_ZONE,
    CONF_ZONE_SECTION,
    DEFAULT_AROUND_MAX_STOPS,
    DEFAULT_AROUND_RADIUS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_AROUND,
    ENTRY_TYPE_BIKE,
    ENTRY_TYPE_STOP,
    MAX_AROUND_MAX_STOPS,
    MAX_AROUND_RADIUS,
    MAX_UPDATE_INTERVAL,
    MIN_AROUND_MAX_STOPS,
    MIN_AROUND_RADIUS,
    MIN_UPDATE_INTERVAL,
)
from .stops import load_stops, nearby_stops, nearest, normalize

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
            menu_options=["by_list", "by_location", "around"],
        )

    async def async_step_bike(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to look for a bike station."""
        return self.async_show_menu(
            step_id="bike",
            menu_options=["bike_by_list", "bike_by_location"],
        )

    def _home(self) -> dict[str, float]:
        """Return the home location, where the map marker starts."""
        return {
            "latitude": self.hass.config.latitude,
            "longitude": self.hass.config.longitude,
        }

    def _location_schema(self) -> vol.Schema:
        """Build the position form: a zone first, then the map.

        Forms cannot react to one field from another, so the precedence is
        applied on submit (see ``_searched_point``) and explained in the text.
        """
        return vol.Schema(
            {
                vol.Optional(CONF_ZONE_SECTION, default={}): section(
                    vol.Schema(
                        {
                            vol.Optional(CONF_ZONE): EntitySelector(
                                EntitySelectorConfig(domain="zone")
                            ),
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required(CONF_LOCATION, default=self._home()): LocationSelector(),
            }
        )

    def _searched_point(self, user_input: dict[str, Any]) -> tuple[float, float] | None:
        """Return the point to search around.

        A picked zone is used unless the marker was moved away from home: a
        moved marker is the more deliberate choice, so the zone is ignored.
        None means the zone to use has no coordinates.
        """
        location = user_input[CONF_LOCATION]
        home = self._home()
        moved = not (
            math.isclose(location["latitude"], home["latitude"], abs_tol=1e-6)
            and math.isclose(location["longitude"], home["longitude"], abs_tol=1e-6)
        )
        zone = user_input.get(CONF_ZONE_SECTION, {}).get(CONF_ZONE)
        if zone and not moved:
            return self._zone_center(zone)
        return location["latitude"], location["longitude"]

    def _zone_center(self, entity_id: str) -> tuple[float, float] | None:
        """Return the centre of a zone, or None if it has no coordinates."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        latitude = state.attributes.get("latitude")
        longitude = state.attributes.get("longitude")
        if latitude is None or longitude is None:
            return None
        return float(latitude), float(longitude)

    async def _async_search_stops(
        self, latitude: float, longitude: float
    ) -> str | None:
        """Look for the stops around a point; return an error key, if any."""
        try:
            self._stops = await self.hass.async_add_executor_job(
                nearby_stops, latitude, longitude
            )
        except Exception:
            _LOGGER.exception("Failed to search for Naolib stops")
            return "unknown"
        return None if self._stops else "no_stops_found"

    async def _async_search_stations(
        self, latitude: float, longitude: float
    ) -> str | None:
        """Look for the bike stations around a point; return an error key."""
        stations = await self._async_fetch_stations()
        if stations is None:
            return "cannot_connect"
        self._stations = nearest(stations, latitude, longitude)
        return None if self._stations else "no_stations_found"

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
        """Search the stops around a point on the map, or around a zone."""
        schema = self._location_schema()
        if user_input is None:
            return self.async_show_form(step_id="by_location", data_schema=schema)

        point = self._searched_point(user_input)
        error = (
            "zone_without_location"
            if point is None
            else await self._async_search_stops(*point)
        )
        if error is None:
            return await self.async_step_select_stop()
        return self.async_show_form(
            step_id="by_location", data_schema=schema, errors={"base": error}
        )

    async def async_step_around(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Follow a person/zone/device_tracker and expose the nearby stops."""
        if user_input is not None:
            source_entity = user_input[CONF_SOURCE_ENTITY]
            label = self._entity_label(source_entity)
            return await self._async_save(
                unique_id=f"around_{source_entity}",
                title=f"Autour de : {label}",
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_AROUND,
                    CONF_SOURCE_ENTITY: source_entity,
                    CONF_RADIUS: int(user_input[CONF_RADIUS]),
                    CONF_MAX_STOPS: int(user_input[CONF_MAX_STOPS]),
                },
            )

        defaults = self._around_defaults()
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SOURCE_ENTITY, default=defaults[CONF_SOURCE_ENTITY]
                ): EntitySelector(
                    EntitySelectorConfig(domain=["person", "zone", "device_tracker"])
                ),
                vol.Required(
                    CONF_RADIUS, default=defaults[CONF_RADIUS]
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_AROUND_RADIUS,
                        max=MAX_AROUND_RADIUS,
                        step=50,
                        unit_of_measurement="m",
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Required(
                    CONF_MAX_STOPS, default=defaults[CONF_MAX_STOPS]
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_AROUND_MAX_STOPS,
                        max=MAX_AROUND_MAX_STOPS,
                        step=1,
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="around", data_schema=schema)

    def _around_defaults(self) -> dict[str, Any]:
        """Pre-fill the "around me" form, reusing a reconfigured entry."""
        defaults: dict[str, Any] = {
            CONF_SOURCE_ENTITY: "",
            CONF_RADIUS: DEFAULT_AROUND_RADIUS,
            CONF_MAX_STOPS: DEFAULT_AROUND_MAX_STOPS,
        }
        if self.source == config_entries.SOURCE_RECONFIGURE:
            data = self._get_reconfigure_entry().data
            for key in defaults:
                if key in data:
                    defaults[key] = data[key]
        return defaults

    def _entity_label(self, entity_id: str) -> str:
        """Return a friendly name for an entity, falling back to its id."""
        state = self.hass.states.get(entity_id)
        if state is not None:
            return state.name
        return entity_id

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
        """Search the bike stations around a point on the map, or a zone."""
        schema = self._location_schema()
        if user_input is None:
            return self.async_show_form(step_id="bike_by_location", data_schema=schema)

        point = self._searched_point(user_input)
        error = (
            "zone_without_location"
            if point is None
            else await self._async_search_stations(*point)
        )
        if error is None:
            return await self.async_step_select_station()
        return self.async_show_form(
            step_id="bike_by_location", data_schema=schema, errors={"base": error}
        )

    async def async_step_select_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a bike station among the ones just found."""
        station = (
            None
            if user_input is None
            else _find(self._stations, user_input[CONF_STATION_ID])
        )
        if station is None:
            return self._show_selection(
                "select_station", CONF_STATION_ID, self._stations, user_input
            )

        station_id = station["id"]
        return await self._async_save(
            unique_id=f"{BIKE_UNIQUE_ID_PREFIX}{station_id}",
            title=f"Station vélo : {station['name']}",
            data={
                CONF_ENTRY_TYPE: ENTRY_TYPE_BIKE,
                CONF_STATION_ID: station_id,
                CONF_STATION_LABEL: station["name"],
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow changing the stop or station of an existing entry.

        The entry keeps its kind: turning a stop into a bike station would
        orphan its entities instead of updating them.
        """
        entry = self._get_reconfigure_entry()
        entry_type = entry.data.get(CONF_ENTRY_TYPE)
        if entry_type == ENTRY_TYPE_BIKE:
            return await self.async_step_bike(user_input)
        if entry_type == ENTRY_TYPE_AROUND:
            return await self.async_step_around(user_input)
        return await self.async_step_stop(user_input)

    async def async_step_select_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose a stop among the ones just found."""
        stop = (
            None
            if user_input is None
            else _find(self._stops, user_input[CONF_STOP_CODE])
        )
        if stop is None:
            return self._show_selection(
                "select_stop", CONF_STOP_CODE, self._stops, user_input
            )

        stop_code = stop["id"]
        return await self._async_save(
            unique_id=stop_code,
            title=f"Arrêt : {stop['name']}",
            data={
                CONF_ENTRY_TYPE: ENTRY_TYPE_STOP,
                CONF_STOP_CODE: stop_code,
                CONF_STOP_LABEL: stop["name"],
                CONF_QUAYS: stop["quays"],
            },
        )

    def _show_selection(
        self,
        step_id: str,
        key: str,
        places: list[dict[str, Any]],
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Offer the stops or stations just found in a searchable dropdown.

        ``custom_value`` is what makes Home Assistant render a picker that
        filters as you type; it also accepts free text, so a value that is not
        one of the places is sent back with an error.
        """
        options = [
            SelectOptionDict(
                value=place["id"],
                label=(
                    f"{place['name']} ({place['distance']} m)"
                    if "distance" in place
                    else place["name"]
                ),
            )
            for place in places
        ]
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(key): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                }
            ),
            errors={"base": "not_in_list"} if user_input is not None else None,
        )

    async def _async_save(
        self, unique_id: str, title: str, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create the entry, or update the one being reconfigured."""
        await self.async_set_unique_id(unique_id)

        if self.source == config_entries.SOURCE_RECONFIGURE:
            reconfigure_entry = self._get_reconfigure_entry()
            # Reject if another entry already tracks this stop or station.
            for entry in self._async_current_entries():
                if (
                    entry.entry_id != reconfigure_entry.entry_id
                    and entry.unique_id == unique_id
                ):
                    return self.async_abort(reason="already_configured")
            return self.async_update_reload_and_abort(
                reconfigure_entry, title=title, unique_id=unique_id, data=data
            )

        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=title, data=data)

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


def _find(places: list[dict[str, Any]], place_id: str) -> dict[str, Any] | None:
    """Return the place with this id among the ones offered, if any."""
    return next((place for place in places if place["id"] == place_id), None)
