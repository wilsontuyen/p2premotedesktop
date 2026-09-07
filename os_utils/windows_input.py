import ctypes
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
MOUSEEVENTF_VIRTUALDESK = 0x4000

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

# Cached virtual-desktop metrics for mouse (multi-monitor)
_cached_screen_w = 0
_cached_screen_h = 0
_cached_screen_x = 0
_cached_screen_y = 0
_cached_screen_time = 0

def send_input_mouse_move(x, y):
    global _cached_screen_w, _cached_screen_h, _cached_screen_x, _cached_screen_y, _cached_screen_time
    try:
        now = time.monotonic() if hasattr(time, 'monotonic') else time.time()
        if now - _cached_screen_time > 2.0 or _cached_screen_w == 0:
            user32 = ctypes.windll.user32
            _cached_screen_x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            _cached_screen_y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
            _cached_screen_w = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            _cached_screen_h = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            if _cached_screen_w <= 0 or _cached_screen_h <= 0:
                _cached_screen_x = 0
                _cached_screen_y = 0
                _cached_screen_w = user32.GetSystemMetrics(0)
                _cached_screen_h = user32.GetSystemMetrics(1)
            _cached_screen_time = now
        w, h = _cached_screen_w, _cached_screen_h
        ox, oy = _cached_screen_x, _cached_screen_y
        if w > 1 and h > 1:
            normalized_x = int(((x - ox) * 65535) / (w - 1))
            normalized_y = int(((y - oy) * 65535) / (h - 1))
            normalized_x = max(0, min(65535, normalized_x))
            normalized_y = max(0, min(65535, normalized_y))
            inp = INPUT()
            inp.type = INPUT_MOUSE
            inp.union.mi = MOUSEINPUT(
                normalized_x, normalized_y, 0,
                MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
                0, None
            )
            ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    except Exception as e:
        print(f"[SendInput] Mouse move injection failed: {e}")

_remote_modifier_keys = set()
