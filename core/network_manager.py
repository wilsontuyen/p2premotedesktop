import os
import sys
import time
import json
import socket
import struct
import threading
import subprocess
import tkinter as tk
import select
import traceback
import tempfile
import platform
import psutil
import re
import multiprocessing as mp
from tkinter import ttk, messagebox
try:
    from PIL import Image, ImageTk
except ImportError:
    pass

from core.i18n import _
from core.config import *
import core.config
from utils.hwid import get_local_ip, get_public_ip, get_public_ipv6
from network.socket_utils import socket_passwords, force_close_socket, APP_KEY


from network.socket_utils import send_msg, recv_msg, is_lan_socket, tune_socket_for_lan_bulk
from utils.vpn_discovery import (
    detect_vpn_interfaces, scan_vpn_network, scan_custom_range, probe_single_host, match_saved_computer,
    hash_password_md5, get_last_seen_epoch, format_last_seen_str,
    deduplicate_lan_peers, are_same_machine, merge_peers
)
from utils.logger import log_debug


def _handshake_is_android(res):
    if not isinstance(res, dict):
        return False
    if res.get("is_android"):
        return True
    osr = str(res.get("os_release") or "").lower()
    if "android" in osr:
        return True
    name = str(res.get("computer_name") or "")
    if name.startswith("MC-Android"):
        return True
    return False


def client_android_speed_test(sock, password, status_cb=None):
    """Mở khóa startFrameSender trên host Android.

    Handshake Android gọi triggerFullFrame() (xóa lastJpegBytes). Trong lúc
    đọc dummy, ImageReader kịp ghi lại JPEG cache. Gửi result quá sớm
    → FrameSender vào lúc cache trống, phải đợi capture mới (chậm hơn).
    """
    def _status(msg):
        if status_cb:
            try:
                status_cb(msg)
            except Exception:
                pass

    net_class, avg_ping, bandwidth = "medium", 50.0, 10.0
    try:
        sock.settimeout(8.0)
        _status(_("Đang kiểm tra chất lượng mạng..."))
        t0 = time.time()
        send_msg(sock, json.dumps({"action": "speed_test_ping"}).encode("utf-8"), password)
        pong_msg = recv_msg(sock, password)
        if pong_msg:
            try:
                pong_data = json.loads(pong_msg.decode("utf-8"))
            except Exception:
                pong_data = {}
            if pong_data.get("action") == "speed_test_pong":
                avg_ping = (time.time() - t0) * 1000.0

        send_msg(sock, json.dumps({"action": "speed_test_bw_req"}).encode("utf-8"), password)
        bw_start_msg = recv_msg(sock, password)
        if bw_start_msg:
            try:
                bw_start_data = json.loads(bw_start_msg.decode("utf-8"))
            except Exception:
                bw_start_data = {}
            if bw_start_data.get("action") == "speed_test_bw_start":
                dummy_size = int(bw_start_data.get("size", 1572864))
                dummy_size = max(1024, min(dummy_size, 1572864))
                got = b""
                t_bw = time.time()
                while len(got) < dummy_size:
                    chunk = sock.recv(min(65536, dummy_size - len(got)))
                    if not chunk:
                        break
                    got += chunk
                dur = time.time() - t_bw
                if dur > 0 and len(got) == dummy_size:
                    bandwidth = (dummy_size * 8.0) / (dur * 1024.0 * 1024.0)

        if bandwidth > 20.0 and avg_ping < 30.0:
            net_class = "high"
        elif bandwidth < 5.0 or avg_ping > 80.0:
            net_class = "low"
        else:
            net_class = "medium"
    except Exception as e:
        print(f"[Client] Android speed test error: {e}")
        net_class, avg_ping, bandwidth = "medium", 50.0, 10.0
    finally:
        try:
            sock.settimeout(None)
        except Exception:
            pass
    try:
        send_msg(sock, json.dumps({
            "action": "speed_test_result",
            "net_class": net_class,
            "ping": avg_ping,
            "bandwidth": bandwidth,
        }).encode("utf-8"), password)
    except Exception:
        pass
    return net_class, avg_ping, bandwidth


def client_quick_link_probe(sock, password, status_cb=None):
    """Phân loại mạng nhanh rồi cho host gửi khung hình. LAN bỏ đo băng thông (tiết kiệm vài giây)."""
    def _status(msg):
        if status_cb:
            try:
                status_cb(msg)
            except Exception:
                pass

    if is_lan_socket(sock):
        # Không gửi result trước khi mở viewer: host sẽ flood JPEG trên LAN
        # rồi multiprocessing nhân socket → Win7/LAN RST ngay ("mất kết nối").
        return "high", 1.0, 100.0

    _status(_("Đang kiểm tra chất lượng mạng..."))
    net_class, ping, bandwidth = "medium", 50.0, 10.0
    try:
        sock.settimeout(5.0)
        t0 = time.time()
        send_msg(sock, json.dumps({"action": "speed_test_ping"}).encode("utf-8"), password)
        pong_msg = recv_msg(sock, password)
        if pong_msg:
            pong_data = json.loads(pong_msg.decode("utf-8"))
            if pong_data.get("action") == "speed_test_pong":
                ping = (time.time() - t0) * 1000.0
        dummy_size = 262144
        if ping > 200.0:
            dummy_size = 65536
        elif ping > 50.0:
            dummy_size = 131072
        send_msg(sock, json.dumps({
            "action": "speed_test_bw_req",
            "suggested_size": dummy_size,
        }).encode("utf-8"), password)
        bw_start_msg = recv_msg(sock, password)
        if bw_start_msg:
            bw_start_data = json.loads(bw_start_msg.decode("utf-8"))
            if bw_start_data.get("action") == "speed_test_bw_start":
                dummy_size = int(bw_start_data.get("size", dummy_size))
                t_start = time.time()
                got = b""
                while len(got) < dummy_size:
                    chunk = sock.recv(min(65536, dummy_size - len(got)))
                    if not chunk:
                        break
                    got += chunk
                dur = time.time() - t_start
                if dur > 0 and len(got) == dummy_size:
                    bandwidth = (dummy_size * 8.0) / (dur * 1024.0 * 1024.0)
        if bandwidth > 20.0 and ping < 30.0:
            net_class = "high"
        elif bandwidth < 5.0 or ping > 80.0:
            net_class = "low"
        else:
            net_class = "medium"
    except Exception as e:
        print(f"[Client] Speed test error: {e}")
        net_class, ping, bandwidth = "medium", 50.0, 10.0
    finally:
        try:
            sock.settimeout(None)
        except Exception:
            pass
    try:
        send_msg(sock, json.dumps({
            "action": "speed_test_result",
            "net_class": net_class,
            "ping": ping,
            "bandwidth": bandwidth,
        }).encode("utf-8"), password)
    except Exception:
        pass
    return net_class, ping, bandwidth
from network.upnp import attempt_upnp_forward
try:
    from host_build_flag import HOST_ONLY_BUILD
except Exception:
    HOST_ONLY_BUILD = False
if HOST_ONLY_BUILD:
    run_client_viewer_loop = None
