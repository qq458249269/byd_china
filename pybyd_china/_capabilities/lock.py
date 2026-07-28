"""Lock/unlock capability."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._state_engine import ProjectionSpec
from ..exceptions import BydEndpointNotSupportedError
from ..models.realtime import LockState

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class LockCapability:
    """Vehicle lock/unlock commands with projection support."""

    def __init__(
        self,
        *,
        lock_fn: Callable[..., Awaitable[Any]],
        unlock_fn: Callable[..., Awaitable[Any]],
        vin: str,
        execute_command: Callable[..., Awaitable[None]],
        available: bool | None = True,
    ) -> None:
        self._lock_fn = lock_fn
        self._unlock_fn = unlock_fn
        self._vin = vin
        self._execute = execute_command
        self._available = available

    @property
    def available(self) -> bool:
        return bool(self._available)

    def _ensure_available(self) -> None:
        if not self.available:
            raise BydEndpointNotSupportedError(
                f"Lock capability not supported for VIN {self._vin}",
                code="capability_unsupported",
                endpoint="lock",
            )

    async def lock(self) -> None:
        """Lock all vehicle doors."""
        self._ensure_available()
        specs = [
            ProjectionSpec("realtime", "left_front_door_lock", LockState.LOCKED),
            ProjectionSpec("realtime", "right_front_door_lock", LockState.LOCKED),
            ProjectionSpec("realtime", "left_rear_door_lock", LockState.LOCKED),
            ProjectionSpec("realtime", "right_rear_door_lock", LockState.LOCKED),
        ]

        async def _cmd() -> Any:
            return await self._lock_fn(self._vin)

        await self._execute(_cmd, specs)

    async def unlock(self) -> None:
        """Unlock all vehicle doors."""
        self._ensure_available()
        specs = [
            ProjectionSpec("realtime", "left_front_door_lock", LockState.UNLOCKED),
            ProjectionSpec("realtime", "right_front_door_lock", LockState.UNLOCKED),
            ProjectionSpec("realtime", "left_rear_door_lock", LockState.UNLOCKED),
            ProjectionSpec("realtime", "right_rear_door_lock", LockState.UNLOCKED),
        ]

        async def _cmd() -> Any:
            return await self._unlock_fn(self._vin)

        await self._execute(_cmd, specs)
