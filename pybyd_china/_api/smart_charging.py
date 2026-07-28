"""Smart charging control endpoints.

Endpoints:
  - /control/smartCharge/changeChargeStatue  (toggle on/off)
  - /control/smartCharge/saveOrUpdate        (save schedule)
"""

from __future__ import annotations

from .._api._common import ENDPOINT_NOT_SUPPORTED_CODES, build_inner_base, post_token_json
from .._transport import Transport
from ..config import BydConfig
from ..models.control import CommandAck
from ..session import Session

_TOGGLE_ENDPOINT = "/control/smartCharge/changeChargeStatue"
_SAVE_ENDPOINT = "/control/smartCharge/saveOrUpdate"


async def toggle_smart_charging(
    config: BydConfig,
    session: Session,
    transport: Transport,
    vin: str,
    *,
    enable: bool,
) -> CommandAck:
    """Toggle smart charging on or off.

    Parameters
    ----------
    enable : bool
        True to enable smart charging, False to disable.

    Returns
    -------
    CommandAck
        Decoded API acknowledgement.
    """
    inner = build_inner_base(config, vin=vin)
    inner["smartChargeSwitch"] = str(1 if enable else 0)
    decoded = await post_token_json(
        endpoint=_TOGGLE_ENDPOINT,
        config=config,
        session=session,
        transport=transport,
        inner=inner,
        vin=vin,
        not_supported_codes=ENDPOINT_NOT_SUPPORTED_CODES,
    )
    raw = decoded if isinstance(decoded, dict) else {}
    return CommandAck.model_validate({"vin": vin, **raw, "raw": raw})


async def save_charging_schedule(
    config: BydConfig,
    session: Session,
    transport: Transport,
    vin: str,
    *,
    target_soc: int,
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
) -> CommandAck:
    """Save a smart charging schedule.

    Parameters
    ----------
    target_soc : int
        Target state of charge (0-100).
    start_hour : int
        Scheduled start hour (0-23).
    start_minute : int
        Scheduled start minute (0-59).
    end_hour : int
        Scheduled end hour (0-23).
    end_minute : int
        Scheduled end minute (0-59).

    Returns
    -------
    CommandAck
        Decoded API acknowledgement.
    """
    inner = build_inner_base(config, vin=vin)
    inner.update(
        {
            "endHour": str(end_hour),
            "endMinute": str(end_minute),
            "startHour": str(start_hour),
            "startMinute": str(start_minute),
            "targetSoc": str(target_soc),
        }
    )
    decoded = await post_token_json(
        endpoint=_SAVE_ENDPOINT,
        config=config,
        session=session,
        transport=transport,
        inner=inner,
        vin=vin,
        not_supported_codes=ENDPOINT_NOT_SUPPORTED_CODES,
    )
    raw = decoded if isinstance(decoded, dict) else {}
    return CommandAck.model_validate({"vin": vin, **raw, "raw": raw})
