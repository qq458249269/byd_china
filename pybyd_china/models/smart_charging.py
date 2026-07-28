"""Smart charging schedule model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class SmartChargingSchedule(BaseModel):
    """Charging schedule configuration for a vehicle."""

    model_config = ConfigDict(frozen=True)

    vin: str
    """Vehicle Identification Number."""
    target_soc: int | None
    """Target state of charge (0-100 percent)."""
    start_hour: int | None
    """Scheduled charge start hour (0-23)."""
    start_minute: int | None
    """Scheduled charge start minute (0-59)."""
    end_hour: int | None
    """Scheduled charge end hour (0-23)."""
    end_minute: int | None
    """Scheduled charge end minute (0-59)."""
    smart_charge_switch: int | None
    """Smart charge toggle state (0=off, 1=on)."""
    raw: dict[str, Any]
    """Full API response dict."""

    @property
    def is_enabled(self) -> bool:
        """Whether smart charging is currently enabled."""
        return self.smart_charge_switch is not None and self.smart_charge_switch == 1
