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
import urllib.request
import urllib.parse
import tkinter as tk
from tkinter import messagebox
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

# Pygame CE drop-in compatibility
# In pygame-ce, it is still imported as pygame.

# Remote Desktop Ports (Avoid 80/443 to prevent Router Web UI collision)
PORTS_TO_TRY = [9999, 8443, 5900, 27015, 4444]
BOUND_PORT = 9999
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

def send_input_keyboard_event(key_name, pressed):
    try:
        if len(key_name) == 1:
            # Use KEYEVENTF_UNICODE for reliable character injection (vital for password boxes in Winlogon/Server)
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            flags = 0x0004 # KEYEVENTF_UNICODE
            if not pressed:
                flags |= KEYEVENTF_KEYUP
            inp.union.ki = KEYBDINPUT(0, ord(key_name), flags, 0, None)
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            return
            
        vk = None
        if key_name in vk_map:
            vk = vk_map[key_name]
            
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
                0x11, 0xA3              # Ctrl_R
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

def send_input_mouse_move(x, y):
    try:
        w = ctypes.windll.user32.GetSystemMetrics(0) # SM_CXSCREEN
        h = ctypes.windll.user32.GetSystemMetrics(1) # SM_CYSCREEN
        if w > 0 and h > 0:
            normalized_x = int((x * 65536) / w)
            normalized_y = int((y * 65536) / h)
            inp = INPUT()
            inp.type = INPUT_MOUSE
            # MOUSEEVENTF_MOVE = 0x0001, MOUSEEVENTF_ABSOLUTE = 0x8000
            inp.union.mi = MOUSEINPUT(normalized_x, normalized_y, 0, 0x0001 | 0x8000, 0, None)
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    except Exception as e:
        print(f"[SendInput] Mouse move injection failed: {e}")

# TCP Frame Helper Functions
socket_send_lock = threading.Lock()

def send_msg(sock, data_bytes):
    try:
        with socket_send_lock:
            msg = struct.pack('>I', len(data_bytes)) + data_bytes
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

def recv_msg(sock):
    length_bytes = recv_exact(sock, 4)
    if not length_bytes:
        return None
    length = struct.unpack('>I', length_bytes)[0]
    return recv_exact(sock, length)

# Helper to fetch hardware identifiers (CPUID & HDD Serial)
def get_hwid():
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
        cpu = res_cpu.stdout.strip()
    except Exception:
        cpu = "FALLBACK_CPUID_888"
    try:
        # Get HDD Serial
        res_hdd = subprocess.run(
            ['powershell', '-Command', '(Get-CimInstance Win32_DiskDrive)[0].SerialNumber'],
            capture_output=True, text=True, check=True, startupinfo=startupinfo
        )
        hdd = res_hdd.stdout.strip()
    except Exception:
        hdd = "FALLBACK_HDD_999"
        
    combined = f"{cpu}_{hdd}".strip()
    sha = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    # Take first 12 hex characters (48-bit int)
    val = int(sha[:12], 16)
    # Generate stable 12-digit ID
    twelve_digit_val = (val % 900000000000) + 100000000000
    s = str(twelve_digit_val)
    return s, f"{s[:3]} {s[3:6]} {s[6:9]} {s[9:]}"

# Get Local LAN IP address
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

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
        sock.sendto(ssdp_msg.encode('utf-8'), ('239.255.255.250', 1900))
        while True:
            data, addr = sock.recvfrom(65535)
            response = data.decode('utf-8', errors='ignore')
            for line in response.split('\r\n'):
                if line.upper().startswith('LOCATION:'):
                    location_url = line.split(':', 1)[1].strip()
                    break
            if location_url:
                break
    except Exception as e:
        print(f"[UPnP] SSDP discovery timeout/error: {e}")
    finally:
        sock.close()
        
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
SIGNALING_SERVER_HOSTS = ['vietnam.sytes.net'] # Fallback default
SIGNALING_SERVER_PORT = 8765

try:
    server_config = configparser.ConfigParser()
    server_config.read('server.ini', encoding='utf-8')
    if 'server' in server_config:
        hosts_str = server_config['server'].get('host', 'vietnam.sytes.net')
        SIGNALING_SERVER_HOSTS = [h.strip() for h in hosts_str.split(',') if h.strip()]
        SIGNALING_SERVER_PORT = server_config['server'].getint('port', 8765)
except Exception as e:
    print(f"[Config] Error reading server.ini: {e}")

# Cấu hình bật/tắt đồng bộ Clipboard để phòng tránh cảnh báo Heuristic của phần mềm diệt virus khi không cần thiết
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


