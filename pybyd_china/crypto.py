"""Crypto utilities for BYD China API.

Implements AES-128-CBC inner payload encryption/decryption,
MD5/SHA1/SHA256 hashing helpers, and signature/checkcode computation.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from Crypto.Cipher import AES


# ---------------------------------------------------------------------------
# AES-128-CBC helpers (zero IV, hex I/O)
# ---------------------------------------------------------------------------

_ZERO_IV = b"\x00" * 16


def aes_encrypt_hex(plaintext: str, key_hex: str) -> str:
    """AES-128-CBC encrypt with zero IV. Returns uppercase hex string."""
    key = bytes.fromhex(key_hex)
    cipher = AES.new(key, AES.MODE_CBC, _ZERO_IV)
    # PKCS7 padding
    plaintext_bytes = plaintext.encode("utf-8")
    pad_len = 16 - (len(plaintext_bytes) % 16)
    plaintext_bytes += bytes([pad_len] * pad_len)
    ciphertext = cipher.encrypt(plaintext_bytes)
    return ciphertext.hex().upper()


def aes_decrypt_utf8(cipher_hex: str, key_hex: str) -> str:
    """AES-128-CBC decrypt with zero IV. Hex input, UTF-8 output."""
    key = bytes.fromhex(key_hex)
    ciphertext = bytes.fromhex(cipher_hex)
    decipher = AES.new(key, AES.MODE_CBC, _ZERO_IV)
    plaintext_padded = decipher.decrypt(ciphertext)
    # Strip PKCS7 padding
    pad_val = plaintext_padded[-1]
    if 1 <= pad_val <= 16:
        if all(b == pad_val for b in plaintext_padded[-pad_val:]):
            plaintext_padded = plaintext_padded[:-pad_val]
    return plaintext_padded.decode("utf-8")


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def md5_hex(value: str) -> str:
    """MD5 hash, uppercase hex output."""
    return hashlib.md5(value.encode("utf-8")).hexdigest().upper()


def pwd_login_key(password: str) -> str:
    """Derive login encryption key: MD5(MD5(password).toUpperCase())."""
    return md5_hex(md5_hex(password))


def sha1_mixed(value: str) -> str:
    """SHA1 with mixed case and zero filtering (BYD sign format)."""
    digest = hashlib.sha1(value.encode("utf-8")).digest()
    mixed = ""
    for idx, byte in enumerate(digest):
        hex_str = format(byte, "02x")
        if idx % 2 == 0:
            hex_str = hex_str.upper()
        else:
            hex_str = hex_str.lower()
        mixed += hex_str

    filtered = ""
    for i, ch in enumerate(mixed):
        if ch == "0" and i % 2 == 0:
            continue
        filtered += ch
    return filtered


def build_sign_string(fields: dict[str, Any], password: str) -> str:
    """Build sorted key=value sign string with password appended."""
    keys = sorted(fields.keys())
    joined = "&".join(f"{k}={fields[k]}" for k in keys)
    return f"{joined}&password={password}"


def compute_cn_checkcode(payload: dict[str, Any]) -> str:
    """Compute CN checkcode: SHA-256 of JSON.stringify(payload).

    JS JSON.stringify default format has no spaces: {"key":"value","key2":123}
    """
    json_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


def compute_checkcode(payload: dict[str, Any]) -> str:
    """Compute overseas checkcode: MD5 with reordered chunks (not used in CN mode, kept for reference)."""
    json_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    md5 = hashlib.md5(json_str.encode("utf-8")).hexdigest()
    return f"{md5[24:32]}{md5[8:16]}{md5[16:24]}{md5[0:8]}"


def random_hex16() -> str:
    """Generate 16 random bytes as uppercase hex string (32 chars)."""
    import os
    return os.urandom(16).hex().upper()
