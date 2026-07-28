"""PKCS#7 padding for the Bangcle white-box AES layer."""

from __future__ import annotations


def add_pkcs7(data: bytes, block_size: int = 16) -> bytes:
    """Add PKCS#7 padding."""
    remainder = len(data) % block_size
    pad_len = block_size if remainder == 0 else block_size - remainder
    return data + bytes([pad_len] * pad_len)


def strip_pkcs7(data: bytes) -> bytes:
    """Strip PKCS#7 padding, returning data as-is if padding is invalid."""
    if not data:
        return data
    pad = data[-1]
    if pad == 0 or pad > 16:
        return data
    if len(data) < pad:
        return data
    if all(b == pad for b in data[-pad:]):
        return data[:-pad]
    return data
