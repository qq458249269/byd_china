"""Sensors for BYD Vehicle."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfPressure
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .pybyd_china.models.gps import GpsInfo
from .pybyd_china.models.realtime import VehicleRealtimeData
from .pybyd_china.models.vehicle import Vehicle

from .const import DOMAIN
from .coordinator import BydDataUpdateCoordinator, BydGpsUpdateCoordinator
from .entity import BydVehicleEntity
from .pybyd_china._state_engine import VehicleSnapshot
from .pybyd_china.config import BRAND_NAMES

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def _normalize_epoch(value: Any) -> datetime | None:
    """Ensure a pre-parsed BydTimestamp is UTC-aware, or return None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    return None


@dataclass(frozen=True, kw_only=True)
class BydSensorDescription(SensorEntityDescription):
    """Describe a BYD sensor."""

    source: str = "realtime"
    attr_key: str | None = None
    value_fn: Callable[[Any], Any] | None = None
    use_gps_coordinator: bool = False


# ---------------------------------------------------------------------------
# Value conversion helpers
# ---------------------------------------------------------------------------

_LEADING_NUMBER_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)")

# System status: 0 -> "正常", >0 -> "异常", -1 -> "不可用"
def _status_text(attr: str) -> Callable[[Any], str | None]:
    def _fn(obj: Any) -> str | None:
        val = getattr(obj, attr, None)
        if val is None:
            return None
        raw = getattr(val, "value", val)
        if raw is None:
            return None
        if raw < 0:
            return "不可用"
        if raw == 0:
            return "正常"
        return "异常"
    return _fn


# Door state: 0 -> "关闭", 1 -> "打开", -1 -> "不可用"
def _door_text(attr: str) -> Callable[[Any], str | None]:
    def _fn(obj: Any) -> str | None:
        val = getattr(obj, attr, None)
        if val is None:
            return None
        raw = getattr(val, "value", val)
        if raw is None or raw < 0:
            return None
        if raw == 1:
            return "打开"
        return "关闭"
    return _fn


# Lock state: 1 -> "已解锁", 2 -> "已锁定", other -> None
def _lock_text(attr: str) -> Callable[[Any], str | None]:
    def _fn(obj: Any) -> str | None:
        val = getattr(obj, attr, None)
        if val is None:
            return None
        raw = getattr(val, "value", val)
        if raw is None or raw < 0:
            return None
        if raw == 2:
            return "已锁定"
        if raw == 1:
            return "已解锁"
        return None
    return _fn


# Window state: 1 -> "关闭", 2 -> "打开", -1 -> "未配备"
def _window_text(attr: str) -> Callable[[Any], str | None]:
    def _fn(obj: Any) -> str | None:
        val = getattr(obj, attr, None)
        if val is None:
            return None
        raw = getattr(val, "value", val)
        if raw is None:
            return None
        if raw < 0:
            return "未配备"
        if raw == 2:
            return "打开"
        return "关闭"
    return _fn


# Tire status: 0 -> "正常", >0 -> "异常", -1 -> "不可用"
def _tire_status_text(attr: str) -> Callable[[Any], str | None]:
    def _fn(obj: Any) -> str | None:
        val = getattr(obj, attr, None)
        if val is None:
            return None
        raw = getattr(val, "value", val)
        if raw is None or raw < 0:
            return None
        if raw == 0:
            return "正常"
        return "异常"
    return _fn


def _extract_kwh_value(obj: Any) -> float | None:
    val = getattr(obj, "total_consumption_en", None)
    if val is None:
        return None
    m = _LEADING_NUMBER_RE.match(str(val))
    if m:
        return float(m.group(1))
    return None


def _power_gear_text(obj: Any) -> str | None:
    val = getattr(obj, "power_gear", None)
    if val is None:
        return None
    raw = getattr(val, "value", val)
    if raw is None:
        return None
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None
    if v == 1:
        return "OFF"
    if v == 3:
        return "ON"
    return f"P{v}"


# =============================================
# SENSOR DESCRIPTIONS - strictly ordered per user spec
# =============================================

