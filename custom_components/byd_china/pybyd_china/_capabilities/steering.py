"""Steering wheel heating capability."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._state_engine import ProjectionSpec, VehicleSnapshot
from ..exceptions import BydEndpointNotSupportedError
from ..models.control import SeatClimateParams
from ..models.hvac import HvacOverallStatus
from ..models.realtime import StearingWheelHeat

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class SteeringCapability:
    """Steering wheel heating command with projection support."""

    def __init__(
        self,
        *,
        set_seat_climate_fn: Callable[..., Awaitable[Any]],
        vin: str,
        get_state: Callable[[], VehicleSnapshot],
        execute_command: Callable[..., Awaitable[None]],
        available: bool | None = True,
    ) -> None:
        self._set_seat_climate_fn = set_seat_climate_fn
        self._vin = vin
        self._get_state = get_state
        self._execute = execute_command
        self._available = available

    @property
    def available(self) -> bool:
        return bool(self._available)

    def _ensure_available(self) -> None:
        if not self.available:
            raise BydEndpointNotSupportedError(
                f"Steering heat capability not supported for VIN {self._vin}",
                code="capability_unsupported",
                endpoint="steering",
            )

    async def heat(self, *, on: bool) -> None:
        """Enable or disable steering wheel heating.

        Parameters
        ----------
        on
            ``True`` to enable, ``False`` to disable.
        """
        self._ensure_available()
        status_value = StearingWheelHeat.ON if on else StearingWheelHeat.OFF
        command_value = 1 if on else 3  # BYD command scale: 1=on, 3=off

        specs = [
            ProjectionSpec("hvac", "steering_wheel_heat_state", status_value),
            ProjectionSpec("realtime", "steering_wheel_heat_state", status_value),
        ]

        # Activating steering wheel heat physically turns on the car's A/C.
        # Project HVAC status ON so climate/AC entities update immediately.
        # Turning it OFF does NOT turn off the A/C, so we skip that direction.
        if on:
            specs.append(ProjectionSpec("hvac", "status", HvacOverallStatus.ON))

        async def _cmd() -> Any:
            state = self._get_state()
            params = SeatClimateParams.from_current_state(
                hvac=state.hvac,
                realtime=state.realtime,
            ).with_change("steering_wheel_heat_state", command_value)
            return await self._set_seat_climate_fn(self._vin, params=params)

        await self._execute(_cmd, specs)
