"""Data coordinators for BYD China."""

from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .pybyd_china.client import BydClient
from .pybyd_china.config import BydConfig, BydSession, DeviceProfile
from .pybyd_china.exceptions import (
    BydApiError,
    BydAuthenticationError,
    BydTransportError,
)
from .pybyd_china.models.gps import GpsInfo
from .pybyd_china.models.hvac import HvacStatus
from .pybyd_china.models.realtime import VehicleRealtimeData
from .pybyd_china.models.vehicle import Vehicle
from .pybyd_china._state_engine import VehicleSnapshot

from .const import (
    CONF_BASE_URL,
    CONF_COUNTRY_CODE,
    CONF_DEBUG_DUMPS,
    CONF_DEVICE_PROFILE,
    CONF_LANGUAGE,
    CONF_TARGET_BRAND,
    DEFAULT_DEBUG_DUMPS,
    DEFAULT_LANGUAGE,
    DEFAULT_TARGET_BRAND,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_HA_EVENT_COMMAND_LIFECYCLE: str = f"{DOMAIN}_command_lifecycle"

_AUTH_ERRORS = (BydAuthenticationError,)
_RECOVERABLE_ERRORS = (BydApiError, BydTransportError)

_A = 6378245.0
_EE = 0.00669342162296594323


def _out_of_china(lat: float, lon: float) -> bool:
    return not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x: float, y: float) -> float:
    ret = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * abs(x ** 0.5))
    ret += (20.0 * (math.sin(6.0 * x * math.pi) + math.sin(2.0 * x * math.pi))) * 2.0 / 3.0
    ret += (20.0 * (math.sin(y * math.pi) + math.sin(3.0 * y * math.pi))) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lon(x: float, y: float) -> float:
    ret = (300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * abs(x ** 0.5))
    ret += (20.0 * (math.sin(6.0 * x * math.pi) + math.sin(2.0 * x * math.pi))) * 2.0 / 3.0
    ret += (20.0 * (math.sin(x * math.pi) + math.sin(3.0 * x * math.pi))) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lat_gcj02: float, lon_gcj02: float) -> tuple[float, float]:
    if _out_of_china(lat_gcj02, lon_gcj02):
        return lat_gcj02, lon_gcj02
    dlat = _transform_lat(lon_gcj02 - 105.0, lat_gcj02 - 35.0)
    dlon = _transform_lon(lon_gcj02 - 105.0, lat_gcj02 - 35.0)
    radlat = lat_gcj02 / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (_A / sqrtmagic * math.cos(radlat) * math.pi)
    return lat_gcj02 - dlat, lon_gcj02 - dlon


def get_vehicle_display(vehicle: Vehicle) -> str:
    """Return a human-readable display name for a vehicle."""
    if vehicle.auto_plate:
        return vehicle.auto_plate
    if vehicle.auto_alias:
        return vehicle.auto_alias
    if vehicle.model_name:
        return vehicle.model_name
    return vehicle.vin[-6:] if vehicle.vin else "BYD"


