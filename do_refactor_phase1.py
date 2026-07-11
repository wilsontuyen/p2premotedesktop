import os
import re
import sys

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# 1. logger.py
logger_code = """import os
import time
import sys

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
            
        log_line = f"{timestamp} File: {filename} | Size: {size_str}\\n"
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
            f.write(f"{timestamp} [PID {os.getpid()}] {msg}\\n")
    except:
        pass

def log_activity(msg):
    try:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        filepath = os.path.join(app_dir, "activity_log.txt")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} - {msg}\\n")
    except Exception as e:
        print(f"[Log] Lỗi ghi activity_log.txt: {e}")
"""

logger_pattern = re.compile(
    r"def get_log_filepath\(filename\):.*?def log_activity\(msg\):.*?print\(f\"\[Log\] Lỗi ghi activity_log\.txt: \{e\}\"\)\n",
    re.DOTALL
)

# 2. hwid.py
hwid_code = """import os
import subprocess
import hashlib
import socket

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
        script_hdd = \"\"\"
        $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" | Get-CimAssociatedInstance -ResultClassName Win32_DiskPartition -ErrorAction SilentlyContinue | Get-CimAssociatedInstance -ResultClassName Win32_DiskDrive -ErrorAction SilentlyContinue
        if ($disk) { $disk[0].SerialNumber } else { (Get-CimInstance Win32_DiskDrive)[0].SerialNumber }
        \"\"\"
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
            ['powershell', '-Command', '(Get-ItemProperty -Path "HKLM:\\\\SOFTWARE\\\\Microsoft\\\\Cryptography" -Name "MachineGuid").MachineGuid'],
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
        script = \"\"\"
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
        \"\"\"
        res_mac = subprocess.run(
            ['powershell', '-Command', script],
            capture_output=True, text=True, startupinfo=startupinfo
        )
        if res_mac and res_mac.stdout:
            for line in res_mac.stdout.split('\\n'):
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
"""

hwid_pattern = re.compile(
    r"# Helper to fetch hardware identifiers \(CPUID & HDD Serial\)\ndef get_hwid\(\):.*?    return \",\"\.join\(ips\)\n",
    re.DOTALL
)

# 3. input_simulator.py
input_sim_code = """import ctypes
from ctypes import wintypes
import time

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
    '\\\\': 0xDC,         # VK_OEM_5
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
"""

input_sim_pattern = re.compile(
    r"# Ctypes definitions for SendInput API \(standard modern input simulation\).*?def send_input_mouse_move\(x, y\):.*?        print\(f\"\[SendInput\] Mouse move injection failed: \{e\}\"\)\n",
    re.DOTALL
)

print(f"Finding blocks to replace in app.py...")

content, n1 = logger_pattern.subn("from utils.logger import get_log_filepath, log_file_transfer, log_debug, log_activity\\n", content)
content, n2 = hwid_pattern.subn("from utils.hwid import get_hwid, get_local_ip\\n", content)
content, n3 = input_sim_pattern.subn("from utils.input_simulator import send_input_keyboard_event, send_input_mouse_click, send_input_mouse_scroll, send_input_mouse_move\\n", content)

print(f"Replacements made: logger={n1}, hwid={n2}, input={n3}")

if n1 == 1 and n2 == 1 and n3 == 1:
    os.makedirs("d:/Data/AG/remote_desktop/utils", exist_ok=True)
    with open("d:/Data/AG/remote_desktop/utils/__init__.py", "w", encoding="utf-8") as f:
        pass
    with open("d:/Data/AG/remote_desktop/utils/logger.py", "w", encoding="utf-8") as f:
        f.write(logger_code)
    with open("d:/Data/AG/remote_desktop/utils/hwid.py", "w", encoding="utf-8") as f:
        f.write(hwid_code)
    with open("d:/Data/AG/remote_desktop/utils/input_simulator.py", "w", encoding="utf-8") as f:
        f.write(input_sim_code)
        
    with open(app_py, "w", encoding="utf-8") as f:
        f.write(content)
    print("Refactor successful!")
else:
    print("Error: Could not find all blocks to replace exactly. Regex might need tweaking.")
