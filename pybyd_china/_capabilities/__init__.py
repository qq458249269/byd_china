"""Capability namespace classes for BydCar.

Each capability encapsulates a group of related vehicle commands with
their associated projection specifications.
"""

from .._capabilities.battery_heat import BatteryHeatCapability
from .._capabilities.finder import FinderCapability
from .._capabilities.hvac import HvacCapability
from .._capabilities.lock import LockCapability
from .._capabilities.seat import SeatCapability, SeatLevel, SeatPosition
from .._capabilities.steering import SteeringCapability
from .._capabilities.windows import WindowsCapability

__all__ = [
    "BatteryHeatCapability",
    "FinderCapability",
    "HvacCapability",
    "LockCapability",
    "SeatCapability",
    "SeatLevel",
    "SeatPosition",
    "SteeringCapability",
    "WindowsCapability",
]
