"""Smart charging status endpoint.

Endpoint:
  - /control/smartCharge/homePage
"""

from __future__ import annotations

from .._api._common import ENDPOINT_NOT_SUPPORTED_CODES, build_inner_base, post_token_json
from .._transport import Transport
from ..config import BydConfig
from ..models.charging import ChargingStatus
from ..session import Session

_ENDPOINT = "/control/smartCharge/homePage"


async def fetch_charging_status(
    config: BydConfig,
    session: Session,
    transport: Transport,
    vin: str,
) -> ChargingStatus:
    """Fetch smart charging status (SOC, charge state, time-to-full)."""
    inner = build_inner_base(config, vin=vin)
    decoded = await post_token_json(
        endpoint=_ENDPOINT,
        config=config,
        session=session,
        transport=transport,
        inner=inner,
        vin=vin,
        not_supported_codes=ENDPOINT_NOT_SUPPORTED_CODES,
    )
    return ChargingStatus.model_validate(decoded)
