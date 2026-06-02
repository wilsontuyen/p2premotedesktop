import socket
import threading
import json
import sys
import time
import hashlib
import os
import struct
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

APP_KEY = "q3tu0y7j"
send_nonce_counter = 0
send_counter_lock = threading.Lock()

# Per-client send locks to eliminate global deadlock
client_send_locks = {}
client_send_locks_lock = threading.Lock()

def get_send_lock(sock):
    with client_send_locks_lock:
        if sock not in client_send_locks:
            client_send_locks[sock] = threading.Lock()
        return client_send_locks[sock]

def remove_send_lock(sock):
    with client_send_locks_lock:
        client_send_locks.pop(sock, None)

# TỐI ƯU RAM: Lưu cache các key đã băm để CPU không phải tính lại SHA256 liên tục
_key_cache = {}
def get_crypto_key(password):
    if password not in _key_cache:
        _key_cache[password] = hashlib.sha256(password.encode('utf-8')).digest()
    return _key_cache[password]

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
    if len(encrypted_bytes) < 12:
        raise ValueError("Dữ liệu mã hóa không hợp lệ")
    nonce = encrypted_bytes[:12]
    ciphertext = encrypted_bytes[12:]
    key = get_crypto_key(password)
    chacha = ChaCha20Poly1305(key)
    return chacha.decrypt(nonce, ciphertext, None)

def send_msg(sock, data_bytes, password):
    try:
        lock = get_send_lock(sock)
        with lock:
            encrypted_data = encrypt_payload(data_bytes, password)
            msg = struct.pack('>I', len(encrypted_data)) + encrypted_data
            sock.sendall(msg)
    except Exception:
        pass

def recv_exact(sock, length):
    data = b''
    while len(data) < length:
        try:
            packet = sock.recv(length - len(data))
            if not packet:
                return None
            data += packet
        except Exception:
            return None
    return data

def recv_msg(sock, password):
    length_bytes = recv_exact(sock, 4)
    if not length_bytes:
        return None
    length = struct.unpack('>I', length_bytes)[0]
    
    # BẢO MẬT: Giới hạn kích thước gói tin tối đa 64KB để chống DDoS tràn bộ nhớ
    if length > 65536: 
        return None
        
    encrypted_data = recv_exact(sock, length)
    if not encrypted_data:
        return None
    try:
        return decrypt_payload(encrypted_data, password)
    except Exception:
        return b''

class TeeLogger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.at_line_start = True
        try:
            self.log = open(filename, "a", encoding="utf-8", buffering=1)
        except:
            self.log = None

    def write(self, message):
        if not message: return
        formatted_message = ""
        lines = message.split('\n')
        for i, line in enumerate(lines):
            if i > 0:
                formatted_message += '\n'
                self.at_line_start = True
            if line:
                if self.at_line_start:
                    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S] ")
                    formatted_message += timestamp
                    self.at_line_start = False
                formatted_message += line

        if self.terminal:
            try: self.terminal.write(formatted_message)
            except: pass
        if self.log:
            try: self.log.write(formatted_message)
            except: pass

    def flush(self):
        if self.terminal:
            try: self.terminal.flush()
            except: pass
        if self.log:
            try: self.log.flush()
            except: pass

sys.stdout = TeeLogger("signaling_log.txt")
sys.stderr = sys.stdout

clients = {}
clients_lock = threading.Lock()

relay_pairs = {}
relay_lock = threading.Lock()

def format_session_id(session_id):
    parts = session_id.split('_')
    if len(parts) >= 3 and parts[0] == "relay":
        return f"{parts[1]} vs {parts[2]}"
    return session_id

def set_keepalive(sock):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        if os.name == 'nt':
            sock.ioctl(socket.SIOC_KEEPALIVE_VALS, (1, 30000, 10000))
        else:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 5)
    except Exception:
        pass

