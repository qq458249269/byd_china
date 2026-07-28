"""BYD China API client with WBSK encryption.

Implements login, vehicle list, realtime data, GPS, MQTT broker,
and remote control commands for the CN BYD app.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

import aiohttp

from .config import (
    BydConfig,
    BydSession,
    DeviceProfile,
    CN_BROKER_FIELDS,
    CN_MQTT_PREFIXES,
)
from .crypto import (
    aes_decrypt_utf8,
    aes_encrypt_hex,
    build_sign_string,
    compute_cn_checkcode,
    md5_hex,
    pwd_login_key,
    random_hex16,
    sha1_mixed,
)
from .exceptions import (
    BydApiError,
    BydAuthenticationError,
    BydDecryptionError,
    BydTransportError,
)
from .wbsk import decrypt_envelope, encrypt_envelope

_LOGGER = logging.getLogger(__name__)

USER_AGENT = "okhttp/4.12.0"


class BydClient:
    """Async BYD China API client."""

    def __init__(
        self,
        config: BydConfig,
        device_profile: DeviceProfile,
        session: aiohttp.ClientSession | None = None,
        on_mqtt_event: Callable | None = None,
        on_command_ack: Callable | None = None,
        on_command_lifecycle: Callable | None = None,
    ) -> None:
        self._config = config
        self._device = device_profile
        self._session_external = session
        self._session_internal: aiohttp.ClientSession | None = None
        self._session_data = BydSession()
        self._cookie_jar: dict[str, str] = {}
        self._on_mqtt_event = on_mqtt_event
        self._on_command_ack = on_command_ack
        self._on_command_lifecycle = on_command_lifecycle
        # If an external session is provided, use it immediately without
        # requiring async with. This allows HA's coordinator to create a
        # client and call methods directly.
        if session:
            self._session_internal = session
        else:
            self._session_internal = None

    @property
    def session_data(self) -> BydSession:
        return self._session_data

    @property
    def config(self) -> BydConfig:
        return self._config

    async def __aenter__(self) -> BydClient:
        if self._session_external:
            self._session_internal = self._session_external
        else:
            self._session_internal = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if not self._session_external and self._session_internal:
            await self._session_internal.close()
            self._session_internal = None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session_internal is None:
            raise RuntimeError("Client not initialized. Use async with.")
        return self._session_internal

    # -----------------------------------------------------------------------
    # Cookie management
    # -----------------------------------------------------------------------

    def _update_cookies(self, headers: dict) -> None:
        """Extract set-cookie headers and store in jar."""
        # aiohttp handles cookies via cookie_jar on the session
        pass  # aiohttp's CookieJar handles this automatically

    # -----------------------------------------------------------------------
    # HTTP request with WBSK encryption
    # -----------------------------------------------------------------------

    async def _post_secure(self, endpoint: str, outer_payload: dict[str, Any]) -> dict[str, Any]:
        """Send an encrypted POST request and decrypt the response."""
        session = self._get_session()

        headers = {
            "accept-encoding": "identity",
            "content-type": "application/json; charset=UTF-8",
            "user-agent": USER_AGENT,
            # CN-specific headers
            "version": self._config.cn_app_inner_version,
            "softType": self._config.soft_type,
            "platform": "ANDROID",
            "BrandFlag": "dynasty",
        }

        # Add CN device fields and checkcode before encryption
        self._add_cn_device_fields(outer_payload)

        # Encrypt outer payload with WBSK
        request_payload = encrypt_envelope(json.dumps(outer_payload, separators=(",", ":"), ensure_ascii=False))

        url = f"{self._config.base_url}{endpoint}"
        _LOGGER.debug("POST %s", url)

        try:
            async with session.post(
                url,
                headers=headers,
                json={"request": request_payload},
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise BydTransportError(f"HTTP {response.status} {endpoint}: {text[:200]}")

                body = await response.json(content_type=None)
        except aiohttp.ClientError as err:
            raise BydTransportError(f"Request failed for {endpoint}: {err}") from err

        if not body or "response" not in body:
            raise BydTransportError(f"Missing response payload for {endpoint}")

        # Decrypt response with WBSK
        try:
            decoded_text = decrypt_envelope(body["response"])
            return json.loads(decoded_text)
        except (ValueError, json.JSONDecodeError) as err:
            raise BydDecryptionError(f"Failed to decrypt response from {endpoint}: {err}") from err

    # -----------------------------------------------------------------------
    # Login
    # -----------------------------------------------------------------------

    async def login(self) -> None:
        """Authenticate with BYD China API."""
        now_ms = int(time.time() * 1000)
        req_timestamp = str(now_ms)
        login_key = pwd_login_key(self._config.password)

        # Inner payload
        inner: dict[str, Any] = {
            "appInnerVersion": self._config.cn_app_inner_version,
            "appVersion": self._config.cn_app_version,
            "bluetoothMac": "",
            "city": "",
            "configVersion": "10000",
            "deviceType": self._config.device_type,
            "devicename": f"{self._device.mobile_brand}{self._device.mobile_model}",
            "imeiMD5": self._device.imei_md5,
            "isAuto": "0",
            "latitude": "",
            "longitude": "",
            "mobileBrand": self._device.mobile_brand,
            "mobileModel": self._device.mobile_model,
            "networkOperator": self._config.network_operator,
            "networkType": self._device.network_type,
            "osType": "Android",
            "osVersion": self._device.os_version,
            "random": random_hex16(),
            "softType": self._config.soft_type,
            "timeStamp": req_timestamp,
        }

        encry_data = aes_encrypt_hex(json.dumps(inner, separators=(",", ":"), ensure_ascii=False), login_key)

        # Sign
        sign_fields = {
            **inner,
            "appChannel": self._config.app_channel,
            "identifier": self._config.username,
            "loginType": 0,
            "reqTimestamp": req_timestamp,
            "targetBrand": self._config.target_brand,
        }
        sign = sha1_mixed(build_sign_string(sign_fields, md5_hex(self._config.password)))

        # Outer payload
        outer: dict[str, Any] = {
            "appChannel": self._config.app_channel,
            "encryData": encry_data,
            "identifier": self._config.username,
            "imeiMD5": self._device.imei_md5,
            "isAuto": "0",
            "loginType": 0,
            "reqTimestamp": req_timestamp,
            "sign": sign,
            "targetBrand": self._config.target_brand,
        }

        # Add CN device fields and checkcode
        self._add_cn_device_fields(outer)

        # Send request
        decoded = await self._post_secure("/app/auth/login", outer)

        if str(decoded.get("code", "")) != "0":
            msg = decoded.get("message", "Unknown error")
            if "password" in msg.lower() or "auth" in msg.lower():
                raise BydAuthenticationError(f"Login failed: {msg}")
            raise BydApiError(f"Login failed: code={decoded.get('code')} message={msg}", code=str(decoded.get("code", "")))

        # Decrypt respondData
        respond_data = self._decrypt_respond_data(decoded.get("respondData", ""), login_key)

        # Extract session data from token object (CN: superId/userId are inside token)
        token = respond_data.get("token", {})
        if not token:
            # Fallback: some responses may put fields at top level
            token = respond_data

        super_id = str(token.get("superId", ""))
        encry_token = str(token.get("encryToken", token.get("encryptToken", "")))
        sign_token = str(token.get("signToken", ""))

        # Extract brand-specific userId from superBindRelationDtoMap (inside token)
        bind_map = token.get("superBindRelationDtoMap", {})
        brand_user_id = ""
        if bind_map and self._config.target_brand in bind_map:
            brand_info = bind_map[self._config.target_brand]
            if isinstance(brand_info, dict) and "userId" in brand_info:
                brand_user_id = str(brand_info["userId"])

        # userId: brand-specific userId > superId
        user_id = brand_user_id or super_id

        if not user_id or not sign_token or not encry_token:
            raise BydAuthenticationError(
                f"Login response missing token fields: "
                f"userId={'✓' if user_id else '✗'}, "
                f"signToken={'✓' if sign_token else '✗'}, "
                f"encryToken={'✓' if encry_token else '✗'}"
            )

        self._session_data = BydSession(
            super_id=super_id,
            user_id=user_id,
            encrypt_token=encry_token,
            sign_token=sign_token,
        )
        self._session_data.content_key = md5_hex(self._session_data.encrypt_token)
        self._session_data.sign_key = md5_hex(self._session_data.sign_token)

        _LOGGER.info("Login successful, superId=%s", self._session_data.super_id)

    # -----------------------------------------------------------------------
    # Vehicle list
    # -----------------------------------------------------------------------

    async def get_vehicles(self) -> list[dict[str, Any]]:
        """Get list of vehicles for the authenticated user."""
        now_ms = int(time.time() * 1000)
        inner = {"appUiName": "", **self._build_inner(now_ms)}

        req = self._build_token_outer_envelope(now_ms, inner)
        decoded = await self._post_secure("/app/auth/getAllListByUserId", req["outer"])

        if str(decoded.get("code", "")) != "0":
            raise BydApiError(f"Vehicle list failed: code={decoded.get('code')} message={decoded.get('message', '')}")

        raw = self._decrypt_respond_data(decoded.get("respondData", ""), req["content_key"])

        # CN response wraps list in diLinkAutoInfoList
        if isinstance(raw, dict) and "diLinkAutoInfoList" in raw:
            vehicles = raw["diLinkAutoInfoList"]
        elif isinstance(raw, list):
            vehicles = raw
        else:
            vehicles = []

        return [v for v in vehicles if v and v.get("vin")]

    # -----------------------------------------------------------------------
    # Realtime data (CN: request + result polling)
    # -----------------------------------------------------------------------

    _REALTIME_POLL_ATTEMPTS = 10
    _REALTIME_POLL_INTERVAL = 1.5  # seconds

    @staticmethod
    def _is_realtime_data_ready(vehicle_info: dict[str, Any] | None) -> bool:
        """Check if realtime data contains meaningful values."""
        if not vehicle_info or not isinstance(vehicle_info, dict):
            return False
        # onlineState === 2 means offline, data not usable
        if int(vehicle_info.get("onlineState", 0)) == 2:
            return False
        # Has tire pressure data?
        tire_fields = [
            "leftFrontTirepressure", "rightFrontTirepressure",
            "leftRearTirepressure", "rightRearTirepressure",
        ]
        if any(float(vehicle_info.get(f, 0)) > 0 for f in tire_fields):
            return True
        # Has timestamp?
        if int(vehicle_info.get("time", 0)) > 0:
            return True
        # Has endurance mileage?
        if float(vehicle_info.get("enduranceMileage", 0)) > 0:
            return True
        return False

    async def _fetch_vehicle_realtime(
        self, endpoint: str, vin: str, request_serial: str | None = None, *, is_shared: bool = False,
    ) -> tuple[dict[str, Any], str | None]:
        """Send a single realtime request and return (vehicleInfo, requestSerial)."""
        now_ms = int(time.time() * 1000)
        inner = self._build_inner(now_ms)
        inner["energyType"] = "0"
        inner["tboxVersion"] = self._config.tbox_version
        inner["vin"] = vin
        if request_serial:
            inner["requestSerial"] = request_serial

        # Xposed log confirmed: authorized accounts use identifierType=1, owner uses 0
        # userType is NOT sent in the outer envelope (not present in real traffic)
        id_type_override = 1 if is_shared else None
        user_type = None
        req = self._build_token_outer_envelope(now_ms, inner, user_type=user_type, identifier_type=id_type_override)
        decoded = await self._post_secure(endpoint, req["outer"])

        if str(decoded.get("code", "")) != "0":
            raise BydApiError(
                f"{endpoint} failed: code={decoded.get('code')} "
                f"message={decoded.get('message', '')}"
            )

        vehicle_info = self._decrypt_respond_data(
            decoded.get("respondData", ""), req["content_key"]
        )
        next_serial = (
            vehicle_info.get("requestSerial") if isinstance(vehicle_info, dict) else None
        )
        if not isinstance(next_serial, str):
            next_serial = request_serial
        return vehicle_info, next_serial

    async def get_vehicle_realtime(self, vin: str, *, is_shared: bool = False) -> dict[str, Any]:
        """Get realtime vehicle telemetry (CN: request + result polling).

        The CN API requires two steps:
        1. POST /vehicleInfo/vehicle/vehicleRealTimeRequest (no requestSerial)
           → returns initial data + requestSerial
        2. POST /vehicleInfo/vehicle/vehicleRealTimeResult (with requestSerial)
           → returns actual telemetry data

        Step 2 is repeated up to 10 times with 1.5s interval until
        meaningful data is received.
        """
        _LOGGER.debug("get_vehicle_realtime: vin=%s, is_shared=%s", vin[-6:], is_shared)
        try:
            vehicle_info, serial = await self._fetch_vehicle_realtime(
                "/vehicleInfo/vehicle/vehicleRealTimeRequest", vin, is_shared=is_shared,
            )
        except BydApiError:
            raise
        except Exception as exc:
            raise BydApiError(f"Realtime request failed: {exc}") from exc

        if self._is_realtime_data_ready(vehicle_info):
            _LOGGER.debug("Realtime data ready from initial request")
            return vehicle_info

        if not serial:
            _LOGGER.debug("No requestSerial returned, cannot poll for result")
            return vehicle_info

        import asyncio

        for attempt in range(1, self._REALTIME_POLL_ATTEMPTS + 1):
            await asyncio.sleep(self._REALTIME_POLL_INTERVAL)
            try:
                vehicle_info, serial = await self._fetch_vehicle_realtime(
                    "/vehicleInfo/vehicle/vehicleRealTimeResult", vin, serial, is_shared=is_shared,
                )
                _LOGGER.debug(
                    "Realtime result poll attempt %d: time=%s, elecPercent=%s",
                    attempt,
                    vehicle_info.get("time"),
                    vehicle_info.get("elecPercent"),
                )
                if self._is_realtime_data_ready(vehicle_info):
                    _LOGGER.debug("Realtime data ready after %d poll attempts", attempt)
                    return vehicle_info
            except BydApiError as exc:
                _LOGGER.debug("Realtime result poll attempt %d failed: %s", attempt, exc)
            except Exception as exc:
                _LOGGER.debug("Realtime result poll attempt %d error: %s", attempt, exc)

        _LOGGER.debug("Realtime polling exhausted after %d attempts", self._REALTIME_POLL_ATTEMPTS)
        return vehicle_info

    # -----------------------------------------------------------------------
    # GPS (CN: single request, no polling)
    # -----------------------------------------------------------------------

    async def get_gps(self, vin: str, *, is_shared: bool = False) -> dict[str, Any]:
        """Get GPS location (CN single-request endpoint).

        The CN GPS response wraps the actual GPS data in a 'gpsInfo' sub-object:
        {"ok": true, "code": "0", "message": "SUCCESS", "gpsInfo": {...}}
        We extract and return the gpsInfo dict for entity compatibility.
        """
        now_ms = int(time.time() * 1000)
        inner = self._build_inner(now_ms)
        inner["vin"] = vin

        user_type = None
        id_type_override = 1 if is_shared else None
        req = self._build_token_outer_envelope(now_ms, inner, user_type=user_type, identifier_type=id_type_override)
        decoded = await self._post_secure("/vehicleInfo/gps/locationRequestService", req["outer"])

        if str(decoded.get("code", "")) != "0":
            raise BydApiError(f"GPS request failed: code={decoded.get('code')} message={decoded.get('message', '')}")

        data = self._decrypt_respond_data(decoded.get("respondData", ""), req["content_key"])

        if isinstance(data, dict) and "gpsInfo" in data:
            gps_info = data["gpsInfo"]
            if isinstance(gps_info, dict):
                return gps_info

        return data

    # -----------------------------------------------------------------------
    # MQTT broker
    # -----------------------------------------------------------------------

    async def get_emq_broker(self) -> str:
        """Get MQTT broker hostname."""
        now_ms = int(time.time() * 1000)
        inner = self._build_inner(now_ms)
        inner["version"] = self._config.cn_app_inner_version

        req = self._build_token_outer_envelope(now_ms, inner)
        decoded = await self._post_secure("/app/emqAuth/getEmqBrokerIp", req["outer"])

        if str(decoded.get("code", "")) != "0":
            raise BydApiError(f"Broker lookup failed: code={decoded.get('code')} message={decoded.get('message', '')}")

        data = self._decrypt_respond_data(decoded.get("respondData", ""), req["content_key"])

        broker_field = CN_BROKER_FIELDS.get(self._config.target_brand, "dynastyEmqBroker")
        broker = str(data.get(broker_field, "")) if data else ""

        if not broker:
            raise BydApiError(f"Broker lookup response missing broker (brand={self._config.target_brand})")

        return broker

    def get_mqtt_params(self) -> dict[str, str]:
        """Build MQTT connection parameters."""
        prefix = CN_MQTT_PREFIXES.get(self._config.target_brand, "dynasty")
        client_id = f"{prefix}_{self._device.imei_md5.upper()}"
        ts_seconds = str(int(time.time()))
        uid = self._session_data.super_id or self._session_data.user_id
        base = f"{self._session_data.sign_token}{client_id}{uid}{ts_seconds}"
        password = f"{ts_seconds}{md5_hex(base)}"
        topic = f"/{prefix}/res/{uid}"

        return {
            "client_id": client_id,
            "username": uid,
            "password": password,
            "topic": topic,
        }

    # -----------------------------------------------------------------------
    # Verify control password
    # -----------------------------------------------------------------------

    async def verify_command_access(self, vin: str, *, is_shared: bool = False) -> None:
        """Verify the control PIN for remote commands."""
        if not self._config.control_pin:
            return

        now_ms = int(time.time() * 1000)
        command_pwd = md5_hex(self._config.control_pin)

        inner: dict[str, Any] = {
            "commandPwd": command_pwd,
            "deviceType": self._config.device_type,
            "functionType": "remoteControl",
            "imeiMD5": self._device.imei_md5,
            "networkType": self._device.network_type,
            "random": random_hex16(),
            "timeStamp": str(now_ms),
            "version": self._config.cn_app_inner_version,
            "vin": vin,
        }

        user_type = None
        id_type_override = 1 if is_shared else None
        req = self._build_token_outer_envelope(now_ms, inner, user_type=user_type, identifier_type=id_type_override)
        decoded = await self._post_secure("/vehicle/vehicleswitch/verifyControlPassword", req["outer"])

        if str(decoded.get("code", "")) != "0":
            from .exceptions import BydControlPasswordError
            raise BydControlPasswordError(f"Control PIN verification failed: code={decoded.get('code')} message={decoded.get('message', '')}")

    # -----------------------------------------------------------------------
    # Remote control
    # -----------------------------------------------------------------------

    async def remote_awake(self, vin: str, *, is_shared: bool = False) -> dict[str, Any]:
        """Send remote awake command."""
        now_ms = int(time.time() * 1000)
        inner = {
            **self._build_inner(now_ms),
            "vin": vin,
        }

        user_type = None
        id_type_override = 1 if is_shared else None
        req = self._build_token_outer_envelope(now_ms, inner, user_type=user_type, identifier_type=id_type_override)
        decoded = await self._post_secure("/control/rc/remoteAwakeRequest", req["outer"])

        data = self._decrypt_respond_data(decoded.get("respondData", ""), req["content_key"])
        return data if isinstance(data, dict) else {}

    async def remote_control(self, vin: str, command_type: str, control_params: dict[str, Any] | None = None, *, is_shared: bool = False) -> dict[str, Any]:
        """Send a remote control command."""
        now_ms = int(time.time() * 1000)
        command_pwd = md5_hex(self._config.control_pin) if self._config.control_pin else ""

        inner = {
            **self._build_inner(now_ms),
            "vin": vin,
            "autoType": "1",
            "commandType": command_type,
            "controlParamsMap": json.dumps(control_params or {}, separators=(",", ":")),
            "commandPwd": command_pwd,
            "asyncControl": "0",
            "requestSerial": str(now_ms % 10000),
            "source": "app",
            "tboxVersion": self._config.tbox_version,
        }

        user_type = None
        id_type_override = 1 if is_shared else None
        req = self._build_token_outer_envelope(now_ms, inner, user_type=user_type, identifier_type=id_type_override)
        decoded = await self._post_secure("/control/rc/remoteControl", req["outer"])

        data = self._decrypt_respond_data(decoded.get("respondData", ""), req["content_key"])
        if isinstance(data, dict):
            if "code" not in data:
                data["code"] = decoded.get("code", "")
            return data
        if isinstance(data, str) and data:
            return {"code": decoded.get("code", ""), "respondData": data}
        return {"code": decoded.get("code", ""), "message": decoded.get("message", ""), "respondData": None}

    async def get_status_now(self, vin: str, *, is_shared: bool = False) -> dict[str, Any]:
        """Get current A/C status via getStatusNow endpoint.

        Response contains outputBase64 which is base64-encoded JSON with
        fields like mainSeatType, cycleChoice, mainSettingTemp, etc.
        """
        now_ms = int(time.time() * 1000)
        inner = {
            **self._build_inner(now_ms),
            "vin": vin,
        }

        user_type = None
        id_type_override = 1 if is_shared else None
        req = self._build_token_outer_envelope(now_ms, inner, user_type=user_type, identifier_type=id_type_override)
        decoded = await self._post_secure("/control/rc/getStatusNow", req["outer"])

        data = self._decrypt_respond_data(decoded.get("respondData", ""), req["content_key"])
        return data if isinstance(data, dict) else {}

    async def get_historical_data_by_vin(self, vin: str, *, is_shared: bool = False, auto_type: str = "1") -> dict[str, Any]:
        """Get recent 50km energy consumption detail (selfList with per-day data)."""
        now_ms = int(time.time() * 1000)
        inner = {
            **self._build_inner(now_ms),
            "vin": vin,
            "tboxVersion": self._config.tbox_version,
            "autoType": auto_type,
        }
        user_type = None
        id_type_override = 1 if is_shared else None
        req = self._build_token_outer_envelope(now_ms, inner, user_type=user_type, identifier_type=id_type_override)
        decoded = await self._post_secure("/vehicleInfo/vehicle/getHistoricalDataByVin", req["outer"])
        if str(decoded.get("code", "")) != "0":
            _LOGGER.warning(
                "getHistoricalDataByVin failed: code=%s message=%s",
                decoded.get("code"), decoded.get("message", ""),
            )
            return {}
        resp = decoded.get("respondData", "")
        if isinstance(resp, dict):
            return resp
        data = self._decrypt_respond_data(resp, req["content_key"])
        return data if isinstance(data, dict) else {}

    async def get_recent_data_by_vin(self, vin: str, *, is_shared: bool = False, auto_type: str = "1") -> dict[str, Any]:
        """Get cumulative energy consumption (avgFullCon, avgEvCon, avgOilCon, etc.).

        Xposed log confirmed: inner payload requires "type": "NEAREST_KM"
        and does NOT include energyType.
        """
        now_ms = int(time.time() * 1000)
        inner = {
            **self._build_inner(now_ms),
            "vin": vin,
            "tboxVersion": self._config.tbox_version,
            "autoType": auto_type,
            "type": "NEAREST_KM",
        }
        user_type = None
        id_type_override = 1 if is_shared else None
        req = self._build_token_outer_envelope(now_ms, inner, user_type=user_type, identifier_type=id_type_override)
        decoded = await self._post_secure("/vehicleInfo/vehicle/getRecentDataByVin", req["outer"])
        if str(decoded.get("code", "")) != "0":
            _LOGGER.warning(
                "getRecentDataByVin failed: code=%s message=%s",
                decoded.get("code"), decoded.get("message", ""),
            )
            return {}
        resp = decoded.get("respondData", "")
        if isinstance(resp, dict):
            return resp
        data = self._decrypt_respond_data(resp, req["content_key"])
        return data if isinstance(data, dict) else {}

    async def remote_control_result(self, vin: str, request_serial: str, *, is_shared: bool = False) -> dict[str, Any]:
        """Poll for remote control result."""
        now_ms = int(time.time() * 1000)
        inner = {
            **self._build_inner(now_ms),
            "vin": vin,
            "requestSerial": request_serial,
            "source": "app",
            "tboxVersion": self._config.tbox_version,
        }

        user_type = None
        id_type_override = 1 if is_shared else None
        req = self._build_token_outer_envelope(now_ms, inner, user_type=user_type, identifier_type=id_type_override)
        decoded = await self._post_secure("/control/rc/remoteControlResult", req["outer"])

        data = self._decrypt_respond_data(decoded.get("respondData", ""), req["content_key"])
        return data if isinstance(data, dict) else {}

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _build_inner(self, now_ms: int) -> dict[str, Any]:
        """Build common inner payload fields for CN mode.

        Xposed log confirmed: osVersion uses os_version ('16'), not sdk ('35').
        mobileModel is just the model code (e.g. '2304FPN6DC'), not brand+model.
        """
        return {
            "deviceName": f"{self._device.mobile_brand}{self._device.mobile_model}",
            "deviceType": self._config.device_type,
            "imeiMD5": self._device.imei_md5,
            "mobileBrand": self._device.mobile_brand,
            "mobileModel": self._device.mobile_model,
            "networkOperator": self._config.network_operator,
            "networkType": self._device.network_type,
            "osType": "Android",
            "osVersion": self._device.os_version,
            "random": random_hex16(),
            "softType": self._config.soft_type,
            "timeStamp": str(now_ms),
            "version": self._config.cn_app_inner_version,
        }

    def _build_token_outer_envelope(self, now_ms: int, inner: dict[str, Any], *, user_type: str | None = None, identifier_type: int | None = None) -> dict[str, Any]:
        """Build outer payload with token-derived keys.

        Parameters
        ----------
        user_type : str | None
            If provided, added as "userType" to the outer envelope.
            Xposed log shows this field is NOT sent in real traffic (always None).
        identifier_type : int | None
            If provided, overrides the default identifierType calculation.
            Xposed log confirmed: authorized accounts use 1, owner uses 0.
        """
        req_timestamp = str(now_ms)
        content_key = self._session_data.content_key
        sign_key = self._session_data.sign_key

        encry_data = aes_encrypt_hex(json.dumps(inner, separators=(",", ":"), ensure_ascii=False), content_key)

        if identifier_type is not None:
            id_type = identifier_type
        else:
            id_type = 0 if inner.get("vin") else 2
        identifier = self._session_data.super_id or self._session_data.user_id
        _LOGGER.debug(
            "Building envelope: identifier=%s, identifierType=%s (user_id=%s, super_id=%s)",
            identifier, id_type, self._session_data.user_id, self._session_data.super_id,
        )

        # Sign fields
        sign_fields = {
            **inner,
            "appChannel": self._config.app_channel,
            "identifier": identifier,
            "identifierType": id_type,
            "imeiMD5": self._device.imei_md5,
            "reqTimestamp": req_timestamp,
            "targetBrand": self._config.target_brand,
            "vehicleBrand": self._config.target_brand,
        }
        if inner.get("vin"):
            sign_fields["objective"] = inner["vin"]

        sign = sha1_mixed(build_sign_string(sign_fields, sign_key))

        outer: dict[str, Any] = {
            "appChannel": self._config.app_channel,
            "encryData": encry_data,
            "identifier": identifier,
            "identifierType": id_type,
            "imeiMD5": self._device.imei_md5,
            "objective": inner.get("vin") or None,
            "outModelTypes": None,
            "reqTimestamp": req_timestamp,
            "sign": sign,
            "softType": None,
            "targetBrand": self._config.target_brand,
            "vehicleBrand": self._config.target_brand,
            "version": None,
        }

        # CN device fields and checkcode are added in _post_secure before encryption
        if user_type is not None:
            outer["userType"] = user_type
            _LOGGER.debug("Envelope userType=%s", user_type)
        return {"outer": outer, "content_key": content_key}

    def _add_cn_device_fields(self, payload: dict[str, Any]) -> None:
        """Add CN-specific device fields and compute checkcode."""
        payload["ostype"] = self._device.ostype
        payload["imei"] = self._device.imei
        payload["mac"] = self._device.mac
        payload["model"] = self._device.model
        payload["sdk"] = self._device.sdk
        payload["serviceTime"] = str(int(time.time() * 1000))
        payload["mod"] = self._device.mod
        payload["checkcode"] = compute_cn_checkcode(payload)

    def _decrypt_respond_data(self, respond_data_hex: str, key_hex: str) -> dict[str, Any] | str:
        """Decrypt AES-128-CBC respondData and parse as JSON or return as string."""
        if not respond_data_hex:
            return {}
        try:
            plain = aes_decrypt_utf8(respond_data_hex, key_hex)
            try:
                return json.loads(plain)
            except json.JSONDecodeError:
                return plain
        except (ValueError, json.JSONDecodeError) as err:
            _LOGGER.warning("Failed to decrypt respondData: %s", err)
            return {}
