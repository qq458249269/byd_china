"""GPS information model."""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from ..models._base import BydBaseModel, BydTimestamp


class GpsInfo(BydBaseModel):
    """GPS location data for a vehicle.

    The response nests fields under a ``data`` dict which is
    flattened automatically.
    """

    latitude: float | None = None
    longitude: float | None = None
    speed: float | None = None
    direction: float | None = None
    gps_timestamp: BydTimestamp = Field(default=None, validation_alias="gpsTimeStamp")
    request_serial: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _flatten_nested_data(cls, values: Any) -> Any:
        """Flatten the nested ``data`` dict the GPS endpoint wraps results in."""
        if not isinstance(values, dict):
            return values
        nested = values.get("data")
        if isinstance(nested, dict):
            merged = dict(values)
            merged.update(nested)
            return merged
        return values
