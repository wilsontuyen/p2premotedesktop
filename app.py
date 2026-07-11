from core.config import *
import socket
import threading
import json
import struct
import time
import mss
# pyrefly: ignore [missing-import]
from PIL import Image, ImageDraw, ImageTk
# pyrefly: ignore [missing-import]
import pystray
# pyrefly: ignore [missing-import]
from pystray import MenuItem as item
import random
import subprocess
import base64
import ctypes
from ctypes import wintypes
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
import urllib.request
import urllib.parse
import tkinter as tk
from tkinter import messagebox, ttk
import sys

from core.clipboard_agent import ClipboardSyncManager, clipboard_sync_manager, run_clipboard_agent_mode
from core.host import encrypt_text, decrypt_text
from core.viewer import run_client_viewer_loop

# Monkey-patch tk.Toplevel.geometry de tu dong ty le kich thuoc theo DPI Scale
_orig_toplevel_geometry = tk.Toplevel.geometry
def _scaled_toplevel_geometry(self, newGeometry=None):
    if newGeometry is None:
        return _orig_toplevel_geometry(self)
    try:
        import re
        m = re.match(r'^(\d+)x(\d+)(?:\+([+-]?\d+)\+([+-]?\d+))?$', newGeometry)
        if m:
            w = int(m.group(1))
            h = int(m.group(2))
            x = m.group(3)
            y = m.group(4)
            scale = self.winfo_fpixels('1i') / 96.0
            sw = int(w * scale)
            sh = int(h * scale)
            if x is not None and y is not None:
                adj_x = int(x) - (sw - w) // 2
                adj_y = int(y) - (sh - h) // 2
                newGeometry = f"{sw}x{sh}+{adj_x}+{adj_y}"
            else:
                newGeometry = f"{sw}x{sh}"
    except Exception as e:
        pass
    return _orig_toplevel_geometry(self, newGeometry)

tk.Toplevel.geometry = _scaled_toplevel_geometry
import pygame
import sys
import os
import traceback

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    except: pass
if sys.stderr is not None and hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    except: pass

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    with open("crash.log", "w", encoding="utf-8") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)

sys.excepthook = handle_exception

import builtins
_orig_print = builtins.print
def print_with_timestamp(*args, **kwargs):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    if args:
        first_arg = str(args[0])
        if first_arg.startswith("[202") and first_arg.find("]") < 25:
            _orig_print(*args, **kwargs)
            return
    msg = " ".join(str(arg) for arg in args)
    _orig_print(f"{timestamp} {msg}", **kwargs)

print = print_with_timestamp

# Chuyển thư mục làm việc về thư mục chứa file thực thi (.exe hoặc .py) để tránh lỗi đọc/ghi file cấu hình khi khởi động cùng Windows
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(app_dir)

is_compiled = getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__')

# Hỗ trợ DPI High-Scaling trên Windows 10/11 để tránh chữ mờ và co giãn sai tỉ lệ cửa sổ
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass

from utils.logger import get_log_filepath, log_file_transfer, log_debug, log_activity

# Pygame CE drop-in compatibility
# In pygame-ce, it is still imported as pygame.

# Remote Desktop Ports (Avoid 80/443 to prevent Router Web UI collision)

# LAN Discovery (UDP Broadcast) - Cho phép các máy trong cùng mạng LAN tự phát hiện nhau
LAN_BEACON_INTERVAL = 5  # Gửi beacon mỗi 5 giây
LAN_OFFLINE_TIMEOUT = 15  # Coi là offline nếu không nhận beacon trong 15 giây

# Host Controllers

# Button mapping for mouse clicks


from utils.input_simulator import send_input_keyboard_event, send_input_mouse_click, send_input_mouse_scroll, send_input_mouse_move

from network.crypto import get_crypto_key, encrypt_payload, decrypt_payload
from network.socket_utils import socket_passwords, APP_KEY, force_close_socket, send_msg, recv_msg, recv_exact

from gui.themes import get_theme_palette
from utils.hwid import get_hwid, get_local_ip, get_public_ip, get_public_ipv6

from network.upnp import attempt_upnp_forward            
# Get Public IPv6 address

# Get Public IP address


