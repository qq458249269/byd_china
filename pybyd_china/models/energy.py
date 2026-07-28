"""Energy consumption data model."""

from __future__ import annotations

from ..models._base import BydBaseModel


class EnergyConsumption(BydBaseModel):
    """Energy consumption data for a vehicle."""

    vin: str = ""
    total_energy: float | None = None
    avg_energy_consumption: float | None = None
    electricity_consumption: float | None = None
    fuel_consumption: float | None = None
