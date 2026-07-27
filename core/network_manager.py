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


from network.socket_utils import send_msg, recv_msg
from utils.logger import log_debug
from network.upnp import attempt_upnp_forward
from core.viewer import run_client_viewer_loop

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class NetworkMixin:
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
        try:
            import winreg
            path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS)
            except WindowsError:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "PromptOnSecureDesktop", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "SoftwareSASGeneration", 0, winreg.REG_DWORD, 3)
            winreg.CloseKey(key)
            print("[Host] Successfully configured registry (PromptOnSecureDesktop=0, SoftwareSASGeneration=3).")
        except PermissionError:
            # Không có quyền Admin → UAC vẫn sẽ dùng Secure Desktop → cảnh báo người dùng ở console/log
            print("[Host] WARNING: No Admin rights → PromptOnSecureDesktop cannot be set. UAC prompts may freeze screen.")
        except Exception as e:
            print(f"[Host] Failed to configure registry for UAC: {e}")

    def wake_on_lan(self, mac_str):
        # mac_str can be multiple MACs separated by comma
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
                try:
                    sock.sendto(data, ('255.255.255.255', 9))
                except:
                    pass
                # Try subnet broadcasts
                try:
                    local_ips = getattr(self, 'local_ip', get_local_ip()).split(',')
                    for lip in local_ips:
                        lip = lip.strip()
                        if lip and not lip.startswith('127.'):
                            parts = lip.split('.')
                            if len(parts) == 4:
                                subnet_broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                                sock.sendto(data, (subnet_broadcast, 9))
                except:
                    pass
                sock.close()
                self.update_status(_("Đã gửi Wake-On-Lan tới MAC {mac}").format(mac=m))
            except Exception as e:
                print(f"[WOL] Lỗi gửi Wake-On-Lan tới MAC {m}: {e}")

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
                    "local_ip": beacon.get("local_ip", addr[0]),
                    "port": int(beacon.get("port", 12345)),
                    "macs": beacon.get("macs", ""),
                    "last_seen": time.time(),
                    "source_ip": addr[0],
                }
                
                with self.lan_peers_lock:
                    old_info = self.lan_peers.get(peer_hwid)
                    is_new = old_info is None
                    should_save = is_new or old_info.get("local_ip") != peer_info["local_ip"] or old_info.get("macs") != peer_info["macs"]
                    # Update without erasing history if already saved
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
        """Hiển thị dialog danh sách các máy tính phát hiện được trong mạng LAN."""
        if hasattr(self, 'lan_computers_dialog') and self.lan_computers_dialog.winfo_exists():
            self.lan_computers_dialog.lift()
            self.lan_computers_dialog.focus_force()
            return
            
        dialog = tk.Toplevel(self)
        self.lan_computers_dialog = dialog
        dialog.title(_("Máy tính trong mạng LAN"))
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)

        w, h = 520, 440
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        # Title
        lbl_title = tk.Label(dialog, text=_("📡 MÁY TÍNH TRONG MẠNG LAN"), font=("Segoe UI", 11, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 5))
        
        lbl_desc = tk.Label(dialog, text=_("Kết nối trực tiếp không qua Signaling Server"), font=("Segoe UI", 8, "italic"), fg=self.text_gray, bg=self.bg_color)
        lbl_desc.pack(pady=(0, 10))

        # Scrollable list frame
        list_outer = tk.Frame(dialog, bg=self.entry_bg, bd=1, relief=tk.SUNKEN)
        list_outer.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

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
        status_label.pack(pady=(0, 5))

        def connect_to_peer(hwid, peer_info):
            # Kiểm tra xem máy này đã được lưu chưa
            saved_comps = self.load_saved_computers()
            existing_comp = next((c for c in saved_comps if c['id'].replace(" ", "") == hwid.replace(" ", "")), None)
            
            # Nếu đã lưu và có mật khẩu, kết nối luôn không cần hỏi
            if existing_comp and existing_comp.get("password"):
                self.update_status(_("Đang kết nối LAN trực tiếp tới {name}...").format(name=peer_info['computer_name']))
                if hasattr(self, 'connect_btn'):
                    self.connect_btn.config(state=tk.DISABLED)
                threading.Thread(target=self._connect_lan_direct, args=(hwid, peer_info, existing_comp["password"]), daemon=True).start()
                return

            """Mở dialog nhập mật khẩu rồi kết nối trực tiếp qua LAN."""
            pass_dialog = tk.Toplevel(dialog)
            pass_dialog.title(_("Kết nối tới ") + str(peer_info['computer_name']))
            pass_dialog.resizable(False, False)
            pass_dialog.configure(bg=self.bg_color)
            pass_dialog.transient(dialog)
            pass_dialog.grab_set()

            pw, ph = 360, 230
            px = dialog.winfo_x() + (dialog.winfo_width() - pw) // 2
            py = dialog.winfo_y() + (dialog.winfo_height() - ph) // 2
            pass_dialog.geometry(f"{pw}x{ph}+{px}+{py}")

            fmt_id = f"{hwid[:3]} {hwid[3:6]} {hwid[6:9]} {hwid[9:]}" if len(hwid) == 12 else hwid
            tk.Label(pass_dialog, text=_("Máy: ") + str(peer_info['computer_name']), font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.bg_color).pack(pady=(15, 2))
            tk.Label(pass_dialog, text=_("ID: ") + str(fmt_id) + _("  •  IP: ") + str(peer_info['local_ip']), font=("Segoe UI", 8), fg=self.text_gray, bg=self.bg_color).pack(pady=(0, 10))

            tk.Label(pass_dialog, text=_("Nhập mật khẩu:"), font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color).pack(anchor=tk.W, padx=30)
            
            pass_var = tk.StringVar()
            pass_entry = tk.Entry(pass_dialog, textvariable=pass_var, font=("Segoe UI", 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, show="*", relief=tk.FLAT, bd=4)
            pass_entry.pack(padx=30, fill=tk.X, pady=(3, 5))
            
            save_var = tk.BooleanVar(value=True)
            save_cb = tk.Checkbutton(pass_dialog, text=_("Lưu mật khẩu máy tính này"), variable=save_var, font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color, selectcolor=self.bg_color, activebackground=self.bg_color, activeforeground=self.text_gray, cursor="hand2")
            save_cb.pack(anchor=tk.W, padx=25, pady=(0, 10))
            
            pass_entry.focus()
            
            def do_connect():
                password = pass_var.get().strip()
                if not password:
                    self.show_custom_error(_("Lỗi"), _("Vui lòng nhập mật khẩu!"), parent=pass_dialog)
                    return
                    
                if save_var.get():
                    comps = self.load_saved_computers()
                    comp_idx = next((i for i, c in enumerate(comps) if c['id'].replace(" ", "") == hwid.replace(" ", "")), -1)
                    if comp_idx >= 0:
                        comps[comp_idx]["password"] = password
                        comps[comp_idx]["name"] = peer_info['computer_name']
                    else:
                        comps.append({
                            "name": peer_info['computer_name'],
                            "id": hwid,
                            "password": password,
                            "group": _("Mạng LAN")
                        })
                    self.save_saved_computers(comps)
                    if hasattr(self, '_reorder_saved_computers_func'):
                        self.after(50, self._reorder_saved_computers_func)
                        
                pass_dialog.destroy()
                # Giữ cửa sổ LAN hiển thị theo yêu cầu người dùng
                # dialog.destroy() 
                # Kết nối trực tiếp qua LAN
                self.update_status(_("Đang kết nối LAN trực tiếp tới {name}...").format(name=peer_info['computer_name']))
                if hasattr(self, 'connect_btn'):
                    self.connect_btn.config(state=tk.DISABLED)
                threading.Thread(target=self._connect_lan_direct, args=(hwid, peer_info, password), daemon=True).start()

            pass_entry.bind("<Return>", lambda e: do_connect())
            pass_entry.bind("<KP_Enter>", lambda e: do_connect())

            btn_frame = tk.Frame(pass_dialog, bg=self.bg_color)
            btn_frame.pack(fill=tk.X, padx=30, pady=(0, 15))
            tk.Button(btn_frame, text=_("Kết nối"), font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, pady=4, cursor="hand2", command=do_connect).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
            tk.Button(btn_frame, text=_("Hủy"), font=("Segoe UI", 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, relief=tk.FLAT, bd=0, pady=4, cursor="hand2", command=pass_dialog.destroy).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))


        def refresh_list():
            # Xóa danh sách cũ
            for w in scroll_frame.winfo_children():
                w.destroy()

            with self.lan_peers_lock:
                peers = dict(self.lan_peers)

            if not peers:
                tk.Label(scroll_frame, text=_("Không tìm thấy máy tính nào trong mạng LAN.\nĐảm bảo các máy đều đang chạy Easy Remote Desktop."), font=("Segoe UI", 9), fg=self.text_gray, bg=self.entry_bg, justify=tk.CENTER).pack(pady=40, padx=20)
                status_label.config(text=_("Đang quét... (0 máy)"))
            else:
                status_label.config(text=_("Tìm thấy ") + str(len(peers)) + _(" máy trong mạng LAN"))
                for hwid, info in sorted(peers.items(), key=lambda x: x[1].get("computer_name", "")):
                    row = tk.Frame(scroll_frame, bg=self.card_color, bd=0)
                    row.pack(fill=tk.X, padx=5, pady=3)

                    # Status dot (green = online)
                    age = time.time() - info["last_seen"]
                    dot_color = "#2ECC71" if age < LAN_OFFLINE_TIMEOUT else "#FF4D4D"
                    tk.Label(row, text="●", font=("Segoe UI", 10), fg=dot_color, bg=self.card_color).pack(side=tk.LEFT, padx=(10, 5))

                    # Connect / WOL button
                    age = time.time() - info["last_seen"]
                    if age < LAN_OFFLINE_TIMEOUT:
                        btn = tk.Button(row, text=_("Kết nối"), font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, padx=12, pady=3, cursor="hand2", command=lambda h=hwid, i=info: connect_to_peer(h, i))
                    else:
                        btn = tk.Button(row, text=_("Bật nguồn (WOL)"), font=("Segoe UI", 9, "bold"), fg=self.text_white, bg="#D35400", activebackground="#E67E22", relief=tk.FLAT, bd=0, padx=12, pady=3, cursor="hand2", command=lambda m=info.get("macs", ""): self.wake_on_lan(m))
                        if not info.get("macs"):
                            btn.config(state=tk.DISABLED, bg="#3A3A4A", disabledforeground="#F39C12")
                    btn.pack(side=tk.RIGHT, padx=10, pady=5)

                    # Info
                    info_frame = tk.Frame(row, bg=self.card_color)
                    info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=5)
                    
                    fmt_id = f"{hwid[:3]} {hwid[3:6]} {hwid[6:9]} {hwid[9:]}" if len(hwid) == 12 else hwid
                    
                    # Shorten IP display if there are multiple IPs
                    ip_str = info['local_ip']
                    ip_list = [ip.strip() for ip in ip_str.split(',') if ip.strip()]
                    display_ip = f"{ip_list[0]} (+{len(ip_list)-1})" if len(ip_list) > 1 else (ip_list[0] if ip_list else ip_str)
                    
                    lbl_name = tk.Label(info_frame, text=info["computer_name"], font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.card_color, anchor=tk.W)
                    lbl_name.pack(fill=tk.X)
                    lbl_details = tk.Label(info_frame, text=_("ID: ") + str(fmt_id) + _("  •  IP: ") + str(display_ip) + ":" + str(info['port']), font=("Segoe UI", 8), fg=self.text_gray, bg=self.card_color, anchor=tk.W)
                    lbl_details.pack(fill=tk.X)
                    
                    # Bind double click
                    def on_row_double_click(e, h=hwid, i=info):
                        connect_to_peer(h, i)
                    
                    for w in [row, info_frame, lbl_name, lbl_details]:
                        w.bind("<Double-1>", on_row_double_click)
                        w.config(cursor="hand2")

        refresh_list()

        # Auto refresh mỗi 5 giây
        auto_refresh_id = [None]
        def auto_refresh():
            if dialog.winfo_exists():
                refresh_list()
                auto_refresh_id[0] = dialog.after(5000, auto_refresh)
        auto_refresh_id[0] = dialog.after(5000, auto_refresh)

        def on_dialog_close():
            if auto_refresh_id[0]:
                dialog.after_cancel(auto_refresh_id[0])
            try:
                canvas.unbind_all("<MouseWheel>")
            except: pass
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

        # Bottom buttons
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        tk.Button(btn_frame, text=_("🔄 Làm mới"), font=("Segoe UI", 9, "bold"), fg=self.text_white, bg="#007ACC", activebackground="#005A9E", relief=tk.FLAT, bd=0, pady=4, padx=10, cursor="hand2", command=refresh_list).pack(side=tk.LEFT)
        tk.Button(btn_frame, text=_("Đóng"), font=("Segoe UI", 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, relief=tk.FLAT, bd=0, pady=4, padx=15, cursor="hand2", command=on_dialog_close).pack(side=tk.RIGHT)

    def _connect_lan_direct(self, hwid, peer_info, password):
        """Kết nối TCP trực tiếp tới máy trong LAN (không qua Signaling Server)."""
        import platform
        ip = peer_info["local_ip"]
        port = peer_info["port"]
        
        # Thử kết nối tới tất cả IP nếu có nhiều
        ips_to_try = [i.strip() for i in ip.split(',') if i.strip()]
        # Thêm source_ip nếu khác
        source_ip = peer_info.get("source_ip", "")
        if source_ip and source_ip not in ips_to_try:
            ips_to_try.append(source_ip)
            
        sock = None
        connected = False
        
        for try_ip in ips_to_try:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3.0)
                s.connect((try_ip, port))
                s.settimeout(15.0)
                sock = s
                connected = True
                print(f"[LAN Direct] Connected to {try_ip}:{port}")
                break
            except Exception as e:
                print(f"[LAN Direct] Failed to connect to {try_ip}:{port}: {e}")
                try: s.close()
                except: pass
                continue

        if not connected or not sock:
            self.update_status(_("Kết nối LAN thất bại!"))
            self.after(0, lambda: self.show_custom_error(_("Lỗi kết nối LAN"), _("Không thể kết nối tới ") + str(peer_info['computer_name']) + " (" + str(ip) + ":" + str(port) + _(").\nKiểm tra Tường lửa (Firewall) hoặc đảm bảo máy đích đang chạy ứng dụng.")))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            return

        # Sử dụng lại flow handshake hiện có
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except: pass
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.ioctl(socket.SIOC_KEEPALIVE_VALS, (1, 1000, 1000))
        except: pass

        try:
            socket_passwords[sock] = password
            hs_data = json.dumps({"password": password, "client_id": self.my_id_clean, "computer_name": platform.node()}).encode('utf-8')
            send_msg(sock, hs_data, password)
            
            res_msg = recv_msg(sock, [password, APP_KEY])
            if not res_msg:
                self.update_status(_("Sẵn sàng kết nối"))
                self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Đối tác ngắt kết nối đột ngột!")))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                force_close_socket(sock)
                return

            res = json.loads(res_msg.decode('utf-8'))
            
            if res.get("status") == "ok":
                host_w = res.get("width")
                host_h = res.get("height")
                computer_name = res.get("computer_name", "")
                zalo_phone = res.get("zalo_phone", "")
                os_release = res.get("os_release", "")
                is_domain = res.get("is_domain", False)
                partner_id = hwid

                # Speed test (same flow as regular connect)
                self.update_status(_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 1/2..."))
                net_class = "medium"
                avg_ping = 50.0
                bandwidth = 10.0
                try:
                    sock.settimeout(10.0)
                    runs = []
                    for run_idx in range(2):
                        if run_idx > 0:
                            self.update_status(_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 2/2..."))
                        rtts = []
                        for _i in range(3):
                            t0 = time.time()
                            send_msg(sock, json.dumps({"action": "speed_test_ping"}).encode('utf-8'), password)
                            pong_msg = recv_msg(sock, password)
                            if pong_msg:
                                pong_data = json.loads(pong_msg.decode('utf-8'))
                                if pong_data.get("action") == "speed_test_pong":
                                    rtts.append(time.time() - t0)
                            time.sleep(0.05)
                        run_ping = (sum(rtts) / len(rtts)) * 1000.0 if rtts else 50.0
                        
                        run_bw = 10.0
                        suggested_size = 1572864
                        if run_ping > 200.0: suggested_size = 131072
                        elif run_ping > 50.0: suggested_size = 524288
                        send_msg(sock, json.dumps({"action": "speed_test_bw_req", "suggested_size": suggested_size}).encode('utf-8'), password)
                        bw_start_msg = recv_msg(sock, password)
                        if bw_start_msg:
                            bw_start_data = json.loads(bw_start_msg.decode('utf-8'))
                            if bw_start_data.get("action") == "speed_test_bw_start":
                                dummy_size = bw_start_data.get("size", 1572864)
                                warm_size = dummy_size // 3
                                measure_size = dummy_size - warm_size
                                warm_data = b''
                                while len(warm_data) < warm_size:
                                    chunk = sock.recv(min(65536, warm_size - len(warm_data)))
                                    if not chunk: break
                                    warm_data += chunk
                                t_start = time.time()
                                measured_data = b''
                                while len(measured_data) < measure_size:
                                    chunk = sock.recv(min(65536, measure_size - len(measured_data)))
                                    if not chunk: break
                                    measured_data += chunk
                                t_end = time.time()
                                duration = t_end - t_start
                                total_len = len(warm_data) + len(measured_data)
                                if duration > 0 and total_len == dummy_size:
                                    run_bw = (measure_size * 8.0) / (duration * 1024.0 * 1024.0)
                        runs.append((run_ping, run_bw))
                        if run_idx == 0: time.sleep(0.2)
                except Exception as e:
                    print(f"[LAN] Speed test error: {e}")
                    try:
                        send_msg(sock, json.dumps({"action": "speed_test_result", "net_class": "medium", "ping": 50.0, "bandwidth": 10.0}).encode('utf-8'), password)
                    except: pass
                finally:
                    try: sock.settimeout(None)
                    except: pass
                    
                if runs:
                    best_run = max(runs, key=lambda x: x[1])
                    avg_ping = best_run[0]
                    bandwidth = best_run[1]
                    if bandwidth > 20.0 and avg_ping < 10.0:
                        net_class = "high"
                    elif bandwidth < 5.0 or avg_ping > 50.0:
                        net_class = "low"
                    else:
                        net_class = "medium"
                    try:
                        send_msg(sock, json.dumps({"action": "speed_test_result", "net_class": net_class, "ping": avg_ping, "bandwidth": bandwidth}).encode('utf-8'), password)
                    except: pass
                    print(f"[LAN Direct] Speed: Ping {avg_ping:.1f}ms, BW {bandwidth:.2f} Mbps, Class: {net_class}")

                self.update_status(_("Kết nối LAN thành công! Đang khởi động màn hình..."))
                sock.settimeout(None)
                self.after(0, self.launch_pygame_viewer, sock, host_w, host_h, computer_name, zalo_phone, is_domain, partner_id, password, False, os_release)
            else:
                msg = res.get("message", _("Sai mật khẩu!"))
                self.update_status(_("Bị từ chối kết nối"))
                self.after(0, lambda: self.show_custom_error(_("Từ chối kết nối"), _("Kết nối bị từ chối:\n{msg}").format(msg=msg)))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
        except Exception as e:
            self.update_status(_("Sẵn sàng kết nối"))
            self.after(0, lambda err=str(e): self.show_custom_error(_("Lỗi bắt tay LAN"), _("Lỗi xác thực handshake:\n{err}").format(err=err)))
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
                sock.connect((host, core.config.SIGNALING_SERVER_PORT))
                sock.settimeout(None)
                
                # Use base HWID if we are the primary instance (port 12345), else append port to avoid stealing ID from background service
                is_svc_active = False
                if hasattr(self, 'check_if_service_active'):
                    is_svc_active = self.check_if_service_active()
                else:
                    is_svc_active = getattr(self, 'is_service_active', False)
                register_id = self.my_id_clean if (BOUND_PORT == PORTS_TO_TRY[0] and not is_svc_active) else f"{self.my_id_clean}_{BOUND_PORT}"
                
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
                self.after(0, lambda t=target, o=online: self.update_saved_computer_status(t, o))
                
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
        partner_id = self.partner_id_var.get().strip().replace(" ", "")
        partner_pass = self.partner_pass_var.get().strip()
        
        if not partner_id or len(partner_id) < 12:
            self.show_custom_error(_("Lỗi"), _("Vui lòng nhập mã ID đối tác hợp lệ (12 chữ số)!"))
            return
            
        if not partner_pass:
            self.show_custom_error(_("Lỗi"), _("Vui lòng nhập mật khẩu đối tác!"))
            return
            
        self.update_status(_("Đang tìm địa chỉ IP của đối tác trên dịch vụ danh bạ..."))
        self.connect_btn.config(state=tk.DISABLED)
        
        # Lưu biến UI vào thuộc tính thông thường để thread chạy ngầm đọc (Tránh lỗi Tcl deadlock khi đọc biến UI từ thread khác)
        self._current_force_relay = False
        if hasattr(self, 'force_relay_var'):
            self._current_force_relay = self.force_relay_var.get()
            
        # Connect inside background thread to prevent UI freezing
        def run_connect():
            try:
                self.connect_to_partner(partner_id, partner_pass)
            except Exception as e:
                import traceback
                try:
                    with open(r"C:\Apps\P2P\crash_connect.log", "a") as f:
                        f.write(traceback.format_exc() + "\n")
                except:
                    pass
                print(f"[Client] Background thread crashed: {e}")
        
        threading.Thread(target=run_connect, daemon=True).start()
    def connect_to_partner(self, partner_id, partner_pass, reconnect_queue=None, retry_count=0, viewer_pid=None):
        if partner_id == getattr(self, "my_id_clean", ""):
            self.after(0, lambda: self.show_custom_info(_("Thông báo"), _("Bạn không thể kết nối tới chính bạn :-)")))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            self.update_status(_("Kết nối bị hủy."))
            return
            
        # Clean up dead viewer processes first
        self.active_viewers = [v for v in self.active_viewers if v["process"].is_alive()]
        
        # Check if we already have an active connection to this partner_id
        existing_viewer = None
        for v in self.active_viewers:
            if v.get("partner_id") == partner_id:
                existing_viewer = v
                break
                
        if existing_viewer and reconnect_queue is None:
            print(f"[Client] Already connected to {partner_id}. Sending blink signal.")
            self.update_status(_("Đang hiển thị cửa sổ điều khiển đã kết nối của {partner_id}...").format(partner_id=partner_id))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            # Write blink signal file
            import tempfile
            blink_file = os.path.join(tempfile.gettempdir(), f"antigravity_blink_{partner_id}.tmp")
            try:
                with open(blink_file, "w") as f:
                    f.write("1")
            except Exception as write_err:
                print(f"[Client] Failed to write blink signal: {write_err}")
            return

        sock = None
        connected = False
        handshake_done = False
        cached_res_payload = None
        force_relay = getattr(self, '_current_force_relay', False)

        # ====== BƯỚC 1: Quét mạng LAN để tìm ID (5 lần) ======
        lan_target = None
        if not force_relay and hasattr(self, 'lan_peers'):
            for attempt in range(5):
                self.update_status(_("Đang tìm máy trong mạng LAN (lần {n}/5)...").format(n=attempt + 1))
                current_time = time.time()
                with self.lan_peers_lock:
                    # Clean up old peers
                    self.lan_peers = {k: v for k, v in self.lan_peers.items() if current_time - v.get("last_seen", 0) < 15}
                    if partner_id in self.lan_peers:
                        lan_target = self.lan_peers[partner_id]
                
                if lan_target:
                    print(f"[LAN Discovery] Tìm thấy đối tác {partner_id} trong mạng LAN!")
                    break
                
                time.sleep(0.5) # Đợi 0.5s giữa các lần tìm

        if lan_target:
            self.update_status(_("Đang thử kết nối LAN trực tiếp..."))
            local_ip = lan_target.get("local_ip", "")
            local_port = lan_target.get("port", 12345)
            ips_to_try = [ip.strip() for ip in local_ip.split(',') if ip.strip()]
            ports_to_try = [local_port]
            for p in [12345, 12346, 12347, 12348]:
                if p not in ports_to_try:
                    ports_to_try.append(p)
            
            for try_ip in ips_to_try:
                if connected: break
                for p in ports_to_try:
                    if connected: break
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(1.0)
                        s.connect((try_ip, p))
                        s.settimeout(None)
                        # Handshake
                        socket_passwords[s] = partner_pass
                        import platform
                        hs_data = json.dumps({"password": partner_pass, "client_id": self.my_id_clean, "computer_name": platform.node()}).encode('utf-8')
                        send_msg(s, hs_data, partner_pass)
                        tmp_res_msg = recv_msg(s, [partner_pass, APP_KEY])
                        if tmp_res_msg:
                            tmp_res = json.loads(tmp_res_msg.decode('utf-8'))
                            if tmp_res.get("status") in ("ok", "error"):
                                sock = s
                                connected = True
                                handshake_done = True
                                cached_res_payload = tmp_res
                                print(f"[Client] Connected & Handshaked via LAN Direct: {try_ip}:{p}")
                                break
                        if not connected:
                            force_close_socket(s)
                    except Exception as e:
                        try:
                            with open(r"C:\Apps\P2P\lan_debug.log", "a") as f:
                                f.write(f"LAN connect to {try_ip}:{p} failed: {e}\n")
                        except: pass
                        try: s.close()
                        except: pass
        
        # ====== BƯỚC 2: Hỏi Signaling Server (nếu LAN thất bại hoặc không tìm thấy) ======
        public_ip, port = None, None
        specific_host = getattr(self, 'current_signaling_host', None)
        
        if not connected:
            if not hasattr(self, 'signaling_sockets') or not self.signaling_sockets:
                self.update_status(_("Chưa kết nối Máy chủ Tín hiệu!"))
                self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Chưa kết nối đến Máy chủ Tín hiệu. Vui lòng kiểm tra lại mạng.")))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                return

            req = json.dumps({
                "action": "connect_request",
                "target": partner_id,
                "port": BOUND_PORT,
                "local_ip": getattr(self, 'local_ip', "127.0.0.1"),
                "local_port": BOUND_PORT
            }) + '\n'
            
            sockets_to_try = []
            with self.signaling_lock:
                if getattr(self, 'primary_signaling_socket', None):
                    sockets_to_try.append(self.primary_signaling_socket)
                for s in getattr(self, 'signaling_sockets', {}).values():
                    if s not in sockets_to_try:
                        sockets_to_try.append(s)
                        
            self.update_status(_("Đang tìm địa chỉ đối tác trên server danh bạ..."))
            
            signaling_success = False
            for s in sockets_to_try:
                self.pending_connection_info = None
                try:
                    with self.signaling_lock:
                        send_msg(s, req.encode('utf-8'), APP_KEY)
                except Exception:
                    continue
                    
                wait_timeout = 6.0
                while wait_timeout > 0 and self.pending_connection_info is None:
                    time.sleep(0.2)
                    wait_timeout -= 0.2
                    
                if self.pending_connection_info and self.pending_connection_info != "error":
                    signaling_success = True
                    break
                    
            if not signaling_success:
                if reconnect_queue and retry_count < 30:
                    status_msg = _("Mất kết nối. Đang thử kết nối lại lần {count}/30...").format(count=retry_count + 1)
                    try: reconnect_queue.put(f"STATUS|{status_msg}")
                    except: pass
                    time.sleep(2)
                    self.connect_to_partner(partner_id, partner_pass, reconnect_queue, retry_count + 1, viewer_pid)
                    return
                self.update_status(_("Sẵn sàng kết nối"))
                if not reconnect_queue:
                    self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Không thể tìm thấy hoặc đối tác đang Offline.")))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                if reconnect_queue:
                    reconnect_queue.put("FAILED")
                return
                
            if len(self.pending_connection_info) >= 4:
                public_ip, port_str, _dummy1, _dummy2 = self.pending_connection_info[:4]
            else:
                public_ip, port_str, _dummy1 = self.pending_connection_info
                
            port = int(port_str) if port_str else 0

        # ====== BƯỚC 3: Đục lỗ Tường lửa (TCP Hole Punching) 10 lần ======
        if not connected and not force_relay and public_ip and port:
            skip_hole_punch = False
            if hasattr(self, 'current_ip') and self.current_ip == public_ip:
                print("[Client] Skipping Hole Punching because both peers share the same Public IP (same router).")
                skip_hole_punch = True
            
            if not skip_hole_punch:
                self.update_status(_("Đang đục lỗ Tường lửa tới {ip}:{port}...").format(ip=public_ip, port=port))
                
                if getattr(self, 'server_socket', None):
                    try: self.server_socket.close()
                    except: pass
                
                for attempt in range(10):
                    self.update_status(_("Đang đục lỗ Tường lửa lần {n}/10...").format(n=attempt + 1))
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
            display_host = specific_host or 'Relay'
            self.update_status(_("Đục lỗ/LAN thất bại. Đang thử kết nối qua Server Trung Chuyển ({host})...").format(host=display_host))
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
                self.update_status(_("Đã kết nối qua Relay Server!"))
            except Exception as e:
                connected = False

        if not connected:
            self.update_status(_("Sẵn sàng kết nối"))
            self.after(0, lambda: self.show_custom_error(_("Lỗi kết nối"), _("Không thể kết nối (LAN, Đục lỗ, Relay đều thất bại).")))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if sock: force_close_socket(sock)
            return

        # ======================================================================
        # Hoàn tất kết nối và handshake
        # ======================================================================
        # Tắt Nagle's algorithm (TCP_NODELAY) để giảm độ trễ tối đa cho cả đo tốc độ và điều khiển
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception as e:
            print(f"[TCP_NODELAY] Lỗi thiết lập TCP_NODELAY trên Client: {e}")
        sock.settimeout(15.0)
            
        # Cấu hình TCP Keep-Alive bảo vệ kết nối khỏi bị đóng bởi Firewall/Router
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.ioctl(socket.SIOC_KEEPALIVE_VALS, (1, 1000, 1000))
        except Exception as e:
            print(f"[KeepAlive] Lỗi cấu hình Keep-Alive trên Client: {e}")
            
        try:
            if not handshake_done:
                # Register the socket password
                socket_passwords[sock] = partner_pass
                # Send handshake password
                import platform
                handshake = json.dumps({
                    "password": partner_pass,
                    "client_id": self.my_id_clean,
                    "computer_name": platform.node()
                }).encode('utf-8')
                send_msg(sock, handshake, partner_pass)
                
                # Read verification response (allow APP_KEY fallback to receive error messages)
                res_msg = recv_msg(sock, [partner_pass, APP_KEY])
                if not res_msg:
                    self.update_status(_("Sẵn sàng kết nối"))
                    self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Đối tác ngắt kết nối đột ngột!")))
                    self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                    force_close_socket(sock)
                    return
                    
                res = json.loads(res_msg.decode('utf-8'))
            else:
                res = cached_res_payload
                
            if res.get("status") == "ok":
                host_w = res.get("width")
                host_h = res.get("height")
                computer_name = res.get("computer_name", "")
                
                # Replace with saved name from list to make it easier to identify the host
                if hasattr(self, 'load_saved_computers'):
                    try:
                        saved_comps = self.load_saved_computers()
                        for c in saved_comps:
                            # The saved ID might contain spaces (e.g. "123 456 789 012")
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
                is_android = res.get("is_android", False)
                
                # Perform pre-connection speed test (Ping/Latency and Bandwidth) - 2 runs, select highest speed
                self.update_status(_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 1/2..."))
                net_class = "medium"
                net_class_viet = _("Trung bình (Medium)")
                avg_ping = 50.0
                bandwidth = 10.0
                try:
                    sock.settimeout(10.0)
                    runs = []
                    for run_idx in range(2):
                        if run_idx > 0:
                            self.update_status(_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 2/2..."))
                        # 1. Ping / Latency test
                        rtts = []
                        for _i in range(3):
                            t0 = time.time()
                            send_msg(sock, json.dumps({"action": "speed_test_ping"}).encode('utf-8'), partner_pass)
                            pong_msg = recv_msg(sock, partner_pass)
                            if pong_msg:
                                pong_data = json.loads(pong_msg.decode('utf-8'))
                                if pong_data.get("action") == "speed_test_pong":
                                    rtts.append(time.time() - t0)
                            time.sleep(0.05)
                        
                        run_ping = 50.0
                        if rtts:
                            run_ping = (sum(rtts) / len(rtts)) * 1000.0
                            
                        # 2. Bandwidth test
                        run_bw = 10.0
                        suggested_size = 1572864
                        if run_ping > 200.0: suggested_size = 131072
                        elif run_ping > 50.0: suggested_size = 524288
                        send_msg(sock, json.dumps({"action": "speed_test_bw_req", "suggested_size": suggested_size}).encode('utf-8'), partner_pass)
                        bw_start_msg = recv_msg(sock, partner_pass)
                        if bw_start_msg:
                            bw_start_data = json.loads(bw_start_msg.decode('utf-8'))
                            if bw_start_data.get("action") == "speed_test_bw_start":
                                dummy_size = bw_start_data.get("size", 1572864)
                                warm_size = dummy_size // 3 # 1/3 cho warm-up
                                measure_size = dummy_size - warm_size
                                
                                warm_data = b''
                                while len(warm_data) < warm_size:
                                    chunk = sock.recv(min(65536, warm_size - len(warm_data)))
                                    if not chunk:
                                        break
                                    warm_data += chunk
                                    
                                t_start = time.time()
                                measured_data = b''
                                while len(measured_data) < measure_size:
                                    chunk = sock.recv(min(65536, measure_size - len(measured_data)))
                                    if not chunk:
                                        break
                                    measured_data += chunk
                                t_end = time.time()
                                
                                duration = t_end - t_start
                                total_len = len(warm_data) + len(measured_data)
                                if duration > 0 and total_len == dummy_size:
                                    run_bw = (measure_size * 8.0) / (duration * 1024.0 * 1024.0)
                        
                        runs.append((run_ping, run_bw))
                        if run_idx == 0:
                            time.sleep(0.2) # Small gap between runs
                except Exception as e:
                    print(f"[Client] Speed test error: {e}")
                    # Send default result to host to avoid locking
                    try:
                        send_msg(sock, json.dumps({
                            "action": "speed_test_result",
                            "net_class": "medium",
                            "ping": 50.0,
                            "bandwidth": 10.0
                        }).encode('utf-8'), partner_pass)
                    except: pass
                finally:
                    try: sock.settimeout(None)
                    except: pass
                            
                if runs:
                    # Compare and select the run with the highest bandwidth speed
                    best_run = max(runs, key=lambda x: x[1])
                    avg_ping = best_run[0]
                    bandwidth = best_run[1]
                                                                        
                    # 3. Network quality classification
                    # - Tốt (High-speed): Băng thông > 20 Mbps, Ping < 10ms.
                    # - Trung bình (Medium): Băng thông 5 - 20 Mbps, Ping 50 - 100ms.
                    # - Yếu (Low-speed): Băng thông < 5 Mbps hoặc Ping > 100ms.
                    if bandwidth > 20.0 and avg_ping < 10.0:
                        net_class = "high"
                        net_class_viet = _("Tốt (High-speed)")
                    elif bandwidth < 5.0 or avg_ping > 50.0:
                        net_class = "low"
                        net_class_viet = _("Yếu (Low-speed)")
                    else:
                        net_class = "medium"
                        net_class_viet = _("Trung bình (Medium)")
                        
                    # 4. Report speed test results to Host
                    try:
                        send_msg(sock, json.dumps({
                            "action": "speed_test_result",
                            "net_class": net_class,
                            "ping": avg_ping,
                            "bandwidth": bandwidth
                        }).encode('utf-8'), partner_pass)
                    except: pass
                    
                    status_text = _("Đo tốc độ (Lớn nhất 2 lần): Ping {ping:.1f}ms, Băng thông {bw:.2f} Mbps. Chất lượng: {quality}.").format(ping=avg_ping, bw=bandwidth, quality=net_class_viet)
                    print(f"[Client] {status_text}")
                    self.update_status(status_text)
                    time.sleep(0.5)
                    
                # Pygame window sẽ mở đúng với độ phân giải thật của host. 
                # (Kích thước ảnh thực tế truyền qua mạng vẫn sẽ được nén lại bởi dyn_scale ở phía Host)
                self.update_status(_("Kết nối thành công! Đang khởi động màn hình..."))
                if reconnect_queue:
                    try:
                        if viewer_pid and sys.platform == "win32":
                            sock_data = sock.share(viewer_pid)
                            reconnect_queue.put(("SHARED_SOCK", sock_data))
                            
                            # Keep socket alive so child process can call WSASocket before it closes
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
                            reconnect_queue.put(sock)
                    except Exception as e:
                        print(f"Failed to put socket in reconnect queue: {e}")
                        reconnect_queue.put("FAILED")
                        force_close_socket(sock)
                        socket_passwords.pop(sock, None)
                else:
                    self.after(0, self.launch_pygame_viewer, sock, host_w, host_h, computer_name, zalo_phone, is_domain, partner_id, partner_pass, is_android, os_release)
            else:
                msg = res.get("message", _("Sai mật khẩu!"))
                self.update_status(_("Bị từ chối kết nối"))
                if reconnect_queue:
                    reconnect_queue.put("FAILED")
                self.after(0, lambda: self.show_custom_error(_("Từ chối kết nối"), _("Kết nối bị từ chối:\n{msg}").format(msg=msg)))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
        except Exception as e:
            if reconnect_queue and retry_count < 30:
                status_msg = _("Mất kết nối. Đang thử kết nối lại lần {count}/30...").format(count=retry_count + 1)
                try: reconnect_queue.put(f"STATUS|{status_msg}")
                except: pass
                if sock:
                    force_close_socket(sock)
                    socket_passwords.pop(sock, None)
                time.sleep(2)
                self.connect_to_partner(partner_id, partner_pass, reconnect_queue, retry_count + 1, viewer_pid)
                return

            self.update_status(_("Sẵn sàng kết nối"))
            if reconnect_queue:
                reconnect_queue.put("FAILED")
            else:
                err_str = str(e)
                if "10054" in err_str:
                    err_str = "Kết nối bị ngắt đột ngột bởi máy đích hoặc Relay Server (WinError 10054)."
                self.after(0, lambda err=err_str: self.show_custom_error(_("Lỗi bắt tay"), _("Lỗi xác thực handshake:\n{err}").format(err=err)))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if sock:
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
            
    def launch_pygame_viewer(self, sock, host_w, host_h, computer_name="", zalo_phone="", is_domain=False, partner_id="", partner_pass="", is_android=False, os_release=""):
        try:
            import multiprocessing as mp
            reconnect_queue = mp.Queue()
            p = mp.Process(target=run_client_viewer_loop, args=(sock, host_w, host_h, computer_name, is_domain, partner_id, reconnect_queue, partner_pass, is_android, os_release), daemon=True)
            p.start()
            
            # Track active viewer
            self.active_viewers.append({
                "process": p,
                "computer_name": computer_name,
                "zalo_phone": zalo_phone,
                "partner_id": partner_id
            })
            
            # Close the socket handle in the parent process ONLY AFTER the viewer process exits.
            # This ensures the child process has full ownership of the socket without the parent dropping it prematurely,
            # while still preventing port leakage when the session ends.
            def wait_and_close():
                try:
                    p.join()
                except:
                    pass
                try:
                    sock.close()
                except:
                    pass
            import threading
            threading.Thread(target=wait_and_close, daemon=True).start()
            
            # Reconnection Monitor Thread
            if partner_id and partner_pass:
                def monitor_reconnect(process, pid, ppass, req_queue):
                    while process.is_alive():
                        try:
                            msg = req_queue.get(timeout=1.0)
                            if msg == "RECONNECT_REQUEST":
                                print(f"[Client Monitor] Pygame requested reconnect for {pid}...")
                                self.after(0, lambda: self.update_status(_("Đang tự động kết nối lại...")))
                                threading.Thread(target=self.connect_to_partner, args=(pid, ppass, req_queue, 0, process.pid), daemon=True).start()
                            else:
                                req_queue.put(msg)
                                time.sleep(0.5)
                        except:
                            pass
                    
                    code = process.exitcode
                    print(f"[Client Monitor] Pygame viewer process exited with code: {code}")
                    
                threading.Thread(target=monitor_reconnect, args=(p, partner_id, partner_pass, reconnect_queue), daemon=True).start()
            
            self.connect_btn.config(state=tk.NORMAL)
            self.update_status(_("Đã mở một cửa sổ điều khiển mới (Sẵn sàng kết nối)"))
            print(f"[Client] Đã mở tiến trình điều khiển cho {computer_name or 'đối tác'}")
            
        except Exception as e:
            print(f"[Client] Lỗi khởi chạy tiến trình điều khiển: {e}")
            self.connect_btn.config(state=tk.NORMAL)
            try: force_close_socket(sock)
            except: pass
            
