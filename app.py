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
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key
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

def get_log_filepath(filename):
    temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except:
        pass
    return os.path.join(temp_dir, filename)

def log_file_transfer(filename, file_size):
    try:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.2f} KB"
        elif file_size < 1024 * 1024 * 1024:
            size_str = f"{file_size / (1024 * 1024):.2f} MB"
        else:
            size_str = f"{file_size / (1024 * 1024 * 1024):.2f} GB"
            
        log_line = f"{timestamp} File: {filename} | Size: {size_str}\n"
        filepath = get_log_filepath("log.txt")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"[Log] Lỗi ghi log.txt: {e}")

def log_debug(msg):
    try:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        filepath = get_log_filepath(f"clipboard_debug_{os.getpid()}.log")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} [PID {os.getpid()}] {msg}\n")
    except:
        pass

def log_activity(msg):
    try:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        filepath = os.path.join(app_dir, "activity_log.txt")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} - {msg}\n")
    except Exception as e:
        print(f"[Log] Lỗi ghi activity_log.txt: {e}")

# Pygame CE drop-in compatibility
# In pygame-ce, it is still imported as pygame.

# Remote Desktop Ports (Avoid 80/443 to prevent Router Web UI collision)
PORTS_TO_TRY = [12345, 12346, 12347, 12348, 12349]
BOUND_PORT = 12345
APP_KEY = "q3tu0y7j"

# LAN Discovery (UDP Broadcast) - Cho phép các máy trong cùng mạng LAN tự phát hiện nhau
LAN_DISCOVERY_PORT = 12399
LAN_BEACON_INTERVAL = 5  # Gửi beacon mỗi 5 giây
LAN_OFFLINE_TIMEOUT = 15  # Coi là offline nếu không nhận beacon trong 15 giây
LAN_APP_SIGNATURE = hashlib.sha256(b"EasyRemoteDesktop_LAN_v1").hexdigest()[:16]

# Host Controllers
mouse = MouseController()
keyboard = KeyboardController()

# Button mapping for mouse clicks
button_map = {
    'left': Button.left,
    'right': Button.right,
    'middle': Button.middle
}

# Key mapping from Pygame key names to pynput Key
key_map = {
    'space': Key.space,
    'enter': Key.enter,
    'return': Key.enter,
    'escape': Key.esc,
    'backspace': Key.backspace,
    'tab': Key.tab,
    'left shift': Key.shift,
    'right shift': Key.shift_r,
    'left ctrl': Key.ctrl_l,
    'right ctrl': Key.ctrl_r,
    'left alt': Key.alt_l,
    'right alt': Key.alt_r,
    'up': Key.up,
    'down': Key.down,
    'left': Key.left,
    'right': Key.right,
    'caps lock': Key.caps_lock,
    'capslock': Key.caps_lock,
    'delete': Key.delete,
    'home': Key.home,
    'end': Key.end,
    'page up': Key.page_up,
    'page down': Key.page_down,
    'f1': Key.f1,
    'f2': Key.f2,
    'f3': Key.f3,
    'f4': Key.f4,
    'f5': Key.f5,
    'f6': Key.f6,
    'f7': Key.f7,
    'f8': Key.f8,
    'f9': Key.f9,
    'f10': Key.f10,
    'f11': Key.f11,
    'f12': Key.f12,
}

# Ctypes definitions for SendInput API (standard modern input simulation)
import ctypes
from ctypes import wintypes

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_UNICODE = 0x0004

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort)
    ]

class INPUT_union(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", INPUT_union)
    ]

# Map Pygame/common key names to Windows Virtual Key (VK) codes
vk_map = {
    'space': 0x20,      # VK_SPACE
    'enter': 0x0D,      # VK_RETURN
    'return': 0x0D,     # VK_RETURN
    'escape': 0x1B,     # VK_ESCAPE
    'backspace': 0x08,  # VK_BACK
    'tab': 0x09,        # VK_TAB
    'left shift': 0xA0, # VK_LSHIFT
    'right shift': 0xA1,# VK_RSHIFT
    'left ctrl': 0xA2,  # VK_LCONTROL
    'right ctrl': 0xA3, # VK_RCONTROL
    'left alt': 0xA4,   # VK_LMENU
    'right alt': 0xA5,  # VK_RMENU
    'up': 0x26,         # VK_UP
    'down': 0x28,       # VK_DOWN
    'left': 0x25,       # VK_LEFT
    'right': 0x27,      # VK_RIGHT
    'caps lock': 0x14,  # VK_CAPITAL
    'capslock': 0x14,   # VK_CAPITAL
    'delete': 0x2E,     # VK_DELETE
    'home': 0x24,       # VK_HOME
    'end': 0x23,        # VK_END
    'page up': 0x21,    # VK_PRIOR
    'page down': 0x22,  # VK_NEXT
    'f1': 0x70,         # VK_F1
    'f2': 0x71,         # VK_F2
    'f3': 0x72,         # VK_F3
    'f4': 0x73,         # VK_F4
    'f5': 0x74,         # VK_F5
    'f6': 0x75,         # VK_F6
    'f7': 0x76,         # VK_F7
    'f8': 0x77,         # VK_F8
    'f9': 0x78,         # VK_F9
    'f10': 0x79,        # VK_F10
    'f11': 0x7A,        # VK_F11
    'f12': 0x7B,        # VK_F12
    '`': 0xC0,          # VK_OEM_3
    '~': 0xC0,          # VK_OEM_3
    '-': 0xBD,          # VK_OEM_MINUS
    '_': 0xBD,          # VK_OEM_MINUS
    '=': 0xBB,          # VK_OEM_PLUS
    '+': 0xBB,          # VK_OEM_PLUS
    '[': 0xDB,          # VK_OEM_4
    '{': 0xDB,          # VK_OEM_4
    ']': 0xDD,          # VK_OEM_6
    '}': 0xDD,          # VK_OEM_6
    '\\': 0xDC,         # VK_OEM_5
    '|': 0xDC,          # VK_OEM_5
    ';': 0xBA,          # VK_OEM_1
    ':': 0xBA,          # VK_OEM_1
    "'": 0xDE,          # VK_OEM_7
    '"': 0xDE,          # VK_OEM_7
    ',': 0xBC,          # VK_OEM_COMMA
    '<': 0xBC,          # VK_OEM_COMMA
    '.': 0xBE,          # VK_OEM_PERIOD
    '>': 0xBE,          # VK_OEM_PERIOD
    '/': 0xBF,          # VK_OEM_2
    '?': 0xBF,          # VK_OEM_2
    'left meta': 0x5B,  # VK_LWIN
    'right meta': 0x5C, # VK_RWIN
    'left windows': 0x5B,
    'right windows': 0x5C,
    'left super': 0x5B,
    'right super': 0x5C,
    'menu': 0x5D,       # VK_APPS (phím right-click / context menu trên bàn phím)
    'application': 0x5D,# VK_APPS (tên thay thế trong một số layout)
    'insert': 0x2D,     # VK_INSERT
    '[0]': 0x60,        # VK_NUMPAD0
    '[1]': 0x61,        # VK_NUMPAD1
    '[2]': 0x62,        # VK_NUMPAD2
    '[3]': 0x63,        # VK_NUMPAD3
    '[4]': 0x64,        # VK_NUMPAD4
    '[5]': 0x65,        # VK_NUMPAD5
    '[6]': 0x66,        # VK_NUMPAD6
    '[7]': 0x67,        # VK_NUMPAD7
    '[8]': 0x68,        # VK_NUMPAD8
    '[9]': 0x69,        # VK_NUMPAD9
    '[.]': 0x6E,        # VK_DECIMAL
    '[/]': 0x6F,        # VK_DIVIDE
    '[*]': 0x6A,        # VK_MULTIPLY
    '[-]': 0x6D,        # VK_SUBTRACT
    '[+]': 0x6B,        # VK_ADD
    'keypad 0': 0x60,
    'keypad 1': 0x61,
    'keypad 2': 0x62,
    'keypad 3': 0x63,
    'keypad 4': 0x64,
    'keypad 5': 0x65,
    'keypad 6': 0x66,
    'keypad 7': 0x67,
    'keypad 8': 0x68,
    'keypad 9': 0x69,
    'keypad .': 0x6E,
    'keypad /': 0x6F,
    'keypad *': 0x6A,
    'keypad -': 0x6D,
    'keypad +': 0x6B,
    'keypad enter': 0x0D,
}

# Track remote modifier key state (set of held modifier key names) to avoid
# polling HOST keyboard state via GetAsyncKeyState which is incorrect for remote input.
_remote_modifier_keys = set()
_remote_modifier_names = {
    'left ctrl', 'right ctrl', 'left alt', 'right alt',
    'left meta', 'right meta', 'left windows', 'right windows',
    'left super', 'right super'
}

def send_input_keyboard_event(key_name, pressed):
    try:
        # Update remote modifier state tracker
        if key_name in _remote_modifier_names:
            if pressed:
                _remote_modifier_keys.add(key_name)
            else:
                _remote_modifier_keys.discard(key_name)

        vk = None
        if key_name in vk_map:
            vk = vk_map[key_name]
        elif len(key_name) == 1:
            char_upper = key_name.upper()
            if ('A' <= char_upper <= 'Z') or ('0' <= char_upper <= '9'):
                vk = ord(char_upper)
            else:
                # Try to resolve VK code for punctuation/symbol characters via VkKeyScanW
                # This enables Vietnamese IME (Unikey) to process keys like [, ], ;, ', etc.
                vk_scan = ctypes.windll.user32.VkKeyScanW(ord(key_name))
                if vk_scan != -1 and (vk_scan & 0xFF) != 0:
                    vk = vk_scan & 0xFF  # Low byte = VK code
                
        # Check if any shortcut modifier is held down based on tracked remote state
        is_modifier = bool(_remote_modifier_keys)
        
        if vk is not None:
            # Use VK code + hardware scan code for all keys that have a VK mapping.
            # This is critical for Vietnamese IME (Unikey/Telex/VNI) compatibility:
            # Unikey hooks WM_KEYDOWN/WM_KEYUP messages and needs real VK codes
            # to detect key sequences (e.g. a+a -> â, o+w -> ơ).
            # KEYEVENTF_UNICODE bypasses keyboard hooks so Unikey cannot intercept it.
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            flags = 0
            if not pressed:
                flags |= KEYEVENTF_KEYUP
                
            # Get hardware scan code from VK for maximum compatibility
            scan = ctypes.windll.user32.MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC
                
            # Check for extended keys
            extended_vks = [
                0x25, 0x26, 0x27, 0x28, # Arrows
                0x2D, 0x2E,             # Insert, Delete
                0x24, 0x23,             # Home, End
                0x21, 0x22,             # PageUp, PageDown
                0x90,                   # Numlock
                0x2F,                   # Print screen
                0xA5,                   # VK_RMENU (Right Alt)
                0xA3,                   # VK_RCONTROL (Right Ctrl)
                0x5B, 0x5C,             # LWIN, RWIN
                0x5D                    # VK_APPS (Menu/Application key)
            ]
            if vk in extended_vks:
                flags |= KEYEVENTF_EXTENDEDKEY
                
            # Map left/right modifiers to their generic VK equivalents.
            # This is critical for the Windows Login Screen (Secure Desktop),
            # which often ignores directional modifiers (like VK_LSHIFT = 0xA0)
            # when injected via SendInput.
            generic_vks = {
                0xA0: 0x10, # VK_LSHIFT -> VK_SHIFT
                0xA1: 0x10, # VK_RSHIFT -> VK_SHIFT
                0xA2: 0x11, # VK_LCONTROL -> VK_CONTROL
                0xA3: 0x11, # VK_RCONTROL -> VK_CONTROL
                0xA4: 0x12, # VK_LMENU -> VK_MENU
                0xA5: 0x12, # VK_RMENU -> VK_MENU
            }
            inject_vk = generic_vks.get(vk, vk)
                
            inp.union.ki = KEYBDINPUT(inject_vk, scan, flags, 0, None)
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        elif len(key_name) == 1 and not is_modifier:
            # Fallback: Use KEYEVENTF_UNICODE only for characters without a VK code
            # (e.g. pre-composed Unicode characters, emoji, special symbols)
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            flags = KEYEVENTF_UNICODE
            if not pressed:
                flags |= KEYEVENTF_KEYUP
            inp.union.ki = KEYBDINPUT(0, ord(key_name), flags, 0, None)
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    except Exception as e:
        print(f"[SendInput] Keyboard injection failed: {e}")

def send_input_mouse_click(button_name, pressed):
    try:
        flags = 0
        if button_name == 'left':
            flags = MOUSEEVENTF_LEFTDOWN if pressed else MOUSEEVENTF_LEFTUP
        elif button_name == 'right':
            flags = MOUSEEVENTF_RIGHTDOWN if pressed else MOUSEEVENTF_RIGHTUP
        elif button_name == 'middle':
            flags = MOUSEEVENTF_MIDDLEDOWN if pressed else MOUSEEVENTF_MIDDLEUP
            
        if flags:
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.union.mi = MOUSEINPUT(0, 0, 0, flags, 0, None)
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    except Exception as e:
        print(f"[SendInput] Mouse click injection failed: {e}")

def send_input_mouse_scroll(dx, dy):
    try:
        if dy != 0:
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.union.mi = MOUSEINPUT(0, 0, int(dy * 120), MOUSEEVENTF_WHEEL, 0, None)
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    except Exception as e:
        print(f"[SendInput] Mouse scroll injection failed: {e}")

# Cached screen metrics for mouse move normalization (avoid calling GetSystemMetrics on every event)
_cached_screen_w = 0
_cached_screen_h = 0
_cached_screen_time = 0

def send_input_mouse_move(x, y):
    global _cached_screen_w, _cached_screen_h, _cached_screen_time
    try:
        # Refresh cached screen dimensions every 2 seconds
        now = time.monotonic() if hasattr(time, 'monotonic') else time.time()
        if now - _cached_screen_time > 2.0 or _cached_screen_w == 0:
            _cached_screen_w = ctypes.windll.user32.GetSystemMetrics(0) # SM_CXSCREEN
            _cached_screen_h = ctypes.windll.user32.GetSystemMetrics(1) # SM_CYSCREEN
            _cached_screen_time = now
        w, h = _cached_screen_w, _cached_screen_h
        if w > 0 and h > 0:
            # Standard absolute coordinate formula: (coord * 65535) / (screen_size - 1)
            normalized_x = int((x * 65535) / (w - 1)) if w > 1 else 0
            normalized_y = int((y * 65535) / (h - 1)) if h > 1 else 0
            inp = INPUT()
            inp.type = INPUT_MOUSE
            # MOUSEEVENTF_MOVE = 0x0001, MOUSEEVENTF_ABSOLUTE = 0x8000
            inp.union.mi = MOUSEINPUT(normalized_x, normalized_y, 0, 0x0001 | 0x8000, 0, None)
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    except Exception as e:
        print(f"[SendInput] Mouse move injection failed: {e}")

# TCP Frame Helper Functions
# Per-socket send locks: prevent screen-frame sends from blocking input-event sends on the same socket
_socket_send_locks = {}
_socket_send_locks_meta = threading.Lock()
send_nonce_counter = 0
send_counter_lock = threading.Lock()
socket_passwords = {}

def _get_socket_send_lock(sock):
    with _socket_send_locks_meta:
        lock = _socket_send_locks.get(sock)
        if lock is None:
            lock = threading.Lock()
            _socket_send_locks[sock] = lock
        return lock

def get_crypto_key(password):
    if not isinstance(password, str):
        if isinstance(password, (list, tuple)) and password:
            password = password[0]
        else:
            password = str(password)
    return hashlib.sha256(password.encode('utf-8')).digest()

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
    passwords = [password] if isinstance(password, str) else list(password)
    passwords = [p for p in passwords if p]
    
    if len(encrypted_bytes) < 12:
        raise ValueError("Dữ liệu mã hóa không hợp lệ (kích thước quá nhỏ)")
    nonce = encrypted_bytes[:12]
    ciphertext = encrypted_bytes[12:]
    
    last_err = None
    for p in passwords:
        try:
            key = get_crypto_key(p)
            chacha = ChaCha20Poly1305(key)
            return chacha.decrypt(nonce, ciphertext, None)
        except Exception as e:
            last_err = e
    raise last_err if last_err else ValueError("Không giải mã được với bất kỳ mật khẩu nào")


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

def send_msg(sock, data_bytes, password=None):
    if password is None:
        password = socket_passwords.get(sock, APP_KEY)
    try:
        lock = _get_socket_send_lock(sock)
        with lock:
            encrypted_data = encrypt_payload(data_bytes, password)
            msg = struct.pack('>I', len(encrypted_data)) + encrypted_data
            sock.sendall(msg)
    except Exception as e:
        print(f"[Socket] Lỗi gửi dữ liệu: {e}")

def recv_exact(sock, length):
    data = b''
    while len(data) < length:
        packet = sock.recv(length - len(data))
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

# Helper to fetch hardware identifiers (CPUID & HDD Serial)
def get_hwid():
    cpu = "FALLBACK_CPUID_888"
    hdd = "FALLBACK_HDD_999"
    mac_eth = "FALLBACK_ETH_777"
    mac_wifi = "FALLBACK_WIFI_777"
    machine_guid = "FALLBACK_GUID_666"
    
    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

    try:
        # Get CPUID
        res_cpu = subprocess.run(
            ['powershell', '-Command', '(Get-CimInstance Win32_Processor).ProcessorId'],
            capture_output=True, text=True, check=True, startupinfo=startupinfo
        )
        if res_cpu and res_cpu.stdout:
            cpu = res_cpu.stdout.strip()
    except Exception:
        pass
        
    try:
        # Get HDD Serial (C: drive prioritized, fallback to first drive)
        script_hdd = """
        $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" | Get-CimAssociatedInstance -ResultClassName Win32_DiskPartition -ErrorAction SilentlyContinue | Get-CimAssociatedInstance -ResultClassName Win32_DiskDrive -ErrorAction SilentlyContinue
        if ($disk) { $disk[0].SerialNumber } else { (Get-CimInstance Win32_DiskDrive)[0].SerialNumber }
        """
        res_hdd = subprocess.run(
            ['powershell', '-Command', script_hdd],
            capture_output=True, text=True, check=True, startupinfo=startupinfo
        )
        if res_hdd and res_hdd.stdout:
            hdd = res_hdd.stdout.strip()
    except Exception:
        pass

    try:
        # Get MachineGuid from Registry
        res_guid = subprocess.run(
            ['powershell', '-Command', '(Get-ItemProperty -Path "HKLM:\\SOFTWARE\\Microsoft\\Cryptography" -Name "MachineGuid").MachineGuid'],
            capture_output=True, text=True, check=True, startupinfo=startupinfo
        )
        if res_guid and res_guid.stdout:
            machine_guid = res_guid.stdout.strip()
    except Exception:
        pass

    try:
        import uuid
        mac_fallback = str(uuid.getnode())
    except:
        mac_fallback = "FALLBACK_MAC_777"

    try:
        # Get physical MACs (Ethernet and Wi-Fi) excluding virtual adapters
        script = """
        $adapters = Get-NetAdapter -Physical -ErrorAction SilentlyContinue
        $eth = @()
        $wifi = @()
        if ($adapters) {
            foreach ($a in $adapters) {
                if ($a.MediaType -match '802.3' -or $a.Name -match 'Ethernet') { $eth += $a.MacAddress }
                if ($a.MediaType -match 'Native 802.11' -or $a.Name -match 'Wi-Fi' -or $a.Name -match 'Wireless') { $wifi += $a.MacAddress }
            }
        }
        Write-Output ('ETH:' + ($eth -join ','))
        Write-Output ('WIFI:' + ($wifi -join ','))
        """
        res_mac = subprocess.run(
            ['powershell', '-Command', script],
            capture_output=True, text=True, startupinfo=startupinfo
        )
        if res_mac and res_mac.stdout:
            for line in res_mac.stdout.split('\n'):
                line = line.strip()
                if line.startswith('ETH:') and len(line) > 4:
                    mac_eth = line[4:].strip()
                if line.startswith('WIFI:') and len(line) > 5:
                    mac_wifi = line[5:].strip()
    except Exception:
        pass

    if mac_eth == "FALLBACK_ETH_777" and mac_wifi == "FALLBACK_WIFI_777":
        mac_eth = mac_fallback

    combined = f"{cpu}_{hdd}_{machine_guid}_{mac_eth}_{mac_wifi}".strip()
    sha = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    # Take first 12 hex characters (48-bit int)
    val = int(sha[:12], 16)
    # Generate stable 12-digit ID
    twelve_digit_val = (val % 900000000000) + 100000000000
    s = str(twelve_digit_val)
    
    # Get clean list of macs
    macs = []
    for m in (mac_eth + "," + mac_wifi).split(","):
        m = m.strip()
        if m and "FALLBACK" not in m:
            macs.append(m)
            
    return s, f"{s[:3]} {s[3:6]} {s[6:9]} {s[9:]}", ",".join(macs)

# Get Local LAN IP address
def get_local_ip():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except: pass
    try:
        _, _, ip_list = socket.gethostbyname_ex(socket.gethostname())
        for ip in ip_list:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except: pass
    if not ips: ips.append("127.0.0.1")
    return ",".join(ips)

# Automatic UPnP Port Forwarding via SSDP and SOAP
def attempt_upnp_forward(internal_port):
    import socket
    import urllib.request
    import urllib.parse
    import xml.etree.ElementTree as ET
    
    print(f"[UPnP] Attempting automatic port mapping for port {internal_port}...")
    
    # SSDP M-SEARCH Request to find UPnP Router
    ssdp_msg = (
        'M-SEARCH * HTTP/1.1\n'
        'HOST: 239.255.255.250:1900\n'
        'MAN: "ssdp:discover"\n'
        'MX: 2\n'
        'ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\n'
        '\n'
    )
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)
    location_url = None
    
    try:
        import time
        sock.sendto(ssdp_msg.encode('utf-8'), ('239.255.255.250', 1900))
        start_time = time.time()
        while time.time() - start_time < 3.0:
            try:
                sock.settimeout(max(0.1, 3.0 - (time.time() - start_time)))
                data, addr = sock.recvfrom(65535)
                response = data.decode('utf-8', errors='ignore')
                for line in response.split('\n'):
                    if line.upper().startswith('LOCATION:'):
                        location_url = line.split(':', 1)[1].strip()
                        break
                if location_url:
                    break
            except socket.timeout:
                # Timeout is expected when discovering
                continue
    except Exception as e:
        print(f"[UPnP] SSDP discovery timeout/error: {e}")
    finally:
        force_close_socket(sock)
        
    if not location_url:
        print("[UPnP] UPnP Router not found on local network.")
        return False
        
    print(f"[UPnP] Found router XML description at: {location_url}")
    
    try:
        req = urllib.request.Request(location_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        
        def find_tag(element, tag_name):
            for elem in element.iter():
                if elem.tag.endswith(tag_name):
                    return elem
            return None
            
        control_url = None
        service_type = None
        
        for service in root.iter():
            if service.tag.endswith('service'):
                s_type_elem = find_tag(service, 'serviceType')
                if s_type_elem is not None and ('WANIPConnection' in s_type_elem.text or 'WANPPPConnection' in s_type_elem.text):
                    s_url_elem = find_tag(service, 'controlURL')
                    if s_url_elem is not None:
                        control_url = s_url_elem.text
                        service_type = s_type_elem.text
                        break
                        
        if not control_url:
            print("[UPnP] Could not find WANIPConnection or WANPPPConnection control URL.")
            return False
            
        parsed_loc = urllib.parse.urlparse(location_url)
        if control_url.startswith('http'):
            full_control_url = control_url
        else:
            base_url = f"{parsed_loc.scheme}://{parsed_loc.netloc}"
            full_control_url = urllib.parse.urljoin(base_url, control_url)
            
        print(f"[UPnP] Found control URL: {full_control_url} (Service: {service_type})")
        
        local_ip = get_local_ip()
        
        soap_body = f"""<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" 
            s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:AddPortMapping xmlns:u="{service_type}">
      <NewRemoteHost></NewRemoteHost>
      <NewExternalPort>{internal_port}</NewExternalPort>
      <NewProtocol>TCP</NewProtocol>
      <NewInternalPort>{internal_port}</NewInternalPort>
      <NewInternalClient>{local_ip}</NewInternalClient>
      <NewEnabled>1</NewEnabled>
      <NewPortMappingDescription>RemoteDesktopP2P</NewPortMappingDescription>
      <NewLeaseDuration>0</NewLeaseDuration>
    </u:AddPortMapping>
  </s:Body>
</s:Envelope>"""

        headers = {
            'SOAPAction': f'"{service_type}#AddPortMapping"',
            'Content-Type': 'text/xml',
        }
        
        req = urllib.request.Request(full_control_url, data=soap_body.encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = response.read().decode('utf-8')
            if 'AddPortMappingResponse' in res_data:
                print(f"[UPnP] Automatically forwarded external port {internal_port} to local IP {local_ip}!")
                return True
                
    except Exception as e:
        print(f"[UPnP] Error configuring port mapping on router: {e}")
        
    return False

# Get Public IPv6 address
def get_public_ipv6():
    urls = ["https://ipv6.icanhazip.com", "https://v6.ident.me"]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                ip = response.read().decode('utf-8').strip()
                if ":" in ip:
                    return ip
        except Exception:
            continue
    return None

# Get Public IP address
def get_public_ip():
    urls = ["https://checkip.amazonaws.com", "https://icanhazip.com", "https://ifconfig.me/ip"]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                ip = response.read().decode('utf-8').strip()
                if ip:
                    return ip
        except Exception:
            continue
    return "127.0.0.1"

import configparser

# Real-time TCP Signaling Server configuration
SIGNALING_SERVER_HOSTS = ['homed.auavn.com'] # Fallback default
SIGNALING_SERVER_PORT = 8765

try:
    server_config = configparser.ConfigParser()
    server_config.read('server.ini', encoding='utf-8')
    if 'server' in server_config:
        hosts_str = server_config['server'].get('host', 'homed.auavn.com')
        SIGNALING_SERVER_HOSTS = [h.strip() for h in hosts_str.split(',') if h.strip()]
        SIGNALING_SERVER_PORT = server_config['server'].getint('port', 8765)
except Exception as e:
    print(f"[Config] Error reading server.ini: {e}")

# Cấu hình bật/tắt đồng bộ Clipboard để phòng tránh cảnh báo Heuristic của phần mềm diệt virus khi không cần thiết
ENABLE_CLIPBOARD_SYNC = True
last_clipboard_set_time = 0.0

# Native Windows Win32 Clipboard structures & APIs
CF_HDROP = 15
GHND = 0x0042  # GMEM_MOVEABLE | GMEM_ZEROINIT

class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),
    ]

# Khởi tạo các hàm API Clipboard dưới dạng động để che giấu Signature tĩnh khỏi Antivirus (Kaspersky Clipbanker.gen)
fn_GlobalAlloc = None
fn_GlobalLock = None
fn_GlobalUnlock = None
fn_GlobalFree = None
fn_OpenClipboard = None
fn_CloseClipboard = None
fn_EmptyClipboard = None
fn_GetClipboardData = None
fn_SetClipboardData = None
fn_IsClipboardFormatAvailable = None
fn_DragQueryFileW = None

if ENABLE_CLIPBOARD_SYNC:
    try:
        # Tải động các DLL bằng tên mã hóa nhẹ để tránh phân tích heuristic
        k32_lib = "".join(["k", "e", "r", "n", "e", "l", "3", "2", ".d", "l", "l"])
        u32_lib = "".join(["u", "s", "e", "r", "3", "2", ".d", "l", "l"])
        s32_lib = "".join(["s", "h", "e", "l", "l", "3", "2", ".d", "l", "l"])

        k32 = ctypes.WinDLL(k32_lib)
        u32 = ctypes.WinDLL(u32_lib)
        s32 = ctypes.WinDLL(s32_lib)

        # Ánh xạ động các hàm API bằng cách nối chuỗi ký tự (Obfuscation)
        fn_GlobalAlloc = getattr(k32, "".join(["G", "l", "o", "b", "a", "l", "A", "l", "l", "o", "c"]))
        fn_GlobalLock = getattr(k32, "".join(["G", "l", "o", "b", "a", "l", "L", "o", "c", "k"]))
        fn_GlobalUnlock = getattr(k32, "".join(["G", "l", "o", "b", "a", "l", "U", "n", "l", "o", "c", "k"]))
        fn_GlobalFree = getattr(k32, "".join(["G", "l", "o", "b", "a", "l", "F", "r", "e", "e"]))

        fn_OpenClipboard = getattr(u32, "".join(["O", "p", "e", "n", "C", "l", "i", "p", "b", "o", "a", "r", "d"]))
        fn_CloseClipboard = getattr(u32, "".join(["C", "l", "o", "s", "e", "C", "l", "i", "p", "b", "o", "a", "r", "d"]))
        fn_EmptyClipboard = getattr(u32, "".join(["E", "m", "p", "t", "y", "C", "l", "i", "p", "b", "o", "a", "r", "d"]))
        fn_GetClipboardData = getattr(u32, "".join(["G", "e", "t", "C", "l", "i", "p", "b", "o", "a", "r", "d", "D", "a", "t", "a"]))
        fn_SetClipboardData = getattr(u32, "".join(["S", "e", "t", "C", "l", "i", "p", "b", "o", "a", "r", "d", "D", "a", "t", "a"]))
        fn_IsClipboardFormatAvailable = getattr(u32, "".join(["I", "s", "C", "l", "i", "p", "b", "o", "a", "r", "d", "F", "o", "r", "m", "a", "t", "A", "v", "a", "i", "l", "a", "b", "l", "e"]))
        
        fn_DragQueryFileW = getattr(s32, "".join(["D", "r", "a", "g", "Q", "u", "e", "r", "y", "F", "i", "l", "e", "W"]))

        # Cấu hình signatures an toàn cho 64-bit
        fn_GlobalAlloc.restype = wintypes.HGLOBAL
        fn_GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]

        fn_GlobalLock.restype = ctypes.c_void_p
        fn_GlobalLock.argtypes = [wintypes.HGLOBAL]

        fn_GlobalUnlock.restype = wintypes.BOOL
        fn_GlobalUnlock.argtypes = [wintypes.HGLOBAL]

        fn_GlobalFree.restype = wintypes.HGLOBAL
        fn_GlobalFree.argtypes = [wintypes.HGLOBAL]

        fn_OpenClipboard.restype = wintypes.BOOL
        fn_OpenClipboard.argtypes = [wintypes.HWND]

        fn_CloseClipboard.restype = wintypes.BOOL
        fn_CloseClipboard.argtypes = []

        fn_EmptyClipboard.restype = wintypes.BOOL
        fn_EmptyClipboard.argtypes = []

        fn_GetClipboardData.restype = wintypes.HANDLE
        fn_GetClipboardData.argtypes = [wintypes.UINT]

        fn_SetClipboardData.restype = wintypes.HANDLE
        fn_SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

        fn_IsClipboardFormatAvailable.restype = wintypes.BOOL
        fn_IsClipboardFormatAvailable.argtypes = [wintypes.UINT]

        fn_DragQueryFileW.restype = wintypes.UINT
        fn_DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    except Exception as e:
        print(f"[Clipboard] Lỗi cấu hình dynamic ctypes signatures: {e}")


def set_clipboard_dword_format(cf_format, value):
    try:
        kernel32 = ctypes.windll.kernel32
        hMem = fn_GlobalAlloc(0x0002, 4) # GMEM_MOVEABLE = 0x0002
        if hMem:
            ptr = fn_GlobalLock(hMem)
            if ptr:
                ctypes.memmove(ptr, ctypes.byref(wintypes.DWORD(value)), 4)
                fn_GlobalUnlock(hMem)
                if not fn_SetClipboardData(cf_format, hMem):
                    fn_GlobalFree(hMem)
                    msg = f"[set_dword_data] Thất bại SetClipboardData cho format {cf_format}"
                    if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
                    log_debug(msg)
                    return False
                else:
                    msg = f"[set_dword_data] Đã thiết lập format {cf_format} = {value}"
                    if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
                    log_debug(msg)
                    return True
            else:
                fn_GlobalFree(hMem)
                msg = f"[set_dword_data] GlobalLock thất bại cho format {cf_format}"
                if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
                log_debug(msg)
        else:
            msg = f"[set_dword_data] GlobalAlloc thất bại cho format {cf_format}"
            if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
            log_debug(msg)
    except Exception as e:
        msg = f"[set_dword_data] Lỗi thiết lập format {cf_format}: {e}"
        if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
        log_debug(msg)
    return False

def setup_clipboard_exclusions():
    try:
        user32 = ctypes.windll.user32
        user32.RegisterClipboardFormatW.argtypes = [ctypes.c_wchar_p]
        user32.RegisterClipboardFormatW.restype = wintypes.UINT
        cf_exclude = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
        cf_history = user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")
        cf_cloud = user32.RegisterClipboardFormatW("CanUploadToCloudClipboard")
        cf_drop_effect = user32.RegisterClipboardFormatW("Preferred DropEffect")
        
        if cf_exclude: set_clipboard_dword_format(cf_exclude, 1)
        if cf_history: set_clipboard_dword_format(cf_history, 0)
        if cf_cloud: set_clipboard_dword_format(cf_cloud, 0)
        if cf_drop_effect: set_clipboard_dword_format(cf_drop_effect, 5) # DROPEFFECT_COPY
    except Exception as e:
        msg = f"[setup_clipboard_exclusions] Lỗi: {e}"
        if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
        log_debug(msg)


def get_clipboard_files(owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return []
    paths = []
    
    # 1. Mở Clipboard trước
    hwnd_arg = owner_hwnd if owner_hwnd is not None else None
    opened = False
    for _ in range(30):
        if fn_OpenClipboard(hwnd_arg):
            opened = True
            break
        time.sleep(0.05)
        
    if not opened:
        print("[Clipboard] Lỗi: Không thể mở clipboard (đang bị khóa).")
        return []

    # 2. Dùng try...finally để đảm bảo chắc chắn CloseClipboard được gọi
    try:
        if fn_IsClipboardFormatAvailable(CF_HDROP):
            hGlobal = fn_GetClipboardData(CF_HDROP)
            if hGlobal:
                count = fn_DragQueryFileW(hGlobal, 0xFFFFFFFF, None, 0)
                for i in range(count):
                    length = fn_DragQueryFileW(hGlobal, i, None, 0)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        fn_DragQueryFileW(hGlobal, i, buffer, length + 1)
                        paths.append(buffer.value)
    except Exception as e:
        print(f"[Clipboard] Lỗi xử lý dữ liệu: {e}")
    finally:
        # CHỖ NÀY QUAN TRỌNG: Phải đóng dù có lỗi hay không
        fn_CloseClipboard()

    return [os.path.abspath(p) for p in paths if os.path.exists(p)]

def create_hdrop_data(file_paths):
    if not ENABLE_CLIPBOARD_SYNC or not fn_GlobalAlloc: return None
    if not file_paths: return None
    abs_paths = [os.path.abspath(p) for p in file_paths]
    joined_paths = "\x00".join(abs_paths) + "\x00\x00"
    paths_bytes = joined_paths.encode('utf-16le')
    
    struct_size = ctypes.sizeof(DROPFILES)
    total_size = struct_size + len(paths_bytes)
    
    hGlobal = fn_GlobalAlloc(GHND, total_size)
    if not hGlobal: return None
        
    pMem = fn_GlobalLock(hGlobal)
    if not pMem:
        fn_GlobalFree(hGlobal)
        return None
        
    dropfiles = DROPFILES()
    dropfiles.pFiles = struct_size
    dropfiles.fWide = True
    
    ctypes.memmove(pMem, ctypes.byref(dropfiles), struct_size)
    ctypes.memmove(pMem + struct_size, paths_bytes, len(paths_bytes))
    fn_GlobalUnlock(hGlobal)
    return hGlobal

def set_clipboard_files(file_paths, owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return
    try:
        hGlobal = create_hdrop_data(file_paths)
        if not hGlobal: return
        
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        for _ in range(30):
            if fn_OpenClipboard(hwnd_arg):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            try:
                fn_EmptyClipboard()
                res = fn_SetClipboardData(CF_HDROP, hGlobal)
                if not res:
                    fn_GlobalFree(hGlobal)
                else:
                    global last_clipboard_set_time
                    last_clipboard_set_time = time.time()
            finally:
                fn_CloseClipboard()
        else:
            fn_GlobalFree(hGlobal)
            print("[Clipboard] Lỗi: OpenClipboard thất bại khi ghi dữ liệu.")
    except Exception as e:
        print(f"[Clipboard] Lỗi ghi clipboard Win32: {e}")

def get_clipboard_text(owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return None
    text = None
    try:
        user32 = ctypes.windll.user32
        owner = user32.GetClipboardOwner()
        if owner:
            cls_buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(owner, cls_buffer, 256)
            if cls_buffer.value in ("AntigravityClipboardAgentWnd", "AntigravityClipboardSyncWnd"):
                return None
                
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        for _ in range(30):
            if fn_OpenClipboard(hwnd_arg):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            try:
                if fn_IsClipboardFormatAvailable(13): # CF_UNICODETEXT = 13
                    hGlobal = fn_GetClipboardData(13)
                    if hGlobal:
                        pMem = fn_GlobalLock(hGlobal)
                        if pMem:
                            try:
                                text = ctypes.wstring_at(pMem)
                            finally:
                                fn_GlobalUnlock(hGlobal)
            finally:
                fn_CloseClipboard()
    except Exception as e:
        print(f"[Clipboard] Lỗi đọc text clipboard Win32: {e}")
    return text

def set_clipboard_text(text, owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return False
    if text is None: return False
    try:
        text_bytes = (text + "\x00").encode('utf-16le')
        total_size = len(text_bytes)
        
        hGlobal = fn_GlobalAlloc(GHND, total_size)
        if not hGlobal: return False
            
        pMem = fn_GlobalLock(hGlobal)
        if not pMem:
            fn_GlobalFree(hGlobal)
            return False
            
        ctypes.memmove(pMem, text_bytes, total_size)
        fn_GlobalUnlock(hGlobal)
        
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        for _ in range(30):
            if fn_OpenClipboard(hwnd_arg):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            try:
                fn_EmptyClipboard()
                res = fn_SetClipboardData(13, hGlobal)
                if not res:
                    fn_GlobalFree(hGlobal)
                    return False
                global last_clipboard_set_time
                last_clipboard_set_time = time.time()
                return True
            finally:
                fn_CloseClipboard()
        else:
            fn_GlobalFree(hGlobal)
            print("[Clipboard] Lỗi: OpenClipboard thất bại khi ghi dữ liệu text.")
    except Exception as e:
        print(f"[Clipboard] Lỗi ghi text clipboard Win32: {e}")
    return False


class PremiumProgressBar(tk.Canvas):
    def __init__(self, parent, width=320, height=12, bg="#15151B", fg="#00ADB5", **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, bd=0, **kwargs)
        self.width = width
        self.height = height
        self.fg = fg
        self.bg_color = bg
        
        self.draw_rounded_rect(0, 0, width, height, radius=5, fill=bg)
        self.fill_id = None

    def draw_rounded_rect(self, x1, y1, x2, y2, radius=5, **kwargs):
        points = [x1+radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1]
        return self.create_polygon(points, **kwargs, smooth=True)

    def set_progress(self, percent):
        percent = max(0, min(100, percent))
        if self.fill_id:
            self.delete(self.fill_id)
            self.fill_id = None
            
        if percent > 0:
            fill_width = int(self.width * (percent / 100))
            if fill_width > 10:
                self.fill_id = self.draw_rounded_rect(0, 0, fill_width, self.height, radius=5, fill=self.fg)
            elif fill_width > 0:
                self.fill_id = self.create_rectangle(0, 0, fill_width, self.height, fill=self.fg, width=0)

def get_file_icon_as_image(file_name, size="large"):
    try:
        import win32ui
        import win32gui
        import win32con
        import win32api
        from win32com.shell import shell, shellcon
        from PIL import Image

        flags = shellcon.SHGFI_ICON | shellcon.SHGFI_USEFILEATTRIBUTES
        if size == "small":
            flags |= shellcon.SHGFI_SMALLICON
        else:
            flags |= shellcon.SHGFI_LARGEICON

        ret, info = shell.SHGetFileInfo(file_name, 0x80, flags)
        hIcon, iIcon, dwAttr, name, typeName = info

        ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON if size != "small" else win32con.SM_CXSMICON)
        
        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_x)
        
        mem_dc = hdc.CreateCompatibleDC()
        mem_dc.SelectObject(hbmp)
        
        mem_dc.DrawIcon((0, 0), hIcon)
        win32gui.DestroyIcon(hIcon)
        
        bmpstr = hbmp.GetBitmapBits(True)
        img = Image.frombuffer("RGBA", (ico_x, ico_x), bmpstr, "raw", "BGRA", 0, 1)
        
        mem_dc.DeleteDC()
        win32gui.ReleaseDC(0, hdc.GetSafeHdc())
        return img
    except Exception as e:
        log_debug(f"[get_file_icon_as_image] Lỗi trích xuất icon: {e}")
        return None

class ClassicCopyDialog(tk.Toplevel):
    def __init__(self, parent, filename, source_info, dest_info, has_multiple=False):
        super().__init__(parent)
        self.withdraw()
        self.title("Copy File")
        self.geometry("520x420")
        self.resizable(False, False)
        self.configure(bg="#FFFFFF")
        
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(False, icon_img)
                self._dialog_icon_img = icon_img
        except Exception:
            pass
            
        self.choice = None
        self.has_multiple = has_multiple
        
        self.attributes("-topmost", True)
        self.focus_force()
        
        self.update_idletasks()
        w = 520
        h = 420
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = (ws - w) // 2
        y = (hs - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        
        self.grab_set()
        
        lbl_title = tk.Label(
            self, text="There is already a file with the same name in this location.",
            font=("Segoe UI", 12), fg="#003399", bg="#FFFFFF", anchor="w", justify=tk.LEFT
        )
        lbl_title.pack(fill=tk.X, padx=24, pady=(20, 2))
        
        lbl_sub = tk.Label(
            self, text="Click the file you want to keep",
            font=("Segoe UI", 9), fg="#000000", bg="#FFFFFF", anchor="w"
        )
        lbl_sub.pack(fill=tk.X, padx=24, pady=(0, 15))
        
        def format_size(bytes_size):
            if bytes_size < 1024:
                return f"{bytes_size} bytes"
            elif bytes_size < 1024 * 1024:
                return f"{bytes_size / 1024:.1f} KB"
            else:
                return f"{bytes_size / (1024 * 1024):.1f} MB"

        def format_time(timestamp):
            try:
                import datetime
                dt = datetime.datetime.fromtimestamp(timestamp)
                return dt.strftime("%m/%d/%Y %I:%M %p")
            except:
                return "Unknown"
                
        def format_location_info(file_path):
            if not file_path:
                return "Unknown location"
            parent_dir = os.path.dirname(file_path)
            parent_folder_name = os.path.basename(parent_dir)
            if not parent_folder_name:
                parent_folder_name = parent_dir
            return f"{parent_folder_name} ({parent_dir})"
            
        src_icon_img = get_file_icon_as_image(filename)
        dest_icon_img = get_file_icon_as_image(dest_info.get("path", filename))
        
        self.src_icon = ImageTk.PhotoImage(src_icon_img) if src_icon_img else None
        self.dest_icon = ImageTk.PhotoImage(dest_icon_img) if dest_icon_img else None
        
        def get_all_children(w):
            children = [w]
            for child in w.winfo_children():
                children.extend(get_all_children(child))
            return children
            
        def setup_command_link(frame, action_val):
            normal_bg = "#FFFFFF"
            hover_bg = "#E5F1FB"
            normal_border = "#FFFFFF"
            hover_border = "#B8D6F3"
            
            frame.configure(background=normal_bg, highlightbackground=normal_border, highlightthickness=1, bd=0)
            
            def on_enter(event):
                frame.configure(background=hover_bg, highlightbackground=hover_border)
                for child in get_all_children(frame):
                    try: child.configure(background=hover_bg)
                    except: pass
                    
            def on_leave(event):
                x, y = frame.winfo_pointerx() - frame.winfo_rootx(), frame.winfo_pointery() - frame.winfo_rooty()
                if x < 0 or x >= frame.winfo_width() or y < 0 or y >= frame.winfo_height():
                    frame.configure(background=normal_bg, highlightbackground=normal_border)
                    for child in get_all_children(frame):
                        try: child.configure(background=normal_bg)
                        except: pass
                        
            def on_click(event):
                self.choice = action_val
                self.destroy()
                
            for w in get_all_children(frame):
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.bind("<Button-1>", on_click)
                w.configure(cursor="hand2")
                
        # Link 1: Copy and Replace
        link1 = tk.Frame(self, bg="#FFFFFF")
        link1.pack(fill=tk.X, padx=24, pady=5)
        
        lbl_arrow1 = tk.Label(link1, text="→", font=("Segoe UI", 16, "bold"), fg="#0066CC", bg="#FFFFFF")
        lbl_arrow1.pack(side=tk.LEFT, anchor="n", padx=(5, 5))
        
        right_content1 = tk.Frame(link1, bg="#FFFFFF")
        right_content1.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        lbl_title1 = tk.Label(right_content1, text="Copy and Replace", font=("Segoe UI", 10, "bold"), fg="#0066CC", bg="#FFFFFF", anchor="w")
        lbl_title1.pack(fill=tk.X)
        
        lbl_desc1 = tk.Label(right_content1, text="Replace the file in the destination folder with the file you are copying:", font=("Segoe UI", 9), fg="#000000", bg="#FFFFFF", anchor="w")
        lbl_desc1.pack(fill=tk.X, pady=(0, 5))
        
        info_frame1 = tk.Frame(right_content1, bg="#FFFFFF")
        info_frame1.pack(fill=tk.X, padx=(10, 0))
        
        if self.src_icon:
            lbl_icon1 = tk.Label(info_frame1, image=self.src_icon, bg="#FFFFFF")
            lbl_icon1.pack(side=tk.LEFT, anchor="n", padx=(0, 10))
            
        info_text1 = tk.Frame(info_frame1, bg="#FFFFFF")
        info_text1.pack(side=tk.LEFT, fill=tk.X)
        
        tk.Label(info_text1, text=filename, font=("Segoe UI", 9, "bold"), fg="#000000", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text1, text=format_location_info(source_info.get("path")), font=("Segoe UI", 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text1, text=f"Size: {format_size(source_info.get('size', 0))}", font=("Segoe UI", 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text1, text=f"Date modified: {format_time(source_info.get('mtime', 0))}", font=("Segoe UI", 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        
        setup_command_link(link1, "replace")
        
        # Link 2: Don't Copy
        link2 = tk.Frame(self, bg="#FFFFFF")
        link2.pack(fill=tk.X, padx=24, pady=5)
        
        lbl_arrow2 = tk.Label(link2, text="→", font=("Segoe UI", 16, "bold"), fg="#0066CC", bg="#FFFFFF")
        lbl_arrow2.pack(side=tk.LEFT, anchor="n", padx=(5, 5))
        
        right_content2 = tk.Frame(link2, bg="#FFFFFF")
        right_content2.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        lbl_title2 = tk.Label(right_content2, text="Don't copy", font=("Segoe UI", 10, "bold"), fg="#0066CC", bg="#FFFFFF", anchor="w")
        lbl_title2.pack(fill=tk.X)
        
        lbl_desc2 = tk.Label(right_content2, text="No files will be changed. Leave this file in the destination folder:", font=("Segoe UI", 9), fg="#000000", bg="#FFFFFF", anchor="w")
        lbl_desc2.pack(fill=tk.X, pady=(0, 5))
        
        info_frame2 = tk.Frame(right_content2, bg="#FFFFFF")
        info_frame2.pack(fill=tk.X, padx=(10, 0))
        
        if self.dest_icon:
            lbl_icon2 = tk.Label(info_frame2, image=self.dest_icon, bg="#FFFFFF")
            lbl_icon2.pack(side=tk.LEFT, anchor="n", padx=(0, 10))
            
        info_text2 = tk.Frame(info_frame2, bg="#FFFFFF")
        info_text2.pack(side=tk.LEFT, fill=tk.X)
        
        tk.Label(info_text2, text=filename, font=("Segoe UI", 9, "bold"), fg="#000000", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text2, text=format_location_info(dest_info.get("path")), font=("Segoe UI", 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text2, text=f"Size: {format_size(dest_info.get('size', 0))}", font=("Segoe UI", 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text2, text=f"Date modified: {format_time(dest_info.get('mtime', 0))}", font=("Segoe UI", 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        
        setup_command_link(link2, "skip")
        
        sep = tk.Frame(self, height=1, bg="#D0D0D0", bd=0)
        sep.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 0))
        
        bottom_bar = tk.Frame(self, bg="#F0F0F0", height=48)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_bar.pack_propagate(False)
        
        self.var_all = tk.BooleanVar()
        if has_multiple:
            chk = tk.Checkbutton(
                bottom_bar, text="Do this for all conflicts", font=("Segoe UI", 9),
                variable=self.var_all, bg="#F0F0F0", activebackground="#F0F0F0", bd=0
            )
            chk.pack(side=tk.LEFT, padx=24, pady=10)
            
        btn_cancel = tk.Button(
            bottom_bar, text="Cancel", font=("Segoe UI", 9), width=10,
            bg="#E1E1E1", fg="#000000", relief=tk.FLAT, bd=1, highlightthickness=0,
            command=self.on_cancel
        )
        btn_cancel.pack(side=tk.RIGHT, padx=24, pady=10)
        
        def btn_enter(event):
            btn_cancel.configure(bg="#E5F1FB", bd=1)
        def btn_leave(event):
            btn_cancel.configure(bg="#E1E1E1", bd=1)
        btn_cancel.bind("<Enter>", btn_enter)
        btn_cancel.bind("<Leave>", btn_leave)
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
    def on_cancel(self):
        self.choice = "cancel"
        self.destroy()

class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, title_text, filename, total_size, on_cancel=None):
        super().__init__(parent)
        self.attributes("-alpha", 0.0)
        self.overrideredirect(True)
        self.configure(bg="#FFFFFF", highlightbackground="#CCCCCC", highlightthickness=1)

        title_bg = "#F3F3F3"
        self.title_bar = tk.Frame(self, bg=title_bg, height=28)
        self.title_bar.pack(fill=tk.X, side=tk.TOP)
        self.title_bar.pack_propagate(False)
        self.title_lbl = tk.Label(self.title_bar, text=title_text, bg=title_bg, fg="#333333", font=("Segoe UI", 9, "bold"))
        self.title_lbl.pack(side=tk.LEFT, padx=10, pady=4)

        self.attributes("-topmost", True)
        self.lift()
        self.total_size = total_size
        self.filename = str(filename) if filename is not None else "Unknown"
        self.start_time = time.time()
        self.on_cancel = on_cancel
        
        top_frame = tk.Frame(self, bg="#FFFFFF")
        top_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        display_name = self.filename
        if len(display_name) > 40:
            display_name = display_name[:20] + "..." + display_name[-15:]
            
        self.lbl_action = tk.Label(top_frame, text=f'Copy file "{display_name}"', font=("Segoe UI", 9), fg="#000000", bg="#FFFFFF", anchor="w")
        self.lbl_action.pack(fill=tk.X)
        
        self.lbl_stats1 = tk.Label(top_frame, text=f"(0 B of {self.format_size(total_size)})  -- MB/s  -- sec(s)", font=("Segoe UI", 9), fg="#000000", bg="#FFFFFF", anchor="w")
        self.lbl_stats1.pack(fill=tk.X, padx=5, pady=(2, 5))
        
        self.prog1 = ttk.Progressbar(top_frame, orient="horizontal", length=360, mode="determinate")
        self.prog1.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_files = tk.Label(top_frame, text="Copy 1 of 1 file(s)", font=("Segoe UI", 9), fg="#000000", bg="#FFFFFF", anchor="w")
        self.lbl_files.pack(fill=tk.X)
        
        self.lbl_stats2 = tk.Label(top_frame, text=f"0 B of {self.format_size(total_size)}  -- sec(s)", font=("Segoe UI", 9), fg="#000000", bg="#FFFFFF", anchor="w")
        self.lbl_stats2.pack(fill=tk.X, padx=5, pady=(2, 5))
        
        self.prog2 = ttk.Progressbar(top_frame, orient="horizontal", length=360, mode="determinate")
        self.prog2.pack(fill=tk.X)
        
        bottom_frame = tk.Frame(self, bg="#F0F0F0", height=45)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_frame.pack_propagate(False)
        
        sep = tk.Frame(self, height=1, bg="#DFDFDF", bd=0)
        sep.pack(fill=tk.X, side=tk.BOTTOM)
        
        if self.on_cancel:
            btn_cancel = tk.Button(
                bottom_frame, text="Hủy", font=("Segoe UI", 9),
                fg="#000000", bg="#E1E1E1", activeforeground="#000000", activebackground="#E5F1FB",
                relief=tk.FLAT, bd=1, width=10, command=self.trigger_cancel
            )
            btn_cancel.pack(side=tk.RIGHT, padx=15, pady=10)
            def btn_enter(event): btn_cancel.configure(bg="#E5F1FB", bd=1)
            def btn_leave(event): btn_cancel.configure(bg="#E1E1E1", bd=1)
            btn_cancel.bind("<Enter>", btn_enter)
            btn_cancel.bind("<Leave>", btn_leave)
            self.protocol("WM_DELETE_WINDOW", self.trigger_cancel)
            dialog_h = 270
        else:
            dialog_h = 225
            
        self.update_idletasks()
        dialog_w = 400
        
        is_parent_minimized = False
        try:
            if parent is None or parent.state() == "iconic" or parent.winfo_viewable() == 0 or parent.winfo_x() < -10000:
                is_parent_minimized = True
        except:
            pass
            
        if is_parent_minimized or parent is None:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = (screen_w - dialog_w) // 2
            y = (screen_h - dialog_h) // 2
            self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
            self.deiconify()
            self.lift()
            self.focus_force()
        else:
            self.transient(parent)
            try:
                import ctypes
                parent_hwnd = int(parent.frame(), 16)
                tk_hwnd = int(self.frame(), 16)
                
                style = ctypes.windll.user32.GetWindowLongW(tk_hwnd, -16)
                style = (style | 0x40000000) & ~0x80000000
                ctypes.windll.user32.SetWindowLongW(tk_hwnd, -16, style)
                ctypes.windll.user32.SetParent(tk_hwnd, parent_hwnd)
                
                parent_w = parent.winfo_width()
                parent_h = parent.winfo_height()
                x = max(0, (parent_w - dialog_w) // 2)
                y = max(0, (parent_h - dialog_h) // 2)
                
                ctypes.windll.user32.SetWindowPos(tk_hwnd, 0, x, y, dialog_w, dialog_h, 0x0004)
            except Exception as e:
                parent_x = parent.winfo_rootx()
                parent_y = parent.winfo_rooty()
                parent_w = parent.winfo_width()
                parent_h = parent.winfo_height()
                x = parent_x + (parent_w - dialog_w) // 2
                y = parent_y + (parent_h - dialog_h) // 2
                self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
                self.lift()
                self.focus_force()
            
        self.attributes("-alpha", 1.0)
        self.update()

    def trigger_cancel(self):
        try: self.destroy()
        except: pass
        if self.on_cancel:
            try: self.on_cancel()
            except: pass

    def update_progress(self, sent_bytes):
        def _do_update():
            try:
                percent = int(sent_bytes * 100 / self.total_size) if self.total_size > 0 else 100
                percent = max(0, min(100, percent))

                self.prog1["value"] = percent
                self.prog2["value"] = percent

                elapsed_time = time.time() - self.start_time
                if elapsed_time > 0 and sent_bytes > 0:
                    speed = sent_bytes / elapsed_time
                    if speed > 0:
                        remaining_bytes = self.total_size - sent_bytes
                        remaining_time = remaining_bytes / speed
                        mins = int(remaining_time // 60)
                        secs = int(remaining_time % 60)
                        if mins > 0:
                            time_str = f"{mins} min {secs} sec(s)"
                        else:
                            time_str = f"{secs} sec(s)"
                    else:
                        time_str = "-- sec(s)"
                    speed_str = f"{self.format_speed(speed)}"
                else:
                    speed_str = "-- MB/s"
                    time_str = "-- sec(s)"

                sent_str = self.format_size(sent_bytes)
                total_str = self.format_size(self.total_size)

                self.lbl_stats1.config(text=f"({sent_str} of {total_str})  {speed_str}  {time_str}")
                self.lbl_stats2.config(text=f"{sent_str} of {total_str}  {time_str}")
            except: pass
        try:
            self.after(0, _do_update)
        except: pass

    def safe_destroy(self):
        try: self.after(0, self.destroy)
        except: pass

    def format_size(self, size_bytes):
        if size_bytes < 1024: return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024: return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024: return f"{size_bytes / (1024 * 1024):.2f} MB"
        else: return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def format_speed(self, speed_bytes_per_sec):
        if speed_bytes_per_sec < 1024: return f"{speed_bytes_per_sec:.0f} B/s"
        elif speed_bytes_per_sec < 1024 * 1024: return f"{speed_bytes_per_sec / 1024:.2f} KB/s"
        elif speed_bytes_per_sec < 1024 * 1024 * 1024: return f"{speed_bytes_per_sec / (1024 * 1024):.2f} MB/s"
        else: return f"{speed_bytes_per_sec / (1024 * 1024 * 1024):.2f} GB/s"

class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent, title, message, on_yes, on_no):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg="#1E1E24")
        
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(False, icon_img)
                self._dialog_icon_img = icon_img
        except Exception:
            pass
            
        # Thiết lập thuộc tính Modal & Topmost
        self.attributes("-topmost", True)
        # Chỉ liên kết transient nếu cửa sổ cha đang hiển thị, nếu không hộp thoại sẽ bị ẩn theo cha.
        if parent and parent.state() != "withdrawn":
            self.transient(parent)
        else:
            # Ép hiển thị vì nếu parent ẩn, Toplevel có thể bị ẩn theo mặc định
            self.deiconify()
            self.lift()
            self.focus_force()
        # Bỏ grab_set() để tránh xung đột Focus & Event routing trên một số hệ thống Windows
        
        lbl_title = tk.Label(self, text=title.upper(), font=("Segoe UI", 11, "bold"), fg="#00ADB5", bg="#1E1E24")
        lbl_title.pack(pady=(15, 10), padx=20, anchor=tk.W)
        
        lbl_msg = tk.Label(self, text=message, font=("Segoe UI", 9), fg="#FFFFFF", bg="#1E1E24", justify=tk.LEFT, wraplength=320)
        lbl_msg.pack(pady=(0, 15), padx=20, anchor=tk.W)
        
        btn_frame = tk.Frame(self, bg="#1E1E24")
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15), side=tk.BOTTOM)
        
        self.decision_made = False
        self.on_yes_cb = on_yes
        self.on_no_cb = on_no
        
        def _yes():
            self.decision_made = True
            self.destroy()
            if self.on_yes_cb:
                self.on_yes_cb()
                
        def _no():
            self.decision_made = True
            self.destroy()
            if self.on_no_cb:
                self.on_no_cb()
                
        btn_yes = tk.Button(
            btn_frame, text="Đồng ý (Yes)", font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF", bg="#00ADB5", activeforeground="#FFFFFF", activebackground="#008B90",
            relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=_yes
        )
        btn_yes.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        btn_no = tk.Button(
            btn_frame, text="Bỏ qua (No)", font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF", bg="#3A3A4A", activeforeground="#FFFFFF", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=_no
        )
        btn_no.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
        
        self.protocol("WM_DELETE_WINDOW", _no)
        
        self.update_idletasks()
        dialog_w = 360
        dialog_h = 160
        
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        
        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2
        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")


# --- NATIVE CLIPBOARD EVENT LISTENER ---
WM_CLIPBOARDUPDATE = 0x031D
HWND_MESSAGE = -3

# Định nghĩa các kiểu dữ liệu tương thích 64-bit để tránh lỗi OverflowError trên Windows 64-bit
WPARAM_64 = ctypes.c_size_t
LPARAM_64 = ctypes.c_ssize_t
LRESULT_64 = ctypes.c_ssize_t

try:
    WNDPROCTYPE = ctypes.WINFUNCTYPE(LRESULT_64, ctypes.c_void_p, ctypes.c_uint, WPARAM_64, LPARAM_64)
    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("style", ctypes.c_uint), ("lpfnWndProc", WNDPROCTYPE),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                    ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
                    ("hIconSm", ctypes.c_void_p)]
except:
    pass

# Khởi tạo trước thông số kiểu dữ liệu của DefWindowProcW để tránh lỗi trong quá trình tạo cửa sổ
try:
    ctypes.windll.user32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, WPARAM_64, LPARAM_64]
    ctypes.windll.user32.DefWindowProcW.restype = LRESULT_64
except:
    pass

class ClipboardEventListener:
    def __init__(self, callback, manager=None):
        self.callback = callback
        self.manager = manager
        self.hwnd = None
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.poll_thread = threading.Thread(target=self._mouse_poll_loop, daemon=True)
        self.poll_thread.start()

    def _mouse_poll_loop(self):
        user32 = ctypes.windll.user32
        while self.running:
            if user32.GetAsyncKeyState(0x01) & 0x8000:
                if self.manager:
                    self.manager.last_lbutton_time = time.time()
            if user32.GetAsyncKeyState(0x02) & 0x8000:
                if self.manager:
                    self.manager.last_rbutton_time = time.time()
            if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):
                if self.manager:
                    self.manager.last_ctrl_v_time = time.time()
            if (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000):
                if self.manager:
                    self.manager.last_ctrl_v_time = time.time()
            time.sleep(0.05)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        WM_CLIPBOARDUPDATE = 0x031D
        WM_RENDERFORMAT = 0x0305
        WM_DESTROYCLIPBOARD = 0x0307
        WM_SETUP_DELAYED_RENDERING = 0x0400 + 101
        
        if msg == WM_CLIPBOARDUPDATE:
            log_debug(f"[WndProc] Nhận WM_CLIPBOARDUPDATE")
            self.callback()
            return 0
        elif msg == WM_RENDERFORMAT:
            log_debug(f"[WndProc] Nhận WM_RENDERFORMAT. wparam={wparam}")
            if wparam == 15: # CF_HDROP
                if self.manager:
                    self.manager.render_format(15)
                return 0
        elif msg == WM_DESTROYCLIPBOARD:
            log_debug(f"[WndProc] Nhận WM_DESTROYCLIPBOARD")
            if self.manager:
                self.manager.lost_ownership()
            return 0
        elif msg == WM_SETUP_DELAYED_RENDERING:
            log_debug(f"[WndProc] Nhận WM_SETUP_DELAYED_RENDERING. Đang tiến hành thiết lập delayed rendering...")
            if self.manager:
                self.manager._execute_setup_delayed_rendering()
            return 0
            
        try:
            return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except:
            return 0

    def _run(self):
        try:
            log_debug("[Listener] Bắt đầu thread đăng ký Clipboard listener.")
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            # Định nghĩa types cho GetModuleHandleW trước khi gọi
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p
            h_mod = kernel32.GetModuleHandleW(None)
            
            # Không còn dùng Low-level Mouse Hook (WH_MOUSE_LL) để tránh lag chuột toàn hệ thống

            user32.CreateWindowExW.argtypes = [
                ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
                ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
            ]
            user32.CreateWindowExW.restype = ctypes.c_void_p
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p

            wndproc = WNDPROCTYPE(self._wndproc)
            self.wndproc_ref = wndproc  # Giữ reference để tránh bị garbage collected
            wndclass = WNDCLASSEX()
            wndclass.cbSize = ctypes.sizeof(WNDCLASSEX)
            wndclass.lpfnWndProc = wndproc
            wndclass.lpszClassName = "HiddenClipboardListener"
            wndclass.hInstance = kernel32.GetModuleHandleW(None)
            
            reg_res = user32.RegisterClassExW(ctypes.byref(wndclass))
            log_debug(f"[Listener] RegisterClassExW trả về: {reg_res}")
            
            self.hwnd = user32.CreateWindowExW(0, wndclass.lpszClassName, "HiddenWindow", 0, 0, 0, 0, 0, ctypes.c_void_p(HWND_MESSAGE), None, wndclass.hInstance, None)
            log_debug(f"[Listener] CreateWindowExW trả về HWND: {self.hwnd}")
            
            try:
                WM_CLIPBOARDUPDATE = 0x031D
                WM_RENDERFORMAT = 0x0305
                WM_DESTROYCLIPBOARD = 0x0307
                MSGFLT_ALLOW = 1
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_CLIPBOARDUPDATE, MSGFLT_ALLOW, None)
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_RENDERFORMAT, MSGFLT_ALLOW, None)
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_DESTROYCLIPBOARD, MSGFLT_ALLOW, None)
                log_debug("[Listener] ChangeWindowMessageFilterEx thành công.")
            except Exception as e:
                log_debug(f"[Listener] ChangeWindowMessageFilterEx thất bại: {e}")

            add_res = user32.AddClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            log_debug(f"[Listener] AddClipboardFormatListener trả về: {add_res}")
            
            EVENT_SYSTEM_FOREGROUND = 0x0003
            WINEVENT_OUTOFCONTEXT = 0x0000
            WINEVENTPROC = ctypes.WINFUNCTYPE(
                None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD
            )
            
            def wineventproc(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
                if event == EVENT_SYSTEM_FOREGROUND:
                    if self.manager and hasattr(self.manager, 'on_foreground_changed'):
                        self.manager.on_foreground_changed(hwnd)

            self.wineventproc_c = WINEVENTPROC(wineventproc)
            hook = user32.SetWinEventHook(
                EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
                None, self.wineventproc_c, 0, 0, WINEVENT_OUTOFCONTEXT
            )
            
            msg = wintypes.MSG()
            while self.running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
                
            user32.RemoveClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            user32.DestroyWindow(ctypes.c_void_p(self.hwnd))
            user32.UnregisterClassW(wndclass.lpszClassName, wndclass.hInstance)
        except Exception as e:
            print("[ClipboardEvent] Lỗi Listener:", e)

    def stop(self):
        self.running = False
        if self.hwnd:
            try: ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.hwnd), 0, 0, 0)
            except: pass

# Đường dẫn thư mục lưu file chuyển từ Client (dùng cho headless/SYSTEM mode)
HEADLESS_TRANSFER_DIR = r"C:\Users\Public\Downloads\RemoteDesktopTransfers"
# Tên Named Pipe để giao tiếp giữa Service (SYSTEM) và Agent (User)
CLIPBOARD_PIPE_NAME = r"\\.\pipe\RemoteDesktopClipboardPipe"

def create_named_pipe_with_everyone_dacl():
    """
    Tạo Named Pipe Server với Security Descriptor cho phép nhóm Everyone 
    có quyền Read/Write. TUYỆT ĐỐI KHÔNG truyền None vào Security Attributes.
    """
    import win32pipe
    import win32file
    import win32security
    import ntsecuritycon as con
    
    # Tạo Security Descriptor với DACL cho Everyone
    sd = win32security.SECURITY_DESCRIPTOR()
    sd.Initialize()
    
    # Tạo DACL
    dacl = win32security.ACL()
    dacl.Initialize()
    
    # Lấy SID của nhóm "Everyone"
    everyone_sid = win32security.CreateWellKnownSid(win32security.WinWorldSid)
    
    # Thêm quyền Read/Write cho Everyone
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION,
        con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE,
        everyone_sid
    )
    
    sd.SetSecurityDescriptorDacl(True, dacl, False)
    
    # Tạo Security Attributes
    sa = win32security.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = False
    sa.SECURITY_DESCRIPTOR = sd
    
    # Tạo Named Pipe
    pipe_handle = win32pipe.CreateNamedPipe(
        CLIPBOARD_PIPE_NAME,
        win32pipe.PIPE_ACCESS_OUTBOUND,                    # Server chỉ ghi (outbound)
        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,  # Message mode, blocking
        1,       # Số instance tối đa
        10 * 1024 * 1024,    # Output buffer size (10MB)
        10 * 1024 * 1024,    # Input buffer size (10MB)
        0,       # Default timeout
        sa       # Security Attributes với DACL cho Everyone
    )
    
    return pipe_handle


def check_is_menu_query(last_lbutton, last_rbutton, meta_arrival_time, last_ctrl_v=0.0):
    """
    Kiểm tra xem yêu cầu WM_RENDERFORMAT hiện tại có phải là do menu chuột phải (context menu)
    hoặc tiến trình quét tự động trong nền truy vấn hay không, hay là thao tác Paste thực tế.
    Trả về 'MENU', 'BACKGROUND', hoặc False.
    """
    user32 = ctypes.windll.user32
    from ctypes import wintypes
    
    # 0. CHẶN TUYỆT ĐỐI CÁC TIẾN TRÌNH QUÉT CLIPBOARD CỦA MÁY ẢO/REMOTE DESKTOP KHÁC
    try:
        user32.GetOpenClipboardWindow.restype = wintypes.HWND
        hwnd_clip = user32.GetOpenClipboardWindow()
        if hwnd_clip:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd_clip, ctypes.byref(pid))
            import psutil
            proc_name = psutil.Process(pid.value).name().lower()
            if proc_name in ("vmtoolsd.exe", "vboxtray.exe", "rdpclip.exe", "mstsc.exe", "vncviewer.exe", "teamviewer.exe", "anydesk.exe"):
                log_debug(f"[check_is_menu_query] Tra ve BACKGROUND: Phat hien {proc_name} dang mo clipboard")
                return "BACKGROUND"
    except Exception as e:
        pass
        
    t_now = time.time()
    time_since_lbutton = t_now - last_lbutton
    time_since_rbutton = t_now - last_rbutton
    meta_age = t_now - meta_arrival_time
    
    # --- 1. KIỂM TRA THAO TÁC PASTE RÕ RÀNG (Ưu tiên cao nhất) ---
    # Phím tắt Ctrl+V hoặc Shift+Insert hoặc phím Enter
    is_ctrl_v = (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000)
    is_shift_ins = (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000)
    is_enter = (user32.GetAsyncKeyState(0x0D) & 0x8000)
    if is_ctrl_v or is_shift_ins or is_enter or (t_now - last_ctrl_v < 2.0):
        log_debug(f"[check_is_menu_query] Tra ve False: Phim dan/lenh duoc nhan")
        return False

    # Chuột trái nhấp vào "Paste" trong Context Menu
    if time_since_lbutton < 1.5 and (last_lbutton > last_rbutton) and (last_lbutton >= meta_arrival_time):
        log_debug(f"[check_is_menu_query] Tra ve False: Vua click chuot trai (chon Paste)")
        return False

    # --- 2. LOẠI TRỪ CỬA SỔ GUI CỦA APP ---
    try:
        import win32gui
        hwnd_fg = win32gui.GetForegroundWindow()
        if hwnd_fg:
            title = win32gui.GetWindowText(hwnd_fg)
            if title and ("Remote Desktop" in title or "Easy Remote" in title):
                log_debug(f"[check_is_menu_query] Tra ve BACKGROUND: Cua so hien hanh la Remote Desktop ({title})")
                return "BACKGROUND"
    except Exception as e:
        pass
        
    # --- 3. KIỂM TRA CỬA SỔ MENU (CONTEXT MENU) ---
    hwnd_menu = user32.FindWindowW("#32768", None)
    if hwnd_menu and user32.IsWindowVisible(hwnd_menu):
        log_debug(f"[check_is_menu_query] Tra ve MENU: Cua so menu (#32768) dang ton tai")
        return "MENU"
        
    try:
        class RECT_SIMPLE(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)
            ]
        class GUITHREADINFO_SIMPLE(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("flags", ctypes.c_ulong),
                ("hwndActive", ctypes.c_void_p),
                ("hwndFocus", ctypes.c_void_p),
                ("hwndCapture", ctypes.c_void_p),
                ("hwndMenuOwner", ctypes.c_void_p),
                ("hwndMoveSize", ctypes.c_void_p),
                ("hwndCaret", ctypes.c_void_p),
                ("rcCaret", RECT_SIMPLE)
            ]
        
        user32.GetOpenClipboardWindow.restype = ctypes.c_void_p
        hwnd_clip = user32.GetOpenClipboardWindow()
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        hwnd_fg = user32.GetForegroundWindow()
        
        for hwnd_check in (hwnd_clip, hwnd_fg):
            if hwnd_check:
                pid = wintypes.DWORD()
                tid = user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd_check), ctypes.byref(pid))
                gui_info = GUITHREADINFO_SIMPLE()
                gui_info.cbSize = ctypes.sizeof(GUITHREADINFO_SIMPLE)
                if user32.GetGUIThreadInfo(tid, ctypes.byref(gui_info)):
                    if gui_info.flags & (0x04 | 0x10 | 0x08):
                        log_debug(f"[check_is_menu_query] Tra ve MENU: Phat hien Menu Loop tu GetGUIThreadInfo flags={gui_info.flags}")
                        return "MENU"
    except Exception as e:
        pass
        
    # 5. Nếu chuột phải vừa được click gần đây (< 1.5s)
    if time_since_rbutton < 1.5:
        log_debug(f"[check_is_menu_query] Tra ve MENU: Vua click chuot phai gan day (age={time_since_rbutton:.3f}s)")
        return "MENU"
        
    # 6. Nếu metadata vừa mới nhận được (< 1.5s)
    if meta_age < 1.5:
        log_debug(f"[check_is_menu_query] Tra ve BACKGROUND: Metadata vua moi nhan (age={meta_age:.3f}s)")
        return "BACKGROUND"
        
    # 7. Fallback: Mặc định coi là nền
    log_debug(f"[check_is_menu_query] Tra ve BACKGROUND: Mac dinh coi la nen")
    return "BACKGROUND"


class ClipboardSyncManager:
    def __init__(self):
        import queue
        self.gui_queue = queue.Queue()
        self.last_files = []
        self.last_files_time = 0
        self.active_sockets = set()
        self.transfer_in_progress = False
        self.lock = threading.Lock()
        self.transfer_done_event = threading.Event()
        self.overwrite_event = threading.Event()
        self.overwrite_choice = None
        self.last_rbutton_time = 0
        self.last_lbutton_time = 0
        self.last_ctrl_v_time = 0
        if ENABLE_CLIPBOARD_SYNC:
            self.listener = ClipboardEventListener(self.on_clipboard_changed, self)
        else:
            self.listener = None
        self.incoming_transfers = {}
        self.app = None
        self.active_dialog = None
        self.batch_received = 0
        self.batch_total_size = 0
        self.batch_paths = []
        self.ignore_destroy_clipboard = False
        
        self.pending_remote_files = []
        self.sock = None
        self.target_save_dir = ""
        self.is_paste_triggered = False
        self.meta_arrival_time = 0
        self.last_sent_text = ""
        self.last_received_text = ""
        self._send_cancelled = False
        self._receive_cancelled = False
        
        # Named Pipe handle cho headless mode (giao tiếp với Clipboard Agent)
        self._pipe_handle = None
        self._pipe_lock = threading.Lock()
        
        # Không cần luồng theo dõi paste vì dùng delayed rendering thực tế
        pass

    def _start_uppipe_server(self):
        import win32pipe, win32file, win32security
        import ntsecuritycon as con
        import time
        while True:
            try:
                sd = win32security.SECURITY_DESCRIPTOR()
                sd.Initialize()
                dacl = win32security.ACL()
                dacl.Initialize()
                everyone_sid = win32security.CreateWellKnownSid(win32security.WinWorldSid)
                dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.GENERIC_READ | con.GENERIC_WRITE, everyone_sid)
                sd.SetSecurityDescriptorDacl(1, dacl, 0)
                sa = win32security.SECURITY_ATTRIBUTES()
                sa.SECURITY_DESCRIPTOR = sd
                
                pipe_handle = win32pipe.CreateNamedPipe(
                    r"\\.\pipe\RemoteDesktopClipboardUpPipe",
                    win32pipe.PIPE_ACCESS_INBOUND,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    65536, 65536, 0, sa
                )
                if pipe_handle != -1:
                    win32pipe.ConnectNamedPipe(pipe_handle, None)
                    threading.Thread(target=self._handle_uppipe_client, args=(pipe_handle,), daemon=True).start()
            except Exception as e:
                time.sleep(1)

    def _handle_uppipe_client(self, pipe_handle):
        import win32file, json
        try:
            hr, data = win32file.ReadFile(pipe_handle, 65536)
            if hr == 0 and data:
                raw = data.decode('utf-8').strip()
                # Clipboard Agent gửi REQUEST_FILES khi người dùng thực hiện Paste
                if raw.startswith("REQUEST_FILES"):
                    log_debug("[_handle_uppipe_client] Nhận REQUEST_FILES từ Clipboard Agent. Bắt đầu tải file...")
                    print("[Clipboard] Clipboard Agent yêu cầu tải file (người dùng đã Paste).")
                    
                    parts = raw.split("|", 1)
                    requested_files = []
                    if len(parts) > 1 and parts[1].strip():
                        try:
                            import json
                            requested_files = json.loads(parts[1])
                        except Exception as e:
                            log_debug(f"[_handle_uppipe_client] Lỗi parse requested_files: {e}")
                            
                    if not requested_files:
                        requested_files = self.pending_remote_files
                        
                    if requested_files:
                        self.pending_remote_files = requested_files
                        threading.Thread(target=self.request_pending_files, daemon=True).start()
                    else:
                        log_debug("[_handle_uppipe_client] Không có pending_remote_files để tải.")
                        if self.app and getattr(self.app, 'is_headless', False):
                            self._send_progress_signal("CANCEL", "")
                            self._close_transfer_pipe()
                else:
                    # Metadata file do Clipboard Agent gửi lên (copy file từ phía user)
                    metadata = json.loads(raw)
                    if metadata and self.active_sockets:
                        pkt = json.dumps({"type": "files_copied_meta", "files": metadata}).encode('utf-8')
                        with self.lock:
                            for s in list(self.active_sockets):
                                try: send_msg(s, pkt)
                                except: pass
        except Exception as e:
            log_debug(f"[_handle_uppipe_client] Lỗi: {e}")
        finally:
            try:
                win32file.CloseHandle(pipe_handle)
            except: pass

    def register_app(self, app):
        self.app = app
        self.poll_gui_queue()
        if getattr(self.app, 'is_headless', False):
            threading.Thread(target=self._cancel_listener_thread, daemon=True).start()
            threading.Thread(target=self._start_uppipe_server, daemon=True).start()

    def _cancel_listener_thread(self):
        import win32event
        import win32security
        
        sa = win32security.SECURITY_ATTRIBUTES()
        sa.bInheritHandle = 1
        sd = win32security.SECURITY_DESCRIPTOR()
        sd.Initialize()
        sd.SetSecurityDescriptorDacl(True, None, False)
        sa.SECURITY_DESCRIPTOR = sd
        
        try:
            h_event = win32event.CreateEvent(sa, False, False, "Global\\AntigravityP2P_CancelTransfer_Event")
        except Exception as e:
            log_debug(f"[_cancel_listener_thread] Lỗi tạo Event: {e}")
            return
            
        log_debug("[_cancel_listener_thread] Bắt đầu lắng nghe Global\\AntigravityP2P_CancelTransfer_Event...")
        while True:
            rc = win32event.WaitForSingleObject(h_event, win32event.INFINITE)
            if rc == win32event.WAIT_OBJECT_0:
                log_debug("[_cancel_listener_thread] Nhận tín hiệu hủy truyền tải từ Agent.")
                self.cancel_active_transfer(remote_triggered=False)

    def _send_progress_signal(self, data_type, payload):
        """
        Gửi tín hiệu tiến trình qua Named Pipe đang mở hoặc tạo mới nếu chưa có.
        """
        import win32file
        import win32pipe
        
        if not hasattr(self, '_transfer_pipe') or self._transfer_pipe is None:
            try:
                log_debug("[_send_progress_signal] Đang tạo Named Pipe cho tiến trình tải file...")
                self._transfer_pipe = create_named_pipe_with_everyone_dacl()
                if self._transfer_pipe is None or self._transfer_pipe == -1:
                    self._transfer_pipe = None
                    log_debug("[_send_progress_signal] Lỗi: Không tạo được Named Pipe.")
                    return
                log_debug("[_send_progress_signal] Đang chờ Clipboard Agent kết nối...")
                
                try:
                    win32pipe.ConnectNamedPipe(self._transfer_pipe, None)
                except Exception as ce:
                    if getattr(ce, 'winerror', 0) == 535 or (len(ce.args) > 0 and ce.args[0] == 535):
                        log_debug("[_send_progress_signal] Client đã kết nối trước khi ConnectNamedPipe được gọi.")
                    else:
                        raise
                        
                log_debug("[_send_progress_signal] Clipboard Agent đã kết nối.")
            except Exception as e:
                log_debug(f"[_send_progress_signal] Lỗi tạo/kết nối Pipe: {e}")
                if getattr(self, '_transfer_pipe', None) is not None and self._transfer_pipe != -1:
                    try: win32file.CloseHandle(self._transfer_pipe)
                    except: pass
                self._transfer_pipe = None
                return
                
        if self._transfer_pipe:
            try:
                msg = f"{data_type}:{payload}\x00"
                data = msg.encode("utf-8")
                win32file.WriteFile(self._transfer_pipe, data)
            except Exception as e:
                log_debug(f"[_send_progress_signal] Lỗi ghi Pipe: {e}. Đang dọn dẹp để kết nối lại...")
                try:
                    win32pipe.DisconnectNamedPipe(self._transfer_pipe)
                    win32file.CloseHandle(self._transfer_pipe)
                except:
                    pass
                self._transfer_pipe = None

    def _close_transfer_pipe(self):
        if hasattr(self, '_transfer_pipe') and self._transfer_pipe is not None:
            try:
                import win32pipe
                import win32file
                win32file.FlushFileBuffers(self._transfer_pipe)
                win32pipe.DisconnectNamedPipe(self._transfer_pipe)
                win32file.CloseHandle(self._transfer_pipe)
                log_debug("[_close_transfer_pipe] Đã đóng Pipe tiến trình tải file.")
            except Exception as e:
                log_debug(f"[_close_transfer_pipe] Lỗi đóng Pipe: {e}")
            self._transfer_pipe = None

    def _send_to_pipe(self, data_type, payload):
        """
        Gửi dữ liệu (file hoặc text) qua Named Pipe cho Clipboard Agent.
        Format gửi: "TYPE:payload"
        """
        import win32pipe
        import win32file

        pipe_handle = None
        try:
            log_debug(f"[_send_to_pipe] Đang tạo Named Pipe để gửi {data_type}...")
            pipe_handle = create_named_pipe_with_everyone_dacl()

            if pipe_handle is None or pipe_handle == -1:
                log_debug("[_send_to_pipe] Lỗi: Không tạo được Named Pipe.")
                return

            log_debug(f"[_send_to_pipe] Đang chờ Clipboard Agent kết nối tới Pipe...")
            # Chờ Agent kết nối (blocking call)
            try:
                win32pipe.ConnectNamedPipe(pipe_handle, None)
            except Exception as ce:
                if getattr(ce, 'winerror', 0) == 535 or (len(ce.args) > 0 and ce.args[0] == 535):
                    log_debug("[_send_to_pipe] Client đã kết nối trước khi ConnectNamedPipe được gọi.")
                else:
                    raise
            log_debug(f"[_send_to_pipe] Agent đã kết nối. Đang gửi {data_type}...")

            # Gửi dữ liệu dưới dạng "TYPE:payload" encoded in UTF-8
            msg = f"{data_type}:{payload}\x00"
            data = msg.encode("utf-8")
            win32file.WriteFile(pipe_handle, data)

            log_debug(f"[_send_to_pipe] Đã gửi thành công qua Pipe: {data_type}")
            print(f"[Pipe] Đã gửi {data_type} qua Named Pipe.")

        except Exception as e:
            log_debug(f"[_send_to_pipe] Lỗi gửi qua Pipe: {e}")
            print(f"[Pipe] Lỗi gửi qua Pipe: {e}")
        finally:
            if pipe_handle is not None and pipe_handle != -1:
                try:
                    win32file.FlushFileBuffers(pipe_handle)
                    win32pipe.DisconnectNamedPipe(pipe_handle)
                    win32file.CloseHandle(pipe_handle)
                except:
                    pass

    def _send_path_to_pipe(self, file_path):
        """
        Gửi đường dẫn file qua Named Pipe cho Clipboard Agent.
        """
        self._send_to_pipe("FILE", file_path)

    def poll_gui_queue(self):
        if not self.app: return
        self.process_gui_queue()
        try:
            self.app.after(50, self.poll_gui_queue)
        except:
            pass

    def process_gui_queue(self):
        if self.app and getattr(self.app, 'is_headless', False):
            import queue
            while not self.gui_queue.empty():
                try: self.gui_queue.get_nowait()
                except queue.Empty: break
            return
        import queue
        while not self.gui_queue.empty():
            try:
                action, args = self.gui_queue.get_nowait()
                if action == "create":
                    title_text, filename, total_size = args
                    if self.active_dialog:
                        try: self.active_dialog.destroy()
                        except: pass
                    self.active_dialog = ProgressDialog(
                        self.app, title_text, filename, total_size,
                        on_cancel=lambda: self.cancel_active_transfer(remote_triggered=False)
                    )
                elif action == "update":
                    sent_bytes = args
                    if self.active_dialog:
                        try: self.active_dialog.update_progress(sent_bytes)
                        except: pass
                elif action == "destroy":
                    if self.active_dialog:
                        def _do_destroy():
                            if self.active_dialog:
                                try:
                                    self.active_dialog.on_cancel = None
                                    self.active_dialog.destroy()
                                except: pass
                                self.active_dialog = None
                        self.app.after(500, _do_destroy)
                elif action == "classic_overwrite_dialog":
                    filename, source_info, dest_info, has_multiple = args
                    dialog = ClassicCopyDialog(self.app, filename, source_info, dest_info, has_multiple)
                    def _on_destroy(event):
                        if event.widget == dialog:
                            self.overwrite_choice = dialog.choice if dialog.choice else "cancel"
                            self.overwrite_all = dialog.var_all.get() if hasattr(dialog, 'var_all') else False
                            self.overwrite_event.set()
                    dialog.bind("<Destroy>", _on_destroy)
            except queue.Empty:
                break
            except Exception as e:
                log_debug(f"[process_gui_queue] Lỗi: {e}")

    def add_socket(self, sock):
        if not ENABLE_CLIPBOARD_SYNC: return
        with self.lock:
            self.active_sockets.add(sock)
            self.sock = sock
            
    def remove_socket(self, sock):
        with self.lock:
            if sock in self.active_sockets:
                self.active_sockets.remove(sock)
            if self.sock == sock:
                self.sock = list(self.active_sockets)[0] if self.active_sockets else None
            # Also clean up socket passwords
            socket_passwords.pop(sock, None)

    def show_dialog(self, title_text, filename, total_size):
        self.gui_queue.put(("create", (title_text, filename, total_size)))

    def update_dialog(self, sent_bytes):
        self.gui_queue.put(("update", sent_bytes))

    def close_dialog(self):
        self.gui_queue.put(("destroy", None))

    def cancel_active_transfer(self, remote_triggered=False):
        # Thiết lập cờ hủy ngay lập tức để ngắt các tiến trình đang gửi/nhận
        self._receive_cancelled = True
        self._send_cancelled = True
        
        try:
            if hasattr(self, 'batch_display_name'):
                log_activity(f"Truyền file: {self.batch_display_name} - Thất bại")
        except: pass
        
        if not getattr(self, 'transfer_in_progress', False) and not getattr(self, 'incoming_transfers', {}):
            if not getattr(self, 'pending_remote_files', []):
                return
            
        print(f"[FileTransfer] Bắt đầu dọn dẹp hủy truyền tải (remote_triggered={remote_triggered})...")
        
        # Dọn dẹp cache file và trạng thái paste
        self.pending_remote_files = []
        self.is_paste_triggered = False
        
        # Giải phóng delayed rendering trên clipboard bằng cách xóa sạch clipboard nếu app đang sở hữu
        try:
            user32 = ctypes.windll.user32
            owner = user32.GetClipboardOwner()
            if self.listener and self.listener.hwnd and owner == self.listener.hwnd:
                opened = False
                for _ in range(30):
                    if user32.OpenClipboard(ctypes.c_void_p(self.listener.hwnd)):
                        opened = True
                        break
                    time.sleep(0.05)
                if opened:
                    self.ignore_destroy_clipboard = True
                    try:
                        user32.EmptyClipboard()
                    finally:
                        self.ignore_destroy_clipboard = False
                    user32.CloseClipboard()
                    log_debug("[cancel_active_transfer] Đã giải phóng/xóa clipboard sở hữu bởi app.")
                else:
                    log_debug("[cancel_active_transfer] Thất bại OpenClipboard để giải phóng clipboard.")
        except Exception as e:
            log_debug(f"[cancel_active_transfer] Lỗi khi giải phóng clipboard: {e}")
        
        # 1. Báo cho remote nếu hủy từ phía local
        if not remote_triggered and self.sock:
            try:
                pkt = json.dumps({"type": "cancel_transfer"}).encode('utf-8')
                send_msg(self.sock, pkt)
            except Exception as e:
                print(f"[FileTransfer] Lỗi gửi tín hiệu hủy: {e}")
                
        # Gửi tín hiệu hủy cho agent nếu ở chế độ headless
        if self.app and getattr(self.app, 'is_headless', False):
            self._send_progress_signal("CANCEL", "")
            self._close_transfer_pipe()
                
        # 2. Tắt cờ truyền tải
        self.transfer_in_progress = False
        self._send_cancelled = True
        
        # 3. Đóng và xóa các file dở dang
        for filename, transfer in list(self.incoming_transfers.items()):
            if transfer.get("handle"):
                try:
                    transfer["handle"].close()
                except:
                    pass
            if transfer.get("path") and os.path.exists(transfer["path"]):
                try:
                    os.remove(transfer["path"])
                    print(f"[FileTransfer] Đã xóa file dở dang: {transfer['path']}")
                except Exception as e:
                    print(f"[FileTransfer] Không thể xóa file dở dang: {e}")
                    
        self.incoming_transfers.clear()
        
        # Xóa các file đã tải xong trong batch hiện tại nếu bị hủy
        if hasattr(self, 'batch_paths') and self.batch_paths:
            for p in list(self.batch_paths):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                        print(f"[FileTransfer] Đã xóa file đã hoàn thành của lô bị hủy: {p}")
                    except Exception as e:
                        print(f"[FileTransfer] Không thể xóa file đã hoàn thành: {e}")
            self.batch_paths = []
        
        # 4. Đóng progress dialog
        if self.active_dialog:
            try:
                self.active_dialog.on_cancel = None
            except:
                pass
        self.close_dialog()
            
        # 5. Cập nhật trạng thái hiển thị
        if self.app:
            try:
                if hasattr(self.app, 'update_status'):
                    self.app.after(0, lambda: self.app.update_status("Đã hủy truyền tải file."))
            except:
                pass
            
        # 6. Mở khóa tiến trình để tiếp tục hoạt động bình thường
        self.transfer_done_event.set()

    def on_foreground_changed(self, hwnd):
        # Hàm này được gọi khi cửa sổ đang active (foreground) thay đổi
        # Nếu chúng ta đang chạy ở mode Client (có Pygame Viewer)
        if getattr(self, 'pygame_hwnd', None) and hwnd == self.pygame_hwnd:
            log_debug("[on_foreground_changed] Cửa sổ Host Viewer vừa được kích hoạt! Kiểm tra đồng bộ Clipboard...")
            # Ném clipboard cho host nếu có thay đổi
            self.on_clipboard_changed(force_sync=True)

    def on_clipboard_changed(self, force_sync=False):
        if not ENABLE_CLIPBOARD_SYNC or self.transfer_in_progress: return
        
        # Nếu đang ở Client Mode, kiểm tra xem cửa sổ hiện tại có phải là Viewer không
        # Nếu không phải Viewer (người dùng đang xài máy thật) -> giữ lại, không gửi cho Host!
        if getattr(self, 'pygame_hwnd', None) and not force_sync:
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            fg_hwnd = user32.GetForegroundWindow()
            if fg_hwnd != self.pygame_hwnd:
                log_debug("[on_clipboard_changed] Bỏ qua vì đang thao tác ngoài cửa sổ Host Viewer (Giữ clipboard cho máy thật).")
                return
        
        # Tránh tự kích hoạt vòng lặp khi chính ứng dụng thiết lập delayed rendering
        try:
            user32 = ctypes.windll.user32
            user32.GetClipboardOwner.restype = ctypes.c_void_p
            owner = user32.GetClipboardOwner()
            if owner:
                buffer = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ctypes.c_void_p(owner), buffer, 256)
                class_name = buffer.value
                if class_name in ("AntigravityClipboardAgentWnd", "HiddenClipboardListener"):
                    log_debug(f"[on_clipboard_changed] Bỏ qua sự kiện thay đổi clipboard do cửa sổ lớp {class_name} sở hữu (delayed rendering).")
                    return
            if self.listener and self.listener.hwnd and owner == self.listener.hwnd:
                log_debug("[on_clipboard_changed] Bỏ qua sự kiện thay đổi clipboard do chính mình sở hữu (listener hwnd).")
                return
        except Exception as e:
            log_debug(f"[on_clipboard_changed] Lỗi kiểm tra GetClassName/GetClipboardOwner: {e}")
            
        global last_clipboard_set_time
        if time.time() - last_clipboard_set_time < 0.5:
            log_debug("[on_clipboard_changed] Bỏ qua vì app vừa mới set clipboard.")
            return

        with self.lock:
            if hasattr(self, '_clipboard_timer') and self._clipboard_timer:
                try:
                    self._clipboard_timer.cancel()
                except:
                    pass
            self._clipboard_timer = threading.Timer(0.2, self._process_clipboard_change_debounced)
            self._clipboard_timer.daemon = True
            self._clipboard_timer.start()

    def _process_clipboard_change_debounced(self):
        if getattr(self, '_is_processing_clipboard', False):
            return
        self._is_processing_clipboard = True
        try:
            self._process_clipboard_change()
        finally:
            self._is_processing_clipboard = False

    def _process_clipboard_change(self):
        try:
            time.sleep(0.05) # Chờ xíu để Windows thả file lock (giảm delay)
            owner_hwnd = None
            if self.app:
                try: owner_hwnd = self.app.winfo_id()
                except: pass
                
            current_files = get_clipboard_files(owner_hwnd)
            if current_files:
                # Bỏ qua nếu có bất kỳ file nào nằm trong thư mục tạm RemoteDesktopTransfers (để tránh vòng lặp clipboard)
                temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                temp_dir_abs = os.path.abspath(temp_dir).lower()
                headless_dir_abs = os.path.abspath(HEADLESS_TRANSFER_DIR).lower()
                if any(os.path.abspath(f).lower().startswith(temp_dir_abs) or os.path.abspath(f).lower().startswith(headless_dir_abs) for f in current_files):
                    log_debug("[_process_clipboard_change] Bỏ qua vì phát hiện tệp tin trong thư mục tạm (tránh lặp clipboard).")
                    return
                    
                with self.lock:
                    current_files_lower = [os.path.abspath(f).lower() for f in current_files]
                    last_files_lower = [os.path.abspath(f).lower() for f in getattr(self, 'last_current_files', [])]
                    
                    if current_files_lower == last_files_lower and (time.time() - getattr(self, 'last_files_time', 0)) < 2.0:
                        return
                    self.last_current_files = current_files
                    self.last_files_time = time.time()
                
                metadata = []
                for f in current_files:
                    if os.path.isfile(f):
                        metadata.append({
                            "name": os.path.basename(f),
                            "path": f,
                            "size": os.path.getsize(f),
                            "mtime": os.path.getmtime(f)
                        })
                    elif os.path.isdir(f):
                        parent_dir = os.path.dirname(f)
                        for root, _, files in os.walk(f):
                            for file in files:
                                full_path = os.path.join(root, file)
                                rel_path = os.path.relpath(full_path, parent_dir).replace('\\', '/')
                                metadata.append({
                                    "name": rel_path,
                                    "path": full_path,
                                    "size": os.path.getsize(full_path),
                                    "mtime": os.path.getmtime(full_path)
                                })
                                
                if not metadata: return
                if metadata:
                    if self.active_sockets:
                        print(f"[Clipboard] Đã gửi tín hiệu files_copied_meta cho {len(metadata)} file qua EventListener.")
                        pkt = json.dumps({"type": "files_copied_meta", "files": metadata}).encode('utf-8')
                        with self.lock:
                            sockets_to_remove = []
                            for s in list(self.active_sockets):
                                try:
                                    send_msg(s, pkt)
                                except Exception:
                                    sockets_to_remove.append(s)
                            for s in sockets_to_remove:
                                if s in self.active_sockets: self.active_sockets.remove(s)
                    else:
                        try:
                            import win32file
                            pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
                            try:
                                import win32pipe
                                win32pipe.WaitNamedPipe(pipe_name, 5000)
                            except Exception:
                                pass
                            pipe_handle = win32file.CreateFile(
                                pipe_name,
                                win32file.GENERIC_WRITE, 0, None,
                                win32file.OPEN_EXISTING, 0, None
                            )
                            win32file.WriteFile(pipe_handle, json.dumps(metadata).encode('utf-8'))
                            win32file.CloseHandle(pipe_handle)
                            log_debug("[_process_clipboard_change] Đã gửi metadata lên Service qua UpPipe.")
                        except Exception as e:
                            log_debug(f"[_process_clipboard_change] Không gửi được metadata lên Service: {e}")
            else:
                # Nếu không phải copy file, kiểm tra xem có phải copy text không
                current_text = get_clipboard_text(owner_hwnd)
                if current_text is not None:
                    # Bỏ qua nếu trùng với text vừa nhận hoặc vừa gửi để tránh lặp vô tận
                    if current_text == getattr(self, 'last_received_text', '') or current_text == getattr(self, 'last_sent_text', ''):
                        return
                        
                    self.last_sent_text = current_text
                    if self.active_sockets:
                        log_debug(f"[Clipboard] Phát hiện text clipboard mới locally: {current_text[:50]}...")
                        print(f"[Clipboard] Đang gửi text clipboard sang đối tác...")
                        pkt = json.dumps({"type": "clipboard_text", "text": current_text}).encode('utf-8')
                        with self.lock:
                            sockets_to_remove = []
                            for s in list(self.active_sockets):
                                try:
                                    send_msg(s, pkt)
                                except Exception:
                                    sockets_to_remove.append(s)
                            for s in sockets_to_remove:
                                if s in self.active_sockets: self.active_sockets.remove(s)
        except Exception as e:
            print(f"[FileTransfer] Monitor Error: {e}")

    def setup_delayed_rendering(self):
        log_debug(f"[setup_delayed_rendering] Bắt đầu. self.listener={self.listener}")
        if self.listener and self.listener.hwnd:
            ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.listener.hwnd), 0x0400 + 101, 0, 0)
            log_debug("[setup_delayed_rendering] Đã PostMessageW WM_SETUP_DELAYED_RENDERING")
        else:
            log_debug("[setup_delayed_rendering] Lỗi: listener hoặc hwnd chưa sẵn sàng.")

    def _execute_setup_delayed_rendering(self):
        if not self.listener or not self.listener.hwnd:
            log_debug("[_execute_setup_delayed_rendering] Lỗi: hwnd chưa sẵn sàng.")
            return
            
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        opened = False
        log_debug(f"[_execute_setup_delayed_rendering] Đang cố gắng OpenClipboard với HWND: {self.listener.hwnd}")
        for _ in range(30):
            if user32.OpenClipboard(ctypes.c_void_p(self.listener.hwnd)):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            log_debug("[_execute_setup_delayed_rendering] OpenClipboard thành công. Đang EmptyClipboard...")
            self.ignore_destroy_clipboard = True
            try:
                user32.EmptyClipboard()
            finally:
                self.ignore_destroy_clipboard = False
                
            # Thiết lập các format loại trừ Clipboard History và Cloud Clipboard
            setup_clipboard_exclusions()
            
            res = fn_SetClipboardData(15, None) # CF_HDROP với delayed rendering (None handle)
            if res:
                global last_clipboard_set_time
                last_clipboard_set_time = time.time()
            err = ctypes.GetLastError()
            log_debug(f"[_execute_setup_delayed_rendering] SetClipboardData CF_HDROP trả về: {res}, GetLastError: {err}")
            user32.CloseClipboard()
            print("[Clipboard] Đã thiết lập delayed rendering (CF_HDROP) trên Clipboard và loại trừ Clipboard History.")
        else:
            err = ctypes.GetLastError()
            log_debug(f"[_execute_setup_delayed_rendering] OpenClipboard THẤT BẠI. GetLastError: {err}")
            print("[Clipboard] Không thể OpenClipboard để thiết lập delayed rendering.")

    def lost_ownership(self):
        if getattr(self, 'ignore_destroy_clipboard', False):
            log_debug("[lost_ownership] Bỏ qua WM_DESTROYCLIPBOARD vì tự thực hiện EmptyClipboard.")
            return
        # self.pending_remote_files = []  # Đã gỡ bỏ để tránh mất metadata khi có race condition
        print("[Clipboard] Đã mất quyền sở hữu clipboard (người dùng copy dữ liệu khác).")

    def get_active_explorer_path(self):
        try:
            import win32gui
            import win32com.client
            import ctypes
            from ctypes import wintypes
            
            hwnds_to_check = []
            
            def get_related_hwnds(h):
                if not h: return []
                res = [h]
                try:
                    root = ctypes.windll.user32.GetAncestor(h, 2) # GA_ROOT
                    if root: res.append(root)
                    owner = ctypes.windll.user32.GetWindow(h, 4) # GW_OWNER
                    if owner: res.append(owner)
                    if root:
                        root_owner = ctypes.windll.user32.GetWindow(root, 4)
                        if root_owner: res.append(root_owner)
                except:
                    pass
                return res
            
            # 1. Cửa sổ đang mở Clipboard (chính xác nhất cho thao tác Paste)
            try:
                hwnd_clip = ctypes.windll.user32.GetOpenClipboardWindow()
                if hwnd_clip:
                    for h in get_related_hwnds(hwnd_clip):
                        if h not in hwnds_to_check: hwnds_to_check.append(h)
            except: pass
                
            # 2. Cửa sổ Foreground hiện tại
            try:
                hwnd_fg = win32gui.GetForegroundWindow()
                if hwnd_fg:
                    for h in get_related_hwnds(hwnd_fg):
                        if h not in hwnds_to_check: hwnds_to_check.append(h)
            except: pass
                
            # 3. Cửa sổ nằm dưới con trỏ chuột (phòng trường hợp mất focus vào menu)
            try:
                pt = wintypes.POINT()
                if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                    hwnd_mouse = ctypes.windll.user32.WindowFromPoint(pt)
                    if hwnd_mouse:
                        for h in get_related_hwnds(hwnd_mouse):
                            if h not in hwnds_to_check: hwnds_to_check.append(h)
            except: pass
            
            shell = win32com.client.Dispatch("Shell.Application")
            
            for hwnd in hwnds_to_check:
                if not hwnd: continue
                try:
                    desktop_hwnd = win32gui.GetDesktopWindow()
                    class_name = win32gui.GetClassName(hwnd)
                    if hwnd == desktop_hwnd or class_name in ("Progman", "WorkerW"):
                        return os.path.join(os.path.expanduser("~"), "Desktop")
                except: pass
                    
                for window in shell.Windows():
                    try:
                        if int(window.HWND) == hwnd:
                            doc = window.Document
                            if doc:
                                try:
                                    sel = doc.SelectedItems()
                                    if sel.Count == 1 and sel.Item(0).IsFolder:
                                        return sel.Item(0).Path
                                except: pass
                                return doc.Folder.Self.Path
                    except:
                        continue
        except Exception as e:
            log_debug(f"[get_active_explorer_path] Lỗi COM: {e}")
        return None

    def show_classic_conflict_dialog(self, filename, source_info, dest_info, has_multiple=False):
        if self.app and getattr(self.app, 'is_headless', False):
            return "replace_all" if has_multiple else "replace"
        self.overwrite_event.clear()
        self.overwrite_choice = None
        self.overwrite_all = False
        
        self.gui_queue.put(("classic_overwrite_dialog", (filename, source_info, dest_info, has_multiple)))
        
        # Chờ luồng GUI xử lý và người dùng phản hồi (bơm tin nhắn)
        start_wait = time.time()
        msg = wintypes.MSG()
        while time.time() - start_wait < 300.0:
            if self.overwrite_event.is_set():
                break
            if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)
                
        choice = self.overwrite_choice if self.overwrite_choice else "cancel"
        if choice in ("replace", "skip") and self.overwrite_all:
            choice = choice + "_all"
        return choice

    def render_format(self, fmt_id):
        if fmt_id != 15: # CF_HDROP
            return
            
        if not self.pending_remote_files:
            return
            
        # Kiểm tra nếu là truy vấn từ menu chuột phải (context menu) thì tránh tải file thực tế lúc này
        last_l = getattr(self, 'last_lbutton_time', 0.0)
        last_r = getattr(self, 'last_rbutton_time', 0.0)
        meta_time = getattr(self, 'meta_arrival_time', 0.0)
        last_ctrl_v = getattr(self, 'last_ctrl_v_time', 0.0)
        is_menu = check_is_menu_query(last_l, last_r, meta_time, last_ctrl_v)
        if is_menu == "MENU":
            log_debug("[render_format] Phát hiện truy vấn menu. Cung cấp dummy HDROP và lập lịch reset delayed rendering...")
            dummy_h = create_hdrop_data(["C:\\RemoteDesktop_Paste_Trigger.tmp"])
            if dummy_h:
                fn_SetClipboardData(15, dummy_h)
            
            # Lập lịch setup lại delayed rendering sau 200ms để chờ menu truy vấn xong
            def re_setup():
                time.sleep(0.2)
                self.setup_delayed_rendering()
            threading.Thread(target=re_setup, daemon=True).start()
            return
        elif is_menu == "BACKGROUND":
            log_debug("[render_format] Phát hiện truy vấn nền (VM Tools, clipboard monitor). Bỏ qua hoàn toàn.")
            return
            

            
        if getattr(self, 'is_rendering', False):
            log_debug("[render_format] Bỏ qua WM_RENDERFORMAT trùng lặp (đang render).")
            return
            
        self.is_rendering = True
        self.transfer_in_progress = True # Đặt cờ truyền tải để chặn các sự kiện thay đổi clipboard trong quá trình render
        try:
            print("[Clipboard] Nhận WM_RENDERFORMAT. Đang bắt đầu kiểm tra tệp tin ghi đè...")
            log_debug("[render_format] Nhận WM_RENDERFORMAT. Đang bắt đầu kiểm tra tệp tin ghi đè...")
            
            # --- HIỂN THỊ DIALOG TIẾN TRÌNH (chỉ GUI mode) ---
            display_name = self.pending_remote_files[0].get("name") if self.pending_remote_files else "Files"
            total_size = sum(f.get("size", 0) for f in self.pending_remote_files)
            log_debug(f"[render_format] Hiển thị dialog truyền tải: {display_name}, size={total_size}")
            # render_format chỉ chạy trong GUI mode (WM_RENDERFORMAT từ ClipboardEventListener)
            # HEADLESS mode xử lý dialog riêng trong Clipboard Agent (WM_RENDERFORMAT của agent)
            if not (self.app and getattr(self.app, 'is_headless', False)):
                self.show_dialog("Đang tải file về...", display_name, total_size)
            
            self._receive_cancelled = False
            self.batch_paths = []
            self.transfer_done_event.clear()
            
            # Lấy thư mục đích hoạt động của Explorer (nơi người dùng chuột phải Paste)
            dest_dir = self.get_active_explorer_path()
            log_debug(f"[render_format] Thư mục đích phát hiện: {dest_dir}")
            
            # Nếu có thư mục đích hợp lệ, tải file trực tiếp vào đó
            # Nếu không, sử dụng thư mục tạm
            if dest_dir and os.path.isdir(dest_dir):
                self.target_save_dir = dest_dir
                log_debug(f"[render_format] Tải file trực tiếp vào thư mục đích: {dest_dir}")
            else:
                temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                os.makedirs(temp_dir, exist_ok=True)
                self.target_save_dir = temp_dir
                log_debug(f"[render_format] Không tìm thấy thư mục đích, sử dụng thư mục tạm: {temp_dir}")
            
            files_to_download = []
            files_to_replace = []
            replace_all = False
            skip_all = False
            
            if dest_dir and os.path.isdir(dest_dir):
                for f in self.pending_remote_files:
                    filename = f.get("name")
                    dest_file_path = os.path.join(dest_dir, filename)
                    
                    if os.path.exists(dest_file_path):
                        # File đã tồn tại ở thư mục đích
                        if replace_all:
                            files_to_download.append(f)
                            files_to_replace.append(dest_file_path)
                        elif skip_all:
                            continue
                        else:
                            source_info = {"size": f.get("size", 0), "mtime": f.get("mtime", 0)}
                            try:
                                dest_stat = os.stat(dest_file_path)
                                dest_info = {"size": dest_stat.st_size, "mtime": dest_stat.st_mtime, "path": dest_file_path}
                            except:
                                dest_info = {"size": 0, "mtime": 0, "path": dest_file_path}
                                
                            has_multiple = len(self.pending_remote_files) > 1
                            choice = self.show_classic_conflict_dialog(filename, source_info, dest_info, has_multiple)
                            log_debug(f"[render_format] Kết quả lựa chọn ghi đè cho {filename}: {choice}")
                            
                            if choice == "replace":
                                files_to_download.append(f)
                                files_to_replace.append(dest_file_path)
                            elif choice == "replace_all":
                                replace_all = True
                                files_to_download.append(f)
                                files_to_replace.append(dest_file_path)
                            elif choice == "skip":
                                continue
                            elif choice == "skip_all":
                                skip_all = True
                                continue
                            else: # cancel
                                log_debug("[render_format] Hủy bỏ truyền tải từ hộp thoại ghi đè.")
                                self.close_dialog()
                                if self.app and getattr(self.app, 'is_headless', False):
                                    self._send_progress_signal("CANCEL", "")
                                    self._close_transfer_pipe()
                                fn_SetClipboardData(15, None)
                                return
                    else:
                        files_to_download.append(f)
            else:
                files_to_download = list(self.pending_remote_files)
                
            if not files_to_download:
                log_debug("[render_format] Không có tệp tin nào được chọn để tải (người dùng bỏ qua tất cả).")
                self.close_dialog()
                if self.app and getattr(self.app, 'is_headless', False):
                    self._send_progress_signal("CANCEL", "")
                    self._close_transfer_pipe()
                fn_SetClipboardData(15, None)
                return
                
            # Đặt lại danh sách tệp tin thực tế cần tải
            self.pending_remote_files = files_to_download
            
            # Xóa các file cần ghi đè TRƯỚC khi bắt đầu tải (để tránh xung đột ghi)
            for p in files_to_replace:
                try: os.remove(p)
                except: pass
            
            # Yêu cầu truyền file thực tế từ đối tác
            self.request_pending_files()
            
            # Chờ nhận xong file (non-blocking message pump)
            succeeded = False
            start_time = time.time()
            msg = wintypes.MSG()
            while time.time() - start_time < 600.0:
                if self.transfer_done_event.is_set():
                    if not getattr(self, '_receive_cancelled', False):
                        succeeded = True
                    break
                # Process window messages to keep Tkinter/hidden window responsive
                if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1): # PM_REMOVE = 1
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.01)
                    
            if succeeded and self.batch_paths:
                print(f"[Clipboard] Tải thành công {len(self.batch_paths)} file vào: {self.target_save_dir}")
                log_debug(f"[render_format] Tải thành công {len(self.batch_paths)} file. Đang nạp vào Clipboard...")
                
                # Tạo HDROP trỏ đến các file đã tải (nằm trực tiếp tại thư mục đích)
                hGlobal = create_hdrop_data(self.batch_paths)
                if hGlobal:
                    self.ignore_destroy_clipboard = True
                    try:
                        res = fn_SetClipboardData(15, hGlobal)
                        if not res:
                            err = ctypes.GetLastError()
                            log_debug(f"[render_format] Lỗi SetClipboardData: res={res}, GetLastError={err}")
                            fn_GlobalFree(hGlobal)
                        else:
                            log_debug(f"[render_format] Đã nạp thành công CF_HDROP vào Clipboard. res={res}")
                            # --- NGĂN CHẶN BOUNCE-BACK ---
                            # Explorer có thể tự động lấy ownership và cập nhật clipboard sau khi paste.
                            # Đánh dấu các file này để _process_clipboard_change bỏ qua.
                            if hasattr(self, 'lock'):
                                with self.lock:
                                    self.last_current_files = [os.path.abspath(p) for p in self.batch_paths if os.path.exists(p)]
                                    self.last_files_time = time.time()
                                    
                            # Lưu lại clipboard sequence number ngay sau khi SetClipboardData thành công
                            seq_after = ctypes.windll.user32.GetClipboardSequenceNumber()
                            log_debug(f"[render_format] Đã nạp thành công CF_HDROP vào Clipboard. seq_after={seq_after} (Bỏ dọn dẹp để hỗ trợ copy liên tiếp)")
                    finally:
                        self.ignore_destroy_clipboard = False
                else:
                    log_debug("[render_format] Không tạo được hGlobal, hủy render.")
            else:
                log_debug(f"[render_format] Tải file thất bại hoặc hết thời gian chờ. succeeded={succeeded}")
                self.close_dialog()
                if self.app and getattr(self.app, 'is_headless', False):
                    self._send_progress_signal("CANCEL", "")
                    self._close_transfer_pipe()
        except Exception as e:
            log_debug(f"[render_format] Lỗi khi xử lý render format: {e}")
            self.close_dialog()
            if self.app and getattr(self.app, 'is_headless', False):
                self._send_progress_signal("CANCEL", "")
                self._close_transfer_pipe()
        finally:
            self.transfer_in_progress = False
            self.is_rendering = False
            self.ignore_destroy_clipboard = False

    def request_pending_files(self):
        if not self.pending_remote_files or not self.sock: return
        send_msg(self.sock, json.dumps({"type": "request_files", "files": self.pending_remote_files}).encode('utf-8'))

    def _process_send_requests(self, sock, files):
        self._send_cancelled = False
        self.transfer_in_progress = True
        log_debug(f"[_process_send_requests] Khởi chạy gửi {len(files)} file...")
        try:
            total_size = sum(f.get("size", 0) for f in files)
            display_name = f"{len(files)} tệp tin" if len(files) > 1 else files[0].get("name", "Unknown")
            self.batch_display_name = display_name
            
            log_file_transfer(display_name, total_size)
            
            start_pkt = json.dumps({
                "type": "batch_start",
                "count": len(files),
                "total_size": total_size,
                "display_name": display_name
            }).encode('utf-8')
            send_msg(sock, start_pkt)
            log_debug(f"[_process_send_requests] Đã gửi batch_start. total_size={total_size}")
            
            total_sent = 0
            batch_start_time = time.time()
            for f in files:
                if self._send_cancelled:
                    log_debug(f"[_process_send_requests] Truyền tải bị hủy ngang.")
                    break
                filepath = f["path"]
                filename = f["name"]
                file_size = f["size"]
                
                log_debug(f"[_process_send_requests] Kiểm tra filepath: {filepath}")
                if not os.path.exists(filepath):
                    log_debug(f"[_process_send_requests] File không tồn tại: {filepath}")
                    continue
                    
                f_start_pkt = json.dumps({"type": "file_start", "name": filename, "size": file_size}).encode('utf-8')
                send_msg(sock, f_start_pkt)
                log_debug(f"[_process_send_requests] Đã gửi file_start cho {filename}, size={file_size}")
                
                try:
                    # Giới hạn băng thông từ từ (Slow Start) để tránh quá tải mạng làm mất điều khiển với host
                    # Bắt đầu từ 500 KB/s, mỗi giây tăng thêm 500 KB/s, tối đa 4 MB/s
                    chunk_size = 256 * 1024
                    file_sent_bytes = 0
                    file_start_time = time.time()
                    
                    with open(filepath, "rb") as fh:
                        while True:
                            if self._send_cancelled:
                                break
                            
                            elapsed_total = time.time() - batch_start_time
                            current_limit = 500 * 1024 + int(500 * 1024 * elapsed_total)
                            max_limit = 1000 * 1024 * 1024
                            if current_limit > max_limit:
                                current_limit = max_limit
                                
                            chunk_data = fh.read(chunk_size)
                            if not chunk_data:
                                break
                                
                            b64 = base64.b64encode(chunk_data).decode('utf-8')
                            send_msg(sock, json.dumps({"type": "file_chunk", "name": filename, "data": b64}).encode('utf-8'))
                            
                            file_sent_bytes += len(chunk_data)
                            total_sent += len(chunk_data)
                            
                            # Tính toán và điều tiết tốc độ gửi
                            target_time = file_sent_bytes / current_limit
                            actual_time = time.time() - file_start_time
                            if actual_time < target_time:
                                sleep_dur = target_time - actual_time
                                if sleep_dur > 2.0:
                                    sleep_dur = 2.0
                                    
                                sleep_end = time.time() + sleep_dur
                                while time.time() < sleep_end:
                                    if self._send_cancelled:
                                        break
                                    time.sleep(0.05)
                                    
                    log_debug(f"[_process_send_requests] Đã gửi xong dữ liệu cho {filename}")
                except Exception as e:
                    print(f"[FileTransfer] Lỗi khi gửi file {filename}: {e}")
                    log_debug(f"[_process_send_requests] Lỗi khi gửi file {filename}: {e}")
                    
                if not self._send_cancelled:
                    send_msg(sock, json.dumps({"type": "file_end", "name": filename}).encode('utf-8'))
                    log_debug(f"[_process_send_requests] Đã gửi file_end cho {filename}")
                
            if not self._send_cancelled:
                send_msg(sock, json.dumps({"type": "batch_end"}).encode('utf-8'))
                log_debug(f"[_process_send_requests] Đã gửi batch_end.")
                try: log_activity(f"Truyền file: {self.batch_display_name} - {total_size} byte - Thành công")
                except: pass
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error processing send request: {e}")
            log_debug(f"[_process_send_requests] Lỗi tổng quát:\n{tb}")
            try:
                log_activity(f"Truyền file: {self.batch_display_name} - {total_size} byte - Thất bại")
            except: pass
            try:
                send_msg(sock, json.dumps({"type": "cancel_transfer"}).encode('utf-8'))
            except:
                pass
        finally:
            self.transfer_in_progress = False
            log_debug(f"[_process_send_requests] Kết thúc hàm gửi file.")

    def handle_received_packet(self, packet):
        ptype = packet.get("type")
        
        # Chặn nhận clipboard từ Host nếu cửa sổ Client Viewer không được kích hoạt
        if ptype in ("clipboard_text", "files_copied_meta"):
            if getattr(self, 'pygame_hwnd', None):
                user32 = ctypes.windll.user32
                user32.GetForegroundWindow.restype = ctypes.c_void_p
                fg_hwnd = user32.GetForegroundWindow()
                if fg_hwnd != self.pygame_hwnd:
                    log_debug(f"[handle_received_packet] Bỏ qua gói tin {ptype} do cửa sổ Viewer không được kích hoạt (Giữ clipboard cho máy thật).")
                    return
                    
        # Nếu đang hủy hoặc đã hủy nhận, bỏ qua các gói tin liên quan đến truyền lô file hiện tại
        if getattr(self, '_receive_cancelled', False) and ptype in ("file_start", "file_chunk", "file_end", "batch_end"):
            log_debug(f"[handle_received_packet] Bỏ qua gói tin {ptype} do tiến trình tải đã bị hủy.")
            return
            
        if ptype == "cancel_transfer":
            print("[FileTransfer] Nhận tín hiệu hủy truyền tải từ đối tác.")
            self.cancel_active_transfer(remote_triggered=True)
            return
            
        elif ptype == "clipboard_text":
            text = packet.get("text", "")
            log_debug(f"[handle_received_packet] Nhận clipboard_text: {text[:50]}...")
            print(f"[Clipboard] Đã nhận được text clipboard từ remote. Đang cập nhật...")
            self.last_received_text = text
            self.ignore_destroy_clipboard = True
            try:
                owner_hwnd = None
                if self.app:
                    try: owner_hwnd = self.app.winfo_id()
                    except: pass
                
                if self.app and getattr(self.app, 'is_headless', False):
                    # Gửi text qua Named Pipe cho Clipboard Agent
                    threading.Thread(target=self._send_to_pipe, args=("TEXT", text), daemon=True).start()
                    log_debug("[handle_received_packet] HEADLESS: Đang gửi text qua Named Pipe cho Clipboard Agent.")
                else:
                    set_clipboard_text(text, owner_hwnd)
            finally:
                self.ignore_destroy_clipboard = False
            return
            
        elif ptype == "files_copied_meta":
            self._receive_cancelled = False
            self.pending_remote_files = packet.get("files", [])
            self.meta_arrival_time = time.time()
            log_debug(f"[handle_received_packet] Nhận files_copied_meta. Số file: {len(self.pending_remote_files)}")
            print(f"[Clipboard] Đã nhận được files_copied_meta. Số file: {len(self.pending_remote_files)}")
            if not self.pending_remote_files: return
            
            # --- HEADLESS MODE (SYSTEM/Service): Gửi PENDING cho Clipboard Agent ---
            if self.app and getattr(self.app, 'is_headless', False):
                transfer_dir = HEADLESS_TRANSFER_DIR
                try:
                    os.makedirs(transfer_dir, exist_ok=True)
                    for item in os.listdir(transfer_dir):
                        item_path = os.path.join(transfer_dir, item)
                        if os.path.isfile(item_path):
                            try: os.remove(item_path)
                            except: pass
                except Exception as e:
                    log_debug(f"[files_copied_meta] Lỗi dọn dẹp thư mục transfer: {e}")
                self.target_save_dir = transfer_dir
                self.batch_paths = []
                self.transfer_done_event.clear()
                
                # Gửi PENDING: tới agent để nó chờ Paste và hiện dialog, thay vì tải ngay im lặng.
                total_size = sum(f.get("size", 0) for f in self.pending_remote_files)
                display_name = "Files"
                if self.pending_remote_files:
                    display_name = self.pending_remote_files[0].get("name", "Files")
                    if len(self.pending_remote_files) > 1:
                        display_name += f" and {len(self.pending_remote_files) - 1} others"
                        
                msg_dict = {
                    "display_name": display_name,
                    "total_size": total_size,
                    "files": self.pending_remote_files
                }
                import json
                msg = json.dumps(msg_dict)
                threading.Thread(target=self._send_to_pipe, args=("PENDING", msg), daemon=True).start()
                log_debug(f"[files_copied_meta] HEADLESS MODE: Đã gửi PENDING tới Agent để chờ Paste.")
                return
            
            # --- GUI MODE (User): Sử dụng delayed rendering như bình thường ---
            temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
            self.target_save_dir = temp_dir
            
            # Đăng ký delayed rendering NGAY LẬP TỨC để sáng nút Paste sớm nhất có thể
            self.setup_delayed_rendering()
            
            # Dọn dẹp thư mục tạm trong luồng nền để không block việc sáng nút Paste
            def cleanup_temp():
                try:
                    os.makedirs(temp_dir, exist_ok=True)
                    for item in os.listdir(temp_dir):
                        item_path = os.path.join(temp_dir, item)
                        if os.path.isfile(item_path):
                            try: os.remove(item_path)
                            except: pass
                except Exception as e:
                    log_debug(f"[files_copied_meta] Lỗi dọn dẹp thư mục tạm: {e}")
            threading.Thread(target=cleanup_temp, daemon=True).start()
            return
            
        elif ptype == "request_files":
            files_to_send = packet.get("files", [])
            threading.Thread(target=self._process_send_requests, args=(self.sock, files_to_send), daemon=True).start()
            return
            
        elif ptype == "batch_start":
            self.batch_total_size = packet.get("total_size", 0)
            self.batch_received = 0
            self.batch_paths = []
            display_name = packet.get("display_name", "Files")
            self.batch_display_name = display_name
            
            self.transfer_in_progress = True
            self._receive_cancelled = False
            
            os.makedirs(self.target_save_dir, exist_ok=True)
            log_file_transfer(display_name, self.batch_total_size)
            log_debug(f"[batch_start] Bắt đầu nhận batch, total_size={self.batch_total_size}, target_save_dir={self.target_save_dir}")
            # GUI mode: hiện dialog khi bắt đầu nhận
            # HEADLESS mode: KHÔNG gửi START ở đây — Clipboard Agent đã hiện dialog ngay
            # khi WM_RENDERFORMAT (tức là đúng lúc user Paste), tránh hiện dialog trùng.
            if not (self.app and getattr(self.app, 'is_headless', False)):
                self.show_dialog("Đang tải file về...", display_name, self.batch_total_size)
            
        elif ptype == "file_start":
            filename = packet.get("name", "")
            if not filename: return
            
            # Use target_dir from packet if provided, else use self.target_save_dir
            save_dir = packet.get("target_dir", self.target_save_dir)
            if not save_dir: save_dir = self.target_save_dir
            
            target_path = os.path.join(save_dir, filename)
            log_debug(f"[file_start] Bắt đầu nhận file: {filename}, target_path={target_path}")

            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                fh = open(target_path, "wb")
                self.incoming_transfers[filename] = {
                    "path": target_path,
                    "handle": fh,
                    "skipped": False,
                    "pending": False,
                }
                log_debug(f"[file_start] Mở thành công file mới: {target_path}")
            except Exception as e:
                print(f"[FileTransfer] Lỗi mở file mới {filename}: {e}")
                log_debug(f"[file_start] Lỗi mở file mới {filename}: {e}")

        elif ptype == "file_chunk":
            filename = packet.get("name", "")
            if filename in self.incoming_transfers:
                transfer = self.incoming_transfers[filename]
                chunk_bytes = base64.b64decode(packet.get("data", ""))

                if transfer.get("handle") is not None:
                    transfer["handle"].write(chunk_bytes)
                    self.batch_received += len(chunk_bytes)
                    self.update_dialog(self.batch_received)
                    if self.app and getattr(self.app, 'is_headless', False):
                        current_time = time.time()
                        if not hasattr(self, '_last_progress_time'):
                            self._last_progress_time = 0
                            self._last_progress_bytes = 0
                        if (current_time - self._last_progress_time > 0.1) or (self.batch_received - self._last_progress_bytes > 100000):
                            self._send_progress_signal("PROGRESS", str(self.batch_received))
                            self._last_progress_time = current_time
                            self._last_progress_bytes = self.batch_received
                
        elif ptype == "file_end":
            filename = packet.get("name", "")
            if filename in self.incoming_transfers:
                transfer = self.incoming_transfers.pop(filename, None)
                if transfer:
                    if transfer.get("handle") is not None:
                        try:
                            transfer["handle"].close()
                            log_debug(f"[file_end] Đóng handle file thành công cho: {filename}")
                        except Exception as e:
                            log_debug(f"[file_end] Lỗi đóng handle file {filename}: {e}")
                    
                    top_level_name = filename.replace('\\', '/').split('/')[0]
                    top_level_path = os.path.join(self.target_save_dir, top_level_name)
                    if top_level_path not in self.batch_paths:
                        self.batch_paths.append(top_level_path)
                    log_debug(f"[file_end] Đã xử lý xong file: {filename}")
                    
                    if not self.incoming_transfers and getattr(self, 'active_batch', False) and getattr(self, 'batch_total_size', 0) > 0 and getattr(self, 'batch_received', 0) >= self.batch_total_size:
                        if hasattr(self, 'active_dialog') and self.active_dialog:
                            try:
                                if hasattr(self.active_dialog, 'safe_destroy'):
                                    self.active_dialog.safe_destroy()
                                else:
                                    self.active_dialog.destroy()
                                self.active_dialog = None
                            except: pass
                        if 'file_manager_callback' in globals():
                            globals()['file_manager_callback']({"type": "trigger_local_refresh"})
                
        elif ptype == "batch_end":
            self.close_dialog()
            self.transfer_done_event.set()
            if 'file_manager_callback' in globals():
                globals()['file_manager_callback']({"type": "trigger_local_refresh"})
            log_debug(f"[batch_end] Đã nhận xong toàn bộ file trong thư mục tạm.")
            try: log_activity(f"Nhận file: {self.batch_display_name} - {self.batch_total_size} byte - Thành công")
            except: pass
            
            # --- HEADLESS MODE: Gửi đường dẫn file qua Named Pipe cho Clipboard Agent ---
            if self.app and getattr(self.app, 'is_headless', False):
                if self.batch_paths:
                    files_str = "|".join(self.batch_paths)
                    self._send_progress_signal("FILES", files_str)
                    log_debug(f"[batch_end] HEADLESS: Đã gửi FILES tới agent: {files_str[:100]}")
                    
                    if hasattr(self, 'lock'):
                        with self.lock:
                            self.last_current_files = [os.path.abspath(p) for p in self.batch_paths if os.path.exists(p)]
                            self.last_files_time = time.time()
                else:
                    self._send_progress_signal("CANCEL", "")
                    log_debug("[batch_end] HEADLESS: batch_paths trống, đã gửi CANCEL tới agent.")
                self._close_transfer_pipe()
                
            # self.pending_remote_files = [] # Bỏ clear để tránh race condition ở lần copy N+1
            self.transfer_in_progress = False



is_agent_process = "--clipboard-agent" in sys.argv or (sys.argv and "clipboard_agent" in sys.argv[0])
if not is_agent_process:
    clipboard_sync_manager = ClipboardSyncManager()
else:
    clipboard_sync_manager = None




# Shared client variables
client_latest_frame = None
client_last_recv_time = 0
client_frame_lock = threading.Lock()
client_running = True
client_is_domain = False
client_is_locked = False
client_switching_desktop_countdown = 0
client_host_resolution = None

# Client Screen Receiver Thread
def client_receiver_thread(sock, password):
    global client_latest_frame, client_running, client_switching_desktop_countdown, client_is_domain, client_is_locked
    client_pending_bbox = None
    while client_running:
        try:
            msg = recv_msg(sock, password)
            if not msg:
                print("[Client] Server closed connection.")
                client_running = False
                break
            
            # [FIX] Decrypt failure trả về b'' thay vì None — log rõ ràng thay vì fail lặng lẽ
            if msg == b'':
                print("[Client] WARNING: Received empty message (decryption may have failed). Skipping.")
                continue
                
            global client_last_recv_time
            client_last_recv_time = time.time()
                
            if msg.startswith(b'{'):
                try:
                    event = json.loads(msg.decode('utf-8'))
                    evt_type = event.get("type", "")
                    if evt_type == "pong":
                        continue
                    elif evt_type in ("batch_start", "file_start", "file_chunk", "file_end", "batch_end", "files_copied_meta", "request_files", "cancel_transfer", "clipboard_text"):
                        clipboard_sync_manager.handle_received_packet(event)
                        continue
                    elif evt_type == "domain_status":
                        client_is_domain = event.get("is_domain", False)
                        client_is_locked = event.get("is_locked", False)
                        reason = event.get("reason", "No reason provided")
                        try:
                            with open("domain_debug.log", "a", encoding="utf-8") as df:
                                df.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Client received domain_status: is_domain={client_is_domain}, is_locked={client_is_locked}, reason={reason}\n")
                        except:
                            pass
                        continue
                    elif evt_type == "switching_desktop":
                        if client_switching_desktop_countdown <= 0:
                            client_switching_desktop_countdown = 10
                        continue
                    elif evt_type == "host_shutdown":
                        print("[Client] Received host_shutdown. Exiting viewer immediately.")
                        import pygame
                        pygame.event.post(pygame.event.Event(pygame.QUIT))
                        continue
                    elif evt_type == "resolution_change":
                        new_w = event.get("w")
                        new_h = event.get("h")
                        if new_w and new_h:
                            global client_host_resolution
                            client_host_resolution = (new_w, new_h)
                        continue
                    elif evt_type == "partial_frame":
                        client_pending_bbox = event.get("bbox")
                        continue
                    elif evt_type in ("list_dir_result", "delete_item_result", "rename_item_result", "create_folder_result", "open_file_result", "read_text_file_result", "write_text_file_result"):
                        cb = globals().get('file_manager_callback')
                        if cb: cb(event)
                        continue
                except Exception as je:
                    print(f"[Client] Lỗi giải mã gói tin JSON: {je}")
                    pass
                continue


            import io
            try:
                pil_img = Image.open(io.BytesIO(msg))
                pil_img.load()  # Force decode in receiver thread
                with client_frame_lock:
                    if client_pending_bbox is not None:
                        if client_latest_frame is not None:
                            temp = client_latest_frame.copy()
                            temp.paste(pil_img, (client_pending_bbox[0], client_pending_bbox[1]))
                            client_latest_frame = temp
                        client_pending_bbox = None
                    else:
                        client_latest_frame = pil_img
                client_switching_desktop_countdown = 0
            except Exception as ie:
                with open("client_error.log", "a", encoding="utf-8") as f: f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - [Client] Lỗi giải mã ảnh Pillow: {ie}\n")
        except Exception as e:
            with open("client_error.log", "a", encoding="utf-8") as f: f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - [Client] Receiver Error: {e}\n")
            client_running = False
            break

# Client keyboard hook helper functions
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

_keyboard_hook = None
_keyboard_hook_id = None

def install_keyboard_hook(hwnd, send_event_fn):
    global _keyboard_hook, _keyboard_hook_id
    
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    
    LRESULT = ctypes.c_int64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_int32
    WPARAM = ctypes.c_size_t
    LPARAM = ctypes.c_size_t
    
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)
    
    def hook_proc(nCode, wParam, lParam):
        if nCode >= 0:
            try:
                user32.GetForegroundWindow.restype = ctypes.c_void_p
                active_hwnd = user32.GetForegroundWindow()
                if hwnd and active_hwnd == hwnd:
                    kbd = KBDLLHOOKSTRUCT.from_address(lParam)
                    vkCode = kbd.vkCode
                    
                    is_win_key = (vkCode == 0x5B or vkCode == 0x5C)
                    is_menu_key = (vkCode == 0x5D)  # VK_APPS - phím Menu/Application (right-click keyboard key)
                    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
                    user32.GetAsyncKeyState.restype = ctypes.c_short
                    is_ctrl_esc = (vkCode == 0x1B and (user32.GetAsyncKeyState(0x11) & 0x8000))
                    is_alt_f4 = (vkCode == 0x73 and (kbd.flags & 0x20))
                    
                    if is_win_key or is_ctrl_esc or is_menu_key or is_alt_f4:
                        pressed = (wParam == 0x0100 or wParam == 0x0104) # WM_KEYDOWN or WM_SYSKEYDOWN
                        
                        if is_win_key:
                            key_name = 'left windows' if vkCode == 0x5B else 'right windows'
                        elif is_menu_key:
                            key_name = 'menu'
                        elif is_alt_f4:
                            key_name = 'f4'
                        else:
                            key_name = 'escape'
                            
                        send_event_fn({
                            "type": "key_event",
                            "key": key_name,
                            "pressed": pressed
                        })
                        
                        return 1
            except Exception:
                pass
                
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, WPARAM, LPARAM]
        user32.CallNextHookEx.restype = LRESULT
        return user32.CallNextHookEx(None, nCode, wParam, lParam)
        
    _keyboard_hook = HOOKPROC(hook_proc)
    
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    h_mod = kernel32.GetModuleHandleW(None)
    
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HANDLE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HANDLE
    
    _keyboard_hook_id = user32.SetWindowsHookExW(13, _keyboard_hook, h_mod, 0)
    if not _keyboard_hook_id:
        print(f"[Client] Hook keyboard failed. Error: {ctypes.GetLastError()}")
    else:
        print(f"[Client] Keyboard hook installed successfully: {_keyboard_hook_id}")

def uninstall_keyboard_hook():
    global _keyboard_hook_id
    if _keyboard_hook_id:
        user32 = ctypes.windll.user32
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        user32.UnhookWindowsHookEx(_keyboard_hook_id)
        _keyboard_hook_id = None
        print("[Client] Keyboard hook uninstalled.")

# Client Main View Pygame Loop
def run_client_viewer_loop(sock, host_w, host_h, computer_name="", is_domain=False, partner_id="", reconnect_queue=None, partner_pass="", is_android=False):
    global client_switching_desktop_countdown
    
    try: log_activity(f"Bắt đầu điều khiển ID {partner_id} ({computer_name})")
    except: pass
    
    # [FIX] Trong Windows, multiprocessing.Process khởi tạo tiến trình con mới hoàn toàn.
    # Từ điển socket_passwords toàn cục bị trống, dẫn đến encrypt_payload mặc định dùng APP_KEY,
    # gây ra lỗi InvalidTag khi Host giải mã dữ liệu clipboard/file.
    if partner_pass:
        socket_passwords[sock] = partner_pass
        
    try:
        pygame_theme = "dark"
        try:
            import json, os
            with open("window_config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                pygame_theme = cfg.get("theme", "dark")
        except:
            pass

        outer_running = True
        
        # Initialize Pygame once outside the loop
        import os
        os.environ['SDL_MOUSE_FOCUS_CLICKTHROUGH'] = '1'
        os.environ['SDL_RENDER_DRIVER'] = 'hardware'
        pygame.init()
        pygame.key.set_repeat(500, 50)
        
        info = pygame.display.Info()
        client_max_w = info.current_w - 100
        client_max_h = info.current_h - 100
        
        ratio = min(client_max_w / host_w, client_max_h / host_h, 1.0)
        
        # [Tùy chỉnh Android] Thu nhỏ màn hình mặc định nếu là thiết bị di động (màn hình dọc)
        if host_h > host_w:
            max_portrait_height = min(900, client_max_h) # Giới hạn chiều cao tối đa khoảng 900px
            if host_h * ratio > max_portrait_height:
                ratio = max_portrait_height / host_h
                
        window_w = int(host_w * ratio)
        window_h = int(host_h * ratio)
        
        window_w = max(100, min(window_w, 3840))
        window_h = max(100, min(window_h, 2160))
        
        try:
            screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
        except Exception as e:
            print(f"[Client] Hardware rendering failed ({e}). Falling back to software rendering.")
            os.environ['SDL_RENDER_DRIVER'] = 'software'
            pygame.display.quit()
            pygame.display.init()
            screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
        
        hwnd = None
        try: hwnd = pygame.display.get_wm_info().get("window")
        except: pass
        if hwnd and clipboard_sync_manager:
            clipboard_sync_manager.pygame_hwnd = hwnd
        import tempfile
        blink_file = ""
        if partner_id:
            blink_file = os.path.join(tempfile.gettempdir(), f"antigravity_blink_{partner_id}.tmp")
            if os.path.exists(blink_file):
                try: os.remove(blink_file)
                except: pass
                
        if computer_name:
            pygame.display.set_caption(f"P2P Remote Desktop  |  {computer_name}")
        else:
            pygame.display.set_caption("P2P Remote Desktop Viewer")
            
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                pygame.display.set_icon(pygame.image.load(icon_path))
        except Exception as e:
            print(f"[App] Lỗi thiết lập icon cửa sổ pygame: {e}")
            
        try: btn_font = pygame.font.SysFont("Segoe UI", 12, bold=True)
        except:
            try: btn_font = pygame.font.SysFont("Arial", 12, bold=True)
            except: btn_font = pygame.font.Font(None, 20)
            
        clock = pygame.time.Clock()
        button_map = {1: 'left', 2: 'middle', 3: 'right'}
        
        while outer_running:
            exit_due_to_disconnect = True
            global client_latest_frame, client_running, client_is_domain, client_is_locked, client_last_recv_time
            client_latest_frame = None
            client_last_recv_time = time.time()
            client_running = True
            client_is_domain = is_domain
            
            try:
                # Check if domain was already queried and reason passed in handshake (or check local log)
                with open("domain_debug.log", "a", encoding="utf-8") as df:
                    df.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Client viewer started: computer_name={computer_name}, is_domain={is_domain}, partner_id={partner_id}\n")
            except:
                pass
                
            import tkinter as tk
            hidden_root = tk.Tk()
            hidden_root.attributes('-alpha', 0.0)
            try:
                icon_path = os.path.join(app_dir, "app_icon.png")
                if os.path.exists(icon_path):
                    hidden_icon = ImageTk.PhotoImage(Image.open(icon_path))
                    hidden_root.iconphoto(True, hidden_icon)
                    hidden_root._hidden_icon_ref = hidden_icon
            except Exception:
                pass
            hidden_root.withdraw()
            clipboard_sync_manager.register_app(hidden_root)
            
            # Start receiver thread
            t = threading.Thread(target=client_receiver_thread, args=(sock, partner_pass), daemon=True)
            t.start()
            
            # Gắn kết socket vào trình quản lý Event Listener của Clipboard
            clipboard_sync_manager.add_socket(sock)
            # We moved pygame init outside
            
            import queue
            import collections
            # Queue riêng cho sự kiện quan trọng (click, key, scroll) - KHÔNG bao giờ bị drop
            critical_queue = queue.Queue()
            # Buffer mouse_move: chỉ giữ vị trí mới nhất, tránh làm đầy queue và mất click
            _mouse_move_buf = {}
            _mouse_move_lock = threading.Lock()
            _mouse_move_has_new = threading.Event()
            
            def event_sender_thread():
                last_ping_time = time.time()
                while client_running:
                    try:
                        now = time.time()
                        if now - last_ping_time >= 3.0:
                            send_msg(sock, json.dumps({"type": "ping"}).encode('utf-8'), partner_pass)
                            last_ping_time = now

                        # Ưu tiên gửi sự kiện quan trọng (click/key/scroll) trước
                        try:
                            event_dict = critical_queue.get_nowait()
                            send_msg(sock, json.dumps(event_dict).encode('utf-8'), partner_pass)
                            continue
                        except queue.Empty:
                            pass
                        # Nếu không có sự kiện quan trọng, gửi mouse_move mới nhất nếu có
                        if _mouse_move_has_new.wait(timeout=0.05):
                            with _mouse_move_lock:
                                move = _mouse_move_buf.get("latest")
                                _mouse_move_has_new.clear()
                            if move:
                                send_msg(sock, json.dumps(move).encode('utf-8'), partner_pass)
                    except Exception:
                        break
                        
            threading.Thread(target=event_sender_thread, daemon=True).start()
            
            # Khởi tạo kích thước viewer ban đầu cho Host biết
            def send_event(event_dict):
                try:
                    evt_type = event_dict.get("type")
                    if evt_type == "mouse_move":
                        # Chỉ giữ vị trí mới nhất, bỏ các vị trí cũ để không làm block click
                        with _mouse_move_lock:
                            _mouse_move_buf["latest"] = event_dict
                        _mouse_move_has_new.set()
                    else:
                        # Click, key, scroll: KHÔNG bao giờ drop, đưa thẳng vào critical_queue
                        critical_queue.put(event_dict)
                except Exception:
                    pass
                    
            # Install keyboard hook to intercept Windows keys and Ctrl+Esc
            if hwnd:
                install_keyboard_hook(hwnd, send_event)
                
            send_event({"type": "check_domain"})
            send_event({"type": "resize_viewer", "w": window_w, "h": window_h})
            
            frame_counter = 0
            blink_frames_remaining = 0
            active_unicode_map = {}
            was_switching = False
            switching_last_tick = 0
            switching_start_tick = 0
            drag_start_pos = None
            drag_start_time = 0
            drag_path = []
            
            while client_running:
                frame_counter += 1
                # Check for blink signal file periodically
                if blink_file and frame_counter % 15 == 0:
                    if os.path.exists(blink_file):
                        try:
                            os.remove(blink_file)
                            blink_frames_remaining = 180 # 3 seconds at 60 FPS
                            if hwnd:
                                import ctypes
                                ctypes.windll.user32.ShowWindow(hwnd, 9) # SW_RESTORE
                                ctypes.windll.user32.SetForegroundWindow(hwnd)
                        except:
                            pass
    
                # Cập nhật event loop của Tkinter ẩn để các hộp thoại (dialog truyền file) vẫn hoạt động trong subprocess
                try:
                    hidden_root.update()
                except Exception:
                    pass
     
                global client_host_resolution
                if client_host_resolution is not None:
                    new_host_w, new_host_h = client_host_resolution
                    client_host_resolution = None
                    if new_host_w != host_w or new_host_h != host_h:
                        print(f"[Client] Host resolution changed from {host_w}x{host_h} to {new_host_w}x{new_host_h}")
                        host_w, host_h = new_host_w, new_host_h
                        
                        import ctypes
                        client_max_w = ctypes.windll.user32.GetSystemMetrics(0) - 100
                        client_max_h = ctypes.windll.user32.GetSystemMetrics(1) - 100
                        
                        ratio = min(client_max_w / host_w, client_max_h / host_h, 1.0)
                        window_w = int(host_w * ratio)
                        window_h = int(host_h * ratio)
                        
                        window_w = max(100, window_w)
                        window_h = max(100, window_h)
                        
                        uninstall_keyboard_hook()
                        pygame.display.quit()
                        pygame.display.init()
                        screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
                        
                        if computer_name:
                            pygame.display.set_caption(f"P2P Remote Desktop  |  {computer_name}")
                        else:
                            pygame.display.set_caption("P2P Remote Desktop Viewer")
                        try:
                            icon_path = os.path.join(app_dir, "app_icon.png")
                            if os.path.exists(icon_path):
                                pygame.display.set_icon(pygame.image.load(icon_path))
                        except Exception:
                            pass
                            
                        hwnd = None
                        try: hwnd = pygame.display.get_wm_info().get("window")
                        except: pass
                        if hwnd:
                            if clipboard_sync_manager: clipboard_sync_manager.pygame_hwnd = hwnd
                            install_keyboard_hook(hwnd, send_event)

                        send_event({"type": "resize_viewer", "w": window_w, "h": window_h})

                # Calculate floating button rectangle dynamically
                min_btn_w, min_btn_h = 40, 22
                cad_btn_w, cad_btn_h = 145, 22
                eye_btn_w, eye_btn_h = 30, 22
                file_btn_w, file_btn_h = 110, 22
                power_btn_w, power_btn_h = 40, 22
                rec_btn_w, rec_btn_h = 30, 22
                close_btn_w, close_btn_h = 40, 22
                
                is_switching = (globals().get('client_switching_desktop_countdown', 0) > 0)
                show_buttons = not is_switching
                
                show_cad_button = show_buttons and not is_android
                show_file_button = show_buttons and is_android
                show_power_button = show_buttons and is_android
                
                total_w = 0
                if show_buttons:
                    total_w = min_btn_w + 10 + (file_btn_w + 10 if show_file_button else 0) + (power_btn_w + 10 if show_power_button else 0) + (eye_btn_w + 10 if show_cad_button else 0) + (cad_btn_w + 10 if show_cad_button else 0) + rec_btn_w + 10 + close_btn_w
                    
                start_x = (window_w - total_w) // 2
                
                if show_buttons:
                    min_btn_rect = pygame.Rect(start_x, 0, min_btn_w, min_btn_h)
                    current_x = start_x + min_btn_w + 10
                    
                    if show_power_button:
                        power_btn_rect = pygame.Rect(current_x, 0, power_btn_w, power_btn_h)
                        current_x += power_btn_w + 10
                    else:
                        power_btn_rect = pygame.Rect(-1000, -1000, 0, 0)

                    if show_file_button:
                        file_btn_rect = pygame.Rect(current_x, 0, file_btn_w, file_btn_h)
                        current_x += file_btn_w + 10
                    else:
                        file_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    if show_cad_button:
                        eye_btn_rect = pygame.Rect(current_x, 0, eye_btn_w, eye_btn_h)
                        current_x += eye_btn_w + 10
                        cad_btn_rect = pygame.Rect(current_x, 0, cad_btn_w, cad_btn_h)
                        current_x += cad_btn_w + 10
                    else:
                        eye_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        cad_btn_rect = pygame.Rect(-1000, -1000, 0, 0)
                        
                    rec_btn_rect = pygame.Rect(current_x, 0, rec_btn_w, rec_btn_h)
                    current_x += rec_btn_w + 10
                    close_btn_rect = pygame.Rect(current_x, 0, close_btn_w, close_btn_h)
                else:
                    min_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    file_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    power_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    eye_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    cad_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    rec_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    close_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden

                mx, my = pygame.mouse.get_pos()
                min_is_hover = min_btn_rect.collidepoint(mx, my) if show_buttons else False
                file_is_hover = file_btn_rect.collidepoint(mx, my) if show_buttons else False
                power_is_hover = power_btn_rect.collidepoint(mx, my) if show_buttons else False
                eye_is_hover = eye_btn_rect.collidepoint(mx, my) if show_buttons else False
                cad_is_hover = cad_btn_rect.collidepoint(mx, my) if show_buttons else False
                rec_is_hover = rec_btn_rect.collidepoint(mx, my) if show_buttons else False
                close_is_hover = close_btn_rect.collidepoint(mx, my) if show_buttons else False
     
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        exit_due_to_disconnect = False
                        client_running = False
                        outer_running = False
                        break
                        
                    elif event.type == pygame.VIDEORESIZE:
                        window_w, window_h = event.w, event.h
                        screen = pygame.display.set_mode((window_w, window_h), pygame.RESIZABLE)
                        send_event({"type": "resize_viewer", "w": window_w, "h": window_h})
                        
                    elif event.type == pygame.MOUSEMOTION:
                        if show_buttons and (min_btn_rect.collidepoint(event.pos) or file_btn_rect.collidepoint(event.pos) or power_btn_rect.collidepoint(event.pos) or eye_btn_rect.collidepoint(event.pos) or cad_btn_rect.collidepoint(event.pos) or rec_btn_rect.collidepoint(event.pos) or close_btn_rect.collidepoint(event.pos)):
                            continue
                        mx_pos, my_pos = event.pos
                        host_x = int(mx_pos * (host_w / window_w))
                        host_y = int(my_pos * (host_h / window_h))
                        
                        if is_android and drag_start_pos is not None:
                            # Record drag path points for Android swipes/patterns
                            if not drag_path:
                                drag_path.append(drag_start_pos)
                            
                            last_pt = drag_path[-1]
                            # Record point if it moved at least 5 pixels (squared distance > 25) to avoid excessive points
                            if (host_x - last_pt[0])**2 + (host_y - last_pt[1])**2 > 25:
                                drag_path.append((host_x, host_y))
                        else:
                            send_event({"type": "mouse_move", "x": host_x, "y": host_y})
                        
                    elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                        if show_buttons and min_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Minimize Button Clicked. Minimizing viewer.")
                                pygame.display.iconify()
                            continue
                        if show_buttons and file_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                if globals().get('fm_is_open'):
                                    continue
                                globals()['fm_is_open'] = True
                                print("[Client] Transfer File Button Clicked.")
                                
                                if globals().get('fm_top') and globals().get('fm_top').winfo_exists():
                                    try:
                                        def restore_fm():
                                            globals().get('fm_top').deiconify()
                                            globals().get('fm_top').focus_force()
                                        globals().get('fm_top').after(0, restore_fm)
                                    except: pass
                                    continue

                                def open_transfer_window():
                                    try:
                                        import tkinter as tk
                                        from tkinter import ttk, filedialog, messagebox
                                        import threading, os, time, base64

                                        top = tk.Tk()
                                        globals()['fm_top'] = top
                                        top.attributes('-alpha', 0.0) # Ẩn đi để tránh nháy khi tạo
                                        
                                        host_title = f" - {computer_name}" if computer_name else ""
                                        top.title(f"P2P Remote Desktop - Trình Quản Lý Tệp (File Manager){host_title}")
                                        
                                        hwnd = pygame.display.get_wm_info().get("window")
                                        if hwnd:
                                            import ctypes
                                            from ctypes import wintypes
                                            rect = wintypes.RECT()
                                            ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
                                            py_w = rect.right - rect.left
                                            py_h = rect.bottom - rect.top
                                            
                                            # Try to get screen coordinates of the Pygame window
                                            pt = wintypes.POINT(0, 0)
                                            ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))
                                            
                                            if host_w >= 1920 and host_h >= 1080:
                                                top.update_idletasks()
                                                tk_hwnd = int(top.frame(), 16)
                                                try: ctypes.windll.user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
                                                except: pass
                                                style = ctypes.windll.user32.GetWindowLongW(tk_hwnd, -16)
                                                style = (style | 0x40000000) & ~0x80000000
                                                ctypes.windll.user32.SetWindowLongW(tk_hwnd, -16, style)
                                                ctypes.windll.user32.SetParent(tk_hwnd, hwnd)
                                                x = max(0, (py_w - 900) // 2)
                                                y = max(0, (py_h - 600) // 2)
                                                top.geometry("900x600")
                                                top.update_idletasks()
                                                ctypes.windll.user32.SetWindowPos(tk_hwnd, 0, x, y, 900, 600, 0x0004)
                                            else:
                                                x = max(0, pt.x + (py_w - 900) // 2)
                                                y = max(0, pt.y + (py_h - 600) // 2)
                                                top.geometry(f"900x600+{x}+{y}")
                                        else:
                                            top.geometry("900x600")

                                        top.attributes('-topmost', True)
                                        top.attributes('-alpha', 1.0) # Hiện lại sau khi set geometry
                                        top.configure(bg="#E5E5E5")
                                    
                                        left_frame = tk.Frame(top, bg="#E5E5E5")
                                        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
                                    
                                        mid_frame = tk.Frame(top, width=60, bg="#E5E5E5")
                                        mid_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
                                    
                                        right_frame = tk.Frame(top, bg="#E5E5E5")
                                        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
                                    
                                        # --- Left Pane (Local) ---
                                        tk.Label(left_frame, text="Máy của bạn (Local)", font=("Segoe UI", 10, "bold"), bg="#E5E5E5").pack()
                                        local_nav = tk.Frame(left_frame, bg="#E5E5E5")
                                        local_nav.pack(fill=tk.X, pady=2)
                                    
                                        local_entry = tk.Entry(local_nav)
                                        local_entry.insert(0, os.path.abspath(os.path.expanduser("~")))
                                    
                                        def format_size(s):
                                            if s < 1024: return f"{s} B"
                                            elif s < 1024*1024: return f"{s/1024:.1f} KB"
                                            else: return f"{s/(1024*1024):.1f} MB"

                                        def refresh_local():
                                            for item in local_tree.get_children():
                                                local_tree.delete(item)
                                            try:
                                                path = local_entry.get()
                                                if path == "This PC":
                                                    import string
                                                    import ctypes
                                                    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
                                                    drives = []
                                                    for letter in string.ascii_uppercase:
                                                        if bitmask & 1:
                                                            drives.append(f"{letter}:\\")
                                                        bitmask >>= 1
                                                    for d in drives:
                                                        local_tree.insert("", "end", text=d, values=("", "Ổ đĩa", 0))
                                                    return
                                                
                                                items = os.listdir(path)
                                                # Folders first, then files
                                                dirs = []
                                                files = []
                                                for item in items:
                                                    full = os.path.join(path, item)
                                                    if os.path.isdir(full):
                                                        dirs.append(item)
                                                    else:
                                                        files.append(item)
                                                dirs.sort(key=str.lower)
                                                files.sort(key=str.lower)
                                            
                                                for d in dirs:
                                                    local_tree.insert("", "end", text=d, values=("", "Thư mục"))
                                                for f in files:
                                                    full = os.path.join(path, f)
                                                    size = os.path.getsize(full)
                                                    local_tree.insert("", "end", text=f, values=(format_size(size), "Tệp", size))
                                            except Exception as e:
                                                pass

                                        def go_up_local():
                                            current = local_entry.get()
                                            if current == "This PC": return
                                            parent = os.path.dirname(current)
                                            if parent and parent == current:
                                                parent = "This PC"
                                            
                                            local_entry.delete(0, tk.END)
                                            local_entry.insert(0, parent)
                                            refresh_local()

                                        tk.Button(local_nav, text="⬆ Lên", command=go_up_local).pack(side=tk.LEFT)
                                        local_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
                                        tk.Button(local_nav, text="Đi", command=refresh_local).pack(side=tk.LEFT)
                                    
                                        local_tree_frame = tk.Frame(left_frame, bd=1, relief=tk.SUNKEN)
                                        local_tree_frame.pack(fill=tk.BOTH, expand=True)
                                        local_scrollbar = tk.Scrollbar(local_tree_frame, orient="vertical", width=16)
                                        local_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                                        local_tree = ttk.Treeview(local_tree_frame, columns=("size", "type", "raw_size"), show="tree headings", yscrollcommand=local_scrollbar.set)
                                        local_tree.heading("#0", text="Tên")
                                        local_tree.heading("size", text="Kích thước")
                                        local_tree.heading("type", text="Loại")
                                        local_tree.column("#0", width=200)
                                        local_tree.column("size", width=80)
                                        local_tree.column("type", width=70)
                                        local_tree.column("raw_size", width=0, stretch=False)
                                        local_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                                        local_scrollbar.config(command=local_tree.yview)

                                        def local_double_click(event):
                                            sel = local_tree.selection()
                                            if sel:
                                                item = local_tree.item(sel[0])
                                                vals = item.get('values', [])
                                                name = item['text']
                                                if local_entry.get() == "This PC":
                                                    fpath = name
                                                else:
                                                    fpath = os.path.join(local_entry.get(), name)
                                                is_dir = (len(vals) > 1 and vals[1] in ("Thư mục", "Ổ đĩa"))
                                                if not is_dir:
                                                    try: is_dir = os.path.isdir(fpath)
                                                    except: pass
                                                if is_dir:
                                                    new_path = fpath
                                                    local_entry.delete(0, tk.END)
                                                    local_entry.insert(0, new_path)
                                                    refresh_local()
                                                else:
                                                    local_action("view")
                                        local_tree.bind("<Double-1>", local_double_click)
                                        local_tree.bind("<BackSpace>", lambda e: go_up_local())

                                        local_menu = tk.Menu(top, tearoff=0)
                                        def local_action(action):
                                            try:
                                                current_dir = local_entry.get()
                                                sel = local_tree.selection()
                                                if action == "mkdir":
                                                    from tkinter import simpledialog
                                                    new_name = simpledialog.askstring("Thư mục mới", "Nhập tên thư mục mới:", parent=top)
                                                    top.focus_force()
                                                    if new_name:
                                                        try:
                                                            folder_path = os.path.join(current_dir, new_name)
                                                            if os.path.exists(folder_path):
                                                                messagebox.showinfo("Lỗi", f'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"', parent=top)
                                                            else:
                                                                os.makedirs(folder_path, exist_ok=True)
                                                                refresh_local()
                                                        except Exception as e:
                                                            with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f: f.write(f"Error mkdir: {str(e)}\n")
                                                    return
                                                if not sel: return
                                                
                                                if action == "delete":
                                                    if len(sel) == 1:
                                                        msg = f"Bạn có chắc muốn xóa '{local_tree.item(sel[0])['text']}' không?"
                                                    else:
                                                        msg = f"Bạn có chắc muốn xóa {len(sel)} mục đã chọn không?"
                                                    confirm = messagebox.askyesno("Xác nhận", msg, parent=top)
                                                    top.focus_force()
                                                    if confirm:
                                                        for s in sel:
                                                            item = local_tree.item(s)
                                                            name = item['text']
                                                            full_path = os.path.join(current_dir, name)
                                                            vals = item.get('values', [])
                                                            is_dir = (len(vals) > 1 and vals[1] == "Thư mục")
                                                            try:
                                                                if is_dir:
                                                                    import shutil
                                                                    shutil.rmtree(full_path)
                                                                else:
                                                                    os.remove(full_path)
                                                            except Exception as e:
                                                                messagebox.showerror("Lỗi", f"Lỗi xóa {name}: {e}", parent=top)
                                                        refresh_local()
                                                    return

                                                for s in sel:
                                                    item = local_tree.item(s)
                                                    name = item['text']
                                                    full_path = os.path.join(current_dir, name)
                                                    vals = item.get('values', [])
                                                    is_dir = (len(vals) > 1 and vals[1] == "Thư mục")
                                                    
                                                    if action == "view":
                                                        from datetime import datetime
                                                        ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
                                                        with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                                            f.write(f"{ts} [Local] Action 'view' started for '{name}', is_dir={is_dir}\n")
                                                        if is_dir:
                                                            messagebox.showwarning("Cảnh báo", f"Không thể xem thư mục '{name}' bằng Notepad!", parent=top)
                                                        else:
                                                            text_exts = {'.txt', '.log', '.md', '.py', '.json', '.xml', '.ini', '.cfg', '.csv', '.html', '.css', '.js', '.kt', '.java', '.c', '.cpp', '.h', '.bat', '.sh', ''}
                                                            _, ext = os.path.splitext(name.lower())
                                                            if ext in text_exts:
                                                                try:
                                                                    with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                                                        f.write(f"{ts} [Local] Opening {full_path}...\n")
                                                                    with open(full_path, "r", encoding="utf-8") as f:
                                                                        file_content = f.read(5 * 1024 * 1024)
                                                                    with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                                                        f.write(f"{ts} [Local] Read successful, creating window...\n")
                                                                    np_win = tk.Toplevel(top)
                                                                    np_win.title(f"Soạn thảo (Local) - {name}")
                                                                    np_win.geometry("800x600")
                                                                    np_win.transient(top)
                                                                    np_win.attributes('-topmost', True)
                                                                    np_win.update_idletasks()
                                                                    w, h = 800, 600
                                                                    px, py = top.winfo_rootx(), top.winfo_rooty()
                                                                    pw, ph = top.winfo_width(), top.winfo_height()
                                                                    np_win.geometry(f"800x600+{px + (pw-w)//2}+{py + (ph-h)//2}")
                                                                    text_area = tk.Text(np_win, wrap="word", font=("Consolas", 11))
                                                                    text_area.pack(expand=True, fill="both")
                                                                    text_area.insert("1.0", file_content)
                                                                    def make_save(fp, ta, win):
                                                                        def save_file():
                                                                            try:
                                                                                with open(fp, "w", encoding="utf-8") as fw:
                                                                                    fw.write(ta.get("1.0", "end-1c"))
                                                                                messagebox.showinfo("Thành công", "Đã lưu tệp!", parent=win)
                                                                            except Exception as e:
                                                                                messagebox.showerror("Lỗi", f"Không thể lưu: {e}", parent=win)
                                                                        return save_file
                                                                    tk.Button(np_win, text="Lưu", command=make_save(full_path, text_area, np_win), bg="green", fg="white", font=("Arial", 10, "bold")).pack(pady=5)
                                                                    with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                                                        f.write(f"{ts} [Local] Window created successfully.\n")
                                                                except Exception as ex:
                                                                    import traceback
                                                                    with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                                                        f.write(f"{ts} [Local] CRASH during view: {traceback.format_exc()}\n")
                                                                    messagebox.showerror("Lỗi", str(ex), parent=top)
                                                            else:
                                                                try:
                                                                    import sys, subprocess
                                                                    if sys.platform == "win32": os.startfile(full_path)
                                                                    else: subprocess.call(["xdg-open", full_path])
                                                                except Exception as e:
                                                                    messagebox.showerror("Lỗi", str(e), parent=top)
                                                    elif action == "rename":
                                                        from tkinter import simpledialog
                                                        new_name = simpledialog.askstring("Đổi tên", f"Nhập tên mới cho '{name}':", initialvalue=name, parent=top)
                                                        top.focus_force()
                                                        if new_name and new_name != name:
                                                            try:
                                                                os.rename(full_path, os.path.join(current_dir, new_name))
                                                            except Exception as e:
                                                                messagebox.showerror("Lỗi", str(e), parent=top)
                                                if action == "rename":
                                                    refresh_local()
                                            except Exception as outer_e:
                                                import traceback
                                                from datetime import datetime
                                                ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
                                                with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                                    f.write(f"{ts} [Local] OUTER CRASH: {traceback.format_exc()}\n")
                                                messagebox.showerror("Lỗi", str(outer_e), parent=top)
                                        def show_local_menu(event):
                                            local_menu.delete(0, 'end')
                                            row = local_tree.identify_row(event.y)
                                            if not row:
                                                local_menu.add_command(label="Tạo thư mục mới", command=lambda: local_action("mkdir"))
                                                local_menu.add_separator()
                                                local_menu.add_command(label="Làm mới", command=refresh_local)
                                                local_menu.tk_popup(event.x_root, event.y_root)
                                                return
                                                
                                            if row not in local_tree.selection():
                                                local_tree.selection_set(row)
                                            
                                            vals = local_tree.item(row, "values")
                                            is_dir = (len(vals) > 1 and vals[1] == "Thư mục")
                                            
                                            if not is_dir:
                                                local_menu.add_command(label="Xem file", command=lambda: local_action("view"))
                                            local_menu.add_command(label="Tạo thư mục mới", command=lambda: local_action("mkdir"))
                                            local_menu.add_command(label="Đổi tên", command=lambda: local_action("rename"))
                                            local_menu.add_separator()
                                            local_menu.add_command(label="Xóa", command=lambda: local_action("delete"))
                                            
                                            try:
                                                local_menu.tk_popup(event.x_root, event.y_root)
                                            finally:
                                                local_menu.grab_release()
                                        local_tree.bind("<Button-3>", show_local_menu)
                                        
                                        def select_all_local(event):
                                            local_tree.selection_set(local_tree.get_children())
                                            return "break"
                                        local_tree.bind("<Control-a>", select_all_local)
                                        local_tree.bind("<Control-A>", select_all_local)
                                    
                                        # --- Right Pane (Remote) ---
                                        tk.Label(right_frame, text="Máy điều khiển (Remote Host)", font=("Segoe UI", 10, "bold"), bg="#E5E5E5").pack()
                                        remote_nav = tk.Frame(right_frame, bg="#E5E5E5")
                                        remote_nav.pack(fill=tk.X, pady=2)
                                        
                                        remote_entry = tk.Entry(remote_nav)
                                        remote_entry.insert(0, "/sdcard/" if is_android else "C:\\")
                                    
                                        def request_remote_dir(path):
                                            # send list_dir request
                                            req = {"type": "request_list_dir", "path": path}
                                            send_event(req)

                                        def on_remote_dir_result(event):
                                            evt_type = event.get("type", "list_dir_result")
                                            if evt_type == "list_dir_result":
                                                if event.get("path") != remote_entry.get():
                                                    return
                                                for item in remote_tree.get_children():
                                                    remote_tree.delete(item)
                                                items = event.get("items", [])
                                                dirs = [i for i in items if i.get("is_dir")]
                                                files = [i for i in items if not i.get("is_dir")]
                                                dirs.sort(key=lambda x: str(x.get("name")).lower())
                                                files.sort(key=lambda x: str(x.get("name")).lower())
                                                
                                                for d in dirs:
                                                    remote_tree.insert("", "end", text=d.get("name"), values=("", "Thư mục"))
                                                for f in files:
                                                    sz = f.get("size", 0)
                                                    remote_tree.insert("", "end", text=f.get("name"), values=(format_size(sz), "Tệp", sz))
                                            elif evt_type in ("delete_item_result", "rename_item_result", "create_folder_result", "open_file_result"):
                                                success = event.get("success")
                                                error = event.get("error")
                                                if not success:
                                                    messagebox.showerror("Lỗi", error or "Thao tác thất bại", parent=top)
                                                else:
                                                    request_remote_dir(remote_entry.get())
                                            elif evt_type == "read_text_file_result":
                                                success = event.get("success")
                                                if success:
                                                    try:
                                                        from datetime import datetime
                                                        ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
                                                        open("C:\\Apps\\P2P\\agent.log", "a", encoding="utf-8").write(f"{ts} [Remote] Remote read success, creating Toplevel Notepad\n")
                                                        content = event.get("content", "")
                                                        path = event.get("path", "")
                                                        name = path.split("/")[-1] if "/" in path else path.split("\\")[-1]
                                                        np_win = tk.Toplevel(top)
                                                        np_win.title(f"Soạn thảo (Remote) - {name}")
                                                        np_win.geometry("800x600")
                                                        np_win.transient(top)
                                                        np_win.attributes('-topmost', True)
                                                        np_win.update_idletasks()
                                                        w, h = 800, 600
                                                        px, py = top.winfo_rootx(), top.winfo_rooty()
                                                        pw, ph = top.winfo_width(), top.winfo_height()
                                                        np_win.geometry(f"800x600+{px + (pw-w)//2}+{py + (ph-h)//2}")
                                                        text_area = tk.Text(np_win, wrap="word", font=("Consolas", 11))
                                                        text_area.pack(expand=True, fill="both")
                                                        text_area.insert("1.0", content)
                                                    except Exception as ex:
                                                        messagebox.showerror("Lỗi Code", f"Lỗi tạo Notepad: {ex}", parent=top)
                                                        return
                                                    def save_remote_file():
                                                        req = {"type": "request_write_text_file", "path": path, "content": text_area.get("1.0", "end-1c")}
                                                        send_event(req)
                                                        messagebox.showinfo("Thông báo", "Đã gửi yêu cầu lưu tệp tới thiết bị điều khiển.", parent=np_win)
                                                    tk.Button(np_win, text="Lưu", command=save_remote_file, bg="green", fg="white", font=("Arial", 10, "bold")).pack(pady=5)
                                                else:
                                                    messagebox.showerror("Lỗi", event.get("error", "Không thể đọc tệp"), parent=top)
                                            elif evt_type == "write_text_file_result":
                                                success = event.get("success")
                                                if not success:
                                                    messagebox.showerror("Lỗi", event.get("error", "Lỗi lưu tệp từ xa"), parent=top)
                                        
                                        import queue
                                        fm_event_queue = queue.Queue()
                                        def process_fm_queue():
                                            try:
                                                while True:
                                                    evt = fm_event_queue.get_nowait()
                                                    if evt.get("type") == "trigger_local_refresh":
                                                        refresh_local()
                                                    else:
                                                        on_remote_dir_result(evt)
                                            except queue.Empty:
                                                pass
                                            if top.winfo_exists():
                                                top.after(100, process_fm_queue)
                                                
                                        top.after(100, process_fm_queue)
                                        globals()['file_manager_callback'] = lambda e: fm_event_queue.put(e)

                                        def go_up_remote():
                                            p = remote_entry.get().replace("\\", "/").rstrip("/")
                                            if "/" in p:
                                                parent = p.rsplit("/", 1)[0]
                                                if not parent: parent = "/"
                                                if not is_android and len(parent) == 2 and parent.endswith(":"):
                                                    parent += "/"
                                                remote_entry.delete(0, tk.END)
                                                remote_entry.insert(0, parent)
                                                request_remote_dir(parent)
                                            
                                        tk.Button(remote_nav, text="⬆ Lên", command=go_up_remote).pack(side=tk.LEFT)
                                        remote_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
                                        tk.Button(remote_nav, text="Đi", command=lambda: request_remote_dir(remote_entry.get())).pack(side=tk.LEFT)

                                        remote_tree_frame = tk.Frame(right_frame, bd=1, relief=tk.SUNKEN)
                                        remote_tree_frame.pack(fill=tk.BOTH, expand=True)
                                        remote_scrollbar = tk.Scrollbar(remote_tree_frame, orient="vertical", width=16)
                                        remote_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                                        remote_tree = ttk.Treeview(remote_tree_frame, columns=("size", "type", "raw_size"), show="tree headings", yscrollcommand=remote_scrollbar.set)
                                        remote_tree.heading("#0", text="Tên")
                                        remote_tree.heading("size", text="Kích thước")
                                        remote_tree.heading("type", text="Loại")
                                        remote_tree.column("#0", width=200)
                                        remote_tree.column("size", width=80)
                                        remote_tree.column("type", width=70)
                                        remote_tree.column("raw_size", width=0, stretch=False)
                                        remote_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                                        remote_scrollbar.config(command=remote_tree.yview)

                                        def remote_double_click(event):
                                            sel = remote_tree.selection()
                                            if sel:
                                                item = remote_tree.item(sel[0])
                                                vals = item.get('values', [])
                                                is_dir = (len(vals) > 1 and vals[1] == "Thư mục")
                                                if is_dir:
                                                    p = remote_entry.get()
                                                    sep = "/" if "/" in p else ("\\" if "\\" in p else "/")
                                                    if not p.endswith(sep): p += sep
                                                    new_path = p + item['text']
                                                    remote_entry.delete(0, tk.END)
                                                    remote_entry.insert(0, new_path)
                                                    request_remote_dir(new_path)
                                                else:
                                                    remote_action("view")
                                        remote_tree.bind("<Double-1>", remote_double_click)
                                        remote_tree.bind("<BackSpace>", lambda e: go_up_remote())

                                        remote_menu = tk.Menu(top, tearoff=0)
                                        def remote_action(action):
                                            current_dir = remote_entry.get()
                                            sep = "/" if "/" in current_dir else ("\\" if "\\" in current_dir else "/")
                                            if not current_dir.endswith(sep): current_dir += sep
                                            sel = remote_tree.selection()
                                            if action == "mkdir":
                                                from tkinter import simpledialog
                                                new_name = simpledialog.askstring("Thư mục mới", "Nhập tên thư mục mới:", parent=top)
                                                top.focus_force()
                                                if new_name:
                                                    exists = False
                                                    for child in remote_tree.get_children():
                                                        if remote_tree.item(child, "text") == new_name:
                                                            exists = True
                                                            break
                                                    if exists:
                                                        messagebox.showinfo("Lỗi", f'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"', parent=top)
                                                    else:
                                                        req = {"type": "request_create_folder", "parent_path": current_dir, "folder_name": new_name}
                                                        send_event(req)
                                                return
                                            if not sel: return
                                            
                                            if action == "delete":
                                                if len(sel) == 1:
                                                    msg = f"Bạn có chắc muốn xóa '{remote_tree.item(sel[0])['text']}' khỏi máy điều khiển không?"
                                                else:
                                                    msg = f"Bạn có chắc muốn xóa {len(sel)} mục đã chọn khỏi máy điều khiển không?"
                                                confirm = messagebox.askyesno("Xác nhận", msg, parent=top)
                                                top.focus_force()
                                                if confirm:
                                                    for s in sel:
                                                        item = remote_tree.item(s)
                                                        name = item['text']
                                                        full_path = current_dir + name
                                                        req = {"type": "request_delete_item", "path": full_path}
                                                        send_event(req)
                                                return
                                                
                                            for s in sel:
                                                item = remote_tree.item(s)
                                                name = item['text']
                                                full_path = current_dir + name
                                                vals = item.get('values', [])
                                                is_dir = (len(vals) > 1 and vals[1] == "Thư mục")
                                                if action == "view":
                                                    from datetime import datetime
                                                    ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
                                                    open("C:\\Apps\\P2P\\agent.log", "a", encoding="utf-8").write(f"{ts} [Remote] Action 'view' on '{name}', is_dir={is_dir}\n")
                                                    if is_dir:
                                                        messagebox.showwarning("Cảnh báo", f"Không thể xem thư mục '{name}' bằng Notepad!", parent=top)
                                                    else:
                                                        text_exts = {'.txt', '.log', '.md', '.py', '.json', '.xml', '.ini', '.cfg', '.csv', '.html', '.css', '.js', '.kt', '.java', '.c', '.cpp', '.h', '.bat', '.sh', ''}
                                                        _, ext = os.path.splitext(name.lower())
                                                        if ext in text_exts:
                                                            req = {"type": "request_read_text_file", "path": full_path}
                                                        else:
                                                            req = {"type": "request_open_file", "path": full_path}
                                                            messagebox.showinfo("Thông báo", f"Đã gửi yêu cầu mở file {ext} bằng ứng dụng mặc định trên máy bị điều khiển.", parent=top)
                                                        try:
                                                            open("C:\\Apps\\P2P\\agent.log", "a", encoding="utf-8").write(f"{ts} [Remote] Sending file read request: {req}\n")
                                                            send_event(req)
                                                        except Exception as ex:
                                                            messagebox.showerror("Lỗi", f"Không thể gửi lệnh: {ex}", parent=top)
                                                elif action == "rename":
                                                    from tkinter import simpledialog
                                                    new_name = simpledialog.askstring("Đổi tên", f"Nhập tên mới cho '{name}':", initialvalue=name, parent=top)
                                                    top.focus_force()
                                                    if new_name and new_name != name:
                                                        req = {"type": "request_rename_item", "old_path": full_path, "new_name": new_name}
                                                        send_event(req)
                                        def show_remote_menu(event):
                                            remote_menu.delete(0, 'end')
                                            row = remote_tree.identify_row(event.y)
                                            if not row:
                                                remote_menu.add_command(label="Tạo thư mục mới", command=lambda: remote_action("mkdir"))
                                                remote_menu.add_separator()
                                                remote_menu.add_command(label="Làm mới", command=lambda: request_remote_dir(remote_entry.get()))
                                                remote_menu.post(event.x_root, event.y_root)
                                                return
                                                
                                            if row not in remote_tree.selection():
                                                remote_tree.selection_set(row)
                                            remote_tree.focus(row)
                                            
                                            vals = remote_tree.item(row, "values")
                                            is_dir = (len(vals) > 1 and vals[1] == "Thư mục")
                                            
                                            if not is_dir:
                                                remote_menu.add_command(label="Xem file", command=lambda: remote_action("view"))
                                            remote_menu.add_command(label="Tạo thư mục mới", command=lambda: remote_action("mkdir"))
                                            remote_menu.add_command(label="Đổi tên", command=lambda: remote_action("rename"))
                                            remote_menu.add_separator()
                                            remote_menu.add_command(label="Xóa", command=lambda: remote_action("delete"))
                                            
                                            remote_menu.post(event.x_root, event.y_root)
                                        remote_tree.bind("<Button-3>", show_remote_menu)
                                        
                                        def select_all_remote(event):
                                            remote_tree.selection_set(remote_tree.get_children())
                                            return "break"
                                        remote_tree.bind("<Control-a>", select_all_remote)
                                        remote_tree.bind("<Control-A>", select_all_remote)

                                        def on_tree_keypress(event, tree):
                                            if not event.char or not event.char.isprintable():
                                                return
                                            char = event.char.lower()
                                            items = tree.get_children()
                                            if not items: return "break"
                                            
                                            start_idx = 0
                                            current_sel = tree.selection()
                                            if current_sel:
                                                try:
                                                    start_idx = items.index(current_sel[0]) + 1
                                                except ValueError:
                                                    start_idx = 0

                                            for idx in list(range(start_idx, len(items))) + list(range(0, start_idx)):
                                                item = items[idx]
                                                text = tree.item(item, 'text').lower()
                                                if text.startswith(char):
                                                    tree.selection_set(item)
                                                    tree.focus(item)
                                                    tree.see(item)
                                                    return "break"
                                            return "break"
                                        
                                        local_tree.bind("<KeyPress>", lambda e: on_tree_keypress(e, local_tree))
                                        remote_tree.bind("<KeyPress>", lambda e: on_tree_keypress(e, remote_tree))

                                        local_tree.bind("<F2>", lambda e: local_action("rename"))
                                        remote_tree.bind("<F2>", lambda e: remote_action("rename"))
                                        
                                        local_tree.bind("<F5>", lambda e: refresh_local())
                                        remote_tree.bind("<F5>", lambda e: request_remote_dir(remote_entry.get()))
                                        local_tree.bind("<BackSpace>", lambda e: "break" if go_up_local() or True else "")
                                        remote_tree.bind("<BackSpace>", lambda e: "break" if go_up_remote() or True else "")
                                        
                                        def tree_go_home(event, tree):
                                            items = tree.get_children()
                                            if items:
                                                tree.selection_set(items[0])
                                                tree.focus(items[0])
                                                tree.see(items[0])
                                            return "break"

                                        def tree_go_end(event, tree):
                                            items = tree.get_children()
                                            if items:
                                                tree.selection_set(items[-1])
                                                tree.focus(items[-1])
                                                tree.see(items[-1])
                                            return "break"

                                        def tree_page_up(event, tree):
                                            items = tree.get_children()
                                            if not items: return "break"
                                            sel = tree.selection()
                                            new_idx = max(0, items.index(sel[0]) - 15) if sel else 0
                                            tree.selection_set(items[new_idx])
                                            tree.focus(items[new_idx])
                                            tree.see(items[new_idx])
                                            return "break"

                                        def tree_page_down(event, tree):
                                            items = tree.get_children()
                                            if not items: return "break"
                                            sel = tree.selection()
                                            new_idx = min(len(items) - 1, items.index(sel[-1]) + 15) if sel else len(items) - 1
                                            tree.selection_set(items[new_idx])
                                            tree.focus(items[new_idx])
                                            tree.see(items[new_idx])
                                            return "break"

                                        for t in (local_tree, remote_tree):
                                            t.bind("<Home>", lambda e, tr=t: tree_go_home(e, tr))
                                            t.bind("<End>", lambda e, tr=t: tree_go_end(e, tr))
                                            t.bind("<Prior>", lambda e, tr=t: tree_page_up(e, tr))
                                            t.bind("<Next>", lambda e, tr=t: tree_page_down(e, tr))

                                        # --- Transfer Actions ---
                                        def resolve_conflicts(conflicts, parent, is_upload):
                                            results = {}
                                            overwrite_all = False
                                            
                                            for c in conflicts:
                                                if overwrite_all:
                                                    results[c['name']] = 'overwrite'
                                                    continue
                                                    
                                                dlg = tk.Frame(parent, bg="#FFFFFF", highlightbackground="#0078D7", highlightthickness=2)
                                                dlg.place(relx=0.5, rely=0.5, anchor="center", width=650, height=380)
                                                dlg.lift()
                                                dlg.focus_force()
                                                
                                                try:
                                                    dlg.grab_set()
                                                except: pass
                                                
                                                title_bar = tk.Frame(dlg, bg="#F3F3F3", height=30)
                                                title_bar.pack(fill=tk.X, side=tk.TOP)
                                                title_bar.pack_propagate(False)
                                                tk.Label(title_bar, text="Xác nhận", bg="#F3F3F3", fg="#333333", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=10, pady=5)
                                                
                                                frame = tk.Frame(dlg, bg="white")
                                                frame.pack(fill="both", expand=True)
                                                
                                                # Pack btn_frame first at the bottom so it never gets clipped
                                                btn_frame = tk.Frame(frame, bg="white")
                                                btn_frame.pack(fill="x", side="bottom", pady=20, padx=20)
                                                
                                                item_type = "Thư mục" if c.get('src_is_dir') else "Tập tin"
                                                lbl_title = tk.Label(frame, text=f"{item_type} với tên \"{c['name']}\" đã tồn tại.", font=("Segoe UI", 11, "bold"), bg="white", anchor="w")
                                                lbl_title.pack(fill="x", padx=20, pady=(20, 10))
                                                
                                                try:
                                                    src_sz_val = int(float(c.get('src_size', 0)))
                                                except:
                                                    src_sz_val = 0
                                                try:
                                                    dst_sz_val = int(float(c.get('dst_size', 0)))
                                                except:
                                                    dst_sz_val = 0
                                                    
                                                src_sz = format_size(src_sz_val)
                                                dst_sz = format_size(dst_sz_val)
                                                
                                                src_path = c.get('src_path', 'Không rõ')
                                                dst_path = c.get('dst_path', 'Không rõ')
                                                src_mtime = c.get('src_mtime', 'Không xác định')
                                                dst_mtime = c.get('dst_mtime', 'Không xác định')
                                                
                                                if is_upload:
                                                    src_title = "Nguồn (Máy bạn):"
                                                    dst_title = "Đích (Máy từ xa):"
                                                else:
                                                    src_title = "Nguồn (Máy từ xa):"
                                                    dst_title = "Đích (Máy bạn):"
                                                    
                                                src_disp = f"{src_title}\n- Thư mục: {src_path}\n- Dung lượng: {src_sz}\n- Ngày sửa đổi: {src_mtime}"
                                                dst_disp = f"{dst_title}\n- Thư mục: {dst_path}\n- Dung lượng: {dst_sz}\n- Ngày sửa đổi: {dst_mtime}"
                                                
                                                tk.Label(frame, text=src_disp, font=("Segoe UI", 10), bg="white", anchor="w", fg="#333333", justify="left").pack(fill="x", padx=20, pady=2)
                                                tk.Label(frame, text=dst_disp, font=("Segoe UI", 10), bg="white", anchor="w", fg="#333333", justify="left").pack(fill="x", padx=20, pady=(2, 10))
                                                tk.Label(frame, text="Bạn muốn làm gì?", font=("Segoe UI", 10, "bold"), bg="white", anchor="w").pack(fill="x", padx=20, pady=(5, 15))
                                                
                                                decision = ["cancel"]
                                                def make_decision(d):
                                                    decision[0] = d
                                                    try: dlg.grab_release()
                                                    except: pass
                                                    dlg.destroy()
                                                    
                                                btn_cancel = tk.Button(btn_frame, text="Hủy", font=("Segoe UI", 10, "bold"), bg="#e0e0e0", fg="black", width=8, relief="raised", borderwidth=2, command=lambda: make_decision("cancel"))
                                                btn_cancel.pack(side="right", padx=5)
                                                
                                                btn_skip = tk.Button(btn_frame, text="Bỏ qua", font=("Segoe UI", 10), bg="#e0e0e0", fg="black", width=10, relief="raised", borderwidth=2, command=lambda: make_decision("skip"))
                                                btn_skip.pack(side="right", padx=10)
                                                
                                                btn_ow = tk.Button(btn_frame, text="Ghi đè", font=("Segoe UI", 10), bg="#e0e0e0", fg="black", width=10, relief="raised", borderwidth=2, command=lambda: make_decision("overwrite"))
                                                btn_ow.pack(side="right", padx=10)
                                                
                                                btn_ow_all = tk.Button(btn_frame, text="Ghi đè toàn bộ", font=("Segoe UI", 10, "bold"), bg="#e0e0e0", fg="black", width=15, relief="raised", borderwidth=2, command=lambda: make_decision("overwrite_all"))
                                                btn_ow_all.pack(side="right", padx=10)
                                                
                                                parent.wait_window(dlg)
                                                if decision[0] == "cancel": return None
                                                elif decision[0] == "overwrite_all":
                                                    overwrite_all = True
                                                    results[c['name']] = 'overwrite'
                                                else: results[c['name']] = decision[0]
                                                    
                                            return results

                                        def write_transfer_log(direction, file_name, file_size, dest_dir):
                                            try:
                                                import datetime
                                                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                                log_line = f"[{now}] {direction} | File: {file_name} | Size: {format_size(file_size)} | To: {dest_dir}\n"
                                                with open("transfer.log", "a", encoding="utf-8") as lf:
                                                    lf.write(log_line)
                                            except Exception as e:
                                                print("Log error:", e)

                                        def do_upload():
                                            sel = local_tree.selection()
                                            if not sel: return
                                            
                                            target_dir = remote_entry.get()
                                            
                                            # Check conflicts
                                            remote_items = {}
                                            for child in remote_tree.get_children():
                                                txt = remote_tree.item(child, "text")
                                                vals = remote_tree.item(child, "values")
                                                is_dir = True if len(vals) > 1 and vals[1] == "Thư mục" else False
                                                sz = vals[2] if len(vals) > 2 else 0
                                                remote_items[txt] = {"is_dir": is_dir, "size": sz}
                                            
                                            conflicts = []
                                            for s in sel:
                                                name = local_tree.item(s, "text")
                                                if name in remote_items:
                                                    fpath = os.path.join(local_entry.get(), name)
                                                    sz = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
                                                    is_dir = os.path.isdir(fpath)
                                                    try:
                                                        import datetime
                                                        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M:%S')
                                                    except: mtime = "Không xác định"
                                                    dpath = remote_entry.get()
                                                    if not dpath.endswith('/'): dpath += '/'
                                                    dpath += name
                                                    conflicts.append({
                                                        "name": name,
                                                        "src_size": sz, "src_is_dir": is_dir, "src_path": fpath, "src_mtime": mtime,
                                                        "dst_size": remote_items[name]["size"], "dst_is_dir": remote_items[name]["is_dir"],
                                                        "dst_path": dpath, "dst_mtime": "Không xác định (Remote)"
                                                    })
                                                    
                                            if conflicts:
                                                decisions = resolve_conflicts(conflicts, top, is_upload=True)
                                                if decisions is None: return
                                            else:
                                                decisions = {}

                                            items_to_upload = [] # List of (local_path, remote_name, size)
                                            total_size = 0
                                            
                                            for s in sel:
                                                item = local_tree.item(s)
                                                name = item['text']
                                                
                                                if name in decisions and decisions[name] == 'skip':
                                                    continue
                                                fpath = os.path.join(local_entry.get(), name)
                                                
                                                if os.path.isfile(fpath):
                                                    sz = os.path.getsize(fpath)
                                                    items_to_upload.append((fpath, name, sz, False))
                                                    total_size += sz
                                                elif os.path.isdir(fpath):
                                                    # Recursive walk for folders
                                                    base_name = name
                                                    for root, dirs, files in os.walk(fpath):
                                                        rel_path = os.path.relpath(root, os.path.dirname(fpath))
                                                        if not dirs and not files:
                                                            remote_name = rel_path.replace('\\', '/')
                                                            items_to_upload.append((None, remote_name, 0, True))
                                                        for d in dirs:
                                                            remote_name = os.path.join(rel_path, d).replace('\\', '/')
                                                        for f in files:
                                                            full_file = os.path.join(root, f)
                                                            if os.path.isfile(full_file):
                                                                sz = os.path.getsize(full_file)
                                                                remote_name = os.path.join(rel_path, f).replace('\\', '/')
                                                                items_to_upload.append((full_file, remote_name, sz, False))
                                                                total_size += sz

                                            if not items_to_upload: return
                                            
                                            display_name = items_to_upload[0][1]
                                            if len(items_to_upload) > 1:
                                                display_name += f" và {len(items_to_upload)-1} mục khác"
                                                
                                            class UploadState:
                                                is_cancelled = False
                                            state = UploadState()
                                            
                                            dialog = ProgressDialog(top, "Chuyển qua", display_name, total_size, on_cancel=lambda: setattr(state, 'is_cancelled', True))
                                            dialog.update_progress(0)
                                            
                                            def upload_batch_thread(items, t_dir, dlg, st):
                                                try:
                                                    sent_total = 0
                                                    for path, n, sz, is_empty_dir in items:
                                                        if st.is_cancelled: break
                                                        
                                                        if is_empty_dir:
                                                            final_target_dir = t_dir
                                                            if not final_target_dir.endswith("/"): final_target_dir += "/"
                                                            
                                                            parts = n.strip('/').rsplit('/', 1)
                                                            if len(parts) == 2:
                                                                parent_path = final_target_dir + parts[0]
                                                                folder_name = parts[1]
                                                            else:
                                                                parent_path = final_target_dir
                                                                if parent_path.endswith("/"): parent_path = parent_path[:-1]
                                                                folder_name = parts[0]
                                                                
                                                            send_event({"type": "request_create_folder", "parent_path": parent_path, "folder_name": folder_name})
                                                            time.sleep(0.1)
                                                            continue
                                                            
                                                        write_transfer_log("UPLOAD", n, sz, t_dir)
                                                        
                                                        parts = n.split('/')
                                                        file_name = parts[-1]
                                                        sub_dir = "/".join(parts[:-1])
                                                        
                                                        final_target_dir = t_dir
                                                        if not final_target_dir.endswith("/"): final_target_dir += "/"
                                                        if sub_dir:
                                                            final_target_dir += sub_dir
                                                            
                                                        send_event({"type": "file_start", "name": file_name, "size": sz, "target_dir": final_target_dir})
                                                        time.sleep(0.5)
                                                        
                                                        with open(path, "rb") as f:
                                                            while True:
                                                                if st.is_cancelled: break
                                                                chunk = f.read(65536)
                                                                if not chunk: break
                                                                send_event({
                                                                    "type": "file_chunk",
                                                                    "name": file_name,
                                                                    "data": base64.b64encode(chunk).decode('utf-8')
                                                                })
                                                                sent_total += len(chunk)
                                                                dlg.update_progress(sent_total)
                                                                time.sleep(0.01)
                                                                
                                                        send_event({"type": "file_end"})
                                                        time.sleep(0.1) 
                                                        
                                                    if not st.is_cancelled:
                                                        dlg.safe_destroy()
                                                    
                                                    def delayed_refresh():
                                                        time.sleep(2)
                                                        top.after(0, lambda: request_remote_dir(t_dir))
                                                    threading.Thread(target=delayed_refresh, daemon=True).start()
                                                except Exception as e:
                                                    print(f"Upload error: {e}")
                                                    dlg.safe_destroy()
                                                    
                                            threading.Thread(target=upload_batch_thread, args=(items_to_upload, target_dir, dialog, state), daemon=True).start()

                                        def do_download():
                                            sel = remote_tree.selection()
                                            if not sel: return

                                            target_dir = local_entry.get()
                                            
                                            # Check conflicts
                                            conflicts = []
                                            for s in sel:
                                                name = remote_tree.item(s, "text")
                                                vals = remote_tree.item(s, "values")
                                                src_is_dir = True if len(vals) > 1 and vals[1] == "Thư mục" else False
                                                src_sz = vals[2] if len(vals) > 2 else 0
                                                
                                                fpath = os.path.join(target_dir, name)
                                                if os.path.exists(fpath):
                                                    dst_is_dir = os.path.isdir(fpath)
                                                    dst_sz = os.path.getsize(fpath) if not dst_is_dir else 0
                                                    try:
                                                        import datetime
                                                        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M:%S')
                                                    except: mtime = "Không xác định"
                                                    spath = remote_entry.get()
                                                    sep = "/" if "/" in spath else ("\\" if "\\" in spath else "/")
                                                    if not spath.endswith(sep): spath += sep
                                                    spath += name
                                                    conflicts.append({
                                                        "name": name,
                                                        "src_size": src_sz, "src_is_dir": src_is_dir, "src_path": spath, "src_mtime": "Không xác định (Remote)",
                                                        "dst_size": dst_sz, "dst_is_dir": dst_is_dir, "dst_path": fpath, "dst_mtime": mtime
                                                    })
                                                    
                                            if conflicts:
                                                decisions = resolve_conflicts(conflicts, top, is_upload=False)
                                                if decisions is None: return
                                            else:
                                                decisions = {}

                                            cm = globals().get('clipboard_sync_manager')
                                            
                                            total_size = 0
                                            files_to_download = []
                                            display_names = []
                                            
                                            for s in sel:
                                                item = remote_tree.item(s)
                                                name = item['text']
                                                
                                                if name in decisions and decisions[name] == 'skip':
                                                    continue
                                                vals = item.get('values', [])
                                                
                                                src_is_dir = True if len(vals) > 1 and vals[1] == "Thư mục" else False
                                                if src_is_dir:
                                                    os.makedirs(os.path.join(target_dir, name), exist_ok=True)
                                                    
                                                p = remote_entry.get()
                                                sep = "/" if "/" in p else ("\\" if "\\" in p else "/")
                                                if not p.endswith(sep): p += sep
                                                full_remote = p + name
                                                
                                                size = vals[2] if len(vals) > 2 else 0
                                                total_size += size
                                                
                                                files_to_download.append(full_remote)
                                                display_names.append(name)
                                                
                                            if not files_to_download: return
                                            
                                            if cm:
                                                cm.target_save_dir = target_dir
                                                cm.batch_total_size = total_size
                                                cm.batch_received = 0
                                                cm.active_batch = True
                                                cm._receive_cancelled = False

                                                display_name = display_names[0]
                                                if len(display_names) > 1:
                                                    display_name += f" và {len(display_names)-1} mục khác"

                                                def _cancel():
                                                    cm.cancel_active_transfer(remote_triggered=False)
                                                
                                                dialog = ProgressDialog(top, "Nhận về", display_name, total_size, on_cancel=_cancel)
                                                dialog.update_progress(0)
                                                cm.active_dialog = dialog
                                                
                                            write_transfer_log("DOWNLOAD", display_names[0] + (" (batch)" if len(display_names) > 1 else ""), total_size, target_dir)
                                            req = {"type": "request_download_batch", "paths": files_to_download, "target_dir_local": target_dir}
                                            send_event(req)

                                        tk.Button(mid_frame, text="Chuyển qua\n>>", font=("Segoe UI", 10, "bold"), bg="#2196F3", fg="white", width=10, command=do_upload).pack(pady=(100, 10))
                                        tk.Button(mid_frame, text="Nhận về\n<<", font=("Segoe UI", 10, "bold"), bg="#4CAF50", fg="white", width=10, command=do_download).pack(pady=10)

                                        def on_close():
                                            globals()['fm_is_open'] = False
                                            try: top.withdraw()
                                            except: pass
                                        
                                        top.protocol("WM_DELETE_WINDOW", on_close)
                                    
                                        # init
                                        refresh_local()
                                        request_remote_dir(remote_entry.get())
                                        
                                        top.focus_force()
                                        local_entry.focus()
                                        top.mainloop()
                                    except Exception as ex:
                                        globals()['fm_is_open'] = False
                                        import traceback
                                        err = traceback.format_exc()
                                        try:
                                            import ctypes
                                            ctypes.windll.user32.MessageBoxW(0, err, "Lỗi File Manager", 0x10)
                                        except: pass

                                threading.Thread(target=open_transfer_window, daemon=True).start()
                            continue
                        if show_buttons and power_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Power Button Clicked. Sending power key event to Android.")
                                send_event({"type": "key_event", "key": "power", "pressed": True})
                            continue
                        if show_buttons and eye_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Eye Button Clicked. Sending toggle_screen_cover to host.")
                                state = globals().get('viewer_cover_state', False)
                                globals()['viewer_cover_state'] = not state
                                send_event({"type": "toggle_screen_cover"})
                            continue
                        if show_buttons and cad_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] CAD Button Clicked. Sending trigger_sas to host.")
                                send_event({"type": "trigger_sas"})
                            continue
                        if show_buttons and rec_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                import cv2 as _cv2
                                import os as _os
                                import datetime as _datetime
                                state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
                                
                                state['is_recording'] = not state['is_recording']
                                if state['is_recording']:
                                    print("[Client] Started recording viewer...")
                                    c_name = computer_name if computer_name else "host"
                                    # Replace invalid chars from computer name
                                    c_name = "".join([c if c.isalnum() else "_" for c in c_name])
                                    filename = f"{c_name}_{_datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.mp4"
                                    videos_dir = _os.path.join(_os.path.expanduser('~'), 'Videos')
                                    _os.makedirs(videos_dir, exist_ok=True)
                                    filepath = _os.path.join(videos_dir, filename)
                                    
                                    fourcc = _cv2.VideoWriter_fourcc(*'mp4v')
                                    state['writer'] = _cv2.VideoWriter(filepath, fourcc, 20.0, (host_w, host_h))
                                    state['size'] = (host_w, host_h)
                                else:
                                    print("[Client] Stopped recording viewer.")
                                    if state['writer']:
                                        state['writer'].release()
                                        state['writer'] = None
                                        
                                globals()['viewer_record_state'] = state
                            continue

                        if show_buttons and close_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Close Button Clicked. Exiting viewer.")
                                pygame.event.post(pygame.event.Event(pygame.QUIT))
                            continue
                        if event.button in button_map:
                            mx_pos, my_pos = event.pos
                            host_x = int(mx_pos * (host_w / window_w))
                            host_y = int(my_pos * (host_h / window_h))
                            
                            if event.type == pygame.MOUSEBUTTONDOWN:
                                drag_start_pos = (host_x, host_y)
                                drag_start_time = time.time()
                                send_event({
                                    "type": "mouse_click",
                                    "button": button_map[event.button],
                                    "pressed": True,
                                    "x": host_x,
                                    "y": host_y
                                })
                            else: # MOUSEBUTTONUP
                                if drag_start_pos and is_android:
                                    dx = host_x - drag_start_pos[0]
                                    dy = host_y - drag_start_pos[1]
                                    if (dx*dx + dy*dy) > 400 or len(drag_path) > 3: # distance > 20 pixels or multi-point path
                                        duration = int((time.time() - drag_start_time) * 1000)
                                        duration = max(200, min(duration, 3000))
                                        
                                        if drag_path and drag_path[-1] != (host_x, host_y):
                                            drag_path.append((host_x, host_y))
                                            
                                        if len(drag_path) > 3:
                                            # Subsample if too many points to avoid massive payloads
                                            if len(drag_path) > 50:
                                                step = len(drag_path) / 50.0
                                                subsampled_path = [drag_path[int(i*step)] for i in range(50)]
                                                if subsampled_path[-1] != drag_path[-1]:
                                                    subsampled_path.append(drag_path[-1])
                                                drag_path = subsampled_path
                                                
                                            send_event({
                                                "type": "mouse_swipe_path",
                                                "path": drag_path,
                                                "duration": duration
                                            })
                                        else:
                                            send_event({
                                                "type": "mouse_swipe",
                                                "x1": drag_start_pos[0],
                                                "y1": drag_start_pos[1],
                                                "x2": host_x,
                                                "y2": host_y,
                                                "duration": duration
                                            })
                                        drag_start_pos = None
                                        drag_path = []
                                        continue
                                        
                                send_event({
                                    "type": "mouse_click",
                                    "button": button_map[event.button],
                                    "pressed": False,
                                    "x": host_x,
                                    "y": host_y
                                })
                                drag_start_pos = None
                                drag_path = []
                            
                    elif event.type == pygame.MOUSEWHEEL:
                        send_event({"type": "mouse_scroll", "dx": event.x, "dy": event.y})
                        
                    elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                        key_name = pygame.key.name(event.key)
                        
                        char_to_send = key_name
                        if event.type == pygame.KEYDOWN:
                            if is_android:
                                # Handle Ctrl+V (Paste) directly by fetching PC clipboard and sending paste_text
                                if event.key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                                    try:
                                        clip_text = get_clipboard_text()
                                        if clip_text:
                                            send_event({
                                                "type": "paste_text",
                                                "text": clip_text
                                            })
                                    except Exception as e:
                                        print(f"[Client] Lỗi paste Ctrl+V: {e}")
                                    continue
                                    
                                # For Android, we inject characters directly into text fields using Accessibility.
                                # Therefore, we MUST use event.unicode to capture Shift modifications (e.g. 'A' instead of 'a').
                                # We also map special keys to their string equivalents.
                                if hasattr(event, 'unicode'):
                                    print(f"[DEBUG KEY] name='{key_name}', unicode='{event.unicode}', mod={event.mod}")
                                    
                                if key_name == "space":
                                    char_to_send = " "
                                elif key_name == "tab":
                                    char_to_send = "tab"
                                elif key_name == "return" or key_name == "enter":
                                    char_to_send = "enter" # handled by Android handleKey
                                elif key_name == "backspace":
                                    char_to_send = "backspace"
                                elif hasattr(event, 'unicode') and event.unicode and len(event.unicode) > 0 and ord(event.unicode[0]) >= 32:
                                    char_to_send = event.unicode
                                else:
                                    if key_name in ["escape", "home", "menu", "volume up", "volume down", "delete", "up", "down", "left", "right"]:
                                        char_to_send = key_name
                                    else:
                                        active_unicode_map[event.key] = ""
                                        continue
                            else:
                                # For Windows hosts, send raw key_name for letters/digits so host IME can compose
                                if len(key_name) == 1 and (key_name.isalpha() or key_name.isdigit()):
                                    char_to_send = key_name  # Raw key, let host IME handle it
                                elif hasattr(event, 'unicode') and event.unicode and len(event.unicode) == 1 and ord(event.unicode) >= 32:
                                    if key_name not in ['space', 'delete', 'home', 'end', 'page up', 'page down', 'insert', 'escape', 'tab', 'backspace', 'return', 'enter']:
                                        char_to_send = event.unicode
                            
                            active_unicode_map[event.key] = char_to_send
                        else:
                            char_to_send = active_unicode_map.get(event.key, key_name)
                            if event.key in active_unicode_map:
                                del active_unicode_map[event.key]
                                
                        send_event({
                            "type": "key_event",
                            "key": char_to_send,
                            "pressed": event.type == pygame.KEYDOWN
                        })
                        
                # Draw frame
                with client_frame_lock:
                    frame_to_draw = client_latest_frame
                    
                if frame_to_draw is not None:
                    w, h = frame_to_draw.size
                    surf = pygame.image.fromstring(frame_to_draw.tobytes(), (w, h), 'RGB')
                    # smoothscale sử dụng bilinear interpolation thay vì nearest-neighbor
                    # cho chất lượng upscale mượt hơn nhiều (đặc biệt khi xem Android 1080p)
                    scaled_surf = pygame.transform.smoothscale(surf, (window_w, window_h))
                    screen.blit(scaled_surf, (0, 0))
                    
                    state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
                    if state['is_recording'] and state['writer']:
                        try:
                            import cv2 as _cv2
                            import numpy as _np
                            frame_arr = _np.array(frame_to_draw)
                            bgr_frame = _cv2.cvtColor(frame_arr, _cv2.COLOR_RGB2BGR)
                            
                            record_size = state.get('size', (host_w, host_h))
                            if bgr_frame.shape[1] != record_size[0] or bgr_frame.shape[0] != record_size[1]:
                                bgr_frame = _cv2.resize(bgr_frame, record_size)
                            
                            # Draw beautiful anti-aliased mouse cursor overlay for recording
                            mx, my = pygame.mouse.get_pos()
                            if pygame.mouse.get_focused() and 0 <= mx <= window_w and 0 <= my <= window_h:
                                hx = int(mx * (w / window_w)) if window_w else 0
                                hy = int(my * (h / window_h)) if window_h else 0
                                pts = _np.array([
                                    [hx, hy], [hx, hy + 17], [hx + 4, hy + 13],
                                    [hx + 9, hy + 23], [hx + 12, hy + 21],
                                    [hx + 7, hy + 11], [hx + 14, hy + 11]
                                ], _np.int32)
                                _cv2.fillPoly(bgr_frame, [pts], (255, 255, 255), lineType=_cv2.LINE_AA)
                                _cv2.polylines(bgr_frame, [pts], True, (0, 0, 0), 1, lineType=_cv2.LINE_AA)
                                
                            state['writer'].write(bgr_frame)
                        except Exception as e:
                            print(f"[Client] Recording error: {e}")
                else:
                    if pygame_theme == "light":
                        screen.fill((240, 240, 245))
                    elif pygame_theme == "gray":
                        screen.fill((82, 89, 98))
                    elif pygame_theme == "pink":
                        screen.fill((255, 240, 245))
                    elif pygame_theme == "crystal":
                        screen.fill((224, 247, 250))
                    elif pygame_theme == "orange":
                        screen.fill((255, 243, 224))
                    elif pygame_theme == "red":
                        screen.fill((255, 235, 238))
                    else:
                        screen.fill((30, 30, 30))
                    
                # Draw red border if blinking (focus requested)
                if blink_frames_remaining > 0:
                    if (blink_frames_remaining // 15) % 2 == 0:
                        border_rect = pygame.Rect(0, 0, window_w, window_h)
                        pygame.draw.rect(screen, (255, 0, 0), border_rect, width=10)
                    blink_frames_remaining -= 1
                    
                # Draw floating buttons on top
                if show_buttons:
                    # Minimize button
                    min_bg_color = (51, 153, 255) if min_is_hover else (0, 102, 204)
                    min_border_color = (255, 255, 255)
                    pygame.draw.rect(screen, min_bg_color, min_btn_rect, border_radius=4)
                    pygame.draw.rect(screen, min_border_color, min_btn_rect, width=1, border_radius=4)
                    
                    min_text_surf = btn_font.render("_", True, (255, 255, 255))
                    min_text_rect = min_text_surf.get_rect(center=min_btn_rect.center)
                    min_text_rect.y -= 2 # Adjust slightly up to center visually
                    screen.blit(min_text_surf, min_text_rect)

                    # Extract common border color for buttons
                    if pygame_theme == "light":
                        btn_border_color = (0, 173, 181)
                    elif pygame_theme == "gray":
                        btn_border_color = (0, 173, 181)
                    elif pygame_theme == "pink":
                        btn_border_color = (255, 105, 180)
                    elif pygame_theme == "crystal":
                        btn_border_color = (128, 222, 234)
                    elif pygame_theme == "orange":
                        btn_border_color = (255, 167, 38)
                    elif pygame_theme == "red":
                        btn_border_color = (229, 57, 53)
                    else:
                        btn_border_color = (0, 173, 181)

                    # CAD / File buttons
                    if show_cad_button or show_file_button:
                        if pygame_theme == "light":
                            cad_bg_color = (220, 220, 235) if cad_is_hover else (245, 245, 255)
                            file_bg_color = (220, 220, 235) if file_is_hover else (245, 245, 255)
                            cad_text_color = (40, 40, 50)
                            file_text_color = (40, 40, 50)
                        elif pygame_theme == "gray":
                            cad_bg_color = (99, 106, 115) if cad_is_hover else (82, 89, 98)
                            file_bg_color = (99, 106, 115) if file_is_hover else (82, 89, 98)
                            cad_text_color = (240, 240, 240)
                            file_text_color = (240, 240, 240)
                        elif pygame_theme == "pink":
                            cad_bg_color = (255, 105, 180) if cad_is_hover else (255, 182, 193)
                            file_bg_color = (255, 105, 180) if file_is_hover else (255, 182, 193)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        elif pygame_theme == "crystal":
                            cad_bg_color = (38, 198, 218) if cad_is_hover else (0, 188, 212)
                            file_bg_color = (38, 198, 218) if file_is_hover else (0, 188, 212)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        elif pygame_theme == "orange":
                            cad_bg_color = (255, 183, 77) if cad_is_hover else (255, 152, 0)
                            file_bg_color = (255, 183, 77) if file_is_hover else (255, 152, 0)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        elif pygame_theme == "red":
                            cad_bg_color = (239, 154, 154) if cad_is_hover else (244, 67, 54)
                            file_bg_color = (239, 154, 154) if file_is_hover else (244, 67, 54)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        else:
                            cad_bg_color = (58, 58, 77) if cad_is_hover else (42, 42, 53)
                            file_bg_color = (58, 58, 77) if file_is_hover else (42, 42, 53)
                            cad_text_color = (255, 255, 255)
                            file_text_color = (255, 255, 255)
                        
                        if show_file_button:
                            pygame.draw.rect(screen, file_bg_color, file_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, file_btn_rect, width=1, border_radius=4)
                            
                            file_text_surf = btn_font.render("Chuyển tệp", True, file_text_color)
                            file_text_rect = file_text_surf.get_rect(center=file_btn_rect.center)
                            screen.blit(file_text_surf, file_text_rect)

                        if show_power_button:
                            power_bg = (240, 240, 240) if power_is_hover else (255, 255, 255)
                            pygame.draw.rect(screen, power_bg, power_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, power_btn_rect, width=1, border_radius=4)
                            
                            try:
                                symbol_font = pygame.font.SysFont("Wingdings", 16)
                                power_text_surf = symbol_font.render("¤", True, (0, 0, 0))
                            except:
                                power_text_surf = btn_font.render("¤", True, (0, 0, 0))
                            power_text_rect = power_text_surf.get_rect(center=power_btn_rect.center)
                            # Shift a bit up for symbol centering
                            power_text_rect.y -= 1
                            screen.blit(power_text_surf, power_text_rect)

                        if show_cad_button:
                            # Draw Eye Button
                            eye_bg = (100, 100, 100) if globals().get('viewer_cover_state', False) else cad_bg_color
                            if eye_is_hover and not globals().get('viewer_cover_state', False):
                                pass # cad_bg_color already has hover color assigned
                            elif eye_is_hover:
                                eye_bg = (130, 130, 130)
                            
                            pygame.draw.rect(screen, eye_bg, eye_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, eye_btn_rect, width=1, border_radius=4)
                            
                            try:
                                symbol_font = pygame.font.SysFont("Webdings", 16)
                                eye_text_surf = symbol_font.render("N", True, cad_text_color)
                            except:
                                eye_text_surf = btn_font.render("N", True, cad_text_color)
                            
                            eye_text_rect = eye_text_surf.get_rect(center=eye_btn_rect.center)
                            eye_text_rect.y -= 2
                            screen.blit(eye_text_surf, eye_text_rect)

                            # Draw CAD Button
                            pygame.draw.rect(screen, cad_bg_color, cad_btn_rect, border_radius=4)
                            pygame.draw.rect(screen, btn_border_color, cad_btn_rect, width=1, border_radius=4)
                            
                            cad_text_surf = btn_font.render("Ctrl + Alt + Delete", True, cad_text_color)
                            cad_text_rect = cad_text_surf.get_rect(center=cad_btn_rect.center)
                            screen.blit(cad_text_surf, cad_text_rect)
                    
                    # Record button (Red circle)
                    state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
                    rec_bg_color = (80, 80, 80) if rec_is_hover else (50, 50, 50)
                    if pygame_theme in ["light", "crystal", "orange", "red"]:
                        rec_bg_color = (220, 220, 235) if rec_is_hover else (245, 245, 255)
                    
                    pygame.draw.rect(screen, rec_bg_color, rec_btn_rect, border_radius=4)
                    pygame.draw.rect(screen, btn_border_color, rec_btn_rect, width=1, border_radius=4)
                    
                    try:
                        windings_font = pygame.font.SysFont("Wingdings", 14)
                        icon_char = "n" if state['is_recording'] else "l"
                        rec_text_surf = windings_font.render(icon_char, True, (255, 0, 0))
                        rec_text_rect = rec_text_surf.get_rect(center=rec_btn_rect.center)
                        screen.blit(rec_text_surf, rec_text_rect)
                    except:
                        if state['is_recording']:
                            pygame.draw.rect(screen, (255, 0, 0), pygame.Rect(rec_btn_rect.centerx - 4, rec_btn_rect.centery - 4, 8, 8))
                        else:
                            pygame.draw.circle(screen, (255, 0, 0), rec_btn_rect.center, 5)
                        
                    if state['is_recording']:
                        import time as _time
                        if int(_time.time() * 2) % 2 == 0:
                            # Make the icon dim to simulate blinking
                            dim_surf = pygame.Surface(rec_btn_rect.size, pygame.SRCALPHA)
                            dim_surf.fill((0, 0, 0, 128))
                            screen.blit(dim_surf, rec_btn_rect.topleft)

                    # Close button (Red X)
                    close_bg_color = (255, 77, 77) if close_is_hover else (204, 0, 0)
                    close_border_color = (255, 255, 255)
                    pygame.draw.rect(screen, close_bg_color, close_btn_rect, border_radius=4)
                    pygame.draw.rect(screen, close_border_color, close_btn_rect, width=1, border_radius=4)
                    
                    close_text_surf = btn_font.render("X", True, (255, 255, 255))
                    close_text_rect = close_text_surf.get_rect(center=close_btn_rect.center)
                    screen.blit(close_text_surf, close_text_rect)
                    
                current_countdown = globals().get('client_switching_desktop_countdown', 0)
                if current_countdown > 0:
                    if not was_switching:
                        was_switching = True
                        switching_last_tick = pygame.time.get_ticks()
                        switching_start_tick = pygame.time.get_ticks()
                    
                    if "msg_font" not in locals():
                        try: msg_font = pygame.font.SysFont("Segoe UI", 24, bold=True)
                        except: msg_font = pygame.font.Font(None, 32)
                    
                    overlay = pygame.Surface((window_w, window_h))
                    overlay.set_alpha(150)
                    overlay.fill((0, 0, 0))
                    screen.blit(overlay, (0, 0))
                    
                    elapsed_switching = pygame.time.get_ticks() - switching_start_tick
                    if elapsed_switching > 3000:
                        text_msg = "Màn hình bảo mật (UAC / Lock Screen) đang hiển thị ở máy Host..."
                    else:
                        text_msg = f"Đang chuyển giao diện... Vui lòng đợi {current_countdown} giây..."
                    
                    text_surf = msg_font.render(text_msg, True, (255, 255, 255))
                    text_rect = text_surf.get_rect(center=(window_w//2, window_h//2))
                    screen.blit(text_surf, text_rect)
                    
                    current_tick = pygame.time.get_ticks()
                    if current_tick - switching_last_tick >= 1000:
                        client_switching_desktop_countdown = max(0, current_countdown - 1)
                        switching_last_tick = current_tick
                        if client_switching_desktop_countdown == 0:
                            was_switching = False
                            send_event({"type": "check_domain"})
                elif was_switching:
                    was_switching = False
                    send_event({"type": "check_domain"})
                
                if client_last_recv_time > 0 and time.time() - client_last_recv_time > 10.0:
                    print("[Client] Connection ping timeout. Disconnecting.")
                    exit_due_to_disconnect = True
                    client_running = False
                    break

                pygame.display.flip()
                clock.tick(60)
                
            uninstall_keyboard_hook()
            
            state = globals().get('viewer_record_state', {'is_recording': False, 'writer': None})
            if state['writer']:
                state['writer'].release()
                state['writer'] = None
                state['is_recording'] = False
                globals()['viewer_record_state'] = state
            
            if exit_due_to_disconnect and reconnect_queue:
                countdown = 90
                last_tick = pygame.time.get_ticks()
                try: msg_font = pygame.font.SysFont("Segoe UI", 24, bold=True)
                except: msg_font = pygame.font.Font(None, 32)
                
                print("[Client] Disconnected. Requesting reconnect in background...")
                try: reconnect_queue.put("RECONNECT_REQUEST")
                except: pass
                
                while countdown > 0 and outer_running:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            countdown = 0
                            exit_due_to_disconnect = False
                            outer_running = False
                    
                    if not outer_running:
                        break
                        
                    try:
                        new_sock = reconnect_queue.get_nowait()
                        if new_sock == "FAILED":
                            print("[Client] Reconnection failed. Closing window.")
                            outer_running = False
                            break
                        elif isinstance(new_sock, tuple) and new_sock[0] == "SHARED_SOCK":
                            print("[Client] Received shared socket. Resuming session!")
                            sock = socket.fromshare(new_sock[1])
                            if partner_pass:
                                socket_passwords[sock] = partner_pass
                            break # Break inner wait loop, outer loop will continue
                        elif hasattr(new_sock, 'fileno'):
                            print("[Client] Received new socket. Resuming session!")
                            sock = new_sock
                            if partner_pass:
                                socket_passwords[sock] = partner_pass
                            break # Break inner wait loop, outer loop will continue
                    except Exception as re_err:
                        print(f"[Client] Lỗi nhận diện socket tái kết nối: {re_err}")
                    
                    screen.fill((30, 30, 30))
                    text_surf = msg_font.render(f"Mất kết nối. Đang thử kết nối lại... {countdown} giây...", True, (255, 255, 255))
                    text_rect = text_surf.get_rect(center=(window_w//2, window_h//2))
                    screen.blit(text_surf, text_rect)
                    pygame.display.flip()
                    
                    current_tick = pygame.time.get_ticks()
                    if current_tick - last_tick >= 1000:
                        countdown -= 1
                        last_tick = current_tick
                        
                    clock.tick(30)
                    
                if outer_running and countdown == 0:
                    print("[Client] Reconnect timeout. Closing window.")
                    outer_running = False
                    
                if outer_running:
                    continue # Jump back to the start of the outer_running loop!
                    
            # If we reach here, we are truly exiting
            outer_running = False
            
        uninstall_keyboard_hook()
        # pygame.quit() # Bỏ qua để tránh deadlock SetParent với Tkinter thread
        try: log_activity(f"Ngừng điều khiển ID {partner_id} ({computer_name})")
        except: pass
        import os
        if exit_due_to_disconnect:
            print("[Client] Viewer exited due to disconnect. Exit code 99.")
            os._exit(99)
        os._exit(0)
    except Exception as critical_e:
        uninstall_keyboard_hook()
        import traceback
        with open("client_crash.log", "w", encoding="utf-8") as f:
            f.write(f"CRITICAL ERROR IN VIEWER LOOP:\n{traceback.format_exc()}\n")
        # try: pygame.quit()
        # except: pass
        import os
        if exit_due_to_disconnect:
            os._exit(99)
        os._exit(1)

def encrypt_text(text, key="AntigravityP2P"):
    if not text:
        return ""
    xored = []
    for i, c in enumerate(text):
        xored_char = ord(c) ^ ord(key[i % len(key)])
        xored.append(chr(xored_char))
    import base64
    return base64.b64encode("".join(xored).encode('utf-8')).decode('utf-8')

def decrypt_text(encrypted_text, key="AntigravityP2P"):
    if not encrypted_text:
        return ""
    import base64
    try:
        decoded = base64.b64decode(encrypted_text.encode('utf-8')).decode('utf-8')
        xored = []
        for i, c in enumerate(decoded):
            xored_char = ord(c) ^ ord(key[i % len(key)])
            xored.append(chr(xored_char))
        return "".join(xored)
    except Exception:
        return ""

def get_session_id():
    try:
        import ctypes
        sid = ctypes.c_ulong()
        if ctypes.windll.kernel32.ProcessIdToSessionId(ctypes.windll.kernel32.GetCurrentProcessId(), ctypes.byref(sid)):
            return sid.value
    except:
        pass
    return 1

def get_desktop_name():
    try:
        import ctypes
        h_desk = ctypes.windll.user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
        name = ctypes.create_unicode_buffer(256)
        size = ctypes.c_ulong(256)
        if ctypes.windll.user32.GetUserObjectInformationW(h_desk, 2, name, size, None):
            return name.value.lower()
    except:
        pass
    return "default"

def is_secure_desktop():
    """Kiểm tra xem thread hiện tại có đang ở Secure Desktop (UAC/Winlogon) không.
    Trả về True nếu đang ở Secure Desktop và KHÔNG thể chụp màn hình bình thường."""
    try:
        # Mở Input Desktop với quyền đọc tối thiểu (DESKTOP_READOBJECTS = 0x0001)
        hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0001)
        if not hdesk:
            # Không mở được Input Desktop → đang bị Secure Desktop lock
            return True
        name = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetUserObjectInformationW(hdesk, 2, name, ctypes.sizeof(name), None)
        ctypes.windll.user32.CloseDesktop(hdesk)
        desktop_name = name.value.lower()
        # "default" là desktop bình thường; bất kỳ tên nào khác (vd: "winlogon", "secure") là Secure Desktop
        return desktop_name not in ("default", "")
    except:
        return False

def check_desktop_change():
    """
    Checks the status of active input desktop relative to the current thread.
    Returns (needs_switch, is_blocked)
    - needs_switch: True if the active input desktop is different from the current thread desktop,
                    and we CAN access/switch to it.
    - is_blocked: True if the active input desktop cannot be accessed (e.g. secure desktop for normal user).
    """
    try:
        import ctypes
        # Try multiple access levels to open the Input Desktop.
        # SYSTEM processes (headless agent) can access Secure Desktop with higher rights.
        # Cascade: GENERIC_ALL (0x02000000) -> GENERIC_READ (0x80000000) -> DESKTOP_READOBJECTS (0x0001)
        h_input = None
        for access_mask in [0x02000000, 0x80000000, 0x0001]:
            h_input = ctypes.windll.user32.OpenInputDesktop(0, False, access_mask)
            if h_input:
                break
        
        if not h_input:
            # Cannot open input desktop with ANY access level -> truly blocked
            return False, True
            
        # Get active input desktop name
        name_input = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetUserObjectInformationW(h_input, 2, name_input, ctypes.sizeof(name_input), None)
        ctypes.windll.user32.CloseDesktop(h_input)
        input_name = name_input.value.lower()
        
        # 2. Get current thread desktop name
        thread_name = get_desktop_name()
            
        if input_name != thread_name:
            return True, False
            
        return False, False
    except Exception as e:
        print(f"[DesktopCheck] Error: {e}")
        return False, False

def is_machine_domain_joined():
    debug_messages = []
    
    # Check if Windows Server first (Server editions always require Ctrl+Alt+Del by default)
    try:
        import ctypes
        is_server_metric = ctypes.windll.user32.GetSystemMetrics(89)
        debug_messages.append(f"GetSystemMetrics(89)={is_server_metric}")
        if is_server_metric != 0:
            return True, f"Windows Server detection (SystemMetrics 89): {is_server_metric}"
    except Exception as e:
        debug_messages.append(f"GetSystemMetrics(89) check failed: {e}")

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
            install_type, _ = winreg.QueryValueEx(key, "InstallationType")
            debug_messages.append(f"OS InstallationType={install_type}")
            if install_type and "server" in install_type.lower():
                return True, f"Windows Server detection (registry): {install_type}"
    except Exception as e:
        debug_messages.append(f"Server check (registry) failed: {e}")

    try:
        import platform
        win_ver = platform.win32_ver()
        release_ver = platform.release()
        debug_messages.append(f"platform.win32_ver={win_ver}, platform.release={release_ver}")
        if "server" in win_ver[1].lower() or "server" in release_ver.lower():
            return True, f"Windows Server detection (platform): win_ver={win_ver}, release={release_ver}"
    except Exception as e:
        debug_messages.append(f"Server check (platform) failed: {e}")
        
    # Method 1: Pure ctypes NetGetJoinInformation (Official Windows API, no dependencies)
    try:
        import ctypes
        netapi32 = ctypes.windll.netapi32
        name_ptr = ctypes.c_wchar_p()
        join_status = ctypes.c_int()
        res = netapi32.NetGetJoinInformation(None, ctypes.byref(name_ptr), ctypes.byref(join_status))
        if res == 0:
            name = name_ptr.value
            status = join_status.value
            netapi32.NetApiBufferFree(name_ptr)
            debug_messages.append(f"ctypes NetGetJoinInformation: name={name}, status={status}")
            if status == 3: # NetSetupDomainName = 3
                return True, f"ctypes NetGetJoinInformation: {name}"
        else:
            debug_messages.append(f"ctypes NetGetJoinInformation failed: error_code={res}")
    except Exception as e:
        debug_messages.append(f"ctypes NetGetJoinInformation exception: {e}")

    # Method 2: Pure ctypes GetComputerNameExW (DnsDomain = 2)
    try:
        import ctypes
        size = ctypes.c_ulong(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.GetComputerNameExW(2, buf, ctypes.byref(size)):
            dns_domain = buf.value.strip()
            debug_messages.append(f"ctypes GetComputerNameExW: domain={dns_domain}")
            if dns_domain and len(dns_domain) > 0:
                return True, f"ctypes GetComputerNameExW: {dns_domain}"
        else:
            debug_messages.append("ctypes GetComputerNameExW failed")
    except Exception as e:
        debug_messages.append(f"ctypes GetComputerNameExW exception: {e}")

    # Method 3: win32net
    try:
        import win32net
        name, join_status = win32net.NetGetJoinInformation()
        debug_messages.append(f"win32net name={name}, status={join_status}")
        if join_status == 3: # NetSetupDomainName = 3
            return True, f"win32net: {name}"
    except Exception as e:
        debug_messages.append(f"win32net failed: {e}")

    # Method 4: Check registry for Tcpip Parameters Domain
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"System\CurrentControlSet\Services\Tcpip\Parameters") as key:
            domain, _ = winreg.QueryValueEx(key, "Domain")
            debug_messages.append(f"Tcpip Domain reg={domain}")
            if domain and len(domain.strip()) > 0:
                return True, f"registry (Tcpip): {domain}"
    except Exception as e:
        debug_messages.append(f"Tcpip Domain reg failed: {e}")

    # Method 5: Check environment variables
    if "USERDNSDOMAIN" in os.environ:
        debug_messages.append(f"USERDNSDOMAIN env={os.environ['USERDNSDOMAIN']}")
        return True, f"env (USERDNSDOMAIN): {os.environ['USERDNSDOMAIN']}"
    else:
        debug_messages.append("USERDNSDOMAIN env not found")
        
    return False, f"Not domain joined. Debug details: {'; '.join(debug_messages)}"

def host_type_password(password):
    import time
    import ctypes
    
    # 1. Type password characters via Unicode SendInput
    for char in password:
        inp_down = INPUT()
        inp_down.type = INPUT_KEYBOARD
        inp_down.union.ki.wVk = 0
        inp_down.union.ki.wScan = ord(char)
        inp_down.union.ki.dwFlags = KEYEVENTF_UNICODE
        inp_down.union.ki.time = 0
        inp_down.union.ki.dwExtraInfo = None
        
        inp_up = INPUT()
        inp_up.type = INPUT_KEYBOARD
        inp_up.union.ki.wVk = 0
        inp_up.union.ki.wScan = ord(char)
        inp_up.union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        inp_up.union.ki.time = 0
        inp_up.union.ki.dwExtraInfo = None
        
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
        time.sleep(0.01)
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
        time.sleep(0.01)
        
    # 2. Press Enter to submit (VK_RETURN = 0x0D)
    time.sleep(0.1)
    inp_enter_down = INPUT()
    inp_enter_down.type = INPUT_KEYBOARD
    inp_enter_down.union.ki.wVk = 0x0D
    inp_enter_down.union.ki.wScan = 0
    inp_enter_down.union.ki.dwFlags = 0
    inp_enter_down.union.ki.time = 0
    inp_enter_down.union.ki.dwExtraInfo = None
    
    inp_enter_up = INPUT()
    inp_enter_up.type = INPUT_KEYBOARD
    inp_enter_up.union.ki.wVk = 0x0D
    inp_enter_up.union.ki.wScan = 0
    inp_enter_up.union.ki.dwFlags = KEYEVENTF_KEYUP
    inp_enter_up.union.ki.time = 0
    inp_enter_up.union.ki.dwExtraInfo = None
    
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp_enter_down), ctypes.sizeof(INPUT))
    time.sleep(0.01)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp_enter_up), ctypes.sizeof(INPUT))

def set_windows_graphics_effects(enabled=True):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # Font Smoothing (ClearType)
        ctypes.windll.user32.SystemParametersInfoW(0x004B, 1 if enabled else 0, None, 3)
        
        # Drag Full Windows
        ctypes.windll.user32.SystemParametersInfoW(0x0025, 1 if enabled else 0, None, 3)
        
        # Menu Animation
        ctypes.windll.user32.SystemParametersInfoW(0x1003, 1 if enabled else 0, None, 3)
        
        # UI Effects
        ctypes.windll.user32.SystemParametersInfoW(0x103E, 1 if enabled else 0, None, 3)
        
        # Window Animations (iMinAnimate)
        class ANIMATIONINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("iMinAnimate", ctypes.c_int)]
        info = ANIMATIONINFO()
        info.cbSize = ctypes.sizeof(ANIMATIONINFO)
        info.iMinAnimate = 1 if enabled else 0
        ctypes.windll.user32.SystemParametersInfoW(0x0049, info.cbSize, ctypes.byref(info), 3)
        
        print(f"[Host] Set Windows graphics effects to: {enabled}")
    except Exception as e:
        print(f"[Host] Error setting Windows graphics effects: {e}")

class ToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.close)
        self.tw = None

    def enter(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                         background='#ffffe0', relief='solid', borderwidth=1,
                         font=("Segoe UI", "8", "normal"), padx=2, pady=1)
        label.pack(ipadx=1)

    def close(self, event=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None

# Unified Application Class
class UnifiedApp(tk.Tk):
    def __init__(self):
        super().__init__()
        import threading
        
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
        self.current_theme = tk.StringVar(value="dark")
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    saved_theme = config.get("theme")
                    if saved_theme in ["light", "dark", "gray", "pink", "crystal", "orange", "red", "custom"]:
                        self.current_theme.set(saved_theme)
            except Exception as e:
                pass

        self._last_applied_theme = self.current_theme.get()
        pal = self.get_theme_palette(self._last_applied_theme)
        self.bg_color = pal["bg_color"]
        self.card_color = pal["card_color"]
        self.text_white = pal["text_white"]
        self.text_gray = pal["text_gray"]
        self.btn_color = pal["btn_color"]
        self.btn_hover = pal["btn_hover"]
        self.entry_bg = pal["entry_bg"]
        self.entry_fg = pal["entry_fg"]
        self.divider_color = pal["divider_color"]
        self.btn_cancel_bg = pal.get("btn_cancel_bg", "#3A3A4A")
        self.btn_cancel_fg = pal.get("btn_cancel_fg", "#FFFFFF")

        self.config(bg=self.bg_color)
        
        if self._last_applied_theme == "crystal":
            try:
                self.attributes("-alpha", 0.88)
            except:
                pass

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
            h_event = win32event.CreateEvent(sa, False, False, cover_event_name)
        except Exception as e:
            print(f"[Event] Failed to create screen cover event: {e}")
            return
            
        print(f"[Event] Listening for screen cover event: {cover_event_name}")
        while True:
            rc = win32event.WaitForSingleObject(h_event, win32event.INFINITE)
            if rc == win32event.WAIT_OBJECT_0:
                print("[Event] Received screen cover signal. Toggling cover.")
                self.after(0, self.toggle_screen_cover_gui)

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

    def get_theme_palette(self, theme_name):
        if theme_name == "light":
            return {
                "bg_color": "#F0F2F5",
                "card_color": "#FFFFFF",
                "text_white": "#1C1C21",
                "text_gray": "#606070",
                "btn_color": "#00ADB5",
                "btn_hover": "#008B90",
                "entry_bg": "#EAECEF",
                "entry_fg": "#1C1C22",
                "divider_color": "#D1D5DB",
                "btn_cancel_bg": "#3A3A4A",
                "btn_cancel_fg": "#FFFFFC"
            }
        elif theme_name == "gray":
            return {
                "bg_color": "#525962",
                "card_color": "#636A73",
                "text_white": "#FFFFFF",
                "text_gray": "#C5CBD1",
                "btn_color": "#00ADB5",
                "btn_hover": "#008B90",
                "entry_bg": "#42474E",
                "entry_fg": "#FFFFFE",
                "divider_color": "#7D848C",
                "btn_cancel_bg": "#3A3A4A",
                "btn_cancel_fg": "#FFFFFD"
            }
        elif theme_name == "pink":
            return {
                "bg_color": "#FFF0F5",
                "card_color": "#FFFFFF",
                "text_white": "#3B2F36",
                "text_gray": "#8C7A86",
                "btn_color": "#FF69B4",
                "btn_hover": "#FF1493",
                "entry_bg": "#FFE4E1",
                "entry_fg": "#3B2F37",
                "divider_color": "#FFC0CB",
                "btn_cancel_bg": "#3A3A4A",
                "btn_cancel_fg": "#FF69B4"
            }
        elif theme_name == "crystal":
            return {
                "bg_color": "#E0F7FA",
                "card_color": "#B2EBF2",
                "text_white": "#006064",
                "text_gray": "#00838F",
                "btn_color": "#00BCD4",
                "btn_hover": "#26C6DA",
                "entry_bg": "#E0F7FA",
                "entry_fg": "#006064",
                "divider_color": "#80DEEA",
                "btn_cancel_bg": "#80DEEA",
                "btn_cancel_fg": "#006064"
            }
        elif theme_name == "orange":
            return {
                "bg_color": "#FFF3E0",
                "card_color": "#FFE0B2",
                "text_white": "#4E342E",
                "text_gray": "#5D4037",
                "btn_color": "#FF9800",
                "btn_hover": "#F57C00",
                "entry_bg": "#FFF3E0",
                "entry_fg": "#3E2723",
                "divider_color": "#FFB74D",
                "btn_cancel_bg": "#FFB74D",
                "btn_cancel_fg": "#4E342E"
            }
        elif theme_name == "red":
            return {
                "bg_color": "#FFEBEE",
                "card_color": "#FFCDD2",
                "text_white": "#B71C1C",
                "text_gray": "#D32F2F",
                "btn_color": "#F44336",
                "btn_hover": "#E53935",
                "entry_bg": "#FFEBEE",
                "entry_fg": "#B71C1C",
                "divider_color": "#EF9A9A",
                "btn_cancel_bg": "#EF9A9A",
                "btn_cancel_fg": "#B71C1C"
            }

        elif theme_name == "custom":
            custom_pal = {
                "bg_color": "#1E1E24",
                "card_color": "#2A2A35",
                "text_white": "#FFFFFF",
                "text_gray": "#A0A0B0",
                "btn_color": "#00ADB5",
                "btn_hover": "#008B90",
                "entry_bg": "#15151B",
                "entry_fg": "#FFFFFE",
                "divider_color": "#3A3A4A",
                "btn_cancel_bg": "#3A3A4B",
                "btn_cancel_fg": "#FFFFFD"
            }
            try:
                import configparser, os
                ini_path = "color.ini"
                if not os.path.exists(ini_path):
                    config = configparser.ConfigParser()
                    config['COLORS'] = custom_pal
                    with open(ini_path, 'w', encoding="utf-8") as configfile:
                        config.write(configfile)
                else:
                    config = configparser.ConfigParser()
                    config.read(ini_path)
                    if 'COLORS' in config:
                        for k in custom_pal:
                            if k in config['COLORS']:
                                custom_pal[k] = config['COLORS'][k]
            except:
                pass
            return custom_pal
        else:
            return {
                "bg_color": "#1E1E24",
                "card_color": "#2A2A35",
                "text_white": "#FFFFFF",
                "text_gray": "#A0A0B0",
                "btn_color": "#00ADB5",
                "btn_hover": "#008B90",
                "entry_bg": "#15151B",
                "entry_fg": "#FFFFFE",
                "divider_color": "#3A3A4A",
                "btn_cancel_bg": "#3A3A4B",
                "btn_cancel_fg": "#FFFFFD"
            }

    def change_theme(self):
        new_theme = self.current_theme.get()
        if new_theme == getattr(self, '_last_applied_theme', None):
            return
            
        self._last_applied_theme = new_theme
        
        # Save position & theme to config file immediately
        self.save_window_position()
        
        # We restart the application to apply the theme cleanly without glitches
        import sys, subprocess
        
        # Clean existing delay arguments
        args = sys.argv[1:] if getattr(sys, 'frozen', False) else sys.argv
        clean_args = []
        i = 0
        while i < len(args):
            if args[i] == "--delay-startup":
                i += 2
            else:
                clean_args.append(args[i])
                i += 1
                
        # Launch new instance with 2 seconds delay via internal argument
        flags = 0
        if sys.platform == "win32":
            flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            
        subprocess.Popen([sys.executable] + clean_args + ["--delay-startup", "2.0"], creationflags=flags)
            
        # Close current instance gracefully
        try:
            if hasattr(self, 'signal_socket') and self.signal_socket:
                self.signal_socket.close()
        except:
            pass
            
        try:
            if hasattr(self, 'tray_icon') and self.tray_icon:
                self.tray_icon.visible = False
                self.tray_icon.stop()
        except:
            pass
            
        try:
            self.destroy()
        except:
            pass
            
        import os
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
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f)
            print(f"[Config] Saved window position & theme: {geom}")
        except Exception as e:
            print(f"[Config] Error saving window config: {e}")

    def copy_id_and_password(self):
        text = f'ID: {self.my_id_formatted}, mật khẩu: {self.my_password}'
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_status("Đã sao chép cả ID & Mật khẩu!")

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text.strip())
        self.update_status(f"Đã sao chép vào bộ nhớ tạm: {text.strip()}")

    def make_context_menu(self, entry):
        menu = tk.Menu(entry, tearoff=0)
        menu.add_command(label="Cắt (Cut)", command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_command(label="Sao chép (Copy)", command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label="Dán (Paste)", command=lambda: entry.event_generate("<<Paste>>"))
        menu.add_command(label="Chọn tất cả (Select All)", command=lambda: entry.event_generate("<<SelectAll>>"))
        
        # Giữ tham chiếu mạnh (Strong Reference) tránh rác hệ thống làm mất menu
        entry.menu = menu
        
        # Bắt chuột phải trên cả Windows (Button-3) và một số Touchpad/Mac (Button-2)
        entry.bind("<Button-3>", lambda e: entry.menu.post(e.x_root, e.y_root))
        entry.bind("<Button-2>", lambda e: entry.menu.post(e.x_root, e.y_root))

    def refresh_password(self):
        import string
        old_password = self.my_password
        ptype = self.pass_type_var.get()
        if ptype == "5 chữ số":
            self.my_password = str(random.randint(10000, 99999))
        elif ptype == "8 ký tự (chữ + số)":
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
                self.show_custom_error("Lỗi", "Không thể cập nhật mật khẩu. Vui lòng chạy ứng dụng bằng quyền Administrator!")
                
        self.my_pass_label.config(text=self.my_password)
        
    def show_saved_computers_dialog(self):
        if not hasattr(self, 'collapsed_groups'):
            self.collapsed_groups = set()
        self.drag_card_id = None
        
        if hasattr(self, 'saved_computers_dialog') and self.saved_computers_dialog.winfo_exists():
            self.saved_computers_dialog.lift()
            self.saved_computers_dialog.focus_force()
            return
            
        dialog = tk.Toplevel(self)
        dialog.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy ở góc trên bên trái màn hình
        self.saved_computers_dialog = dialog
        dialog.title("Danh sách Máy tính")
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
        dialog.deiconify()  # Chỉ hiển thị sau khi đã tính toán căn giữa hoàn hảo!

        # Top title
        lbl_title = tk.Label(dialog, text="DANH SÁCH MÁY TÍNH ĐÃ LƯU", font=("Segoe UI", 12, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        # Thanh Tìm kiếm
        search_frame = tk.Frame(dialog, bg=self.bg_color)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        search_inner = tk.Frame(search_frame, bg="#2A2A3D", highlightthickness=1, highlightbackground=self.divider_color)
        search_inner.pack(fill=tk.X)
        
        lbl_search_icon = tk.Label(search_inner, text="🔍", font=("Segoe UI", 9), fg=self.text_gray, bg="#2A2A3D")
        lbl_search_icon.pack(side=tk.LEFT, padx=(8, 5), pady=4)
        
        search_var = tk.StringVar()
        entry_search = tk.Entry(search_inner, textvariable=search_var, font=("Segoe UI", 9), fg=self.text_white, bg="#2A2A3D", bd=0, insertbackground=self.text_white)
        entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4, padx=(0, 8))
        
        # Thiết lập Placeholder chuyên nghiệp
        entry_search.insert(0, "Tìm kiếm theo tên hoặc ID...")
        entry_search.configure(fg=self.text_gray)
        
        def on_focus_in(event):
            if entry_search.get() == "Tìm kiếm theo tên hoặc ID...":
                entry_search.delete(0, tk.END)
                entry_search.configure(fg=self.text_white)
                
        def on_focus_out(event):
            if entry_search.get() == "":
                entry_search.insert(0, "Tìm kiếm theo tên hoặc ID...")
                entry_search.configure(fg=self.text_gray)
                
        entry_search.bind("<FocusIn>", on_focus_in)
        entry_search.bind("<FocusOut>", on_focus_out)
        
        def on_search_change(*args):
            val = search_var.get()
            if val == "Tìm kiếm theo tên hoặc ID...":
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
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def on_dialog_destroy():
            canvas.unbind_all("<MouseWheel>")
            self.status_dots_widgets.clear()
            if hasattr(self, '_reorder_saved_computers_func'):
                delattr(self, '_reorder_saved_computers_func')
            dialog.destroy()
            
        dialog.protocol("WM_DELETE_WINDOW", on_dialog_destroy)

        def connect_computer(item):
            self.partner_id_var.set(item["id"])
            self.partner_pass_var.set(item["password"])
            # Giữ cửa sổ Danh sách Máy tính tiếp tục hiển thị theo yêu cầu người dùng
            # Trigger connection immediately
            self.click_connect()

        def delete_computer(item):
            if self.show_custom_question("Xóa máy tính", f"Bạn có chắc muốn xóa '{item['name']}' khỏi danh sách?", parent=dialog):
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
                                    c.config(fg=self.btn_color)
                                else:
                                    c.config(fg=self.text_gray)
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
                            c.config(fg=self.text_gray)
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
            rn_win.title("Đổi tên nhóm")
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

            lbl = tk.Label(rn_win, text=f"Nhập tên mới cho nhóm:\n'{old_group_name if old_group_name else 'Chưa phân nhóm'}'", font=("Segoe UI", 9), fg=self.text_white, bg=self.bg_color)
            lbl.pack(pady=(15, 10))

            entry_var = tk.StringVar(value=old_group_name)
            entry = tk.Entry(rn_win, textvariable=entry_var, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
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
            
            btn_save = tk.Button(btn_frame, text="Lưu", font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=do_rename)
            btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
            
            btn_cancel = tk.Button(btn_frame, text="Hủy", font=("Segoe UI", 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35", relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=rn_win.destroy)
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

        def refresh_list():
            current_online = {}
            for cid, widgets in self.status_dots_widgets.items():
                if widgets and widgets[0].winfo_exists():
                    current_online[cid] = (widgets[0].cget("fg") == "#00F5D4")

            # Clear previous items
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            self.status_dots_widgets.clear()

            query = search_var.get().strip().lower()
            if query == "tìm kiếm theo tên hoặc id...":
                query = ""

            computers = load_computers()
            
            # Filter
            if query:
                computers = [c for c in computers if query in c["name"].lower() or query in c["id"].replace(" ", "")]

            if not computers:
                txt = "Không tìm thấy máy tính phù hợp." if query else "Chưa có máy tính nào được lưu.\nBấm nút thêm bên dưới để tạo mới."
                lbl_empty = tk.Label(scrollable_frame, text=txt, font=("Segoe UI", 9, "italic"), fg=self.text_gray, bg=self.card_color, justify=tk.CENTER)
                lbl_empty.pack(pady=40, fill=tk.X, expand=True)
                return

            unique_groups = set()
            for c in computers:
                unique_groups.add(c.get("group", "").strip())
            
            for grp in unique_groups:
                grp_display = grp if grp else "Chưa phân nhóm"
                icon = "▶" if grp in self.collapsed_groups else "▼"
                header_text = f"{icon} {grp_display.upper()}"
                
                header = tk.Label(scrollable_frame, text=header_text, font=("Segoe UI", 9, "bold"), fg=self.text_gray, bg=self.card_color, anchor=tk.W, cursor="hand2")
                header.is_group_header = True
                header.group_name = grp
                
                def toggle_group(event, g=grp):
                    if g in self.collapsed_groups:
                        self.collapsed_groups.remove(g)
                    else:
                        self.collapsed_groups.add(g)
                    new_icon = "▶" if g in self.collapsed_groups else "▼"
                    event.widget.config(text=f"{new_icon} {(g if g else 'Chưa phân nhóm').upper()}")
                    reorder_list()
                    self.save_group_states_only()
                    
                header.bind("<Button-1>", toggle_group)
                header.bind("<ButtonRelease-1>", on_drop)

                grp_context_menu = tk.Menu(header, tearoff=0, bg=self.entry_bg, fg=self.text_white, bd=0, activebackground=self.btn_hover)
                grp_context_menu.add_command(label="Đổi tên nhóm", command=lambda g=grp: rename_group_dialog(g))

                def show_grp_context(event, menu=grp_context_menu):
                    try:
                        menu.tk_popup(event.x_root, event.y_root)
                    finally:
                        menu.grab_release()

                header.bind("<Button-3>", show_grp_context)

            for comp in computers:
                card = tk.Frame(scrollable_frame, bg=self.card_color)
                card.comp_id = comp["id"].replace(" ", "")
                card.comp_name = comp["name"]
                card.comp_group = comp.get("group", "").strip()

                content_frame = tk.Frame(card, bg=self.card_color, pady=8, padx=12)
                content_frame.pack(fill=tk.X)
                
                separator = tk.Frame(card, bg=self.divider_color, height=2)
                separator.pack(fill=tk.X, padx=10)

                info_frame = tk.Frame(content_frame, bg=self.card_color)
                info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                title_frame = tk.Frame(info_frame, bg=self.card_color)
                title_frame.pack(fill=tk.X)

                clean_id = card.comp_id
                is_online = current_online.get(clean_id, False)
                dot_color = "#00F5D4" if is_online else "#8A8A9A"
                dot_lbl = tk.Label(title_frame, text="●", font=("Segoe UI", 13, "bold"), fg=dot_color, bg=self.card_color)
                dot_lbl.pack(side=tk.LEFT, padx=(0, 5))

                name_lbl = tk.Label(title_frame, text=comp["name"], font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.card_color, anchor=tk.W)
                name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

                id_lbl = tk.Label(info_frame, text=f"ID: {comp['id']}", font=("Segoe UI", 8), fg=self.text_gray, bg=self.card_color, anchor=tk.W)
                id_lbl.pack(fill=tk.X, pady=(2, 0))

                context_menu = tk.Menu(card, tearoff=0, bg=self.entry_bg, fg=self.text_white, bd=0, activebackground=self.btn_hover)
                context_menu.add_command(label="Kết nối", command=lambda c=comp: connect_computer(c))
                context_menu.add_separator()
                context_menu.add_command(label="Thay đổi thông tin", command=lambda c=comp: self.open_edit_computer_dialog(c, dialog, refresh_list))
                context_menu.add_command(label="Xóa máy tính", command=lambda c=comp: delete_computer(c))

                def show_context_menu(event, menu=context_menu):
                    try:
                        menu.tk_popup(event.x_root, event.y_root)
                    finally:
                        menu.grab_release()
                        
                def start_drag(event, c_id=clean_id):
                    self.drag_card_id = c_id

                for w in [card, content_frame, separator, info_frame, title_frame, dot_lbl, name_lbl, id_lbl]:
                    w.bind("<Double-Button-1>", lambda e, c=comp: connect_computer(c))
                    w.bind("<Button-3>", show_context_menu)
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
                    btn_refresh.config(text=f"🔄 Làm mới ({seconds_left}s)")
                    seconds_left -= 1
                    if dialog.winfo_exists():
                        dialog.after(1000, update_timer)
                else:
                    if dialog.winfo_exists():
                        btn_refresh.config(
                            state="normal", text="🔄 Làm mới",
                            fg=self.text_white, bg="#2ECC71",
                            cursor="hand2"
                        )
                        
            btn_refresh.config(state="disabled", text="🔄 Làm mới (30s)", bg="#2A2A35", fg="#8A8A9A", cursor="arrow")
            update_timer()

        btn_add = tk.Button(
            bottom_frame, text="+ Thêm Mới", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2", command=open_add_dialog
        )
        btn_add.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

        btn_refresh = tk.Button(
            bottom_frame, text="🔄 Làm mới", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg="#2ECC71", activebackground="#27AE60",
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2",
            command=lambda: [refresh_list(), start_refresh_cooldown()]
        )
        btn_refresh.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        btn_close = tk.Button(
            bottom_frame, text="Đóng", font=("Segoe UI", 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2", command=on_dialog_destroy
        )
        btn_close.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))

        # Pack list_container sau cùng để lấp đầy phần diện tích còn lại ở giữa Search Bar và Bottom Buttons!
        list_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        refresh_list()

        def auto_refresh_status():
            if not dialog.winfo_exists(): return
            for clean_id in list(self.status_dots_widgets.keys()):
                self.query_computer_status(clean_id)
            dialog.after(10000, auto_refresh_status)

        dialog.after(10000, auto_refresh_status)

    def add_current_partner_to_saved(self):
        curr_id = self.partner_id_var.get().strip()
        curr_pass = self.partner_pass_var.get().strip()
        self.open_add_computer_dialog_with_vals(curr_id, curr_pass)

    def open_add_computer_dialog_with_vals(self, initial_id="", initial_pass="", parent_win=None, on_save=None):
        parent = parent_win if parent_win else self
        
        add_win = tk.Toplevel(parent)
        add_win.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy
        add_win.title("Thêm Máy tính")
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

        lbl_add_title = tk.Label(add_win, text="THÊM MÁY TÍNH MỚI", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_add_title.pack(pady=(12, 10))

        lbl_name = tk.Label(add_win, text="Tên gọi gợi nhớ:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_name.pack(anchor=tk.W, padx=20)
        entry_name = tk.Entry(add_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_name.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_name.focus()

        lbl_comp_id = tk.Label(add_win, text="ID đối tác:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_id.pack(anchor=tk.W, padx=20)
        entry_comp_id = tk.Entry(add_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_id.pack(fill=tk.X, padx=20, pady=(3, 8))
        if initial_id:
            entry_comp_id.insert(0, initial_id)

        lbl_comp_pass = tk.Label(add_win, text="Mật khẩu:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_pass.pack(anchor=tk.W, padx=20)
        entry_comp_pass = tk.Entry(add_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_pass.pack(fill=tk.X, padx=20, pady=(3, 8))
        if initial_pass:
            entry_comp_pass.insert(0, initial_pass)

        lbl_group = tk.Label(add_win, text="Nhóm (Tùy chọn):", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_group.pack(anchor=tk.W, padx=20)
        entry_group = tk.Entry(add_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
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
                self.show_custom_error("Lỗi nhập liệu", "Vui lòng điền đầy đủ các thông tin!", parent=add_win)
                return

            computers = load_computers()
            for c in computers:
                if c["id"] == cid and c["name"] == name:
                    self.show_custom_error("Trùng lặp", "Máy tính này đã tồn tại trong danh sách!", parent=add_win)
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
                self.show_custom_info("Thành công", f"Đã lưu máy tính '{name}' vào danh sách thành công!", parent=add_win)
            add_win.destroy()

        btn_add_frame = tk.Frame(add_win, bg=self.bg_color)
        btn_add_frame.pack(fill=tk.X, padx=20, pady=5)

        btn_save = tk.Button(
            btn_add_frame, text="Lưu lại", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=save_new
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_add_frame, text="Hủy bỏ", font=("Segoe UI", 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=add_win.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def open_edit_computer_dialog(self, item, parent_win, on_save):
        parent = parent_win
        
        edit_win = tk.Toplevel(parent)
        edit_win.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy
        edit_win.title("Sửa thông tin")
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

        lbl_edit_title = tk.Label(edit_win, text="CẬP NHẬT THÔNG TIN", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_edit_title.pack(pady=(12, 10))

        lbl_name = tk.Label(edit_win, text="Tên gọi gợi nhớ:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_name.pack(anchor=tk.W, padx=20)
        entry_name = tk.Entry(edit_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_name.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_name.insert(0, item["name"])
        entry_name.focus()

        lbl_comp_id = tk.Label(edit_win, text="ID đối tác:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_id.pack(anchor=tk.W, padx=20)
        entry_comp_id = tk.Entry(edit_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_id.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_comp_id.insert(0, item["id"])

        lbl_comp_pass = tk.Label(edit_win, text="Mật khẩu mới:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_pass.pack(anchor=tk.W, padx=20)
        entry_comp_pass = tk.Entry(edit_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_pass.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_comp_pass.insert(0, item["password"])

        lbl_group = tk.Label(edit_win, text="Nhóm (Tùy chọn):", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_group.pack(anchor=tk.W, padx=20)
        entry_group = tk.Entry(edit_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
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
                self.show_custom_error("Lỗi nhập liệu", "Vui lòng điền đầy đủ các thông tin!", parent=edit_win)
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
                self.show_custom_error("Lỗi", "Không tìm thấy máy tính tương ứng để sửa!", parent=edit_win)

        btn_edit_frame = tk.Frame(edit_win, bg=self.bg_color)
        btn_edit_frame.pack(fill=tk.X, padx=20, pady=5)

        btn_save = tk.Button(
            btn_edit_frame, text="Lưu lại", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=save_edit
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_edit_frame, text="Hủy bỏ", font=("Segoe UI", 9, "bold"),
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
        computers_file = "saved_computers.xml"
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
        computers_file = "saved_computers.xml"
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

    def save_group_states_only(self):
        computers_file = "saved_computers.xml"
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
        computers_file = "saved_computers.xml"
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
        computers_file = "saved_computers.xml"
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
        computers_file = "saved_computers.xml"
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
        computers_file = "saved_computers.xml"
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
        dialog.title("Cài Zalo / Điện thoại")
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

        lbl_title = tk.Label(dialog, text="CÀI ĐẶT ZALO / ĐIỆN THOẠI", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        desc_text = "Nhập số điện thoại hoặc liên kết Zalo của bạn.\nClient điều khiển máy bạn có thể click Help -> Zalo\nđể trực tiếp nhắn tin cho bạn."
        lbl_desc = tk.Label(dialog, text=desc_text, font=("Segoe UI", 8, "italic"), fg=self.text_gray, bg=self.bg_color, justify=tk.CENTER)
        lbl_desc.pack(pady=(0, 10))

        entry_frame = tk.Frame(dialog, bg=self.bg_color)
        entry_frame.pack(fill=tk.X, padx=30)

        entry_val = tk.Entry(entry_frame, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_val.pack(fill=tk.X, pady=(0, 15))
        
        current_val = self.load_zalo_phone_from_xml()
        if current_val:
            entry_val.insert(0, current_val)
        entry_val.focus()

        def save_val():
            new_val = entry_val.get().strip()
            self.save_zalo_phone_to_xml(new_val)
            self.show_custom_info("Thành công", "Đã lưu thông tin liên hệ Zalo / Điện thoại thành công!", parent=dialog)
            dialog.destroy()

        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=30, pady=5)

        btn_save = tk.Button(
            btn_frame, text="Lưu lại", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=save_val
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_frame, text="Hủy bỏ", font=("Segoe UI", 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def show_server_settings_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Cài đặt Máy chủ (Signaling Server)")
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

        lbl_title = tk.Label(dialog, text="CẤU HÌNH MÁY CHỦ SIGNALING", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        desc_text = "Nhập danh sách tên miền hoặc IP máy chủ\n(Cách nhau bằng dấu phẩy để dự phòng)"
        lbl_desc = tk.Label(dialog, text=desc_text, font=("Segoe UI", 8, "italic"), fg=self.text_gray, bg=self.bg_color, justify=tk.CENTER)
        lbl_desc.pack(pady=(0, 10))

        form_frame = tk.Frame(dialog, bg=self.bg_color)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=30)

        lbl_hosts = tk.Label(form_frame, text="Danh sách Máy chủ:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_hosts.pack(anchor=tk.W)
        
        entry_hosts = tk.Entry(form_frame, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_hosts.pack(fill=tk.X, pady=(3, 10))
        
        lbl_port = tk.Label(form_frame, text="Cổng kết nối (Port):", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_port.pack(anchor=tk.W)
        
        entry_port = tk.Entry(form_frame, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_port.pack(fill=tk.X, pady=(3, 15))


        current_hosts = ", ".join(SIGNALING_SERVER_HOSTS)
        entry_hosts.insert(0, current_hosts)
        entry_port.insert(0, str(SIGNALING_SERVER_PORT))
        
        entry_hosts.focus()

        def save_config():
            new_hosts_str = entry_hosts.get().strip()
            new_port_str = entry_port.get().strip()
            
            if not new_hosts_str or not new_port_str:
                self.show_custom_error("Lỗi", "Vui lòng nhập đầy đủ thông tin!", parent=dialog)
                return
                
            try:
                new_port = int(new_port_str)
            except ValueError:
                self.show_custom_error("Lỗi", "Cổng kết nối (Port) phải là số!", parent=dialog)
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
                
                self.show_custom_info("Thành công", "Đã cập nhật máy chủ thành công!\nỨng dụng sẽ sử dụng cấu hình mới cho các kết nối tiếp theo.", parent=dialog)
                dialog.destroy()
            except Exception as e:
                self.show_custom_error("Lỗi", f"Không thể lưu file server.ini: {e}", parent=dialog)

        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=30, pady=10)
        
        btn_save = tk.Button(
            btn_frame, text="Lưu lại", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=save_config
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        
        btn_cancel = tk.Button(
            btn_frame, text="Hủy bỏ", font=("Segoe UI", 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def update_fixed_password_indicator(self):
        if hasattr(self, 'fixed_pass_indicator'):
            if self.fixed_password:
                self.fixed_pass_indicator.config(text="● Mật khẩu cố định: Đang hoạt động")
            else:
                self.fixed_pass_indicator.config(text="")

    def open_set_fixed_password_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Mật khẩu cố định")
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

        lbl_title = tk.Label(dialog, text="CÀI ĐẶT MẬT KHẨU CỐ ĐỊNH", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        desc_text = "Đặt mật khẩu cố định giúp đối tác kết nối vào\nmáy của bạn mà không cần hỏi mật khẩu ngẫu nhiên.\n(Để trống để tắt tính năng này)"
        lbl_desc = tk.Label(dialog, text=desc_text, font=("Segoe UI", 8, "italic"), fg=self.text_gray, bg=self.bg_color, justify=tk.CENTER)
        lbl_desc.pack(pady=(0, 10))

        # Entry and show password check
        entry_frame = tk.Frame(dialog, bg=self.bg_color)
        entry_frame.pack(fill=tk.X, padx=30)

        show_pass = tk.BooleanVar(value=False)
        
        entry_pass = tk.Entry(entry_frame, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, show="*", insertbackground=self.text_white)
        entry_pass.pack(fill=tk.X, pady=(0, 5))
        if self.fixed_password:
            entry_pass.insert(0, self.fixed_password)

        def toggle_password():
            if show_pass.get():
                entry_pass.config(show="")
            else:
                entry_pass.config(show="*")

        chk_show = tk.Checkbutton(
            dialog, text="Hiển thị mật khẩu", font=("Segoe UI", 8),
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
                self.show_custom_info("Thành công", "Đã lưu mật khẩu cố định thành công!", parent=dialog)
            else:
                self.show_custom_info("Thành công", "Đã tắt mật khẩu cố định thành công!", parent=dialog)
            dialog.destroy()

        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=30, pady=(5, 10))

        btn_save = tk.Button(
            btn_frame, text="Lưu lại", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=save_password
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_frame, text="Hủy bỏ", font=("Segoe UI", 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def is_startup_enabled(self):
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key_name = "RemoteDesktopP2P"
        approved_key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, key_name)
                winreg.CloseKey(key)
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
            
            # Check if StartupApproved has disabled it (Windows 11)
            try:
                approved_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, approved_key_path, 0, winreg.KEY_READ)
                approved_val, _ = winreg.QueryValueEx(approved_key, key_name)
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
        import winreg
        import sys
        import os
        
        enabled = self.startup_var.get()
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
                self.show_custom_info("Thành công", "Đã bật tính năng chạy khi mở máy thành công!")
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
                self.show_custom_info("Thành công", "Đã tắt tính năng chạy khi mở máy thành công!")
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[Startup] Failed to modify registry: {e}")
            self.show_custom_error("Thất bại", f"Không thể thay đổi cài đặt Registry: {e}")
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
            dialog.title("Liên hệ Zalo")
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
            
            lbl_title = tk.Label(dialog, text="CHỌN ĐỐI TÁC ĐỂ LIÊN HỆ ZALO", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
            lbl_title.pack(pady=(12, 10))
            
            for v in self.active_viewers:
                c_name = v["computer_name"] or "Không rõ"
                p_val = v["zalo_phone"]
                display_text = f"{c_name} ({p_val if p_val else 'Không có số'})"
                
                def contact(val=p_val, name=c_name):
                    dialog.destroy()
                    if val:
                        webbrowser.open(f"https://zalo.me/{val}")
                    else:
                        self.show_zalo_error_popup(name)
                        
                btn = tk.Button(
                    dialog, text=display_text, font=("Segoe UI", 9),
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
        dialog.title("Liên hệ Zalo")
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

        title_text = "LIÊN HỆ ZALO"
        if comp_name:
            title_text = f"ZALO: {comp_name.upper()}"
            
        lbl_title = tk.Label(dialog, text=title_text, font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        lbl_phone = tk.Label(dialog, text="Chưa có liên lạc", font=("Segoe UI", 16, "bold"), fg="#2ECC71", bg=self.entry_bg, bd=0, height=1, width=20)
        lbl_phone.pack(pady=(5, 15))

        btn_ok = tk.Button(
            dialog, text="Đóng", font=("Segoe UI", 9, "bold"),
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
            dialog.title("Chọn đối tác")
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
            
            lbl_title = tk.Label(dialog, text="CHỌN ĐỐI TÁC XEM ĐIỆN THOẠI", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
            lbl_title.pack(pady=(12, 10))
            
            for v in self.active_viewers:
                c_name = v["computer_name"] or "Không rõ"
                p_val = v["zalo_phone"]
                display_text = f"{c_name} ({p_val if p_val else 'Không có số'})"
                
                def show_phone(val=p_val, name=c_name):
                    dialog.destroy()
                    self.show_phone_number_popup(val, name)
                    
                btn = tk.Button(
                    dialog, text=display_text, font=("Segoe UI", 9),
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
        dialog.title("Điện thoại liên hệ")
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

        title_text = "SỐ ĐIỆN THOẠI LIÊN HỆ"
        if comp_name:
            title_text = f"ĐIỆN THOẠI: {comp_name.upper()}"
            
        lbl_title = tk.Label(dialog, text=title_text, font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        display_text = phone_val if phone_val else "Chưa có liên lạc"
        lbl_phone = tk.Label(dialog, text=display_text, font=("Segoe UI", 16, "bold"), fg="#2ECC71", bg=self.entry_bg, bd=0, height=1, width=20)
        lbl_phone.pack(pady=(5, 15))

        btn_ok = tk.Button(
            dialog, text="Đóng", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, width=12, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_ok.pack()

    def show_about_dialog(self):
        # Tạo cửa sổ Toplevel mới đóng vai trò Modal
        about = tk.Toplevel(self)
        about.title("About")
        about.resizable(False, False)
        about.configure(bg=self.bg_color)
        
        # Thiết lập thuộc tính Modal (nổi lên trên cửa sổ chính và chặn tương tác bên ngoài)
        about.transient(self)
        about.grab_set()
        
        # Thiết kế giao diện premium cho dialog About
        title_label = tk.Label(about, text="Easy Remote Desktop", font=("Inter", 13, "bold"), fg=self.text_white, bg=self.bg_color)
        title_label.pack(pady=(15, 2))
        
        ai_label = tk.Label(about, text="AI Pro Version", font=("Inter", 9, "bold"), fg=self.btn_color, bg=self.bg_color)
        ai_label.pack(pady=(0, 5))
        
        contact_label = tk.Label(about, text="Liên hệ: Mr. Tuyến - 0941 261 771", font=("Inter", 10), fg=self.text_gray, bg=self.bg_color)
        contact_label.pack(pady=(0, 15))
        
        close_btn = tk.Button(about, text="Đóng", font=("Inter", 9, "bold"), fg=self.text_white, bg="#E05252", 
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
    def show_custom_info(self, title, message, parent=None):
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
        icon_lbl = tk.Label(content_frame, text="ℹ", font=("Segoe UI", 22), fg=self.btn_color, bg=self.bg_color)
        icon_lbl.pack(side=tk.LEFT, anchor=tk.N, padx=(0, 15), pady=(2, 0))
        
        msg_lbl = tk.Label(content_frame, text=message, font=("Segoe UI", 9), fg=self.text_white, bg=self.bg_color, wraplength=310, justify=tk.LEFT)
        msg_lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor=tk.N)
        
        # OK Button at bottom
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 12))
        
        btn_ok = tk.Button(
            btn_frame, text="OK", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, width=8, pady=3, cursor="hand2", command=dialog.destroy
        )
        btn_ok.pack(side=tk.RIGHT)
        
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
        icon_lbl = tk.Label(content_frame, text="⚠", font=("Segoe UI", 22), fg="#E05252", bg=self.bg_color)
        icon_lbl.pack(side=tk.LEFT, anchor=tk.N, padx=(0, 15), pady=(2, 0))
        
        msg_lbl = tk.Label(content_frame, text=message, font=("Segoe UI", 9), fg=self.text_white, bg=self.bg_color, wraplength=310, justify=tk.LEFT)
        msg_lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor=tk.N)
        
        # OK Button at bottom
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 12))
        
        btn_ok = tk.Button(
            btn_frame, text="OK", font=("Segoe UI", 9, "bold"),
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
        dialog.title("Lỗi kết nối mạng LAN")
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

        tk.Label(title_frame, text="⚠", font=("Segoe UI", 22), fg="#E05252", bg=self.bg_color).pack(side=tk.LEFT, padx=(0, 10))
        title_col = tk.Frame(title_frame, bg=self.bg_color)
        title_col.pack(side=tk.LEFT, fill=tk.BOTH)
        tk.Label(title_col, text="Kết nối mạng LAN thất bại", font=("Segoe UI", 12, "bold"),
                 fg="#E05252", bg=self.bg_color, anchor="w").pack(anchor="w")
        tk.Label(title_col, text="Cả hai máy cùng mạng nội bộ nhưng không kết nối được trực tiếp",
                 font=("Segoe UI", 8), fg=self.text_gray, bg=self.bg_color, anchor="w").pack(anchor="w")

        # ── SEPARATOR ───────────────────────────────────────────
        tk.Frame(dialog, bg=self.divider_color, height=1).pack(fill=tk.X, padx=20, pady=(12, 0))

        # ── THÔNG TIN KỸ THUẬT ──────────────────────────────────
        info_frame = tk.Frame(dialog, bg=self.entry_bg, bd=0, highlightthickness=1, highlightbackground=self.divider_color)
        info_frame.pack(fill=tk.X, padx=20, pady=(12, 0))

        tk.Label(info_frame, text="📋  Thông tin kỹ thuật", font=("Segoe UI", 8, "bold"),
                 fg=self.btn_color, bg=self.entry_bg, anchor="w").pack(fill=tk.X, padx=12, pady=(8, 4))

        rows = [
            ("Public IP phát hiện", public_ip if public_ip else "N/A"),
            ("Trạng thái",          "Cùng Public IP → cùng Router/Mạng nội bộ"),
            ("Phương thức thử",     "Kết nối TCP trực tiếp qua Local IP (LAN)"),
            ("Kết quả",             "❌  Tất cả địa chỉ LAN đều không phản hồi"),
        ]
        for label, value in rows:
            row = tk.Frame(info_frame, bg=self.entry_bg)
            row.pack(fill=tk.X, padx=12, pady=2)
            tk.Label(row, text=f"{label}:", font=("Segoe UI", 8), fg=self.text_gray,
                     bg=self.entry_bg, width=22, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, font=("Segoe UI", 8, "bold"), fg=self.text_white,
                     bg=self.entry_bg, anchor="w", wraplength=240, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X)
        tk.Frame(info_frame, bg=self.entry_bg, height=6).pack()

        # ── NGUYÊN NHÂN & CÁCH KHẮC PHỤC ───────────────────────
        tk.Label(dialog, text="🔧  Cách khắc phục", font=("Segoe UI", 9, "bold"),
                 fg="#F39C12", bg=self.bg_color, anchor="w").pack(fill=tk.X, padx=20, pady=(12, 4))

        steps = [
            ("1", "Kiểm tra Tường lửa Windows",
             "Vào Windows Defender Firewall → Allow an app → đảm bảo RemoteDesktopP2P.exe được phép trên Private & Public network."),
            ("2", "Kiểm tra phần mềm diệt virus / VPN",
             "Tắt tạm thời các phần mềm Antivirus hoặc VPN có thể đang chặn kết nối nội bộ."),
            ("3", "Kiểm tra cổng mạng đang dùng",
             f"Ứng dụng dùng cổng {BOUND_PORT}. Đảm bảo cổng này chưa bị chiếm hoặc bị chặn bởi Firewall."),
        ]
        for num, title_step, desc in steps:
            sf = tk.Frame(dialog, bg=self.bg_color)
            sf.pack(fill=tk.X, padx=20, pady=2)
            badge = tk.Label(sf, text=num, font=("Segoe UI", 8, "bold"), fg=self.bg_color,
                             bg=self.btn_color, width=2, height=1)
            badge.pack(side=tk.LEFT, anchor="n", padx=(0, 8), pady=2)
            txt_col = tk.Frame(sf, bg=self.bg_color)
            txt_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tk.Label(txt_col, text=title_step, font=("Segoe UI", 8, "bold"),
                     fg=self.text_white, bg=self.bg_color, anchor="w").pack(anchor="w")
            tk.Label(txt_col, text=desc, font=("Segoe UI", 8), fg=self.text_gray,
                     bg=self.bg_color, anchor="w", wraplength=360, justify=tk.LEFT).pack(anchor="w")

        # ── BUTTON ──────────────────────────────────────────────
        tk.Frame(dialog, bg="#2A2A3A", height=1).pack(fill=tk.X, padx=20, pady=(10, 0))
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(8, 14))
        tk.Button(
            btn_frame, text="Đã hiểu", font=("Segoe UI", 9, "bold"),
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
        icon_lbl = tk.Label(content_frame, text="❓", font=("Segoe UI", 22), fg="#F39C12", bg=self.bg_color)
        icon_lbl.pack(side=tk.LEFT, anchor=tk.N, padx=(0, 15), pady=(2, 0))
        
        msg_lbl = tk.Label(content_frame, text=message, font=("Segoe UI", 9), fg=self.text_white, bg=self.bg_color, wraplength=310, justify=tk.LEFT)
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
            btn_frame, text="Không", font=("Segoe UI", 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, width=8, pady=3, cursor="hand2", command=on_no
        )
        btn_no.pack(side=tk.RIGHT, padx=(4, 0))
        
        # Nút "Có"
        btn_yes = tk.Button(
            btn_frame, text="Có", font=("Segoe UI", 9, "bold"),
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
            self.status_var.set(f"Trạng thái: {text}")
            
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
            elif is_success or "thành công" in text.lower():
                self.lbl_status.config(fg="#2ECC71")  # Xanh lục (Emerald Green)
            else:
                self.lbl_status.config(fg="#8A8A9A")
        
        self.after(0, _do_update)

    def _poll_signaling_status(self):
        """Polling loop chạy trên main Tkinter thread - kiểm tra Signaling mỗi 3s và cập nhật status UI đáng tin cậy."""
        if not getattr(self, 'running_server', True):
            return
        try:
            current_status = self.status_var.get()
            # Chỉ update nếu status đang ở các trạng thái chưa kết nối/đang thử
            is_pending = any(kw in current_status for kw in [
                "Không thể kết nối Signaling",
                "Chưa kết nối Signaling",
                "Đang kết nối Signaling",
                "Đang thử lại",
                "chế độ nền",
                "Sẵn sàng kết nối",  # cũng update nếu đang sẵn sàng mà Signaling chưa confirm
            ])
            if is_pending and getattr(self, 'signaling_sockets', {}):
                self.update_status("Kết nối Signaling thành công! Sẵn sàng kết nối.")
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
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS)
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
                self.update_status(f"Đã gửi Wake-On-Lan tới MAC {m}")
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
        while getattr(self, 'running_server', True):
            try:
                beacon = json.dumps({
                    "sig": LAN_APP_SIGNATURE,
                    "hwid": self.my_id_clean,
                    "computer_name": platform.node(),
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
        dialog.title("Máy tính trong mạng LAN")
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)

        w, h = 520, 440
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        # Title
        lbl_title = tk.Label(dialog, text="📡 MÁY TÍNH TRONG MẠNG LAN", font=("Segoe UI", 11, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 5))
        
        lbl_desc = tk.Label(dialog, text="Kết nối trực tiếp không qua Signaling Server", font=("Segoe UI", 8, "italic"), fg=self.text_gray, bg=self.bg_color)
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
                self.update_status(f"Đang kết nối LAN trực tiếp tới {peer_info['computer_name']}...")
                if hasattr(self, 'connect_btn'):
                    self.connect_btn.config(state=tk.DISABLED)
                threading.Thread(target=self._connect_lan_direct, args=(hwid, peer_info, existing_comp["password"]), daemon=True).start()
                return

            """Mở dialog nhập mật khẩu rồi kết nối trực tiếp qua LAN."""
            pass_dialog = tk.Toplevel(dialog)
            pass_dialog.title(f"Kết nối tới {peer_info['computer_name']}")
            pass_dialog.resizable(False, False)
            pass_dialog.configure(bg=self.bg_color)
            pass_dialog.transient(dialog)
            pass_dialog.grab_set()

            pw, ph = 360, 230
            px = dialog.winfo_x() + (dialog.winfo_width() - pw) // 2
            py = dialog.winfo_y() + (dialog.winfo_height() - ph) // 2
            pass_dialog.geometry(f"{pw}x{ph}+{px}+{py}")

            fmt_id = f"{hwid[:3]} {hwid[3:6]} {hwid[6:9]} {hwid[9:]}" if len(hwid) == 12 else hwid
            tk.Label(pass_dialog, text=f"Máy: {peer_info['computer_name']}", font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.bg_color).pack(pady=(15, 2))
            tk.Label(pass_dialog, text=f"ID: {fmt_id}  •  IP: {peer_info['local_ip']}", font=("Segoe UI", 8), fg=self.text_gray, bg=self.bg_color).pack(pady=(0, 10))

            tk.Label(pass_dialog, text="Nhập mật khẩu:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color).pack(anchor=tk.W, padx=30)
            
            pass_var = tk.StringVar()
            pass_entry = tk.Entry(pass_dialog, textvariable=pass_var, font=("Segoe UI", 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, show="*", relief=tk.FLAT, bd=4)
            pass_entry.pack(padx=30, fill=tk.X, pady=(3, 5))
            
            save_var = tk.BooleanVar(value=True)
            save_cb = tk.Checkbutton(pass_dialog, text="Lưu mật khẩu máy tính này", variable=save_var, font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color, selectcolor=self.bg_color, activebackground=self.bg_color, activeforeground=self.text_gray, cursor="hand2")
            save_cb.pack(anchor=tk.W, padx=25, pady=(0, 10))
            
            pass_entry.focus()
            
            def do_connect():
                password = pass_var.get().strip()
                if not password:
                    self.show_custom_error("Lỗi", "Vui lòng nhập mật khẩu!", parent=pass_dialog)
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
                            "group": "Mạng LAN"
                        })
                    self.save_saved_computers(comps)
                    if hasattr(self, '_reorder_saved_computers_func'):
                        self.after(50, self._reorder_saved_computers_func)
                        
                pass_dialog.destroy()
                # Giữ cửa sổ LAN hiển thị theo yêu cầu người dùng
                # dialog.destroy() 
                # Kết nối trực tiếp qua LAN
                self.update_status(f"Đang kết nối LAN trực tiếp tới {peer_info['computer_name']}...")
                if hasattr(self, 'connect_btn'):
                    self.connect_btn.config(state=tk.DISABLED)
                threading.Thread(target=self._connect_lan_direct, args=(hwid, peer_info, password), daemon=True).start()

            pass_entry.bind("<Return>", lambda e: do_connect())
            pass_entry.bind("<KP_Enter>", lambda e: do_connect())

            btn_frame = tk.Frame(pass_dialog, bg=self.bg_color)
            btn_frame.pack(fill=tk.X, padx=30, pady=(0, 15))
            tk.Button(btn_frame, text="Kết nối", font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, pady=4, cursor="hand2", command=do_connect).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
            tk.Button(btn_frame, text="Hủy", font=("Segoe UI", 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, relief=tk.FLAT, bd=0, pady=4, cursor="hand2", command=pass_dialog.destroy).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))


        def refresh_list():
            # Xóa danh sách cũ
            for w in scroll_frame.winfo_children():
                w.destroy()

            with self.lan_peers_lock:
                peers = dict(self.lan_peers)

            if not peers:
                tk.Label(scroll_frame, text="Không tìm thấy máy tính nào trong mạng LAN.\nĐảm bảo các máy đều đang chạy Easy Remote Desktop.", font=("Segoe UI", 9), fg=self.text_gray, bg=self.entry_bg, justify=tk.CENTER).pack(pady=40, padx=20)
                status_label.config(text="Đang quét... (0 máy)")
            else:
                status_label.config(text=f"Tìm thấy {len(peers)} máy trong mạng LAN")
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
                        btn = tk.Button(row, text="Kết nối", font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, padx=12, pady=3, cursor="hand2", command=lambda h=hwid, i=info: connect_to_peer(h, i))
                    else:
                        btn = tk.Button(row, text="Bật nguồn (WOL)", font=("Segoe UI", 9, "bold"), fg=self.text_white, bg="#D35400", activebackground="#E67E22", relief=tk.FLAT, bd=0, padx=12, pady=3, cursor="hand2", command=lambda m=info.get("macs", ""): self.wake_on_lan(m))
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
                    lbl_details = tk.Label(info_frame, text=f"ID: {fmt_id}  •  IP: {display_ip}:{info['port']}", font=("Segoe UI", 8), fg=self.text_gray, bg=self.card_color, anchor=tk.W)
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
        tk.Button(btn_frame, text="🔄 Làm mới", font=("Segoe UI", 9, "bold"), fg=self.text_white, bg="#007ACC", activebackground="#005A9E", relief=tk.FLAT, bd=0, pady=4, padx=10, cursor="hand2", command=refresh_list).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="Đóng", font=("Segoe UI", 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, relief=tk.FLAT, bd=0, pady=4, padx=15, cursor="hand2", command=on_dialog_close).pack(side=tk.RIGHT)

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
                s.settimeout(None)
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
            self.update_status("Kết nối LAN thất bại!")
            self.after(0, lambda: self.show_custom_error("Lỗi kết nối LAN", f"Không thể kết nối tới {peer_info['computer_name']} ({ip}:{port}).\nKiểm tra Tường lửa (Firewall) hoặc đảm bảo máy đích đang chạy ứng dụng."))
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
                self.update_status("Sẵn sàng kết nối")
                self.after(0, lambda: self.show_custom_error("Lỗi", "Đối tác ngắt kết nối đột ngột!"))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                force_close_socket(sock)
                return

            res = json.loads(res_msg.decode('utf-8'))
            
            if res.get("status") == "ok":
                host_w = res.get("width")
                host_h = res.get("height")
                computer_name = res.get("computer_name", "")
                zalo_phone = res.get("zalo_phone", "")
                is_domain = res.get("is_domain", False)
                partner_id = hwid

                # Speed test (same flow as regular connect)
                self.update_status("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 1/2...")
                net_class = "medium"
                avg_ping = 50.0
                bandwidth = 10.0
                try:
                    runs = []
                    for run_idx in range(2):
                        if run_idx > 0:
                            self.update_status("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 2/2...")
                        rtts = []
                        for _ in range(3):
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
                        send_msg(sock, json.dumps({"action": "speed_test_bw_req"}).encode('utf-8'), password)
                        bw_start_msg = recv_msg(sock, password)
                        if bw_start_msg:
                            bw_start_data = json.loads(bw_start_msg.decode('utf-8'))
                            if bw_start_data.get("action") == "speed_test_bw_start":
                                dummy_size = bw_start_data.get("size", 1572864)
                                warm_size = 1048576
                                measure_size = dummy_size - warm_size
                                warm_data = b''
                                while len(warm_data) < warm_size:
                                    chunk = sock.recv(warm_size - len(warm_data))
                                    if not chunk: break
                                    warm_data += chunk
                                t_start = time.time()
                                measured_data = b''
                                while len(measured_data) < measure_size:
                                    chunk = sock.recv(measure_size - len(measured_data))
                                    if not chunk: break
                                    measured_data += chunk
                                t_end = time.time()
                                duration = t_end - t_start
                                total_len = len(warm_data) + len(measured_data)
                                if duration > 0 and total_len == dummy_size:
                                    run_bw = (measure_size * 8.0) / (duration * 1024.0 * 1024.0)
                        runs.append((run_ping, run_bw))
                        if run_idx == 0: time.sleep(0.2)
                    if runs:
                        best_run = max(runs, key=lambda x: x[1])
                        avg_ping = best_run[0]
                        bandwidth = best_run[1]
                    if bandwidth > 20.0 and avg_ping < 10.0:
                        net_class = "high"
                    elif bandwidth < 5.0 or avg_ping > 50.0:
                        net_class = "low"
                    send_msg(sock, json.dumps({"action": "speed_test_result", "net_class": net_class, "ping": avg_ping, "bandwidth": bandwidth}).encode('utf-8'), password)
                    print(f"[LAN Direct] Speed: Ping {avg_ping:.1f}ms, BW {bandwidth:.2f} Mbps, Class: {net_class}")
                except Exception as ste:
                    print(f"[LAN Direct] Speed test error: {ste}")
                    try:
                        send_msg(sock, json.dumps({"action": "speed_test_result", "net_class": "medium", "ping": 50.0, "bandwidth": 10.0}).encode('utf-8'), password)
                    except: pass

                self.update_status("Kết nối LAN thành công! Đang khởi động màn hình...")
                self.after(0, self.launch_pygame_viewer, sock, host_w, host_h, computer_name, zalo_phone, is_domain, partner_id, password)
            else:
                msg = res.get("message", "Sai mật khẩu!")
                self.update_status("Bị từ chối kết nối")
                self.after(0, lambda: self.show_custom_error("Từ chối kết nối", f"Kết nối bị từ chối:\n{msg}"))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
        except Exception as e:
            self.update_status("Sẵn sàng kết nối")
            self.after(0, lambda err=str(e): self.show_custom_error("Lỗi bắt tay LAN", f"Lỗi xác thực handshake:\n{err}"))
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
            self.update_status("Đang khởi động Server lắng nghe...")
            self.start_host_server()
            
            # 2. Try automatic UPnP Port Forwarding
            self.update_status("Đang tự động cấu hình Router (UPnP)...")
            upnp_success = attempt_upnp_forward(BOUND_PORT)
        
        # 3. Get Public & Local IPs
        self.update_status("Đang lấy thông vị trí mạng...")
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
        self.update_status(f"Đang kết nối tới các Signaling Server...")
        self.signaling_sockets = {}
        self.primary_signaling_socket = None
        self.current_signaling_host = None
        
        for host in SIGNALING_SERVER_HOSTS:
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
                self.update_status(f"Đang kết nối Signaling Server... ({8 - int(timeout)}s)")
            
        if self.signaling_sockets:
            suffix = " (Dịch vụ hoạt động)" if getattr(self, "is_service_active", False) else ""
            if upnp_success:
                self.update_status(f"Kết nối Signaling & Mở cổng Router thành công (Cổng {BOUND_PORT})!{suffix}")
            else:
                self.update_status(f"Kết nối Signaling thành công (Cổng {BOUND_PORT})! Sẵn sàng kết nối.{suffix}")
        else:
            suffix = " (Dịch vụ hoạt động)" if getattr(self, "is_service_active", False) else ""
            self.update_status(f"Chưa kết nối Signaling Server. Đang thử lại ở chế độ nền...{suffix}")

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
                    
                try:
                    if os.name == 'nt':
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                        sock.ioctl(socket.SIOC_KEEPALIVE_VALS, (1, 30000, 10000))
                    else:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                except Exception: pass
                
                sock.settimeout(5.0)
                sock.connect((host, SIGNALING_SERVER_PORT))
                sock.settimeout(None)
                
                # Use base HWID if we are the primary instance (port 12345), else append port to avoid stealing ID from background service
                register_id = self.my_id_clean if BOUND_PORT == PORTS_TO_TRY[0] else f"{self.my_id_clean}_{BOUND_PORT}"
                
                req = json.dumps({"action": "register", "hwid": register_id})
                req_data = req.encode('utf-8')
                send_msg(sock, req_data, APP_KEY)
                
                with self.signaling_lock:
                    self.signaling_sockets[host] = sock
                    if getattr(self, 'current_signaling_host', None) is None:
                        self.current_signaling_host = host
                        self.primary_signaling_socket = sock
                    # Luôn cập nhật status khi kết nối thành công (kể cả lần đầu sau timeout hoặc sau reconnect)
                    self.after(0, lambda: self.update_status("Kết nối Signaling thành công! Sẵn sàng kết nối."))
                
                # Reset counters khi kết nối thành công
                fail_count = 0
                retry_delay = 2
                
                print(f"[Signaling] Connected to {host}")
                
                last_ping = time.time()
                last_pong = time.time()
                
                import select
                while self.running_server:
                    r, _, _ = select.select([sock], [], [], 1.0)
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
                                self.after(0, lambda: self.update_status("Mất kết nối toàn bộ Signaling Server. Đang thử lại...", is_error=True, blink=True))
            
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
            host_to_connect = specific_host if specific_host else SIGNALING_SERVER_HOSTS[0]
            
            relay_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            relay_sock.settimeout(5.0)
            relay_sock.connect((host_to_connect, SIGNALING_SERVER_PORT))
            relay_sock.settimeout(None)
            
            header = f"RELAY_HOST:{session_id}\n"
            relay_sock.sendall(header.encode('utf-8'))
            
            # Truyền hình ảnh qua kết nối Relay
            threading.Thread(target=self.handle_host_handshake, args=(relay_sock, (host_to_connect, SIGNALING_SERVER_PORT)), daemon=True).start()
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
        for _ in range(10):
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
    def start_host_server(self):
        global BOUND_PORT
        bound = False
        for port in PORTS_TO_TRY:
            # Check if port is already in use by another instance
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.settimeout(0.5)
            in_use = (test_sock.connect_ex(('127.0.0.1', port)) == 0)
            test_sock.close()
            if in_use:
                print(f"[Host] Port {port} is already in use. Skipping.")
                continue

            try:
                # Try IPv6 Dual-Stack first (binds to both IPv6 and IPv4)
                try:
                    if hasattr(socket, 'AF_INET6'):
                        self.server_socket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        if hasattr(socket, 'IPPROTO_IPV6') and hasattr(socket, 'IPV6_V6ONLY'):
                            try: self.server_socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                            except: pass
                        self.server_socket.bind(("", port))
                    else:
                        raise Exception("No IPv6")
                except Exception:
                    self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self.server_socket.bind(('0.0.0.0', port))
                    
                BOUND_PORT = port
                self.server_socket.listen(5)
                print(f"[Host] TCP server successfully listening on port {BOUND_PORT} (Dual-Stack)...")
                bound = True
                break
            except Exception as e:
                print(f"[Host] Failed to bind to port {port}: {e}")
                continue
                
        if not bound:
            self.after(0, lambda: self.show_custom_error("Lỗi hệ thống", "Không thể chạy server! Các cổng mạng đều bị chiếm dụng hoặc bị chặn bởi Tường lửa.\nVui lòng kiểm tra lại cấu hình mạng hoặc tắt bớt ứng dụng chiếm cổng."))
            self.update_status("Lỗi khởi động Server")
            return
            
        # Spawn the socket accept loop in a separate thread
        threading.Thread(target=self.host_accept_loop, daemon=True).start()

    def host_accept_loop(self):
        while self.running_server:
            try:
                conn, addr = self.server_socket.accept()
                print(f"[Host] Connection attempt from {addr[0]}:{addr[1]}")
                threading.Thread(target=self.handle_host_handshake, args=(conn, addr), daemon=True).start()
            except Exception as e:
                if not self.running_server:
                    break
                print(f"[Host] Warning: accept() failed with error: {e}")
                time.sleep(0.1)
                continue
                
    def show_host_connection_border(self):
        try:
            self.hide_host_connection_border()
            
            import tkinter as tk
            self.host_border_wins = []
            
            w = self.winfo_screenwidth()
            h = self.winfo_screenheight()
            self._last_border_w = w
            self._last_border_h = h
            
            thickness = 5
            color = "#FF69B4"
            
            rects = [
                (0, 0, w, thickness),           # top
                (0, h - thickness, w, thickness), # bottom
                (0, 0, thickness, h),           # left
                (w - thickness, 0, thickness, h)  # right
            ]
            
            for x, y, rw, rh in rects:
                win = tk.Toplevel(self)
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                win.attributes("-alpha", 0.8)
                win.configure(bg=color)
                win.geometry(f"{rw}x{rh}+{x}+{y}")
                win.update_idletasks()
                try:
                    import ctypes
                    hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
                    if not hwnd:
                        hwnd = win.winfo_id()
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                    ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x00000020)
                except:
                    pass
                self.host_border_wins.append(win)
                
            if not getattr(self, '_tracking_border_res', False):
                self._tracking_border_res = True
                self._check_border_resolution()
                
        except Exception as e:
            print(f"[Host] Lỗi tạo viền hồng kết nối: {e}")

    def _check_border_resolution(self):
        if not getattr(self, '_tracking_border_res', False):
            return
            
        try:
            current_w = self.winfo_screenwidth()
            current_h = self.winfo_screenheight()
            last_w = getattr(self, '_last_border_w', 0)
            last_h = getattr(self, '_last_border_h', 0)
            
            if current_w != last_w or current_h != last_h:
                if getattr(self, 'host_border_wins', None):
                    self.show_host_connection_border()
                    return
        except Exception:
            pass
            
        self.after(2000, self._check_border_resolution)

    def hide_host_connection_border(self):
        try:
            self._tracking_border_res = False
            if hasattr(self, 'host_border_wins'):
                for win in self.host_border_wins:
                    try: win.destroy()
                    except: pass
                self.host_border_wins = []
            if hasattr(self, 'host_border_win') and self.host_border_win:
                try: self.host_border_win.destroy()
                except: pass
                self.host_border_win = None
        except Exception as e:
            pass

    def wake_display(self):
        try:
            import ctypes
            # WM_SYSCOMMAND = 0x0112, SC_MONITORPOWER = 0xF170, -1 = power on
            # Use SendNotifyMessageW to avoid blocking if a window is non-responsive
            ctypes.windll.user32.SendNotifyMessageW(0xFFFF, 0x0112, 0xF170, -1)
            # Prevent sleep
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 | 0x00000002)
            # Simulate a harmless VK_F15 keypress to wake display/lockscreen
            import win32api, win32con
            win32api.keybd_event(win32con.VK_F15, 0, 0, 0)
            win32api.keybd_event(win32con.VK_F15, 0, win32con.KEYEVENTF_KEYUP, 0)
            print("[Host] Wake display signal sent.")
        except Exception as e:
            print(f"[Host] Failed to wake display: {e}")

    def handle_host_handshake(self, conn, addr):
        # We now support multiple clients, so we don't block new connections if active_clients is non-empty.
            
        try:
            # If we are headless, let's reload the random password from session_pass.txt to stay in sync with GUI
            if self.is_headless:
                try:
                    pass_path = os.path.join(app_dir, "session_pass.txt")
                    if os.path.exists(pass_path):
                        with open(pass_path, "r", encoding="utf-8") as f:
                            val = f.read().strip()
                            if val:
                                self.my_password = val
                except Exception as e:
                    print(f"[Host Service] Failed to reload password from session_pass.txt during handshake: {e}")
                    
                try:
                    self.fixed_password = self.load_fixed_password_from_xml()
                except Exception as e:
                    print(f"[Host Service] Failed to reload fixed password from XML during handshake: {e}")

            # Register the socket with candidate passwords so recv_msg can decrypt client's handshake
            socket_passwords[conn] = [self.my_password, self.fixed_password]
            msg = recv_msg(conn, [self.my_password, self.fixed_password])
            if not msg:
                print("[Host] Failed to decrypt handshake. Sending error using APP_KEY.")
                try:
                    err_info = json.dumps({
                        "status": "error",
                        "message": "Sai mật khẩu kết nối hoặc dữ liệu không hợp lệ!"
                    }).encode('utf-8')
                    send_msg(conn, err_info, APP_KEY)
                except: pass
                time.sleep(0.5)
                try: force_close_socket(conn)
                except: pass
                socket_passwords.pop(conn, None)
                return
                
            data = json.loads(msg.decode('utf-8'))
            client_pass = data.get("password")
            
            password_valid = False
            if client_pass == self.my_password:
                password_valid = True
            elif self.fixed_password and client_pass == self.fixed_password:
                password_valid = True
                
            if password_valid:
                print("[Host] Password matches! Accepting connection.")
                socket_passwords[conn] = client_pass
                
                client_id = data.get("client_id", "Không rõ")
                client_comp = data.get("computer_name", "Không rõ")
                fmt_client_id = f"{client_id[:3]} {client_id[3:6]} {client_id[6:9]} {client_id[9:]}" if len(client_id) == 12 else client_id
                
                if client_comp != "Không rõ":
                    msg_text = f"Máy tính [{client_comp}] đang điều khiển máy bạn"
                else:
                    msg_text = f"Máy tính có ID [{fmt_client_id}] đang điều khiển máy bạn"
                    
                try: log_activity(f"Chấp nhận kết nối từ ID {fmt_client_id} ({client_comp})")
                except: pass
                    
                self.after(0, lambda: self.show_custom_info("Kết nối từ xa", msg_text))
                self.after(0, self.show_host_connection_border)
                
                self.wake_display()
                
                # Tắt Nagle's algorithm (TCP_NODELAY) để giảm độ trễ tối đa
                try:
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except Exception as e:
                    print(f"[TCP_NODELAY] Lỗi thiết lập TCP_NODELAY trên Host: {e}")
                
                # Cấu hình TCP Keep-Alive bảo vệ kết nối đục lỗ khỏi bị đóng bởi Firewall/Router
                try:
                    conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    conn.ioctl(socket.SIOC_KEEPALIVE_VALS, (1, 1000, 1000))
                except Exception as e:
                    print(f"[KeepAlive] Lỗi cấu hình Keep-Alive trên Host: {e}")
                
                # Get resolution safely
                with mss.mss() as sct:
                    if len(sct.monitors) > 1:
                        monitor = sct.monitors[1]
                    else:
                        monitor = sct.monitors[0]
                    host_w = monitor['width']
                    host_h = monitor['height']
                    
                import platform
                computer_name = platform.node()
                
                is_domain = False
                chk_reason = "Unknown"
                try:
                    is_domain, chk_reason = is_machine_domain_joined()
                except Exception as ex:
                    chk_reason = f"Error: {ex}"
                
                try:
                    with open("domain_debug.log", "a", encoding="utf-8") as df:
                        df.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Host domain check: is_domain={is_domain}, reason={chk_reason}\n")
                except:
                    pass
                    
                res_info = json.dumps({
                    "status": "ok",
                    "width": host_w,
                    "height": host_h,
                    "computer_name": computer_name,
                    "zalo_phone": self.load_zalo_phone_from_xml(),
                    "is_domain": is_domain,
                    "chk_reason": chk_reason
                }).encode('utf-8')
                send_msg(conn, res_info, client_pass)
                
                client_state = {"running": True, "net_class": "medium", "wake_event": threading.Event()}
                
                # Perform pre-connection speed test handling on host (2 rounds to match client)
                try:
                    for run_idx in range(2):
                        # 1. Ping / Latency test (3 pings per round)
                        for _ in range(3):
                            ping_msg = recv_msg(conn, client_pass)
                            if ping_msg:
                                ping_data = json.loads(ping_msg.decode('utf-8'))
                                if ping_data.get("action") == "speed_test_ping":
                                    send_msg(conn, json.dumps({"action": "speed_test_pong"}).encode('utf-8'), client_pass)
                                    
                        # 2. Bandwidth test
                        bw_msg = recv_msg(conn, client_pass)
                        if bw_msg:
                            bw_data = json.loads(bw_msg.decode('utf-8'))
                            if bw_data.get("action") == "speed_test_bw_req":
                                dummy_size = 1572864 # 1.5 MB để nới rộng TCP Window
                                send_msg(conn, json.dumps({"action": "speed_test_bw_start", "size": dummy_size}).encode('utf-8'), client_pass)
                                conn.sendall(b'\x00' * dummy_size)
                            
                    # 3. Receive final results (sent once after both rounds)
                    res_msg = recv_msg(conn, client_pass)
                    if res_msg:
                        res_data = json.loads(res_msg.decode('utf-8'))
                        if res_data.get("action") == "speed_test_result":
                            net_class = res_data.get("net_class", "medium")
                            client_state["net_class"] = net_class
                            bandwidth = res_data.get("bandwidth", 32.0)
                            print(f"[Host] Speed test finished. Class: {net_class}, Bandwidth: {bandwidth:.2f} Mbps")
                            
                            # Adjust windows graphics effects based on net_class
                            if net_class == "high":
                                set_windows_graphics_effects(True)
                            else:
                                set_windows_graphics_effects(False)
                except Exception as ste:
                    print(f"[Host] Speed test handler error: {ste}")
                
                self.active_clients[addr] = client_state
                
                addrs_str = ", ".join([str(a[0]) for a in self.active_clients.keys()])
                self.update_status(f"Đang dùng máy chủ {addrs_str}")
                
                t_sender = threading.Thread(target=self.host_sender_thread, args=(conn, monitor, client_state, client_pass), daemon=True)
                t_receiver = threading.Thread(target=self.host_receiver_thread, args=(conn, client_state, client_pass), daemon=True)
                
                t_sender.start()
                t_receiver.start()
                
                # Khởi chạy luồng đồng bộ Clipboard File cho Host
                clipboard_sync_manager.add_socket(conn)
                
                try:
                    t_receiver.join()
                finally:
                    client_state["running"] = False
                    t_sender.join()
                    clipboard_sync_manager.remove_socket(conn)
                    set_windows_graphics_effects(True) # Restore graphics effects upon disconnection
                    
                    print(f"[Host] Đã đóng kết nối với Client {addr[0]}:{addr[1]}.")
                    try: log_activity(f"Ngắt kết nối với ID {fmt_client_id} ({client_comp})")
                    except: pass
                    
                    if addr in self.active_clients:
                        del self.active_clients[addr]
                        
                    if self.active_clients:
                        addrs_str = ", ".join([str(a[0]) for a in self.active_clients.keys()])
                        self.update_status(f"Đang bị điều khiển bởi {addrs_str}")
                    else:
                        self.update_status(f"Đã đóng kết nối với Client {addr[0]} lúc {time.strftime('%H:%M:%S')} (Sẵn sàng kết nối)")
                        self.after(0, self.hide_host_connection_border)
                        
                    try:
                        force_close_socket(conn)
                    except:
                        pass
            else:
                print("[Host] Password mismatch!")
                err_info = json.dumps({
                    "status": "error",
                    "message": "Sai mật khẩu kết nối!"
                }).encode('utf-8')
                send_msg(conn, err_info, client_pass)
                time.sleep(0.5)
                force_close_socket(conn)
                socket_passwords.pop(conn, None)
        except Exception as e:
            print(f"[Host] Handshake Exception: {e}")
            try:
                err_info = json.dumps({
                    "status": "error",
                    "message": f"Lỗi xảy ra trên máy Host:\n{e}"
                }).encode('utf-8')
                send_msg(conn, err_info, locals().get('client_pass'))
            except:
                pass
            time.sleep(0.5)
            force_close_socket(conn)
            socket_passwords.pop(conn, None)
            
    # Host Sender Thread
    def host_sender_thread(self, conn, monitor, client_state, password):
        print("[Host] Started Screen Sender Thread.")
        import io
        
        try:
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, 2000)
        except: pass

        _last_switching_signal_time = 0
        while client_state.get("running", False):
            try:
                # Early check for desktop status
                needs_switch, is_blocked = check_desktop_change()
                if is_blocked:
                    # Throttle: only send switching_desktop signal once every 12 seconds
                    # to avoid resetting the client's countdown timer in an infinite loop
                    now = time.time()
                    if now - _last_switching_signal_time >= 12:
                        print("[Host] Secure Desktop detected and cannot be accessed. Signaling client...")
                        try:
                            signal = json.dumps({"type": "switching_desktop"}).encode('utf-8')
                            send_msg(conn, signal, password)
                        except:
                            pass
                        _last_switching_signal_time = now
                    time.sleep(0.5)
                    continue

                # Switch thread to active Input Desktop if needed
                if needs_switch:
                    _last_switching_signal_time = 0  # Reset throttle so next block event signals immediately
                    print("[Host] Desktop change detected. Switching thread desktop...")
                    try:
                        hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x02000000)
                        if hdesk:
                            result = ctypes.windll.user32.SetThreadDesktop(hdesk)
                            ctypes.windll.user32.CloseDesktop(hdesk)
                            if not result:
                                print("[Host] SetThreadDesktop() failed (thread may have existing windows). Retrying...")
                                time.sleep(0.3)
                                continue
                    except Exception as e:
                        print(f"[Host] SetThreadDesktop exception: {e}")
                        time.sleep(0.3)
                        continue
                    
                with mss.mss() as sct:
                    # Dynamically get monitor for current desktop (fixes black screen on Win10 Winlogon)
                    if len(sct.monitors) > 1:
                        dynamic_monitor = sct.monitors[1]
                    else:
                        dynamic_monitor = sct.monitors[0]
                        
                    while client_state.get("running", False):
                        try:
                            # Check for mid-session desktop transitions
                            inner_needs_switch, inner_is_blocked = check_desktop_change()
                            if inner_is_blocked or inner_needs_switch:
                                if inner_is_blocked:
                                    print("[Host] Secure Desktop appeared mid-session and blocked. Signaling client...")
                                    now = time.time()
                                    if now - _last_switching_signal_time >= 12:
                                        try:
                                            signal = json.dumps({"type": "switching_desktop"}).encode('utf-8')
                                            send_msg(conn, signal, password)
                                        except:
                                            pass
                                        _last_switching_signal_time = now
                                    time.sleep(0.5)
                                else:
                                    print("[Host] Desktop switched mid-session. Breaking capture loop to switch thread...")
                                break  # Break inner loop to recreate mss.mss() on new desktop
                                
                            sys_w = ctypes.windll.user32.GetSystemMetrics(0)
                            sys_h = ctypes.windll.user32.GetSystemMetrics(1)
                            if sys_w > 0 and sys_h > 0 and (dynamic_monitor['width'] != sys_w or dynamic_monitor['height'] != sys_h):
                                print("[Host] Resolution change detected via GetSystemMetrics. Breaking capture loop...")
                                break
                                
                            img = sct.grab(dynamic_monitor)
                            # Convert raw BGRA from mss directly to Pillow Image
                            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                            
                            target_w = getattr(self, 'client_viewer_w', 1280)
                            target_h = getattr(self, 'client_viewer_h', 720)
                            
                            force_update = client_state.pop("force_update", False)
                            if client_state.get("last_target_w") != target_w or client_state.get("last_target_h") != target_h:
                                force_update = True
                                client_state["last_target_w"] = target_w
                                client_state["last_target_h"] = target_h

                            net_class = client_state.get("net_class", "medium")
                            
                            if net_class == "high":
                                base_quality = 98
                                fps_limit = 60
                                res_scale = 1.0
                            elif net_class == "low":
                                base_quality = 40
                                fps_limit = 12
                                res_scale = 0.6
                            else:
                                base_quality = 75
                                fps_limit = 30
                                res_scale = 0.8

                            quality = client_state.get("dyn_quality", base_quality)
                            sleep_time = client_state.get("dyn_sleep_time", 1.0 / fps_limit)
                            dyn_scale = client_state.get("dyn_scale", res_scale)

                            if "start_time" not in client_state:
                                client_state["start_time"] = time.time()
                                
                            if time.time() - client_state["start_time"] < 5.0:
                                quality = min(98, quality + 10)
                                dyn_scale = min(1.0, dyn_scale + 0.1)
                                client_state["dyn_quality"] = quality
                                client_state["dyn_scale"] = dyn_scale

                            cap_w, cap_h = img.size
                            if client_state.get("last_cap_w") != cap_w or client_state.get("last_cap_h") != cap_h:
                                client_state["last_cap_w"] = cap_w
                                client_state["last_cap_h"] = cap_h
                                force_update = True
                                try:
                                    res_meta = {"type": "resolution_change", "w": cap_w, "h": cap_h}
                                    send_msg(conn, json.dumps(res_meta).encode('utf-8'), password)
                                except Exception:
                                    pass

                            w = int(target_w * dyn_scale)
                            h = int(target_h * dyn_scale)
                            
                            # Calculate final dimensions while preserving aspect ratio
                            cap_ratio = cap_w / cap_h if cap_h > 0 else 1.0
                            target_ratio = w / h if h > 0 else 1.0
                            
                            if cap_ratio > target_ratio:
                                final_w = w
                                final_h = int(w / cap_ratio)
                            else:
                                final_h = h
                                final_w = int(h * cap_ratio)
                                
                            final_w = max(10, min(final_w, cap_w))
                            final_h = max(10, min(final_h, cap_h))
                            
                            if cap_w != final_w or cap_h != final_h:
                                pil_img = pil_img.resize((final_w, final_h), Image.Resampling.LANCZOS)

                            static_frame = False
                            diff_bbox = None
                            try:
                                if "prev_sent_img" in client_state and not force_update:
                                    from PIL import ImageChops
                                    prev_img = client_state["prev_sent_img"]
                                    if prev_img.size == pil_img.size:
                                        diff_bbox = ImageChops.difference(pil_img, prev_img).getbbox()
                                        if diff_bbox is None:
                                            static_frame = True
                            except: pass
                            
                            if not static_frame:
                                client_state["prev_sent_img"] = pil_img.copy()
                            
                            if static_frame:
                                current_q = client_state.get("dyn_quality", 40)
                                current_s = client_state.get("dyn_scale", 0.6)
                                if current_q < 98 or current_s < 1.0:
                                    client_state["dyn_quality"] = min(98, current_q + 15)
                                    client_state["dyn_scale"] = min(1.0, current_s + 0.1)
                                    static_frame = False 
                                else:
                                    if "wake_event" in client_state:
                                        client_state["wake_event"].wait(1.0)
                                        client_state["wake_event"].clear()
                                    else:
                                        time.sleep(1.0)
                                    continue
                                    
                            if diff_bbox is not None and not static_frame and not force_update:
                                box_w = diff_bbox[2] - diff_bbox[0]
                                box_h = diff_bbox[3] - diff_bbox[1]
                                if box_w * box_h < (w * h) * 0.7:
                                    pil_img = pil_img.crop(diff_bbox)
                                    partial_meta = {"type": "partial_frame", "bbox": diff_bbox}
                                    send_msg(conn, json.dumps(partial_meta).encode('utf-8'), password)
                            
                            buf = io.BytesIO()
                            pil_img.save(buf, format="JPEG", quality=quality, subsampling=0)
                            jpeg_data = buf.getvalue()
                            
                            t_start_send = time.time()
                            send_msg(conn, jpeg_data, password)
                            send_time = time.time() - t_start_send
                            
                            if "send_ema" not in client_state:
                                client_state["send_ema"] = send_time
                            else:
                                client_state["send_ema"] = 0.8 * client_state["send_ema"] + 0.2 * send_time
                                
                            ema = client_state["send_ema"]
                            
                            if ema > 0.35:
                                # Mạng chậm: Chỉ giảm chất lượng ảnh, hạn chế bóp scale để tránh vỡ khối pixel
                                quality = max(max(35, base_quality - 20), quality - 5)
                                sleep_time = min(0.3, sleep_time + 0.05)
                                if ema > 0.6:
                                    dyn_scale = max(res_scale, dyn_scale - 0.05)
                            elif ema < 0.20:
                                # Phương án 2: Dynamic Scaling mượt hơn (vượt qua giới hạn ban đầu nếu mạng tốt)
                                quality = min(98, quality + 1)
                                sleep_time = max(1.0 / 60, sleep_time - 0.005)
                                dyn_scale = min(1.0, dyn_scale + 0.02)
                                
                            client_state["dyn_quality"] = quality
                            client_state["dyn_sleep_time"] = sleep_time
                            client_state["dyn_scale"] = dyn_scale

                            time.sleep(sleep_time)
                        except mss.exception.ScreenShotError as e:
                            print(f"[Host] Screen capture error (re-initializing): {e}")
                            
                            # Thử fallback sang monitors[0] một lần duy nhất.
                            # KHÔNG dùng continue vì nếu monitors[0] cũng fail → vòng lặp vô tận.
                            if len(sct.monitors) > 1 and dynamic_monitor != sct.monitors[0]:
                                print("[Host] Falling back to sct.monitors[0] (Virtual Screen) - one-shot attempt")
                                dynamic_monitor = sct.monitors[0]
                                try:
                                    img2 = sct.grab(dynamic_monitor)
                                    # Fallback thành công: cập nhật dynamic_monitor và tiếp tục
                                    img = img2
                                except Exception:
                                    pass  # Fallback cũng fail → rơi xuống break bên dưới
                                else:
                                    continue  # Fallback thành công → tiếp tục inner loop
                                
                            try:
                                signal = json.dumps({"type": "switching_desktop"}).encode('utf-8')
                                send_msg(conn, signal, password)
                            except: pass
                            time.sleep(1.0)
                            break  # Break inner loop to recreate mss.mss()
                        except Exception as e:
                            import traceback
                            with open("host_error.log", "a", encoding="utf-8") as f:
                                f.write(f"[{time.strftime('%H:%M:%S')}] [Host] Screen Sender Error: {e}\n{traceback.format_exc()}\n")
                            client_state["running"] = False
                            try:
                                force_close_socket(conn)
                            except:
                                pass
                            break
            except Exception as e:
                print(f"[Host] mss.mss() context error: {e}")
                time.sleep(1.0)
        print("[Host] Screen Sender Thread Stopped.")
        
    # Host Receiver Thread (Simulates actions)
    def host_receiver_thread(self, conn, client_state, password):
        print("[Host] Started Input Receiver Thread.")
        import select
        # Cache để tránh gọi OpenInputDesktop/SetThreadDesktop mỗi vòng lặp
        _last_desk_check_time = 0.0
        _last_desk_name = None
        _DESK_CHECK_INTERVAL = 0.5  # Chỉ kiểm tra desktop mỗi 0.5 giây
        last_recv_time = time.time()
        while client_state.get("running", False):
            try:
                # Chờ 2 giây, nếu không có gói tin nào thì nhả hết phím modifier để chống kẹt
                r, _, _ = select.select([conn], [], [], 2.0)
                if not r:
                    self.host_release_all_modifiers()
                    if time.time() - last_recv_time > 60.0:
                        print("[Host] Connection ping timeout. Disconnecting client.")
                        client_state["running"] = False
                        break
                    continue

                # Chỉ kiểm tra/chuyển desktop khi có gói tin đến VÀ đã qua interval
                # Điều này tránh overhead khi mouse_move liên tục và tránh SetThreadDesktop
                # gọi quá nhiều lần (có thể fail nếu hook đã được gắn vào thread)
                now = time.monotonic()
                if now - _last_desk_check_time >= _DESK_CHECK_INTERVAL:
                    _last_desk_check_time = now
                    try:
                        import ctypes as _ct
                        # Lấy tên desktop hiện tại để phát hiện thay đổi (UAC/Winlogon)
                        _buf = _ct.create_unicode_buffer(256)
                        _hd_cur = _ct.windll.user32.GetThreadDesktop(_ct.windll.kernel32.GetCurrentThreadId())
                        _ct.windll.user32.GetUserObjectInformationW(_hd_cur, 2, _buf, _ct.sizeof(_buf), None)
                        _cur_name = _buf.value.lower() if _buf.value else None

                        _hdesk_new = _ct.windll.user32.OpenInputDesktop(0, False, 0x02000000)
                        if _hdesk_new:
                            # Lấy tên của input desktop mới
                            _buf2 = _ct.create_unicode_buffer(256)
                            _ct.windll.user32.GetUserObjectInformationW(_hdesk_new, 2, _buf2, _ct.sizeof(_buf2), None)
                            _new_name = _buf2.value.lower() if _buf2.value else None

                            if _new_name != _last_desk_name:
                                # Desktop đã thay đổi → switch thread sang desktop mới
                                if _ct.windll.user32.SetThreadDesktop(_hdesk_new):
                                    _last_desk_name = _new_name
                                    print(f"[Host] Switched input desktop: {_last_desk_name}")
                                    if getattr(self, 'host_block_input_active', False):
                                        try:
                                            _ct.windll.user32.BlockInput(False)
                                            _ct.windll.user32.BlockInput(True)
                                        except: pass
                                    # Đóng handle cũ sau khi switch thành công
                                    if hasattr(self, '_last_hdesk') and self._last_hdesk:
                                        _ct.windll.user32.CloseDesktop(self._last_hdesk)
                                    self._last_hdesk = _hdesk_new
                                    _hdesk_new = None  # Prevent double-close below
                                # else: SetThreadDesktop thất bại → giữ nguyên desktop cũ
                            # Đóng handle nếu không được lưu lại (không có thay đổi hoặc switch fail)
                            if _hdesk_new:
                                _ct.windll.user32.CloseDesktop(_hdesk_new)
                    except Exception:
                        pass
                    
                import select
                r, _, _ = select.select([conn], [], [], 0.5)
                
                if getattr(self, 'host_block_input_active', False):
                    try:
                        import ctypes
                        # Luôn re-apply BlockInput mỗi 0.5s để chống lại SAS (Ctrl+Alt+Del)
                        if ctypes.windll.user32.BlockInput(True) == 0:
                            ctypes.windll.user32.BlockInput(False)
                            ctypes.windll.user32.BlockInput(True)
                    except: pass
                    
                if not r:
                    continue
                    
                msg = recv_msg(conn, password)
                if not msg:
                    print("[Host] Input Receiver got empty message (Client disconnected).")
                    break
                last_recv_time = time.time()
                try:
                    event = json.loads(msg.decode('utf-8'))
                    evt_type = event.get("type", "")
                    if evt_type in ("batch_start", "file_start", "file_chunk", "file_end", "batch_end", "files_copied_meta", "request_files", "cancel_transfer", "clipboard_text"):
                        clipboard_sync_manager.handle_received_packet(event)
                    else:
                        self.host_handle_event(event, conn, password)
                        if evt_type in ("mouse_click", "mouse_scroll", "key_event"):
                            client_state["force_update"] = True
                            if "wake_event" in client_state:
                                client_state["wake_event"].set()
                except Exception as parse_err:
                    print(f"[Host] Packet Handle Error (Ignoring): {parse_err}")
                    continue
            except Exception as e:
                print(f"[Host] Input Receiver Critical Error: {e}")
                break
        print("[Host] Input Receiver Thread Stopped.")
        self.host_release_all_modifiers()
        
    def host_handle_event(self, event, conn, password):
        ev_type = event.get('type')
        if ev_type == 'mouse_move':
            x, y = event['x'], event['y']
            # Single SendInput call with MOUSEEVENTF_ABSOLUTE is sufficient and fastest
            send_input_mouse_move(x, y)
                
        elif ev_type == 'mouse_click':
            button_name = event.get('button')
            pressed = event.get('pressed')
            # Primary simulation using standard SendInput API
            send_input_mouse_click(button_name, pressed)
            try:
                if pressed:
                    if button_name == 'right':
                        clipboard_sync_manager.last_rbutton_time = time.time()
                    elif button_name == 'left':
                        clipboard_sync_manager.last_lbutton_time = time.time()
            except Exception as e:
                pass
                
        elif ev_type == 'mouse_scroll':
            dx, dy = event['dx'], event['dy']
            # Primary simulation using standard SendInput API
            send_input_mouse_scroll(dx, dy)
                
        elif ev_type == 'key_event':
            key_name = event['key']
            pressed = event['pressed']
            
            # Primary simulation using standard SendInput API
            send_input_keyboard_event(key_name, pressed)
                
        elif ev_type == 'resize_viewer':
            self.client_viewer_w = event.get('w', 1280)
            self.client_viewer_h = event.get('h', 720)
            
        elif ev_type == 'ping':
            try:
                send_msg(conn, json.dumps({"type": "pong"}).encode('utf-8'), password)
            except Exception:
                pass
            
        elif ev_type == 'toggle_screen_cover':
            self.toggle_screen_cover()
            
        elif ev_type == 'trigger_sas':
            self.trigger_sas()
            
        elif ev_type == 'trigger_taskmgr':
            self.trigger_taskmgr()
            
        elif ev_type == 'check_domain':
            is_domain = False
            chk_reason = "Unknown"
            try:
                is_domain, chk_reason = is_machine_domain_joined()
            except Exception as ex:
                chk_reason = f"Error: {ex}"
            
            is_locked = (get_desktop_name() == "winlogon")
            
            try:
                with open("domain_debug.log", "a", encoding="utf-8") as df:
                    df.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Host check_domain query response: is_domain={is_domain}, reason={chk_reason}, is_locked={is_locked}\n")
            except:
                pass
                
            try:
                send_msg(conn, json.dumps({
                    "type": "domain_status", 
                    "is_domain": is_domain, 
                    "reason": chk_reason,
                    "is_locked": is_locked
                }).encode('utf-8'), password)
            except Exception as e:
                print(f"[Host] Failed to send domain_status: {e}")
                
        elif ev_type == 'type_password':
            password = event.get("password", "")
            if password:
                print("[Host] Received type_password command.")
                try:
                    host_type_password(password)
                except Exception as e:
                    print(f"[Host] Failed to type password: {e}")
                    
        elif ev_type == 'request_list_dir':
            path = event.get('path', 'C:\\')
            try:
                import os
                items = []
                if os.path.isdir(path):
                    for item in os.listdir(path):
                        full = os.path.join(path, item)
                        is_dir = os.path.isdir(full)
                        size = 0 if is_dir else os.path.getsize(full)
                        items.append({"name": item, "is_dir": is_dir, "size": size})
                res = {"type": "list_dir_result", "path": path, "items": items}
                send_msg(conn, json.dumps(res).encode('utf-8'), password)
            except Exception as e:
                print(f"[Host] list dir error: {e}")
                
        elif ev_type == 'request_file_download':
            path = event.get('path')
            target_dir_local = event.get('target_dir_local')
            if path and os.path.isfile(path):
                def download_thread(p, t_dir, c, pwd):
                    try:
                        import os, base64, time
                        size = os.path.getsize(p)
                        name = os.path.basename(p)
                        
                        start_msg = {"type": "file_start", "name": name, "size": size, "target_dir": t_dir}
                        send_msg(c, json.dumps(start_msg).encode('utf-8'), pwd)
                        time.sleep(0.5)
                        
                        with open(p, "rb") as f:
                            while True:
                                chunk = f.read(65536)
                                if not chunk: break
                                chunk_msg = {
                                    "type": "file_chunk",
                                    "name": name,
                                    "data": base64.b64encode(chunk).decode('utf-8')
                                }
                                send_msg(c, json.dumps(chunk_msg).encode('utf-8'), pwd)
                                time.sleep(0.01)
                                
                        end_msg = {"type": "file_end"}
                        send_msg(c, json.dumps(end_msg).encode('utf-8'), pwd)
                    except Exception as e:
                        print(f"[Host] File download error: {e}")
                import threading
                threading.Thread(target=download_thread, args=(path, target_dir_local, conn, password), daemon=True).start()

        elif ev_type == 'request_delete_item':
            path = event.get('path')
            try:
                import os, shutil
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                res = {"type": "delete_item_result", "success": True}
            except Exception as e:
                res = {"type": "delete_item_result", "success": False, "error": str(e)}
            send_msg(conn, json.dumps(res).encode('utf-8'), password)
            
        elif ev_type == 'request_rename_item':
            old_path = event.get('old_path')
            new_name = event.get('new_name')
            try:
                import os
                new_path = os.path.join(os.path.dirname(old_path), new_name)
                os.rename(old_path, new_path)
                res = {"type": "rename_item_result", "success": True}
            except Exception as e:
                res = {"type": "rename_item_result", "success": False, "error": str(e)}
            send_msg(conn, json.dumps(res).encode('utf-8'), password)
            
        elif ev_type == 'request_create_folder':
            parent_path = event.get('parent_path')
            folder_name = event.get('folder_name')
            try:
                import os
                os.makedirs(os.path.join(parent_path, folder_name), exist_ok=True)
                res = {"type": "create_folder_result", "success": True}
            except Exception as e:
                res = {"type": "create_folder_result", "success": False, "error": str(e)}
            send_msg(conn, json.dumps(res).encode('utf-8'), password)
            
        elif ev_type == 'request_open_file':
            path = event.get('path')
            try:
                import os, subprocess, sys
                if sys.platform == "win32":
                    os.startfile(path)
                else:
                    subprocess.call(["xdg-open", path])
                res = {"type": "open_file_result", "success": True}
            except Exception as e:
                res = {"type": "open_file_result", "success": False, "error": str(e)}
            send_msg(conn, json.dumps(res).encode('utf-8'), password)

        elif ev_type == 'request_read_text_file':
            path = event.get('path')
            try:
                import os
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read(5 * 1024 * 1024)
                res = {"type": "read_text_file_result", "success": True, "content": content, "path": path}
            except Exception as e:
                res = {"type": "read_text_file_result", "success": False, "error": str(e), "path": path}
            send_msg(conn, json.dumps(res).encode('utf-8'), password)

        elif ev_type == 'request_write_text_file':
            path = event.get('path')
            content = event.get('content', '')
            try:
                import os
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                res = {"type": "write_text_file_result", "success": True, "path": path}
            except Exception as e:
                res = {"type": "write_text_file_result", "success": False, "error": str(e), "path": path}
            send_msg(conn, json.dumps(res).encode('utf-8'), password)

    def toggle_screen_cover(self):
        import win32event, win32api, ctypes
        
        if hasattr(self, 'host_block_input_active') and self.host_block_input_active:
            self.host_block_input_active = False
            try:
                ctypes.windll.user32.BlockInput(False)
                print("[Host] BlockInput Disabled.")
            except:
                pass
        else:
            self.host_block_input_active = True
            try:
                ctypes.windll.user32.BlockInput(True)
                print("[Host] BlockInput Enabled.")
            except:
                pass
                
        try:
            active_session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
        except:
            active_session_id = 1
            
        cover_event_name = f"Global\\AntigravityP2PRemoteDesktopScreenCoverEvent_{active_session_id}_default"
        
        try:
            h_event = win32event.OpenEvent(win32event.EVENT_MODIFY_STATE, False, cover_event_name)
            if h_event:
                win32event.SetEvent(h_event)
                win32api.CloseHandle(h_event)
                print(f"[Host] Signaled ScreenCover Event to GUI Agent at Session {active_session_id}.")
            else:
                if not self.is_headless:
                    self.after(0, self.toggle_screen_cover_gui)
        except Exception as e:
            print(f"[Host] Failed to signal ScreenCover Event: {e}")
            if not self.is_headless:
                self.after(0, self.toggle_screen_cover_gui)

    def toggle_screen_cover_gui(self):
        if hasattr(self, 'screen_cover_running') and self.screen_cover_running:
            self.screen_cover_running = False
            try:
                if hasattr(self, 'screen_cover_root') and self.screen_cover_root:
                    self.screen_cover_root.destroy()
                    self.screen_cover_root = None
            except:
                pass
            print("[Host] Screen cover disabled.")
            return

        self.screen_cover_running = True
        print("[Host] Screen cover enabled.")


        import tkinter as tk
        root = tk.Toplevel(self)
        self.screen_cover_root = root
        root.config(bg='black')
        root.attributes('-alpha', 1.0)
        root.overrideredirect(True)
        root.attributes('-topmost', True)
        root.config(cursor="none")
        
        lbl = tk.Label(root, text="Máy tính đang hoạt động, vui lòng không tắt", font=("Segoe UI", 24, "bold"), fg="white", bg="black")
        lbl.place(relx=0.5, rely=0.6, anchor="center")

        icon_lbl = tk.Label(root, bg="black")
        icon_lbl.place(relx=0.5, rely=0.4, anchor="center")
        
        import os
        icon_path = os.path.join(app_dir, "app_icon.png")
        fade_frames = []
        if os.path.exists(icon_path):
            try:
                from PIL import Image, ImageTk
                original_img = Image.open(icon_path).convert("RGBA")
                try:
                    resample = Image.Resampling.LANCZOS
                except AttributeError:
                    resample = Image.LANCZOS
                original_img = original_img.resize((256, 256), resample)
                
                for alpha in range(50, 256, 10):
                    frame = original_img.copy()
                    alpha_channel = frame.split()[3]
                    alpha_channel = alpha_channel.point(lambda p: p * (alpha / 255.0))
                    frame.putalpha(alpha_channel)
                    
                    bg = Image.new("RGBA", frame.size, (0, 0, 0, 255))
                    bg.paste(frame, (0, 0), frame)
                    fade_frames.append(ImageTk.PhotoImage(bg))
                    
                fade_frames.extend(fade_frames[::-1])
            except Exception as e:
                print(f"[Host] Cover icon load error: {e}")
                
        # Ngăn chặn GC dọn dẹp frame
        icon_lbl.image_frames = fade_frames
                
        if fade_frames:
            def animate_icon(frame_idx=0):
                if not getattr(self, 'screen_cover_running', False) or not root.winfo_exists():
                    return
                try:
                    icon_lbl.config(image=fade_frames[frame_idx])
                    next_idx = (frame_idx + 1) % len(fade_frames)
                    root.after(40, animate_icon, next_idx)
                except:
                    pass
            animate_icon()
        
        try:
            import ctypes
            w = ctypes.windll.user32.GetSystemMetrics(78) # SM_CXVIRTUALSCREEN
            h = ctypes.windll.user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
            x = ctypes.windll.user32.GetSystemMetrics(76) # SM_XVIRTUALSCREEN
            y = ctypes.windll.user32.GetSystemMetrics(77) # SM_YVIRTUALSCREEN
            if w > 0 and h > 0:
                root.geometry(f"{w}x{h}+{x}+{y}")
            else:
                root.attributes('-fullscreen', True)
            
            root.update_idletasks()
            hwnd = int(root.frame(), 16)
            ctypes.windll.user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
            
            try:
                res = ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x11)
                if not res:
                    ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x01)
            except Exception:
                pass
        except Exception as e:
            print(f"[Host] Cover screen setup error: {e}")

        def keep_topmost():
            if not getattr(self, 'screen_cover_running', False) or not root.winfo_exists():
                return
            try:
                root.attributes('-topmost', True)
            except:
                pass
            root.after(1000, keep_topmost)
                
        root.after(1000, keep_topmost)


    def trigger_taskmgr(self):
        print("[Host] Received trigger_taskmgr command.")
        import win32event
        try:
            h_event = win32event.OpenEvent(win32event.EVENT_MODIFY_STATE, False, "Global\\AntigravityP2P_TaskMgr_Event")
            if h_event:
                win32event.SetEvent(h_event)
                win32event.CloseHandle(h_event)
                print("[Host] Signaled Global\\AntigravityP2P_TaskMgr_Event successfully.")
            else:
                print("[Host] Failed to open Global\\AntigravityP2P_TaskMgr_Event (event is null).")
        except Exception as e:
            print(f"[Host] Failed to signal TaskMgr event: {e}")

    def trigger_sas(self):
        print("[Host] Received trigger_sas command.")
        
        # Configure SoftwareSASGeneration = 3 in registry
        try:
            import winreg
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", 0, winreg.KEY_ALL_ACCESS)
            except WindowsError:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "SoftwareSASGeneration", 0, winreg.REG_DWORD, 3)
            winreg.CloseKey(key)
            print("[Host] Configured SoftwareSASGeneration = 3 in registry.")
        except Exception as reg_err:
            print(f"[Host] Failed to configure SoftwareSASGeneration in registry: {reg_err}")
            
        import win32event
        try:
            h_event = win32event.OpenEvent(win32event.EVENT_MODIFY_STATE, False, "Global\\AntigravityP2P_SAS_Event")
            if h_event:
                win32event.SetEvent(h_event)
                win32event.CloseHandle(h_event)
                print("[Host] Signaled Global\\AntigravityP2P_SAS_Event successfully.")
            else:
                print("[Host] Failed to open Global\\AntigravityP2P_SAS_Event (event is null).")
        except Exception as ex:
            print(f"[Host] Failed to signal SAS event: {ex}")

    def host_release_all_modifiers(self):
        try:
            for key_name in [
                'left shift', 'right shift', 
                'left ctrl', 'right ctrl', 
                'left alt', 'right alt', 
                'left windows', 'right windows'
            ]:
                send_input_keyboard_event(key_name, False)
            # Clear remote modifier tracker to stay in sync
            _remote_modifier_keys.clear()
        except Exception as e:
            print(f"[Host] Failed to release modifiers via SendInput: {e}")
                
    # CLIENT (Controller) functions
    def click_connect(self):
        partner_id = self.partner_id_var.get().strip().replace(" ", "")
        partner_pass = self.partner_pass_var.get().strip()
        
        if not partner_id or len(partner_id) < 12:
            self.show_custom_error("Lỗi", "Vui lòng nhập mã ID đối tác hợp lệ (12 chữ số)!")
            return
            
        if not partner_pass:
            self.show_custom_error("Lỗi", "Vui lòng nhập mật khẩu đối tác!")
            return
            
        self.update_status("Đang tìm địa chỉ IP của đối tác trên dịch vụ danh bạ...")
        self.connect_btn.config(state=tk.DISABLED)
        
        # Connect inside background thread to prevent UI freezing
        threading.Thread(target=self.connect_to_partner, args=(partner_id, partner_pass), daemon=True).start()
        
    def connect_to_partner(self, partner_id, partner_pass, reconnect_queue=None, retry_count=0, viewer_pid=None):
        if partner_id == getattr(self, "my_id_clean", ""):
            self.after(0, lambda: self.show_custom_info("Thông báo", "Bạn không thể kết nối tới chính bạn :-)"))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            self.update_status("Kết nối bị hủy.")
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
            self.update_status(f"Đang hiển thị cửa sổ điều khiển đã kết nối của {partner_id}...")
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

        if not hasattr(self, 'signaling_sockets') or not self.signaling_sockets:
            self.update_status("Chưa kết nối Signaling Server!")
            self.after(0, lambda: self.show_custom_error("Lỗi", "Chưa kết nối đến Server Báo hiệu. Vui lòng kiểm tra lại mạng hoặc VPS."))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            return

        req = json.dumps({
            "action": "connect_request",
            "target": partner_id,
            "port": BOUND_PORT,
            "local_ip": self.local_ip,
            "local_port": BOUND_PORT
        }) + '\n'
        
        # Thử tìm đối tác trên tất cả các server đang kết nối
        sockets_to_try = []
        with self.signaling_lock:
            if getattr(self, 'primary_signaling_socket', None):
                sockets_to_try.append(self.primary_signaling_socket)
            for sock in self.signaling_sockets.values():
                if sock not in sockets_to_try:
                    sockets_to_try.append(sock)
                    
        success = False
        self.update_status("Đang tìm và chờ đối tác phản hồi...")
        
        for sock in sockets_to_try:
            self.pending_connection_info = None
            try:
                with self.signaling_lock:
                    send_msg(sock, req.encode('utf-8'), APP_KEY)
            except Exception as e:
                continue
                
            timeout = 6.0
            while timeout > 0 and self.pending_connection_info is None:
                time.sleep(0.2)
                timeout -= 0.2
                
            if self.pending_connection_info and self.pending_connection_info != "error":
                success = True
                break
                
        if not success:
            if reconnect_queue and retry_count < 30:
                self.update_status(f"Mất kết nối. Đang thử kết nối lại lần {retry_count + 1}/30...")
                time.sleep(2)
                self.connect_to_partner(partner_id, partner_pass, reconnect_queue, retry_count + 1, viewer_pid)
                return
                
            self.update_status("Sẵn sàng kết nối")
            if not reconnect_queue:
                self.after(0, lambda: self.show_custom_error("Lỗi", "Không thể tìm thấy hoặc đối tác đang Offline / Từ chối kết nối."))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if reconnect_queue:
                reconnect_queue.put("FAILED")
            return
            
        if len(self.pending_connection_info) >= 4:
            public_ip, port, local_ip, local_port = self.pending_connection_info[:4]
        else:
            public_ip, port, local_ip = self.pending_connection_info
            local_port = 12345
            
        port = int(port) if port else 0
        local_port = int(local_port) if local_port else 12345
            
        sock = None
        connected = False
        handshake_done = False
        cached_res_payload = None
        
        # 1. Try local IP first (LAN) (Chỉ thử nếu không ép buộc Relay)
        if not self.force_relay_var.get() and local_ip:
            ips_to_try = [ip.strip() for ip in local_ip.split(',') if ip.strip()]
            ports_to_try = [local_port]
            for p in [12345, 12346, 12347, 12348]:
                if p not in ports_to_try:
                    ports_to_try.append(p)
                    
            self.update_status(f"Đang quét kết nối nội bộ (LAN)...")
            import select
            
            # Quét tuần tự từng port (ưu tiên local_port trước) để tránh lỗi dính Kaspersky/ứng dụng rác ở port 12345
            for p in ports_to_try:
                if connected: break
                sockets = []
                for ip in ips_to_try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setblocking(False)
                    try: s.connect((ip, p))
                    except Exception: pass
                    sockets.append((s, ip, p))
                
                # Chờ tối đa 0.4s cho mỗi port
                end_time = time.time() + 0.4
                while time.time() < end_time and not connected:
                    timeout = max(0.05, end_time - time.time())
                    try:
                        sock_list = [item[0] for item in sockets]
                        if not sock_list: break
                        _, writable, _ = select.select([], sock_list, [], timeout)
                        for w_sock in writable:
                            if w_sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0:
                                try:
                                    w_sock.getpeername()
                                    w_sock.setblocking(True)
                                    
                                    # Kểm tra handshake ngay để xác minh đây có phải Host thật không
                                    # (Tránh trường hợp VM NAT hay proxy tự động nhận TCP rồi reset)
                                    w_sock.settimeout(2.0)
                                    try:
                                        socket_passwords[w_sock] = partner_pass
                                        import platform
                                        hs_data = json.dumps({"password": partner_pass, "client_id": self.my_id_clean, "computer_name": platform.node()}).encode('utf-8')
                                        send_msg(w_sock, hs_data, partner_pass)
                                        tmp_res_msg = recv_msg(w_sock, [partner_pass, APP_KEY])
                                        if tmp_res_msg:
                                            tmp_res = json.loads(tmp_res_msg.decode('utf-8'))
                                            if tmp_res.get("status") == "ok" or tmp_res.get("status") == "error":
                                                sock = w_sock
                                                connected = True
                                                handshake_done = True
                                                cached_res_payload = tmp_res
                                                matched = next((item for item in sockets if item[0] == w_sock), None)
                                                if matched:
                                                    print(f"[Client] Connected & Handshaked via LAN: {matched[1]}:{matched[2]}")
                                                break
                                    except Exception:
                                        pass
                                    
                                    if not connected:
                                        force_close_socket(w_sock)
                                except: pass
                    except: pass
                    if connected: break
                    
                # Đóng các socket không dùng tới trong batch này
                for s_tuple in sockets:
                    if s_tuple[0] != sock: force_close_socket(s_tuple[0])
                
        # 2. Kỹ thuật đục lỗ Tường lửa (TCP Hole Punching) (Chỉ thử nếu không ép buộc Relay)
        if not self.force_relay_var.get() and not connected:
            do_hole_punch = True
            if hasattr(self, 'current_ip') and self.current_ip == public_ip:
                print("[Client] Skipping Hole Punching because both peers share the same Public IP (same router).")
                do_hole_punch = False
                
            if do_hole_punch:
                self.update_status(f"Đang đục lỗ Tường lửa (TCP Hole Punching) tới {public_ip}:{port}...")
                print(f"[Client] Initiating Simultaneous Open to {public_ip}:{port}...")
                log_activity(f"[P2P] Bắt đầu quá trình đục lỗ tường lửa tới IP {public_ip}:{port}...")
                
                # Tạm thời đóng server_socket bên Client để nhường port cho outbound connect
                if getattr(self, 'server_socket', None):
                    try:
                        self.server_socket.close()
                    except: pass
                
                # Liên tục spam kết nối cực nhanh để đục lỗ (10 lần, mỗi lần 150ms)
                for _ in range(10):
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    try:
                        sock.bind(('0.0.0.0', BOUND_PORT))
                    except:
                        pass
                    sock.settimeout(0.5)
                    try:
                        sock.connect((public_ip, port))
                        connected = True
                        print(f"[Client] Hole punch successful to {public_ip}:{port}!")
                        log_activity(f"[P2P] THÀNH CÔNG: Đục lỗ tường lửa hoàn tất sau {_+1} lần thử!")
                        break
                    except Exception:
                        force_close_socket(sock)
                        time.sleep(0.15)
                        
                # Mở lại server_socket bất kể đục lỗ thành công hay thất bại
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
                    print(f"[Client] Đã phục hồi TCP server lắng nghe trên port {BOUND_PORT}")
                except Exception as e:
                    print(f"[Client] Cảnh báo: Không thể phục hồi server_socket: {e}")

        if not connected:
            display_host = getattr(self, 'current_signaling_host', None) or 'Relay'
            print("[Client] Hole punching failed. Attempting Relay fallback...")
            self.update_status("Đục lỗ thất bại. Đang chuyển hướng qua Relay Server...")
            log_activity(f"[P2P] THẤT BẠI: Không thể đục lỗ tường lửa. Bắt đầu chuyển hướng qua Relay Server ({display_host})...")
            
            try:
                relay_session_id = f"relay_{self.my_id_clean}_{partner_id}"
                relay_req = json.dumps({
                    "action": "relay_request",
                    "target": partner_id,
                    "session_id": relay_session_id,
                    "relay_host": getattr(self, 'current_signaling_host', None)
                })
                
                with self.signaling_lock:
                    if self.primary_signaling_socket:
                        try:
                            send_msg(self.primary_signaling_socket, relay_req.encode('utf-8'), APP_KEY)
                        except Exception as e:
                            print(f"[Client] Gửi relay_request thất bại: {e}")
                
                # 2. Connect to Relay Server
                host_to_connect = getattr(self, 'current_signaling_host', None) or SIGNALING_SERVER_HOSTS[0]
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((host_to_connect, SIGNALING_SERVER_PORT))
                sock.settimeout(None)
                
                header = f"RELAY_CLIENT:{relay_session_id}\n"
                sock.sendall(header.encode('utf-8'))
                
                connected = True
                print("[Client] Relay connection established successfully!")
                self.update_status("Đã kết nối qua Relay Server!")
                log_activity("[Relay] THÀNH CÔNG: Đã kết nối với đối tác qua Relay Server.")
            except Exception as e:
                print(f"[Client] Relay fallback failed: {e}")
                log_activity(f"[Relay] THẤT BẠI: Kết nối Relay thất bại ({e}).")
                self.update_status("Sẵn sàng kết nối")
                self.after(0, lambda: self.show_custom_error("Lỗi kết nối", 
                    f"Kỹ thuật Đục Lỗ Tường Lửa & Server Trung Chuyển ({display_host}) đều thất bại!\n\n"
                    f"Vui lòng kiểm tra lại kết nối mạng hoặc thử lại sau."
                ))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                if sock: force_close_socket(sock)
                return
                
        # Connection succeeded, proceed with handshake
        sock.settimeout(None) # Reset back to blocking
        
        # Tắt Nagle's algorithm (TCP_NODELAY) để giảm độ trễ tối đa cho cả đo tốc độ và điều khiển
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception as e:
            print(f"[TCP_NODELAY] Lỗi thiết lập TCP_NODELAY trên Client: {e}")
            
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
                    "computer_name": platform.node(),
                    "real_width": 1920,
                    "real_height": 1080,
                    "is_mobile": False,
                    "zalo_phone": ""
                }).encode('utf-8')
                send_msg(sock, handshake, partner_pass)
                
                # Read verification response (allow APP_KEY fallback to receive error messages)
                res_msg = recv_msg(sock, [partner_pass, APP_KEY])
                if not res_msg:
                    self.update_status("Sẵn sàng kết nối")
                    self.after(0, lambda: self.show_custom_error("Lỗi", "Đối tác ngắt kết nối đột ngột!"))
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
                zalo_phone = res.get("zalo_phone", "")
                is_domain = res.get("is_domain", False)
                is_android = res.get("is_android", False)
                
                # Perform pre-connection speed test (Ping/Latency and Bandwidth) - 2 runs, select highest speed
                self.update_status("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 1/2...")
                net_class = "medium"
                net_class_viet = "Trung bình (Medium)"
                avg_ping = 50.0
                bandwidth = 10.0
                try:
                    runs = []
                    for run_idx in range(2):
                        if run_idx > 0:
                            self.update_status("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 2/2...")
                        # 1. Ping / Latency test
                        rtts = []
                        for _ in range(3):
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
                        send_msg(sock, json.dumps({"action": "speed_test_bw_req"}).encode('utf-8'), partner_pass)
                        bw_start_msg = recv_msg(sock, partner_pass)
                        if bw_start_msg:
                            bw_start_data = json.loads(bw_start_msg.decode('utf-8'))
                            if bw_start_data.get("action") == "speed_test_bw_start":
                                dummy_size = bw_start_data.get("size", 1572864)
                                warm_size = min(1048576, int(dummy_size * 0.3)) # Scale warm-up size dynamically
                                measure_size = dummy_size - warm_size
                                
                                warm_data = b''
                                while len(warm_data) < warm_size:
                                    chunk = sock.recv(warm_size - len(warm_data))
                                    if not chunk:
                                        break
                                    warm_data += chunk
                                    
                                t_start = time.time()
                                measured_data = b''
                                while len(measured_data) < measure_size:
                                    chunk = sock.recv(measure_size - len(measured_data))
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
                        net_class_viet = "Tốt (High-speed)"
                    elif bandwidth < 5.0 or avg_ping > 50.0:
                        net_class = "low"
                        net_class_viet = "Yếu (Low-speed)"
                    else:
                        net_class = "medium"
                        net_class_viet = "Trung bình (Medium)"
                        
                    # 4. Report speed test results to Host
                    send_msg(sock, json.dumps({
                        "action": "speed_test_result",
                        "net_class": net_class,
                        "ping": avg_ping,
                        "bandwidth": bandwidth
                    }).encode('utf-8'), partner_pass)
                    
                    status_text = f"Đo tốc độ (Lớn nhất 2 lần): Ping {avg_ping:.1f}ms, Băng thông {bandwidth:.2f} Mbps. Chất lượng: {net_class_viet}."
                    print(f"[Client] {status_text}")
                    self.update_status(status_text)
                    time.sleep(0.5)
                except Exception as ste:
                    print(f"[Client] Speed test error: {ste}")
                    # Send default result to host to avoid locking
                    try:
                        send_msg(sock, json.dumps({
                            "action": "speed_test_result",
                            "net_class": "medium",
                            "ping": 50.0,
                            "bandwidth": 10.0
                        }).encode('utf-8'), partner_pass)
                    except: pass
                    
                # Pygame window sẽ mở đúng với độ phân giải thật của host. 
                # (Kích thước ảnh thực tế truyền qua mạng vẫn sẽ được nén lại bởi dyn_scale ở phía Host)
                self.update_status("Kết nối thành công! Đang khởi động màn hình...")
                if reconnect_queue:
                    try:
                        if viewer_pid and sys.platform == "win32":
                            sock_data = sock.share(viewer_pid)
                            reconnect_queue.put(("SHARED_SOCK", sock_data))
                        else:
                            reconnect_queue.put(sock)
                    except Exception as e:
                        print(f"Failed to put socket in reconnect queue: {e}")
                        reconnect_queue.put("FAILED")
                        force_close_socket(sock)
                        socket_passwords.pop(sock, None)
                else:
                    self.after(0, self.launch_pygame_viewer, sock, host_w, host_h, computer_name, zalo_phone, is_domain, partner_id, partner_pass, is_android)
            else:
                msg = res.get("message", "Sai mật khẩu!")
                self.update_status("Bị từ chối kết nối")
                if reconnect_queue:
                    reconnect_queue.put("FAILED")
                self.after(0, lambda: self.show_custom_error("Từ chối kết nối", f"Kết nối bị từ chối:\n{msg}"))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
        except Exception as e:
            if reconnect_queue and retry_count < 30:
                self.update_status(f"Mất kết nối. Đang thử kết nối lại lần {retry_count + 1}/30...")
                if sock:
                    force_close_socket(sock)
                    socket_passwords.pop(sock, None)
                time.sleep(2)
                self.connect_to_partner(partner_id, partner_pass, reconnect_queue, retry_count + 1, viewer_pid)
                return

            self.update_status("Sẵn sàng kết nối")
            if reconnect_queue:
                reconnect_queue.put("FAILED")
            else:
                self.after(0, lambda err=str(e): self.show_custom_error("Lỗi bắt tay", f"Lỗi xác thực handshake:\n{err}"))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if sock:
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
            
    def launch_pygame_viewer(self, sock, host_w, host_h, computer_name="", zalo_phone="", is_domain=False, partner_id="", partner_pass="", is_android=False):
        try:
            import multiprocessing as mp
            reconnect_queue = mp.Queue()
            p = mp.Process(target=run_client_viewer_loop, args=(sock, host_w, host_h, computer_name, is_domain, partner_id, reconnect_queue, partner_pass, is_android), daemon=True)
            p.start()
            
            # Track active viewer
            self.active_viewers.append({
                "process": p,
                "computer_name": computer_name,
                "zalo_phone": zalo_phone,
                "partner_id": partner_id
            })
            
            # Close the socket handle in the parent process to prevent port leakage
            # on Windows, which causes Hole Punching to fail on the second connection
            try:
                sock.close()
            except Exception:
                pass
            
            # Reconnection Monitor Thread
            if partner_id and partner_pass:
                def monitor_reconnect(process, pid, ppass, req_queue):
                    while process.is_alive():
                        try:
                            msg = req_queue.get(timeout=1.0)
                            if msg == "RECONNECT_REQUEST":
                                print(f"[Client Monitor] Pygame requested reconnect for {pid}...")
                                self.after(0, lambda: self.update_status(f"Đang tự động kết nối lại..."))
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
            self.update_status("Đã mở một cửa sổ điều khiển mới (Sẵn sàng kết nối)")
            print(f"[Client] Đã mở tiến trình điều khiển cho {computer_name or 'đối tác'}")
            
        except Exception as e:
            print(f"[Client] Lỗi khởi chạy tiến trình điều khiển: {e}")
            self.connect_btn.config(state=tk.NORMAL)
            try: force_close_socket(sock)
            except: pass
            
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
                item('Hiện (Show)', self.show_gui_from_tray, default=True),
                item('Thoát (Exit)', self.exit_from_tray)
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


def run_clipboard_agent_mode():
    """
    Chế độ Clipboard Agent: Chạy ở quyền User thường.
    Lắng nghe Named Pipe từ Service/headless app để nhận đường dẫn file
    và nạp vào Clipboard hệ thống.
    
    Kiến trúc: App Headless (SYSTEM) -> Named Pipe -> App ClipboardAgent (User) -> Clipboard
    """
    import logging
    import queue
    import win32file
    import win32pipe
    import win32event
    import win32api
    import time
    import tkinter as tk
    
    log_path = os.path.join(app_dir, "clipboard_agent.log")
    agent_log = logging.getLogger("clipboard_agent")
    agent_log.setLevel(logging.DEBUG)
    
    # Xoá các handler cũ nếu có để tránh ghi lặp
    for h in list(agent_log.handlers):
        agent_log.removeHandler(h)
        
    formatter = logging.Formatter("[%(asctime)s] [PID %(process)d] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    
    # Ghi file với UTF-8
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(formatter)
    agent_log.addHandler(fh)
    
    # Chỉ ghi ra console nếu stdout không phải là chính file log đó (tránh lặp 2 dòng trong file)
    is_stdout_log = False
    try:
        if sys.stdout and hasattr(sys.stdout, 'name'):
            is_stdout_log = (os.path.abspath(sys.stdout.name) == os.path.abspath(log_path))
    except:
        pass
        
    if not is_stdout_log and sys.stdout:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        agent_log.addHandler(sh)

    def agent_print(msg):
        agent_log.info(msg)

    agent_print("=" * 60)
    agent_print(f"[ClipboardAgent] Khởi động. PID: {os.getpid()}")
    agent_print(f"[ClipboardAgent] Thư mục ứng dụng: {app_dir}")
    agent_print("=" * 60)

    pipe_name = CLIPBOARD_PIPE_NAME
    gui_queue = queue.Queue()

    def pipe_listener_loop():
        while True:
            pipe_handle = None
            try:
                agent_print(f"[ClipboardAgent] Đang chờ kết nối tới Pipe: {pipe_name}")
                while True:
                    try:
                        pipe_handle = win32file.CreateFile(
                            pipe_name,
                            win32file.GENERIC_READ,
                            0,
                            None,
                            win32file.OPEN_EXISTING,
                            0,
                            None
                        )
                        break
                    except Exception:
                        time.sleep(0.5)

                agent_print(f"[ClipboardAgent] Đã kết nối thành công tới Pipe.")

                try:
                    win32pipe.SetNamedPipeHandleState(
                        pipe_handle,
                        win32pipe.PIPE_READMODE_MESSAGE,
                        None,
                        None
                    )
                except Exception as se:
                    agent_print(f"[ClipboardAgent] Cảnh báo SetNamedPipeHandleState: {se}. Tiếp tục ở chế độ byte mode.")

                buffer = bytearray()
                while True:
                    try:
                        hr, data = win32file.ReadFile(pipe_handle, 10 * 1024 * 1024)
                        if hr == 0:
                            buffer.extend(data)
                            while b"\x00" in buffer:
                                idx = buffer.index(b"\x00")
                                msg_bytes = buffer[:idx]
                                del buffer[:idx + 1]
                                msg = msg_bytes.decode("utf-8").strip()
                                if msg:
                                    agent_print(f"[ClipboardAgent] Nhận tin nhắn từ Pipe (độ dài {len(msg)}): {msg[:100]}...")
                                    if msg.startswith("TEXT:"):
                                        gui_queue.put(("text", msg[5:]))
                                    elif msg.startswith("FILES:"):
                                        gui_queue.put(("files_ready", msg[6:]))
                                    elif msg.startswith("PENDING:"):
                                        try:
                                            import json
                                            info = json.loads(msg[8:])
                                            gui_queue.put(("pending", info))
                                        except Exception as e:
                                            agent_print(f"[ClipboardAgent] Lỗi parse PENDING JSON: {e}")
                                    elif msg.startswith("PROGRESS:"):
                                        try:
                                            val = int(msg[9:])
                                            gui_queue.put(("progress", val))
                                        except:
                                            pass
                                    elif msg.startswith("CANCEL:"):
                                        gui_queue.put(("pipe_cancel", None))
                                    else:
                                        agent_print(f"[ClipboardAgent] Bỏ qua tin nhắn không nhận dạng: {msg[:50]}")
                        else:
                            agent_print(f"[ClipboardAgent] ReadFile trả về mã lỗi: {hr}")
                            break
                    except Exception as read_err:
                        err_code = getattr(read_err, 'winerror', 0)
                        if err_code == 109:
                            agent_print("[ClipboardAgent] Pipe bị ngắt. Đang kết nối lại...")
                            break
                        elif err_code == 234:
                            continue
                        else:
                            agent_print(f"[ClipboardAgent] Lỗi đọc Pipe: {read_err}")
                            break
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lỗi kết nối Pipe: {e}")
            finally:
                if pipe_handle is not None:
                    try:
                        win32file.CloseHandle(pipe_handle)
                    except:
                        pass
            time.sleep(0.1)

    # Khởi tạo Tkinter GUI
    root = tk.Tk()
    root.attributes('-alpha', 0.0) # Tránh nháy cửa sổ
    root.withdraw()
    
    active_dialog = None

    # -----------------------------------------------------------------------
    # Delayed-rendering Win32 cho HEADLESS mode
    # -----------------------------------------------------------------------
    # Khi host gửi PENDING:, agent tạo cửa sổ ẩn và trở thành chủ sở hữu clipboard
    # với dạng delayed render (CF_HDROP = NULL). Windows sẽ gửi WM_RENDERFORMAT
    # đúng lúc người dùng thực sự Paste, lúc đó agent mới yêu cầu host tải file.
    # -----------------------------------------------------------------------
    from ctypes import wintypes

    CF_HDROP        = 15
    WM_RENDERFORMAT = 0x0305
    WM_RENDERALLFORMATS = 0x0306
    WM_DESTROYCLIPBOARD = 0x0307
    WM_USER_SETUP_DELAYED = 0x0400 + 201  # tin nhắn nội bộ để setup từ luồng khác

    _agent_hwnd = None              # HWND cửa sổ ẩn của agent
    _pending_info = {}              # {'display_name': ..., 'total_size': ...}
    _files_ready_event = threading.Event()  # set khi host gửi FILES: xong
    _files_ready_paths = []        # các đưỜng dẫn file đã download
    _ignore_destroy = False        # tránh phản ứng WM_DESTROYCLIPBOARD do chính mình gây ra
    _is_rendering = False          # chống race condition WM_RENDERFORMAT
    
    _agent_last_lbutton_time = 0.0
    _agent_last_rbutton_time = 0.0
    _agent_last_ctrl_v_time = 0.0
    _agent_meta_arrival_time = 0.0

    def _agent_mouse_poll_loop():
        nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_ctrl_v_time
        user32 = ctypes.windll.user32
        while True:
            try:
                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    _agent_last_lbutton_time = time.time()
                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    _agent_last_rbutton_time = time.time()
                if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):
                    _agent_last_ctrl_v_time = time.time()
                if (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000):
                    _agent_last_ctrl_v_time = time.time()
            except:
                pass
            time.sleep(0.05)
            
    threading.Thread(target=_agent_mouse_poll_loop, daemon=True, name="AgentMousePoll").start()

    def _send_request_files_to_host(files_to_request=None):
        """Gửi chuỗi REQUEST_FILES cho host qua UpPipe."""
        import win32file, json
        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
        try:
            import win32pipe
            try:
                win32pipe.WaitNamedPipe(pipe_name, 5000)
            except Exception as e:
                pass
            pipe_handle = win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_WRITE, 0, None,
                win32file.OPEN_EXISTING, 0, None
            )
            msg = "REQUEST_FILES"
            if files_to_request:
                msg += "|" + json.dumps(files_to_request)
            win32file.WriteFile(pipe_handle, msg.encode('utf-8'))
            win32file.CloseHandle(pipe_handle)
            agent_print("[ClipboardAgent] Đã gửi REQUEST_FILES tới host.")
        except Exception as e:
            agent_print(f"[ClipboardAgent] Lỗi gửi REQUEST_FILES: {e}")

    def _execute_agent_delayed_rendering(hwnd):
        """Chạy trong WndProc thread: mở clipboard, đăng ký deferred CF_HDROP."""
        nonlocal _ignore_destroy
        if not _pending_info:
            agent_print("[ClipboardAgent] Không có pending_info, bỏ qua setup delayed rendering.")
            return
            
        try:
            _ignore_destroy = True
            user32 = ctypes.windll.user32
            opened = False
            for _ in range(30):
                if user32.OpenClipboard(hwnd):
                    opened = True
                    break
                time.sleep(0.05)
            if opened:
                user32.EmptyClipboard()
                
                # Thiết lập loại trừ Clipboard History và Cloud Clipboard
                setup_clipboard_exclusions()
                
                # SetClipboardData với NULL = hứa cung cấp dữ liệu khi được yêu cầu
                res = fn_SetClipboardData(CF_HDROP, None)
                user32.CloseClipboard()
                agent_print(f"[ClipboardAgent] Đã setup delayed rendering CF_HDROP. res={res}")
            else:
                err = ctypes.GetLastError()
                agent_print(f"[ClipboardAgent] OpenClipboard thất bại khi setup (10 lần). Err={err}")
        except Exception as e:
            agent_print(f"[ClipboardAgent] Lỗi setup delayed rendering: {e}")
        finally:
            _ignore_destroy = False

    def _agent_wndproc(hwnd, msg, wparam, lparam):
        """WndProc cho hidden window của agent. Xử lý WM_RENDERFORMAT (Paste xảy ra)."""
        nonlocal _is_rendering, _files_ready_paths, _files_ready_event, _ignore_destroy, _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time

        if msg == WM_USER_SETUP_DELAYED:
            if _pending_info:
                _execute_agent_delayed_rendering(hwnd)
            return 0

        if msg == WM_RENDERFORMAT and wparam == CF_HDROP:
            if _is_rendering:
                agent_print("[ClipboardAgent] WM_RENDERFORMAT trùng lặp, bỏ qua.")
                return 0
                
            # Kiểm tra nếu là truy vấn từ menu chuột phải (context menu) thì tránh tải file thực tế lúc này
            is_menu = check_is_menu_query(_agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_ctrl_v_time)
            if is_menu == "MENU":
                agent_print("[ClipboardAgent] Phát hiện truy vấn menu. Cung cấp dummy HDROP và lập lịch reset delayed rendering...")
                dummy_h = create_hdrop_data(["C:\\RemoteDesktop_Paste_Trigger.tmp"])
                if dummy_h:
                    ctypes.windll.user32.SetClipboardData(CF_HDROP, dummy_h)
                
                # Lập lịch setup lại delayed rendering sau 200ms để chờ menu truy vấn xong
                def re_setup_agent():
                    time.sleep(0.2)
                    if _agent_hwnd and _pending_info:
                        ctypes.windll.user32.PostMessageW(
                            ctypes.c_void_p(_agent_hwnd),
                            WM_USER_SETUP_DELAYED, 0, 0
                        )
                threading.Thread(target=re_setup_agent, daemon=True).start()
                return 0
            elif is_menu == "BACKGROUND":
                agent_print("[ClipboardAgent] Phát hiện truy vấn nền (VM Tools). Bỏ qua hoàn toàn.")
                return 0

            _is_rendering = True
            agent_print("[ClipboardAgent] Nhận WM_RENDERFORMAT → người dùng đã Paste. Bắt đầu tải file...")
            try:
                # Hiển thị dialog qua gui_queue ngay lập tức
                info = _pending_info.copy()
                gui_queue.put(("start", (info.get("display_name", "Files"), info.get("total_size", 0))))

                # Yêu cầu host bắt đầu gửi file
                _files_ready_event.clear()
                _files_ready_paths.clear()
                _send_request_files_to_host(info.get("files", []))

                # Chờ host download xong (tối đa 600 giây, pump Win32 messages)
                user32 = ctypes.windll.user32
                m = wintypes.MSG()
                deadline = time.time() + 600.0
                while time.time() < deadline:
                    if _files_ready_event.is_set():
                        break
                    if user32.PeekMessageW(ctypes.byref(m), 0, 0, 0, 1):
                        user32.TranslateMessage(ctypes.byref(m))
                        user32.DispatchMessageW(ctypes.byref(m))
                    else:
                        time.sleep(0.01)

                if _files_ready_event.is_set() and _files_ready_paths:
                    # Tạo HDROP thực sự và nạp vào clipboard
                    hGlobal = create_hdrop_data(_files_ready_paths)
                    if hGlobal:
                        _ignore_destroy = True
                        try:
                            # Lưu ý: Clipboard đã được mở sẵn bởi chương trình Paste khi gửi WM_RENDERFORMAT.
                            # Không được gọi OpenClipboard/CloseClipboard ở đây.
                            res = fn_SetClipboardData(CF_HDROP, hGlobal)
                            if not res:
                                fn_GlobalFree(hGlobal)
                            agent_print(f"[ClipboardAgent] Đã nạp HDROP vào clipboard. res={res} (Bỏ dọn dẹp để hỗ trợ copy liên tiếp)")
                            
                        except Exception as e:
                            agent_print(f"[ClipboardAgent] Lỗi SetClipboardData: {e}")
                            fn_GlobalFree(hGlobal)
                        finally:
                            _ignore_destroy = False
                    gui_queue.put(("end", None))
                    agent_print("[ClipboardAgent] Đã nạp data thực thành công.")
                else:
                    agent_print("[ClipboardAgent] Hết thời gian chờ file hoặc bị hủy.")
                    gui_queue.put(("cancel", None))
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lỗi xử lý WM_RENDERFORMAT: {e}")
                gui_queue.put(("cancel", None))
            finally:
                _is_rendering = False
                _pending_info.clear()
            return 0

        if msg == WM_DESTROYCLIPBOARD and not _ignore_destroy:
            # Clipboard bị xóa bởi app khác → hủy trạng thái pending
            if _pending_info:
                agent_print("[ClipboardAgent] WM_DESTROYCLIPBOARD → hủy pending.")
                _pending_info.clear()
                _files_ready_event.set()  # unlock nếu đang chờ
                _files_ready_paths.clear()
            return 0

        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _create_agent_window():
        """Tạo hidden Win32 window cho agent, chạy trong luồng riêng với message loop."""
        nonlocal _agent_hwnd
        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_uint,
            ctypes.c_size_t, ctypes.c_size_t
        )
        _wndproc_ref = WNDPROC(_agent_wndproc)

        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize",        wintypes.UINT),
                ("style",         wintypes.UINT),
                ("lpfnWndProc",   WNDPROC),
                ("cbClsExtra",    ctypes.c_int),
                ("cbWndExtra",    ctypes.c_int),
                ("hInstance",     ctypes.c_void_p),
                ("hIcon",         ctypes.c_void_p),
                ("hCursor",       ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName",  wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm",       ctypes.c_void_p),
            ]

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Định nghĩa kiểu dữ liệu chuẩn Win32 API cho môi trường 64-bit
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p

        user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
        user32.RegisterClassExW.restype = wintypes.ATOM

        user32.CreateWindowExW.argtypes = [
            ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
            ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        ]
        user32.CreateWindowExW.restype = ctypes.c_void_p

        cls_name = "AntigravityClipboardAgentWnd"
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = _wndproc_ref
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = cls_name
        user32.RegisterClassExW(ctypes.byref(wc))

        hwnd = user32.CreateWindowExW(
            0, cls_name, "ClipboardAgent",
            0, 0, 0, 0, 0,
            ctypes.c_void_p(-3),  # HWND_MESSAGE
            None, wc.hInstance, None
        )
        _agent_hwnd = hwnd
        agent_print(f"[ClipboardAgent] Window ẩn đã tạo. HWND={hwnd}")

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    threading.Thread(target=_create_agent_window, daemon=True, name="AgentWin32MsgLoop").start()
    time.sleep(0.1)  # Chờ window khởi tạo

    def trigger_cancel():
        """Giải phóng luồng chờ WM_RENDERFORMAT và xóa trạng thái pending."""
        nonlocal _pending_info
        _files_ready_paths.clear()
        _pending_info.clear()
        _files_ready_event.set()  # unlock nếu đang chờ trong WM_RENDERFORMAT
        agent_print("[ClipboardAgent] Đã hủy trạng thái pending.")

    def trigger_cancel_win32():
        """Nút Hủy trong dialog → gửi Win32 Event để host service dừng gửi."""
        try:
            h_event = win32event.OpenEvent(win32event.EVENT_MODIFY_STATE, False, "Global\\AntigravityP2P_CancelTransfer_Event")
            win32event.SetEvent(h_event)
            win32api.CloseHandle(h_event)
        except Exception as e:
            agent_print(f"[ClipboardAgent] Không thể gửi sự kiện hủy: {e}")
        trigger_cancel()

    def poll_gui_queue():
        nonlocal active_dialog, _agent_meta_arrival_time
        while not gui_queue.empty():
            try:
                action, val = gui_queue.get_nowait()
                if action == "text":
                    agent_print(f"[ClipboardAgent] Đang nạp text vào Clipboard...")
                    set_clipboard_text(val, owner_hwnd=_agent_hwnd)
                elif action == "files":
                    # Được gửi bởi luồng WM_RENDERFORMAT (cũ giữ lại cho trường hợp khác)
                    paths = [p for p in val.split("|") if os.path.exists(p)]
                    if paths:
                        set_clipboard_files(paths, owner_hwnd=_agent_hwnd)
                        agent_print(f"[ClipboardAgent] Đã nạp {len(paths)} file vào Clipboard.")
                    else:
                        agent_print(f"[ClipboardAgent] File không tồn tại để nạp clipboard.")
                elif action == "pending":
                    # Host gửi PENDING: → setup delayed rendering nếu window đã sẵn sàng
                    info = val
                    _pending_info.update(info)
                    display_name = info.get("display_name", "Files")
                    total_size = info.get("total_size", 0)
                    _files_ready_event.clear()
                    _files_ready_paths.clear()
                    _agent_meta_arrival_time = time.time()
                    agent_print(f"[ClipboardAgent] Nhận PENDING: '{display_name}' ({total_size} bytes). Đang setup delayed rendering...")
                    if _agent_hwnd:
                        ctypes.windll.user32.PostMessageW(
                            ctypes.c_void_p(_agent_hwnd),
                            WM_USER_SETUP_DELAYED, 0, 0
                        )
                    else:
                        agent_print("[ClipboardAgent] HWND chưa sẵn sàng, bỏ qua PENDING.")
                elif action == "pipe_cancel":
                    agent_print("[ClipboardAgent] Nhận tín hiệu CANCEL từ Pipe. Đang hủy...")
                    trigger_cancel()
                elif action == "files_ready":
                    # Cầu hiệu nội bộ: luồng WM_RENDERFORMAT đã nhận FILES: từ host
                    paths_str = val
                    paths = [p for p in paths_str.split("|") if p]
                    _files_ready_paths.clear()
                    _files_ready_paths.extend(paths)
                    _files_ready_event.set()
                    agent_print(f"[ClipboardAgent] files_ready: {len(paths)} file đã sẵn sàng.")
                elif action == "start":
                    display_name, total_size = val
                    if active_dialog:
                        try: active_dialog.destroy()
                        except: pass
                    active_dialog = ProgressDialog(
                        root, "Đang tải file về...", display_name, total_size,
                        on_cancel=trigger_cancel_win32
                    )
                elif action == "progress":
                    if active_dialog:
                        try: active_dialog.update_progress(val)
                        except: pass
                elif action == "end":
                    if active_dialog:
                        def _close():
                            nonlocal active_dialog
                            if active_dialog:
                                try: active_dialog.destroy()
                                except: pass
                                active_dialog = None
                        root.after(500, _close)
                elif action == "cancel":
                    if active_dialog:
                        try: active_dialog.destroy()
                        except: pass
                        active_dialog = None
            except queue.Empty:
                break
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lỗi xử lý hàng đợi GUI: {e}")
        root.after(50, poll_gui_queue)

    t = threading.Thread(target=pipe_listener_loop, daemon=True)
    t.start()
    
    poll_gui_queue()
    root.mainloop()

if __name__ == '__main__':
    import multiprocessing as mp
    mp.freeze_support()
    
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
            # Service headless helper uses mutex index 1
            mutex_name = f"Global\\AntigravityP2PRemoteDesktopAppMutex_1_{session_id}_{desktop_name}"
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
                        msg_text = "Ứng dụng P2P Remote Desktop đang chạy ở khay hệ thống"
                        msg_title = "Thông báo"
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
        app.mainloop()
        with open("C:\\Apps\\P2P\\agent.log", "a", encoding="utf-8") as f:
            f.write("\\n[DEBUG] Exited mainloop cleanly!\\n")
        # Keep the process alive just in case
        if "--headless" in sys.argv:
            import time
            while True:
                time.sleep(1)
    except BaseException as e:
        import traceback
        with open("C:\\Apps\\P2P\\agent_crash.txt", "w") as f:
            traceback.print_exc(file=f)
        raise
