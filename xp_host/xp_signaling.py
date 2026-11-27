# -*- coding: utf-8 -*-
"""
xp_host/xp_signaling.py
Quản lý hạ tầng kết nối mạng cho Host XP Lite:
  1. Lắng nghe trực tiếp TCP trên cổng nội bộ LAN/VPN (12345..12349).
  2. Phát sóng UDP LAN Discovery Beacon (:12399) định kỳ để máy Win 10/11 tự thấy máy XP.
  3. Tự động mở cổng Router qua UPnP (SSDP + SOAP XML).
  4. Kết nối, duy trì Heartbeat, đục lỗ TCP (Hole Punching) và chuyển tiếp Relay qua Signaling Server.
"""

import json
import platform
import random
import select
import socket
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .xp_config import (
    LAN_APP_SIGNATURE,
    LAN_BEACON_INTERVAL,
    LAN_DISCOVERY_PORT,
    PORTS_TO_TRY,
    load_signaling_config,
    parse_signaling_host_entry,
    xp_log,
)
from .xp_hwid import get_hwid, get_local_ip
from .xp_socket import APP_KEY, force_close_socket, recv_msg, send_msg, set_xp_keepalive


def attempt_xp_upnp_forward(internal_port, local_ip=""):
    """Mở cổng tự động trên Router bằng giao thức UPnP IGD (thuần UDP + HTTP XML)."""
    ssdp_msg = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 2\r\n"
        "ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n"
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.5)
    location_url = None
    try:
        sock.sendto(ssdp_msg.encode("ascii"), ("239.255.255.250", 1900))
        deadline = time.time() + 2.5
        while time.time() < deadline:
            try:
                sock.settimeout(max(0.1, deadline - time.time()))
                data, _ = sock.recvfrom(8192)
                txt = data.decode("utf-8", errors="ignore")
                for line in txt.splitlines():
                    if line.upper().startswith("LOCATION:"):
                        location_url = line.split(":", 1)[1].strip()
                        break
                if location_url:
                    break
            except socket.timeout:
                break
    except Exception:
        pass
    finally:
        force_close_socket(sock)

    if not location_url:
        return False

    try:
        req = urllib.request.Request(location_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            xml_bytes = resp.read()
        root = ET.fromstring(xml_bytes)

        control_url = None
        service_type = None
        for elem in root.iter():
            if elem.tag.endswith("service"):
                st = None
                cu = None
                for ch in elem:
                    if ch.tag.endswith("serviceType") and ch.text:
                        st = ch.text.strip()
                    elif ch.tag.endswith("controlURL") and ch.text:
                        cu = ch.text.strip()
                if st and ("WANIPConnection" in st or "WANPPPConnection" in st) and cu:
                    service_type = st
                    control_url = cu
                    break
        if not control_url or not service_type:
            return False

        parsed = urllib.parse.urlparse(location_url)
        full_url = control_url if control_url.startswith("http") else urllib.parse.urljoin(
            f"{parsed.scheme}://{parsed.netloc}", control_url
        )
        lip = (local_ip or get_local_ip()).split(",")[0].strip()
        soap = (
            '<?xml version="1.0"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            "<s:Body>"
            f'<u:AddPortMapping xmlns:u="{service_type}">'
            "<NewRemoteHost></NewRemoteHost>"
            f"<NewExternalPort>{internal_port}</NewExternalPort>"
            "<NewProtocol>TCP</NewProtocol>"
            f"<NewInternalPort>{internal_port}</NewInternalPort>"
            f"<NewInternalClient>{lip}</NewInternalClient>"
            "<NewEnabled>1</NewEnabled>"
            "<NewPortMappingDescription>EasyRemoteDesktopXP</NewPortMappingDescription>"
            "<NewLeaseDuration>0</NewLeaseDuration>"
            "</u:AddPortMapping>"
            "</s:Body></s:Envelope>"
        )
        headers = {
            "SOAPAction": f'"{service_type}#AddPortMapping"',
            "Content-Type": "text/xml; charset=utf-8",
        }
        req2 = urllib.request.Request(full_url, data=soap.encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req2, timeout=4) as resp2:
            _ = resp2.read()
        xp_log(f"[UPnP] Mapped external TCP port {internal_port} -> {lip}:{internal_port}")
        return True
    except Exception as e:
        xp_log(f"[UPnP] Port mapping skipped/failed: {e}")
        return False


class XPNetworkCoordinator:
    """
    Điều phối đồng thời LAN Listener, LAN UDP Beacon, UPnP và Signaling/Relay Internet.
    """

    def __init__(self, on_client_socket, on_status_change=None, base_dir=None):
        self.on_client_socket = on_client_socket
        self.on_status_change = on_status_change
        self.base_dir = base_dir

        self.hwid, self.hwid_display, self.macs = get_hwid(base_dir)
        self.local_ip = get_local_ip()
        self.bound_port = PORTS_TO_TRY[0]
        self.running = False
        self.signaling_online = False
        self.signaling_server_active = ""

        self._listen_sock = None
        self._sig_lock = threading.Lock()
        self._sig_sock = None
        self._sig_gen = 0
        self._stop_ev = threading.Event()

    def _emit_status(self, text):
        xp_log(f"[Network] {text}", base_dir=self.base_dir)
        if callable(self.on_status_change):
            try:
                self.on_status_change(text)
            except Exception:
                pass

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop_ev.clear()
        self._bind_lan_listener()
        threading.Thread(target=self._accept_loop, daemon=True, name="XPLanAccept").start()
        threading.Thread(target=self._lan_beacon_loop, daemon=True, name="XPLanBeacon").start()
        threading.Thread(
            target=attempt_xp_upnp_forward, args=(self.bound_port, self.local_ip), daemon=True, name="XPUpnp"
        ).start()
        self.restart_signaling()

    def stop(self):
        self.running = False
        self._stop_ev.set()
        self._sig_gen += 1
        with self._sig_lock:
            if self._sig_sock:
                force_close_socket(self._sig_sock)
                self._sig_sock = None
        if self._listen_sock:
            force_close_socket(self._listen_sock)
            self._listen_sock = None

    def _bind_lan_listener(self):
        for p in PORTS_TO_TRY:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", p))
                s.listen(8)
                self._listen_sock = s
                self.bound_port = p
                self._emit_status(f"Sẵn sàng kết nối LAN/Internet (Cổng {p})")
                return
            except Exception:
                force_close_socket(s)
        # Fallback port bất kỳ nếu cả 5 cổng đều bận
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", 0))
        s.listen(8)
        self._listen_sock = s
        self.bound_port = s.getsockname()[1]
        self._emit_status(f"Sẵn sàng kết nối (Cổng động {self.bound_port})")

    def _accept_loop(self):
        while self.running and self._listen_sock:
            try:
                conn, addr = self._listen_sock.accept()
                threading.Thread(
                    target=self.on_client_socket,
                    args=(conn, addr),
                    daemon=True,
                    name=f"XPClient_{addr[0]}",
                ).start()
            except Exception:
                if not self.running:
                    break
                time.sleep(0.2)

    def _lan_beacon_loop(self):
        comp_name = platform.node() or "WIN-XP-HOST"
        while self.running and not self._stop_ev.is_set():
            try:
                self.local_ip = get_local_ip()
                payload = json.dumps({
                    "sig": LAN_APP_SIGNATURE,
                    "hwid": self.hwid,
                    "computer_name": comp_name,
                    "port": self.bound_port,
                    "local_ip": self.local_ip,
                    "macs": self.macs,
                }).encode("utf-8")
                usock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                usock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                usock.settimeout(1.0)
                try:
                    usock.sendto(payload, ("255.255.255.255", LAN_DISCOVERY_PORT))
                except Exception:
                    pass
                for lip in self.local_ip.split(","):
                    lip = lip.strip()
                    octs = lip.split(".")
                    if len(octs) == 4 and not lip.startswith("127."):
                        try:
                            usock.sendto(payload, (f"{octs[0]}.{octs[1]}.{octs[2]}.255", LAN_DISCOVERY_PORT))
                        except Exception:
                            pass
                usock.close()
            except Exception:
                pass
            self._stop_ev.wait(LAN_BEACON_INTERVAL)

    # ---------- Signaling & Relay Lifecycle ----------
    def restart_signaling(self):
        self._sig_gen += 1
        my_gen = self._sig_gen
        with self._sig_lock:
            if self._sig_sock:
                force_close_socket(self._sig_sock)
                self._sig_sock = None
        threading.Thread(
            target=self._signaling_loop,
            args=(my_gen,),
            daemon=True,
            name=f"XPSignaling_{my_gen}",
        ).start()

    def _connect_one_signaling(self, srv_host, srv_port, reg_id):
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            set_xp_keepalive(sock, 25000, 8000)
            sock.settimeout(6.0)
            sock.connect((srv_host, int(srv_port)))

            if not send_msg(sock, json.dumps({"action": "register", "hwid": reg_id}).encode("utf-8"), APP_KEY):
                raise ConnectionError("Failed to send register")
            if not send_msg(sock, json.dumps({"action": "ping"}).encode("utf-8"), APP_KEY):
                raise ConnectionError("Failed to send ping")

            deadline = time.time() + 4.5
            early = []
            verified = False
            while time.time() < deadline:
                r, _, _ = select.select([sock], [], [], 0.25)
                if not r:
                    continue
                raw = recv_msg(sock, APP_KEY, max_size=65536)
                if raw is None or raw == b"":
                    raise ConnectionError("Signaling closed during verify")
                for line in raw.decode("utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    act = obj.get("action")
                    if act == "pong":
                        verified = True
                    elif act:
                        verified = True
                        early.append(line)
                if verified:
                    break
            if not verified:
                raise TimeoutError("Signaling pong timeout")
            sock.settimeout(None)
            return sock, early
        except Exception as e:
            xp_log(f"[Signaling] Connect {srv_host}:{srv_port} failed: {e}", base_dir=self.base_dir)
            if sock:
                force_close_socket(sock)
            return None, []

    def _signaling_loop(self, my_gen):
        # Nếu tiến trình này không giữ được cổng 12345 (ví dụ GUI mở thêm khi Service đã giữ 12345),
        # đăng ký kèm hậu tố _{port} giống cơ chế signaling_server.py để không cướp ID chính của Service!
        reg_id = self.hwid if self.bound_port == 12345 else f"{self.hwid}_{self.bound_port}"

        while self.running and not self._stop_ev.is_set() and self._sig_gen == my_gen:
            hosts_raw, def_port = load_signaling_config(self.base_dir)
            targets = []
            for entry in hosts_raw:
                h, p = parse_signaling_host_entry(entry, def_port)
                if h and (h, p) not in targets:
                    targets.append((h, p))

            connected = None
            active_host = ""
            active_port = def_port
            early_msgs = []

            for sh, sp in targets:
                if not self.running or self._sig_gen != my_gen:
                    return
                sock, early = self._connect_one_signaling(sh, sp, reg_id)
                if sock is not None:
                    connected = sock
                    active_host = sh
                    active_port = sp
                    early_msgs = early
                    break
                if self._stop_ev.wait(random.uniform(1.0, 3.0)):
                    return

            if connected is None:
                self.signaling_online = False
                self._emit_status(f"Chế độ LAN sẵn sàng (Đang thử kết nối lại Signaling...)")
                if self._stop_ev.wait(random.uniform(8.0, 15.0)):
                    return
                continue

            with self._sig_lock:
                self._sig_sock = connected
            self.signaling_online = True
            self.signaling_server_active = f"{active_host}:{active_port}"
            self._emit_status(f"Trực tuyến sẵn sàng kết nối (ID: {self.hwid_display})")

            for em in early_msgs:
                self._handle_signaling_msg(em, connected, active_host, active_port)

            last_ping = time.time()
            last_pong = time.time()
            try:
                while self.running and not self._stop_ev.is_set() and self._sig_gen == my_gen:
                    r, _, _ = select.select([connected], [], [], 1.0)
                    if r:
                        msg_bytes = recv_msg(connected, APP_KEY, max_size=65536)
                        if msg_bytes is None or msg_bytes == b"":
                            break
                        txt = msg_bytes.decode("utf-8", errors="ignore")
                        for line in txt.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            if '"pong"' in line:
                                last_pong = time.time()
                            self._handle_signaling_msg(line, connected, active_host, active_port)
                    now = time.time()
                    if now - last_ping >= 20.0:
                        if not send_msg(connected, json.dumps({"action": "ping"}).encode("utf-8"), APP_KEY):
                            break
                        last_ping = now
                    if now - last_pong >= 55.0:
                        xp_log("[Signaling] Heartbeat timeout, reconnecting...", base_dir=self.base_dir)
                        break
            except Exception as e:
                xp_log(f"[Signaling] Monitor error: {e}", base_dir=self.base_dir)
            finally:
                self.signaling_online = False
                with self._sig_lock:
                    if self._sig_sock is connected:
                        self._sig_sock = None
                force_close_socket(connected)

    def _handle_signaling_msg(self, line, sig_sock, srv_host, srv_port):
        try:
            obj = json.loads(line)
        except Exception:
            return
        act = obj.get("action")
        if act == "incoming_request":
            from_hwid = obj.get("from_hwid")
            pub_ip = obj.get("public_ip")
            pub_port = int(obj.get("port") or obj.get("public_port") or 0)
            self.local_ip = get_local_ip()
            accept = json.dumps({
                "action": "connect_accept",
                "target": from_hwid,
                "port": self.bound_port,
                "local_ip": self.local_ip,
                "local_port": self.bound_port,
            }).encode("utf-8")
            with self._sig_lock:
                send_msg(sig_sock, accept, APP_KEY)
            if pub_ip and pub_port:
                threading.Thread(
                    target=self._punch_tcp_hole,
                    args=(pub_ip, pub_port),
                    daemon=True,
                ).start()
        elif act == "relay_request":
            session_id = obj.get("session_id")
            relay_entry = obj.get("relay_host") or f"{srv_host}:{srv_port}"
            if session_id:
                threading.Thread(
                    target=self._connect_relay_host,
                    args=(session_id, relay_entry, srv_port),
                    daemon=True,
                ).start()

    def _punch_tcp_hole(self, client_ip, client_port):
        time.sleep(1.5)
        for _ in range(8):
            if not self.running:
                return
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", self.bound_port))
            except Exception:
                pass
            s.settimeout(0.5)
            try:
                s.connect((client_ip, int(client_port)))
                s.settimeout(None)
                xp_log(f"[HolePunch] Direct P2P established to {client_ip}:{client_port}", base_dir=self.base_dir)
                threading.Thread(
                    target=self.on_client_socket,
                    args=(s, (client_ip, int(client_port))),
                    daemon=True,
                ).start()
                return
            except Exception:
                force_close_socket(s)
                time.sleep(0.12)

    def _connect_relay_host(self, session_id, relay_entry, default_port):
        r_host, r_port = parse_signaling_host_entry(relay_entry, default_port)
        if not r_host:
            return
        rs = None
        try:
            rs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            set_xp_keepalive(rs, 15000, 5000)
            rs.settimeout(8.0)
            rs.connect((r_host, int(r_port)))
            rs.settimeout(None)
            rs.sendall(f"RELAY_HOST:{session_id}\n".encode("utf-8"))
            xp_log(f"[Relay] Connected RELAY_HOST session={session_id} via {r_host}:{r_port}", base_dir=self.base_dir)
            threading.Thread(
                target=self.on_client_socket,
                args=(rs, (r_host, int(r_port))),
                daemon=True,
            ).start()
        except Exception as e:
            xp_log(f"[Relay] Failed session={session_id}: {e}", base_dir=self.base_dir)
            if rs:
                force_close_socket(rs)
