"""Request signing for BYD API."""

from __future__ import annotations


def build_sign_string(fields: dict[str, str], password: str) -> str:
    """Build the sign string by sorting fields and appending password."""
    keys = sorted(fields.keys())
    joined = "&".join(f"{key}={'null' if fields[key] is None else fields[key]}" for key in keys)
    return f"{joined}&password={password}"
