"""
Connection Broker (Session 0, no Tk).

Muc dich: giu ket noi cua viewer o mot tien trinh BAT TU trong Session 0, va
proxy khung hinh/input toi/tu agent (capture-worker) dang chay trong session
nguoi dung / winlogon. Khi Windows doi session (logon/logoff/lock), agent bi
huy nhung ket noi viewer VAN GIU NGUYEN o broker; broker chi noi lai kenh IPC
sang worker moi -> viewer khong phai reconnect, nho vay bat duoc man "Signing out".

Phase 1: LAN-direct :12345.
Phase 2: Signaling + UPnP + hole-punch + relay (WAN), van giu viewer socket o Session 0.

Kien truc:
  Viewer  --TCP 12345-->  Broker (Session 0)  --TCP 127.0.0.1:12400-->  Worker (session)
                                 |                                          |
                          lam handshake 1 lan                        capture + input
                          relay frame trong suot                     (host_sender/receiver)

Giao thuc IPC (localhost):
  - Worker mo ket noi CONTROL toi 12400, gui 1 dong JSON:
      {"role":"control","session":<sid>,"desktop":"default|winlogon","width":W,"height":H,"pid":P}\n
    Broker coi worker moi nhat la "active". Sau do broker gui lenh (JSON dong)
    xuong control socket:
      {"cmd":"start_session","token":T,"password":P,"net_class":N,"nonce_base":X}\n
      {"cmd":"stop_session","token":T}\n
  - Khi nhan start_session, worker mo ket noi DATA moi toi 12400, gui:
      {"role":"data","token":T}\n
    roi chay host_sender/host_receiver tren socket DATA do (bo qua handshake).
  - Broker ghep DATA socket <-> viewer socket va relay frame theo tung message
    ([4-byte length][payload]) de an toan khi doi worker giua chung.
"""

import os
import sys
import json
import time
import socket
import struct
import threading

import core.config
from core.config import LAN_APP_SIGNATURE, LAN_DISCOVERY_PORT, LAN_BEACON_INTERVAL
from network.socket_utils import send_msg, recv_msg, recv_exact, socket_passwords, APP_KEY, force_close_socket, _get_socket_send_lock
from network.crypto import decrypt_payload

AGENT_IPC_PORT = 12400          # 127.0.0.1 only: worker <-> broker
VIEWER_PORT = 12345             # LAN-direct viewer (Phase 1)


def _decrypt_fixed_password(encrypted_text, key="AntigravityP2P"):
    if not encrypted_text:
        return ""
    import base64
    try:
        decoded = base64.b64decode(encrypted_text.encode("utf-8")).decode("utf-8")
        return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(decoded))
    except Exception:
        return ""


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_line(sock, max_len=8192):
    """Doc mot dong ket thuc bang \\n, tung byte mot (khong over-read sang frame)."""
    buf = bytearray()
    try:
        while len(buf) < max_len:
            b = sock.recv(1)
            if not b:
                return None
            if b == b"\n":
                return bytes(buf)
            buf += b
        return bytes(buf)
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError, TimeoutError):
        return None


def _write_line(sock, obj):
    data = (json.dumps(obj) + "\n").encode("utf-8")
    sock.sendall(data)


def _read_frame(sock):
    """Doc 1 message [4-byte len][payload], tra ve raw bytes (ca header) de forward."""
    try:
        header = recv_exact(sock, 4)
        if not header or len(header) < 4:
            return None
        length = struct.unpack(">I", header)[0]
        if length <= 0 or length > 64 * 1024 * 1024:
            return None
        payload = recv_exact(sock, length)
        if payload is None or len(payload) < length:
            return None
        return header + payload
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError, TimeoutError):
        # Worker/viewer dong socket giua chung: tra None de relay handoff, khong crash thread.
        return None


class Worker:
    def __init__(self, control_sock, info):
        self.control_sock = control_sock
        self.session = info.get("session")
        self.desktop = info.get("desktop", "default")
        self.width = int(info.get("width", 0) or 0)
        self.height = int(info.get("height", 0) or 0)
        self.pid = info.get("pid")
        self.passwords = [p for p in (info.get("passwords") or []) if p]
        self.beacon = info.get("beacon") or {}
        self.send_lock = threading.Lock()
        self.alive = True

    def send_cmd(self, obj):
        try:
            with self.send_lock:
                _write_line(self.control_sock, obj)
            return True
        except Exception as e:
            print(f"[Broker] send_cmd toi worker pid={self.pid} loi: {e}")
            self.alive = False
            return False


