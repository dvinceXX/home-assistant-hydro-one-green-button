"""Constants for the Hydro One Green Button integration."""
from datetime import timedelta

DOMAIN = "hydro_one_green_button"
CONF_FILE_PATH = "file_path"
CONF_PRICING_PLAN = "pricing_plan"
CONF_OFF_PEAK_RATE = "off_peak_rate"
CONF_MID_PEAK_RATE = "mid_peak_rate"
CONF_ON_PEAK_RATE = "on_peak_rate"
CONF_ULO_OVERNIGHT_RATE = "ulo_overnight_rate"
CONF_ULO_WEEKEND_RATE = "ulo_weekend_rate"
CONF_TIER1_RATE = "tier1_rate"
CONF_TIER2_RATE = "tier2_rate"
CONF_RATE_EFFECTIVE_DATE = "rate_effective_date"
DEFAULT_OFF_PEAK_RATE = 0.091
DEFAULT_MID_PEAK_RATE = 0.146
DEFAULT_ON_PEAK_RATE = 0.189
DEFAULT_ULO_OVERNIGHT_RATE = 0.037
DEFAULT_ULO_WEEKEND_RATE = 0.091
DEFAULT_TIER1_RATE = 0.112
DEFAULT_TIER2_RATE = 0.132
DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)
PLATFORMS = ["sensor"]
