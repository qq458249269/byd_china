"""Vehicle capability config endpoint.

Endpoint:
  - /vehicle/vehicleswitch/getLatestConfig
"""

from __future__ import annotations

import json

from .._api._common import build_inner_base, post_token_json
from .._transport import Transport
from ..config import BydConfig
from ..models.latest_config import VehicleLatestConfig
from ..session import Session

_ENDPOINT = "/vehicle/vehicleswitch/getLatestConfig"


async def fetch_latest_config(
    config: BydConfig,
    session: Session,
    transport: Transport,
    vin_list: list[str],
) -> dict[str, VehicleLatestConfig]:
    """Fetch latest per-VIN capability configuration."""
    inner = build_inner_base(config)
    inner["appConfigVersion"] = "2"
    inner["terminalType"] = "0"
    inner["vinList"] = json.dumps(vin_list, ensure_ascii=False)

    decoded = await post_token_json(
        endpoint=_ENDPOINT,
        config=config,
        session=session,
        transport=transport,
        inner=inner,
    )
    payload = decoded if isinstance(decoded, dict) else {}

    parsed: dict[str, VehicleLatestConfig] = {}
    for vin, raw in payload.items():
        if not isinstance(vin, str) or not isinstance(raw, dict):
            continue
        parsed[vin] = VehicleLatestConfig.model_validate(raw)

    return parsed