class Broker:
    def __init__(self):
        self.active_worker = None            # Worker hien dang capture
        self.workers = []                    # tat ca worker control (broadcast logoff)
        self.worker_lock = threading.Lock()
        self.pending_data = {}               # token -> data socket (worker vua mo)
        self.pending_cv = threading.Condition()
        self.handoff_gen = 0                 # tang khi can doi data channel ngay
        self.live_data_socks = []            # data sock dang relay — dong de unblocking _read_frame
        self.live_data_lock = threading.Lock()
        self._token_seq = 0
        self._nonce_seq = int(time.time()) & 0xFFFF
        self.identity = {"hwid": "", "computer_name": "", "local_ip": "", "macs": ""}
        self.signaling_lock = threading.Lock()
        self.signaling_sockets = {}
        self.active_viewers = []  # [(sock, password), ...]
        self.viewers_lock = threading.Lock()
        threading.Thread(target=self._load_identity, daemon=True).start()

    def _register_viewer(self, conn, password):
        with self.viewers_lock:
            self.active_viewers.append((conn, password))

    def _unregister_viewer(self, conn):
        with self.viewers_lock:
            self.active_viewers = [(c, p) for c, p in self.active_viewers if c is not conn]

    def notify_viewers_shutdown(self):
        """Bao viewer khi broker/service tat (dong app, taskkill co the khong toi day)."""
        with self.viewers_lock:
            viewers = list(self.active_viewers)
        pkt = json.dumps({"type": "host_shutdown"}).encode("utf-8")
        for conn, pw in viewers:
            try:
                send_msg(conn, pkt, pw)
            except Exception:
                pass
        print(f"[Broker] Da gui host_shutdown toi {len(viewers)} viewer.")

    def _tune_viewer_socket(self, sock):
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if os.name == "nt":
                # idle 3s, retry moi 1s — phat hien day mang dut / app dong dot ngot
                sock.ioctl(socket.SIOC_KEEPALIVE_VALS, (1, 3000, 1000))
        except Exception:
            pass

    def _load_identity(self):
        """HWID/IP cua may — khong phu thuoc worker (fast-start khong goi get_hwid)."""
        import platform
        hwid, macs, lip = "", "", ""
        try:
            from utils.hwid import get_hwid, get_local_ip
            hwid, _fmt, macs = get_hwid()
            lip = get_local_ip() or ""
        except Exception as e:
            print(f"[Broker] load identity loi: {e}")
        if not lip or str(lip).startswith("127."):
            try:
                lip = _worker_local_ip()
            except Exception:
                pass
        self.identity = {
            "hwid": hwid or "",
            "computer_name": platform.node(),
            "local_ip": lip or "",
            "macs": macs or "",
        }
        print(f"[Broker] LAN identity hwid={self.identity['hwid']} ip={self.identity['local_ip']} name={self.identity['computer_name']}")

    # ---------- password ----------
    def _current_password(self):
        try:
            p = os.path.join(_app_dir(), "session_pass.txt")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8-sig") as f:
                    v = f.read().strip()
                    if v:
                        return v
        except Exception as e:
            print(f"[Broker] doc session_pass.txt loi: {e}")
        return None

    def _fixed_password(self):
        try:
            xml_path = os.path.join(_app_dir(), "saved_computers.xml")
            if not os.path.exists(xml_path):
                return None
            import xml.etree.ElementTree as ET
            root = ET.parse(xml_path).getroot()
            node = root.find("fixed_password")
            if node is not None and node.text:
                v = _decrypt_fixed_password(node.text)
                v = (v or "").strip()
                return v or None
        except Exception as e:
            print(f"[Broker] doc mat khau co dinh loi: {e}")
        return None

    def _handshake_passwords(self, worker):
        """Reload session + fixed luc bat tay (khong dung mat khau worker dong bang luc start)."""
        cands = []

        def add(p):
            if not p:
                return
            p = str(p).strip()
            if p and p not in cands:
                cands.append(p)

        if worker:
            for p in (worker.passwords or []):
                add(p)
        add(self._current_password())
        add(self._fixed_password())
        return cands

    def _next_token(self):
        with self.pending_cv:
            self._token_seq += 1
            return f"t{self._token_seq}_{int(time.time()*1000)&0xFFFFFF}"

    def _next_nonce_base(self):
        self._nonce_seq = (self._nonce_seq + 1) & 0xFFFFFFFF
        # dich len cao de moi worker/session dung dai nonce khac nhau
        return (self._nonce_seq << 24) & 0xFFFFFFFFFFFF

    # ---------- agent (worker) IPC listener ----------
    def start_agent_listener(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", AGENT_IPC_PORT))
        s.listen(16)
        print(f"[Broker] Agent IPC listening 127.0.0.1:{AGENT_IPC_PORT}")
        while True:
            try:
                conn, _addr = s.accept()
                threading.Thread(target=self._handle_agent_conn, args=(conn,), daemon=True).start()
            except Exception as e:
                print(f"[Broker] agent accept loi: {e}")
                time.sleep(0.2)

    def _handle_agent_conn(self, conn):
        try:
            line = _read_line(conn)
            if not line:
                conn.close()
                return
            info = json.loads(line.decode("utf-8"))
            role = info.get("role")
            if role == "control":
                self._register_worker(conn, info)
            elif role == "data":
                token = info.get("token")
                with self.pending_cv:
                    self.pending_data[token] = conn
                    self.pending_cv.notify_all()
            elif role == "session_event":
                self._on_session_event(info)
                try: conn.close()
                except: pass
            else:
                conn.close()
        except Exception as e:
            print(f"[Broker] agent conn loi: {e}")
            try: conn.close()
            except: pass

    def _bump_handoff(self, reason=""):
        """Dong data sock hien tai de _relay_loop gan ngay worker moi (Signing out)."""
        with self.live_data_lock:
            self.handoff_gen += 1
            socks = list(self.live_data_socks)
            self.live_data_socks = []
        for s in socks:
            try:
                s.close()
            except Exception:
                pass
        print(f"[Broker] Handoff gen={self.handoff_gen} {reason} (dong {len(socks)} data sock)")

    def _track_data_sock(self, sock):
        if sock is None:
            return
        with self.live_data_lock:
            self.live_data_socks.append(sock)

    def _untrack_data_sock(self, sock):
        if sock is None:
            return
        with self.live_data_lock:
            try:
                self.live_data_socks.remove(sock)
            except ValueError:
                pass

    def _broadcast_workers(self, obj):
        with self.worker_lock:
            workers = [w for w in self.workers if w.alive]
        for w in workers:
            w.send_cmd(obj)

    def _on_session_event(self, info):
        """Service bao WTS logoff/lock — worker Default phai PrintWindow ngay."""
        kind = (info.get("kind") or "").lower()
        sid = info.get("session")
        print(f"[Broker] session_event kind={kind} session={sid}")
        if kind == "logoff":
            self._broadcast_workers({"cmd": "session_phase", "phase": "logoff"})
        elif kind == "lock":
            self._broadcast_workers({"cmd": "session_phase", "phase": "lock"})
        elif kind in ("interactive", "logon", "unlock"):
            self._broadcast_workers({"cmd": "session_phase", "phase": "none"})

    def _register_worker(self, conn, info):
        w = Worker(conn, info)
        with self.worker_lock:
            old = self.active_worker
            self.active_worker = w
            self.workers.append(w)
        print(f"[Broker] Worker moi active: pid={w.pid} session={w.session} "
              f"desktop={w.desktop} {w.width}x{w.height}"
              + (f" (thay pid={old.pid})" if old else ""))
        # Khong handoff ngay khi Winlogon dang ky: process moi chua kip gui frame.
        # Default PrintWindow Signing out; doi data sock Default chet roi moi gan worker moi.
        # Giu control socket song; neu worker chet, doc se loi -> danh dau
        try:
            while True:
                line = _read_line(conn)
                if line is None:
                    break
                # worker co the gui cap nhat resolution
                try:
                    upd = json.loads(line.decode("utf-8"))
                    if upd.get("width"):
                        w.width = int(upd["width"]); w.height = int(upd["height"])
                except Exception:
                    pass
        except Exception:
            pass
        w.alive = False
        with self.worker_lock:
            self.workers = [x for x in self.workers if x is not w]
            if self.active_worker is w:
                # khong xoa active_worker ngay: co the worker moi chua ket noi
                pass
        print(f"[Broker] Worker pid={w.pid} control dong.")

    def _get_active_worker(self, timeout=15.0, exclude=None):
        end = time.time() + timeout
        while time.time() < end:
            with self.worker_lock:
                w = self.active_worker
            if w and w.alive and w is not exclude:
                return w
            time.sleep(0.1)
        with self.worker_lock:
            w = self.active_worker
        if w is exclude:
            return None
        return w

    def _request_data_channel(self, worker, password, net_class):
        token = self._next_token()
        nonce_base = self._next_nonce_base()
        ok = worker.send_cmd({
            "cmd": "start_session", "token": token,
            "password": password, "net_class": net_class,
            "nonce_base": nonce_base,
        })
        if not ok:
            return None
        # cho worker mo data socket
        with self.pending_cv:
            end = time.time() + 6.0
            while token not in self.pending_data and time.time() < end:
                self.pending_cv.wait(0.2)
            data_sock = self.pending_data.pop(token, None)
        if data_sock is None:
            print(f"[Broker] Worker pid={worker.pid} khong mo data channel (token={token}).")
        return data_sock

    # ---------- LAN discovery beacon (thay cho worker) ----------
    def start_lan_beacon(self):
        while True:
            try:
                bc = dict(self.identity or {})
                with self.worker_lock:
                    w = self.active_worker
                if w and w.beacon:
                    # Worker co the co IP tot hon; HWID luon lay tu broker (on dinh).
                    if w.beacon.get("local_ip") and not str(w.beacon.get("local_ip")).startswith("127."):
                        bc["local_ip"] = w.beacon.get("local_ip")
                    if w.beacon.get("computer_name"):
                        bc["computer_name"] = w.beacon.get("computer_name")
                    if w.beacon.get("macs"):
                        bc["macs"] = w.beacon.get("macs")
                if bc.get("hwid"):
                    payload = json.dumps({
                        "sig": LAN_APP_SIGNATURE,
                        "hwid": bc.get("hwid"),
                        "computer_name": bc.get("computer_name", ""),
                        "port": VIEWER_PORT,
                        "local_ip": bc.get("local_ip", ""),
                        "macs": bc.get("macs", ""),
                    }).encode("utf-8")
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    sock.settimeout(1.0)
                    try:
                        sock.sendto(payload, ("255.255.255.255", LAN_DISCOVERY_PORT))
                    except Exception:
                        pass
                    try:
                        for lip in str(bc.get("local_ip", "")).split(","):
                            lip = lip.strip()
                            p = lip.split(".")
                            if len(p) == 4 and not lip.startswith("127."):
                                sock.sendto(payload, (f"{p[0]}.{p[1]}.{p[2]}.255", LAN_DISCOVERY_PORT))
                    except Exception:
                        pass
                    sock.close()
                else:
                    print("[Broker] Beacon bo qua: chua co HWID")
            except Exception as e:
                print(f"[Broker] beacon loi: {e}")
            time.sleep(LAN_BEACON_INTERVAL)

    # ---------- viewer listener ----------
    def start_viewer_listener(self):
        s = None
        try:
            s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except Exception:
                pass
            s.bind(("", VIEWER_PORT))
        except Exception:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", VIEWER_PORT))
        s.listen(8)
        print(f"[Broker] Viewer listening :{VIEWER_PORT} (LAN-direct)")
        while True:
            try:
                conn, addr = s.accept()
                print(f"[Broker] Viewer connect {addr[0]}:{addr[1]}")
                threading.Thread(target=self._handle_viewer, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print(f"[Broker] viewer accept loi: {e}")
                time.sleep(0.2)

    def _handle_viewer(self, conn, addr):
        try:
            worker = self._get_active_worker()
            if worker is None:
                print("[Broker] khong co worker de capture.")
                conn.close(); return

            candidates = self._handshake_passwords(worker)
            sp = self._current_password()
            fp = self._fixed_password()
            if not candidates:
                print("[Broker] Chua co mat khau, tu choi viewer.")
                conn.close(); return
            print(f"[Broker] handshake: {len(candidates)} khoa (session={'y' if sp else 'n'} fixed={'y' if fp else 'n'})")

            self._tune_viewer_socket(conn)

            decrypt_keys = list(candidates)
            if APP_KEY not in decrypt_keys:
                decrypt_keys.append(APP_KEY)
            socket_passwords[conn] = decrypt_keys
            msg = recv_msg(conn, decrypt_keys)
            if not msg:
                print("[Broker] handshake: khong giai ma duoc.")
                try:
                    send_msg(conn, json.dumps({
                        "status": "error",
                        "message": "Sai mat khau ket noi hoac du lieu khong hop le!"
                    }).encode("utf-8"), APP_KEY)
                except Exception:
                    pass
                conn.close(); return
            data = json.loads(msg.decode("utf-8"))
            client_pass = data.get("password")
            if client_pass not in candidates:
                print("[Broker] handshake: sai mat khau.")
                try:
                    send_msg(conn, json.dumps({"status": "error", "message": "Sai mat khau"}).encode("utf-8"), APP_KEY)
                except Exception:
                    pass
                conn.close(); return
            password = client_pass
            socket_passwords[conn] = password

            host_w = worker.width or 1920
            host_h = worker.height or 1080
            import platform
            res_info = json.dumps({
                "status": "ok",
                "width": host_w,
                "height": host_h,
                "computer_name": platform.node(),
                "zalo_phone": "",
                "is_domain": False,
                "chk_reason": "broker",
                "os_release": platform.release(),
            }).encode("utf-8")
            send_msg(conn, res_info, password)

            net_class = self._run_speed_test(conn, password)
            self._register_viewer(conn, password)
            self._relay_loop(conn, addr, password, net_class)
        except Exception as e:
            print(f"[Broker] viewer handler loi: {e}")
        finally:
            self._unregister_viewer(conn)
            socket_passwords.pop(conn, None)
            try: conn.close()
            except: pass

    def _run_speed_test(self, conn, password):
        net_class = "medium"
        try:
            conn.settimeout(15.0)
            while True:
                probe_msg = recv_msg(conn, password)
                if not probe_msg:
                    break
                try:
                    probe = json.loads(probe_msg.decode("utf-8"))
                except Exception:
                    break
                act = probe.get("action")
                evt = probe.get("type")
                if act == "speed_test_ping":
                    send_msg(conn, json.dumps({"action": "speed_test_pong"}).encode("utf-8"), password)
                elif act == "speed_test_bw_req":
                    dummy = int(probe.get("suggested_size", 262144))
                    dummy = max(1024, min(dummy, 1572864))
                    send_msg(conn, json.dumps({"action": "speed_test_bw_start", "size": dummy}).encode("utf-8"), password)
                    conn.sendall(b"\x00" * dummy)
                elif act == "speed_test_result":
                    net_class = probe.get("net_class", "medium")
                    print(f"[Broker] Speed test: {net_class}")
                    break
                elif evt == "ping":
                    # LAN shortcut
                    net_class = "high"
                    print("[Broker] Viewer ready (ping).")
                    break
                else:
                    break
        except Exception as e:
            print(f"[Broker] speed test loi: {e}")
        finally:
            try: conn.settimeout(None)
            except: pass
        return net_class

    def _relay_loop(self, viewer, addr, password, net_class):
        """Ghep viewer <-> worker data socket, relay theo message; handoff khi doi worker."""
        stop = threading.Event()
        data_holder = {"sock": None, "worker": None}

        def open_data(exclude=None):
            # Cho toi ~30s de worker moi (session moi) len sau khi doi session.
            for _ in range(150):
                if stop.is_set():
                    return None, None
                w = self._get_active_worker(timeout=2.0, exclude=exclude)
                if not w or not w.alive:
                    time.sleep(0.2); continue
                ds = self._request_data_channel(w, password, net_class)
                if ds is not None:
                    try:
                        ds.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    except Exception:
                        pass
                    self._track_data_sock(ds)
                    return ds, w
                time.sleep(0.2)
            return None, None

        def _maybe_answer_ping(frame):
            """Broker tu tra pong — khong phu thuoc worker (handoff / worker chet)."""
            try:
                if not frame or len(frame) < 5:
                    return
                plain = decrypt_payload(frame[4:], password)
                obj = json.loads(plain.decode("utf-8"))
                if obj.get("type") == "ping":
                    send_msg(viewer, json.dumps({"type": "pong"}).encode("utf-8"), password)
            except Exception:
                pass

        def viewer_to_worker():
            import select
            last_in = time.time()
            try:
                while not stop.is_set():
                    try:
                        r, _w, _e = select.select([viewer], [], [], 1.0)
                    except Exception:
                        stop.set(); break
                    if not r:
                        if time.time() - last_in > 25.0:
                            print(f"[Broker] Viewer {addr[0]} im lang 25s (mat mang / app dong). Ngat.")
                            stop.set(); break
                        continue
                    frame = _read_frame(viewer)
                    if frame is None:
                        print(f"[Broker] Viewer {addr[0]} dong socket.")
                        stop.set(); break
                    last_in = time.time()
                    _maybe_answer_ping(frame)
                    ds = data_holder["sock"]
                    if ds is None:
                        continue
                    try:
                        ds.sendall(frame)
                    except Exception:
                        time.sleep(0.05)
            except Exception as e:
                print(f"[Broker] viewer_to_worker loi: {e}")
                stop.set()

        def heartbeat():
            # Giu client_last_recv_time tren viewer song, ke ca luc doi worker.
            while not stop.wait(2.5):
                try:
                    send_msg(viewer, json.dumps({"type": "pong"}).encode("utf-8"), password)
                except Exception:
                    print(f"[Broker] Heartbeat toi viewer {addr[0]} that bai. Ngat.")
                    stop.set()
                    break

        def worker_to_viewer():
            import select
            dead_worker = None
            local_gen = self.handoff_gen
            while not stop.is_set():
                try:
                    ds = data_holder["sock"]
                    if ds is None:
                        ds, w = open_data(exclude=dead_worker)
                        if ds is None:
                            if stop.is_set():
                                break
                            time.sleep(0.3)
                            continue
                        data_holder["sock"] = ds
                        data_holder["worker"] = w
                        dead_worker = None
                        local_gen = self.handoff_gen
                        print(f"[Broker] Data channel san sang cho viewer {addr[0]} (worker pid={getattr(w,'pid',None)}).")
                    if self.handoff_gen != local_gen:
                        print(f"[Broker] Handoff gen doi, ngat data channel hien tai cho {addr[0]}...")
                        dead_worker = data_holder.get("worker")
                        self._untrack_data_sock(ds)
                        try: ds.close()
                        except: pass
                        data_holder["sock"] = None
                        data_holder["worker"] = None
                        local_gen = self.handoff_gen
                        continue
                    try:
                        r, _w, _e = select.select([ds], [], [], 0.2)
                    except Exception:
                        r = [ds]
                    if not r:
                        continue
                    frame = _read_frame(ds)
                    if frame is None:
                        print(f"[Broker] Data channel dut, handoff worker moi cho {addr[0]}...")
                        dead_worker = data_holder.get("worker")
                        self._untrack_data_sock(ds)
                        try: ds.close()
                        except: pass
                        data_holder["sock"] = None
                        data_holder["worker"] = None
                        continue
                    try:
                        lock = _get_socket_send_lock(viewer)
                        with lock:
                            viewer.sendall(frame)
                    except Exception:
                        stop.set(); break
                except Exception as e:
                    print(f"[Broker] worker_to_viewer loi (handoff): {e}")
                    dead_worker = data_holder.get("worker")
                    try:
                        ds = data_holder.get("sock")
                        self._untrack_data_sock(ds)
                        if ds:
                            ds.close()
                    except Exception:
                        pass
                    data_holder["sock"] = None
                    data_holder["worker"] = None
                    time.sleep(0.2)

        t1 = threading.Thread(target=viewer_to_worker, daemon=True)
        t2 = threading.Thread(target=worker_to_viewer, daemon=True)
        t3 = threading.Thread(target=heartbeat, daemon=True)
        t1.start(); t2.start(); t3.start()
        t2.join()
        stop.set()
        try:
            ds = data_holder["sock"]
            if ds:
                ds.close()
        except Exception:
            pass
        print(f"[Broker] Viewer {addr[0]} ket thuc.")

    def _wait_hwid(self, timeout=45.0):
        end = time.time() + timeout
        while time.time() < end:
            h = (self.identity or {}).get("hwid")
            if h:
                return h
            time.sleep(0.2)
        return (self.identity or {}).get("hwid") or ""

    def start_upnp(self):
        try:
            from network.upnp import attempt_upnp_forward
            ok = attempt_upnp_forward(VIEWER_PORT)
            print(f"[Broker] UPnP port {VIEWER_PORT}: {'OK' if ok else 'that bai / khong co router'}")
        except Exception as e:
            print(f"[Broker] UPnP loi: {e}")

    def start_signaling(self):
        hosts = list(core.config.SIGNALING_SERVER_HOSTS or [])
        if not hosts:
            print("[Broker] Khong co SIGNALING_SERVER_HOSTS")
            return
        for host in hosts:
            threading.Thread(target=self._signaling_maintainer, args=(host,), daemon=True).start()

    def _signaling_maintainer(self, host):
        hwid = self._wait_hwid()
        if not hwid:
            print(f"[Broker] Signaling {host}: chua co HWID, thu lai...")
            time.sleep(5)
            hwid = self._wait_hwid()
        retry_delay = 2
        fail_count = 0
        port = core.config.SIGNALING_SERVER_PORT
        while True:
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(("0.0.0.0", VIEWER_PORT))
                except Exception:
                    try:
                        sock.close()
                    except Exception:
                        pass
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    if os.name == "nt":
                        sock.ioctl(socket.SIOC_KEEPALIVE_VALS, (1, 30000, 10000))
                except Exception:
                    pass
                sock.settimeout(8.0)
                sock.connect((host, port))
                sock.settimeout(None)
                hwid = (self.identity or {}).get("hwid") or hwid
                send_msg(sock, json.dumps({"action": "register", "hwid": hwid}).encode("utf-8"), APP_KEY)
                with self.signaling_lock:
                    self.signaling_sockets[host] = sock
                fail_count = 0
                retry_delay = 2
                print(f"[Broker] Signaling connected {host} hwid={hwid}")
                last_ping = time.time()
                last_pong = time.time()
                import select
                while True:
                    r, _w, _e = select.select([sock], [], [], 1.0)
                    if r:
                        msg_bytes = recv_msg(sock, APP_KEY)
                        if msg_bytes is None:
                            break
                        if msg_bytes == b"":
                            continue
                        try:
                            msg = msg_bytes.decode("utf-8")
                            self._process_signaling(msg, sock, host)
                            if "pong" in msg:
                                last_pong = time.time()
                        except Exception as de:
                            print(f"[Broker] Signaling decode: {de}")
                    now = time.time()
                    if now - last_ping > 20:
                        send_msg(sock, json.dumps({"action": "ping"}).encode("utf-8"), APP_KEY)
                        last_ping = now
                    if now - last_pong > 50:
                        print(f"[Broker] Signaling heartbeat timeout {host}")
                        break
            except Exception as e:
                print(f"[Broker] Signaling {host}: {e}")
            finally:
                if sock:
                    try:
                        force_close_socket(sock)
                    except Exception:
                        pass
                with self.signaling_lock:
                    self.signaling_sockets.pop(host, None)
            time.sleep(retry_delay)
            fail_count += 1
            if fail_count >= 3:
                retry_delay = 5

    def _process_signaling(self, msg, sock, host):
        try:
            res = json.loads(msg)
        except Exception:
            return
        action = res.get("action")
        if action == "incoming_request":
            from_hwid = res.get("from_hwid")
            public_ip = res.get("public_ip")
            public_port = int(res.get("port") or res.get("public_port") or 0)
            print(f"[Broker] incoming_request from {from_hwid} {public_ip}:{public_port}")
            local_ip = (self.identity or {}).get("local_ip") or ""
            accept = json.dumps({
                "action": "connect_accept",
                "target": from_hwid,
                "port": VIEWER_PORT,
                "local_ip": local_ip,
                "local_port": VIEWER_PORT,
            })
            with self.signaling_lock:
                send_msg(sock, accept.encode("utf-8"), APP_KEY)
            if public_ip and public_port:
                threading.Thread(
                    target=self._punch_hole, args=(public_ip, public_port), daemon=True
                ).start()
        elif action == "relay_request":
            session_id = res.get("session_id")
            relay_host = res.get("relay_host") or host
            print(f"[Broker] relay_request session={session_id} via {relay_host}")
            threading.Thread(
                target=self._start_relay_host, args=(session_id, relay_host), daemon=True
            ).start()
        elif action == "error":
            print(f"[Broker] Signaling error {host}: {res.get('message')}")

    def _punch_hole(self, c_ip, c_port):
        """Khong dong listener 12345 — bind SO_REUSEADDR de simultaneous-open."""
        time.sleep(2.0)
        success = None
        for _i in range(10):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("0.0.0.0", VIEWER_PORT))
            except Exception:
                pass
            sock.settimeout(0.5)
            try:
                sock.connect((c_ip, int(c_port)))
                print(f"[Broker] HolePunch OK toi {c_ip}:{c_port}")
                success = sock
                break
            except Exception:
                force_close_socket(sock)
                time.sleep(0.1)
        if not success:
            print(f"[Broker] HolePunch that bai {c_ip}:{c_port} (viewer co the vao UPnP/relay)")
            return
        try:
            success.settimeout(None)
        except Exception:
            pass
        threading.Thread(
            target=self._handle_viewer, args=(success, (c_ip, int(c_port))), daemon=True
        ).start()

    def _start_relay_host(self, session_id, relay_host):
        try:
            print(f"[Broker] Relay HOST connect {relay_host} session={session_id}")
            rs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            rs.settimeout(8.0)
            rs.connect((relay_host, core.config.SIGNALING_SERVER_PORT))
            rs.settimeout(None)
            rs.sendall(f"RELAY_HOST:{session_id}\n".encode("utf-8"))
            threading.Thread(
                target=self._handle_viewer,
                args=(rs, (relay_host, core.config.SIGNALING_SERVER_PORT)),
                daemon=True,
            ).start()
        except Exception as e:
            print(f"[Broker] Relay HOST that bai: {e}")


def run_broker():
    print(f"\n--- Broker started at {time.strftime('%Y-%m-%d %H:%M:%S')} (PID: {os.getpid()}) ---")
    b = Broker()
    try:
        import atexit
        atexit.register(b.notify_viewers_shutdown)
    except Exception:
        pass
    threading.Thread(target=b.start_agent_listener, daemon=True).start()
    threading.Thread(target=b.start_viewer_listener, daemon=True).start()
    threading.Thread(target=b.start_lan_beacon, daemon=True).start()
    threading.Thread(target=b.start_upnp, daemon=True).start()
    b.start_signaling()
    try:
        while True:
            time.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        b.notify_viewers_shutdown()
        raise


# ==========================================================================
#  Worker (capture-worker) side: chay trong session nguoi dung / winlogon.
#  Noi toi broker, chay host_sender/host_receiver tren socket DATA, bo handshake.
# ==========================================================================

def _worker_screen_size():
    try:
        import mss
        with mss.mss() as sct:
            m = sct.monitors[0]
            return int(m["width"]), int(m["height"]), dict(m)
    except Exception:
        pass
    try:
        import ctypes
        w = int(ctypes.windll.user32.GetSystemMetrics(78)) or int(ctypes.windll.user32.GetSystemMetrics(0))
        h = int(ctypes.windll.user32.GetSystemMetrics(79)) or int(ctypes.windll.user32.GetSystemMetrics(1))
        left = int(ctypes.windll.user32.GetSystemMetrics(76))
        top = int(ctypes.windll.user32.GetSystemMetrics(77))
        if w < 1 or h < 1:
            w, h = 1024, 768
        return w, h, {"left": left, "top": top, "width": w, "height": h}
    except Exception:
        return 1024, 768, {"left": 0, "top": 0, "width": 1024, "height": 768}


def _worker_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


def _worker_desktop_name():
    try:
        import ctypes
        h_desk = ctypes.windll.user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
        name = ctypes.create_unicode_buffer(256)
        size = ctypes.c_ulong(256)
        if ctypes.windll.user32.GetUserObjectInformationW(h_desk, 2, name, size, None):
            return name.value.lower()
    except Exception:
        pass
    return "default"


def _worker_session_id():
    try:
        import ctypes
        sid = ctypes.c_ulong()
        if ctypes.windll.kernel32.ProcessIdToSessionId(ctypes.windll.kernel32.GetCurrentProcessId(), ctypes.byref(sid)):
            return sid.value
    except Exception:
        pass
    return 1


def _run_worker_session(app, cmd):
    """Xu ly 1 lenh start_session: mo data socket, chay sender/receiver."""
    token = cmd.get("token")
    password = cmd.get("password")
    net_class = cmd.get("net_class", "medium")
    nonce_base = int(cmd.get("nonce_base", 0) or 0)

    # Tranh trung (key,nonce) giua cac worker: dat lai bo dem nonce global.
    try:
        import network.crypto as _crypto
        if nonce_base:
            with _crypto.send_counter_lock:
                _crypto.send_nonce_counter = nonce_base
    except Exception:
        pass

    try:
        ds = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ds.connect(("127.0.0.1", AGENT_IPC_PORT))
        ds.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        _write_line(ds, {"role": "data", "token": token})
    except Exception as e:
        print(f"[Worker] mo data socket loi: {e}")
        return

    w, h, monitor = _worker_screen_size()
    try:
        app._capture_origin = (int(monitor.get("left", 0)), int(monitor.get("top", 0)))
    except Exception:
        app._capture_origin = (0, 0)

    client_state = {
        "running": True,
        "net_class": net_class,
        "wake_event": threading.Event(),
    }
    socket_passwords[ds] = password

    print(f"[Worker] Session bat dau token={token} net={net_class} {w}x{h}")
    clipboard_mgr = None
    try:
        from core.clipboard_agent import clipboard_sync_manager as clipboard_mgr
        if clipboard_mgr:
            clipboard_mgr.register_app(app)
            clipboard_mgr.add_socket(ds)
            print("[Worker] Clipboard gan data socket (text 2 chieu).")
    except Exception as e:
        print(f"[Worker] clipboard add_socket: {e}")
        clipboard_mgr = None
    def _recv_wrap():
        try:
            app.host_receiver_thread(ds, client_state, password)
        finally:
            try:
                if clipboard_mgr:
                    clipboard_mgr.remove_socket(ds)
            except Exception:
                pass
    t_send = threading.Thread(target=app.host_sender_thread, args=(ds, monitor, client_state, password), daemon=True)
    t_recv = threading.Thread(target=_recv_wrap, daemon=True)
    t_send.start()
    t_recv.start()


def run_capture_worker(app):
    """Vong lap worker: giu ket noi control toi broker, nhan lenh start/stop."""
    print(f"\n--- Capture worker started at {time.strftime('%Y-%m-%d %H:%M:%S')} (PID: {os.getpid()}) ---")
    try:
        from core.host import _ensure_host_wts_phase_listener, _ensure_winlogon_grab_thread
        _ensure_host_wts_phase_listener()
        _ensure_winlogon_grab_thread()
    except Exception as e:
        print(f"[Worker] WTS/Winlogon grab: {e}")
    while True:
        ctrl = None
        try:
            ctrl = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ctrl.connect(("127.0.0.1", AGENT_IPC_PORT))
            w, h, _m = _worker_screen_size()
            pwds = []
            try:
                if getattr(app, "my_password", None):
                    pwds.append(app.my_password)
                if getattr(app, "fixed_password", None):
                    pwds.append(app.fixed_password)
            except Exception:
                pass
            import platform
            _lip = getattr(app, "local_ip", "") or ""
            if (not _lip) or _lip.startswith("127."):
                _lip = _worker_local_ip()
            beacon = {
                "hwid": getattr(app, "my_id_clean", "") or "",
                "computer_name": platform.node(),
                "local_ip": _lip,
                "macs": getattr(app, "my_macs", "") or "",
            }
            _write_line(ctrl, {
                "role": "control",
                "session": _worker_session_id(),
                "desktop": _worker_desktop_name(),
                "width": w, "height": h,
                "pid": os.getpid(),
                "passwords": pwds,
                "beacon": beacon,
            })
            print(f"[Worker] Da dang ky control voi broker ({w}x{h}).")
            while True:
                line = _read_line(ctrl)
                if line is None:
                    break
                try:
                    cmd = json.loads(line.decode("utf-8"))
                except Exception:
                    continue
                if cmd.get("cmd") == "start_session":
                    _run_worker_session(app, cmd)
                elif cmd.get("cmd") == "session_phase":
                    try:
                        from core.host import _wts_phase
                        ph = cmd.get("phase") or "none"
                        _wts_phase(ph)
                        print(f"[Worker] session_phase={ph} (tu broker/service)")
                    except Exception as e:
                        print(f"[Worker] session_phase: {e}")
        except Exception as e:
            print(f"[Worker] control loi: {e}")
        finally:
            try:
                if ctrl:
                    ctrl.close()
            except Exception:
                pass
        time.sleep(1.0)  # broker chua len / mat ket noi -> thu lai
