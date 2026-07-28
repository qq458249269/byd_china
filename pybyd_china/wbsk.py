"""WBSK white-box AES-256 encrypt/decrypt for BYD China app.

Ported from BYD-re-main/wbsk.js - two-layer WBSK envelope encryption
used by the CN BYD app (com.byd.aeri.caranywhere).
"""

from __future__ import annotations

import base64
import struct
from typing import Final

from .wbsk_tables import WBSK_TABLES


# ---------------------------------------------------------------------------
# Table decoding helpers
# ---------------------------------------------------------------------------

def _decode_byte_table(name: str) -> bytes:
    """Decode a 256-byte lookup table from Base64."""
    b64 = WBSK_TABLES.get(name)
    if not b64:
        raise ValueError(f"Missing embedded WBSK table: {name}")
    raw = base64.b64decode(b64)
    if len(raw) != 256:
        raise ValueError(f"WBSK table {name} has unexpected size {len(raw)} (expected 256)")
    return raw


def _decode_u32_table(name: str) -> list[int]:
    """Decode a 256-entry uint32-LE lookup table from Base64."""
    b64 = WBSK_TABLES.get(name)
    if not b64:
        raise ValueError(f"Missing embedded WBSK table: {name}")
    raw = base64.b64decode(b64)
    if len(raw) != 1024:
        raise ValueError(f"WBSK table {name} has unexpected size {len(raw)} (expected 1024)")
    return [struct.unpack_from("<I", raw, i * 4)[0] for i in range(256)]


# ---------------------------------------------------------------------------
# Static tables (loaded once at module level)
# ---------------------------------------------------------------------------

# Encrypt tables
ENC_INIT_XOR: Final = _decode_byte_table("encInitXor")
ENC_ROUND_XOR: Final = _decode_byte_table("encRoundXor")
ENC_SBOX: Final = _decode_byte_table("encSbox")
ENC_FINAL_XOR: Final = _decode_byte_table("encFinalXor")
ENC_TE0: Final = _decode_u32_table("encTe0")
ENC_TE1: Final = _decode_u32_table("encTe1")
ENC_TE2: Final = _decode_u32_table("encTe2")
ENC_TE3: Final = _decode_u32_table("encTe3")

# Decrypt tables
DEC_INIT_XOR: Final = _decode_byte_table("decInitXor")
DEC_ROUND_XOR: Final = _decode_byte_table("decRoundXor")
DEC_INV_SBOX: Final = _decode_byte_table("decInvSbox")
DEC_FINAL_XOR: Final = _decode_byte_table("decFinalXor")
DEC_TD0: Final = _decode_u32_table("decTd0")
DEC_TD1: Final = _decode_u32_table("decTd1")
DEC_TD2: Final = _decode_u32_table("decTd2")
DEC_TD3: Final = _decode_u32_table("decTd3")


# ---------------------------------------------------------------------------
# Static WBSK keys (device-bound, not per-session)
# ---------------------------------------------------------------------------

