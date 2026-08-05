"""The Naolib integration for Home Assistant."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .bike import NaolibBikeCoordinator, NaolibBikeStation
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DIRECTION,
    ATTR_LIMIT,
    ATTR_LINES,
    ATTR_WALK_TIME,
    CARD_URL_PATH,
    CONF_ENTRY_TYPE,
    CONF_QUAYS,
    CONF_STATION_ID,
    CONF_STATION_LABEL,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_BIKE,
    LOADER_FILENAME,
    MAX_TIMETABLE_DAY_OFFSET,
    PLATFORMS,
    SERVICE_GET_DEPARTURES,
)
from .coordinator import (
    NaolibData,
    NaolibGlobalCoordinator,
    NaolibStop,
    build_stop_data,
    filter_departures,
)
from .schedules import build_timetable

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

GET_DEPARTURES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_LINES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_DIRECTION): vol.All(vol.Coerce(int), vol.In([1, 2])),
        vol.Optional(ATTR_WALK_TIME): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=60)
        ),
        vol.Optional(ATTR_LIMIT): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
    }
)

# Type alias for an entry carrying its coordinator as runtime data. Which one
# depends on what the entry tracks: a stop or a bike station.
type NaolibConfigEntry = ConfigEntry[NaolibGlobalCoordinator | NaolibBikeCoordinator]


def _is_bike(entry: ConfigEntry) -> bool:
    """Tell whether an entry tracks a bike station.

    Entries created before bike support have no type and are stops.
    """
    return entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_BIKE


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up everything that is shared by all config entries.

    Called once per Home Assistant start, before any entry is set up, so
    nothing here depends on the entry load/unload cycle.
    """
    hass.data[DOMAIN] = NaolibData(
        NaolibGlobalCoordinator(hass), NaolibBikeCoordinator(hass)
    )
    websocket_api.async_register_command(hass, handle_get_data)
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DEPARTURES,
        _async_get_departures,
        schema=GET_DEPARTURES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    await _async_register_frontend(hass)
    return True


async def _async_get_departures(call: ServiceCall) -> ServiceResponse:
    """Return the next departures of a configured stop."""
    hass = call.hass
    entry_id = call.data[ATTR_CONFIG_ENTRY_ID]
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
            translation_placeholders={"target": entry.title},
        )
    if _is_bike(entry):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_wrong_type",
            translation_placeholders={"target": entry.title},
        )

    stop = entry.runtime_data.stops[entry.entry_id]
    payload = build_stop_data(entry.runtime_data.data or {}, stop)
    return {
        "stop_code": stop.code,
        "stop_label": stop.name,
        "departures": filter_departures(
            payload["next_departures"],
            lines=call.data.get(ATTR_LINES),
            direction=call.data.get(ATTR_DIRECTION),
            walk_minutes=call.data.get(ATTR_WALK_TIME, 0),
            limit=call.data.get(ATTR_LIMIT),
        ),
    }


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card's files and load it on the frontend."""
    integration = await async_get_integration(hass, DOMAIN)
    path = hass.config.path("custom_components/naolib/www")

    # The version in the URL acts as a cache-buster, so caching is safe and
    # avoids the transient error shown while the card downloads.
    await hass.http.async_register_static_paths(
        [StaticPathConfig(url_path=CARD_URL_PATH, path=path, cache_headers=True)]
    )

    loader_url = f"{CARD_URL_PATH}/{LOADER_FILENAME}?v={integration.version}"
    hass.data[DOMAIN].loader_url = loader_url

    # What gets imported is the loader, not the card itself: Home Assistant
    # imports a custom card once per page load and never retries, so a single
    # transient failure would hide the card until the page is reloaded.
    add_extra_js_url(hass, loader_url)
    _LOGGER.debug("Registered Naolib frontend module: %s", loader_url)


async def async_frontend_diagnostics(hass: HomeAssistant) -> dict[str, Any]:
    """Report how the card is served, for diagnostics."""
    return {
        "loader_url": hass.data[DOMAIN].loader_url,
        "extra_module_urls": sorted(
            getattr(hass.data.get(DATA_EXTRA_MODULE_URL), "urls", ())
        ),
    }


