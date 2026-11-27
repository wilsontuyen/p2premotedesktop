# -*- coding: utf-8 -*-
"""
xp_host/xp_input.py
Giả lập Chuột, Bàn phím, Gõ mật khẩu và tổ hợp Ctrl+Alt+Del (SAS) trên Windows XP
bằng Win32 SendInput API thuần ctypes (không dùng pynput hay UIAutomation COM).
"""

import ctypes
from ctypes import wintypes
import sys
import time

from .xp_capture import attach_thread_to_active_desktop

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
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", INPUT_UNION),
    ]


_user32 = getattr(ctypes.windll, "user32", None) if sys.platform == "win32" else None
if _user32:
    try:
        _user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
        _user32.SendInput.restype = wintypes.UINT
    except Exception:
        pass

VK_MAP = {
    "space": 0x20,
    "enter": 0x0D,
    "return": 0x0D,
    "keypad enter": 0x0D,
    "escape": 0x1B,
    "esc": 0x1B,
    "backspace": 0x08,
    "tab": 0x09,
    "left shift": 0xA0,
    "right shift": 0xA1,
    "shift": 0x10,
    "left ctrl": 0xA2,
    "right ctrl": 0xA3,
    "ctrl": 0x11,
    "left alt": 0xA4,
    "right alt": 0xA5,
    "alt": 0x12,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "caps lock": 0x14,
    "capslock": 0x14,
    "insert": 0x2D,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "page up": 0x21,
    "page down": 0x22,
    "print screen": 0x2C,
    "scroll lock": 0x91,
    "pause": 0x13,
    "numlock": 0x90,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "`": 0xC0, "~": 0xC0,
    "-": 0xBD, "_": 0xBD,
    "=": 0xBB, "+": 0xBB,
    "[": 0xDB, "{": 0xDB,
    "]": 0xDD, "}": 0xDD,
    "\\": 0xDC, "|": 0xDC,
    ";": 0xBA, ":": 0xBA,
    "'": 0xDE, '"': 0xDE,
    ",": 0xBC, "<": 0xBC,
    ".": 0xBE, ">": 0xBE,
    "/": 0xBF, "?": 0xBF,
    "left meta": 0x5B, "right meta": 0x5C,
    "left windows": 0x5B, "right windows": 0x5C,
    "left super": 0x5B, "right super": 0x5C,
    "menu": 0x5D,
    "[0]": 0x60, "[1]": 0x61, "[2]": 0x62, "[3]": 0x63, "[4]": 0x64,
    "[5]": 0x65, "[6]": 0x66, "[7]": 0x67, "[8]": 0x68, "[9]": 0x69,
    "[.]": 0x6E, "[/]": 0x6F, "[*]": 0x6A, "[-]": 0x6D, "[+]": 0x6B,
}

_EXTENDED_VKS = frozenset({
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
    0x2D, 0x2E, 0x5B, 0x5C, 0x5D, 0x6F, 0xA3, 0xA5,
})

_SHIFTED_ASCII = {
    "!": "1", "@": "2", "#": "3", "$": "4", "%": "5",
    "^": "6", "&": "7", "*": "8", "(": "9", ")": "0",
    "_": "-", "+": "=", "{": "[", "}": "]", "|": "\\",
    ":": ";", '"': "'", "<": ",", ">": ".", "?": "/", "~": "`",
}

_active_modifiers = set()


def _send_inputs(inputs_list):
    if not _user32 or not inputs_list:
        return 0
    arr = (INPUT * len(inputs_list))(*inputs_list)
    res = _user32.SendInput(len(inputs_list), ctypes.byref(arr), ctypes.sizeof(INPUT))
    if res == 0:
        attach_thread_to_active_desktop()
        res = _user32.SendInput(len(inputs_list), ctypes.byref(arr), ctypes.sizeof(INPUT))
    return res


def get_cursor_pos():
    if not _user32:
        return None
    pt = wintypes.POINT()
    if _user32.GetCursorPos(ctypes.byref(pt)):
        return int(pt.x), int(pt.y)
    return None


def _normalize_abs_coords(x, y):
    if not _user32:
        return 0, 0, MOUSEEVENTF_ABSOLUTE
    vx = int(_user32.GetSystemMetrics(76))  # SM_XVIRTUALSCREEN
    vy = int(_user32.GetSystemMetrics(77))  # SM_YVIRTUALSCREEN
    vw = int(_user32.GetSystemMetrics(78))  # SM_CXVIRTUALSCREEN
    vh = int(_user32.GetSystemMetrics(79))  # SM_CYVIRTUALSCREEN
    if vw > 1 and vh > 1:
        nx = int(round(((x - vx) * 65535.0) / float(vw - 1)))
        ny = int(round(((y - vy) * 65535.0) / float(vh - 1)))
        flags = MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
    else:
        sw = max(2, int(_user32.GetSystemMetrics(0)) or 1024)
        sh = max(2, int(_user32.GetSystemMetrics(1)) or 768)
        nx = int(round((x * 65535.0) / float(sw - 1)))
        ny = int(round((y * 65535.0) / float(sh - 1)))
        flags = MOUSEEVENTF_ABSOLUTE
    return max(0, min(65535, nx)), max(0, min(65535, ny)), flags


def send_mouse_move(x, y):
    nx, ny, base_flags = _normalize_abs_coords(int(x), int(y))
    inp = INPUT(type=INPUT_MOUSE)
    inp.union.mi = MOUSEINPUT(dx=nx, dy=ny, mouseData=0, dwFlags=MOUSEEVENTF_MOVE | base_flags, time=0, dwExtraInfo=None)
    _send_inputs([inp])