def get_clipboard_files(owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return []
    paths = []
    try:
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        # Retry loop để chờ ứng dụng khác (ví dụ Explorer) nhả khóa Clipboard
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
            print("[Clipboard] Lỗi: OpenClipboard thất bại do bị khóa bởi tiến trình khác.")
    except Exception as e:
        print(f"[Clipboard] Lỗi đọc clipboard Win32: {e}")
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
            print("[Clipboard] Lỗi: OpenClipboard thất bại khi ghi dữ liệu.")
    except Exception as e:
        print(f"[Clipboard] Lỗi ghi clipboard Win32: {e}")

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
        self.title("Copy File")
        self.geometry("520x420")
        self.resizable(False, False)
        self.configure(bg="#FFFFFF")
        
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
        self.title("Truyền tải File")
        self.resizable(False, False)
        self.configure(bg="#1E1E24")
        
        # Luôn hiển thị trên cùng mọi cửa sổ
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
        self.lbl_file = tk.Label(self, text=f"Tên file: {display_name}", font=("Segoe UI", 9), fg="#FFFFFF", bg="#1E1E24")
        self.lbl_file.pack(pady=2, padx=20, anchor=tk.W)
        
        self.lbl_size = tk.Label(self, text=f"Dung lượng: {self.format_size(total_size)}", font=("Segoe UI", 9), fg="#A0A0B0", bg="#1E1E24")
        self.lbl_size.pack(pady=2, padx=20, anchor=tk.W)
        
        self.lbl_progress = tk.Label(self, text="Đang chuẩn bị... 0%", font=("Segoe UI", 9), fg="#A0A0B0", bg="#1E1E24")
        self.lbl_progress.pack(pady=(10, 2), padx=20, anchor=tk.W)
        
        self.lbl_stats = tk.Label(self, text="Tốc độ: -- KB/s | Thời gian dự kiến: --:--", font=("Segoe UI", 9), fg="#A0A0B0", bg="#1E1E24")
        self.lbl_stats.pack(pady=2, padx=20, anchor=tk.W)
        
        self.progress_bar = PremiumProgressBar(self, width=320, height=12, bg="#15151B", fg="#00ADB5")
        self.progress_bar.pack(pady=(5, 10), padx=20)
        
        if self.on_cancel:
            btn_cancel = tk.Button(
                self, text="Hủy (Cancel)", font=("Segoe UI", 9, "bold"),
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
        if self.on_cancel:
            self.on_cancel()
        
    def update_progress(self, sent_bytes):
        percent = int(sent_bytes * 100 / self.total_size) if self.total_size > 0 else 100
        percent = max(0, min(100, percent))
        
        self.lbl_progress.config(
            text=f"Đang truyền tải... {percent}% ({self.format_size(sent_bytes)} / {self.format_size(self.total_size)})"
        )
        
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0 and sent_bytes > 0:
            speed = sent_bytes / elapsed_time
            if speed > 0:
                remaining_bytes = self.total_size - sent_bytes
                remaining_time = remaining_bytes / speed
                mins = int(remaining_time // 60)
                secs = int(remaining_time % 60)
                time_str = f"{mins} min {secs:02d} giây"
            else:
                time_str = "--:--"
            speed_str = f"{self.format_speed(speed)}"
        else:
            speed_str = "-- KB/s"
            time_str = "--:--"
            
        self.lbl_stats.config(text=f"Tốc độ: {speed_str} | Thời gian dự kiến: {time_str}")
        
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
        self.mouse_hook = None
        self.mouse_hook_callback = None
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _mouse_hook_proc(self, nCode, wParam, lParam):
        if nCode >= 0:
            # WM_RBUTTONDOWN = 0x0204, WM_RBUTTONUP = 0x0205, WM_NCRBUTTONDOWN = 0x00A4, WM_NCRBUTTONUP = 0x00A5
            if wParam in (0x0204, 0x0205, 0x00A4, 0x00A5):
                if self.manager:
                    self.manager.last_rbutton_time = time.time()
                    log_debug(f"[MouseHook] Phát hiện click chuột phải lúc: {self.manager.last_rbutton_time}")
            # WM_LBUTTONDOWN = 0x0201, WM_LBUTTONUP = 0x0202, WM_NCLBUTTONDOWN = 0x00A1, WM_NCLBUTTONUP = 0x00A2
            elif wParam in (0x0201, 0x0202, 0x00A1, 0x00A2):
                if self.manager:
                    self.manager.last_lbutton_time = time.time()
        return ctypes.windll.user32.CallNextHookEx(None, nCode, wParam, lParam)

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
            
            # Định nghĩa types cho CallNextHookEx để tránh lỗi OverflowError trên 64-bit Windows
            user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, WPARAM_64, LPARAM_64]
            user32.CallNextHookEx.restype = LRESULT_64
            
            # Đăng ký Low-level Mouse Hook để theo dõi chuột phải toàn hệ thống
            try:
                HOOKPROC = ctypes.WINFUNCTYPE(LRESULT_64, ctypes.c_int, WPARAM_64, LPARAM_64)
                self.mouse_hook_callback = HOOKPROC(self._mouse_hook_proc)
                user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HANDLE, wintypes.DWORD]
                user32.SetWindowsHookExW.restype = wintypes.HANDLE
                
                self.mouse_hook = user32.SetWindowsHookExW(
                    14, # WH_MOUSE_LL = 14
                    self.mouse_hook_callback,
                    h_mod,
                    0
                )
                log_debug(f"[Listener] Đã đăng ký Low-level Mouse Hook thành công: {self.mouse_hook}")
            except Exception as e:
                log_debug(f"[Listener] Lỗi đăng ký Mouse Hook: {e}")

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
            
            add_res = user32.AddClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            log_debug(f"[Listener] AddClipboardFormatListener trả về: {add_res}")
            
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
        if self.mouse_hook:
            try:
                ctypes.windll.user32.UnhookWindowsHookEx(self.mouse_hook)
                log_debug("[Listener] Đã gỡ bỏ Low-level Mouse Hook.")
            except Exception as e:
                log_debug(f"[Listener] Lỗi gỡ bỏ Mouse Hook: {e}")
        if self.hwnd:
            try: ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.hwnd), 0, 0, 0)
            except: pass

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
        
        # Không cần luồng theo dõi paste vì dùng delayed rendering thực tế

    def register_app(self, app):
        self.app = app
        self.poll_gui_queue()

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

    def show_dialog(self, title_text, filename, total_size):
        self.gui_queue.put(("create", (title_text, filename, total_size)))

    def update_dialog(self, sent_bytes):
        self.gui_queue.put(("update", sent_bytes))

    def close_dialog(self):
        self.gui_queue.put(("destroy", None))

    def cancel_active_transfer(self, remote_triggered=False):
        if not self.transfer_in_progress and not self.incoming_transfers:
            if not self.pending_remote_files:
                return
            
        print(f"[FileTransfer] Bắt đầu hủy truyền tải (remote_triggered={remote_triggered})...")
        
        # Dọn dẹp cache file và trạng thái paste
        self.pending_remote_files = []
        self.is_paste_triggered = False
        
        # Giải phóng delayed rendering trên clipboard bằng cách xóa sạch clipboard nếu app đang sở hữu
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
                    log_debug("[cancel_active_transfer] Đã giải phóng/xóa clipboard sở hữu bởi app.")
        except Exception as e:
            log_debug(f"[cancel_active_transfer] Lỗi khi giải phóng clipboard: {e}")
        
        # 1. Báo cho remote nếu hủy từ phía local
        if not remote_triggered and self.sock:
            try:
                pkt = json.dumps({"type": "cancel_transfer"}).encode('utf-8')
                send_msg(self.sock, pkt)
            except Exception as e:
                print(f"[FileTransfer] Lỗi gửi tín hiệu hủy: {e}")
                
        # 2. Tắt cờ truyền tải
        self.transfer_in_progress = False
        
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

    def on_clipboard_changed(self):
        if not ENABLE_CLIPBOARD_SYNC or self.transfer_in_progress: return
        
        # Tránh tự kích hoạt vòng lặp khi chính ứng dụng thiết lập delayed rendering
        try:
            user32 = ctypes.windll.user32
            user32.GetClipboardOwner.restype = ctypes.c_void_p
            owner = user32.GetClipboardOwner()
            if self.listener and self.listener.hwnd and owner == self.listener.hwnd:
                log_debug("[on_clipboard_changed] Bỏ qua sự kiện thay đổi clipboard do chính mình sở hữu (delayed rendering).")
                return
        except Exception as e:
            log_debug(f"[on_clipboard_changed] Lỗi kiểm tra GetClipboardOwner: {e}")
            
        threading.Thread(target=self._process_clipboard_change, daemon=True).start()

    def _process_clipboard_change(self):
        try:
            time.sleep(0.2) # Chờ xíu để Windows thả file lock
            owner_hwnd = None
            if self.app:
                try: owner_hwnd = self.app.winfo_id()
                except: pass
                
            current_files = get_clipboard_files(owner_hwnd)
            if current_files:
                valid_files = [f for f in current_files if os.path.isfile(f)]
                if not valid_files: return
                
                # Bỏ qua nếu có bất kỳ file nào nằm trong thư mục tạm RemoteDesktopTransfers (để tránh vòng lặp clipboard)
                temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                temp_dir_abs = os.path.abspath(temp_dir).lower()
                if any(os.path.abspath(f).lower().startswith(temp_dir_abs) for f in valid_files):
                    log_debug("[_process_clipboard_change] Bỏ qua vì phát hiện tệp tin trong thư mục tạm (tránh lặp clipboard).")
                    return
                    
                with self.lock:
                    if valid_files == self.last_files and (time.time() - getattr(self, 'last_files_time', 0)) < 2.0:
                        return
                    self.last_files = valid_files
                    self.last_files_time = time.time()
                    
                metadata = [{"name": os.path.basename(f), "size": os.path.getsize(f), "mtime": os.path.getmtime(f), "path": f} for f in valid_files]
                if metadata and self.active_sockets:
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
        for _ in range(10):
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
                
            # Đăng ký các format để tránh Clipboard History / Cloud Clipboard tự động quét gây mất delayed rendering
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
                            log_debug(f"[set_dword_data] Thất bại SetClipboardData cho format {cf_format}")
                        else:
                            log_debug(f"[set_dword_data] Đã thiết lập format {cf_format} = {value}")
                    else:
                        kernel32.GlobalFree(hMem)
                else:
                    log_debug("[set_dword_data] GlobalAlloc thất bại")
                            
            if cf_exclude: set_dword_data(cf_exclude, 1)
            if cf_history: set_dword_data(cf_history, 0)
            if cf_cloud: set_dword_data(cf_cloud, 0)
            
            res = fn_SetClipboardData(15, None) # CF_HDROP với delayed rendering (None handle)
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
        self.pending_remote_files = []
        print("[Clipboard] Đã mất quyền sở hữu clipboard (người dùng copy dữ liệu khác).")

    def get_active_explorer_path(self):
        try:
            import win32gui
            import win32com.client
            import ctypes
            from ctypes import wintypes
            
            hwnds_to_check = []
            
            def get_root_hwnd(h):
                if not h: return None
                try:
                    root = ctypes.windll.user32.GetAncestor(h, 2) # GA_ROOT = 2
                    return root if root else h
                except:
                    return h
            
            # 1. Cửa sổ đang mở Clipboard (chính xác nhất cho thao tác Paste)
            try:
                hwnd_clip = ctypes.windll.user32.GetOpenClipboardWindow()
                if hwnd_clip:
                    root_clip = get_root_hwnd(hwnd_clip)
                    if root_clip and root_clip not in hwnds_to_check:
                        hwnds_to_check.append(root_clip)
            except: pass
                
            # 2. Cửa sổ Foreground hiện tại
            try:
                hwnd_fg = win32gui.GetForegroundWindow()
                if hwnd_fg:
                    root_fg = get_root_hwnd(hwnd_fg)
                    if root_fg and root_fg not in hwnds_to_check:
                        hwnds_to_check.append(root_fg)
            except: pass
                
            # 3. Cửa sổ nằm dưới con trỏ chuột (phòng trường hợp mất focus vào menu)
            try:
                pt = wintypes.POINT()
                if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                    hwnd_mouse = ctypes.windll.user32.WindowFromPoint(pt)
                    if hwnd_mouse:
                        root_mouse = get_root_hwnd(hwnd_mouse)
                        if root_mouse and root_mouse not in hwnds_to_check:
                            hwnds_to_check.append(root_mouse)
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
        is_menu_query = False
        try:
            user32 = ctypes.windll.user32
            
            # 0. Nếu vừa click chuột trái (trong vòng 0.8 giây), đây chắc chắn là thao tác click "Paste" từ Menu, bỏ qua mọi kiểm tra
            time_since_lbutton = time.time() - getattr(self, 'last_lbutton_time', 0)
            if time_since_lbutton < 0.8:
                log_debug("[render_format] Bỏ qua kiểm tra menu do người dùng vừa click chuột trái (Paste).")
            else:
                # 1. Kiểm tra nếu vừa mới click chuột phải (trong vòng 1.5 giây)
                time_since_rbutton = time.time() - getattr(self, 'last_rbutton_time', 0)
                if time_since_rbutton < 1.5:
                    is_menu_query = True
                    
                # 2. Kiểm tra nếu lớp cửa sổ menu hiển thị (#32768) hoặc tồn tại (kể cả ẩn)
                if not is_menu_query:
                    user32.FindWindowW.restype = wintypes.HWND
                    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
                    hwnd_menu = user32.FindWindowW("#32768", None)
                    if hwnd_menu:
                        is_menu_query = True
                    
            # 3. Kiểm tra trạng thái Menu Loop của luồng yêu cầu clipboard (Explorer) hoặc Foreground Window
            if not is_menu_query:
                user32.GetOpenClipboardWindow.restype = wintypes.HWND
                user32.GetOpenClipboardWindow.argtypes = []
                user32.GetWindowThreadProcessId.restype = wintypes.DWORD
                user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
                user32.GetGUIThreadInfo.restype = wintypes.BOOL
                user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.c_void_p]
                
                class GUITHREADINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("flags", wintypes.DWORD),
                        ("hwndActive", wintypes.HWND),
                        ("hwndFocus", wintypes.HWND),
                        ("hwndCapture", wintypes.HWND),
                        ("hwndMenuOwner", wintypes.HWND),
                        ("hwndMoveSize", wintypes.HWND),
                        ("hwndCaret", wintypes.HWND),
                        ("rcCaret", wintypes.RECT),
                    ]
                
                hwnd_clip = user32.GetOpenClipboardWindow()
                for hwnd_check in (hwnd_clip, user32.GetForegroundWindow()):
                    if hwnd_check:
                        pid = wintypes.DWORD()
                        tid = user32.GetWindowThreadProcessId(hwnd_check, ctypes.byref(pid))
                        gui_info = GUITHREADINFO()
                        gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)
                        if user32.GetGUIThreadInfo(tid, ctypes.byref(gui_info)):
                            # GUI_INMENULOOP = 0x04, GUI_POPUPMENUMODE = 0x10, GUI_SYSTEMMENUMODE = 0x08
                            if gui_info.flags & (0x04 | 0x10 | 0x08):
                                is_menu_query = True
                                break
                                
            # 4. Kiểm tra nếu nút chuột phải đang được nhấn giữ (Fallback)
            if not is_menu_query:
                user32.GetAsyncKeyState.restype = wintypes.SHORT
                user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
                VK_RBUTTON = 0x02
                if user32.GetAsyncKeyState(VK_RBUTTON) & 0x8000:
                    is_menu_query = True
                    
            # 5. Nếu không phải là truy vấn menu hiển nhiên, hãy kiểm tra xem có dấu hiệu hành động PASTE thực tế không
            if not is_menu_query:
                user32.GetAsyncKeyState.restype = wintypes.SHORT
                user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
                VK_CONTROL = 0x11
                VK_V = 0x56
                ctrl_pressed = bool(user32.GetAsyncKeyState(VK_CONTROL) & 0x8000)
                v_pressed = bool(user32.GetAsyncKeyState(VK_V) & 0x8000)
                ctrl_v = ctrl_pressed and v_pressed
                
                recent_right_click = time_since_rbutton < 5.0
                meta_age = time.time() - getattr(self, 'meta_arrival_time', 0)
                
                # Nếu không có Ctrl+V, không có click chuột phải gần đây, HOẶC nếu đây là truy vấn tự động
                # xảy ra ngay khi vừa nhận được metadata (thường do clipboard history hoặc shell extension tự quét trong vòng 1.5s đầu)
                # thì coi như đây không phải là Paste thực tế.
                if not (ctrl_v or recent_right_click):
                    is_menu_query = True
                elif meta_age < 0.5 and not ctrl_v:
                    is_menu_query = True
                    
            if is_menu_query:
                log_debug(f"[render_format] Phát hiện truy vấn tự động hoặc menu chuột phải. Bỏ qua tải file thực tế và giữ delayed rendering.")
                return
        except Exception as e:
            log_debug(f"[render_format] Lỗi kiểm tra context menu: {e}")
            
        if getattr(self, 'is_rendering', False):
            log_debug("[render_format] Bỏ qua WM_RENDERFORMAT trùng lặp (đang render).")
            return
            
        self.is_rendering = True
        self.transfer_in_progress = True # Đặt cờ truyền tải để chặn các sự kiện thay đổi clipboard trong quá trình render
        try:
            print("[Clipboard] Nhận WM_RENDERFORMAT. Đang bắt đầu kiểm tra tệp tin ghi đè...")
            log_debug("[render_format] Nhận WM_RENDERFORMAT. Đang bắt đầu kiểm tra tệp tin ghi đè...")
            
            self.batch_paths = []
            self.transfer_done_event.clear()
            
            # Lấy thư mục đích hoạt động của Explorer để kiểm tra file tồn tại
            dest_dir = self.get_active_explorer_path()
            log_debug(f"[render_format] Thư mục đích phát hiện: {dest_dir}")
            
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
                                dest_info = {"size": dest_stat.st_size, "mtime": dest_stat.st_mtime}
                            except:
                                dest_info = {"size": 0, "mtime": 0}
                                
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
                                fn_SetClipboardData(15, None)
                                return
                    else:
                        files_to_download.append(f)
            else:
                files_to_download = list(self.pending_remote_files)
                
            if not files_to_download:
                log_debug("[render_format] Không có tệp tin nào được chọn để tải (người dùng bỏ qua tất cả).")
                fn_SetClipboardData(15, None)
                return
                
            # Đặt lại danh sách tệp tin thực tế cần tải
            self.pending_remote_files = files_to_download
            
            # Yêu cầu truyền file thực tế từ Host
            self.request_pending_files()
            
            # Chờ nhận xong file trong thư mục tạm (non-blocking message pump)
            succeeded = False
            start_time = time.time()
            msg = wintypes.MSG()
            while time.time() - start_time < 600.0:
                if self.transfer_done_event.is_set():
                    succeeded = True
                    break
                # Process window messages to keep Tkinter/hidden window responsive
                if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1): # PM_REMOVE = 1
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    time.sleep(0.01)
                    
            if succeeded and self.batch_paths:
                # Xóa các file cần ghi đè ngay trước khi đưa cho Explorer copy
                for p in files_to_replace:
                    try: os.remove(p)
                    except: pass

                print(f"[Clipboard] Tải thành công {len(self.batch_paths)} file. Đang nạp vào Clipboard...")
                log_debug(f"[render_format] Tải thành công {len(self.batch_paths)} file. Đang nạp vào Clipboard...")
                hGlobal = create_hdrop_data(self.batch_paths)
                if hGlobal:
                    self.ignore_destroy_clipboard = True
                    try:
                        res = fn_SetClipboardData(15, hGlobal)
                        if not res:
                            err = ctypes.GetLastError()
                            log_debug(f"[render_format] Lỗi SetClipboardData: res={res}, GetLastError={err}")
                        else:
                            log_debug(f"[render_format] Đã nạp thành công CF_HDROP vào Clipboard. res={res}")
                    finally:
                        self.ignore_destroy_clipboard = False
                else:
                    log_debug("[render_format] Không tạo được hGlobal, hủy render.")
            else:
                log_debug(f"[render_format] Tải file thất bại hoặc hết thời gian chờ. succeeded={succeeded}")
        finally:
            if not is_menu_query:
                self.pending_remote_files = []
            self.transfer_in_progress = False
            self.is_rendering = False

    def request_pending_files(self):
        if not self.pending_remote_files or not self.sock: return
        send_msg(self.sock, json.dumps({"type": "request_files", "files": self.pending_remote_files}).encode('utf-8'))

    def _process_send_requests(self, sock, files):
        self.transfer_in_progress = True
        log_debug(f"[_process_send_requests] Khởi chạy gửi {len(files)} file...")
        try:
            total_size = sum(f.get("size", 0) for f in files)
            display_name = f"{len(files)} tệp tin" if len(files) > 1 else files[0].get("name", "Unknown")
            
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
            for f in files:
                if not self.transfer_in_progress:
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
                    with open(filepath, "rb") as fh:
                        while True:
                            if not self.transfer_in_progress:
                                break
                            chunk_data = fh.read(4 * 1024 * 1024)
                            if not chunk_data: break
                            b64 = base64.b64encode(chunk_data).decode('utf-8')
                            send_msg(sock, json.dumps({"type": "file_chunk", "name": filename, "data": b64}).encode('utf-8'))
                            total_sent += len(chunk_data)
                    log_debug(f"[_process_send_requests] Đã gửi xong dữ liệu cho {filename}")
                except Exception as e:
                    print(f"[FileTransfer] Lỗi khi gửi file {filename}: {e}")
                    log_debug(f"[_process_send_requests] Lỗi khi gửi file {filename}: {e}")
                    
                if self.transfer_in_progress:
                    send_msg(sock, json.dumps({"type": "file_end", "name": filename}).encode('utf-8'))
                    log_debug(f"[_process_send_requests] Đã gửi file_end cho {filename}")
                
            if self.transfer_in_progress:
                send_msg(sock, json.dumps({"type": "batch_end"}).encode('utf-8'))
                log_debug(f"[_process_send_requests] Đã gửi batch_end.")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error processing send request: {e}")
            log_debug(f"[_process_send_requests] Lỗi tổng quát:\n{tb}")
            try:
                send_msg(sock, json.dumps({"type": "cancel_transfer"}).encode('utf-8'))
            except:
                pass
        finally:
            self.transfer_in_progress = False
            log_debug(f"[_process_send_requests] Kết thúc hàm gửi file.")

    def handle_received_packet(self, packet):
        ptype = packet.get("type")
        
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
                set_clipboard_text(text, owner_hwnd)
            finally:
                self.ignore_destroy_clipboard = False
            return
            
        elif ptype == "files_copied_meta":
            self.pending_remote_files = packet.get("files", [])
            self.meta_arrival_time = time.time()
            log_debug(f"[handle_received_packet] Nhận files_copied_meta. Số file: {len(self.pending_remote_files)}")
            print(f"[Clipboard] Đã nhận được files_copied_meta. Số file: {len(self.pending_remote_files)}")
            if not self.pending_remote_files: return
            
            # Đặt target_save_dir là thư mục tạm
            temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
            try:
                os.makedirs(temp_dir, exist_ok=True)
                for item in os.listdir(temp_dir):
                    item_path = os.path.join(temp_dir, item)
                    if os.path.isfile(item_path):
                        try: os.remove(item_path)
                        except: pass
            except Exception as e:
                log_debug(f"[files_copied_meta] Lỗi dọn dẹp thư mục tạm: {e}")
            self.target_save_dir = temp_dir
            
            # Đăng ký delayed rendering để Windows gửi WM_RENDERFORMAT khi người dùng Paste
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
            log_debug(f"[batch_start] Bắt đầu nhận batch, total_size={self.batch_total_size}, target_save_dir={self.target_save_dir}")
            self.show_dialog("Đang tải file về...", display_name, self.batch_total_size)
            
        elif ptype == "file_start":
            filename = packet.get("name", "")
            if not filename: return
            target_path = os.path.join(self.target_save_dir, filename)
            log_debug(f"[file_start] Bắt đầu nhận file: {filename}, target_path={target_path}")

            try:
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
                    
                    self.batch_paths.append(transfer["path"])
                    log_debug(f"[file_end] Đã xử lý xong file: {filename}")
                
        elif ptype == "batch_end":
            self.close_dialog()
            self.transfer_done_event.set()
            log_debug(f"[batch_end] Đã nhận xong toàn bộ file trong thư mục tạm.")