SENSOR_DESCRIPTIONS: tuple[BydSensorDescription, ...] = (
    # --- 车辆信息 ---
    BydSensorDescription(key="vin", source="realtime", icon="mdi:car"),
    BydSensorDescription(key="c_car_type", source="realtime", icon="mdi:car-side"),
    BydSensorDescription(key="auto_plate", source="realtime", icon="mdi:card-text"),
    BydSensorDescription(key="auto_out_color", source="realtime", icon="mdi:palette"),
    BydSensorDescription(key="vehicle_image", source="realtime", icon="mdi:image"),
    BydSensorDescription(key="channel", source="realtime", icon="mdi:tag"),
    # --- 系统状态 (0=正常, >0=异常) ---
    BydSensorDescription(key="power_battery", source="realtime", icon="mdi:battery-outline", value_fn=_status_text("power_battery")),
    BydSensorDescription(key="charging_system", source="realtime", icon="mdi:ev-station", value_fn=_status_text("charging_system")),
    BydSensorDescription(key="srs", source="realtime", icon="mdi:airbag", value_fn=_status_text("srs")),
    BydSensorDescription(key="esp", source="realtime", icon="mdi:car-traction-control", value_fn=_status_text("esp")),
    BydSensorDescription(key="braking_system", source="realtime", icon="mdi:car-brake-alert", value_fn=_status_text("braking_system")),
    BydSensorDescription(key="abs_warning", source="realtime", icon="mdi:car-brake-abs", value_fn=_status_text("abs_warning")),
    BydSensorDescription(key="steering_system", source="realtime", icon="mdi:steering", value_fn=_status_text("steering_system")),
    BydSensorDescription(key="power_system", source="realtime", icon="mdi:flash", value_fn=_status_text("power_system")),
    BydSensorDescription(key="oil_pressure_system", source="realtime", icon="mdi:oil", value_fn=_status_text("oil_pressure_system")),
    BydSensorDescription(key="engine_status", source="realtime", icon="mdi:engine", value_fn=_status_text("engine_status")),
    BydSensorDescription(key="ect", source="realtime", icon="mdi:coolant-temperature", value_fn=_status_text("ect")),
    BydSensorDescription(key="tirepressure_system", source="realtime", icon="mdi:car-tire-alert", value_fn=_status_text("tirepressure_system")),
    # --- 车门 (0=关闭, 1=打开) ---
    BydSensorDescription(key="left_front_door", source="realtime", icon="mdi:car-door", value_fn=_door_text("left_front_door")),
    BydSensorDescription(key="right_front_door", source="realtime", icon="mdi:car-door", value_fn=_door_text("right_front_door")),
    BydSensorDescription(key="left_rear_door", source="realtime", icon="mdi:car-door", value_fn=_door_text("left_rear_door")),
    BydSensorDescription(key="right_rear_door", source="realtime", icon="mdi:car-door", value_fn=_door_text("right_rear_door")),
    BydSensorDescription(key="trunk_lid", source="realtime", icon="mdi:car-back", value_fn=_door_text("trunk_lid")),
    # --- 门锁 (1=已解锁, 2=已锁定) ---
    BydSensorDescription(key="left_front_door_lock", source="realtime", icon="mdi:lock", value_fn=_lock_text("left_front_door_lock")),
    BydSensorDescription(key="right_front_door_lock", source="realtime", icon="mdi:lock", value_fn=_lock_text("right_front_door_lock")),
    BydSensorDescription(key="left_rear_door_lock", source="realtime", icon="mdi:lock", value_fn=_lock_text("left_rear_door_lock")),
    BydSensorDescription(key="right_rear_door_lock", source="realtime", icon="mdi:lock", value_fn=_lock_text("right_rear_door_lock")),
    # --- 车窗 (1=关闭, 2=打开, -1=未配备) ---
    BydSensorDescription(key="left_front_window", source="realtime", icon="mdi:car-door", value_fn=_window_text("left_front_window")),
    BydSensorDescription(key="right_front_window", source="realtime", icon="mdi:car-door", value_fn=_window_text("right_front_window")),
    BydSensorDescription(key="right_rear_window", source="realtime", icon="mdi:car-door", value_fn=_window_text("right_rear_window")),
    BydSensorDescription(key="left_rear_window", source="realtime", icon="mdi:car-door", value_fn=_window_text("left_rear_window")),
    BydSensorDescription(key="skylight", source="realtime", icon="mdi:car-door", value_fn=_window_text("skylight")),
    # --- 轮胎状态 (0=正常, >0=异常) ---
    BydSensorDescription(key="left_front_tire_status", source="realtime", icon="mdi:car-tire-alert", value_fn=_tire_status_text("left_front_tire_status")),
    BydSensorDescription(key="right_front_tire_status", source="realtime", icon="mdi:car-tire-alert", value_fn=_tire_status_text("right_front_tire_status")),
    BydSensorDescription(key="left_rear_tire_status", source="realtime", icon="mdi:car-tire-alert", value_fn=_tire_status_text("left_rear_tire_status")),
    BydSensorDescription(key="right_rear_tire_status", source="realtime", icon="mdi:car-tire-alert", value_fn=_tire_status_text("right_rear_tire_status")),
    # --- 胎压 (kPa, 整数) ---
    BydSensorDescription(key="left_front_tire_pressure", source="realtime", icon="mdi:car-tire-alert", native_unit_of_measurement=UnitOfPressure.KPA, suggested_display_precision=0),
    BydSensorDescription(key="right_front_tire_pressure", source="realtime", icon="mdi:car-tire-alert", native_unit_of_measurement=UnitOfPressure.KPA, suggested_display_precision=0),
    BydSensorDescription(key="left_rear_tire_pressure", source="realtime", icon="mdi:car-tire-alert", native_unit_of_measurement=UnitOfPressure.KPA, suggested_display_precision=0),
    BydSensorDescription(key="right_rear_tire_pressure", source="realtime", icon="mdi:car-tire-alert", native_unit_of_measurement=UnitOfPressure.KPA, suggested_display_precision=0),
    # --- 充电 ---
    BydSensorDescription(key="small_ui_smart_charge_tips", source="realtime", icon="mdi:ev-station"),
    BydSensorDescription(key="charging_power", source="realtime", icon="mdi:flash"),
    BydSensorDescription(key="remaining_hours", source="realtime", icon="mdi:clock-outline"),
    BydSensorDescription(key="remaining_minutes", source="realtime", icon="mdi:clock-outline"),
    # --- 电量/里程 (带单位，整数) ---
    BydSensorDescription(key="elec_percent", source="realtime", icon="mdi:battery", native_unit_of_measurement=PERCENTAGE, suggested_display_precision=0),
    BydSensorDescription(key="ev_endurance", source="realtime", icon="mdi:road-variant", native_unit_of_measurement=UnitOfLength.KILOMETERS, suggested_display_precision=0),
    BydSensorDescription(key="oil_percent", source="realtime", icon="mdi:gas-station", native_unit_of_measurement=PERCENTAGE, suggested_display_precision=0),
    BydSensorDescription(key="oil_endurance", source="realtime", icon="mdi:gas-station", native_unit_of_measurement=UnitOfLength.KILOMETERS, suggested_display_precision=0),
    BydSensorDescription(key="hev_mileage", source="realtime", icon="mdi:counter", native_unit_of_measurement=UnitOfLength.KILOMETERS, suggested_display_precision=0),
    BydSensorDescription(key="total_mileage", source="realtime", icon="mdi:counter", native_unit_of_measurement=UnitOfLength.KILOMETERS, suggested_display_precision=0),
    # --- 能耗 ---
    BydSensorDescription(key="recent_50km_avg_consumption_combined", source="recent_energy", icon="mdi:lightning-bolt", native_unit_of_measurement="L", suggested_display_precision=1),
    BydSensorDescription(key="recent_50km_avg_consumption_electric", source="recent_energy", icon="mdi:ev-station", native_unit_of_measurement="kWh", suggested_display_precision=1),
    BydSensorDescription(key="recent_50km_avg_consumption_fuel", source="recent_energy", icon="mdi:gas-station", native_unit_of_measurement="L", suggested_display_precision=1),
    BydSensorDescription(key="cumulative_avg_consumption_combined", source="historical_energy", icon="mdi:lightning-bolt", native_unit_of_measurement="L", suggested_display_precision=1),
    BydSensorDescription(key="cumulative_avg_consumption_fuel", source="historical_energy", icon="mdi:gas-station", native_unit_of_measurement="L", suggested_display_precision=1),
    BydSensorDescription(key="cumulative_avg_consumption_electric", source="realtime", icon="mdi:ev-station", native_unit_of_measurement="kWh", suggested_display_precision=1, value_fn=_extract_kwh_value),
    # --- 车辆状态 ---
    BydSensorDescription(key="speed", source="realtime", icon="mdi:speedometer", suggested_display_precision=0),
    BydSensorDescription(key="power_gear", source="realtime", icon="mdi:car-shift-pattern", value_fn=_power_gear_text),
    # --- GPS (原始数值) ---
    BydSensorDescription(key="gps_latitude", source="gps", suggested_display_precision=6, icon="mdi:crosshairs-gps", use_gps_coordinator=True),
    BydSensorDescription(key="gps_longitude", source="gps", suggested_display_precision=6, icon="mdi:crosshairs-gps", use_gps_coordinator=True),
    # --- 账号类型 ---
    BydSensorDescription(key="account_type", source="realtime", icon="mdi:account-check"),
    # --- 时间戳 ---
    BydSensorDescription(key="last_updated", source="realtime", device_class=SensorDeviceClass.TIMESTAMP, icon="mdi:clock-outline"),
    BydSensorDescription(key="gps_last_updated", source="gps", device_class=SensorDeviceClass.TIMESTAMP, icon="mdi:crosshairs-gps", use_gps_coordinator=True),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BYD sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, BydDataUpdateCoordinator] = data["coordinators"]
    gps_coordinators = data.get("gps_coordinators", {})

    entities: list[SensorEntity] = []
    for vin, coordinator in coordinators.items():
        vehicle = coordinator.vehicle
        gps_coordinator = gps_coordinators.get(vin)
        for description in SENSOR_DESCRIPTIONS:
            if description.use_gps_coordinator:
                if gps_coordinator is not None:
                    entities.append(BydSensor(gps_coordinator, vin, vehicle, description))
                continue
            entities.append(BydSensor(coordinator, vin, vehicle, description))

    async_add_entities(entities)


