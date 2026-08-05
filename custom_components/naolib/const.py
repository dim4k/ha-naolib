"""Constants for the Naolib integration."""

DOMAIN: str = "naolib"

# Platforms set up by this integration
PLATFORMS: list[str] = ["sensor"]

# Configuration Keys
CONF_ENTRY_TYPE: str = "entry_type"
CONF_STOP_CODE: str = "stop_code"
CONF_STOP_LABEL: str = "stop_label"
CONF_QUAYS: str = "quays"
CONF_STATION_ID: str = "station_id"
CONF_STATION_LABEL: str = "station_label"
CONF_LOCATION: str = "location"
CONF_UPDATE_INTERVAL: str = "update_interval"

# An entry either tracks a transit stop or a bike-sharing station. Entries
# created before the bike support have no type and are stops.
ENTRY_TYPE_STOP: str = "stop"
ENTRY_TYPE_BIKE: str = "bike"

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

# Naolib bike-sharing (ex-Bicloo) GBFS 3.0 feeds, operated by JCDecaux under
# the Cyclocity umbrella. Keyless, and referenced as the official source on
# transport.data.gouv.fr.
GBFS_BASE_URL: str = "https://api.cyclocity.fr/contracts/nantes/gbfs/v3"
GBFS_STATION_INFORMATION_URL: str = f"{GBFS_BASE_URL}/station_information.json"
GBFS_STATION_STATUS_URL: str = f"{GBFS_BASE_URL}/station_status.json"

# The station list barely changes; the feed itself advertises a 1 hour TTL.
GBFS_INFO_TTL: int = 3600

# Upper bounds for the nearby stations exposed as a sensor attribute. The card
# narrows this list down further with its own radius and count.
BIKE_NEARBY_LIMIT: int = 10
BIKE_NEARBY_RADIUS_M: int = 1000

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

# Number of stops proposed when searching around a location.
NEARBY_STOPS_LIMIT: int = 15

# Number of bike stations proposed when searching around a location.
NEARBY_STATIONS_LIMIT: int = 15
