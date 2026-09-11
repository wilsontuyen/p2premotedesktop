import socket
import struct
import threading
import ipaddress
import select
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

def send_msg(sock, data_bytes, password=None, should_stop=None, lock_timeout=None):
    """Gửi 1 khung. Mặc định sendall (signaling/video). should_stop/lock_timeout chỉ dùng lúc gửi file/Hủy."""
    if should_stop and should_stop():
        return False
    if password is None:
        password = socket_passwords.get(sock, APP_KEY)
    lock = _get_socket_send_lock(sock)

    # Signaling, ping, video: giữ sendall như cũ. select() + lock sai indent làm mất đăng ký online.
    if should_stop is None and lock_timeout is None:
        try:
            with lock:
                encrypted_data = encrypt_payload(data_bytes, password)
                msg = struct.pack('>I', len(encrypted_data)) + encrypted_data
                sock.sendall(msg)
            return True
        except Exception as e:
            print(f"[Socket] Lỗi gửi dữ liệu: {e}")
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
        msg = struct.pack('>I', len(encrypted_data)) + encrypted_data
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
                n = sock.send(view[sent:sent + min(65536, len(msg) - sent)])
            except BlockingIOError:
                continue
            except InterruptedError:
                continue
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[Socket] Lỗi gửi dữ liệu: {e}")
                return False
            if n == 0:
                return False
            sent += n
        return True
    except Exception as e:
        print(f"[Socket] Lỗi gửi dữ liệu: {e}")
        return False
    finally:
        if acquired:
            try:
                lock.release()
            except Exception:
                pass

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
        return bool(addr.is_private or addr.is_loopback or addr.is_link_local)
    except Exception:
        return False

def is_lan_socket(sock):
    """True nếu peer là IP LAN/private (kết nối trực tiếp trong mạng nội bộ)."""
    if not sock:
        return False
    try:
        return is_private_ip(sock.getpeername()[0])
    except Exception:
        return False

def tune_socket_for_lan_bulk(sock):
    """Tăng cửa sổ TCP để copy file trên LAN sát băng thông local."""
    if not sock:
        return
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    except Exception:
        pass

def ensure_session_socket_blocking(sock):
    """Pygame/Tk trên Windows hay để socket FIONBIO → recv WinError 10035."""
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


def recv_exact(sock, length):
    data = b''
    while len(data) < length:
        try:
            packet = sock.recv(length - len(data))
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
