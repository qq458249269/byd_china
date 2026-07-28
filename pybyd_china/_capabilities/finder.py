"""Vehicle finder capability (find car / flash lights)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..exceptions import BydEndpointNotSupportedError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class FinderCapability:
    """Find-my-car and flash lights commands.

    These are fire-and-forget commands with no observable state change,
    so no projections are registered.
    """

    def __init__(
        self,
        *,
        find_fn: Callable[..., Awaitable[Any]],
        flash_fn: Callable[..., Awaitable[Any]],
        vin: str,
        execute_command: Callable[..., Awaitable[None]],
        find_available: bool | None = True,
        flash_available: bool | None = True,
    ) -> None:
        self._find_fn = find_fn
        self._flash_fn = flash_fn
        self._vin = vin
        self._execute = execute_command
        self._find_available = find_available
        self._flash_available = flash_available

    @property
    def find_available(self) -> bool:
        return bool(self._find_available)

    @property
    def flash_available(self) -> bool:
        return bool(self._flash_available)

    async def find(self) -> None:
        """Activate find-my-car (horn + lights)."""
        if not self.find_available:
            raise BydEndpointNotSupportedError(
                f"Find-car capability not supported for VIN {self._vin}",
                code="capability_unsupported",
                endpoint="finder.find",
            )

        async def _cmd() -> Any:
            return await self._find_fn(self._vin)

        await self._execute(_cmd, [])

    async def flash_lights(self) -> None:
        """Flash vehicle lights."""
        if not self.flash_available:
            raise BydEndpointNotSupportedError(
                f"Flash-lights capability not supported for VIN {self._vin}",
                code="capability_unsupported",
                endpoint="finder.flash_lights",
            )

        async def _cmd() -> Any:
            return await self._flash_fn(self._vin)

        await self._execute(_cmd, [])