WBSK_KEYS: Final[dict[str, str]] = {
    "outer_encrypt_key": "4dca015d9f0488cdea45e890de3b9c4d16c9f82e1082e295c8312d34da7214b805bdec33d8473ab04c84a51eebee4fd5efee21ed403a159a083dbb2854c92719d8f24dd3002ce675c4b930fd5f410ebe56d9594532f9c109b7f2dc58eebd83a83cc948fd3dc0b696add8b06d19efa7c8c04d17f60d144d943e21ef4add5af566ef14241de9c3bb03cf9b9d3c5d042caa1fcdf222e02ba7cf577cc70375d0b4e7e3340278e56ddee1a180451b3a04f25fe34f0d1f05ec426b0de801e7d7382ecf2c3ab7be923c2d5ff0c33eaa4c45c71b258045f68bd7ad0f594ff86785611f67f30da78dfa9b427f04d625a2c61e2db62e1fe7d4",
    "outer_decrypt_key": "72ca0163b22e2973656a67ac1ae1490a61133824a0cd235bcfcd6032dba79d3ca51b1c4d1b03068566ff084645dcc9e6e8a28b39c71e72dec3fe4074109a84f5564d3f43f4854fb634bf633dabe218a5b73470dff70b07161b76c74d92bffa15bcb7fa4fc448a0fe83b62c9dd97f36d1d1d7613028041bb1dd328397bbf8c8bf6f81321f5e2d4982761a375bded52a1de198169839fabad771bc677b57f806c1ca385f43627e9a5081c43d7c9d9fa86e7e78cc0a8050a2420a76c842abbe93eb38f2487bdf93087cd24097a16539da2f86feb693432daf8f0618cbf97ffea3a762b7b91050f8634a8d3ceb25ea7d2b3264a77337",
    "inner_encrypt_key": "9fca018f72712b15e23c275ea5e06a92d8b98404cf0bf960955596ff47dd2adf8f9e0c3ca1363e8be88cb6fced211933e5c3484c20c7bc3ae1eb8541027fef4a20b2f302d93582f7f4349fef05c16d389956ae9f2a7aea278fd5232229e38caca017ffbaf5138d2cadbca917b4694fb2882a64809c095387b7353608ca3a17913e5863770465986995c684ea7db01e0c35c69fd169a8e14ec5123beb5b8dad6e1c5198f34ed1c44d5f9b15035673df5953e5e42351f58052c1483fa4cf93c646a396081355a46d5a7e0ce30d54049802829cd78c1a77c7db8f74acb244b73c5147f161ee25bd702112cec97c339a6b3314527d12",
    "inner_decrypt_key": "71ca0160b689febe1c11e07bc8f8cec81decf71b6c3e0be299a35211888c2fb177958e57a6e971d0a874ecb50991786faf3a34b178f13a668bd14b81a82d3f799f6f0c8bd002406c8b6fdd54b3bb30c0c7d27c906dba87decde28717a0874abacf41755646b4a2c06854615ab00ae53136cbea3302b047659e7a42f792a7369fc130d8ffdc114a7a2cf2fa669b9b337905ff58fe3cc40b9b1edf37ebe50d36b3416abbd32837895b8ea1f22b9eab35efd791d9153208630297b8b953a9ca33265854c33959979b9eb1d049326986851170f4b51d151f43a30c6298a8c03503477336b2000c49746181ca30eabded6d3088b7f615",
    "outer_encrypt_iv": "91339992399838993130933138923692",
    "outer_decrypt_iv": "54cc5558c551c155c4c05cc4c158ca58",
    "inner_encrypt_iv": "a8bb9ab895ba95363a81b1949da68184",
}


# ---------------------------------------------------------------------------
# Protected XOR operation (nibble-decomposed lookup)
# ---------------------------------------------------------------------------

def _prot_xor(table: bytes, a: int, b: int) -> int:
    """Nibble-decomposed XOR in the encoded byte domain."""
    hi = table[((a >> 4) << 4) ^ (b >> 4)] & 0xF0
    lo = (table[((a & 0xF) << 4) ^ (b & 0xF)] >> 4) & 0x0F
    return hi | lo


# ---------------------------------------------------------------------------
# WBC key blob parser
# ---------------------------------------------------------------------------

def parse_wbc_key(hex_str: str) -> dict:
    """Parse a WBC key blob from hex string."""
    raw = bytes.fromhex(hex_str)
    if len(raw) < 5:
        raise ValueError(f"WBC key blob too short: {len(raw)} bytes")

    mode = raw[0] ^ raw[3]

    key_data = bytearray(len(raw) - 4)
    for i in range(4, len(raw)):
        key_data[i - 4] = raw[i] ^ raw[i % 3]

    # Determine key size and block size from mode
    mode_key_sizes = {
        0: 0x80, 1: 0x80, 2: 0xC0, 3: 0xC0,
        4: 0x80, 5: 0x80, 6: 0x40, 7: 0x40,
        8: 0xC0, 9: 0xC0, 0xA: 0x80, 0xB: 0x80,
        0xC: 0x80, 0xD: 0x80, 0xE: 0xC0, 0xF: 0xC0,
        0x10: 0x100, 0x11: 0x100, 0x12: 0x40, 0x13: 0x40,
        0x14: 0xC0, 0x15: 0xC0, 0x16: 0x80, 0x17: 0x80,
    }
    key_size_bits = mode_key_sizes.get(mode)
    if key_size_bits is None:
        raise ValueError(f"Unknown WBC mode: 0x{mode:x}")

    num_rounds = (key_size_bits >> 5) + 6
    is_decrypt = mode & 1
    block_size = 8 if mode in (6, 7, 0x12, 0x13) else 16

    return {
        "key_data": bytes(key_data),
        "key_size_bits": key_size_bits,
        "num_rounds": num_rounds,
        "is_decrypt": is_decrypt,
        "block_size": block_size,
        "mode": mode,
    }


