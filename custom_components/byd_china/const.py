"""Constants for the BYD Vehicle (China) integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "byd_china"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SENSOR,
]

CONF_BASE_URL = "base_url"
CONF_COUNTRY_CODE = "country_code"
CONF_LANGUAGE = "language"
CONF_POLL_INTERVAL = "poll_interval"
CONF_GPS_POLL_INTERVAL = "gps_poll_interval"
CONF_DEVICE_PROFILE = "device_profile"
CONF_DEBUG_DUMPS = "debug_dumps"
CONF_TARGET_BRAND = "target_brand"
CONF_CONTROL_PIN = "control_pin"

DEFAULT_POLL_INTERVAL = 21600  # seconds = 6 hours
DEFAULT_GPS_POLL_INTERVAL = 21600  # seconds = 6 hours
DEFAULT_DEBUG_DUMPS = False
DEFAULT_LANGUAGE = "zh-Hans"
DEFAULT_COUNTRY_CODE = "CN"
DEFAULT_BASE_URL = "https://dilinksuperappserver-cn.byd.auto"
DEFAULT_TARGET_BRAND = "1"

MIN_POLL_INTERVAL = 1800  # seconds = 0.5 hour
MAX_POLL_INTERVAL = 2592000  # seconds = 720 hours (30 days)
MIN_GPS_POLL_INTERVAL = 1800  # seconds = 0.5 hour
MAX_GPS_POLL_INTERVAL = 2592000  # seconds = 720 hours (30 days)

# Only China
COUNTRY_OPTIONS: dict[str, tuple[str, str]] = {
    "China": ("CN", "zh-Hans"),
}

# Brand options for config flow
BRAND_OPTIONS: dict[str, str] = {
    "1": "王朝 (Dynasty)",
    "2": "海洋 (Ocean)",
    "3": "腾势 (Denza)",
    "4": "仰望 (Yangwang)",
    "5": "方程豹 (Fangchengbao)",
}


def get_country_connection_settings(country_name: str) -> tuple[str, str, str]:
    """Return (country_code, language, api_base_url) - always China."""
    return DEFAULT_COUNTRY_CODE, DEFAULT_LANGUAGE, DEFAULT_BASE_URL
