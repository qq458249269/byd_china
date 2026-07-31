"""Button entities for BYD Vehicle."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .pybyd_china.models.vehicle import Vehicle

from .const import DOMAIN
from .coordinator import BydDataUpdateCoordinator
from .entity import BydVehicleEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class BydButtonDescription(ButtonEntityDescription):
    command_type: str = ""


BUTTON_DESCRIPTIONS: tuple[BydButtonDescription, ...] = (
    BydButtonDescription(key="door_unlock", command_type="OPENDOOR", icon="mdi:lock-open"),
    BydButtonDescription(key="door_lock", command_type="LOCKDOOR", icon="mdi:lock"),
    BydButtonDescription(key="ac_on", command_type="OPENAIR", icon="mdi:air-conditioner"),
    BydButtonDescription(key="ac_off", command_type="CLOSEAIR", icon="mdi:air-conditioner-off"),
    BydButtonDescription(key="open_trunk", command_type="OPENTRUNK", icon="mdi:car-back"),
    BydButtonDescription(key="window_close", command_type="CLOSEWINDOW", icon="mdi:car-door"),
    BydButtonDescription(key="find_car", command_type="FINDCAR", icon="mdi:car"),
    BydButtonDescription(key="flash_lights", command_type="FLASHLIGHTNOWHISTLE", icon="mdi:car-light-high"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, BydDataUpdateCoordinator] = data["coordinators"]

    entities: list[ButtonEntity] = []
    for vin, coordinator in coordinators.items():
        vehicle = coordinator.vehicle
        for description in BUTTON_DESCRIPTIONS:
            entities.append(BydButton(coordinator, vin, vehicle, description))

    async_add_entities(entities)


class BydButton(BydVehicleEntity, ButtonEntity):
    _attr_has_entity_name = True
    entity_description: BydButtonDescription

    def __init__(
        self,
        coordinator: BydDataUpdateCoordinator,
        vin: str,
        vehicle: Vehicle,
        description: BydButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._vin = vin
        self._vehicle = vehicle
        self._attr_unique_id = f"{vin}_button_{description.key}"

    async def async_press(self) -> None:
        try:
            await self.coordinator.execute_control(self.entity_description.command_type)
            await self.coordinator.async_delayed_refresh()
        except Exception as exc:
            _LOGGER.error("Button command %s failed: %s", self.entity_description.command_type, exc)
            raise
