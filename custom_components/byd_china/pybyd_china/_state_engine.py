"""Immutable vehicle state snapshot shared between coordinator and entities."""



from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any

from .models.charging import ChargingStatus
from .models.energy import EnergyConsumption
from .models.gps import GpsInfo
from .models.hvac import HvacStatus
from .models.realtime import VehicleRealtimeData
from .models.vehicle import Vehicle


# ------------------------------------------------------------------
# Immutable snapshot
# ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VehicleSnapshot:
    """Immutable composite snapshot of all known vehicle state.

    A new instance is created on every accepted state change.
    Consumers compare identity (``is``) or field values to detect changes.
    """

    vehicle: Vehicle
    realtime: VehicleRealtimeData | None = None
    hvac: HvacStatus | None = None
    gps: GpsInfo | None = None
    charging: ChargingStatus | None = None
    energy: EnergyConsumption | None = None
    is_shared: bool = False
    gps_wgs84_latitude: float | None = None
    gps_wgs84_longitude: float | None = None
    historical_energy: dict[str, Any] = dc_field(default_factory=dict)
    recent_energy: dict[str, Any] = dc_field(default_factory=dict)
