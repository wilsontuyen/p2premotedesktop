import socket
import json
import struct
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

APP_KEY = "q3tu0y7j"
send_nonce_counter = 0

def get_crypto_key(password):
    return hashlib.sha256(password.encode('utf-8')).digest()

def encrypt_payload(data_bytes, password):
    global send_nonce_counter
    key = get_crypto_key(password)
    chacha = ChaCha20Poly1305(key)
    send_nonce_counter += 1
    nonce = struct.pack('>Q', send_nonce_counter) + b'\x00\x00\x00\x00'
    return nonce + chacha.encrypt(nonce, data_bytes, None)

def decrypt_payload(encrypted_bytes, password):
    nonce = encrypted_bytes[:12]
    ciphertext = encrypted_bytes[12:]
    key = get_crypto_key(password)
    chacha = ChaCha20Poly1305(key)
    return chacha.decrypt(nonce, ciphertext, None)

def send_msg(sock, data_bytes, password):
    encrypted_data = encrypt_payload(data_bytes, password)
    msg = struct.pack('>I', len(encrypted_data)) + encrypted_data
    sock.sendall(msg)

def recv_exact(sock, length):
    data = b''
    while len(data) < length:
        packet = sock.recv(length - len(data))
        if not packet:
            return None
        data += packet
    return data

def recv_msg(sock, password):
    length_bytes = recv_exact(sock, 4)
    if not length_bytes: return None
    length = struct.unpack('>I', length_bytes)[0]
    encrypted_data = recv_exact(sock, length)
    return decrypt_payload(encrypted_data, password)

import threading
import time

def test_signaling():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('127.0.0.1', 8765))
    
    req = json.dumps({"action": "register", "hwid": "TEST_CLIENT_1"})
    send_msg(sock, req.encode('utf-8'), APP_KEY)
    
    ping_req = json.dumps({"action": "ping"})
    send_msg(sock, ping_req.encode('utf-8'), APP_KEY)
    
    res_bytes = recv_msg(sock, APP_KEY)
    print("Response:", res_bytes.decode('utf-8'))
    
    sock.close()

if __name__ == '__main__':
    test_signaling()