# ---------------------------------------------------------------------------
# WBC AES block encrypt/decrypt (16 bytes)
# ---------------------------------------------------------------------------

def _wbc_encrypt_block(input_block: bytes, key_data: bytes, num_rounds: int) -> bytes:
    """WBC AES encrypt a single 16-byte block."""
    state = bytearray(16)
    temp1 = bytearray(16)
    temp2 = bytearray(16)

    # Initial AddRoundKey
    for i in range(16):
        state[i] = _prot_xor(ENC_INIT_XOR, input_block[i], key_data[i])

    # Main rounds
    for r in range(1, num_rounds):
        # Te0 [0,4,8,12]
        for c in range(4):
            v = ENC_TE0[state[c * 4]]
            temp1[c * 4] = (v >> 24) & 0xFF
            temp1[c * 4 + 1] = (v >> 16) & 0xFF
            temp1[c * 4 + 2] = (v >> 8) & 0xFF
            temp1[c * 4 + 3] = v & 0xFF
        # Te1 [5,9,13,1]
        te1i = [5, 9, 13, 1]
        for c in range(4):
            v = ENC_TE1[state[te1i[c]]]
            temp2[c * 4] = (v >> 24) & 0xFF
            temp2[c * 4 + 1] = (v >> 16) & 0xFF
            temp2[c * 4 + 2] = (v >> 8) & 0xFF
            temp2[c * 4 + 3] = v & 0xFF
        for i in range(16):
            temp1[i] = _prot_xor(ENC_ROUND_XOR, temp1[i], temp2[i])
        # Te2 [10,14,2,6]
        te2i = [10, 14, 2, 6]
        for c in range(4):
            v = ENC_TE2[state[te2i[c]]]
            temp2[c * 4] = (v >> 24) & 0xFF
            temp2[c * 4 + 1] = (v >> 16) & 0xFF
            temp2[c * 4 + 2] = (v >> 8) & 0xFF
            temp2[c * 4 + 3] = v & 0xFF
        for i in range(16):
            temp1[i] = _prot_xor(ENC_ROUND_XOR, temp1[i], temp2[i])
        # Te3 [15,3,7,11]
        te3i = [15, 3, 7, 11]
        for c in range(4):
            v = ENC_TE3[state[te3i[c]]]
            temp2[c * 4] = (v >> 24) & 0xFF
            temp2[c * 4 + 1] = (v >> 16) & 0xFF
            temp2[c * 4 + 2] = (v >> 8) & 0xFF
            temp2[c * 4 + 3] = v & 0xFF
        for i in range(16):
            temp1[i] = _prot_xor(ENC_ROUND_XOR, temp1[i], temp2[i])
        # AddRoundKey
        rk_off = r * 16
        for i in range(16):
            state[i] = _prot_xor(ENC_ROUND_XOR, temp1[i], key_data[rk_off + i])

    # Final round: S-box + ShiftRows + AddRoundKey
    sr = [0, 5, 10, 15, 4, 9, 14, 3, 8, 13, 2, 7, 12, 1, 6, 11]
    for i in range(16):
        temp1[i] = ENC_SBOX[state[sr[i]]]
    output = bytearray(16)
    frk_off = num_rounds * 16
    for i in range(16):
        output[i] = _prot_xor(ENC_FINAL_XOR, temp1[i], key_data[frk_off + i])
    return bytes(output)


