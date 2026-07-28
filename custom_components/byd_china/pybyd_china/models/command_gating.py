"""Command gating rules and verdicts for remote-control preflight checks.

Mapping contract:
- This module is the command-level source of truth: `RemoteCommand` -> required `functionNo` values.
- Gating is strict and functionNo-only: if any required value for a gate is present, it is supported.

How to add support:
1) Add/extend a rule in `_COMMAND_GATE_RULES` for the command/gate variant.
2) If it is a seat variant, ensure `_SEAT_GATE_BY_CHAIR_TYPE` routes the right `chairType`.
3) Add/update tests in `tests/test_command_gating.py` and `tests/test_client_command_gating.py`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from pydantic import Field

from ..models._base import BydBaseModel
from ..models.control import RemoteCommand

if TYPE_CHECKING:
    from ..models.latest_config import VehicleCapabilities


class CommandGateRule(BydBaseModel):
    """Canonical command gate definition."""

    gate_id: str
    command: RemoteCommand
    required_function_nos: list[str] = Field(default_factory=list)


class CommandGateVerdict(BydBaseModel):
    """Evaluated support verdict for a command gate."""

    command: RemoteCommand
    gate_id: str
    supported: bool
    reason: str

    required_function_nos: list[str] = Field(default_factory=list)

    matched_function_nos: list[str] = Field(default_factory=list)

    counterpart_function_nos: list[str] = Field(default_factory=list)


# Canonical command -> functionNo mapping used by both client preflight and reporting.
_COMMAND_GATE_RULES: tuple[CommandGateRule, ...] = (
    CommandGateRule.model_validate(
        {
            "gateId": "lock",
            "command": RemoteCommand.LOCK,
            "requiredFunctionNos": ["1005"],
        }
    ),
    CommandGateRule.model_validate(
        {
            "gateId": "unlock",
            "command": RemoteCommand.UNLOCK,
            "requiredFunctionNos": ["1006"],
        }
    ),
    CommandGateRule.model_validate(
        {
            "gateId": "climate",
            "command": RemoteCommand.START_CLIMATE,
            "requiredFunctionNos": ["1001", "10300001"],
        }
    ),
    CommandGateRule.model_validate(
        {
            "gateId": "climate",
            "command": RemoteCommand.STOP_CLIMATE,
            "requiredFunctionNos": ["1001", "10300001"],
        }
    ),
    CommandGateRule.model_validate(
        {
            "gateId": "climate_schedule",
            "command": RemoteCommand.SCHEDULE_CLIMATE,
            "requiredFunctionNos": ["1001", "10300001"],
        }
    ),
    CommandGateRule.model_validate(
        {
            "gateId": "find_car",
            "command": RemoteCommand.FIND_CAR,
            "requiredFunctionNos": ["1007"],
        }
    ),
    CommandGateRule.model_validate(
        {
            "gateId": "flash_lights",
            "command": RemoteCommand.FLASH_LIGHTS,
            "requiredFunctionNos": ["1008"],
        }
    ),
    CommandGateRule.model_validate(
        {
            "gateId": "close_windows",
            "command": RemoteCommand.CLOSE_WINDOWS,
            "requiredFunctionNos": ["1026"],
        }
    ),
    CommandGateRule.model_validate(
        {
            "gateId": "seat_driver",
            "command": RemoteCommand.SEAT_CLIMATE,
            "requiredFunctionNos": ["10030001", "10030002", "10300003"],
        }
    ),
    CommandGateRule.model_validate(
        {
            "gateId": "seat_passenger",
            "command": RemoteCommand.SEAT_CLIMATE,
            "requiredFunctionNos": ["10030004", "10030005", "10300003"],
        }
    ),
    CommandGateRule.model_validate(
        {
            "gateId": "steering_wheel_heat",
            "command": RemoteCommand.SEAT_CLIMATE,
            "requiredFunctionNos": ["10030010", "10300004"],
        }
    ),
    CommandGateRule.model_validate(
        {
            "gateId": "battery_heat",
            "command": RemoteCommand.BATTERY_HEAT,
            "requiredFunctionNos": ["10300002"],
        }
    ),
)

# Seat command requires explicit target selection via control_params.chairType.
_SEAT_GATE_BY_CHAIR_TYPE: dict[str, str] = {
    "1": "seat_driver",
    "2": "seat_passenger",
    "5": "steering_wheel_heat",
}


def _require(function_nos: set[str], required_function_nos: list[str]) -> bool:
    return any(function_no in function_nos for function_no in required_function_nos)


def command_gate_rules() -> tuple[CommandGateRule, ...]:
    """Return canonical command gate rules."""
    return _COMMAND_GATE_RULES


def known_command_function_nos() -> frozenset[str]:
    """Return all functionNos referenced by command rules.

    latest_config uses this set as part of its registered functionNo registry,
    so adding a new command rule automatically participates in coverage checks.
    """
    return frozenset(
        function_no for rule in _COMMAND_GATE_RULES for function_no in rule.required_function_nos if function_no
    )


def _evaluate_rule(
    rule: CommandGateRule,
    capabilities: VehicleCapabilities,
    *,
    function_nos: set[str],
) -> CommandGateVerdict:
    matched_function_nos = sorted([fn for fn in rule.required_function_nos if fn in function_nos])

    supported = _require(function_nos, rule.required_function_nos)
    reason = "supported" if supported else "function_no_missing"

    counterpart_function_nos = sorted(
        function_no for function_no in rule.required_function_nos if function_no not in matched_function_nos
    )

    return CommandGateVerdict.model_validate(
        {
            "command": rule.command,
            "gateId": rule.gate_id,
            "supported": supported,
            "reason": reason,
            "requiredFunctionNos": rule.required_function_nos,
            "matchedFunctionNos": matched_function_nos,
            "counterpartFunctionNos": counterpart_function_nos,
        }
    )


def evaluate_all_command_gates(capabilities: VehicleCapabilities) -> list[CommandGateVerdict]:
    """Evaluate all canonical gates for reporting and diagnostics."""
    function_nos = set(capabilities.function_nos)
    return [_evaluate_rule(rule, capabilities, function_nos=function_nos) for rule in _COMMAND_GATE_RULES]


def evaluate_command_gate(
    command: RemoteCommand,
    capabilities: VehicleCapabilities,
    *,
    control_params: Mapping[str, object] | None = None,
) -> CommandGateVerdict:
    """Evaluate preflight support for a command against capabilities/functionNos."""
    function_nos = set(capabilities.function_nos)
    command_rules = [rule for rule in _COMMAND_GATE_RULES if rule.command == command]

    if command == RemoteCommand.SEAT_CLIMATE:
        chair_type: str | None = None
        if control_params is not None:
            raw_chair_type = control_params.get("chairType")
            if isinstance(raw_chair_type, str):
                chair_type = raw_chair_type
            elif raw_chair_type is not None:
                chair_type = str(raw_chair_type)

        gate_id = _SEAT_GATE_BY_CHAIR_TYPE.get(chair_type or "")
        if gate_id is None:
            all_seat_rules = [rule for rule in command_rules if rule.gate_id in set(_SEAT_GATE_BY_CHAIR_TYPE.values())]
            required_function_nos = sorted(
                {function_no for rule in all_seat_rules for function_no in rule.required_function_nos}
            )
            return CommandGateVerdict.model_validate(
                {
                    "command": command,
                    "gateId": "seat_target",
                    "supported": False,
                    "reason": "seat_target_unknown",
                    "requiredFunctionNos": required_function_nos,
                    "matchedFunctionNos": [],
                    "counterpartFunctionNos": required_function_nos,
                }
            )

        selected_rule = next(rule for rule in command_rules if rule.gate_id == gate_id)
        return _evaluate_rule(selected_rule, capabilities, function_nos=function_nos)

    selected = command_rules[0]
    return _evaluate_rule(selected, capabilities, function_nos=function_nos)
