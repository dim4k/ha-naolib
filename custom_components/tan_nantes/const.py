"""Constants for the Tan Nantes integration."""

DOMAIN = "tan_nantes"

# Configuration Keys
CONF_STOP_CODE = "stop_code"
CONF_STOP_LABEL = "stop_label"

# URL to find stops (Latitude/Longitude)
URL_STOPS = "http://open.tan.fr/ewp/arrets.json/{}/{}" 

# URL for waiting time (CodeLieu)
URL_WAITING_TIME = "http://open.tan.fr/ewp/tempsattente.json/{}"

# URL for stop schedule (CodeArret/NumLigne/Sens)
URL_STOP_SCHEDULE = "http://open.tan.fr/ewp/horairesarret.json/{}/{}/{}"