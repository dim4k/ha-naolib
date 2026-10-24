"""The Naolib integration for Home Assistant."""

from dataclasses import dataclass
from datetime import date, timedelta
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
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
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
    BIKE_ID_PREFIX,
    CARD_URL_PATH,
    CONF_ENTRY_TYPE,
    CONF_QUAYS,
    CONF_STATION_ID,
    CONF_STATION_LABEL,
    CONF_STOP_CODE,
    CONF_STOP_LABEL,
    CONF_UPDATE_INTERVAL,
    DEFAULT_AROUND_MAX_STOPS,
    DEFAULT_AROUND_RADIUS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    ENTRY_TYPE_BIKE,
    LOADER_FILENAME,
    MAX_AROUND_MAX_STOPS,
    MAX_AROUND_RADIUS,
    MAX_DEPARTURES_LIMIT,
    MAX_TIMETABLE_DAY_OFFSET,
    MAX_WALK_TIME,
    MIN_AROUND_MAX_STOPS,
    MIN_AROUND_RADIUS,
    PLATFORMS,
    SERVICE_GET_DEPARTURES,
)
from .coordinator import (
    NaolibDeparturesCoordinator,
    NaolibStop,
    build_stop_data,
    filter_departures,
)
from .live import NaolibLiveAround
from .schedules import build_timetable, calendar_end

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

GET_DEPARTURES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Optional(ATTR_LINES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_DIRECTION): vol.All(vol.Coerce(int), vol.In([1, 2])),
        vol.Optional(ATTR_WALK_TIME): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=MAX_WALK_TIME)
        ),
        vol.Optional(ATTR_LIMIT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_DEPARTURES_LIMIT)
        ),
    }
)

# Which coordinator serves an entry depends on what it tracks: a stop or a
# bike station. The entry carries it as runtime data.
type NaolibCoordinator = NaolibDeparturesCoordinator | NaolibBikeCoordinator
type NaolibConfigEntry = ConfigEntry[NaolibCoordinator]


@dataclass
class NaolibData:
    """State shared by every config entry, stored in ``hass.data``."""

    departures: NaolibDeparturesCoordinator
    bikes: NaolibBikeCoordinator
    loader_url: str = ""


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
        NaolibDeparturesCoordinator(hass), NaolibBikeCoordinator(hass)
    )
    websocket_api.async_register_command(hass, handle_get_data)
    websocket_api.async_register_command(hass, handle_around_subscribe)
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
    coordinator = entry.runtime_data
    if not isinstance(coordinator, NaolibDeparturesCoordinator):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_wrong_type",
            translation_placeholders={"target": entry.title},
        )

    stop = coordinator.tracked[entry.entry_id]
    payload = build_stop_data(coordinator.data or {}, stop)
    # Typed loosely: a response holds JSON values, and lists are invariant.
    departures: list[Any] = filter_departures(
        payload["next_departures"],
        lines=call.data.get(ATTR_LINES),
        direction=call.data.get(ATTR_DIRECTION),
        walk_minutes=call.data.get(ATTR_WALK_TIME, 0),
        limit=call.data.get(ATTR_LIMIT),
    )
    return {"stop_code": stop.code, "stop_label": stop.name, "departures": departures}


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card's files and load it on the frontend."""
    # Imported here so the frontend helpers stay out of the module imports.
    from .frontend import WWW_PATH, async_register_loader

    integration = await async_get_integration(hass, DOMAIN)

    # The card is imported under its content hash (stamped into the loader),
    # so caching it is safe and avoids the transient error shown while the
    # card downloads.
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url_path=CARD_URL_PATH, path=str(WWW_PATH), cache_headers=True
            )
        ]
    )

    # The loader itself is served at a fixed URL, uncached: an outdated page
    # (service worker, mobile app cache) still runs the current one.
    loader_url = await async_register_loader(hass, LOADER_FILENAME)
    hass.data[DOMAIN].loader_url = loader_url

    # What gets imported is the loader, not the card itself: Home Assistant
    # imports a custom card once per page load and never retries, so a single
    # transient failure would hide the card until the page is reloaded.
    add_extra_js_url(hass, loader_url)
    _LOGGER.debug(
        "Registered Naolib %s frontend module: %s", integration.version, loader_url
    )


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
    data: NaolibData = hass.data[DOMAIN]
    interval = int(entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
    coordinator: NaolibCoordinator
    if _is_bike(entry):
        coordinator = data.bikes
        device_id = _register_station(entry, coordinator, interval)
    else:
        coordinator = data.departures
        device_id = _register_stop(hass, entry, coordinator, interval)
    if device_id is None:
        return False

    _remove_stale_devices(hass, entry, (DOMAIN, device_id))
    _schedule_refresh(hass, entry, coordinator)
    entry.runtime_data = coordinator

    # Reload the entry when its options change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _register_stop(
    hass: HomeAssistant,
    entry: NaolibConfigEntry,
    coordinator: NaolibDeparturesCoordinator,
    interval: int,
) -> str | None:
    """Register a stop on the departures coordinator; return its device id."""
    stop_code = entry.data.get(CONF_STOP_CODE)
    quays = entry.data.get(CONF_QUAYS)
    if not stop_code:
        _LOGGER.error("Stop code missing from configuration")
        return None

    # Backfill the unique_id for entries created before it was introduced
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=stop_code)

    issue_id = f"missing_quays_{entry.entry_id}"
    if quays:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
    else:
        _LOGGER.warning(
            "Stop '%s' has no quays; please re-add it (the stop identifiers "
            "changed with the new Naolib API)",
            stop_code,
        )
        # Surface it in Settings > Repairs too: the entry stays loaded but can
        # never show a departure until it is re-added.
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="missing_quays",
            translation_placeholders={"stop": entry.title},
        )

    coordinator.register(
        entry.entry_id,
        NaolibStop(
            code=stop_code,
            name=entry.data.get(CONF_STOP_LABEL) or stop_code,
            quays=quays or [],
            interval=interval,
        ),
    )
    return str(stop_code)


