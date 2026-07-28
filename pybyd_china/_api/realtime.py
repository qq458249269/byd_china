"""Vehicle realtime data endpoints.

Endpoints:
  - /vehicleInfo/vehicle/vehicleRealTimeRequest  (trigger)
  - /vehicleInfo/vehicle/vehicleRealTimeResult    (poll)
"""

from __future__ import annotations

import time
from typing import Any

from .._api._common import ENDPOINT_NOT_SUPPORTED_CODES, build_inner_base, post_token_json
from .._transport import Transport
from ..config import BydConfig
from ..session import Session


async def fetch_realtime_endpoint(
    endpoint: str,
    config: BydConfig,
    session: Session,
    transport: Transport,
    vin: str,
    request_serial: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Fetch a single realtime endpoint, returning (vehicle_info_dict, next_serial)."""
    now_ms = int(time.time() * 1000)
    inner = build_inner_base(config, now_ms=now_ms, vin=vin, request_serial=request_serial)
    inner["energyType"] = "0"
    inner["tboxVersion"] = config.tbox_version

    decoded = await post_token_json(
        endpoint=endpoint,
        config=config,
        session=session,
        transport=transport,
        inner=inner,
        now_ms=now_ms,
        vin=vin,
        not_supported_codes=ENDPOINT_NOT_SUPPORTED_CODES,
    )
    vehicle_info: dict[str, Any] = decoded if isinstance(decoded, dict) else {}
    next_serial = vehicle_info.get("requestSerial") or request_serial

    return vehicle_info, next_serial
