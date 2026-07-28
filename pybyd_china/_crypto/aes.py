"""Standard AES-128-CBC encryption for BYD inner payloads."""

from __future__ import annotations

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ..exceptions import BydCryptoError

_ZERO_IV = b"\x00" * 16


def _parse_hex_bytes(
    value: str,
    *,
    name: str,
    allowed_nbytes: set[int] | None = None,
) -> bytes:
    text = value.strip()
    if text.startswith("0x") or text.startswith("0X"):
        text = text[2:]
    if not text:
        raise BydCryptoError(f"{name} is empty")
    if len(text) % 2 != 0:
        raise BydCryptoError(f"{name} hex length must be even (got {len(text)})")
    try:
        data = bytes.fromhex(text)
    except ValueError as exc:
        raise BydCryptoError(f"{name} must be hex-encoded") from exc

    if allowed_nbytes is not None and len(data) not in allowed_nbytes:
        allowed = ", ".join(str(n) for n in sorted(allowed_nbytes))
        raise BydCryptoError(f"{name} must be {allowed} bytes (got {len(data)})")
    return data


def aes_encrypt_hex(plaintext: str, key_hex: str) -> str:
    """AES-128-CBC encrypt with zero IV, returning uppercase hex."""
    try:
        key = _parse_hex_bytes(key_hex, name="AES key", allowed_nbytes={16, 24, 32})
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(_ZERO_IV))
        encryptor = cipher.encryptor()
        ct = encryptor.update(padded) + encryptor.finalize()
        return ct.hex().upper()
    except Exception as exc:
        raise BydCryptoError(f"AES encryption failed: {exc}") from exc


def aes_decrypt_utf8(cipher_hex: str, key_hex: str) -> str:
    """AES-128-CBC decrypt from hex with zero IV, returning UTF-8 string."""
    try:
        key = _parse_hex_bytes(key_hex, name="AES key", allowed_nbytes={16, 24, 32})
        ct = _parse_hex_bytes(cipher_hex, name="AES ciphertext")
        cipher = Cipher(algorithms.AES(key), modes.CBC(_ZERO_IV))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ct) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()
        return plaintext.decode("utf-8")
    except BydCryptoError:
        raise
    except Exception as exc:
        raise BydCryptoError(f"AES decryption failed: {exc}") from exc
