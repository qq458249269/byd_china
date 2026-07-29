"""Constants for the BYD Vehicle (China) integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "byd_china"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.DEVICE_TRACKER,
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
CONF_APP_CHANNEL = "app_channel"
CONF_CONTROL_PIN = "control_pin"

DEFAULT_POLL_INTERVAL = 300
DEFAULT_GPS_POLL_INTERVAL = 300
DEFAULT_DEBUG_DUMPS = False
DEFAULT_COUNTRY = "China"
DEFAULT_LANGUAGE = "zh-Hans"
DEFAULT_COUNTRY_CODE = "CN"
DEFAULT_BASE_URL = "https://dilinksuperappserver-cn.byd.auto"
DEFAULT_TARGET_BRAND = "1"
DEFAULT_APP_CHANNEL = "99"

MIN_POLL_INTERVAL = 30
MAX_POLL_INTERVAL = 3600
MIN_GPS_POLL_INTERVAL = 30
MAX_GPS_POLL_INTERVAL = 3600

# China-only node
NODE_METADATA: dict[int, dict[str, str]] = {
    1: {
        "region": "China",
        "api_base_url": DEFAULT_BASE_URL,
    },
}

BASE_URLS: dict[str, str] = {
    node["region"]: node["api_base_url"] for node in NODE_METADATA.values()
}

# Only China
COUNTRY_OPTIONS: dict[str, tuple[str, str]] = {
    "China": ("CN", "zh-Hans"),
}

COUNTRY_TO_NODE: dict[str, int] = {
    "CN": 1,
}

COUNTRY_BY_CODE: dict[str, tuple[str, str]] = {
    country_code: (country_name, language)
    for country_name, (country_code, language) in COUNTRY_OPTIONS.items()
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


def get_country_connection_settings_by_code(country_code: str) -> tuple[str, str, str]:
    """Return (country_code, language, api_base_url) - always China."""
    return DEFAULT_COUNTRY_CODE, DEFAULT_LANGUAGE, DEFAULT_BASE_URL
