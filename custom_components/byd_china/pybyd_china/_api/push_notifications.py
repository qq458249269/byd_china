"""Push notification endpoints.

Endpoints:
  - /app/push/getPushSwitchState  (get current state)
  - /app/push/setPushSwitchState  (toggle on/off)
"""

from __future__ import annotations

from .._api._common import ENDPOINT_NOT_SUPPORTED_CODES, build_inner_base, post_token_json
from .._transport import Transport
from ..config import BydConfig
from ..models.control import CommandAck
from ..models.push_notification import PushNotificationState
from ..session import Session

_GET_ENDPOINT = "/app/push/getPushSwitchState"
_SET_ENDPOINT = "/app/push/setPushSwitchState"


async def fetch_push_state(
    config: BydConfig,
    session: Session,
    transport: Transport,
    vin: str,
) -> PushNotificationState:
    """Fetch the current push notification state for a vehicle.

    Returns
    -------
    PushNotificationState
        Current push notification toggle state.
    """
    inner = build_inner_base(config, vin=vin)
    decoded = await post_token_json(
        endpoint=_GET_ENDPOINT,
        config=config,
        session=session,
        transport=transport,
        inner=inner,
        vin=vin,
        not_supported_codes=ENDPOINT_NOT_SUPPORTED_CODES,
    )
    raw = decoded if isinstance(decoded, dict) else {}
    return PushNotificationState.model_validate({"vin": vin, **raw})


async def set_push_state(
    config: BydConfig,
    session: Session,
    transport: Transport,
    vin: str,
    *,
    enable: bool,
) -> CommandAck:
    """Set the push notification state for a vehicle.

    Parameters
    ----------
    enable : bool
        True to enable push notifications, False to disable.

    Returns
    -------
    CommandAck
        Decoded API acknowledgement.
    """
    inner = build_inner_base(config, vin=vin)
    inner["pushSwitch"] = str(1 if enable else 0)
    decoded = await post_token_json(
        endpoint=_SET_ENDPOINT,
        config=config,
        session=session,
        transport=transport,
        inner=inner,
        vin=vin,
        not_supported_codes=ENDPOINT_NOT_SUPPORTED_CODES,
    )
    raw = decoded if isinstance(decoded, dict) else {}
    return CommandAck.model_validate({"vin": vin, **raw, "raw": raw})
