"""Window control capability."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..exceptions import BydEndpointNotSupportedError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class WindowsCapability:
    """Window close command.

    Close-windows is a fire-and-forget command.  No projections are
    registered because window state updates arrive asynchronously.
    """

    def __init__(
        self,
        *,
        close_fn: Callable[..., Awaitable[Any]],
        vin: str,
        execute_command: Callable[..., Awaitable[None]],
        close_available: bool | None = True,
    ) -> None:
        self._close_fn = close_fn
        self._vin = vin
        self._execute = execute_command
        self._close_available = close_available

    @property
    def close_available(self) -> bool:
        return bool(self._close_available)

    async def close(self) -> None:
        """Close all windows."""
        if not self.close_available:
            raise BydEndpointNotSupportedError(
                f"Close-windows capability not supported for VIN {self._vin}",
                code="capability_unsupported",
                endpoint="windows.close",
            )

        async def _cmd() -> Any:
            return await self._close_fn(self._vin)

        await self._execute(_cmd, [])
