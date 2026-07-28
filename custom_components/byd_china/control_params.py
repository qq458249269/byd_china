"""Control parameter data models and enums for BYD China remote commands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class AccountType(StrEnum):
    OWNER = "车主账号"
    SHARED = "授权账号"


class SeatHeatLevel(IntEnum):
    OFF = 3
    LOW = 2
    HIGH = 1


class SeatVentilationLevel(IntEnum):
    OFF = 0
    LOW = 2
    HIGH = 1


SEAT_HEAT_MAP: dict[str, int] = {
    "关": SeatHeatLevel.OFF,
    "低": SeatHeatLevel.LOW,
    "高": SeatHeatLevel.HIGH,
}

SEAT_VENTILATION_MAP: dict[str, int] = {
    "关": SeatVentilationLevel.OFF,
    "低": SeatVentilationLevel.LOW,
    "高": SeatVentilationLevel.HIGH,
}


@dataclass(frozen=True, kw_only=True)
class AcOnParams:
    main_setting_temp: int | None = None
    copilot_setting_temp: int | None = None
    wind_level: int | None = None
    cycle_mode: int | None = None

    def to_api_map(self) -> dict:
        params: dict = {
            "cycleMode": self.cycle_mode if self.cycle_mode is not None else 2,
            "remoteMode": 4,
            "timeSpan": 1,
        }
        if self.main_setting_temp is not None:
            params["mainSettingTemp"] = self.main_setting_temp - 14
        if self.copilot_setting_temp is not None:
            params["copilotSettingTemp"] = self.copilot_setting_temp - 14
        if self.wind_level is not None:
            params["windLevel"] = self.wind_level
        return params


@dataclass
class SeatClimateParams:
    chair_type: str = "1"
    main_seat_heat: int | None = None
    main_seat_ventilation: int | None = None
    copilot_seat_heat: int | None = None
    copilot_seat_ventilation: int | None = None
    steering_wheel_heat: int | None = None

    def to_api_map(self) -> dict:
        params: dict = {"chairType": self.chair_type}
        if self.main_seat_heat is not None:
            params["mainSeatHeatState"] = int(self.main_seat_heat)
        if self.main_seat_ventilation is not None:
            params["mainSeatVentilationState"] = int(self.main_seat_ventilation)
        if self.copilot_seat_heat is not None:
            params["copilotSeatHeatState"] = int(self.copilot_seat_heat)
        if self.copilot_seat_ventilation is not None:
            params["copilotSeatVentilationState"] = int(self.copilot_seat_ventilation)
        if self.steering_wheel_heat is not None:
            params["steeringWheelHeatState"] = int(self.steering_wheel_heat)
        return params


@dataclass
class BookingAirParams:
    main_setting_temp: int | None = None
    copilot_setting_temp: int | None = None
    booking_time: int | None = None

    def to_api_map(self) -> dict:
        params: dict = {
            "cycleMode": 2,
            "remoteMode": 1,
            "acSwitch": 0,
        }
        if self.main_setting_temp is not None:
            params["mainSettingTemp"] = self.main_setting_temp - 14
        if self.copilot_setting_temp is not None:
            params["copilotSettingTemp"] = self.copilot_setting_temp - 14
        if self.booking_time is not None:
            params["bookingTime"] = self.booking_time
        return params


@dataclass
class BatteryHeatParams:
    battery_heat_switch: int = 1

    def to_api_map(self) -> dict:
        return {"batteryHeatSwitch": self.battery_heat_switch}
