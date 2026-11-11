"""Constants for the Hydro One Green Button integration."""
from datetime import timedelta

DOMAIN = "hydro_one_green_button"
CONF_FILE_PATH = "file_path"
CONF_OFF_PEAK_RATE = "off_peak_rate"
CONF_MID_PEAK_RATE = "mid_peak_rate"
CONF_ON_PEAK_RATE = "on_peak_rate"
DEFAULT_OFF_PEAK_RATE = 0.091
DEFAULT_MID_PEAK_RATE = 0.146
DEFAULT_ON_PEAK_RATE = 0.189
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)
PLATFORMS = ["sensor"]