async def async_setup_entry(hass: HomeAssistant, entry: NaolibConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    if _is_bike(entry):
        if not await _async_setup_bike_entry(hass, entry):
            return False
    elif not await _async_setup_stop_entry(hass, entry):
        return False

    # Reload the entry when its options change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_setup_stop_entry(
    hass: HomeAssistant, entry: NaolibConfigEntry
) -> bool:
    """Register a stop on the departures coordinator."""
    coordinator = hass.data[DOMAIN].coordinator

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

    coordinator.register_stop(
        entry.entry_id,
        NaolibStop(
            code=stop_code,
            name=entry.data.get(CONF_STOP_LABEL) or stop_code,
            quays=quays or [],
            interval=int(
                entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ),
        ),
    )

    # The endpoint is rate-limited (1 request / 30 s), so setup must not fail or
    # retry on a transient 429 -- the coordinator will keep polling. A stop
    # added later needs a refresh too, since the snapshot only holds the quays
    # that were registered when it was taken; the debouncer collapses the
    # requests fired when several entries are set up at once.
    _schedule_refresh(hass, entry, coordinator)
    entry.runtime_data = coordinator
    return True


async def _async_setup_bike_entry(
    hass: HomeAssistant, entry: NaolibConfigEntry
) -> bool:
    """Register a bike station on the bike coordinator."""
    coordinator = hass.data[DOMAIN].bike_coordinator

    station_id = entry.data.get(CONF_STATION_ID)
    if not station_id:
        _LOGGER.error("Station id missing from configuration")
        return False

    coordinator.register_station(
        entry.entry_id,
        NaolibBikeStation(
            id=station_id,
            name=entry.data.get(CONF_STATION_LABEL) or station_id,
            interval=int(
                entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ),
        ),
    )

    _schedule_refresh(hass, entry, coordinator)
    entry.runtime_data = coordinator
    return True


def _schedule_refresh(
    hass: HomeAssistant,
    entry: NaolibConfigEntry,
    coordinator: NaolibGlobalCoordinator | NaolibBikeCoordinator,
) -> None:
    """Warm up the coordinator without blocking (or failing) the setup."""
    refresh = (
        coordinator.async_refresh()
        if coordinator.data is None
        else coordinator.async_request_refresh()
    )
    entry.async_create_background_task(hass, refresh, "naolib_refresh")


async def _async_update_listener(hass: HomeAssistant, entry: NaolibConfigEntry) -> None:
    """Reload the entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "naolib/get_data",
        vol.Required("stop_code"): str,
        vol.Optional("day_offset", default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=MAX_TIMETABLE_DAY_OFFSET)
        ),
    }
)
@websocket_api.async_response
async def handle_get_data(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Handle get data command."""
    stop_code = msg["stop_code"]
    coordinator = hass.data[DOMAIN].coordinator
    stop = coordinator.stop_by_code(stop_code)

    if stop is None:
        connection.send_error(
            msg["id"], "stop_not_found", f"Stop code {stop_code} not found"
        )
        return

    payload = build_stop_data(coordinator.data or {}, stop)
    day = dt_util.now().date() + timedelta(days=msg["day_offset"])
    payload["schedules"] = await hass.async_add_executor_job(
        build_timetable, stop_code, day
    )
    payload["schedules_date"] = day.isoformat()
    connection.send_result(msg["id"], payload)


async def async_unload_entry(hass: HomeAssistant, entry: NaolibConfigEntry) -> bool:
    """Unload the integration and clean up resources.

    The shared coordinator and the frontend module stay registered: unloading
    also happens on every reload, and the coordinator stops polling on its own
    once no entity listens to it.
    """
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        if _is_bike(entry):
            hass.data[DOMAIN].bike_coordinator.unregister_station(entry.entry_id)
        else:
            hass.data[DOMAIN].coordinator.unregister_stop(entry.entry_id)
    return unloaded