def cleanup_stale_relays():
    while True:
        time.sleep(30)
        now = time.time()
        stale_sessions = []
        with relay_lock:
            for session_id, info in list(relay_pairs.items()):
                if now - info.get("created_at", 0) > 30:
                    if info["host"] is None or info["client"] is None:
                        stale_sessions.append((session_id, info["host"], info["client"]))
            
            for session_id, host_conn, client_conn in stale_sessions:
                if session_id in relay_pairs:
                    del relay_pairs[session_id]
                if host_conn:
                    try: host_conn.close()
                    except: pass
                if client_conn:
                    try: client_conn.close()
                    except: pass
                session_display = format_session_id(session_id)
                print(f"[Relay] Đã dọn dẹp session mồ côi quá hạn: {session_display}")

def pipe_sockets(src, dst, session_id, closed_flag, lock):
    try:
        while True:
            data = src.recv(65536)
            if not data: break
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass
        
        with lock:
            if not closed_flag[0]:
                closed_flag[0] = True
                session_display = format_session_id(session_id)
                print(f"[Relay] Đã đóng session: {session_display}")

def handle_relay_connection(conn, role, session_id):
    session_display = format_session_id(session_id)
    print(f"[Relay] {role} kết nối cho session: {session_display}")
    with relay_lock:
        if session_id not in relay_pairs:
            relay_pairs[session_id] = {
                "host": None,
                "client": None,
                "created_at": time.time()
            }
        
        if role == "RELAY_HOST":
            relay_pairs[session_id]["host"] = conn
        else:
            relay_pairs[session_id]["client"] = conn
        
        pair = relay_pairs[session_id]
        host_conn = pair["host"]
        client_conn = pair["client"]
    
    if host_conn and client_conn:
        print(f"[Relay] Cả hai phía đã sẵn sàng! Bắt đầu chuyển tiếp dữ liệu cho session: {session_display}")
        closed_flag = [False]
        relay_close_lock = threading.Lock()
        threading.Thread(target=pipe_sockets, args=(host_conn, client_conn, session_id, closed_flag, relay_close_lock), daemon=True).start()
        threading.Thread(target=pipe_sockets, args=(client_conn, host_conn, session_id, closed_flag, relay_close_lock), daemon=True).start()
        with relay_lock:
            if session_id in relay_pairs:
                del relay_pairs[session_id]