def _wbc_decrypt_block(input_block: bytes, key_data: bytes, num_rounds: int) -> bytes:
    """WBC AES decrypt a single 16-byte block."""
    state = bytearray(16)
    temp1 = bytearray(16)
    temp2 = bytearray(16)

    # Initial AddRoundKey
    for i in range(16):
        state[i] = _prot_xor(DEC_INIT_XOR, input_block[i], key_data[i])

    # Main rounds
    for r in range(1, num_rounds):
        # Td0 [0,4,8,12]
        for c in range(4):
            v = DEC_TD0[state[c * 4]]
            temp1[c * 4] = (v >> 24) & 0xFF
            temp1[c * 4 + 1] = (v >> 16) & 0xFF
            temp1[c * 4 + 2] = (v >> 8) & 0xFF
            temp1[c * 4 + 3] = v & 0xFF
        # Td1 [13,1,5,9] (InvShiftRows)
        td1i = [13, 1, 5, 9]
        for c in range(4):
            v = DEC_TD1[state[td1i[c]]]
            temp2[c * 4] = (v >> 24) & 0xFF
            temp2[c * 4 + 1] = (v >> 16) & 0xFF
            temp2[c * 4 + 2] = (v >> 8) & 0xFF
            temp2[c * 4 + 3] = v & 0xFF
        for i in range(16):
            temp1[i] = _prot_xor(DEC_ROUND_XOR, temp1[i], temp2[i])
        # Td2 [10,14,2,6]
        td2i = [10, 14, 2, 6]
        for c in range(4):
            v = DEC_TD2[state[td2i[c]]]
            temp2[c * 4] = (v >> 24) & 0xFF
            temp2[c * 4 + 1] = (v >> 16) & 0xFF
            temp2[c * 4 + 2] = (v >> 8) & 0xFF
            temp2[c * 4 + 3] = v & 0xFF
        for i in range(16):
            temp1[i] = _prot_xor(DEC_ROUND_XOR, temp1[i], temp2[i])
        # Td3 [7,11,15,3] (InvShiftRows)
        td3i = [7, 11, 15, 3]
        for c in range(4):
            v = DEC_TD3[state[td3i[c]]]
            temp2[c * 4] = (v >> 24) & 0xFF
            temp2[c * 4 + 1] = (v >> 16) & 0xFF
            temp2[c * 4 + 2] = (v >> 8) & 0xFF
            temp2[c * 4 + 3] = v & 0xFF
        for i in range(16):
            temp1[i] = _prot_xor(DEC_ROUND_XOR, temp1[i], temp2[i])
        # AddRoundKey
        rk_off = r * 16
        for i in range(16):
            state[i] = _prot_xor(DEC_ROUND_XOR, temp1[i], key_data[rk_off + i])

    # Final round: inv S-box + InvShiftRows + AddRoundKey
    inv_sr = [0, 13, 10, 7, 4, 1, 14, 11, 8, 5, 2, 15, 12, 9, 6, 3]
    for i in range(16):
        temp1[i] = DEC_INV_SBOX[state[inv_sr[i]]]
    output = bytearray(16)
    frk_off = num_rounds * 16
    for i in range(16):
        output[i] = _prot_xor(DEC_FINAL_XOR, temp1[i], key_data[frk_off + i])
    return bytes(output)


# ---------------------------------------------------------------------------
# CBC mode
# ---------------------------------------------------------------------------

def _wbc_encrypt_cbc(plaintext: bytes, key_data: bytes, num_rounds: int, iv: bytes) -> bytes:
    """WBC AES CBC encrypt."""
    block_count = len(plaintext) // 16
    output = bytearray(len(plaintext))
    prev = iv

    for b in range(block_count):
        block = bytearray(16)
        for i in range(16):
            block[i] = plaintext[b * 16 + i] ^ prev[i]
        enc = _wbc_encrypt_block(bytes(block), key_data, num_rounds)
        output[b * 16:b * 16 + 16] = enc
        prev = enc

    return bytes(output)


def _wbc_decrypt_cbc(ciphertext: bytes, key_data: bytes, num_rounds: int, iv: bytes) -> bytes:
    """WBC AES CBC decrypt."""
    block_count = len(ciphertext) // 16
    output = bytearray(len(ciphertext))
    prev = iv

    for b in range(block_count):
        block = ciphertext[b * 16:b * 16 + 16]
        dec = _wbc_decrypt_block(block, key_data, num_rounds)
        for i in range(16):
            output[b * 16 + i] = dec[i] ^ prev[i]
        prev = block

    return bytes(output)


