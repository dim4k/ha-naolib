"""Constants for the Tan Nantes integration."""

DOMAIN: str = "tan_nantes"

# Platforms set up by this integration
PLATFORMS: list[str] = ["sensor"]

# Configuration Keys
CONF_STOP_CODE: str = "stop_code"
CONF_STOP_LABEL: str = "stop_label"
CONF_LOCATION: str = "location"
CONF_UPDATE_INTERVAL: str = "update_interval"

# Polling / network defaults
DEFAULT_UPDATE_INTERVAL: int = 60
MIN_UPDATE_INTERVAL: int = 30
MAX_UPDATE_INTERVAL: int = 600
API_TIMEOUT: int = 10

# Sensor state values
STATE_NO_BUS: str = "Aucun bus"
STATE_UNAVAILABLE: str = "Indisponible"

# URL to find stops (Latitude/Longitude)
URL_STOPS: str = "https://open.tan.fr/ewp/arrets.json/{}/{}" 

# URL for waiting time (CodeLieu)
URL_WAITING_TIME: str = "https://open.tan.fr/ewp/tempsattente.json/{}"

# URL for stop schedule (CodeArret/NumLigne/Sens)
URL_STOP_SCHEDULE: str = "https://open.tan.fr/ewp/horairesarret.json/{}/{}/{}"