# Keys that read from Vehicle model (not realtime data)
_VEHICLE_INFO_KEYS = {"vin", "c_car_type", "auto_plate", "auto_out_color", "vehicle_image", "channel"}

# Brand channel -> display name (keys are ints; BRAND_NAMES uses strings)
_CHANNEL_MAP = {int(k): v for k, v in BRAND_NAMES.items()}


class BydSensor(BydVehicleEntity, SensorEntity):
    """Representation of a BYD vehicle sensor."""

    _attr_has_entity_name = True
    entity_description: BydSensorDescription

    def __init__(
        self,
        coordinator: BydDataUpdateCoordinator | BydGpsUpdateCoordinator,
        vin: str,
        vehicle: Vehicle,
        description: BydSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_translation_key = description.key
        self._vin = vin
        self._vehicle = vehicle
        self._attr_unique_id = f"{vin}_{description.source}_{description.key}"
        super().__init__(coordinator)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_gps_direct(self) -> GpsInfo | None:
        """Get GPS data directly - works for both coordinator types.

        For GPS coordinator: data IS GpsInfo.
        For telemetry coordinator: data is VehicleSnapshot, gps is snap.gps.
        """
        data = self.coordinator.data
        if data is None:
            return None
        if isinstance(data, GpsInfo):
            return data
        # VehicleSnapshot path
        return getattr(data, "gps", None)

    def _resolve_value(self) -> Any:
        """Extract the current value using the description's extraction logic."""
        key = self.entity_description.key

        # Timestamp sensors
        if key == "last_updated":
            realtime = self._get_realtime()
            if realtime is None:
                return None
            return _normalize_epoch(getattr(realtime, "timestamp", None))

        if key == "gps_last_updated":
            gps = self._get_gps_direct()
            if gps is None:
                return None
            return _normalize_epoch(getattr(gps, "gps_timestamp", None))

        # Vehicle info fields
        if key == "vin":
            return self._vehicle.vin or None
        if key == "c_car_type":
            # Try multiple sources for full model name
            realtime = self._get_realtime()
            if realtime is not None:
                val = getattr(realtime, "c_car_type", None)
                if val:
                    return val
            # Try raw dict from vehicle_info
            raw = getattr(self._vehicle, "raw", None)
            if isinstance(raw, dict):
                for k in ("cCarType", "outModelType", "modelName"):
                    v = raw.get(k)
                    if v and isinstance(v, str) and v.strip():
                        return v.strip()
            if self._vehicle.out_model_type:
                return self._vehicle.out_model_type
            return self._vehicle.model_name or None
        if key == "auto_plate":
            realtime = self._get_realtime()
            if realtime is not None:
                val = getattr(realtime, "auto_plate", None)
                if val:
                    return val
            raw = getattr(self._vehicle, "raw", None)
            if isinstance(raw, dict):
                v = raw.get("autoPlate")
                if v and isinstance(v, str) and v.strip():
                    return v.strip()
            return self._vehicle.auto_plate or None
        if key == "auto_out_color":
            realtime = self._get_realtime()
            if realtime is not None:
                val = getattr(realtime, "auto_out_color", None)
                if val:
                    return val
            raw = getattr(self._vehicle, "raw", None)
            if isinstance(raw, dict):
                v = raw.get("autoOutColor")
                if v and isinstance(v, str) and v.strip():
                    return v.strip()
            return self._vehicle.auto_out_color or None
        if key == "vehicle_image":
            raw = getattr(self._vehicle, "raw", None)
            if isinstance(raw, dict):
                v = raw.get("diFansVehicleImg")
                if v and isinstance(v, str) and v.strip():
                    return v.strip()
            return self._vehicle.pic_main_url or None
        if key == "channel":
            # channel from vehicle_info raw dict, translate to brand name
            ch = self._vehicle.channel
            if ch is not None:
                return _CHANNEL_MAP.get(ch, str(ch))
            # Fallback: try raw dict
            raw = getattr(self._vehicle, "raw", None)
            if isinstance(raw, dict):
                ch = raw.get("channel") or raw.get("appChannel")
                if ch is not None:
                    ch = int(ch) if isinstance(ch, str) and ch.isdigit() else ch
                    return _CHANNEL_MAP.get(ch, str(ch)) if isinstance(ch, int) else str(ch)
            return None

        # GPS fields
        if key == "gps_latitude":
            gps = self._get_gps_direct()
            return gps.latitude if gps is not None else None
        if key == "gps_longitude":
            gps = self._get_gps_direct()
            return gps.longitude if gps is not None else None

        # Account type field
        if key == "account_type":
            snap = self._snapshot()
            if snap is not None and snap.is_shared:
                return "授权账号"
            return "车主账号"

        # Standard path: get source object and apply value_fn or direct attr
        source = self.entity_description.source
        obj = self._get_source_obj(source)
        if obj is None:
            return None

        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(obj)

        # Energy dict sources: historical_energy / recent_energy are plain dicts
        # recent_energy structure: {avgFullCon, avgEvCon, avgOilCon, driveConP, ...} (from getRecentDataByVin)
        # historical_energy structure: {sumOilData: {cost, size, fuel, fee, ...}, selfList: [{date, lastFee, sumFee}, ...]}
        if source in ("historical_energy", "recent_energy") and isinstance(obj, dict):
            if key == "recent_50km_avg_consumption_combined":
                return obj.get("avgFullCon")
            if key == "recent_50km_avg_consumption_electric":
                return obj.get("avgEvCon")
            if key == "recent_50km_avg_consumption_fuel":
                return obj.get("avgOilCon")
            if key == "cumulative_avg_consumption_combined":
                sum_oil = obj.get("sumOilData")
                if isinstance(sum_oil, dict):
                    return sum_oil.get("fee")
                return None
            if key == "cumulative_avg_consumption_fuel":
                sum_oil = obj.get("sumOilData")
                if isinstance(sum_oil, dict):
                    return sum_oil.get("fuel")
                return None
            return obj.get(key)

        attr = self.entity_description.attr_key or key
        value = getattr(obj, attr, None)
        # For enum values, return the raw int
        enum_value = getattr(value, "value", None)
        if isinstance(enum_value, int):
            return enum_value
        return value

    # ------------------------------------------------------------------
    # Entity properties
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Return True when the coordinator has data for this source."""
        if not super().available:
            return False
        key = self.entity_description.key
        if key in ("last_updated", "gps_last_updated"):
            return self._resolve_value() is not None
        if key in _VEHICLE_INFO_KEYS:
            return True
        if key in ("gps_latitude", "gps_longitude"):
            return self._get_gps_direct() is not None
        if key == "account_type":
            return True
        if key in ("recent_50km_avg_consumption_combined", "recent_50km_avg_consumption_electric", "recent_50km_avg_consumption_fuel"):
            snap = self._snapshot()
            return snap is not None and bool(snap.recent_energy)
        if key in ("cumulative_avg_consumption_combined", "cumulative_avg_consumption_fuel"):
            snap = self._snapshot()
            if snap is None or not snap.historical_energy:
                return False
            sum_oil = snap.historical_energy.get("sumOilData")
            return isinstance(sum_oil, dict)
        return self._get_source_obj(self.entity_description.source) is not None

    @property
    def icon(self) -> str | None:
        key = self.entity_description.key
        if key == "account_type":
            snap = self._snapshot()
            if snap is not None and snap.is_shared:
                return "mdi:account-switch"
            return "mdi:account-check"
        return self.entity_description.icon

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self._resolve_value()
