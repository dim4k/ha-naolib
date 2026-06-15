from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.http import StaticPathConfig
from homeassistant.loader import async_get_integration
from homeassistant.components import websocket_api
from homeassistant.util import dt as dt_util
import voluptuous as vol
from .const import (
    CONF_QUAYS,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import TanGlobalCoordinator, build_stop_data
from .schedules import build_timetable
import logging

_LOGGER = logging.getLogger(__name__)

# Type alias for an entry carrying the shared coordinator as runtime data.
type TanConfigEntry = ConfigEntry[TanGlobalCoordinator]


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
    # This is only possible when Lovelace runs in "storage" mode (the default,
    # UI-managed dashboards). In YAML mode the resources are read-only and the
    # user is expected to declare the resource themselves, so we skip silently.
    lovelace = hass.data.get("lovelace")
    if lovelace is None:
        _LOGGER.warning("Lovelace not available yet, skipping resource registration")
    elif getattr(lovelace, "mode", None) != "storage":
        _LOGGER.debug(
            "Lovelace is in YAML mode; add the card resource manually: %s",
            f"{url_path}/tan-card.js",
        )
    else:
        try:
            resources = lovelace.resources
            if resources is None:
                raise AttributeError("Lovelace resources collection is unavailable")

            if not resources.loaded:
                await resources.async_load()

            card_url = f"{url_path}/tan-card.js?hacstag={version}"

            # Check if already registered, update version if needed
            found = False
            for resource in resources.async_items():
                if resource["url"].startswith(url_path):
                    found = True
                    if resource["url"] != card_url:
                        await resources.async_update_item(
                            resource["id"], {"url": card_url}
                        )
                    break

            if not found:
                await resources.async_create_item(
                    {"res_type": "module", "url": card_url}
                )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Could not register Lovelace resource: %s", err)

    # 3. Register WebSocket command
    websocket_api.async_register_command(hass, handle_get_data)


async def async_setup_entry(hass: HomeAssistant, entry: TanConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    data = hass.data.setdefault(DOMAIN, {})
    data.setdefault("stops", {})

    # Register static path, JS and WS command only once
    if not data.get("js_registered"):
        await _async_register_frontend(hass)
        data["js_registered"] = True

    stop_code = entry.data.get(CONF_STOP_CODE)
    quays = entry.data.get(CONF_QUAYS)
    if not stop_code:
        _LOGGER.error("Stop code missing from configuration")
        return False

    # Backfill the unique_id for entries created before it was introduced
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=stop_code)

    if not quays:
        _LOGGER.warning(
            "Stop '%s' has no quays; please re-add it (the stop identifiers "
            "changed with the new Naolib API)",
            stop_code,
        )

    # Single shared coordinator polls the whole network for all stops
    coordinator: TanGlobalCoordinator = data.get("coordinator")
    if coordinator is None:
        coordinator = TanGlobalCoordinator(hass)
        data["coordinator"] = coordinator
        # Kick off an initial fetch in the background. The endpoint is
        # rate-limited (1 request / 30 s), so we must not fail or retry the
        # whole setup on a transient 429 — the coordinator will keep polling.
        entry.async_create_background_task(
            hass, coordinator.async_refresh(), "tan_nantes_initial_refresh"
        )

    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    coordinator.set_interval(entry.entry_id, int(update_interval))

    entry.runtime_data = coordinator
    data["stops"][stop_code] = {
        "quays": quays or [],
        "name": entry.data.get(CONF_STOP_LABEL) or stop_code,
    }

    # Reload the entry when its options change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: TanConfigEntry) -> None:
    """Reload the entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


@websocket_api.websocket_command({
    vol.Required("type"): "tan_nantes/get_data",
    vol.Required("stop_code"): str,
})
@websocket_api.async_response
async def handle_get_data(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Handle get data command."""
    stop_code = msg["stop_code"]
    domain_data = hass.data.get(DOMAIN, {})
    coordinator: TanGlobalCoordinator = domain_data.get("coordinator")
    stop = domain_data.get("stops", {}).get(stop_code)

    if not coordinator or stop is None:
        connection.send_error(
            msg["id"], "stop_not_found", f"Stop code {stop_code} not found"
        )
        return

    payload = build_stop_data(coordinator.data or {}, stop["quays"])
    today = dt_util.now().date()
    payload["schedules"] = await hass.async_add_executor_job(
        build_timetable, stop_code, today
    )
    connection.send_result(msg["id"], payload)


async def async_unload_entry(hass: HomeAssistant, entry: TanConfigEntry) -> bool:
    """Unload the integration and clean up resources."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data = hass.data[DOMAIN]
        stop_code = entry.data.get(CONF_STOP_CODE)
        if stop_code:
            data["stops"].pop(stop_code, None)
        coordinator: TanGlobalCoordinator = data.get("coordinator")
        if coordinator is not None:
            coordinator.remove_interval(entry.entry_id)
        # Drop the shared coordinator once no stop remains
        if not data["stops"]:
            data.pop("coordinator", None)
    return unloaded