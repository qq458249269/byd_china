"""Vehicle realtime data model.

Enum values and field meanings are documented in API_MAPPING.md.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from ..models._base import COMMON_KEY_ALIASES, BydBaseModel, BydEnum, BydTimestamp, is_negative, is_temp_sentinel

# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------


class OnlineState(BydEnum):
    """Vehicle online/offline state."""

    UNKNOWN = -1
    ONLINE = 1
    OFFLINE = 2


class ConnectState(BydEnum):
    """T-Box connection state."""

    UNKNOWN = -1
    DISCONNECTED = 0
    CONNECTED = 1


class VehicleState(BydEnum):
    """Vehicle power state."""

    UNKNOWN = -1
    OFF = 0
    ON = 2  # not confirmed


class ChargingState(BydEnum):
    """Charging state indicator."""

    UNKNOWN = -1
    NOT_CHARGING = 0
    CHARGING = 1
    CONNECTED = 15
    # We previously thought value 15 represented "connected", but this value
    # does not change when the charging gun is disconnected, so we should not
    # rely on it.


class TirePressureUnit(BydEnum):
    """Unit used for tire pressure readings."""

    UNKNOWN = -1
    BAR = 1
    PSI = 2
    KPA = 3


class DoorOpenState(BydEnum):
    """Door/trunk open/closed state."""

    UNKNOWN = -1
    CLOSED = 0
    OPEN = 1


class LockState(BydEnum):
    """Door lock state.

    ``UNAVAILABLE`` (0) is returned by the API when state is unknown.
    """

    UNKNOWN = -1
    UNAVAILABLE = 0
    UNLOCKED = 1
    LOCKED = 2


class WindowState(BydEnum):
    """Window open/closed state."""

    UNKNOWN = -1
    CLOSED = 1
    OPEN = 2


class PowerGear(BydEnum):
    """Vehicle power state."""

    UNKNOWN = -1
    OFF = 1
    ON = 3


class StearingWheelHeat(BydEnum):
    """Steering wheel heating state.

    Status values: ``-1`` = on, ``1`` = off.
    Command values use a different scale (see ``to_command_level``).
    """

    ON = -1
    OFF = 1

    def to_command_level(self) -> int:
        """Return the value to send in a seat-climate command.

        Command scale: ``1`` = on, ``3`` = off.
        """
        return 1 if self == StearingWheelHeat.ON else 3


class SeatHeatVentState(BydEnum):
    """Seat heating / ventilation level.

    ``NO_DATA`` (0) means the API has no information for this seat
    in the current response -- it does not indicate hardware absence.
    """

    UNKNOWN = -1
    NO_DATA = 0
    OFF = 1
    LOW = 2
    HIGH = 3

    def to_command_level(self) -> int:
        """Return the value to send in a ``set_seat_climate()`` command.

        Command scale is inverted: HIGH=3 -> 1, LOW=2 -> 2, OFF=1 -> 3.
        ``NO_DATA`` and ``UNKNOWN`` map to ``0`` (no action).
        """
        return _SEAT_STATUS_TO_COMMAND.get(self.value, 0)


_SEAT_STATUS_TO_COMMAND: dict[int, int] = {
    -1: 0,  # UNKNOWN  -> no action
    0: 0,  # NO_DATA  -> no action
    1: 3,  # OFF      -> 3 (off)
    2: 2,  # LOW      -> 2 (low)
    3: 1,  # HIGH     -> 1 (high)
}


class AirCirculationMode(BydEnum):
    """Air circulation mode.

    Xposed log confirmed:
    - Request 1 (first open AC, default = internal circulation): cycleMode=2
    - Request 4 (only occurrence, switched to external): cycleMode=1
    Therefore: 1 = EXTERNAL (外循环), 2 = INTERNAL (内循环).
    """

    UNKNOWN = -1
    UNAVAILABLE = 0
    EXTERNAL = 1
    INTERNAL = 2


# ------------------------------------------------------------------
# Key aliases: BYD API key -> canonical camelCase key
# ------------------------------------------------------------------

_KEY_ALIASES: dict[str, str] = {
    **COMMON_KEY_ALIASES,
    "backCover": "trunkLid",
    "leftFrontTirepressure": "leftFrontTirePressure",
    "rightFrontTirepressure": "rightFrontTirePressure",
    "leftRearTirepressure": "leftRearTirePressure",
    "rightRearTirepressure": "rightRearTirePressure",
    "abs": "absWarning",
    "time": "timestamp",
    "recent50kmEnergy": "recent50KmEnergy",
}


class VehicleRealtimeData(BydBaseModel):
    """Realtime telemetry data for a vehicle.

    Numeric fields are ``None`` when the value is absent or
    unparseable from the API response.  All original data is
    available in the ``raw`` dict.
    """

    _KEY_ALIASES: ClassVar[dict[str, str]] = _KEY_ALIASES

    _SENTINEL_RULES: ClassVar[dict[str, Callable[..., bool]]] = {
        "temp_in_car": is_temp_sentinel,
        "full_hour": is_negative,
        "full_minute": is_negative,
        "remaining_hours": is_negative,
        "remaining_minutes": is_negative,
        # ECT value uses both -129 (temp sentinel) and -1 (generic unavailable).
        "ect_value": lambda v: is_temp_sentinel(v) or is_negative(v),
        # Warning / status indicators: -1 means unavailable.
        "ect": is_negative,
        "abs_warning": is_negative,
        "svs": is_negative,
        "srs": is_negative,
        "eps": is_negative,
        "esp": is_negative,
        "pwr": is_negative,
        "power_system": is_negative,
        "tirepressure_system": is_negative,
        "rapid_tire_leak": is_negative,
        "left_front_tire_status": is_negative,
        "right_front_tire_status": is_negative,
        "left_rear_tire_status": is_negative,
        "right_rear_tire_status": is_negative,
        "upgrade_status": is_negative,
        # Fuel range: -1 means unavailable (BEV or no data).
        "oil_endurance": is_negative,
        # Charge rate: large negative sentinels when not charging.
        "rate": lambda v: v is not None and v <= -9,
    }

    # --- Connection & state ---
    online_state: OnlineState = OnlineState.UNKNOWN
    connect_state: ConnectState = ConnectState.UNKNOWN
    vehicle_state: VehicleState = VehicleState.UNKNOWN
    request_serial: str | None = None

    # --- Battery & range ---
    elec_percent: float | None = None
    """Battery state of charge (0-100 %)."""
    power_battery: float | None = None
    """Alternative battery percentage field."""
    endurance_mileage: float | None = None
    """Estimated remaining EV range (km)."""
    ev_endurance: float | None = None
    """Alternative EV range field."""
    endurance_mileage_v2: float | None = None
    endurance_mileage_v2_unit: str | None = None
    total_mileage: float | None = None
    """Odometer reading (km)."""
    total_mileage_v2: float | None = None
    total_mileage_v2_unit: str | None = None

    # --- Driving ---
    speed: float | None = None
    """Current speed (km/h)."""
    power_gear: PowerGear | None = None
    """Vehicle power state (off / on)."""

    # --- Climate ---
    temp_in_car: float | None = None
    """Interior temperature (deg C). Sentinel ``-129`` is normalised to ``None``."""
    main_setting_temp: int | None = None
    """Driver-side set temperature on BYD scale (1-17)."""
    main_setting_temp_new: float | None = None
    """Driver-side set temperature (deg C, precise)."""
    air_run_state: AirCirculationMode | None = None
    """Air circulation mode."""

    # --- Seat heating/ventilation ---
    main_seat_heat_state: SeatHeatVentState | None = None
    main_seat_ventilation_state: SeatHeatVentState | None = None
    copilot_seat_heat_state: SeatHeatVentState | None = None
    copilot_seat_ventilation_state: SeatHeatVentState | None = None
    steering_wheel_heat_state: StearingWheelHeat | None = None
    lr_seat_heat_state: SeatHeatVentState | None = None
    lr_seat_ventilation_state: SeatHeatVentState | None = None
    rr_seat_heat_state: SeatHeatVentState | None = None
    rr_seat_ventilation_state: SeatHeatVentState | None = None

    # --- Charging ---
    charging_state: ChargingState = ChargingState.UNKNOWN
    """Charging field from the realtime payload.

    May remain ``UNKNOWN`` while ``charge_state`` carries the
    authoritative status.  Prefer :pyattr:`effective_charging_state`.
    """
    charge_state: ChargingState | None = None
    """Authoritative realtime charging state."""
    wait_status: int | None = None
    """Charge wait status."""
    full_hour: int | None = None
    """Estimated hours to full charge. Sentinel ``-1`` -> ``None``."""
    full_minute: int | None = None
    """Estimated minutes to full charge. Sentinel ``-1`` -> ``None``."""
    remaining_hours: int | None = None
    """Remaining hours component. Sentinel ``-1`` -> ``None``."""
    remaining_minutes: int | None = None
    """Remaining minutes component. Sentinel ``-1`` -> ``None``."""
    booking_charge_state: int | None = None
    """Scheduled charging state (0=off)."""
    booking_charging_hour: int | None = None
    """Scheduled charge start hour."""
    booking_charging_minute: int | None = None
    """Scheduled charge start minute."""

    # --- Doors ---
    left_front_door: DoorOpenState | None = None
    right_front_door: DoorOpenState | None = None
    left_rear_door: DoorOpenState | None = None
    right_rear_door: DoorOpenState | None = None
    trunk_lid: DoorOpenState | None = None
    sliding_door: DoorOpenState | None = None
    forehold: DoorOpenState | None = None
    """Front trunk / frunk."""

    # --- Locks ---
    left_front_door_lock: LockState | None = None
    right_front_door_lock: LockState | None = None
    left_rear_door_lock: LockState | None = None
    right_rear_door_lock: LockState | None = None
    sliding_door_lock: LockState | None = None

    # --- Windows ---
    left_front_window: WindowState | None = None
    right_front_window: WindowState | None = None
    left_rear_window: WindowState | None = None
    right_rear_window: WindowState | None = None
    skylight: WindowState | None = None

    # --- Tire pressure ---
    left_front_tire_pressure: float | None = None
    right_front_tire_pressure: float | None = None
    left_rear_tire_pressure: float | None = None
    right_rear_tire_pressure: float | None = None
    left_front_tire_status: int | None = None
    right_front_tire_status: int | None = None
    left_rear_tire_status: int | None = None
    right_rear_tire_status: int | None = None
    tire_press_unit: TirePressureUnit | None = None
    """Pressure unit: BAR (1), PSI (2), KPA (3)."""
    tirepressure_system: int | None = None
    """TPMS system state. 0=normal, >0=warning. Sentinel ``-1`` -> ``None``."""
    rapid_tire_leak: int | None = None
    """Rapid tire leak indicator. 0=no leak, >0=leak. Sentinel ``-1`` -> ``None``."""

    # --- Energy consumption ---
    total_power: float | None = None
    gl: float | None = None
    """Instantaneous battery power (W)."""
    total_energy: str | None = None
    """Total energy (string; "--" when unavailable)."""
    nearest_energy_consumption: str | None = None
    """Nearest energy consumption (string; "--" when unavailable)."""
    nearest_energy_consumption_unit: str | None = None
    recent_50km_energy: str | None = None
    """Recent 50 km energy (string; "--" when unavailable)."""

    # --- Fuel (hybrid vehicles) ---
    oil_endurance: float | None = None
    """Fuel-based range (km). Sentinel ``-1`` -> ``None``."""
    oil_percent: float | None = None
    """Fuel percentage."""
    total_oil: float | None = None
    """Total fuel consumption."""

    # --- System indicators ---
    power_system: int | None = None
    """Power system warning. 0=normal, >0=warning."""
    engine_status: int | None = None
    """Engine status."""
    epb: int | None = None
    """Electronic parking brake. 0=released, 1=engaged."""
    eps: int | None = None
    """Electric power steering warning. 0=normal, >0=warning."""
    esp: int | None = None
    """Electronic stability program warning. 0=normal, >0=warning."""
    abs_warning: int | None = None
    """ABS warning. 0=normal, >0=warning."""
    svs: int | None = None
    """Service vehicle soon. 0=normal, >0=warning."""
    srs: int | None = None
    """Supplemental restraint system (airbag) warning. 0=normal, >0=warning."""
    ect: int | None = None
    """Engine coolant temperature warning. 0=normal, >0=warning."""
    ect_value: int | None = None
    """Engine coolant temperature (deg C)."""
    pwr: int | None = None
    """Power warning. 0=normal, >0=warning."""

    # --- Feature states ---
    sentry_status: int | None = None
    """Sentry/dashcam mode (0=off, 1=on)."""
    battery_heat_state: int | None = None
    """Battery heating state."""
    charge_heat_state: int | None = None
    """Charge heating state."""
    upgrade_status: int | None = None
    """OTA upgrade status. 0=none, >0=active."""

    # --- Third-row seats ---
    lr_third_heat_state: SeatHeatVentState | None = None
    """Third-row left seat heat state."""
    lr_third_ventilation_state: SeatHeatVentState | None = None
    """Third-row left seat ventilation state."""
    rr_third_heat_state: SeatHeatVentState | None = None
    """Third-row right seat heat state."""
    rr_third_ventilation_state: SeatHeatVentState | None = None
    """Third-row right seat ventilation state."""

    # --- Charging (extended) ---
    rate: float | None = None
    """Charge rate. Sentinel values (-999, -9) when not charging."""
    less_one_min: bool | None = None
    """Time-to-full is less than one minute."""

    # --- Energy (extended) ---
    energy_consumption: str | None = None
    """Energy consumption value (string, differs from nearestEnergyConsumption)."""
    total_consumption: str | None = None
    """Chinese-locale total consumption label."""
    total_consumption_en: str | None = None
    """English-locale total consumption label (e.g. '16.6kW·h/100km')."""
    charging_power: str | None = None
    """Charging power (string, e.g. '0' or '7.0')."""
    hev_mileage: float | None = None
    """HEV (hybrid) mileage in km."""

    # --- Fuel (extended) ---
    oil_pressure_system: int | None = None
    """Oil pressure warning. 0=normal."""

    # --- HVAC (CN extended) ---
    heat_status: str | None = None
    """Seat/steering heat status (CN API, string like 'null' or '1')."""
    small_ui_smart_charge_tips: str | None = None
    """Smart charging tip text (CN API, e.g. '未预约')."""

    # --- Warnings (extended) ---
    braking_system: int | None = None
    """Braking system warning. 0=normal."""
    charging_system: int | None = None
    """Charging system warning. 0=normal."""
    steering_system: int | None = None
    """Steering system warning. 0=normal."""
    ok_light: int | None = None
    """OK/ready indicator. 0=off."""

    # --- Features (extended) ---
    repair_mode_switch: str | None = None
    """Repair/service mode. '0'=off."""

    # --- Misc ---
    vehicle_time_zone: str | None = None
    """Vehicle timezone (e.g. 'Europe/Rome')."""
    power_battery_connection: int | None = None
    """Battery connectivity indicator. -1=unknown, 0=disconnected."""
    ins: int | None = None
    """Unknown indicator field."""

    # --- Metadata ---
    timestamp: BydTimestamp = None
    """Data timestamp (parsed to UTC datetime)."""

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_ready_raw(vehicle_info: dict[str, Any]) -> bool:
        """Return True if a raw realtime payload appears to contain meaningful data."""
        if not vehicle_info:
            return False
        if vehicle_info.get("onlineState") == int(OnlineState.OFFLINE):
            return False

        tire_fields = [
            "leftFrontTirepressure",
            "rightFrontTirepressure",
            "leftRearTirepressure",
            "rightRearTirepressure",
        ]
        try:
            if any(float(vehicle_info.get(f) or 0) > 0 for f in tire_fields):
                return True
        except (ValueError, TypeError):
            pass
        try:
            if int(vehicle_info.get("time") or 0) > 0:
                return True
        except (ValueError, TypeError):
            pass
        try:
            return float(vehicle_info.get("enduranceMileage") or 0) > 0
        except (ValueError, TypeError):
            return False

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_online(self) -> bool:
        """Whether the vehicle is reporting as online."""
        return self.online_state == OnlineState.ONLINE

    @property
    def effective_charging_state(self) -> ChargingState:
        """Canonical charging state derived from realtime payload.

        ``charge_state`` is the authoritative source.
        """
        if self.charge_state is None:
            return ChargingState.UNKNOWN
        return self.charge_state

    @property
    def is_charging(self) -> bool:
        """Whether the vehicle is currently charging."""
        return self.effective_charging_state == ChargingState.CHARGING

    @property
    def is_charger_connected(self) -> bool:
        """Whether the charging gun is physically connected."""
        return self.effective_charging_state in (
            ChargingState.CHARGING,
            ChargingState.CONNECTED,
        )

    @property
    def time_to_full_minutes(self) -> int | None:
        """Total estimated minutes until fully charged.

        Returns ``None`` when either component is unavailable.
        """
        if self.full_hour is None or self.full_minute is None:
            return None
        return self.full_hour * 60 + self.full_minute

    @property
    def interior_temp_available(self) -> bool:
        """Whether interior temperature reading is valid."""
        return self.temp_in_car is not None

    @property
    def is_locked(self) -> bool | None:
        """Whether all doors are locked.

        Returns ``None`` when no authoritative lock state is available.
        """
        locks = [
            self.left_front_door_lock,
            self.right_front_door_lock,
            self.left_rear_door_lock,
            self.right_rear_door_lock,
        ]
        _SKIP = {None, LockState.UNKNOWN, LockState.UNAVAILABLE}
        known = [lk for lk in locks if lk not in _SKIP]
        if not known:
            return None
        return all(lk == LockState.LOCKED for lk in known)

    @property
    def is_any_door_open(self) -> bool:
        """Whether any door/trunk/frunk is open."""
        doors = [
            self.left_front_door,
            self.right_front_door,
            self.left_rear_door,
            self.right_rear_door,
            self.trunk_lid,
            self.sliding_door,
            self.forehold,
        ]
        return any(d == DoorOpenState.OPEN for d in doors if d is not None)

    @property
    def is_any_window_open(self) -> bool:
        """Whether any window is open."""
        windows = [
            self.left_front_window,
            self.right_front_window,
            self.left_rear_window,
            self.right_rear_window,
            self.skylight,
        ]
        return any(w == WindowState.OPEN for w in windows if w is not None)

    @property
    def is_vehicle_on(self) -> bool:
        """Whether the vehicle is powered on."""
        return self.power_gear == PowerGear.ON

    @property
    def is_battery_heating(self) -> bool | None:
        """Whether the battery heating system is active."""
        if self.battery_heat_state is None:
            return None
        return bool(self.battery_heat_state)

    @property
    def is_steering_wheel_heating(self) -> bool | None:
        """Whether steering wheel heating is active."""
        if self.steering_wheel_heat_state is None:
            return None
        return self.steering_wheel_heat_state == StearingWheelHeat.ON
