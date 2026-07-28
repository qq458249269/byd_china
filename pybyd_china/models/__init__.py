"""Data models for BYD API responses."""

from .._constants import VALID_CLIMATE_DURATIONS, minutes_to_time_span
from ..models._base import BydBaseModel, BydEnum, BydTimestamp, parse_byd_timestamp
from ..models.charging import ChargingStatus
from ..models.command_gating import CommandGateRule, CommandGateVerdict
from ..models.control import (
    BatteryHeatParams,
    ClimateScheduleParams,
    ClimateStartParams,
    CommandAck,
    CommandAckDiagnostics,
    CommandAckEvent,
    CommandLifecycleEvent,
    CommandLifecycleStatus,
    ControlState,
    RemoteCommand,
    RemoteControlResult,
    SeatClimateParams,
    VerifyControlPasswordResponse,
)
from ..models.energy import EnergyConsumption
from ..models.gps import GpsInfo
from ..models.hvac import HvacStatus, celsius_to_scale
from ..models.latest_config import LatestConfigFunction, VehicleCapabilities, VehicleLatestConfig
from ..models.push_notification import PushNotificationState
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
from ..models.smart_charging import SmartChargingSchedule
from ..models.token import AuthToken
from ..models.vehicle import EmpowerRange, Vehicle

__all__ = [
    "AirCirculationMode",
    "AuthToken",
    "BatteryHeatParams",
    "BydBaseModel",
    "BydEnum",
    "BydTimestamp",
    "ChargingState",
    "ChargingStatus",
    "CommandGateRule",
    "CommandGateVerdict",
    "ClimateScheduleParams",
    "ClimateStartParams",
    "CommandAck",
    "CommandAckDiagnostics",
    "CommandAckEvent",
    "CommandLifecycleEvent",
    "CommandLifecycleStatus",
    "ConnectState",
    "ControlState",
    "DoorOpenState",
    "EmpowerRange",
    "EnergyConsumption",
    "GpsInfo",
    "HvacStatus",
    "LatestConfigFunction",
    "LockState",
    "OnlineState",
    "PowerGear",
    "PushNotificationState",
    "RemoteCommand",
    "RemoteControlResult",
    "SeatClimateParams",
    "SeatHeatVentState",
    "SmartChargingSchedule",
    "StearingWheelHeat",
    "TirePressureUnit",
    "VALID_CLIMATE_DURATIONS",
    "VehicleCapabilities",
    "Vehicle",
    "VehicleLatestConfig",
    "VehicleRealtimeData",
    "VehicleState",
    "VerifyControlPasswordResponse",
    "WindowState",
    "celsius_to_scale",
    "minutes_to_time_span",
    "parse_byd_timestamp",
]
