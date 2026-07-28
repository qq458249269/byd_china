"""White-box AES block cipher and CBC mode for Bangcle envelopes.

The cipher uses pre-computed lookup tables extracted from
libencrypt.so rather than a standard AES key schedule.
"""

from __future__ import annotations

import struct
from typing import NamedTuple


class BangcleTables(NamedTuple):
    """Lookup tables for the white-box AES cipher."""

    inv_round: bytes  # 0x28000 bytes
    inv_xor: bytes  # 0x3c000 bytes
    inv_first: bytes  # 0x1000 bytes
    round: bytes  # 0x28000 bytes
    xor: bytes  # 0x3c000 bytes
    final: bytes  # 0x1000 bytes
    perm_decrypt: bytes  # 8 bytes
    perm_encrypt: bytes  # 8 bytes


def _prepare_aes_matrix(input_block: bytes | bytearray, output: bytearray) -> None:
    """Transpose 4x4 block into working state layout (col*8+row)."""
    for col in range(4):
        for row in range(4):
            output[col * 8 + row] = input_block[col + row * 4]


def decrypt_block_auth(
    tables: BangcleTables,
    block: bytes | bytearray,
    round_start: int = 1,
) -> bytes:
    """Decrypt a single 16-byte block using white-box AES tables."""
    state = bytearray(32)
    temp64 = bytearray(64)
    tmp32 = bytearray(32)
    output = bytearray(16)

    _prepare_aes_matrix(block, state)
    param3 = round_start

    for rnd in range(9, max(0, param3 - 1), -1):
        l_var20 = rnd
        l_var21 = l_var20 * 4
        perm_ptr = 0

        for i in range(4):
            b_var3 = tables.perm_decrypt[perm_ptr]
            l_var16 = i * 8
            base = i * 16

            for j in range(4):
                u_var7 = (b_var3 + j) & 3
                byte_val = state[l_var16 + u_var7]
                idx = byte_val + (i + (l_var21 + u_var7) * 4) * 256
                value = struct.unpack_from("<I", tables.inv_round, idx * 4)[0]
                struct.pack_into("<I", temp64, base + j * 4, value)

            perm_ptr += 2

        i_var15 = 1
        for l_var21_xor in range(4):
            pb_var18_offset = l_var21_xor

            for l_var9_xor in range(4):
                local10 = temp64[pb_var18_offset]
                u_var6 = local10 & 0xF
                u_var26 = local10 & 0xF0

                local_f0 = temp64[pb_var18_offset + 0x10]
                local_f1 = temp64[pb_var18_offset + 0x20]
                local_f2 = temp64[pb_var18_offset + 0x30]

                l_var2 = l_var9_xor * 0x18 + l_var20 * 0x60
                i_var25 = i_var15

                for l_var16 in range(3):
                    if l_var16 == 0:
                        b_var3_inner = local_f0
                    elif l_var16 == 1:
                        b_var3_inner = local_f1
                    else:
                        b_var3_inner = local_f2

                    u_var1 = (b_var3_inner << 4) & 0xFF
                    u_var27 = u_var6 | u_var1
                    u_var26 = ((u_var26 >> 4) | ((b_var3_inner >> 4) << 4)) & 0xFF

                    idx1 = (l_var2 + (i_var25 - 1)) * 0x100 + u_var27
                    u_var6 = tables.inv_xor[idx1] & 0xF

                    idx2 = (l_var2 + i_var25) * 0x100 + u_var26
                    b_var3_new = tables.inv_xor[idx2]
                    u_var26 = (b_var3_new & 0xF) << 4
                    i_var25 += 2

                state[l_var9_xor + l_var21_xor * 8] = (u_var26 | u_var6) & 0xFF
                pb_var18_offset += 4

            i_var15 += 6

    if param3 == 1:
        tmp32[:] = state[:]
        u_var8 = 1
        u_var10 = 3
        u_var12 = 2

        for row in range(4):
            idx0 = tmp32[row] + row * 0x400
            state[row] = tables.inv_first[idx0]

            row1 = u_var10 & 3
            idx1 = tmp32[8 + row1] + row1 * 0x400 + 0x100
            state[8 + row] = tables.inv_first[idx1]

            row2 = u_var12 & 3
            idx2 = tmp32[0x10 + row2] + row2 * 0x400 + 0x200
            state[0x10 + row] = tables.inv_first[idx2]

            row3 = u_var8 & 3
            idx3 = tmp32[0x18 + row3] + row3 * 0x400 + 0x300
            state[0x18 + row] = tables.inv_first[idx3]

            u_var8 += 1
            u_var10 += 1
            u_var12 += 1

    for col in range(4):
        for row in range(4):
            output[col + row * 4] = state[col * 8 + row]

    return bytes(output)


