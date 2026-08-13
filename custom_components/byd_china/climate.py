"""Climate entity for BYD Vehicle A/C control."""

from __future__ import annotations

import asyncio
import logging
import time as _time
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .pybyd_china.models.vehicle import Vehicle

from .const import DOMAIN
from .coordinator import BydDataUpdateCoordinator
from .entity import BydVehicleEntity
from .pybyd_china._constants import celsius_to_scale, scale_to_celsius

_LOGGER = logging.getLogger(__name__)

BYD_TEMP_MIN = 17
BYD_TEMP_MAX = 33
BYD_TEMP_STEP = 1.0
BYD_TEMP_OFFSET = 16

CYCLE_MODE_EXTERNAL = 1
CYCLE_MODE_INTERNAL = 2

PRESET_EXTERNAL = "外循环"
PRESET_INTERNAL = "内循环"

FAN_AUTO = "自动"
FAN_LEVELS = [FAN_AUTO, "1", "2", "3", "4", "5", "6", "7"]

SWING_10MIN = "10分钟"
SWING_15MIN = "15分钟"
SWING_20MIN = "20分钟"
SWING_25MIN = "25分钟"
SWING_30MIN = "30分钟"
SWING_MODES = [SWING_10MIN, SWING_15MIN, SWING_20MIN, SWING_25MIN, SWING_30MIN]

TIMESPAN_MAP = {
    SWING_10MIN: 1,
    SWING_15MIN: 2,
    SWING_20MIN: 3,
    SWING_25MIN: 4,
    SWING_30MIN: 5,
}
TIMESPAN_REVERSE = {v: k for k, v in TIMESPAN_MAP.items()}
TIMESPAN_DEFAULT = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, BydDataUpdateCoordinator] = data["coordinators"]

    entities: list[ClimateEntity] = []
    for vin, coordinator in coordinators.items():
        vehicle = coordinator.vehicle
        entities.append(BydClimate(coordinator, vin, vehicle))

    async_add_entities(entities)


