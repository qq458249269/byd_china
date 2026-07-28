"""Hash functions for BYD API signing and verification."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def md5_hex(value: str) -> str:
    """Compute MD5 of a UTF-8 string, returning uppercase hex."""
    return hashlib.md5(value.encode("utf-8")).hexdigest().upper()


def pwd_login_key(password: str) -> str:
    """Derive the login AES key from a plaintext password."""
    return md5_hex(md5_hex(password))


def sha1_mixed(value: str) -> str:
    """Compute SHA1 with alternating-case hex and zero filtering."""
    digest = hashlib.sha1(value.encode("utf-8")).digest()

    mixed_chars: list[str] = []
    for i, byte_val in enumerate(digest):
        hex_str = f"{byte_val:02x}"
        if i % 2 == 0:
            mixed_chars.append(hex_str.upper())
        else:
            mixed_chars.append(hex_str.lower())
    mixed = "".join(mixed_chars)

    filtered: list[str] = []
    for j, ch in enumerate(mixed):
        if ch == "0" and j % 2 == 0:
            continue
        filtered.append(ch)
    return "".join(filtered)


def compute_checkcode(payload: dict[str, Any]) -> str:
    """Compute checkcode: MD5 of compact JSON with chunk reordering."""
    json_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    md5 = hashlib.md5(json_str.encode("utf-8")).hexdigest()
    return md5[24:32] + md5[8:16] + md5[16:24] + md5[0:8]
