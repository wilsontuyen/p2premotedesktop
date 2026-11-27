# -*- coding: utf-8 -*-
"""
xp_host/xp_crypto.py
Mã hóa đường truyền RFC 8439 ChaCha20-Poly1305 cho Windows XP (32-bit).
Tương thích byte-for-byte 100% với network/crypto.py và signaling_server.py:
  key   = SHA-256(password.encode('utf-8')) (32 bytes)
  nonce = struct.pack('>Q', counter) + b'\\x00\\x00\\x00\\x00' (12 bytes)
  wire  = nonce (12B) + ciphertext + tag (16B)  (AAD = None / b'')

Thứ tự ưu tiên backend tự động (không phụ thuộc Rust hay bcrypt.dll của Vista+):
  1. pycryptodomex (Cryptodome.Cipher.ChaCha20_Poly1305 - C extension chạy mượt trên XP x86)
  2. pycryptodome  (Crypto.Cipher.ChaCha20_Poly1305)
  3. cryptography  (khi chạy kiểm thử trên máy dev Windows 10/11)
  4. Pure-Python RFC 8439 ChaCha20-Poly1305 tích hợp sẵn (chạy được ngay cả khi không có C wheel)
"""

import hashlib
import hmac
import struct
import threading

send_nonce_counter = 0
send_counter_lock = threading.Lock()
_key_cache = {}
_key_cache_lock = threading.Lock()

# Phát hiện backend C tốc độ cao tương thích XP
_BACKEND = "pure_python"
_CryptodomeChaCha = None
_CryptographyChaCha = None

try:
    from Cryptodome.Cipher import ChaCha20_Poly1305 as _CryptodomeChaCha  # type: ignore
    _BACKEND = "pycryptodomex"
except Exception:
    try:
        from Crypto.Cipher import ChaCha20_Poly1305 as _CryptodomeChaCha  # type: ignore
        _BACKEND = "pycryptodome"
    except Exception:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305 as _CryptographyChaCha  # type: ignore
            _BACKEND = "cryptography"
        except Exception:
            _BACKEND = "pure_python"


def get_crypto_backend():
    return _BACKEND


def get_crypto_key(password):
    if not isinstance(password, str):
        if isinstance(password, (list, tuple)) and password:
            password = password[0]
        else:
            password = str(password)
    with _key_cache_lock:
        cached = _key_cache.get(password)
        if cached is not None:
            return cached
        digest = hashlib.sha256(password.encode("utf-8")).digest()
        if len(_key_cache) > 128:
            _key_cache.clear()
        _key_cache[password] = digest
        return digest


# ==============================================================================
# Pure-Python RFC 8439 ChaCha20-Poly1305 Fallback (Zero External Dependencies)
# ==============================================================================
_CHACHA_CONSTANTS = (0x61707865, 0x3320646E, 0x79622D32, 0x6B206574)
_POLY1305_P = (1 << 130) - 5