class BydClimate(BydVehicleEntity, ClimateEntity):
    """BYD vehicle climate entity.

    Controls: on/off, temperature, preset (cycle mode), fan (wind level),
    swing mode (time span duration).
    """

    _attr_has_entity_name = True
    _attr_translation_key = "byd_climate"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = BYD_TEMP_MIN
    _attr_max_temp = BYD_TEMP_MAX
    _attr_target_temperature_step = BYD_TEMP_STEP
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_preset_modes = [PRESET_EXTERNAL, PRESET_INTERNAL]
    _attr_fan_modes = FAN_LEVELS
    _attr_swing_modes = SWING_MODES
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: BydDataUpdateCoordinator,
        vin: str,
        vehicle: Vehicle,
    ) -> None:
        self._vin = vin
        self._vehicle = vehicle
        self._attr_unique_id = f"{vin}_climate_byd_climate"
        super().__init__(coordinator)
        self._optimistic_mode: HVACMode | None = None
        self._optimistic_temp: float | None = None
        self._optimistic_preset: str | None = None
        self._optimistic_fan: str | None = None
        self._optimistic_timespan: int = TIMESPAN_DEFAULT
        self._optimistic_until: float = 0.0

    def _is_optimistic_valid(self) -> bool:
        return _time.time() < self._optimistic_until

    def _cloud_hvac_on(self) -> bool:
        snap = self._snapshot()
        if snap is None or snap.hvac is None:
            return False
        raw = getattr(snap.hvac, "raw", None)
        if isinstance(raw, dict):
            val = raw.get("status")
            if val is not None:
                try:
                    return int(val) == 1
                except (TypeError, ValueError):
                    pass
        st = getattr(snap.hvac, "status", None)
        if st is not None:
            try:
                return int(st) == 1
            except (TypeError, ValueError):
                pass
        return snap.hvac.is_ac_on

    def _cloud_target_temp(self) -> float | None:
        snap = self._snapshot()
        if snap is None or snap.hvac is None:
            return None
        raw = getattr(snap.hvac, "raw", None)
        if isinstance(raw, dict):
            val = raw.get("mainSettingTempNew")
            if val is not None:
                try:
                    c = float(val)
                    if BYD_TEMP_MIN <= c <= BYD_TEMP_MAX:
                        return c
                except (TypeError, ValueError):
                    pass
            val = raw.get("mainSettingTemp")
            if val is not None:
                try:
                    c = self._decode_temp(val)
                    if c is not None and BYD_TEMP_MIN <= c <= BYD_TEMP_MAX:
                        return c
                except (TypeError, ValueError):
                    pass
        hvac = snap.hvac
        val = hvac.main_setting_temp_new
        if val is not None:
            try:
                c = float(val)
                if BYD_TEMP_MIN <= c <= BYD_TEMP_MAX:
                    return c
            except (TypeError, ValueError):
                pass
        val = hvac.main_setting_temp
        if val is not None:
            try:
                c = self._decode_temp(val)
                if c is not None and BYD_TEMP_MIN <= c <= BYD_TEMP_MAX:
                    return c
            except (TypeError, ValueError):
                pass
        return None

    def _decode_temp(self, raw: Any) -> float | None:
        """Decode a BYD scale temperature (1-17 → 17-33 °C).

        ``main_setting_temp`` is always scale; precise degrees come from
        ``main_setting_temp_new``. Treating every value as scale removes the
        old scale/°C ambiguity (a raw °C of 17 previously decoded as 33 °C).
        """
        return scale_to_celsius(raw)

    def _cloud_cycle_mode(self) -> int | None:
        snap = self._snapshot()
        if snap is None or snap.hvac is None:
            return None
        raw = getattr(snap.hvac, "raw", None)
        if isinstance(raw, dict):
            val = raw.get("cycleChoice")
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass
        val = getattr(snap.hvac, "cycle_choice", None)
        if val is not None:
            try:
                return int(val.value if hasattr(val, "value") else val)
            except (TypeError, ValueError):
                pass
        return None

    def _cloud_wind_level(self) -> int | None:
        snap = self._snapshot()
        if snap is None or snap.hvac is None:
            return None
        raw = getattr(snap.hvac, "raw", None)
        if isinstance(raw, dict):
            val = raw.get("windLevel")
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass
            val = raw.get("powerGear")
            if val is not None:
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass
        val = getattr(snap.hvac, "power_gear", None)
        if val is not None:
            try:
                return int(val.value if hasattr(val, "value") else val)
            except (TypeError, ValueError):
                pass
        return None

    @property
    def hvac_mode(self) -> HVACMode:
        if self._is_optimistic_valid() and self._optimistic_mode is not None:
            return self._optimistic_mode
        if self._cloud_hvac_on():
            return HVACMode.HEAT_COOL
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        mode = self.hvac_mode
        if mode == HVACMode.OFF:
            return HVACAction.OFF
        return HVACAction.IDLE

    @property
    def target_temperature(self) -> float | None:
        if self._is_optimistic_valid() and self._optimistic_temp is not None:
            return self._optimistic_temp
        return self._cloud_target_temp()

    @property
    def current_temperature(self) -> float | None:
        snap = self._snapshot()
        if snap is None or snap.hvac is None:
            return None
        if snap.hvac.temp_in_car is not None:
            try:
                return float(snap.hvac.temp_in_car)
            except (TypeError, ValueError):
                pass
        return None

    @property
    def preset_mode(self) -> str | None:
        if self._is_optimistic_valid() and self._optimistic_preset is not None:
            return self._optimistic_preset
        cycle = self._cloud_cycle_mode()
        if cycle == CYCLE_MODE_INTERNAL:
            return PRESET_INTERNAL
        if cycle == CYCLE_MODE_EXTERNAL:
            return PRESET_EXTERNAL
        return PRESET_INTERNAL

    @property
    def fan_mode(self) -> str | None:
        if self._is_optimistic_valid() and self._optimistic_fan is not None:
            return self._optimistic_fan
        wl = self._cloud_wind_level()
        if wl is None or wl == 0:
            return FAN_AUTO
        if 1 <= wl <= 7:
            return str(wl)
        return FAN_AUTO

    @property
    def swing_mode(self) -> str | None:
        ts = self._optimistic_timespan if self._is_optimistic_valid() else TIMESPAN_DEFAULT
        return TIMESPAN_REVERSE.get(ts, SWING_10MIN)

    async def _poll_sync(self) -> None:
        for delay in (2.0, 4.0, 8.0):
            await asyncio.sleep(delay)
            try:
                await self.coordinator.async_refresh_hvac()
            except Exception:
                pass

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            self._optimistic_mode = HVACMode.OFF
            self._optimistic_until = _time.time() + 30
            self.async_write_ha_state()
            try:
                await self.coordinator.execute_control("CLOSEAIR")
                await self._poll_sync()
            except Exception as exc:
                self._optimistic_mode = None
                _LOGGER.error("CLOSEAIR failed: %s", exc)
                raise
            return

        params = self._build_ac_params()
        self._optimistic_mode = HVACMode.HEAT_COOL
        self._optimistic_temp = params.get("_display_temp")
        self._optimistic_until = _time.time() + 30
        self.async_write_ha_state()
        try:
            await self.coordinator.execute_control("OPENAIR", params)
            await self._poll_sync()
        except Exception as exc:
            self._optimistic_mode = None
            self._optimistic_temp = None
            _LOGGER.error("OPENAIR failed: %s", exc)
            raise

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        if not (BYD_TEMP_MIN <= temperature <= BYD_TEMP_MAX):
            _LOGGER.warning("忽略非法空调温度设置 %s（支持 %s-%s°C）", temperature, BYD_TEMP_MIN, BYD_TEMP_MAX)
            return
        params = self._build_ac_params(temperature=temperature)
        self._optimistic_mode = HVACMode.HEAT_COOL
        self._optimistic_temp = temperature
        self._optimistic_until = _time.time() + 30
        self.async_write_ha_state()
        try:
            await self.coordinator.execute_control("OPENAIR", params)
            await self._poll_sync()
        except Exception as exc:
            self._optimistic_mode = None
            self._optimistic_temp = None
            _LOGGER.error("OPENAIR (set temp) failed: %s", exc)
            raise

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_EXTERNAL:
            cycle = CYCLE_MODE_EXTERNAL
        else:
            cycle = CYCLE_MODE_INTERNAL
        self._optimistic_preset = preset_mode
        self._optimistic_until = _time.time() + 30
        self.async_write_ha_state()
        params = self._build_ac_params(cycle_mode=cycle)
        try:
            await self.coordinator.execute_control("OPENAIR", params)
            await self._poll_sync()
        except Exception as exc:
            self._optimistic_preset = None
            _LOGGER.error("OPENAIR (set preset) failed: %s", exc)
            raise

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        self._optimistic_fan = fan_mode
        self._optimistic_until = _time.time() + 30
        self.async_write_ha_state()
        params = self._build_ac_params(fan_mode_str=fan_mode)
        try:
            await self.coordinator.execute_control("OPENAIR", params)
            await self._poll_sync()
        except Exception as exc:
            self._optimistic_fan = None
            _LOGGER.error("OPENAIR (set fan) failed: %s", exc)
            raise

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        ts = TIMESPAN_MAP.get(swing_mode, TIMESPAN_DEFAULT)
        self._optimistic_timespan = ts
        self._optimistic_until = _time.time() + 30
        self.async_write_ha_state()
        # TIMESPAN_MAP values are already the BYD time_span codes (1-5).
        params = self._build_ac_params(time_span=ts)
        try:
            await self.coordinator.execute_control("OPENAIR", params)
            await self._poll_sync()
        except Exception as exc:
            self._optimistic_timespan = TIMESPAN_DEFAULT
            _LOGGER.error("OPENAIR (set swing/timespan) failed: %s", exc)
            raise

    def _build_ac_params(
        self,
        temperature: float | None = None,
        cycle_mode: int | None = None,
        fan_mode_str: str | None = None,
        time_span: int | None = None,
    ) -> dict[str, Any]:
        # temperature=None: use the cloud's current set temp so the car keeps
        # its setting; fall back to 25°C only when the cloud hasn't reported a
        # valid value.
        if temperature is None:
            temperature = self.target_temperature
        if not (BYD_TEMP_MIN <= (temperature or 0) <= BYD_TEMP_MAX):
            temperature = 25.0
        byd_temp = celsius_to_scale(temperature)

        if cycle_mode is None:
            preset = self.preset_mode
            cycle_mode = CYCLE_MODE_EXTERNAL if preset == PRESET_EXTERNAL else CYCLE_MODE_INTERNAL

        if fan_mode_str is None:
            fan_mode_str = self.fan_mode or FAN_AUTO
        if fan_mode_str == FAN_AUTO:
            wind_level = 0
        else:
            try:
                wind_level = max(0, min(7, int(fan_mode_str)))
            except (TypeError, ValueError):
                wind_level = 0

        if time_span is None:
            time_span = self._optimistic_timespan

        params: dict[str, Any] = {
            "cycleMode": cycle_mode,
            "remoteMode": 4,
            "windLevel": wind_level,
            "timeSpan": time_span,
        }
        if byd_temp is not None:
            params["mainSettingTemp"] = byd_temp
            params["copilotSettingTemp"] = byd_temp
            # Store the degrees actually sent, so optimistic state reflects the
            # command even when it fell back to the cloud's or 25°C default.
            params["_display_temp"] = float(byd_temp) + BYD_TEMP_OFFSET
        return params

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._is_optimistic_valid():
            cloud_on = self._cloud_hvac_on()
            cloud_temp = self._cloud_target_temp()
            if self._optimistic_mode == HVACMode.OFF and not cloud_on:
                self._optimistic_mode = None
                self._optimistic_temp = None
                self._optimistic_until = 0
            elif self._optimistic_mode == HVACMode.HEAT_COOL and cloud_on:
                if self._optimistic_temp is not None and cloud_temp is not None:
                    if abs(cloud_temp - self._optimistic_temp) <= 1.0:
                        self._optimistic_mode = None
                        self._optimistic_temp = None
                        self._optimistic_until = 0
                elif self._optimistic_temp is None:
                    self._optimistic_mode = None
                    self._optimistic_until = 0
        super()._handle_coordinator_update()
