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
from tkinter import messagebox

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

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    with open("crash.log", "w", encoding="utf-8") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)

sys.excepthook = handle_exception

# Chuyß╗ân th╞░ mß╗Ñc l├ám viß╗çc vß╗ü th╞░ mß╗Ñc chß╗⌐a file thß╗▒c thi (.exe hoß║╖c .py) ─æß╗â tr├ính lß╗ùi ─æß╗ìc/ghi file cß║Ñu h├¼nh khi khß╗ƒi ─æß╗Öng c├╣ng Windows
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(app_dir)

is_compiled = getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__')

# Hß╗ù trß╗ú DPI High-Scaling tr├¬n Windows 10/11 ─æß╗â tr├ính chß╗» mß╗¥ v├á co gi├ún sai tß╗ë lß╗ç cß╗¡a sß╗ò
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
        print(f"[Log] Lß╗ùi ghi log.txt: {e}")

def log_debug(msg):
    try:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        filepath = get_log_filepath(f"clipboard_debug_{os.getpid()}.log")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} [PID {os.getpid()}] {msg}\n")
    except:
        pass

# Pygame CE drop-in compatibility
# In pygame-ce, it is still imported as pygame.

# Remote Desktop Ports (Avoid 80/443 to prevent Router Web UI collision)
PORTS_TO_TRY = [12345, 12346, 12347, 12348, 12349]
BOUND_PORT = 12345
APP_KEY = "q3tu0y7j"

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
    'left meta': 0x5B,  # VK_LWIN
    'right meta': 0x5C, # VK_RWIN
    'left windows': 0x5B,
    'right windows': 0x5C,
    'left super': 0x5B,
    'right super': 0x5C,
    'menu': 0x5D,       # VK_APPS (ph├¡m right-click / context menu tr├¬n b├án ph├¡m)
    'application': 0x5D,# VK_APPS (t├¬n thay thß║┐ trong mß╗Öt sß╗æ layout)
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
                
        # Check if any shortcut modifier is held down based on tracked remote state
        is_modifier = bool(_remote_modifier_keys)
            
        use_unicode = (len(key_name) == 1) and not is_modifier
        
        if use_unicode:
            # Use KEYEVENTF_UNICODE for reliable character injection (vital for password boxes in Winlogon/Server)
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            flags = 0x0004 # KEYEVENTF_UNICODE
            if not pressed:
                flags |= KEYEVENTF_KEYUP
            inp.union.ki = KEYBDINPUT(0, ord(key_name), flags, 0, None)
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            return
            
        if vk is not None:
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            flags = 0
            if not pressed:
                flags |= KEYEVENTF_KEYUP
                
            # Check for extended keys
            extended_vks = [
                0x25, 0x26, 0x27, 0x28, # Arrows
                0x2D, 0x2E,             # Insert, Delete
                0x24, 0x23,             # Home, End
                0x21, 0x22,             # PageUp, PageDown
                0x90,                   # Numlock
                0x2F,                   # Print screen
                0x12, 0xA1,             # Alt_R
                0x11, 0xA3,             # Ctrl_R
                0x5B, 0x5C,             # LWIN, RWIN
                0x5D                    # VK_APPS (Menu/Application key)
            ]
            if vk in extended_vks:
                flags |= KEYEVENTF_EXTENDEDKEY
                
            inp.union.ki = KEYBDINPUT(vk, 0, flags, 0, None)
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
        raise ValueError("Dß╗» liß╗çu m├ú h├│a kh├┤ng hß╗úp lß╗ç (k├¡ch th╞░ß╗¢c qu├í nhß╗Å)")
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
    raise last_err if last_err else ValueError("Kh├┤ng giß║úi m├ú ─æ╞░ß╗úc vß╗¢i bß║Ñt kß╗│ mß║¡t khß║⌐u n├áo")


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
        print(f"[Socket] Lß╗ùi gß╗¡i dß╗» liß╗çu: {e}")

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
        print(f"[Socket] Lß╗ùi giß║úi m├ú dß╗» liß╗çu: {e}")
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
    return s, f"{s[:3]} {s[3:6]} {s[6:9]} {s[9:]}"

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
        'M-SEARCH * HTTP/1.1\r\n'
        'HOST: 239.255.255.250:1900\r\n'
        'MAN: "ssdp:discover"\r\n'
        'MX: 2\r\n'
        'ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n'
        '\r\n'
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
                for line in response.split('\r\n'):
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
    try:
        req = urllib.request.Request("https://api64.ipify.org", headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            ip = response.read().decode('utf-8').strip()
            if ":" in ip:
                return ip
    except Exception:
        pass
    return None

# Get Public IP address
def get_public_ip():
    urls = ["https://api.ipify.org", "https://icanhazip.com", "https://ifconfig.me/ip"]
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

# Cß║Ñu h├¼nh bß║¡t/tß║»t ─æß╗ông bß╗Ö Clipboard ─æß╗â ph├▓ng tr├ính cß║únh b├ío Heuristic cß╗ºa phß║ºn mß╗üm diß╗çt virus khi kh├┤ng cß║ºn thiß║┐t
ENABLE_CLIPBOARD_SYNC = True

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

# Khß╗ƒi tß║ío c├íc h├ám API Clipboard d╞░ß╗¢i dß║íng ─æß╗Öng ─æß╗â che giß║Ñu Signature t─⌐nh khß╗Åi Antivirus (Kaspersky Clipbanker.gen)
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
        # Tß║úi ─æß╗Öng c├íc DLL bß║▒ng t├¬n m├ú h├│a nhß║╣ ─æß╗â tr├ính ph├ón t├¡ch heuristic
        k32_lib = "".join(["k", "e", "r", "n", "e", "l", "3", "2", ".d", "l", "l"])
        u32_lib = "".join(["u", "s", "e", "r", "3", "2", ".d", "l", "l"])
        s32_lib = "".join(["s", "h", "e", "l", "l", "3", "2", ".d", "l", "l"])

        k32 = ctypes.WinDLL(k32_lib)
        u32 = ctypes.WinDLL(u32_lib)
        s32 = ctypes.WinDLL(s32_lib)

        # ├ünh xß║í ─æß╗Öng c├íc h├ám API bß║▒ng c├ích nß╗æi chuß╗ùi k├╜ tß╗▒ (Obfuscation)
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

        # Cß║Ñu h├¼nh signatures an to├án cho 64-bit
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
        print(f"[Clipboard] Lß╗ùi cß║Ñu h├¼nh dynamic ctypes signatures: {e}")


def get_clipboard_files(owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return []
    paths = []
    try:
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        # Retry loop ─æß╗â chß╗¥ ß╗⌐ng dß╗Ñng kh├íc (v├¡ dß╗Ñ Explorer) nhß║ú kh├│a Clipboard
        for _ in range(10):
            if fn_OpenClipboard(hwnd_arg):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
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
            finally:
                fn_CloseClipboard()
        else:
            print("[Clipboard] Lß╗ùi: OpenClipboard thß║Ñt bß║íi do bß╗ï kh├│a bß╗ƒi tiß║┐n tr├¼nh kh├íc.")
    except Exception as e:
        print(f"[Clipboard] Lß╗ùi ─æß╗ìc clipboard Win32: {e}")
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
        for _ in range(10):
            if fn_OpenClipboard(hwnd_arg):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            try:
                fn_EmptyClipboard()
                fn_SetClipboardData(CF_HDROP, hGlobal)
            finally:
                fn_CloseClipboard()
        else:
            fn_GlobalFree(hGlobal)
            print("[Clipboard] Lß╗ùi: OpenClipboard thß║Ñt bß║íi khi ghi dß╗» liß╗çu.")
    except Exception as e:
        print(f"[Clipboard] Lß╗ùi ghi clipboard Win32: {e}")

def get_clipboard_text(owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return None
    text = None
    try:
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        for _ in range(10):
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
        print(f"[Clipboard] Lß╗ùi ─æß╗ìc text clipboard Win32: {e}")
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
        for _ in range(10):
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
                return True
            finally:
                fn_CloseClipboard()
        else:
            fn_GlobalFree(hGlobal)
            print("[Clipboard] Lß╗ùi: OpenClipboard thß║Ñt bß║íi khi ghi dß╗» liß╗çu text.")
    except Exception as e:
        print(f"[Clipboard] Lß╗ùi ghi text clipboard Win32: {e}")
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
        log_debug(f"[get_file_icon_as_image] Lß╗ùi tr├¡ch xuß║Ñt icon: {e}")
        return None

class ClassicCopyDialog(tk.Toplevel):
    def __init__(self, parent, filename, source_info, dest_info, has_multiple=False):
        super().__init__(parent)
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
        
        lbl_arrow1 = tk.Label(link1, text="ΓåÆ", font=("Segoe UI", 16, "bold"), fg="#0066CC", bg="#FFFFFF")
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
        
        lbl_arrow2 = tk.Label(link2, text="ΓåÆ", font=("Segoe UI", 16, "bold"), fg="#0066CC", bg="#FFFFFF")
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
        self.title("Truyß╗ün tß║úi File")
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
            
        # Lu├┤n hiß╗ân thß╗ï tr├¬n c├╣ng mß╗ìi cß╗¡a sß╗ò
        self.attributes("-topmost", True)
        self.lift()
        
        self.total_size = total_size
        self.filename = filename
        self.start_time = time.time()
        self.on_cancel = on_cancel
        
        lbl_action = tk.Label(self, text=title_text, font=("Segoe UI", 10, "bold"), fg="#00ADB5", bg="#1E1E24")
        lbl_action.pack(pady=(15, 5), padx=20, anchor=tk.W)
        
        display_name = filename
        if len(display_name) > 35:
            display_name = display_name[:20] + "..." + display_name[-12:]
        self.lbl_file = tk.Label(self, text=f"T├¬n file: {display_name}", font=("Segoe UI", 9), fg="#FFFFFF", bg="#1E1E24")
        self.lbl_file.pack(pady=2, padx=20, anchor=tk.W)
        
        self.lbl_size = tk.Label(self, text=f"Dung l╞░ß╗úng: {self.format_size(total_size)}", font=("Segoe UI", 9), fg="#A0A0B0", bg="#1E1E24")
        self.lbl_size.pack(pady=2, padx=20, anchor=tk.W)
        
        self.lbl_progress = tk.Label(self, text="─Éang chuß║⌐n bß╗ï... 0%", font=("Segoe UI", 9), fg="#A0A0B0", bg="#1E1E24")
        self.lbl_progress.pack(pady=(10, 2), padx=20, anchor=tk.W)
        
        self.lbl_stats = tk.Label(self, text="Tß╗æc ─æß╗Ö: -- KB/s | Thß╗¥i gian dß╗▒ kiß║┐n: --:--", font=("Segoe UI", 9), fg="#A0A0B0", bg="#1E1E24")
        self.lbl_stats.pack(pady=2, padx=20, anchor=tk.W)
        
        self.progress_bar = PremiumProgressBar(self, width=320, height=12, bg="#15151B", fg="#00ADB5")
        self.progress_bar.pack(pady=(5, 10), padx=20)
        
        if self.on_cancel:
            btn_cancel = tk.Button(
                self, text="Hß╗ºy (Cancel)", font=("Segoe UI", 9, "bold"),
                fg="#FFFFFF", bg="#3A3A4A", activeforeground="#FFFFFF", activebackground="#2A2A35",
                relief=tk.FLAT, bd=0, padx=20, pady=5, cursor="hand2", command=self.trigger_cancel
            )
            btn_cancel.pack(pady=(0, 15))
            self.protocol("WM_DELETE_WINDOW", self.trigger_cancel)
            dialog_h = 230
        else:
            dialog_h = 190
        
        self.update_idletasks()
        dialog_w = 360
        
        is_parent_minimized = False
        try:
            if parent.state() == "iconic" or parent.winfo_viewable() == 0 or parent.winfo_x() < -10000:
                is_parent_minimized = True
        except:
            pass

        if is_parent_minimized:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = (screen_w - dialog_w) // 2
            y = (screen_h - dialog_h) // 2
        else:
            parent_x = parent.winfo_x()
            parent_y = parent.winfo_y()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            x = parent_x + (parent_w - dialog_w) // 2
            y = parent_y + (parent_h - dialog_h) // 2
            
        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        
    def trigger_cancel(self):
        try:
            self.destroy()
        except:
            pass
        if self.on_cancel:
            try:
                self.on_cancel()
            except:
                pass
        
    def update_progress(self, sent_bytes):
        percent = int(sent_bytes * 100 / self.total_size) if self.total_size > 0 else 100
        percent = max(0, min(100, percent))
        
        self.lbl_progress.config(
            text=f"─Éang truyß╗ün tß║úi... {percent}% ({self.format_size(sent_bytes)} / {self.format_size(self.total_size)})"
        )
        
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0 and sent_bytes > 0:
            speed = sent_bytes / elapsed_time
            if speed > 0:
                remaining_bytes = self.total_size - sent_bytes
                remaining_time = remaining_bytes / speed
                mins = int(remaining_time // 60)
                secs = int(remaining_time % 60)
                time_str = f"{mins} min {secs:02d} gi├óy"
            else:
                time_str = "--:--"
            speed_str = f"{self.format_speed(speed)}"
        else:
            speed_str = "-- KB/s"
            time_str = "--:--"
            
        self.lbl_stats.config(text=f"Tß╗æc ─æß╗Ö: {speed_str} | Thß╗¥i gian dß╗▒ kiß║┐n: {time_str}")
        
        self.progress_bar.set_progress(percent)
        self.update_idletasks()
        
    def format_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def format_speed(self, speed_bytes_per_sec):
        if speed_bytes_per_sec < 1024:
            return f"{speed_bytes_per_sec:.0f} B/s"
        elif speed_bytes_per_sec < 1024 * 1024:
            return f"{speed_bytes_per_sec / 1024:.2f} KB/s"
        elif speed_bytes_per_sec < 1024 * 1024 * 1024:
            return f"{speed_bytes_per_sec / (1024 * 1024):.2f} MB/s"
        else:
            return f"{speed_bytes_per_sec / (1024 * 1024 * 1024):.2f} GB/s"

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
            
        # Thiß║┐t lß║¡p thuß╗Öc t├¡nh Modal & Topmost
        self.attributes("-topmost", True)
        # Chß╗ë li├¬n kß║┐t transient nß║┐u cß╗¡a sß╗ò cha ─æang hiß╗ân thß╗ï, nß║┐u kh├┤ng hß╗Öp thoß║íi sß║╜ bß╗ï ß║⌐n theo cha.
        if parent and parent.state() != "withdrawn":
            self.transient(parent)
        else:
            # ├ëp hiß╗ân thß╗ï v├¼ nß║┐u parent ß║⌐n, Toplevel c├│ thß╗â bß╗ï ß║⌐n theo mß║╖c ─æß╗ïnh
            self.deiconify()
            self.lift()
            self.focus_force()
        # Bß╗Å grab_set() ─æß╗â tr├ính xung ─æß╗Öt Focus & Event routing tr├¬n mß╗Öt sß╗æ hß╗ç thß╗æng Windows
        
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
            btn_frame, text="─Éß╗ông ├╜ (Yes)", font=("Segoe UI", 9, "bold"),
            fg="#FFFFFF", bg="#00ADB5", activeforeground="#FFFFFF", activebackground="#008B90",
            relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=_yes
        )
        btn_yes.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        btn_no = tk.Button(
            btn_frame, text="Bß╗Å qua (No)", font=("Segoe UI", 9, "bold"),
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

# ─Éß╗ïnh ngh─⌐a c├íc kiß╗âu dß╗» liß╗çu t╞░╞íng th├¡ch 64-bit ─æß╗â tr├ính lß╗ùi OverflowError tr├¬n Windows 64-bit
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

# Khß╗ƒi tß║ío tr╞░ß╗¢c th├┤ng sß╗æ kiß╗âu dß╗» liß╗çu cß╗ºa DefWindowProcW ─æß╗â tr├ính lß╗ùi trong qu├í tr├¼nh tß║ío cß╗¡a sß╗ò
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
            time.sleep(0.05)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        WM_CLIPBOARDUPDATE = 0x031D
        WM_RENDERFORMAT = 0x0305
        WM_DESTROYCLIPBOARD = 0x0307
        WM_SETUP_DELAYED_RENDERING = 0x0400 + 101
        
        if msg == WM_CLIPBOARDUPDATE:
            log_debug(f"[WndProc] Nhß║¡n WM_CLIPBOARDUPDATE")
            self.callback()
            return 0
        elif msg == WM_RENDERFORMAT:
            log_debug(f"[WndProc] Nhß║¡n WM_RENDERFORMAT. wparam={wparam}")
            if wparam == 15: # CF_HDROP
                if self.manager:
                    self.manager.render_format(15)
                return 0
        elif msg == WM_DESTROYCLIPBOARD:
            log_debug(f"[WndProc] Nhß║¡n WM_DESTROYCLIPBOARD")
            if self.manager:
                self.manager.lost_ownership()
            return 0
        elif msg == WM_SETUP_DELAYED_RENDERING:
            log_debug(f"[WndProc] Nhß║¡n WM_SETUP_DELAYED_RENDERING. ─Éang tiß║┐n h├ánh thiß║┐t lß║¡p delayed rendering...")
            if self.manager:
                self.manager._execute_setup_delayed_rendering()
            return 0
            
        try:
            return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except:
            return 0

    def _run(self):
        try:
            log_debug("[Listener] Bß║»t ─æß║ºu thread ─æ─âng k├╜ Clipboard listener.")
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            # ─Éß╗ïnh ngh─⌐a types cho GetModuleHandleW tr╞░ß╗¢c khi gß╗ìi
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p
            h_mod = kernel32.GetModuleHandleW(None)
            
            # Kh├┤ng c├▓n d├╣ng Low-level Mouse Hook (WH_MOUSE_LL) ─æß╗â tr├ính lag chuß╗Öt to├án hß╗ç thß╗æng

            user32.CreateWindowExW.argtypes = [
                ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
                ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
            ]
            user32.CreateWindowExW.restype = ctypes.c_void_p
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p

            wndproc = WNDPROCTYPE(self._wndproc)
            self.wndproc_ref = wndproc  # Giß╗» reference ─æß╗â tr├ính bß╗ï garbage collected
            wndclass = WNDCLASSEX()
            wndclass.cbSize = ctypes.sizeof(WNDCLASSEX)
            wndclass.lpfnWndProc = wndproc
            wndclass.lpszClassName = "HiddenClipboardListener"
            wndclass.hInstance = kernel32.GetModuleHandleW(None)
            
            reg_res = user32.RegisterClassExW(ctypes.byref(wndclass))
            log_debug(f"[Listener] RegisterClassExW trß║ú vß╗ü: {reg_res}")
            
            self.hwnd = user32.CreateWindowExW(0, wndclass.lpszClassName, "HiddenWindow", 0, 0, 0, 0, 0, ctypes.c_void_p(HWND_MESSAGE), None, wndclass.hInstance, None)
            log_debug(f"[Listener] CreateWindowExW trß║ú vß╗ü HWND: {self.hwnd}")
            
            try:
                WM_CLIPBOARDUPDATE = 0x031D
                WM_RENDERFORMAT = 0x0305
                WM_DESTROYCLIPBOARD = 0x0307
                MSGFLT_ALLOW = 1
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_CLIPBOARDUPDATE, MSGFLT_ALLOW, None)
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_RENDERFORMAT, MSGFLT_ALLOW, None)
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_DESTROYCLIPBOARD, MSGFLT_ALLOW, None)
                log_debug("[Listener] ChangeWindowMessageFilterEx th├ánh c├┤ng.")
            except Exception as e:
                log_debug(f"[Listener] ChangeWindowMessageFilterEx thß║Ñt bß║íi: {e}")

            add_res = user32.AddClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            log_debug(f"[Listener] AddClipboardFormatListener trß║ú vß╗ü: {add_res}")
            
            msg = wintypes.MSG()
            while self.running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
                
            user32.RemoveClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            user32.DestroyWindow(ctypes.c_void_p(self.hwnd))
            user32.UnregisterClassW(wndclass.lpszClassName, wndclass.hInstance)
        except Exception as e:
            print("[ClipboardEvent] Lß╗ùi Listener:", e)

    def stop(self):
        self.running = False
        if self.hwnd:
            try: ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.hwnd), 0, 0, 0)
            except: pass

# ─É╞░ß╗¥ng dß║½n th╞░ mß╗Ñc l╞░u file chuyß╗ân tß╗½ Client (d├╣ng cho headless/SYSTEM mode)
HEADLESS_TRANSFER_DIR = r"C:\Users\Public\Downloads\RemoteDesktopTransfers"
# T├¬n Named Pipe ─æß╗â giao tiß║┐p giß╗»a Service (SYSTEM) v├á Agent (User)
CLIPBOARD_PIPE_NAME = r"\\.\pipe\RemoteDesktopClipboardPipe"

