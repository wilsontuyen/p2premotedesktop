import sys
APP_FONT_NAME = "Segoe UI" if sys.platform == "win32" else "TkDefaultFont"

import traceback
import os
try:
    import tempfile
    crash_log_path = os.path.join(tempfile.gettempdir(), "early_crash.log")
    _f = open(crash_log_path, "w", encoding="utf-8", buffering=1)
    sys.stderr = _f
    sys.stdout = _f
    print("Bắt đầu khởi chạy ứng dụng...")
except:
    pass

from core.config import *

import platform

_is_old_win = platform.release() in ["7", "8", "8.1"]
EMOJI_FONT = (APP_FONT_NAME, 9)
EMOJI_FONT_BOLD = (APP_FONT_NAME, 9, "bold")
EMOJI_FONT_LARGE = (APP_FONT_NAME, 12, "bold")
EMOJI_FONT_10 = (APP_FONT_NAME, 10)
EMOJI_FONT_8_BOLD = (APP_FONT_NAME, 8, "bold")


def E(text):
    import sys
    if sys.platform == "darwin":
        return text
    if sys.platform != "win32" or platform.release() in ["7", "8", "8.1"]:
        mapping = {
            "📋": "❐", "📁": "≡", "📡": "⌂", "🔧": "¤",
            "🔄": "↻", "🔍": "⌕", "➕": "+", "❌": "X"
        }
        for k, v in mapping.items():
            text = text.replace(k, v)
    return text

from core.i18n import _, load_language, get_available_languages, export_template, get_language_name

import socket
import threading
import json
import struct
import time
import mss
# pyrefly: ignore [missing-import]
from PIL import Image, ImageDraw, ImageTk
try:
    if sys.platform == "darwin":
        raise Exception("Disabled on macOS to prevent Tkinter runloop crash")
    # pyrefly: ignore [missing-import]
    import pystray
    # pyrefly: ignore [missing-import]
    from pystray import MenuItem as item
except Exception as e:
    print(f"Warning: pystray could not be loaded: {e}")
    pystray = None
    item = None

import random
import subprocess
import base64
import ctypes
if sys.platform == "win32":
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

# macOS Tkinter compatibility for Sequoia (macOS 15).
# Frame backgrounds are ignored on some Sequoia builds, rendering as light gray.
# The app's white text becomes invisible on the light gray frames.
# Solution: Use ttk widgets and force black text via a shared style.

_orig_tk_label = tk.Label
def _mac_tk_label(master=None, cnf={}, **kw):
    kw.pop('bg', None)
    kw.pop('background', None)
    return _orig_tk_label(master, cnf, **kw)

_orig_tk_entry = tk.Entry
def _mac_tk_entry(master=None, cnf={}, **kw):
    kw.pop('bg', None)
    kw.pop('background', None)
    kw['relief'] = tk.SUNKEN
    kw['bd'] = 2
    return _orig_tk_entry(master, cnf, **kw)

if sys.platform == "darwin":
    tk.Label = _mac_tk_label
    tk.Entry = _mac_tk_entry


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
    # In ra stderr (để hiển thị trên terminal hoặc gui.log)
    sys.__excepthook__(exc_type, exc_value, exc_traceback)
    # Ghi vào file
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
if sys.platform != "win32":
    try:
        import os
        os.umask(0) # Đảm bảo file cấu hình tạo bởi root (systemd) có quyền rw-rw-rw-
    except:
        pass
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(app_dir)

def get_app_data_dir():
    import os, sys
    if sys.platform != "win32":
        if os.path.exists("/opt/p2p_remote"):
            path = "/opt/p2p_remote/config"
        else:
            path = os.path.expanduser("~/.config/RemoteDesktopP2P")
        try:
            os.makedirs(path, exist_ok=True)
            # Đảm bảo quyền ghi cho mọi user (vì root tạo ra thì user không sửa được)
            os.chmod(path, 0o777)
        except Exception:
            pass
        return path
    else:
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))

def get_computers_xml_path():
    import os, sys, shutil
    
    user_path = os.path.join(get_app_data_dir(), "saved_computers.xml")
    if os.path.exists(user_path):
        return user_path
        
    if sys.platform == "win32":
        installed_path = r"C:\Apps\P2P\saved_computers.xml"
    else:
        installed_path = "/opt/p2p_remote/config/saved_computers.xml"
        
    if os.path.exists(installed_path):
        try:
            with open(installed_path, 'a'):
                pass
            return installed_path
        except Exception:
            try:
                shutil.copy2(installed_path, user_path)
            except Exception:
                pass
            return user_path
            
    return user_path

is_compiled = getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__')

