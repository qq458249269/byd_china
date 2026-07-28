"""Battery heating capability."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._state_engine import ProjectionSpec
from ..exceptions import BydEndpointNotSupportedError
from ..models.control import BatteryHeatParams

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class BatteryHeatCapability:
    """Battery heating command with projection support."""

    def __init__(
        self,
        *,
        set_battery_heat_fn: Callable[..., Awaitable[Any]],
        vin: str,
        execute_command: Callable[..., Awaitable[None]],
        available: bool | None = True,
    ) -> None:
        self._set_battery_heat_fn = set_battery_heat_fn
        self._vin = vin
        self._execute = execute_command
        self._available = available

    @property
    def available(self) -> bool:
        return bool(self._available)

    def _ensure_available(self) -> None:
        if not self.available:
            raise BydEndpointNotSupportedError(
                f"Battery heat capability not supported for VIN {self._vin}",
                code="capability_unsupported",
                endpoint="battery_heat",
            )

    async def heat(self, *, on: bool) -> None:
        """Enable or disable battery heating.

        Parameters
        ----------
        on
            ``True`` to enable, ``False`` to disable.
        """
        self._ensure_available()
        params = BatteryHeatParams(on=on)
        specs = [
            ProjectionSpec("realtime", "battery_heat_state", 1 if on else 0),
        ]

        async def _cmd() -> Any:
            return await self._set_battery_heat_fn(self._vin, params=params)

        await self._execute(_cmd, specs)