# ---------------------------------------------------------------------------
# Nibble codec
# ---------------------------------------------------------------------------

NIBBLE_ENCODE: Final = [0x0, 0x8, 0x4, 0xC, 0x1, 0x9, 0x5, 0xD, 0x2, 0xA, 0x6, 0xE, 0x3, 0xB, 0x7, 0xF]
NIBBLE_DECODE: Final = [0x0, 0x4, 0x8, 0xC, 0x2, 0x6, 0xA, 0xE, 0x1, 0x5, 0x9, 0xD, 0x3, 0x7, 0xB, 0xF]


def _nibble_encode(buf: bytes) -> bytes:
    out = bytearray(len(buf))
    for i in range(len(buf)):
        out[i] = (NIBBLE_ENCODE[buf[i] >> 4] << 4) | NIBBLE_ENCODE[buf[i] & 0xF]
    return bytes(out)


def _nibble_decode(buf: bytes) -> bytes:
    out = bytearray(len(buf))
    for i in range(len(buf)):
        out[i] = (NIBBLE_DECODE[buf[i] >> 4] << 4) | NIBBLE_DECODE[buf[i] & 0xF]
    return bytes(out)


# ---------------------------------------------------------------------------
# PKCS7 padding
# ---------------------------------------------------------------------------

def _strip_pkcs7(buf: bytes) -> bytes:
    pad_val = buf[-1]
    if pad_val < 1 or pad_val > 16:
        return buf
    for i in range(len(buf) - pad_val, len(buf)):
        if buf[i] != pad_val:
            return buf
    return buf[:len(buf) - pad_val]


def _add_pkcs7(buf: bytes, block_size: int = 16) -> bytes:
    remainder = len(buf) % block_size
    pad = block_size if remainder == 0 else block_size - remainder
    return buf + bytes([pad] * pad)


# ---------------------------------------------------------------------------
# WBC domain helpers for encrypt
# ---------------------------------------------------------------------------

# "Mystery encode": per-nibble ENCODE[ENCODE[n^8]]
MYSTERY_ENCODE: Final = [NIBBLE_ENCODE[NIBBLE_ENCODE[n ^ 8]] for n in range(16)]


def _wbc_input_encode(buf: bytes) -> bytes:
    """Convert plaintext to WBC encrypt input domain."""
    out = bytearray(len(buf))
    for i in range(len(buf)):
        out[i] = (MYSTERY_ENCODE[buf[i] >> 4] << 4) | MYSTERY_ENCODE[buf[i] & 0xF]
    return bytes(out)


def _wbc_output_decode(buf: bytes) -> bytes:
    """Convert WBC encrypt output to raw envelope domain."""
    out = bytearray(len(buf))
    for i in range(len(buf)):
        out[i] = (NIBBLE_ENCODE[NIBBLE_ENCODE[buf[i] >> 4]] << 4) | NIBBLE_ENCODE[NIBBLE_ENCODE[buf[i] & 0xF]]
    return bytes(out)


def _add_wbc_pkcs7(buf: bytes, block_size: int = 16) -> bytes:
    """PKCS7 padding in the WBC input domain (mystery-encoded pad values)."""
    remainder = len(buf) % block_size
    pad_n = block_size if remainder == 0 else block_size - remainder
    pad_byte = (MYSTERY_ENCODE[pad_n >> 4] << 4) | MYSTERY_ENCODE[pad_n & 0xF]
    return buf + bytes([pad_byte] * pad_n)


# ---------------------------------------------------------------------------
# Two-layer WBSK envelope decrypt
# ---------------------------------------------------------------------------

