import socket
import struct
import threading
from .crypto import encrypt_payload, decrypt_payload

_socket_send_locks = {}
_socket_send_locks_meta = threading.Lock()
socket_passwords = {}
APP_KEY = "q3tu0y7j"

def _get_socket_send_lock(sock):
    with _socket_send_locks_meta:
        lock = _socket_send_locks.get(sock)
        if lock is None:
            lock = threading.Lock()
            _socket_send_locks[sock] = lock
        return lock

def force_close_socket(sock):
    if not sock: return
    try:
        import struct
        # Set SO_LINGER to abort the connection with RST to avoid TIME_WAIT
        linger = struct.pack('ii', 1, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
    except:
        pass
    try:
        sock.close()
    except:
        pass
    # Clean up per-socket lock to prevent memory leaks
    with _socket_send_locks_meta:
        _socket_send_locks.pop(sock, None)
    socket_passwords.pop(sock, None)

def send_msg(sock, data_bytes, password=None):
    if password is None:
        password = socket_passwords.get(sock, APP_KEY)
    try:
        lock = _get_socket_send_lock(sock)
        with lock:
            encrypted_data = encrypt_payload(data_bytes, password)
            msg = struct.pack('>I', len(encrypted_data)) + encrypted_data
            sock.sendall(msg)
    except Exception as e:
        print(f"[Socket] Lỗi gửi dữ liệu: {e}")

def recv_exact(sock, length):
    data = b''
    while len(data) < length:
        packet = sock.recv(length - len(data))
        if not packet:
            return None
        data += packet
    return data

def recv_msg(sock, password=None):
    if password is None:
        password = socket_passwords.get(sock, APP_KEY)
    length_bytes = recv_exact(sock, 4)
    if not length_bytes:
        return None
    length = struct.unpack('>I', length_bytes)[0]
    encrypted_data = recv_exact(sock, length)
    if not encrypted_data:
        return None
    try:
        return decrypt_payload(encrypted_data, password)
    except Exception as e:
        print(f"[Socket] Lỗi giải mã dữ liệu: {e}")
        return b''
