import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, CONF_STOP_CODE, CONF_STOP_LABEL
from .api import TanApiClient

_LOGGER = logging.getLogger(__name__)

class TanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Tan Nantes."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step (user input)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            lat = user_input["latitude"]
            lon = user_input["longitude"]

            # Verify coordinates via the API
            try:
                session = async_get_clientsession(self.hass)
                client = TanApiClient(session)
                stops = await client.get_stops(lat, lon)
                
                if not stops:
                    errors["base"] = "no_stops_found"
                else:
                    # Take the first stop (the closest one)
                    closest_stop = stops[0]
                    stop_code = closest_stop["codeLieu"]
                    stop_label = closest_stop["libelle"]

                    # Create the configuration entry stored in HA
                    return self.async_create_entry(
                        title=f"Stop: {stop_label}",
                        data={
                            CONF_STOP_CODE: stop_code,
                            CONF_STOP_LABEL: stop_label
                        }
                    )
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Form displayed to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("latitude"): float,
                vol.Required("longitude"): float,
            }),
            errors=errors,
        )