def handle_client(conn, addr):
    print(f"[+] Client mới kết nối từ: {addr}")
    set_keepalive(conn)
    conn.settimeout(15.0)  # Khởi tạo timeout 15s để chống treo thread do Slowloris
    hwid = None
    is_relay = False
    try:
        first_4 = recv_exact(conn, 4)
        if not first_4:
            try: conn.close()
            except: pass
            return
            
        if first_4.startswith(b'RELA'):
            rest = bytearray()
            # FIX LỖI CPU: Giới hạn số byte tối đa đọc tiêu đề để không bị treo vòng lặp
            for _ in range(1024): 
                chunk = conn.recv(1)
                if not chunk: break
                rest.extend(chunk)
                if chunk == b'\n': break
            decoded = (first_4 + rest).decode('utf-8', errors='ignore').strip()
            if decoded.startswith("RELAY_HOST:") or decoded.startswith("RELAY_CLIENT:"):
                parts = decoded.split(":")
                if len(parts) >= 2:
                    role = parts[0]
                    session_id = parts[1]
                    is_relay = True
                    conn.settimeout(None)  # Giao dịch P2P relay không dùng timeout
                    handle_relay_connection(conn, role, session_id)
                    return 
        else:
            length = struct.unpack('>I', first_4)[0]
            if length > 65536: # Chống DDoS kích thước ảo (tối đa 64KB)
                print(f"[-] Client {addr} gửi length quá lớn ({length}), có thể là phiên bản client cũ chưa mã hóa.")
                try: conn.close()
                except: pass
                return
            encrypted_data = recv_exact(conn, length)
            if not encrypted_data:
                try: conn.close()
                except: pass
                return
            msg_bytes = decrypt_payload(encrypted_data, APP_KEY)
            if not msg_bytes:
                print(f"[-] Client {addr} giải mã thất bại. Ngắt kết nối.")
                try: conn.close()
                except: pass
                return
            decoded = msg_bytes.decode('utf-8')
            
            # Cấu hình timeout dài (60s) cho luồng signaling để giải phóng khi client mất mạng đột ngột
            conn.settimeout(60.0)
        
        def process_msg(msg):
            nonlocal hwid
            if not msg: return
            try:
                req = json.loads(msg)
            except Exception as je:
                print(f"[Signal] JSON decode error: {je} for msg: {msg}")
                return
            action = req.get("action")
            
            if action == "register":
                hwid = req.get("hwid")
                with clients_lock:
                    clients[hwid] = conn
                print(f"[Register] ID {hwid} online ({addr[0]})")
                
            elif action == "connect_request":
                target = req.get("target")
                with clients_lock:
                    target_conn = clients.get(target)
                
                if target_conn:
                    print(f"[Signal] Yêu cầu kết nối từ {hwid} -> {target}")
                    forward_msg = json.dumps({
                        "action": "incoming_request",
                        "from_hwid": hwid,
                        "public_ip": addr[0],
                        "public_port": req.get("port"),
                        "local_ip": req.get("local_ip")
                    })
                    send_msg(target_conn, forward_msg.encode('utf-8'), APP_KEY)
                else:
                    err_msg = json.dumps({"action": "error", "message": "Đối tác đang offline!"})
                    send_msg(conn, err_msg.encode('utf-8'), APP_KEY)

            elif action == "connect_accept":
                target = req.get("target")
                with clients_lock:
                    target_conn = clients.get(target)
                    
                if target_conn:
                    print(f"[Signal] {hwid} chấp nhận kết nối từ {target}")
                    forward_msg = json.dumps({
                        "action": "request_accepted",
                        "from_hwid": hwid,
                        "public_ip": addr[0],
                        "public_port": req.get("port"),
                        "local_ip": req.get("local_ip")
                    })
                    send_msg(target_conn, forward_msg.encode('utf-8'), APP_KEY)
            
            elif action == "relay_request":
                target = req.get("target")
                with clients_lock:
                    target_conn = clients.get(target)
                if target_conn:
                    print(f"[Signal] Yêu cầu RELAY từ {hwid} -> {target}")
                    forward_msg = json.dumps({
                        "action": "relay_request",
                        "from_hwid": hwid,
                        "session_id": req.get("session_id")
                    })
                    send_msg(target_conn, forward_msg.encode('utf-8'), APP_KEY)
            
            elif action == "check_online":
                target = req.get("target")
                with clients_lock:
                    is_online = target in clients
                print(f"[Signal] Yêu cầu check_online ID: {target} -> Kết quả: {'ONLINE' if is_online else 'OFFLINE'}")
                res_msg = json.dumps({
                    "action": "online_status",
                    "target": target,
                    "online": is_online
                })
                send_msg(conn, res_msg.encode('utf-8'), APP_KEY)

            elif action == "ping":
                res_msg = json.dumps({"action": "pong"})
                send_msg(conn, res_msg.encode('utf-8'), APP_KEY)

        for part in decoded.strip().split('\n'):
            if part.strip():
                process_msg(part.strip())
            
        while True:
            msg_bytes = recv_msg(conn, APP_KEY)
            if msg_bytes is None:
                break
            # FIX LỖI XOAY VÒNG VÔ TẬN: Nếu nhận gói lỗi b'' (giải mã sai), phải thoát ngắt kết nối luôn để bảo vệ CPU
            if msg_bytes == b'': 
                print(f"[-] Phát hiện gói tin giải mã lỗi từ {addr}. Ngắt kết nối để bảo vệ CPU.")
                break
            decoded = msg_bytes.decode('utf-8')
            for part in decoded.strip().split('\n'):
                if part.strip():
                    process_msg(part.strip())
                
    except Exception:
        pass
    finally:
        remove_send_lock(conn)
        if not is_relay:
            with clients_lock:
                if hwid and hwid in clients:
                    if clients[hwid] == conn: # Chỉ xóa nếu đúng socket đó
                        del clients[hwid]
            try: conn.close()
            except: pass
            print(f"[-] Client ngắt kết nối: {addr} (ID: {hwid})")

def main():
    host = '0.0.0.0'
    port = 8765
    
    # Khởi động luồng dọn dẹp các session relay quá hạn
    threading.Thread(target=cleanup_stale_relays, daemon=True).start()
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(100)
    print(f"[*] Signaling & Relay Server đang chạy tại {host}:{port}")
    
    while True:
        try:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(0.1)

if __name__ == "__main__":
    main()