class BydApi:
    """Thin wrapper around the pybyd_china client.

    Manages client lifecycle, exception translation, and debug dump writing.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, session: Any) -> None:
        self._hass = hass
        self._entry = entry
        self._http_session = session
        time_zone = hass.config.time_zone or "UTC"
        device_data = entry.data.get(CONF_DEVICE_PROFILE, {})
        self._device = DeviceProfile(**device_data) if device_data else DeviceProfile()
        self._config = BydConfig(
            username=entry.data["username"],
            password=entry.data["password"],
            base_url=entry.data[CONF_BASE_URL],
            country_code=entry.data.get(CONF_COUNTRY_CODE, "CN"),
            language=entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
            time_zone=time_zone,
            control_pin=entry.data.get("control_pin"),
            target_brand=entry.data.get(CONF_TARGET_BRAND, DEFAULT_TARGET_BRAND),
        )
        self._client: BydClient | None = None
        self._debug_dumps_enabled = entry.options.get(
            CONF_DEBUG_DUMPS,
            DEFAULT_DEBUG_DUMPS,
        )
        self._debug_dump_dir = Path(hass.config.path(".storage/byd_vehicle_debug"))
        _LOGGER.debug(
            "BYD API initialized: entry_id=%s, base_url=%s, target_brand=%s",
            entry.entry_id,
            entry.data[CONF_BASE_URL],
            self._config.target_brand,
        )

    # ------------------------------------------------------------------
    # Debug dumps
    # ------------------------------------------------------------------

    def _write_debug_dump(self, category: str, payload: dict[str, Any]) -> None:
        if not self._debug_dumps_enabled:
            return
        try:
            self._debug_dump_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%fZ")
            file_path = self._debug_dump_dir / f"{timestamp}_{category}.json"
            file_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Failed to write BYD debug dump.", exc_info=True)

    async def _async_write_debug_dump(
        self,
        category: str,
        payload: dict[str, Any],
    ) -> None:
        await self._hass.async_add_executor_job(
            self._write_debug_dump, category, payload
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def config(self) -> BydConfig:
        return self._config

    @property
    def debug_dumps_enabled(self) -> bool:
        return self._debug_dumps_enabled

    async def async_write_debug_dump(
        self, category: str, payload: dict[str, Any]
    ) -> None:
        await self._async_write_debug_dump(category, payload)

    async def async_shutdown(self) -> None:
        await self._invalidate_client()

    async def _ensure_client(self) -> BydClient:
        if self._client is None:
            _LOGGER.debug(
                "Creating new pybyd_china client: entry_id=%s",
                self._entry.entry_id,
            )
            self._client = BydClient(
                self._config,
                self._device,
                session=self._http_session,
            )
            await self._client.login()
        return self._client

    async def _invalidate_client(self) -> None:
        if self._client is not None:
            _LOGGER.debug(
                "Invalidating pybyd_china client: entry_id=%s",
                self._entry.entry_id,
            )
            self._client = None

    async def async_call(
        self,
        handler: Any,
        *,
        vin: str | None = None,
        command: str | None = None,
    ) -> Any:
        """Execute a pybyd_china call with error translation."""
        call_started = perf_counter()
        _LOGGER.debug(
            "BYD API call started: entry_id=%s, vin=%s, command=%s",
            self._entry.entry_id,
            vin[-6:] if vin else "-",
            command or "-",
        )
        try:
            client = await self._ensure_client()
            result = await handler(client)
            _LOGGER.debug(
                "BYD API call succeeded: entry_id=%s, vin=%s, "
                "command=%s, duration_ms=%.1f",
                self._entry.entry_id,
                vin[-6:] if vin else "-",
                command or "-",
                (perf_counter() - call_started) * 1000,
            )
            return result
        except BydAuthenticationError as exc:
            await self._invalidate_client()
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except BydTransportError as exc:
            await self._invalidate_client()
            raise UpdateFailed(str(exc)) from exc
        except BydApiError as exc:
            raise UpdateFailed(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug(
                "BYD API call failed: entry_id=%s, vin=%s, command=%s, "
                "duration_ms=%.1f, error=%s",
                self._entry.entry_id,
                vin[-6:] if vin else "-",
                command or "-",
                (perf_counter() - call_started) * 1000,
                type(exc).__name__,
            )
            raise


class BydDataUpdateCoordinator(DataUpdateCoordinator[VehicleSnapshot | None]):
    """Coordinator for telemetry updates for a single VIN."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: BydApi,
        vin: str,
        vehicle_info: dict[str, Any],
        poll_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_telemetry_{vin[-6:]}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self._api = api
        self._vin = vin
        self._vehicle_info = vehicle_info
        self._fixed_interval = timedelta(seconds=poll_interval)
        self._polling_enabled = True
        self._force_next_refresh = False
        self._is_shared = False
        self._pin_verified: bool = False

        # Build a Vehicle model from the vehicle_info dict for entity compatibility.
        # CN API may return Java-style date strings (e.g. "Mon Aug 12 00:00:00 CST 2024")
        # that BydTimestamp can't parse. We pre-process and also fall back to
        # manual construction if model_validate still fails.
        if vehicle_info:
            vehicle_info = self._preprocess_vehicle_info(vehicle_info)
        try:
            self._vehicle = Vehicle.model_validate(vehicle_info) if vehicle_info else Vehicle(vin=vin)
        except Exception as exc:
            _LOGGER.warning("Vehicle.model_validate failed, using fallback: %s", exc)
            self._vehicle = self._build_vehicle_fallback(vehicle_info or {}, vin)

    @staticmethod
    def _preprocess_vehicle_info(info: dict[str, Any]) -> dict[str, Any]:
        """Convert CN-specific Java date strings to epoch timestamps.

        The CN API returns dates like "Mon Aug 12 00:00:00 CST 2024" for
        autoBoughtTime / yunActiveTime, but the pydantic Vehicle model
        expects epoch integers for BydTimestamp fields. This method converts
        them in-place before model_validate is called.
        """
        import re
        from datetime import datetime, timedelta, timezone

        result = dict(info)
        date_fields = {"autoBoughtTime", "yunActiveTime"}

        for field in date_fields:
            value = result.get(field)
            if not isinstance(value, str) or not value.strip():
                continue
            # Already an epoch number string?
            try:
                int(value)
                continue
            except ValueError:
                pass
            # Parse Java-style date: "Mon Aug 12 00:00:00 CST 2024"
            try:
                stripped = value.strip()
                # CST = China Standard Time (UTC+8)
                tz_offset = timedelta(hours=8)
                tz_match = re.search(r'\s+(CST|CTS)\s+', stripped)
                if tz_match:
                    stripped = stripped[:tz_match.start()] + " " + stripped[tz_match.end():]
                else:
                    cleaned = re.sub(r'\s+[A-Z]{2,4}\s+(\d{4})', r' \1', stripped)
                    tz_offset = timedelta(0)
                    stripped = cleaned
                for fmt in ("%a %b %d %H:%M:%S %Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                    try:
                        dt = datetime.strptime(stripped.strip(), fmt)
                        utc_dt = dt - tz_offset
                        epoch = int(utc_dt.timestamp())
                        result[field] = epoch
                        break
                    except ValueError:
                        continue
            except Exception:
                # If parsing fails, remove the field so pydantic uses default
                result.pop(field, None)
        return result

    @staticmethod
    def _build_vehicle_fallback(info: dict[str, Any], vin: str) -> Vehicle:
        """Build a Vehicle object manually when model_validate fails.

        This is a safety net for CN API responses that contain fields
        incompatible with the pydantic model (e.g. Java date strings).
        """
        return Vehicle(
            vin=info.get("vin", vin),
            model_name=info.get("modelName", info.get("model_name", "")),
            brand_name=info.get("brandName", info.get("brand_name", "")),
            auto_plate=info.get("autoPlate", info.get("auto_plate", "")),
            auto_alias=info.get("autoAlias", info.get("auto_alias", "")),
            auto_out_color=info.get("autoOutColor", info.get("auto_out_color", "")),
            energy_type=info.get("energyType", info.get("energy_type", "")),
            out_model_type=info.get("outModelType", info.get("out_model_type", "")),
            pic_main_url=info.get("picMainUrl", info.get("pic_main_url", "")),
            pic_set_url=info.get("picSetUrl", info.get("pic_set_url", "")),
            tbox_version=info.get("tboxVersion", info.get("tbox_version", "")),
            channel=info.get("channel", info.get("appChannel", None)),
        )

    @property
    def vehicle(self) -> Vehicle:
        """Return the Vehicle model for entity compatibility."""
        return self._vehicle

    @property
    def vehicle_info(self) -> dict[str, Any]:
        return self._vehicle_info

    @property
    def vin(self) -> str:
        return self._vin

    async def _async_update_data(self) -> VehicleSnapshot | None:
        """Fetch realtime telemetry data and build a VehicleSnapshot."""
        _LOGGER.debug("Telemetry refresh started: vin=%s", self._vin[-6:])
        force = self._force_next_refresh
        self._force_next_refresh = False

        if not self._polling_enabled and not force:
            return self.data

        try:
            client = await self._api._ensure_client()
            empower_type = self._vehicle_info.get("empowerType")
            empower_id = self._vehicle_info.get("empowerId")
            permission_status = self._vehicle_info.get("permissionStatus")
            is_shared = (
                empower_id is not None
                and str(empower_id).strip() != ""
            )
            self._is_shared = is_shared
            _LOGGER.debug(
                "Telemetry is_shared=%s (empowerType=%s, empowerId=%s, permissionStatus=%s)",
                is_shared, empower_type, empower_id, permission_status,
            )
            realtime_raw = await client.get_vehicle_realtime(self._vin, is_shared=is_shared)

            if self._api.debug_dumps_enabled:
                dump: dict[str, Any] = {"vin": self._vin, "realtime": realtime_raw}
                self.hass.async_create_task(
                    self._api.async_write_debug_dump("telemetry", dump)
                )

            # Parse raw dict into typed models for entity compatibility.
            try:
                realtime = VehicleRealtimeData.model_validate(realtime_raw) if isinstance(realtime_raw, dict) else None
            except Exception as exc:
                _LOGGER.warning("VehicleRealtimeData.model_validate failed: %s", exc)
                realtime = None

            hvac = None
            if isinstance(realtime_raw, dict):
                try:
                    hvac_extract = {}
                    ac_field_map = {
                        "acSwitch": "acSwitch",
                        "status": "status",
                        "mainSettingTemp": "mainSettingTemp",
                        "mainSettingTempNew": "mainSettingTempNew",
                        "copilotSettingTemp": "copilotSettingTemp",
                        "copilotSettingTempNew": "copilotSettingTempNew",
                        "tempInCar": "tempInCar",
                        "tempOutCar": "tempOutCar",
                        "windMode": "windMode",
                        "windPosition": "windPosition",
                        "cycleChoice": "cycleChoice",
                        "airRunState": "cycleChoice",
                        "timeChoice": "timeChoice",
                        "delayOffTime": "delayOffTime",
                        "mainSeatHeatState": "mainSeatHeatState",
                        "steeringWheelHeatState": "steeringWheelHeatState",
                    }
                    for src_key, dst_key in ac_field_map.items():
                        val = realtime_raw.get(src_key)
                        if val is not None:
                            hvac_extract[dst_key] = val
                    _LOGGER.debug("realtime fallback hvac_extract: %s", hvac_extract)
                    if hvac_extract:
                        ac_sw = hvac_extract.get("acSwitch")
                        st = hvac_extract.get("status")
                        if ac_sw is None and st is None:
                            has_temp = hvac_extract.get("mainSettingTemp") is not None
                            has_circ = hvac_extract.get("cycleChoice") is not None
                            if has_temp or has_circ:
                                hvac_extract.setdefault("acSwitch", 1)
                                hvac_extract.setdefault("status", 1)
                        hvac = HvacStatus.model_validate(hvac_extract)
                except Exception as exc:
                    _LOGGER.debug("HvacStatus from realtime fallback failed: %s", exc)

            if hvac is not None:
                _LOGGER.debug(
                    "HVAC: is_ac_on=%s, status=%s, acSwitch=%s, mainSettingTemp=%s, mainSettingTempNew=%s, raw_keys=%s",
                    hvac.is_ac_on, hvac.status, hvac.ac_switch, hvac.main_setting_temp, hvac.main_setting_temp_new,
                    list(hvac.raw.keys()) if isinstance(getattr(hvac, "raw", None), dict) else "no_raw",
                )
            else:
                _LOGGER.debug("HVAC: hvac is None after all attempts")

            historical_raw: dict[str, Any] = {}
            recent_raw: dict[str, Any] = {}
            auto_type = self._vehicle.out_model_type or "1"
            try:
                historical_raw = await client.get_historical_data_by_vin(self._vin, is_shared=is_shared, auto_type=auto_type)
                _LOGGER.debug("Historical energy data: %s", historical_raw)
            except Exception as exc:
                _LOGGER.warning("get_historical_data_by_vin failed: %s", exc)
            try:
                recent_raw = await client.get_recent_data_by_vin(self._vin, is_shared=is_shared, auto_type=auto_type)
                _LOGGER.debug("Recent energy data: %s", recent_raw)
            except Exception as exc:
                _LOGGER.warning("get_recent_data_by_vin failed: %s", exc)

            snapshot = VehicleSnapshot(
                vehicle=self._vehicle,
                realtime=realtime,
                hvac=hvac,
                is_shared=self._is_shared,
                historical_energy=historical_raw,
                recent_energy=recent_raw,
            )

            _LOGGER.debug(
                "Telemetry refresh succeeded: vin=%s",
                self._vin[-6:],
            )
            return snapshot
        except _AUTH_ERRORS:
            raise
        except _RECOVERABLE_ERRORS as exc:
            _LOGGER.warning("Telemetry fetch failed (keeping stale data): vin=%s, error=%s", self._vin[-6:], exc)
            return self.data

    # Polling control
    @property
    def polling_enabled(self) -> bool:
        return self._polling_enabled

    @property
    def poll_interval_seconds(self) -> int:
        return int(self._fixed_interval.total_seconds())

    def set_poll_interval(self, seconds: int) -> None:
        self._fixed_interval = timedelta(seconds=seconds)
        if self._polling_enabled:
            self.update_interval = self._fixed_interval
        self.async_update_listeners()

    def set_polling_enabled(self, enabled: bool) -> bool:
        was_enabled = self._polling_enabled
        self._polling_enabled = bool(enabled)
        self.update_interval = self._fixed_interval if self._polling_enabled else None
        return not was_enabled and self._polling_enabled

    async def async_set_polling_enabled(self, enabled: bool) -> None:
        if self.set_polling_enabled(enabled):
            await self.async_request_refresh()

    async def async_force_refresh(self) -> None:
        self._force_next_refresh = True
        await self.async_request_refresh()

    async def async_delayed_refresh(self, delay: float = 8.0) -> None:
        """Refresh after a delay to allow T-BOX to process command and update cloud state."""
        await asyncio.sleep(delay)
        self._force_next_refresh = True
        await self.async_request_refresh()

    async def async_refresh_hvac(self) -> None:
        """Fetch HVAC status via get_status_now and merge into current snapshot.

        Called only by climate entity after a command, not during regular polling.
        """
        try:
            client = await self._api._ensure_client()
            hvac_status_raw = await client.get_status_now(self._vin, is_shared=self._is_shared)
            _LOGGER.debug("get_status_now raw keys: %s", list(hvac_status_raw.keys()) if isinstance(hvac_status_raw, dict) else type(hvac_status_raw))
            hvac = None
            if isinstance(hvac_status_raw, dict) and hvac_status_raw:
                output_b64 = hvac_status_raw.get("outputBase64")
                if output_b64 and isinstance(output_b64, str):
                    # outputBase64 is base64-encoded JSON.  Decode it, then wrap
                    # the inner dict as "statusNow" so HvacStatus._unwrap_status_now
                    # extracts it (the field names use the same camelCase keys).
                    import base64
                    decoded_json = base64.b64decode(output_b64).decode("utf-8", errors="replace")
                    hvac_inner = {"statusNow": json.loads(decoded_json)} if decoded_json else {}
                else:
                    hvac_inner = hvac_status_raw
                _LOGGER.debug("get_status_now hvac_inner keys: %s", list(hvac_inner.get("statusNow", {}).keys()) if isinstance(hvac_inner.get("statusNow"), dict) else type(hvac_inner))
                if isinstance(hvac_inner, dict):
                    hvac = HvacStatus.model_validate(hvac_inner)
            if hvac is not None and self.data is not None:
                snapshot = VehicleSnapshot(
                    vehicle=self.data.vehicle,
                    realtime=self.data.realtime,
                    hvac=hvac,
                    is_shared=self._is_shared,
                )
                self.async_set_updated_data(snapshot)
                _LOGGER.debug("HVAC snapshot merged from get_status_now")
        except Exception as exc:
            _LOGGER.debug("async_refresh_hvac failed (non-critical): %s", exc)

    async def execute_control(self, command_type: str, control_params: dict | None = None, max_retries: int = 3) -> dict:
        client = await self._api._ensure_client()
        vin = self._vin
        if not self._pin_verified:
            await client.verify_command_access(vin, is_shared=self._is_shared)
            self._pin_verified = True
        await client.remote_awake(vin, is_shared=self._is_shared)
        for attempt in range(max_retries + 1):
            result = await client.remote_control(vin, command_type, control_params or {}, is_shared=self._is_shared)
            code = str(result.get("code", ""))
            if code == "6024" and attempt < max_retries:
                _LOGGER.warning("Control rate limited (6024), retrying in 5s... (attempt %d/%d)", attempt + 1, max_retries)
                await asyncio.sleep(5.0)
                continue
            if code not in ("0", "200"):
                raise UpdateFailed(f"Control command failed: code={code}, message={result.get('message', '')}")
            request_serial = result.get("respondData")
            if request_serial:
                for poll in range(10):
                    await asyncio.sleep(1.5)
                    poll_result = await client.remote_control_result(vin, request_serial, is_shared=self._is_shared)
                    rd = poll_result.get("respondData", {})
                    if isinstance(rd, dict):
                        state = rd.get("controlState")
                        if state == 1:
                            return rd
                        if state == 2:
                            raise UpdateFailed(f"Control failed: {rd}")
            return result
        raise UpdateFailed("Control command failed after max retries")


class BydGpsUpdateCoordinator(DataUpdateCoordinator[GpsInfo | None]):
    """Coordinator for GPS updates for a single VIN (CN single-request)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: BydApi,
        vin: str,
        poll_interval: int,
        vehicle_info: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_gps_{vin[-6:]}",
            update_interval=timedelta(seconds=poll_interval),
        )
        self._api = api
        self._vin = vin
        self._vehicle_info = vehicle_info or {}
        self._fixed_interval = timedelta(seconds=poll_interval)
        self._polling_enabled = True
        self._force_next_refresh = False

    @property
    def polling_enabled(self) -> bool:
        return self._polling_enabled

    @property
    def poll_interval_seconds(self) -> int:
        return int(self._fixed_interval.total_seconds())

    def set_poll_interval(self, seconds: int) -> None:
        self._fixed_interval = timedelta(seconds=seconds)
        if self._polling_enabled:
            self.update_interval = self._fixed_interval
        self.async_update_listeners()

    def set_polling_enabled(self, enabled: bool) -> bool:
        was_enabled = self._polling_enabled
        self._polling_enabled = bool(enabled)
        self.update_interval = self._fixed_interval if self._polling_enabled else None
        return not was_enabled and self._polling_enabled

    async def async_set_polling_enabled(self, enabled: bool) -> None:
        if self.set_polling_enabled(enabled):
            await self.async_request_refresh()

    async def async_force_refresh(self) -> None:
        self._force_next_refresh = True
        await self.async_request_refresh()

    async def _async_update_data(self) -> GpsInfo | None:
        """Fetch GPS data (CN single-request endpoint)."""
        _LOGGER.debug("GPS refresh started: vin=%s", self._vin[-6:])
        force = self._force_next_refresh
        self._force_next_refresh = False

        if not self._polling_enabled and not force:
            return self.data

        try:
            client = await self._api._ensure_client()
            empower_type = self._vehicle_info.get("empowerType")
            empower_id = self._vehicle_info.get("empowerId")
            permission_status = self._vehicle_info.get("permissionStatus")
            is_shared = (
                empower_id is not None
                and str(empower_id).strip() != ""
            )
            gps_raw = await client.get_gps(self._vin, is_shared=is_shared)

            if self._api.debug_dumps_enabled:
                dump: dict[str, Any] = {"vin": self._vin, "gps": gps_raw}
                self.hass.async_create_task(
                    self._api.async_write_debug_dump("gps", dump)
                )

            # Parse raw dict into GpsInfo model for entity compatibility.
            try:
                gps = GpsInfo.model_validate(gps_raw) if isinstance(gps_raw, dict) else None
            except Exception as exc:
                _LOGGER.warning("GpsInfo.model_validate failed: %s", exc)
                gps = None

            _LOGGER.debug(
                "GPS refresh succeeded: vin=%s",
                self._vin[-6:],
            )
            return gps
        except _AUTH_ERRORS:
            raise
        except _RECOVERABLE_ERRORS as exc:
            _LOGGER.warning("GPS fetch failed: vin=%s, error=%s", self._vin, exc)
            return self.data