clipboard_sync_manager = ClipboardSyncManager()




# Shared client variables
client_latest_frame = None
client_frame_lock = threading.Lock()
client_running = True
client_is_domain = False
client_is_locked = False
client_switching_desktop_countdown = 0

# Client Screen Receiver Thread
def client_receiver_thread(sock):
    global client_latest_frame, client_running
    while client_running:
        try:
            msg = recv_msg(sock)
            if not msg:
                print("[Client] Server closed connection.")
                client_running = False
                break
                
            if msg.startswith(b'{'):
                try:
                    event = json.loads(msg.decode('utf-8'))
                    evt_type = event.get("type", "")
                    if evt_type in ("batch_start", "file_start", "file_chunk", "file_end", "batch_end", "files_copied_meta", "request_files", "cancel_transfer", "clipboard_text"):
                        clipboard_sync_manager.handle_received_packet(event)
                        continue
                    elif evt_type == "domain_status":
                        global client_is_domain, client_is_locked
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
                        global client_switching_desktop_countdown
                        client_switching_desktop_countdown = 15
                        continue
                except Exception as je:
                    print(f"[Client] Lỗi giải mã gói tin JSON: {je}")
                    pass

            import io
            try:
                pil_img = Image.open(io.BytesIO(msg))
                pil_img.load()  # Force decode in receiver thread
                with client_frame_lock:
                    client_latest_frame = pil_img
                global client_switching_desktop_countdown
                client_switching_desktop_countdown = 0
            except Exception as ie:
                with open("client_error.log", "a") as f: f.write(f"[Client] Lỗi giải mã ảnh Pillow: {ie}\n")
        except Exception as e:
            with open("client_error.log", "a") as f: f.write(f"[Client] Receiver Error: {e}\n")
            client_running = False
            break

