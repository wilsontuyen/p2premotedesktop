# -*- coding: utf-8 -*-
"""
xp_host/xp_socket.py
Đóng gói gói tin TCP 4-byte framing + ChaCha20-Poly1305 tối ưu cho Winsock Windows XP.
Giảm SO_SNDBUF / SO_RCVBUF xuống 512 KB (thay vì 4 MB) để không làm cạn kiệt
Kernel Non-Paged Pool của nhân Windows XP 32-bit.
"""

import ipaddress
import select
import socket
import struct
import threading

from .xp_crypto import decrypt_payload, encrypt_payload

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
    if not sock:
        return
    try:
        linger = struct.pack("ii", 1, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
    except Exception:
        pass
    try:
        sock.close()
    except Exception:
        pass
    with _socket_send_locks_meta:
        _socket_send_locks.pop(sock, None)
    socket_passwords.pop(sock, None)


def _is_disconnect_error(e):
    if isinstance(e, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return True
    err_str = str(e)
    return any(code in err_str for code in ("10053", "10054", "10058", "10038", "WSAECONNABORTED", "WSAECONNRESET"))


def is_private_ip(ip):
    if not ip:
        return False
    if isinstance(ip, bytes):
        try:
            ip = ip.decode("ascii")
        except Exception:
            return False
    if ip.startswith("::ffff:"):
        ip = ip[7:]
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            return True
        if addr.version == 4:
            octs = [int(x) for x in ip.split(".")]
            if len(octs) == 4:
                if octs[0] in (25, 26):  # Hamachi / Radmin VPN
                    return True
                if octs[0] == 100 and (64 <= octs[1] <= 127):  # Tailscale CGNAT
                    return True
        return False
    except Exception:
        return False


def is_lan_socket(sock):
    if not sock:
        return False
    try:
        return is_private_ip(sock.getpeername()[0])
    except Exception:
        return False


def tune_socket_for_xp_lan(sock):
    """Tối ưu buffer TCP 512KB an toàn cho nhân Windows XP 32-bit."""
    if not sock:
        return
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception:
        pass
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 512 * 1024)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 512 * 1024)
    except Exception:
        pass


def set_xp_keepalive(sock, idle_ms=15000, interval_ms=5000):
    if not sock:
        return
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sio_keepalive = getattr(socket, "SIO_KEEPALIVE_VALS", 0x98000004)
        if hasattr(sock, "ioctl"):
            sock.ioctl(sio_keepalive, (1, int(idle_ms), int(interval_ms)))
    except Exception:
        pass


def ensure_session_socket_blocking(sock):
    if not sock:
        return
    try:
        sock.settimeout(None)
    except Exception:
        pass
    try:
        sock.setblocking(True)
    except Exception:
        pass


def send_msg(sock, data_bytes, password=None, should_stop=None, lock_timeout=None):
    if should_stop and should_stop():
        return False
    if password is None:
        password = socket_passwords.get(sock, APP_KEY)
    lock = _get_socket_send_lock(sock)

    if should_stop is None and lock_timeout is None:
        try:
            with lock:
                encrypted_data = encrypt_payload(data_bytes, password)
                msg = struct.pack(">I", len(encrypted_data)) + encrypted_data
                sock.sendall(msg)
            return True
        except Exception as e:
            if not _is_disconnect_error(e):
                print(f"[XP Socket] Send error: {e}")
            return False

    acquired = False
    try:
        if should_stop:
            while True:
                if should_stop():
                    return False
                acquired = lock.acquire(timeout=0.2)
                if acquired:
                    break
        else:
            acquired = lock.acquire(timeout=float(lock_timeout))
            if not acquired:
                return False

        encrypted_data = encrypt_payload(data_bytes, password)
        msg = struct.pack(">I", len(encrypted_data)) + encrypted_data
        view = memoryview(msg)
        sent = 0
        while sent < len(msg):
            if sent == 0 and should_stop and should_stop():
                return False
            try:
                writable = select.select([], [sock], [], 0.2)[1]
            except Exception:
                writable = [sock]
            if not writable:
                continue
            try:
                n = sock.send(view[sent:sent + min(32768, len(msg) - sent)])
            except (BlockingIOError, InterruptedError, socket.timeout):
                continue
            except Exception as e:
                if not _is_disconnect_error(e):
                    print(f"[XP Socket] Send chunk error: {e}")
                return False
            if n == 0:
                return False
            sent += n
        return True
    except Exception as e:
        if not _is_disconnect_error(e):
            print(f"[XP Socket] Send error: {e}")
        return False
    finally:
        if acquired:
            try:
                lock.release()
            except Exception:
                pass


def recv_exact(sock, length):
    data = bytearray()
    while len(data) < length:
        try:
            packet = sock.recv(min(65536, length - len(data)))
        except BlockingIOError:
            ensure_session_socket_blocking(sock)
            try:
                select.select([sock], [], [], 0.25)
            except Exception:
                pass
            continue
        except InterruptedError:
            continue
        if not packet:
            return None
        data.extend(packet)
    return bytes(data)


def recv_msg(sock, password=None, max_size=32 * 1024 * 1024):
    if password is None:
        password = socket_passwords.get(sock, APP_KEY)
    length_bytes = recv_exact(sock, 4)
    if not length_bytes:
        return None
    length = struct.unpack(">I", length_bytes)[0]
    if length <= 0 or (max_size and length > max_size):
        return None
    encrypted_data = recv_exact(sock, length)
    if not encrypted_data:
        return None
    try:
        return decrypt_payload(encrypted_data, password)
    except Exception as e:
        print(f"[XP Socket] Decrypt error: {e}")
        return b""