def decrypt_wbsk_envelope(
    base64_str: str,
    outer_key_hex: str,
    inner_key_hex: str,
    outer_session_iv_hex: str,
) -> str:
    """Decrypt a two-layer WBSK envelope."""
    # 1. Base64 decode
    raw = base64.b64decode(base64_str)

    # 2. Nibble-encode + 256 zero bytes padding
    outer_encoded = _nibble_encode(raw) + bytes(256)

    # 3. WBC decrypt CBC with outer key and session IV
    outer_key = parse_wbc_key(outer_key_hex)
    outer_iv = bytes.fromhex(outer_session_iv_hex)
    outer_decrypted = _wbc_decrypt_cbc(outer_encoded, outer_key["key_data"], outer_key["num_rounds"], outer_iv)

    # 4. Nibble-decode content region and strip PKCS7
    outer_content = _strip_pkcs7(_nibble_decode(outer_decrypted[:len(raw)]))
    content_len = len(outer_content)

    # 5. Split: base64(inner) is first (contentLen-16) bytes,
    #    inner session IV is last 16 bytes from raw WBC output
    inner_base64 = outer_content[:content_len - 16].decode("latin-1")
    inner_iv = outer_decrypted[content_len - 16:content_len]

    # 6. Base64 decode inner envelope + nibble-encode + pad
    inner_raw = base64.b64decode(inner_base64)
    inner_encoded = _nibble_encode(inner_raw) + bytes(256)

    # 7. WBC decrypt CBC with inner key and session IV
    inner_key = parse_wbc_key(inner_key_hex)
    inner_decrypted = _wbc_decrypt_cbc(inner_encoded, inner_key["key_data"], inner_key["num_rounds"], inner_iv)

    # 8. Nibble-decode content region + strip PKCS7
    inner_content = _strip_pkcs7(_nibble_decode(inner_decrypted[:len(inner_raw)]))
    return inner_content.decode("utf-8")


# ---------------------------------------------------------------------------
# Two-layer WBSK envelope encrypt
# ---------------------------------------------------------------------------

def encrypt_wbsk_envelope(
    plaintext: str,
    inner_enc_key_hex: str,
    inner_enc_iv_hex: str,
    outer_enc_key_hex: str,
    outer_enc_iv_hex: str,
) -> str:
    """Encrypt a two-layer WBSK envelope."""
    # 1. Mystery-encode plaintext UTF-8 bytes + PKCS7 pad
    plain_buf = plaintext.encode("utf-8")
    inner_padded = _add_wbc_pkcs7(_wbc_input_encode(plain_buf))

    # 2. WBC encrypt CBC with inner key + IV
    inner_key = parse_wbc_key(inner_enc_key_hex)
    inner_iv = bytes.fromhex(inner_enc_iv_hex)
    inner_encrypted = _wbc_encrypt_cbc(inner_padded, inner_key["key_data"], inner_key["num_rounds"], inner_iv)

    # 3. Transform WBC output to raw domain -> base64
    inner_raw = _wbc_output_decode(inner_encrypted)
    inner_b64 = base64.b64encode(inner_raw).decode("ascii")

    # 4. Build outer content: base64 string + transform(innerEncIV), then mystery-encode
    outer_content_plain = inner_b64.encode("latin-1") + _wbc_output_decode(inner_iv)
    outer_mystery = _add_wbc_pkcs7(_wbc_input_encode(outer_content_plain))

    # 5. WBC encrypt CBC with outer key + IV
    outer_key = parse_wbc_key(outer_enc_key_hex)
    outer_iv = bytes.fromhex(outer_enc_iv_hex)
    outer_encrypted = _wbc_encrypt_cbc(outer_mystery, outer_key["key_data"], outer_key["num_rounds"], outer_iv)

    # 6. Transform WBC output to raw domain -> base64
    return base64.b64encode(_wbc_output_decode(outer_encrypted)).decode("ascii")


# ---------------------------------------------------------------------------
# Convenience wrappers using hardcoded keys
# ---------------------------------------------------------------------------

def encrypt_envelope(plaintext: str) -> str:
    """Encrypt a WBSK envelope using the default static keys."""
    return encrypt_wbsk_envelope(
        plaintext,
        WBSK_KEYS["inner_encrypt_key"],
        WBSK_KEYS["inner_encrypt_iv"],
        WBSK_KEYS["outer_encrypt_key"],
        WBSK_KEYS["outer_encrypt_iv"],
    )


def decrypt_envelope(base64_str: str) -> str:
    """Decrypt a WBSK envelope using the default static keys."""
    return decrypt_wbsk_envelope(
        base64_str,
        WBSK_KEYS["outer_decrypt_key"],
        WBSK_KEYS["inner_decrypt_key"],
        WBSK_KEYS["outer_decrypt_iv"],
    )