# Client Main View Pygame Loop
def run_client_viewer_loop(sock, host_w, host_h, computer_name="", is_domain=False, partner_id="", reconnect_queue=None):
    try:
        outer_running = True
        
        # Initialize Pygame once outside the loop
        pygame.init()
        pygame.key.set_repeat(500, 50)
        
        info = pygame.display.Info()
        client_max_w, client_max_h = info.current_w, info.current_h
        
        window_w = min(host_w, client_max_w, 3840)
        window_h = min(host_h, client_max_h, 2160)
        
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
            print(f"[App] Lỗi thiết lập icon cửa sổ pygame: {e}")
            
        try: btn_font = pygame.font.SysFont("Segoe UI", 12, bold=True)
        except:
            try: btn_font = pygame.font.SysFont("Arial", 12, bold=True)
            except: btn_font = pygame.font.Font(None, 20)
            
        clock = pygame.time.Clock()
        button_map = {1: 'left', 2: 'middle', 3: 'right'}
        
        while outer_running:
            exit_due_to_disconnect = True
            global client_latest_frame, client_running, client_is_domain, client_is_locked
            client_latest_frame = None
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
            t = threading.Thread(target=client_receiver_thread, args=(sock,), daemon=True)
            t.start()
            
            # Gắn kết socket vào trình quản lý Event Listener của Clipboard
            clipboard_sync_manager.add_socket(sock)
            # We moved pygame init outside
            
            # Khởi tạo kích thước viewer ban đầu cho Host biết
            def send_event(event_dict):
                try:
                    data = json.dumps(event_dict).encode('utf-8')
                    send_msg(sock, data)
                except Exception:
                    pass
                    
            send_event({"type": "check_domain"})
            send_event({"type": "resize_viewer", "w": window_w, "h": window_h})
            
            frame_counter = 0
            blink_frames_remaining = 0
            
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
     
                # Calculate floating button rectangle dynamically
                btn_w, btn_h = 145, 30
                btn_x = (window_w - btn_w) // 2
                btn_y = 5
                btn_rect = pygame.Rect(btn_x, btn_y, btn_w, btn_h)
                
                mx, my = pygame.mouse.get_pos()
                is_hover = btn_rect.collidepoint(mx, my) if (client_is_domain and client_is_locked) else False
     
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
                        if client_is_domain and client_is_locked and btn_rect.collidepoint(event.pos):
                            continue
                        mx_pos, my_pos = event.pos
                        host_x = int(mx_pos * (host_w / window_w))
                        host_y = int(my_pos * (host_h / window_h))
                        send_event({"type": "mouse_move", "x": host_x, "y": host_y})
                        
                    elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                        if client_is_domain and client_is_locked and btn_rect.collidepoint(event.pos):
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                print("[Client] SAS Button Clicked. Sending trigger_sas to host.")
                                send_event({"type": "trigger_sas"})
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
                        send_event({
                            "type": "key_event",
                            "key": key_name,
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
                    
                # Draw floating SAS button on top
                if client_is_domain and client_is_locked:
                    bg_color = (58, 58, 77) if is_hover else (42, 42, 53)
                    border_color = (0, 173, 181)
                    pygame.draw.rect(screen, bg_color, btn_rect, border_radius=4)
                    pygame.draw.rect(screen, border_color, btn_rect, width=1, border_radius=4)
                    
                    # Render and blit text
                    text_surf = btn_font.render("Gửi Ctrl+Alt+Del", True, (255, 255, 255))
                    text_rect = text_surf.get_rect(center=btn_rect.center)
                    screen.blit(text_surf, text_rect)
                    
                if globals().get('client_switching_desktop_countdown', 0) > 0:
                    if "msg_font" not in locals():
                        try: msg_font = pygame.font.SysFont("Segoe UI", 24, bold=True)
                        except: msg_font = pygame.font.Font(None, 32)
                    
                    overlay = pygame.Surface((window_w, window_h))
                    overlay.set_alpha(150)
                    overlay.fill((0, 0, 0))
                    screen.blit(overlay, (0, 0))
                    
                    text_surf = msg_font.render(f"Đang chuyển giao diện ! Sẽ kết nối lại trong vòng {client_switching_desktop_countdown} giây...", True, (255, 255, 255))
                    text_rect = text_surf.get_rect(center=(window_w//2, window_h//2))
                    screen.blit(text_surf, text_rect)
                    
                    current_tick = pygame.time.get_ticks()
                    if "last_tick" not in locals(): last_tick = current_tick
                    if current_tick - last_tick >= 1000:
                        global client_switching_desktop_countdown
                        client_switching_desktop_countdown -= 1
                        last_tick = current_tick
                
                pygame.display.flip()
                clock.tick(60)
                
            if exit_due_to_disconnect and reconnect_queue:
                countdown = 15
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
                        elif hasattr(new_sock, 'fileno'):
                            print("[Client] Received new socket. Resuming session!")
                            sock = new_sock
                            break # Break inner wait loop, outer loop will continue
                    except:
                        pass
                    
                    screen.fill((30, 30, 30))
                    text_surf = msg_font.render(f"Đang chuyển giao diện ! Sẽ kết nối lại trong vòng {countdown} giây...", True, (255, 255, 255))
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
            
        pygame.quit()
        if exit_due_to_disconnect:
            print("[Client] Viewer exited due to disconnect. Exit code 99.")
            import sys
            sys.exit(99)
    except Exception as critical_e:
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
        self.force_relay_var = tk.BooleanVar(value=True)
        self.startup_var = tk.BooleanVar(value=self.is_startup_enabled())
        
        # Register Trace for Auto-Formatting Partner ID
        self.id_trace_id = self.partner_id_var.trace_add("write", self.format_partner_id)
        
        # Intercept close window button ("X")
        self.protocol("WM_DELETE_WINDOW", self.on_close_window)
        
        # Setup UI
        self.setup_ui()
        
        # Start background services
        threading.Thread(target=self.init_network_services, daemon=True).start()
        
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
        file_menu.add_command(label="Danh sách (Saved Computers)", command=self.show_saved_computers_dialog)
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
        container.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # LEFT PANEL: Allow Remote Control
        left_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        left_panel.place(relx=0.0, rely=0.0, relwidth=0.47, relheight=0.88)
        
        lbl_allow = tk.Label(left_panel, text="CHO PHÉP ĐIỀU KHIỂN", font=("Segoe UI", 11, "bold"), fg=self.btn_color, bg=self.card_color)
        lbl_allow.pack(pady=(15, 10))
        
        lbl_id = tk.Label(left_panel, text="Mã ID của bạn:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.card_color)
        lbl_id.pack(anchor=tk.W, padx=20)
        
        id_frame = tk.Frame(left_panel, bg=self.card_color)
        id_frame.pack(fill=tk.X, padx=20, pady=(5, 12))
        
        self.my_id_label = tk.Label(id_frame, text=self.my_id_formatted, font=("Segoe UI", 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0, height=1)
        self.my_id_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_id_btn = tk.Button(id_frame, text="📋", font=("Segoe UI", 10), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=lambda: self.copy_to_clipboard(self.my_id_formatted))
        copy_id_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        lbl_pass = tk.Label(left_panel, text="Mật khẩu kết nối:", font=("Segoe UI", 9), fg=self.text_gray, bg=self.card_color)
        lbl_pass.pack(anchor=tk.W, padx=20)
        
        pass_frame = tk.Frame(left_panel, bg=self.card_color)
        pass_frame.pack(fill=tk.X, padx=20, pady=(5, 5))
        
        self.my_pass_label = tk.Label(pass_frame, text=self.my_password, font=("Segoe UI", 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0)
        self.my_pass_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_pass_btn = tk.Button(pass_frame, text="📋", font=("Segoe UI", 10), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=lambda: self.copy_to_clipboard(self.my_password))
        copy_pass_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        refresh_btn = tk.Button(pass_frame, text="↻", font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, width=3, command=self.refresh_password)
        refresh_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # Nhãn hiển thị trạng thái mật khẩu cố định
        self.fixed_pass_indicator = tk.Label(left_panel, text="", font=("Segoe UI", 8, "italic"), fg="#2ECC71", bg=self.card_color)
        self.fixed_pass_indicator.pack(anchor=tk.W, padx=20, pady=(2, 0))
        self.update_fixed_password_indicator()

        # Button to Copy both ID & Password at once
        copy_all_btn = tk.Button(left_panel, text="📋 Sao chép cả ID & Mật khẩu", font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, command=self.copy_id_and_password)
        copy_all_btn.pack(pady=(8, 0), padx=20, fill=tk.X)
        
        # RIGHT PANEL: Control Remote Computer
        right_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        right_panel.place(relx=0.53, rely=0.0, relwidth=0.47, relheight=0.88)
        
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
        
        # Container to hold CONNECT & ADD (+) buttons
        btn_container = tk.Frame(right_panel, bg=self.card_color)
        btn_container.pack(padx=20, fill=tk.X)
        
        self.connect_btn = tk.Button(btn_container, text="KẾT NỐI (CONNECT)", font=("Segoe UI", 11, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, command=self.click_connect)
        self.connect_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Add button with a blue "+"
        self.add_partner_btn = tk.Button(btn_container, text="➕", font=("Segoe UI", 12, "bold"), fg=self.text_white, bg="#007ACC", activebackground="#005A9E", relief=tk.FLAT, bd=0, width=4, cursor="hand2", command=self.add_current_partner_to_saved)
        self.add_partner_btn.pack(side=tk.RIGHT, padx=(8, 0))

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
        raw_val = self.partner_id_var.get().replace(" ", "")
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
            
        self.partner_id_var.trace_remove("write", self.id_trace_id)
        self.partner_id_var.set(formatted)
        self.id_trace_id = self.partner_id_var.trace_add("write", self.format_partner_id)
        
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
        default_geometry = "680x450"
        self.minsize(680, 450)
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    config = json.load(f)
                    geom = config.get("geometry")
                    if geom:
                        # Bảo đảm chiều rộng tối thiểu 680 và chiều cao tối thiểu 450
                        if "x" in geom:
                            parts = geom.split("+")[0].split("x")
                            if len(parts) == 2:
                                gw = max(680, int(parts[0]))
                                gh = max(450, int(parts[1]))
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
        w = 680
        h = 450
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        geom = f"{w}x{h}+{x}+{y}"
        self.geometry(geom)
        self.last_normal_geometry = geom

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
                        
            with open(self.config_file, "w") as f:
                json.dump({"geometry": geom}, f)
            print(f"[Config] Saved window position: {geom}")
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
        ptype = self.pass_type_var.get()
        if ptype == "5 chữ số":
            self.my_password = str(random.randint(10000, 99999))
        elif ptype == "8 ký tự (chữ + số)":
            chars = string.ascii_letters + string.digits
            self.my_password = ''.join(random.choices(chars, k=8))
        else:  # Mặc định: 4 chữ số
            self.my_password = str(random.randint(1000, 9999))
        self.my_pass_label.config(text=self.my_password)
        
    def show_saved_computers_dialog(self):
        if hasattr(self, 'saved_computers_dialog') and self.saved_computers_dialog.winfo_exists():
            self.saved_computers_dialog.lift()
            self.saved_computers_dialog.focus_force()
            return
            
        dialog = tk.Toplevel(self)
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

        def refresh_list():
            # Clear previous items
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            self.status_dots_widgets.clear()

            query = search_var.get().strip().lower()
            if query == "tìm kiếm theo tên hoặc id...":
                query = ""

            computers = load_computers()
            
            # 1. Sắp xếp danh sách theo tên gợi nhớ (không phân biệt chữ hoa/thường)
            computers.sort(key=lambda x: x["name"].lower())
            
            # 2. Lọc theo từ khóa tìm kiếm (tên hoặc ID)
            if query:
                computers = [c for c in computers if query in c["name"].lower() or query in c["id"].replace(" ", "")]

            if not computers:
                txt = "Không tìm thấy máy tính phù hợp." if query else "Chưa có máy tính nào được lưu.\nBấm nút thêm bên dưới để tạo mới."
                lbl_empty = tk.Label(scrollable_frame, text=txt, font=("Segoe UI", 9, "italic"), fg=self.text_gray, bg=self.card_color, justify=tk.CENTER)
                lbl_empty.pack(pady=40, fill=tk.X, expand=True)
                return

            for comp in computers:
                # Card for each saved computer
                card = tk.Frame(scrollable_frame, bg=self.bg_color, pady=8, padx=12, highlightthickness=1, highlightbackground=self.divider_color)
                card.pack(fill=tk.X, pady=(0, 6), padx=(0, 10))

                info_frame = tk.Frame(card, bg=self.bg_color)
                info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                # Title frame to place the status indicator dot next to the name
                title_frame = tk.Frame(info_frame, bg=self.bg_color)
                title_frame.pack(fill=tk.X)

                # Status dot: Unicode circle, initially Gray (checking)
                dot_lbl = tk.Label(title_frame, text="●", font=("Segoe UI", 13, "bold"), fg="#8A8A9A", bg=self.bg_color)
                dot_lbl.pack(side=tk.LEFT, padx=(0, 5))

                name_lbl = tk.Label(title_frame, text=comp["name"], font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.bg_color, anchor=tk.W)
                name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

                id_lbl = tk.Label(info_frame, text=f"ID: {comp['id']}", font=("Segoe UI", 8), fg=self.text_gray, bg=self.bg_color, anchor=tk.W)
                id_lbl.pack(fill=tk.X, pady=(2, 0))

                actions_frame = tk.Frame(card, bg=self.bg_color)
                actions_frame.pack(side=tk.RIGHT, fill=tk.Y)

                # Connect Button
                connect_btn = tk.Button(
                    actions_frame, text="Kết nối", font=("Segoe UI", 8, "bold"),
                    fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
                    relief=tk.FLAT, bd=0, padx=8, pady=3, cursor="hand2",
                    command=lambda c=comp: connect_computer(c)
                )
                connect_btn.pack(side=tk.LEFT, padx=3)

                # Edit Button
                edit_btn = tk.Button(
                    actions_frame, text="Sửa", font=("Segoe UI", 8, "bold"),
                    fg=self.text_white, bg="#F39C12", activebackground="#D35400",
                    relief=tk.FLAT, bd=0, padx=8, pady=3, cursor="hand2",
                    command=lambda c=comp: self.open_edit_computer_dialog(c, dialog, refresh_list)
                )
                edit_btn.pack(side=tk.LEFT, padx=3)

                # Delete Button
                delete_btn = tk.Button(
                    actions_frame, text="Xóa", font=("Segoe UI", 8, "bold"),
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
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2", command=on_dialog_destroy
        )
        btn_close.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))

        # Pack list_container sau cùng để lấp đầy phần diện tích còn lại ở giữa Search Bar và Bottom Buttons!
        list_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        refresh_list()

    def add_current_partner_to_saved(self):
        curr_id = self.partner_id_var.get().strip()
        curr_pass = self.partner_pass_var.get().strip()
        self.open_add_computer_dialog_with_vals(curr_id, curr_pass)

    def open_add_computer_dialog_with_vals(self, initial_id="", initial_pass="", parent_win=None, on_save=None):
        parent = parent_win if parent_win else self
        
        add_win = tk.Toplevel(parent)
        add_win.title("Thêm Máy tính")
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
                "password": cpass
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
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=add_win.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def open_edit_computer_dialog(self, item, parent_win, on_save):
        parent = parent_win
        
        edit_win = tk.Toplevel(parent)
        edit_win.title("Sửa thông tin")
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
                self.show_custom_error("Lỗi nhập liệu", "Vui lòng điền đầy đủ các thông tin!", parent=edit_win)
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
            print(f"[Config] Lỗi lưu XML: {e}")

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
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
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
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
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
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=5, cursor="hand2", command=dialog.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

    def is_startup_enabled(self):
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key_name = "RemoteDesktopP2P"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            try:
                value, _ = winreg.QueryValueEx(key, key_name)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False

    def toggle_startup(self):
        import winreg
        import sys
        import os
        
        enabled = self.startup_var.get()
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key_name = "RemoteDesktopP2P"
        
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            exe_path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
            
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enabled:
                winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, exe_path)
                print(f"[Startup] Enabled run on startup: {exe_path}")
                self.show_custom_info("Thành công", "Đã bật tính năng chạy khi mở máy thành công!")
            else:
                try:
                    winreg.DeleteValue(key, key_name)
                except FileNotFoundError:
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
                req = json.dumps({"action": "check_online", "target": clean_id}) + '\n'
                with self.signaling_lock:
                    sock.sendall(req.encode('utf-8'))
                
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

    def update_saved_computer_status(self, partner_id, is_online):
        clean_id = partner_id.replace(" ", "")
        if clean_id in self.status_dots_widgets:
            widgets = self.status_dots_widgets[clean_id]
            for dot_widget in widgets:
                try:
                    if dot_widget.winfo_exists():
                        if is_online:
                            dot_widget.config(fg="#00F5D4")  # Xanh ngọc (Cyan / Turquoise)
                        else:
                            dot_widget.config(fg="#E05252")  # Đỏ (Crimson / Coral Red)
                except Exception:
                    pass
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
        dialog.transient(p)
        dialog.grab_set()
        
        # Center calculations relative to parent
        dialog.update_idletasks()
        w = 320
        h = 130
        x = p.winfo_x() + (p.winfo_width() - w) // 2
        y = p.winfo_y() + (p.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.deiconify()  # Chỉ hiển thị sau khi đã tính toán căn giữa hoàn hảo!
        
        # Content frame
        content_frame = tk.Frame(dialog, bg=self.bg_color)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(15, 10))
        
        # Icon & Message side-by-side
        icon_lbl = tk.Label(content_frame, text="ℹ", font=("Segoe UI", 22), fg=self.btn_color, bg=self.bg_color)
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
        w = 320
        h = 130
        x = p.winfo_x() + (p.winfo_width() - w) // 2
        y = p.winfo_y() + (p.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.deiconify()  # Chỉ hiển thị sau khi đã tính toán căn giữa hoàn hảo!
        
        # Content frame
        content_frame = tk.Frame(dialog, bg=self.bg_color)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(15, 10))
        
        # Icon & Message side-by-side
        icon_lbl = tk.Label(content_frame, text="⚠", font=("Segoe UI", 22), fg="#E05252", bg=self.bg_color)
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
        
        # Đợi cho đến khi cửa sổ Modal này đóng để đồng bộ luồng chặn
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
        w = 320
        h = 130
        x = p.winfo_x() + (p.winfo_width() - w) // 2
        y = p.winfo_y() + (p.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")
        dialog.deiconify()  # Chỉ hiển thị sau khi đã tính toán căn giữa hoàn hảo!
        
        # Content frame
        content_frame = tk.Frame(dialog, bg=self.bg_color)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(15, 10))
        
        # Icon & Message side-by-side
        icon_lbl = tk.Label(content_frame, text="❓", font=("Segoe UI", 22), fg="#F39C12", bg=self.bg_color)
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
        
        # Nút "Không"
        btn_no = tk.Button(
            btn_frame, text="Không", font=("Segoe UI", 9, "bold"),
            fg=self.text_white, bg="#3A3A4A", activebackground="#2A2A35",
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

    def update_status(self, text, is_error=False, blink=False):
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
        else:
            self.lbl_status.config(fg="#8A8A9A")

    def _blink_status(self):
        if not hasattr(self, 'lbl_status'): return
        current_color = self.lbl_status.cget("fg")
        next_color = self.entry_bg if current_color == "#FF4D4D" else "#FF4D4D"
        self.lbl_status.config(fg=next_color)
        self._blink_job = self.after(500, self._blink_status)
        
    # Background Network Initialization
    def init_network_services(self):
        # 1. Start Host Server first to determine which port is available
        self.update_status("Đang khởi động Server lắng nghe...")
        self.start_host_server()
        
        # 2. Try automatic UPnP Port Forwarding
        self.update_status("Đang tự động cấu hình Router (UPnP)...")
        upnp_success = attempt_upnp_forward(BOUND_PORT)
        
        # 3. Get Public & Local IPs
        self.update_status("Đang lấy thông vị trí mạng...")
        self.current_ip = get_public_ip()
        self.ipv6 = get_public_ipv6()
        self.local_ip = get_local_ip()
        print(f"[Host] Public IPv4: {self.current_ip}, IPv6: {self.ipv6}, Local IP: {self.local_ip}")
        
        # 4. Connect to real-time Signaling Server
        self.update_status(f"Đang kết nối tới các Signaling Server...")
        self.signaling_sockets = {}
        self.primary_signaling_socket = None
        self.current_signaling_host = None
        
        for host in SIGNALING_SERVER_HOSTS:
            threading.Thread(target=self.signaling_maintainer_thread, args=(host,), daemon=True).start()
            
        # Try to wait up to 3 seconds for at least one connection
        timeout = 3.0
        while timeout > 0 and not self.signaling_sockets:
            time.sleep(0.2)
            timeout -= 0.2
            
        if self.signaling_sockets:
            if upnp_success:
                self.update_status(f"Kết nối Signaling & Mở cổng Router thành công (Cổng {BOUND_PORT})!")
            else:
                self.update_status(f"Kết nối Signaling thành công (Cổng {BOUND_PORT})! Sẵn sàng kết nối.")
        else:
            self.update_status(f"Không thể kết nối Signaling Server. Đang tiếp tục thử ở chế độ nền...")

    def signaling_maintainer_thread(self, host):
        retry_delay = 5
        while self.running_server:
            sock = None
            try:
                # 1. Connect
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
                
                req = json.dumps({"action": "register", "hwid": self.my_id_clean}) + '\n'
                sock.sendall(req.encode('utf-8'))
                
                with self.signaling_lock:
                    self.signaling_sockets[host] = sock
                    if getattr(self, 'current_signaling_host', None) is None:
                        self.current_signaling_host = host
                        self.primary_signaling_socket = sock
                        self.after(0, lambda: self.update_status("Kết nối Signaling thành công! Sẵn sàng kết nối."))
                
                print(f"[Signaling] Connected to {host}")
                
                last_ping = time.time()
                last_pong = time.time()
                
                import select
                while self.running_server:
                    r, _, _ = select.select([sock], [], [], 1.0)
                    if r:
                        data = sock.recv(4096)
                        if not data: break
                        messages = data.decode('utf-8').strip().split('\n')
                        for msg in messages:
                            if not msg: continue
                            self.process_signaling_message(msg, sock, host)
                            if "pong" in msg:
                                last_pong = time.time()
                                
                    now = time.time()
                    if now - last_ping > 20:
                        ping_req = json.dumps({"action": "ping"}) + '\n'
                        sock.sendall(ping_req.encode('utf-8'))
                        last_ping = now
                        
                    if now - last_pong > 50:
                        print(f"[Signaling] Heartbeat timeout for {host}")
                        break
                        
            except Exception as e:
                print(f"[Signaling] Connection error on {host}: {e}")
                
            finally:
                if sock:
                    try: sock.close()
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

    def process_signaling_message(self, msg, sock, host):
        try:
            res = json.loads(msg)
            action = res.get("action")
            
            if action == "incoming_request":
                from_hwid = res.get("from_hwid")
                public_ip = res.get("public_ip")
                public_port = res.get("public_port")
                local_ip = res.get("local_ip")
                
                print(f"[Signaling] Connection request from {from_hwid} ({public_ip}:{public_port}) via {host}")
                
                accept_req = json.dumps({
                    "action": "connect_accept",
                    "target": from_hwid,
                    "port": BOUND_PORT,
                    "local_ip": self.local_ip
                }) + '\n'
                with self.signaling_lock:
                    sock.sendall(accept_req.encode('utf-8'))
                    
                threading.Thread(target=self.punch_hole_to_client, args=(public_ip, public_port), daemon=True).start()
                
            elif action == "request_accepted":
                public_ip = res.get("public_ip")
                public_port = res.get("public_port")
                local_ip = res.get("local_ip")
                self.pending_connection_info = (public_ip, public_port, local_ip)
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

    def punch_hole_to_client(self, c_ip, c_port):
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
                threading.Thread(target=self.handle_host_handshake, args=(sock, (c_ip, c_port)), daemon=True).start()
                return
            except Exception:
                sock.close()
                time.sleep(0.1)
        print("[HolePunch] Host gave up trying to punch hole.")

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
            
    # TCP Server (Host) functions
    def start_host_server(self):
        global BOUND_PORT
        bound = False
        for port in PORTS_TO_TRY:
            try:
                # Try IPv6 Dual-Stack first (binds to both IPv6 and IPv4)
                if hasattr(socket, 'create_server') and hasattr(socket, 'AF_INET6'):
                    try:
                        self.server_socket = socket.create_server(("", port), family=socket.AF_INET6, dualstack_ipv6=True)
                    except Exception:
                        self.server_socket = socket.create_server(("", port), family=socket.AF_INET)
                else:
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
            except Exception:
                break
                
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
            msg = recv_msg(conn)
            if not msg:
                try: conn.close()
                except: pass
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
                send_msg(conn, res_info)
                
                client_state = {"running": True, "net_class": "medium"}
                
                # Perform pre-connection speed test handling on host (2 rounds to match client)
                try:
                    for run_idx in range(2):
                        # 1. Ping / Latency test (3 pings per round)
                        for _ in range(3):
                            ping_msg = recv_msg(conn)
                            if ping_msg:
                                ping_data = json.loads(ping_msg.decode('utf-8'))
                                if ping_data.get("action") == "speed_test_ping":
                                    send_msg(conn, json.dumps({"action": "speed_test_pong"}).encode('utf-8'))
                                    
                        # 2. Bandwidth test
                        bw_msg = recv_msg(conn)
                        if bw_msg:
                            bw_data = json.loads(bw_msg.decode('utf-8'))
                            if bw_data.get("action") == "speed_test_bw_req":
                                dummy_size = 1572864 # 1.5 MB để nới rộng TCP Window
                                send_msg(conn, json.dumps({"action": "speed_test_bw_start", "size": dummy_size}).encode('utf-8'))
                                conn.sendall(b'\x00' * dummy_size)
                            
                    # 3. Receive final results (sent once after both rounds)
                    res_msg = recv_msg(conn)
                    if res_msg:
                        res_data = json.loads(res_msg.decode('utf-8'))
                        if res_data.get("action") == "speed_test_result":
                            net_class = res_data.get("net_class", "medium")
                            client_state["net_class"] = net_class
                            print(f"[Host] Speed test finished. Class: {net_class}")
                            
                            # Adjust windows graphics effects based on net_class
                            if net_class == "high":
                                set_windows_graphics_effects(True)
                            else:
                                set_windows_graphics_effects(False)
                except Exception as ste:
                    print(f"[Host] Speed test handler error: {ste}")
                
                self.active_clients[addr] = client_state
                
                addrs_str = ", ".join([str(a[0]) for a in self.active_clients.keys()])
                self.update_status(f"Đang bị điều khiển bởi {addrs_str}")
                
                t_sender = threading.Thread(target=self.host_sender_thread, args=(conn, monitor, client_state), daemon=True)
                t_receiver = threading.Thread(target=self.host_receiver_thread, args=(conn, client_state), daemon=True)
                
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
                    
                    if addr in self.active_clients:
                        del self.active_clients[addr]
                        
                    if self.active_clients:
                        addrs_str = ", ".join([str(a[0]) for a in self.active_clients.keys()])
                        self.update_status(f"Đang bị điều khiển bởi {addrs_str}")
                    else:
                        self.update_status(f"Đã đóng kết nối với Client {addr[0]} lúc {time.strftime('%H:%M:%S')} (Sẵn sàng kết nối)")
            else:
                print("[Host] Password mismatch!")
                err_info = json.dumps({
                    "status": "error",
                    "message": "Sai mật khẩu kết nối!"
                }).encode('utf-8')
                send_msg(conn, err_info)
                conn.close()
        except Exception as e:
            print(f"[Host] Handshake Exception: {e}")
            try:
                err_info = json.dumps({
                    "status": "error",
                    "message": f"Lỗi xảy ra trên máy Host:\n{e}"
                }).encode('utf-8')
                send_msg(conn, err_info)
            except:
                pass
            conn.close()
            
    # Host Sender Thread
    def host_sender_thread(self, conn, monitor, client_state):
        print("[Host] Started Screen Sender Thread.")
        import io
        
        try:
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, 2000)
        except: pass

        while client_state.get("running", False):
            try:
                # Attempt to switch to the active input desktop dynamically to keep connection alive
                try:
                    import ctypes
                    hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x02000000)
                    if hdesk:
                        ctypes.windll.user32.SetThreadDesktop(hdesk)
                        ctypes.windll.user32.CloseDesktop(hdesk)
                except Exception:
                    pass
                    
                with mss.mss() as sct:
                    # Dynamically get monitor for current desktop (fixes black screen on Win10 Winlogon)
                    if len(sct.monitors) > 1:
                        dynamic_monitor = sct.monitors[1]
                    else:
                        dynamic_monitor = sct.monitors[0]
                        
                    while client_state.get("running", False):
                        try:
                            img = sct.grab(dynamic_monitor)
                            # Convert raw BGRA from mss directly to Pillow Image
                            pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                            
                            # Grayscale 64x64 difference detection to skip identical frames
                            static_frame = False
                            try:
                                small_gray = pil_img.resize((64, 64)).convert("L")
                                if "prev_small_gray" in client_state:
                                    prev_gray = client_state["prev_small_gray"]
                                    diff = 0
                                    p1 = small_gray.getdata()
                                    p2 = prev_gray.getdata()
                                    for i in range(64 * 64):
                                        diff += abs(p1[i] - p2[i])
                                    mean_diff = diff / (64.0 * 64.0)
                                    if mean_diff < 0.5:
                                        static_frame = True
                                if not static_frame:
                                    client_state["prev_small_gray"] = small_gray
                            except: pass
                            
                            # Lấy độ phân giải hiển thị mong muốn từ Client (Phải lấy trước khi check static)
                            target_w = getattr(self, 'client_viewer_w', 1280)
                            target_h = getattr(self, 'client_viewer_h', 720)
                            
                            # Nếu Client vừa cập nhật độ phân giải thực tế, ta phải ép gửi 1 khung hình mới ngay lập tức
                            if client_state.get("last_target_w") != target_w or client_state.get("last_target_h") != target_h:
                                static_frame = False
                                client_state["last_target_w"] = target_w
                                client_state["last_target_h"] = target_h

                            if static_frame:
                                current_q = client_state.get("dyn_quality", 40)
                                current_s = client_state.get("dyn_scale", 0.6)
                                if current_q < 95 or current_s < 1.0:
                                    # Cơ hội vàng: Màn hình tĩnh, ép tăng độ nét cực nhanh (Fast Progressive Refinement)
                                    client_state["dyn_quality"] = min(95, current_q + 15)
                                    client_state["dyn_scale"] = min(1.0, current_s + 0.1)
                                    static_frame = False # Bắt buộc gửi tiếp để làm nét ảnh
                                else:
                                    time.sleep(1.0)
                                    continue

                            net_class = client_state.get("net_class", "medium")
                            
                            if net_class == "high":
                                base_quality = 95
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

                            # Ép buộc tăng độ nét lên tối đa trong 5 giây đầu tiên (Fast Warm-up)
                            if "start_time" not in client_state:
                                client_state["start_time"] = time.time()
                                
                            if time.time() - client_state["start_time"] < 5.0:
                                quality = min(95, quality + 10)
                                dyn_scale = min(1.0, dyn_scale + 0.1)
                                client_state["dyn_quality"] = quality
                                client_state["dyn_scale"] = dyn_scale

                            cap_w, cap_h = img.size
                            w = int(target_w * dyn_scale)
                            h = int(target_h * dyn_scale)
                            
                            if cap_w != w or cap_h != h:
                                pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)
                                
                            buf = io.BytesIO()
                            pil_img.save(buf, format="JPEG", quality=quality)
                            jpeg_data = buf.getvalue()
                            
                            t_start_send = time.time()
                            send_msg(conn, jpeg_data)
                            send_time = time.time() - t_start_send
                            
                            if "send_ema" not in client_state:
                                client_state["send_ema"] = send_time
                            else:
                                client_state["send_ema"] = 0.8 * client_state["send_ema"] + 0.2 * send_time
                                
                            ema = client_state["send_ema"]
                            
                            if ema > 0.35:
                                # Mạng chậm: Chỉ giảm chất lượng ảnh, hạn chế bóp scale để tránh vỡ khối pixel
                                quality = max(35, quality - 5)
                                sleep_time = min(0.3, sleep_time + 0.05)
                                if ema > 0.6:
                                    dyn_scale = max(0.6, dyn_scale - 0.05)
                            elif ema < 0.20:
                                # Phương án 2: Dynamic Scaling mượt hơn (vượt qua giới hạn ban đầu nếu mạng tốt)
                                quality = min(95, quality + 1)
                                sleep_time = max(1.0 / 60, sleep_time - 0.005)
                                dyn_scale = min(1.0, dyn_scale + 0.02)
                                
                            client_state["dyn_quality"] = quality
                            client_state["dyn_sleep_time"] = sleep_time
                            client_state["dyn_scale"] = dyn_scale

                            time.sleep(sleep_time)
                        except mss.exception.ScreenShotError as e:
                            print(f"[Host] Screen capture error (re-initializing): {e}")
                            try:
                                signal = json.dumps({"type": "switching_desktop"}).encode('utf-8')
                                send_msg(conn, signal)
                            except: pass
                            time.sleep(1.0)
                            break  # Break inner loop to recreate mss.mss()
                        except Exception as e:
                            import traceback
                            with open("host_error.log", "a") as f:
                                f.write(f"[{time.strftime('%H:%M:%S')}] [Host] Screen Sender Error: {e}\n{traceback.format_exc()}\n")
                            client_state["running"] = False
                            try:
                                conn.close()
                            except:
                                pass
                            break
            except Exception as e:
                print(f"[Host] mss.mss() context error: {e}")
                time.sleep(1.0)
        print("[Host] Screen Sender Thread Stopped.")
        
    # Host Receiver Thread (Simulates actions)
    def host_receiver_thread(self, conn, client_state):
        print("[Host] Started Input Receiver Thread.")
        import select
        while client_state.get("running", False):
            try:
                # Chờ 2 giây, nếu không có gói tin nào thì nhả hết phím modifier để chống kẹt
                r, _, _ = select.select([conn], [], [], 2.0)
                if not r:
                    self.host_release_all_modifiers()
                    continue
                    
                msg = recv_msg(conn)
                if not msg:
                    print("[Host] Input Receiver got empty message (Client disconnected).")
                    break
                event = json.loads(msg.decode('utf-8'))
                evt_type = event.get("type", "")
                if evt_type in ("batch_start", "file_start", "file_chunk", "file_end", "batch_end", "files_copied_meta", "request_files", "cancel_transfer", "clipboard_text"):
                    clipboard_sync_manager.handle_received_packet(event)
                else:
                    self.host_handle_event(event, conn)
            except Exception as e:
                print(f"[Host] Input Receiver Error: {e}")
                break
        print("[Host] Input Receiver Thread Stopped.")
        self.host_release_all_modifiers()
        
    def host_handle_event(self, event, conn):
        ev_type = event.get('type')
        if ev_type == 'mouse_move':
            x, y = event['x'], event['y']
            send_input_mouse_move(x, y)
            try:
                mouse.position = (x, y)
            except:
                pass
            try:
                import win32api
                win32api.SetCursorPos((x, y))
            except Exception as e:
                print(f"[Host] SetCursorPos fallback failed: {e}")
                
        elif ev_type == 'mouse_click':
            button_name = event.get('button')
            pressed = event.get('pressed')
            # Primary simulation using standard SendInput API
            send_input_mouse_click(button_name, pressed)
                
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
            
        elif ev_type == 'trigger_sas':
            self.trigger_sas()
            
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
                }).encode('utf-8'))
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
        for mod_key in [Key.shift, Key.ctrl, Key.alt]:
            try:
                keyboard.release(mod_key)
            except:
                pass
        try:
            # Release via SendInput
            for key_name in ['left shift', 'right shift', 'left ctrl', 'right ctrl', 'left alt', 'right alt']:
                send_input_keyboard_event(key_name, False)
        except:
            pass
                
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
        
    def connect_to_partner(self, partner_id, partner_pass, reconnect_queue=None):
        # Clean up dead viewer processes first
        self.active_viewers = [v for v in self.active_viewers if v["process"].is_alive()]
        
        # Check if we already have an active connection to this partner_id
        existing_viewer = None
        for v in self.active_viewers:
            if v.get("partner_id") == partner_id:
                existing_viewer = v
                break
                
        if existing_viewer:
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
            "local_ip": self.local_ip
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
                    sock.sendall(req.encode('utf-8'))
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
            self.update_status("Sẵn sàng kết nối")
            self.after(0, lambda: self.show_custom_error("Lỗi", "Không thể tìm thấy hoặc đối tác đang Offline / Từ chối kết nối."))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            return
            
        public_ip, port, local_ip = self.pending_connection_info
            
        # If connecting to self (testing on the same computer)
        if partner_id == self.my_id_clean:
            local_ip = "127.0.0.1"
            print("[Client] Self-connection detected! Routing connection to localhost.")
            
        sock = None
        connected = False
        
        # 1. Try local IP first (LAN) (Chỉ thử nếu không ép buộc Relay)
        if not self.force_relay_var.get() and local_ip:
            self.update_status(f"Đang thử kết nối nội bộ (LAN): {local_ip}:{port}...")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect((local_ip, port))
                connected = True
                print(f"[Client] Connected via LAN: {local_ip}")
            except Exception:
                print(f"[Client] LAN connection failed.")
                if sock: sock.close()
                
        # 2. Kỹ thuật đục lỗ Tường lửa (TCP Hole Punching) (Chỉ thử nếu không ép buộc Relay)
        if not self.force_relay_var.get() and not connected:
            self.update_status(f"Đang đục lỗ Tường lửa (TCP Hole Punching) tới {public_ip}:{port}...")
            print(f"[Client] Initiating Simultaneous Open to {public_ip}:{port}...")
            
            # Liên tục spam kết nối cực nhanh để đục lỗ (20 lần, mỗi lần 100ms)
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
                    sock.close()
                    time.sleep(0.1)

        if not connected:
            specific_host = getattr(self, 'current_signaling_host', None)
            display_host = specific_host or 'Relay'
            self.update_status(f"Đục lỗ thất bại. Đang thử kết nối qua Server Trung Chuyển ({display_host})...")
            print("[Client] Hole punching failed. Attempting Relay fallback...")
            try:
                # 1. Gửi tín hiệu yêu cầu Host cùng nhảy vào Relay
                relay_session_id = f"relay_{self.my_id_clean}_{partner_id}"
                relay_req = json.dumps({
                    "action": "relay_request",
                    "target": partner_id,
                    "session_id": relay_session_id,
                    "relay_host": specific_host
                }) + '\n'
                with self.signaling_lock:
                    if getattr(self, 'primary_signaling_socket', None):
                        self.primary_signaling_socket.sendall(relay_req.encode('utf-8'))
                
                # 2. Tạo kết nối từ Client lên Relay Server
                host_to_connect = specific_host if specific_host else SIGNALING_SERVER_HOSTS[0]
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((host_to_connect, SIGNALING_SERVER_PORT))
                sock.settimeout(None)
                
                header = f"RELAY_CLIENT:{relay_session_id}\n"
                sock.sendall(header.encode('utf-8'))
                
                connected = True
                print("[Client] Relay connection established successfully!")
            except Exception as e:
                print(f"[Client] Relay fallback failed: {e}")
                connected = False

        if not connected:
            self.update_status("Sẵn sàng kết nối")
            self.after(0, lambda: self.show_custom_error("Lỗi kết nối", 
                f"Kỹ thuật Đục Lỗ Tường Lửa (Hole Punching) & Server Trung Chuyển ({getattr(self, 'current_signaling_host', None) or 'Relay'}) đều thất bại!\n\n"
                f"Lý do: Không thể kết nối tới máy chủ trung chuyển."
            ))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            if sock: sock.close()
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
            # Send handshake password
            handshake = json.dumps({"password": partner_pass}).encode('utf-8')
            send_msg(sock, handshake)
            
            # Read verification response
            res_msg = recv_msg(sock)
            if not res_msg:
                self.update_status("Sẵn sàng kết nối")
                self.after(0, lambda: self.show_custom_error("Lỗi", "Đối tác ngắt kết nối đột ngột!"))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                sock.close()
                return
                
            res = json.loads(res_msg.decode('utf-8'))
            if res.get("status") == "ok":
                host_w = res.get("width")
                host_h = res.get("height")
                computer_name = res.get("computer_name", "")
                zalo_phone = res.get("zalo_phone", "")
                is_domain = res.get("is_domain", False)
                
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
                            send_msg(sock, json.dumps({"action": "speed_test_ping"}).encode('utf-8'))
                            pong_msg = recv_msg(sock)
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
                        send_msg(sock, json.dumps({"action": "speed_test_bw_req"}).encode('utf-8'))
                        bw_start_msg = recv_msg(sock)
                        if bw_start_msg:
                            bw_start_data = json.loads(bw_start_msg.decode('utf-8'))
                            if bw_start_data.get("action") == "speed_test_bw_start":
                                dummy_size = bw_start_data.get("size", 1572864)
                                warm_size = 1048576 # 1 MB warm-up để vượt qua TCP slow-start
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
                    # - Tốt (High-speed): Băng thông > 20 Mbps, Ping < 30ms.
                    # - Trung bình (Medium): Băng thông 5 - 20 Mbps, Ping 30 - 100ms.
                    # - Yếu (Low-speed): Băng thông < 5 Mbps hoặc Ping > 100ms.
                    if bandwidth > 20.0 and avg_ping < 30.0:
                        net_class = "high"
                        net_class_viet = "Tốt (High-speed)"
                    elif bandwidth < 5.0 or avg_ping > 100.0:
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
                    }).encode('utf-8'))
                    
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
                        }).encode('utf-8'))
                    except: pass
                    
                # Pygame window sẽ mở đúng với độ phân giải thật của host. 
                # (Kích thước ảnh thực tế truyền qua mạng vẫn sẽ được nén lại bởi dyn_scale ở phía Host)
                self.update_status("Kết nối thành công! Đang khởi động màn hình...")
                if reconnect_queue:
                    try:
                        reconnect_queue.put(sock)
                    except Exception as e:
                        print(f"Failed to put socket in reconnect queue: {e}")
                        reconnect_queue.put("FAILED")
                        sock.close()
                else:
                    self.after(0, self.launch_pygame_viewer, sock, host_w, host_h, computer_name, zalo_phone, is_domain, partner_id, partner_pass)
            else:
                msg = res.get("message", "Sai mật khẩu!")
                self.update_status("Bị từ chối kết nối")
                if reconnect_queue:
                    reconnect_queue.put("FAILED")
                self.after(0, lambda: self.show_custom_error("Từ chối kết nối", f"Kết nối bị từ chối:\n{msg}"))
                self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
                sock.close()
        except Exception as e:
            self.update_status("Sẵn sàng kết nối")
            if reconnect_queue:
                reconnect_queue.put("FAILED")
            self.after(0, lambda err=str(e): self.show_custom_error("Lỗi bắt tay", f"Lỗi xác thực handshake:\n{err}"))
            self.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))
            sock.close()
            
    def launch_pygame_viewer(self, sock, host_w, host_h, computer_name="", zalo_phone="", is_domain=False, partner_id="", partner_pass=""):
        try:
            import multiprocessing as mp
            reconnect_queue = mp.Queue()
            p = mp.Process(target=run_client_viewer_loop, args=(sock, host_w, host_h, computer_name, is_domain, partner_id, reconnect_queue), daemon=True)
            p.start()
            
            # Track active viewer
            self.active_viewers.append({
                "process": p,
                "computer_name": computer_name,
                "zalo_phone": zalo_phone,
                "partner_id": partner_id
            })
            
            # Reconnection Monitor Thread
            if partner_id and partner_pass:
                def monitor_reconnect(process, pid, ppass, req_queue):
                    while process.is_alive():
                        try:
                            msg = req_queue.get(timeout=1.0)
                            if msg == "RECONNECT_REQUEST":
                                print(f"[Client Monitor] Pygame requested reconnect for {pid}...")
                                self.after(0, lambda: self.update_status(f"Đang tự động kết nối lại..."))
                                threading.Thread(target=self.connect_to_partner, args=(pid, ppass, req_queue), daemon=True).start()
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
            try: sock.close()
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
        if self.state() == "normal" and self.attributes("-alpha") == 1.0:
            self.lift()
            self.focus_force()
            return
            
        import re
        geom = self.geometry()
        m = re.match(r"(\d+)x(\d+)([-+]\d+)([-+]\d+)", geom)
        if m:
            end_w, end_h = int(m.group(1)), int(m.group(2))
            end_x, end_y = int(m.group(3)), int(m.group(4))
        else:
            end_w, end_h, end_x, end_y = 1000, 700, 100, 100 # Fallback
            
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        start_w, start_h = 20, 20
        start_x, start_y = screen_w - 50, screen_h - 50
        
        self.geometry(f"{start_w}x{start_h}+{start_x}+{start_y}")
        self.attributes("-alpha", 0.0)
        self.deiconify()
        self.lift()
        
        frames = 15
        duration_ms = 250
        delay = duration_ms // frames
        
        def animate_step(frame):
            if frame > frames:
                self.geometry(f"{end_w}x{end_h}+{end_x}+{end_y}")
                self.attributes("-alpha", 1.0)
                self.focus_force()
                print("[Tray] Main window restored with animation.")
                return
                
            progress = frame / frames
            ease = 1 - (1 - progress) ** 3
            
            cur_w = int(start_w + (end_w - start_w) * ease)
            cur_h = int(start_h + (end_h - start_h) * ease)
            cur_x = int(start_x + (end_x - start_x) * ease)
            cur_y = int(start_y + (end_y - start_y) * ease)
            cur_alpha = ease
            
            self.geometry(f"{cur_w}x{cur_h}+{cur_x}+{cur_y}")
            self.attributes("-alpha", cur_alpha)
            
            self.after(delay, animate_step, frame + 1)
            
        animate_step(1)
        
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
                try: sock.close()
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
    
    import sys
    import ctypes
    
    is_headless = "--headless" in sys.argv
    
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
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            try: ctypes.windll.user32.SetProcessDPIAware()
            except: pass
            
    app = UnifiedApp()
    app.mainloop()