def encrypt_block_auth(
    tables: BangcleTables,
    block: bytes | bytearray,
    round_end: int = 10,
) -> bytes:
    """Encrypt a single 16-byte block using white-box AES tables."""
    state = bytearray(32)
    temp64 = bytearray(64)
    tmp32 = bytearray(32)
    output = bytearray(16)

    _prepare_aes_matrix(block, state)
    param3 = round_end

    rounds = min(9, max(0, param3))
    for rnd in range(rounds):
        l_var21 = rnd * 4
        perm_ptr = 0

        for i in range(4):
            b_var4 = tables.perm_encrypt[perm_ptr]
            l_var16 = i * 8
            base = i * 16

            for j in range(4):
                u_var8 = (b_var4 + j) & 3
                byte_val = state[l_var16 + u_var8]
                idx = byte_val + (i + (l_var21 + u_var8) * 4) * 256
                value = struct.unpack_from("<I", tables.round, idx * 4)[0]
                struct.pack_into("<I", temp64, base + j * 4, value)

            perm_ptr += 2

        i_var16 = 1
        for l_var22 in range(4):
            pb_var19_offset = l_var22

            for l_var10 in range(4):
                local10 = temp64[pb_var19_offset]
                u_var7 = local10 & 0xF
                u_var26 = local10 & 0xF0

                local_f0 = temp64[pb_var19_offset + 0x10]
                local_f1 = temp64[pb_var19_offset + 0x20]
                local_f2 = temp64[pb_var19_offset + 0x30]

                l_var2 = l_var10 * 0x18 + rnd * 0x60
                i_var25 = i_var16

                for l_var17 in range(3):
                    if l_var17 == 0:
                        b_var4_inner = local_f0
                    elif l_var17 == 1:
                        b_var4_inner = local_f1
                    else:
                        b_var4_inner = local_f2

                    u_var1 = (b_var4_inner << 4) & 0xFF
                    u_var27 = u_var7 | u_var1
                    u_var26 = ((u_var26 >> 4) | ((b_var4_inner >> 4) << 4)) & 0xFF

                    idx1 = (l_var2 + (i_var25 - 1)) * 0x100 + u_var27
                    u_var7 = tables.xor[idx1] & 0xF

                    idx2 = (l_var2 + i_var25) * 0x100 + u_var26
                    b_var4_new = tables.xor[idx2]
                    u_var26 = (b_var4_new & 0xF) << 4
                    i_var25 += 2

                state[l_var10 + l_var22 * 8] = (u_var26 | u_var7) & 0xFF
                pb_var19_offset += 4

            i_var16 += 6

    if param3 == 10:
        tmp32[:] = state[:]
        u_var13 = 3
        u_var9 = 2
        u_var11 = 1
        u_var8_enc = 0

        for row in range(4):
            row0 = (u_var8_enc + row) & 3
            state[row] = tables.final[tmp32[row0] + row0 * 0x400]

            row1 = (u_var11 + row) & 3
            state[8 + row] = tables.final[tmp32[8 + row1] + row1 * 0x400 + 0x100]

            row2 = (u_var9 + row) & 3
            state[0x10 + row] = tables.final[tmp32[0x10 + row2] + row2 * 0x400 + 0x200]

            row3 = (u_var13 + row) & 3
            state[0x18 + row] = tables.final[tmp32[0x18 + row3] + row3 * 0x400 + 0x300]

    for col in range(4):
        for row in range(4):
            output[col + row * 4] = state[col * 8 + row]

    return bytes(output)


def _xor_into(target: bytearray, source: bytes | bytearray) -> None:
    """XOR source into target in-place."""
    for i in range(len(target)):
        target[i] ^= source[i]


def decrypt_cbc(tables: BangcleTables, data: bytes, iv: bytes) -> bytes:
    """Decrypt data using white-box AES in CBC mode."""
    if len(data) % 16 != 0:
        raise ValueError(f"Ciphertext length {len(data)} is not a multiple of 16")
    if len(iv) != 16:
        raise ValueError(f"IV must be 16 bytes, got {len(iv)}")

    result = bytearray(len(data))
    prev = bytearray(iv)

    for offset in range(0, len(data), 16):
        block = data[offset : offset + 16]
        decrypted = bytearray(decrypt_block_auth(tables, block, 1))
        _xor_into(decrypted, prev)
        result[offset : offset + 16] = decrypted
        prev[:] = block

    return bytes(result)


def encrypt_cbc(tables: BangcleTables, data: bytes, iv: bytes) -> bytes:
    """Encrypt data using white-box AES in CBC mode."""
    if len(data) % 16 != 0:
        raise ValueError(f"Plaintext length {len(data)} is not a multiple of 16")
    if len(iv) != 16:
        raise ValueError(f"IV must be 16 bytes, got {len(iv)}")

    result = bytearray(len(data))
    prev = bytearray(iv)

    for offset in range(0, len(data), 16):
        block = bytearray(data[offset : offset + 16])
        _xor_into(block, prev)
        encrypted = encrypt_block_auth(tables, block, 10)
        result[offset : offset + 16] = encrypted
        prev[:] = encrypted

    return bytes(result)
