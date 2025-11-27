from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.loader import async_get_integration
from homeassistant.components import websocket_api
import voluptuous as vol
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault("coordinators", {})

    # Only register static path and js once
    if not hass.data[DOMAIN].get("js_registered"):
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
        except Exception:
            pass
        
        # 3. Register WebSocket command
        websocket_api.async_register_command(hass, handle_get_data)
        
        hass.data[DOMAIN]["js_registered"] = True
    
    # 4. Load sensors
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

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

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the integration."""
    return await hass.config_entries.async_unload_platforms(entry, ["sensor"])