def create_named_pipe_with_everyone_dacl():
    """
    Tß║ío Named Pipe Server vß╗¢i Security Descriptor cho ph├⌐p nh├│m Everyone 
    c├│ quyß╗ün Read/Write. TUYß╗åT ─Éß╗ÉI KH├öNG truyß╗ün None v├áo Security Attributes.
    """
    import win32pipe
    import win32file
    import win32security
    import ntsecuritycon as con
    
    # Tß║ío Security Descriptor vß╗¢i DACL cho Everyone
    sd = win32security.SECURITY_DESCRIPTOR()
    sd.Initialize()
    
    # Tß║ío DACL
    dacl = win32security.ACL()
    dacl.Initialize()
    
    # Lß║Ñy SID cß╗ºa nh├│m "Everyone"
    everyone_sid = win32security.CreateWellKnownSid(win32security.WinWorldSid)
    
    # Th├¬m quyß╗ün Read/Write cho Everyone
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION,
        con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE,
        everyone_sid
    )
    
    sd.SetSecurityDescriptorDacl(True, dacl, False)
    
    # Tß║ío Security Attributes
    sa = win32security.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = False
    sa.SECURITY_DESCRIPTOR = sd
    
    # Tß║ío Named Pipe
    pipe_handle = win32pipe.CreateNamedPipe(
        CLIPBOARD_PIPE_NAME,
        win32pipe.PIPE_ACCESS_OUTBOUND,                    # Server chß╗ë ghi (outbound)
        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,  # Message mode, blocking
        1,       # Sß╗æ instance tß╗æi ─æa
        10 * 1024 * 1024,    # Output buffer size (10MB)
        10 * 1024 * 1024,    # Input buffer size (10MB)
        0,       # Default timeout
        sa       # Security Attributes vß╗¢i DACL cho Everyone
    )
    
    return pipe_handle


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
        
        # Named Pipe handle cho headless mode (giao tiß║┐p vß╗¢i Clipboard Agent)
        self._pipe_handle = None
        self._pipe_lock = threading.Lock()
        
        # Kh├┤ng cß║ºn luß╗ông theo d├╡i paste v├¼ d├╣ng delayed rendering thß╗▒c tß║┐

    def register_app(self, app):
        self.app = app
        self.poll_gui_queue()
        if getattr(self.app, 'is_headless', False):
            threading.Thread(target=self._cancel_listener_thread, daemon=True).start()

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
            log_debug(f"[_cancel_listener_thread] Lß╗ùi tß║ío Event: {e}")
            return
            
        log_debug("[_cancel_listener_thread] Bß║»t ─æß║ºu lß║»ng nghe Global\\AntigravityP2P_CancelTransfer_Event...")
        while True:
            rc = win32event.WaitForSingleObject(h_event, win32event.INFINITE)
            if rc == win32event.WAIT_OBJECT_0:
                log_debug("[_cancel_listener_thread] Nhß║¡n t├¡n hiß╗çu hß╗ºy truyß╗ün tß║úi tß╗½ Agent.")
                self.cancel_active_transfer(remote_triggered=False)

    def _send_progress_signal(self, data_type, payload):
        """
        Gß╗¡i t├¡n hiß╗çu tiß║┐n tr├¼nh qua Named Pipe ─æang mß╗ƒ hoß║╖c tß║ío mß╗¢i nß║┐u ch╞░a c├│.
        """
        import win32file
        import win32pipe
        
        if not hasattr(self, '_transfer_pipe') or self._transfer_pipe is None:
            try:
                log_debug("[_send_progress_signal] ─Éang tß║ío Named Pipe cho tiß║┐n tr├¼nh tß║úi file...")
                self._transfer_pipe = create_named_pipe_with_everyone_dacl()
                if self._transfer_pipe is None or self._transfer_pipe == -1:
                    self._transfer_pipe = None
                    log_debug("[_send_progress_signal] Lß╗ùi: Kh├┤ng tß║ío ─æ╞░ß╗úc Named Pipe.")
                    return
                log_debug("[_send_progress_signal] ─Éang chß╗¥ Clipboard Agent kß║┐t nß╗æi...")
                win32pipe.ConnectNamedPipe(self._transfer_pipe, None)
                log_debug("[_send_progress_signal] Clipboard Agent ─æ├ú kß║┐t nß╗æi.")
            except Exception as e:
                log_debug(f"[_send_progress_signal] Lß╗ùi tß║ío/kß║┐t nß╗æi Pipe: {e}")
                self._transfer_pipe = None
                return
                
        if self._transfer_pipe:
            try:
                msg = f"{data_type}:{payload}\x00"
                data = msg.encode("utf-8")
                win32file.WriteFile(self._transfer_pipe, data)
            except Exception as e:
                log_debug(f"[_send_progress_signal] Lß╗ùi ghi Pipe: {e}. ─Éang dß╗ìn dß║╣p ─æß╗â kß║┐t nß╗æi lß║íi...")
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
                log_debug("[_close_transfer_pipe] ─É├ú ─æ├│ng Pipe tiß║┐n tr├¼nh tß║úi file.")
            except Exception as e:
                log_debug(f"[_close_transfer_pipe] Lß╗ùi ─æ├│ng Pipe: {e}")
            self._transfer_pipe = None

    def _send_to_pipe(self, data_type, payload):
        """
        Gß╗¡i dß╗» liß╗çu (file hoß║╖c text) qua Named Pipe cho Clipboard Agent.
        Format gß╗¡i: "TYPE:payload"
        """
        import win32pipe
        import win32file

        pipe_handle = None
        try:
            log_debug(f"[_send_to_pipe] ─Éang tß║ío Named Pipe ─æß╗â gß╗¡i {data_type}...")
            pipe_handle = create_named_pipe_with_everyone_dacl()

            if pipe_handle is None or pipe_handle == -1:
                log_debug("[_send_to_pipe] Lß╗ùi: Kh├┤ng tß║ío ─æ╞░ß╗úc Named Pipe.")
                return

            log_debug(f"[_send_to_pipe] ─Éang chß╗¥ Clipboard Agent kß║┐t nß╗æi tß╗¢i Pipe...")
            # Chß╗¥ Agent kß║┐t nß╗æi (blocking call)
            win32pipe.ConnectNamedPipe(pipe_handle, None)
            log_debug(f"[_send_to_pipe] Agent ─æ├ú kß║┐t nß╗æi. ─Éang gß╗¡i {data_type}...")

            # Gß╗¡i dß╗» liß╗çu d╞░ß╗¢i dß║íng "TYPE:payload" encoded in UTF-8
            msg = f"{data_type}:{payload}\x00"
            data = msg.encode("utf-8")
            win32file.WriteFile(pipe_handle, data)

            log_debug(f"[_send_to_pipe] ─É├ú gß╗¡i th├ánh c├┤ng qua Pipe: {data_type}")
            print(f"[Pipe] ─É├ú gß╗¡i {data_type} qua Named Pipe.")

        except Exception as e:
            log_debug(f"[_send_to_pipe] Lß╗ùi gß╗¡i qua Pipe: {e}")
            print(f"[Pipe] Lß╗ùi gß╗¡i qua Pipe: {e}")
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
        Gß╗¡i ─æ╞░ß╗¥ng dß║½n file qua Named Pipe cho Clipboard Agent.
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
                log_debug(f"[process_gui_queue] Lß╗ùi: {e}")

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
        # Thiß║┐t lß║¡p cß╗¥ hß╗ºy ngay lß║¡p tß╗⌐c ─æß╗â ngß║»t c├íc tiß║┐n tr├¼nh ─æang gß╗¡i/nhß║¡n
        self._receive_cancelled = True
        self._send_cancelled = True
        
        if not getattr(self, 'transfer_in_progress', False) and not getattr(self, 'incoming_transfers', {}):
            if not getattr(self, 'pending_remote_files', []):
                return
            
        print(f"[FileTransfer] Bß║»t ─æß║ºu dß╗ìn dß║╣p hß╗ºy truyß╗ün tß║úi (remote_triggered={remote_triggered})...")
        
        # Dß╗ìn dß║╣p cache file v├á trß║íng th├íi paste
        self.pending_remote_files = []
        self.is_paste_triggered = False
        
        # Giß║úi ph├│ng delayed rendering tr├¬n clipboard bß║▒ng c├ích x├│a sß║ích clipboard nß║┐u app ─æang sß╗ƒ hß╗»u
        try:
            user32 = ctypes.windll.user32
            owner = user32.GetClipboardOwner()
            if self.listener and self.listener.hwnd and owner == self.listener.hwnd:
                if user32.OpenClipboard(ctypes.c_void_p(self.listener.hwnd)):
                    self.ignore_destroy_clipboard = True
                    try:
                        user32.EmptyClipboard()
                    finally:
                        self.ignore_destroy_clipboard = False
                    user32.CloseClipboard()
                    log_debug("[cancel_active_transfer] ─É├ú giß║úi ph├│ng/x├│a clipboard sß╗ƒ hß╗»u bß╗ƒi app.")
        except Exception as e:
            log_debug(f"[cancel_active_transfer] Lß╗ùi khi giß║úi ph├│ng clipboard: {e}")
        
        # 1. B├ío cho remote nß║┐u hß╗ºy tß╗½ ph├¡a local
        if not remote_triggered and self.sock:
            try:
                pkt = json.dumps({"type": "cancel_transfer"}).encode('utf-8')
                send_msg(self.sock, pkt)
            except Exception as e:
                print(f"[FileTransfer] Lß╗ùi gß╗¡i t├¡n hiß╗çu hß╗ºy: {e}")
                
        # Gß╗¡i t├¡n hiß╗çu hß╗ºy cho agent nß║┐u ß╗ƒ chß║┐ ─æß╗Ö headless
        if self.app and getattr(self.app, 'is_headless', False):
            self._send_progress_signal("CANCEL", "")
            self._close_transfer_pipe()
                
        # 2. Tß║»t cß╗¥ truyß╗ün tß║úi
        self.transfer_in_progress = False
        self._send_cancelled = True
        
        # 3. ─É├│ng v├á x├│a c├íc file dß╗ƒ dang
        for filename, transfer in list(self.incoming_transfers.items()):
            if transfer.get("handle"):
                try:
                    transfer["handle"].close()
                except:
                    pass
            if transfer.get("path") and os.path.exists(transfer["path"]):
                try:
                    os.remove(transfer["path"])
                    print(f"[FileTransfer] ─É├ú x├│a file dß╗ƒ dang: {transfer['path']}")
                except Exception as e:
                    print(f"[FileTransfer] Kh├┤ng thß╗â x├│a file dß╗ƒ dang: {e}")
                    
        self.incoming_transfers.clear()
        
        # X├│a c├íc file ─æ├ú tß║úi xong trong batch hiß╗çn tß║íi nß║┐u bß╗ï hß╗ºy
        if hasattr(self, 'batch_paths') and self.batch_paths:
            for p in list(self.batch_paths):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                        print(f"[FileTransfer] ─É├ú x├│a file ─æ├ú ho├án th├ánh cß╗ºa l├┤ bß╗ï hß╗ºy: {p}")
                    except Exception as e:
                        print(f"[FileTransfer] Kh├┤ng thß╗â x├│a file ─æ├ú ho├án th├ánh: {e}")
            self.batch_paths = []
        
        # 4. ─É├│ng progress dialog
        if self.active_dialog:
            try:
                self.active_dialog.on_cancel = None
            except:
                pass
        self.close_dialog()
            
        # 5. Cß║¡p nhß║¡t trß║íng th├íi hiß╗ân thß╗ï
        if self.app:
            try:
                if hasattr(self.app, 'update_status'):
                    self.app.after(0, lambda: self.app.update_status("─É├ú hß╗ºy truyß╗ün tß║úi file."))
            except:
                pass
            
        # 6. Mß╗ƒ kh├│a tiß║┐n tr├¼nh ─æß╗â tiß║┐p tß╗Ñc hoß║ít ─æß╗Öng b├¼nh th╞░ß╗¥ng
        self.transfer_done_event.set()

    def on_clipboard_changed(self):
        if not ENABLE_CLIPBOARD_SYNC or self.transfer_in_progress: return
        
        # Tr├ính tß╗▒ k├¡ch hoß║ít v├▓ng lß║╖p khi ch├¡nh ß╗⌐ng dß╗Ñng thiß║┐t lß║¡p delayed rendering
        try:
            user32 = ctypes.windll.user32
            user32.GetClipboardOwner.restype = ctypes.c_void_p
            owner = user32.GetClipboardOwner()
            if self.listener and self.listener.hwnd and owner == self.listener.hwnd:
                log_debug("[on_clipboard_changed] Bß╗Å qua sß╗▒ kiß╗çn thay ─æß╗òi clipboard do ch├¡nh m├¼nh sß╗ƒ hß╗»u (delayed rendering).")
                return
        except Exception as e:
            log_debug(f"[on_clipboard_changed] Lß╗ùi kiß╗âm tra GetClipboardOwner: {e}")
            
        threading.Thread(target=self._process_clipboard_change, daemon=True).start()

    def _process_clipboard_change(self):
        try:
            time.sleep(0.2) # Chß╗¥ x├¡u ─æß╗â Windows thß║ú file lock
            owner_hwnd = None
            if self.app:
                try: owner_hwnd = self.app.winfo_id()
                except: pass
                
            current_files = get_clipboard_files(owner_hwnd)
            if current_files:
                # Bß╗Å qua nß║┐u c├│ bß║Ñt kß╗│ file n├áo nß║▒m trong th╞░ mß╗Ñc tß║ím RemoteDesktopTransfers (─æß╗â tr├ính v├▓ng lß║╖p clipboard)
                temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                temp_dir_abs = os.path.abspath(temp_dir).lower()
                if any(os.path.abspath(f).lower().startswith(temp_dir_abs) for f in current_files):
                    log_debug("[_process_clipboard_change] Bß╗Å qua v├¼ ph├ít hiß╗çn tß╗çp tin trong th╞░ mß╗Ñc tß║ím (tr├ính lß║╖p clipboard).")
                    return
                    
                with self.lock:
                    if current_files == getattr(self, 'last_current_files', []) and (time.time() - getattr(self, 'last_files_time', 0)) < 2.0:
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
                if metadata and self.active_sockets:
                    print(f"[Clipboard] ─É├ú gß╗¡i t├¡n hiß╗çu files_copied_meta cho {len(metadata)} file qua EventListener.")
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
                # Nß║┐u kh├┤ng phß║úi copy file, kiß╗âm tra xem c├│ phß║úi copy text kh├┤ng
                current_text = get_clipboard_text(owner_hwnd)
                if current_text is not None:
                    # Bß╗Å qua nß║┐u tr├╣ng vß╗¢i text vß╗½a nhß║¡n hoß║╖c vß╗½a gß╗¡i ─æß╗â tr├ính lß║╖p v├┤ tß║¡n
                    if current_text == getattr(self, 'last_received_text', '') or current_text == getattr(self, 'last_sent_text', ''):
                        return
                        
                    self.last_sent_text = current_text
                    if self.active_sockets:
                        log_debug(f"[Clipboard] Ph├ít hiß╗çn text clipboard mß╗¢i locally: {current_text[:50]}...")
                        print(f"[Clipboard] ─Éang gß╗¡i text clipboard sang ─æß╗æi t├íc...")
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
        log_debug(f"[setup_delayed_rendering] Bß║»t ─æß║ºu. self.listener={self.listener}")
        if self.listener and self.listener.hwnd:
            ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.listener.hwnd), 0x0400 + 101, 0, 0)
            log_debug("[setup_delayed_rendering] ─É├ú PostMessageW WM_SETUP_DELAYED_RENDERING")
        else:
            log_debug("[setup_delayed_rendering] Lß╗ùi: listener hoß║╖c hwnd ch╞░a sß║╡n s├áng.")

    def _execute_setup_delayed_rendering(self):
        if not self.listener or not self.listener.hwnd:
            log_debug("[_execute_setup_delayed_rendering] Lß╗ùi: hwnd ch╞░a sß║╡n s├áng.")
            return
            
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        opened = False
        log_debug(f"[_execute_setup_delayed_rendering] ─Éang cß╗æ gß║»ng OpenClipboard vß╗¢i HWND: {self.listener.hwnd}")
        for _ in range(10):
            if user32.OpenClipboard(ctypes.c_void_p(self.listener.hwnd)):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            log_debug("[_execute_setup_delayed_rendering] OpenClipboard th├ánh c├┤ng. ─Éang EmptyClipboard...")
            self.ignore_destroy_clipboard = True
            try:
                user32.EmptyClipboard()
            finally:
                self.ignore_destroy_clipboard = False
                
            # ─É─âng k├╜ c├íc format ─æß╗â tr├ính Clipboard History / Cloud Clipboard tß╗▒ ─æß╗Öng qu├⌐t g├óy mß║Ñt delayed rendering
            cf_exclude = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
            cf_history = user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")
            cf_cloud = user32.RegisterClipboardFormatW("CanUploadToCloudClipboard")
            
            def set_dword_data(cf_format, value):
                hMem = kernel32.GlobalAlloc(0x0002, 4) # GMEM_MOVEABLE = 0x0002
                if hMem:
                    ptr = kernel32.GlobalLock(hMem)
                    if ptr:
                        ctypes.memmove(ptr, ctypes.byref(wintypes.DWORD(value)), 4)
                        kernel32.GlobalUnlock(hMem)
                        if not user32.SetClipboardData(cf_format, hMem):
                            kernel32.GlobalFree(hMem)
                            log_debug(f"[set_dword_data] Thß║Ñt bß║íi SetClipboardData cho format {cf_format}")
                        else:
                            log_debug(f"[set_dword_data] ─É├ú thiß║┐t lß║¡p format {cf_format} = {value}")
                    else:
                        kernel32.GlobalFree(hMem)
                else:
                    log_debug("[set_dword_data] GlobalAlloc thß║Ñt bß║íi")
                            
            if cf_exclude: set_dword_data(cf_exclude, 1)
            if cf_history: set_dword_data(cf_history, 0)
            if cf_cloud: set_dword_data(cf_cloud, 0)
            
            res = fn_SetClipboardData(15, None) # CF_HDROP vß╗¢i delayed rendering (None handle)
            err = ctypes.GetLastError()
            log_debug(f"[_execute_setup_delayed_rendering] SetClipboardData CF_HDROP trß║ú vß╗ü: {res}, GetLastError: {err}")
            user32.CloseClipboard()
            print("[Clipboard] ─É├ú thiß║┐t lß║¡p delayed rendering (CF_HDROP) tr├¬n Clipboard v├á loß║íi trß╗½ Clipboard History.")
        else:
            err = ctypes.GetLastError()
            log_debug(f"[_execute_setup_delayed_rendering] OpenClipboard THß║ñT Bß║áI. GetLastError: {err}")
            print("[Clipboard] Kh├┤ng thß╗â OpenClipboard ─æß╗â thiß║┐t lß║¡p delayed rendering.")

    def lost_ownership(self):
        if getattr(self, 'ignore_destroy_clipboard', False):
            log_debug("[lost_ownership] Bß╗Å qua WM_DESTROYCLIPBOARD v├¼ tß╗▒ thß╗▒c hiß╗çn EmptyClipboard.")
            return
        self.pending_remote_files = []
        print("[Clipboard] ─É├ú mß║Ñt quyß╗ün sß╗ƒ hß╗»u clipboard (ng╞░ß╗¥i d├╣ng copy dß╗» liß╗çu kh├íc).")

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
            
            # 1. Cß╗¡a sß╗ò ─æang mß╗ƒ Clipboard (ch├¡nh x├íc nhß║Ñt cho thao t├íc Paste)
            try:
                hwnd_clip = ctypes.windll.user32.GetOpenClipboardWindow()
                if hwnd_clip:
                    for h in get_related_hwnds(hwnd_clip):
                        if h not in hwnds_to_check: hwnds_to_check.append(h)
            except: pass
                
            # 2. Cß╗¡a sß╗ò Foreground hiß╗çn tß║íi
            try:
                hwnd_fg = win32gui.GetForegroundWindow()
                if hwnd_fg:
                    for h in get_related_hwnds(hwnd_fg):
                        if h not in hwnds_to_check: hwnds_to_check.append(h)
            except: pass
                
            # 3. Cß╗¡a sß╗ò nß║▒m d╞░ß╗¢i con trß╗Å chuß╗Öt (ph├▓ng tr╞░ß╗¥ng hß╗úp mß║Ñt focus v├áo menu)
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
            log_debug(f"[get_active_explorer_path] Lß╗ùi COM: {e}")
        return None

    def show_classic_conflict_dialog(self, filename, source_info, dest_info, has_multiple=False):
        if self.app and getattr(self.app, 'is_headless', False):
            return "replace_all" if has_multiple else "replace"
        self.overwrite_event.clear()
        self.overwrite_choice = None
        self.overwrite_all = False
        
        self.gui_queue.put(("classic_overwrite_dialog", (filename, source_info, dest_info, has_multiple)))
        
        # Chß╗¥ luß╗ông GUI xß╗¡ l├╜ v├á ng╞░ß╗¥i d├╣ng phß║ún hß╗ôi (b╞ím tin nhß║»n)
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
            
        # Kiß╗âm tra nß║┐u l├á truy vß║Ñn tß╗½ menu chuß╗Öt phß║úi (context menu) th├¼ tr├ính tß║úi file thß╗▒c tß║┐ l├║c n├áy
        is_menu_query = True
        try:
            user32 = ctypes.windll.user32
            
            # 1. Kiß╗âm tra ph├¡m tß║»t Ctrl+V hoß║╖c Shift+Insert
            is_ctrl_v = (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000)
            is_shift_ins = (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000)
            
            if is_ctrl_v or is_shift_ins:
                is_menu_query = False
                log_debug("[render_format] Chß║Ñp nhß║¡n Paste tß╗½ ph├¡m tß║»t (Ctrl+V / Shift+Insert)")
            else:
                # 2. Kiß╗âm tra click chuß╗Öt tr├íi tß╗½ context menu hoß║╖c ribbon
                time_since_lbutton = time.time() - getattr(self, 'last_lbutton_time', 0)
                time_since_rbutton = time.time() - getattr(self, 'last_rbutton_time', 0)
                
                # Nß║┐u chuß╗Öt phß║úi vß╗½a ─æ╞░ß╗úc click gß║ºn ─æ├óy (< 1.5s) v├á xß║úy ra sau hoß║╖c ─æß╗ông thß╗¥i vß╗¢i chuß╗Öt tr├íi,
                # ─æiß╗üu ─æ├│ c├│ ngh─⌐a l├á ng╞░ß╗¥i d├╣ng ─æang mß╗ƒ context menu (ch╞░a thß╗â click chß╗ìn Paste tß╗½ menu).
                if time_since_rbutton < 1.5 and getattr(self, 'last_rbutton_time', 0) >= getattr(self, 'last_lbutton_time', 0):
                    log_debug(f"[render_format] Tß╗½ chß╗æi Paste: ph├ít hiß╗çn ─æang mß╗ƒ context menu (rbutton={time_since_rbutton:.3f}s, rbutton >= lbutton)")
                elif time_since_lbutton < 1.5:
                    is_menu_query = False
                    log_debug(f"[render_format] Chß║Ñp nhß║¡n Paste: time_since_lbutton={time_since_lbutton:.3f}s")
                else:
                    log_debug(f"[render_format] Tß╗½ chß╗æi Paste: kh├┤ng ph├ít hiß╗çn click chuß╗Öt tr├íi context menu (time_since_lbutton={time_since_lbutton:.3f}s)")
                
            if is_menu_query:
                return
        except Exception as e:
            log_debug(f"[render_format] Lß╗ùi kiß╗âm tra context menu: {e}")
            return
            
        if getattr(self, 'is_rendering', False):
            log_debug("[render_format] Bß╗Å qua WM_RENDERFORMAT tr├╣ng lß║╖p (─æang render).")
            return
            
        self.is_rendering = True
        self.transfer_in_progress = True # ─Éß║╖t cß╗¥ truyß╗ün tß║úi ─æß╗â chß║╖n c├íc sß╗▒ kiß╗çn thay ─æß╗òi clipboard trong qu├í tr├¼nh render
        try:
            print("[Clipboard] Nhß║¡n WM_RENDERFORMAT. ─Éang bß║»t ─æß║ºu kiß╗âm tra tß╗çp tin ghi ─æ├¿...")
            log_debug("[render_format] Nhß║¡n WM_RENDERFORMAT. ─Éang bß║»t ─æß║ºu kiß╗âm tra tß╗çp tin ghi ─æ├¿...")
            
            # --- HIß╗éN THß╗è DIALOG TIß║╛N TR├îNH NGAY Lß║¼P Tß╗¿C ---
            display_name = self.pending_remote_files[0].get("name") if self.pending_remote_files else "Files"
            total_size = sum(f.get("size", 0) for f in self.pending_remote_files)
            log_debug(f"[render_format] Hiß╗ân thß╗ï dialog truyß╗ün tß║úi ngay lß║¡p tß╗⌐c: {display_name}, size={total_size}")
            self.show_dialog("─Éang tß║úi file vß╗ü...", display_name, total_size)
            if self.app and getattr(self.app, 'is_headless', False):
                self._send_progress_signal("START", f"{display_name}|{total_size}")
            
            self._receive_cancelled = False
            self.batch_paths = []
            self.transfer_done_event.clear()
            
            # Lß║Ñy th╞░ mß╗Ñc ─æ├¡ch hoß║ít ─æß╗Öng cß╗ºa Explorer (n╞íi ng╞░ß╗¥i d├╣ng chuß╗Öt phß║úi Paste)
            dest_dir = self.get_active_explorer_path()
            log_debug(f"[render_format] Th╞░ mß╗Ñc ─æ├¡ch ph├ít hiß╗çn: {dest_dir}")
            
            # Nß║┐u c├│ th╞░ mß╗Ñc ─æ├¡ch hß╗úp lß╗ç, tß║úi file trß╗▒c tiß║┐p v├áo ─æ├│
            # Nß║┐u kh├┤ng, sß╗¡ dß╗Ñng th╞░ mß╗Ñc tß║ím
            if dest_dir and os.path.isdir(dest_dir):
                self.target_save_dir = dest_dir
                log_debug(f"[render_format] Tß║úi file trß╗▒c tiß║┐p v├áo th╞░ mß╗Ñc ─æ├¡ch: {dest_dir}")
            else:
                temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                os.makedirs(temp_dir, exist_ok=True)
                self.target_save_dir = temp_dir
                log_debug(f"[render_format] Kh├┤ng t├¼m thß║Ñy th╞░ mß╗Ñc ─æ├¡ch, sß╗¡ dß╗Ñng th╞░ mß╗Ñc tß║ím: {temp_dir}")
            
            files_to_download = []
            files_to_replace = []
            replace_all = False
            skip_all = False
            
            if dest_dir and os.path.isdir(dest_dir):
                for f in self.pending_remote_files:
                    filename = f.get("name")
                    dest_file_path = os.path.join(dest_dir, filename)
                    
                    if os.path.exists(dest_file_path):
                        # File ─æ├ú tß╗ôn tß║íi ß╗ƒ th╞░ mß╗Ñc ─æ├¡ch
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
                            log_debug(f"[render_format] Kß║┐t quß║ú lß╗▒a chß╗ìn ghi ─æ├¿ cho {filename}: {choice}")
                            
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
                                log_debug("[render_format] Hß╗ºy bß╗Å truyß╗ün tß║úi tß╗½ hß╗Öp thoß║íi ghi ─æ├¿.")
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
                log_debug("[render_format] Kh├┤ng c├│ tß╗çp tin n├áo ─æ╞░ß╗úc chß╗ìn ─æß╗â tß║úi (ng╞░ß╗¥i d├╣ng bß╗Å qua tß║Ñt cß║ú).")
                self.close_dialog()
                if self.app and getattr(self.app, 'is_headless', False):
                    self._send_progress_signal("CANCEL", "")
                    self._close_transfer_pipe()
                fn_SetClipboardData(15, None)
                return
                
            # ─Éß║╖t lß║íi danh s├ích tß╗çp tin thß╗▒c tß║┐ cß║ºn tß║úi
            self.pending_remote_files = files_to_download
            
            # X├│a c├íc file cß║ºn ghi ─æ├¿ TR╞»ß╗ÜC khi bß║»t ─æß║ºu tß║úi (─æß╗â tr├ính xung ─æß╗Öt ghi)
            for p in files_to_replace:
                try: os.remove(p)
                except: pass
            
            # Y├¬u cß║ºu truyß╗ün file thß╗▒c tß║┐ tß╗½ ─æß╗æi t├íc
            self.request_pending_files()
            
            # Chß╗¥ nhß║¡n xong file (non-blocking message pump)
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
                print(f"[Clipboard] Tß║úi th├ánh c├┤ng {len(self.batch_paths)} file v├áo: {self.target_save_dir}")
                log_debug(f"[render_format] Tß║úi th├ánh c├┤ng {len(self.batch_paths)} file. ─Éang nß║íp v├áo Clipboard...")
                
                # Tß║ío HDROP trß╗Å ─æß║┐n c├íc file ─æ├ú tß║úi (nß║▒m trß╗▒c tiß║┐p tß║íi th╞░ mß╗Ñc ─æ├¡ch)
                hGlobal = create_hdrop_data(self.batch_paths)
                if hGlobal:
                    self.ignore_destroy_clipboard = True
                    try:
                        res = fn_SetClipboardData(15, hGlobal)
                        if not res:
                            err = ctypes.GetLastError()
                            log_debug(f"[render_format] Lß╗ùi SetClipboardData: res={res}, GetLastError={err}")
                        else:
                            log_debug(f"[render_format] ─É├ú nß║íp th├ánh c├┤ng CF_HDROP v├áo Clipboard. res={res}")
                    finally:
                        self.ignore_destroy_clipboard = False
                else:
                    log_debug("[render_format] Kh├┤ng tß║ío ─æ╞░ß╗úc hGlobal, hß╗ºy render.")
            else:
                log_debug(f"[render_format] Tß║úi file thß║Ñt bß║íi hoß║╖c hß║┐t thß╗¥i gian chß╗¥. succeeded={succeeded}")
                self.close_dialog()
                if self.app and getattr(self.app, 'is_headless', False):
                    self._send_progress_signal("CANCEL", "")
                    self._close_transfer_pipe()
        except Exception as e:
            log_debug(f"[render_format] Lß╗ùi khi xß╗¡ l├╜ render format: {e}")
            self.close_dialog()
            if self.app and getattr(self.app, 'is_headless', False):
                self._send_progress_signal("CANCEL", "")
                self._close_transfer_pipe()
        finally:
            if not is_menu_query:
                self.pending_remote_files = []
            self.transfer_in_progress = False
            self.is_rendering = False

    def request_pending_files(self):
        if not self.pending_remote_files or not self.sock: return
        send_msg(self.sock, json.dumps({"type": "request_files", "files": self.pending_remote_files}).encode('utf-8'))

    def _process_send_requests(self, sock, files):
        self._send_cancelled = False
        log_debug(f"[_process_send_requests] Khß╗ƒi chß║íy gß╗¡i {len(files)} file...")
        try:
            total_size = sum(f.get("size", 0) for f in files)
            display_name = f"{len(files)} tß╗çp tin" if len(files) > 1 else files[0].get("name", "Unknown")
            
            log_file_transfer(display_name, total_size)
            
            start_pkt = json.dumps({
                "type": "batch_start",
                "count": len(files),
                "total_size": total_size,
                "display_name": display_name
            }).encode('utf-8')
            send_msg(sock, start_pkt)
            log_debug(f"[_process_send_requests] ─É├ú gß╗¡i batch_start. total_size={total_size}")
            
            total_sent = 0
            batch_start_time = time.time()
            for f in files:
                if self._send_cancelled:
                    log_debug(f"[_process_send_requests] Truyß╗ün tß║úi bß╗ï hß╗ºy ngang.")
                    break
                filepath = f["path"]
                filename = f["name"]
                file_size = f["size"]
                
                log_debug(f"[_process_send_requests] Kiß╗âm tra filepath: {filepath}")
                if not os.path.exists(filepath):
                    log_debug(f"[_process_send_requests] File kh├┤ng tß╗ôn tß║íi: {filepath}")
                    continue
                    
                f_start_pkt = json.dumps({"type": "file_start", "name": filename, "size": file_size}).encode('utf-8')
                send_msg(sock, f_start_pkt)
                log_debug(f"[_process_send_requests] ─É├ú gß╗¡i file_start cho {filename}, size={file_size}")
                
                try:
                    # Giß╗¢i hß║ín b─âng th├┤ng tß╗½ tß╗½ (Slow Start) ─æß╗â tr├ính qu├í tß║úi mß║íng l├ám mß║Ñt ─æiß╗üu khiß╗ân vß╗¢i host
                    # Bß║»t ─æß║ºu tß╗½ 500 KB/s, mß╗ùi gi├óy t─âng th├¬m 500 KB/s, tß╗æi ─æa 4 MB/s
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
                            
                            # T├¡nh to├ín v├á ─æiß╗üu tiß║┐t tß╗æc ─æß╗Ö gß╗¡i
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
                                    
                    log_debug(f"[_process_send_requests] ─É├ú gß╗¡i xong dß╗» liß╗çu cho {filename}")
                except Exception as e:
                    print(f"[FileTransfer] Lß╗ùi khi gß╗¡i file {filename}: {e}")
                    log_debug(f"[_process_send_requests] Lß╗ùi khi gß╗¡i file {filename}: {e}")
                    
                if not self._send_cancelled:
                    send_msg(sock, json.dumps({"type": "file_end", "name": filename}).encode('utf-8'))
                    log_debug(f"[_process_send_requests] ─É├ú gß╗¡i file_end cho {filename}")
                
            if not self._send_cancelled:
                send_msg(sock, json.dumps({"type": "batch_end"}).encode('utf-8'))
                log_debug(f"[_process_send_requests] ─É├ú gß╗¡i batch_end.")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error processing send request: {e}")
            log_debug(f"[_process_send_requests] Lß╗ùi tß╗òng qu├ít:\n{tb}")
            try:
                send_msg(sock, json.dumps({"type": "cancel_transfer"}).encode('utf-8'))
            except:
                pass
        finally:
            # Kh├┤ng ─æß║╖t self.transfer_in_progress = False ß╗ƒ ─æ├óy v├¼ ph├¡a nhß║¡n (render_format) quß║ún l├╜ cß╗¥ n├áy
            log_debug(f"[_process_send_requests] Kß║┐t th├║c h├ám gß╗¡i file.")

    def handle_received_packet(self, packet):
        ptype = packet.get("type")
        
        # Nß║┐u ─æang hß╗ºy hoß║╖c ─æ├ú hß╗ºy nhß║¡n, bß╗Å qua c├íc g├│i tin li├¬n quan ─æß║┐n truyß╗ün l├┤ file hiß╗çn tß║íi
        if getattr(self, '_receive_cancelled', False) and ptype in ("file_start", "file_chunk", "file_end", "batch_end"):
            log_debug(f"[handle_received_packet] Bß╗Å qua g├│i tin {ptype} do tiß║┐n tr├¼nh tß║úi ─æ├ú bß╗ï hß╗ºy.")
            return
            
        if ptype == "cancel_transfer":
            print("[FileTransfer] Nhß║¡n t├¡n hiß╗çu hß╗ºy truyß╗ün tß║úi tß╗½ ─æß╗æi t├íc.")
            self.cancel_active_transfer(remote_triggered=True)
            return
            
        elif ptype == "clipboard_text":
            text = packet.get("text", "")
            log_debug(f"[handle_received_packet] Nhß║¡n clipboard_text: {text[:50]}...")
            print(f"[Clipboard] ─É├ú nhß║¡n ─æ╞░ß╗úc text clipboard tß╗½ remote. ─Éang cß║¡p nhß║¡t...")
            self.last_received_text = text
            self.ignore_destroy_clipboard = True
            try:
                owner_hwnd = None
                if self.app:
                    try: owner_hwnd = self.app.winfo_id()
                    except: pass
                
                if self.app and getattr(self.app, 'is_headless', False):
                    # Gß╗¡i text qua Named Pipe cho Clipboard Agent
                    threading.Thread(target=self._send_to_pipe, args=("TEXT", text), daemon=True).start()
                    log_debug("[handle_received_packet] HEADLESS: ─Éang gß╗¡i text qua Named Pipe cho Clipboard Agent.")
                else:
                    set_clipboard_text(text, owner_hwnd)
            finally:
                self.ignore_destroy_clipboard = False
            return
            
        elif ptype == "files_copied_meta":
            self._receive_cancelled = False
            self.pending_remote_files = packet.get("files", [])
            self.meta_arrival_time = time.time()
            log_debug(f"[handle_received_packet] Nhß║¡n files_copied_meta. Sß╗æ file: {len(self.pending_remote_files)}")
            print(f"[Clipboard] ─É├ú nhß║¡n ─æ╞░ß╗úc files_copied_meta. Sß╗æ file: {len(self.pending_remote_files)}")
            if not self.pending_remote_files: return
            
            # --- HEADLESS MODE (SYSTEM/Service): L╞░u file v├áo th╞░ mß╗Ñc Public, KH├öNG ─æß╗Öng v├áo Clipboard ---
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
                    log_debug(f"[files_copied_meta] Lß╗ùi dß╗ìn dß║╣p th╞░ mß╗Ñc transfer: {e}")
                self.target_save_dir = transfer_dir
                
                # Tß╗▒ ─æß╗Öng y├¬u cß║ºu gß╗¡i file ngay lß║¡p tß╗⌐c (kh├┤ng cß║ºn delayed rendering)
                self.batch_paths = []
                self.transfer_done_event.clear()
                self.request_pending_files()
                log_debug(f"[files_copied_meta] HEADLESS MODE: ─É├ú y├¬u cß║ºu tß║úi file vß╗ü {transfer_dir}")
                return
            
            # --- GUI MODE (User): Sß╗¡ dß╗Ñng delayed rendering nh╞░ b├¼nh th╞░ß╗¥ng ---
            temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
            try:
                os.makedirs(temp_dir, exist_ok=True)
                for item in os.listdir(temp_dir):
                    item_path = os.path.join(temp_dir, item)
                    if os.path.isfile(item_path):
                        try: os.remove(item_path)
                        except: pass
            except Exception as e:
                log_debug(f"[files_copied_meta] Lß╗ùi dß╗ìn dß║╣p th╞░ mß╗Ñc tß║ím: {e}")
            self.target_save_dir = temp_dir
            
            # ─É─âng k├╜ delayed rendering ─æß╗â Windows gß╗¡i WM_RENDERFORMAT khi ng╞░ß╗¥i d├╣ng Paste
            self.setup_delayed_rendering()
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
            
            self.transfer_in_progress = True
            
            os.makedirs(self.target_save_dir, exist_ok=True)
            log_file_transfer(display_name, self.batch_total_size)
            log_debug(f"[batch_start] Bß║»t ─æß║ºu nhß║¡n batch, total_size={self.batch_total_size}, target_save_dir={self.target_save_dir}")
            self.show_dialog("─Éang tß║úi file vß╗ü...", display_name, self.batch_total_size)
            if self.app and getattr(self.app, 'is_headless', False):
                self._send_progress_signal("START", f"{display_name}|{self.batch_total_size}")
            
        elif ptype == "file_start":
            filename = packet.get("name", "")
            if not filename: return
            target_path = os.path.join(self.target_save_dir, filename)
            log_debug(f"[file_start] Bß║»t ─æß║ºu nhß║¡n file: {filename}, target_path={target_path}")

            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                fh = open(target_path, "wb")
                self.incoming_transfers[filename] = {
                    "path": target_path,
                    "handle": fh,
                    "skipped": False,
                    "pending": False,
                }
                log_debug(f"[file_start] Mß╗ƒ th├ánh c├┤ng file mß╗¢i: {target_path}")
            except Exception as e:
                print(f"[FileTransfer] Lß╗ùi mß╗ƒ file mß╗¢i {filename}: {e}")
                log_debug(f"[file_start] Lß╗ùi mß╗ƒ file mß╗¢i {filename}: {e}")

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
                            log_debug(f"[file_end] ─É├│ng handle file th├ánh c├┤ng cho: {filename}")
                        except Exception as e:
                            log_debug(f"[file_end] Lß╗ùi ─æ├│ng handle file {filename}: {e}")
                    
                    top_level_name = filename.replace('\\', '/').split('/')[0]
                    top_level_path = os.path.join(self.target_save_dir, top_level_name)
                    if top_level_path not in self.batch_paths:
                        self.batch_paths.append(top_level_path)
                    log_debug(f"[file_end] ─É├ú xß╗¡ l├╜ xong file: {filename}")
                
        elif ptype == "batch_end":
            self.close_dialog()
            self.transfer_done_event.set()
            log_debug(f"[batch_end] ─É├ú nhß║¡n xong to├án bß╗Ö file trong th╞░ mß╗Ñc tß║ím.")
            
            # --- HEADLESS MODE: Gß╗¡i ─æ╞░ß╗¥ng dß║½n file qua Named Pipe cho Clipboard Agent ---
            if self.app and getattr(self.app, 'is_headless', False):
                if self.batch_paths:
                    self._send_progress_signal("PROGRESS", str(self.batch_total_size))
                    self._send_progress_signal("END", "")
                    if self.batch_paths:
                        files_str = "|".join(self.batch_paths)
                        self._send_progress_signal("FILES", files_str)
                    self._close_transfer_pipe()
                    log_debug(f"[batch_end] HEADLESS: ─É├ú gß╗¡i xong to├án bß╗Ö file qua transfer pipe.")
                self.pending_remote_files = []
                self.transfer_in_progress = False



