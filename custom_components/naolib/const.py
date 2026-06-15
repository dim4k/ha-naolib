"""Constants for the Naolib integration."""

DOMAIN: str = "naolib"

# Platforms set up by this integration
PLATFORMS: list[str] = ["sensor"]

# Configuration Keys
CONF_STOP_CODE: str = "stop_code"
CONF_STOP_LABEL: str = "stop_label"
CONF_QUAYS: str = "quays"
CONF_LOCATION: str = "location"
CONF_UPDATE_INTERVAL: str = "update_interval"

# Polling / network defaults
DEFAULT_UPDATE_INTERVAL: int = 60
MIN_UPDATE_INTERVAL: int = 30
MAX_UPDATE_INTERVAL: int = 600
API_TIMEOUT: int = 20

# Naolib / Okina real-time SIRI endpoint (keyless public access).
# A single StopMonitoring request without MonitoringRef returns the whole
# network, which we fetch once and share across all configured stops.
SIRI_DATASET_ID: str = "NAOLIBORG"
SIRI_URL: str = f"https://api.okina.fr/gateway/sem/realtime/anshar/services/{SIRI_DATASET_ID}"
SIRI_REQUESTOR_REF: str = "ha-naolib"
SIRI_NAMESPACE: str = "http://www.siri.org.uk/siri"

# Embedded stop index (generated from the GTFS feed by scripts/).
STOPS_INDEX_FILE: str = "data/stops_index.json"

# Embedded theoretical timetables (generated from the GTFS feed by scripts/).
SCHEDULES_FILE: str = "data/schedules.json"
CALENDAR_FILE: str = "data/calendar.json"

# Number of nearby stops proposed in the config flow.
NEARBY_STOPS_LIMIT: int = 15
