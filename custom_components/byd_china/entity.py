"""Base entity mixins for BYD Vehicle."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .pybyd_china._state_engine import VehicleSnapshot
from .pybyd_china.models.gps import GpsInfo
from .pybyd_china.models.realtime import VehicleRealtimeData
from .pybyd_china.models.vehicle import Vehicle

from .const import DOMAIN
from .coordinator import BydDataUpdateCoordinator, get_vehicle_display

_LOGGER = logging.getLogger(__name__)


class BydVehicleEntity(CoordinatorEntity[BydDataUpdateCoordinator]):
    """Mixin providing common properties for BYD vehicle entities.

    Subclasses must set ``_vin`` and ``_vehicle`` before calling
    ``super().__init__``.  Data is read from ``coordinator.data`` which
    is a :class:`VehicleSnapshot` — no local shadow state, no optimistic
    tracking.
    """

    _vin: str
    _vehicle: Vehicle

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info common to every BYD entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._vin)},
            name=get_vehicle_display(self._vehicle),
            manufacturer=self._vehicle.brand_name or "BYD",
            model=self._vehicle.model_name,
            serial_number=self._vin,
            hw_version=self._vehicle.tbox_version or None,
        )

    @property
    def available(self) -> bool:
        """Available when coordinator has a snapshot with vehicle data."""
        if not super().available:
            return False
        return self.coordinator.data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return VIN as the default extra attribute."""
        return {"vin": self._vin}

    # ------------------------------------------------------------------
    # Snapshot data helpers
    # ------------------------------------------------------------------

    def _snapshot(self) -> VehicleSnapshot | None:
        """Return the coordinator's current snapshot."""
        return self.coordinator.data

    def _get_realtime(self) -> VehicleRealtimeData | None:
        """Return realtime data from the snapshot."""
        snap = self._snapshot()
        return snap.realtime if snap is not None else None

    def _get_gps(self) -> GpsInfo | None:
        """Return GPS data from the snapshot."""
        snap = self._snapshot()
        return snap.gps if snap is not None else None

    def _get_source_obj(self, source: str = "realtime") -> Any | None:
        """Return the snapshot section for the given *source* string.

        Supported values: ``"realtime"``, ``"gps"``, ``"hvac"``, ``"historical_energy"``, ``"recent_energy"``.
        """
        if source == "realtime":
            return self._get_realtime()
        if source == "gps":
            return self._get_gps()
        if source == "hvac":
            snap = self._snapshot()
            return snap.hvac if snap is not None else None
        if source == "historical_energy":
            snap = self._snapshot()
            return snap.historical_energy if snap is not None else None
        if source == "recent_energy":
            snap = self._snapshot()
            return snap.recent_energy if snap is not None else None
        return None

    def _is_vehicle_on(self) -> bool:
        """Return True when the vehicle is on."""
        realtime = self._get_realtime()
        if realtime is None:
            return False
        return bool(realtime.is_vehicle_on)

    async def _execute_control(self, command_type: str, control_params: dict | None = None) -> None:
        """Execute a remote control command via the coordinator."""
        await self.coordinator.execute_control(command_type, control_params)

    def _build_control_params(self, description: Any) -> dict | None:
        """Build control parameters from an entity description.

        Override in subclasses that need command-specific parameters.
        """
        return None
