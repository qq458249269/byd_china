"""Push notification state model."""

from __future__ import annotations

from ..models._base import BydBaseModel


class PushNotificationState(BydBaseModel):
    """Push notification switch state for a vehicle."""

    vin: str = ""
    push_switch: int | None = None

    @property
    def is_enabled(self) -> bool:
        return self.push_switch is not None and self.push_switch == 1