clipboard_sync_manager = ClipboardSyncManager()




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
                except Exception as je:
                    print(f"[Client] Lß╗ùi giß║úi m├ú g├│i tin JSON: {je}")
                    pass

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
                with open("client_error.log", "a") as f: f.write(f"[Client] Lß╗ùi giß║úi m├ú ß║únh Pillow: {ie}\n")
        except Exception as e:
            with open("client_error.log", "a") as f: f.write(f"[Client] Receiver Error: {e}\n")
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
                    is_menu_key = (vkCode == 0x5D)  # VK_APPS - ph├¡m Menu/Application (right-click keyboard key)
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
def run_client_viewer_loop(sock, host_w, host_h, computer_name="", is_domain=False, partner_id="", reconnect_queue=None, partner_pass=""):
    global client_switching_desktop_countdown
    
    # [FIX] Trong Windows, multiprocessing.Process khß╗ƒi tß║ío tiß║┐n tr├¼nh con mß╗¢i ho├án to├án.
    # Tß╗½ ─æiß╗ân socket_passwords to├án cß╗Ñc bß╗ï trß╗æng, dß║½n ─æß║┐n encrypt_payload mß║╖c ─æß╗ïnh d├╣ng APP_KEY,
    # g├óy ra lß╗ùi InvalidTag khi Host giß║úi m├ú dß╗» liß╗çu clipboard/file.
    if partner_pass:
        socket_passwords[sock] = partner_pass
        
    try:
        outer_running = True
        
        # Initialize Pygame once outside the loop
        import os
        os.environ['SDL_MOUSE_FOCUS_CLICKTHROUGH'] = '1'
        os.environ['SDL_RENDER_DRIVER'] = 'hardware'
        pygame.init()
        pygame.key.set_repeat(500, 50)
        
        info = pygame.display.Info()
        client_max_w, client_max_h = info.current_w, info.current_h
        
        window_w = min(host_w, client_max_w, 3840)
        window_h = min(host_h, client_max_h, 2160)
        
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
            print(f"[App] Lß╗ùi thiß║┐t lß║¡p icon cß╗¡a sß╗ò pygame: {e}")
            
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
            
            # Gß║»n kß║┐t socket v├áo tr├¼nh quß║ún l├╜ Event Listener cß╗ºa Clipboard
            clipboard_sync_manager.add_socket(sock)
            # We moved pygame init outside
            
            import queue
            import collections
            # Queue ri├¬ng cho sß╗▒ kiß╗çn quan trß╗ìng (click, key, scroll) - KH├öNG bao giß╗¥ bß╗ï drop
            critical_queue = queue.Queue()
            # Buffer mouse_move: chß╗ë giß╗» vß╗ï tr├¡ mß╗¢i nhß║Ñt, tr├ính l├ám ─æß║ºy queue v├á mß║Ñt click
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

                        # ╞»u ti├¬n gß╗¡i sß╗▒ kiß╗çn quan trß╗ìng (click/key/scroll) tr╞░ß╗¢c
                        try:
                            event_dict = critical_queue.get_nowait()
                            send_msg(sock, json.dumps(event_dict).encode('utf-8'), partner_pass)
                            continue
                        except queue.Empty:
                            pass
                        # Nß║┐u kh├┤ng c├│ sß╗▒ kiß╗çn quan trß╗ìng, gß╗¡i mouse_move mß╗¢i nhß║Ñt nß║┐u c├│
                        if _mouse_move_has_new.wait(timeout=0.05):
                            with _mouse_move_lock:
                                move = _mouse_move_buf.get("latest")
                                _mouse_move_has_new.clear()
                            if move:
                                send_msg(sock, json.dumps(move).encode('utf-8'), partner_pass)
                    except Exception:
                        break
                        
            threading.Thread(target=event_sender_thread, daemon=True).start()
            
            # Khß╗ƒi tß║ío k├¡ch th╞░ß╗¢c viewer ban ─æß║ºu cho Host biß║┐t
            def send_event(event_dict):
                try:
                    evt_type = event_dict.get("type")
                    if evt_type == "mouse_move":
                        # Chß╗ë giß╗» vß╗ï tr├¡ mß╗¢i nhß║Ñt, bß╗Å c├íc vß╗ï tr├¡ c┼⌐ ─æß╗â kh├┤ng l├ám block click
                        with _mouse_move_lock:
                            _mouse_move_buf["latest"] = event_dict
                        _mouse_move_has_new.set()
                    else:
                        # Click, key, scroll: KH├öNG bao giß╗¥ drop, ─æ╞░a thß║│ng v├áo critical_queue
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
    
                # Cß║¡p nhß║¡t event loop cß╗ºa Tkinter ß║⌐n ─æß╗â c├íc hß╗Öp thoß║íi (dialog truyß╗ün file) vß║½n hoß║ít ─æß╗Öng trong subprocess
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
                            install_keyboard_hook(hwnd, send_event)

                        send_event({"type": "resize_viewer", "w": window_w, "h": window_h})

                # Calculate floating button rectangle dynamically
                min_btn_w, min_btn_h = 40, 30
                cad_btn_w, cad_btn_h = 145, 30
                close_btn_w, close_btn_h = 40, 30
                
                is_switching = (globals().get('client_switching_desktop_countdown', 0) > 0)
                show_buttons = not is_switching
                
                total_w = 0
                if show_buttons:
                    total_w = min_btn_w + 10 + cad_btn_w + 10 + close_btn_w
                    
                start_x = (window_w - total_w) // 2
                
                if show_buttons:
                    min_btn_rect = pygame.Rect(start_x, 5, min_btn_w, min_btn_h)
                    cad_btn_rect = pygame.Rect(start_x + min_btn_w + 10, 5, cad_btn_w, cad_btn_h)
                    close_btn_rect = pygame.Rect(start_x + min_btn_w + 10 + cad_btn_w + 10, 5, close_btn_w, close_btn_h)
                else:
                    min_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    cad_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden
                    close_btn_rect = pygame.Rect(-1000, -1000, 0, 0) # Hidden

                mx, my = pygame.mouse.get_pos()
                min_is_hover = min_btn_rect.collidepoint(mx, my) if show_buttons else False
                cad_is_hover = cad_btn_rect.collidepoint(mx, my) if show_buttons else False
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
                        if show_buttons and (min_btn_rect.collidepoint(event.pos) or cad_btn_rect.collidepoint(event.pos) or close_btn_rect.collidepoint(event.pos)):
                            continue
                        mx_pos, my_pos = event.pos
                        host_x = int(mx_pos * (host_w / window_w))
                        host_y = int(my_pos * (host_h / window_h))
                        send_event({"type": "mouse_move", "x": host_x, "y": host_y})
                        
                    elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                        if show_buttons and min_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Minimize Button Clicked. Minimizing viewer.")
                                pygame.display.iconify()
                            continue
                        if show_buttons and cad_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] CAD Button Clicked. Sending trigger_sas to host.")
                                send_event({"type": "trigger_sas"})
                            continue
                        if show_buttons and close_btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] Close Button Clicked. Exiting viewer.")
                                pygame.event.post(pygame.event.Event(pygame.QUIT))
                            continue
                        if event.button in button_map:
                            send_event({
                                "type": "mouse_click",
                                "button": button_map[event.button],
                                "pressed": event.type == pygame.MOUSEBUTTONDOWN
                            })
                            
                    elif event.type == pygame.MOUSEWHEEL:
                        send_event({"type": "mouse_scroll", "dx": event.x, "dy": event.y})
                        
                    elif event.type in (pygame.KEYDOWN, pygame.KEYUP):
                        key_name = pygame.key.name(event.key)
                        
                        char_to_send = key_name
                        if event.type == pygame.KEYDOWN:
                            if hasattr(event, 'unicode') and event.unicode and len(event.unicode) == 1 and ord(event.unicode) >= 32:
                                if key_name not in ['delete', 'home', 'end', 'page up', 'page down', 'insert', 'escape', 'tab', 'backspace', 'return', 'enter']:
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
                    scaled_surf = pygame.transform.scale(surf, (window_w, window_h))
                    screen.blit(scaled_surf, (0, 0))
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

                    # CAD button
                    cad_bg_color = (58, 58, 77) if cad_is_hover else (42, 42, 53)
                    cad_border_color = (0, 173, 181)
                    pygame.draw.rect(screen, cad_bg_color, cad_btn_rect, border_radius=4)
                    pygame.draw.rect(screen, cad_border_color, cad_btn_rect, width=1, border_radius=4)
                    
                    cad_text_surf = btn_font.render("Ctrl + Alt + Delete", True, (255, 255, 255))
                    cad_text_rect = cad_text_surf.get_rect(center=cad_btn_rect.center)
                    screen.blit(cad_text_surf, cad_text_rect)
                    
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
                        text_msg = "M├án h├¼nh bß║úo mß║¡t (UAC / Lock Screen) ─æang hiß╗ân thß╗ï ß╗ƒ m├íy Host..."
                    else:
                        text_msg = f"─Éang chuyß╗ân giao diß╗çn... Vui l├▓ng ─æß╗úi {current_countdown} gi├óy..."
                    
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
                
                global client_last_recv_time
                if client_last_recv_time > 0 and time.time() - client_last_recv_time > 10.0:
                    print("[Client] Connection ping timeout. Disconnecting.")
                    exit_due_to_disconnect = True
                    client_running = False
                    break

                pygame.display.flip()
                clock.tick(60)
                
            uninstall_keyboard_hook()
            
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
                            break # Break inner wait loop, outer loop will continue
                        elif hasattr(new_sock, 'fileno'):
                            print("[Client] Received new socket. Resuming session!")
                            sock = new_sock
                            break # Break inner wait loop, outer loop will continue
                    except:
                        pass
                    
                    screen.fill((30, 30, 30))
                    text_surf = msg_font.render(f"Mß║Ñt kß║┐t nß╗æi. ─Éang thß╗¡ kß║┐t nß╗æi lß║íi... {countdown} gi├óy...", True, (255, 255, 255))
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
        pygame.quit()
        if exit_due_to_disconnect:
            print("[Client] Viewer exited due to disconnect. Exit code 99.")
            import sys
            sys.exit(99)
    except Exception as critical_e:
        uninstall_keyboard_hook()
        import traceback
        with open("client_crash.log", "w", encoding="utf-8") as f:
            f.write(f"CRITICAL ERROR IN VIEWER LOOP:\n{traceback.format_exc()}\n")
        try: pygame.quit()
        except: pass
        if exit_due_to_disconnect:
            import sys
            sys.exit(99)

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
    """Kiß╗âm tra xem thread hiß╗çn tß║íi c├│ ─æang ß╗ƒ Secure Desktop (UAC/Winlogon) kh├┤ng.
    Trß║ú vß╗ü True nß║┐u ─æang ß╗ƒ Secure Desktop v├á KH├öNG thß╗â chß╗Ñp m├án h├¼nh b├¼nh th╞░ß╗¥ng."""
    try:
        # Mß╗ƒ Input Desktop vß╗¢i quyß╗ün ─æß╗ìc tß╗æi thiß╗âu (DESKTOP_READOBJECTS = 0x0001)
        hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0001)
        if not hdesk:
            # Kh├┤ng mß╗ƒ ─æ╞░ß╗úc Input Desktop ΓåÆ ─æang bß╗ï Secure Desktop lock
            return True
        name = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetUserObjectInformationW(hdesk, 2, name, ctypes.sizeof(name), None)
        ctypes.windll.user32.CloseDesktop(hdesk)
        desktop_name = name.value.lower()
        # "default" l├á desktop b├¼nh th╞░ß╗¥ng; bß║Ñt kß╗│ t├¬n n├áo kh├íc (vd: "winlogon", "secure") l├á Secure Desktop
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
        # 1. Try to open the active input desktop
        h_input = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0001) # DESKTOP_READOBJECTS
        if not h_input:
            # Cannot open input desktop -> we are blocked
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
        
        # Thiß║┐t lß║¡p icon cho cß╗¡a sß╗ò ch├¡nh
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(True, icon_img)
                self._app_icon_img = icon_img  # Giß╗» reference tr├ính GC
        except Exception as e:
            print(f"[App] Lß╗ùi thiß║┐t lß║¡p icon cß╗¡a sß╗ò: {e}")
        
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
        
        # Cß╗¥ trß║íng th├íi chß╗æng mß╗ƒ nhiß╗üu cß╗¡a sß╗ò ─æiß╗üu khiß╗ân c├╣ng l├║c
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
                print("[Migration] ─É├ú chuyß╗ân ─æß╗òi th├ánh c├┤ng danh s├ích m├íy t├¡nh sang XML m├ú h├│a!")
            except Exception as e:
                print(f"[Migration] Lß╗ùi chuyß╗ân ─æß╗òi: {e}")
        
        # Color Theme (Sleek Dark Mode)
        self.bg_color = "#1E1E24"
        self.card_color = "#2A2A35"
        self.text_white = "#FFFFFF"
        self.text_gray = "#A0A0B0"
        self.btn_color = "#00ADB5"
        self.btn_hover = "#008B90"
        self.entry_bg = "#15151B"
        self.entry_fg = "#FFFFFF"
        self.divider_color = "#3A3A4A"
        
        self.config(bg=self.bg_color)
        
        # Host State Variables
        self.my_id_clean, self.my_id_formatted = get_hwid()
        
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
                print("[Migration] ─É├ú di tr├║ mß║¡t khß║⌐u cß╗æ ─æß╗ïnh sang saved_computers.xml v├á x├│a tß╗çp c┼⌐!")
            except Exception as e:
                print(f"[Config] Lß╗ùi di tr├║ mß║¡t khß║⌐u cß╗æ ─æß╗ïnh: {e}")
        else:
            self.fixed_password = self.load_fixed_password_from_xml()
        self.pass_type_var = tk.StringVar(value="4 chß╗» sß╗æ")
        self.server_socket = None
        self.running_server = True
        self.active_clients = {}
        self.active_viewers = []
        self.current_ip = "─Éang lß║Ñy IP..."
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
        self.status_var = tk.StringVar(value="─Éang kß║┐t nß╗æi tß╗¢i mß║íng ─æ─âng k├╜...")
        self.partner_id_var = tk.StringVar()
        self.partner_pass_var = tk.StringVar()
        self.force_relay_var = tk.BooleanVar(value=False)
        self.startup_var = tk.BooleanVar(value=self.is_startup_enabled())
        
        # Register Trace for Auto-Formatting Partner ID
        self.id_trace_id = self.partner_id_var.trace_add("write", self.format_partner_id)
        
        # Intercept close window button ("X")
        self.protocol("WM_DELETE_WINDOW", self.on_close_window)
        
        # Setup UI
        self.setup_ui()
        
        # Start background services
        threading.Thread(target=self.init_network_services, daemon=True).start()
        
        # Bß║»t ─æß║ºu polling Signaling status tr├¬n main thread (─æß╗Ö tin cß║¡y cao h╞ín self.after tß╗½ background thread)
        self.after(3000, self._poll_signaling_status)
        
        # Restore Event Listener for waking the GUI
        if not self.is_headless:
            threading.Thread(target=self.restore_event_listener_thread, daemon=True).start()

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
        file_menu.add_command(label="Danh s├ích (Saved Computers)", command=self.show_saved_computers_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Tho├ít (Exit)", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # 2. Options Menu
        options_menu = tk.Menu(menubar, tearoff=0)

        # Submenu: Password type
        password_menu = tk.Menu(options_menu, tearoff=0)
        password_menu.add_radiobutton(
            label="4 chß╗» sß╗æ",
            variable=self.pass_type_var, value="4 chß╗» sß╗æ",
            command=self.refresh_password
        )
        password_menu.add_radiobutton(
            label="5 chß╗» sß╗æ",
            variable=self.pass_type_var, value="5 chß╗» sß╗æ",
            command=self.refresh_password
        )
        password_menu.add_radiobutton(
            label="8 k├╜ tß╗▒ (chß╗» + sß╗æ)",
            variable=self.pass_type_var, value="8 k├╜ tß╗▒ (chß╗» + sß╗æ)",
            command=self.refresh_password
        )
        password_menu.add_separator()
        password_menu.add_command(
            label="C├ái mß║¡t khß║⌐u cß╗æ ─æß╗ïnh...",
            command=self.open_set_fixed_password_dialog
        )
        options_menu.add_cascade(label="Mß║¡t khß║⌐u (Password)", menu=password_menu)
        options_menu.add_separator()
        options_menu.add_checkbutton(
            label="Chß║íy khi mß╗ƒ m├íy (Run on Startup)",
            variable=self.startup_var,
            command=self.toggle_startup
        )
        options_menu.add_command(
            label="C├ái Zalo / ─Éiß╗çn thoß║íi",
            command=self.open_set_zalo_phone_dialog
        )
        options_menu.add_separator()
        options_menu.add_command(
            label="C├ái ─æß║╖t m├íy chß╗º...",
            command=self.show_server_settings_dialog
        )
 
        menubar.add_cascade(label="Options", menu=options_menu)
        
        # 3. Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Zalo", command=self.open_zalo)
        help_menu.add_command(label="─Éiß╗çn thoß║íi", command=self.open_phone_dialog)
        help_menu.add_command(label="About", command=self.show_about_dialog)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        # Apply menubar to window
        self.config(menu=menubar)

        # Header Label
        header = tk.Label(self, text="P2P REMOTE DESKTOP", font=("Segoe UI", 16, "bold"), fg=self.btn_color, bg=self.bg_color)
        header.pack(pady=(15, 5))
        
        # Sub-header
        subheader = tk.Label(self, text="─Éiß╗üu khiß╗ân trß╗▒c tuyß║┐n m├íy t├¡nh bß║▒ng HWID", font=("Segoe UI", 9, "italic"), fg=self.text_gray, bg=self.bg_color)
        subheader.pack(pady=(0, 15))
        
        # Main Panels Container
        container = tk.Frame(self, bg=self.bg_color)
        container.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # LEFT PANEL: Allow Remote Control
        left_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        left_panel.place(relx=0.0, rely=0.0, relwidth=0.47, relheight=0.88)
        
        lbl_allow = tk.Label(left_panel, text="CHO PH├ëP ─ÉIß╗ÇU KHIß╗éN", font=("Segoe UI", 11, "bold"), fg=self.btn_color, bg=self.card_color)
        lbl_allow.pack(pady=(15, 10))
        
        lbl_id = tk.Label(left_panel, text="M├ú ID cß╗ºa bß║ín:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.card_color)
        lbl_id.pack(anchor=tk.W, padx=20)
        
        id_frame = tk.Frame(left_panel, bg=self.card_color)
        id_frame.pack(fill=tk.X, padx=20, pady=(5, 12))
        
        self.my_id_label = tk.Label(id_frame, text=self.my_id_formatted, font=("Segoe UI", 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0, height=1)
        self.my_id_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_id_btn = tk.Button(id_frame, text="≡ƒôï", font=("Segoe UI", 10), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=lambda: self.copy_to_clipboard(self.my_id_formatted))
        copy_id_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        lbl_pass = tk.Label(left_panel, text="Mß║¡t khß║⌐u kß║┐t nß╗æi:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.card_color)
        lbl_pass.pack(anchor=tk.W, padx=20)
        
        pass_frame = tk.Frame(left_panel, bg=self.card_color)
        pass_frame.pack(fill=tk.X, padx=20, pady=(5, 5))
        
        self.my_pass_label = tk.Label(pass_frame, text=self.my_password, font=("Segoe UI", 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0)
        self.my_pass_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_pass_btn = tk.Button(pass_frame, text="≡ƒôï", font=("Segoe UI", 10), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=lambda: self.copy_to_clipboard(self.my_password))
        copy_pass_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        refresh_btn = tk.Button(pass_frame, text="Γå╗", font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=self.refresh_password)
        refresh_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # Nh├ún hiß╗ân thß╗ï trß║íng th├íi mß║¡t khß║⌐u cß╗æ ─æß╗ïnh
        self.fixed_pass_indicator = tk.Label(left_panel, text="", font=("Segoe UI", 8, "italic"), fg="#2ECC71", bg=self.card_color)
        self.fixed_pass_indicator.pack(anchor=tk.W, padx=20, pady=(2, 0))
        self.update_fixed_password_indicator()

        # Button to Copy both ID & Password at once
        copy_all_btn = tk.Button(left_panel, text="≡ƒôï Sao ch├⌐p cß║ú ID & Mß║¡t khß║⌐u", font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, command=self.copy_id_and_password)
        copy_all_btn.pack(pady=(8, 0), padx=20, fill=tk.X)
        
        # RIGHT PANEL: Control Remote Computer
        right_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        right_panel.place(relx=0.53, rely=0.0, relwidth=0.47, relheight=0.88)
        
        lbl_control = tk.Label(right_panel, text="─ÉIß╗ÇU KHIß╗éN ─Éß╗ÉI T├üC", font=("Segoe UI", 11, "bold"), fg=self.btn_color, bg=self.card_color)
        lbl_control.pack(pady=(15, 10))
        
        lbl_p_id = tk.Label(right_panel, text="Nhß║¡p ID ─æß╗æi t├íc:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.card_color)
        lbl_p_id.pack(anchor=tk.W, padx=20)
        
        self.entry_p_id = tk.Entry(right_panel, textvariable=self.partner_id_var, font=("Segoe UI", 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, relief=tk.FLAT, bd=4)
        self.entry_p_id.pack(pady=(5, 10), padx=20, fill=tk.X)
        
        lbl_p_pass = tk.Label(right_panel, text="Nhß║¡p Mß║¡t khß║⌐u ─æß╗æi t├íc:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.card_color)
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
        
        self.connect_btn = tk.Button(btn_container, text="Kß║╛T Nß╗ÉI (CONNECT)", font=("Segoe UI", 11, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, command=self.click_connect)
        self.connect_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Add button with a blue "+"
        self.add_partner_btn = tk.Button(btn_container, text="Γ₧ò", font=("Segoe UI", 12, "bold"), fg=self.text_white, bg="#007ACC", activebackground="#005A9E", relief=tk.FLAT, bd=0, width=4, cursor="hand2", command=self.add_current_partner_to_saved)
        self.add_partner_btn.pack(side=tk.RIGHT, padx=(8, 0))

        # Attach Context Menus for Copy & Paste
        self.make_context_menu(self.entry_p_id)
        self.make_context_menu(self.entry_p_pass)
        
        # BOTTOM STATUS BAR
        status_bar = tk.Frame(self, bg=self.entry_bg, height=25)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl_status = tk.Label(status_bar, textvariable=self.status_var, font=("Segoe UI", 8, "italic"), fg="#8A8A9A", bg=self.entry_bg, anchor=tk.W)
        self.lbl_status.pack(fill=tk.BOTH, padx=10, pady=2)
        
        # Khß╗ƒi chß║íy icon khay hß╗ç thß╗æng ngay khi bß║¡t ß╗⌐ng dß╗Ñng
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
            # Chß╗ë ghi lß║íi tß╗ìa ─æß╗Ö khi cß╗¡a sß╗ò ß╗ƒ trß║íng th├íi hiß╗ân thß╗ï b├¼nh th╞░ß╗¥ng v├á ─æang ─æ╞░ß╗úc vß║╜
            if self.wm_state() == "normal" and self.winfo_ismapped():
                geom = self.geometry()
                # Kiß╗âm tra tß╗ìa ─æß╗Ö c├│ hß╗úp lß╗ç kh├┤ng (tr├ính l╞░u tß╗ìa ─æß╗Ö ß║úo khi Windows thu nhß╗Å)
                if "+" in geom:
                    parts = geom.split("+")
                    if len(parts) >= 3:
                        x = int(parts[1])
                        y = int(parts[2])
                        # Tr├ính l╞░u tß╗ìa ─æß╗Ö ß║úo ├óm qu├í lß╗¢n
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
        min_h = int(400 * scale) # T─âng chiß╗üu cao ─æß╗â hiß╗ân thß╗ï ─æß╗º n├║t bß║Ñm
        default_geometry = f"{min_w}x{min_h}"
        self.minsize(min_w, min_h)
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    config = json.load(f)
                    geom = config.get("geometry")
                    if geom:
                        # Bß║úo ─æß║úm k├¡ch th╞░ß╗¢c lu├┤n ch├¡nh x├íc theo scale m├án h├¼nh
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

    def save_window_position(self):
        try:
            # ╞»u ti├¬n lß║Ñy tß╗ìa ─æß╗Ö hoß║ít ─æß╗Öng b├¼nh th╞░ß╗¥ng cuß╗æi c├╣ng ─æ╞░ß╗úc ghi nhß║¡n
            geom = getattr(self, 'last_normal_geometry', None)
            if not geom:
                geom = self.geometry()
                
            # Tr├ính l╞░u tß╗ìa ─æß╗Ö ß║úo/thu nhß╗Å lß╗ùi
            if "+" in geom:
                parts = geom.split("+")
                if len(parts) >= 3:
                    x = int(parts[1])
                    y = int(parts[2])
                    if x <= -30000 or y <= -30000:
                        print(f"[Config] Skip saving minimized geometry: {geom}")
                        return
                        
            with open(self.config_file, "w") as f:
                json.dump({"geometry": geom}, f)
            print(f"[Config] Saved window position: {geom}")
        except Exception as e:
            print(f"[Config] Error saving window config: {e}")

    def copy_id_and_password(self):
        text = f'ID: {self.my_id_formatted}, mß║¡t khß║⌐u: {self.my_password}'
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_status("─É├ú sao ch├⌐p cß║ú ID & Mß║¡t khß║⌐u!")

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text.strip())
        self.update_status(f"─É├ú sao ch├⌐p v├áo bß╗Ö nhß╗¢ tß║ím: {text.strip()}")

    def make_context_menu(self, entry):
        menu = tk.Menu(entry, tearoff=0)
        menu.add_command(label="Cß║»t (Cut)", command=lambda: entry.event_generate("<<Cut>>"))
        menu.add_command(label="Sao ch├⌐p (Copy)", command=lambda: entry.event_generate("<<Copy>>"))
        menu.add_command(label="D├ín (Paste)", command=lambda: entry.event_generate("<<Paste>>"))
        menu.add_command(label="Chß╗ìn tß║Ñt cß║ú (Select All)", command=lambda: entry.event_generate("<<SelectAll>>"))
        
        # Giß╗» tham chiß║┐u mß║ính (Strong Reference) tr├ính r├íc hß╗ç thß╗æng l├ám mß║Ñt menu
        entry.menu = menu
        
        # Bß║»t chuß╗Öt phß║úi tr├¬n cß║ú Windows (Button-3) v├á mß╗Öt sß╗æ Touchpad/Mac (Button-2)
        entry.bind("<Button-3>", lambda e: entry.menu.post(e.x_root, e.y_root))
        entry.bind("<Button-2>", lambda e: entry.menu.post(e.x_root, e.y_root))

    def refresh_password(self):
        import string
        ptype = self.pass_type_var.get()
        if ptype == "5 chß╗» sß╗æ":
            self.my_password = str(random.randint(10000, 99999))
        elif ptype == "8 k├╜ tß╗▒ (chß╗» + sß╗æ)":
            chars = string.ascii_letters + string.digits
            self.my_password = ''.join(random.choices(chars, k=8))
        else:  # Mß║╖c ─æß╗ïnh: 4 chß╗» sß╗æ
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
                
        self.my_pass_label.config(text=self.my_password)
        
    def show_saved_computers_dialog(self):
        if hasattr(self, 'saved_computers_dialog') and self.saved_computers_dialog.winfo_exists():
            self.saved_computers_dialog.lift()
            self.saved_computers_dialog.focus_force()
            return
            
        dialog = tk.Toplevel(self)
        dialog.withdraw()  # ß║¿n ngay khi khß╗ƒi tß║ío ─æß╗â tr├ính bß╗ï nh├íy ß╗ƒ g├│c tr├¬n b├¬n tr├íi m├án h├¼nh
        self.saved_computers_dialog = dialog
        dialog.title("Danh s├ích M├íy t├¡nh")
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
        dialog.deiconify()  # Chß╗ë hiß╗ân thß╗ï sau khi ─æ├ú t├¡nh to├ín c─ân giß╗»a ho├án hß║úo!

        # Top title
        lbl_title = tk.Label(dialog, text="DANH S├üCH M├üY T├ìNH ─É├â L╞»U", font=("Segoe UI", 12, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        # Thanh T├¼m kiß║┐m
        search_frame = tk.Frame(dialog, bg=self.bg_color)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        search_inner = tk.Frame(search_frame, bg="#2A2A3D", highlightthickness=1, highlightbackground=self.divider_color)
        search_inner.pack(fill=tk.X)
        
        lbl_search_icon = tk.Label(search_inner, text="≡ƒöì", font=("Segoe UI", 9), fg=self.text_gray, bg="#2A2A3D")
        lbl_search_icon.pack(side=tk.LEFT, padx=(8, 5), pady=4)
        
        search_var = tk.StringVar()
        entry_search = tk.Entry(search_inner, textvariable=search_var, font=("Segoe UI", 9), fg=self.text_white, bg="#2A2A3D", bd=0, insertbackground=self.text_white)
        entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4, padx=(0, 8))
        
        # Thiß║┐t lß║¡p Placeholder chuy├¬n nghiß╗çp
        entry_search.insert(0, "T├¼m kiß║┐m theo t├¬n hoß║╖c ID...")
        entry_search.configure(fg=self.text_gray)
        
        def on_focus_in(event):
            if entry_search.get() == "T├¼m kiß║┐m theo t├¬n hoß║╖c ID...":
                entry_search.delete(0, tk.END)
                entry_search.configure(fg=self.text_white)
                
        def on_focus_out(event):
            if entry_search.get() == "":
                entry_search.insert(0, "T├¼m kiß║┐m theo t├¬n hoß║╖c ID...")
                entry_search.configure(fg=self.text_gray)
                
        entry_search.bind("<FocusIn>", on_focus_in)
        entry_search.bind("<FocusOut>", on_focus_out)
        
        def on_search_change(*args):
            val = search_var.get()
            if val == "T├¼m kiß║┐m theo t├¬n hoß║╖c ID...":
                return
            refresh_list()
            
        search_var.trace_add("write", on_search_change)

        def load_computers():
            return self.load_saved_computers()

        def save_computers(lst):
            self.save_saved_computers(lst)

        # Container for the list (Sß║╜ pack ß╗ƒ cuß╗æi c├╣ng sau khi ─æ├ú pack bottom_frame ─æß╗â tr├ính bß╗ï ─æ├¿/cß║»t n├║t)
        list_container = tk.Frame(dialog, bg=self.card_color)

        # Canvas & Scrollbar for scrollable area
        canvas = tk.Canvas(list_container, bg=self.card_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.card_color)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW, width=420)
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
            # Giß╗» cß╗¡a sß╗ò Danh s├ích M├íy t├¡nh tiß║┐p tß╗Ñc hiß╗ân thß╗ï theo y├¬u cß║ºu ng╞░ß╗¥i d├╣ng
            # Trigger connection immediately
            self.click_connect()

        def delete_computer(item):
            if self.show_custom_question("X├│a m├íy t├¡nh", f"Bß║ín c├│ chß║»c muß╗æn x├│a '{item['name']}' khß╗Åi danh s├ích?", parent=dialog):
                computers = load_computers()
                computers = [c for c in computers if not (c["id"] == item["id"] and c["name"] == item["name"])]
                save_computers(computers)
                refresh_list()

        def reorder_list():
            if not scrollable_frame.winfo_exists(): return
            cards = scrollable_frame.winfo_children()
            cards = [c for c in cards if hasattr(c, 'comp_id')]
            if not cards: return
            
            def get_is_online(c):
                if c.comp_id in self.status_dots_widgets:
                    widgets = self.status_dots_widgets[c.comp_id]
                    if widgets and widgets[0].winfo_exists():
                        return widgets[0].cget("fg") == "#00F5D4"
                return False

            cards.sort(key=lambda c: (not get_is_online(c), c.comp_name.lower()))
            for c in cards:
                c.pack_forget()
            for c in cards:
                c.pack(fill=tk.X, pady=(0, 6), padx=(0, 10))

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
            if query == "t├¼m kiß║┐m theo t├¬n hoß║╖c id...":
                query = ""

            computers = load_computers()
            
            # 1. Sß║»p xß║┐p danh s├ích (Online l├¬n tr├¬n, sau ─æ├│ theo t├¬n)
            computers.sort(key=lambda x: (not current_online.get(x["id"].replace(" ", ""), False), x["name"].lower()))
            
            # 2. Lß╗ìc theo tß╗½ kh├│a t├¼m kiß║┐m (t├¬n hoß║╖c ID)
            if query:
                computers = [c for c in computers if query in c["name"].lower() or query in c["id"].replace(" ", "")]

            if not computers:
                txt = "Kh├┤ng t├¼m thß║Ñy m├íy t├¡nh ph├╣ hß╗úp." if query else "Ch╞░a c├│ m├íy t├¡nh n├áo ─æ╞░ß╗úc l╞░u.\nBß║Ñm n├║t th├¬m b├¬n d╞░ß╗¢i ─æß╗â tß║ío mß╗¢i."
                lbl_empty = tk.Label(scrollable_frame, text=txt, font=("Segoe UI", 9, "italic"), fg=self.text_gray, bg=self.card_color, justify=tk.CENTER)
                lbl_empty.pack(pady=40, fill=tk.X, expand=True)
                return

            for comp in computers:
                # Card for each saved computer
                card = tk.Frame(scrollable_frame, bg=self.bg_color, pady=8, padx=12, highlightthickness=1, highlightbackground=self.divider_color)
                card.comp_id = comp["id"].replace(" ", "")
                card.comp_name = comp["name"]
                card.pack(fill=tk.X, pady=(0, 6), padx=(0, 10))

                info_frame = tk.Frame(card, bg=self.bg_color)
                info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                # Title frame to place the status indicator dot next to the name
                title_frame = tk.Frame(info_frame, bg=self.bg_color)
                title_frame.pack(fill=tk.X)

                # Status dot: Unicode circle, initially Gray (checking)
                dot_lbl = tk.Label(title_frame, text="ΓùÅ", font=("Segoe UI", 13, "bold"), fg="#8A8A9A", bg=self.bg_color)
                dot_lbl.pack(side=tk.LEFT, padx=(0, 5))

                name_lbl = tk.Label(title_frame, text=comp["name"], font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.bg_color, anchor=tk.W)
                name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

                id_lbl = tk.Label(info_frame, text=f"ID: {comp['id']}", font=("Segoe UI", 8), fg=self.text_gray, bg=self.bg_color, anchor=tk.W)
                id_lbl.pack(fill=tk.X, pady=(2, 0))

                actions_frame = tk.Frame(card, bg=self.bg_color)
                actions_frame.pack(side=tk.RIGHT, fill=tk.Y)

                # Connect Button
                connect_btn = tk.Button(
                    actions_frame, text="Kß║┐t nß╗æi", font=("Segoe UI", 8, "bold"),
                    fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
                    relief=tk.FLAT, bd=0, padx=8, pady=3, cursor="hand2",
                    command=lambda c=comp: connect_computer(c)
                )
                connect_btn.pack(side=tk.LEFT, padx=3)

                # Edit Button
                edit_btn = tk.Button(
                    actions_frame, text="Sß╗¡a", font=("Segoe UI", 8, "bold"),
                    fg=self.text_white, bg="#F39C12", activebackground="#D35400",
                    relief=tk.FLAT, bd=0, padx=8, pady=3, cursor="hand2",
                    command=lambda c=comp: self.open_edit_computer_dialog(c, dialog, refresh_list)
                )
                edit_btn.pack(side=tk.LEFT, padx=3)

                # Delete Button
                delete_btn = tk.Button(
                    actions_frame, text="X├│a", font=("Segoe UI", 8, "bold"),
                    fg=self.text_white, bg="#E05252", activebackground="#C0392B",
                    relief=tk.FLAT, bd=0, padx=8, pady=3, cursor="hand2",
                    command=lambda c=comp: delete_computer(c)
                )
                delete_btn.pack(side=tk.LEFT, padx=3)

                # Register the dot widget and dispatch status check
                clean_id = comp["id"].replace(" ", "")
                if clean_id not in self.status_dots_widgets:
                    self.status_dots_widgets[clean_id] = []
                self.status_dots_widgets[clean_id].append(dot_lbl)
                self.query_computer_status(clean_id)

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
                    btn_refresh.config(text=f"≡ƒöä L├ám mß╗¢i ({seconds_left}s)")
                    seconds_left -= 1
                    if dialog.winfo_exists():
                        dialog.after(1000, update_timer)
                else:
                    if dialog.winfo_exists():
                        btn_refresh.config(
                            state="normal", text="≡ƒöä L├ám mß╗¢i",
                            fg=self.text_white, bg="#2ECC71",
                            cursor="hand2"
                        )
                        
            btn_refresh.config(state="disabled", text="≡ƒöä L├ám mß╗¢i (30s)", bg="#2A2A35", fg="#8A8A9A", cursor="arrow")
            update_timer()

        btn_add = tk.Button(
            bottom_frame, text="+ Th├¬m Mß╗¢i", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2", command=open_add_dialog
        )
        btn_add.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

        btn_refresh = tk.Button(
            bottom_frame, text="≡ƒöä L├ám mß╗¢i", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg="#2ECC71", activebackground="#27AE60",
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2",
            command=lambda: [refresh_list(), start_refresh_cooldown()]
        )
        btn_refresh.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        btn_close = tk.Button(
            bottom_frame, text="─É├│ng", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2", command=on_dialog_destroy
        )
        btn_close.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))

        # Pack list_container sau c├╣ng ─æß╗â lß║Ñp ─æß║ºy phß║ºn diß╗çn t├¡ch c├▓n lß║íi ß╗ƒ giß╗»a Search Bar v├á Bottom Buttons!
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
        add_win.withdraw()  # ß║¿n ngay khi khß╗ƒi tß║ío ─æß╗â tr├ính bß╗ï nh├íy
        add_win.title("Th├¬m M├íy t├¡nh")
        add_win.resizable(False, False)
        add_win.configure(bg=self.bg_color)
        add_win.transient(parent)
        add_win.grab_set()

        # Center add window
        add_win.update_idletasks()
        aw = 320
        ah = 300
        ax = parent.winfo_x() + (parent.winfo_width() - aw) // 2
        ay = parent.winfo_y() + (parent.winfo_height() - ah) // 2
        add_win.geometry(f"{aw}x{ah}+{ax}+{ay}")
        add_win.deiconify()  # Chß╗ë hiß╗ân thß╗ï sau khi ─æ├ú t├¡nh to├ín c─ân giß╗»a ho├án hß║úo!

        lbl_add_title = tk.Label(add_win, text="TH├èM M├üY T├ìNH Mß╗ÜI", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_add_title.pack(pady=(12, 10))

        lbl_name = tk.Label(add_win, text="T├¬n gß╗ìi gß╗úi nhß╗¢:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_name.pack(anchor=tk.W, padx=20)
        entry_name = tk.Entry(add_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_name.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_name.focus()

        lbl_comp_id = tk.Label(add_win, text="ID ─æß╗æi t├íc:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_id.pack(anchor=tk.W, padx=20)
        entry_comp_id = tk.Entry(add_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_id.pack(fill=tk.X, padx=20, pady=(3, 8))
        if initial_id:
            entry_comp_id.insert(0, initial_id)

        lbl_comp_pass = tk.Label(add_win, text="Mß║¡t khß║⌐u:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_pass.pack(anchor=tk.W, padx=20)
        entry_comp_pass = tk.Entry(add_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_pass.pack(fill=tk.X, padx=20, pady=(3, 12))
        if initial_pass:
            entry_comp_pass.insert(0, initial_pass)

        def load_computers():
            return self.load_saved_computers()

        def save_computers(lst):
            self.save_saved_computers(lst)

        def save_new():
            name = entry_name.get().strip()
            cid = entry_comp_id.get().strip()
            cpass = entry_comp_pass.get().strip()

            if not name or not cid or not cpass:
                self.show_custom_error("Lß╗ùi nhß║¡p liß╗çu", "Vui l├▓ng ─æiß╗ün ─æß║ºy ─æß╗º c├íc th├┤ng tin!", parent=add_win)
                return

            computers = load_computers()
            for c in computers:
                if c["id"] == cid and c["name"] == name:
                    self.show_custom_error("Tr├╣ng lß║╖p", "M├íy t├¡nh n├áy ─æ├ú tß╗ôn tß║íi trong danh s├ích!", parent=add_win)
                    return

            computers.append({
                "name": name,
                "id": cid,
                "password": cpass
            })
            save_computers(computers)
            if on_save:
                on_save()
            if not parent_win:
                self.show_custom_info("Th├ánh c├┤ng", f"─É├ú l╞░u m├íy t├¡nh '{name}' v├áo danh s├ích th├ánh c├┤ng!", parent=add_win)
            add_win.destroy()

        btn_add_frame = tk.Frame(add_win, bg=self.bg_color)
        btn_add_frame.pack(fill=tk.X, padx=20, pady=5)

        btn_save = tk.Button(
            btn_add_frame, text="L╞░u lß║íi", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=save_new
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_add_frame, text="Hß╗ºy bß╗Å", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=add_win.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def open_edit_computer_dialog(self, item, parent_win, on_save):
        parent = parent_win
        
        edit_win = tk.Toplevel(parent)
        edit_win.withdraw()  # ß║¿n ngay khi khß╗ƒi tß║ío ─æß╗â tr├ính bß╗ï nh├íy
        edit_win.title("Sß╗¡a th├┤ng tin")
        edit_win.resizable(False, False)
        edit_win.configure(bg=self.bg_color)
        edit_win.transient(parent)
        edit_win.grab_set()

        # Center edit window
        edit_win.update_idletasks()
        ew = 320
        eh = 300
        ex = parent.winfo_x() + (parent.winfo_width() - ew) // 2
        ey = parent.winfo_y() + (parent.winfo_height() - eh) // 2
        edit_win.geometry(f"{ew}x{eh}+{ex}+{ey}")
        edit_win.deiconify()  # Chß╗ë hiß╗ân thß╗ï sau khi ─æ├ú t├¡nh to├ín c─ân giß╗»a ho├án hß║úo!

        lbl_edit_title = tk.Label(edit_win, text="Cß║¼P NHß║¼T TH├öNG TIN", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_edit_title.pack(pady=(12, 10))

        lbl_name = tk.Label(edit_win, text="T├¬n gß╗ìi gß╗úi nhß╗¢:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_name.pack(anchor=tk.W, padx=20)
        entry_name = tk.Entry(edit_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_name.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_name.insert(0, item["name"])
        entry_name.focus()

        lbl_comp_id = tk.Label(edit_win, text="ID ─æß╗æi t├íc:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_id.pack(anchor=tk.W, padx=20)
        entry_comp_id = tk.Entry(edit_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_id.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_comp_id.insert(0, item["id"])

        lbl_comp_pass = tk.Label(edit_win, text="Mß║¡t khß║⌐u mß╗¢i:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_pass.pack(anchor=tk.W, padx=20)
        entry_comp_pass = tk.Entry(edit_win, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_pass.pack(fill=tk.X, padx=20, pady=(3, 12))
        entry_comp_pass.insert(0, item["password"])

        def load_computers():
            return self.load_saved_computers()

        def save_computers(lst):
            self.save_saved_computers(lst)

        def save_edit():
            name = entry_name.get().strip()
            new_id = entry_comp_id.get().strip()
            cpass = entry_comp_pass.get().strip()

            if not name or not new_id or not cpass:
                self.show_custom_error("Lß╗ùi nhß║¡p liß╗çu", "Vui l├▓ng ─æiß╗ün ─æß║ºy ─æß╗º c├íc th├┤ng tin!", parent=edit_win)
                return

            computers = load_computers()
            updated = False
            for c in computers:
                if c["id"] == item["id"] and c["name"] == item["name"]:
                    c["name"] = name
                    c["id"] = new_id
                    c["password"] = cpass
                    updated = True
                    break
            
            if updated:
                save_computers(computers)
                if on_save:
                    on_save()
                edit_win.destroy()
            else:
                self.show_custom_error("Lß╗ùi", "Kh├┤ng t├¼m thß║Ñy m├íy t├¡nh t╞░╞íng ß╗⌐ng ─æß╗â sß╗¡a!", parent=edit_win)

        btn_edit_frame = tk.Frame(edit_win, bg=self.bg_color)
        btn_edit_frame.pack(fill=tk.X, padx=20, pady=5)

        btn_save = tk.Button(
            btn_edit_frame, text="L╞░u lß║íi", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=save_edit
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_edit_frame, text="Hß╗ºy bß╗Å", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=edit_win.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

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
                    
                    name = decrypt_text(name_node.text) if name_node is not None else ""
                    cid = decrypt_text(id_node.text) if id_node is not None else ""
                    cpass = decrypt_text(pass_node.text) if pass_node is not None else ""
                    
                    if cid:
                        lst.append({
                            "name": name,
                            "id": cid,
                            "password": cpass
                        })
            except Exception as e:
                print(f"[Config] Lß╗ùi tß║úi XML: {e}")
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
                
            for comp in lst:
                comp_node = ET.SubElement(root, "computer")
                name_node = ET.SubElement(comp_node, "name")
                name_node.text = encrypt_text(comp["name"])
                
                id_node = ET.SubElement(comp_node, "id")
                id_node.text = encrypt_text(comp["id"])
                
                pass_node = ET.SubElement(comp_node, "password")
                pass_node.text = encrypt_text(comp["password"])
                
            if hasattr(ET, "indent"):
                ET.indent(root, space="  ")
                
            tree = ET.ElementTree(root)
            tree.write(computers_file, encoding="utf-8", xml_declaration=True)
        except Exception as e:
            print(f"[Config] Lß╗ùi l╞░u XML: {e}")

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
                print(f"[Config] Lß╗ùi ─æß╗ìc mß║¡t khß║⌐u cß╗æ ─æß╗ïnh tß╗½ XML: {e}")
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
            print(f"[Config] Lß╗ùi l╞░u XML: {e}")

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
                print(f"[Config] Lß╗ùi ─æß╗ìc Zalo/─Éiß╗çn thoß║íi tß╗½ XML: {e}")
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
            print(f"[Config] Lß╗ùi l╞░u Zalo/─Éiß╗çn thoß║íi v├áo XML: {e}")

    def open_set_zalo_phone_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("C├ái Zalo / ─Éiß╗çn thoß║íi")
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

        lbl_title = tk.Label(dialog, text="C├ÇI ─Éß║╢T ZALO / ─ÉIß╗åN THOß║áI", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        desc_text = "Nhß║¡p sß╗æ ─æiß╗çn thoß║íi hoß║╖c li├¬n kß║┐t Zalo cß╗ºa bß║ín.\nClient ─æiß╗üu khiß╗ân m├íy bß║ín c├│ thß╗â click Help -> Zalo\n─æß╗â trß╗▒c tiß║┐p nhß║»n tin cho bß║ín."
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
            self.show_custom_info("Th├ánh c├┤ng", "─É├ú l╞░u th├┤ng tin li├¬n hß╗ç Zalo / ─Éiß╗çn thoß║íi th├ánh c├┤ng!", parent=dialog)
            dialog.destroy()

        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=30, pady=5)

        btn_save = tk.Button(
            btn_frame, text="L╞░u lß║íi", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=save_val
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_frame, text="Hß╗ºy bß╗Å", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def show_server_settings_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("C├ái ─æß║╖t M├íy chß╗º (Signaling Server)")
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

        lbl_title = tk.Label(dialog, text="Cß║ñU H├îNH M├üY CHß╗ª SIGNALING", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        desc_text = "Nhß║¡p danh s├ích t├¬n miß╗ün hoß║╖c IP m├íy chß╗º\n(C├ích nhau bß║▒ng dß║Ñu phß║⌐y ─æß╗â dß╗▒ ph├▓ng)"
        lbl_desc = tk.Label(dialog, text=desc_text, font=("Segoe UI", 8, "italic"), fg=self.text_gray, bg=self.bg_color, justify=tk.CENTER)
        lbl_desc.pack(pady=(0, 10))

        form_frame = tk.Frame(dialog, bg=self.bg_color)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=30)

        lbl_hosts = tk.Label(form_frame, text="Danh s├ích M├íy chß╗º:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
        lbl_hosts.pack(anchor=tk.W)
        
        entry_hosts = tk.Entry(form_frame, font=("Segoe UI", 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_hosts.pack(fill=tk.X, pady=(3, 10))
        
        lbl_port = tk.Label(form_frame, text="Cß╗òng kß║┐t nß╗æi (Port):", font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color)
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
                self.show_custom_error("Lß╗ùi", "Vui l├▓ng nhß║¡p ─æß║ºy ─æß╗º th├┤ng tin!", parent=dialog)
                return
                
            try:
                new_port = int(new_port_str)
            except ValueError:
                self.show_custom_error("Lß╗ùi", "Cß╗òng kß║┐t nß╗æi (Port) phß║úi l├á sß╗æ!", parent=dialog)
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
                
                self.show_custom_info("Th├ánh c├┤ng", "─É├ú cß║¡p nhß║¡t m├íy chß╗º th├ánh c├┤ng!\nß╗¿ng dß╗Ñng sß║╜ sß╗¡ dß╗Ñng cß║Ñu h├¼nh mß╗¢i cho c├íc kß║┐t nß╗æi tiß║┐p theo.", parent=dialog)
                dialog.destroy()
            except Exception as e:
                self.show_custom_error("Lß╗ùi", f"Kh├┤ng thß╗â l╞░u file server.ini: {e}", parent=dialog)

        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=30, pady=10)
        
        btn_save = tk.Button(
            btn_frame, text="L╞░u lß║íi", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=save_config
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        
        btn_cancel = tk.Button(
            btn_frame, text="Hß╗ºy bß╗Å", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def update_fixed_password_indicator(self):
        if hasattr(self, 'fixed_pass_indicator'):
            if self.fixed_password:
                self.fixed_pass_indicator.config(text="ΓùÅ Mß║¡t khß║⌐u cß╗æ ─æß╗ïnh: ─Éang hoß║ít ─æß╗Öng")
            else:
                self.fixed_pass_indicator.config(text="")

    def open_set_fixed_password_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("Mß║¡t khß║⌐u cß╗æ ─æß╗ïnh")
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

        lbl_title = tk.Label(dialog, text="C├ÇI ─Éß║╢T Mß║¼T KHß║¿U Cß╗É ─Éß╗èNH", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        desc_text = "─Éß║╖t mß║¡t khß║⌐u cß╗æ ─æß╗ïnh gi├║p ─æß╗æi t├íc kß║┐t nß╗æi v├áo\nm├íy cß╗ºa bß║ín m├á kh├┤ng cß║ºn hß╗Åi mß║¡t khß║⌐u ngß║½u nhi├¬n.\n(─Éß╗â trß╗æng ─æß╗â tß║»t t├¡nh n─âng n├áy)"
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
            dialog, text="Hiß╗ân thß╗ï mß║¡t khß║⌐u", font=("Segoe UI", 8),
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
                self.show_custom_info("Th├ánh c├┤ng", "─É├ú l╞░u mß║¡t khß║⌐u cß╗æ ─æß╗ïnh th├ánh c├┤ng!", parent=dialog)
            else:
                self.show_custom_info("Th├ánh c├┤ng", "─É├ú tß║»t mß║¡t khß║⌐u cß╗æ ─æß╗ïnh th├ánh c├┤ng!", parent=dialog)
            dialog.destroy()

        # Buttons
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=30, pady=(5, 10))

        btn_save = tk.Button(
            btn_frame, text="L╞░u lß║íi", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=save_password
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_frame, text="Hß╗ºy bß╗Å", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
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
                self.show_custom_info("Th├ánh c├┤ng", "─É├ú bß║¡t t├¡nh n─âng chß║íy khi mß╗ƒ m├íy th├ánh c├┤ng!")
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
                self.show_custom_info("Th├ánh c├┤ng", "─É├ú tß║»t t├¡nh n─âng chß║íy khi mß╗ƒ m├íy th├ánh c├┤ng!")
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[Startup] Failed to modify registry: {e}")
            self.show_custom_error("Thß║Ñt bß║íi", f"Kh├┤ng thß╗â thay ─æß╗òi c├ái ─æß║╖t Registry: {e}")
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
            dialog.title("Li├¬n hß╗ç Zalo")
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
            
            lbl_title = tk.Label(dialog, text="CHß╗îN ─Éß╗ÉI T├üC ─Éß╗é LI├èN Hß╗å ZALO", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
            lbl_title.pack(pady=(12, 10))
            
            for v in self.active_viewers:
                c_name = v["computer_name"] or "Kh├┤ng r├╡"
                p_val = v["zalo_phone"]
                display_text = f"{c_name} ({p_val if p_val else 'Kh├┤ng c├│ sß╗æ'})"
                
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
        dialog.title("Li├¬n hß╗ç Zalo")
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

        title_text = "LI├èN Hß╗å ZALO"
        if comp_name:
            title_text = f"ZALO: {comp_name.upper()}"
            
        lbl_title = tk.Label(dialog, text=title_text, font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        lbl_phone = tk.Label(dialog, text="Ch╞░a c├│ li├¬n lß║íc", font=("Segoe UI", 16, "bold"), fg="#2ECC71", bg=self.entry_bg, bd=0, height=1, width=20)
        lbl_phone.pack(pady=(5, 15))

        btn_ok = tk.Button(
            dialog, text="─É├│ng", font=("Segoe UI", 9, "bold"),
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
            dialog.title("Chß╗ìn ─æß╗æi t├íc")
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
            
            lbl_title = tk.Label(dialog, text="CHß╗îN ─Éß╗ÉI T├üC XEM ─ÉIß╗åN THOß║áI", font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
            lbl_title.pack(pady=(12, 10))
            
            for v in self.active_viewers:
                c_name = v["computer_name"] or "Kh├┤ng r├╡"
                p_val = v["zalo_phone"]
                display_text = f"{c_name} ({p_val if p_val else 'Kh├┤ng c├│ sß╗æ'})"
                
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
        dialog.title("─Éiß╗çn thoß║íi li├¬n hß╗ç")
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

        title_text = "Sß╗É ─ÉIß╗åN THOß║áI LI├èN Hß╗å"
        if comp_name:
            title_text = f"─ÉIß╗åN THOß║áI: {comp_name.upper()}"
            
        lbl_title = tk.Label(dialog, text=title_text, font=("Segoe UI", 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        display_text = phone_val if phone_val else "Ch╞░a c├│ li├¬n lß║íc"
        lbl_phone = tk.Label(dialog, text=display_text, font=("Segoe UI", 16, "bold"), fg="#2ECC71", bg=self.entry_bg, bd=0, height=1, width=20)
        lbl_phone.pack(pady=(5, 15))

        btn_ok = tk.Button(
            dialog, text="─É├│ng", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, width=12, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_ok.pack()

    def show_about_dialog(self):
        # Tß║ío cß╗¡a sß╗ò Toplevel mß╗¢i ─æ├│ng vai tr├▓ Modal
        about = tk.Toplevel(self)
        about.title("About")
        about.resizable(False, False)
        about.configure(bg=self.bg_color)
        
        # Thiß║┐t lß║¡p thuß╗Öc t├¡nh Modal (nß╗òi l├¬n tr├¬n cß╗¡a sß╗ò ch├¡nh v├á chß║╖n t╞░╞íng t├íc b├¬n ngo├ái)
        about.transient(self)
        about.grab_set()
        
        # Thiß║┐t kß║┐ giao diß╗çn premium cho dialog About
        title_label = tk.Label(about, text="Easy Remote Desktop", font=("Inter", 13, "bold"), fg=self.text_white, bg=self.bg_color)
        title_label.pack(pady=(15, 2))
        
        ai_label = tk.Label(about, text="AI Pro Version", font=("Inter", 9, "bold"), fg=self.btn_color, bg=self.bg_color)
        ai_label.pack(pady=(0, 5))
        
        contact_label = tk.Label(about, text="Li├¬n hß╗ç: Mr. Tuyß║┐n - 0941 261 771", font=("Inter", 10), fg=self.text_gray, bg=self.bg_color)
        contact_label.pack(pady=(0, 15))
        
        close_btn = tk.Button(about, text="─É├│ng", font=("Inter", 9, "bold"), fg=self.text_white, bg="#E05252", 
                              activeforeground=self.text_white, activebackground="#C04242",
                              bd=0, padx=25, pady=6, cursor="hand2", command=about.destroy)
        close_btn.pack(pady=(0, 15))
        
        # Cß║¡p nhß║¡t layout ─æß╗â lß║Ñy k├¡ch th╞░ß╗¢c h├¼nh hß╗ìc ch├¡nh x├íc
        about.update_idletasks()
        
        # K├¡ch th╞░ß╗¢c cß╗æ ─æß╗ïnh cß╗ºa dialog About
        dialog_w = 320
        dialog_h = 175
        
        # Lß║Ñy th├┤ng sß╗æ tß╗ìa ─æß╗Ö v├á k├¡ch th╞░ß╗¢c cß╗ºa cß╗¡a sß╗ò ch├¡nh UnifiedApp
        parent_x = self.winfo_x()
        parent_y = self.winfo_y()
        parent_w = self.winfo_width()
        parent_h = self.winfo_height()
        
        # T├¡nh to├ín tß╗ìa ─æß╗Ö x, y ─æß╗â c─ân ch├¡nh x├íc giß╗»a cß╗¡a sß╗ò ch├¡nh
        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2
        
        # ├üp dß╗Ñng h├¼nh hß╗ìc h├¼nh chß╗» nhß║¡t c─ân giß╗»a
        about.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        
        # Kh├│a t╞░╞íng t├íc cß╗ºa luß╗ông cho ─æß║┐n khi Modal ─æ├│ng
        self.wait_window(about)

    def query_computer_status(self, clean_id):
        if clean_id == self.my_id_clean:
            self.update_saved_computer_status(clean_id, True)
            return

        sock = getattr(self, 'primary_signaling_socket', None)
        if sock:
            try:
                print(f"[StatusQuery] ─Éang gß╗¡i y├¬u cß║ºu kiß╗âm tra trß║íng th├íi ID: {clean_id}")
                req = json.dumps({"action": "check_online", "target": clean_id})
                with self.signaling_lock:
                    send_msg(sock, req.encode('utf-8'), APP_KEY)
                
                # Sau 1.5s nß║┐u ─æ├¿n LED vß║½n l├á m├áu x├ím (ch╞░a c├│ phß║ún hß╗ôi) th├¼ tß╗▒ ─æß╗Öng chuyß╗ân sang m├áu ─æß╗Å (Offline)
                self.after(1500, lambda cid=clean_id: self.check_and_default_offline(cid))
            except Exception as e:
                print(f"[StatusQuery] Lß╗ùi gß╗¡i y├¬u cß║ºu status {clean_id}: {e}")
                self.update_saved_computer_status(clean_id, False)
        else:
            print(f"[StatusQuery] Ch╞░a kß║┐t nß╗æi Signaling, mß║╖c ─æß╗ïnh {clean_id} l├á Offline")
            self.update_saved_computer_status(clean_id, False)

    def check_and_default_offline(self, clean_id):
        if clean_id in self.status_dots_widgets:
            widgets = self.status_dots_widgets[clean_id]
            for dot_widget in widgets:
                try:
                    if dot_widget.winfo_exists() and dot_widget.cget("fg") == "#8A8A9A":
                        dot_widget.config(fg="#E05252")  # ─Éß╗Å (Offline)
                except Exception:
                    pass
            if hasattr(self, '_reorder_saved_computers_func'):
                self.after(50, self._reorder_saved_computers_func)

    def update_saved_computer_status(self, partner_id, is_online):
        clean_id = partner_id.replace(" ", "")
        if clean_id in self.status_dots_widgets:
            widgets = self.status_dots_widgets[clean_id]
            for dot_widget in widgets:
                try:
                    if dot_widget.winfo_exists():
                        if is_online:
                            dot_widget.config(fg="#00F5D4")  # Xanh ngß╗ìc (Cyan / Turquoise)
                        else:
                            dot_widget.config(fg="#E05252")  # ─Éß╗Å (Crimson / Coral Red)
                except Exception:
                    pass
            if hasattr(self, '_reorder_saved_computers_func'):
                self.after(50, self._reorder_saved_computers_func)
    def show_custom_info(self, title, message, parent=None):
        if getattr(self, 'is_headless', False):
            print(f"[Info] {title}: {message}")
            return
        import tkinter as tk
        p = parent if parent else self
        
        dialog = tk.Toplevel(p)
        dialog.withdraw()  # ß║¿n ngay khi khß╗ƒi tß║ío ─æß╗â tr├ính bß╗ï nh├íy ß╗ƒ g├│c tr├¬n b├¬n tr├íi m├án h├¼nh
        dialog.title(title)
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.attributes("-topmost", True)
        dialog.transient(p)
        dialog.grab_set()
        
        # Center calculations relative to parent
        dialog.update_idletasks()
        w = 320
        h = 130
        x = p.winfo_x() + (p.winfo_width() - w) // 2
        y = p.winfo_y() + (p.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.deiconify()  # Chß╗ë hiß╗ân thß╗ï sau khi ─æ├ú t├¡nh to├ín c─ân giß╗»a ho├án hß║úo!
        
        # Content frame
        content_frame = tk.Frame(dialog, bg=self.bg_color)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(15, 10))
        
        # Icon & Message side-by-side
        icon_lbl = tk.Label(content_frame, text="Γä╣", font=("Segoe UI", 22), fg=self.btn_color, bg=self.bg_color)
        icon_lbl.pack(side=tk.LEFT, padx=(0, 12))
        
        msg_lbl = tk.Label(content_frame, text=message, font=("Segoe UI", 9), fg=self.text_white, bg=self.bg_color, wraplength=230, justify=tk.LEFT)
        msg_lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # OK Button at bottom
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 12))
        
        btn_ok = tk.Button(
            btn_frame, text="OK", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, width=8, pady=3, cursor="hand2", command=dialog.destroy
        )
        btn_ok.pack(side=tk.RIGHT)
        
        # ─Éß╗úi cho ─æß║┐n khi cß╗¡a sß╗ò Modal n├áy ─æ├│ng ─æß╗â ─æß╗ông bß╗Ö luß╗ông chß║╖n
        self.wait_window(dialog)

    def show_custom_error(self, title, message, parent=None):
        if getattr(self, 'is_headless', False):
            print(f"[Error] {title}: {message}", file=sys.stderr)
            return
        import tkinter as tk
        p = parent if parent else self
        
        dialog = tk.Toplevel(p)
        dialog.withdraw()  # ß║¿n ngay khi khß╗ƒi tß║ío ─æß╗â tr├ính bß╗ï nh├íy ß╗ƒ g├│c tr├¬n b├¬n tr├íi m├án h├¼nh
        dialog.title(title)
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.transient(p)
        dialog.grab_set()
        
        # Center calculations relative to parent
        dialog.update_idletasks()
        w = 320
        h = 130
        x = p.winfo_x() + (p.winfo_width() - w) // 2
        y = p.winfo_y() + (p.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.deiconify()  # Chß╗ë hiß╗ân thß╗ï sau khi ─æ├ú t├¡nh to├ín c─ân giß╗»a ho├án hß║úo!
        
        # Content frame
        content_frame = tk.Frame(dialog, bg=self.bg_color)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(15, 10))
        
        # Icon & Message side-by-side
        icon_lbl = tk.Label(content_frame, text="ΓÜá", font=("Segoe UI", 22), fg="#E05252", bg=self.bg_color)
        icon_lbl.pack(side=tk.LEFT, padx=(0, 12))
        
        msg_lbl = tk.Label(content_frame, text=message, font=("Segoe UI", 9), fg=self.text_white, bg=self.bg_color, wraplength=230, justify=tk.LEFT)
        msg_lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # OK Button at bottom
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 12))
        
        btn_ok = tk.Button(
            btn_frame, text="OK", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg="#E05252", activebackground="#C0392B",
            relief=tk.FLAT, bd=0, width=8, pady=3, cursor="hand2", command=dialog.destroy
        )
        btn_ok.pack(side=tk.RIGHT)
        
        # ─Éß╗úi cho ─æß║┐n khi cß╗¡a sß╗ò Modal n├áy ─æ├│ng ─æß╗â ─æß╗ông bß╗Ö luß╗ông chß║╖n
        self.wait_window(dialog)

    def _show_lan_error_dialog(self, public_ip=""):
        if getattr(self, 'is_headless', False):
            print("[LAN Error] Kß║┐t nß╗æi LAN thß║Ñt bß║íi - Firewall c├│ thß╗â ─æang chß║╖n kß║┐t nß╗æi.")
            return
        import tkinter as tk

        dialog = tk.Toplevel(self)
        dialog.withdraw()
        dialog.title("Lß╗ùi kß║┐t nß╗æi mß║íng LAN")
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

        # ΓöÇΓöÇ HEADER ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        hdr = tk.Frame(dialog, bg="#C0392B", height=5)
        hdr.pack(fill=tk.X)

        title_frame = tk.Frame(dialog, bg=self.bg_color)
        title_frame.pack(fill=tk.X, padx=20, pady=(14, 0))

        tk.Label(title_frame, text="ΓÜá", font=("Segoe UI", 22), fg="#E05252", bg=self.bg_color).pack(side=tk.LEFT, padx=(0, 10))
        title_col = tk.Frame(title_frame, bg=self.bg_color)
        title_col.pack(side=tk.LEFT, fill=tk.BOTH)
        tk.Label(title_col, text="Kß║┐t nß╗æi mß║íng LAN thß║Ñt bß║íi", font=("Segoe UI", 12, "bold"),
                 fg="#E05252", bg=self.bg_color, anchor="w").pack(anchor="w")
        tk.Label(title_col, text="Cß║ú hai m├íy c├╣ng mß║íng nß╗Öi bß╗Ö nh╞░ng kh├┤ng kß║┐t nß╗æi ─æ╞░ß╗úc trß╗▒c tiß║┐p",
                 font=("Segoe UI", 8), fg=self.text_gray, bg=self.bg_color, anchor="w").pack(anchor="w")

        # ΓöÇΓöÇ SEPARATOR ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        tk.Frame(dialog, bg="#2A2A3A", height=1).pack(fill=tk.X, padx=20, pady=(12, 0))

        # ΓöÇΓöÇ TH├öNG TIN Kß╗╕ THUß║¼T ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        info_frame = tk.Frame(dialog, bg="#1A1A2A", bd=0, highlightthickness=1, highlightbackground="#2A2A4A")
        info_frame.pack(fill=tk.X, padx=20, pady=(12, 0))

        tk.Label(info_frame, text="≡ƒôï  Th├┤ng tin kß╗╣ thuß║¡t", font=("Segoe UI", 8, "bold"),
                 fg=self.btn_color, bg="#1A1A2A", anchor="w").pack(fill=tk.X, padx=12, pady=(8, 4))

        rows = [
            ("Public IP ph├ít hiß╗çn", public_ip if public_ip else "N/A"),
            ("Trß║íng th├íi",          "C├╣ng Public IP ΓåÆ c├╣ng Router/Mß║íng nß╗Öi bß╗Ö"),
            ("Ph╞░╞íng thß╗⌐c thß╗¡",     "Kß║┐t nß╗æi TCP trß╗▒c tiß║┐p qua Local IP (LAN)"),
            ("Kß║┐t quß║ú",             "Γ¥î  Tß║Ñt cß║ú ─æß╗ïa chß╗ë LAN ─æß╗üu kh├┤ng phß║ún hß╗ôi"),
        ]
        for label, value in rows:
            row = tk.Frame(info_frame, bg="#1A1A2A")
            row.pack(fill=tk.X, padx=12, pady=2)
            tk.Label(row, text=f"{label}:", font=("Segoe UI", 8), fg=self.text_gray,
                     bg="#1A1A2A", width=22, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, font=("Segoe UI", 8, "bold"), fg=self.text_white,
                     bg="#1A1A2A", anchor="w", wraplength=240, justify=tk.LEFT).pack(side=tk.LEFT, fill=tk.X)
        tk.Frame(info_frame, bg="#1A1A2A", height=6).pack()

        # ΓöÇΓöÇ NGUY├èN NH├éN & C├üCH KHß║«C PHß╗ñC ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        tk.Label(dialog, text="≡ƒöº  C├ích khß║»c phß╗Ñc", font=("Segoe UI", 9, "bold"),
                 fg="#F39C12", bg=self.bg_color, anchor="w").pack(fill=tk.X, padx=20, pady=(12, 4))

        steps = [
            ("1", "Kiß╗âm tra T╞░ß╗¥ng lß╗¡a Windows",
             "V├áo Windows Defender Firewall ΓåÆ Allow an app ΓåÆ ─æß║úm bß║úo RemoteDesktopP2P.exe ─æ╞░ß╗úc ph├⌐p tr├¬n Private & Public network."),
            ("2", "Kiß╗âm tra phß║ºn mß╗üm diß╗çt virus / VPN",
             "Tß║»t tß║ím thß╗¥i c├íc phß║ºn mß╗üm Antivirus hoß║╖c VPN c├│ thß╗â ─æang chß║╖n kß║┐t nß╗æi nß╗Öi bß╗Ö."),
            ("3", "Kiß╗âm tra cß╗òng mß║íng ─æang d├╣ng",
             f"ß╗¿ng dß╗Ñng d├╣ng cß╗òng {BOUND_PORT}. ─Éß║úm bß║úo cß╗òng n├áy ch╞░a bß╗ï chiß║┐m hoß║╖c bß╗ï chß║╖n bß╗ƒi Firewall."),
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

        # ΓöÇΓöÇ BUTTON ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
        tk.Frame(dialog, bg="#2A2A3A", height=1).pack(fill=tk.X, padx=20, pady=(10, 0))
        btn_frame = tk.Frame(dialog, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, padx=20, pady=(8, 14))
        tk.Button(
            btn_frame, text="─É├ú hiß╗âu", font=("Segoe UI", 9, "bold"),
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
        dialog.withdraw()  # ß║¿n ngay khi khß╗ƒi tß║ío ─æß╗â tr├ính bß╗ï nh├íy ß╗ƒ g├│c tr├¬n b├¬n tr├íi m├án h├¼nh
        dialog.title(title)
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.transient(p)
        dialog.grab_set()
        
        # Center calculations relative to parent
        dialog.update_idletasks()
        w = 320
        h = 130
        x = p.winfo_x() + (p.winfo_width() - w) // 2
        y = p.winfo_y() + (p.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.deiconify()  # Chß╗ë hiß╗ân thß╗ï sau khi ─æ├ú t├¡nh to├ín c─ân giß╗»a ho├án hß║úo!
        
        # Content frame
        content_frame = tk.Frame(dialog, bg=self.bg_color)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(15, 10))
        
        # Icon & Message side-by-side
        icon_lbl = tk.Label(content_frame, text="Γ¥ô", font=("Segoe UI", 22), fg="#F39C12", bg=self.bg_color)
        icon_lbl.pack(side=tk.LEFT, padx=(0, 12))
        
        msg_lbl = tk.Label(content_frame, text=message, font=("Segoe UI", 9), fg=self.text_white, bg=self.bg_color, wraplength=230, justify=tk.LEFT)
        msg_lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
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
        
        # N├║t "Kh├┤ng"
        btn_no = tk.Button(
            btn_frame, text="Kh├┤ng", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, width=8, pady=3, cursor="hand2", command=on_no
        )
        btn_no.pack(side=tk.RIGHT, padx=(4, 0))
        
        # N├║t "C├│"
        btn_yes = tk.Button(
            btn_frame, text="C├│", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, width=8, pady=3, cursor="hand2", command=on_yes
        )
        btn_yes.pack(side=tk.RIGHT, padx=(0, 4))
        
        dialog.protocol("WM_DELETE_WINDOW", on_no)
        
        # ─Éß╗úi cho ─æß║┐n khi cß╗¡a sß╗ò Modal n├áy ─æ├│ng ─æß╗â ─æß╗ông bß╗Ö luß╗ông chß║╖n
        self.wait_window(dialog)
        return result[0]

    def update_status(self, text, is_error=False, blink=False, is_success=False):
        def _do_update():
            self.status_var.set(f"Trß║íng th├íi: {text}")
            
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
            elif is_success or "th├ánh c├┤ng" in text.lower():
                self.lbl_status.config(fg="#2ECC71")  # Xanh lß╗Ñc (Emerald Green)
            else:
                self.lbl_status.config(fg="#8A8A9A")
        
        self.after(0, _do_update)

    def _poll_signaling_status(self):
        """Polling loop chß║íy tr├¬n main Tkinter thread - kiß╗âm tra Signaling mß╗ùi 3s v├á cß║¡p nhß║¡t status UI ─æ├íng tin cß║¡y."""
        if not getattr(self, 'running_server', True):
            return
        try:
            current_status = self.status_var.get()
            # Chß╗ë update nß║┐u status ─æang ß╗ƒ c├íc trß║íng th├íi ch╞░a kß║┐t nß╗æi/─æang thß╗¡
            is_pending = any(kw in current_status for kw in [
                "Kh├┤ng thß╗â kß║┐t nß╗æi Signaling",
                "Ch╞░a kß║┐t nß╗æi Signaling",
                "─Éang kß║┐t nß╗æi Signaling",
                "─Éang thß╗¡ lß║íi",
                "chß║┐ ─æß╗Ö nß╗ün",
                "Sß║╡n s├áng kß║┐t nß╗æi",  # c┼⌐ng update nß║┐u ─æang sß║╡n s├áng m├á Signaling ch╞░a confirm
            ])
            if is_pending and getattr(self, 'signaling_sockets', {}):
                self.update_status("Kß║┐t nß╗æi Signaling th├ánh c├┤ng! Sß║╡n s├áng kß║┐t nß╗æi.")
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
            # Kh├┤ng c├│ quyß╗ün Admin ΓåÆ UAC vß║½n sß║╜ d├╣ng Secure Desktop ΓåÆ cß║únh b├ío ng╞░ß╗¥i d├╣ng ß╗ƒ console/log
            print("[Host] WARNING: No Admin rights ΓåÆ PromptOnSecureDesktop cannot be set. UAC prompts may freeze screen.")
        except Exception as e:
            print(f"[Host] Failed to configure registry for UAC: {e}")

    def init_network_services(self):
        # 0. Thß╗¡ tß╗▒ ─æß╗Öng th├¬m rule T╞░ß╗¥ng lß╗¡a v├á cß║Ñu h├¼nh UAC (sß║╜ th├ánh c├┤ng nß║┐u c├│ quyß╗ün Admin)
        self.configure_uac_registry()
        self.add_firewall_rule_for_app()
        
        # 1. Start Host Server first to determine which port is available
        if not self.is_headless and getattr(self, "is_service_active", False):
            print("[Host GUI] Service is active. Skipping local host TCP server startup to avoid conflict.")
            self.server_socket = None
            upnp_success = False
        else:
            self.update_status("─Éang khß╗ƒi ─æß╗Öng Server lß║»ng nghe...")
            self.start_host_server()
            
            # 2. Try automatic UPnP Port Forwarding
            self.update_status("─Éang tß╗▒ ─æß╗Öng cß║Ñu h├¼nh Router (UPnP)...")
            upnp_success = attempt_upnp_forward(BOUND_PORT)
        
        # 3. Get Public & Local IPs
        self.update_status("─Éang lß║Ñy th├┤ng vß╗ï tr├¡ mß║íng...")
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
        self.update_status(f"─Éang kß║┐t nß╗æi tß╗¢i c├íc Signaling Server...")
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
            # Hiß╗çn th├┤ng b├ío ─æang chß╗¥ mß╗ùi 2 gi├óy
            elapsed = 8.0 - timeout
            if abs(elapsed - 2.0) < 0.1 or abs(elapsed - 5.0) < 0.1:
                self.update_status(f"─Éang kß║┐t nß╗æi Signaling Server... ({8 - int(timeout)}s)")
            
        if self.signaling_sockets:
            suffix = " (Dß╗ïch vß╗Ñ hoß║ít ─æß╗Öng)" if getattr(self, "is_service_active", False) else ""
            if upnp_success:
                self.update_status(f"Kß║┐t nß╗æi Signaling & Mß╗ƒ cß╗òng Router th├ánh c├┤ng (Cß╗òng {BOUND_PORT})!{suffix}")
            else:
                self.update_status(f"Kß║┐t nß╗æi Signaling th├ánh c├┤ng (Cß╗òng {BOUND_PORT})! Sß║╡n s├áng kß║┐t nß╗æi.{suffix}")
        else:
            suffix = " (Dß╗ïch vß╗Ñ hoß║ít ─æß╗Öng)" if getattr(self, "is_service_active", False) else ""
            self.update_status(f"Ch╞░a kß║┐t nß╗æi Signaling Server. ─Éang thß╗¡ lß║íi ß╗ƒ chß║┐ ─æß╗Ö nß╗ün...{suffix}")


    def signaling_maintainer_thread(self, host):
        retry_delay = 2  # Bß║»t ─æß║ºu retry nhanh (2s), t─âng dß║ºn sau 3 lß║ºn thß║Ñt bß║íi
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
                    # Lu├┤n cß║¡p nhß║¡t status khi kß║┐t nß╗æi th├ánh c├┤ng (kß╗â cß║ú lß║ºn ─æß║ºu sau timeout hoß║╖c sau reconnect)
                    self.after(0, lambda: self.update_status("Kß║┐t nß╗æi Signaling th├ánh c├┤ng! Sß║╡n s├áng kß║┐t nß╗æi."))
                
                # Reset counters khi kß║┐t nß╗æi th├ánh c├┤ng
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
                                self.after(0, lambda: self.update_status("Mß║Ñt kß║┐t nß╗æi to├án bß╗Ö Signaling Server. ─Éang thß╗¡ lß║íi...", is_error=True, blink=True))
            
            time.sleep(retry_delay)
            # T─âng retry_delay sau 3 lß║ºn thß║Ñt bß║íi li├¬n tiß║┐p
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
                
            elif action == "online_status":
                target = res.get("target")
                online = res.get("online", False)
                self.after(0, lambda t=target, o=online: self.update_saved_computer_status(t, o))
                
        except Exception as e:
            print(f"[Signaling] Lß╗ùi xß╗¡ l├╜ tin nhß║»n tß╗½ {host}: {e}")

    def punch_hole_to_client(self, c_ip, c_port):
        # 0. ─Éß╗úi Client thß╗¡ kß║┐t nß╗æi mß║íng LAN tr╞░ß╗¢c (2.0 gi├óy)
        # Viß╗çc n├áy gi├║p giß╗» listener mß╗ƒ ─æß╗â Client c├│ thß╗â kß║┐t nß╗æi nß╗Öi bß╗Ö.
        # ─Éß╗ông thß╗¥i ─æß╗ông bß╗Ö thß╗¥i gian ─æß╗Ñc lß╗ù (Simultaneous Open) vß╗¢i Client (Client timeout LAN l├á 2.0s)
        time.sleep(2.0)
        
        # 1. Tß║ím thß╗¥i ─æ├│ng server_socket ─æß╗â giß║úi ph├│ng port
        if self.server_socket:
            try:
                self.server_socket.close()
            except: pass
            
        success_sock = None
        
        # Spam outbound connections quickly for Simultaneous Open
        for _ in range(20):
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
            
        # 2. Mß╗ƒ lß║íi server_socket bß║Ñt kß╗â ─æß╗Ñc lß╗ù th├ánh c├┤ng hay thß║Ñt bß║íi
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
            print(f"[Host] ─É├ú phß╗Ñc hß╗ôi TCP server lß║»ng nghe tr├¬n port {BOUND_PORT}")
        except Exception as e:
            print(f"[Host] Cß║únh b├ío: Kh├┤ng thß╗â phß╗Ñc hß╗ôi server_socket: {e}")
            
        # 3. Bß║»t tay kß║┐t nß╗æi nß║┐u th├ánh c├┤ng
        if success_sock:
            # Kh├┤i phß╗Ñc timeout vß╗ü None (blocking) cho socket sau khi ─æß╗Ñc lß╗ù th├ánh c├┤ng
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
            self.after(0, lambda: self.show_custom_error("Lß╗ùi hß╗ç thß╗æng", "Kh├┤ng thß╗â chß║íy server! C├íc cß╗òng mß║íng ─æß╗üu bß╗ï chiß║┐m dß╗Ñng hoß║╖c bß╗ï chß║╖n bß╗ƒi T╞░ß╗¥ng lß╗¡a.\nVui l├▓ng kiß╗âm tra lß║íi cß║Ñu h├¼nh mß║íng hoß║╖c tß║»t bß╗¢t ß╗⌐ng dß╗Ñng chiß║┐m cß╗òng."))
            self.update_status("Lß╗ùi khß╗ƒi ─æß╗Öng Server")
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
                        "message": "Sai mß║¡t khß║⌐u kß║┐t nß╗æi hoß║╖c dß╗» liß╗çu kh├┤ng hß╗úp lß╗ç!"
                    }).encode('utf-8')
                    send_msg(conn, err_info, APP_KEY)
                except: pass
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
                
                client_id = data.get("client_id", "Kh├┤ng r├╡")
                client_comp = data.get("computer_name", "Kh├┤ng r├╡")
                fmt_client_id = f"{client_id[:3]} {client_id[3:6]} {client_id[6:9]} {client_id[9:]}" if len(client_id) == 12 else client_id
                
                if client_comp != "Kh├┤ng r├╡":
                    msg_text = f"M├íy t├¡nh [{client_comp}] ─æang ─æiß╗üu khiß╗ân m├íy bß║ín"
                else:
                    msg_text = f"M├íy t├¡nh c├│ ID [{fmt_client_id}] ─æang ─æiß╗üu khiß╗ân m├íy bß║ín"
                    
                self.after(0, lambda: self.show_custom_info("Kß║┐t nß╗æi tß╗½ xa", msg_text))
                
                self.wake_display()
                
                # Tß║»t Nagle's algorithm (TCP_NODELAY) ─æß╗â giß║úm ─æß╗Ö trß╗à tß╗æi ─æa
                try:
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except Exception as e:
                    print(f"[TCP_NODELAY] Lß╗ùi thiß║┐t lß║¡p TCP_NODELAY tr├¬n Host: {e}")
                
                # Cß║Ñu h├¼nh TCP Keep-Alive bß║úo vß╗ç kß║┐t nß╗æi ─æß╗Ñc lß╗ù khß╗Åi bß╗ï ─æ├│ng bß╗ƒi Firewall/Router
                try:
                    conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    conn.ioctl(socket.SIOC_KEEPALIVE_VALS, (1, 1000, 1000))
                except Exception as e:
                    print(f"[KeepAlive] Lß╗ùi cß║Ñu h├¼nh Keep-Alive tr├¬n Host: {e}")
                
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
                                dummy_size = 1572864 # 1.5 MB ─æß╗â nß╗¢i rß╗Öng TCP Window
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
                self.update_status(f"─Éang d├╣ng m├íy chß╗º {addrs_str}")
                
                t_sender = threading.Thread(target=self.host_sender_thread, args=(conn, monitor, client_state, client_pass), daemon=True)
                t_receiver = threading.Thread(target=self.host_receiver_thread, args=(conn, client_state, client_pass), daemon=True)
                
                t_sender.start()
                t_receiver.start()
                
                # Khß╗ƒi chß║íy luß╗ông ─æß╗ông bß╗Ö Clipboard File cho Host
                clipboard_sync_manager.add_socket(conn)
                
                try:
                    t_receiver.join()
                finally:
                    client_state["running"] = False
                    t_sender.join()
                    clipboard_sync_manager.remove_socket(conn)
                    set_windows_graphics_effects(True) # Restore graphics effects upon disconnection
                    
                    print(f"[Host] ─É├ú ─æ├│ng kß║┐t nß╗æi vß╗¢i Client {addr[0]}:{addr[1]}.")
                    
                    if addr in self.active_clients:
                        del self.active_clients[addr]
                        
                    if self.active_clients:
                        addrs_str = ", ".join([str(a[0]) for a in self.active_clients.keys()])
                        self.update_status(f"─Éang bß╗ï ─æiß╗üu khiß╗ân bß╗ƒi {addrs_str}")
                    else:
                        self.update_status(f"─É├ú ─æ├│ng kß║┐t nß╗æi vß╗¢i Client {addr[0]} l├║c {time.strftime('%H:%M:%S')} (Sß║╡n s├áng kß║┐t nß╗æi)")
                        
                    try:
                        force_close_socket(conn)
                    except:
                        pass
            else:
                print("[Host] Password mismatch!")
                err_info = json.dumps({
                    "status": "error",
                    "message": "Sai mß║¡t khß║⌐u kß║┐t nß╗æi!"
                }).encode('utf-8')
                send_msg(conn, err_info, client_pass)
                force_close_socket(conn)
                socket_passwords.pop(conn, None)
        except Exception as e:
            print(f"[Host] Handshake Exception: {e}")
            try:
                err_info = json.dumps({
                    "status": "error",
                    "message": f"Lß╗ùi xß║úy ra tr├¬n m├íy Host:\n{e}"
                }).encode('utf-8')
                send_msg(conn, err_info, locals().get('client_pass'))
            except:
                pass
            force_close_socket(conn)
            socket_passwords.pop(conn, None)
            
    # Host Sender Thread
    def host_sender_thread(self, conn, monitor, client_state, password):
        print("[Host] Started Screen Sender Thread.")
        import io
        
        try:
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, 2000)
        except: pass

        while client_state.get("running", False):
            try:
                # Early check for desktop status
                needs_switch, is_blocked = check_desktop_change()
                if is_blocked:
                    print("[Host] Secure Desktop detected and cannot be accessed. Pausing screen capture...")
                    try:
                        signal = json.dumps({"type": "switching_desktop"}).encode('utf-8')
                        send_msg(conn, signal, password)
                    except:
                        pass
                    time.sleep(0.5)
                    continue

                # Switch thread to active Input Desktop if needed
                if needs_switch:
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
                                    try:
                                        signal = json.dumps({"type": "switching_desktop"}).encode('utf-8')
                                        send_msg(conn, signal, password)
                                    except:
                                        pass
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
                            
                            if cap_w != w or cap_h != h:
                                pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)

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
                                # Mß║íng chß║¡m: Chß╗ë giß║úm chß║Ñt l╞░ß╗úng ß║únh, hß║ín chß║┐ b├│p scale ─æß╗â tr├ính vß╗í khß╗æi pixel
                                quality = max(max(35, base_quality - 20), quality - 5)
                                sleep_time = min(0.3, sleep_time + 0.05)
                                if ema > 0.6:
                                    dyn_scale = max(res_scale, dyn_scale - 0.05)
                            elif ema < 0.20:
                                # Ph╞░╞íng ├ín 2: Dynamic Scaling m╞░ß╗út h╞ín (v╞░ß╗út qua giß╗¢i hß║ín ban ─æß║ºu nß║┐u mß║íng tß╗æt)
                                quality = min(98, quality + 1)
                                sleep_time = max(1.0 / 60, sleep_time - 0.005)
                                dyn_scale = min(1.0, dyn_scale + 0.02)
                                
                            client_state["dyn_quality"] = quality
                            client_state["dyn_sleep_time"] = sleep_time
                            client_state["dyn_scale"] = dyn_scale

                            time.sleep(sleep_time)
                        except mss.exception.ScreenShotError as e:
                            print(f"[Host] Screen capture error (re-initializing): {e}")
                            
                            # Thß╗¡ fallback sang monitors[0] mß╗Öt lß║ºn duy nhß║Ñt.
                            # KH├öNG d├╣ng continue v├¼ nß║┐u monitors[0] c┼⌐ng fail ΓåÆ v├▓ng lß║╖p v├┤ tß║¡n.
                            if len(sct.monitors) > 1 and dynamic_monitor != sct.monitors[0]:
                                print("[Host] Falling back to sct.monitors[0] (Virtual Screen) - one-shot attempt")
                                dynamic_monitor = sct.monitors[0]
                                try:
                                    img2 = sct.grab(dynamic_monitor)
                                    # Fallback th├ánh c├┤ng: cß║¡p nhß║¡t dynamic_monitor v├á tiß║┐p tß╗Ñc
                                    img = img2
                                except Exception:
                                    pass  # Fallback c┼⌐ng fail ΓåÆ r╞íi xuß╗æng break b├¬n d╞░ß╗¢i
                                else:
                                    continue  # Fallback th├ánh c├┤ng ΓåÆ tiß║┐p tß╗Ñc inner loop
                                
                            try:
                                signal = json.dumps({"type": "switching_desktop"}).encode('utf-8')
                                send_msg(conn, signal, password)
                            except: pass
                            time.sleep(1.0)
                            break  # Break inner loop to recreate mss.mss()
                        except Exception as e:
                            import traceback
                            with open("host_error.log", "a") as f:
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
        # Cache ─æß╗â tr├ính gß╗ìi OpenInputDesktop/SetThreadDesktop mß╗ùi v├▓ng lß║╖p
        _last_desk_check_time = 0.0
        _last_desk_name = None
        _DESK_CHECK_INTERVAL = 0.5  # Chß╗ë kiß╗âm tra desktop mß╗ùi 0.5 gi├óy
        last_recv_time = time.time()
        while client_state.get("running", False):
            try:
                # Chß╗¥ 2 gi├óy, nß║┐u kh├┤ng c├│ g├│i tin n├áo th├¼ nhß║ú hß║┐t ph├¡m modifier ─æß╗â chß╗æng kß║╣t
                r, _, _ = select.select([conn], [], [], 2.0)
                if not r:
                    self.host_release_all_modifiers()
                    if time.time() - last_recv_time > 10.0:
                        print("[Host] Connection ping timeout. Disconnecting client.")
                        client_state["running"] = False
                        break
                    continue

                # Chß╗ë kiß╗âm tra/chuyß╗ân desktop khi c├│ g├│i tin ─æß║┐n V├Ç ─æ├ú qua interval
                # ─Éiß╗üu n├áy tr├ính overhead khi mouse_move li├¬n tß╗Ñc v├á tr├ính SetThreadDesktop
                # gß╗ìi qu├í nhiß╗üu lß║ºn (c├│ thß╗â fail nß║┐u hook ─æ├ú ─æ╞░ß╗úc gß║»n v├áo thread)
                now = time.monotonic()
                if now - _last_desk_check_time >= _DESK_CHECK_INTERVAL:
                    _last_desk_check_time = now
                    try:
                        import ctypes as _ct
                        # Lß║Ñy t├¬n desktop hiß╗çn tß║íi ─æß╗â ph├ít hiß╗çn thay ─æß╗òi (UAC/Winlogon)
                        _buf = _ct.create_unicode_buffer(256)
                        _hd_cur = _ct.windll.user32.GetThreadDesktop(_ct.windll.kernel32.GetCurrentThreadId())
                        _ct.windll.user32.GetUserObjectInformationW(_hd_cur, 2, _buf, _ct.sizeof(_buf), None)
                        _cur_name = _buf.value.lower() if _buf.value else None

                        _hdesk_new = _ct.windll.user32.OpenInputDesktop(0, False, 0x02000000)
                        if _hdesk_new:
                            # Lß║Ñy t├¬n cß╗ºa input desktop mß╗¢i
                            _buf2 = _ct.create_unicode_buffer(256)
                            _ct.windll.user32.GetUserObjectInformationW(_hdesk_new, 2, _buf2, _ct.sizeof(_buf2), None)
                            _new_name = _buf2.value.lower() if _buf2.value else None

                            if _new_name != _last_desk_name:
                                # Desktop ─æ├ú thay ─æß╗òi ΓåÆ switch thread sang desktop mß╗¢i
                                if _ct.windll.user32.SetThreadDesktop(_hdesk_new):
                                    _last_desk_name = _new_name
                                    print(f"[Host] Switched input desktop: {_last_desk_name}")
                                    # ─É├│ng handle c┼⌐ sau khi switch th├ánh c├┤ng
                                    if hasattr(self, '_last_hdesk') and self._last_hdesk:
                                        _ct.windll.user32.CloseDesktop(self._last_hdesk)
                                    self._last_hdesk = _hdesk_new
                                    _hdesk_new = None  # Prevent double-close below
                                # else: SetThreadDesktop thß║Ñt bß║íi ΓåÆ giß╗» nguy├¬n desktop c┼⌐
                            # ─É├│ng handle nß║┐u kh├┤ng ─æ╞░ß╗úc l╞░u lß║íi (kh├┤ng c├│ thay ─æß╗òi hoß║╖c switch fail)
                            if _hdesk_new:
                                _ct.windll.user32.CloseDesktop(_hdesk_new)
                    except Exception:
                        pass
                    
                msg = recv_msg(conn, password)
                if not msg:
                    print("[Host] Input Receiver got empty message (Client disconnected).")
                    break
                last_recv_time = time.time()
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
            except Exception as e:
                print(f"[Host] Input Receiver Error: {e}")
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
            self.show_custom_error("Lß╗ùi", "Vui l├▓ng nhß║¡p m├ú ID ─æß╗æi t├íc hß╗úp lß╗ç (12 chß╗» sß╗æ)!")
            return
            
        if not partner_pass:
            self.show_custom_error("Lß╗ùi", "Vui l├▓ng nhß║¡p mß║¡t khß║⌐u ─æß╗æi t├íc!")
            return
            
        self.update_status("─Éang t├¼m ─æß╗ïa chß╗ë IP cß╗ºa ─æß╗æi t├íc tr├¬n dß╗ïch vß╗Ñ danh bß║í...")
        self.connect_btn.config(state=tk.DISABLED)
        
        # Connect inside background thread to prevent UI freezing
        threading.Thread(target=self.connect_to_partner, args=(partner_id, partner_pass), daemon=True).start()
        
    def connect_to_partner(self, partner_id, partner_pass, reconnect_queue=None, retry_count=0, viewer_pid=None):
        if partner_id == getattr(self, "my_id_clean", ""):
            self.after(0, lambda: self.show_custom_info("Th├┤ng b├ío", "Bß║ín kh├┤ng thß╗â kß║┐t nß╗æi tß╗¢i ch├¡nh bß║ín :-)"))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            self.update_status("Kß║┐t nß╗æi bß╗ï hß╗ºy.")
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
            self.update_status(f"─Éang hiß╗ân thß╗ï cß╗¡a sß╗ò ─æiß╗üu khiß╗ân ─æ├ú kß║┐t nß╗æi cß╗ºa {partner_id}...")
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
            self.update_status("Ch╞░a kß║┐t nß╗æi Signaling Server!")
            self.after(0, lambda: self.show_custom_error("Lß╗ùi", "Ch╞░a kß║┐t nß╗æi ─æß║┐n Server B├ío hiß╗çu. Vui l├▓ng kiß╗âm tra lß║íi mß║íng hoß║╖c VPS."))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            return

        req = json.dumps({
            "action": "connect_request",
            "target": partner_id,
            "port": BOUND_PORT,
            "local_ip": self.local_ip,
            "local_port": BOUND_PORT
        }) + '\n'
        
        # Thß╗¡ t├¼m ─æß╗æi t├íc tr├¬n tß║Ñt cß║ú c├íc server ─æang kß║┐t nß╗æi
        sockets_to_try = []
        with self.signaling_lock:
            if getattr(self, 'primary_signaling_socket', None):
                sockets_to_try.append(self.primary_signaling_socket)
            for sock in self.signaling_sockets.values():
                if sock not in sockets_to_try:
                    sockets_to_try.append(sock)
                    
        success = False
        self.update_status("─Éang t├¼m v├á chß╗¥ ─æß╗æi t├íc phß║ún hß╗ôi...")
        
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
                self.update_status(f"Mß║Ñt kß║┐t nß╗æi. ─Éang thß╗¡ kß║┐t nß╗æi lß║íi lß║ºn {retry_count + 1}/30...")
                time.sleep(2)
                self.connect_to_partner(partner_id, partner_pass, reconnect_queue, retry_count + 1, viewer_pid)
                return
                
            self.update_status("Sß║╡n s├áng kß║┐t nß╗æi")
            if not reconnect_queue:
                self.after(0, lambda: self.show_custom_error("Lß╗ùi", "Kh├┤ng thß╗â t├¼m thß║Ñy hoß║╖c ─æß╗æi t├íc ─æang Offline / Tß╗½ chß╗æi kß║┐t nß╗æi."))
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
        
        # 1. Try local IP first (LAN) (Chß╗ë thß╗¡ nß║┐u kh├┤ng ├⌐p buß╗Öc Relay)
        if not self.force_relay_var.get() and local_ip:
            ips_to_try = [ip.strip() for ip in local_ip.split(',') if ip.strip()]
            ports_to_try = [local_port]
            for p in [12345, 12346, 12347, 12348]:
                if p not in ports_to_try:
                    ports_to_try.append(p)
                    
            self.update_status(f"─Éang qu├⌐t kß║┐t nß╗æi nß╗Öi bß╗Ö (LAN)...")
            import select
            
            # Qu├⌐t tuß║ºn tß╗▒ tß╗½ng port (╞░u ti├¬n local_port tr╞░ß╗¢c) ─æß╗â tr├ính lß╗ùi d├¡nh Kaspersky/ß╗⌐ng dß╗Ñng r├íc ß╗ƒ port 12345
            for p in ports_to_try:
                if connected: break
                sockets = []
                for ip in ips_to_try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.setblocking(False)
                    try: s.connect((ip, p))
                    except Exception: pass
                    sockets.append((s, ip, p))
                
                # Chß╗¥ tß╗æi ─æa 0.4s cho mß╗ùi port
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
                                    
                                    # Kß╗âm tra handshake ngay ─æß╗â x├íc minh ─æ├óy c├│ phß║úi Host thß║¡t kh├┤ng
                                    # (Tr├ính tr╞░ß╗¥ng hß╗úp VM NAT hay proxy tß╗▒ ─æß╗Öng nhß║¡n TCP rß╗ôi reset)
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
                    
                # ─É├│ng c├íc socket kh├┤ng d├╣ng tß╗¢i trong batch n├áy
                for s_tuple in sockets:
                    if s_tuple[0] != sock: force_close_socket(s_tuple[0])
                
        # 2. Kß╗╣ thuß║¡t ─æß╗Ñc lß╗ù T╞░ß╗¥ng lß╗¡a (TCP Hole Punching) (Chß╗ë thß╗¡ nß║┐u kh├┤ng ├⌐p buß╗Öc Relay)
        if not self.force_relay_var.get() and not connected:
            if hasattr(self, 'current_ip') and self.current_ip == public_ip:
                print("[Client] Skipping Hole Punching because both peers share the same Public IP (same router).")
                self.update_status("Sß║╡n s├áng kß║┐t nß╗æi")
                self.after(0, lambda pip=public_ip: self._show_lan_error_dialog(pip))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                return
            self.update_status(f"─Éang ─æß╗Ñc lß╗ù T╞░ß╗¥ng lß╗¡a (TCP Hole Punching) tß╗¢i {public_ip}:{port}...")
            print(f"[Client] Initiating Simultaneous Open to {public_ip}:{port}...")
            
            # Tß║ím thß╗¥i ─æ├│ng server_socket b├¬n Client ─æß╗â nh╞░ß╗¥ng port cho outbound connect
            if getattr(self, 'server_socket', None):
                try:
                    self.server_socket.close()
                except: pass
            
            # Li├¬n tß╗Ñc spam kß║┐t nß╗æi cß╗▒c nhanh ─æß╗â ─æß╗Ñc lß╗ù (20 lß║ºn, mß╗ùi lß║ºn 100ms)
            for _ in range(20):
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
                    break
                except Exception:
                    force_close_socket(sock)
                    time.sleep(0.1)
                    
            # Mß╗ƒ lß║íi server_socket bß║Ñt kß╗â ─æß╗Ñc lß╗ù th├ánh c├┤ng hay thß║Ñt bß║íi
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
                print(f"[Client] ─É├ú phß╗Ñc hß╗ôi TCP server lß║»ng nghe tr├¬n port {BOUND_PORT}")
            except Exception as e:
                print(f"[Client] Cß║únh b├ío: Kh├┤ng thß╗â phß╗Ñc hß╗ôi server_socket: {e}")

        if not connected:
            self.update_status("Sß║╡n s├áng kß║┐t nß╗æi")
            self.after(0, lambda: self.show_custom_error("Lß╗ùi kß║┐t nß╗æi", 
                f"Kß╗╣ thuß║¡t ─Éß╗Ñc Lß╗ù T╞░ß╗¥ng Lß╗¡a (Hole Punching) thß║Ñt bß║íi!\n\n"
                f"L├╜ do: Kh├┤ng thß╗â thiß║┐t lß║¡p kß║┐t nß╗æi trß╗▒c tiß║┐p P2P tß╗¢i ─æß╗æi t├íc."
            ))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if sock: force_close_socket(sock)
            return
                
        # Connection succeeded, proceed with handshake
        sock.settimeout(None) # Reset back to blocking
        
        # Tß║»t Nagle's algorithm (TCP_NODELAY) ─æß╗â giß║úm ─æß╗Ö trß╗à tß╗æi ─æa cho cß║ú ─æo tß╗æc ─æß╗Ö v├á ─æiß╗üu khiß╗ân
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception as e:
            print(f"[TCP_NODELAY] Lß╗ùi thiß║┐t lß║¡p TCP_NODELAY tr├¬n Client: {e}")
            
        # Cß║Ñu h├¼nh TCP Keep-Alive bß║úo vß╗ç kß║┐t nß╗æi khß╗Åi bß╗ï ─æ├│ng bß╗ƒi Firewall/Router
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.ioctl(socket.SIOC_KEEPALIVE_VALS, (1, 1000, 1000))
        except Exception as e:
            print(f"[KeepAlive] Lß╗ùi cß║Ñu h├¼nh Keep-Alive tr├¬n Client: {e}")
            
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
                    self.update_status("Sß║╡n s├áng kß║┐t nß╗æi")
                    self.after(0, lambda: self.show_custom_error("Lß╗ùi", "─Éß╗æi t├íc ngß║»t kß║┐t nß╗æi ─æß╗Öt ngß╗Öt!"))
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
                
                # Perform pre-connection speed test (Ping/Latency and Bandwidth) - 2 runs, select highest speed
                self.update_status("─Éang kiß╗âm tra chß║Ñt l╞░ß╗úng mß║íng (Ping & B─âng th├┤ng) lß║ºn 1/2...")
                net_class = "medium"
                net_class_viet = "Trung b├¼nh (Medium)"
                avg_ping = 50.0
                bandwidth = 10.0
                try:
                    runs = []
                    for run_idx in range(2):
                        if run_idx > 0:
                            self.update_status("─Éang kiß╗âm tra chß║Ñt l╞░ß╗úng mß║íng (Ping & B─âng th├┤ng) lß║ºn 2/2...")
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
                                warm_size = 1048576 # 1 MB warm-up ─æß╗â v╞░ß╗út qua TCP slow-start
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
                    # - Tß╗æt (High-speed): B─âng th├┤ng > 20 Mbps, Ping < 10ms.
                    # - Trung b├¼nh (Medium): B─âng th├┤ng 5 - 20 Mbps, Ping 50 - 100ms.
                    # - Yß║┐u (Low-speed): B─âng th├┤ng < 5 Mbps hoß║╖c Ping > 100ms.
                    if bandwidth > 20.0 and avg_ping < 10.0:
                        net_class = "high"
                        net_class_viet = "Tß╗æt (High-speed)"
                    elif bandwidth < 5.0 or avg_ping > 50.0:
                        net_class = "low"
                        net_class_viet = "Yß║┐u (Low-speed)"
                    else:
                        net_class = "medium"
                        net_class_viet = "Trung b├¼nh (Medium)"
                        
                    # 4. Report speed test results to Host
                    send_msg(sock, json.dumps({
                        "action": "speed_test_result",
                        "net_class": net_class,
                        "ping": avg_ping,
                        "bandwidth": bandwidth
                    }).encode('utf-8'), partner_pass)
                    
                    status_text = f"─Éo tß╗æc ─æß╗Ö (Lß╗¢n nhß║Ñt 2 lß║ºn): Ping {avg_ping:.1f}ms, B─âng th├┤ng {bandwidth:.2f} Mbps. Chß║Ñt l╞░ß╗úng: {net_class_viet}."
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
                    
                # Pygame window sß║╜ mß╗ƒ ─æ├║ng vß╗¢i ─æß╗Ö ph├ón giß║úi thß║¡t cß╗ºa host. 
                # (K├¡ch th╞░ß╗¢c ß║únh thß╗▒c tß║┐ truyß╗ün qua mß║íng vß║½n sß║╜ ─æ╞░ß╗úc n├⌐n lß║íi bß╗ƒi dyn_scale ß╗ƒ ph├¡a Host)
                self.update_status("Kß║┐t nß╗æi th├ánh c├┤ng! ─Éang khß╗ƒi ─æß╗Öng m├án h├¼nh...")
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
                    self.after(0, self.launch_pygame_viewer, sock, host_w, host_h, computer_name, zalo_phone, is_domain, partner_id, partner_pass)
            else:
                msg = res.get("message", "Sai mß║¡t khß║⌐u!")
                self.update_status("Bß╗ï tß╗½ chß╗æi kß║┐t nß╗æi")
                if reconnect_queue:
                    reconnect_queue.put("FAILED")
                self.after(0, lambda: self.show_custom_error("Tß╗½ chß╗æi kß║┐t nß╗æi", f"Kß║┐t nß╗æi bß╗ï tß╗½ chß╗æi:\n{msg}"))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
        except Exception as e:
            if reconnect_queue and retry_count < 30:
                self.update_status(f"Mß║Ñt kß║┐t nß╗æi. ─Éang thß╗¡ kß║┐t nß╗æi lß║íi lß║ºn {retry_count + 1}/30...")
                if sock:
                    force_close_socket(sock)
                    socket_passwords.pop(sock, None)
                time.sleep(2)
                self.connect_to_partner(partner_id, partner_pass, reconnect_queue, retry_count + 1, viewer_pid)
                return

            self.update_status("Sß║╡n s├áng kß║┐t nß╗æi")
            if reconnect_queue:
                reconnect_queue.put("FAILED")
            else:
                self.after(0, lambda err=str(e): self.show_custom_error("Lß╗ùi bß║»t tay", f"Lß╗ùi x├íc thß╗▒c handshake:\n{err}"))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if sock:
                force_close_socket(sock)
                socket_passwords.pop(sock, None)
            
    def launch_pygame_viewer(self, sock, host_w, host_h, computer_name="", zalo_phone="", is_domain=False, partner_id="", partner_pass=""):
        try:
            import multiprocessing as mp
            reconnect_queue = mp.Queue()
            p = mp.Process(target=run_client_viewer_loop, args=(sock, host_w, host_h, computer_name, is_domain, partner_id, reconnect_queue, partner_pass), daemon=True)
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
                                self.after(0, lambda: self.update_status(f"─Éang tß╗▒ ─æß╗Öng kß║┐t nß╗æi lß║íi..."))
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
            self.update_status("─É├ú mß╗ƒ mß╗Öt cß╗¡a sß╗ò ─æiß╗üu khiß╗ân mß╗¢i (Sß║╡n s├áng kß║┐t nß╗æi)")
            print(f"[Client] ─É├ú mß╗ƒ tiß║┐n tr├¼nh ─æiß╗üu khiß╗ân cho {computer_name or '─æß╗æi t├íc'}")
            
        except Exception as e:
            print(f"[Client] Lß╗ùi khß╗ƒi chß║íy tiß║┐n tr├¼nh ─æiß╗üu khiß╗ân: {e}")
            self.connect_btn.config(state=tk.NORMAL)
            try: force_close_socket(sock)
            except: pass
            
    def on_close_window(self):
        # L╞░u tß╗ìa ─æß╗Ö hiß╗çn tß║íi tr╞░ß╗¢c khi ß║⌐n cß╗¡a sß╗ò
        self.save_window_position()
        
        # Nß║┐u t├╣y chß╗ìn "Chß║íy khi mß╗ƒ m├íy" ─æ╞░ß╗úc bß║¡t th├¼ thu nhß╗Å xuß╗æng system tray
        if getattr(self, 'startup_var', None) and self.startup_var.get():
            self.withdraw()
            print("[Tray] App minimized to system tray.")
        else:
            # Nß║┐u kh├┤ng, ─æ├│ng ho├án to├án ß╗⌐ng dß╗Ñng
            self.destroy()

    def setup_tray_icon(self):
        if hasattr(self, 'tray_icon') and self.tray_icon:
            return
            
        try:
            # Tß║úi icon tß╗½ file png nß║┐u tß╗ôn tß║íi, ng╞░ß╗úc lß║íi vß║╜ icon mß║╖c ─æß╗ïnh
            icon_path = os.path.join(app_dir, "app_icon.png")
            image = None
            if os.path.exists(icon_path):
                try:
                    image = Image.open(icon_path)
                except Exception as e:
                    print(f"[Tray] Kh├┤ng thß╗â mß╗ƒ file app_icon.png: {e}")
            
            if image is None:
                image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
                dc = ImageDraw.Draw(image)
                dc.ellipse((4, 4, 60, 60), fill="#1E2022", outline="#00ADB5", width=3)
                dc.ellipse((16, 16, 48, 48), fill="#00ADB5")
            
            menu = pystray.Menu(
                item('Hiß╗çn (Show)', self.show_gui_from_tray, default=True),
                item('Tho├ít (Exit)', self.exit_from_tray)
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
    Chß║┐ ─æß╗Ö Clipboard Agent: Chß║íy ß╗ƒ quyß╗ün User th╞░ß╗¥ng.
    Lß║»ng nghe Named Pipe tß╗½ Service/headless app ─æß╗â nhß║¡n ─æ╞░ß╗¥ng dß║½n file
    v├á nß║íp v├áo Clipboard hß╗ç thß╗æng.
    
    Kiß║┐n tr├║c: App Headless (SYSTEM) -> Named Pipe -> App ClipboardAgent (User) -> Clipboard
    """
    import logging
    import queue
    import tkinter as tk
    import win32file
    import win32pipe
    import win32event
    import win32api
    
    log_path = os.path.join(app_dir, "clipboard_agent.log")
    logging.basicConfig(
        filename=log_path,
        level=logging.DEBUG,
        format="[%(asctime)s] [PID %(process)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    agent_log = logging.getLogger("clipboard_agent")

    def agent_print(msg):
        agent_log.info(msg)
        try:
            print(msg)
        except:
            pass

    agent_print("=" * 60)
    agent_print(f"[ClipboardAgent] Khß╗ƒi ─æß╗Öng. PID: {os.getpid()}")
    agent_print(f"[ClipboardAgent] Th╞░ mß╗Ñc ß╗⌐ng dß╗Ñng: {app_dir}")
    agent_print("=" * 60)

    pipe_name = CLIPBOARD_PIPE_NAME
    gui_queue = queue.Queue()

    def pipe_listener_loop():
        while True:
            pipe_handle = None
            try:
                agent_print(f"[ClipboardAgent] ─Éang chß╗¥ kß║┐t nß╗æi tß╗¢i Pipe: {pipe_name}")
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

                agent_print(f"[ClipboardAgent] ─É├ú kß║┐t nß╗æi th├ánh c├┤ng tß╗¢i Pipe.")

                try:
                    win32pipe.SetNamedPipeHandleState(
                        pipe_handle,
                        win32pipe.PIPE_READMODE_MESSAGE,
                        None,
                        None
                    )
                except Exception as se:
                    agent_print(f"[ClipboardAgent] Cß║únh b├ío SetNamedPipeHandleState: {se}. Tiß║┐p tß╗Ñc ß╗ƒ chß║┐ ─æß╗Ö byte mode.")

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
                                    agent_print(f"[ClipboardAgent] Nhß║¡n tin nhß║»n tß╗½ Pipe (─æß╗Ö d├ái {len(msg)}): {msg[:100]}...")
                                    if msg.startswith("TEXT:"):
                                        gui_queue.put(("text", msg[5:]))
                                    elif msg.startswith("START:"):
                                        parts = msg[6:].split("|")
                                        display_name = parts[0]
                                        total_size = int(parts[1]) if len(parts) > 1 else 0
                                        gui_queue.put(("start", (display_name, total_size)))
                                    elif msg.startswith("PROGRESS:"):
                                        received = int(msg[9:])
                                        gui_queue.put(("progress", received))
                                    elif msg.startswith("END"):
                                        gui_queue.put(("end", None))
                                    elif msg.startswith("CANCEL"):
                                        gui_queue.put(("cancel", None))
                                    elif msg.startswith("FILES:"):
                                        gui_queue.put(("files", msg[6:]))
                                    else:
                                        gui_queue.put(("files", msg))
                        else:
                            agent_print(f"[ClipboardAgent] ReadFile trß║ú vß╗ü m├ú lß╗ùi: {hr}")
                            break
                    except Exception as read_err:
                        err_code = getattr(read_err, 'winerror', 0)
                        if err_code == 109:
                            agent_print("[ClipboardAgent] Pipe bß╗ï ngß║»t. ─Éang kß║┐t nß╗æi lß║íi...")
                            break
                        elif err_code == 234:
                            continue
                        else:
                            agent_print(f"[ClipboardAgent] Lß╗ùi ─æß╗ìc Pipe: {read_err}")
                            break
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lß╗ùi kß║┐t nß╗æi Pipe: {e}")
            finally:
                if pipe_handle is not None:
                    try:
                        win32file.CloseHandle(pipe_handle)
                    except:
                        pass
            time.sleep(0.1)

    # Khß╗ƒi tß║ío Tkinter GUI
    root = tk.Tk()
    root.withdraw()
    
    active_dialog = None
    
    def trigger_cancel():
        agent_print("[ClipboardAgent] Ng╞░ß╗¥i d├╣ng ß║Ñn Hß╗ºy truyß╗ün tß║úi.")
        try:
            h_event = win32event.OpenEvent(win32event.EVENT_MODIFY_STATE, False, "Global\\AntigravityP2P_CancelTransfer_Event")
            win32event.SetEvent(h_event)
            win32api.CloseHandle(h_event)
        except Exception as e:
            agent_print(f"[ClipboardAgent] Kh├┤ng thß╗â gß╗¡i sß╗▒ kiß╗çn hß╗ºy: {e}")

    def poll_gui_queue():
        nonlocal active_dialog
        while not gui_queue.empty():
            try:
                action, val = gui_queue.get_nowait()
                if action == "text":
                    agent_print(f"[ClipboardAgent] ─Éang nß║íp text v├áo Clipboard...")
                    set_clipboard_text(val)
                elif action == "files":
                    paths = [p for p in val.split("|") if os.path.exists(p)]
                    if paths:
                        set_clipboard_files(paths)
                        agent_print(f"[ClipboardAgent] ─É├ú nß║íp {len(paths)} file v├áo Clipboard.")
                    else:
                        agent_print(f"[ClipboardAgent] File kh├┤ng tß╗ôn tß║íi ─æß╗â nß║íp clipboard.")
                elif action == "start":
                    display_name, total_size = val
                    if active_dialog:
                        try: active_dialog.destroy()
                        except: pass
                    active_dialog = ProgressDialog(
                        root, "─Éang tß║úi file vß╗ü...", display_name, total_size,
                        on_cancel=trigger_cancel
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
                agent_print(f"[ClipboardAgent] Lß╗ùi xß╗¡ l├╜ h├áng ─æß╗úi GUI: {e}")
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
    
    is_headless = "--headless" in sys.argv
    is_clipboard_agent = "--clipboard-agent" in sys.argv
    
    # --- Chß║┐ ─æß╗Ö Clipboard Agent: Chß╗ë lß║»ng nghe Pipe v├á nß║íp Clipboard, tho├ít sß╗¢m ---
    if is_clipboard_agent:
        if sys.platform == "win32":
            import win32event, win32api, winerror
            
            # Mutex ri├¬ng cho Clipboard Agent (index 3) ─æß╗â tr├ính chß║íy tr├╣ng
            try:
                sid = ctypes.c_ulong()
                ctypes.windll.kernel32.ProcessIdToSessionId(
                    ctypes.windll.kernel32.GetCurrentProcessId(), ctypes.byref(sid)
                )
                session_id = sid.value
            except:
                session_id = 1
                
            mutex_name = f"Global\\AntigravityP2PClipboardAgentMutex_{session_id}"
            mutex = win32event.CreateMutex(None, False, mutex_name)
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                sys.exit(0)
        
        # Redirect stdout/stderr cho clipboard agent mode
        try:
            log_path = os.path.join(app_dir, "clipboard_agent.log")
            sys.stdout = open(log_path, "a", encoding="utf-8", buffering=1)
            sys.stderr = sys.stdout
        except:
            pass
        
        run_clipboard_agent_mode()  # V├▓ng lß║╖p v├┤ tß║¡n, kh├┤ng return
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
            mutex = win32event.CreateMutex(None, False, mutex_name)
            
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                # Topmost native message dialog
                msg_text = "ß╗¿ng dß╗Ñng P2P Remote Desktop ─æang chß║íy ß╗ƒ khay hß╗ç thß╗æng"
                msg_title = "Th├┤ng b├ío"
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
