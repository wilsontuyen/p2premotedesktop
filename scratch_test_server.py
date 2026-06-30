import socket
import struct
import json
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

def get_crypto_key(password):
    if not isinstance(password, str):
        if isinstance(password, (list, tuple)) and password:
            password = password[0]
        else:
            password = str(password)
    return hashlib.sha256(password.encode('utf-8')).digest()

def main():
    print("Test Server Listening on 12345...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', 12345))
    sock.listen(1)
    
    conn, addr = sock.accept()
    print(f"Accepted connection from {addr}")
    
    # We will try to decrypt with a hardcoded test password
    test_password = "123"
    
    # recv length
    length_bytes = b''
    while len(length_bytes) < 4:
        packet = conn.recv(4 - len(length_bytes))
        if not packet: break
        length_bytes += packet
        
    if len(length_bytes) < 4:
        print("Failed to read length")
        return
        
    length = struct.unpack('>I', length_bytes)[0]
    print(f"Received Length prefix: {length}")
    
    # recv data
    encrypted_data = b''
    while len(encrypted_data) < length:
        packet = conn.recv(length - len(encrypted_data))
        if not packet: break
        encrypted_data += packet
        
    print(f"Received encrypted data size: {len(encrypted_data)}")
    
    if len(encrypted_data) < 12:
        print("Data too short to contain nonce")
        return
        
    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]
    
    print(f"Nonce (hex): {nonce.hex()}")
    print(f"Ciphertext length: {len(ciphertext)}")
    
    key = get_crypto_key(test_password)
    chacha = ChaCha20Poly1305(key)
    
    try:
        plaintext = chacha.decrypt(nonce, ciphertext, None)
        print(f"SUCCESSFULLY DECRYPTED!")
        print(f"Plaintext: {plaintext.decode('utf-8')}")
    except Exception as e:
        print(f"DECRYPTION FAILED: {e}")
        
    conn.close()
    sock.close()

if __name__ == "__main__":
    main()
