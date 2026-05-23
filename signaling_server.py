import socket
import threading
import json
import sys
import time

class TeeLogger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.at_line_start = True
        try:
            self.log = open(filename, "a", encoding="utf-8", buffering=1)
        except:
            self.log = None

    def write(self, message):
        if not message:
            return
        
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
            try:
                self.terminal.write(formatted_message)
            except:
                pass
        if self.log:
            try:
                self.log.write(formatted_message)
            except:
                pass

    def flush(self):
        if self.terminal:
            try:
                self.terminal.flush()
            except:
                pass
        if self.log:
            try:
                self.log.flush()
            except:
                pass

sys.stdout = TeeLogger("signaling_log.txt")
sys.stderr = sys.stdout

# Lưu trữ các client đang kết nối: { "hwid": connection_socket }
clients = {}
clients_lock = threading.Lock()

# Lưu trữ các session trung chuyển (Relay): { "session_id": { "host": conn, "client": conn } }
relay_pairs = {}
relay_lock = threading.Lock()

def recv_until_newline(conn):
    """
    Đọc dữ liệu từ socket chính xác từng byte một cho đến khi gặp ký tự xuống dòng '\\n'.
    Điều này cực kỳ quan trọng để tránh 'nuốt' mất dữ liệu P2P (như handshake password)
    được gửi ngay sau gói tin cấu hình Relay trong cùng một packet TCP.
    """
    buf = bytearray()
    while True:
        try:
            chunk = conn.recv(1)
            if not chunk:
                return None
            buf.extend(chunk)
            if chunk == b'\n':
                break
        except Exception:
            return None
    return buf.decode('utf-8', errors='ignore')

def format_session_id(session_id):
    parts = session_id.split('_')
    if len(parts) >= 3 and parts[0] == "relay":
        return f"{parts[1]} vs {parts[2]}"
    return session_id

def pipe_sockets(src, dst, session_id, closed_flag, lock):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
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
            relay_pairs[session_id] = {"host": None, "client": None}
        
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
    hwid = None
    is_relay = False
    try:
        # Đọc dòng đầu tiên (chính xác đến dấu xuống dòng \n để tránh nuốt dữ liệu P2P phía sau)
        first_line = recv_until_newline(conn)
        if not first_line:
            conn.close()
            return
        
        # Loại bỏ khoảng trắng thừa
        decoded = first_line.strip()
        
        # Kiểm tra xem có phải là kết nối Relay hay không
        if decoded.startswith("RELAY_HOST:") or decoded.startswith("RELAY_CLIENT:"):
            parts = decoded.split(":")
            if len(parts) >= 2:
                role = parts[0]
                session_id = parts[1]
                is_relay = True
                handle_relay_connection(conn, role, session_id)
                return
        
        # Nếu không phải Relay, xử lý như Signaling Server bình thường
        def process_msg(msg):
            nonlocal hwid
            if not msg: return
            req = json.loads(msg)
            action = req.get("action")
            
            # 1. Đăng ký ID khi mở app
            if action == "register":
                hwid = req.get("hwid")
                with clients_lock:
                    clients[hwid] = conn
                print(f"[Register] ID {hwid} online ({addr[0]})")
                
            # 2. Client yêu cầu kết nối tới một ID khác
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
                    }) + '\n'
                    target_conn.sendall(forward_msg.encode('utf-8'))
                else:
                    err_msg = json.dumps({"action": "error", "message": "Đối tác đang offline!"}) + '\n'
                    conn.sendall(err_msg.encode('utf-8'))

            # 3. Host chấp nhận kết nối, gửi lại IP/Port cho Client
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
                    }) + '\n'
                    target_conn.sendall(forward_msg.encode('utf-8'))
            
            # 4. Yêu cầu chuyển sang chế độ Relay (Trung chuyển) do đục lỗ thất bại
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
                    }) + '\n'
                    target_conn.sendall(forward_msg.encode('utf-8'))
            
            # 5. Kiểm tra trạng thái online/offline của một ID khác
            elif action == "check_online":
                target = req.get("target")
                with clients_lock:
                    is_online = target in clients
                print(f"[Signal] Yêu cầu check_online ID: {target} -> Kết quả: {'ONLINE' if is_online else 'OFFLINE'} (Danh sách online: {list(clients.keys())})")
                res_msg = json.dumps({
                    "action": "online_status",
                    "target": target,
                    "online": is_online
                }) + '\n'
                conn.sendall(res_msg.encode('utf-8'))

            # 6. Ping-pong để giữ kết nối và phát hiện kết nối chết
            elif action == "ping":
                res_msg = json.dumps({"action": "pong"}) + '\n'
                conn.sendall(res_msg.encode('utf-8'))


        # Xử lý tin nhắn đầu tiên trước (đó là JSON đăng ký/kết nối của signaling client)
        process_msg(decoded)
            
        # Lắng nghe các tin nhắn tiếp theo
        while True:
            data = conn.recv(4096)
            if not data:
                break
            messages = data.decode('utf-8').strip().split('\n')
            for msg in messages:
                process_msg(msg)
                
    except Exception as e:
        print(f"[-] Lỗi với client {addr}: {e}")
    finally:
        if not is_relay:
            with clients_lock:
                if hwid and hwid in clients:
                    del clients[hwid]
            conn.close()
            print(f"[-] Client ngắt kết nối: {addr} (ID: {hwid})")

def main():
    host = '0.0.0.0'
    port = 8765
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(100)
    print(f"[*] Signaling & Relay Server đang chạy tại {host}:{port}")
    
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
