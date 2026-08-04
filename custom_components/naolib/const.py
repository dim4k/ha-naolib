"""Constants for the Naolib integration."""

DOMAIN: str = "naolib"

# Platforms set up by this integration
PLATFORMS: list[str] = ["sensor"]

# Configuration Keys
CONF_STOP_CODE: str = "stop_code"
CONF_STOP_LABEL: str = "stop_label"
CONF_QUAYS: str = "quays"
CONF_LOCATION: str = "location"
CONF_QUERY: str = "query"
CONF_UPDATE_INTERVAL: str = "update_interval"

# Action exposing the departures to scripts and automations.
SERVICE_GET_DEPARTURES: str = "get_departures"
ATTR_CONFIG_ENTRY_ID: str = "config_entry_id"
ATTR_LINES: str = "lines"
ATTR_DIRECTION: str = "direction"
ATTR_WALK_TIME: str = "walk_time"
ATTR_LIMIT: str = "limit"

# Polling / network defaults
DEFAULT_UPDATE_INTERVAL: int = 60
MIN_UPDATE_INTERVAL: int = 30
MAX_UPDATE_INTERVAL: int = 600
API_TIMEOUT: int = 20

# Naolib / Okina real-time SIRI endpoint (keyless public access).
# A single StopMonitoring request without MonitoringRef returns the whole
# network, which we fetch once and share across all configured stops.
SIRI_URL: str = "https://api.okina.fr/gateway/sem/realtime/anshar/services/NAOLIBORG"
SIRI_REQUESTOR_REF: str = "ha-naolib"
SIRI_NAMESPACE: str = "http://www.siri.org.uk/siri"

# Embedded stop index (generated from the GTFS feed by scripts/).
STOPS_INDEX_FILE: str = "data/stops_index.json"

# URL path serving the card's static files.
CARD_URL_PATH: str = "/naolib_static"

# Thin module Home Assistant imports; it retries the card import on failure.
LOADER_FILENAME: str = "naolib-loader.js"

# Embedded theoretical timetables (generated from the GTFS feed by scripts/).
# One compressed row per station, read on demand.
SCHEDULES_DB: str = "data/schedules.sqlite"
CALENDAR_FILE: str = "data/calendar.json"

# How far ahead the card may ask for a timetable, in days.
MAX_TIMETABLE_DAY_OFFSET: int = 6

# Number of nearby stops proposed in the config flow.
NEARBY_STOPS_LIMIT: int = 15

# Number of stops proposed when searching by name.
SEARCH_STOPS_LIMIT: int = 25
