"""Switch entities for BYD Vehicle.

All switch entities (battery heat, steering wheel heat) have been removed
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
    """Set up BYD switch entities from a config entry — currently empty."""
