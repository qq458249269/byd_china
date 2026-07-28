"""Vehicle latest-config models and normalized capabilities."""

from __future__ import annotations

import re

from pydantic import Field

from ..models._base import BydBaseModel
from ..models.command_gating import known_command_function_nos

_NON_ALNUM_RE = re.compile(r"[^A-Z0-9]")


def registered_latest_config_function_nos() -> frozenset[str]:
    """Return all latest-config functionNos currently registered by pyBYD.

    Relationship to command gating:
    - Command-related functionNos come from `known_command_function_nos()`.
    - Additional non-command latest-config values (parents/metadata) are listed here.

    How to add more:
    - Add new command values in `models/command_gating.py`.
    - Add non-command latest-config values in this set.
    - Keep tests in `tests/test_latest_config.py` green (`unknown_function_nos` should only contain truly new values).
    """
    return frozenset(
        set(known_command_function_nos())
        | {
            "1002",  # door/window (parent)
            "1003",  # ventilation/heating (parent)
            "1004",  # tire pressure (parent)
            "1014",  # location
            "1030",  # one-tap prep (parent)
            "10020001",  # sunroof
            "10020002",  # hood
            "10020003",  # trunk
            "10020004",  # up windows remotely
            "10020005",  # windows
            "10030011",  # seat rows
            "10040001",  # direct tire pressure
        }
    )


def _normalize_code(code: str) -> str:
    return _NON_ALNUM_RE.sub("", code.upper())


class LatestConfigFunction(BydBaseModel):
    """One capability node from getLatestConfig (top-level or second-level)."""

    code: str = ""
    function_name: str = ""
    function_no: str = ""
    sort_num: int | None = None
    cf_fixed_second_level_list: list[LatestConfigFunction] = Field(default_factory=list)

    def iter_flat(self) -> list[LatestConfigFunction]:
        """Flatten current node and all nested second-level nodes."""
        flattened: list[LatestConfigFunction] = [self]
        for child in self.cf_fixed_second_level_list:
            flattened.extend(child.iter_flat())
        return flattened


class VehicleLatestConfig(BydBaseModel):
    """Latest per-vehicle feature configuration from BYD cloud."""

    widget_config_id: str = ""
    config_version: int | None = None
    app_config_version: int | None = None
    style_id: int | None = None
    terminal_type: int | None = None
    cf_fixed_list: list[LatestConfigFunction] = Field(default_factory=list)

    def iter_functions(self) -> list[LatestConfigFunction]:
        """Return all capability nodes including nested second-level items."""
        items: list[LatestConfigFunction] = []
        for item in self.cf_fixed_list:
            items.extend(item.iter_flat())
        return items


class VehicleCapabilities(BydBaseModel):
    """Normalized vehicle capability availability used by integrations."""

    vin: str = ""
    source: str = "latest_config"

    lock: bool | None = None
    unlock: bool | None = None
    climate: bool | None = None
    car_on: bool | None = None
    battery_heat: bool | None = None
    steering_wheel_heat: bool | None = None

    driver_seat_heat: bool | None = None
    driver_seat_ventilation: bool | None = None
    passenger_seat_heat: bool | None = None
    passenger_seat_ventilation: bool | None = None

    find_car: bool | None = None
    flash_lights: bool | None = None
    close_windows: bool | None = None
    location: bool | None = None

    function_nos: list[str] = Field(default_factory=list)
    codes: list[str] = Field(default_factory=list)
    unknown_function_nos: list[str] = Field(default_factory=list)

    @classmethod
    def from_latest_config(cls, vin: str, latest: VehicleLatestConfig) -> VehicleCapabilities:
        """Build normalized capability flags from a latest-config payload.

        Notes:
        - Capability booleans are derived from `functionNo` only.
        - `unknown_function_nos` is computed against `registered_latest_config_function_nos()`.
        """
        function_nos: set[str] = set()
        normalized_codes: set[str] = set()

        for item in latest.iter_functions():
            if item.function_no:
                function_nos.add(str(item.function_no))
            if item.code:
                normalized = _normalize_code(item.code)
                if normalized:
                    normalized_codes.add(normalized)

        known_function_nos = set(registered_latest_config_function_nos())

        unknown_function_nos = sorted(function_nos - known_function_nos)

        def require(required_function_nos: list[str]) -> bool:
            return any(function_no in function_nos for function_no in required_function_nos)

        return cls.model_validate(
            {
                "vin": vin,
                "source": "latest_config",
                "lock": require(["1005"]),
                "unlock": require(["1006"]),
                "climate": require(["1001", "10300001"]),
                "car_on": require(["1001", "10300001"]),
                "battery_heat": require(["10300002"]),
                "steering_wheel_heat": require(["10030010", "10300004"]),
                "driver_seat_heat": require(["10030002", "10300003"]),
                "driver_seat_ventilation": require(["10030001", "10300003"]),
                "passenger_seat_heat": require(["10030005", "10300003"]),
                "passenger_seat_ventilation": require(["10030004", "10300003"]),
                "find_car": require(["1007"]),
                "flash_lights": require(["1008"]),
                "close_windows": require(["1026"]),
                "location": require(["1014"]),
                "function_nos": sorted(function_nos),
                "codes": sorted(normalized_codes),
                "unknown_function_nos": unknown_function_nos,
                "raw": latest.raw,
            }
        )

    @classmethod
    def unknown(cls, vin: str, *, reason: str = "unavailable") -> VehicleCapabilities:
        """Return an unknown capability map (treat as unavailable by strict consumers)."""
        return cls.model_validate(
            {
                "vin": vin,
                "source": f"unknown:{reason}",
            }
        )
