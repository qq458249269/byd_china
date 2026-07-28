"""Binary sensors for BYD Vehicle.

All door/lock/window/tire-status entities have been moved to sensor.py
as text sensors (showing "打开"/"关闭"/"已锁定"/"已解锁"/"正常"/"异常"/"未配备")
per user requirement. This file is kept as a stub for the platform registration.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BYD binary sensors from a config entry — currently empty."""
    # All entities moved to sensor.py as text sensors.