else:
    from core.viewer import run_client_viewer_loop

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class NetworkMixin:
    def _is_host_only_app(self):
        """Host build / host.mode: incoming sessions only — no outbound viewer."""
        return bool(getattr(self, "is_host_only", False) or HOST_ONLY_BUILD)

    def add_firewall_rule_for_app(self):
        try:
            import sys, os, subprocess
            exe_path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
            rule_name = "EasyRemoteDesktop_P2P"
            subprocess.run(f'netsh advfirewall firewall delete rule name="{rule_name}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(f'netsh advfirewall firewall add rule name="{rule_name}" dir=in action=allow program="{exe_path}" enable=yes profile=any', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def configure_uac_registry(self):
        if sys.platform != "win32":
            return
        from utils.windows_uac import apply_remote_uac_desktop_policy
        ok, err = apply_remote_uac_desktop_policy()
        if ok:
            print("[Host] Successfully configured registry (PromptOnSecureDesktop=0, SoftwareSASGeneration=3).")
        elif isinstance(err, PermissionError) or (err and "Access is denied" in str(err)):
            print("[Host] WARNING: No Admin rights → PromptOnSecureDesktop cannot be set. UAC prompts may freeze screen.")
        elif err:
            print(f"[Host] Failed to configure registry for UAC: {err}")

    def wake_on_lan(self, mac_str, extra_ips=None):
        # mac_str can be multiple MACs separated by comma
        dest_ips = ["255.255.255.255"]
        try:
            local_ips = getattr(self, 'local_ip', get_local_ip()).split(',')
            for lip in local_ips:
                lip = lip.strip()
                if lip and not lip.startswith('127.'):
                    parts = lip.split('.')
                    if len(parts) == 4:
                        dest_ips.append(f"{parts[0]}.{parts[1]}.{parts[2]}.255")
        except Exception:
            pass
        for extra in extra_ips or []:
            if not extra:
                continue
            for ip in str(extra).split(","):
                ip = ip.strip()
                if ip and ip not in dest_ips:
                    dest_ips.append(ip)
                    parts = ip.split(".")
                    if len(parts) == 4:
                        bcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                        if bcast not in dest_ips:
                            dest_ips.append(bcast)
        sent_any = False
        for m in mac_str.split(','):
            m = m.strip()
            if not m: continue
            try:
                # Remove common separators
                mac = m.replace(':', '').replace('-', '').replace('.', '')
                if len(mac) != 12:
                    continue
                data = bytes.fromhex('F' * 12 + mac * 16)
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                for ip in dest_ips:
                    for port in (9, 7):
                        try:
                            sock.sendto(data, (ip, port))
                        except Exception:
                            pass
                sock.close()
                sent_any = True
                self.update_status(_("Đã gửi Wake-On-Lan tới MAC {mac}").format(mac=m), is_success=True)
            except Exception as e:
                print(f"[WOL] Lỗi gửi Wake-On-Lan tới MAC {m}: {e}")
        if not sent_any:
            print("[WOL] Không gửi được: MAC trống hoặc không hợp lệ.")

    # ==================== LAN DISCOVERY (UDP Broadcast) ====================
    def start_lan_discovery(self):
        """Khởi chạy 2 luồng: beacon broadcaster và beacon listener cho LAN Discovery."""
        threading.Thread(target=self._lan_beacon_sender, daemon=True).start()
        threading.Thread(target=self._lan_beacon_listener, daemon=True).start()
        print("[LAN Discovery] Started beacon sender and listener threads.")

    def _lan_beacon_sender(self):
        """Phát UDP broadcast beacon mỗi LAN_BEACON_INTERVAL giây."""
        import platform
        
        comp_name = platform.node()
        # Host Windows build does not advertise as Android.
        if not self._is_host_only_app():
            try:
                import os, sys
                is_android = 'ANDROID_ARGUMENT' in os.environ or 'ANDROID_BOOTLOGO' in os.environ
                if hasattr(sys, 'getandroidapilevel'):
                    is_android = True
                if is_android:
                    serial = ""
                    try:
                        with open("/sys/block/mmcblk0/device/serial", "r") as f:
                            serial = f.read().strip()
                            if serial.startswith("0x"):
                                serial = serial[2:]
                    except Exception:
                        pass
                    if serial:
                        comp_name = f"MC-Android {serial}"
            except Exception:
                pass

        while getattr(self, 'running_server', True):
            if not self.is_headless and getattr(self, "is_service_active", False):
                # Service is active, GUI app should not broadcast beacon to avoid hijacking LAN connection
                time.sleep(LAN_BEACON_INTERVAL)
                continue
            try:
                beacon = json.dumps({
                    "sig": LAN_APP_SIGNATURE,
                    "hwid": self.my_id_clean,
                    "computer_name": comp_name,
                    "port": BOUND_PORT,
                    "local_ip": getattr(self, 'local_ip', get_local_ip()),
                    "macs": getattr(self, 'my_macs', "")
                }).encode('utf-8')
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(1.0)
                try:
                    sock.sendto(beacon, ('255.255.255.255', LAN_DISCOVERY_PORT))
                except Exception:
                    pass
                # Gửi thêm tới các subnet broadcast cụ thể (hỗ trợ router chặn global broadcast)
                try:
                    local_ips = getattr(self, 'local_ip', '').split(',')
                    for lip in local_ips:
                        lip = lip.strip()
                        if lip and not lip.startswith('127.'):
                            parts = lip.split('.')
                            if len(parts) == 4:
                                subnet_broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                                sock.sendto(beacon, (subnet_broadcast, LAN_DISCOVERY_PORT))
                except Exception:
                    pass
                sock.close()
            except Exception as e:
                print(f"[LAN Discovery] Beacon send error: {e}")
            time.sleep(LAN_BEACON_INTERVAL)

    def _lan_beacon_listener(self):
        """Lắng nghe UDP broadcast beacon từ các máy khác trong LAN."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind(('', LAN_DISCOVERY_PORT))
        except Exception as e:
            print(f"[LAN Discovery] Cannot bind UDP listener on port {LAN_DISCOVERY_PORT}: {e}")
            return
        sock.settimeout(2.0)
        
        while getattr(self, 'running_server', True):
            try:
                data, addr = sock.recvfrom(4096)
                try:
                    beacon = json.loads(data.decode('utf-8'))
                except Exception:
                    continue
                    
                # Xác thực beacon
                if beacon.get("sig") != LAN_APP_SIGNATURE:
                    continue
                    
                peer_hwid = beacon.get("hwid", "")
                # Bỏ qua chính mình
                if peer_hwid == self.my_id_clean:
                    continue
                    
                peer_info = {
                    "computer_name": beacon.get("computer_name", "Unknown"),
                    "name_verified": True,
                    "local_ip": beacon.get("local_ip", addr[0]),
                    "port": int(beacon.get("port", 12345)),
                    "hwid": peer_hwid,
                    "macs": beacon.get("macs", ""),
                    "last_seen": time.time(),
                    "source_ip": addr[0],
                }
                
                with self.lan_peers_lock:
                    matched_k = None
                    for k, v in self.lan_peers.items():
                        if k == peer_hwid or are_same_machine(k, v, peer_hwid, peer_info):
                            matched_k = k
                            break
                    old_ip = None
                    if matched_k:
                        old_info = self.lan_peers[matched_k]
                        old_ip = old_info.get("local_ip")
                        peer_info = merge_peers(peer_info, old_info)
                        if matched_k != peer_hwid:
                            self.lan_peers.pop(matched_k, None)
                    is_new = matched_k is None
                    should_save = is_new or (old_ip != peer_info.get("local_ip"))
                    self.lan_peers[peer_hwid] = peer_info
                    
                if should_save:
                    self.save_lan_peers()
                    
                if is_new:
                    fmt_id = f"{peer_hwid[:3]} {peer_hwid[3:6]} {peer_hwid[6:9]} {peer_hwid[9:]}" if len(peer_hwid) == 12 else peer_hwid
                    print(f"[LAN Discovery] Phát hiện máy mới: {peer_info['computer_name']} ({fmt_id}) tại {peer_info['local_ip']}:{peer_info['port']}")
            except socket.timeout:
                continue
            except Exception as e:
                if getattr(self, 'running_server', True):
                    print(f"[LAN Discovery] Listener error: {e}")
                time.sleep(1)

    def show_lan_computers_dialog(self):
        """Hiển thị dialog danh sách các máy tính phát hiện được trong mạng LAN & VPN."""
        if self._is_host_only_app():
            return
        if hasattr(self, 'lan_computers_dialog') and self.lan_computers_dialog.winfo_exists():
            # Đọc lại file lan_peers.json đã có đưa vào dialog hiển thị
            try:
                stored = self.load_lan_peers()
                if stored and isinstance(stored, dict):
                    with self.lan_peers_lock:
                        self.lan_peers = deduplicate_lan_peers(dict(stored))
                    self.save_lan_peers()
            except Exception:
                pass
            if self.lan_computers_dialog.state() == 'withdrawn':
                self.lan_computers_dialog.deiconify()
            self.lan_computers_dialog.lift()
            self.lan_computers_dialog.focus_force()
            if hasattr(self, '_lan_refresh_list_func') and self._lan_refresh_list_func:
                self._lan_refresh_list_func()
            return

        # Đọc lại file lan_peers.json đã có đưa vào dialog hiển thị các máy
        try:
            stored = self.load_lan_peers()
            if stored and isinstance(stored, dict):
                with self.lan_peers_lock:
                    self.lan_peers = deduplicate_lan_peers(dict(stored))
                self.save_lan_peers()
        except Exception:
            pass
            
        dialog = tk.Toplevel(self)
        dialog.withdraw()  # Ẩn tạm thời để tính toán kích thước/vị trí tránh nháy hình
        self.lan_computers_dialog = dialog
        dialog.title(_("Máy tính trong mạng LAN & VPN"))
        dialog.resizable(True, True)
        dialog.configure(bg=self.bg_color)
        dialog.transient(self)  # Gắn transient vào cửa sổ chính để không tạo thêm icon riêng trên Taskbar (giống Danh sách máy tính đã lưu)

        w, h = 640, 540
        parent_x = self.winfo_x()
        parent_y = self.winfo_y()
        parent_w = self.winfo_width()
        parent_h = self.winfo_height()

        # Căn giữa theo chiều ngang cửa sổ chính
        x = max(10, parent_x + (parent_w - w) // 2)
        
        # Căn dọc: Khi app chính ở sát đỉnh màn hình, đặt dialog thẳng hàng với mép trên hoặc thấp hơn
        # Tuyệt đối không để y < parent_y và không nhảy lên khỏi mép trên màn hình
        y = max(parent_y + 15, 35)
        try:
            screen_h = self.winfo_screenheight()
            if y + h > screen_h - 40:
                y = max(35, screen_h - h - 40)
        except Exception:
            pass

        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.minsize(600, 480)
        dialog.deiconify()
        dialog.lift()
        dialog.focus_force()

        # Title
        lbl_title = tk.Label(dialog, text=_("📡 MÁY TÍNH TRONG MẠNG LAN & VPN"), font=("Segoe UI", 11, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(12, 2))
        
        lbl_desc = tk.Label(dialog, text=_("Kết nối trực tiếp tốc độ cao qua mạng nội bộ hoặc VPN (không qua Signaling Server)"), font=("Segoe UI", 8, "italic"), fg=self.text_gray, bg=self.bg_color)
        lbl_desc.pack(pady=(0, 8))

        # Nhận diện các mạng VPN đang hoạt động trên máy
        detected_vpns = detect_vpn_interfaces()

        # VPN Toolbar
        vpn_toolbar = tk.Frame(dialog, bg=getattr(self, 'card_color', '#252836'), bd=0, padx=10, pady=6)
        vpn_toolbar.pack(fill=tk.X, padx=20, pady=(0, 6))

        if detected_vpns:
            vpn_names = ", ".join(f"{v['vpn_type']} ({v['ip']})" for v in detected_vpns)
            vpn_info_text = f"🛡️ " + _("Phát hiện VPN: ") + vpn_names
            lbl_vpn_info = tk.Label(vpn_toolbar, text=vpn_info_text, font=("Segoe UI", 8), fg="#56CCF2", bg=getattr(self, 'card_color', '#252836'), anchor=tk.W)
            lbl_vpn_info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        else:
            lbl_vpn_info = tk.Label(vpn_toolbar, text="🛡️ " + _("VPN: Chưa phát hiện card mạng VPN (Có thể quét theo dải IP tùy chọn)"), font=("Segoe UI", 8, "italic"), fg=self.text_gray, bg=getattr(self, 'card_color', '#252836'), anchor=tk.W)
            lbl_vpn_info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_vpn_scan = tk.Button(vpn_toolbar, text=_("🛡️ Quét VPN"), font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#8E44AD", activebackground="#9B59B6", relief=tk.FLAT, bd=0, padx=8, pady=2, cursor="hand2")
        btn_vpn_scan.pack(side=tk.RIGHT, padx=(4, 0))

        btn_custom_scan = tk.Button(vpn_toolbar, text=_("🌐 Dải IP..."), font=("Segoe UI", 8, "bold"), fg="#FFFFFF", bg="#2980B9", activebackground="#3498DB", relief=tk.FLAT, bd=0, padx=8, pady=2, cursor="hand2")
        btn_custom_scan.pack(side=tk.RIGHT, padx=(0, 4))

        # Progress / Status label
        progress_label = tk.Label(dialog, text="", font=("Segoe UI", 8, "italic"), fg="#56CCF2", bg=self.bg_color)
        progress_label.pack(pady=(0, 4))

        # Scrollable list frame
        list_outer = tk.Frame(dialog, bg=self.entry_bg, bd=1, relief=tk.SUNKEN)
        list_outer.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 8))

        canvas = tk.Canvas(list_outer, bg=self.entry_bg, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_outer, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=self.entry_bg)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas_win_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win_id, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Status label
        status_label = tk.Label(dialog, text="", font=("Segoe UI", 8, "italic"), fg=self.text_gray, bg=self.bg_color)
        status_label.pack(pady=(0, 4))

        # Quản lý luồng quét & trạng thái trực tuyến
        scan_state = {
            "is_scanning": False,
            "cancel_event": threading.Event(),
            "online_status": {},  # hwid -> bool (True=Online, False=Offline, None=Checking)
            "probe_gen": 0,
        }

        def _persist_peer_password(target_hwid, peer_info, new_pw):
            """Lưu mật khẩu đồng bộ vào cả saved_computers.xml và lan_peers.json."""
            comp_name = str(peer_info.get("computer_name") or "").strip()
            # Ưu tiên HWID thực tế 12 số của peer
            p_hw = ''.join(ch for ch in str(peer_info.get("hwid") or target_hwid or "") if ch.isdigit())
            p_sid = ''.join(ch for ch in str(peer_info.get("saved_id") or "") if ch.isdigit())
            canonical_id = p_hw if len(p_hw) == 12 else (p_sid if len(p_sid) == 12 else (p_hw or p_sid or target_hwid))

            # 1. Cập nhật saved_computers.xml (cập nhật tất cả các bản ghi trùng ID hoặc tên để không sót mật khẩu cũ)
            comps = self.load_saved_computers()
            matched_existing = match_saved_computer(comp_name, canonical_id, canonical_id)
            matched_existing_id = ''.join(ch for ch in str(matched_existing.get('id', '')) if ch.isdigit()) if matched_existing else ''
            matched_existing_name = str(matched_existing.get('name', '')).strip().lower() if matched_existing else ''

            id_targets = {x for x in (canonical_id, matched_existing_id) if x}
            name_targets = {x for x in (comp_name.lower(), matched_existing_name) if x and x not in ('unknown', 'không rõ')}

            fmt_saved_id = f"{canonical_id[:3]} {canonical_id[3:6]} {canonical_id[6:9]} {canonical_id[9:]}" if len(canonical_id) == 12 else canonical_id
            updated_any = False
            for idx, c in enumerate(comps):
                c_id_clean = ''.join(ch for ch in str(c.get('id', '')) if ch.isdigit())
                c_name_lower = str(c.get('name', '')).strip().lower()
                if (c_id_clean and c_id_clean in id_targets) or (c_name_lower and c_name_lower in name_targets):
                    comps[idx]["password"] = new_pw
                    # Cập nhật ID chuẩn nếu bản ghi cũ bị sai hoặc thiếu
                    if len(canonical_id) == 12:
                        comps[idx]["id"] = fmt_saved_id
                    updated_any = True

            group_label = peer_info.get("network_type") or _("Mạng LAN & VPN")
            if not updated_any:
                comps.append({
                    "name": comp_name or target_hwid,
                    "id": fmt_saved_id,
                    "password": new_pw,
                    "group": group_label
                })
            self.save_saved_computers(comps)
            if hasattr(self, '_reorder_saved_computers_func'):
                self.after(50, self._reorder_saved_computers_func)

            # 2. Cập nhật trực tiếp vào peer_info và toàn bộ bản ghi tương ứng trong self.lan_peers rồi ghi ra lan_peers.json
            pw_md5 = hash_password_md5(new_pw)
            peer_info["saved_password"] = pw_md5
            peer_info["saved_id"] = canonical_id
            peer_info["hwid"] = canonical_id

            with self.lan_peers_lock:
                found_in_peers = False
                for k, v in list(self.lan_peers.items()):
                    if k == target_hwid or k == canonical_id or are_same_machine(k, v, canonical_id, peer_info):
                        v["saved_password"] = pw_md5
                        v["saved_id"] = canonical_id
                        v["hwid"] = canonical_id
                        found_in_peers = True
                if not found_in_peers and canonical_id:
                    self.lan_peers[canonical_id] = dict(peer_info)

            self.save_lan_peers()

        def connect_to_peer(hwid, peer_info, force_prompt=False):
            # Lưu lại hàm gọi để có thể mở lại khi sai mật khẩu
            self._last_lan_connect_fn = lambda fp=True: connect_to_peer(hwid, peer_info, force_prompt=fp)

            # 1. Tìm đối chiếu máy tính trong saved_computers (chỉ khớp chính xác HWID, saved_id hoặc tên)
            existing_comp = match_saved_computer(peer_info.get("computer_name"), hwid, peer_info.get("saved_id"))
            saved_pw = existing_comp.get("password", "") if existing_comp else ""
            saved_id = (existing_comp.get("id", "") if existing_comp else "") or peer_info.get("saved_id") or hwid

            # Đồng bộ lại thông tin vào peer_info (mã hóa MD5 mật khẩu, không xóa hash cũ nếu chưa khớp)
            if saved_pw:
                peer_info["saved_password"] = hash_password_md5(saved_pw)
            peer_info["saved_id"] = saved_id

            clean_id = ''.join(ch for ch in str(saved_id) if ch.isdigit()) if saved_id else ''.join(ch for ch in str(hwid) if ch.isdigit())
            fmt_id = f"{clean_id[:3]} {clean_id[3:6]} {clean_id[6:9]} {clean_id[9:]}" if len(clean_id) == 12 else (saved_id or hwid)

            # Điền ID và Mật khẩu lên cửa sổ chính để người dùng thấy rõ
            if hasattr(self, 'partner_id_var'):
                self.partner_id_var.set(fmt_id)
            if saved_pw and hasattr(self, 'partner_pass_var'):
                self.partner_pass_var.set(saved_pw)

            # Nếu đã lưu và có mật khẩu và không ép nhập lại, kết nối luôn không cần hỏi lại
            if saved_pw and not force_prompt:
                self.update_status(_("Đang kết nối trực tiếp tới {name}...").format(name=peer_info['computer_name']))
                if hasattr(self, 'connect_btn'):
                    self.connect_btn.config(state=tk.DISABLED)
                threading.Thread(target=self._connect_lan_direct, args=(hwid, peer_info, saved_pw), daemon=True).start()
                return

            """Mở dialog nhập mật khẩu rồi kết nối trực tiếp qua LAN/VPN."""
            if hasattr(self, '_active_lan_pass_dialog') and self._active_lan_pass_dialog:
                try:
                    if self._active_lan_pass_dialog.winfo_exists():
                        self._active_lan_pass_dialog.destroy()
                except Exception:
                    pass

            pass_dialog = tk.Toplevel(dialog)
            self._active_lan_pass_dialog = pass_dialog
            pass_dialog.withdraw()
            pass_dialog.title(_("Kết nối tới ") + str(peer_info['computer_name']))
            pass_dialog.resizable(False, False)
            pass_dialog.configure(bg=self.bg_color)
            pass_dialog.transient(dialog)
            pass_dialog.bind("<Escape>", lambda e: pass_dialog.destroy())

            pw, ph = 360, 230
            dialog.update_idletasks()
            px = dialog.winfo_x() + (dialog.winfo_width() - pw) // 2
            py = dialog.winfo_y() + (dialog.winfo_height() - ph) // 2
            pass_dialog.geometry(f"{pw}x{ph}+{px}+{py}")

            fmt_id = f"{hwid[:3]} {hwid[3:6]} {hwid[6:9]} {hwid[9:]}" if len(hwid) == 12 else hwid
            tk.Label(pass_dialog, text=_("Máy: ") + str(peer_info['computer_name']), font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.bg_color).pack(pady=(15, 2))
            tk.Label(pass_dialog, text=_("ID: ") + str(fmt_id) + _("  •  IP: ") + str(peer_info['local_ip']), font=("Segoe UI", 8), fg=self.text_gray, bg=self.bg_color).pack(pady=(0, 10))

            tk.Label(pass_dialog, text=_("Nhập mật khẩu:"), font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color).pack(anchor=tk.W, padx=30)
            
            pass_var = tk.StringVar(value=saved_pw)
            pass_entry = tk.Entry(pass_dialog, textvariable=pass_var, font=("Segoe UI", 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, show="*", relief=tk.FLAT, bd=4)
            pass_entry.pack(padx=30, fill=tk.X, pady=(3, 5))
            
            save_var = tk.BooleanVar(value=True)
            save_cb = tk.Checkbutton(pass_dialog, text=_("Lưu mật khẩu máy tính này"), variable=save_var, font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color, selectcolor=self.bg_color, activebackground=self.bg_color, activeforeground=self.text_gray, cursor="hand2")
            save_cb.pack(anchor=tk.W, padx=25, pady=(0, 10))
            
            pass_dialog.deiconify()
            pass_dialog.lift()
            pass_dialog.grab_set()
            pass_entry.focus_set()
            if saved_pw:
                pass_entry.select_range(0, tk.END)
            
            def do_connect():
                password = pass_var.get().strip()
                if not password:
                    self.show_custom_error(_("Lỗi"), _("Vui lòng nhập mật khẩu!"), parent=pass_dialog)
                    return
                    
                if save_var.get():
                    _persist_peer_password(hwid, peer_info, password)
                    refresh_list()
                        
                pass_dialog.destroy()
                self.update_status(_("Đang kết nối trực tiếp tới {name}...").format(name=peer_info['computer_name']))
                if hasattr(self, 'connect_btn'):
                    self.connect_btn.config(state=tk.DISABLED)
                threading.Thread(target=self._connect_lan_direct, args=(hwid, peer_info, password), daemon=True).start()

            pass_entry.bind("<Return>", lambda e: do_connect())
            pass_entry.bind("<KP_Enter>", lambda e: do_connect())

            btn_frame = tk.Frame(pass_dialog, bg=self.bg_color)
            btn_frame.pack(fill=tk.X, padx=30, pady=(0, 15))
            tk.Button(btn_frame, text=_("Kết nối"), font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, pady=4, cursor="hand2", command=do_connect).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
            tk.Button(btn_frame, text=_("Hủy"), font=("Segoe UI", 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, relief=tk.FLAT, bd=0, pady=4, cursor="hand2", command=pass_dialog.destroy).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

        def open_change_lan_password_dialog(hwid, peer_info):
            """Hộp thoại thay đổi mật khẩu cho máy trong danh sách LAN & VPN."""
            existing = match_saved_computer(peer_info.get("computer_name"), hwid, peer_info.get("saved_id"))
            current_pw = existing.get("password", "") if existing else ""
            
            pwd_win = tk.Toplevel(dialog)
            pwd_win.withdraw()
            pwd_win.title(_("Thay đổi mật khẩu"))
            pwd_win.resizable(False, False)
            pwd_win.configure(bg=self.bg_color)
            pwd_win.transient(dialog)
            pwd_win.grab_set()
            pwd_win.bind("<Escape>", lambda e: pwd_win.destroy())

            pw, ph = 360, 220
            px = dialog.winfo_x() + (dialog.winfo_width() - pw) // 2
            py = dialog.winfo_y() + (dialog.winfo_height() - ph) // 2
            pwd_win.geometry(f"{pw}x{ph}+{px}+{py}")
            pwd_win.deiconify()

            comp_name = peer_info.get("computer_name", _("Máy tính"))
            disp_id = peer_info.get("hwid") or peer_info.get("saved_id") or hwid
            clean_h = ''.join(ch for ch in str(disp_id) if ch.isdigit())
            fmt_id = f"{clean_h[:3]} {clean_h[3:6]} {clean_h[6:9]} {clean_h[9:]}" if len(clean_h) == 12 else disp_id

            lbl_title = tk.Label(pwd_win, text=_("🔑 THAY ĐỔI MẬT KHẨU"), font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
            lbl_title.pack(pady=(15, 4))

            lbl_sub = tk.Label(pwd_win, text=f"💻 {comp_name}  •  ID: {fmt_id}", font=("Segoe UI", 8), fg=self.text_gray, bg=self.bg_color)
            lbl_sub.pack(pady=(0, 10))

            tk.Label(pwd_win, text=_("Nhập mật khẩu mới:"), font=("Segoe UI", 9), fg=self.text_white, bg=self.bg_color).pack(anchor=tk.W, padx=30)

            pw_var = tk.StringVar(value=current_pw)
            entry_pw = tk.Entry(pwd_win, textvariable=pw_var, font=("Segoe UI", 12), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, show="*", relief=tk.FLAT, bd=4)
            entry_pw.pack(fill=tk.X, padx=30, pady=(4, 15))
            entry_pw.focus()
            if current_pw:
                entry_pw.select_range(0, tk.END)

            def do_save_password():
                new_pw = pw_var.get().strip()
                if not new_pw:
                    self.show_custom_error(_("Lỗi"), _("Mật khẩu không được để trống!"), parent=pwd_win)
                    return

                _persist_peer_password(hwid, peer_info, new_pw)

                # Cập nhật partner_pass_var nếu ID khớp
                if hasattr(self, 'partner_pass_var'):
                    self.partner_pass_var.set(new_pw)

                pwd_win.destroy()
                refresh_list()
                progress_label.config(text=_("Đã cập nhật mật khẩu cho {name}!").format(name=comp_name))
                dialog.after(3000, lambda: progress_label.config(text=""))

            entry_pw.bind("<Return>", lambda e: do_save_password())
            entry_pw.bind("<KP_Enter>", lambda e: do_save_password())

            btn_f = tk.Frame(pwd_win, bg=self.bg_color)
            btn_f.pack(fill=tk.X, padx=30, pady=(0, 15))
            tk.Button(btn_f, text=_("Lưu"), font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=do_save_password).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
            tk.Button(btn_f, text=_("Hủy"), font=("Segoe UI", 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=pwd_win.destroy).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

        def delete_lan_peer(hwid, peer_info):
            """Xóa máy tính khỏi danh sách LAN & VPN."""
            comp_name = peer_info.get("computer_name", hwid)
            if self.show_custom_question(_("Xóa máy tính"), _("Bạn có chắc muốn xóa") + f" '{comp_name}' " + _("khỏi danh sách?"), parent=dialog):
                with self.lan_peers_lock:
                    self.lan_peers.pop(hwid, None)
                self.save_lan_peers()
                refresh_list()
                progress_label.config(text=_("Đã xóa '{name}' khỏi danh sách!").format(name=comp_name))
                dialog.after(3000, lambda: progress_label.config(text=""))


        class RowTooltip:
            """Hiển thị tooltip chi tiết khi rê chuột vào hàng hoặc tên máy tính."""
            def __init__(self, widgets, text):
                self.widgets = widgets if isinstance(widgets, (list, tuple)) else [widgets]
                self.text = text
                self.tw = None
                self.after_id = None
                self.lbl_widget = None
                for w in self.widgets:
                    w.bind("<Enter>", self.schedule_show, add="+")
                    w.bind("<Leave>", self.hide, add="+")
                    w.bind("<ButtonPress>", self.hide, add="+")
                    w.bind("<Destroy>", self.hide, add="+")

            def update_text(self, new_text):
                self.text = new_text
                try:
                    if self.tw and self.lbl_widget and self.lbl_widget.winfo_exists():
                        self.lbl_widget.config(text=new_text)
                except Exception:
                    pass

            def schedule_show(self, event=None):
                self.hide()
                if self.widgets:
                    try:
                        self.after_id = self.widgets[0].after(250, self.show)
                    except Exception:
                        pass

            def show(self, event=None):
                if not self.widgets:
                    return
                w0 = self.widgets[0]
                try:
                    if not w0.winfo_exists():
                        return
                    x, y = w0.winfo_pointerxy()
                    x += 15
                    y += 12
                    screen_w = w0.winfo_screenwidth()
                    screen_h = w0.winfo_screenheight()
                    if x + 340 > screen_w:
                        x = max(10, screen_w - 350)
                    if y + 210 > screen_h:
                        y = max(10, y - 220)

                    self.tw = tk.Toplevel(w0)
                    self.tw.wm_overrideredirect(True)
                    self.tw.wm_geometry(f"+{x}+{y}")
                    self.tw.configure(bg="#374151") # Viền màu xám đậm hiện đại
                    
                    inner = tk.Frame(self.tw, bg="#1E202B", padx=10, pady=8)
                    inner.pack(padx=1, pady=1)
                    
                    self.lbl_widget = tk.Label(
                        inner, text=self.text, font=("Segoe UI", 8),
                        fg="#E6EDF3", bg="#1E202B", justify=tk.LEFT, anchor="w"
                    )
                    self.lbl_widget.pack()
                except Exception:
                    self.hide()

            def hide(self, event=None):
                if self.after_id:
                    try:
                        if self.widgets and self.widgets[0].winfo_exists():
                            self.widgets[0].after_cancel(self.after_id)
                    except Exception:
                        pass
                    self.after_id = None
                if self.tw:
                    try:
                        self.tw.destroy()
                    except Exception:
                        pass
                    self.tw = None
                self.lbl_widget = None

        # Bộ đệm cập nhật danh sách chống nháy giật màn hình
        refresh_timer = [None]
        def schedule_refresh(delay_ms=160):
            if not dialog.winfo_exists():
                return
            if refresh_timer[0] is not None:
                try:
                    dialog.after_cancel(refresh_timer[0])
                except Exception:
                    pass
            refresh_timer[0] = dialog.after(delay_ms, refresh_list)

        def _is_self_peer(p_hwid, p_info):
            """Kiểm tra xem peer có phải là máy tính hiện tại (self) hay không."""
            my_clean = ''.join(ch for ch in str(getattr(self, "my_id_clean", "") or "") if ch.isdigit())
            if not my_clean:
                try:
                    from utils.hwid import get_hwid
                    my_clean = ''.join(ch for ch in str(get_hwid()[0] or "") if ch.isdigit())
                except Exception:
                    my_clean = ""
            k_clean = ''.join(ch for ch in str(p_hwid or "") if ch.isdigit())
            h_clean = ''.join(ch for ch in str((p_info or {}).get("hwid") or "") if ch.isdigit())
            s_clean = ''.join(ch for ch in str((p_info or {}).get("saved_id") or "") if ch.isdigit())
            if my_clean and (my_clean == k_clean or my_clean == h_clean or my_clean == s_clean):
                return True
            p_name = str((p_info or {}).get("computer_name") or "").strip().lower()
            my_hostname = socket.gethostname().strip().lower()
            if p_name and p_name == my_hostname and p_name not in ("unknown", "không rõ", "localhost"):
                return True
            p_ips = [x.strip() for x in (str((p_info or {}).get("local_ip", "")) + "," + str((p_info or {}).get("source_ip", ""))).split(",") if x.strip()]
            try:
                my_ips = get_all_local_ipv4()
            except Exception:
                my_ips = set()
            if any(ip in my_ips for ip in p_ips if not ip.startswith("127.")):
                return True
            my_macs_raw = str(getattr(self, "my_macs", "") or "")
            if not my_macs_raw:
                try:
                    from utils.hwid import get_hwid
                    my_macs_raw = str(get_hwid()[2] or "")
                except Exception:
                    pass
            my_mac_list = [re.sub(r'[^A-Fa-f0-9]', '', m).upper() for m in my_macs_raw.split(',') if len(m) >= 12]
            p_macs = [re.sub(r'[^A-Fa-f0-9]', '', m).upper() for m in str((p_info or {}).get("macs") or "").split(',') if len(m) >= 12]
            if any(m in my_mac_list for m in p_macs if not all(c == '0' for c in m)):
                return True
            return False

        def _on_peer_found(p):
            if not p or not p.get("hwid"):
                return
            # Loại bỏ hoàn toàn nếu là ID/máy tính của chính mình
            if _is_self_peer(p.get("hwid"), p):
                return
            with self.lan_peers_lock:
                # Kiểm tra máy này đã tồn tại chưa bằng are_same_machine (trùng HWID, MAC, tên máy hoặc IP)
                existing_key = None
                for k, v in self.lan_peers.items():
                    if are_same_machine(k, v, p["hwid"], p):
                        existing_key = k
                        break

                if existing_key:
                    old = self.lan_peers[existing_key]
                    # p vừa được dò trực tiếp (mới nhất), gộp thông tin bổ sung từ old vào p
                    p = merge_peers(p, old)
                    target_key = p.get("hwid") or existing_key
                    if existing_key != target_key:
                        try:
                            del self.lan_peers[existing_key]
                        except Exception:
                            pass
                        scan_state.setdefault("online_status", {}).pop(existing_key, None)
                    self.lan_peers[target_key] = p
                    scan_state.setdefault("online_status", {})[target_key] = True
                else:
                    self.lan_peers[p["hwid"]] = p
                    scan_state.setdefault("online_status", {})[p["hwid"]] = True

            if dialog.winfo_exists():
                schedule_refresh(150)

        def get_custom_ip_file():
            try:
                from pclist import get_app_data_dir
                b = get_app_data_dir()
            except Exception:
                b = os.path.dirname(os.path.abspath(__file__))
            if sys.platform == "win32" and not os.access(b, os.W_OK):
                appdata = os.environ.get("APPDATA")
                if appdata:
                    folder = os.path.join(appdata, "EasyRemoteDesktop")
                    try:
                        os.makedirs(folder, exist_ok=True)
                        return os.path.join(folder, "custom_ip_range.json")
                    except Exception:
                        pass
            return os.path.join(b, "custom_ip_range.json")

        def load_saved_custom_ip(default_s, default_e):
            fpath = get_custom_ip_file()
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        s = data.get("start_ip", "").strip()
                        e = data.get("end_ip", "").strip()
                        if s and e:
                            return s, e
                except Exception:
                    pass
            return default_s, default_e

        def save_saved_custom_ip(s_ip, e_ip):
            fpath = get_custom_ip_file()
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump({"start_ip": s_ip.strip(), "end_ip": e_ip.strip()}, f, indent=2)
            except Exception as e:
                print(f"[Custom IP] Save error: {e}")

        def run_vpn_scan_background():
            """Quét tất cả các dải IP của các VPN đang kết nối trong luồng nền."""
            if scan_state["is_scanning"]:
                return
            scan_state["is_scanning"] = True
            scan_state["cancel_event"].clear()
            btn_vpn_scan.config(state=tk.DISABLED, text=_("Đang quét..."))

            def _thread():
                try:
                    vpns = detect_vpn_interfaces()
                    # Cập nhật thông tin VPN trên thanh công cụ
                    if vpns and dialog.winfo_exists():
                        vpn_names = ", ".join(f"{v['vpn_type']} ({v['ip']})" for v in vpns)
                        dialog.after(0, lambda n=vpn_names: lbl_vpn_info.config(
                            text=f"🛡️ " + _("Phát hiện VPN: ") + n,
                            fg="#56CCF2",
                            font=("Segoe UI", 8, "bold")
                        ))
                    elif dialog.winfo_exists():
                        dialog.after(0, lambda: lbl_vpn_info.config(
                            text="🛡️ " + _("VPN: Chưa phát hiện card mạng VPN (Có thể quét theo dải IP tùy chọn)"),
                            fg=self.text_gray,
                            font=("Segoe UI", 8, "italic")
                        ))

                    if not vpns:
                        if dialog.winfo_exists():
                            dialog.after(0, lambda: progress_label.config(text=_("Không tìm thấy kết nối VPN nào đang hoạt động.")))
                            dialog.after(2500, lambda: progress_label.config(text=""))
                        return
                        
                    for vpn in vpns:
                        if scan_state["cancel_event"].is_set():
                            break
                        v_name = vpn.get("vpn_type", "VPN")
                        subnet = vpn.get("target_subnet", "")
                        
                        def _prog(cur, tot, target_ip):
                            if dialog.winfo_exists():
                                dialog.after(0, lambda c=cur, t=tot, tip=target_ip, v=v_name: progress_label.config(
                                    text=_("Đang quét {vpn} ({tip} - {c}/{t})...").format(vpn=v, tip=tip, c=c, t=t)
                                ))

                        with self.lan_peers_lock:
                            current_known = dict(self.lan_peers)
                        found = scan_vpn_network(
                            vpn, 
                            ports=[12345, 12346], 
                            max_workers=60, 
                            progress_callback=_prog, 
                            cancel_event=scan_state["cancel_event"],
                            peer_found_callback=_on_peer_found,
                            known_peers=current_known
                        )
                        
                        if found:
                            for p in found:
                                _on_peer_found(p)
                            self.save_lan_peers()
                            if dialog.winfo_exists():
                                dialog.after(0, refresh_list)

                    self.save_lan_peers()
                    if dialog.winfo_exists():
                        with self.lan_peers_lock:
                            count_now = len(self.lan_peers)
                        dialog.after(0, lambda cnt=count_now: progress_label.config(text=_("Quét VPN hoàn tất! Tìm thấy {count} máy.").format(count=cnt)))
                        dialog.after(4000, lambda: progress_label.config(text=""))
                except Exception as ex:
                    print(f"[VPN Scan] Error: {ex}")
                finally:
                    scan_state["is_scanning"] = False
                    self.save_lan_peers()
                    if dialog.winfo_exists():
                        dialog.after(0, lambda: btn_vpn_scan.config(state=tk.NORMAL, text=_("🛡️ Quét VPN")))
                        dialog.after(0, refresh_list)

            threading.Thread(target=_thread, daemon=True).start()

        btn_vpn_scan.config(command=run_vpn_scan_background)

        def open_custom_ip_dialog():
            """Hộp thoại nhập dải IP tùy chọn để quét."""
            ip_dialog = tk.Toplevel(dialog)
            ip_dialog.title(_("Quét dải IP tùy chọn"))
            ip_dialog.resizable(False, False)
            ip_dialog.configure(bg=self.bg_color)
            ip_dialog.transient(dialog)
            ip_dialog.grab_set()
            ip_dialog.bind("<Escape>", lambda e: ip_dialog.destroy())

            pw, ph = 380, 220
            px = dialog.winfo_x() + (dialog.winfo_width() - pw) // 2
            py = dialog.winfo_y() + (dialog.winfo_height() - ph) // 2
            ip_dialog.geometry(f"{pw}x{ph}+{px}+{py}")

            default_start = "192.168.1.1"
            default_end = "192.168.1.254"
            try:
                vpns_now = detect_vpn_interfaces()
                if vpns_now:
                    bp = vpns_now[0].get("base_prefix", "")
                    if bp:
                        default_start = f"{bp}1"
                        default_end = f"{bp}254"
                else:
                    local_ip = getattr(self, 'local_ip', '').split(',')[0].strip()
                    if local_ip and '.' in local_ip:
                        parts = local_ip.split('.')
                        if len(parts) == 4:
                            default_start = f"{parts[0]}.{parts[1]}.{parts[2]}.1"
                            default_end = f"{parts[0]}.{parts[1]}.{parts[2]}.254"
            except Exception:
                pass

            cur_start, cur_end = load_saved_custom_ip(default_start, default_end)

            tk.Label(ip_dialog, text=_("Nhập dải IP mạng cần quét"), font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.bg_color).pack(pady=(15, 10))

            frame_inputs = tk.Frame(ip_dialog, bg=self.bg_color)
            frame_inputs.pack(padx=20, fill=tk.X, pady=(0, 15))

            tk.Label(frame_inputs, text=_("Từ IP:"), font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color).grid(row=0, column=0, sticky="w", pady=4)
            start_var = tk.StringVar(value=cur_start)
            entry_start = tk.Entry(frame_inputs, textvariable=start_var, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, relief=tk.FLAT, bd=3)
            entry_start.grid(row=0, column=1, padx=(10, 0), sticky="ew", pady=4)

            tk.Label(frame_inputs, text=_("Đến IP:"), font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color).grid(row=1, column=0, sticky="w", pady=4)
            end_var = tk.StringVar(value=cur_end)
            entry_end = tk.Entry(frame_inputs, textvariable=end_var, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, relief=tk.FLAT, bd=3)
            entry_end.grid(row=1, column=1, padx=(10, 0), sticky="ew", pady=4)
            frame_inputs.columnconfigure(1, weight=1)

            def do_start_custom_scan():
                s_ip = start_var.get().strip()
                e_ip = end_var.get().strip()
                save_saved_custom_ip(s_ip, e_ip)
                ip_dialog.destroy()
                if scan_state["is_scanning"]:
                    return
                scan_state["is_scanning"] = True
                scan_state["cancel_event"].clear()
                
                def _c_thread():
                    try:
                        def _prog(cur, tot, tip):
                            if dialog.winfo_exists():
                                dialog.after(0, lambda c=cur, t=tot, ip=tip: progress_label.config(
                                    text=_("Đang quét {ip} ({c}/{t})...").format(ip=ip, c=c, t=t)
                                ))
                        with self.lan_peers_lock:
                            current_known = dict(self.lan_peers)
                        found = scan_custom_range(
                            s_ip, e_ip, 
                            ports=[12345, 12346], 
                            max_workers=60, 
                            progress_callback=_prog, 
                            cancel_event=scan_state["cancel_event"],
                            peer_found_callback=_on_peer_found,
                            known_peers=current_known
                        )
                        if found:
                            for p in found:
                                _on_peer_found(p)
                            self.save_lan_peers()
                            if dialog.winfo_exists():
                                schedule_refresh(100)
                        self.save_lan_peers()
                        if dialog.winfo_exists():
                            with self.lan_peers_lock:
                                count_now = len(self.lan_peers)
                            dialog.after(0, lambda cnt=count_now: progress_label.config(text=_("Quét dải IP hoàn tất! Tìm thấy {count} máy.").format(count=cnt)))
                            dialog.after(4000, lambda: progress_label.config(text=""))
                    except Exception as err:
                        print(f"[Custom Scan] Error: {err}")
                    finally:
                        scan_state["is_scanning"] = False
                        self.save_lan_peers()
                        if dialog.winfo_exists():
                            schedule_refresh(50)
                            
                threading.Thread(target=_c_thread, daemon=True).start()

            entry_start.bind("<Return>", lambda e: do_start_custom_scan())
            entry_end.bind("<Return>", lambda e: do_start_custom_scan())
            entry_start.bind("<KP_Enter>", lambda e: do_start_custom_scan())
            entry_end.bind("<KP_Enter>", lambda e: do_start_custom_scan())

            btn_f = tk.Frame(ip_dialog, bg=self.bg_color)
            btn_f.pack(fill=tk.X, padx=20, pady=(0, 10))
            tk.Button(btn_f, text=_("Quét ngay"), font=("Segoe UI", 9, "bold"), fg="#FFFFFF", activeforeground="#FFFFFF", bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, pady=4, cursor="hand2", command=do_start_custom_scan).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
            tk.Button(btn_f, text=_("Hủy"), font=("Segoe UI", 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, relief=tk.FLAT, bd=0, pady=4, cursor="hand2", command=ip_dialog.destroy).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

        btn_custom_scan.config(command=open_custom_ip_dialog)

        # Biến lọc: Chỉ hiện máy có tên xác định (mặc định BẬT)
        filter_named_var = tk.BooleanVar(value=True)

        def is_named_peer(info):
            name = (info.get("computer_name") or "").strip()
            if not name or name.lower() in ("unknown", "không rõ"):
                return False
            # Nếu là fallback dạng PC-xxx (ví dụ: PC-48, PC-201) và chưa được xác thực
            if not info.get("name_verified", True):
                return False
            if re.match(r"^PC-\d{1,3}$", name):
                return False
            return True

        def toggle_filter_named():
            filter_named_var.set(not filter_named_var.get())
            _update_filter_btn_ui()
            refresh_list()

        def _update_filter_btn_ui():
            try:
                if filter_named_var.get():
                    btn_filter_named.config(
                        text=_("🏷️ Hiện tên máy: BẬT"),
                        bg="#27AE60",
                        activebackground="#2ECC71"
                    )
                else:
                    btn_filter_named.config(
                        text=_("🏷️ Hiện tên máy: TẮT"),
                        bg="#5D6D7E",
                        activebackground="#7F8C8D"
                    )
            except Exception:
                pass

        def refresh_list():
            if not dialog.winfo_exists():
                return
            try:
                cur_scroll = canvas.yview()
            except Exception:
                cur_scroll = (0.0, 1.0)

            # Xóa danh sách cũ
            for w in scroll_frame.winfo_children():
                w.destroy()

            with self.lan_peers_lock:
                self.lan_peers = deduplicate_lan_peers(self.lan_peers)
                # Loại bỏ hoàn toàn ID và máy hiện tại ra khỏi danh sách
                self_keys = [k for k, v in list(self.lan_peers.items()) if _is_self_peer(k, v)]
                for sk in self_keys:
                    try:
                        del self.lan_peers[sk]
                    except Exception:
                        pass
                peers = {h: i for h, i in self.lan_peers.items() if not _is_self_peer(h, i)}

            if not peers:
                tk.Label(scroll_frame, text=_("Chưa có máy tính nào trong danh sách.\nBấm nút 'Làm mới' hoặc 'Quét VPN' bên dưới để dò tìm các máy trong mạng."), font=("Segoe UI", 9), fg=self.text_gray, bg=self.entry_bg, justify=tk.CENTER).pack(pady=40, padx=20)
                status_label.config(text=_("Danh sách máy tính (0 máy)"))
                return

            total_all = len(peers)
            if filter_named_var.get():
                filtered_peers = {h: i for h, i in peers.items() if is_named_peer(i)}
            else:
                filtered_peers = peers
            filtered_peers = deduplicate_lan_peers(filtered_peers)

            hidden_count = total_all - len(filtered_peers)
            if hidden_count > 0 and filter_named_var.get():
                status_label.config(text=_("Tìm thấy ") + str(len(filtered_peers)) + _(" máy trong mạng LAN & VPN (Đã ẩn {n} máy chưa rõ tên)").format(n=hidden_count))
            else:
                status_label.config(text=_("Tìm thấy ") + str(len(filtered_peers)) + _(" máy trong mạng LAN & VPN"))

            if not filtered_peers:
                tk.Label(scroll_frame, text=_("Không có máy tính nào có tên xác định.\nBấm nút 'Hiện tên máy' bên dưới để xem tất cả {n} thiết bị đã phát hiện.").format(n=total_all), font=("Segoe UI", 9), fg=self.text_gray, bg=self.entry_bg, justify=tk.CENTER).pack(pady=40, padx=20)
                return

            # Sắp xếp: máy nhóm "LAN" lên trên cùng, sau đó là các nhóm "VPN khác" ở dưới; theo thứ tự bảng chữ cái
            def _peer_sort_key(item):
                hwid, p = item
                net_type = str(p.get("network_type") or "").strip().lower()
                is_lan = (not net_type or net_type == "lan")
                group_rank = 0 if is_lan else 1
                comp_name = (p.get("computer_name") or "").strip().lower()
                return (group_rank, comp_name)

            sorted_items = sorted(filtered_peers.items(), key=_peer_sort_key)
            row_ui_map = {}

            def _make_tooltip_text(h_info, is_on, f_id):
                ip_str = h_info.get('local_ip', '')
                ip_list = [ip.strip() for ip in ip_str.split(',') if ip.strip()]
                display_ip = f"{ip_list[0]} (+{len(ip_list)-1})" if len(ip_list) > 1 else (ip_list[0] if ip_list else ip_str)

                if is_on is True:
                    status_str = _("Trực tuyến (Online)")
                elif is_on is False:
                    status_str = _("Ngoại tuyến (Offline)")
                else:
                    status_str = _("Đang kiểm tra kết nối...")

                matched_c = match_saved_computer(h_info.get("computer_name"), h_info.get("hwid"), h_info.get("saved_id"))
                sp = (matched_c.get("password", "") if matched_c else "") or h_info.get("saved_password", "")
                pw_status = _("🔑 Đã lưu mật khẩu") if sp else _("⚠️ Chưa lưu mật khẩu (Sẽ hỏi khi kết nối)")

                tip_lines = [
                    f"💻 {h_info.get('computer_name', 'Unknown')}",
                    "──────────────────────────────",
                    f"• ID: {f_id}",
                    f"• IP: {display_ip}:{h_info.get('port', BOUND_PORT)}",
                    f"• Mạng: {h_info.get('network_type') or 'LAN'}",
                ]
                if h_info.get("os"):
                    tip_lines.append(f"• Hệ điều hành: {h_info['os']}")
                if h_info.get("macs"):
                    tip_lines.append(f"• Địa chỉ MAC: {h_info['macs']}")
                tip_lines.append(f"• Trạng thái: {status_str}")
                tip_lines.append(f"• Mật khẩu: {pw_status}")
                tip_lines.append("──────────────────────────────")
                tip_lines.append(_("💡 Bấm chuột trái: Kết nối trực tiếp ngay\n💡 Bấm chuột phải: Thay đổi mật khẩu hoặc Xóa máy"))
                return "\n".join(tip_lines)

            def _build_wol_button(container, h_info):
                return tk.Button(
                    container, text=_("Bật nguồn (WOL)"), font=("Segoe UI", 8, "bold"),
                    fg="#FFFFFF", activeforeground="#FFFFFF", bg="#D35400", activebackground="#E67E22",
                    relief=tk.FLAT, bd=0, padx=8, pady=2, cursor="hand2",
                    command=lambda m=h_info.get("macs", ""), i=h_info: self.wake_on_lan(
                        m, extra_ips=[i.get("local_ip"), i.get("source_ip")]
                    )
                )

            any_peer_synced = False
            my_clean_id = ''.join(ch for ch in str(getattr(self, "my_id_clean", "") or "") if ch.isdigit())
            if not my_clean_id:
                try:
                    from utils.hwid import get_hwid
                    my_clean_id = ''.join(ch for ch in str(get_hwid()[0] or "") if ch.isdigit())
                except Exception:
                    my_clean_id = ""
            my_hostname_lower = socket.gethostname().strip().lower()
            try:
                my_ips_set = get_all_local_ipv4()
            except Exception:
                my_ips_set = set()

            for hwid, info in sorted_items:
                if _is_self_peer(hwid, info):
                    continue
                row = tk.Frame(scroll_frame, bg=self.card_color, bd=0)
                row.pack(fill=tk.X, padx=5, pady=2)

                clean_hwid_key = ''.join(ch for ch in str(hwid) if ch.isdigit())
                clean_info_hwid = ''.join(ch for ch in str(info.get("hwid") or "") if ch.isdigit())

                # Ưu tiên HWID thực tế 12 số của peer (từ probe_pong hoặc key 12 số)
                actual_hwid = clean_info_hwid if len(clean_info_hwid) == 12 else (clean_hwid_key if len(clean_hwid_key) == 12 else "")

                # Đối chiếu với danh sách đã lưu (ưu tiên saved_computers.xml ở thư mục app) để lấy mật khẩu
                matched = match_saved_computer(info.get("computer_name"), actual_hwid or hwid, info.get("saved_id"))
                saved_pw = matched.get("password", "") if matched else ""
                m_id_clean = ''.join(ch for ch in str(matched.get("id", "")) if ch.isdigit()) if matched else ""

                is_hwid_verified = bool(info.get("hwid_verified", False))
                if is_hwid_verified and actual_hwid:
                    clean_hwid = actual_hwid
                elif m_id_clean and len(m_id_clean) == 12:
                    clean_hwid = m_id_clean
                    info["hwid_verified"] = True
                elif actual_hwid:
                    clean_hwid = actual_hwid
                else:
                    clean_hwid = ''.join(ch for ch in str(info.get("saved_id") or hwid) if ch.isdigit())

                info["saved_id"] = clean_hwid
                info["hwid"] = clean_hwid

                if saved_pw:
                    pw_hash = hash_password_md5(saved_pw)
                    if info.get("saved_password") != pw_hash or info.get("saved_id") != clean_hwid:
                        any_peer_synced = True
                    info["saved_password"] = pw_hash

                with self.lan_peers_lock:
                    if hwid in self.lan_peers:
                        if info.get("saved_password"):
                            self.lan_peers[hwid]["saved_password"] = info["saved_password"]
                        if clean_hwid:
                            self.lan_peers[hwid]["saved_id"] = clean_hwid
                            self.lan_peers[hwid]["hwid"] = clean_hwid

                clean_disp = clean_hwid if clean_hwid else ''.join(ch for ch in str(info.get("saved_id") or hwid) if ch.isdigit())
                fmt_id = f"{clean_disp[:3]} {clean_disp[3:6]} {clean_disp[6:9]} {clean_disp[9:]}" if len(clean_disp) == 12 else (clean_disp or info.get("saved_id") or hwid)

                # Trạng thái trực tuyến (None = đang kiểm tra, True = online, False = offline)
                online_state = scan_state.get("online_status", {})
                if hwid in online_state:
                    peer_online = online_state[hwid]
                else:
                    age = time.time() - get_last_seen_epoch(info.get("last_seen", 0))
                    peer_online = True if age < 30 else None

                dot_color = "#2ECC71" if peer_online is True else ("#FF4D4D" if peer_online is False else "#8A8A9A")
                lbl_dot = tk.Label(row, text="●", font=("Segoe UI", 9), fg=dot_color, bg=self.card_color)
                lbl_dot.pack(side=tk.LEFT, padx=(8, 4))

                # Network Badge
                net_type = str(info.get("network_type") or "LAN")
                nt_lower = net_type.lower()
                if "windows" in nt_lower:
                    badge_text = "WIN VPN"
                    badge_bg = "#4A235A"
                    badge_fg = "#E8DAEF"
                elif any(k in nt_lower for k in ("vpn", "tailscale", "zerotier", "hamachi", "radmin", "wireguard", "openvpn")):
                    badge_text = "VPN"
                    badge_bg = "#1B334D"
                    badge_fg = "#56CCF2"
                elif "custom" in nt_lower:
                    badge_text = "IP SCAN"
                    badge_bg = "#4D3319"
                    badge_fg = "#F39C12"
                else:
                    badge_text = "LAN"
                    badge_bg = "#145A32"
                    badge_fg = "#D4EFDF"
                    
                lbl_badge = tk.Label(row, text=badge_text, font=("Segoe UI", 7, "bold"), bg=badge_bg, fg=badge_fg, padx=4, pady=1)
                lbl_badge.pack(side=tk.LEFT, padx=(0, 8))

                # === CÁC PHẦN TỬ BÊN PHẢI (PACK RIGHT TRƯỚC) ===
                right_box = tk.Frame(row, bg=self.card_color)
                right_box.pack(side=tk.RIGHT, padx=(0, 10), pady=4)

                # 1. Container cho nút Bật nguồn WOL (chỉ hiển thị khi máy XÁC NHẬN NGOẠI TUYẾN và có địa chỉ MAC)
                wol_container = tk.Frame(right_box, bg=self.card_color)
                wol_container.pack(side=tk.RIGHT, padx=(6, 0))

                if peer_online is False and info.get("macs"):
                    btn = _build_wol_button(wol_container, info)
                    btn.pack()

                # 2. Huy hiệu "🔑 Đã lưu MK" nằm về bên phải, gần sát cạnh phải
                lbl_key = None
                if saved_pw or info.get("saved_password"):
                    lbl_key = tk.Label(right_box, text="🔑 " + _("Đã lưu MK"), font=("Segoe UI", 8, "bold"), bg="#145A32", fg="#2ECC71", padx=6, pady=2)
                    lbl_key.pack(side=tk.RIGHT, padx=(8, 0))

                # 3. ID máy tính canh gần sát về bên phải, ngay cạnh "🔑 Đã lưu MK"
                lbl_id = tk.Label(right_box, text="ID: " + str(fmt_id), font=("Segoe UI", 9), fg=self.text_gray, bg=self.card_color)
                lbl_id.pack(side=tk.RIGHT, padx=(8, 0))

                # === PHẦN TỬ BÊN TRÁI: TÊN MÁY TÍNH (chiếm toàn bộ khoảng trống còn lại) ===
                lbl_name = tk.Label(row, text=info.get("computer_name", "Unknown"), font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.card_color, anchor=tk.W)
                lbl_name.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4)

                tooltip_text = _make_tooltip_text(info, peer_online, fmt_id)

                # Menu chuột phải cho từng máy tính (giống như bên Danh sách máy tính đã lưu)
                row_menu = tk.Menu(row, tearoff=0, bg=self.entry_bg, fg=self.text_white, bd=0, activebackground=self.btn_hover)
                row_menu.add_command(label=_("🚀 Kết nối"), command=lambda h=hwid, i=info: connect_to_peer(h, i))
                row_menu.add_command(label=_("🔑 Thay đổi mật khẩu"), command=lambda h=hwid, i=info: open_change_lan_password_dialog(h, i))

                def _sync_menu_wol(m, h_info, is_on):
                    try:
                        end_idx = m.index(tk.END)
                        if end_idx is not None:
                            for idx in range(end_idx, -1, -1):
                                if m.type(idx) == "command" and "WOL" in m.entrycget(idx, "label"):
                                    m.delete(idx)
                                    break
                    except Exception:
                        pass
                    if not is_on and h_info.get("macs"):
                        m.insert_command(
                            2,
                            label=_("⚡ Bật nguồn (WOL)"),
                            command=lambda mac=h_info.get("macs", ""), inf=h_info: self.wake_on_lan(
                                mac, extra_ips=[inf.get("local_ip"), inf.get("source_ip")]
                            )
                        )

                _sync_menu_wol(row_menu, info, peer_online)
                row_menu.add_separator()
                row_menu.add_command(label=_("🗑️ Xóa"), command=lambda h=hwid, i=info: delete_lan_peer(h, i))

                def show_context(event, m=row_menu):
                    try:
                        m.tk_popup(event.x_root, event.y_root)
                    finally:
                        m.grab_release()

                # Gắn sự kiện click và hover tooltip cho toàn hàng (bỏ nút Kết nối, nhấp chuột trực tiếp để kết nối)
                bind_targets = [row, lbl_name, lbl_id, lbl_badge, lbl_dot, right_box]
                if lbl_key:
                    bind_targets.append(lbl_key)

                tooltip_obj = RowTooltip(bind_targets, tooltip_text)

                row_ui_map[hwid] = {
                    "row": row,
                    "dot": lbl_dot,
                    "wol_container": wol_container,
                    "info": info,
                    "tooltip": tooltip_obj,
                    "menu": row_menu,
                    "sync_menu_wol": _sync_menu_wol,
                    "fmt_id": fmt_id
                }

                def on_row_click(e, h=hwid, i=info):
                    connect_to_peer(h, i)

                # Dòng máy OFFLINE được làm tối hơn để phân biệt trực quan
                try:
                    from gui.components import apply_row_online_state
                    apply_row_online_state(row, peer_online, self.card_color, (self.text_white, self.text_gray))
                except Exception:
                    pass

                for w in bind_targets:
                    w.bind("<Button-1>", on_row_click)
                    w.bind("<Double-1>", on_row_click)
                    w.bind("<ButtonRelease-3>", show_context)
                    w.bind("<Button-3>", show_context)
                    w.bind("<ButtonRelease-2>", show_context)
                    w.bind("<Button-2>", show_context)
                    try:
                        w.config(cursor="hand2")
                    except Exception:
                        pass

            if any_peer_synced:
                self.save_lan_peers()

            # Khôi phục vị trí cuộn mượt mà
            try:
                canvas.yview_moveto(cur_scroll[0])
            except Exception:
                pass

            # Khởi chạy luồng thăm dò trạng thái trực tuyến của toàn bộ máy trong mạng LAN & VPN
            # Dùng trực tiếp TCP socket kết nối thẳng tới từng máy (cực nhanh, không qua Signaling Server)
            scan_state["probe_gen"] = scan_state.get("probe_gen", 0) + 1
            cur_probe_gen = scan_state["probe_gen"]

            def _apply_peer_online_status_ui(h_id, is_on, u_data=None):
                if not dialog.winfo_exists():
                    return
                ui_item = row_ui_map.get(h_id)
                if not ui_item:
                    return

                # 1. Cập nhật màu đèn LED (Xanh = Online, Đỏ = Offline)
                d = ui_item.get("dot")
                if d and d.winfo_exists():
                    d.config(fg="#2ECC71" if is_on else "#FF4D4D")

                try:
                    from gui.components import apply_row_online_state
                    apply_row_online_state(ui_item.get("row"), is_on, self.card_color, (self.text_white, self.text_gray))
                except Exception:
                    pass

                # 2. Cập nhật tooltip (gộp an toàn qua merge_peers để không bao giờ mất saved_password hay tên máy verified)
                inf = ui_item.get("info", {})
                if u_data:
                    merged_ui = merge_peers(u_data, inf)
                    merged_ui["hwid"] = inf.get("hwid") or h_id
                    inf.update(merged_ui)
                tip = ui_item.get("tooltip")
                if tip:
                    tip.update_text(_make_tooltip_text(inf, is_on, ui_item.get("fmt_id", h_id)))

                # 3. Nút Bật nguồn WOL: Chỉ hiển thị khi máy XÁC NHẬN NGOẠI TUYẾN và có địa chỉ MAC
                w_box = ui_item.get("wol_container")
                if w_box and w_box.winfo_exists():
                    for ch in w_box.winfo_children():
                        ch.destroy()
                    if not is_on and inf.get("macs"):
                        w_btn = _build_wol_button(w_box, inf)
                        w_btn.pack()

                # 4. Menu chuột phải
                m_ctx = ui_item.get("menu")
                sync_fn = ui_item.get("sync_menu_wol")
                if m_ctx and sync_fn and m_ctx.winfo_exists():
                    sync_fn(m_ctx, inf, is_on)

            def _probe_all_peers_bg(peers_to_check, gen):
                from concurrent.futures import ThreadPoolExecutor
                from utils.vpn_discovery import probe_peer_direct

                def _check_one(item_entry):
                    h, inf = item_entry
                    if not dialog.winfo_exists() or scan_state.get("probe_gen") != gen:
                        return
                    is_on, u_data = probe_peer_direct(inf, timeout=0.35)
                    scan_state.setdefault("online_status", {})[h] = is_on
                    if is_on and u_data:
                        with self.lan_peers_lock:
                            if h in self.lan_peers:
                                merged = merge_peers(u_data, self.lan_peers[h])
                                merged["hwid"] = self.lan_peers[h].get("hwid") or h
                                self.lan_peers[h] = merged
                    if dialog.winfo_exists() and scan_state.get("probe_gen") == gen:
                        dialog.after(0, lambda h_val=h, on_val=is_on, u_val=u_data: _apply_peer_online_status_ui(h_val, on_val, u_val))

                def _worker():
                    items = list(peers_to_check.items())
                    if not items:
                        return
                    with ThreadPoolExecutor(max_workers=min(25, max(1, len(items)))) as executor:
                        list(executor.map(_check_one, items))
                    self.save_lan_peers()

                threading.Thread(target=_worker, daemon=True).start()

            if filtered_peers:
                _probe_all_peers_bg(filtered_peers, cur_probe_gen)

        def clear_all_peers():
            """Xóa sạch toàn bộ danh sách máy đã quét và lưu file rỗng."""
            with self.lan_peers_lock:
                self.lan_peers.clear()
            scan_state.setdefault("online_status", {}).clear()
            self.save_lan_peers()
            refresh_list()
            progress_label.config(text=_("Đã xóa sạch danh sách máy đã quét!"))
            dialog.after(2500, lambda: progress_label.config(text=""))

        def do_scan_once():
            """Thực hiện quét 1 lần duy nhất (phát beacon LAN + quét dải VPN)."""
            scan_state.setdefault("online_status", {}).clear()
            # 1. Phát 1 beacon LAN
            try:
                comp_name = platform.node()
                beacon = json.dumps({
                    "sig": LAN_APP_SIGNATURE,
                    "hwid": getattr(self, "my_id_clean", ""),
                    "computer_name": comp_name,
                    "port": BOUND_PORT,
                    "local_ip": getattr(self, 'local_ip', get_local_ip()),
                    "macs": getattr(self, 'my_macs', "")
                }).encode('utf-8')
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(1.0)
                try: sock.sendto(beacon, ('255.255.255.255', LAN_DISCOVERY_PORT))
                except Exception: pass
                try:
                    local_ips = getattr(self, 'local_ip', '').split(',')
                    for lip in local_ips:
                        lip = lip.strip()
                        if lip and not lip.startswith('127.'):
                            parts = lip.split('.')
                            if len(parts) == 4:
                                sock.sendto(beacon, (f"{parts[0]}.{parts[1]}.{parts[2]}.255", LAN_DISCOVERY_PORT))
                except Exception: pass
                sock.close()
            except Exception:
                pass

            # 2. Quét VPN với phát hiện động
            run_vpn_scan_background()

        self._lan_refresh_list_func = refresh_list
        refresh_list()

        def on_dialog_close():
            self._lan_refresh_list_func = None
            scan_state["cancel_event"].set()
            scan_state["probe_gen"] = scan_state.get("probe_gen", 0) + 1
            if refresh_timer[0] is not None:
                try:
                    dialog.after_cancel(refresh_timer[0])
                except Exception:
                    pass
                refresh_timer[0] = None
            try:
                canvas.unbind_all("<MouseWheel>")
            except: pass
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
        dialog.bind("<Escape>", lambda e: on_dialog_close())

        # Bottom buttons
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15))

        # Nút "Làm mới" với màu chữ trắng sáng (#FFFFFF) nổi bật trên nền xanh (#007ACC)
        tk.Button(
            btn_frame, 
            text=_("🔄 Làm mới"), 
            font=("Segoe UI", 9, "bold"), 
            fg="#FFFFFF", 
            activeforeground="#FFFFFF", 
            bg="#007ACC", 
            activebackground="#005A9E", 
            relief=tk.FLAT, 
            bd=0, 
            pady=4, 
            padx=14, 
            cursor="hand2", 
            command=do_scan_once
        ).pack(side=tk.LEFT)

        # Nút "Xóa sạch" để xóa toàn bộ danh sách đã quét
        tk.Button(
            btn_frame, 
            text=_("🗑️ Xóa sạch"), 
            font=("Segoe UI", 9, "bold"), 
            fg="#FFFFFF", 
            activeforeground="#FFFFFF", 
            bg="#D9534F", 
            activebackground="#C9302C", 
            relief=tk.FLAT, 
            bd=0, 
            pady=4, 
            padx=14, 
            cursor="hand2", 
            command=clear_all_peers
        ).pack(side=tk.LEFT, padx=(8, 0))


        # Nút lọc "Hiện tên máy"
        btn_filter_named = tk.Button(
            btn_frame, 
            text=_("🏷️ Hiện tên máy: BẬT"), 
            font=("Segoe UI", 9, "bold"), 
            fg="#FFFFFF", 
            activeforeground="#FFFFFF", 
            bg="#27AE60", 
            activebackground="#2ECC71", 
            relief=tk.FLAT, 
            bd=0, 
            pady=4, 
            padx=12, 
            cursor="hand2", 
            command=toggle_filter_named
        )
        btn_filter_named.pack(side=tk.LEFT, padx=(8, 0))

        tk.Button(
            btn_frame, 
            text=_("Đóng"), 
            font=("Segoe UI", 9, "bold"), 
            fg=self.btn_cancel_fg, 
            bg=self.btn_cancel_bg, 
            relief=tk.FLAT, 
            bd=0, 
            pady=4, 
            padx=15, 
            cursor="hand2", 
            command=on_dialog_close
        ).pack(side=tk.RIGHT)

    def _connect_lan_direct(self, hwid, peer_info, password):
        """Kết nối TCP trực tiếp tới máy trong LAN (không qua Signaling Server)."""
        if self._is_host_only_app():
            return
        import platform
        ip = peer_info.get("local_ip", "")
        port = peer_info.get("port", BOUND_PORT)
        
        # Thử kết nối tới tất cả IP nếu có nhiều
        ips_to_try = [i.strip() for i in ip.split(',') if i.strip()]
        # Thêm source_ip nếu khác
        source_ip = peer_info.get("source_ip", "")
        if source_ip and source_ip not in ips_to_try:
            ips_to_try.append(source_ip)
            
        ports_to_try = [port]
        for p_alt in (12345, 12346):
            if p_alt not in ports_to_try:
                ports_to_try.append(p_alt)

        sock = None
        connected = False
        connected_port = port
        
        for try_ip in ips_to_try:
            for try_port in ports_to_try:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2.5)
                    s.connect((try_ip, try_port))
                    s.settimeout(15.0)
                    sock = s
                    connected = True
                    connected_port = try_port
                    print(f"[LAN Direct] Connected to {try_ip}:{try_port}")
                    break
                except Exception as e:
                    print(f"[LAN Direct] Failed to connect to {try_ip}:{try_port}: {e}")
                    try: s.close()
                    except: pass
                    continue
            if connected:
                break

        if not connected or not sock:
            comp_name = peer_info.get('computer_name', 'máy đích')
            self.update_status(_("Kết nối LAN thất bại!"))
            err_msg = _("Không thể kết nối tới {name} ({ip}:{port}).\n\nVui lòng kiểm tra lại:\n• Mật khẩu kết nối (nhấp chuột phải vào tên máy để chọn 'Thay đổi mật khẩu' nếu máy đổi mật khẩu).\n• Tường lửa (Firewall) hoặc đảm bảo máy đích đang mở Easy Remote Desktop.").format(
                name=comp_name, ip=ip, port=port
            )
            self.after(0, lambda: self.show_custom_error(_("Lỗi kết nối LAN"), err_msg))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            return

        # Sử dụng lại flow handshake hiện có
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except: pass
        if is_lan_socket(sock):
            tune_socket_for_lan_bulk(sock)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if sys.platform == "win32":
                sock.ioctl(socket.SIOC_KEEPALIVE_VALS, (1, 10000, 2000))
        except: pass

        try:
            socket_passwords[sock] = password
            hs_data = json.dumps({"password": password, "client_id": self.my_id_clean, "computer_name": platform.node()}).encode('utf-8')
            send_msg(sock, hs_data, password)
            
            res_msg = recv_msg(sock, [password, APP_KEY])
            if not res_msg:
                self.update_status(_("Sẵn sàng kết nối"))
                comp_name = peer_info.get('computer_name', '')
                err_msg = _("Không thể hoàn tất xác thực kết nối tới {name}.\nNguyên nhân có thể do mật khẩu không chính xác hoặc đối tác ngắt kết nối.\n\nVui lòng kiểm tra lại mật khẩu (nhấp chuột phải chọn 'Thay đổi mật khẩu').").format(name=comp_name)
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
                def _on_auth_empty():
                    if hasattr(self, 'connect_btn'):
                        self.connect_btn.config(state=tk.NORMAL)
                    parent_win = self.lan_computers_dialog if (hasattr(self, 'lan_computers_dialog') and self.lan_computers_dialog.winfo_exists()) else None
                    # Hiển thị dialog báo lỗi trước và chờ người dùng bấm OK (wait_window bên trong show_custom_error)
                    self.show_custom_error(_("Sai mật khẩu hoặc lỗi xác thực"), err_msg, parent=parent_win)
                    # Chỉ sau khi bấm OK đóng thông báo lỗi thì mới mở dialog nhập mật khẩu lên
                    if hasattr(self, '_last_lan_connect_fn') and self._last_lan_connect_fn:
                        if hasattr(self, 'lan_computers_dialog') and self.lan_computers_dialog.winfo_exists():
                            fn = self._last_lan_connect_fn
                            fn(fp=True)
                self.after(0, _on_auth_empty)
                return

            res = json.loads(res_msg.decode('utf-8'))
            
            if res.get("status") == "ok":
                host_w = res.get("width")
                host_h = res.get("height")
                computer_name = res.get("computer_name", "")
                zalo_phone = res.get("zalo_phone", "")
                os_release = res.get("os_release", "")
                is_domain = res.get("is_domain", False)
                is_android = _handshake_is_android(res)
                if is_android and not os_release:
                    os_release = "android"
                partner_id = hwid

                if is_android:
                    client_android_speed_test(sock, password, self.update_status)
                self.update_status(_("Kết nối LAN thành công! Đang khởi động màn hình..."))
                sock.settimeout(None)
                self.after(0, self.launch_pygame_viewer, sock, host_w, host_h, computer_name, zalo_phone, is_domain, partner_id, password, is_android, os_release)
            else:
                msg = res.get("message", _("Sai mật khẩu!"))
                self.update_status(_("Bị từ chối kết nối"))
                comp_name = peer_info.get('computer_name', '')
                if any(w in msg.lower() for w in ("mật khẩu", "password", "auth", "xác thực")):
                    err_title = _("Sai mật khẩu kết nối")
                    err_msg = _("Mật khẩu kết nối tới {name} không chính xác!\n\nVui lòng kiểm tra lại mật khẩu hoặc nhấp chuột phải vào tên máy để chọn 'Thay đổi mật khẩu'.").format(name=comp_name)
                else:
                    err_title = _("Từ chối kết nối")
                    err_msg = _("Kết nối tới {name} bị từ chối:\n{msg}").format(name=comp_name, msg=msg)
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
                def _on_auth_rejected(t=err_title, m=err_msg):
                    if hasattr(self, 'connect_btn'):
                        self.connect_btn.config(state=tk.NORMAL)
                    parent_win = self.lan_computers_dialog if (hasattr(self, 'lan_computers_dialog') and self.lan_computers_dialog.winfo_exists()) else None
                    # Hiển thị dialog báo sai mật khẩu trước và chờ người dùng bấm OK
                    self.show_custom_error(t, m, parent=parent_win)
                    # Chỉ sau khi bấm OK đóng thông báo lỗi thì mới mở dialog nhập mật khẩu lên
                    if hasattr(self, '_last_lan_connect_fn') and self._last_lan_connect_fn:
                        if hasattr(self, 'lan_computers_dialog') and self.lan_computers_dialog.winfo_exists():
                            fn = self._last_lan_connect_fn
                            fn(fp=True)
                self.after(0, _on_auth_rejected)
        except Exception as e:
            self.update_status(_("Sẵn sàng kết nối"))
            comp_name = peer_info.get('computer_name', '')
            self.after(0, lambda err=str(e): self.show_custom_error(_("Lỗi kết nối LAN"), _("Lỗi trong quá trình kết nối tới {name}:\n{err}\n\nVui lòng kiểm tra lại mật khẩu hoặc mạng.").format(name=comp_name, err=err)))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if sock:
                force_close_socket(sock)
                socket_passwords.pop(sock, None)

    def init_network_services(self):
        # 0. Thử tự động thêm rule Tường lửa và cấu hình UAC (sẽ thành công nếu có quyền Admin)
        self.configure_uac_registry()
        self.add_firewall_rule_for_app()
        
        # 1. Start Host Server first to determine which port is available
        if not self.is_headless and getattr(self, "is_service_active", False):
            print("[Host GUI] Service is active. Skipping local host TCP server startup to avoid conflict.")
            self.server_socket = None
            upnp_success = False
        else:
            self.update_status(_("Đang khởi động Server lắng nghe..."))
            self.start_host_server()
            
            # 2. Try automatic UPnP Port Forwarding
            self.update_status(_("Đang tự động cấu hình Router (UPnP)..."))
            upnp_success = attempt_upnp_forward(BOUND_PORT)
        
        # 3. Get Public & Local IPs
        self.update_status(_("Đang lấy thông vị trí mạng..."))
        print("[DEBUG] Calling get_public_ip()")
        self.current_ip = get_public_ip()
        print("[DEBUG] Returned from get_public_ip()")
        print("[DEBUG] Calling get_public_ipv6()")
        self.ipv6 = get_public_ipv6()
        print("[DEBUG] Returned from get_public_ipv6()")
        print("[DEBUG] Calling get_local_ip()")
        self.local_ip = get_local_ip()
        print("[DEBUG] Returned from get_local_ip()")
        print(f"[Host] Public IPv4: {self.current_ip}, IPv6: {self.ipv6}, Local IP: {self.local_ip}")
        
        # 4. Connect to real-time Signaling Server
        self.update_status(_("Đang kết nối tới các Signaling Server..."))
        self.signaling_sockets = {}
        self.primary_signaling_socket = None
        self.current_signaling_host = None
        
        for host in core.config.SIGNALING_SERVER_HOSTS:
            threading.Thread(target=self.signaling_maintainer_thread, args=(host,), daemon=True).start()
            
        # Try to wait up to 8 seconds for at least one connection
        # (GUI instance starts after headless, needs more time for Signaling Server to stabilize)
        timeout = 8.0
        while timeout > 0 and not self.signaling_sockets:
            time.sleep(0.2)
            timeout -= 0.2
            # Hiện thông báo đang chờ mỗi 2 giây
            elapsed = 8.0 - timeout
            if abs(elapsed - 2.0) < 0.1 or abs(elapsed - 5.0) < 0.1:
                self.update_status(_("Đang kết nối Signaling Server... ({sec}s)").format(sec=8 - int(timeout)))
            
        if self.signaling_sockets:
            suffix = _(" (Dịch vụ hoạt động)") if getattr(self, "is_service_active", False) else ""
            if upnp_success:
                self.update_status(_("Kết nối Signaling & Mở cổng Router thành công (Cổng {port})!{suffix}").format(port=BOUND_PORT, suffix=suffix))
            else:
                self.update_status(_("Kết nối Signaling thành công (Cổng {port})! Sẵn sàng kết nối.{suffix}").format(port=BOUND_PORT, suffix=suffix))
        else:
            suffix = _(" (Dịch vụ hoạt động)") if getattr(self, "is_service_active", False) else ""
            self.update_status(_("Chưa kết nối Signaling Server. Đang thử lại ở chế độ nền... {suffix}").format(suffix=suffix))

        # 5. Start LAN Discovery (UDP Broadcast) - Phát hiện máy trong mạng nội bộ
        self.start_lan_discovery()


    def signaling_maintainer_thread(self, host):
        retry_delay = 2  # Bắt đầu retry nhanh (2s), tăng dần sau 3 lần thất bại
        fail_count = 0
        while self.running_server:
            sock = None
            try:
                # 1. Connect
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(('0.0.0.0', BOUND_PORT))
                except Exception as e:
                    print(f"[Signaling] Warning: Could not bind to BOUND_PORT {BOUND_PORT} for signaling: {e}")
                    try: sock.close()
                    except: pass
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    
                try:
                    if os.name == 'nt':
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                        sock.ioctl(socket.SIOC_KEEPALIVE_VALS, (1, 30000, 10000))
                    else:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                except Exception: pass
                
                sock.settimeout(5.0)
                try:
                    sock.connect((host, core.config.SIGNALING_SERVER_PORT))
                except Exception as ce:
                    if getattr(ce, 'winerror', None) == 10048 or "10048" in str(ce):
                        try: sock.close()
                        except: pass
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        sock.settimeout(5.0)
                        sock.connect((host, core.config.SIGNALING_SERVER_PORT))
                    else:
                        raise ce
                sock.settimeout(None)
                
                # Use base HWID if we are the primary instance (port 12345), else append port to avoid stealing ID from background service
                is_svc_active = False
                if hasattr(self, 'check_if_service_active'):
                    is_svc_active = self.check_if_service_active()
                else:
                    is_svc_active = getattr(self, 'is_service_active', False)
                register_id = self.my_id_clean if (BOUND_PORT == PORTS_TO_TRY[0] and not is_svc_active) else f"{self.my_id_clean}_{BOUND_PORT}"
                print(f"[Signaling] Register as {register_id} (port={BOUND_PORT}, service={is_svc_active})")
                
                req = json.dumps({"action": "register", "hwid": register_id})
                req_data = req.encode('utf-8')
                send_msg(sock, req_data, APP_KEY)
                
                with self.signaling_lock:
                    self.signaling_sockets[host] = sock
                    if getattr(self, 'current_signaling_host', None) is None:
                        self.current_signaling_host = host
                        self.primary_signaling_socket = sock
                    # Luôn cập nhật status khi kết nối thành công (kể cả lần đầu sau timeout hoặc sau reconnect)
                    self.after(0, lambda: self.update_status(_("Kết nối Signaling thành công! Sẵn sàng kết nối.")))
                
                # Reset counters khi kết nối thành công
                fail_count = 0
                retry_delay = 2
                
                print(f"[Signaling] Connected to {host}")
                
                last_ping = time.time()
                last_pong = time.time()
                
                import select
                while self.running_server:
                    r, _w, _e = select.select([sock], [], [], 1.0)
                    if r:
                        msg_bytes = recv_msg(sock, APP_KEY)
                        if msg_bytes is None:
                            break
                        if msg_bytes == b'':
                            continue
                        
                        try:
                            msg = msg_bytes.decode('utf-8')
                            self.process_signaling_message(msg, sock, host)
                            if "pong" in msg:
                                last_pong = time.time()
                        except Exception as de:
                            print(f"[Signaling] Decode error: {de}")
                                
                    now = time.time()
                    if now - last_ping > 20:
                        ping_req = json.dumps({"action": "ping"})
                        send_msg(sock, ping_req.encode('utf-8'), APP_KEY)
                        last_ping = now
                        
                    if now - last_pong > 50:
                        print(f"[Signaling] Heartbeat timeout for {host}")
                        break
                        
            except Exception as e:
                print(f"[Signaling] Connection error on {host}: {e}")
                
            finally:
                if sock:
                    try: force_close_socket(sock)
                    except: pass
                with self.signaling_lock:
                    if host in getattr(self, 'signaling_sockets', {}):
                        del self.signaling_sockets[host]
                    if getattr(self, 'current_signaling_host', None) == host:
                        self.current_signaling_host = None
                        self.primary_signaling_socket = None
                        if self.signaling_sockets:
                            new_host = next(iter(self.signaling_sockets))
                            self.current_signaling_host = new_host
                            self.primary_signaling_socket = self.signaling_sockets[new_host]
                        else:
                            if self.running_server:
                                self.after(0, lambda: self.update_status(_("Mất kết nối toàn bộ Signaling Server. Đang thử lại..."), is_error=True, blink=True))
            
            time.sleep(retry_delay)
            # Tăng retry_delay sau 3 lần thất bại liên tiếp
            fail_count += 1
            if fail_count >= 3:
                retry_delay = 5

    def process_signaling_message(self, msg, sock, host):
        try:
            res = json.loads(msg)
            action = res.get("action")
            
            if action == "incoming_request":
                from_hwid = res.get("from_hwid")
                public_ip = res.get("public_ip")
                public_port = int(res.get("port") or res.get("public_port") or 0)
                local_ip = res.get("local_ip")
                local_port = int(res.get("local_port") or 12345)
                
                print(f"[Signaling] Connection request from {from_hwid} ({public_ip}:{public_port}) via {host}")
                
                accept_req = json.dumps({
                    "action": "connect_accept",
                    "target": from_hwid,
                    "port": BOUND_PORT,
                    "local_ip": self.local_ip,
                    "local_port": BOUND_PORT
                })
                with self.signaling_lock:
                    send_msg(sock, accept_req.encode('utf-8'), APP_KEY)
                    
                threading.Thread(target=self.punch_hole_to_client, args=(public_ip, public_port), daemon=True).start()
                
            elif action == "request_accepted":
                public_ip = res.get("public_ip")
                public_port = int(res.get("port") or res.get("public_port") or 0)
                local_ip = res.get("local_ip")
                local_port = int(res.get("local_port") or 12345)
                self.pending_connection_info = (public_ip, public_port, local_ip, local_port)
                self.current_signaling_host = host
                self.primary_signaling_socket = sock
                
            elif action == "error":
                print(f"[Signaling] Error on {host}: {res.get('message')}")
                self.pending_connection_info = "error"
                
            elif action == "relay_request":
                session_id = res.get("session_id")
                relay_host = res.get("relay_host") or host
                print(f"[Signaling] Nhận yêu cầu trung chuyển (RELAY) via {host}. Đang kết nối làm Host...")
                threading.Thread(target=self.start_relay_host, args=(session_id, relay_host), daemon=True).start()
                
            elif action == "online_status":
                target = res.get("target")
                online = res.get("online", False)
                self.after(0, lambda t=target, o=online: self._on_check_online_result(t, o))
                
        except Exception as e:
            print(f"[Signaling] Lỗi xử lý tin nhắn từ {host}: {e}")

    def start_relay_host(self, session_id, specific_host=None):
        try:
            print(f"[Relay] Host đang kết nối tới Relay Server cho session: {session_id}")
            host_to_connect = specific_host if specific_host else core.config.SIGNALING_SERVER_HOSTS[0]
            
            relay_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            relay_sock.settimeout(5.0)
            relay_sock.connect((host_to_connect, core.config.SIGNALING_SERVER_PORT))
            relay_sock.settimeout(None)
            
            header = f"RELAY_HOST:{session_id}\n"
            relay_sock.sendall(header.encode('utf-8'))
            
            # Truyền hình ảnh qua kết nối Relay
            threading.Thread(target=self.handle_host_handshake, args=(relay_sock, (host_to_connect, core.config.SIGNALING_SERVER_PORT)), daemon=True).start()
        except Exception as e:
            print(f"[Relay] Host kết nối Relay Server thất bại: {e}")

    def punch_hole_to_client(self, c_ip, c_port):
        # 0. Đợi Client thử kết nối mạng LAN trước (2.0 giây)
        # Việc này giúp giữ listener mở để Client có thể kết nối nội bộ.
        # Đồng thời đồng bộ thời gian đục lỗ (Simultaneous Open) với Client (Client timeout LAN là 2.0s)
        time.sleep(2.0)
        
        # 1. Tạm thời đóng server_socket để giải phóng port
        if self.server_socket:
            try:
                self.server_socket.close()
            except: pass
            
        success_sock = None
        
        # Spam outbound connections quickly for Simultaneous Open
        for _i in range(10):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('0.0.0.0', BOUND_PORT))
            except:
                pass
            sock.settimeout(0.5)
            try:
                sock.connect((c_ip, c_port))
                print("[HolePunch] Host successfully punched through to Client!")
                success_sock = sock
                break
            except Exception:
                force_close_socket(sock)
                time.sleep(0.1)
                
        if not success_sock:
            print("[HolePunch] Host gave up trying to punch hole.")
            
        # 2. Mở lại server_socket bất kể đục lỗ thành công hay thất bại
        try:
            try:
                if hasattr(socket, 'AF_INET6'):
                    self.server_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                    self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    if hasattr(socket, 'IPPROTO_IPV6') and hasattr(socket, 'IPV6_V6ONLY'):
                        try: self.server_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                        except: pass
                    self.server_socket.bind(("", BOUND_PORT))
                else:
                    raise Exception("No IPv6")
            except Exception:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind(('0.0.0.0', BOUND_PORT))
            self.server_socket.listen(5)
            print(f"[Host] Đã phục hồi TCP server lắng nghe trên port {BOUND_PORT}")
        except Exception as e:
            print(f"[Host] Cảnh báo: Không thể phục hồi server_socket: {e}")
            
        # 3. Bắt tay kết nối nếu thành công
        if success_sock:
            # Khôi phục timeout về None (blocking) cho socket sau khi đục lỗ thành công
            success_sock.settimeout(None)
            threading.Thread(target=self.handle_host_handshake, args=(success_sock, (c_ip, c_port)), daemon=True).start()


    # TCP Server (Host) functions


    def click_connect(self):
        if self._is_host_only_app():
            return
        partner_id = self.partner_id_var.get().strip().replace(" ", "")
        partner_pass = self.partner_pass_var.get().strip()
        
        if not partner_id or len(partner_id) < 12:
            self.show_custom_error(_("Lỗi"), _("Vui lòng nhập mã ID đối tác hợp lệ (12 chữ số)!"))
            return
            
        if not partner_pass and hasattr(self, 'load_saved_computers'):
            try:
                saved = self.load_saved_computers()
                matched = next((c for c in saved if "".join(ch for ch in c.get('id', '') if ch.isdigit()) == partner_id or c.get('id', '').replace(' ', '') == partner_id), None)
                if matched and matched.get('password'):
                    partner_pass = matched['password']
                    self.partner_pass_var.set(partner_pass)
            except Exception:
                pass

        if not partner_pass:
            self.show_custom_error(_("Lỗi"), _("Vui lòng nhập mật khẩu đối tác!"))
            return

        if partner_id == getattr(self, "my_id_clean", ""):
            self.show_custom_info(_("Thông báo"), _("Bạn không thể kết nối tới chính bạn :-)"))
            return

        # Dọn dẹp tiến trình viewer đã thoát
        self.active_viewers = [v for v in self.active_viewers if v["process"].is_alive()]
        
        # Kiểm tra xem đã có cửa sổ nào đang kết nối tới partner_id này chưa
        for v in self.active_viewers:
            if v.get("partner_id") == partner_id:
                print(f"[Client] Already connected to {partner_id}. Sending blink signal.")
                import tempfile
                blink_file = os.path.join(tempfile.gettempdir(), f"antigravity_blink_{partner_id}.tmp")
                try:
                    with open(blink_file, "w") as f:
                        f.write("1")
                except Exception as write_err:
                    print(f"[Client] Failed to write blink signal: {write_err}")
                return

        # Tìm tên máy từ danh sách máy đã lưu
        computer_name = ""
        if hasattr(self, 'load_saved_computers'):
            try:
                saved_comps = self.load_saved_computers()
                for c in saved_comps:
                    if c.get("id", "").replace(" ", "") == partner_id:
                        computer_name = c.get("name", "")
                        break
            except Exception:
                pass
        if not computer_name:
            clean_digits = "".join(c for c in str(partner_id or "") if c.isdigit())
            disp_id = " ".join(clean_digits[i:i+3] for i in range(0, len(clean_digits), 3)) if (clean_digits and len(clean_digits) == len(str(partner_id).replace(" ", ""))) else partner_id
            computer_name = f"ID: {disp_id}"

        # Lưu biến UI force_relay
        self._current_force_relay = False
        if hasattr(self, 'force_relay_var'):
            self._current_force_relay = self.force_relay_var.get()

        # Mở ngay cửa sổ Pygame Viewer (1024x768, nền đen, chữ trắng)
        import multiprocessing as mp
        reconnect_queue = mp.Queue()
        cmd_queue = mp.Queue()
        p = mp.Process(
            target=run_client_viewer_loop,
            args=(None, 1024, 768, computer_name, False, partner_id, reconnect_queue, partner_pass, False, "", cmd_queue),
            daemon=True,
        )
        p.start()
        p._cmd_queue = cmd_queue

        self.active_viewers.append({
            "process": p,
            "computer_name": computer_name,
            "zalo_phone": "",
            "partner_id": partner_id
        })

        # Nút kết nối vẫn ở trạng thái NORMAL để có thể mở nhiều máy cùng lúc
        self.connect_btn.config(state=tk.NORMAL)

        def run_connect():
            try:
                self.connect_to_partner(
                    partner_id,
                    partner_pass,
                    reconnect_queue=reconnect_queue,
                    retry_count=0,
                    viewer_pid=p.pid,
                    reconnect_reason="",
                    computer_name_override=computer_name,
                    viewer_proc=p
                )
            except Exception as e:
                import traceback
                print(f"[Client] Background connect thread crashed: {e}")
                if reconnect_queue:
                    try: reconnect_queue.put(f"FAILED|{e}")
                    except: pass

        threading.Thread(target=run_connect, daemon=True).start()

    def connect_to_partner(self, partner_id, partner_pass, reconnect_queue=None, retry_count=0, viewer_pid=None, reconnect_reason="", computer_name_override="", viewer_proc=None):
        if self._is_host_only_app():
            return
        if partner_id == getattr(self, "my_id_clean", ""):
            self.after(0, lambda: self.show_custom_info(_("Thông báo"), _("Bạn không thể kết nối tới chính bạn :-)")))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if reconnect_queue:
                try: reconnect_queue.put("FAILED|" + _("Bạn không thể kết nối tới chính bạn :-)"))
                except: pass
            return

        # Nếu được gọi trực tiếp mà chưa có reconnect_queue (fallback):
        if reconnect_queue is None:
            self.active_viewers = [v for v in self.active_viewers if v["process"].is_alive()]
            for v in self.active_viewers:
                if v.get("partner_id") == partner_id:
                    print(f"[Client] Already connected to {partner_id}. Sending blink signal.")
                    import tempfile
                    blink_file = os.path.join(tempfile.gettempdir(), f"antigravity_blink_{partner_id}.tmp")
                    try:
                        with open(blink_file, "w") as f:
                            f.write("1")
                    except Exception:
                        pass
                    return

            computer_name = computer_name_override
            if not computer_name and hasattr(self, 'load_saved_computers'):
                try:
                    saved_comps = self.load_saved_computers()
                    for c in saved_comps:
                        if c.get("id", "").replace(" ", "") == partner_id:
                            computer_name = c.get("name", "")
                            break
                except Exception:
                    pass
            if not computer_name:
                clean_digits = "".join(c for c in str(partner_id or "") if c.isdigit())
                disp_id = " ".join(clean_digits[i:i+3] for i in range(0, len(clean_digits), 3)) if (clean_digits and len(clean_digits) == len(str(partner_id).replace(" ", ""))) else partner_id
                computer_name = f"ID: {disp_id}"

            import multiprocessing as mp
            reconnect_queue = mp.Queue()
            cmd_queue = mp.Queue()
            p = mp.Process(
                target=run_client_viewer_loop,
                args=(None, 1024, 768, computer_name, False, partner_id, reconnect_queue, partner_pass, False, "", cmd_queue),
                daemon=True,
            )
            p.start()
            p._cmd_queue = cmd_queue
            viewer_pid = p.pid
            viewer_proc = p
            computer_name_override = computer_name

            self.active_viewers.append({
                "process": p,
                "computer_name": computer_name,
                "zalo_phone": "",
                "partner_id": partner_id
            })

        def notify_status(msg):
            # Nếu đang ở chế độ reconnect hoặc chu kỳ retry, không gửi các trạng thái chi tiết nội bộ
            # vào reconnect_queue (để tránh đè mất dòng chữ "Đang thử kết nối lại (lần {x}/10)...")
            is_retry_status = ("Đang thử kết nối lại" in msg or _("Đang thử kết nối lại") in msg or "lần " in msg)
            if is_reconnect or retry_count > 0:
                if is_retry_status and reconnect_queue:
                    try: reconnect_queue.put(f"STATUS|{msg}")
                    except: pass
                return

            if reconnect_queue:
                try: reconnect_queue.put(f"STATUS|{msg}")
                except: pass

        def is_cancelled():
            if viewer_proc and not viewer_proc.is_alive():
                print(f"[Client] Viewer process closed by user, cancelling connect to {partner_id}")
                return True
            return False

        sock = None
        connected = False
        handshake_done = False
        cached_res_payload = None
        conn_mode_info = None
        force_relay = getattr(self, '_current_force_relay', False)
        specific_host = getattr(self, 'current_signaling_host', None)

        is_reconnect = bool(reconnect_reason or retry_count > 0)
        current_attempt = min(10, retry_count + 1)
        retry_banner = _("Đang thử kết nối lại (lần {x}/10)...").format(x=current_attempt)
        if is_reconnect:
            notify_status(retry_banner)

        # ====== BƯỚC 0: Thử kết nối lại siêu tốc bằng thông số phiên gần nhất (Fast-Path Reconnect) ======
        # Nếu trước đó đã kết nối thành công (LAN / Direct WAN / Relay), ưu tiên thử ngay thông số cũ
        # để bỏ qua thời gian quét mạng và đục lỗ không cần thiết.
        p_key = str(partner_id).replace(" ", "")
        cached_conn = getattr(self, 'last_connected_peers', {}).get(p_key)
        if is_reconnect and cached_conn and retry_count < 5 and not is_cancelled():
            c_mode = cached_conn.get("mode")
            if c_mode == "lan" and not force_relay:
                c_ip = cached_conn.get("ip")
                c_port = cached_conn.get("port", 12345)
                ports_to_try = [c_port]
                for p_port in [12345, 12346, 12347, 12348]:
                    if p_port not in ports_to_try:
                        ports_to_try.append(p_port)
                print(f"[FastReconnect] Ưu tiên thử kết nối nhanh LAN gần nhất: {c_ip}:{ports_to_try}")
                for p_port in ports_to_try:
                    if connected or is_cancelled(): break
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(1.0)
                        s.connect((c_ip, p_port))
                        s.settimeout(2.0)
                        socket_passwords[s] = partner_pass
                        import platform
                        hs_data = json.dumps({"password": partner_pass, "client_id": self.my_id_clean, "computer_name": platform.node()}).encode('utf-8')
                        send_msg(s, hs_data, partner_pass)
                        tmp_res_msg = recv_msg(s, [partner_pass, APP_KEY])
                        if tmp_res_msg:
                            tmp_res = json.loads(tmp_res_msg.decode('utf-8'))
                            if tmp_res.get("status") in ("ok", "error"):
                                s.settimeout(None)
                                sock = s
                                connected = True
                                handshake_done = True
                                cached_res_payload = tmp_res
                                conn_mode_info = {"mode": "lan", "ip": c_ip, "port": p_port}
                                print(f"[FastReconnect] Thành công kết nối lại LAN trực tiếp: {c_ip}:{p_port}")
                                break
                        if not connected:
                            force_close_socket(s)
                    except Exception:
                        try: s.close()
                        except: pass

            elif c_mode == "direct" and not force_relay:
                c_ip = cached_conn.get("ip")
                c_port = cached_conn.get("port")
                if c_ip and c_port:
                    print(f"[FastReconnect] Ưu tiên thử kết nối nhanh Direct WAN gần nhất: {c_ip}:{c_port}")
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(1.5)
                        s.connect((c_ip, c_port))
                        s.settimeout(None)
                        sock = s
                        connected = True
                        conn_mode_info = {"mode": "direct", "ip": c_ip, "port": c_port}
                        print(f"[FastReconnect] Thành công kết nối lại Direct WAN: {c_ip}:{c_port}")
                    except Exception:
                        force_close_socket(s)

            elif c_mode == "relay":
                r_host = cached_conn.get("relay_host") or specific_host or (core.config.SIGNALING_SERVER_HOSTS[0] if core.config.SIGNALING_SERVER_HOSTS else None)
                if r_host:
                    print(f"[FastReconnect] Phiên trước dùng Relay -> Nhảy thẳng tới kết nối Relay ({r_host})...")
                    try:
                        relay_session_id = f"relay_{self.my_id_clean}_{partner_id}"
                        relay_req = json.dumps({
                            "action": "relay_request",
                            "target": partner_id,
                            "session_id": relay_session_id,
                            "relay_host": r_host
                        }) + '\n'
                        with self.signaling_lock:
                            if getattr(self, 'primary_signaling_socket', None):
                                send_msg(self.primary_signaling_socket, relay_req.encode('utf-8'), APP_KEY)
                            else:
                                raise Exception("Chưa kết nối tới Signaling Server!")

                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(4.0)
                        s.connect((r_host, core.config.SIGNALING_SERVER_PORT))
                        s.settimeout(None)
                        header = f"RELAY_CLIENT:{relay_session_id}\n"
                        s.sendall(header.encode('utf-8'))
                        time.sleep(1.0)
                        sock = s
                        connected = True
                        conn_mode_info = {"mode": "relay", "relay_host": r_host}
                        print(f"[FastReconnect] Thành công kết nối lại qua Relay: {r_host}")
                    except Exception as e:
                        print(f"[FastReconnect] Thử Relay nhanh thất bại ({e}), tiếp tục quy trình dò tìm đầy đủ...")
                        connected = False

        # ====== BƯỚC 1: Quét mạng LAN để tìm ID ======
        lan_target = None
        if not connected and not force_relay and hasattr(self, 'lan_peers'):
            scan_rounds = 1 if is_reconnect else 5
            for attempt in range(scan_rounds):
                if is_cancelled(): return
                if is_reconnect:
                    notify_status(retry_banner)
                else:
                    notify_status(_("Đang tìm máy trong mạng LAN (lần {n}/5)...").format(n=attempt + 1))
                current_time = time.time()
                with self.lan_peers_lock:
                    if partner_id in self.lan_peers:
                        p_peer = self.lan_peers[partner_id]
                        is_vpn = bool(p_peer.get("network_type"))
                        max_age = 180 if is_vpn else 15
                        if current_time - get_last_seen_epoch(p_peer.get("last_seen", 0)) < max_age:
                            lan_target = p_peer
                if lan_target:
                    print(f"[LAN Discovery] Tìm thấy đối tác {partner_id} trong mạng LAN/VPN!")
                    break
                time.sleep(0.3 if is_reconnect else 0.5)

        if not connected and lan_target:
            if is_cancelled(): return
            if not is_reconnect and retry_count == 0:
                notify_status(_("Đang thử kết nối LAN trực tiếp..."))
            local_ip = lan_target.get("local_ip", "")
            local_port = lan_target.get("port", 12345)
            ips_to_try = [ip.strip() for ip in local_ip.split(',') if ip.strip()]
            ports_to_try = [local_port]
            for p_port in [12345, 12346, 12347, 12348]:
                if p_port not in ports_to_try:
                    ports_to_try.append(p_port)
            
            for try_ip in ips_to_try:
                if connected or is_cancelled(): break
                for p_port in ports_to_try:
                    if connected or is_cancelled(): break
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(1.5)
                        s.connect((try_ip, p_port))
                        s.settimeout(2.5)
                        # Handshake
                        socket_passwords[s] = partner_pass
                        import platform
                        hs_data = json.dumps({"password": partner_pass, "client_id": self.my_id_clean, "computer_name": platform.node()}).encode('utf-8')
                        send_msg(s, hs_data, partner_pass)
                        tmp_res_msg = recv_msg(s, [partner_pass, APP_KEY])
                        if tmp_res_msg:
                            tmp_res = json.loads(tmp_res_msg.decode('utf-8'))
                            if tmp_res.get("status") in ("ok", "error"):
                                s.settimeout(None)
                                sock = s
                                connected = True
                                handshake_done = True
                                cached_res_payload = tmp_res
                                conn_mode_info = {"mode": "lan", "ip": try_ip, "port": p_port}
                                print(f"[Client] Connected & Handshaked via LAN Direct: {try_ip}:{p_port}")
                                break
                        if not connected:
                            force_close_socket(s)
                    except Exception as e:
                        try: s.close()
                        except: pass

        # ====== BƯỚC 2: Hỏi Signaling Server (nếu LAN thất bại hoặc không tìm thấy) ======
        public_ip, port = None, None
        specific_host = getattr(self, 'current_signaling_host', None)
        
        if not connected:
            if is_cancelled(): return
            if not hasattr(self, 'signaling_sockets') or not self.signaling_sockets:
                notify_status(_("Chưa kết nối Máy chủ Tín hiệu!"))
                if reconnect_queue:
                    reconnect_queue.put("FAILED|" + _("Chưa kết nối đến Máy chủ Tín hiệu. Vui lòng kiểm tra lại mạng."))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                return

            sockets_to_try = []
            with self.signaling_lock:
                if getattr(self, 'primary_signaling_socket', None):
                    sockets_to_try.append(self.primary_signaling_socket)
                for s in getattr(self, 'signaling_sockets', {}).values():
                    if s not in sockets_to_try:
                        sockets_to_try.append(s)
                        
            if not is_reconnect:
                notify_status(_("Đang tìm địa chỉ đối tác trên server danh bạ..."))
            
            from utils.hwid import signaling_lookup_ids
            signaling_success = False
            lookup_ids = signaling_lookup_ids(partner_id)
            for target_id in lookup_ids:
                if is_cancelled(): return
                req = json.dumps({
                    "action": "connect_request",
                    "target": target_id,
                    "port": BOUND_PORT,
                    "local_ip": getattr(self, 'local_ip', "127.0.0.1"),
                    "local_port": BOUND_PORT
                }) + '\n'
                wait_timeout = (2.5 if is_reconnect else 6.0) if target_id == lookup_ids[0] else 1.5
                for s in sockets_to_try:
                    self.pending_connection_info = None
                    try:
                        with self.signaling_lock:
                            send_msg(s, req.encode('utf-8'), APP_KEY)
                    except Exception:
                        continue
                        
                    remain = wait_timeout
                    while remain > 0 and self.pending_connection_info is None:
                        if is_cancelled(): return
                        time.sleep(0.2)
                        remain -= 0.2
                        
                    if self.pending_connection_info and self.pending_connection_info != "error":
                        signaling_success = True
                        break
                if signaling_success:
                    break
                    
            if not signaling_success:
                if reconnect_queue and retry_count + 1 < 10:
                    next_attempt = retry_count + 2
                    status_msg = _("Đang thử kết nối lại (lần {x}/10)...").format(x=next_attempt)
                    notify_status(status_msg)
                    time.sleep(4)
                    self.connect_to_partner(partner_id, partner_pass, reconnect_queue, retry_count + 1, viewer_pid, reconnect_reason or "drop", computer_name_override, viewer_proc)
                    return
                notify_status(_("Không thể tìm thấy hoặc đối tác đang Offline."))
                if reconnect_queue:
                    reconnect_queue.put("FAILED|" + _("Không thể tìm thấy hoặc đối tác đang Offline."))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                return
                
            if len(self.pending_connection_info) >= 4:
                public_ip, port_str, _dummy1, _dummy2 = self.pending_connection_info[:4]
            else:
                public_ip, port_str, _dummy1 = self.pending_connection_info
                
            port = int(port_str) if port_str else 0

        # ====== BƯỚC 3: Đục lỗ Tường lửa (TCP Hole Punching) 10 lần ======
        if not connected and not force_relay and public_ip and port:
            if is_cancelled(): return
            skip_hole_punch = False
            if hasattr(self, 'current_ip') and self.current_ip == public_ip:
                print("[Client] Skipping Hole Punching because both peers share the same Public IP (same router).")
                skip_hole_punch = True
            
            if not skip_hole_punch:
                notify_status(_("Đang đục lỗ Tường lửa tới {ip}:{port}...").format(ip=public_ip, port=port))
                
                if getattr(self, 'server_socket', None):
                    try: self.server_socket.close()
                    except: pass
                
                for attempt in range(10):
                    if is_cancelled():
                        break
                    notify_status(_("Đang đục lỗ Tường lửa lần {n}/10...").format(n=attempt + 1))
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    try: s.bind(('0.0.0.0', BOUND_PORT))
                    except: pass
                    s.settimeout(0.5)
                    try:
                        s.connect((public_ip, port))
                        s.settimeout(None)
                        connected = True
                        sock = s
                        conn_mode_info = {"mode": "direct", "ip": public_ip, "port": port}
                        print(f"[Client] Hole punch successful!")
                        break
                    except Exception:
                        force_close_socket(s)
                        time.sleep(0.1)
                        
                # Phục hồi server_socket
                try:
                    try:
                        if hasattr(socket, 'AF_INET6'):
                            self.server_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                            if hasattr(socket, 'IPPROTO_IPV6') and hasattr(socket, 'IPV6_V6ONLY'):
                                try: self.server_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                                except: pass
                            self.server_socket.bind(("", BOUND_PORT))
                        else:
                            raise Exception("No IPv6")
                    except Exception:
                        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        self.server_socket.bind(('0.0.0.0', BOUND_PORT))
                    self.server_socket.listen(5)
                except Exception as e:
                    pass

        # ====== BƯỚC 4: Server Trung Chuyển (Relay) Fallback ======
        if not connected:
            if is_cancelled(): return
            display_host = specific_host or 'Relay'
            notify_status(_("Đục lỗ thất bại. Đang thử kết nối qua Server Trung Chuyển ({host})...").format(host=display_host))
            try:
                relay_session_id = f"relay_{self.my_id_clean}_{partner_id}"
                relay_req = json.dumps({
                    "action": "relay_request",
                    "target": partner_id,
                    "session_id": relay_session_id,
                    "relay_host": specific_host
                }) + '\n'
                with self.signaling_lock:
                    if getattr(self, 'primary_signaling_socket', None):
                        send_msg(self.primary_signaling_socket, relay_req.encode('utf-8'), APP_KEY)
                    else:
                        raise Exception("Chưa kết nối tới Signaling Server!")
                
                host_to_connect = specific_host if specific_host else core.config.SIGNALING_SERVER_HOSTS[0]
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5.0)
                s.connect((host_to_connect, core.config.SIGNALING_SERVER_PORT))
                s.settimeout(None)
                header = f"RELAY_CLIENT:{relay_session_id}\n"
                s.sendall(header.encode('utf-8'))
                
                time.sleep(1.5)
                sock = s
                connected = True
                conn_mode_info = {"mode": "relay", "relay_host": host_to_connect}
                notify_status(_("Đã kết nối qua Relay Server! Đang bắt tay..."))
            except Exception as e:
                connected = False

        if not connected:
            if reconnect_queue and retry_count + 1 < 10:
                next_attempt = retry_count + 2
                status_msg = _("Đang thử kết nối lại (lần {x}/10)...").format(x=next_attempt)
                notify_status(status_msg)
                time.sleep(4)
                self.connect_to_partner(partner_id, partner_pass, reconnect_queue, retry_count + 1, viewer_pid, reconnect_reason or "drop", computer_name_override, viewer_proc)
                return
            notify_status(_("Không thể kết nối (LAN, Đục lỗ, Relay đều thất bại)."))
            if reconnect_queue:
                reconnect_queue.put("FAILED|" + _("Không thể kết nối (LAN, Đục lỗ, Relay đều thất bại)."))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if sock: force_close_socket(sock)
            return

        # ======================================================================
        # Hoàn tất kết nối và handshake
        # ======================================================================
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception as e:
            print(f"[TCP_NODELAY] Lỗi thiết lập TCP_NODELAY trên Client: {e}")
        if is_lan_socket(sock):
            tune_socket_for_lan_bulk(sock)
        sock.settimeout(15.0)
            
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if sys.platform == "win32":
                ka = (1, 10000, 2000) if is_lan_socket(sock) else (1, 1000, 1000)
                sock.ioctl(socket.SIOC_KEEPALIVE_VALS, ka)
        except Exception as e:
            print(f"[KeepAlive] Lỗi cấu hình Keep-Alive trên Client: {e}")
            
        try:
            if not handshake_done:
                if is_cancelled():
                    force_close_socket(sock)
                    return
                notify_status(_("Đang bắt tay xác thực với đối tác..."))
                socket_passwords[sock] = partner_pass
                import platform
                handshake = json.dumps({
                    "password": partner_pass,
                    "client_id": self.my_id_clean,
                    "computer_name": platform.node()
                }).encode('utf-8')
                send_msg(sock, handshake, partner_pass)
                
                res_msg = recv_msg(sock, [partner_pass, APP_KEY])
                if not res_msg:
                    notify_status(_("Đối tác ngắt kết nối đột ngột!"))
                    if reconnect_queue:
                        reconnect_queue.put("FAILED|" + _("Đối tác ngắt kết nối đột ngột!"))
                    self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                    force_close_socket(sock)
                    return
                    
                res = json.loads(res_msg.decode('utf-8'))
            else:
                res = cached_res_payload
                
            if res.get("status") == "ok":
                if not hasattr(self, 'last_connected_peers'):
                    self.last_connected_peers = {}
                p_key = str(partner_id).replace(" ", "")
                if 'conn_mode_info' in locals() and conn_mode_info:
                    self.last_connected_peers[p_key] = conn_mode_info
                    print(f"[Client] Đã lưu thông số kết nối gần nhất cho {p_key}: {conn_mode_info}")

                host_w = res.get("width")
                host_h = res.get("height")
                computer_name = res.get("computer_name", "")
                
                if computer_name_override:
                    original_name = computer_name
                    computer_name = f"{computer_name_override} | {original_name}" if original_name else computer_name_override
                elif hasattr(self, 'load_saved_computers'):
                    try:
                        saved_comps = self.load_saved_computers()
                        for c in saved_comps:
                            if c.get("id", "").replace(" ", "") == partner_id:
                                if c.get("name"):
                                    original_name = computer_name
                                    computer_name = f"{c.get('name')} | {original_name}" if original_name else c.get("name")
                                break
                    except Exception:
                        pass
                        
                zalo_phone = res.get("zalo_phone", "")
                os_release = res.get("os_release", "")
                is_domain = res.get("is_domain", False)
                is_android = _handshake_is_android(res)
                if is_android and not os_release:
                    os_release = "android"
                
                probe_status_cb = None if (is_reconnect or retry_count > 0) else notify_status
                if is_android:
                    net_class, avg_ping, bandwidth = client_android_speed_test(sock, partner_pass, probe_status_cb)
                else:
                    net_class, avg_ping, bandwidth = client_quick_link_probe(sock, partner_pass, probe_status_cb)
                if net_class == "high":
                    net_class_viet = _("Tốt (High-speed)")
                elif net_class == "low":
                    net_class_viet = _("Yếu (Low-speed)")
                else:
                    net_class_viet = _("Trung bình (Medium)")
                if is_android or not is_lan_socket(sock):
                    status_text = _("Đo tốc độ: Ping {ping:.1f}ms, Băng thông {bw:.2f} Mbps. Chất lượng: {quality}.").format(ping=avg_ping, bw=bandwidth, quality=net_class_viet)
                    print(f"[Client] {status_text}")
                    if not is_reconnect and retry_count == 0:
                        notify_status(status_text)
                try:
                    sock.settimeout(None)
                    sock.setblocking(True)
                except Exception:
                    pass
                    
                if not is_reconnect and retry_count == 0:
                    notify_status(_("Kết nối thành công! Đang chuyển sang màn hình Host..."))
                if reconnect_queue:
                    try:
                        if viewer_pid and sys.platform == "win32":
                            sock_data = sock.share(viewer_pid)
                            reconnect_queue.put(("CONNECTED", ("SHARED_SOCK", sock_data), host_w, host_h, is_domain, is_android, os_release, zalo_phone, computer_name))
                            
                            def delayed_reconnect_close():
                                try:
                                    import psutil
                                    ps_proc = psutil.Process(viewer_pid)
                                    ps_proc.wait()
                                except:
                                    import time
                                    time.sleep(10.0)
                                try: sock.close()
                                except: pass
                            import threading
                            threading.Thread(target=delayed_reconnect_close, daemon=True).start()
                            
                        else:
                            reconnect_queue.put(("CONNECTED", sock, host_w, host_h, is_domain, is_android, os_release, zalo_phone, computer_name))
                    except Exception as e:
                        print(f"Failed to put socket in reconnect queue: {e}")
                        reconnect_queue.put("FAILED|" + str(e))
                        force_close_socket(sock)
                        socket_passwords.pop(sock, None)
                        return
                else:
                    self.after(0, self.launch_pygame_viewer, sock, host_w, host_h, computer_name, zalo_phone, is_domain, partner_id, partner_pass, is_android, os_release)

                # Cập nhật trạng thái App chính
                self.after(0, lambda: self.update_status(_("Đã kết nối"), is_success=True))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))

                # Kích hoạt giám sát reconnect cho phiên làm việc
                if viewer_proc and partner_id and partner_pass and not getattr(viewer_proc, '_monitor_started', False):
                    viewer_proc._monitor_started = True
                    c_queue = getattr(viewer_proc, '_cmd_queue', None)
                    def monitor_reconnect(process, pid, ppass, req_queue, cmd_q=None):
                        print(f"[Client Monitor] Started reconnect monitor for {pid}...")
                        while process.is_alive():
                            try:
                                msg = None
                                if cmd_q:
                                    try:
                                        msg = cmd_q.get(timeout=0.3)
                                    except Exception:
                                        pass
                                if not msg and req_queue:
                                    try:
                                        raw_msg = req_queue.get_nowait()
                                        if isinstance(raw_msg, str) and (raw_msg.startswith("RECONNECT_REQUEST") or raw_msg == "CANCEL_CONNECT"):
                                            msg = raw_msg
                                        else:
                                            req_queue.put(raw_msg)
                                            time.sleep(0.1)
                                    except Exception:
                                        pass
                                if not msg:
                                    continue

                                if isinstance(msg, str) and msg.startswith("RECONNECT_REQUEST"):
                                    reason = "login" if "|LOGIN" in msg else "drop"
                                    print(f"[Client Monitor] Pygame requested reconnect for {pid}... reason={reason}")
                                    if reason != "login":
                                        self.after(0, lambda: self.update_status(_("Đang tự động kết nối lại...")))
                                    threading.Thread(target=self.connect_to_partner, args=(pid, ppass, req_queue, 0, process.pid, reason, computer_name, process), daemon=True).start()
                                elif msg == "CANCEL_CONNECT":
                                    print(f"[Client Monitor] Reconnect monitor cancelled for {pid}")
                                    break
                            except Exception as e:
                                pass
                        print(f"[Client Monitor] Pygame viewer process exited with code: {process.exitcode}")
                        alive_viewers = [v for v in self.active_viewers if v["process"].is_alive()]
                        if not alive_viewers:
                            self.after(0, lambda: self.update_status(_("Sẵn sàng kết nối")))
                    threading.Thread(target=monitor_reconnect, args=(viewer_proc, partner_id, partner_pass, reconnect_queue, c_queue), daemon=True).start()

            else:
                msg = res.get("message", _("Sai mật khẩu!"))
                notify_status(_("Bị từ chối kết nối: ") + msg)
                if reconnect_queue:
                    reconnect_queue.put("FAILED|" + _("Kết nối bị từ chối:\n{msg}").format(msg=msg))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
        except Exception as e:
            if reconnect_queue and retry_count + 1 < 10:
                next_attempt = retry_count + 2
                status_msg = _("Đang thử kết nối lại (lần {x}/10)...").format(x=next_attempt)
                notify_status(status_msg)
                if sock:
                    force_close_socket(sock)
                    socket_passwords.pop(sock, None)
                time.sleep(4)
                self.connect_to_partner(partner_id, partner_pass, reconnect_queue, retry_count + 1, viewer_pid, reconnect_reason or "drop", computer_name_override, viewer_proc)
                return

            err_str = str(e)
            if "10054" in err_str:
                err_str = "Kết nối bị ngắt đột ngột bởi máy đích hoặc Relay Server (WinError 10054)."
            notify_status(_("Lỗi xác thực handshake:\n{err}").format(err=err_str))
            if reconnect_queue:
                reconnect_queue.put("FAILED|" + _("Lỗi xác thực handshake:\n{err}").format(err=err_str))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if sock:
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
            
    def launch_pygame_viewer(self, sock, host_w, host_h, computer_name="", zalo_phone="", is_domain=False, partner_id="", partner_pass="", is_android=False, os_release=""):
        if self._is_host_only_app() or run_client_viewer_loop is None:
            try:
                sock.close()
            except Exception:
                pass
            return
        try:
            import multiprocessing as mp
            reconnect_queue = mp.Queue()
            cmd_queue = mp.Queue()
            p = mp.Process(
                target=run_client_viewer_loop,
                args=(sock, host_w, host_h, computer_name, is_domain, partner_id, reconnect_queue, partner_pass, is_android, os_release, cmd_queue),
                daemon=True,
            )
            p.start()
            p._cmd_queue = cmd_queue
            
            # Track active viewer
            self.active_viewers.append({
                "process": p,
                "computer_name": computer_name,
                "zalo_phone": zalo_phone,
                "partner_id": partner_id
            })
            
            # Parent giữ socket đến khi viewer thoát — không close sớm (Win7 sẽ RST).
            def wait_and_close():
                try:
                    p.join()
                except:
                    pass
                try:
                    sock.close()
                except:
                    pass
            threading.Thread(target=wait_and_close, daemon=True).start()
            
            if partner_id and partner_pass and not getattr(p, '_monitor_started', False):
                p._monitor_started = True
                c_queue = getattr(p, '_cmd_queue', None)
                def monitor_reconnect(process, pid, ppass, req_queue, cmd_q=None):
                    print(f"[Client Monitor] Started reconnect monitor for {pid}...")
                    while process.is_alive():
                        try:
                            msg = None
                            if cmd_q:
                                try:
                                    msg = cmd_q.get(timeout=0.3)
                                except Exception:
                                    pass
                            if not msg and req_queue:
                                try:
                                    raw_msg = req_queue.get_nowait()
                                    if isinstance(raw_msg, str) and (raw_msg.startswith("RECONNECT_REQUEST") or raw_msg == "CANCEL_CONNECT"):
                                        msg = raw_msg
                                    else:
                                        req_queue.put(raw_msg)
                                        time.sleep(0.1)
                                except Exception:
                                    pass
                            if not msg:
                                continue

                            if isinstance(msg, str) and msg.startswith("RECONNECT_REQUEST"):
                                reason = "login" if "|LOGIN" in msg else "drop"
                                print(f"[Client Monitor] Pygame requested reconnect for {pid}... reason={reason}")
                                if reason != "login":
                                    self.after(0, lambda: self.update_status(_("Đang tự động kết nối lại...")))
                                threading.Thread(target=self.connect_to_partner, args=(pid, ppass, req_queue, 0, process.pid, reason, "", process), daemon=True).start()
                            elif msg == "CANCEL_CONNECT":
                                print(f"[Client Monitor] Reconnect monitor cancelled for {pid}")
                                break
                        except Exception as e:
                            pass
                    print(f"[Client Monitor] Pygame viewer process exited with code: {process.exitcode}")
                    
                threading.Thread(target=monitor_reconnect, args=(p, partner_id, partner_pass, reconnect_queue, c_queue), daemon=True).start()
            
            self.connect_btn.config(state=tk.NORMAL)
            self.update_status(_("Đã mở một cửa sổ điều khiển mới (Sẵn sàng kết nối)"))
            print(f"[Client] Đã mở tiến trình điều khiển cho {computer_name or 'đối tác'}")
            
        except Exception as e:
            print(f"[Client] Lỗi khởi chạy tiến trình điều khiển: {e}")
            self.connect_btn.config(state=tk.NORMAL)
            try: force_close_socket(sock)
            except: pass
            
