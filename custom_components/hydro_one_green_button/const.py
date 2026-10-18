"""Constants for the Hydro One Green Button integration."""
from datetime import timedelta

DOMAIN = "hydro_one_green_button"
CONF_FILE_PATH = "file_path"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)
PLATFORMS = ["sensor"]
