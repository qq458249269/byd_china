"""Vehicle settings endpoints.

Endpoints:
  - /control/vehicle/modifyAutoAlias  (rename vehicle)
"""

from __future__ import annotations

from .._api._common import ENDPOINT_NOT_SUPPORTED_CODES, build_inner_base, post_token_json
from .._transport import Transport
from ..config import BydConfig
from ..models.control import CommandAck
from ..session import Session

_RENAME_ENDPOINT = "/control/vehicle/modifyAutoAlias"


async def rename_vehicle(
    config: BydConfig,
    session: Session,
    transport: Transport,
    vin: str,
    *,
    name: str,
) -> CommandAck:
    """Rename a vehicle (set its alias).

    Parameters
    ----------
    name : str
        New display name for the vehicle.

    Returns
    -------
    CommandAck
        Decoded API acknowledgement.
    """
    inner = build_inner_base(config, vin=vin)
    inner["autoAlias"] = name
    decoded = await post_token_json(
        endpoint=_RENAME_ENDPOINT,
        config=config,
        session=session,
        transport=transport,
        inner=inner,
        vin=vin,
        not_supported_codes=ENDPOINT_NOT_SUPPORTED_CODES,
    )
    raw = decoded if isinstance(decoded, dict) else {}
    return CommandAck.model_validate({"vin": vin, **raw, "raw": raw})
