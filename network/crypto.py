import hashlib
import struct
import threading
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

send_nonce_counter = 0
send_counter_lock = threading.Lock()

def get_crypto_key(password):
    if not isinstance(password, str):
        if isinstance(password, (list, tuple)) and password:
            password = password[0]
        else:
            password = str(password)
    return hashlib.sha256(password.encode('utf-8')).digest()

def encrypt_payload(data_bytes, password):
    global send_nonce_counter
    key = get_crypto_key(password)
    chacha = ChaCha20Poly1305(key)
    
    with send_counter_lock:
        send_nonce_counter += 1
        current_counter = send_nonce_counter
        
    nonce = struct.pack('>Q', current_counter) + b'\x00\x00\x00\x00'
    return nonce + chacha.encrypt(nonce, data_bytes, None)

def decrypt_payload(encrypted_bytes, password):
    passwords = [password] if isinstance(password, str) else list(password)
    passwords = [p for p in passwords if p]
    
    if len(encrypted_bytes) < 12:
        raise ValueError("Dữ liệu mã hóa không hợp lệ (kích thước quá nhỏ)")
    nonce = encrypted_bytes[:12]
    ciphertext = encrypted_bytes[12:]
    
    last_err = None
    for p in passwords:
        try:
            key = get_crypto_key(p)
            chacha = ChaCha20Poly1305(key)
            return chacha.decrypt(nonce, ciphertext, None)
        except Exception as e:
            last_err = e
    raise last_err if last_err else ValueError("Không giải mã được với bất kỳ mật khẩu nào")
