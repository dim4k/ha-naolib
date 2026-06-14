import logging
from typing import Any, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
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

from .api import TanApiClient
from .const import (
    CONF_LOCATION,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class TanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Tan Nantes."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._stops: list[dict[str, Any]] = []

    async def _async_fetch_stops(self, lat: float, lon: float) -> list[dict[str, Any]]:
        """Fetch nearby stops for the given coordinates."""
        session = async_get_clientsession(self.hass)
        client = TanApiClient(session)
        return await client.get_stops(lat, lon) or []

    async def async_step_user(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step: pick a location on the map."""
        errors: dict[str, str] = {}

        if user_input is not None:
            location = user_input[CONF_LOCATION]
            lat = location["latitude"]
            lon = location["longitude"]

            try:
                self._stops = await self._async_fetch_stops(lat, lon)
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception while fetching stops")
                errors["base"] = "unknown"
            else:
                if not self._stops:
                    errors["base"] = "no_stops_found"
                else:
                    return await self.async_step_select_stop()

        default_location = {
            "latitude": self.hass.config.latitude,
            "longitude": self.hass.config.longitude,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCATION, default=default_location
                    ): LocationSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Allow changing the stop of an existing entry."""
        return await self.async_step_user(user_input)

    async def async_step_select_stop(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the second step: choose a stop among the nearby ones."""
        if user_input is not None:
            stop_code = user_input[CONF_STOP_CODE]
            stop = next(
                (s for s in self._stops if s["codeLieu"] == stop_code),
                None,
            )
            stop_label = stop["libelle"] if stop else stop_code

            data = {
                CONF_STOP_CODE: stop_code,
                CONF_STOP_LABEL: stop_label,
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
                "value": stop["codeLieu"],
                "label": stop["libelle"],
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
        return TanOptionsFlow()


class TanOptionsFlow(OptionsFlow):
    """Handle options (polling interval)."""

    async def async_step_init(
        self, user_input: Optional[dict[str, Any]] = None
    ) -> FlowResult:
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
                    vol.Required(
                        CONF_UPDATE_INTERVAL, default=current
                    ): NumberSelector(
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