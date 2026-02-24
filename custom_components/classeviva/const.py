"""Constants for the ClasseViva integration."""

DOMAIN = "classeviva"
BASE_URL = "https://web.spaggiari.eu/rest/v1"

# Configuration keys
CONF_STUDENT_NAME = "student_name"

# Default polling interval in minutes
DEFAULT_SCAN_INTERVAL = 60

# Platforms to set up
PLATFORMS = ["sensor", "calendar"]

# HA event names fired when new content is detected
EVENT_NEW_DIDACTICS = f"{DOMAIN}_new_didactics"
EVENT_NEW_NOTICEBOARD = f"{DOMAIN}_new_noticeboard"
EVENT_NEW_AGENDA = f"{DOMAIN}_new_agenda"