def send_mouse_click(button, pressed, x=None, y=None):
    btn_map = {
        ("left", True): MOUSEEVENTF_LEFTDOWN,
        ("left", False): MOUSEEVENTF_LEFTUP,
        ("right", True): MOUSEEVENTF_RIGHTDOWN,
        ("right", False): MOUSEEVENTF_RIGHTUP,
        ("middle", True): MOUSEEVENTF_MIDDLEDOWN,
        ("middle", False): MOUSEEVENTF_MIDDLEUP,
    }
    flag = btn_map.get((str(button or "left").lower(), bool(pressed)))
    if not flag:
        return
    items = []
    if x is not None and y is not None:
        nx, ny, base_flags = _normalize_abs_coords(int(x), int(y))
        mv = INPUT(type=INPUT_MOUSE)
        mv.union.mi = MOUSEINPUT(dx=nx, dy=ny, mouseData=0, dwFlags=MOUSEEVENTF_MOVE | base_flags, time=0, dwExtraInfo=None)
        items.append(mv)
    clk = INPUT(type=INPUT_MOUSE)
    clk.union.mi = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flag, time=0, dwExtraInfo=None)
    items.append(clk)
    _send_inputs(items)


def send_mouse_scroll(dx, dy):
    if not dy:
        return
    wheel_delta = int(dy * 120)
    inp = INPUT(type=INPUT_MOUSE)
    inp.union.mi = MOUSEINPUT(
        dx=0,
        dy=0,
        mouseData=ctypes.c_ulong(wheel_delta & 0xFFFFFFFF).value,
        dwFlags=MOUSEEVENTF_WHEEL,
        time=0,
        dwExtraInfo=None,
    )
    _send_inputs([inp])


def _make_vk_input(vk, pressed):
    scan = _user32.MapVirtualKeyW(vk, 0) if _user32 else 0
    flags = 0 if pressed else KEYEVENTF_KEYUP
    if vk in _EXTENDED_VKS:
        flags |= KEYEVENTF_EXTENDEDKEY
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.union.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None)
    return inp


def _make_unicode_input(ch, pressed):
    flags = KEYEVENTF_UNICODE | (0 if pressed else KEYEVENTF_KEYUP)
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.union.ki = KEYBDINPUT(wVk=0, wScan=ord(ch), dwFlags=flags, time=0, dwExtraInfo=None)
    return inp


def send_keyboard_event(key_name, pressed):
    if not key_name:
        return
    k_raw = str(key_name)
    k_low = k_raw.lower()
    pressed = bool(pressed)

    vk = VK_MAP.get(k_low)
    if vk is None and len(k_raw) == 1:
        ch = k_raw
        if "a" <= ch.lower() <= "z":
            vk = ord(ch.upper())
        elif "0" <= ch <= "9":
            vk = ord(ch)
        elif ch in _SHIFTED_ASCII and _active_modifiers:
            base = _SHIFTED_ASCII[ch]
            vk = VK_MAP.get(base) or ord(base.upper())
        elif ord(ch) > 127 or not _active_modifiers:
            # Gõ trực tiếp ký tự tiếng Việt Unicode hoặc ký hiệu đặc biệt
            _send_inputs([_make_unicode_input(ch, pressed)])
            return

    if vk is not None:
        if vk in (0x10, 0xA0, 0xA1, 0x11, 0xA2, 0xA3, 0x12, 0xA4, 0xA5, 0x5B, 0x5C):
            if pressed:
                _active_modifiers.add(vk)
            else:
                _active_modifiers.discard(vk)
        _send_inputs([_make_vk_input(vk, pressed)])


def release_all_modifiers():
    for vk in (0xA0, 0xA1, 0x10, 0xA2, 0xA3, 0x11, 0xA4, 0xA5, 0x12, 0x5B, 0x5C):
        try:
            _send_inputs([_make_vk_input(vk, False)])
        except Exception:
            pass
    _active_modifiers.clear()


def type_text_unicode(text):
    if not text:
        return
    attach_thread_to_active_desktop()
    release_all_modifiers()
    for ch in str(text):
        if ch in ("\r", "\n"):
            _send_inputs([_make_vk_input(0x0D, True), _make_vk_input(0x0D, False)])
        else:
            _send_inputs([_make_unicode_input(ch, True), _make_unicode_input(ch, False)])
        time.sleep(0.01)


def trigger_xp_ctrl_alt_del():
    """
    Mở khóa hộp thoại 'Press Ctrl+Alt+Delete to begin' (GINA / msgina.dll) trên Windows XP:
    Trên Windows XP (Interactive Service chạy quyền SYSTEM gắn vào desktop Winlogon),
    gửi thông điệp WM_HOTKEY (MOD_ALT | MOD_CONTROL, VK_DELETE) tới cửa sổ SAS window
    sẽ kích hoạt ngay màn hình nhập User/Password của XP!
    """
    if not _user32:
        return False
    attach_thread_to_active_desktop()
    WM_HOTKEY = 0x0312
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    VK_DELETE = 0x2E
    lparam = ((VK_DELETE & 0xFFFF) << 16) | (MOD_ALT | MOD_CONTROL)
    try:
        sas_hwnd = _user32.FindWindowW(ctypes.c_wchar_p("SAS window class"), ctypes.c_wchar_p("SAS window"))
        if sas_hwnd:
            _user32.PostMessageW(sas_hwnd, WM_HOTKEY, 0, lparam)
            return True
        _user32.PostMessageW(0xFFFF, WM_HOTKEY, 0, lparam)  # HWND_BROADCAST fallback
        return True
    except Exception:
        return False
