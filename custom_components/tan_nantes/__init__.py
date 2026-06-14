from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.http import StaticPathConfig
from homeassistant.loader import async_get_integration
from homeassistant.components import websocket_api
import voluptuous as vol
from .const import (
    CONF_STOP_CODE,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import TanDataCoordinator
import logging

_LOGGER = logging.getLogger(__name__)

# Type alias for an entry carrying its coordinator as runtime data.
type TanConfigEntry = ConfigEntry[TanDataCoordinator]


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Register the static path, Lovelace resource and WS command once."""
    integration = await async_get_integration(hass, DOMAIN)
    version = integration.version

    # 1. Define the virtual URL path to serve static files
    path = hass.config.path("custom_components/tan_nantes/www")
    url_path = "/tan_nantes_static"

    await hass.http.async_register_static_paths([
        StaticPathConfig(
            url_path=url_path,
            path=path,
            cache_headers=False
        )
    ])

    # 2. Register the card as a Lovelace resource
    # This is required for the card to be recognized by the dashboard
    try:
        resources = hass.data["lovelace"].resources
        if not resources.loaded:
            await resources.async_load()

        card_url = f"{url_path}/tan-card.js?hacstag={version}"

        # Check if already registered, update version if needed
        found = False
        for resource in resources.async_items():
            if resource["url"].startswith(url_path):
                found = True
                if resource["url"] != card_url:
                    await resources.async_update_item(resource["id"], {"url": card_url})
                break

        if not found:
            await resources.async_create_item({"res_type": "module", "url": card_url})
    except KeyError:
        _LOGGER.warning("Lovelace not available yet, skipping resource registration")
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not register Lovelace resource: %s", err)

    # 3. Register WebSocket command
    websocket_api.async_register_command(hass, handle_get_data)


async def async_setup_entry(hass: HomeAssistant, entry: TanConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("coordinators", {})

    # Register static path, JS and WS command only once
    if not hass.data[DOMAIN].get("js_registered"):
        await _async_register_frontend(hass)
        hass.data[DOMAIN]["js_registered"] = True

    # Resolve stop code (with backward compatibility for legacy keys)
    stop_code = entry.data.get(CONF_STOP_CODE) or entry.data.get("code_lieu")
    if not stop_code:
        _LOGGER.error("Stop code missing from configuration")
        return False

    # Backfill the unique_id for entries created before it was introduced
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=stop_code)

    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    coordinator = TanDataCoordinator(hass, stop_code, int(update_interval))
    await coordinator.async_config_entry_first_refresh()

    # Expose the coordinator via runtime_data and a WS-accessible registry
    entry.runtime_data = coordinator
    hass.data[DOMAIN]["coordinators"][stop_code] = coordinator

    # Reload the entry when its options change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: TanConfigEntry) -> None:
    """Reload the entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


@callback
@websocket_api.websocket_command({
    vol.Required("type"): "tan_nantes/get_data",
    vol.Required("stop_code"): str,
})
def handle_get_data(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Handle get data command."""
    stop_code = msg["stop_code"]
    coordinator = hass.data[DOMAIN]["coordinators"].get(stop_code)

    if not coordinator:
        connection.send_error(msg["id"], "stop_not_found", f"Stop code {stop_code} not found")
        return

    data = coordinator.data or {}

    connection.send_result(msg["id"], {
        "next_departures": data.get("next_departures", []),
        "schedules": data.get("schedules", {})
    })

async def async_unload_entry(hass: HomeAssistant, entry: TanConfigEntry) -> bool:
    """Unload the integration and clean up resources."""
    stop_code = entry.data.get(CONF_STOP_CODE) or entry.data.get("code_lieu")
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded and stop_code:
        hass.data[DOMAIN]["coordinators"].pop(stop_code, None)
    return unloaded