"""Constants for the Tan Nantes integration."""

DOMAIN: str = "tan_nantes"

# Configuration Keys
CONF_STOP_CODE: str = "stop_code"
CONF_STOP_LABEL: str = "stop_label"

# URL to find stops (Latitude/Longitude)
URL_STOPS: str = "http://open.tan.fr/ewp/arrets.json/{}/{}" 

# URL for waiting time (CodeLieu)
URL_WAITING_TIME: str = "http://open.tan.fr/ewp/tempsattente.json/{}"

# URL for stop schedule (CodeArret/NumLigne/Sens)
URL_STOP_SCHEDULE: str = "http://open.tan.fr/ewp/horairesarret.json/{}/{}/{}"