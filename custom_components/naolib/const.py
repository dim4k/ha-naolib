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

# A bike station and a stop could share an identifier, so the unique ids and
# device identifiers of stations carry this prefix.
BIKE_ID_PREFIX: str = "bike_"

# "Around me" card: follow a person/zone/device_tracker and stream the stops
# within a radius, recomputed as the entity moves.
DEFAULT_AROUND_RADIUS: int = 500
MIN_AROUND_RADIUS: int = 100
MAX_AROUND_RADIUS: int = 3000
DEFAULT_AROUND_MAX_STOPS: int = 5
MIN_AROUND_MAX_STOPS: int = 1
MAX_AROUND_MAX_STOPS: int = 15
# Collapse bursts of location updates before recomputing nearby stops.
AROUND_DEBOUNCE: int = 15

# Action exposing the departures to scripts and automations.
SERVICE_GET_DEPARTURES: str = "get_departures"
ATTR_CONFIG_ENTRY_ID: str = "config_entry_id"
ATTR_LINES: str = "lines"
ATTR_DIRECTION: str = "direction"
ATTR_WALK_TIME: str = "walk_time"
ATTR_LIMIT: str = "limit"
# Bounds of the action's options (the walk time mirrors the card's).
MAX_WALK_TIME: int = 60
MAX_DEPARTURES_LIMIT: int = 50

# Polling / network defaults
DEFAULT_UPDATE_INTERVAL: int = 60
MIN_UPDATE_INTERVAL: int = 30
MAX_UPDATE_INTERVAL: int = 600
API_TIMEOUT: int = 20
# The public SIRI endpoint allows one request every 30 seconds per IP.
API_MIN_SPACING: int = 31

# Naolib / Okina real-time SIRI endpoint (keyless public access).
# A single StopMonitoring request without MonitoringRef returns the whole
# network, which we fetch once and share across all configured stops.
SIRI_URL: str = "https://api.okina.fr/gateway/sem/realtime/anshar/services/NAOLIBORG"
SIRI_REQUESTOR_REF: str = "ha-naolib"
SIRI_NAMESPACE: str = "http://www.siri.org.uk/siri"

# A bike entry reads one of two operators. Entries created before Voi have no
# provider and read JCDecaux, whose network is dismantled by January 2027.
CONF_BIKE_PROVIDER: str = "provider"
BIKE_PROVIDER_JCDECAUX: str = "jcdecaux"
BIKE_PROVIDER_VOI: str = "voi"

# Naolib bike-sharing (ex-Bicloo) GBFS 3.0 feeds, operated by JCDecaux under
# the Cyclocity umbrella. Keyless, and referenced as the official source on
# transport.data.gouv.fr.
GBFS_BASE_URL: str = "https://api.cyclocity.fr/contracts/nantes/gbfs/v3"
GBFS_STATION_INFORMATION_URL: str = f"{GBFS_BASE_URL}/station_information.json"
GBFS_STATION_STATUS_URL: str = f"{GBFS_BASE_URL}/station_status.json"

# Voi electric bikes, which replace the JCDecaux network from October 2026.
# Keyless GBFS 2.3 feed of the Nantes zone (421), published by Voi on
# transport.data.gouv.fr. The UUID segment is shared by every French Voi city.
VOI_GBFS_BASE_URL: str = (
    "https://api.voiapp.io/gbfs/fr/6bb6b5dc-1cda-4da7-9216-d3023a0bc54a/v2/421"
)
VOI_STATION_INFORMATION_URL: str = f"{VOI_GBFS_BASE_URL}/station_information.json"
VOI_STATION_STATUS_URL: str = f"{VOI_GBFS_BASE_URL}/station_status.json"
VOI_FREE_BIKE_STATUS_URL: str = f"{VOI_GBFS_BASE_URL}/free_bike_status.json"
# Opens the Voi app on the closest bike (advertised by system_information).
VOI_APP_URL: str = "voiapp://closest_vehicle"

# A Voi bike belongs to the spot it stands within this distance of: 99 % of
# the parked bikes are within 30 m of a spot's centre.
VOI_SPOT_RADIUS_M: int = 30
# A Voi spot is named after the closest stop within this distance.
VOI_LABEL_STOP_RADIUS_M: int = 200

# The station list barely changes; the feed itself advertises a 1 hour TTL.
GBFS_INFO_TTL: int = 3600

# A JCDecaux station is reported as retired once it has been missing (or
# uninstalled) for this many polls in a row, or once the whole feed has been
# unreachable for this long.
BIKE_RETIRED_AFTER_POLLS: int = 3
BIKE_FEED_GONE_AFTER: int = 24 * 3600

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

# Departures before this hour belong to the tail of the previous service day.
SERVICE_DAY_CUTOFF_HOUR: int = 4

# Number of stops or bike stations proposed when searching around a location.
NEARBY_LIMIT: int = 15
