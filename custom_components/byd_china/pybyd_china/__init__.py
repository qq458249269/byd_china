"""pybyd_china - BYD China API client library with WBSK encryption."""

__version__ = "0.0.2"

from .client import BydClient
from .config import BydConfig, BydSession, DeviceProfile
from .exceptions import (
    BydApiError,
    BydAuthenticationError,
    BydControlPasswordError,
    BydDecryptionError,
    BydError,
    BydTransportError,
)
from ._state_engine import VehicleSnapshot
from .models.gps import GpsInfo
from .models.hvac import HvacStatus
from .models.realtime import VehicleRealtimeData
from .models.vehicle import Vehicle

__all__ = [
    "__version__",
    "BydApiError",
    "BydAuthenticationError",
    "BydClient",
    "BydConfig",
    "BydControlPasswordError",
    "BydDecryptionError",
    "BydError",
    "BydTransportError",
    "BydSession",
    "DeviceProfile",
    "GpsInfo",
    "HvacStatus",
    "Vehicle",
    "VehicleRealtimeData",
    "VehicleSnapshot",
]