# Hỗ trợ DPI High-Scaling trên Windows 10/11 để tránh chữ mờ và co giãn sai tỉ lệ cửa sổ
if sys.platform == "win32":
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
            
        # Configure logging and stdout redirection for diagnostics
        try:
            log_filename = "agent.log" if self.is_headless else "gui.log"
            log_path = os.path.join(app_dir, log_filename)
            sys.stdout = open(log_path, "a", encoding="utf-8", buffering=1)
            sys.stderr = sys.stdout
            
            # Override built-in print to flush immediately so logs are unbuffered
            import builtins
            orig_print = builtins.print
            def unbuffered_print(*args, **kwargs):
                orig_print(*args, **kwargs)
                try:
                    sys.stdout.flush()
                except:
                    pass
            builtins.print = unbuffered_print
            
            print(f"\n--- App started in {'headless' if self.is_headless else 'GUI'} mode at {time.strftime('%Y-%m-%d %H:%M:%S')} (PID: {os.getpid()}) ---")
            
            # Run diagnostics check for both GUI and Headless clients
            try:
                import getpass
                username = getpass.getuser()
                print(f"[Diagnostics] Process running under user: {username}")
                
                if sys.platform == "win32":
                    import win32con
                    import win32api, win32security, winreg
                    
                    h_token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
                    sid_info = win32security.GetTokenInformation(h_token, win32security.TokenIntegrityLevel)
                    sid = sid_info[0] if sid_info else None
                    il_name = "Unknown"
                    il = 0
                    if sid:
                        try:
                            il = sid.GetSubAuthority(0)
                            if il == 0x0000: il_name = "Untrusted"
                            elif il == 0x1000: il_name = "Low"
                            elif il == 0x2000: il_name = "Medium"
                            elif il == 0x3000: il_name = "High"
                            elif il >= 0x4000: il_name = "System"
                        except Exception as e_sub:
                            print(f"[Diagnostics] GetSubAuthority failed: {e_sub}")
                    print(f"[Diagnostics] Integrity Level: {il_name} ({hex(il) if sid else 'N/A'})")
                    
                    # Token UIAccess Status
                    try:
                        import ctypes
                        from ctypes import wintypes
                        ADVAPI32 = ctypes.WinDLL('advapi32', use_last_error=True)
                        GetTokenInformation = ADVAPI32.GetTokenInformation
                        GetTokenInformation.argtypes = [
                            wintypes.HANDLE,
                            ctypes.c_int,
                            ctypes.c_void_p,
                            wintypes.DWORD,
                            ctypes.POINTER(wintypes.DWORD)
                        ]
                        GetTokenInformation.restype = wintypes.BOOL
                        
                        uia_val = ctypes.c_ulong(0)
                        ret_len = wintypes.DWORD(0)
                        res = GetTokenInformation(
                            int(h_token),
                            26, # TokenUIAccess
                            ctypes.byref(uia_val),
                            ctypes.sizeof(uia_val),
                            ctypes.byref(ret_len)
                        )
                        if res:
                            print(f"[Diagnostics] Token UIAccess Status: {'Enabled' if uia_val.value else 'Disabled'}")
                        else:
                            print(f"[Diagnostics] GetTokenInformation for UIAccess failed: {ctypes.get_last_error()}")
                    except Exception as uia_err:
                        print(f"[Diagnostics] UIAccess check error: {uia_err}")
                    
                    reg_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
                    try:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ)
                        posd, reg_t = winreg.QueryValueEx(key, "PromptOnSecureDesktop")
                        ssas, reg_t = winreg.QueryValueEx(key, "SoftwareSASGeneration")
                        winreg.CloseKey(key)
                        print(f"[Diagnostics] Registry: PromptOnSecureDesktop = {posd}, SoftwareSASGeneration = {ssas}")
                    except Exception as ree:
                        print(f"[Diagnostics] Registry read failed: {ree}")
                    
                    # Check scheduled task status
                    try:
                        import subprocess
                        res = subprocess.run('schtasks /query /tn "EasyRemoteDesktopAgent" /fo list', shell=True, capture_output=True, text=True)
                        print(f"[Diagnostics] Scheduled Task Status:\n{res.stdout if res.returncode == 0 else res.stderr}")
                    except Exception as te:
                        print(f"[Diagnostics] Failed to query scheduled task: {te}")
            except Exception as de:
                print(f"[Diagnostics] Diagnostics gathering failed: {de}")
        except Exception as e:
            pass
        
        # Thiết lập icon cho cửa sổ chính
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                try:
                    icon_img = tk.PhotoImage(file=icon_path)
                except Exception:
                    icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(True, icon_img)
                self._app_icon_img = icon_img  # Giữ reference tránh GC
        except Exception as e:
            print(f"[App] Lỗi thiết lập icon cửa sổ: {e}")
        
        # Register app instance to ClipboardSyncManager
        if clipboard_sync_manager:
            clipboard_sync_manager.register_app(self)
        
        # Window attributes
        title_text = "Easy Remote Desktop"
        try:
            is_android = 'ANDROID_ARGUMENT' in os.environ or 'ANDROID_BOOTLOGO' in os.environ
            try:
                if hasattr(sys, 'getandroidapilevel'):
                    is_android = True
            except: pass
            
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
                    title_text += f" - MC-Android {serial}"
        except Exception:
            pass
        self.title(title_text)
        self.resizable(False, False)
        
        # Shutdown listener for closing client cleanly
        if sys.platform == "win32":
            try:
                import win32gui, win32con, win32api
                def WndProc(hwnd, msg, wparam, lparam):
                    if msg == win32con.WM_QUERYENDSESSION:
                        if not (lparam & 0x80000000): # 0x80000000 is ENDSESSION_LOGOFF
                            print("[Host] System Shutdown/Restart detected!")
                            try:
                                from network.socket_utils import socket_passwords, send_msg
                                import json
                                for conn in list(socket_passwords.keys()):
                                    try:
                                        send_msg(conn, json.dumps({"type": "host_shutdown"}).encode('utf-8'), socket_passwords[conn])
                                    except: pass
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
        elif sys.platform.startswith("linux") or sys.platform == "darwin":
            try:
                import signal
                def handle_sigterm(signum, frame):
                    print(f"[Host] System Shutdown/Restart detected (signal {signum})!")
                    try:
                        from network.socket_utils import socket_passwords, send_msg
                        import json
                        for conn in list(socket_passwords.keys()):
                            try:
                                send_msg(conn, json.dumps({"type": "host_shutdown"}).encode('utf-8'), socket_passwords[conn])
                            except: pass
                    except: pass
                    import time
                    time.sleep(1)
                    sys.exit(0)
                signal.signal(signal.SIGTERM, handle_sigterm)
                signal.signal(signal.SIGHUP, handle_sigterm)
            except Exception as e:
                print(f"[Host] Failed to setup Linux shutdown listener: {e}")
        
        # Cờ trạng thái chống mở nhiều cửa sổ điều khiển cùng lúc
        self.is_client_connected = False
        
        # Load saved window position or center it
        self.config_file = os.path.join(get_app_data_dir(), "window_config.json")
        self.last_normal_geometry = None
        self.bind("<Configure>", self.on_window_configure)
        self.load_window_position()
        # Load language setting
        self.current_lang = tk.StringVar(value="vi")
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    cfg = json.load(f)
                    saved_lang = cfg.get("language", "vi")
                    self.current_lang.set(saved_lang)
                    load_language(saved_lang)
        except:
            pass

        
        # Migrate old JSON list to new encrypted XML format
        old_json_file = "saved_computers.json"
        new_xml_file = get_computers_xml_path()
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
        
        from gui.themes import setup_app_theme
        setup_app_theme(self, self.config_file)
        
        self.my_id_clean, self.my_id_formatted, self.my_macs = get_hwid()
        
        # Check if service (headless agent) is active by checking the mutex
        self.is_service_active = False
        if not self.is_headless:
            exe_path = sys.argv[0] if (sys.argv and sys.argv[0]) else sys.executable
            exe_path_abs = os.path.abspath(exe_path).lower()
            if sys.platform != "win32":
                if "/opt/p2p_remote" in exe_path_abs:
                    self.is_service_active = True
                    
        if sys.platform == "win32" and not self.is_headless:
            import win32event, win32con
            
            # Since the service is actually a Scheduled Task (EasyRemoteDesktopAgent),
            # we check if we are running from the installation directory and wait for the headless agent.
            is_installed_version = False
            try:
                if "c:\\apps\\p2p" in exe_path_abs or "program files" in exe_path_abs:
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
                # If running from installation directory, always assume service is active to avoid port 12345 hijacking
                self.is_service_active = True
            else:
                # Fallback to checking Mutex for portable versions
                for d_name in ["default", "winlogon"]:
                    m_name = f"Global\\AntigravityP2PRemoteDesktopAppMutex_1_{session_id}_{d_name}"
                    try:
                        h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, m_name)
                        if h_mutex:
                            win32api.CloseHandle(h_mutex)
                            self.is_service_active = True
                            break
                    except Exception as e:
                        err_code = getattr(e, 'winerror', 0)
                        if not err_code and hasattr(e, 'args') and len(e.args) > 0:
                            err_code = e.args[0]
                        if err_code == 5: # ERROR_ACCESS_DENIED
                            self.is_service_active = True
                            break

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
                import core.config; core.config.BOUND_PORT = 12346
                import core.network_manager; core.network_manager.BOUND_PORT = 12346
                import core.host; core.host.BOUND_PORT = 12346
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
        self.pass_type_var = tk.StringVar(value=_("4 chữ số"))
        self.server_socket = None
        self.running_server = True
        self.active_clients = {}
        self.active_viewers = []
        self.current_ip = _("Đang lấy IP...")
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
        self.status_var = tk.StringVar(value=_("Đang kết nối tới mạng đăng ký..."))
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
        
    def change_theme(self):
        from gui.themes import change_app_theme
        change_app_theme(self)

    
    def export_lang_template(self):
        try:
            # Đọc template từ file lang_template.json (được tạo bởi gen_lang_template.py)
            from core.i18n import get_lang_dir
            template_file = os.path.join(get_lang_dir(), "lang_template.json")
            if os.path.exists(template_file):
                with open(template_file, "r", encoding="utf-8") as f:
                    template = json.load(f)
            else:
                template = {}
            template_path = export_template(template)
            if template_path:
                messagebox.showinfo(_("Lưu lại"), _("Tệp ngôn ngữ mẫu đã được lưu tại:") + f"\n{template_path}\n" + _("Bạn có thể sao chép và đổi tên thành 'yourown.json' để dịch.\nGợi ý: dùng ChatGPT để dịch tự động là 1 lựa chọn\nThank you!"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def import_custom_language(self):
        from tkinter import filedialog
        import shutil
        from core.i18n import get_lang_dir
        
        file_path = filedialog.askopenfilename(
            title=_("Chọn tệp ngôn ngữ riêng của bạn"),
            filetypes=[("JSON Files", "*.json")]
        )
        if file_path:
            try:
                filename = os.path.basename(file_path)
                if filename in ["lang_template.json", "vi.json"]:
                    messagebox.showerror(_("Lỗi"), _("Không thể ghi đè tệp ngôn ngữ mặc định!"))
                    return
                
                dest_path = os.path.join(get_lang_dir(), filename)
                try:
                    shutil.copy2(file_path, dest_path)
                except shutil.SameFileError:
                    pass # Bỏ qua nếu người dùng chọn chính tệp trong thư mục lang
                
                lang_code = filename[:-5]
                self.current_lang.set(lang_code)
                self.change_language()
            except Exception as e:
                messagebox.showerror(_("Lỗi"), str(e))

    def change_language(self, *args):
        lang = self.current_lang.get()
        load_language(lang)
        self.save_window_position()
        messagebox.showinfo(_("Thay đổi thông tin"), _("Vui lòng khởi động lại ứng dụng để áp dụng ngôn ngữ mới."))
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv[1:])
        os._exit(0)

        
    def setup_ui(self):
        # Setup Window Menu Bar
        menubar = tk.Menu(self)
        
        # 1. File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=_("Danh sách (Saved Computers)"), command=self.show_saved_computers_dialog)
        file_menu.add_command(label=E(_("📡 Quét mạng LAN (LAN Discovery)")), command=self.show_lan_computers_dialog)
        file_menu.add_separator()
        file_menu.add_command(label=_("Thoát (Exit)"), command=self.destroy)
        menubar.add_cascade(label=_("File"), menu=file_menu)
        
        # 2. Options Menu
        options_menu = tk.Menu(menubar, tearoff=0)

        # Submenu: Password type
        password_menu = tk.Menu(options_menu, tearoff=0)
        password_menu.add_radiobutton(
            label=_("4 chữ số"),
            variable=self.pass_type_var, value=_("4 chữ số"),
            command=self.refresh_password
        )
        password_menu.add_radiobutton(
            label=_("5 chữ số"),
            variable=self.pass_type_var, value=_("5 chữ số"),
            command=self.refresh_password
        )
        password_menu.add_radiobutton(
            label=_("8 ký tự (chữ + số)"),
            variable=self.pass_type_var, value=_("8 ký tự (chữ + số)"),
            command=self.refresh_password
        )
        password_menu.add_separator()
        password_menu.add_command(
            label=_("Cài mật khẩu cố định..."),
            command=self.open_set_fixed_password_dialog
        )
        options_menu.add_cascade(label=_("Mật khẩu (Password)"), menu=password_menu)
        options_menu.add_separator()
        options_menu.add_checkbutton(
            label=_("Chạy khi mở máy (Run on Startup)"),
            variable=self.startup_var,
            command=self.toggle_startup
        )
        options_menu.add_command(
            label=_("Cài Zalo / Điện thoại"),
            command=self.open_set_zalo_phone_dialog
        )
        options_menu.add_separator()
        options_menu.add_command(
            label=_("Cài đặt máy chủ..."),
            command=self.show_server_settings_dialog
        )
        options_menu.add_separator()
        
        
        # Submenu: Language
        lang_menu = tk.Menu(options_menu, tearoff=0)
        langs = get_available_languages()
        for l in langs:
            lang_menu.add_radiobutton(label=get_language_name(l), variable=self.current_lang, value=l, command=self.change_language)
        
        # Export template
        lang_menu.add_separator()
        lang_menu.add_command(label=_("Xuất tệp ngôn ngữ mẫu..."), command=self.export_lang_template)
        lang_menu.add_command(label=_("Ngôn ngữ riêng của bạn"), command=self.import_custom_language)
        options_menu.add_cascade(label=_("Ngôn ngữ (Language)"), menu=lang_menu) # Tạm thay thế
        options_menu.add_separator()

        # Submenu: Theme
        theme_menu = tk.Menu(options_menu, tearoff=0)
        theme_menu.add_radiobutton(label=_("Sáng"), variable=self.current_theme, value="light", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Tối"), variable=self.current_theme, value="dark", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Xám"), variable=self.current_theme, value="gray", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Hồng"), variable=self.current_theme, value="pink", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Pha lê"), variable=self.current_theme, value="crystal", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Cam"), variable=self.current_theme, value="orange", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Đỏ"), variable=self.current_theme, value="red", command=self.change_theme)
        theme_menu.add_separator()
        theme_menu.add_radiobutton(label=_("Tùy chỉnh"), variable=self.current_theme, value="custom", command=self.change_theme)
        options_menu.add_cascade(label=_("Giao diện"), menu=theme_menu)
 
        menubar.add_cascade(label=_("Options"), menu=options_menu)
        
        # 3. Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=_("Zalo"), command=self.open_zalo)
        help_menu.add_command(label=_("Điện thoại"), command=self.open_phone_dialog)
        help_menu.add_command(label=_("About"), command=self.show_about_dialog)
        menubar.add_cascade(label=_("Help"), menu=help_menu)
        
        self.config(menu=menubar)
        
        if sys.platform == "darwin":
            self.after(2000, self._dump_mac_ui_geometry)

    def _dump_mac_ui_geometry(self):
        _log_mac("=== DUMPING GEOMETRY AFTER 2 SECONDS ===")
        labels = getattr(sys, '_mac_labels', [])
        _log_mac(f"Total labels tracked: {len(labels)}")
        for i, lbl in enumerate(labels[:20]):  # just check first 20
            try:
                _log_mac(f"Label {i} ['{lbl.cget('text')}']: viewable={lbl.winfo_viewable()}, x={lbl.winfo_x()}, y={lbl.winfo_y()}, w={lbl.winfo_width()}, h={lbl.winfo_height()}, ismapped={lbl.winfo_ismapped()}, fg={lbl.cget('fg')}, bg={lbl.cget('bg')}")
            except Exception as e:
                _log_mac(f"Label {i} error: {e}")
        _log_mac("=== DUMP COMPLETE ===")

        # Header Label
        header = tk.Label(self, text=_("P2P REMOTE DESKTOP"), font=(APP_FONT_NAME, 16, "bold"), fg=self.btn_color, bg=self.bg_color)
        header.pack(pady=(15, 5))
        
        # Sub-header
        subheader = tk.Label(self, text=_("Điều khiển trực tuyến máy tính bằng HWID"), font=(APP_FONT_NAME, 9, "italic"), fg=self.text_gray, bg=self.bg_color)
        subheader.pack(pady=(0, 15))
        
        # Main Panels Container
        container = tk.Frame(self, bg=self.bg_color)
        self._main_container = container
        container.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # LEFT PANEL: Allow Remote Control
        left_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        self._left_panel = left_panel
        left_panel.place(relx=0.0, rely=0.0, relwidth=0.47, relheight=0.92)
        
        lbl_allow = tk.Label(left_panel, text=_("CHO PHÉP ĐIỀU KHIỂN"), font=(APP_FONT_NAME, 11, "bold"), fg=self.btn_color, bg=self.card_color)
        lbl_allow.pack(pady=(15, 10))
        
        lbl_id = tk.Label(left_panel, text=_("Mã ID của bạn:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_id.pack(anchor=tk.W, padx=20)
        
        id_frame = tk.Frame(left_panel, bg=self.card_color)
        self._id_frame = id_frame
        id_frame.pack(fill=tk.X, padx=20, pady=(5, 12))
        
        self.my_id_label = tk.Label(id_frame, text=self.my_id_formatted, font=(APP_FONT_NAME, 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0, height=1)
        self.my_id_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_id_btn = tk.Button(id_frame, text=E("📋"), font=EMOJI_FONT_10, fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=lambda: self.copy_to_clipboard(self.my_id_formatted))
        copy_id_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(copy_id_btn, _("Sao chép"))
        
        lbl_pass = tk.Label(left_panel, text=_("Mật khẩu kết nối:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_pass.pack(anchor=tk.W, padx=20)
        
        pass_frame = tk.Frame(left_panel, bg=self.card_color)
        self._pass_frame = pass_frame
        pass_frame.pack(fill=tk.X, padx=20, pady=(5, 5))
        
        self.my_pass_label = tk.Label(pass_frame, text=self.my_password, font=(APP_FONT_NAME, 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0)
        self.my_pass_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_pass_btn = tk.Button(pass_frame, text=E("📋"), font=EMOJI_FONT_10, fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=lambda: self.copy_to_clipboard(self.my_password))
        copy_pass_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(copy_pass_btn, _("Sao chép"))
        
        refresh_btn = tk.Button(pass_frame, text="↻", font=(APP_FONT_NAME, 10, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=self.refresh_password)
        refresh_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(refresh_btn, _("Đổi mật khẩu"))

        # Nhãn hiển thị trạng thái mật khẩu cố định
        self.fixed_pass_indicator = tk.Label(left_panel, text="", font=(APP_FONT_NAME, 8, "italic"), fg="#2ECC71", bg=self.card_color)
        self.fixed_pass_indicator.pack(anchor=tk.W, padx=20, pady=(2, 0))
        self.update_fixed_password_indicator()

        # Button to Copy both ID & Password at once
        copy_all_btn = tk.Button(left_panel, text=E(_("📋 Sao chép cả ID & Mật khẩu")), font=EMOJI_FONT_BOLD, fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, command=self.copy_id_and_password)
        copy_all_btn.pack(pady=(8, 0), padx=20, fill=tk.X)
        
        # Nút gọi Danh sách máy tính đã lưu
        saved_list_btn = tk.Button(left_panel, text=E(_("📁 Danh sách máy tính đã lưu")), font=EMOJI_FONT, fg="#FFFFFF", bg="#5B2C8E", activebackground="#7B3FA8", relief=tk.FLAT, bd=0, pady=3, cursor="hand2", command=self.show_saved_computers_dialog)
        saved_list_btn.pack(side=tk.BOTTOM, padx=20, fill=tk.X, pady=(0, 20))
        
        # RIGHT PANEL: Control Remote Computer
        right_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        self._right_panel = right_panel
        right_panel.place(relx=0.53, rely=0.0, relwidth=0.47, relheight=0.92)
        
        lbl_control = tk.Label(right_panel, text=_("ĐIỀU KHIỂN ĐỐI TÁC"), font=(APP_FONT_NAME, 11, "bold"), fg=self.btn_color, bg=self.card_color)
        lbl_control.pack(pady=(15, 10))
        
        lbl_p_id = tk.Label(right_panel, text=_("Nhập ID đối tác:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_p_id.pack(anchor=tk.W, padx=20)
        
        self.entry_p_id = tk.Entry(right_panel, textvariable=self.partner_id_var, font=(APP_FONT_NAME, 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, relief=tk.FLAT, bd=4)
        self.entry_p_id.pack(pady=(5, 10), padx=20, fill=tk.X)
        
        lbl_p_pass = tk.Label(right_panel, text=_("Nhập Mật khẩu đối tác:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_p_pass.pack(anchor=tk.W, padx=20)
        
        self.entry_p_pass = tk.Entry(right_panel, textvariable=self.partner_pass_var, font=(APP_FONT_NAME, 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, show="*", relief=tk.FLAT, bd=4)
        self.entry_p_pass.pack(pady=(5, 20), padx=20, fill=tk.X)
        
        # Bind Enter keys to trigger Connection immediately
        self.entry_p_id.bind("<Return>", lambda event: self.click_connect())
        self.entry_p_id.bind("<KP_Enter>", lambda event: self.click_connect())
        self.entry_p_pass.bind("<Return>", lambda event: self.click_connect())
        self.entry_p_pass.bind("<KP_Enter>", lambda event: self.click_connect())
        
        # Container to hold CONNECT & ADD (+) buttons
        btn_container = tk.Frame(right_panel, bg=self.card_color)
        btn_container.pack(padx=20, fill=tk.X)
        
        self.connect_btn = tk.Button(btn_container, text=_("KẾT NỐI (CONNECT)"), font=(APP_FONT_NAME, 11, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, command=self.click_connect)
        self.connect_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Add button with a blue "+"
        self.add_partner_btn = tk.Button(btn_container, text=E("➕"), font=EMOJI_FONT_LARGE, fg=self.text_white, bg="#007ACC", activebackground="#005A9E", relief=tk.FLAT, bd=0, width=4, cursor="hand2", command=self.add_current_partner_to_saved)
        self.add_partner_btn.pack(side=tk.RIGHT, padx=(8, 0))
        ToolTip(self.add_partner_btn, _("Thêm máy tính"))

        # LAN Discovery button - Quét máy trong mạng nội bộ
        lan_btn = tk.Button(right_panel, text=E(_("📡 Quét mạng LAN (LAN Only)")), font=EMOJI_FONT, fg="#FFFFFF", bg="#5B2C8E", activebackground="#7B3FA8", relief=tk.FLAT, bd=0, pady=3, cursor="hand2", command=self.show_lan_computers_dialog)
        lan_btn.pack(side=tk.BOTTOM, padx=20, fill=tk.X, pady=(0, 20))

        # Attach Context Menus for Copy & Paste
        self.make_context_menu(self.entry_p_id)
        self.make_context_menu(self.entry_p_pass)
        
        # BOTTOM STATUS BAR
        status_bar = tk.Frame(self, bg=self.entry_bg, height=25)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl_status = tk.Label(status_bar, textvariable=self.status_var, font=(APP_FONT_NAME, 8, "italic"), fg="#8A8A9A", bg=self.entry_bg, anchor=tk.W)
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

    
    def export_lang_template(self):
        try:
            template = {
    _("Đang kết nối tới mạng đăng ký..."): _("Đang kết nối tới mạng đăng ký..."),
    _("Đã sao chép cả ID & Mật khẩu!"): _("Đã sao chép cả ID & Mật khẩu!"),
    _("Đã sao chép vào bộ nhớ tạm: "): _("Đã sao chép vào bộ nhớ tạm: "),
    _("Lỗi"): _("Lỗi"),
    _("Không thể cập nhật mật khẩu. Vui lòng chạy ứng dụng bằng quyền Administrator!"): _("Không thể cập nhật mật khẩu. Vui lòng chạy ứng dụng bằng quyền Administrator!"),
    _("Tìm kiếm theo tên hoặc ID..."): _("Tìm kiếm theo tên hoặc ID..."),
    _("tìm kiếm theo tên hoặc id..."): _("tìm kiếm theo tên hoặc id..."),
    _("Lỗi nhập liệu"): _("Lỗi nhập liệu"),
    _("Vui lòng điền đầy đủ các thông tin!"): _("Vui lòng điền đầy đủ các thông tin!"),
    _("Trùng lặp"): _("Trùng lặp"),
    _("Máy tính này đã tồn tại trong danh sách!"): _("Máy tính này đã tồn tại trong danh sách!"),
    _("Sửa thông tin"): _("Sửa thông tin"),
    _("Không tìm thấy máy tính tương ứng để sửa!"): _("Không tìm thấy máy tính tương ứng để sửa!"),
    _("Vui lòng nhập đầy đủ thông tin!"): _("Vui lòng nhập đầy đủ thông tin!"),
    _("Cổng kết nối (Port) phải là số!"): _("Cổng kết nối (Port) phải là số!"),
    _("Không thể lưu file server.ini: "): _("Không thể lưu file server.ini: "),
    _("Thất bại"): _("Thất bại"),
    _("Không thể thay đổi cài đặt Registry: "): _("Không thể thay đổi cài đặt Registry: "),
    _("Sao chép"): _("Sao chép"),
    _("Đổi mật khẩu"): _("Đổi mật khẩu"),
    _("Thêm máy tính"): _("Thêm máy tính"),
    _("Thành công"): _("Thành công"),
    _("Đã lưu máy tính '{name}' vào danh sách thành công!"): _("Đã lưu máy tính '{name}' vào danh sách thành công!"),
    _("Đã lưu thông tin liên hệ Zalo / Điện thoại thành công!"): _("Đã lưu thông tin liên hệ Zalo / Điện thoại thành công!"),
    "Đã cập nhật máy chủ thành công!\nỨng dụng sẽ sử dụng cấu hình mới cho các kết nối tiếp theo.": "Đã cập nhật máy chủ thành công!\nỨng dụng sẽ sử dụng cấu hình mới cho các kết nối tiếp theo.",
    _("Đã lưu mật khẩu cố định thành công!"): _("Đã lưu mật khẩu cố định thành công!"),
    _("Đã tắt mật khẩu cố định thành công!"): _("Đã tắt mật khẩu cố định thành công!"),
    _("Đã bật tính năng chạy khi mở máy thành công!"): _("Đã bật tính năng chạy khi mở máy thành công!"),
    _("Đã tắt tính năng chạy khi mở máy thành công!"): _("Đã tắt tính năng chạy khi mở máy thành công!"),
    _("+ Thêm Mới"): _("+ Thêm Mới"),
    _("4 chữ số"): _("4 chữ số"),
    _("5 chữ số"): _("5 chữ số"),
    _("8 ký tự (chữ + số)"): _("8 ký tự (chữ + số)"),
    "AI Pro Version": "AI Pro Version",
    "About": "About",
    _("CHO PHÉP ĐIỀU KHIỂN"): _("CHO PHÉP ĐIỀU KHIỂN"),
    _("CHỌN ĐỐI TÁC XEM ĐIỆN THOẠI"): _("CHỌN ĐỐI TÁC XEM ĐIỆN THOẠI"),
    _("CHỌN ĐỐI TÁC ĐỂ LIÊN HỆ ZALO"): _("CHỌN ĐỐI TÁC ĐỂ LIÊN HỆ ZALO"),
    "Cam": "Cam",
    _("Chưa có liên lạc"): _("Chưa có liên lạc"),
    _("Chạy khi mở máy (Run on Startup)"): _("Chạy khi mở máy (Run on Startup)"),
    _("Chọn tất cả (Select All)"): _("Chọn tất cả (Select All)"),
    _("Chọn đối tác"): _("Chọn đối tác"),
    _("CÀI ĐẶT MẬT KHẨU CỐ ĐỊNH"): _("CÀI ĐẶT MẬT KHẨU CỐ ĐỊNH"),
    _("CÀI ĐẶT ZALO / ĐIỆN THOẠI"): _("CÀI ĐẶT ZALO / ĐIỆN THOẠI"),
    _("Cài Zalo / Điện thoại"): _("Cài Zalo / Điện thoại"),
    _("Cài mật khẩu cố định..."): _("Cài mật khẩu cố định..."),
    _("Cài đặt Máy chủ (Signaling Server)"): _("Cài đặt Máy chủ (Signaling Server)"),
    _("Cài đặt máy chủ..."): _("Cài đặt máy chủ..."),
    _("Có"): _("Có"),
    _("Cả hai máy cùng mạng nội bộ nhưng không kết nối được trực tiếp"): _("Cả hai máy cùng mạng nội bộ nhưng không kết nối được trực tiếp"),
    _("CẤU HÌNH MÁY CHỦ SIGNALING"): _("CẤU HÌNH MÁY CHỦ SIGNALING"),
    _("CẬP NHẬT THÔNG TIN"): _("CẬP NHẬT THÔNG TIN"),
    _("Cắt (Cut)"): _("Cắt (Cut)"),
    _("Cổng kết nối (Port):"): _("Cổng kết nối (Port):"),
    _("DANH SÁCH MÁY TÍNH ĐÃ LƯU"): _("DANH SÁCH MÁY TÍNH ĐÃ LƯU"),
    _("Danh sách (Saved Computers)"): _("Danh sách (Saved Computers)"),
    _("Danh sách Máy chủ:"): _("Danh sách Máy chủ:"),
    _("Danh sách Máy tính"): _("Danh sách Máy tính"),
    _("Dán (Paste)"): _("Dán (Paste)"),
    "Easy Remote Desktop": "Easy Remote Desktop",
    "File": "File",
    _("Giao diện"): _("Giao diện"),
    "Help": "Help",
    _("Hiển thị mật khẩu"): _("Hiển thị mật khẩu"),
    _("Hồng"): _("Hồng"),
    _("Hủy"): _("Hủy"),
    _("Hủy bỏ"): _("Hủy bỏ"),
    _("ID đối tác:"): _("ID đối tác:"),
    _("Không"): _("Không"),
    _("KẾT NỐI (CONNECT)"): _("KẾT NỐI (CONNECT)"),
    _("Kết nối"): _("Kết nối"),
    _("Kết nối mạng LAN thất bại"): _("Kết nối mạng LAN thất bại"),
    _("Liên hệ Zalo"): _("Liên hệ Zalo"),
    _("Liên hệ: Mr. Tuyến - 0941 261 771"): _("Liên hệ: Mr. Tuyến - 0941 261 771"),
    _("Lưu"): _("Lưu"),
    _("Lưu lại"): _("Lưu lại"),
    _("Lỗi kết nối mạng LAN"): _("Lỗi kết nối mạng LAN"),
    _("Mã ID của bạn:"): _("Mã ID của bạn:"),
    _("Mật khẩu (Password)"): _("Mật khẩu (Password)"),
    _("Mật khẩu cố định"): _("Mật khẩu cố định"),
    _("Mật khẩu kết nối:"): _("Mật khẩu kết nối:"),
    _("Mật khẩu mới:"): _("Mật khẩu mới:"),
    _("Mật khẩu:"): _("Mật khẩu:"),
    _("Nhóm (Tùy chọn):"): _("Nhóm (Tùy chọn):"),
    _("Nhập ID đối tác:"): _("Nhập ID đối tác:"),
    _("Nhập Mật khẩu đối tác:"): _("Nhập Mật khẩu đối tác:"),
    "OK": "OK",
    "Options": "Options",
    "P2P REMOTE DESKTOP": "P2P REMOTE DESKTOP",
    _("Pha lê"): _("Pha lê"),
    _("Sao chép (Copy)"): _("Sao chép (Copy)"),
    _("Sáng"): _("Sáng"),
    _("Sửa thông tin"): _("Sửa thông tin"),
    _("THÊM MÁY TÍNH MỚI"): _("THÊM MÁY TÍNH MỚI"),
    _("Thay đổi thông tin"): _("Thay đổi thông tin"),
    _("Thoát (Exit)"): _("Thoát (Exit)"),
    _("Thêm Máy tính"): _("Thêm Máy tính"),
    _("Tên gọi gợi nhớ:"): _("Tên gọi gợi nhớ:"),
    _("Tùy chỉnh"): _("Tùy chỉnh"),
    _("Tối"): _("Tối"),
    _("Xám"): _("Xám"),
    _("Xóa máy tính"): _("Xóa máy tính"),
    "Zalo": "Zalo",
    _("ĐIỀU KHIỂN ĐỐI TÁC"): _("ĐIỀU KHIỂN ĐỐI TÁC"),
    _("Điều khiển trực tuyến máy tính bằng HWID"): _("Điều khiển trực tuyến máy tính bằng HWID"),
    _("Điện thoại"): _("Điện thoại"),
    _("Điện thoại liên hệ"): _("Điện thoại liên hệ"),
    _("Đã hiểu"): _("Đã hiểu"),
    _("Đóng"): _("Đóng"),
    _("Đỏ"): _("Đỏ"),
    _("Đổi tên nhóm"): _("Đổi tên nhóm"),
    _("● Mật khẩu cố định: Đang hoạt động"): _("● Mật khẩu cố định: Đang hoạt động"),
    _("📁 Danh sách máy tính đã lưu"): _("📁 Danh sách máy tính đã lưu"),
    _("📋  Thông tin kỹ thuật"): _("📋  Thông tin kỹ thuật"),
    _("📋 Sao chép cả ID & Mật khẩu"): _("📋 Sao chép cả ID & Mật khẩu"),
    _("📡 Quét mạng LAN (LAN Discovery)"): _("📡 Quét mạng LAN (LAN Discovery)"),
    _("📡 Quét mạng LAN (LAN Only)"): _("📡 Quét mạng LAN (LAN Only)"),
    _("🔄 Làm mới"): _("🔄 Làm mới"),
    _("🔄 Làm mới (30s)"): _("🔄 Làm mới (30s)"),
    _("🔧  Cách khắc phục"): _("🔧  Cách khắc phục")
}
            template_path = export_template(template)
            if template_path:
                messagebox.showinfo(_("Lưu lại"), _("Tệp ngôn ngữ mẫu đã được lưu tại:") + f"\n{template_path}\n" + _("Bạn có thể sao chép và đổi tên thành 'yourown.json' để dịch.\nGợi ý: dùng ChatGPT để dịch tự động là 1 lựa chọn\nThank you!"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def change_language(self, *args):
        lang = self.current_lang.get()
        load_language(lang)
        self.save_window_position()
        messagebox.showinfo(_("Thay đổi thông tin"), _("Ứng dụng sẽ khởi động lại để áp dụng ngôn ngữ mới."))
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv[1:])
        os._exit(0)

    def save_window_position(self):
        try:
            # Ưu tiên lấy tọa độ hoạt động bình thường cuối cùng được ghi nhận
            geom = getattr(self, 'last_normal_geometry', None)
            if not geom:
                geom = self.geometry()
                
            # Tránh lưu tọa độ ảo/thu nhỏ lỗi
            if "+" in geom:
                parts = geom.split("+")
                if len(parts) >= 3:
                    x = int(parts[1])
                    y = int(parts[2])
                    if x <= -30000 or y <= -30000:
                        print(f"[Config] Skip saving minimized geometry: {geom}")
                        return
                        
            config_data = {"geometry": geom}
            if hasattr(self, 'current_theme'):
                config_data["theme"] = self.current_theme.get()
            if hasattr(self, 'current_lang'):
                config_data["language"] = self.current_lang.get()
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            print(f"[Config] Saved window position & theme & language: {geom}")
        except Exception as e:
            print(f"[Config] Error saving window config: {e}")


    def copy_id_and_password(self):
        text = f'ID: {self.my_id_formatted}, mật khẩu: {self.my_password}'
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_status(_("Đã sao chép cả ID & Mật khẩu!"), is_success=True)


    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text.strip())
        self.update_status(_("Đã sao chép vào bộ nhớ tạm: ") + text.strip(), is_success=True)


    def make_context_menu(self, entry):
        menu = tk.Menu(entry, tearoff=0)
        menu.add_command(label=_("Cắt (Cut)"), command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_command(label=_("Sao chép (Copy)"), command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label=_("Dán (Paste)"), command=lambda: entry.event_generate("<<Paste>>"))
        menu.add_command(label=_("Chọn tất cả (Select All)"), command=lambda: entry.event_generate("<<SelectAll>>"))
        
        # Giữ tham chiếu mạnh (Strong Reference) tránh rác hệ thống làm mất menu
        entry.menu = menu
        
        # Bắt chuột phải trên cả Windows (Button-3) và một số Touchpad/Mac (Button-2)
        entry.bind("<Button-3>", lambda e: entry.menu.post(e.x_root, e.y_root))
        entry.bind("<Button-2>", lambda e: entry.menu.post(e.x_root, e.y_root))


    def refresh_password(self):
        import string
        old_password = self.my_password
        ptype = self.pass_type_var.get()
        if ptype == _("5 chữ số"):
            self.my_password = str(random.randint(10000, 99999))
        elif ptype == _("8 ký tự (chữ + số)"):
            chars = string.ascii_letters + string.digits
            self.my_password = ''.join(random.choices(chars, k=8))
        else:  # Mặc định: 4 chữ số
            self.my_password = str(random.randint(1000, 9999))
            
        # Write to session_pass.txt if service is active or we are headless
        if self.is_headless or getattr(self, "is_service_active", False):
            try:
                pass_path = os.path.join(app_dir, "session_pass.txt")
                with open(pass_path, "w", encoding="utf-8") as f:
                    f.write(self.my_password)
                print(f"[Host] Saved refreshed session password to {pass_path}")
            except Exception as e:
                print(f"[Host] Failed to save refreshed session password: {e}")
                self.my_password = old_password
                self.show_custom_error(_("Lỗi"), _("Không thể cập nhật mật khẩu. Vui lòng chạy ứng dụng bằng quyền Administrator!"))
                
        self.my_pass_label.config(text=self.my_password)
        

    def show_saved_computers_dialog(self):
        if not hasattr(self, 'collapsed_groups'):
            self.collapsed_groups = set()
        self.drag_card_id = None
        
        if hasattr(self, 'saved_computers_dialog') and self.saved_computers_dialog.winfo_exists():
            if self.saved_computers_dialog.state() == 'withdrawn':
                if hasattr(self.saved_computers_dialog, 'refresh_list_func'):
                    self.saved_computers_dialog.refresh_list_func()
                # Re-bind mousewheel khi mở lại dialog
                if hasattr(self.saved_computers_dialog, '_bind_mousewheel'):
                    self.saved_computers_dialog._bind_mousewheel()
                self.saved_computers_dialog.attributes("-alpha", 0.0)
                self.saved_computers_dialog.deiconify()
                def _show_reopen():
                    if self.saved_computers_dialog.winfo_exists():
                        self.saved_computers_dialog.attributes("-alpha", 1.0)
                        self.saved_computers_dialog.lift()
                        self.saved_computers_dialog.focus_force()
                self.after(50, _show_reopen)
                return
            self.saved_computers_dialog.lift()
            self.saved_computers_dialog.focus_force()
            return
            
        dialog = tk.Toplevel(self)
        dialog.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy ở góc trên bên trái màn hình
        self.saved_computers_dialog = dialog
        dialog.title(_("Danh sách Máy tính"))
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.transient(self)

        # Center dialog
        dialog.update_idletasks()
        w = 480
        h = 400
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        # Top title
        lbl_title = tk.Label(dialog, text=_("DANH SÁCH MÁY TÍNH ĐÃ LƯU"), font=(APP_FONT_NAME, 12, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        # Thanh Tìm kiếm
        search_frame = tk.Frame(dialog, bg=self.bg_color)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        search_inner = tk.Frame(search_frame, bg="#2A2A3D", highlightthickness=1, highlightbackground=self.divider_color)
        search_inner.pack(fill=tk.X)
        
        lbl_search_icon = tk.Label(search_inner, text=E("🔍"), font=EMOJI_FONT, fg=self.text_gray, bg="#2A2A3D")
        lbl_search_icon.pack(side=tk.LEFT, padx=(8, 5), pady=4)
        
        search_var = tk.StringVar()
        entry_search = tk.Entry(search_inner, textvariable=search_var, font=(APP_FONT_NAME, 9), fg=self.text_white, bg="#2A2A3D", bd=0, insertbackground=self.text_white)
        entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4, padx=(0, 8))
        
        # Thiết lập Placeholder chuyên nghiệp
        entry_search.insert(0, _("Tìm kiếm theo tên hoặc ID..."))
        entry_search.configure(fg=self.text_gray)
        
        def on_focus_in(event):
            if entry_search.get() == _("Tìm kiếm theo tên hoặc ID..."):
                entry_search.delete(0, tk.END)
                entry_search.configure(fg=self.text_white)
                
        def on_focus_out(event):
            if entry_search.get() == "":
                entry_search.insert(0, _("Tìm kiếm theo tên hoặc ID..."))
                entry_search.configure(fg=self.text_gray)
                
        entry_search.bind("<FocusIn>", on_focus_in)
        entry_search.bind("<FocusOut>", on_focus_out)
        
        def on_search_change(*args):
            val = search_var.get()
            if val == _("Tìm kiếm theo tên hoặc ID..."):
                return
            refresh_list()
            
        search_var.trace_add("write", on_search_change)

        def load_computers():
            return self.load_saved_computers()

        def save_computers(lst):
            self.save_saved_computers(lst)

        # Container for the list (Sẽ pack ở cuối cùng sau khi đã pack bottom_frame để tránh bị đè/cắt nút)
        list_container = tk.Frame(dialog, bg=self.card_color)

        # Canvas & Scrollbar for scrollable area
        canvas = tk.Canvas(list_container, bg=self.card_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.card_color)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW)
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(canvas_frame, width=e.width)
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel support
        def _on_mousewheel(event):
            try:
                if not dialog.winfo_exists() or not canvas.winfo_exists():
                    return
                # Chỉ scroll khi con trỏ chuột nằm trong dialog
                mx, my = dialog.winfo_pointerxy()
                dx = dialog.winfo_rootx()
                dy = dialog.winfo_rooty()
                dw = dialog.winfo_width()
                dh = dialog.winfo_height()
                if dx <= mx <= dx + dw and dy <= my <= dy + dh:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        def _bind_mousewheel():
            """Gắn mousewheel binding."""
            try:
                if canvas.winfo_exists():
                    canvas.bind_all("<MouseWheel>", _on_mousewheel)
            except Exception:
                pass

        def _unbind_mousewheel():
            """Gỡ mousewheel binding khi dialog đóng."""
            try:
                canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass

        # Gắn lên dialog object để có thể gọi lại khi reopen
        dialog._bind_mousewheel = _bind_mousewheel
        dialog._unbind_mousewheel = _unbind_mousewheel

        # Kích hoạt scroll ngay lập tức
        _bind_mousewheel()

        def on_dialog_destroy():
            _unbind_mousewheel()
            dialog.withdraw()
            
        dialog.protocol("WM_DELETE_WINDOW", on_dialog_destroy)

        def connect_computer(item):
            self.partner_id_var.set(item["id"])
            self.partner_pass_var.set(item["password"])
            # Giữ cửa sổ Danh sách Máy tính tiếp tục hiển thị theo yêu cầu người dùng
            # Trigger connection immediately
            self.click_connect()

        def delete_computer(item):
            if self.show_custom_question(_("Xóa máy tính"), _("Bạn có chắc muốn xóa") + f" '{item['name']}' " + _("khỏi danh sách?"), parent=dialog):
                computers = load_computers()
                computers = [c for c in computers if not (c["id"] == item["id"] and c["name"] == item["name"])]
                save_computers(computers)
                refresh_list()

        self.auto_scroll_job = None

        def check_auto_scroll():
            drag_id = getattr(self, 'drag_card_id', None)
            if not drag_id:
                self.auto_scroll_job = None
                return

            try:
                x, y = canvas.winfo_pointerxy()
                cy = canvas.winfo_rooty()
                ch = canvas.winfo_height()
                rel_y = y - cy
                
                if rel_y < 40:
                    canvas.yview_scroll(-1, "units")
                elif rel_y > ch - 40:
                    canvas.yview_scroll(1, "units")
                    
                self.auto_scroll_job = dialog.after(50, check_auto_scroll)
            except Exception:
                self.auto_scroll_job = None

        def on_drag_motion(event):
            drag_id = getattr(self, 'drag_card_id', None)
            if drag_id and not getattr(self, 'auto_scroll_job', None):
                check_auto_scroll()
            
            if drag_id:
                try:
                    x, y = event.x_root, event.y_root
                    target_widget = dialog.winfo_containing(x, y)
                    target_group = None
                    if target_widget:
                        w = target_widget
                        while w:
                            if getattr(w, 'is_group_header', False):
                                target_group = w.group_name
                                break
                            if hasattr(w, 'comp_group'):
                                target_group = w.comp_group
                                break
                            if str(w) == str(dialog):
                                break
                            parent_str = w.winfo_parent()
                            if not parent_str: break
                            w = w._nametowidget(parent_str)
                    
                    if scrollable_frame.winfo_exists():
                        for c in scrollable_frame.winfo_children():
                            if getattr(c, 'is_group_header', False):
                                if target_group is not None and c.group_name == target_group:
                                    c["fg"] = self.btn_color
                                else:
                                    c["fg"] = self.text_gray
                except Exception:
                    pass

        def on_drop(event):
            if getattr(self, 'auto_scroll_job', None):
                try:
                    dialog.after_cancel(self.auto_scroll_job)
                except Exception:
                    pass
                self.auto_scroll_job = None
                
            try:
                if scrollable_frame.winfo_exists():
                    for c in scrollable_frame.winfo_children():
                        if getattr(c, 'is_group_header', False):
                            c["fg"] = self.text_gray
            except Exception:
                pass
                
            drag_id = getattr(self, 'drag_card_id', None)
            if not drag_id: return
            self.drag_card_id = None
            
            x, y = event.x_root, event.y_root
            target_widget = dialog.winfo_containing(x, y)
            if not target_widget: return
            
            target_group = None
            w = target_widget
            while w:
                if getattr(w, 'is_group_header', False):
                    target_group = w.group_name
                    break
                if hasattr(w, 'comp_group'):
                    target_group = w.comp_group
                    break
                if str(w) == str(dialog):
                    break
                parent_str = w.winfo_parent()
                if not parent_str: break
                w = w._nametowidget(parent_str)
                
            if target_group is not None:
                comps = load_computers()
                updated = False
                for c in comps:
                    if c["id"].replace(" ", "") == drag_id:
                        if c.get("group", "").strip() != target_group:
                            c["group"] = target_group
                            updated = True
                        break
                if updated:
                    save_computers(comps)
                    refresh_list()

        def rename_group_dialog(old_group_name):
            rn_win = tk.Toplevel(dialog)
            rn_win.withdraw()
            rn_win.title(_("Đổi tên nhóm"))
            rn_win.resizable(False, False)
            rn_win.configure(bg=self.bg_color)
            rn_win.transient(dialog)
            rn_win.grab_set()

            rn_win.update_idletasks()
            rw, rh = 300, 160
            rx = dialog.winfo_x() + (dialog.winfo_width() - rw) // 2
            ry = dialog.winfo_y() + (dialog.winfo_height() - rh) // 2
            rn_win.geometry(f"{rw}x{rh}+{rx}+{ry}")
            rn_win.deiconify()

            display_group = old_group_name if old_group_name else _("Chưa phân nhóm")
            lbl = tk.Label(rn_win, text=_("Nhập tên mới cho nhóm:") + f"\n({display_group})", font=(APP_FONT_NAME, 9), fg=self.text_white, bg=self.bg_color)
            lbl.pack(pady=(15, 10))

            entry_var = tk.StringVar(value=old_group_name)
            entry = tk.Entry(rn_win, textvariable=entry_var, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
            entry.pack(fill=tk.X, padx=20, pady=(0, 15))
            entry.focus()
            entry.select_range(0, tk.END)

            def do_rename():
                new_name = entry_var.get().strip()
                if new_name != old_group_name:
                    comps = load_computers()
                    for c in comps:
                        if c.get("group", "").strip() == old_group_name:
                            c["group"] = new_name
                    save_computers(comps)
                    if old_group_name in getattr(self, 'collapsed_groups', set()):
                        self.collapsed_groups.remove(old_group_name)
                        self.collapsed_groups.add(new_name)
                    refresh_list()
                rn_win.destroy()

            btn_frame = tk.Frame(rn_win, bg=self.bg_color)
            btn_frame.pack(fill=tk.X, padx=20)
            
            btn_save = tk.Button(btn_frame, text=_("Lưu"), font=(APP_FONT_NAME, 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=do_rename)
            btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
            
            btn_cancel = tk.Button(btn_frame, text=_("Hủy"), font=(APP_FONT_NAME, 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35", relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=rn_win.destroy)
            btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

        def reorder_list():
            if not scrollable_frame.winfo_exists(): return
            children = scrollable_frame.winfo_children()
            headers = [c for c in children if getattr(c, 'is_group_header', False)]
            cards = [c for c in children if hasattr(c, 'comp_id')]
            if not cards and not headers: return
            
            def get_is_online(c):
                if c.comp_id in self.status_dots_widgets:
                    widgets = self.status_dots_widgets[c.comp_id]
                    if widgets and widgets[0].winfo_exists():
                        return widgets[0].cget("fg") == "#00F5D4"
                return False

            for c in children:
                c.pack_forget()

            # Group cards
            grouped_cards = {}
            for c in cards:
                grp = getattr(c, 'comp_group', '')
                if grp not in grouped_cards:
                    grouped_cards[grp] = []
                grouped_cards[grp].append(c)

            def group_sort_key(g):
                return (1, g) if not g else (0, g.lower())
            
            sorted_groups = sorted(grouped_cards.keys(), key=group_sort_key)
            header_map = {h.group_name: h for h in headers}

            for grp in sorted_groups:
                if grp in header_map:
                    header_map[grp].pack(fill=tk.X, pady=(15, 5), padx=15)
                
                if grp not in self.collapsed_groups:
                    grp_cards = grouped_cards.get(grp, [])
                    grp_cards.sort(key=lambda c: (not get_is_online(c), c.comp_name.lower()))
                    for c in grp_cards:
                        c.pack(fill=tk.X, pady=0, padx=(0, 10))

        self._reorder_saved_computers_func = reorder_list

        def refresh_list(force=False):
            try:
                dialog.config(cursor="watch")
            except:
                pass
            dialog.update_idletasks()
            
            def _refresh_task():
                try:
                    _refresh_list_inner(force)
                finally:
                    try:
                        dialog.config(cursor="")
                    except:
                        pass
            
            dialog.after(10, _refresh_task)
            
        def _refresh_list_inner(force=False):
            query = search_var.get().strip().lower()
            if query == _("Tìm kiếm theo tên hoặc ID...").lower() or query == _("tìm kiếm theo tên hoặc id...").lower():
                query = ""

            computers = load_computers()
            
            # Filter
            if query:
                computers = [c for c in computers if query in c["name"].lower() or query in c["id"].replace(" ", "")]

            import json
            current_hash = json.dumps(computers, sort_keys=True)
            if not force and getattr(dialog, '_last_rendered_hash', None) == current_hash:
                reorder_list()
                return
            dialog._last_rendered_hash = current_hash

            current_online = {}
            for cid, widgets in self.status_dots_widgets.items():
                if widgets and widgets[0].winfo_exists():
                    current_online[cid] = (widgets[0].cget("fg") == "#00F5D4")

            # Clear previous items
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            self.status_dots_widgets.clear()

            if not computers:
                txt = _("Không tìm thấy máy tính phù hợp.") if query else _("Chưa có máy tính nào được lưu.\nBấm nút thêm bên dưới để tạo mới.")
                lbl_empty = tk.Label(scrollable_frame, text=txt, font=(APP_FONT_NAME, 9, "italic"), fg=self.text_gray, bg=self.card_color, justify=tk.CENTER)
                lbl_empty.pack(pady=40, fill=tk.X, expand=True)
                return

            unique_groups = set()
            for c in computers:
                unique_groups.add(c.get("group", "").strip())
            
            for grp in unique_groups:
                grp_display = grp if grp else _("Chưa phân nhóm")
                icon = "▶" if grp in self.collapsed_groups else "▼"
                header_text = f"{icon} {grp_display.upper()}"
                
                header = tk.Label(scrollable_frame, text=header_text, font=(APP_FONT_NAME, 9, "bold"), fg=self.text_gray, bg=self.card_color, anchor=tk.W, cursor="hand2")
                header.is_group_header = True
                header.group_name = grp
                
                def toggle_group(event, g=grp):
                    if g in self.collapsed_groups:
                        self.collapsed_groups.remove(g)
                    else:
                        self.collapsed_groups.add(g)
                    new_icon = "▶" if g in self.collapsed_groups else "▼"
                    g_display = g if g else _("Chưa phân nhóm")
                    event.widget.config(text=f"{new_icon} {g_display.upper()}")
                    reorder_list()
                    self.save_group_states_only()
                    
                header.bind("<Button-1>", toggle_group)
                header.bind("<ButtonRelease-1>", on_drop)

                grp_context_menu = tk.Menu(header, tearoff=0, bg=self.entry_bg, fg=self.text_white, bd=0, activebackground=self.btn_hover)
                grp_context_menu.add_command(label=_("Đổi tên nhóm"), command=lambda g=grp: rename_group_dialog(g))

                def show_grp_context(event, menu=grp_context_menu):
                    menu.tk_popup(event.x_root, event.y_root)

                header.bind("<ButtonRelease-3>", show_grp_context)

            for comp in computers:
                card = tk.Frame(scrollable_frame, bg=self.card_color)
                card.comp_id = comp["id"].replace(" ", "")
                card.comp_name = comp["name"]
                card.comp_group = comp.get("group", "").strip()

                content_frame = tk.Frame(card, bg=self.card_color, pady=5, padx=12)
                content_frame.pack(fill=tk.X)
                
                separator = tk.Frame(card, bg=self.divider_color, height=2)
                separator.pack(fill=tk.X, padx=10)

                info_frame = tk.Frame(content_frame, bg=self.card_color)
                info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                clean_id = card.comp_id
                is_online = current_online.get(clean_id, False)
                dot_color = "#00F5D4" if is_online else "#8A8A9A"
                dot_lbl = tk.Label(info_frame, text="●", font=(APP_FONT_NAME, 13, "bold"), fg=dot_color, bg=self.card_color)
                dot_lbl.pack(side=tk.LEFT, padx=(0, 5))

                # ID label aligned to the right
                id_lbl = tk.Label(info_frame, text=f"ID: {comp['id']}", font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color, anchor=tk.E)
                id_lbl.pack(side=tk.RIGHT, padx=(0, 10))

                # Name label aligned to the left
                name_lbl = tk.Label(info_frame, text=comp["name"], font=(APP_FONT_NAME, 10, "bold"), fg=self.text_white, bg=self.card_color, anchor=tk.W)
                name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

                context_menu = tk.Menu(card, tearoff=0, bg=self.entry_bg, fg=self.text_white, bd=0, activebackground=self.btn_hover)
                context_menu.add_command(label=_("Kết nối"), command=lambda c=comp: connect_computer(c))
                context_menu.add_separator()
                context_menu.add_command(label=_("Thay đổi thông tin"), command=lambda c=comp: self.open_edit_computer_dialog(c, dialog, refresh_list))
                context_menu.add_command(label=_("Xóa máy tính"), command=lambda c=comp: delete_computer(c))

                def show_context_menu(event, menu=context_menu):
                    menu.tk_popup(event.x_root, event.y_root)
                        
                def start_drag(event, c_id=clean_id, c=comp):
                    self.drag_card_id = c_id
                    import time
                    now = time.time()
                    last = getattr(self, "_last_click_time", 0)
                    last_id = getattr(self, "_last_click_id", "")
                    if now - last < 0.5 and last_id == c_id:
                        connect_computer(c)
                    self._last_click_time = now
                    self._last_click_id = c_id

                for w in [card, content_frame, separator, info_frame, dot_lbl, name_lbl, id_lbl]:
                    w.bind("<Double-Button-1>", lambda e, c=comp: connect_computer(c))
                    w.bind("<ButtonRelease-3>", show_context_menu)
                    w.bind("<ButtonPress-1>", start_drag)
                    w.bind("<B1-Motion>", on_drag_motion)
                    w.bind("<ButtonRelease-1>", on_drop)
                    
                    try:
                        w.config(cursor="hand2")
                    except Exception:
                        pass

                if clean_id not in self.status_dots_widgets:
                    self.status_dots_widgets[clean_id] = []
                self.status_dots_widgets[clean_id].append(dot_lbl)
                self.query_computer_status(clean_id)
                
            reorder_list()

        # Bottom buttons panel
        bottom_frame = tk.Frame(dialog, bg=self.bg_color)
        bottom_frame.pack(fill=tk.X, padx=20, pady=(10, 15))

        def open_add_dialog():
            self.open_add_computer_dialog_with_vals("", "", parent_win=dialog, on_save=refresh_list)

        def start_refresh_cooldown():
            seconds_left = 30
            
            def update_timer():
                nonlocal seconds_left
                if seconds_left > 0:
                    btn_refresh.config(text=E(_("🔄 Làm mới")) + f" ({seconds_left}s)")
                    seconds_left -= 1
                    if dialog.winfo_exists():
                        dialog.after(1000, update_timer)
                else:
                    if dialog.winfo_exists():
                        btn_refresh.config(
                            state="normal", text=E(_("🔄 Làm mới")),
                            fg=self.text_white, bg="#2ECC71",
                            cursor="hand2"
                        )
                        
            btn_refresh.config(state="disabled", text=E(_("🔄 Làm mới (30s)")), bg="#2A2A35", fg="#8A8A9A", cursor="arrow")
            update_timer()

        btn_add = tk.Button(
            bottom_frame, text=_("+ Thêm Mới"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2", command=open_add_dialog
        )
        btn_add.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

        btn_refresh = tk.Button(
            bottom_frame, text=E(_("🔄 Làm mới")), font=EMOJI_FONT_BOLD,
            fg=self.text_white, bg="#2ECC71", activebackground="#27AE60",
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2",
            command=lambda: [refresh_list(), start_refresh_cooldown()]
        )
        btn_refresh.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        btn_close = tk.Button(
            bottom_frame, text=_("Đóng"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2", command=on_dialog_destroy
        )
        btn_close.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))

        # Pack list_container sau cùng để lấp đầy phần diện tích còn lại ở giữa Search Bar và Bottom Buttons!
        list_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        dialog.refresh_list_func = refresh_list
        refresh_list()

        def auto_refresh_status():
            if not dialog.winfo_exists(): return
            for clean_id in list(self.status_dots_widgets.keys()):
                self.query_computer_status(clean_id)
            dialog.after(10000, auto_refresh_status)

        dialog.after(10000, auto_refresh_status)

        # Hiển thị mượt mà bằng cách ẩn độ mờ trước, đợi Tk vẽ xong rồi mới hiện lên
        dialog.attributes("-alpha", 0.0)
        dialog.deiconify()
        def _show_initial():
            if dialog.winfo_exists():
                dialog.attributes("-alpha", 1.0)
                dialog.lift()
                dialog.focus_force()
        dialog.after(50, _show_initial)


    def add_current_partner_to_saved(self):
        curr_id = self.partner_id_var.get().strip()
        curr_pass = self.partner_pass_var.get().strip()
        self.open_add_computer_dialog_with_vals(curr_id, curr_pass)


    def open_add_computer_dialog_with_vals(self, initial_id="", initial_pass="", parent_win=None, on_save=None):
        parent = parent_win if parent_win else self
        
        add_win = tk.Toplevel(parent)
        add_win.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy
        add_win.title(_("Thêm Máy tính"))
        add_win.resizable(False, False)
        add_win.configure(bg=self.bg_color)
        add_win.transient(parent)
        add_win.grab_set()

        # Center add window
        add_win.update_idletasks()
        aw = 320
        ah = 360
        ax = parent.winfo_x() + (parent.winfo_width() - aw) // 2
        ay = parent.winfo_y() + (parent.winfo_height() - ah) // 2
        add_win.geometry(f"{aw}x{ah}+{ax}+{ay}")
        add_win.deiconify()  # Chỉ hiển thị sau khi đã tính toán căn giữa hoàn hảo!

        lbl_add_title = tk.Label(add_win, text=_("THÊM MÁY TÍNH MỚI"), font=(APP_FONT_NAME, 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_add_title.pack(pady=(12, 10))

        lbl_name = tk.Label(add_win, text=_("Tên gọi gợi nhớ:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_name.pack(anchor=tk.W, padx=20)
        entry_name = tk.Entry(add_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_name.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_name.focus()

        lbl_comp_id = tk.Label(add_win, text=_("ID đối tác:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_id.pack(anchor=tk.W, padx=20)
        entry_comp_id = tk.Entry(add_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_id.pack(fill=tk.X, padx=20, pady=(3, 8))
        if initial_id:
            entry_comp_id.insert(0, initial_id)

        lbl_comp_pass = tk.Label(add_win, text=_("Mật khẩu:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_pass.pack(anchor=tk.W, padx=20)
        entry_comp_pass = tk.Entry(add_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_pass.pack(fill=tk.X, padx=20, pady=(3, 8))
        if initial_pass:
            entry_comp_pass.insert(0, initial_pass)

        lbl_group = tk.Label(add_win, text=_("Nhóm (Tùy chọn):"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_group.pack(anchor=tk.W, padx=20)
        entry_group = tk.Entry(add_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_group.pack(fill=tk.X, padx=20, pady=(3, 12))

        def load_computers():
            return self.load_saved_computers()

        def save_computers(lst):
            self.save_saved_computers(lst)

        def save_new():
            name = entry_name.get().strip()
            cid = entry_comp_id.get().strip()
            cpass = entry_comp_pass.get().strip()
            cgroup = entry_group.get().strip()

            if not name or not cid or not cpass:
                self.show_custom_error(_("Lỗi nhập liệu"), _("Vui lòng điền đầy đủ các thông tin!"), parent=add_win)
                return

            computers = load_computers()
            for c in computers:
                if c["id"] == cid and c["name"] == name:
                    self.show_custom_error(_("Trùng lặp"), _("Máy tính này đã tồn tại trong danh sách!"), parent=add_win)
                    return

            computers.append({
                "name": name,
                "id": cid,
                "password": cpass,
                "group": cgroup
            })
            save_computers(computers)
            if on_save:
                on_save()
            if not parent_win:
                self.show_custom_info(_("Thành công"), _("Đã lưu máy tính '{name}' vào danh sách thành công!").replace("{name}", name), parent=add_win)
            add_win.destroy()

        btn_add_frame = tk.Frame(add_win, bg=self.bg_color)
        btn_add_frame.pack(fill=tk.X, padx=20, pady=5)

        btn_save = tk.Button(
            btn_add_frame, text=_("Lưu lại"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=save_new
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_add_frame, text=_("Hủy bỏ"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=add_win.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))


    def open_edit_computer_dialog(self, item, parent_win, on_save):
        parent = parent_win
        
        edit_win = tk.Toplevel(parent)
        edit_win.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy
        edit_win.title(_("Sửa thông tin"))
        edit_win.resizable(False, False)
        edit_win.configure(bg=self.bg_color)
        edit_win.transient(parent)
        edit_win.grab_set()

        # Center edit window
        edit_win.update_idletasks()
        ew = 320
        eh = 360
        ex = parent.winfo_x() + (parent.winfo_width() - ew) // 2
        ey = parent.winfo_y() + (parent.winfo_height() - eh) // 2
        edit_win.geometry(f"{ew}x{eh}+{ex}+{ey}")
        edit_win.deiconify()  # Chỉ hiển thị sau khi đã tính toán căn giữa hoàn hảo!

        lbl_edit_title = tk.Label(edit_win, text=_("CẬP NHẬT THÔNG TIN"), font=(APP_FONT_NAME, 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_edit_title.pack(pady=(12, 10))

        lbl_name = tk.Label(edit_win, text=_("Tên gọi gợi nhớ:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_name.pack(anchor=tk.W, padx=20)
        entry_name = tk.Entry(edit_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_name.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_name.insert(0, item["name"])
        entry_name.focus()

        lbl_comp_id = tk.Label(edit_win, text=_("ID đối tác:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_id.pack(anchor=tk.W, padx=20)
        entry_comp_id = tk.Entry(edit_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_id.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_comp_id.insert(0, item["id"])

        lbl_comp_pass = tk.Label(edit_win, text=_("Mật khẩu mới:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_pass.pack(anchor=tk.W, padx=20)
        entry_comp_pass = tk.Entry(edit_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_pass.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_comp_pass.insert(0, item["password"])

        lbl_group = tk.Label(edit_win, text=_("Nhóm (Tùy chọn):"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_group.pack(anchor=tk.W, padx=20)
        entry_group = tk.Entry(edit_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_group.pack(fill=tk.X, padx=20, pady=(3, 12))
        entry_group.insert(0, item.get("group", ""))

        def load_computers():
            return self.load_saved_computers()

        def save_computers(lst):
            self.save_saved_computers(lst)

        def save_edit():
            name = entry_name.get().strip()
            new_id = entry_comp_id.get().strip()
            cpass = entry_comp_pass.get().strip()
            cgroup = entry_group.get().strip()

            if not name or not new_id or not cpass:
                self.show_custom_error(_("Lỗi nhập liệu"), _("Vui lòng điền đầy đủ các thông tin!"), parent=edit_win)
                return

            computers = load_computers()
            updated = False
            for c in computers:
                if c["id"] == item["id"] and c["name"] == item["name"]:
                    c["name"] = name
                    c["id"] = new_id
                    c["password"] = cpass
                    c["group"] = cgroup
                    updated = True
                    break
            
            if updated:
                save_computers(computers)
                if on_save:
                    on_save()
                edit_win.destroy()
            else:
                self.show_custom_error(_("Lỗi"), _("Không tìm thấy máy tính tương ứng để sửa!"), parent=edit_win)

        btn_edit_frame = tk.Frame(edit_win, bg=self.bg_color)
        btn_edit_frame.pack(fill=tk.X, padx=20, pady=5)

        btn_save = tk.Button(
            btn_edit_frame, text=_("Lưu lại"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=save_edit
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_edit_frame, text=_("Hủy bỏ"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=edit_win.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))


    def load_lan_peers(self):
        lan_file = "lan_peers.json"
        if os.path.exists(lan_file):
            try:
                with open(lan_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data
            except:
                pass
        return {}


    def save_lan_peers(self):
        lan_file = "lan_peers.json"
        try:
            with open(lan_file, 'w', encoding='utf-8') as f:
                with self.lan_peers_lock:
                    json.dump(self.lan_peers, f, ensure_ascii=False, indent=4)
        except:
            pass


    def load_saved_computers(self):
        computers_file = get_computers_xml_path()
        import xml.etree.ElementTree as ET
        lst = []
        if os.path.exists(computers_file):
            try:
                tree = ET.parse(computers_file)
                root = tree.getroot()
                for comp_node in root.findall("computer"):
                    name_node = comp_node.find("name")
                    id_node = comp_node.find("id")
                    pass_node = comp_node.find("password")
                    group_node = comp_node.find("group")
                    
                    name = decrypt_text(name_node.text) if name_node is not None else ""
                    cid = decrypt_text(id_node.text) if id_node is not None else ""
                    cpass = decrypt_text(pass_node.text) if pass_node is not None else ""
                    cgroup = decrypt_text(group_node.text) if group_node is not None else ""
                    
                    if cid:
                        lst.append({
                            "name": name,
                            "id": cid,
                            "password": cpass,
                            "group": cgroup
                        })
                        
                if not hasattr(self, 'collapsed_groups_loaded'):
                    self.collapsed_groups = set()
                    self.collapsed_groups_loaded = True
                    gs_node = root.find("group_states")
                    if gs_node is not None:
                        for g_node in gs_node.findall("collapsed_group"):
                            self.collapsed_groups.add(decrypt_text(g_node.text) if g_node.text else "")
            except Exception as e:
                print(f"[Config] Lỗi tải XML: {e}")
        return lst


    def save_saved_computers(self, lst):
        computers_file = get_computers_xml_path()
        import xml.etree.ElementTree as ET
        try:
            fixed_node = None
            zalo_node = None
            if os.path.exists(computers_file):
                try:
                    tree = ET.parse(computers_file)
                    root = tree.getroot()
                    fixed_node = root.find("fixed_password")
                    zalo_node = root.find("zalo_phone")
                except:
                    pass
            
            root = ET.Element("computers")
            
            if fixed_node is not None:
                root.append(fixed_node)
            if zalo_node is not None:
                root.append(zalo_node)
                
            if hasattr(self, 'collapsed_groups'):
                gs_node = ET.SubElement(root, "group_states")
                for grp in self.collapsed_groups:
                    g_node = ET.SubElement(gs_node, "collapsed_group")
                    g_node.text = encrypt_text(grp)
                

            for comp in lst:
                comp_node = ET.SubElement(root, "computer")
                name_node = ET.SubElement(comp_node, "name")
                name_node.text = encrypt_text(comp["name"])
                
                id_node = ET.SubElement(comp_node, "id")
                id_node.text = encrypt_text(comp["id"])
                
                pass_node = ET.SubElement(comp_node, "password")
                pass_node.text = encrypt_text(comp["password"])
                
                group_node = ET.SubElement(comp_node, "group")
                group_node.text = encrypt_text(comp.get("group", ""))
                
            if hasattr(ET, "indent"):
                ET.indent(root, space="  ")
                
            tree = ET.ElementTree(root)
            tree.write(computers_file, encoding="utf-8", xml_declaration=True)
        except Exception as e:
            print(f"[Config] Lỗi lưu XML: {e}")
            if hasattr(self, 'show_custom_error'):
                self.after(0, lambda err=str(e): self.show_custom_error(_("Lỗi lưu file"), _("Không thể lưu danh sách máy tính. Vui lòng kiểm tra quyền ghi tệp (Administrator/Root)!\nChi tiết: {err}").format(err=err)))


    def save_group_states_only(self):
        computers_file = get_computers_xml_path()
        if not os.path.exists(computers_file):
            return
        import xml.etree.ElementTree as ET
        try:
            tree = ET.parse(computers_file)
            root = tree.getroot()
            old_gs = root.find("group_states")
            if old_gs is not None:
                root.remove(old_gs)
            if hasattr(self, 'collapsed_groups'):
                gs_node = ET.SubElement(root, "group_states")
                for grp in self.collapsed_groups:
                    g_node = ET.SubElement(gs_node, "collapsed_group")
                    g_node.text = encrypt_text(grp)
            if hasattr(ET, "indent"):
                ET.indent(root, space="  ")
            tree.write(computers_file, encoding="utf-8", xml_declaration=True)
        except:
            pass


    def load_fixed_password_from_xml(self):
        computers_file = get_computers_xml_path()
        if os.path.exists(computers_file):
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(computers_file)
                root = tree.getroot()
                fixed_node = root.find("fixed_password")
                if fixed_node is not None and fixed_node.text:
                    return decrypt_text(fixed_node.text)
            except Exception as e:
                print(f"[Config] Lỗi đọc mật khẩu cố định từ XML: {e}")
        return ""


    def save_fixed_password_to_xml(self, password):
        computers_file = get_computers_xml_path()
        import xml.etree.ElementTree as ET
        
        computers = []
        zalo_node_text = ""
        if os.path.exists(computers_file):
            try:
                tree = ET.parse(computers_file)
                root = tree.getroot()
                for comp_node in root.findall("computer"):
                    name_node = comp_node.find("name")
                    id_node = comp_node.find("id")
                    pass_node = comp_node.find("password")
                    computers.append({
                        "name": name_node.text if name_node is not None else "",
                        "id": id_node.text if id_node is not None else "",
                        "password": pass_node.text if pass_node is not None else ""
                    })
                z_node = root.find("zalo_phone")
                if z_node is not None:
                    zalo_node_text = z_node.text
            except:
                pass
                
        root = ET.Element("computers")
        
        if password:
            fixed_node = ET.SubElement(root, "fixed_password")
            fixed_node.text = encrypt_text(password)
            
        if zalo_node_text:
            z_node = ET.SubElement(root, "zalo_phone")
            z_node.text = zalo_node_text
            
        for comp in computers:
            comp_node = ET.SubElement(root, "computer")
            name_node = ET.SubElement(comp_node, "name")
            name_node.text = comp["name"]
            
            id_node = ET.SubElement(comp_node, "id")
            id_node.text = comp["id"]
            
            pass_node = ET.SubElement(comp_node, "password")
            pass_node.text = comp["password"]
            
        if hasattr(ET, "indent"):
            ET.indent(root, space="  ")
            
        try:
            tree = ET.ElementTree(root)
            tree.write(computers_file, encoding="utf-8", xml_declaration=True)
        except Exception as e:
            print(f"[Config] Lỗi lưu XML: {e}")


    def save_fixed_password(self, password):
        self.fixed_password = password
        self.save_fixed_password_to_xml(password)


    def load_zalo_phone_from_xml(self):
        computers_file = get_computers_xml_path()
        if os.path.exists(computers_file):
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(computers_file)
                root = tree.getroot()
                zalo_node = root.find("zalo_phone")
                if zalo_node is not None and zalo_node.text:
                    return zalo_node.text
            except Exception as e:
                print(f"[Config] Lỗi đọc Zalo/Điện thoại từ XML: {e}")
        return ""


    def save_zalo_phone_to_xml(self, value):
        computers_file = get_computers_xml_path()
        import xml.etree.ElementTree as ET
        
        computers = []
        fixed_node_text = ""
        if os.path.exists(computers_file):
            try:
                tree = ET.parse(computers_file)
                root = tree.getroot()
                for comp_node in root.findall("computer"):
                    name_node = comp_node.find("name")
                    id_node = comp_node.find("id")
                    pass_node = comp_node.find("password")
                    computers.append({
                        "name": name_node.text if name_node is not None else "",
                        "id": id_node.text if id_node is not None else "",
                        "password": pass_node.text if pass_node is not None else ""
                    })
                f_node = root.find("fixed_password")
                if f_node is not None:
                    fixed_node_text = f_node.text
            except:
                pass
                
        root = ET.Element("computers")
        
        if fixed_node_text:
            f_node = ET.SubElement(root, "fixed_password")
            f_node.text = fixed_node_text
            
        if value:
            zalo_node = ET.SubElement(root, "zalo_phone")
            zalo_node.text = value
            
        for comp in computers:
            comp_node = ET.SubElement(root, "computer")
            name_node = ET.SubElement(comp_node, "name")
            name_node.text = comp["name"]
            
            id_node = ET.SubElement(comp_node, "id")
            id_node.text = comp["id"]
            
            pass_node = ET.SubElement(comp_node, "password")
            pass_node.text = comp["password"]
            
        if hasattr(ET, "indent"):
            ET.indent(root, space="  ")
            
        try:
            tree = ET.ElementTree(root)
            tree.write(computers_file, encoding="utf-8", xml_declaration=True)
        except Exception as e:
            print(f"[Config] Lỗi lưu Zalo/Điện thoại vào XML: {e}")


    def open_set_zalo_phone_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title(_("Cài Zalo / Điện thoại"))
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        w = 340
        h = 220
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        lbl_title = tk.Label(dialog, text=_("CÀI ĐẶT ZALO / ĐIỆN THOẠI"), font=(APP_FONT_NAME, 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        desc_text = _("Nhập số điện thoại hoặc liên kết Zalo của bạn. Client điều khiển máy bạn có thể click Help -> Zalo để trực tiếp nhắn tin cho bạn.")
        lbl_desc = tk.Label(dialog, text=desc_text, font=(APP_FONT_NAME, 8, "italic"), fg=self.text_gray, bg=self.bg_color, justify=tk.CENTER, wraplength=320)
        lbl_desc.pack(pady=(0, 10))

        entry_frame = tk.Frame(dialog, bg=self.bg_color)
        entry_frame.pack(fill=tk.X, padx=30)

        entry_val = tk.Entry(entry_frame, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_val.pack(fill=tk.X, pady=(0, 15))
        
        current_val = self.load_zalo_phone_from_xml()
        if current_val:
            entry_val.insert(0, current_val)
        entry_val.focus()

        def save_val():
            new_val = entry_val.get().strip()
            self.save_zalo_phone_to_xml(new_val)
            self.show_custom_info(_("Thành công"), _("Đã lưu thông tin liên hệ Zalo / Điện thoại thành công!"), parent=dialog)
            dialog.destroy()

        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=30, pady=5)

        btn_save = tk.Button(
            btn_frame, text=_("Lưu lại"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=save_val
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_frame, text=_("Hủy bỏ"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))


    def show_server_settings_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title(_("Cài đặt Máy chủ (Signaling Server)"))
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.transient(self)
        dialog.grab_set()

        dialog.update_idletasks()
        w = 360
        h = 320
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        lbl_title = tk.Label(dialog, text=_("CẤU HÌNH MÁY CHỦ SIGNALING"), font=(APP_FONT_NAME, 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        desc_text = _("Nhập danh sách tên miền hoặc IP máy chủ (Cách nhau bằng dấu phẩy để dự phòng)")
        lbl_desc = tk.Label(dialog, text=desc_text, font=(APP_FONT_NAME, 8, "italic"), fg=self.text_gray, bg=self.bg_color, justify=tk.CENTER, wraplength=350)
        lbl_desc.pack(pady=(0, 10))

        form_frame = tk.Frame(dialog, bg=self.bg_color)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=30)

        lbl_hosts = tk.Label(form_frame, text=_("Danh sách Máy chủ:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_hosts.pack(anchor=tk.W)
        
        entry_hosts = tk.Entry(form_frame, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_hosts.pack(fill=tk.X, pady=(3, 10))
        
        lbl_port = tk.Label(form_frame, text=_("Cổng kết nối (Port):"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_port.pack(anchor=tk.W)
        
        entry_port = tk.Entry(form_frame, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_port.pack(fill=tk.X, pady=(3, 15))


        current_hosts = ", ".join(SIGNALING_SERVER_HOSTS)
        entry_hosts.insert(0, current_hosts)
        entry_port.insert(0, str(SIGNALING_SERVER_PORT))
        
        entry_hosts.focus()

        def save_config():
            new_hosts_str = entry_hosts.get().strip()
            new_port_str = entry_port.get().strip()
            
            if not new_hosts_str or not new_port_str:
                self.show_custom_error(_("Lỗi"), _("Vui lòng nhập đầy đủ thông tin!"), parent=dialog)
                return
                
            try:
                new_port = int(new_port_str)
            except ValueError:
                self.show_custom_error(_("Lỗi"), _("Cổng kết nối (Port) phải là số!"), parent=dialog)
                return
                
            global SIGNALING_SERVER_HOSTS, SIGNALING_SERVER_PORT
            SIGNALING_SERVER_HOSTS = [h.strip() for h in new_hosts_str.split(',') if h.strip()]
            SIGNALING_SERVER_PORT = new_port
            
            try:
                import configparser
                config = configparser.ConfigParser()
                config.read('server.ini', encoding='utf-8')
                if 'server' not in config:
                    config.add_section('server')
                config['server']['host'] = new_hosts_str
                config['server']['port'] = str(new_port)
                with open('server.ini', 'w', encoding='utf-8') as f:
                    config.write(f)
                
                self.show_custom_info(_("Thành công"), _("Đã cập nhật máy chủ thành công!\nỨng dụng sẽ sử dụng cấu hình mới cho các kết nối tiếp theo."), parent=dialog)
                dialog.destroy()
            except Exception as e:
                self.show_custom_error(_("Lỗi"), _("Không thể lưu file server.ini: ") + str(e), parent=dialog)

        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=30, pady=10)
        
        btn_save = tk.Button(
            btn_frame, text=_("Lưu lại"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=save_config
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        
        btn_cancel = tk.Button(
            btn_frame, text=_("Hủy bỏ"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))


    def update_fixed_password_indicator(self):
        if hasattr(self, 'fixed_pass_indicator'):
            if self.fixed_password:
                self.fixed_pass_indicator.config(text=_("● Mật khẩu cố định: Đang hoạt động"))
            else:
                self.fixed_pass_indicator.config(text="")


    def open_set_fixed_password_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title(_("Mật khẩu cố định"))
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        w = 340
        h = 240
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        lbl_title = tk.Label(dialog, text=_("CÀI ĐẶT MẬT KHẨU CỐ ĐỊNH"), font=(APP_FONT_NAME, 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        desc_text = _("Đặt mật khẩu cố định giúp đối tác kết nối vào máy của bạn mà không cần hỏi mật khẩu ngẫu nhiên. (Để trống để tắt tính năng này)")
        lbl_desc = tk.Label(dialog, text=desc_text, font=(APP_FONT_NAME, 8, "italic"), fg=self.text_gray, bg=self.bg_color, justify=tk.CENTER, wraplength=350)
        lbl_desc.pack(pady=(0, 10))

        # Entry and show password check
        entry_frame = tk.Frame(dialog, bg=self.bg_color)
        entry_frame.pack(fill=tk.X, padx=30)

        show_pass = tk.BooleanVar(value=False)
        
        entry_pass = tk.Entry(entry_frame, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, show="*", insertbackground=self.text_white)
        entry_pass.pack(fill=tk.X, pady=(0, 5))
        if self.fixed_password:
            entry_pass.insert(0, self.fixed_password)

        def toggle_password():
            if show_pass.get():
                entry_pass.config(show="")
            else:
                entry_pass.config(show="*")

        chk_show = tk.Checkbutton(
            dialog, text=_("Hiển thị mật khẩu"), font=(APP_FONT_NAME, 8),
            variable=show_pass, onvalue=True, offvalue=False,
            command=toggle_password, bg=self.bg_color, fg=self.text_gray,
            activebackground=self.bg_color, activeforeground=self.text_white,
            selectcolor=self.bg_color, bd=0, highlightthickness=0
        )
        chk_show.pack(pady=(0, 15))

        def save_password():
            new_pass = entry_pass.get().strip()
            self.save_fixed_password(new_pass)
            self.update_fixed_password_indicator()
            
            if new_pass:
                self.show_custom_info(_("Thành công"), _("Đã lưu mật khẩu cố định thành công!"), parent=dialog)
            else:
                self.show_custom_info(_("Thành công"), _("Đã tắt mật khẩu cố định thành công!"), parent=dialog)
            dialog.destroy()

        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=30, pady=(5, 10))

        btn_save = tk.Button(
            btn_frame, text=_("Lưu lại"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=save_password
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_frame, text=_("Hủy bỏ"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))


    def is_startup_enabled(self):
        if sys.platform != "win32":
            import os
            autostart_path = os.path.expanduser("~/.config/autostart/RemoteDesktopP2P.desktop")
            return os.path.exists(autostart_path)
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key_name = "RemoteDesktopP2P"
        approved_key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            try:
                value, _type = winreg.QueryValueEx(key, key_name)
                winreg.CloseKey(key)
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
            
            # Check if StartupApproved has disabled it (Windows 11)
            try:
                approved_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, approved_key_path, 0, winreg.KEY_READ)
                approved_val, _type = winreg.QueryValueEx(approved_key, key_name)
                winreg.CloseKey(approved_key)
                # First byte: 02=enabled, 03/06=disabled
                if isinstance(approved_val, bytes) and len(approved_val) >= 1 and approved_val[0] != 0x02:
                    return False
            except FileNotFoundError:
                pass  # No approved entry = not blocked
            except Exception:
                pass
            
            return True
        except Exception:
            return False


    def toggle_startup(self):
        import sys
        import os
        
        enabled = self.startup_var.get()

        if sys.platform != "win32":
            autostart_dir = os.path.expanduser("~/.config/autostart")
            autostart_path = os.path.join(autostart_dir, "RemoteDesktopP2P.desktop")
            if enabled:
                try:
                    os.makedirs(autostart_dir, exist_ok=True)
                    if getattr(sys, 'frozen', False):
                        exe_path = sys.executable
                    else:
                        exe_path = f'{sys.executable} "{os.path.abspath(sys.argv[0])}"'
                    
                    desktop_entry = f"""[Desktop Entry]
Type=Application
Exec={exe_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=Easy Remote Desktop
Comment=Remote Desktop P2P AutoStart
"""
                    with open(autostart_path, "w") as f:
                        f.write(desktop_entry)
                    os.chmod(autostart_path, 0o755)
                    self.show_custom_info(_("Thành công"), _("Đã bật tính năng chạy khi mở máy thành công!"))
                except Exception as e:
                    print(f"[Startup] Failed to create autostart entry: {e}")
                    self.show_custom_error(_("Thất bại"), _("Không thể thay đổi cài đặt autostart: ") + str(e))
                    self.startup_var.set(False)
            else:
                try:
                    if os.path.exists(autostart_path):
                        os.remove(autostart_path)
                    self.show_custom_info(_("Thành công"), _("Đã tắt tính năng chạy khi mở máy thành công!"))
                except Exception as e:
                    print(f"[Startup] Failed to remove autostart entry: {e}")
                    self.show_custom_error(_("Thất bại"), _("Không thể thay đổi cài đặt autostart: ") + str(e))
                    self.startup_var.set(True)
            return

        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key_name = "RemoteDesktopP2P"
        approved_key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
        
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            exe_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
            
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enabled:
                winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, exe_path)
                # Mark as Enabled in StartupApproved (required for Windows 11)
                try:
                    approved_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, approved_key_path)
                    # 12 bytes: first byte 02 = enabled
                    enabled_value = b'\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    winreg.SetValueEx(approved_key, key_name, 0, winreg.REG_BINARY, enabled_value)
                    winreg.CloseKey(approved_key)
                    print("[Startup] Set StartupApproved = Enabled for Windows 11")
                except Exception as e:
                    print(f"[Startup] Warning: Could not set StartupApproved: {e}")
                print(f"[Startup] Enabled run on startup: {exe_path}")
                self.show_custom_info(_("Thành công"), _("Đã bật tính năng chạy khi mở máy thành công!"))
            else:
                try:
                    winreg.DeleteValue(key, key_name)
                except FileNotFoundError:
                    pass
                # Also remove from StartupApproved
                try:
                    approved_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, approved_key_path, 0, winreg.KEY_ALL_ACCESS)
                    winreg.DeleteValue(approved_key, key_name)
                    winreg.CloseKey(approved_key)
                except Exception:
                    pass
                self.show_custom_info(_("Thành công"), _("Đã tắt tính năng chạy khi mở máy thành công!"))
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[Startup] Failed to modify registry: {e}")
            self.show_custom_error(_("Thất bại"), _("Không thể thay đổi cài đặt Registry: ") + str(e))
            self.startup_var.set(not enabled)



    def open_zalo(self):
        import webbrowser
        
        # Clean up dead viewer processes
        self.active_viewers = [v for v in self.active_viewers if v["process"].is_alive()]
        
        phone_val = ""
        comp_name = ""
        
        if len(self.active_viewers) == 1:
            phone_val = self.active_viewers[0]["zalo_phone"]
            comp_name = self.active_viewers[0]["computer_name"]
        elif len(self.active_viewers) > 1:
            # Multiple active sessions
            dialog = tk.Toplevel(self)
            dialog.title(_("Liên hệ Zalo"))
            dialog.resizable(False, False)
            dialog.configure(bg=self.bg_color)
            dialog.transient(self)
            dialog.grab_set()
            
            # Center dialog
            dialog.update_idletasks()
            w = 340
            h = 80 + len(self.active_viewers) * 45
            x = self.winfo_x() + (self.winfo_width() - w) // 2
            y = self.winfo_y() + (self.winfo_height() - h) // 2
            dialog.geometry(f"{w}x{h}+{x}+{y}")
            
            lbl_title = tk.Label(dialog, text=_("CHỌN ĐỐI TÁC ĐỂ LIÊN HỆ ZALO"), font=(APP_FONT_NAME, 10, "bold"), fg=self.btn_color, bg=self.bg_color)
            lbl_title.pack(pady=(12, 10))
            
            for v in self.active_viewers:
                c_name = v["computer_name"] or _("Không rõ")
                p_val = v["zalo_phone"]
                display_text = f"{c_name} ({p_val if p_val else _('Không có số')})"
                
                def contact(val=p_val, name=c_name):
                    dialog.destroy()
                    if val:
                        webbrowser.open(f"https://zalo.me/{val}")
                    else:
                        self.show_zalo_error_popup(name)
                        
                btn = tk.Button(
                    dialog, text=display_text, font=(APP_FONT_NAME, 9),
                    fg=self.text_white, bg=self.card_color, activebackground=self.entry_bg,
                    relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=contact
                )
                btn.pack(fill=tk.X, padx=30, pady=4)
            return
        else:
            phone_val = self.load_zalo_phone_from_xml()
            comp_name = ""
            
        if phone_val:
            webbrowser.open(f"https://zalo.me/{phone_val}")
        else:
            self.show_zalo_error_popup(comp_name)


    def show_zalo_error_popup(self, comp_name=""):
        dialog = tk.Toplevel(self)
        dialog.title(_("Liên hệ Zalo"))
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        w = 340
        h = 160
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        title_text = _("LIÊN HỆ ZALO")
        if comp_name:
            title_text = _("ZALO:") + f" {comp_name.upper()}"
            
        lbl_title = tk.Label(dialog, text=title_text, font=(APP_FONT_NAME, 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        lbl_phone = tk.Label(dialog, text=_("Chưa có liên lạc"), font=(APP_FONT_NAME, 16, "bold"), fg="#2ECC71", bg=self.entry_bg, bd=0, height=1, width=20)
        lbl_phone.pack(pady=(5, 15))

        btn_ok = tk.Button(
            dialog, text=_("Đóng"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, width=12, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_ok.pack()


    def open_phone_dialog(self):
        # Get phone number
        self.active_viewers = [v for v in self.active_viewers if v["process"].is_alive()]
        
        phone_val = ""
        comp_name = ""
        
        if len(self.active_viewers) == 1:
            phone_val = self.active_viewers[0]["zalo_phone"]
            comp_name = self.active_viewers[0]["computer_name"]
        elif len(self.active_viewers) > 1:
            # Let them select which computer's phone number to view
            dialog = tk.Toplevel(self)
            dialog.title(_("Chọn đối tác"))
            dialog.resizable(False, False)
            dialog.configure(bg=self.bg_color)
            dialog.transient(self)
            dialog.grab_set()
            
            # Center dialog
            dialog.update_idletasks()
            w = 340
            h = 80 + len(self.active_viewers) * 45
            x = self.winfo_x() + (self.winfo_width() - w) // 2
            y = self.winfo_y() + (self.winfo_height() - h) // 2
            dialog.geometry(f"{w}x{h}+{x}+{y}")
            
            lbl_title = tk.Label(dialog, text=_("CHỌN ĐỐI TÁC XEM ĐIỆN THOẠI"), font=(APP_FONT_NAME, 10, "bold"), fg=self.btn_color, bg=self.bg_color)
            lbl_title.pack(pady=(12, 10))
            
            for v in self.active_viewers:
                c_name = v["computer_name"] or _("Không rõ")
                p_val = v["zalo_phone"]
                display_text = f"{c_name} ({p_val if p_val else _('Không có số')})"
                
                def show_phone(val=p_val, name=c_name):
                    dialog.destroy()
                    self.show_phone_number_popup(val, name)
                    
                btn = tk.Button(
                    dialog, text=display_text, font=(APP_FONT_NAME, 9),
                    fg=self.text_white, bg=self.card_color, activebackground=self.entry_bg,
                    relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=show_phone
                )
                btn.pack(fill=tk.X, padx=30, pady=4)
            return
        else:
            phone_val = self.load_zalo_phone_from_xml()
            comp_name = ""
            
        self.show_phone_number_popup(phone_val, comp_name)


    def show_phone_number_popup(self, phone_val, comp_name=""):
        dialog = tk.Toplevel(self)
        dialog.title(_("Điện thoại liên hệ"))
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        w = 340
        h = 160
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        title_text = _("SỐ ĐIỆN THOẠI LIÊN HỆ")
        if comp_name:
            title_text = _("ĐIỆN THOẠI:") + f" {comp_name.upper()}"
            
        lbl_title = tk.Label(dialog, text=title_text, font=(APP_FONT_NAME, 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        display_text = phone_val if phone_val else _("Chưa có liên lạc")
        lbl_phone = tk.Label(dialog, text=display_text, font=(APP_FONT_NAME, 16, "bold"), fg="#2ECC71", bg=self.entry_bg, bd=0, height=1, width=20)
        lbl_phone.pack(pady=(5, 15))

        btn_ok = tk.Button(
            dialog, text=_("Đóng"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, width=12, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_ok.pack()


    def show_about_dialog(self):
        # Tạo cửa sổ Toplevel mới đóng vai trò Modal
        about = tk.Toplevel(self)
        about.title(_("About"))
        about.resizable(False, False)
        about.configure(bg=self.bg_color)
        
        # Thiết lập thuộc tính Modal (nổi lên trên cửa sổ chính và chặn tương tác bên ngoài)
        about.transient(self)
        about.grab_set()
        
        # Thiết kế giao diện premium cho dialog About
        title_label = tk.Label(about, text="Easy Remote Desktop", font=("Inter", 13, "bold"), fg=self.text_white, bg=self.bg_color)
        title_label.pack(pady=(15, 2))
        
        ai_label = tk.Label(about, text=_("AI Pro Version"), font=("Inter", 9, "bold"), fg=self.btn_color, bg=self.bg_color)
        ai_label.pack(pady=(0, 5))
        
        contact_label = tk.Label(about, text=_("Liên hệ: Mr. Tuyến - 0941 261 771"), font=("Inter", 10), fg=self.text_gray, bg=self.bg_color)
        contact_label.pack(pady=(0, 15))
        
        close_btn = tk.Button(about, text=_("Đóng"), font=("Inter", 9, "bold"), fg=self.text_white, bg="#E05252", 
                              activeforeground=self.text_white, activebackground="#C04242",
                              bd=0, padx=25, pady=6, cursor="hand2", command=about.destroy)
        close_btn.pack(pady=(0, 15))
        
        # Cập nhật layout để lấy kích thước hình học chính xác
        about.update_idletasks()
        
        # Kích thước cố định của dialog About
        dialog_w = 320
        dialog_h = 175
        
        # Lấy thông số tọa độ và kích thước của cửa sổ chính UnifiedApp
        parent_x = self.winfo_x()
        parent_y = self.winfo_y()
        parent_w = self.winfo_width()
        parent_h = self.winfo_height()
        
        # Tính toán tọa độ x, y để căn chính xác giữa cửa sổ chính
        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2
        
        # Áp dụng hình học hình chữ nhật căn giữa
        about.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        
        # Khóa tương tác của luồng cho đến khi Modal đóng
        self.wait_window(about)


    def query_computer_status(self, clean_id):
        if clean_id == self.my_id_clean:
            self.update_saved_computer_status(clean_id, True)
            return

        sock = getattr(self, 'primary_signaling_socket', None)
        if sock:
            try:
                print(f"[StatusQuery] Đang gửi yêu cầu kiểm tra trạng thái ID: {clean_id}")
                req = json.dumps({"action": "check_online", "target": clean_id})
                with self.signaling_lock:
                    send_msg(sock, req.encode('utf-8'), APP_KEY)
                
                # Sau 1.5s nếu đèn LED vẫn là màu xám (chưa có phản hồi) thì tự động chuyển sang màu đỏ (Offline)
                self.after(1500, lambda cid=clean_id: self.check_and_default_offline(cid))
            except Exception as e:
                print(f"[StatusQuery] Lỗi gửi yêu cầu status {clean_id}: {e}")
                self.update_saved_computer_status(clean_id, False)
        else:
            print(f"[StatusQuery] Chưa kết nối Signaling, mặc định {clean_id} là Offline")
            self.update_saved_computer_status(clean_id, False)


    def check_and_default_offline(self, clean_id):
        if clean_id in self.status_dots_widgets:
            widgets = self.status_dots_widgets[clean_id]
            for dot_widget in widgets:
                try:
                    if dot_widget.winfo_exists() and dot_widget.cget("fg") == "#8A8A9A":
                        dot_widget.config(fg="#E05252")  # Đỏ (Offline)
                except Exception:
                    pass
            if hasattr(self, '_reorder_saved_computers_func'):
                self.after(50, self._reorder_saved_computers_func)


    def update_saved_computer_status(self, partner_id, is_online):
        clean_id = partner_id.replace(" ", "")
        if clean_id in self.status_dots_widgets:
            widgets = self.status_dots_widgets[clean_id]
            status_changed = False
            for dot_widget in widgets:
                try:
                    if dot_widget.winfo_exists():
                        current_color = dot_widget.cget("fg")
                        new_color = "#00F5D4" if is_online else "#E05252"
                        if current_color != new_color:
                            dot_widget.config(fg=new_color)
                            status_changed = True
                except Exception:
                    pass
            if status_changed and hasattr(self, '_reorder_saved_computers_func'):
                self.after(50, self._reorder_saved_computers_func)

    def show_custom_info(self, title, message, parent=None, auto_close_sec=None):
        if getattr(self, 'is_headless', False):
            print(f"[Info] {title}: {message}")
            return
        import tkinter as tk
        p = parent if parent else self
        
        dialog = tk.Toplevel(p)
        dialog.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy ở góc trên bên trái màn hình
        dialog.title(title)
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.attributes("-topmost", True)
        dialog.transient(p)
        dialog.grab_set()
        
        # Center calculations relative to parent
        dialog.update_idletasks()
        w = 400
        h = 180
        x = p.winfo_x() + (p.winfo_width() - w) // 2
        y = p.winfo_y() + (p.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.deiconify()  # Chỉ hiển thị sau khi đã tính toán căn giữa hoàn hảo!
        
        # Content frame
        content_frame = tk.Frame(dialog, bg=self.bg_color)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 10))
        
        # Icon & Message side-by-side
        icon_lbl = tk.Label(content_frame, text="ℹ", font=(APP_FONT_NAME, 22), fg=self.btn_color, bg=self.bg_color)
        icon_lbl.pack(side=tk.LEFT, anchor=tk.N, padx=(0, 15), pady=(2, 0))
        
        msg_lbl = tk.Label(content_frame, text=message, font=(APP_FONT_NAME, 9), fg=self.text_white, bg=self.bg_color, wraplength=310, justify=tk.LEFT)
        msg_lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor=tk.N)
        
        # OK Button at bottom
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 12))
        
        btn_ok = tk.Button(
            btn_frame, text=_("OK"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, width=12, pady=3, cursor="hand2", command=dialog.destroy
        )
        btn_ok.pack(side=tk.RIGHT)
        
        if auto_close_sec is not None:
            def update_countdown(remaining):
                if not dialog.winfo_exists():
                    return
                if remaining > 0:
                    btn_ok.config(text=f"{_('OK')} ({remaining}s)")
                    if remaining % 2 == 0:
                        btn_ok.config(bg=self.btn_hover)
                    else:
                        btn_ok.config(bg=self.btn_color)
                    dialog.after(1000, update_countdown, remaining - 1)
                else:
                    dialog.destroy()
            update_countdown(auto_close_sec)
        
        # Đợi cho đến khi cửa sổ Modal này đóng để đồng bộ luồng chặn
        self.wait_window(dialog)


    def show_custom_error(self, title, message, parent=None):
        if getattr(self, 'is_headless', False):
            print(f"[Error] {title}: {message}", file=sys.stderr)
            return
        import tkinter as tk
        p = parent if parent else self
        
        dialog = tk.Toplevel(p)
        dialog.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy ở góc trên bên trái màn hình
        dialog.title(title)
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.attributes("-topmost", True)
        dialog.transient(p)
        dialog.grab_set()
        
        # Center calculations relative to parent
        dialog.update_idletasks()
        w = 400
        h = 180
        x = p.winfo_x() + (p.winfo_width() - w) // 2
        y = p.winfo_y() + (p.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.deiconify()  # Chỉ hiển thị sau khi đã tính toán căn giữa hoàn hảo!
        
        # Content frame
        content_frame = tk.Frame(dialog, bg=self.bg_color)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 10))
        
        # Icon & Message side-by-side
        icon_lbl = tk.Label(content_frame, text="⚠", font=(APP_FONT_NAME, 22), fg="#E05252", bg=self.bg_color)
        icon_lbl.pack(side=tk.LEFT, anchor=tk.N, padx=(0, 15), pady=(2, 0))
        
        msg_lbl = tk.Label(content_frame, text=message, font=(APP_FONT_NAME, 9), fg=self.text_white, bg=self.bg_color, wraplength=310, justify=tk.LEFT)
        msg_lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor=tk.N)
        
        # OK Button at bottom
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 12))
        
        btn_ok = tk.Button(
            btn_frame, text=_("OK"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg="#E05252", activebackground="#C0392B",
            relief=tk.FLAT, bd=0, width=8, pady=3, cursor="hand2", command=dialog.destroy
        )
        btn_ok.pack(side=tk.RIGHT)
        
        # Đợi cho đến khi cửa sổ Modal này đóng để đồng bộ luồng chặn
        self.wait_window(dialog)


    def _show_lan_error_dialog(self, public_ip=""):
        if getattr(self, 'is_headless', False):
            print("[LAN Error] Kết nối LAN thất bại - Firewall có thể đang chặn kết nối.")
            return
        import tkinter as tk

        dialog = tk.Toplevel(self)
        dialog.withdraw()
        dialog.title(_("Lỗi kết nối mạng LAN"))
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.attributes("-topmost", True)
        dialog.transient(self)
        dialog.grab_set()

        W = 460
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - W) // 2
        y = self.winfo_y() + (self.winfo_height() - 420) // 2
        dialog.geometry(f"{W}x420+{x}+{y}")
        dialog.deiconify()

        # ── HEADER ──────────────────────────────────────────────
        hdr = tk.Frame(dialog, bg="#C0392B", height=5)
        hdr.pack(fill=tk.X)

        title_frame = tk.Frame(dialog, bg=self.bg_color)
        title_frame.pack(fill=tk.X, padx=20, pady=(14, 0))

        tk.Label(title_frame, text="⚠", font=(APP_FONT_NAME, 22), fg="#E05252", bg=self.bg_color).pack(side=tk.LEFT, padx=(0, 10))
        title_col = tk.Frame(title_frame, bg=self.bg_color)
        title_col.pack(side=tk.LEFT, fill=tk.BOTH)
        tk.Label(title_col, text=_("Kết nối mạng LAN thất bại"), font=(APP_FONT_NAME, 12, "bold"),
                 fg="#E05252", bg=self.bg_color, anchor="w").pack(anchor="w")
        tk.Label(title_col, text=_("Cả hai máy cùng mạng nội bộ nhưng không kết nối được trực tiếp"),
                 font=(APP_FONT_NAME, 8), fg=self.text_gray, bg=self.bg_color, anchor="w").pack(anchor="w")

        # ── SEPARATOR ───────────────────────────────────────────
        tk.Frame(dialog, bg=self.divider_color, height=1).pack(fill=tk.X, padx=20, pady=(12, 0))

        # ── THÔNG TIN KỸ THUẬT ──────────────────────────────────
        info_frame = tk.Frame(dialog, bg=self.entry_bg, bd=0, highlightthickness=1, highlightbackground=self.divider_color)
        info_frame.pack(fill=tk.X, padx=20, pady=(12, 0))

        tk.Label(info_frame, text=E(_("📋  Thông tin kỹ thuật")), font=EMOJI_FONT_8_BOLD,
                 fg=self.btn_color, bg=self.entry_bg, anchor="w").pack(fill=tk.X, padx=12, pady=(8, 4))

        rows = [
            (_("Public IP phát hiện"), public_ip if public_ip else "N/A"),
            (_("Trạng thái"),          _("Cùng Public IP → cùng Router/Mạng nội bộ")),
            (_("Phương thức thử"),     _("Kết nối TCP trực tiếp qua Local IP (LAN)")),
            (_("Kết quả"),             _("❌  Tất cả địa chỉ LAN đều không phản hồi")),
        ]
        for label, value in rows:
            row = tk.Frame(info_frame, bg=self.entry_bg)
            row.pack(fill=tk.X, padx=12, pady=2)
            tk.Label(row, text=f"{label}:", font=(APP_FONT_NAME, 8), fg=self.text_gray,
                     bg=self.entry_bg, width=22, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, font=(APP_FONT_NAME, 8, "bold"), fg=self.text_white,
                     bg=self.entry_bg, anchor="w", wraplength=240, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X)
        tk.Frame(info_frame, bg=self.entry_bg, height=6).pack()

        # ── NGUYÊN NHÂN & CÁCH KHẮC PHỤC ───────────────────────
        tk.Label(dialog, text=E(_("🔧  Cách khắc phục")), font=EMOJI_FONT_BOLD,
                 fg="#F39C12", bg=self.bg_color, anchor="w").pack(fill=tk.X, padx=20, pady=(12, 4))

        steps = [
            ("1", _("Kiểm tra Tường lửa Windows"),
             _("Vào Windows Defender Firewall → Allow an app → đảm bảo RemoteDesktopP2P.exe được phép trên Private & Public network.")),
            ("2", _("Kiểm tra phần mềm diệt virus / VPN"),
             _("Tắt tạm thời các phần mềm Antivirus hoặc VPN có thể đang chặn kết nối nội bộ.")),
            ("3", _("Kiểm tra cổng mạng đang dùng"),
             _("Ứng dụng dùng cổng") + f" {BOUND_PORT}. " + _("Đảm bảo cổng này chưa bị chiếm hoặc bị chặn bởi Firewall.")),
        ]
        for num, title_step, desc in steps:
            sf = tk.Frame(dialog, bg=self.bg_color)
            sf.pack(fill=tk.X, padx=20, pady=2)
            badge = tk.Label(sf, text=num, font=(APP_FONT_NAME, 8, "bold"), fg=self.bg_color,
                             bg=self.btn_color, width=2, height=1)
            badge.pack(side=tk.LEFT, anchor="n", padx=(0, 8), pady=2)
            txt_col = tk.Frame(sf, bg=self.bg_color)
            txt_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tk.Label(txt_col, text=title_step, font=(APP_FONT_NAME, 8, "bold"),
                     fg=self.text_white, bg=self.bg_color, anchor="w").pack(anchor="w")
            tk.Label(txt_col, text=desc, font=(APP_FONT_NAME, 8), fg=self.text_gray,
                     bg=self.bg_color, anchor="w", wraplength=360, justify=tk.LEFT).pack(anchor="w")

        # ── BUTTON ──────────────────────────────────────────────
        tk.Frame(dialog, bg="#2A2A3A", height=1).pack(fill=tk.X, padx=20, pady=(10, 0))
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(8, 14))
        tk.Button(
            btn_frame, text=_("Đã hiểu"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg="#E05252", activebackground="#C0392B",
            relief=tk.FLAT, bd=0, width=12, pady=5, cursor="hand2",
            command=dialog.destroy
        ).pack(side=tk.RIGHT)

        self.wait_window(dialog)


    def show_custom_question(self, title, message, parent=None):
        if getattr(self, 'is_headless', False):
            print(f"[Question] {title}: {message} -> Auto-confirmed (Yes)")
            return True

        import tkinter as tk
        p = parent if parent else self
        
        dialog = tk.Toplevel(p)
        dialog.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy ở góc trên bên trái màn hình
        dialog.title(title)
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.attributes("-topmost", True)
        dialog.transient(p)
        dialog.grab_set()
        
        # Center calculations relative to parent
        dialog.update_idletasks()
        w = 400
        h = 180
        x = p.winfo_x() + (p.winfo_width() - w) // 2
        y = p.winfo_y() + (p.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.deiconify()  # Chỉ hiển thị sau khi đã tính toán căn giữa hoàn hảo!
        
        # Content frame
        content_frame = tk.Frame(dialog, bg=self.bg_color)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(20, 10))
        
        # Icon & Message side-by-side
        icon_lbl = tk.Label(content_frame, text="❓", font=(APP_FONT_NAME, 22), fg="#F39C12", bg=self.bg_color)
        icon_lbl.pack(side=tk.LEFT, anchor=tk.N, padx=(0, 15), pady=(2, 0))
        
        msg_lbl = tk.Label(content_frame, text=message, font=(APP_FONT_NAME, 9), fg=self.text_white, bg=self.bg_color, wraplength=310, justify=tk.LEFT)
        msg_lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor=tk.N)
        
        result = [False]
        
        def on_yes():
            result[0] = True
            dialog.destroy()
            
        def on_no():
            result[0] = False
            dialog.destroy()
            
        # Button frame at bottom
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 12))
        
        # Nút "Không"
        btn_no = tk.Button(
            btn_frame, text=_("Không"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, width=8, pady=3, cursor="hand2", command=on_no
        )
        btn_no.pack(side=tk.RIGHT, padx=(4, 0))
        
        # Nút "Có"
        btn_yes = tk.Button(
            btn_frame, text=_("Có"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, width=8, pady=3, cursor="hand2", command=on_yes
        )
        btn_yes.pack(side=tk.RIGHT, padx=(0, 4))
        
        dialog.protocol("WM_DELETE_WINDOW", on_no)
        
        # Đợi cho đến khi cửa sổ Modal này đóng để đồng bộ luồng chặn
        self.wait_window(dialog)
        return result[0]


    def update_status(self, text, is_error=False, blink=False, is_success=False):
        def _do_update():
            self.status_var.set(_("Trạng thái:") + f" {text}")
            
            if not hasattr(self, 'lbl_status'):
                return
                
            if hasattr(self, '_blink_job') and self._blink_job:
                self.after_cancel(self._blink_job)
                self._blink_job = None
                
            if blink:
                self.lbl_status.config(fg="#FF4D4D")
                self._blink_status()
            elif is_error:
                self.lbl_status.config(fg="#FF4D4D")
            elif is_success or _("thành công") in text.lower():
                self.lbl_status.config(fg="#2ECC71")  # Xanh lục (Emerald Green)
            else:
                self.lbl_status.config(fg="#8A8A9A")
        
        self.after(0, _do_update)


    def check_if_service_active(self):
        if getattr(self, 'is_headless', False):
            return False
            
        # 1. Quick check if RemoteDesktopService.exe is running in the system process list
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() == "remotedesktopservice.exe":
                    return True
        except:
            pass
            
        # 2. Mutex fallback check
        session_id = 1
        try:
            import win32event, win32con, win32api
            sid = ctypes.c_ulong()
            if ctypes.windll.kernel32.ProcessIdToSessionId(ctypes.windll.kernel32.GetCurrentProcessId(), ctypes.byref(sid)):
                session_id = sid.value
        except Exception:
            return False
        except:
            pass
            
        for d_name in ["default", "winlogon"]:
            m_name = f"Global\\AntigravityP2PRemoteDesktopAppMutex_1_{session_id}_{d_name}"
            try:
                h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, m_name)
                if h_mutex:
                    win32api.CloseHandle(h_mutex)
                    return True
            except Exception as e:
                err_code = getattr(e, 'winerror', 0)
                if not err_code and hasattr(e, 'args') and len(e.args) > 0:
                    err_code = e.args[0]
                if err_code == 5: # ERROR_ACCESS_DENIED means it exists
                    return True
        return False

    def _poll_signaling_status(self):
        """Polling loop chạy trên main Tkinter thread - kiểm tra Signaling mỗi 3s và cập nhật status UI đáng tin cậy."""
        if not getattr(self, 'running_server', True):
            return
            
        # Check if service became active
        if not getattr(self, 'is_headless', False) and not getattr(self, 'is_service_active', False):
            if self.check_if_service_active():
                print("[Host GUI] Service has started in background. Switching to service-compatible mode...")
                self.is_service_active = True
                global BOUND_PORT
                BOUND_PORT = 12346
                import core.config; core.config.BOUND_PORT = 12346
                import core.network_manager; core.network_manager.BOUND_PORT = 12346
                import core.host; core.host.BOUND_PORT = 12346
                
                if getattr(self, 'server_socket', None):
                    try:
                        self.server_socket.close()
                        self.server_socket = None
                    except:
                        pass
                
                if hasattr(self, 'signaling_sockets'):
                    sockets_to_close = list(self.signaling_sockets.values())
                    self.signaling_sockets.clear()
                    for sock in sockets_to_close:
                        try:
                            sock.close()
                        except:
                            pass
                            
        try:
            current_status = self.status_var.get()
            # Chỉ update nếu status đang ở các trạng thái chưa kết nối/đang thử
            is_pending = any(kw in current_status for kw in [
                _("Không thể kết nối Signaling"),
                _("Chưa kết nối Signaling"),
                _("Đang kết nối Signaling"),
                _("Đang thử lại"),
                _("chế độ nền"),
                _("Sẵn sàng kết nối"),  # cũng update nếu đang sẵn sàng mà Signaling chưa confirm
            ])
            if is_pending and getattr(self, 'signaling_sockets', {}):
                self.update_status(_("Kết nối Signaling thành công! Sẵn sàng kết nối."), is_success=True)
        except Exception:
            pass
        self.after(3000, self._poll_signaling_status)


    def _blink_status(self):
        if not hasattr(self, 'lbl_status'): return
        current_color = self.lbl_status.cget("fg")
        next_color = self.entry_bg if current_color == "#FF4D4D" else "#FF4D4D"
        self.lbl_status.config(fg=next_color)
        self._blink_job = self.after(500, self._blink_status)
        
    # Background Network Initialization

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
                self.update_status(_("Đã gửi Wake-On-Lan tới MAC") + f" {m}", is_success=True)
            except Exception as e:
                print(f"[WOL] Lỗi gửi Wake-On-Lan tới MAC {m}: {e}")

    # ==================== LAN DISCOVERY (UDP Broadcast) ====================

    def on_close_window(self):
        # Lưu tọa độ hiện tại trước khi ẩn cửa sổ
        self.save_window_position()
        
        # Nếu tùy chọn "Chạy khi mở máy" được bật thì thu nhỏ xuống system tray
        if getattr(self, 'startup_var', None) and self.startup_var.get():
            self.withdraw()
            print("[Tray] App minimized to system tray.")
        else:
            # Nếu không, đóng hoàn toàn ứng dụng
            self.destroy()


    def setup_tray_icon(self):
        if hasattr(self, 'tray_icon') and self.tray_icon:
            return
            
        if pystray is None:
            print("[Tray] pystray is not available, skipping tray icon setup.")
            return
            
        try:
            # Tải icon từ file png nếu tồn tại, ngược lại vẽ icon mặc định
            icon_path = os.path.join(app_dir, "app_icon.png")
            image = None
            if os.path.exists(icon_path):
                try:
                    image = Image.open(icon_path)
                except Exception as e:
                    print(f"[Tray] Không thể mở file app_icon.png: {e}")
            
            if image is None:
                image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
                dc = ImageDraw.Draw(image)
                dc.ellipse((4, 4, 60, 60), fill="#1E2022", outline="#00ADB5", width=3)
                dc.ellipse((16, 16, 48, 48), fill="#00ADB5")
            
            menu = pystray.Menu(
                item(_('Hiện (Show)'), self.show_gui_from_tray, default=True),
                item(_('Thoát (Exit)'), self.exit_from_tray)
            )
            
            self.tray_icon = pystray.Icon("EasyRemoteDesktop", image, "Easy Remote Desktop", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            print("[Tray] System tray icon started successfully.")
        except Exception as e:
            print(f"[Tray] Failed to initialize system tray icon: {e}")




    def show_gui_from_tray(self, icon=None, item=None):
        self.after(0, self._restore_window)
        

    def _restore_window(self):
        if self.state() == "normal":
            try:
                if self.attributes("-alpha") == 1.0:
                    self.lift()
                    self.focus_force()
                    return
            except:
                pass
                
        import re
        geom = self.geometry()
        m = re.match(r"(\d+)x(\d+)([-+]\d+)([-+]\d+)", geom)
        if m:
            end_w, end_h = int(m.group(1)), int(m.group(2))
            end_x, end_y = int(m.group(3)), int(m.group(4))
        else:
            end_w, end_h, end_x, end_y = 1000, 700, 100, 100 # Fallback
            
        self.geometry(f"{end_w}x{end_h}+{end_x}+{end_y}")
        try:
            self.attributes("-alpha", 1.0)
        except:
            pass
            
        self.deiconify()
        self.lift()
        self.focus_force()
        print("[Tray] Main window restored.")
        

    def exit_from_tray(self, icon=None, item=None):
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.visible = False
                self.tray_icon.stop()
            except:
                pass
        self.after(0, self.destroy)


    def destroy(self):
        # Force terminate in a background thread to prevent any hanging issues on Windows 11
        # Force terminate in a background thread to prevent any hanging issues on Windows 11
        def force_terminate():
            import time
            time.sleep(1.0)
            try:
                import os, subprocess
                subprocess.run(f"taskkill /F /PID {os.getpid()} /T", shell=True, creationflags=0x08000000)
            except:
                pass
            try:
                import os
                os._exit(0)
            except:
                pass
                
        import threading
        threading.Thread(target=force_terminate, daemon=True).start()

        # Graceful exit on closing window
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.visible = False
                self.tray_icon.stop()
            except:
                pass
        self.save_window_position()
        self.running_server = False
        if getattr(self, 'server_socket', None):
            try: self.server_socket.close()
            except: pass
        
        if hasattr(self, 'signaling_sockets'):
            for sock in self.signaling_sockets.values():
                try: force_close_socket(sock)
                except: pass
                
        # Terminate any running child processes (viewers)
        if hasattr(self, 'active_viewers'):
            for viewer in self.active_viewers:
                try:
                    p = viewer.get("process")
                    if p and p.is_alive():
                        p.terminate()
                        p.join(timeout=0.5)
                except:
                    pass
                
        try:
            super().destroy()
        except:
            pass
            
        try:
            import os
            os._exit(0)
        except:
            pass


if __name__ == '__main__':
    import multiprocessing as mp
    mp.freeze_support()
    try:
        mp.set_start_method("spawn")
    except RuntimeError:
        pass
    
    import sys
    import ctypes
    import time
    

    is_headless = "--headless" in sys.argv
    is_clipboard_agent = "--clipboard-agent" in sys.argv
    
    # --- Chế độ Clipboard Agent: Chỉ lắng nghe Pipe và nạp Clipboard, thoát sớm ---
    if is_clipboard_agent:
        if sys.platform == "win32":
            import win32event, win32api, winerror
            
            # Mutex riêng cho Clipboard Agent (index 3) để tránh chạy trùng
            try:
                sid = ctypes.c_ulong()
                ctypes.windll.kernel32.ProcessIdToSessionId(
                    ctypes.windll.kernel32.GetCurrentProcessId(), ctypes.byref(sid)
                )
                session_id = sid.value
            except:
                session_id = 1
                
            mutex_name = f"Global\\AntigravityP2PClipboardAgentMutex_{session_id}"
            try:
                mutex = win32event.CreateMutex(None, False, mutex_name)
            except Exception as e:
                # Fallback to Local namespace if Global access is denied (common for non-admin users)
                mutex_name = f"Local\\AntigravityP2PClipboardAgentMutex_{session_id}"
                try:
                    mutex = win32event.CreateMutex(None, False, mutex_name)
                except Exception as ex:
                    # If even Local fails, print warning but proceed
                    print(f"[ClipboardAgent] Error creating Local mutex: {ex}", flush=True)
                    mutex = None
            
            if mutex and win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                sys.exit(0)
        
        # Redirect stdout/stderr cho clipboard agent mode
        try:
            log_path = os.path.join(app_dir, "clipboard_agent.log")
            sys.stdout = open(log_path, "a", encoding="utf-8", buffering=1)
            sys.stderr = sys.stdout
        except:
            pass
        
        run_clipboard_agent_mode()  # Vòng lặp vô tận, không return
        sys.exit(0)
    

    if sys.platform == "win32":
        import win32event, win32api, winerror, win32security
        
        def get_session_id():
            try:
                sid = ctypes.c_ulong()
                if ctypes.windll.kernel32.ProcessIdToSessionId(ctypes.windll.kernel32.GetCurrentProcessId(), ctypes.byref(sid)):
                    return sid.value
            except:
                pass
            return 1
            
        def get_desktop_name():
            try:
                h_desk = ctypes.windll.user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
                name = ctypes.create_unicode_buffer(256)
                size = ctypes.c_ulong(256)
                if ctypes.windll.user32.GetUserObjectInformationW(h_desk, 2, name, size, None):
                    return name.value.lower()
            except:
                pass
            return "default"
            
        session_id = get_session_id()
        desktop_name = get_desktop_name()
        
        if is_headless:
            # Enable SYSTEM privileges (SeTcbPrivilege, SeDebugPrivilege, SeImpersonatePrivilege, etc.)
            # for the headless agent process to switch desktops and control UAC.
            try:
                import win32con
                h_process = win32api.GetCurrentProcess()
                h_token = win32security.OpenProcessToken(
                    h_process, win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY
                )
                privs = []
                for priv_name in [
                    win32security.SE_DEBUG_NAME, 
                    win32security.SE_TCB_NAME, 
                    win32security.SE_ASSIGNPRIMARYTOKEN_NAME, 
                    win32security.SE_INCREASE_QUOTA_NAME,
                    win32security.SE_IMPERSONATE_NAME
                ]:
                    try:
                        luid = win32security.LookupPrivilegeValue(None, priv_name)
                        privs.append((luid, win32security.SE_PRIVILEGE_ENABLED))
                    except:
                        pass
                if privs:
                    win32security.AdjustTokenPrivileges(h_token, False, privs)
                win32api.CloseHandle(h_token)
                print("[Headless] All SYSTEM privileges successfully enabled for the agent process.")
            except Exception as e:
                print(f"[Headless] Failed to enable SYSTEM privileges: {e}")

            # Service headless helper uses mutex index 1
            mutex_name = f"Global\\AntigravityP2PRemoteDesktopAppMutex_1_{session_id}_{desktop_name}"
            # Create mutex with NULL DACL so standard user processes can open/query it
            try:
                import win32security
                sd = win32security.SECURITY_DESCRIPTOR()
                sd.Initialize()
                sd.SetSecurityDescriptorDacl(True, None, False)
                sa = win32security.SECURITY_ATTRIBUTES()
                sa.bInheritHandle = 1
                sa.SECURITY_DESCRIPTOR = sd
                mutex = win32event.CreateMutex(sa, False, mutex_name)
            except Exception as e:
                print(f"[Headless] Security descriptor creation failed: {e}")
                mutex = win32event.CreateMutex(None, False, mutex_name)
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                sys.exit(0)
        else:
            # GUI client uses mutex index 2
            mutex_name = f"Global\\AntigravityP2PRemoteDesktopAppMutex_2_{session_id}_{desktop_name}"
            
            is_delay = "--delay-startup" in sys.argv
            wait_time = 0
            while True:
                mutex = win32event.CreateMutex(None, False, mutex_name)
                if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                    if is_delay and wait_time < 100:
                        win32api.CloseHandle(mutex)
                        time.sleep(0.1)
                        wait_time += 1
                        continue
                    else:
                        # Topmost native message dialog
                        msg_text = _("Ứng dụng P2P Remote Desktop đang chạy ở khay hệ thống")
                        msg_title = _("Thông báo")
                        # MB_OK | MB_ICONINFORMATION | MB_TOPMOST
                        ctypes.windll.user32.MessageBoxW(0, msg_text, msg_title, 0x00040040)
                        
                        # Signal restore event to primary GUI instance
                        restore_event_name = f"Global\\AntigravityP2PRemoteDesktopRestoreEvent_{session_id}_{desktop_name}"
                        try:
                            h_event = win32event.OpenEvent(win32event.EVENT_MODIFY_STATE, False, restore_event_name)
                            if h_event:
                                win32event.SetEvent(h_event)
                                win32api.CloseHandle(h_event)
                        except Exception as e:
                            print(f"Failed to signal restore event: {e}")
                        sys.exit(0)
                else:
                    break
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            try: ctypes.windll.user32.SetProcessDPIAware()
            except: pass
            
    try:
        app = UnifiedApp()
        
        if sys.platform != "win32":
            import signal
            def graceful_shutdown(signum, frame):
                print(f"[App] Caught signal {signum}, notifying clients and shutting down...")
                try:
                    with open("/tmp/p2p_shutdown.log", "a", encoding="utf-8") as f:
                        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Caught signal {signum}, notifying clients and shutting down...\n")
                except: pass
                try:
                    from network.socket_utils import socket_passwords, send_msg
                    import json
                    pkt = json.dumps({"type": "host_shutdown"}).encode('utf-8')
                    for conn in list(socket_passwords.keys()):
                        try:
                            send_msg(conn, pkt, socket_passwords[conn])
                            with open("/tmp/p2p_shutdown.log", "a", encoding="utf-8") as f:
                                f.write(f"  -> Sent host_shutdown to {conn.getpeername() if hasattr(conn, 'getpeername') else conn}\n")
                        except Exception as e:
                            with open("/tmp/p2p_shutdown.log", "a", encoding="utf-8") as f:
                                f.write(f"  -> Failed to send to {conn}: {e}\n")
                except: pass
                import time
                time.sleep(1)
                sys.exit(0)
            try:
                signal.signal(signal.SIGTERM, graceful_shutdown)
                signal.signal(signal.SIGINT, graceful_shutdown)
                signal.signal(signal.SIGHUP, graceful_shutdown)
            except: pass

        def check_signals():
            app.after(500, check_signals)
        app.after(500, check_signals)

        app.mainloop()
        try:
            import sys
            if sys.platform == "win32":
                log_path = "C:\\Apps\\P2P\\agent.log"
            else:
                log_path = "/tmp/agent.log"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write("\\n[DEBUG] Exited mainloop cleanly!\\n")
        except:
            pass
        # Keep the process alive just in case
        if "--headless" in sys.argv:
            import time
            while True:
                time.sleep(1)
    except BaseException as e:
        import traceback
        import datetime
        try:
            import sys, os
            if sys.platform == "win32":
                crash_log_path = "C:\\Apps\\P2P\\agent_crash.txt"
            else:
                crash_log_path = "/opt/p2p_remote/agent_crash.txt"
            
            with open(crash_log_path, "w", encoding="utf-8") as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] Exception: {e}\n\n")
                traceback.print_exc(file=f)
                f.flush()
        except:
            pass
        raise
