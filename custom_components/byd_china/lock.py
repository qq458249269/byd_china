"""Lock entities for BYD Vehicle."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .pybyd_china.models.realtime import LockState
from .pybyd_china.models.vehicle import Vehicle

from .const import DOMAIN
from .coordinator import BydDataUpdateCoordinator
from .entity import BydVehicleEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, BydDataUpdateCoordinator] = data["coordinators"]

    entities: list[LockEntity] = []
    for vin, coordinator in coordinators.items():
        vehicle = coordinator.vehicle
        entities.append(BydLock(coordinator, vin, vehicle))

    async_add_entities(entities)


class BydLock(BydVehicleEntity, LockEntity):
    """BYD vehicle lock — locks/unlocks all doors."""

    _attr_has_entity_name = True
    _attr_translation_key = "vehicle_lock"

    def __init__(
        self,
        coordinator: BydDataUpdateCoordinator,
        vin: str,
        vehicle: Vehicle,
    ) -> None:
        super().__init__(coordinator)
        self._vin = vin
        self._vehicle = vehicle
        self._attr_unique_id = f"{vin}_lock"

    def _get_lock_states(self) -> list[LockState] | None:
        """Return list of door lock states from realtime data, or None if unknown."""
        snap = self._snapshot()
        if snap is None or snap.realtime is None:
            return None
        rt = snap.realtime
        states = [
            rt.left_front_door_lock,
            rt.right_front_door_lock,
            rt.left_rear_door_lock,
            rt.right_rear_door_lock,
        ]
        known = [s for s in states if s is not None]
        return known if known else None

    @property
    def is_locked(self) -> bool | None:
        states = self._get_lock_states()
        if states is None:
            return None
        return all(s == LockState.LOCKED for s in states)

    async def async_lock(self, **kwargs: Any) -> None:
        _LOGGER.debug("Locking all doors: vin=%s", self._vin[-6:])
        try:
            # execute_control internally polls remoteControlResult until the
            # cloud confirms the command; the lock state itself is only
            # refreshed by the low-frequency telemetry poll.
            await self.coordinator.execute_control("LOCKDOOR")
        except Exception as exc:
            _LOGGER.error("Lock command failed: %s", exc)
            raise

    async def async_unlock(self, **kwargs: Any) -> None:
        _LOGGER.debug("Unlocking all doors: vin=%s", self._vin[-6:])
        try:
            await self.coordinator.execute_control("OPENDOOR")
        except Exception as exc:
            _LOGGER.error("Unlock command failed: %s", exc)
            raise
