"""Data models for BYD API responses."""

from .._constants import celsius_to_scale
from ..models._base import BydBaseModel, BydEnum, BydTimestamp, parse_byd_timestamp
from ..models.charging import ChargingStatus
from ..models.energy import EnergyConsumption
from ..models.gps import GpsInfo
from ..models.hvac import HvacStatus
from ..models.realtime import (
    AirCirculationMode,
    ChargingState,
    ConnectState,
    DoorOpenState,
    LockState,
    OnlineState,
    PowerGear,
    SeatHeatVentState,
    StearingWheelHeat,
    TirePressureUnit,
    VehicleRealtimeData,
    VehicleState,
    WindowState,
)
from ..models.vehicle import EmpowerRange, Vehicle

__all__ = [
    "AirCirculationMode",
    "BydBaseModel",
    "BydEnum",
    "BydTimestamp",
    "ChargingState",
    "ChargingStatus",
    "ConnectState",
    "DoorOpenState",
    "EmpowerRange",
    "EnergyConsumption",
    "GpsInfo",
    "HvacStatus",
    "LockState",
    "OnlineState",
    "PowerGear",
    "SeatHeatVentState",
    "StearingWheelHeat",
    "TirePressureUnit",
    "Vehicle",
    "VehicleRealtimeData",
    "VehicleState",
    "WindowState",
    "celsius_to_scale",
    "parse_byd_timestamp",
]