def _register_station(
    entry: NaolibConfigEntry, coordinator: NaolibBikeCoordinator, interval: int
) -> str | None:
    """Register a bike station on the bike coordinator; return its device id."""
    station_id = entry.data.get(CONF_STATION_ID)
    if not station_id:
        _LOGGER.error("Station id missing from configuration")
        return None

    coordinator.register(
        entry.entry_id,
        NaolibBikeStation(
            id=station_id,
            name=entry.data.get(CONF_STATION_LABEL) or station_id,
            interval=interval,
        ),
    )
    return f"{BIKE_ID_PREFIX}{station_id}"


def _remove_stale_devices(
    hass: HomeAssistant, entry: NaolibConfigEntry, identifier: tuple[str, str]
) -> None:
    """Drop the devices left behind by a previous stop or station.

    Reconfiguring an entry moves it to another stop or station, whose device
    has a new identifier; the old device would otherwise linger with an
    orphaned entity.
    """
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if identifier not in device.identifiers:
            device_registry.async_remove_device(device.id)


def _schedule_refresh(
    hass: HomeAssistant, entry: NaolibConfigEntry, coordinator: NaolibCoordinator
) -> None:
    """Warm up the coordinator without blocking (or failing) the setup.

    The departures endpoint is rate-limited (1 request / 30 s), so setup must
    not fail or retry on a transient 429 -- the coordinator will keep polling.
    An entry added later needs a refresh too, since the snapshot only holds
    what was registered when it was taken; the debouncer collapses the
    requests fired when several entries are set up at once.
    """
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
        vol.Required("type"): "naolib/around/subscribe",
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("radius", default=DEFAULT_AROUND_RADIUS): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_AROUND_RADIUS, max=MAX_AROUND_RADIUS)
        ),
        vol.Optional("max_stops", default=DEFAULT_AROUND_MAX_STOPS): vol.All(
            vol.Coerce(int),
            vol.Range(min=MIN_AROUND_MAX_STOPS, max=MAX_AROUND_MAX_STOPS),
        ),
    }
)
@websocket_api.async_response
async def handle_around_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Stream the stops around an entity, and their departures, to a card.

    The stops follow the entity as it moves; they are registered on the
    shared coordinator only while the subscription lives.
    """
    msg_id = msg["id"]
    live = NaolibLiveAround(
        hass,
        hass.data[DOMAIN].departures,
        f"live:{id(connection)}:{msg_id}",
        lambda data: connection.send_message(websocket_api.event_message(msg_id, data)),
        entity_id=msg["entity_id"],
        radius=msg["radius"],
        max_stops=msg["max_stops"],
    )
    connection.subscriptions[msg_id] = live.stop
    connection.send_result(msg_id)
    await live.async_start()


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
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the full timetable of a configured stop for one day.

    The departures themselves are not sent: the card reads them from the
    sensor attributes.
    """
    stop_code = msg["stop_code"]
    if hass.data[DOMAIN].departures.stop_by_code(stop_code) is None:
        connection.send_error(
            msg["id"], "stop_not_found", f"Stop code {stop_code} not found"
        )
        return

    day = dt_util.now().date() + timedelta(days=msg["day_offset"])
    schedules, end = await hass.async_add_executor_job(_timetable, stop_code, day)
    connection.send_result(
        msg["id"],
        {
            "schedules": schedules,
            "schedules_date": day.isoformat(),
            # The timetables ship with the integration: once the calendar runs
            # out, every day is empty and only an update brings them back.
            "schedules_expired": end is not None and day > end,
        },
    )


def _timetable(
    stop_code: str, day: date
) -> tuple[dict[str, dict[str, Any]], date | None]:
    """Read a day's timetable and the end of the calendar in one executor job."""
    return build_timetable(stop_code, day), calendar_end()


async def async_unload_entry(hass: HomeAssistant, entry: NaolibConfigEntry) -> bool:
    """Unload the integration and clean up resources.

    The shared coordinator and the frontend module stay registered: unloading
    also happens on every reload, and the coordinator stops polling on its own
    once no entity listens to it.
    """
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.unregister(entry.entry_id)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: NaolibConfigEntry) -> None:
    """Drop the repair issue of a deleted entry, if any."""
    ir.async_delete_issue(hass, DOMAIN, f"missing_quays_{entry.entry_id}")
