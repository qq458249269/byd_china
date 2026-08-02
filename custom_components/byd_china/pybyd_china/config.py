"""Configuration and data models for BYD China API client."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Default values for CN app
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://dilinksuperappserver-cn.byd.auto"
DEFAULT_COUNTRY_CODE = "CN"
DEFAULT_LANGUAGE = "zh-Hans"
DEFAULT_TARGET_BRAND = "1"  # dynasty
DEFAULT_APP_CHANNEL = "99"
DEFAULT_CN_APP_INNER_VERSION = "512"
DEFAULT_CN_APP_VERSION = "9.11.2"
DEFAULT_NETWORK_OPERATOR = "\u4e2d\u56fd\u7535\u4fe1"
DEFAULT_TBOX_VERSION = "3"
DEFAULT_SOFT_TYPE = "0"
DEFAULT_DEVICE_TYPE = "0"
DEFAULT_IS_AUTO = "0"

# Brand ID to name mapping
BRAND_NAMES = {
    "1": "王朝",
    "2": "海洋",
    "3": "腾势",
    "4": "仰望",
    "5": "方程豹",
}

# ---------------------------------------------------------------------------
# BydConfig
# ---------------------------------------------------------------------------

@dataclass
class BydConfig:
    """Configuration for BYD China API client."""

    username: str
    password: str
    base_url: str = DEFAULT_BASE_URL
    country_code: str = DEFAULT_COUNTRY_CODE
    language: str = DEFAULT_LANGUAGE
    time_zone: str = "Asia/Shanghai"
    control_pin: str | None = None
    target_brand: str = DEFAULT_TARGET_BRAND
    app_channel: str = DEFAULT_APP_CHANNEL
    cn_app_inner_version: str = DEFAULT_CN_APP_INNER_VERSION
    cn_app_version: str = DEFAULT_CN_APP_VERSION
    network_operator: str = DEFAULT_NETWORK_OPERATOR
    tbox_version: str = DEFAULT_TBOX_VERSION
    soft_type: str = DEFAULT_SOFT_TYPE
    device_type: str = DEFAULT_DEVICE_TYPE
    is_auto: str = DEFAULT_IS_AUTO


# ---------------------------------------------------------------------------
# DeviceProfile
# ---------------------------------------------------------------------------

@dataclass
class DeviceProfile:
    """Device fingerprint for API requests.

    Uses generic device values that match common CN Android phones.
    These are NOT real device identifiers - they are synthetic defaults
    that pass BYD CN server validation.
    """

    ostype: str = "and"
    imei: str = "BANGCLE01234"
    mac: str = "00:00:00:00:00:00"
    model: str = "M2006C3LG"
    sdk: str = "35"
    mod: str = "Xiaomi"
    imei_md5: str = "A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6"
    mobile_brand: str = "XIAOMI"
    mobile_model: str = "M2006C3LG"
    device_type: str = DEFAULT_DEVICE_TYPE
    network_type: str = "wifi"
    os_type: str = "Android"
    os_version: str = "16"


# ---------------------------------------------------------------------------
# BydSession
# ---------------------------------------------------------------------------

@dataclass
class BydSession:
    """Login session data."""

    super_id: str = ""
    user_id: str = ""
    encrypt_token: str = ""
    sign_token: str = ""
    content_key: str = ""
    sign_key: str = ""

    @property
    def identifier(self) -> str:
        """Return the primary identifier (superId for CN)."""
        return self.super_id or self.user_id

    @property
    def has_tokens(self) -> bool:
        """Return whether both token fields are present and usable."""
        return bool(self.encrypt_token and self.sign_token)