from utils.clipboard_api import (ENABLE_CLIPBOARD_SYNC, set_clipboard_dword_format, setup_clipboard_exclusions, 
                                get_clipboard_files, set_clipboard_files, get_clipboard_text, set_clipboard_text)

from gui.components import PremiumProgressBar, get_file_icon_as_image, ClassicCopyDialog, ProgressDialog, ConfirmDialog, ToolTip
from core.clipboard_agent import ClipboardSyncManager, clipboard_sync_manager, run_clipboard_agent_mode, run_clipboard_agent_mode

from core.host import HostMixin, check_desktop_change
from core.network_manager import NetworkMixin

class UnifiedApp(tk.Tk, HostMixin, NetworkMixin):
    def __init__(self):
        super().__init__()
        import threading
        
        # Đảm bảo reset trạng thái BlockInput và màn hình che phủ khi app mới khởi động
        try:
            import ctypes
            ctypes.windll.user32.BlockInput(False)
            print("[App] Reset BlockInput to False on startup.")
        except:
            pass
        
        # Check headless flag (run in Session 0 / background service mode)
        self.is_headless = "--headless" in sys.argv
        if self.is_headless:
            self.withdraw()
            try:
                log_path = os.path.join(app_dir, "agent.log")
                sys.stdout = open(log_path, "a", encoding="utf-8", buffering=1)
                sys.stderr = sys.stdout
                print(f"\n--- Agent started in headless mode at {time.strftime('%Y-%m-%d %H:%M:%S')} (PID: {os.getpid()}) ---")
            except Exception as e:
                pass
        
        # Thiết lập icon cho cửa sổ chính
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(True, icon_img)
                self._app_icon_img = icon_img  # Giữ reference tránh GC
        except Exception as e:
            print(f"[App] Lỗi thiết lập icon cửa sổ: {e}")
        
        # Register app instance to ClipboardSyncManager
        if clipboard_sync_manager:
            clipboard_sync_manager.register_app(self)
        
        # Window attributes
        self.title("Easy Remote Desktop")
        self.resizable(False, False)
        
        # Shutdown listener for closing client cleanly
        if sys.platform == "win32":
            try:
                import win32gui, win32con, win32api
                def WndProc(hwnd, msg, wparam, lparam):
                    if msg == win32con.WM_QUERYENDSESSION:
                        if not (lparam & 0x80000000): # 0x80000000 is ENDSESSION_LOGOFF
                            print("[Host] System Shutdown/Restart detected!")
                            for conn in list(socket_passwords.keys()):
                                try:
                                    import json
                                    send_msg(conn, json.dumps({"type": "host_shutdown"}).encode('utf-8'), socket_passwords[conn])
                                except: pass
                        return True
                    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
                
                wc = win32gui.WNDCLASS()
                wc.lpfnWndProc = WndProc
                wc.lpszClassName = "AntigravityShutdownListener"
                wc.hInstance = win32api.GetModuleHandle(None)
                try: win32gui.RegisterClass(wc)
                except: pass
                self.shutdown_hwnd = win32gui.CreateWindow(wc.lpszClassName, "ShutdownListener", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)
            except Exception as e:
                print(f"[Host] Failed to setup shutdown listener: {e}")
        
        # Cờ trạng thái chống mở nhiều cửa sổ điều khiển cùng lúc
        self.is_client_connected = False
        
        # Load saved window position or center it
        self.config_file = "window_config.json"
        self.last_normal_geometry = None
        self.bind("<Configure>", self.on_window_configure)
        self.load_window_position()
        
        # Migrate old JSON list to new encrypted XML format
        old_json_file = "saved_computers.json"
        new_xml_file = "saved_computers.xml"
        if os.path.exists(old_json_file) and not os.path.exists(new_xml_file):
            try:
                with open(old_json_file, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                
                import xml.etree.ElementTree as ET
                root = ET.Element("computers")
                for comp in old_data:
                    comp_node = ET.SubElement(root, "computer")
                    
                    name_node = ET.SubElement(comp_node, "name")
                    name_node.text = encrypt_text(comp.get("name", ""))
                    
                    id_node = ET.SubElement(comp_node, "id")
                    id_node.text = encrypt_text(comp.get("id", ""))
                    
                    pass_node = ET.SubElement(comp_node, "password")
                    pass_node.text = encrypt_text(comp.get("password", ""))
                
                tree = ET.ElementTree(root)
                tree.write(new_xml_file, encoding="utf-8", xml_declaration=True)
                os.remove(old_json_file)
                print("[Migration] Đã chuyển đổi thành công danh sách máy tính sang XML mã hóa!")
            except Exception as e:
                print(f"[Migration] Lỗi chuyển đổi: {e}")
        
        # Color Theme Setup
        from gui.themes import setup_app_theme
        setup_app_theme(self, self.config_file)
        # Host State Variables
        self.my_id_clean, self.my_id_formatted, self.my_macs = get_hwid()
        
        # Check if service (headless agent) is active by checking the mutex
        self.is_service_active = False
        if sys.platform == "win32" and not self.is_headless:
            import win32event, win32con
            
            # Check Windows Service status first to avoid race condition on startup
            # Check Windows Service status first to avoid race condition on startup
            # Since the service is actually a Scheduled Task (EasyRemoteDesktopAgent),
            # we check if we are running from the installation directory and wait for the headless agent.
            is_installed_version = False
            try:
                exe_path = sys.argv[0] if (sys.argv and sys.argv[0]) else sys.executable
                if "C:\\Apps\\P2P" in os.path.abspath(exe_path):
                    is_installed_version = True
            except:
                pass

            session_id = 1
            try:
                sid = ctypes.c_ulong()
                if ctypes.windll.kernel32.ProcessIdToSessionId(ctypes.windll.kernel32.GetCurrentProcessId(), ctypes.byref(sid)):
                    session_id = sid.value
            except:
                pass

            if is_installed_version:
                for _ in range(10): # Wait up to 5 seconds for the service to spawn headless agent
                    for d_name in ["default", "winlogon"]:
                        m_name = f"Global\\AntigravityP2PRemoteDesktopAppMutex_1_{session_id}_{d_name}"
                        try:
                            h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, m_name)
                            if h_mutex:
                                win32api.CloseHandle(h_mutex)
                                self.is_service_active = True
                                break
                        except Exception:
                            pass
                    if self.is_service_active:
                        break
                    time.sleep(0.5)

            # Fallback to checking Mutex if not installed version or still not found
            if not self.is_service_active:
                for d_name in ["default", "winlogon"]:
                    m_name = f"Global\\AntigravityP2PRemoteDesktopAppMutex_1_{session_id}_{d_name}"
                    try:
                        h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, m_name)
                        if h_mutex:
                            win32api.CloseHandle(h_mutex)
                            self.is_service_active = True
                            break
                    except Exception:
                        pass

        # Load or generate password
        if self.is_headless:
            self.my_password = str(random.randint(1000, 9999))
            try:
                pass_path = os.path.join(app_dir, "session_pass.txt")
                with open(pass_path, "w", encoding="utf-8") as f:
                    f.write(self.my_password)
                print(f"[Host Service] Generated and saved session password to {pass_path}")
            except Exception as e:
                print(f"[Host Service] Failed to save session password: {e}")
        else:
            if getattr(self, "is_service_active", False):
                global BOUND_PORT
                BOUND_PORT = 12346 # Prevent using port 12345 to avoid conflicting with the service
                pass_path = os.path.join(app_dir, "session_pass.txt")
                if os.path.exists(pass_path):
                    try:
                        with open(pass_path, "r", encoding="utf-8") as f:
                            self.my_password = f.read().strip()
                        print(f"[Host GUI] Loaded shared session password from {pass_path}: {self.my_password}")
                    except Exception as e:
                        print(f"[Host GUI] Failed to load shared session password: {e}")
                        self.my_password = str(random.randint(1000, 9999))
                else:
                    self.my_password = str(random.randint(1000, 9999))
            else:
                self.my_password = str(random.randint(1000, 9999))
        # Migrate old fixed_password.txt to XML if it exists
        self.fixed_password = ""
        if os.path.exists("fixed_password.txt"):
            try:
                with open("fixed_password.txt", "r", encoding="utf-8") as f:
                    encrypted = f.read().strip()
                    if encrypted:
                        self.fixed_password = decrypt_text(encrypted)
                if self.fixed_password:
                    self.save_fixed_password_to_xml(self.fixed_password)
                os.remove("fixed_password.txt")
                print("[Migration] Đã di trú mật khẩu cố định sang saved_computers.xml và xóa tệp cũ!")
            except Exception as e:
                print(f"[Config] Lỗi di trú mật khẩu cố định: {e}")
        else:
            self.fixed_password = self.load_fixed_password_from_xml()
        self.pass_type_var = tk.StringVar(value="4 chữ số")
        self.server_socket = None
        self.running_server = True
        self.active_clients = {}
        self.active_viewers = []
        self.current_ip = "Đang lấy IP..."
        self.local_ip = "127.0.0.1"
        self.ipv6 = None
        self.client_viewer_w = 1280
        self.client_viewer_h = 720
        
        # Signaling State
        self.signaling_socket = None
        self.signaling_lock = threading.Lock()
        self._reconnecting_signaling = False
        self.pending_connection_info = None
        self.status_dots_widgets = {}
        self.tray_icon = None
        self.last_signaling_response = time.time()
        self.received_first_pong = False
        
        # Form variables
        self.status_var = tk.StringVar(value="Đang kết nối tới mạng đăng ký...")
        self.partner_id_var = tk.StringVar()
        self.partner_pass_var = tk.StringVar()
        self.force_relay_var = tk.BooleanVar(value=False)
        self.startup_var = tk.BooleanVar(value=self.is_startup_enabled())
        
        # LAN Discovery State - Lưu trữ các máy phát hiện được trong mạng LAN
        # Key: hwid, Value: {computer_name, local_ip, port, last_seen, macs}
        self.lan_peers = self.load_lan_peers()
        self.lan_peers_lock = threading.Lock()
        
        # Register Trace for Auto-Formatting Partner ID
        self.id_trace_id = self.partner_id_var.trace_add("write", self.format_partner_id)
        
        # Intercept close window button ("X")
        self.protocol("WM_DELETE_WINDOW", self.on_close_window)
        
        # Setup UI
        self.setup_ui()
        
        # Start background services
        threading.Thread(target=self.init_network_services, daemon=True).start()
        
        # Bắt đầu polling Signaling status trên main thread (độ tin cậy cao hơn self.after từ background thread)
        self.after(3000, self._poll_signaling_status)
        
        # Restore Event Listener for waking the GUI
        if not self.is_headless:
            threading.Thread(target=self.restore_event_listener_thread, daemon=True).start()
            threading.Thread(target=self.screen_cover_event_listener_thread, daemon=True).start()
    def screen_cover_event_listener_thread(self):
        if sys.platform != "win32":
            return
        import win32event, win32security, ctypes
        
        try:
            active_session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
        except:
            active_session_id = 1
            
        cover_event_name = f"Global\\AntigravityP2PRemoteDesktopScreenCoverEvent_{active_session_id}_default"
        
        sa = win32security.SECURITY_ATTRIBUTES()
        sa.bInheritHandle = 1
        sd = win32security.SECURITY_DESCRIPTOR()
        sd.Initialize()
        sd.SetSecurityDescriptorDacl(True, None, False)
        sa.SECURITY_DESCRIPTOR = sd
        
        try:
            h_event_toggle = win32event.CreateEvent(sa, False, False, cover_event_name)
            h_event_disable = win32event.CreateEvent(sa, False, False, cover_event_name + "_disable")
        except Exception as e:
            print(f"[Event] Failed to create screen cover event: {e}")
            return
            
        print(f"[Event] Listening for screen cover event: {cover_event_name}")
        while True:
            res = win32event.WaitForMultipleObjects([h_event_toggle, h_event_disable], False, win32event.INFINITE)
            if res == win32event.WAIT_OBJECT_0:
                print("[Event] Received screen cover toggle signal.")
                self.after(0, self.toggle_screen_cover_gui)
            elif res == win32event.WAIT_OBJECT_0 + 1:
                print("[Event] Received screen cover disable signal.")
                self.after(0, self.disable_screen_cover_gui)

    def restore_event_listener_thread(self):
        if sys.platform != "win32":
            return
        import win32event, win32security
        session_id = get_session_id()
        desktop_name = get_desktop_name()
        restore_event_name = f"Global\\AntigravityP2PRemoteDesktopRestoreEvent_{session_id}_{desktop_name}"
        
        sa = win32security.SECURITY_ATTRIBUTES()
        sa.bInheritHandle = 1
        sd = win32security.SECURITY_DESCRIPTOR()
        sd.Initialize()
        sd.SetSecurityDescriptorDacl(True, None, False)
        sa.SECURITY_DESCRIPTOR = sd
        
        try:
            h_event = win32event.CreateEvent(sa, False, False, restore_event_name)
        except Exception as e:
            print(f"[Event] Failed to create restore event: {e}")
            return
            
        print(f"[Event] Listening for restore event: {restore_event_name}")
        while True:
            rc = win32event.WaitForSingleObject(h_event, win32event.INFINITE)
            if rc == win32event.WAIT_OBJECT_0:
                print("[Event] Received restore signal. Restoring window.")
                self.after(0, self._restore_window)
        
    def setup_ui(self):
        # Setup Window Menu Bar
        menubar = tk.Menu(self)
        
        # 1. File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Danh sách (Saved Computers)", command=self.show_saved_computers_dialog)
        file_menu.add_command(label="📡 Quét mạng LAN (LAN Discovery)", command=self.show_lan_computers_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Thoát (Exit)", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # 2. Options Menu
        options_menu = tk.Menu(menubar, tearoff=0)

        # Submenu: Password type
        password_menu = tk.Menu(options_menu, tearoff=0)
        password_menu.add_radiobutton(
            label="4 chữ số",
            variable=self.pass_type_var, value="4 chữ số",
            command=self.refresh_password
        )
        password_menu.add_radiobutton(
            label="5 chữ số",
            variable=self.pass_type_var, value="5 chữ số",
            command=self.refresh_password
        )
        password_menu.add_radiobutton(
            label="8 ký tự (chữ + số)",
            variable=self.pass_type_var, value="8 ký tự (chữ + số)",
            command=self.refresh_password
        )
        password_menu.add_separator()
        password_menu.add_command(
            label="Cài mật khẩu cố định...",
            command=self.open_set_fixed_password_dialog
        )
        options_menu.add_cascade(label="Mật khẩu (Password)", menu=password_menu)
        options_menu.add_separator()
        options_menu.add_checkbutton(
            label="Chạy khi mở máy (Run on Startup)",
            variable=self.startup_var,
            command=self.toggle_startup
        )
        options_menu.add_command(
            label="Cài Zalo / Điện thoại",
            command=self.open_set_zalo_phone_dialog
        )
        options_menu.add_separator()
        options_menu.add_command(
            label="Cài đặt máy chủ...",
            command=self.show_server_settings_dialog
        )
        options_menu.add_separator()
        
        # Submenu: Theme
        theme_menu = tk.Menu(options_menu, tearoff=0)
        theme_menu.add_radiobutton(label="Sáng", variable=self.current_theme, value="light", command=self.change_theme)
        theme_menu.add_radiobutton(label="Tối", variable=self.current_theme, value="dark", command=self.change_theme)
        theme_menu.add_radiobutton(label="Xám", variable=self.current_theme, value="gray", command=self.change_theme)
        theme_menu.add_radiobutton(label="Hồng", variable=self.current_theme, value="pink", command=self.change_theme)
        theme_menu.add_radiobutton(label="Pha lê", variable=self.current_theme, value="crystal", command=self.change_theme)
        theme_menu.add_radiobutton(label="Cam", variable=self.current_theme, value="orange", command=self.change_theme)
        theme_menu.add_radiobutton(label="Đỏ", variable=self.current_theme, value="red", command=self.change_theme)
        theme_menu.add_separator()
        theme_menu.add_radiobutton(label="Tùy chỉnh", variable=self.current_theme, value="custom", command=self.change_theme)
        options_menu.add_cascade(label="Giao diện", menu=theme_menu)
 
        menubar.add_cascade(label="Options", menu=options_menu)
        
        # 3. Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Zalo", command=self.open_zalo)
        help_menu.add_command(label="Điện thoại", command=self.open_phone_dialog)
        help_menu.add_command(label="About", command=self.show_about_dialog)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        # Apply menubar to window
        self.config(menu=menubar)

        # Header Label
        header = tk.Label(self, text="P2P REMOTE DESKTOP", font=("Segoe UI", 16, "bold"), fg=self.btn_color, bg=self.bg_color)
        header.pack(pady=(15, 5))
        
        # Sub-header
        subheader = tk.Label(self, text="Điều khiển trực tuyến máy tính bằng HWID", font=("Segoe UI", 9, "italic"), fg=self.text_gray, bg=self.bg_color)
        subheader.pack(pady=(0, 15))
        
        # Main Panels Container
        container = tk.Frame(self, bg=self.bg_color)
        self._main_container = container
        container.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # LEFT PANEL: Allow Remote Control
        left_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        self._left_panel = left_panel
        left_panel.place(relx=0.0, rely=0.0, relwidth=0.47, relheight=0.92)
        
        lbl_allow = tk.Label(left_panel, text="CHO PHÉP ĐIỀU KHIỂN", font=("Segoe UI", 11, "bold"), fg=self.btn_color, bg=self.card_color)
        lbl_allow.pack(pady=(15, 10))
        
        lbl_id = tk.Label(left_panel, text="Mã ID của bạn:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.card_color)
        lbl_id.pack(anchor=tk.W, padx=20)
        
        id_frame = tk.Frame(left_panel, bg=self.card_color)
        self._id_frame = id_frame
        id_frame.pack(fill=tk.X, padx=20, pady=(5, 12))
        
        self.my_id_label = tk.Label(id_frame, text=self.my_id_formatted, font=("Segoe UI", 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0, height=1)
        self.my_id_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_id_btn = tk.Button(id_frame, text="📋", font=("Segoe UI", 10), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=lambda: self.copy_to_clipboard(self.my_id_formatted))
        copy_id_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(copy_id_btn, "Sao chép")
        
        lbl_pass = tk.Label(left_panel, text="Mật khẩu kết nối:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.card_color)
        lbl_pass.pack(anchor=tk.W, padx=20)
        
        pass_frame = tk.Frame(left_panel, bg=self.card_color)
        self._pass_frame = pass_frame
        pass_frame.pack(fill=tk.X, padx=20, pady=(5, 5))
        
        self.my_pass_label = tk.Label(pass_frame, text=self.my_password, font=("Segoe UI", 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0)
        self.my_pass_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_pass_btn = tk.Button(pass_frame, text="📋", font=("Segoe UI", 10), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=lambda: self.copy_to_clipboard(self.my_password))
        copy_pass_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(copy_pass_btn, "Sao chép")
        
        refresh_btn = tk.Button(pass_frame, text="↻", font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=self.refresh_password)
        refresh_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(refresh_btn, "Đổi mật khẩu")

        # Nhãn hiển thị trạng thái mật khẩu cố định
        self.fixed_pass_indicator = tk.Label(left_panel, text="", font=("Segoe UI", 8, "italic"), fg="#2ECC71", bg=self.card_color)
        self.fixed_pass_indicator.pack(anchor=tk.W, padx=20, pady=(2, 0))
        self.update_fixed_password_indicator()

        # Button to Copy both ID & Password at once
        copy_all_btn = tk.Button(left_panel, text="📋 Sao chép cả ID & Mật khẩu", font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, command=self.copy_id_and_password)
        copy_all_btn.pack(pady=(8, 0), padx=20, fill=tk.X)
        
        # Nút gọi Danh sách máy tính đã lưu
        saved_list_btn = tk.Button(left_panel, text="📁 Danh sách máy tính đã lưu", font=("Segoe UI", 9), fg="#FFFFFF", bg="#5B2C8E", activebackground="#7B3FA8", relief=tk.FLAT, bd=0, pady=3, cursor="hand2", command=self.show_saved_computers_dialog)
        saved_list_btn.pack(side=tk.BOTTOM, padx=20, fill=tk.X, pady=(0, 20))
        
        # RIGHT PANEL: Control Remote Computer
        right_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        self._right_panel = right_panel
        right_panel.place(relx=0.53, rely=0.0, relwidth=0.47, relheight=0.92)
        
        lbl_control = tk.Label(right_panel, text="ĐIỀU KHIỂN ĐỐI TÁC", font=("Segoe UI", 11, "bold"), fg=self.btn_color, bg=self.card_color)
        lbl_control.pack(pady=(15, 10))
        
        lbl_p_id = tk.Label(right_panel, text="Nhập ID đối tác:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.card_color)
        lbl_p_id.pack(anchor=tk.W, padx=20)
        
        self.entry_p_id = tk.Entry(right_panel, textvariable=self.partner_id_var, font=("Segoe UI", 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, relief=tk.FLAT, bd=4)
        self.entry_p_id.pack(pady=(5, 10), padx=20, fill=tk.X)
        
        lbl_p_pass = tk.Label(right_panel, text="Nhập Mật khẩu đối tác:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.card_color)
        lbl_p_pass.pack(anchor=tk.W, padx=20)
        
        self.entry_p_pass = tk.Entry(right_panel, textvariable=self.partner_pass_var, font=("Segoe UI", 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, show="*", relief=tk.FLAT, bd=4)
        self.entry_p_pass.pack(pady=(5, 20), padx=20, fill=tk.X)
        
        # Bind Enter keys to trigger Connection immediately
        self.entry_p_id.bind("<Return>", lambda event: self.click_connect())
        self.entry_p_id.bind("<KP_Enter>", lambda event: self.click_connect())
        self.entry_p_pass.bind("<Return>", lambda event: self.click_connect())
        self.entry_p_pass.bind("<KP_Enter>", lambda event: self.click_connect())
        
        # Container to hold CONNECT & ADD (+) buttons
        btn_container = tk.Frame(right_panel, bg=self.card_color)
        btn_container.pack(padx=20, fill=tk.X)
        
        self.connect_btn = tk.Button(btn_container, text="KẾT NỐI (CONNECT)", font=("Segoe UI", 11, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, command=self.click_connect)
        self.connect_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Add button with a blue "+"
        self.add_partner_btn = tk.Button(btn_container, text="➕", font=("Segoe UI", 12, "bold"), fg=self.text_white, bg="#007ACC", activebackground="#005A9E", relief=tk.FLAT, bd=0, width=4, cursor="hand2", command=self.add_current_partner_to_saved)
        self.add_partner_btn.pack(side=tk.RIGHT, padx=(8, 0))
        ToolTip(self.add_partner_btn, "Thêm máy tính")

        # LAN Discovery button - Quét máy trong mạng nội bộ
        lan_btn = tk.Button(right_panel, text="📡 Quét mạng LAN (LAN Only)", font=("Segoe UI", 9), fg="#FFFFFF", bg="#5B2C8E", activebackground="#7B3FA8", relief=tk.FLAT, bd=0, pady=3, cursor="hand2", command=self.show_lan_computers_dialog)
        lan_btn.pack(side=tk.BOTTOM, padx=20, fill=tk.X, pady=(0, 20))

        # Attach Context Menus for Copy & Paste
        self.make_context_menu(self.entry_p_id)
        self.make_context_menu(self.entry_p_pass)
        
        # BOTTOM STATUS BAR
        status_bar = tk.Frame(self, bg=self.entry_bg, height=25)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl_status = tk.Label(status_bar, textvariable=self.status_var, font=("Segoe UI", 8, "italic"), fg="#8A8A9A", bg=self.entry_bg, anchor=tk.W)
        self.lbl_status.pack(fill=tk.BOTH, padx=10, pady=2)
        
        # Khởi chạy icon khay hệ thống ngay khi bật ứng dụng
        if not self.is_headless:
            self.setup_tray_icon()
        
    # Auto formatting spaces inside ID: "123 456 789 012"
    def format_partner_id(self, *args):
        # Defer formatting to after the current key event is fully processed
        # This prevents cursor position conflicts when typing rapidly
        if hasattr(self, '_format_after_id') and self._format_after_id:
            try:
                self.after_cancel(self._format_after_id)
            except Exception:
                pass
        self._format_after_id = self.after_idle(self._do_format_partner_id)

    def _do_format_partner_id(self):
        self._format_after_id = None
        
        # Save cursor position (now stable since key event is fully processed)
        try:
            cursor_pos = self.entry_p_id.index(tk.INSERT)
        except Exception:
            cursor_pos = None
        
        current_val = self.partner_id_var.get()
        raw_val = current_val.replace(" ", "")
        clean_val = "".join([c for c in raw_val if c.isdigit()])[:12]
        
        formatted = ""
        if len(clean_val) > 9:
            formatted = f"{clean_val[:3]} {clean_val[3:6]} {clean_val[6:9]} {clean_val[9:]}"
        elif len(clean_val) > 6:
            formatted = f"{clean_val[:3]} {clean_val[3:6]} {clean_val[6:]}"
        elif len(clean_val) > 3:
            formatted = f"{clean_val[:3]} {clean_val[3:]}"
        else:
            formatted = clean_val
        
        # Only update if the value actually changed
        if current_val == formatted:
            return
        
        # Count digits before cursor in the current (unformatted) string
        new_cursor = None
        if cursor_pos is not None:
            digits_before = sum(1 for c in current_val[:cursor_pos] if c.isdigit())
            # Find position in formatted string after the same number of digits
            count = 0
            new_cursor = len(formatted)
            for i, ch in enumerate(formatted):
                if ch.isdigit():
                    count += 1
                    if count == digits_before:
                        new_cursor = i + 1
                        break
        
        self.partner_id_var.trace_remove("write", self.id_trace_id)
        self.partner_id_var.set(formatted)
        self.id_trace_id = self.partner_id_var.trace_add("write", self.format_partner_id)
        
        # Restore cursor position
        if new_cursor is not None:
            try:
                self.entry_p_id.icursor(new_cursor)
            except Exception:
                pass
        
    def on_window_configure(self, event):
        try:
            # Chỉ ghi lại tọa độ khi cửa sổ ở trạng thái hiển thị bình thường và đang được vẽ
            if self.wm_state() == "normal" and self.winfo_ismapped():
                geom = self.geometry()
                # Kiểm tra tọa độ có hợp lệ không (tránh lưu tọa độ ảo khi Windows thu nhỏ)
                if "+" in geom:
                    parts = geom.split("+")
                    if len(parts) >= 3:
                        x = int(parts[1])
                        y = int(parts[2])
                        # Tránh lưu tọa độ ảo âm quá lớn
                        if x > -1000 and y > -1000:
                            self.last_normal_geometry = geom
        except Exception:
            pass

    def load_window_position(self):
        # Force Tkinter to calculate proper font/widget scales based on physical DPI
        try:
            dpi = self.winfo_fpixels('1i')
            # The default scaling is usually dpi/72.0 for points, but Tkinter on Windows defaults to 96
            self.tk.call('tk', 'scaling', dpi / 72.0)
        except Exception:
            pass

        scale = self.winfo_fpixels('1i') / 96.0
        min_w = int(680 * scale)
        min_h = int(430 * scale) # Tăng chiều cao để hiển thị đủ nút bấm
        default_geometry = f"{min_w}x{min_h}"
        self.minsize(min_w, min_h)
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    config = json.load(f)
                    geom = config.get("geometry")
                    if geom:
                        # Bảo đảm kích thước luôn chính xác theo scale màn hình
                        if "x" in geom:
                            parts = geom.split("+")[0].split("x")
                            if len(parts) == 2:
                                gw = min_w
                                gh = min_h
                                pos = "+".join(geom.split("+")[1:])
                                geom = f"{gw}x{gh}"
                                if pos:
                                    geom += f"+{pos}"
                        self.geometry(geom)
                        self.last_normal_geometry = geom
                        return
            except Exception as e:
                print(f"[Config] Error loading window config: {e}")
                
        # Center the window if no config or config is invalid
        self.geometry(default_geometry)
        self.update_idletasks()
        w = min_w
        h = min_h
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        geom = f"{w}x{h}+{x}+{y}"
        self.geometry(geom)
        self.last_normal_geometry = geom

    def change_theme(self):
        from gui.themes import change_app_theme
        change_app_theme(self)
