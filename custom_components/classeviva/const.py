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
# Fired when a new agenda event specifically concerns the student
EVENT_STUDENT_AGENDA = f"{DOMAIN}_student_agenda_event"

# Local storage for downloaded didactic content
# Files land under  <config>/www/classeviva_didactics/ → served at /local/classeviva_didactics/
DIDACTICS_STORAGE_SUBDIR = "classeviva_didactics"
DIDACTICS_MAX_AGE_DAYS = 60

# Name of the HA service that triggers an immediate storage cleanup
SERVICE_CLEANUP_DIDACTICS = "cleanup_didactics_storage"