def _chacha20_block(key_words, counter, nonce_words):
    s0, s1, s2, s3 = _CHACHA_CONSTANTS
    s4, s5, s6, s7, s8, s9, s10, s11 = key_words
    s12 = counter & 0xFFFFFFFF
    s13, s14, s15 = nonce_words

    x0, x1, x2, x3 = s0, s1, s2, s3
    x4, x5, x6, x7 = s4, s5, s6, s7
    x8, x9, x10, x11 = s8, s9, s10, s11
    x12, x13, x14, x15 = s12, s13, s14, s15

    for _ in range(10):
        # Column rounds
        x0 = (x0 + x4) & 0xFFFFFFFF; x12 ^= x0; x12 = ((x12 << 16) | (x12 >> 16)) & 0xFFFFFFFF
        x8 = (x8 + x12) & 0xFFFFFFFF; x4 ^= x8; x4 = ((x4 << 12) | (x4 >> 20)) & 0xFFFFFFFF
        x0 = (x0 + x4) & 0xFFFFFFFF; x12 ^= x0; x12 = ((x12 << 8) | (x12 >> 24)) & 0xFFFFFFFF
        x8 = (x8 + x12) & 0xFFFFFFFF; x4 ^= x8; x4 = ((x4 << 7) | (x4 >> 25)) & 0xFFFFFFFF

        x1 = (x1 + x5) & 0xFFFFFFFF; x13 ^= x1; x13 = ((x13 << 16) | (x13 >> 16)) & 0xFFFFFFFF
        x9 = (x9 + x13) & 0xFFFFFFFF; x5 ^= x9; x5 = ((x5 << 12) | (x5 >> 20)) & 0xFFFFFFFF
        x1 = (x1 + x5) & 0xFFFFFFFF; x13 ^= x1; x13 = ((x13 << 8) | (x13 >> 24)) & 0xFFFFFFFF
        x9 = (x9 + x13) & 0xFFFFFFFF; x5 ^= x9; x5 = ((x5 << 7) | (x5 >> 25)) & 0xFFFFFFFF

        x2 = (x2 + x6) & 0xFFFFFFFF; x14 ^= x2; x14 = ((x14 << 16) | (x14 >> 16)) & 0xFFFFFFFF
        x10 = (x10 + x14) & 0xFFFFFFFF; x6 ^= x10; x6 = ((x6 << 12) | (x6 >> 20)) & 0xFFFFFFFF
        x2 = (x2 + x6) & 0xFFFFFFFF; x14 ^= x2; x14 = ((x14 << 8) | (x14 >> 24)) & 0xFFFFFFFF
        x10 = (x10 + x14) & 0xFFFFFFFF; x6 ^= x10; x6 = ((x6 << 7) | (x6 >> 25)) & 0xFFFFFFFF

        x3 = (x3 + x7) & 0xFFFFFFFF; x15 ^= x3; x15 = ((x15 << 16) | (x15 >> 16)) & 0xFFFFFFFF
        x11 = (x11 + x15) & 0xFFFFFFFF; x7 ^= x11; x7 = ((x7 << 12) | (x7 >> 20)) & 0xFFFFFFFF
        x3 = (x3 + x7) & 0xFFFFFFFF; x15 ^= x3; x15 = ((x15 << 8) | (x15 >> 24)) & 0xFFFFFFFF
        x11 = (x11 + x15) & 0xFFFFFFFF; x7 ^= x11; x7 = ((x7 << 7) | (x7 >> 25)) & 0xFFFFFFFF

        # Diagonal rounds
        x0 = (x0 + x5) & 0xFFFFFFFF; x15 ^= x0; x15 = ((x15 << 16) | (x15 >> 16)) & 0xFFFFFFFF
        x10 = (x10 + x15) & 0xFFFFFFFF; x5 ^= x10; x5 = ((x5 << 12) | (x5 >> 20)) & 0xFFFFFFFF
        x0 = (x0 + x5) & 0xFFFFFFFF; x15 ^= x0; x15 = ((x15 << 8) | (x15 >> 24)) & 0xFFFFFFFF
        x10 = (x10 + x15) & 0xFFFFFFFF; x5 ^= x10; x5 = ((x5 << 7) | (x5 >> 25)) & 0xFFFFFFFF

        x1 = (x1 + x6) & 0xFFFFFFFF; x12 ^= x1; x12 = ((x12 << 16) | (x12 >> 16)) & 0xFFFFFFFF
        x11 = (x11 + x12) & 0xFFFFFFFF; x6 ^= x11; x6 = ((x6 << 12) | (x6 >> 20)) & 0xFFFFFFFF
        x1 = (x1 + x6) & 0xFFFFFFFF; x12 ^= x1; x12 = ((x12 << 8) | (x12 >> 24)) & 0xFFFFFFFF
        x11 = (x11 + x12) & 0xFFFFFFFF; x6 ^= x11; x6 = ((x6 << 7) | (x6 >> 25)) & 0xFFFFFFFF

        x2 = (x2 + x7) & 0xFFFFFFFF; x13 ^= x2; x13 = ((x13 << 16) | (x13 >> 16)) & 0xFFFFFFFF
        x8 = (x8 + x13) & 0xFFFFFFFF; x7 ^= x8; x7 = ((x7 << 12) | (x7 >> 20)) & 0xFFFFFFFF
        x2 = (x2 + x7) & 0xFFFFFFFF; x13 ^= x2; x13 = ((x13 << 8) | (x13 >> 24)) & 0xFFFFFFFF
        x8 = (x8 + x13) & 0xFFFFFFFF; x7 ^= x8; x7 = ((x7 << 7) | (x7 >> 25)) & 0xFFFFFFFF

        x3 = (x3 + x4) & 0xFFFFFFFF; x14 ^= x3; x14 = ((x14 << 16) | (x14 >> 16)) & 0xFFFFFFFF
        x9 = (x9 + x14) & 0xFFFFFFFF; x4 ^= x9; x4 = ((x4 << 12) | (x4 >> 20)) & 0xFFFFFFFF
        x3 = (x3 + x4) & 0xFFFFFFFF; x14 ^= x3; x14 = ((x14 << 8) | (x14 >> 24)) & 0xFFFFFFFF
        x9 = (x9 + x14) & 0xFFFFFFFF; x4 ^= x9; x4 = ((x4 << 7) | (x4 >> 25)) & 0xFFFFFFFF

    return struct.pack(
        "<16I",
        (x0 + s0) & 0xFFFFFFFF, (x1 + s1) & 0xFFFFFFFF, (x2 + s2) & 0xFFFFFFFF, (x3 + s3) & 0xFFFFFFFF,
        (x4 + s4) & 0xFFFFFFFF, (x5 + s5) & 0xFFFFFFFF, (x6 + s6) & 0xFFFFFFFF, (x7 + s7) & 0xFFFFFFFF,
        (x8 + s8) & 0xFFFFFFFF, (x9 + s9) & 0xFFFFFFFF, (x10 + s10) & 0xFFFFFFFF, (x11 + s11) & 0xFFFFFFFF,
        (x12 + s12) & 0xFFFFFFFF, (x13 + s13) & 0xFFFFFFFF, (x14 + s14) & 0xFFFFFFFF, (x15 + s15) & 0xFFFFFFFF,
    )


