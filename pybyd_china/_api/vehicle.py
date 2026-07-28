"""Vehicle list endpoint.

Endpoint:
  - /app/account/getAllListByUserId
"""

from __future__ import annotations

from .._api._common import build_inner_base, post_token_json
from .._transport import Transport
from ..config import BydConfig
from ..models.vehicle import Vehicle
from ..session import Session

_ENDPOINT = "/app/account/getAllListByUserId"


async def fetch_vehicle_list(
    config: BydConfig,
    session: Session,
    transport: Transport,
) -> list[Vehicle]:
    """Fetch all vehicles associated with the authenticated user."""
    inner = build_inner_base(config)
    decoded = await post_token_json(
        endpoint=_ENDPOINT,
        config=config,
        session=session,
        transport=transport,
        inner=inner,
    )
    items = decoded if isinstance(decoded, list) else []
    return [Vehicle.model_validate(item) for item in items]
