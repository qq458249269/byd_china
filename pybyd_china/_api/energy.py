"""Energy consumption endpoint.

Endpoint:
  - /vehicleInfo/vehicle/getEnergyConsumption (single request)
"""

from __future__ import annotations

from .._api._common import ENDPOINT_NOT_SUPPORTED_CODES, build_inner_base, post_token_json
from .._transport import Transport
from ..config import BydConfig
from ..models.energy import EnergyConsumption
from ..session import Session

_ENDPOINT = "/vehicleInfo/vehicle/getEnergyConsumption"


async def fetch_energy_consumption(
    config: BydConfig,
    session: Session,
    transport: Transport,
    vin: str,
) -> EnergyConsumption:
    """Fetch energy consumption data for a vehicle.

    Parameters
    ----------
    config : BydConfig
        Client configuration.
    session : Session
        Authenticated session.
    transport : Transport
        HTTP transport.
    vin : str
        Vehicle Identification Number.

    Returns
    -------
    EnergyConsumption
        Energy consumption data.

    Raises
    ------
    BydApiError
        If the API returns an error.
    """
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
    return EnergyConsumption.model_validate(decoded)