def _chacha20_xor(key_words, counter, nonce_words, data):
    n = len(data)
    if n == 0:
        return b""
    out = bytearray(n)
    mv = memoryview(data)
    pos = 0
    blk = counter
    while pos < n:
        ks = _chacha20_block(key_words, blk, nonce_words)
        blk = (blk + 1) & 0xFFFFFFFF
        rem = n - pos
        if rem >= 64:
            # XOR theo khối 8-byte (uint64) nhanh gấp ~8 lần vòng lặp từng byte trên Python 32-bit
            d_u64 = struct.unpack_from("<8Q", mv, pos)
            k_u64 = struct.unpack("<8Q", ks)
            struct.pack_into(
                "<8Q", out, pos,
                d_u64[0] ^ k_u64[0], d_u64[1] ^ k_u64[1], d_u64[2] ^ k_u64[2], d_u64[3] ^ k_u64[3],
                d_u64[4] ^ k_u64[4], d_u64[5] ^ k_u64[5], d_u64[6] ^ k_u64[6], d_u64[7] ^ k_u64[7],
            )
            pos += 64
        else:
            for i in range(rem):
                out[pos + i] = mv[pos + i] ^ ks[i]
            pos += rem
    return bytes(out)


def _poly1305_aead_tag(otk, ciphertext):
    r = int.from_bytes(otk[:16], "little") & 0x0FFFFFFC0FFFFFFC0FFFFFFC0FFFFFFF
    s = int.from_bytes(otk[16:32], "little")
    ct_len = len(ciphertext)
    pad_len = (16 - (ct_len % 16)) % 16
    mac_data = ciphertext + (b"\x00" * pad_len) + struct.pack("<QQ", 0, ct_len)
    acc = 0
    hi_bit = 1 << 128
    p = _POLY1305_P
    mv = memoryview(mac_data)
    for off in range(0, len(mac_data), 16):
        val = int.from_bytes(mv[off:off + 16], "little") | hi_bit
        acc = ((acc + val) * r) % p
    tag_int = (acc + s) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    return tag_int.to_bytes(16, "little")


def pure_chacha20_poly1305_encrypt(key, nonce, data_bytes):
    key_words = struct.unpack("<8I", key)
    nonce_words = struct.unpack("<3I", nonce)
    otk = _chacha20_block(key_words, 0, nonce_words)[:32]
    ct = _chacha20_xor(key_words, 1, nonce_words, data_bytes)
    tag = _poly1305_aead_tag(otk, ct)
    return ct + tag


def pure_chacha20_poly1305_decrypt(key, nonce, ct_and_tag):
    if len(ct_and_tag) < 16:
        raise ValueError("Invalid ChaCha20-Poly1305 ciphertext length")
    ct = ct_and_tag[:-16]
    tag = ct_and_tag[-16:]
    key_words = struct.unpack("<8I", key)
    nonce_words = struct.unpack("<3I", nonce)
    otk = _chacha20_block(key_words, 0, nonce_words)[:32]
    expected_tag = _poly1305_aead_tag(otk, ct)
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("ChaCha20-Poly1305 authentication tag mismatch")
    return _chacha20_xor(key_words, 1, nonce_words, ct)


# ==============================================================================
# Public API (Drop-in replacement for network/crypto.py)
# ==============================================================================
def encrypt_payload(data_bytes, password):
    global send_nonce_counter
    key = get_crypto_key(password)
    with send_counter_lock:
        send_nonce_counter += 1
        current_counter = send_nonce_counter
    nonce = struct.pack(">Q", current_counter) + b"\x00\x00\x00\x00"

    if _CryptodomeChaCha is not None:
        cipher = _CryptodomeChaCha.new(key=key, nonce=nonce)
        ct, tag = cipher.encrypt_and_digest(data_bytes)
        return nonce + ct + tag
    if _CryptographyChaCha is not None:
        return nonce + _CryptographyChaCha(key).encrypt(nonce, data_bytes, None)
    return nonce + pure_chacha20_poly1305_encrypt(key, nonce, data_bytes)


def decrypt_payload(encrypted_bytes, password):
    passwords = [password] if isinstance(password, str) else list(password or [])
    passwords = [p for p in passwords if p]

    if len(encrypted_bytes) < 28:  # 12B nonce + >=0B ct + 16B tag
        raise ValueError("Encrypted payload too short")
    nonce = encrypted_bytes[:12]
    body = encrypted_bytes[12:]

    last_err = None
    for p in passwords:
        try:
            key = get_crypto_key(p)
            if _CryptodomeChaCha is not None:
                cipher = _CryptodomeChaCha.new(key=key, nonce=nonce)
                return cipher.decrypt_and_verify(body[:-16], body[-16:])
            if _CryptographyChaCha is not None:
                return _CryptographyChaCha(key).decrypt(nonce, body, None)
            return pure_chacha20_poly1305_decrypt(key, nonce, body)
        except Exception as e:
            last_err = e
    raise last_err if last_err else ValueError("Unable to decrypt payload with any candidate password")
