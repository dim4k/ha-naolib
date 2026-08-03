from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, add_extra_js_url
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_when_setup
from homeassistant.loader import async_get_integration
from homeassistant.components import websocket_api
from homeassistant.util import dt as dt_util
import voluptuous as vol
from .const import (
    CARD_FILENAME,
    CARD_URL_PATH,
    CONF_QUAYS,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LEGACY_CARD_DIR,
    LEGACY_CARD_URL_PATH,
    LOADER_FILENAME,
    PLATFORMS,
)
from .coordinator import NaolibGlobalCoordinator, build_stop_data
from .schedules import build_timetable
from typing import Any
import logging
import os

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Type alias for an entry carrying the shared coordinator as runtime data.
type NaolibConfigEntry = ConfigEntry[NaolibGlobalCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up everything that is shared by all config entries.

    Called once per Home Assistant start, before any entry is set up, so
    nothing here depends on the entry load/unload cycle.
    """
    hass.data[DOMAIN] = {"stops": {}}
    websocket_api.async_register_command(hass, handle_get_data)
    await _async_register_frontend(hass)
    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card's files and load it on the frontend."""
    integration = await async_get_integration(hass, DOMAIN)
    path = hass.config.path("custom_components/naolib/www")

    # The version in the URL acts as a cache-buster, so caching is safe and
    # avoids the transient error shown while the card downloads.
    await hass.http.async_register_static_paths([
        StaticPathConfig(url_path=CARD_URL_PATH, path=path, cache_headers=True)
    ])

    loader_url = f"{CARD_URL_PATH}/{LOADER_FILENAME}?v={integration.version}"
    hass.data[DOMAIN]["loader_url"] = loader_url

    # What gets imported is the loader, not the card itself: Home Assistant
    # imports a custom card once per page load and never retries, so a single
    # transient failure would hide the card until the page is reloaded.
    add_extra_js_url(hass, loader_url)
    _LOGGER.debug("Registered Naolib frontend module: %s", loader_url)

    async_when_setup(hass, "lovelace", _async_clean_up_legacy_frontend)


async def _async_clean_up_legacy_frontend(
    hass: HomeAssistant, _component: str
) -> None:
    """Drop the Lovelace resource and config/www copy earlier versions made.

    Both are now redundant with add_extra_js_url, and a leftover resource
    would keep loading a stale copy of the card next to the current one.
    """
    try:
        await _async_remove_lovelace_resources(hass)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning(
            "Could not remove the obsolete Naolib Lovelace resource (%s); "
            "remove it manually in Settings > Dashboards > Resources",
            err,
        )
    await hass.async_add_executor_job(_remove_legacy_www_copy, hass)


async def _async_remove_lovelace_resources(hass: HomeAssistant) -> None:
    """Delete every Lovelace resource pointing at the card."""
    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None or lovelace_data.resource_mode != MODE_STORAGE:
        # YAML-mode resources are owned by the user and cannot be edited here.
        return
    collection = lovelace_data.resources

    # The collection is lazily loaded the first time the frontend lists
    # resources; reading it before that returns an empty list.
    if not getattr(collection, "loaded", True):
        await collection.async_load()
        collection.loaded = True

    prefixes = (f"{LEGACY_CARD_URL_PATH}/", f"{CARD_URL_PATH}/")
    obsolete = [
        item
        for item in collection.async_items()
        if item.get("url", "").startswith(prefixes)
    ]
    for item in obsolete:
        await collection.async_delete_item(item["id"])
        _LOGGER.info("Removed the obsolete Naolib Lovelace resource")


def _remove_legacy_www_copy(hass: HomeAssistant) -> None:
    """Delete the card files earlier versions copied into config/www."""
    directory = hass.config.path("www", LEGACY_CARD_DIR)
    removed = False
    for filename in (CARD_FILENAME, LOADER_FILENAME):
        try:
            os.remove(os.path.join(directory, filename))
        except OSError:
            continue
        removed = True
    if removed:
        _LOGGER.info("Removed the obsolete Naolib card copy from %s", directory)
    try:
        os.rmdir(directory)
    except OSError:
        # Kept if the user put anything else in there.
        pass


async def async_frontend_diagnostics(hass: HomeAssistant) -> dict[str, Any]:
    """Report how the card is served, for diagnostics."""
    return {
        "loader_url": hass.data.get(DOMAIN, {}).get("loader_url"),
        "extra_module_urls": sorted(
            getattr(hass.data.get(DATA_EXTRA_MODULE_URL), "urls", ())
        ),
    }


async def async_setup_entry(hass: HomeAssistant, entry: NaolibConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    data = hass.data[DOMAIN]

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
    coordinator: NaolibGlobalCoordinator = data.get("coordinator")
    if coordinator is None:
        coordinator = NaolibGlobalCoordinator(hass)
        data["coordinator"] = coordinator
        # Kick off an initial fetch in the background. The endpoint is
        # rate-limited (1 request / 30 s), so we must not fail or retry the
        # whole setup on a transient 429 — the coordinator will keep polling.
        entry.async_create_background_task(
            hass, coordinator.async_refresh(), "naolib_initial_refresh"
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


async def _async_update_listener(hass: HomeAssistant, entry: NaolibConfigEntry) -> None:
    """Reload the entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


@websocket_api.websocket_command({
    vol.Required("type"): "naolib/get_data",
    vol.Required("stop_code"): str,
})
@websocket_api.async_response
async def handle_get_data(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Handle get data command."""
    stop_code = msg["stop_code"]
    domain_data = hass.data.get(DOMAIN, {})
    coordinator: NaolibGlobalCoordinator = domain_data.get("coordinator")
    stop = domain_data.get("stops", {}).get(stop_code)

    if not coordinator or stop is None:
        connection.send_error(
            msg["id"], "stop_not_found", f"Stop code {stop_code} not found"
        )
        return

    payload = build_stop_data(
        coordinator.data or {}, stop["quays"], stop.get("last_times")
    )
    today = dt_util.now().date()
    payload["schedules"] = await hass.async_add_executor_job(
        build_timetable, stop_code, today
    )
    connection.send_result(msg["id"], payload)


async def async_unload_entry(hass: HomeAssistant, entry: NaolibConfigEntry) -> bool:
    """Unload the integration and clean up resources."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data = hass.data[DOMAIN]
        stop_code = entry.data.get(CONF_STOP_CODE)
        if stop_code:
            data["stops"].pop(stop_code, None)
        coordinator: NaolibGlobalCoordinator = data.get("coordinator")
        if coordinator is not None:
            coordinator.remove_interval(entry.entry_id)
        # Drop the shared coordinator once no stop remains. The frontend module
        # stays registered: unloading also happens on every reload, and
        # re-adding it would not take effect until the frontend is reloaded.
        if not data["stops"]:
            data.pop("coordinator", None)
    return unloaded
