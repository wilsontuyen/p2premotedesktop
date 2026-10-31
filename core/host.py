import os
import sys
import time
import json
import queue
import threading
import socket
import ctypes
import struct
import base64
import platform
import io
import select
import traceback
if sys.platform == "win32":
    import winreg
    from ctypes import wintypes
import zlib
import mss
import tkinter as tk
from PIL import Image, ImageChops
import cv2
import numpy as np
from core.i18n import _

from core.config import *
try:
    from host_build_flag import HOST_ONLY_BUILD
except Exception:
    HOST_ONLY_BUILD = False
from network.socket_utils import socket_passwords, force_close_socket, APP_KEY
from utils.input_simulator import INPUT, INPUT_KEYBOARD, KEYEVENTF_UNICODE, KEYEVENTF_KEYUP, _remote_modifier_keys
from PIL import Image


from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from utils.logger import log_debug, log_activity, log_file_transfer
from network.socket_utils import send_msg, recv_msg, is_lan_socket, tune_socket_for_lan_bulk
from utils.input_simulator import send_input_keyboard_event, send_input_mouse_click, send_input_mouse_click_at, send_input_mouse_move, send_input_mouse_scroll
from core.clipboard_agent import ClipboardSyncManager, clipboard_sync_manager, run_clipboard_agent_mode, CLIPBOARD_PKT_TYPES

if getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__') or ("__compiled__" in globals()):
    app_dir = os.path.dirname(os.path.abspath(sys.executable))
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Host Utilities
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

from os_utils.system import (
    get_session_id,
    get_desktop_name,
    get_input_desktop_name,
    get_desktop_name_from_handle,
    is_secure_desktop,
    check_desktop_change,
    is_machine_domain_joined,
    open_input_desktop_handle,
    open_named_desktop_handle,
    attach_process_window_station,
    uac_consent_running,
    attach_thread_for_remote_input,
    boost_process_priority,
)

_desktop_name_from_handle = get_desktop_name_from_handle

def _encode_switching_desktop():
    desk = ""
    try:
        desk = get_input_desktop_name()
    except Exception:
        try:
            desk = get_desktop_name()
        except Exception:
            desk = ""
    return json.dumps({"type": "switching_desktop", "desktop": desk}).encode("utf-8")

def _is_secure_capture_desktop():
    """Winlogon / UAC / sign-out — không phải Default hay màn riêng tư."""
    try:
        name = (get_desktop_name() or "default").lower()
        return name not in ("default", "", "agprivacydesk")
    except Exception:
        return False

def _is_winlogon_thread_desktop():
    return _is_secure_capture_desktop()

def _logonui_running():
    if sys.platform != "win32":
        return False
    now = time.time()
    cache = getattr(_logonui_running, "_c", (0.0, False))
    if now - cache[0] < 0.12:
        return cache[1]
    found = False
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            if str(p.info.get("name") or "").lower() == "logonui.exe":
                found = True
                break
    except Exception:
        found = False
    _logonui_running._c = (now, found)
    return found

def _session_has_interactive_user():
    """True/False nếu gọi được WTSQueryUserToken (agent SYSTEM). None nếu không xác định."""
    if sys.platform != "win32":
        return None
    now = time.time()
    cache = getattr(_session_has_interactive_user, "_c", (0.0, None))
    if now - cache[0] < 0.2:
        return cache[1]
    val = None
    try:
        import win32ts
        import win32api
        sid = get_session_id()
        h = win32ts.WTSQueryUserToken(int(sid))
        win32api.CloseHandle(h)
        val = True
    except Exception as e:
        err = getattr(e, "winerror", None)
        if err is None and getattr(e, "args", None):
            err = e.args[0]
        # 5 ACCESS_DENIED, 1314 PRIVILEGE_NOT_HELD: không phải SYSTEM → bỏ qua.
        if err in (5, 1314):
            val = None
        else:
            val = False
    _session_has_interactive_user._c = (now, val)
    return val

def _explorer_running():
    if sys.platform != "win32":
        return False
    now = time.time()
    cache = getattr(_explorer_running, "_c", (0.0, False))
    if now - cache[0] < 0.08:
        return cache[1]
    found = False
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            if str(p.info.get("name") or "").lower() == "explorer.exe":
                found = True
                break
    except Exception:
        found = False
    _explorer_running._c = (now, found)
    return found

def _input_desktop_name():
    try:
        return (get_input_desktop_name() or "default").lower()
    except Exception:
        return "default"

def _user_desktop_was_shown(val=None):
    if val is not None:
        _user_desktop_was_shown._v = bool(val)
        return _user_desktop_was_shown._v
    return bool(getattr(_user_desktop_was_shown, "_v", False))

def _pid_image_basename(pid):
    if not pid:
        return ""
    try:
        k32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        PROCESS_QUERY_INFORMATION = 0x0400
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not h:
            h = k32.OpenProcess(PROCESS_QUERY_INFORMATION, False, int(pid))
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(32768)
            size = ctypes.c_ulong(32768)
            if not k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return ""
            return os.path.basename(buf.value).lower()
        finally:
            k32.CloseHandle(h)
    except Exception:
        return ""

def _pid_image_is_logonui(pid):
    return _pid_image_basename(pid) == "logonui.exe"

def _pid_is_secure_ui(pid):
    return _pid_image_basename(pid) in ("logonui.exe", "winlogon.exe", "consent.exe", "lockapp.exe")

def _hwnd_class_and_title(hwnd):
    if sys.platform != "win32" or not hwnd:
        return "", ""
    user32 = ctypes.windll.user32
    c_buf = ctypes.create_unicode_buffer(256)
    t_buf = ctypes.create_unicode_buffer(256)
    try:
        user32.GetClassNameW(hwnd, c_buf, 255)
    except Exception:
        pass
    try:
        user32.GetWindowTextW(hwnd, t_buf, 255)
    except Exception:
        pass
    return (c_buf.value or ""), (t_buf.value or "")

def _is_bsdr_hwnd(hwnd):
    """Kiểm tra cửa sổ Blocked Shutdown Resolver ('Closing X apps and restarting') trên Winlogon."""
    cls, title = _hwnd_class_and_title(hwnd)
    cl = cls.lower()
    tl = title.lower()
    return ("blockedshutdown" in cl) or ("blocked shutdown" in tl) or ("blockedshutdown" in tl)

def _filter_winlogon_top_hwnds(items, sw, sh):
    """Khi trên Winlogon có nhiều cửa sổ fullscreen (ví dụ 'BlockedShutdownUX XAML Host' đè lên
    'LogonUI Logon Window' đang quay 'Restarting'):
    1. Nếu có cửa sổ BSDR ('BlockedShutdownUX XAML Host'), loại bỏ mọi cửa sổ fullscreen khác.
    2. Nếu không có BSDR, chỉ giữ cửa sổ fullscreen đầu tiên (trên cùng theo Z-order của EnumDesktopWindows)
       để cửa sổ nền phía sau không vẽ đè lên cửa sổ trước mặt."""
    if not items:
        return items
    has_bsdr = any(_is_bsdr_hwnd(it[0]) for it in items)
    out = []
    kept_fullscreen = False
    for it in items:
        hwnd, w, h = it[0], it[1], it[2]
        is_full = (w >= int(sw * 0.75) and h >= int(sh * 0.75))
        if not is_full:
            out.append(it)
            continue
        if has_bsdr:
            if _is_bsdr_hwnd(hwnd) and not kept_fullscreen:
                out.append(it)
                kept_fullscreen = True
        else:
            if not kept_fullscreen:
                out.append(it)
                kept_fullscreen = True
    return out

def _enum_desktop_hwnds(hdesk, min_w=80, min_h=40):
    """Cửa sổ visible trên HDESK (không cần thread đang gắn desktop đó)."""
    out = []
    if not hdesk:
        return out
    user32 = ctypes.windll.user32
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    rect = wintypes.RECT()

    def _cb(hwnd, _lp):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        if _hwnd_is_dwm_cloaked(hwnd):
            return True
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        w = int(rect.right - rect.left)
        h = int(rect.bottom - rect.top)
        if w < min_w or h < min_h:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        out.append((hwnd, w, h, int(pid.value), int(rect.left), int(rect.top)))
        return True

    user32.EnumDesktopWindows(hdesk, WNDENUMPROC(_cb), 0)
    return out

def _winlogon_secure_ui_hwnds():
    """HWND LogonUI.exe / winlogon.exe / LockApp.exe / Network Flyout trên desktop Winlogon hoặc Input Desktop."""
    if sys.platform != "win32":
        return []
    attach_process_window_station("WinSta0")
    logoff = getattr(_wts_phase, "_v", "none") == "logoff" or (
        float(getattr(_wts_phase, "_until", 0) or 0) > time.time()
    )
    now = time.time()
    cache = getattr(_winlogon_secure_ui_hwnds, "_c", (0.0, []))
    if (not logoff) and now - cache[0] < 0.03:
        return cache[1]
    found = []
    seen = set()
    user32 = ctypes.windll.user32
    try:
        sw = int(user32.GetSystemMetrics(0))
        sh = int(user32.GetSystemMetrics(1))
    except Exception:
        sw, sh = 800, 600

    desks_to_close = []
    desks = []
    try:
        h_wl = open_named_desktop_handle("Winlogon")
        if h_wl:
            if _desktop_name_from_handle(h_wl) == "winlogon":
                desks.append(h_wl)
            desks_to_close.append(h_wl)
        h_in = open_input_desktop_handle()
        if h_in:
            if _desktop_name_from_handle(h_in) == "winlogon":
                desks.append(h_in)
            desks_to_close.append(h_in)
        h_cur = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
        if h_cur and h_cur not in desks:
            if _desktop_name_from_handle(h_cur) == "winlogon":
                desks.append(h_cur)

        for hd in desks:
            for hwnd, w, h, pid, x, y in _enum_desktop_hwnds(hd, 20, 20):
                if hwnd in seen:
                    continue
                seen.add(hwnd)
                name = _pid_image_basename(pid)
                is_fullscreen = (w >= int(sw * 0.85) and h >= int(sh * 0.85))
                if not is_fullscreen:
                    # Bất kỳ flyout, popup, menu con (mạng LAN/Wifi, nguồn, accessibility...) trên Winlogon
                    if name in ("logonui.exe", "winlogon.exe", "consent.exe", "lockapp.exe", "applicationframehost.exe", "shellexperiencehost.exe", ""):
                        found.append((hwnd, w, h, pid, x, y))
                elif name in ("logonui.exe", "consent.exe", "lockapp.exe", "applicationframehost.exe", "shellexperiencehost.exe") or not name:
                    found.append((hwnd, w, h, pid, x, y))
                elif name == "winlogon.exe":
                    if logoff:
                        found.append((hwnd, w, h, pid, x, y))

        found = _filter_winlogon_top_hwnds(found, sw, sh)
        seen = {item[0] for item in found}

        # Enum child windows của mọi cửa sổ tìm thấy (Network Flyout, DirectUIHWND, popup con)
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _child_cb(ch, _lp):
            if ch in seen:
                return True
            is_vis = user32.IsWindowVisible(ch) or bool(user32.GetWindowLongW(ch, -16) & 0x10000000)
            if not is_vis or user32.IsIconic(ch):
                return True
            if _hwnd_is_dwm_cloaked(ch):
                return True
            r = wintypes.RECT()
            if not user32.GetWindowRect(ch, ctypes.byref(r)):
                return True
            cw = int(r.right - r.left)
            ch_h = int(r.bottom - r.top)
            if 20 <= cw < int(sw * 0.95) and 20 <= ch_h < int(sh * 0.95):
                seen.add(ch)
                cpid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(ch, ctypes.byref(cpid))
                found.append((ch, cw, ch_h, int(cpid.value), int(r.left), int(r.top)))
            return True

        child_proc = WNDENUMPROC(_child_cb)
        for item in list(found):
            user32.EnumChildWindows(item[0], child_proc, 0)
    except Exception:
        found = []
    finally:
        for hd in desks_to_close:
            try:
                ctypes.windll.user32.CloseDesktop(hd)
            except Exception:
                pass
    _winlogon_secure_ui_hwnds._c = (now, found)
    return found

def _consent_hwnds_on_desktop(desk_name):
    """HWND consent.exe trên Default hoặc Winlogon."""
    found = []
    hdesk = None
    try:
        hdesk = open_named_desktop_handle(desk_name)
        if not hdesk:
            return found
        for hwnd, w, h, pid, x, y in _enum_desktop_hwnds(hdesk, 80, 40):
            if _pid_image_basename(pid) == "consent.exe":
                found.append((hwnd, w, h, pid, x, y))
    except Exception:
        found = []
    finally:
        if hdesk:
            try:
                ctypes.windll.user32.CloseDesktop(hdesk)
            except Exception:
                pass
    return found


def _hwnd_is_dwm_cloaked(hwnd):
    try:
        cloaked = ctypes.c_int(0)
        # DWMWA_CLOAKED = 14
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            ctypes.c_void_p(hwnd), 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
        return hr == 0 and int(cloaked.value) != 0
    except Exception:
        return False


def _pick_uac_dialog_hwnds(hwnds):
    """Chỉ hộp Yes/No thật. Bỏ HWND phụ/cloaked ở (0,0) — PrintWindow chúng làm nháy góc trái Win11."""
    usable = []
    for hwnd, w, h, pid, x, y in hwnds or ():
        if not hwnd or w < 280 or h < 160:
            continue
        if _hwnd_is_dwm_cloaked(hwnd):
            continue
        # Ghost/tool window DWM hay đặt origin (0,0) lúc compose.
        if int(x) <= 2 and int(y) <= 2 and w < 700 and h < 500:
            continue
        usable.append((hwnd, w, h, pid, x, y))
    if not usable:
        return []
    usable.sort(key=lambda t: t[1] * t[2], reverse=True)
    return usable[:1]


def _bitblt_screen_rect_bgr(x, y, w, h):
    """Chụp vùng màn hình đã vẽ — không PrintWindow (Win11 UAC nháy nếu RENDERFULLCONTENT mỗi frame)."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    w, h = int(w), int(h)
    x, y = int(x), int(y)
    if w < 8 or h < 8:
        return None
    hdc = user32.GetDC(0)
    if not hdc:
        return None
    memdc = gdi32.CreateCompatibleDC(hdc)
    hbmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(memdc, hbmp)
    try:
        blt_ok = gdi32.BitBlt(memdc, 0, 0, w, h, hdc, x, y, 0x40CC0020)
        if not blt_ok:
            blt_ok = gdi32.BitBlt(memdc, 0, 0, w, h, hdc, x, y, 0x00CC0020)
        if not blt_ok:
            return None

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32),
                ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER)]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buf = (ctypes.c_ubyte * (w * h * 4))()
        bmi.bmiHeader.biHeight = -h
        got = gdi32.GetDIBits(memdc, hbmp, 0, h, buf, ctypes.byref(bmi), 0)
        top_down = True
        if got == 0:
            bmi.bmiHeader.biHeight = h
            got = gdi32.GetDIBits(memdc, hbmp, 0, h, buf, ctypes.byref(bmi), 0)
            top_down = False
        if got == 0:
            return None
        img = np.frombuffer(bytes(buf), dtype=np.uint8).reshape((h, w, 4))
        if not top_down:
            img = np.flipud(img).copy()
        frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        if _frame_is_nearly_black(frame):
            return None
        return frame, w, h, (x, y)
    finally:
        gdi32.SelectObject(memdc, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(0, hdc)


def grab_uac_dialog_bgr():
    """Win11 DXGI lúc UAC = màn trắng. GDI desktop; không PrintWindow consent (nháy góc trái)."""
    attach_thread_for_remote_input()
    on_wl = _consent_hwnds_on_desktop("Winlogon")
    on_def = _consent_hwnds_on_desktop("Default")
    if on_wl and not on_def:
        if get_desktop_name() != "winlogon":
            _switch_capture_thread_to_named_desktop("Winlogon")
        hwnds = on_wl
    else:
        if get_desktop_name() == "winlogon":
            _switch_capture_thread_to_named_desktop("Default")
        hwnds = on_def or on_wl
        attach_thread_for_remote_input()

    hwnds = _pick_uac_dialog_hwnds(hwnds)

    frame_bgr = None
    cap_w = cap_h = 0
    origin = (0, 0)
    try:
        frame_bgr, cap_w, cap_h, origin = grab_gdi_primary_bgr(use_screen_dc=True)
    except Exception:
        try:
            frame_bgr, cap_w, cap_h, origin = grab_gdi_primary_bgr(use_screen_dc=False)
        except Exception:
            frame_bgr = None

    # Desktop GDI đã có hộp thoại (PromptOnSecureDesktop=0): đừng dán thêm tile.
    if (
        frame_bgr is not None
        and getattr(frame_bgr, "size", 0)
        and not _frame_is_nearly_black(frame_bgr)
        and not _frame_is_nearly_white(frame_bgr)
    ):
        return frame_bgr, cap_w, cap_h, origin

    overlays = []
    for hwnd, w, h, _pid, x, y in hwnds:
        cap = _bitblt_screen_rect_bgr(x, y, w, h)
        if cap is None:
            continue
        overlays.append((cap[0], x, y, w, h))

    if frame_bgr is None:
        if overlays:
            overlays.sort(key=lambda t: t[3] * t[4], reverse=True)
            tile, x, y, tw, th = overlays[0]
            return tile, tw, th, (int(x), int(y))
        alt = grab_current_desktop_printwindow()
        if alt is not None:
            return alt
        raise RuntimeError("UAC GDI capture failed")

    left0 = origin[0] if origin else 0
    top0 = origin[1] if origin else 0
    for tile, x, y, _tw, _th in overlays:
        _clip_tile_onto_canvas(frame_bgr, tile, int(x) - left0, int(y) - top0)
    return frame_bgr, cap_w, cap_h, origin

def _winlogon_has_logonui_windows():
    """Signing out / Welcome: UI trên Winlogon (LogonUI hoặc status winlogon)."""
    return bool(_winlogon_secure_ui_hwnds())

def _wts_phase(val=None):
    """none | logoff | lock — WTS 6 và 7 không cùng một trạng thái."""
    if val is not None:
        _wts_phase._v = val
        if val == "logoff":
            _wts_phase._until = time.time() + 25.0
        elif val != "logoff":
            _wts_phase._until = 0.0
        return val
    v = getattr(_wts_phase, "_v", "none")
    until = float(getattr(_wts_phase, "_until", 0) or 0)
    if v == "logoff":
        if until and time.time() < until:
            return "logoff"
        _wts_phase._v = "none"
        _wts_phase._until = 0.0
        return "none"
    return v

_wts_phase_listener_started = False

def _ensure_host_wts_phase_listener():
    global _wts_phase_listener_started
    if sys.platform != "win32" or _wts_phase_listener_started:
        return
    _wts_phase_listener_started = True
    threading.Thread(target=_host_wts_phase_listener, name="HostWTSPhase", daemon=True).start()

def _host_wts_phase_listener():
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
        wtsapi32.WTSRegisterSessionNotification.argtypes = [wintypes.HWND, wintypes.DWORD]
        wtsapi32.WTSRegisterSessionNotification.restype = wintypes.BOOL
        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HANDLE),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        WM_WTSSESSION_CHANGE = 0x02B1
        names = {
            1: "console_connect",
            2: "console_disconnect",
            3: "remote_connect",
            4: "remote_disconnect",
            5: "logon",
            6: "logoff",
            7: "lock",
            8: "unlock",
        }

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_WTSSESSION_CHANGE:
                code = int(wparam)
                kind = names.get(code, "")
                if code == 6:
                    _wts_phase("logoff")
                    print(f"[Host] WTS_SESSION_LOGOFF session={int(lparam)} — Signing out, capture loop Winlogon")
                elif code == 7:
                    _wts_phase("lock")
                    print(f"[Host] WTS_SESSION_LOCK session={int(lparam)} — LogonUI khóa")
                elif code in (5, 8):
                    _wts_phase("none")
                    print(f"[Host] WTS {kind} — hết lock/logoff")
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        _host_wts_phase_listener._proc = WNDPROC(wndproc)
        wc = WNDCLASSW()
        wc.lpfnWndProc = _host_wts_phase_listener._proc
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = "EasyRDHostWTSPhase"
        user32.RegisterClassW(ctypes.byref(wc))
        hwnd = user32.CreateWindowExW(
            0, wc.lpszClassName, "EasyRDHostWTSPhase", 0, 0, 0, 0, 0, 0, None, wc.hInstance, None
        )
        if not hwnd:
            print(f"[Host] WTS phase listener: CreateWindowExW failed err={ctypes.get_last_error()}")
            return
        if not wtsapi32.WTSRegisterSessionNotification(hwnd, 1):
            print(f"[Host] WTS phase listener: WTSRegisterSessionNotification failed err={ctypes.get_last_error()}")
            return
        print(f"[Host] WTS phase listener registered (agent PID={os.getpid()}, desk={get_desktop_name()}).")
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except Exception as e:
        print(f"[Host] WTS phase listener: {e}")

def _should_capture_logon_ui():
    """True khi màn hình người dùng thấy là logon / sign-out / khóa.
    UAC: DXGI Win11 trắng — dùng GDI riêng (grab_uac_dialog_bgr), không ghim Winlogon."""
    if uac_consent_running():
        return False
    _ensure_host_wts_phase_listener()
    phase = _wts_phase()
    input_name = _input_desktop_name()
    logged_in = _session_has_interactive_user()
    explorer = _explorer_running()
    secure_ui = _winlogon_has_logonui_windows()
    logonui = _logonui_running() or secure_ui
    saw = _user_desktop_was_shown()

    # Khi Input Desktop thực tế đang là Winlogon -> Màn hình người dùng (BSDR / Lock / Logon) đang ở Winlogon!
    if input_name == "winlogon":
        return True

    if explorer:
        if phase == "lock" and logonui:
            return True
        return False

    if logged_in is False:
        _user_desktop_was_shown(False)
        return True
    if not explorer:
        return True
    if logonui:
        return True
    return False

def _pin_capture_to_winlogon_if_needed():
    """Sign-out/logon: input có thể còn Default trong khi UI đã ở Winlogon."""
    if not _should_capture_logon_ui():
        return False
    if get_desktop_name() == "winlogon":
        return False
    return _switch_capture_thread_to_named_desktop("Winlogon")

def _switch_capture_thread_to_named_desktop(name):
    attach_process_window_station("WinSta0")
    hdesk = open_named_desktop_handle(name)
    if not hdesk:
        return False
    try:
        result = ctypes.windll.user32.SetThreadDesktop(hdesk)
        if result:
            print(f"[Host] Capture thread switched to {name}")
        return bool(result)
    finally:
        try:
            ctypes.windll.user32.CloseDesktop(hdesk)
        except Exception:
            pass

def _switch_capture_thread_to_input_desktop():
    attach_process_window_station("WinSta0")
    hdesk = None
    try:
        hdesk = open_input_desktop_handle()
        if not hdesk:
            thread_name = get_desktop_name()
            want_winlogon = _should_capture_logon_ui() or _logonui_running() or (not _explorer_running())
            target_name = "Winlogon" if want_winlogon else "Default"
            if thread_name == target_name.lower():
                return True
            hdesk = open_named_desktop_handle(target_name)
            if hdesk:
                print(f"[Host] Opened {target_name} desktop by name (fallback)")
        if not hdesk:
            print("[Host] OpenInputDesktop failed for all access masks.")
            return False

        target_name = _desktop_name_from_handle(hdesk)
        thread_name = get_desktop_name()
        if target_name and thread_name == target_name.lower():
            return True

        result = ctypes.windll.user32.SetThreadDesktop(hdesk)
        if not result:
            err = ctypes.windll.kernel32.GetLastError()
            if err == 170:
                print(f"[Host] SetThreadDesktop({target_name}) failed with ERROR_BUSY (170): thread has existing windows/hooks/GDI handles.")
            else:
                print(f"[Host] SetThreadDesktop({target_name}) failed with error code: {err}. Retrying...")
            return False
        print(f"[Host] Capture thread desktop successfully switched to: {target_name}")
        return True
    except Exception as e:
        print(f"[Host] SetThreadDesktop exception: {e}")
        return False
    finally:
        if hdesk:
            try:
                ctypes.windll.user32.CloseDesktop(hdesk)
            except Exception:
                pass

def _frame_is_nearly_black(frame, max_mean=6.0):
    try:
        if frame is None or getattr(frame, "size", 0) == 0:
            return True
        if getattr(frame, "ndim", 0) == 3 and frame.shape[2] >= 4:
            frame = frame[:, :, :3]
        # Nếu frame có điểm sáng rõ rệt (chữ Admin, icon, avatar, text trong dark theme flyout như Network flyout):
        # np.max > 35 và có ít nhất 30 pixel sáng -> Đây là giao diện dark theme có nội dung, không phải màn hình đen rỗng!
        if float(np.max(frame)) > 35.0:
            if np.count_nonzero(frame > 30) > 30:
                return False
        return float(np.mean(frame)) < max_mean
    except Exception:
        return False

def _frame_is_nearly_white(frame, min_mean=235.0):
    """DXGI lúc UAC Win11 hay trả desktop mờ trắng, không có hộp Yes/No."""
    try:
        if frame is None or getattr(frame, "size", 0) == 0:
            return False
        if getattr(frame, "ndim", 0) == 3 and frame.shape[2] >= 4:
            frame = frame[:, :, :3]
        return float(np.mean(frame)) > min_mean
    except Exception:
        return False

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
        if _is_server_or_remote_session():
            return
    except Exception:
        pass
    try:
        import ctypes
        # Font Smoothing (ClearType) - LUÔN LUÔN BẬT ĐỂ CHỮ MỊN VÀ SẮC NÉT TRÊN MỌI BẢN WINDOWS (7, 10, 11)
        flag = 0  # Apply in-memory, avoid broadcasting WM_SETTINGCHANGE which can freeze/blank GDI windows on Intel UHD
        ctypes.windll.user32.SystemParametersInfoW(0x004B, 1, None, flag)  # SPI_SETFONTSMOOTHING = 1
        ctypes.windll.user32.SystemParametersInfoW(0x200B, 0, ctypes.c_void_p(2), flag)  # SPI_SETFONTSMOOTHINGTYPE = ClearType (2)
        
        # Drag Full Windows
        ctypes.windll.user32.SystemParametersInfoW(0x0025, 1, None, flag)
        
        # Menu Animation
        ctypes.windll.user32.SystemParametersInfoW(0x1003, 1 if enabled else 0, None, flag)
        
        # UI Effects
        ctypes.windll.user32.SystemParametersInfoW(0x103E, 1, None, flag)
        
        # Window Animations (iMinAnimate)
        class ANIMATIONINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("iMinAnimate", ctypes.c_int)]
        info = ANIMATIONINFO()
        info.cbSize = ctypes.sizeof(ANIMATIONINFO)
        info.iMinAnimate = 1 if enabled else 0
        ctypes.windll.user32.SystemParametersInfoW(0x0049, info.cbSize, ctypes.byref(info), flag)
        
        print(f"[Host] Set Windows graphics effects to: {enabled} (ClearType always ON)")
    except Exception as e:
        print(f"[Host] Error setting Windows graphics effects: {e}")


# Unified Application Class


_MAX_SEND_EDGE_LAN = 4096
_MAX_SEND_EDGE_WAN = 2560
_MAX_SEND_EDGE_LEGACY = 2560


def _is_legacy_windows_host():
    """Windows 7/Vista: không có DXGI Desktop Duplication (dùng GDI)."""
    if sys.platform != "win32":
        return False
    try:
        v = sys.getwindowsversion()
        return v.major < 6 or (v.major == 6 and v.minor < 2)
    except Exception:
        return str(platform.release()) in ("7", "Vista", "XP")


def _is_server_or_remote_session():
    """Windows Server hoac RDP remote session: khong dung DXGI Desktop Duplication."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        if user32.GetSystemMetrics(89):  # SM_SERVERR2
            return True
        if user32.GetSystemMetrics(4096):  # SM_REMOTESESSION
            return True
    except Exception:
        pass
    return False


def _windows_has_dxgi_duplication():
    return sys.platform == "win32" and not _is_legacy_windows_host() and not _is_server_or_remote_session()


def _primary_screen_rect():
    if sys.platform != "win32":
        return 0, 0, 1920, 1080
    try:
        user32 = ctypes.windll.user32
        w = int(user32.GetSystemMetrics(0))
        h = int(user32.GetSystemMetrics(1))
        if w > 0 and h > 0:
            return 0, 0, w, h
    except Exception:
        pass
    return 0, 0, 1920, 1080


def _virtual_screen_rect():
    if sys.platform != "win32":
        return 0, 0, 1920, 1080
    user32 = ctypes.windll.user32
    left0 = int(user32.GetSystemMetrics(76))
    top0 = int(user32.GetSystemMetrics(77))
    w = int(user32.GetSystemMetrics(78))
    h = int(user32.GetSystemMetrics(79))
    if w < 1 or h < 1:
        left0, top0 = 0, 0
        w = int(user32.GetSystemMetrics(0))
        h = int(user32.GetSystemMetrics(1))
    return left0, top0, w, h


def _enum_win32_monitors():
    """Lấy danh sách các màn hình trên Windows thông qua pywin32 (win32api.EnumDisplayMonitors)
    kèm fallback ctypes. Trả về danh sách dict {'left', 'top', 'width', 'height', 'is_primary'}."""
    if sys.platform != "win32":
        return []
    mons_out = []
    seen = set()
    try:
        import win32api
        raw_mons = win32api.EnumDisplayMonitors()
        for hmon, _hdc, rc_tuple in (raw_mons or []):
            is_prim = False
            ml, mt, mr, mb = int(rc_tuple[0]), int(rc_tuple[1]), int(rc_tuple[2]), int(rc_tuple[3])
            try:
                info = win32api.GetMonitorInfo(hmon)
                rc_m = info.get("Monitor") or rc_tuple
                ml, mt, mr, mb = int(rc_m[0]), int(rc_m[1]), int(rc_m[2]), int(rc_m[3])
                is_prim = bool(int(info.get("Flags", 0)) & 1)
            except Exception:
                is_prim = (ml == 0 and mt == 0)
            mw, mh = mr - ml, mb - mt
            if mw > 0 and mh > 0:
                key = (ml, mt, mw, mh)
                if key not in seen:
                    seen.add(key)
                    mons_out.append({
                        "left": ml, "top": mt, "width": mw, "height": mh,
                        "is_primary": is_prim,
                    })
    except Exception:
        pass

    if not mons_out:
        try:
            user32 = ctypes.windll.user32
            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
            )

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            _get_mon_info = user32.GetMonitorInfoW
            _get_mon_info.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
            _get_mon_info.restype = wintypes.BOOL

            _enum_mons = user32.EnumDisplayMonitors
            _enum_mons.argtypes = [wintypes.HDC, ctypes.c_void_p, MONITORENUMPROC, wintypes.LPARAM]
            _enum_mons.restype = wintypes.BOOL

            def _mon_cb(hmon, _hdc, lprc, _lparam):
                rc = None
                is_prim = False
                try:
                    mi = MONITORINFO()
                    mi.cbSize = ctypes.sizeof(MONITORINFO)
                    if _get_mon_info(hmon, ctypes.byref(mi)):
                        rc = mi.rcMonitor
                        is_prim = bool(int(mi.dwFlags) & 1)
                except Exception:
                    rc = None
                if rc is None and lprc:
                    try:
                        rc = lprc.contents
                    except Exception:
                        rc = None
                if rc is not None:
                    ml, mt = int(rc.left), int(rc.top)
                    mw, mh = int(rc.right - rc.left), int(rc.bottom - rc.top)
                    if mw > 0 and mh > 0:
                        key = (ml, mt, mw, mh)
                        if key not in seen:
                            seen.add(key)
                            mons_out.append({
                                "left": ml, "top": mt, "width": mw, "height": mh,
                                "is_primary": is_prim or (ml == 0 and mt == 0),
                            })
                return True

            _cb_instance = MONITORENUMPROC(_mon_cb)
            _enum_mons(None, None, _cb_instance, 0)
        except Exception:
            pass

    mons_out.sort(key=lambda m: (int(m.get("left", 0)), int(m.get("top", 0))))
    return mons_out


def is_multi_monitor_windows():
    """Kiểm tra máy Host Windows có nhiều hơn 1 màn hình hay không qua win32api.EnumDisplayMonitors()."""
    if sys.platform != "win32":
        return False
    mons = _enum_win32_monitors()
    return len(mons) > 1


# Danh sách (left, top, width, height) của các màn hình thực sự có hình (không phải màn hình ma đen kịt)
_active_monitor_rects_last = []


def _pick_primary_monitor_dict(valid_mons):
    """Chọn màn hình chính (is_primary hoặc gốc tọa độ 0,0 hoặc phần tử đầu tiên)."""
    if not valid_mons:
        l0, t0, w0, h0 = _primary_screen_rect()
        return {"left": l0, "top": t0, "width": w0, "height": h0}
    for m in valid_mons:
        if m.get("is_primary"):
            return m
    for m in valid_mons:
        if int(m.get("left", 0)) == 0 and int(m.get("top", 0)) == 0:
            return m
    return valid_mons[0]


def _filter_active_mss_monitors(sct):
    """Trả về (active_mons, valid_mons) từ đối tượng mss kết hợp win32api.EnumDisplayMonitors().
    Chỉ khi có >= 2 màn hình thực sự có nội dung (không đen kịt) mới coi là đa màn hình;
    nếu <= 1 màn hình có nội dung thì luôn trả về đúng 1 màn hình để không bị nháy 2 màn hình."""
    global _active_monitor_rects_last
    mons = getattr(sct, "monitors", None) or []
    valid_mons = [
        m for m in mons[1:]
        if int(m.get("width", 0)) > 0 and int(m.get("height", 0)) > 0
    ]
    if sys.platform == "win32":
        win32_mons = _enum_win32_monitors()
        if len(win32_mons) == 1:
            m = win32_mons[0]
            _active_monitor_rects_last = [
                (int(m["left"]), int(m["top"]), int(m["width"]), int(m["height"]))
            ]
            return [m], [m]
        elif win32_mons and not valid_mons:
            valid_mons = win32_mons

    valid_mons.sort(key=lambda m: (int(m.get("left", 0)), int(m.get("top", 0))))
    if len(valid_mons) <= 1:
        if len(valid_mons) == 1:
            m = valid_mons[0]
            _active_monitor_rects_last = [
                (int(m.get("left", 0)), int(m.get("top", 0)), int(m.get("width", 0)), int(m.get("height", 0)))
            ]
        return valid_mons, valid_mons

    active_mons = []
    active_rects = []
    for m in valid_mons:
        mrect = (int(m.get("left", 0)), int(m.get("top", 0)), int(m.get("width", 0)), int(m.get("height", 0)))
        try:
            raw = sct.grab(m)
            tile = np.array(raw, dtype=np.uint8)
            if tile is not None and getattr(tile, "size", 0) > 0 and not _frame_is_nearly_black(tile):
                active_mons.append(m)
                active_rects.append(mrect)
        except Exception:
            pass
    if len(active_mons) >= 2:
        _active_monitor_rects_last = active_rects
        return active_mons, valid_mons
    elif len(active_mons) == 1:
        _active_monitor_rects_last = active_rects
        return active_mons, valid_mons
    else:
        # Khi màn hình đang ngủ / vừa khởi động (chưa chụp được màn nào có nội dung),
        # TUYỆT ĐỐI chỉ mặc định 1 màn hình chính, không mặc định ghép 2 màn hình!
        prim = _pick_primary_monitor_dict(valid_mons)
        _active_monitor_rects_last = [
            (int(prim.get("left", 0)), int(prim.get("top", 0)), int(prim.get("width", 0)), int(prim.get("height", 0)))
        ]
        return [prim], valid_mons


def _get_active_monitors_and_virtual_rect(sct=None):
    """Xác định monitor hiệu dụng (loại bỏ màn hình ma đen kịt) cho Handshake và Worker.
    Trả về (monitor_dict, active_rects_list)."""
    try:
        if sys.platform == "win32":
            win32_mons = _enum_win32_monitors()
            if len(win32_mons) == 1:
                m = win32_mons[0]
                ml, mt, mw, mh = int(m["left"]), int(m["top"]), int(m["width"]), int(m["height"])
                return {"left": ml, "top": mt, "width": mw, "height": mh}, [(ml, mt, mw, mh)]
        if sct is not None:
            active_mons, valid_mons = _filter_active_mss_monitors(sct)
            mons = getattr(sct, "monitors", None) or []
        else:
            with mss.mss() as _sct_tmp:
                active_mons, valid_mons = _filter_active_mss_monitors(_sct_tmp)
                mons = getattr(_sct_tmp, "monitors", None) or []
        if len(active_mons) >= 2:
            chosen = active_mons
        elif len(active_mons) == 1:
            chosen = active_mons
        elif valid_mons:
            chosen = [_pick_primary_monitor_dict(valid_mons)]
        elif mons:
            chosen = [mons[1] if len(mons) > 1 else mons[0]]
        else:
            chosen = []
        if len(chosen) == 1:
            m = chosen[0]
            ml, mt = int(m.get("left", 0)), int(m.get("top", 0))
            mw, mh = int(m.get("width", 0)), int(m.get("height", 0))
            if mw > 0 and mh > 0:
                return {"left": ml, "top": mt, "width": mw, "height": mh}, [(ml, mt, mw, mh)]
        elif len(chosen) >= 2:
            min_l = min(int(m.get("left", 0)) for m in chosen)
            min_t = min(int(m.get("top", 0)) for m in chosen)
            max_r = max(int(m.get("left", 0)) + int(m.get("width", 0)) for m in chosen)
            max_b = max(int(m.get("top", 0)) + int(m.get("height", 0)) for m in chosen)
            rects = [
                (int(m.get("left", 0)), int(m.get("top", 0)), int(m.get("width", 0)), int(m.get("height", 0)))
                for m in chosen
            ]
            rects.sort(key=lambda r: (r[0], r[1]))
            return {"left": min_l, "top": min_t, "width": max_r - min_l, "height": max_b - min_t}, rects
    except Exception:
        pass
    l0, t0, w0, h0 = _primary_screen_rect()
    return {"left": l0, "top": t0, "width": w0, "height": h0}, [(l0, t0, w0, h0)]


def _get_physical_monitor_rects(sct=None, dx_cams=None):
    """Trả về danh sách (left, top, width, height) của các màn hình vật lý đang hoạt động,
    sắp xếp theo (left, top) tăng dần: index 0 = Màn hình Trái, index 1 = Màn hình Phải."""
    rects = []
    seen = set()
    expected_min = 1
    if sys.platform == "win32":
        try:
            # SM_CMONITORS = 80: số màn hình hiển thị vật lý đang bật theo Windows Kernel
            expected_min = max(1, int(ctypes.windll.user32.GetSystemMetrics(80)))
        except Exception:
            expected_min = 1
        try:
            user32 = ctypes.windll.user32
            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
            )

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            _get_mon_info = user32.GetMonitorInfoW
            _get_mon_info.argtypes = [wintypes.HMONITOR, ctypes.c_void_p]
            _get_mon_info.restype = wintypes.BOOL

            _enum_mons = user32.EnumDisplayMonitors
            _enum_mons.argtypes = [wintypes.HDC, ctypes.c_void_p, MONITORENUMPROC, wintypes.LPARAM]
            _enum_mons.restype = wintypes.BOOL

            def _mon_cb(hmon, _hdc, lprc, _lparam):
                rc = None
                try:
                    mi = MONITORINFO()
                    mi.cbSize = ctypes.sizeof(MONITORINFO)
                    if _get_mon_info(hmon, ctypes.byref(mi)):
                        rc = mi.rcMonitor
                except Exception:
                    rc = None
                if rc is None and lprc:
                    try:
                        rc = lprc.contents
                    except Exception:
                        rc = None
                if rc is not None:
                    ml, mt = int(rc.left), int(rc.top)
                    mw, mh = int(rc.right - rc.left), int(rc.bottom - rc.top)
                    if mw > 0 and mh > 0:
                        key = (ml, mt, mw, mh)
                        if key not in seen:
                            seen.add(key)
                            rects.append(key)
                return True

            _cb_instance = MONITORENUMPROC(_mon_cb)
            _enum_mons(None, None, _cb_instance, 0)
        except Exception:
            pass

    if len(rects) < expected_min and dx_cams:
        for cam in list(dx_cams):
            try:
                cam._output.update_desc()
                rc = cam._output.desc.DesktopCoordinates
                ml, mt = int(rc.left), int(rc.top)
                mw, mh = int(rc.right - rc.left), int(rc.bottom - rc.top)
                if mw > 0 and mh > 0:
                    key = (ml, mt, mw, mh)
                    if key not in seen:
                        seen.add(key)
                        rects.append(key)
            except Exception:
                pass

    if not rects or len(rects) < expected_min:
        try:
            if sct is not None:
                mons = getattr(sct, "monitors", None) or []
                for m in mons[1:]:
                    ml, mt = int(m.get("left", 0)), int(m.get("top", 0))
                    mw, mh = int(m.get("width", 0)), int(m.get("height", 0))
                    if mw > 0 and mh > 0:
                        key = (ml, mt, mw, mh)
                        if key not in seen:
                            seen.add(key)
                            rects.append(key)
            else:
                with mss.mss() as _sct_tmp:
                    for m in (_sct_tmp.monitors or [])[1:]:
                        ml, mt = int(m.get("left", 0)), int(m.get("top", 0))
                        mw, mh = int(m.get("width", 0)), int(m.get("height", 0))
                        if mw > 0 and mh > 0:
                            key = (ml, mt, mw, mh)
                            if key not in seen:
                                seen.add(key)
                                rects.append(key)
        except Exception:
            pass

    rects.sort(key=lambda r: (r[0], r[1]))
    if len(rects) > 1 and _active_monitor_rects_last:
        verified = [r for r in rects if r in _active_monitor_rects_last]
        if verified:
            rects = verified
    return rects


_pynput_mouse_ctrl = None


def _get_host_cursor_pos():
    """Đọc tọa độ chuột vật lý hiện tại trên máy Host."""
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            pt = wintypes.POINT()
            if hasattr(user32, "GetPhysicalCursorPos") and user32.GetPhysicalCursorPos(ctypes.byref(pt)):
                return int(pt.x), int(pt.y)
            if user32.GetCursorPos(ctypes.byref(pt)):
                return int(pt.x), int(pt.y)
        except Exception:
            pass
        return None
    try:
        global _pynput_mouse_ctrl
        if _pynput_mouse_ctrl is None:
            from pynput.mouse import Controller as _MC
            _pynput_mouse_ctrl = _MC()
        pos = _pynput_mouse_ctrl.position
        if pos is not None:
            return int(pos[0]), int(pos[1])
    except Exception:
        pass
    return None


def _clip_tile_onto_canvas(canvas, tile, x, y, mask_black=False):
    if tile is None or getattr(tile, "size", 0) == 0:
        return False
    if tile.ndim == 2:
        tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
    elif tile.shape[2] == 4:
        tile = cv2.cvtColor(tile, cv2.COLOR_BGRA2BGR)
    ch, cw = canvas.shape[:2]
    th, tw = tile.shape[:2]
    x0 = max(int(x), 0)
    y0 = max(int(y), 0)
    x1 = min(int(x) + tw, cw)
    y1 = min(int(y) + th, ch)
    if x1 <= x0 or y1 <= y0:
        return False
    sx = x0 - int(x)
    sy = y0 - int(y)
    dst = canvas[y0:y1, x0:x1]
    src = tile[sy:sy + (y1 - y0), sx:sx + (x1 - x0)]
    if src.shape[0] != dst.shape[0] or src.shape[1] != dst.shape[1]:
        interp = cv2.INTER_AREA if (src.shape[1] > dst.shape[1] or src.shape[0] > dst.shape[0]) else cv2.INTER_NEAREST
        src = cv2.resize(src, (dst.shape[1], dst.shape[0]), interpolation=interp)
    if mask_black:
        mask = (src[:, :, 0] > 12) | (src[:, :, 1] > 12) | (src[:, :, 2] > 12)
        dst[mask] = src[mask]
    else:
        dst[:] = src
    return True


_last_tscon_call_time = 0.0

def _get_tscon_path():
    """Tìm đường dẫn thực tế tới tscon.exe, xử lý chuyển hướng WOW64 trên Windows 64-bit."""
    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    sysnative_tscon = os.path.join(sys_root, "Sysnative", "tscon.exe")
    if os.path.exists(sysnative_tscon):
        return sysnative_tscon
    system32_tscon = os.path.join(sys_root, "System32", "tscon.exe")
    if os.path.exists(system32_tscon):
        return system32_tscon
    return "tscon.exe"

def connect_session_to_console(source_session_id):
    """Kết nối session về console desktop mà không chạy qua cmd.exe / shell=True."""
    if sys.platform != "win32":
        return False
    try:
        sid_int = int(source_session_id)
    except Exception:
        return False
    if sid_int in (0, 0xFFFFFFFF, -1):
        return False

    # 1. Thử WTSConnectSessionW nếu target console khác source session
    try:
        wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
        wtsapi32.WTSConnectSessionW.argtypes = [
            wintypes.ULONG, wintypes.ULONG, wintypes.LPCWSTR, wintypes.BOOL
        ]
        wtsapi32.WTSConnectSessionW.restype = wintypes.BOOL

        target_console_id = 0xFFFFFFFF
        try:
            import win32ts
            target_console_id = win32ts.WTSGetActiveConsoleSessionId()
        except Exception:
            pass
        if target_console_id in (0xFFFFFFFF, -1):
            target_console_id = 1

        ok = wtsapi32.WTSConnectSessionW(int(target_console_id), sid_int, "", False)
        if ok:
            return True
    except Exception:
        pass

    # 2. Gọi tscon.exe trực tiếp qua Sysnative / tắt WOW64 redirection
    try:
        tscon_exe = _get_tscon_path()
        import subprocess
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE

        old_val = ctypes.c_void_p()
        redir_disabled = False
        try:
            if hasattr(ctypes.windll.kernel32, "Wow64DisableWow64FsRedirection"):
                redir_disabled = bool(ctypes.windll.kernel32.Wow64DisableWow64FsRedirection(ctypes.byref(old_val)))
        except Exception:
            pass

        try:
            res = subprocess.run(
                [tscon_exe, str(sid_int), "/dest:console"],
                shell=False,
                startupinfo=startupinfo,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
                capture_output=True,
                timeout=3
            )
            if res.returncode == 0:
                return True
            if target_console_id not in (0xFFFFFFFF, -1, sid_int):
                res2 = subprocess.run(
                    [tscon_exe, str(sid_int), f"/dest:{target_console_id}"],
                    shell=False,
                    startupinfo=startupinfo,
                    creationflags=0x08000000,
                    capture_output=True,
                    timeout=3
                )
                if res2.returncode == 0:
                    return True
            return False
        finally:
            if redir_disabled:
                try:
                    ctypes.windll.kernel32.Wow64RevertWow64FsRedirection(old_val)
                except Exception:
                    pass
    except Exception:
        pass
    return False

def attach_disconnected_session_to_console():
    """Chỉ khi MS RDP thực sự đã đóng cửa sổ (session chuyển sang Disconnected = 4),
    mới gọi tscon để trả session về màn hình desktop console.
    TUYỆT ĐỐI không gọi khi RDP đang Active (state == 0) để cả 2 có thể chạy song song."""
    if sys.platform != "win32":
        return
    global _last_tscon_call_time
    now = time.time()
    if now - _last_tscon_call_time < 3.0:
        return
    _last_tscon_call_time = now
    try:
        kernel32 = ctypes.windll.kernel32
        current_sid = ctypes.c_ulong()
        if kernel32.ProcessIdToSessionId(kernel32.GetCurrentProcessId(), ctypes.byref(current_sid)):
            sid = current_sid.value
            if sid in (0, 0xFFFFFFFF):
                try:
                    import win32ts
                    sessions = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE, 1, 0)
                    for s in sessions:
                        s_id = s.get("SessionId")
                        if s_id not in (0, 0xFFFFFFFF, -1) and s.get("State") in (win32ts.WTSActive, win32ts.WTSConnected, win32ts.WTSDisconnected):
                            sid = s_id
                            break
                except Exception:
                    pass

            if sid not in (0, 0xFFFFFFFF):
                state = None
                try:
                    import win32ts
                    state = win32ts.WTSQuerySessionInformation(win32ts.WTS_CURRENT_SERVER_HANDLE, sid, win32ts.WTSConnectState)
                except Exception:
                    pass
                
                # CHỈ xử lý khi session thực sự là Disconnected (4)
                # Nếu RDP đang kết nối (WTSActive = 0), KHÔNG được gọi tscon và KHÔNG gửi disconnect IPC
                if state != 4:
                    return

                # Báo Broker/Service để Service (quyền SYSTEM) gọi tscon chắc chắn thành công
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.5)
                    s.connect(("127.0.0.1", 12400))  # BROKER_IPC_PORT
                    payload = json.dumps({
                        "role": "session_event",
                        "kind": "remote_disconnect",
                        "session": sid,
                    }) + "\n"
                    s.sendall(payload.encode("utf-8"))
                    s.close()
                except Exception:
                    pass
                
                # Gọi trực tiếp API / tscon không dùng shell=True làm fallback
                connect_session_to_console(sid)
    except Exception:
        pass


def grab_gdi_primary_bgr(use_screen_dc=False):
    """BitBlt màn chính — ổn định trên Windows 7 (không DXGI, không mss virtual desktop).
    use_screen_dc=True: GetDC(0) — cần cho Winlogon/Server sau SetThreadDesktop."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    w = int(user32.GetSystemMetrics(0))
    h = int(user32.GetSystemMetrics(1))
    if w < 1 or h < 1:
        w = int(user32.GetSystemMetrics(78))
        h = int(user32.GetSystemMetrics(79))
    if w < 1 or h < 1:
        w, h = 1280, 720
    is_server = False
    try:
        is_server = bool(user32.GetSystemMetrics(89))
    except Exception:
        pass
    prefer_screen_dc = use_screen_dc or is_server or get_desktop_name() == "winlogon"
    hwnd = 0 if prefer_screen_dc else user32.GetDesktopWindow()
    hdc = user32.GetDC(hwnd)
    if not hdc and hwnd != 0:
        hwnd = 0
        hdc = user32.GetDC(0)
    if not hdc:
        attach_disconnected_session_to_console()
        hdc = user32.GetDC(0)
    if not hdc:
        raise RuntimeError("GDI GetDC failed")
    memdc = gdi32.CreateCompatibleDC(hdc)
    hbmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(memdc, hbmp)
    try:
        blt_ok = gdi32.BitBlt(memdc, 0, 0, w, h, hdc, 0, 0, 0x00CC0020)
        if not blt_ok and hwnd != 0:
            user32.ReleaseDC(hwnd, hdc)
            hwnd = 0
            hdc = user32.GetDC(0)
            if hdc:
                blt_ok = gdi32.BitBlt(memdc, 0, 0, w, h, hdc, 0, 0, 0x00CC0020)
        if not blt_ok:
            # Re-attach console nếu BitBlt thất bại (thường gặp trên Windows Server khi session bị Disconnected)
            attach_disconnected_session_to_console()
            time.sleep(0.1)
            hdc_retry = user32.GetDC(0)
            if hdc_retry:
                blt_ok = gdi32.BitBlt(memdc, 0, 0, w, h, hdc_retry, 0, 0, 0x00CC0020)
                user32.ReleaseDC(0, hdc_retry)
        if not blt_ok:
            raise RuntimeError("GDI BitBlt failed")

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32),
                ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER)]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buf = (ctypes.c_ubyte * (w * h * 4))()
        DIB_RGB_COLORS = 0
        bmi.bmiHeader.biHeight = -h
        got = gdi32.GetDIBits(memdc, hbmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
        top_down = True
        if got == 0:
            bmi.bmiHeader.biHeight = h
            got = gdi32.GetDIBits(memdc, hbmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
            top_down = False
        if got == 0:
            raise RuntimeError("GDI GetDIBits failed")
        img = np.frombuffer(bytes(buf), dtype=np.uint8).reshape((h, w, 4))
        if not top_down:
            img = np.flipud(img).copy()
        frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        # Tránh màn hình trắng/đen sau khi ngắt MS RDP trên Windows Server:
        # Nếu GetDesktopWindow() trả về frame trắng tinh hoặc đen tinh, fallback ngay sang GetDC(0)
        if hwnd != 0 and (_frame_is_nearly_white(frame) or _frame_is_nearly_black(frame)):
            hdc_screen = user32.GetDC(0)
            if hdc_screen:
                try:
                    if gdi32.BitBlt(memdc, 0, 0, w, h, hdc_screen, 0, 0, 0x00CC0020):
                        got2 = gdi32.GetDIBits(memdc, hbmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
                        if got2 != 0:
                            img2 = np.frombuffer(bytes(buf), dtype=np.uint8).reshape((h, w, 4))
                            if not top_down:
                                img2 = np.flipud(img2).copy()
                            frame2 = cv2.cvtColor(img2, cv2.COLOR_BGRA2BGR)
                            if not (_frame_is_nearly_white(frame2) or _frame_is_nearly_black(frame2)):
                                frame = frame2
                finally:
                    user32.ReleaseDC(0, hdc_screen)

        return frame, w, h, (0, 0)
    finally:
        gdi32.SelectObject(memdc, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(hwnd, hdc)


def _printwindow_hwnd_bgr(hwnd, w, h):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    used_screen_dc = False
    hdc = user32.GetDC(hwnd)
    if not hdc:
        hdc = user32.GetDC(0)
        used_screen_dc = True
    if not hdc:
        return None
    memdc = gdi32.CreateCompatibleDC(hdc)
    hbmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(memdc, hbmp)
    try:
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32),
                ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER)]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buf = (ctypes.c_ubyte * (w * h * 4))()

        def _is_uniform_solid(bgr):
            if bgr is None or not getattr(bgr, "size", 0):
                return True
            try:
                hf, wf = bgr.shape[:2]
                if wf < 160 or hf < 100:
                    return False
                sub = bgr[::2, ::2]
                med = np.median(sub.reshape(-1, 3), axis=0)
                diff = np.max(np.abs(sub.astype(np.int16) - med.astype(np.int16)), axis=2)
                return int(np.count_nonzero(diff > 18)) < 20
            except Exception:
                return False

        def _fetch_frame(target_hwnd):
            for flag in (2, 0, 3, 1): # PW_RENDERFULLCONTENT, standard, client+render, clientonly
                try:
                    if user32.PrintWindow(target_hwnd, memdc, flag):
                        got = gdi32.GetDIBits(memdc, hbmp, 0, h, buf, ctypes.byref(bmi), 0)
                        if got != 0:
                            img = np.frombuffer(bytes(buf), dtype=np.uint8).reshape((h, w, 4))
                            f = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                            if not _frame_is_nearly_black(f) and not _is_uniform_solid(f):
                                return f
                except Exception:
                    pass
            return None

        # 1. Thử trực tiếp trên cửa sổ target
        frame = _fetch_frame(hwnd)

        # 2. Nếu cửa sổ cha là container rỗng (như ApplicationFrameWindow của UWP Network Flyout):
        # Duyệt qua các cửa sổ con bên trong để tìm nơi chứa DirectComposition content
        if frame is None:
            child_hwnds = []
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            def _child_cb(chwnd, _lp):
                child_hwnds.append(chwnd)
                return True
            try:
                user32.EnumChildWindows(hwnd, WNDENUMPROC(_child_cb), 0)
                for chwnd in child_hwnds:
                    f_child = _fetch_frame(chwnd)
                    if f_child is not None:
                        frame = f_child
                        break
            except Exception:
                pass

        if frame is None or _frame_is_nearly_black(frame):
            return None
        return frame, w, h, (0, 0)
    finally:
        gdi32.SelectObject(memdc, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(0 if used_screen_dc else hwnd, hdc)


def _bitblt_hwnd_bgr(hwnd, w, h):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    hdc = user32.GetWindowDC(hwnd)
    if not hdc:
        return None
    memdc = gdi32.CreateCompatibleDC(hdc)
    hbmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(memdc, hbmp)
    try:
        blt_ok = gdi32.BitBlt(memdc, 0, 0, w, h, hdc, 0, 0, 0x40CC0020)
        if not blt_ok:
            blt_ok = gdi32.BitBlt(memdc, 0, 0, w, h, hdc, 0, 0, 0x00CC0020)
        if not blt_ok:
            return None

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32),
                ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER)]

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buf = (ctypes.c_ubyte * (w * h * 4))()
        bmi.bmiHeader.biHeight = -h
        got = gdi32.GetDIBits(memdc, hbmp, 0, h, buf, ctypes.byref(bmi), 0)
        top_down = True
        if got == 0:
            bmi.bmiHeader.biHeight = h
            got = gdi32.GetDIBits(memdc, hbmp, 0, h, buf, ctypes.byref(bmi), 0)
            top_down = False
        if got == 0:
            return None
        img = np.frombuffer(bytes(buf), dtype=np.uint8).reshape((h, w, 4))
        if not top_down:
            img = np.flipud(img).copy()
        frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        if _frame_is_nearly_black(frame):
            return None
        return frame, w, h, (0, 0)
    finally:
        gdi32.SelectObject(memdc, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(hwnd, hdc)


def _capture_hwnd_bgr(hwnd, w, h, x=0, y=0):
    r = _printwindow_hwnd_bgr(hwnd, w, h)
    if r is not None:
        return r
    r = _bitblt_hwnd_bgr(hwnd, w, h)
    if r is not None:
        return r
    # Fallback cho Windows 10: Nếu PrintWindow và WindowDC không chụp được cửa sổ XAML/DirectComposition,
    # nhưng cửa sổ đang hiện trên màn hình tại tọa độ (x, y), chụp trực tiếp vùng màn hình đó từ Screen DC!
    if w >= 20 and h >= 20:
        try:
            r_scr = _bitblt_screen_rect_bgr(x, y, w, h)
            if r_scr is not None and not _frame_is_nearly_black(r_scr[0]):
                return r_scr
        except Exception:
            pass
    return None


def _logonui_window_captures():
    """Cửa sổ LogonUI / Sign out trên desktop Winlogon."""
    if sys.platform != "win32":
        return []
    out = []
    seen = set()
    hwnds_info = list(_winlogon_secure_ui_hwnds())
    
    # Thread hiện tại có thể đang gắn desktop Winlogon: enum thêm để không bỏ sót popup menu
    try:
        user32 = ctypes.windll.user32
        sw = int(user32.GetSystemMetrics(0))
        sh = int(user32.GetSystemMetrics(1))
    except Exception:
        sw, sh = 800, 600

    try:
        user32 = ctypes.windll.user32
        existing = {item[0] for item in hwnds_info}
        thread_desk = (get_desktop_name() or "").lower()
        if thread_desk == "winlogon":
            hdesk_cur = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
            if hdesk_cur:
                for item in _enum_desktop_hwnds(hdesk_cur, 20, 20):
                    if item[0] not in existing:
                        hwnd, w, h, pid, x, y = item
                        name = _pid_image_basename(pid)
                        is_fullscreen = (w >= int(sw * 0.85) and h >= int(sh * 0.85))
                        if not is_fullscreen or name in ("logonui.exe", "winlogon.exe", "consent.exe", "lockapp.exe", "applicationframehost.exe", "shellexperiencehost.exe") or not name:
                            existing.add(hwnd)
                            hwnds_info.append(item)
            
            def _cur_top_cb(h, _lp):
                if h not in existing:
                    is_vis = user32.IsWindowVisible(h) or bool(user32.GetWindowLongW(h, -16) & 0x10000000)
                    if is_vis and not user32.IsIconic(h) and not _hwnd_is_dwm_cloaked(h):
                        r = wintypes.RECT()
                        if user32.GetWindowRect(h, ctypes.byref(r)):
                            cw = int(r.right - r.left)
                            ch = int(r.bottom - r.top)
                            if cw >= 20 and ch >= 20:
                                cpid = wintypes.DWORD()
                                user32.GetWindowThreadProcessId(h, ctypes.byref(cpid))
                                cname = _pid_image_basename(cpid.value)
                                c_full = (cw >= int(sw * 0.85) and ch >= int(sh * 0.85))
                                if not c_full or cname in ("logonui.exe", "winlogon.exe", "consent.exe", "lockapp.exe", "applicationframehost.exe", "shellexperiencehost.exe") or not cname:
                                    existing.add(h)
                                    hwnds_info.append((h, cw, ch, int(cpid.value), int(r.left), int(r.top)))
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            top_proc = WNDENUMPROC(_cur_top_cb)
            user32.EnumDesktopWindows(None, top_proc, 0)
            user32.EnumWindows(top_proc, 0)

        hwnds_info = _filter_winlogon_top_hwnds(hwnds_info, sw, sh)
        existing = {item[0] for item in hwnds_info}

        # Duyệt child windows của mọi cửa sổ tìm thấy (Network Flyout, DirectUIHWND, popup con)
        def _child_cb(ch, _lp):
            if ch not in existing:
                is_vis = user32.IsWindowVisible(ch) or bool(user32.GetWindowLongW(ch, -16) & 0x10000000)
                if is_vis and not user32.IsIconic(ch) and not _hwnd_is_dwm_cloaked(ch):
                    r = wintypes.RECT()
                    if user32.GetWindowRect(ch, ctypes.byref(r)):
                        cw = int(r.right - r.left)
                        ch_h = int(r.bottom - r.top)
                        if 20 <= cw < int(sw * 0.95) and 20 <= ch_h < int(sh * 0.95):
                            existing.add(ch)
                            cpid = wintypes.DWORD()
                            user32.GetWindowThreadProcessId(ch, ctypes.byref(cpid))
                            hwnds_info.append((ch, cw, ch_h, int(cpid.value), int(r.left), int(r.top)))
            return True

        child_proc = WNDENUMPROC(_child_cb)
        for item in list(hwnds_info):
            user32.EnumChildWindows(item[0], child_proc, 0)
    except Exception:
        pass

    for hwnd, w, h, _pid, x, y in hwnds_info:
        if hwnd in seen:
            continue
        seen.add(hwnd)
        cap = _capture_hwnd_bgr(hwnd, w, h, x, y)
        if cap is None:
            continue
        out.append((cap[0], x, y, w, h))
    return out


def grab_current_desktop_printwindow():
    """Logon / Sign out / UAC: PrintWindow cửa sổ lớn nhất trên desktop của thread."""
    if sys.platform != "win32":
        return None
    user32 = ctypes.windll.user32
    from ctypes import wintypes
    hwnds = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lp):
        if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd) and not _hwnd_is_dwm_cloaked(hwnd):
            hwnds.append(hwnd)
        return True

    cb = WNDENUMPROC(_cb)
    if not user32.EnumDesktopWindows(None, cb, 0):
        user32.EnumWindows(cb, 0)

    extra_pids = set()
    try:
        import psutil
        for p in psutil.process_iter(["name", "pid"]):
            nm = str(p.info.get("name") or "").lower()
            if nm in ("logonui.exe", "winlogon.exe", "consent.exe", "lockapp.exe"):
                extra_pids.add(int(p.info["pid"]))
    except Exception:
        pass
    if extra_pids:
        def _cb_pid(hwnd, _lp):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in extra_pids and user32.IsWindowVisible(hwnd) and not _hwnd_is_dwm_cloaked(hwnd):
                hwnds.append(hwnd)
            return True
        user32.EnumWindows(WNDENUMPROC(_cb_pid), 0)

    best = None
    best_score = (0, 0)
    rect = wintypes.RECT()
    seen = set()
    for hwnd in hwnds:
        if hwnd in seen:
            continue
        seen.add(hwnd)
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            continue
        w = int(rect.right - rect.left)
        h = int(rect.bottom - rect.top)
        area = w * h
        if w >= 200 and h >= 200:
            score = (1 if _is_bsdr_hwnd(hwnd) else 0, area)
            if score > best_score:
                best_score = score
                best = (hwnd, w, h)
    if not best:
        return None
    hwnd, w, h = best
    return _printwindow_hwnd_bgr(hwnd, w, h)


def grab_logonui_printwindow():
    return grab_current_desktop_printwindow()


def _bsdr_band_detail(bgr):
    """Đếm số pixel chi tiết giao diện (chữ trắng/nút/icon khác màu nền trung vị) ở dải trên (tiêu đề BSDR),
    dải dưới (nút Restart anyway / Cancel) và toàn màn hình."""
    if bgr is None or not getattr(bgr, "size", 0):
        return 0, 0, 0
    try:
        sub = bgr[::2, ::2]
        sh_f = sub.shape[0]
        med = np.median(sub.reshape(-1, 3), axis=0)
        diff = np.max(np.abs(sub.astype(np.int16) - med.astype(np.int16)), axis=2)
        mask = diff > 22
        top_nz = int(np.count_nonzero(mask[int(sh_f * 0.08):int(sh_f * 0.35), :]))
        bot_nz = int(np.count_nonzero(mask[int(sh_f * 0.65):int(sh_f * 0.92), :]))
        tot_nz = int(np.count_nonzero(mask))
        return top_nz, bot_nz, tot_nz
    except Exception:
        return 0, 0, 0


def _grab_secure_desktop_bgr_here():
    """PrintWindow HWND LogonUI/winlogon → BitBlt HWND → BitBlt cả desktop Winlogon."""
    # Ưu tiên BitBlt màn hình chính Winlogon (LogonUI luôn nằm ở màn hình chính 0,0)
    frame_bgr = None
    cap_w = cap_h = 0
    origin = (0, 0)
    try:
        sw = int(ctypes.windll.user32.GetSystemMetrics(0))
        sh = int(ctypes.windll.user32.GetSystemMetrics(1))
        left, top = 0, 0
        if sw <= 0 or sh <= 0:
            left = int(ctypes.windll.user32.GetSystemMetrics(76))
            top = int(ctypes.windll.user32.GetSystemMetrics(77))
            vw = int(ctypes.windll.user32.GetSystemMetrics(78))
            vh = int(ctypes.windll.user32.GetSystemMetrics(79))
            if vw > 0 and vh > 0:
                sw, sh = vw, vh
            else:
                left, top = 0, 0
        frame_bgr, cap_w, cap_h, origin = _bitblt_screen_rect_bgr(left, top, sw, sh)
    except Exception:
        frame_bgr = None

    frame_bgr_orig = frame_bgr.copy() if frame_bgr is not None else None

    # 2. Trên Windows 10/11, BitBlt GetDC(0) CHỈ chụp được hình nền (Bloom wallpaper),
    # KHÔNG chụp được các cửa sổ XAML/DirectComposition của LogonUI (Avatar, tên Admin, nút Sign in, Power menu).
    # Do đó BẮT BUỘC phải lấy cửa sổ LogonUI qua PrintWindow và dán đè lên canvas!
    overlays = _logonui_window_captures()
    if overlays:
        if frame_bgr is None:
            frame_bgr = np.zeros((sh, sw, 3), dtype=np.uint8)
            cap_w, cap_h = sw, sh
            origin = (left, top)
        left0 = origin[0] if origin else left
        top0 = origin[1] if origin else top
        # QUAN TRỌNG: Sắp xếp theo diện tích giảm dần (Painter's Algorithm)
        # Cửa sổ to (nền LogonUI) dán trước.
        # Cửa sổ nhỏ (menu con Restart, Shutdown, Sleep, dialog, Network flyout) dán sau đè lên trên!
        overlays.sort(key=lambda t: t[3] * t[4], reverse=True)
        has_small_bottom_right_overlay = False
        for tile, x, y, _tw, _th in overlays:
            if _frame_is_nearly_black(tile):
                continue
            is_large = (_tw >= sw * 0.75 and _th >= sh * 0.75)
            if is_large and not _frame_is_nearly_black(frame_bgr):
                # Nếu tile là màn hình nền đặc (như nền xanh 'Restarting' của LogonUI, không phải nền đen trong suốt của Login),
                # tuyệt đối không cho phép nó đè xóa mất màn hình BSDR ('Closing X apps and restarting') đã có trên frame_bgr!
                try:
                    sub_t = tile[::4, ::4]
                    black_pixels = np.count_nonzero(
                        (sub_t[:, :, 0] <= 12) & (sub_t[:, :, 1] <= 12) & (sub_t[:, :, 2] <= 12)
                    )
                    black_ratio = float(black_pixels) / max(1, sub_t.shape[0] * sub_t.shape[1])
                    if black_ratio < 0.25:
                        c_top, c_bot, c_tot = _bsdr_band_detail(frame_bgr)
                        t_top, t_bot, t_tot = _bsdr_band_detail(tile)
                        if (c_top > 150 and c_bot > 150 and t_top < c_top * 0.35) or (
                            c_tot > 300 and t_tot < c_tot * 0.45
                        ):
                            continue
                except Exception:
                    pass
            if not is_large and (int(x) >= int(sw * 0.45)) and (int(y) >= int(sh * 0.35)):
                has_small_bottom_right_overlay = True
            _clip_tile_onto_canvas(frame_bgr, tile, int(x) - left0, int(y) - top0, mask_black=is_large)

        # Failsafe cho Network Flyout / Popup: Nếu không có overlay riêng ở góc phải dưới,
        # nhưng frame_bgr_orig (Screen DC trước khi bị LogonUI PrintWindow đè lên)
        # có chứa popup menu (chữ trắng/icon/nút), phục hồi lại vùng flyout đó!
        if not has_small_bottom_right_overlay and frame_bgr_orig is not None:
            try:
                fly_w = max(500, int(sw * 0.28))
                fly_h = max(550, int(sh * 0.38))
                rx0 = max(0, sw - fly_w)
                ry0 = max(0, sh - fly_h)
                rx1 = sw
                ry1 = sh
                orig_roi = frame_bgr_orig[ry0:ry1, rx0:rx1]
                if float(np.max(orig_roi)) > 55.0 and np.count_nonzero(orig_roi > 40) > 100:
                    cur_roi = frame_bgr[ry0:ry1, rx0:rx1]
                    diff = cv2.absdiff(orig_roi, cur_roi)
                    if np.count_nonzero(diff > 25) > 150:
                        frame_bgr[ry0:ry1, rx0:rx1] = orig_roi
            except Exception:
                pass

        if not _frame_is_nearly_black(frame_bgr):
            return frame_bgr, cap_w, cap_h, origin

    # Nếu không có overlay (không tìm thấy cửa sổ LogonUI riêng), dùng frame BitBlt toàn màn hình
    if frame_bgr is not None and not _frame_is_nearly_black(frame_bgr):
        return frame_bgr, cap_w, cap_h, origin

    try:
        alt = grab_gdi_primary_bgr(use_screen_dc=False)
        if alt is not None and not _frame_is_nearly_black(alt[0]):
            return alt
    except Exception:
        pass
    alt = grab_current_desktop_printwindow()
    if alt is not None:
        return alt
    if frame_bgr is not None:
        return frame_bgr, cap_w, cap_h, origin
    raise RuntimeError("Winlogon desktop capture failed")


_winlogon_grab_lock = threading.Lock()
_winlogon_grab_req = queue.Queue(maxsize=1)
_winlogon_grab_res = queue.Queue(maxsize=1)
_winlogon_grab_thread = None

def _winlogon_grab_loop():
    """Thread sạch (không cửa sổ DXGI) — SetThreadDesktop(Winlogon) giống lúc Login."""
    if _switch_capture_thread_to_named_desktop("Winlogon"):
        print("[Host] Dedicated Winlogon capture thread attached")
    else:
        print("[Host] Dedicated Winlogon capture thread: SetThreadDesktop failed")
    while True:
        _winlogon_grab_req.get()
        try:
            if get_desktop_name() != "winlogon":
                _switch_capture_thread_to_named_desktop("Winlogon")
            _winlogon_grab_res.put(_grab_secure_desktop_bgr_here())
        except Exception as e:
            try:
                _winlogon_grab_res.put(e)
            except Exception:
                pass

def _ensure_winlogon_grab_thread():
    """Gắn thread Winlogon từ lúc worker start — Sign out không chờ SetThreadDesktop."""
    if sys.platform != "win32":
        return
    global _winlogon_grab_thread
    with _winlogon_grab_lock:
        if _winlogon_grab_thread is None or not _winlogon_grab_thread.is_alive():
            _winlogon_grab_thread = threading.Thread(
                target=_winlogon_grab_loop, name="WinlogonGrab", daemon=True
            )
            _winlogon_grab_thread.start()

def grab_secure_desktop_bgr():
    """Luôn capture từ thread đã SetThreadDesktop(Winlogon) — DXGI Default hay trả về đen."""
    if sys.platform != "win32":
        return _grab_secure_desktop_bgr_here()
    _ensure_winlogon_grab_thread()
    try:
        while True:
            try:
                _winlogon_grab_res.get_nowait()
            except queue.Empty:
                break
        _winlogon_grab_req.put(True, timeout=0.15)
        r = _winlogon_grab_res.get(timeout=0.7)
        if isinstance(r, Exception):
            raise r
        return r
    except Exception:
        if get_desktop_name() != "winlogon":
            _switch_capture_thread_to_named_desktop("Winlogon")
        return _grab_secure_desktop_bgr_here()


_dxcam_patched = False

def _patch_dxcam_safe():
    """Vá lỗi chí mạng trong dxcam.dxcam.DXCamera._on_output_change:
    Ngăn vòng lặp vô tận `while True` khi màn hình tắt / sleep / khóa máy làm CPU 100% và treo capture engine."""
    global _dxcam_patched
    if _dxcam_patched or sys.platform != "win32":
        return
    try:
        import dxcam
        from dxcam.dxcam import DXCamera
        from dxcam.core.duplicator import Duplicator

        def _safe_on_output_change(self):
            time.sleep(0.05)
            try:
                if hasattr(self, "_duplicator") and self._duplicator:
                    self._duplicator.release()
                if hasattr(self, "_stagesurf") and self._stagesurf:
                    self._stagesurf.release()
                if hasattr(self, "_output") and self._output:
                    self._output.update_desc()
                    self.width, self.height = self._output.resolution
                    if self.region is None or not self._region_set_by_user:
                        self.region = (0, 0, self.width, self.height)
                    self._validate_region(self.region)
                    if self.is_capturing:
                        self._rebuild_frame_buffer(self.region)
                    self.rotation_angle = self._output.rotation_angle
            except Exception:
                pass
            # Thử tối đa 10 lần, mỗi lần cách nhau 50ms (tổng 500ms). Nếu sau 500ms vẫn chưa sẵn sàng (màn hình đang ngủ/khóa),
            # ném lỗi ra ngoài để luồng capture chuyển sang fallback MSS / GDI an toàn, không bị while True vô tận!
            for _ in range(10):
                try:
                    self._stagesurf.rebuild(output=self._output, device=self._device)
                    self._duplicator = Duplicator(output=self._output, device=self._device)
                    return
                except Exception:
                    time.sleep(0.05)
            raise RuntimeError("DXCam output duplication access lost (screen sleeping or locked)")

        DXCamera._on_output_change = _safe_on_output_change
        _dxcam_patched = True
        print("[Host] Da ap dung ban va an toan chong treo cho DXCam.")
    except Exception as e:
        print(f"[Host] Khong the va DXCam: {e}")


def _open_dxcam_outputs():
    cams = []
    if not _windows_has_dxgi_duplication():
        print("[Host] Skip dxcam (Windows 7/Vista không hỗ trợ Desktop Duplication)")
        return cams
    _patch_dxcam_safe()
    try:
        import dxcam
        fac = dxcam.DXFactory()
        # Dọn dẹp cache instance cũ đã bị release trong DXFactory để không nhận lại camera lỗi
        if hasattr(fac, "_camera_instances"):
            fac._camera_instances.clear()
    except Exception as e:
        print(f"[Host] dxcam factory failed: {e}")
        return cams
    for di, outputs in enumerate(getattr(fac, "outputs", []) or []):
        for oi, output in enumerate(outputs):
            try:
                if hasattr(output, "attached_to_desktop") and not output.attached_to_desktop:
                    continue
                # Bỏ qua output có kích thước không hợp lệ (màn hình ma / 0x0)
                res = getattr(output, "resolution", (0, 0))
                if not res or res[0] <= 0 or res[1] <= 0:
                    continue
                cam = dxcam.create(
                    device_idx=di,
                    output_idx=oi,
                    output_color="BGR",
                    max_buffer_len=2,
                )
                if cam is None:
                    continue
                cams.append(cam)
                print(f"[Host] DXGI capture Device {di} Output {oi}: {output}")
            except Exception as e:
                print(f"[Host] dxcam Device {di} Output {oi} failed: {e}")
    return cams


def grab_gdi_monitor_bgr(monitor_mode="both"):
    """Chụp GDI theo chế độ màn hình ('both', 'left', 'right')."""
    if monitor_mode in ("left", "right"):
        rects = _get_physical_monitor_rects()
        if len(rects) >= 2:
            idx = 0 if monitor_mode == "left" else 1
            ml, mt, mw, mh = rects[idx]
            cap = _bitblt_screen_rect_bgr(ml, mt, mw, mh)
            if cap is not None:
                return cap
    return grab_gdi_primary_bgr()


def grab_dxcam_virtual_bgr(cams, canvas=None, monitor_mode="both"):
    left0, top0, w, h = _virtual_screen_rect()
    cam_entries = []
    for cam in list(cams):
        try:
            cam._output.update_desc()
            rc = cam._output.desc.DesktopCoordinates
            cl, ct = int(rc.left), int(rc.top)
            cw = max(1, int(rc.right - rc.left))
            ch = max(1, int(rc.bottom - rc.top))
            cam_entries.append((cam, cl, ct, cw, ch))
        except Exception:
            cam_entries.append((cam, left0, top0, w, h))
    cam_entries.sort(key=lambda it: (it[1], it[2]))

    global _active_monitor_rects_last
    if len(cam_entries) == 1 or (monitor_mode in ("left", "right") and len(cam_entries) >= 2):
        idx = 0 if len(cam_entries) == 1 else (0 if monitor_mode == "left" else 1)
        target_cam, cl, ct, cw, ch = cam_entries[idx]
        try:
            tile = target_cam.grab()
            if tile is not None and getattr(tile, "size", 0) > 0:
                if tile.ndim == 2:
                    tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
                elif tile.shape[2] == 4:
                    tile = cv2.cvtColor(tile, cv2.COLOR_BGRA2BGR)
                th, tw = tile.shape[:2]
                if not _frame_is_nearly_black(tile):
                    target_cam._last_good_tile = tile
                    if len(cam_entries) == 1:
                        _active_monitor_rects_last = [(int(cl), int(ct), int(tw), int(th))]
                    return tile, tw, th, (cl, ct), True
                cached = getattr(target_cam, "_last_good_tile", None)
                if cached is not None and getattr(cached, "size", 0) > 0:
                    th, tw = cached.shape[:2]
                    if len(cam_entries) == 1:
                        _active_monitor_rects_last = [(int(cl), int(ct), int(tw), int(th))]
                    return cached, tw, th, (cl, ct), True
                if len(cam_entries) == 1:
                    _active_monitor_rects_last = [(int(cl), int(ct), int(tw), int(th))]
                return tile, tw, th, (cl, ct), False
            cached = getattr(target_cam, "_last_good_tile", None)
            if cached is not None and getattr(cached, "size", 0) > 0:
                th, tw = cached.shape[:2]
                if len(cam_entries) == 1:
                    _active_monitor_rects_last = [(int(cl), int(ct), int(tw), int(th))]
                return cached, tw, th, (cl, ct), True
            return None, cw, ch, (cl, ct), False
        except Exception as e:
            print(f"[Host] dxcam single monitor grab failed: {e}")
            try:
                if target_cam in cams:
                    cams.remove(target_cam)
                target_cam.release()
            except Exception:
                pass
            return None, cw, ch, (cl, ct), False

    canvas_fresh = (canvas is None or canvas.shape[0] != h or canvas.shape[1] != w)
    if canvas_fresh:
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
    any_ok = False
    bad_cams = []
    captured_tiles = []
    for cam, cl, ct, _cw, _ch in cam_entries:
        try:
            tile = cam.grab()
            if (tile is None or getattr(tile, "size", 0) == 0) and not getattr(cam, "_init_probed", False):
                cam._init_probed = True
                if sys.platform == "win32" and len(cam_entries) > 1:
                    try:
                        cap_g = _bitblt_screen_rect_bgr(cl, ct, _cw, _ch)
                        if cap_g is not None and cap_g[0] is not None and getattr(cap_g[0], "size", 0) > 0:
                            tile = cap_g[0]
                    except Exception:
                        pass
            if tile is not None and getattr(tile, "size", 0) > 0:
                if tile.ndim == 2:
                    tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
                elif tile.shape[2] == 4:
                    tile = cv2.cvtColor(tile, cv2.COLOR_BGRA2BGR)
                if not _frame_is_nearly_black(tile):
                    cam._last_good_tile = tile
            else:
                tile = getattr(cam, "_last_good_tile", None)
            if tile is None or getattr(tile, "size", 0) == 0:
                continue
            x, y = cl - left0, ct - top0
            orig_pos = (cl, ct)

            tile_is_black = _frame_is_nearly_black(tile)
            # Nếu màn hình này đen kịt (phantom/inactive) và đã có màn hình khác có nội dung -> bỏ qua
            if tile_is_black and any_ok:
                continue

            if _clip_tile_onto_canvas(canvas, tile, x, y, mask_black=any_ok):
                any_ok = True
                captured_tiles.append((tile, orig_pos))
        except Exception as e:
            print(f"[Host] dxcam grab failed: {e}")
            bad_cams.append(cam)

    # Loại bỏ ngay camera bị hỏng để các lần lặp sau không bị khựng delay 500ms
    if bad_cams:
        for bc in bad_cams:
            try:
                if bc in cams:
                    cams.remove(bc)
            except Exception:
                pass
            try:
                bc.release()
            except Exception:
                pass

    # QUY TẮC CHỐNG NHÁY 2 MÀN HÌNH:
    # Chỉ khi có >= 2 màn hình thực sự có hình (len(non_black) >= 2) mới trả về canvas ghép đa màn hình.
    # Khi <= 1 màn hình có nội dung (hoặc lúc vừa wake_display màn hình đang thức dậy nên non_black rỗng),
    # LUÔN trả về đúng 1 tile màn hình đơn lẻ, TUYỆT ĐỐI không trả về canvas ghép 2 màn hình!
    if any_ok and captured_tiles:
        non_black = [t for t in captured_tiles if not _frame_is_nearly_black(t[0])]
        if len(non_black) >= 2:
            _active_monitor_rects_last = [
                (int(pos[0]), int(pos[1]), int(t.shape[1]), int(t.shape[0]))
                for (t, pos) in non_black
            ]
        elif len(non_black) == 1:
            tile, (orig_x, orig_y) = non_black[0]
            canvas = tile
            h, w = tile.shape[:2]
            left0, top0 = orig_x, orig_y
            _active_monitor_rects_last = [(int(orig_x), int(orig_y), int(w), int(h))]
        else:
            tile, (orig_x, orig_y) = captured_tiles[0]
            canvas = tile
            h, w = tile.shape[:2]
            left0, top0 = orig_x, orig_y
            if not _active_monitor_rects_last:
                _active_monitor_rects_last = [(int(orig_x), int(orig_y), int(w), int(h))]
            any_ok = False

    return canvas, w, h, (left0, top0), any_ok


def grab_virtual_desktop_bgr(sct, canvas=None, monitor_mode="both"):
    """Bắt từng màn rồi ghép. Không BitBlt cả monitors[0] (thường đen trên máy nhiều GPU)."""
    left0, top0, w, h = _virtual_screen_rect()
    mons = sct.monitors
    if mons:
        virt = mons[0]
        left0 = int(virt.get("left", left0))
        top0 = int(virt.get("top", top0))
        w = int(virt.get("width", w))
        h = int(virt.get("height", h))
    if w < 1 or h < 1:
        raise RuntimeError("invalid virtual screen size")
    parts = mons[1:] if mons and len(mons) > 1 else (mons[:1] if mons else [])
    
    # Lọc bỏ các monitor không hợp lệ (width <= 0 hoặc height <= 0) và sắp xếp Trái -> Phải
    valid_parts = [m for m in parts if m.get("width", 0) > 0 and m.get("height", 0) > 0]
    valid_parts.sort(key=lambda m: (int(m.get("left", 0)), int(m.get("top", 0))))
    if not valid_parts and mons:
        valid_parts = [mons[0]]

    global _active_monitor_rects_last
    if len(valid_parts) == 1 or (monitor_mode in ("left", "right") and len(valid_parts) >= 2):
        idx = 0 if len(valid_parts) == 1 else (0 if monitor_mode == "left" else 1)
        mon = valid_parts[idx]
        raw = sct.grab(mon)
        tile = np.array(raw, dtype=np.uint8)
        if tile is None or getattr(tile, "size", 0) == 0:
            raise mss.exception.ScreenShotError("single monitor grab empty")
        if tile.ndim == 2:
            tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
        elif tile.shape[2] == 4:
            tile = cv2.cvtColor(tile, cv2.COLOR_BGRA2BGR)
        th, tw = tile.shape[:2]
        ml, mt = int(mon.get("left", 0)), int(mon.get("top", 0))
        if len(valid_parts) == 1:
            _active_monitor_rects_last = [(ml, mt, int(tw), int(th))]
        return tile, tw, th, (ml, mt)

    if canvas is None or canvas.shape[0] != h or canvas.shape[1] != w:
        canvas = np.zeros((h, w, 3), dtype=np.uint8)

    any_ok = False
    captured_tiles = []
    for mon in valid_parts:
        try:
            raw = sct.grab(mon)
            tile = np.array(raw, dtype=np.uint8)
            if tile is None or getattr(tile, "size", 0) == 0:
                continue
            if tile.ndim == 2:
                tile = cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR)
            elif tile.shape[2] == 4:
                tile = cv2.cvtColor(tile, cv2.COLOR_BGRA2BGR)

            tile_is_black = _frame_is_nearly_black(tile)
            # Nếu màn hình này đen kịt (phantom/inactive) nhưng đã có màn hình khác có nội dung -> bỏ qua không cho đè
            if tile_is_black and any_ok:
                continue

            mx = int(mon.get("left", 0)) - left0
            my = int(mon.get("top", 0)) - top0
            if _clip_tile_onto_canvas(
                canvas, tile,
                mx,
                my,
                mask_black=any_ok,
            ):
                any_ok = True
                captured_tiles.append((tile, mon))
        except Exception as e:
            print(f"[Host] Monitor grab failed ({mon}): {e}")

    # QUY TẮC CHỐNG NHÁY 2 MÀN HÌNH:
    # Chỉ khi có >= 2 màn hình thực sự có nội dung (len(non_black) >= 2) mới trả về canvas ghép đa màn hình.
    # Khi <= 1 màn hình có nội dung (hoặc non_black rỗng khi màn hình đang ngủ/thức dậy),
    # LUÔN trả về đúng 1 tile màn hình đơn lẻ, TUYỆT ĐỐI không trả về canvas ghép 2 màn hình!
    if any_ok and captured_tiles:
        non_black = [t for t in captured_tiles if not _frame_is_nearly_black(t[0])]
        if len(non_black) >= 2:
            _active_monitor_rects_last = [
                (int(m.get("left", 0)), int(m.get("top", 0)), int(t.shape[1]), int(t.shape[0]))
                for (t, m) in non_black
            ]
        elif len(non_black) == 1:
            tile, mon = non_black[0]
            canvas = tile
            h, w = tile.shape[:2]
            left0 = int(mon.get("left", 0))
            top0 = int(mon.get("top", 0))
            _active_monitor_rects_last = [(left0, top0, int(w), int(h))]
        else:
            tile, mon = captured_tiles[0]
            canvas = tile
            h, w = tile.shape[:2]
            left0 = int(mon.get("left", 0))
            top0 = int(mon.get("top", 0))
            if not _active_monitor_rects_last:
                _active_monitor_rects_last = [(left0, top0, int(w), int(h))]

    if not any_ok:
        raise mss.exception.ScreenShotError("all monitor grabs failed")
    return canvas, w, h, (left0, top0)


def scale_frame_for_send(frame_bgr, cap_w, cap_h, max_edge=2560):
    if max_edge <= 0 or (cap_w <= max_edge and cap_h <= max_edge):
        return frame_bgr
    scale = min(max_edge / float(cap_w), max_edge / float(cap_h))
    nw = max(10, int(cap_w * scale))
    nh = max(10, int(cap_h * scale))
    return cv2.resize(frame_bgr, (nw, nh), interpolation=cv2.INTER_AREA)


def _fm_host_should_stop():
    cm = clipboard_sync_manager
    ev = getattr(cm, "_fm_send_abort", None) if cm else None
    return bool(ev is not None and ev.is_set())


def _fm_host_send(c, payload, pwd):
    """Gửi gói File Manager; timeout 2s, dừng khi Hủy."""
    if _fm_host_should_stop():
        return False
    old = None
    try:
        old = c.gettimeout()
        c.settimeout(2.0)
        send_msg(c, json.dumps(payload).encode("utf-8"), pwd)
        return True
    except Exception as e:
        print(f"[Host] FM send loi/timeout: {e}")
        return False
    finally:
        try:
            c.settimeout(old)
        except Exception:
            pass


class HostMixin:
    def ensure_input_thread_desktop(self, force=False):
        """Gắn thread input vào desktop đang nhận chuột (hộp UAC Yes/No)."""
        if getattr(self, 'is_headless', False) is False and sys.platform != "win32":
            return
            
        now = time.time()
        last_check = getattr(self, '_last_input_desktop_check', 0)
        if not force and (now - last_check < 0.2):
            return
        self._last_input_desktop_check = now
        try:
            attach_thread_for_remote_input()
        except Exception as e:
            print(f"[Host Input] Error in ensure_input_thread_desktop: {e}")

    def start_host_server(self):
        if sys.platform == "win32":
            set_windows_graphics_effects(True)
            boost_process_priority()
            try:
                # Giữ hệ thống và màn hình luôn sẵn sàng trong khi Host đang chờ kết nối
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
            except Exception:
                pass
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
                import core.config; core.config.BOUND_PORT = port
                import core.network_manager; core.network_manager.BOUND_PORT = port
                self.server_socket.listen(5)
                print(f"[Host] TCP server successfully listening on port {BOUND_PORT} (Dual-Stack)...")
                bound = True
                break
            except Exception as e:
                print(f"[Host] Failed to bind to port {port}: {e}")
                continue
                
        if not bound:
            self.after(0, lambda: self.show_custom_error(_("Lỗi hệ thống"), _("Không thể chạy server! Các cổng mạng đều bị chiếm dụng hoặc bị chặn bởi Tường lửa.\nVui lòng kiểm tra lại cấu hình mạng hoặc tắt bớt ứng dụng chiếm cổng.")))
            self.update_status(_("Lỗi khởi động Server"))
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
                
    def _physical_virtual_screen(self):
        """Physical pixel rect of the virtual desktop (correct at 125%/150% DPI). Tk winfo_screen* is logical."""
        user32 = ctypes.windll.user32
        vx = int(user32.GetSystemMetrics(76))  # SM_XVIRTUALSCREEN
        vy = int(user32.GetSystemMetrics(77))  # SM_YVIRTUALSCREEN
        vw = int(user32.GetSystemMetrics(78))  # SM_CXVIRTUALSCREEN
        vh = int(user32.GetSystemMetrics(79))  # SM_CYVIRTUALSCREEN
        if vw <= 0 or vh <= 0:
            vx, vy = 0, 0
            vw = int(user32.GetSystemMetrics(0))
            vh = int(user32.GetSystemMetrics(1))
        return vx, vy, vw, vh

    def show_host_connection_border(self):
        if sys.platform != "win32" or _is_legacy_windows_host() or _is_server_or_remote_session():
            return
        try:
            self.hide_host_connection_border()
            
            import tkinter as tk
            self.host_border_wins = []
            
            vx, vy, w, h = self._physical_virtual_screen()
            self._last_border_w = w
            self._last_border_h = h
            
            thickness = 5
            color = "#FF69B4"
            
            # Use a SINGLE window with a border-shaped region instead of 4 windows
            win = tk.Toplevel(self)
            win.withdraw()
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.attributes("-alpha", 0.8)
            win.configure(bg=color)
            win.geometry(f"{w}x{h}+{vx}+{vy}")
            win.update_idletasks()
            
            try:
                import ctypes
                tk_hwnd = win.winfo_id()

                # Get host window HWNDs to strictly exclude from transparent/toolwindow styling
                host_hwnds = set()
                try:
                    host_hwnds.add(self.winfo_id())
                except Exception:
                    pass
                try:
                    hf = int(self.frame(), 16)
                    if hf:
                        host_hwnds.add(hf)
                except Exception:
                    pass
                
                # Collect ALL unique HWNDs of the BORDER window only (never the host window)
                hwnds_to_style = set()
                if tk_hwnd not in host_hwnds:
                    hwnds_to_style.add(tk_hwnd)
                
                parent = ctypes.windll.user32.GetParent(tk_hwnd)
                if parent and parent not in host_hwnds and parent != ctypes.windll.user32.GetDesktopWindow():
                    hwnds_to_style.add(parent)
                
                GA_ROOT = 2
                root = ctypes.windll.user32.GetAncestor(tk_hwnd, GA_ROOT)
                if root and root not in host_hwnds and root != ctypes.windll.user32.GetDesktopWindow():
                    hwnds_to_style.add(root)
                
                # NOTE: Never add GA_ROOTOWNER because owner is the host window (self)!
                
                try:
                    frame_id = win.wm_frame()
                    fh = int(frame_id, 0) if isinstance(frame_id, str) else int(frame_id)
                    if fh and fh not in host_hwnds:
                        hwnds_to_style.add(fh)
                except:
                    pass
                
                GWL_EXSTYLE = -20
                WS_EX_TRANSPARENT = 0x00000020
                WS_EX_TOOLWINDOW = 0x00000080
                WS_EX_APPWINDOW = 0x00040000
                WS_EX_NOACTIVATE = 0x08000000
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOZORDER = 0x0004
                SWP_FRAMECHANGED = 0x0020
                SWP_NOACTIVATE = 0x0010
                HWND_TOPMOST = -1
                
                pos_hwnd = root if (root and root not in host_hwnds and root != ctypes.windll.user32.GetDesktopWindow()) else tk_hwnd
                try:
                    dpi = int(ctypes.windll.user32.GetDpiForWindow(pos_hwnd))
                    if dpi > 0:
                        thickness = max(4, int(round(5 * dpi / 96.0)))
                except Exception:
                    pass
                
                # Apply WS_EX_TOOLWINDOW only on border HWNDs to guarantee taskbar hiding
                for hwnd in hwnds_to_style:
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    new_style = (style & ~WS_EX_APPWINDOW) | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE)
                
                # Tk geometry is logical pixels; pin the window to physical virtual-screen size.
                ctypes.windll.user32.SetWindowPos(
                    pos_hwnd, HWND_TOPMOST, vx, vy, w, h, SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE
                )
                if tk_hwnd != pos_hwnd:
                    ctypes.windll.user32.SetWindowPos(
                        tk_hwnd, 0, 0, 0, w, h, SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
                    )
                
                def _apply_frame_rgn(hwnd):
                    outer = ctypes.windll.gdi32.CreateRectRgn(0, 0, w, h)
                    inner = ctypes.windll.gdi32.CreateRectRgn(thickness, thickness, w - thickness, h - thickness)
                    ctypes.windll.gdi32.CombineRgn(outer, outer, inner, 4)  # RGN_DIFF
                    ctypes.windll.user32.SetWindowRgn(hwnd, outer, True)
                    ctypes.windll.gdi32.DeleteObject(inner)
                
                _apply_frame_rgn(tk_hwnd)
                if root and root != tk_hwnd and root not in host_hwnds and root != ctypes.windll.user32.GetDesktopWindow():
                    _apply_frame_rgn(root)
                    
            except Exception as rgn_err:
                print(f"[Host] Failed to set border region/style: {rgn_err}")
            
            win.deiconify()
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
            _vx, _vy, current_w, current_h = self._physical_virtual_screen()
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
        if sys.platform != "win32":
            return
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
            # 1. Báo Windows người dùng có mặt và yêu cầu bật màn hình ngay lập tức (ES_USER_PRESENT | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)
            # Chú ý: Không kèm ES_CONTINUOUS khi có ES_USER_PRESENT thì Windows mới kích hoạt đánh thức màn hình
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(0x00000001 | 0x00000002 | 0x00000004)
                # 2. Duy trì trạng thái không ngủ trong suốt phiên kết nối
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
            except Exception:
                pass

            # 3. Gửi lệnh bật nguồn màn hình SC_MONITORPOWER = 0xF170, -1 = power on (bỏ qua trên Server/RDP)
            if not _is_server_or_remote_session():
                try:
                    ctypes.windll.user32.PostMessageW(0xFFFF, 0x0112, 0xF170, -1)
                except Exception:
                    pass

            # 4. Gắn input desktop nếu có thể để phím/chuột gửi đúng desktop đang hoạt động
            try:
                attach_thread_for_remote_input()
            except Exception:
                pass

            # 5. Giả lập phím VK_SHIFT (0x10) nhả ngay - an toàn không gõ chữ nhưng kích hoạt GPU driver & Windows DPMS
            try:
                ctypes.windll.user32.keybd_event(0x10, 0, 0, 0)
                ctypes.windll.user32.keybd_event(0x10, 0, 0x0002, 0)
            except Exception:
                pass

            # 6. Di chuyển chuột vi mô (1 pixel rồi về vị trí cũ) - đánh thức driver GPU/màn hình cực nhạy
            try:
                ctypes.windll.user32.mouse_event(0x0001, 1, 1, 0, 0)
                ctypes.windll.user32.mouse_event(0x0001, -1, -1, 0, 0)
            except Exception:
                pass
            print("[Host] Wake display signal sent.")
        except Exception as e:
            print(f"[Host] Failed to wake display: {e}")

    def handle_host_handshake(self, conn, addr):
        # We now support multiple clients, so we don't block new connections if active_clients is non-empty.
            
        try:
            # Reload random password from session_pass.txt (headless) and ALWAYS reload fixed_password from XML during handshake
            if self.is_headless:
                try:
                    pass_path = os.path.join(app_dir, "session_pass.txt")
                    if os.path.exists(pass_path):
                        with open(pass_path, "r", encoding="utf-8-sig") as f:
                            val = f.read().strip()
                            if val:
                                self.my_password = val
                except Exception as e:
                    print(f"[Host Service] Failed to reload password from session_pass.txt during handshake: {e}")

            try:
                self.fixed_password = self.load_fixed_password_from_xml()
            except Exception as e:
                print(f"[Host] Failed to reload fixed password from XML during handshake: {e}")

            # Register the socket with non-empty candidate passwords so recv_msg can decrypt client's handshake
            cand_keys = [k for k in (self.my_password, self.fixed_password, APP_KEY) if k]
            socket_passwords[conn] = cand_keys
            msg = recv_msg(conn, cand_keys)
            if not msg:
                print("[Host] Failed to decrypt handshake. Sending error using APP_KEY.")
                try:
                    err_info = json.dumps({
                        "status": "error",
                        "message": _("Sai mật khẩu kết nối hoặc dữ liệu không hợp lệ!")
                    }).encode('utf-8')
                    send_msg(conn, err_info, APP_KEY)
                except: pass
                time.sleep(0.5)
                try: force_close_socket(conn)
                except: pass
                socket_passwords.pop(conn, None)
                return
                
            data = json.loads(msg.decode('utf-8'))

            # Check if this is a LAN / VPN discovery probe
            if data.get("action") == "probe":
                try:
                    import platform
                    from core.config import LAN_APP_SIGNATURE
                    hw = getattr(self, "my_id_clean", "")
                    if not hw:
                        try:
                            from utils.hwid import load_saved_hwid, get_hwid
                            hw = load_saved_hwid() or get_hwid()[0] or ""
                        except Exception:
                            hw = ""
                    pong_data = json.dumps({
                        "status": "ok",
                        "type": "probe_pong",
                        "sig": LAN_APP_SIGNATURE,
                        "hwid": hw,
                        "computer_name": platform.node(),
                        "os": platform.system(),
                        "port": BOUND_PORT,
                        "local_ip": getattr(self, 'local_ip', ""),
                        "macs": getattr(self, 'my_macs', "")
                    }).encode('utf-8')
                    send_msg(conn, pong_data, APP_KEY)
                except Exception as probe_err:
                    print(f"[Host] Probe response error: {probe_err}")
                time.sleep(0.1)
                try: force_close_socket(conn)
                except: pass
                socket_passwords.pop(conn, None)
                return

            client_pass = data.get("password")
            
            password_valid = False
            if client_pass == self.my_password:
                password_valid = True
            elif self.fixed_password and client_pass == self.fixed_password:
                password_valid = True
                
            if password_valid:
                print("[Host] Password matches! Accepting connection.")
                socket_passwords[conn] = client_pass
                
                client_id = data.get("client_id", _("Không rõ"))
                client_comp = data.get("computer_name", _("Không rõ"))
                fmt_client_id = f"{client_id[:3]} {client_id[3:6]} {client_id[6:9]} {client_id[9:]}" if len(client_id) == 12 else client_id
                
                if client_comp != _("Không rõ"):
                    msg_text = _("Máy tính [{comp}] đang điều khiển máy bạn").format(comp=client_comp)
                else:
                    msg_text = _("Máy tính có ID [{id}] đang điều khiển máy bạn").format(id=fmt_client_id)
                    
                try: log_activity(_("Chấp nhận kết nối từ ID {id} ({comp})").format(id=fmt_client_id, comp=client_comp))
                except: pass
                
                # Notification UI will be shown after speed test

                # Tắt Nagle's algorithm (TCP_NODELAY) để giảm độ trễ tối đa
                try:
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except Exception as e:
                    print(f"[TCP_NODELAY] Lỗi thiết lập TCP_NODELAY trên Host: {e}")
                if is_lan_socket(conn):
                    tune_socket_for_lan_bulk(conn)
                
                # Cấu hình TCP Keep-Alive bảo vệ kết nối đục lỗ khỏi bị đóng bởi Firewall/Router
                try:
                    conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                    if not _is_legacy_windows_host():
                        ka = (1, 10000, 2000) if is_lan_socket(conn) else (1, 1000, 1000)
                        conn.ioctl(socket.SIOC_KEEPALIVE_VALS, ka)
                except Exception as e:
                    print(f"[KeepAlive] Lỗi cấu hình Keep-Alive trên Host: {e}")
                
                if _is_legacy_windows_host():
                    host_w = int(ctypes.windll.user32.GetSystemMetrics(0))
                    host_h = int(ctypes.windll.user32.GetSystemMetrics(1))
                    if host_w < 1 or host_h < 1:
                        host_w, host_h = 1024, 768
                    self._capture_origin = (0, 0)
                    monitor = {"left": 0, "top": 0, "width": host_w, "height": host_h}
                    active_mon_rects = [(0, 0, host_w, host_h)]
                    print(f"[Host] Win7 GDI handshake size {host_w}x{host_h}")
                else:
                    active_mon_rects = []
                    with mss.mss() as sct:
                        monitor, active_mon_rects = _get_active_monitors_and_virtual_rect(sct)
                        host_w = int(monitor.get('width', 0))
                        host_h = int(monitor.get('height', 0))
                        if host_w < 1 or host_h < 1:
                            host_w = int(ctypes.windll.user32.GetSystemMetrics(0)) or 1280
                            host_h = int(ctypes.windll.user32.GetSystemMetrics(1)) or 720
                            monitor = {"left": 0, "top": 0, "width": host_w, "height": host_h}
                            active_mon_rects = [(0, 0, host_w, host_h)]
                        self._capture_origin = (int(monitor.get('left', 0)), int(monitor.get('top', 0)))
                    
                import platform
                computer_name = platform.node()
                is_android = False
                try:
                    _HOST_ONLY = bool(getattr(__import__("host_build_flag", fromlist=["HOST_ONLY_BUILD"]), "HOST_ONLY_BUILD", False))
                except Exception:
                    _HOST_ONLY = False
                if not _HOST_ONLY and sys.platform != "win32":
                    try:
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
                                computer_name = f"MC-Android {serial}"
                    except Exception:
                        pass
                
                is_domain = False
                chk_reason = "Unknown"
                try:
                    is_domain, chk_reason = is_machine_domain_joined()
                except Exception as ex:
                    chk_reason = f"Error: {ex}"
                
                try:
                    with open("domain_debug.log", "a", encoding="utf-8-sig") as df:
                        df.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Host domain check: is_domain={is_domain}, reason={chk_reason}\n")
                except:
                    pass
                    
                init_mon_rects = [] if is_android else (active_mon_rects if active_mon_rects else _get_physical_monitor_rects())
                init_mon_cnt = 1 if is_android else max(1, len(init_mon_rects))
                res_info = json.dumps({
                    "status": "ok",
                    "width": host_w,
                    "height": host_h,
                    "monitor_count": init_mon_cnt,
                    "monitors": [{"left": r[0], "top": r[1], "width": r[2], "height": r[3]} for r in init_mon_rects],
                    "computer_name": computer_name,
                    "zalo_phone": self.load_zalo_phone_from_xml(),
                    "is_domain": is_domain,
                    "chk_reason": chk_reason,
                    "os_release": "android" if is_android else platform.release(),
                    "is_android": is_android,
                }).encode('utf-8')
                send_msg(conn, res_info, client_pass)
                
                client_state = {"running": True, "net_class": "medium", "wake_event": threading.Event()}
                
                # Speed test: WAN đo 1 vòng. LAN: client không gửi result trước khi mở viewer
                # (tránh flood JPEG rồi nhân socket → mất kết nối ngay). Ping từ viewer = sẵn sàng.
                try:
                    conn.settimeout(15.0)
                    while client_state.get("running", True):
                        probe_msg = recv_msg(conn, client_pass)
                        if not probe_msg:
                            break
                        try:
                            probe = json.loads(probe_msg.decode("utf-8"))
                        except Exception:
                            break
                        act = probe.get("action")
                        evt = probe.get("type")
                        if act == "speed_test_ping":
                            send_msg(conn, json.dumps({"action": "speed_test_pong"}).encode("utf-8"), client_pass)
                        elif act == "speed_test_bw_req":
                            dummy_size = int(probe.get("suggested_size", 262144))
                            dummy_size = max(1024, min(dummy_size, 1572864))
                            send_msg(conn, json.dumps({"action": "speed_test_bw_start", "size": dummy_size}).encode("utf-8"), client_pass)
                            conn.sendall(b"\x00" * dummy_size)
                        elif act == "speed_test_result":
                            net_class = probe.get("net_class", "medium")
                            client_state["net_class"] = net_class
                            bandwidth = probe.get("bandwidth", 32.0)
                            # Luôn đảm bảo hiệu ứng đồ họa và ClearType font smoothing đầy đủ cho cả Win 7, Win 10, Win 11
                            set_windows_graphics_effects(True)
                            break
                        elif evt == "ping":
                            if is_lan_socket(conn):
                                client_state["net_class"] = "high"
                            print("[Host] Viewer ready (ping). Starting capture.")
                            break
                        else:
                            break
                except Exception as ste:
                    print(f"[Host] Speed test handler error: {ste}")
                finally:
                    try: conn.settimeout(None)
                    except: pass
                
                # Hiển thị thông báo và viền đỏ sau khi test xong
                try:
                    _is_host_app = bool(HOST_ONLY_BUILD or getattr(self, "is_host_only", False))
                except Exception:
                    _is_host_app = False
                if not _is_host_app and not _is_server_or_remote_session():
                    self.after(0, lambda: self.show_custom_info(_("Kết nối từ xa"), msg_text, auto_close_sec=15))
                if not _is_legacy_windows_host() and not _is_server_or_remote_session():
                    self.after(0, self.show_host_connection_border)
                self.wake_display()
                attach_disconnected_session_to_console()
                if hasattr(self, "force_repaint"):
                    self.after(100, self.force_repaint)
                
                self.active_clients[addr] = client_state
                
                addrs_str = ", ".join([str(a[0]) for a in self.active_clients.keys()])
                self.update_status(_("Đang dùng máy chủ {addrs}").format(addrs=addrs_str))
                
                t_sender = threading.Thread(target=self.host_sender_thread, args=(conn, monitor, client_state, client_pass), daemon=True)
                t_receiver = threading.Thread(target=self.host_receiver_thread, args=(conn, client_state, client_pass), daemon=True)
                
                t_sender.start()
                t_receiver.start()
                
                # Khởi chạy luồng đồng bộ Clipboard File cho Host
                if clipboard_sync_manager and not _is_legacy_windows_host():
                    clipboard_sync_manager.add_socket(conn)
                
                try:
                    t_receiver.join()
                finally:
                    client_state["running"] = False
                    t_sender.join()
                    if clipboard_sync_manager:
                        clipboard_sync_manager.remove_socket(conn)
                    if not _is_legacy_windows_host():
                        set_windows_graphics_effects(True)
                    
                    print(f"[Host] Đã đóng kết nối với Client {addr[0]}:{addr[1]}.")
                    try: log_activity(_("Ngắt kết nối với ID {id} ({comp})").format(id=fmt_client_id, comp=client_comp))
                    except: pass
                    
                    if addr in self.active_clients:
                        del self.active_clients[addr]
                        
                    if self.active_clients:
                        addrs_str = ", ".join([str(a[0]) for a in self.active_clients.keys()])
                        self.update_status(_("Đang bị điều khiển bởi {addrs}").format(addrs=addrs_str))
                    else:
                        self.update_status(_("Đã đóng kết nối với Client {client} lúc {time} (Sẵn sàng kết nối)").format(client=addr[0], time=time.strftime('%H:%M:%S')))
                        self.after(0, self.hide_host_connection_border)
                        
                    try:
                        force_close_socket(conn)
                    except:
                        pass
            else:
                print("[Host] Password mismatch!")
                err_info = json.dumps({
                    "status": "error",
                    "message": _("Sai mật khẩu kết nối!")
                }).encode('utf-8')
                send_msg(conn, err_info, client_pass)
                time.sleep(0.5)
                force_close_socket(conn)
                socket_passwords.pop(conn, None)
        except Exception as e:
            import traceback
            print(f"[Host] Handshake Exception: {e}\n{traceback.format_exc()}")
            try:
                err_info = json.dumps({
                    "status": "error",
                    "message": _("Lỗi xảy ra trên máy Host:\n") + str(e)
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
        
        class MultiCapCtx:
            def __init__(self):
                self.dx_cams = []
                self.sct = None
            def __enter__(self):
                if _is_legacy_windows_host() or _is_server_or_remote_session():
                    print("[Host] Using GDI/MSS BitBlt capture (Windows 7 / Windows Server / Remote Session)")
                    attach_disconnected_session_to_console()
                    try:
                        self.sct = mss.mss()
                        self.sct.__enter__()
                    except Exception as e:
                        print(f"[Host] mss init for legacy host fallback to GDI: {e}")
                        self.sct = None
                    return self
                if _should_capture_logon_ui():
                    print("[Host] Winlogon/Signing out: PrintWindow/BitBlt HWND (skip DXGI)")
                    return self
                if sys.platform == "win32":
                    self.dx_cams = _open_dxcam_outputs()
                try:
                    self.sct = mss.mss()
                    self.sct.__enter__()
                except Exception as e:
                    print(f"[Host] mss init failed: {e}")
                    self.sct = None
                if not self.dx_cams and not self.sct:
                    print("[Host] DXGI and MSS unavailable (Server/RDP/headless). Using GDI BitBlt capture.")
                    attach_disconnected_session_to_console()
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                for cam in self.dx_cams:
                    try:
                        cam.release()
                    except Exception:
                        pass
                self.dx_cams = []
                try:
                    import dxcam
                    fac = dxcam.DXFactory()
                    if hasattr(fac, "_camera_instances"):
                        fac._camera_instances.clear()
                except Exception:
                    pass
                if self.sct:
                    try:
                        self.sct.__exit__(exc_type, exc_val, exc_tb)
                    except Exception:
                        pass
                    self.sct = None

        
        if not _is_legacy_windows_host():
            try:
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, 30000)
            except: pass
        try:
            client_state["is_lan"] = is_lan_socket(conn)
        except Exception:
            client_state["is_lan"] = False
        try:
            send_msg(conn, json.dumps({"type": "pong"}).encode("utf-8"), password)
        except Exception:
            pass

        _legacy_host = _is_legacy_windows_host()
        _last_hb = time.time()
        _last_switching_signal_time = 0
        _last_lock_sync = 0
        _last_sent_locked = None

        def _host_cursor_watcher():
            last_sent_pos = None
            last_visible = True
            last_desk_attach = 0.0
            while client_state.get("running", False):
                try:
                    now_m = time.monotonic() if hasattr(time, "monotonic") else time.time()
                    if sys.platform == "win32" and (now_m - last_desk_attach >= 0.4):
                        last_desk_attach = now_m
                        try:
                            attach_thread_for_remote_input()
                        except Exception:
                            pass
                    pos = _get_host_cursor_pos()
                    if pos is not None and pos != last_sent_pos:
                        cx, cy = pos
                        inj = client_state.get("last_injected_cursor")
                        last_c_ts = client_state.get("last_client_mouse_ts", 0.0)
                        is_client_echo = (
                            (inj is not None and abs(cx - inj[0]) <= 4 and abs(cy - inj[1]) <= 4)
                            or (now_m - last_c_ts < 0.12)
                        )
                        if is_client_echo:
                            last_sent_pos = pos
                        else:
                            cap_rect = client_state.get("cap_rect")
                            if cap_rect and cap_rect[2] > 1 and cap_rect[3] > 1:
                                ox, oy, cw, ch = cap_rect
                                inside = (ox <= cx < ox + cw) and (oy <= cy < oy + ch)
                                if not inside:
                                    last_sent_pos = pos
                                    if last_visible:
                                        pkt = json.dumps({"type": "host_cursor", "visible": False}).encode("utf-8")
                                        if send_msg(conn, pkt, password, lock_timeout=0.015):
                                            last_visible = False
                                else:
                                    rx = max(0.0, min(1.0, (cx - ox) / float(cw - 1)))
                                    ry = max(0.0, min(1.0, (cy - oy) / float(ch - 1)))
                                    pkt = json.dumps({
                                        "type": "host_cursor",
                                        "rx": round(rx, 5),
                                        "ry": round(ry, 5),
                                        "visible": True,
                                    }).encode("utf-8")
                                    if send_msg(conn, pkt, password, lock_timeout=0.015):
                                        last_sent_pos = pos
                                        last_visible = True
                except Exception:
                    pass
                time.sleep(0.025)

        threading.Thread(target=_host_cursor_watcher, name="HostCursorWatcher", daemon=True).start()

        def _sync_lock_status():
            nonlocal _last_lock_sync, _last_sent_locked
            try:
                if uac_consent_running():
                    locked_now = False
                else:
                    locked_now = (
                        (get_input_desktop_name() or "default") not in ("default", "", "agprivacydesk")
                        or _logonui_running()
                        or _session_has_interactive_user() is False
                    )
                now_l = time.time()
                if locked_now != _last_sent_locked or (locked_now and now_l - _last_lock_sync >= 8):
                    send_msg(conn, json.dumps({
                        "type": "domain_status",
                        "is_locked": locked_now,
                        "reason": "winlogon" if locked_now else "desktop",
                    }).encode("utf-8"), password)
                    _last_sent_locked = locked_now
                    _last_lock_sync = now_l
            except Exception:
                pass

        while client_state.get("running", False):
            try:
                if time.time() - _last_hb >= 2.5:
                    try:
                        send_msg(conn, json.dumps({"type": "pong"}).encode("utf-8"), password)
                        _last_hb = time.time()
                    except Exception:
                        pass
                try:
                    self._sync_privacy_with_uac()
                except Exception:
                    pass
                # Early check for desktop status
                needs_switch, is_blocked = check_desktop_change()
                # Hộp UAC Yes/No: không đứng capture (switching_desktop) — vẫn GDI + SendInput.
                if uac_consent_running():
                    is_blocked = False
                    try:
                        attach_thread_for_remote_input()
                    except Exception:
                        pass
                # Sign-out / logon: ghim Winlogon khi UI khóa; khi đã vào Default thì phải rời ra.
                if _should_capture_logon_ui():
                    if get_desktop_name() != "winlogon":
                        _pin_capture_to_winlogon_if_needed()
                    is_blocked = False
                    needs_switch = False
                elif uac_consent_running():
                    is_blocked = False
                    needs_switch = False
                elif get_desktop_name() == "winlogon":
                    print("[Host] User desktop ready. Leaving Winlogon capture for Default.")
                    if not _switch_capture_thread_to_input_desktop():
                        _switch_capture_thread_to_named_desktop("Default")
                    is_blocked = False
                    needs_switch = False
                    client_state["force_update"] = True
                    client_state.pop("prev_sent_img", None)
                if is_blocked:
                    # Throttle: only send switching_desktop signal once every 12 seconds
                    # to avoid resetting the client's countdown timer in an infinite loop
                    now = time.time()
                    if now - _last_switching_signal_time >= 12:
                        print("[Host] Secure Desktop detected and cannot be accessed. Signaling client...")
                        try:
                            if not send_msg(conn, _encode_switching_desktop(), password):
                                client_state["running"] = False
                                break
                        except:
                            client_state["running"] = False
                            break
                        _last_switching_signal_time = now
                    _sync_lock_status()
                    time.sleep(0.5)
                    continue

                # Switch thread to active Input Desktop if needed
                if needs_switch:
                    _last_switching_signal_time = 0  # Reset throttle so next block event signals immediately
                    print("[Host] Desktop change detected. Switching thread desktop...")
                    if not _switch_capture_thread_to_input_desktop():
                        time.sleep(0.3)
                        continue
                    
                with MultiCapCtx() as cap_ctx:
                    dx_cams = cap_ctx.dx_cams
                    sct = cap_ctx.sct
                    
                    last_vw, last_vh = 0, 0
                    try:
                        last_vw = ctypes.windll.user32.GetSystemMetrics(78)
                        last_vh = ctypes.windll.user32.GetSystemMetrics(79)
                    except Exception:
                        pass

                    last_remote_session = None
                    try:
                        if sys.platform == "win32":
                            last_remote_session = bool(ctypes.windll.user32.GetSystemMetrics(4096))
                    except Exception:
                        pass
                        
                    while client_state.get("running", False):
                        try:
                            if client_state.get("_got_frame"):
                                if getattr(self, "_remote_disconnect_requested", False):
                                    self._remote_disconnect_requested = False
                                    print("[Host] Nhan tin hieu remote_disconnect: reset capture sang console desktop...")
                                    client_state["force_update"] = True
                                    client_state.pop("prev_sent_img", None)
                                    time.sleep(0.3)
                                    break

                                try:
                                    if sys.platform == "win32":
                                        cur_remote = bool(ctypes.windll.user32.GetSystemMetrics(4096))
                                        if last_remote_session is not None and cur_remote != last_remote_session:
                                            print(f"[Host] SM_REMOTESESSION thay doi ({last_remote_session} -> {cur_remote}). Reset capture sang console...")
                                            last_remote_session = cur_remote
                                            client_state["force_update"] = True
                                            client_state.pop("prev_sent_img", None)
                                            time.sleep(0.3)
                                            break
                                        last_remote_session = cur_remote
                                except Exception:
                                    pass
                            else:
                                self._remote_disconnect_requested = False
                                try:
                                    if sys.platform == "win32":
                                        last_remote_session = bool(ctypes.windll.user32.GetSystemMetrics(4096))
                                except Exception:
                                    pass
                            if not client_state.get("_got_frame"):
                                _now_w = time.time()
                                if _now_w - client_state.get("_last_wake_ts", 0) >= 1.0:
                                    client_state["_last_wake_ts"] = _now_w
                                    self.wake_display()
                            if time.time() - _last_hb >= 2.0:
                                try:
                                    if not send_msg(conn, json.dumps({"type": "pong"}).encode("utf-8"), password):
                                        client_state["running"] = False
                                        break
                                    _last_hb = time.time()
                                except Exception:
                                    client_state["running"] = False
                                    break
                                _sync_lock_status()
                            want_logon = _should_capture_logon_ui()
                            thread_desk = get_desktop_name()
                            if want_logon:
                                # PrintWindow ngay frame này. Không break DXGI trước — teardown
                                # DXGI mất trăm ms và nuốt man Signing out.
                                client_state["_secure_frames"] = client_state.get("_secure_frames", 0) + 1
                                if dx_cams and client_state["_secure_frames"] > 8:
                                    print("[Host] Signing out/logon: drop DXGI after Winlogon frames.")
                                    break
                                elif _legacy_host and thread_desk != "winlogon":
                                    really_logon = _logonui_running() or (_wts_phase() in ("logoff", "lock")) or (_session_has_interactive_user() is False) or (not _explorer_running())
                                    if really_logon:
                                        print("[Host] Windows 7 Logon/Logoff detected. Breaking capture to switch to Winlogon...")
                                        break
                            else:
                                client_state["_secure_frames"] = 0
                            if (not want_logon) and thread_desk == "winlogon":
                                print("[Host] Explorer/Default ready. Dropping Winlogon capture to show desktop.")
                                client_state["force_update"] = True
                                client_state.pop("prev_sent_img", None)
                                break
                            if not want_logon and not uac_consent_running():
                                inner_needs_switch, inner_is_blocked = check_desktop_change()
                                if inner_is_blocked or inner_needs_switch:
                                    if inner_is_blocked:
                                        print("[Host] Secure Desktop mid-session: recreate capture after desktop switch...")
                                    else:
                                        print("[Host] Desktop switched mid-session. Breaking capture loop to switch thread...")
                                    break
                                
                            sys_w, sys_h = 0, 0
                            try:
                                if sys.platform == "win32":
                                    sys_w = ctypes.windll.user32.GetSystemMetrics(78)
                                    sys_h = ctypes.windll.user32.GetSystemMetrics(79)
                            except Exception:
                                pass
                                
                            if sys_w > 0 and sys_h > 0 and last_vw > 0 and last_vh > 0 and (sys_w != last_vw or sys_h != last_vh):
                                print("[Host] Virtual screen size changed. Breaking capture loop...")
                                break
                            if sys_w > 0 and sys_h > 0:
                                last_vw, last_vh = sys_w, sys_h

                            mon_mode = client_state.get("monitor_mode", "both")
                            grabbed = False
                            on_winlogon = _should_capture_logon_ui()
                            on_uac = uac_consent_running()
                            if on_uac:
                                try:
                                    frame_bgr, cap_w, cap_h, origin = grab_uac_dialog_bgr()
                                    self._capture_origin = origin
                                    grabbed = bool(
                                        frame_bgr is not None
                                        and getattr(frame_bgr, "size", 0)
                                        and not _frame_is_nearly_black(frame_bgr)
                                    )
                                except Exception:
                                    grabbed = False
                            elif _legacy_host or _is_server_or_remote_session() or on_winlogon or (not dx_cams and sct is None):
                                if on_winlogon:
                                    try:
                                        frame_bgr, cap_w, cap_h, origin = grab_secure_desktop_bgr()
                                        self._capture_origin = origin
                                        grabbed = bool(frame_bgr is not None and getattr(frame_bgr, "size", 0))
                                    except Exception:
                                        grabbed = False
                                else:
                                    try:
                                        frame_bgr, cap_w, cap_h, origin = grab_gdi_monitor_bgr(mon_mode)
                                        self._capture_origin = origin
                                        grabbed = bool(frame_bgr is not None and getattr(frame_bgr, "size", 0))
                                        if grabbed and (_frame_is_nearly_white(frame_bgr) or _frame_is_nearly_black(frame_bgr)):
                                            attach_disconnected_session_to_console()
                                            frame_bgr, cap_w, cap_h, origin = grab_gdi_monitor_bgr(mon_mode)
                                            self._capture_origin = origin
                                            grabbed = bool(frame_bgr is not None and getattr(frame_bgr, "size", 0))
                                    except Exception as ge:
                                        grabbed = False
                                if on_winlogon and grabbed:
                                    _now_diag = time.time()
                                    if _now_diag - client_state.get("_secure_diag_ts", 0) >= 0.8:
                                        client_state["_secure_diag_ts"] = _now_diag
                                        try:
                                            _mean = float(np.mean(frame_bgr))
                                        except Exception:
                                            _mean = -1.0
                                        print(
                                             f"[SecureCap] phase={_wts_phase()} thread_desk={get_desktop_name()} "
                                             f"input={_input_desktop_name()} secure_ui={len(_winlogon_secure_ui_hwnds())} "
                                             f"logonui={_logonui_running()} explorer={_explorer_running()} "
                                             f"mean={_mean:.1f} size={cap_w}x{cap_h}"
                                         )
                            if not dx_cams and not _legacy_host and not _is_server_or_remote_session() and not on_winlogon and sys.platform == "win32":
                                now_dxcam = time.time()
                                if now_dxcam - client_state.get("_last_dxcam_retry", 0) >= 5.0:
                                    client_state["_last_dxcam_retry"] = now_dxcam
                                    try:
                                        new_cams = _open_dxcam_outputs()
                                        if new_cams:
                                            dx_cams = new_cams
                                            cap_ctx.dx_cams = new_cams
                                            client_state["_dxcam_fail_streak"] = 0
                                            print("[Host] DXCam da phuc hoi va gan lai thanh cong.")
                                    except Exception:
                                        pass
                            if dx_cams and not grabbed:
                                retries = 8 if not client_state.get("_got_frame") else 1
                                for _try in range(retries):
                                    frame_bgr, cap_w, cap_h, origin, grabbed = grab_dxcam_virtual_bgr(
                                        dx_cams, client_state.get("_stitch_canvas"), monitor_mode=mon_mode
                                    )
                                    if grabbed and mon_mode == "both":
                                        client_state["_stitch_canvas"] = frame_bgr
                                    self._capture_origin = origin
                                    if grabbed:
                                        break
                                    time.sleep(0.01)
                                if grabbed and client_state.get("_got_frame") and _frame_is_nearly_black(frame_bgr):
                                    grabbed = False
                                elif grabbed and on_uac and _frame_is_nearly_white(frame_bgr):
                                    grabbed = False
                                if grabbed:
                                    client_state["_dxcam_fail_streak"] = 0
                                elif mon_mode == "both":
                                    streak = client_state.get("_dxcam_fail_streak", 0) + 1
                                    client_state["_dxcam_fail_streak"] = streak
                                    if streak >= 3:
                                        print("[Host] DXCam khong bat duoc hinh (man hinh ngu/khoa). Chuyen sang MSS/GDI fallback.")
                                        for c in dx_cams:
                                            try: c.release()
                                            except Exception: pass
                                        dx_cams = []
                                        cap_ctx.dx_cams = []
                            if not grabbed:
                                if on_uac:
                                    frame_bgr, cap_w, cap_h, origin = grab_uac_dialog_bgr()
                                    self._capture_origin = origin
                                    grabbed = bool(frame_bgr is not None and getattr(frame_bgr, "size", 0))
                                elif on_winlogon:
                                    try:
                                        frame_bgr, cap_w, cap_h, origin = grab_secure_desktop_bgr()
                                        self._capture_origin = origin
                                        grabbed = bool(frame_bgr is not None and getattr(frame_bgr, "size", 0))
                                    except Exception:
                                        grabbed = False
                                else:
                                    # Fallback 1: MSS
                                    fb_ok = False
                                    if sct is not None:
                                        try:
                                            frame_bgr, cap_w, cap_h, origin = grab_virtual_desktop_bgr(
                                                sct, client_state.get("_stitch_canvas"), monitor_mode=mon_mode
                                            )
                                            if mon_mode == "both":
                                                client_state["_stitch_canvas"] = frame_bgr
                                            self._capture_origin = origin
                                            fb_ok = bool(
                                                frame_bgr is not None 
                                                and getattr(frame_bgr, "size", 0)
                                                and not _frame_is_nearly_white(frame_bgr)
                                                and not (client_state.get("_got_frame") and _frame_is_nearly_black(frame_bgr))
                                            )
                                            if fb_ok:
                                                grabbed = True
                                        except Exception:
                                            pass
                                    # Fallback 2: GDI (luôn hoạt động ổn định trên Windows Server / sau khi ngắt RDP)
                                    if not fb_ok:
                                        try:
                                            frame_bgr, cap_w, cap_h, origin = grab_gdi_monitor_bgr(mon_mode)
                                            self._capture_origin = origin
                                            grabbed = bool(frame_bgr is not None and getattr(frame_bgr, "size", 0))
                                            if grabbed and (_frame_is_nearly_white(frame_bgr) or _frame_is_nearly_black(frame_bgr)):
                                                attach_disconnected_session_to_console()
                                                frame_bgr, cap_w, cap_h, origin = grab_gdi_monitor_bgr(mon_mode)
                                                self._capture_origin = origin
                                                grabbed = bool(frame_bgr is not None and getattr(frame_bgr, "size", 0))
                                        except Exception as e:
                                            print(f"[Host] GDI grab fallback failed: {e}")

                            if not grabbed or frame_bgr is None or getattr(frame_bgr, "size", 0) == 0:
                                fail_streak = client_state.get("_grab_fail_streak", 0) + 1
                                client_state["_grab_fail_streak"] = fail_streak
                                # Phục hồi session console khi WTSDisconnected (kể cả trước hay sau khi đã có frame)
                                if fail_streak >= 6:
                                    is_disconnected = False
                                    try:
                                        import win32ts
                                        c_state = win32ts.WTSQuerySessionInformation(win32ts.WTS_CURRENT_SERVER_HANDLE, win32ts.WTS_CURRENT_SESSION, win32ts.WTSConnectState)
                                        if c_state == win32ts.WTSDisconnected:
                                            is_disconnected = True
                                    except Exception:
                                        pass
                                    if is_disconnected:
                                        print(f"[Host] Session WTSDisconnected ({fail_streak} lần thử). Reset capture sang console...")
                                        client_state["_grab_fail_streak"] = 0
                                        attach_disconnected_session_to_console()
                                        client_state["force_update"] = True
                                        client_state.pop("prev_sent_img", None)
                                        time.sleep(0.3)
                                        break
                                    elif fail_streak >= 15 and not client_state.get("_got_frame"):
                                        print(f"[Host] Chưa có frame sau {fail_streak} lần thử. Gọi khôi phục console desktop...")
                                        client_state["_grab_fail_streak"] = 0
                                        attach_disconnected_session_to_console()
                                        if hasattr(self, "wake_display"):
                                            self.wake_display()
                                        time.sleep(0.3)
                                        break
                                time.sleep(0.05)
                                continue
                            else:
                                client_state["_grab_fail_streak"] = 0
                                orig_xy = origin if (origin and len(origin) >= 2) else (0, 0)
                                client_state["cap_rect"] = (int(orig_xy[0]), int(orig_xy[1]), int(cap_w), int(cap_h))

                            now_mon_chk = time.time()
                            if now_mon_chk - client_state.get("_last_mon_info_chk", 0) >= 2.0:
                                client_state["_last_mon_info_chk"] = now_mon_chk
                                try:
                                    mon_rects = _get_physical_monitor_rects(sct, dx_cams)
                                    if mon_mode == "both" and len(mon_rects) > 1 and cap_w > 0 and cap_h > 0:
                                        matched_single = [r for r in mon_rects if r[2] == int(cap_w) and r[3] == int(cap_h)]
                                        if len(matched_single) == 1:
                                            mon_rects = matched_single
                                    if _active_monitor_rects_last:
                                        mon_cnt = max(1, len(mon_rects))
                                    else:
                                        sm_cnt = 1
                                        if sys.platform == "win32" and len(mon_rects) > 1:
                                            try:
                                                sm_cnt = max(1, int(ctypes.windll.user32.GetSystemMetrics(80)))
                                            except Exception:
                                                sm_cnt = 1
                                        mon_cnt = max(1, len(mon_rects), sm_cnt) if len(mon_rects) > 1 else 1
                                    if mon_cnt != client_state.get("_last_sent_mon_count") or mon_rects != client_state.get("_last_sent_mon_rects"):
                                        client_state["_last_sent_mon_count"] = mon_cnt
                                        client_state["_last_sent_mon_rects"] = mon_rects
                                        send_msg(conn, json.dumps({
                                            "type": "monitor_info",
                                            "count": mon_cnt,
                                            "monitors": [{"left": r[0], "top": r[1], "width": r[2], "height": r[3]} for r in mon_rects],
                                        }).encode("utf-8"), password)
                                        if mon_cnt < 2 and client_state.get("monitor_mode", "both") != "both":
                                            client_state["monitor_mode"] = "both"
                                            client_state["force_update"] = True
                                            client_state.pop("prev_sent_img", None)
                                except Exception:
                                    pass

                            if (
                                not on_winlogon
                                and (get_desktop_name() or "default") in ("default", "")
                                and _explorer_running()
                                and not _logonui_running()
                                and not _winlogon_has_logonui_windows()
                            ):
                                _user_desktop_was_shown(True)
                            
                            target_w = getattr(self, 'client_viewer_w', 1280)
                            target_h = getattr(self, 'client_viewer_h', 720)
                            
                            force_update = client_state.pop("force_update", False)
                            if on_winlogon or on_uac:
                                force_update = True
                            if not client_state.get("_first_sent"):
                                force_update = True
                            if client_state.get("last_target_w") != target_w or client_state.get("last_target_h") != target_h:
                                force_update = True
                                client_state["last_target_w"] = target_w
                                client_state["last_target_h"] = target_h

                            net_class = client_state.get("net_class", "medium")
                            q_mode = getattr(self, 'client_quality_mode', 'quality')

                            if _legacy_host:
                                # Win7/GDI: CPU yếu hơn nên FPS thấp hơn, luôn ưu tiên chữ nét (-1.0)
                                if q_mode == "quality" or net_class in ("high", "medium"):
                                    base_quality = 90
                                    fps_limit = 15
                                    res_scale = -1.0
                                elif net_class == "low":
                                    base_quality = 75
                                    fps_limit = 10
                                    res_scale = -1.0
                                else:
                                    base_quality = 88
                                    fps_limit = 12
                                    res_scale = -1.0
                            elif q_mode == "quality":
                                base_quality = 96
                                fps_limit = 30
                                res_scale = -1.0
                            elif net_class == "high":
                                base_quality = 98
                                fps_limit = 60
                                res_scale = -1.0
                            elif net_class == "low":
                                base_quality = 75
                                fps_limit = 15
                                res_scale = -1.0
                            else:
                                # Windows 10 / 11 mặc định: Giữ độ phân giải gốc (-1.0) và chất lượng 90 để chữ nét đẹp như Win 7
                                base_quality = 90
                                fps_limit = 30
                                res_scale = -1.0

                            quality = client_state.get("dyn_quality", base_quality)
                            sleep_time = client_state.get("dyn_sleep_time", 1.0 / fps_limit)
                            dyn_scale = client_state.get("dyn_scale", res_scale)

                            if "start_time" not in client_state:
                                client_state["start_time"] = time.time()
                                
                            if time.time() - client_state["start_time"] < 5.0 and cap_w * cap_h <= (1920 * 1200):
                                # 5s đầu: ưu tiên nét (cả Win7) để UI/chữ đọc được ngay.
                                boost = 6 if _legacy_host else 10
                                quality = min(98 if not _legacy_host else 92, quality + boost)
                                if dyn_scale >= 0:
                                    dyn_scale = min(1.0, dyn_scale + 0.1)
                                client_state["dyn_quality"] = quality
                                client_state["dyn_scale"] = dyn_scale

                            if client_state.get("last_cap_w") != cap_w or client_state.get("last_cap_h") != cap_h:
                                client_state["last_cap_w"] = cap_w
                                client_state["last_cap_h"] = cap_h
                                force_update = True
                                cur_mon_cnt = int(client_state.get("_last_sent_mon_count") or (len(_active_monitor_rects_last) if _active_monitor_rects_last else 1))
                                cur_mon_rects = client_state.get("_last_sent_mon_rects") or list(_active_monitor_rects_last or [])
                                cur_mon_dicts = [{"left": r[0], "top": r[1], "width": r[2], "height": r[3]} for r in cur_mon_rects]
                                if mon_mode == "both":
                                    ctrl_sock = getattr(self, "_broker_ctrl_sock", None)
                                    if ctrl_sock is not None:
                                        try:
                                            ctrl_sock.sendall((json.dumps({
                                                "width": int(cap_w),
                                                "height": int(cap_h),
                                                "monitor_count": max(1, cur_mon_cnt),
                                                "monitors": cur_mon_dicts,
                                            }) + "\n").encode("utf-8"))
                                        except Exception:
                                            pass
                                try:
                                    res_meta = {
                                        "type": "resolution_change",
                                        "w": cap_w,
                                        "h": cap_h,
                                        "monitor_count": max(1, cur_mon_cnt),
                                        "monitors": cur_mon_dicts,
                                    }
                                    if not send_msg(conn, json.dumps(res_meta).encode('utf-8'), password):
                                        client_state["running"] = False
                                        break
                                except Exception:
                                    client_state["running"] = False
                                    break

                            # dyn_scale < 0 = gửi gần độ phân giải gốc (không thu về kích thước cửa sổ viewer)
                            send_max_edge = _MAX_SEND_EDGE_LEGACY if _legacy_host else (
                                _MAX_SEND_EDGE_LAN if client_state.get("is_lan") or net_class == "high" else _MAX_SEND_EDGE_WAN
                            )
                            if dyn_scale >= 0:
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
                                    frame_bgr = cv2.resize(frame_bgr, (final_w, final_h), interpolation=cv2.INTER_AREA)
                            frame_bgr = scale_frame_for_send(frame_bgr, frame_bgr.shape[1], frame_bgr.shape[0], send_max_edge)

                            static_frame = False
                            diff_bbox = None
                            try:
                                if "prev_sent_img" in client_state and not force_update:
                                    prev_img = client_state["prev_sent_img"]
                                    if prev_img.shape == frame_bgr.shape:
                                        diff = cv2.absdiff(frame_bgr, prev_img)
                                        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
                                        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY)
                                        x, y, w_box, h_box = cv2.boundingRect(thresh)
                                        if w_box == 0 or h_box == 0:
                                            static_frame = True
                                        else:
                                            diff_bbox = (x, y, x + w_box, y + h_box)
                            except: pass
                            
                            if not static_frame:
                                client_state["prev_sent_img"] = frame_bgr.copy()
                            
                            if static_frame:
                                current_q = client_state.get("dyn_quality", 40)
                                current_s = client_state.get("dyn_scale", 0.6)
                                target_scale = -1.0  # Luôn phục hồi về độ phân giải gốc khi màn hình tĩnh để chữ nét tuyệt đối
                                if current_q < 98 or (current_s >= 0 and current_s < target_scale) or (current_s >= 0 and target_scale < 0):
                                    client_state["dyn_quality"] = min(98, current_q + 15)
                                    if target_scale < 0:
                                        client_state["dyn_scale"] = -1.0  # Phục hồi về full resolution
                                    else:
                                        client_state["dyn_scale"] = min(target_scale, current_s + 0.1)
                                    static_frame = False 
                                else:
                                    wait_s = 0.08 if _user_desktop_was_shown() else 1.0
                                    if "wake_event" in client_state:
                                        client_state["wake_event"].wait(wait_s)
                                        client_state["wake_event"].clear()
                                    else:
                                        time.sleep(wait_s)
                                    continue
                                    
                            if diff_bbox is not None and not static_frame and not force_update:
                                box_w = diff_bbox[2] - diff_bbox[0]
                                box_h = diff_bbox[3] - diff_bbox[1]
                                frame_h_cur, frame_w_cur = frame_bgr.shape[:2]
                                if box_w * box_h < (frame_w_cur * frame_h_cur) * 0.7:
                                    frame_bgr = frame_bgr[diff_bbox[1]:diff_bbox[3], diff_bbox[0]:diff_bbox[2]]
                                    partial_meta = {"type": "partial_frame", "bbox": diff_bbox}
                                    if not send_msg(conn, json.dumps(partial_meta).encode('utf-8'), password):
                                        client_state["running"] = False
                                        break
                            
                            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
                            if (not _legacy_host) and hasattr(cv2, "IMWRITE_JPEG_OPTIMIZE"):
                                encode_param.extend([int(cv2.IMWRITE_JPEG_OPTIMIZE), 1])
                            # 4:4:4 giữ sắc độ chữ và icon (cả Win 7, Win 10, Win 11), tránh lem màu/vỡ viền
                            _jpeg_444_min = 75
                            if quality >= _jpeg_444_min and hasattr(cv2, "IMWRITE_JPEG_SAMPLING_FACTOR") and hasattr(cv2, "IMWRITE_JPEG_SAMPLING_FACTOR_444"):
                                encode_param.extend([int(cv2.IMWRITE_JPEG_SAMPLING_FACTOR), int(cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444)])
                            result, encimg = cv2.imencode('.jpg', frame_bgr, encode_param)
                            if not result:
                                time.sleep(0.05)
                                continue
                            jpeg_data = encimg.tobytes()
                            
                            t_start_send = time.time()
                            if not send_msg(conn, jpeg_data, password):
                                client_state["running"] = False
                                break
                            send_time = time.time() - t_start_send
                            _last_hb = time.time()
                            
                            if "send_ema" not in client_state:
                                client_state["send_ema"] = send_time
                            else:
                                client_state["send_ema"] = 0.8 * client_state["send_ema"] + 0.2 * send_time
                                
                            ema = client_state["send_ema"]
                            
                            if q_mode == "quality":
                                floor_q = 88 if _legacy_host else 94
                                ceil_q = 92 if _legacy_host else 98
                                quality = max(floor_q, min(ceil_q, int(quality)))
                                if ema > 0.45:
                                    sleep_time = min(0.12, sleep_time + 0.02)
                                elif ema < 0.20:
                                    sleep_time = max(1.0 / (15 if _legacy_host else 30), sleep_time - 0.005)
                                dyn_scale = -1.0
                            elif ema > 0.35:
                                # Mạng chậm: Chỉ giảm chất lượng ảnh, không bóp xuống dưới 65 để giữ chữ nét
                                floor_drop = 65
                                quality = max(floor_drop, quality - 5)
                                sleep_time = min(0.3, sleep_time + 0.05)
                                if ema > 0.6 and dyn_scale >= 0:
                                    dyn_scale = max(max(0.5, res_scale if res_scale > 0 else 0.5), dyn_scale - 0.05)
                            elif ema < 0.20:
                                # Mạng tốt: Tăng dần chất lượng và scale
                                quality = min(92 if _legacy_host else 98, quality + 1)
                                sleep_time = max(1.0 / (15 if _legacy_host else 60), sleep_time - 0.005)
                                if res_scale < 0:
                                    dyn_scale = -1.0  # Phục hồi về full resolution mode
                                elif dyn_scale >= 0:
                                    dyn_scale = min(1.0, dyn_scale + 0.02)
                                
                            client_state["dyn_quality"] = quality
                            client_state["dyn_sleep_time"] = sleep_time
                            client_state["dyn_scale"] = dyn_scale

                            if not client_state.get("_first_sent"):
                                client_state["_first_sent"] = True
                                client_state["_got_frame"] = True
                                continue
                            if on_winlogon:
                                sleep_time = min(float(sleep_time), 1.0 / 12.0)
                            time.sleep(sleep_time)
                        except mss.exception.ScreenShotError as e:
                            print(f"[Host] Screen capture error (re-initializing): {e}")
                            time.sleep(0.3)
                            break
                        except Exception as e:
                            import traceback
                            try:
                                with open("host_error.log", "a", encoding="utf-8-sig") as f:
                                    f.write(f"[{time.strftime('%H:%M:%S')}] [Host] Screen Sender Error: {e}\n{traceback.format_exc()}\n")
                            except Exception:
                                pass
                            print(f"[Host] Screen Sender Error (retry): {e}")
                            time.sleep(0.25)
                            break
            except Exception as e:
                print(f"[Host] mss.mss() context error: {e}")
                time.sleep(1.0)
        print("[Host] Screen Sender Thread Stopped.")
        
    # Host Receiver Thread (Simulates actions)
    def host_receiver_thread(self, conn, client_state, password):
        print("[Host] Started Input Receiver Thread.")
        import select
        import queue
        import threading
        
        input_queue = queue.Queue()
        
        def _input_worker():
            print("[Host Input] Dedicated Worker Started")
            while client_state.get("running", False):
                try:
                    event = input_queue.get(timeout=0.5)
                    if event == "STOP":
                        break
                    self.host_handle_event(event, conn, password, client_state=client_state)
                except queue.Empty:
                    pass
                except Exception as e:
                    print(f"[Host Input] Worker error: {e}")
            print("[Host Input] Dedicated Worker Stopped")
            
        worker_thread = threading.Thread(target=_input_worker, daemon=True)
        worker_thread.start()

        last_recv_time = time.time()
        while client_state.get("running", False):
            try:
                # Chờ gói tin; nếu quá 1 giây không có gói thì nhả modifier để chống kẹt phím
                r, _, _ = select.select([conn], [], [], 1.0)
                if not r:
                    self.host_release_all_modifiers()
                    if time.time() - last_recv_time > 60.0:
                        print("[Host] Connection ping timeout. Disconnecting client.")
                        client_state["running"] = False
                        break
                    continue

                try:
                    self._sync_privacy_with_uac()
                except Exception:
                    pass
                if getattr(self, 'head_screen_cover_active', False) and not uac_consent_running():
                    try:
                        if not self._apply_block_input(True):
                            self._apply_block_input(False)
                            self._apply_block_input(True)
                    except Exception:
                        pass
                    
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
                    if evt_type in CLIPBOARD_PKT_TYPES:
                        if clipboard_sync_manager:
                            clipboard_sync_manager.enqueue_packet(event)
                    else:
                        input_queue.put(event)
                        if evt_type in ("mouse_click", "mouse_scroll", "key_event", "set_monitors"):
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
        input_queue.put("STOP")
        self.host_release_all_modifiers()
        print("[Host] Client disconnected, forcing screen cover to disable.")
        self.disable_screen_cover()
        
    def _resolve_client_mouse_target(self, event, client_state=None):
        cap_rect = client_state.get("cap_rect") if isinstance(client_state, dict) else None
        rx = event.get("rx")
        ry = event.get("ry")
        if cap_rect and len(cap_rect) == 4 and rx is not None and ry is not None:
            ox, oy, cw, ch = cap_rect
            rx_clamped = max(0.0, min(1.0, float(rx)))
            ry_clamped = max(0.0, min(1.0, float(ry)))
            tx = int(round(ox + rx_clamped * max(1, cw - 1)))
            ty = int(round(oy + ry_clamped * max(1, ch - 1)))
            return tx, ty
        x, y = event.get("x"), event.get("y")
        if x is None or y is None:
            return None, None
        if cap_rect and len(cap_rect) == 4:
            ox, oy = int(cap_rect[0]), int(cap_rect[1])
        else:
            ox, oy = getattr(self, "_capture_origin", (0, 0))
        return int(x) + int(ox), int(y) + int(oy)

    def host_handle_event(self, event, conn, password, client_state=None):
        ev_type = event.get('type')
        if ev_type == 'mouse_move':
            self.ensure_input_thread_desktop(force=False)
            tx, ty = self._resolve_client_mouse_target(event, client_state=client_state)
            if tx is not None and ty is not None:
                if isinstance(client_state, dict):
                    client_state["last_injected_cursor"] = (tx, ty)
                    client_state["last_client_mouse_ts"] = time.monotonic()
                send_input_mouse_move(tx, ty)
                
        elif ev_type == 'mouse_click':
            self.ensure_input_thread_desktop(force=True)
            button_name = event.get('button')
            pressed = event.get('pressed')
            tx, ty = self._resolve_client_mouse_target(event, client_state=client_state)
            if tx is not None and ty is not None:
                if isinstance(client_state, dict):
                    client_state["last_injected_cursor"] = (tx, ty)
                    client_state["last_client_mouse_ts"] = time.monotonic()
                send_input_mouse_click_at(tx, ty, button_name, pressed)
            else:
                send_input_mouse_click(button_name, pressed)
            try:
                if pressed and clipboard_sync_manager:
                    if button_name == 'right':
                        clipboard_sync_manager.last_rbutton_time = time.time()
                    elif button_name == 'left':
                        clipboard_sync_manager.last_lbutton_time = time.time()
            except Exception as e:
                pass

        elif ev_type == 'set_monitors':
            left_on = bool(event.get('left', True))
            right_on = bool(event.get('right', True))
            # Bắt buộc giữ ít nhất 1 màn hình bật (không cho tắt cả 2)
            if not left_on and not right_on:
                left_on = True
            if left_on and right_on:
                new_mode = "both"
            elif left_on:
                new_mode = "left"
            else:
                new_mode = "right"
            if isinstance(client_state, dict):
                if client_state.get("monitor_mode", "both") != new_mode:
                    print(f"[Host] Client monitor mode changed to: {new_mode}")
                client_state["monitor_mode"] = new_mode
                client_state.pop("prev_sent_img", None)
                client_state.pop("_stitch_canvas", None)
                client_state["force_update"] = True
                if "wake_event" in client_state:
                    client_state["wake_event"].set()
                
        elif ev_type == 'mouse_scroll':
            self.ensure_input_thread_desktop(force=True)
            dx, dy = event['dx'], event['dy']
            # Primary simulation using standard SendInput API
            send_input_mouse_scroll(dx, dy)
                
        elif ev_type == 'key_event':
            self.ensure_input_thread_desktop(force=True)
            key_name = event['key']
            pressed = event['pressed']
            
            # Primary simulation using standard SendInput API
            send_input_keyboard_event(key_name, pressed)
                
        elif ev_type == 'resize_viewer':
            self.client_viewer_w = event.get('w', 1280)
            self.client_viewer_h = event.get('h', 720)
            
        elif ev_type == 'quality_mode':
            mode = event.get('mode', 'quality')
            self.client_quality_mode = mode
            # Reset dynamic state để áp dụng ngay chế độ mới
            for addr, cs in self.active_clients.items():
                cs.pop('dyn_quality', None)
                cs.pop('dyn_scale', None)
                cs.pop('dyn_sleep_time', None)
                cs.pop('start_time', None)
                cs['force_update'] = True
            print(f"[Host] Client quality mode set to: {mode}")
            
        elif ev_type == 'ping':
            try:
                send_msg(conn, json.dumps({"type": "pong"}).encode('utf-8'), password)
            except Exception:
                pass
            
        elif ev_type == 'toggle_screen_cover':
            self.toggle_screen_cover()
            try:
                send_msg(conn, json.dumps({
                    "type": "screen_cover_state",
                    "active": bool(getattr(self, "head_screen_cover_active", False)),
                }).encode("utf-8"), password)
            except Exception:
                pass
            
        elif ev_type == 'trigger_sas':
            self.trigger_sas()
        elif ev_type == 'trigger_terminal':
            self.trigger_terminal()
            
        elif ev_type == 'trigger_taskmgr':
            self.trigger_taskmgr()
            
        elif ev_type == 'check_domain':
            is_domain = False
            chk_reason = "Unknown"
            try:
                is_domain, chk_reason = is_machine_domain_joined()
            except Exception as ex:
                chk_reason = f"Error: {ex}"
            
            try:
                if uac_consent_running():
                    is_locked = False
                else:
                    is_locked = (get_input_desktop_name() or "default") not in ("default", "", "agprivacydesk")
            except Exception:
                is_locked = (get_desktop_name() or "default") not in ("default", "", "agprivacydesk")
            
            try:
                with open("domain_debug.log", "a", encoding="utf-8-sig") as df:
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
                    try:
                        dir_items = os.listdir(path)
                    except Exception:
                        dir_items = []
                    for item in dir_items:
                        full = os.path.join(path, item)
                        try:
                            is_dir = os.path.isdir(full)
                            size = 0 if is_dir else os.path.getsize(full)
                        except Exception:
                            is_dir = False
                            size = 0
                        items.append({"name": item, "is_dir": is_dir, "size": size})
                res = {"type": "list_dir_result", "path": path, "items": items}
                send_msg(conn, json.dumps(res).encode('utf-8'), password)
            except Exception as e:
                print(f"[Host] list dir error: {e}")
                res = {"type": "list_dir_result", "path": path, "items": []}
                try:
                    send_msg(conn, json.dumps(res).encode('utf-8'), password)
                except Exception:
                    pass
                
        elif ev_type == 'request_file_download':
            path = event.get('path')
            target_dir_local = event.get('target_dir_local')
            if path and os.path.isfile(path):
                def download_thread(p, t_dir, c, pwd):
                    try:
                        import os, base64, time
                        cm = clipboard_sync_manager
                        if cm and getattr(cm, "_fm_send_abort", None) is not None:
                            cm._fm_send_abort.clear()
                        size = os.path.getsize(p)
                        name = os.path.basename(p)
                        
                        start_msg = {"type": "file_start", "name": name, "size": size, "target_dir": t_dir}
                        if not _fm_host_send(c, start_msg, pwd):
                            return
                        time.sleep(0.5)
                        
                        with open(p, "rb") as f:
                            while True:
                                if _fm_host_should_stop():
                                    print("[Host] FM download dung (Huy).")
                                    break
                                chunk = f.read(65536)
                                if not chunk: break
                                chunk_msg = {
                                    "type": "file_chunk",
                                    "name": name,
                                    "data": base64.b64encode(chunk).decode('utf-8')
                                }
                                if not _fm_host_send(c, chunk_msg, pwd):
                                    break
                                
                        if not _fm_host_should_stop():
                            end_msg = {"type": "file_end", "name": name}
                            _fm_host_send(c, end_msg, pwd)
                    except Exception as e:
                        print(f"[Host] File download error: {e}")
                import threading
                threading.Thread(target=download_thread, args=(path, target_dir_local, conn, password), daemon=True).start()

        elif ev_type == 'request_download_batch':
            paths = event.get('paths', [])
            target_dir_local = event.get('target_dir_local')
            
            def download_batch_thread(pts, t_dir, c, pwd):
                try:
                    import os, base64, time
                    cm = clipboard_sync_manager
                    if cm and getattr(cm, "_fm_send_abort", None) is not None:
                        cm._fm_send_abort.clear()
                    all_files = []
                    total_sz = 0
                    
                    for p in pts:
                        if os.path.isfile(p):
                            sz = os.path.getsize(p)
                            all_files.append((p, os.path.basename(p), sz))
                            total_sz += sz
                        elif os.path.isdir(p):
                            for root, dirs, files in os.walk(p):
                                rel_path = os.path.relpath(root, os.path.dirname(p))
                                for f in files:
                                    full_file = os.path.join(root, f)
                                    if os.path.isfile(full_file):
                                        sz = os.path.getsize(full_file)
                                        remote_name = os.path.join(rel_path, f).replace('\\', '/')
                                        all_files.append((full_file, remote_name, sz))
                                        total_sz += sz

                    if not all_files:
                        batch_end_msg = {"type": "batch_end"}
                        _fm_host_send(c, batch_end_msg, pwd)
                        return
                        
                    display_name = all_files[0][1]
                    if len(pts) > 1:
                        display_name += f" và {len(pts)-1} mục khác"
                        
                    batch_start_msg = {"type": "batch_start", "total_size": total_sz, "display_name": display_name}
                    if not _fm_host_send(c, batch_start_msg, pwd):
                        return
                    time.sleep(0.5)
                        
                    for fpath, rname, sz in all_files:
                        if _fm_host_should_stop():
                            print("[Host] FM batch dung (Huy).")
                            break
                        parts = rname.split('/')
                        fname = parts[-1]
                        sub_dir = "/".join(parts[:-1])
                        
                        final_t_dir = t_dir
                        if not final_t_dir.endswith("/"): final_t_dir += "/"
                        if sub_dir:
                            final_t_dir += sub_dir
                            
                        start_msg = {"type": "file_start", "name": fname, "size": sz, "target_dir": final_t_dir}
                        if not _fm_host_send(c, start_msg, pwd):
                            break
                        time.sleep(0.5)
                        
                        with open(fpath, "rb") as f:
                            while True:
                                if _fm_host_should_stop():
                                    break
                                chunk = f.read(65536)
                                if not chunk: break
                                chunk_msg = {
                                    "type": "file_chunk",
                                    "name": fname,
                                    "data": base64.b64encode(chunk).decode('utf-8')
                                }
                                if not _fm_host_send(c, chunk_msg, pwd):
                                    break
                                
                        if _fm_host_should_stop():
                            break
                        end_msg = {"type": "file_end", "name": fname}
                        if not _fm_host_send(c, end_msg, pwd):
                            break
                        time.sleep(0.1)
                        
                    if not _fm_host_should_stop():
                        batch_end_msg = {"type": "batch_end"}
                        _fm_host_send(c, batch_end_msg, pwd)
                        
                except Exception as e:
                    print(f"[Host] Batch download error: {e}")

            import threading
            threading.Thread(target=download_batch_thread, args=(paths, target_dir_local, conn, password), daemon=True).start()

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

        elif ev_type == 'request_get_properties':
            path = event.get('path')
            try:
                import os
                from datetime import datetime
                name = os.path.basename(path.rstrip('/\\'))
                location = os.path.dirname(path)
                is_dir = os.path.isdir(path)
                try:
                    mtime = os.path.getmtime(path)
                    modified_time = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                except:
                    modified_time = ""

                if is_dir:
                    total_size = 0
                    file_count = 0
                    folder_count = 0
                    try:
                        for dirpath, dirnames, filenames in os.walk(path):
                            folder_count += len(dirnames)
                            for f in filenames:
                                file_count += 1
                                try:
                                    total_size += os.path.getsize(os.path.join(dirpath, f))
                                except:
                                    pass
                    except:
                        pass
                    res = {"type": "get_properties_result", "success": True, "name": name,
                           "is_dir": True, "location": location, "size": total_size,
                           "file_count": file_count, "folder_count": folder_count,
                           "modified_time": modified_time}
                else:
                    size = os.path.getsize(path)
                    res = {"type": "get_properties_result", "success": True, "name": name,
                           "is_dir": False, "location": location, "size": size,
                           "modified_time": modified_time}
            except Exception as e:
                res = {"type": "get_properties_result", "success": False, "error": str(e)}
            send_msg(conn, json.dumps(res).encode('utf-8'), password)

    def _apply_block_input(self, active):
        """BlockInput khóa hardware; thường cần quyền. Hook LL là lớp khóa chính khi không admin."""
        if sys.platform != "win32":
            return False
        try:
            user32 = ctypes.windll.user32
            user32.BlockInput.argtypes = [ctypes.c_bool]
            user32.BlockInput.restype = ctypes.c_bool
            ok = bool(user32.BlockInput(bool(active)))
            if not ok:
                err = ctypes.GetLastError()
                print(f"[Host] BlockInput({active}) failed, GetLastError={err}")
            return ok
        except Exception as e:
            print(f"[Host] BlockInput error: {e}")
            return False

    def _run_input_hooks(self):
        import ctypes
        from ctypes import wintypes
        import win32con
        
        user32 = ctypes.windll.user32
        
        # Ensure thread is bound to active desktop
        try:
            hdesk = user32.OpenInputDesktop(0, False, win32con.MAXIMUM_ALLOWED)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
                user32.CloseDesktop(hdesk)
        except Exception as e:
            print(f"[Host] SetThreadDesktop error in input hooks: {e}")
            
        WH_KEYBOARD_LL = 13
        WH_MOUSE_LL = 14
        LLKHF_INJECTED = 0x00000010
        LLKHF_LOWER_IL_INJECTED = 0x00000002
        LLMHF_INJECTED = 0x00000001
        LLMHF_LOWER_IL_INJECTED = 0x00000002
        KB_INJECTED = LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED
        MS_INJECTED = LLMHF_INJECTED | LLMHF_LOWER_IL_INJECTED

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", POINT),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]
        
        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        
        def keyboard_hook_proc(nCode, wParam, lParam):
            try:
                if uac_consent_running():
                    return user32.CallNextHookEx(None, nCode, wParam, lParam)
            except Exception:
                pass
            if nCode >= 0 and lParam:
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if not (kb.flags & KB_INJECTED):
                    return 1
            return user32.CallNextHookEx(None, nCode, wParam, lParam)
            
        def mouse_hook_proc(nCode, wParam, lParam):
            try:
                if uac_consent_running():
                    return user32.CallNextHookEx(None, nCode, wParam, lParam)
            except Exception:
                pass
            if nCode >= 0 and lParam:
                ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if not (ms.flags & MS_INJECTED):
                    return 1
            return user32.CallNextHookEx(None, nCode, wParam, lParam)
            
        self._kb_hook_ref = HOOKPROC(keyboard_hook_proc)
        self._ms_hook_ref = HOOKPROC(mouse_hook_proc)

        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, ctypes.c_uint]
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        
        h_mod = ctypes.windll.kernel32.GetModuleHandleW(None)
        kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_hook_ref, h_mod, 0)
        ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._ms_hook_ref, h_mod, 0)
        if not kb_hook or not ms_hook:
            print(f"[Host] SetWindowsHookEx failed kb={kb_hook} ms={ms_hook} err={ctypes.GetLastError()}")
        else:
            print("[Host] Input hooks installed (physical KB/mouse blocked, remote SendInput allowed).")
        
        def timer_proc(hwnd, msg, timer_id, time):
            if not getattr(self, 'host_block_input_active', False):
                user32.PostQuitMessage(0)
                
        TIMERPROC = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint)
        timer_ref = TIMERPROC(timer_proc)
        self._hook_timer_ref = timer_ref
        timer_id = user32.SetTimer(None, 0, 200, timer_ref)
        
        msg = wintypes.MSG()
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
        user32.GetMessageW.restype = ctypes.c_int
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
            
        user32.KillTimer(None, timer_id)
        if kb_hook:
            user32.UnhookWindowsHookEx(kb_hook)
        if ms_hook:
            user32.UnhookWindowsHookEx(ms_hook)
        self._kb_hook_ref = None
        self._ms_hook_ref = None
        print("[Host] Input hooks stopped.")
        
    def start_input_hooks(self):
        import threading
        if not getattr(self, 'host_block_input_active', False):
            self.host_block_input_active = True
            threading.Thread(target=self._run_input_hooks, daemon=True).start()
            print("[Host] Input hooks (KB/Mouse) Enabled.")
            
    def stop_input_hooks(self):
        self.host_block_input_active = False
        print("[Host] Input hooks (KB/Mouse) Disabled.")

    def _sync_privacy_with_uac(self):
        """UAC Yes/No: BlockInput + hook privacy khóa cứng chuột/phím trên host — phải nhả."""
        try:
            uac = uac_consent_running()
        except Exception:
            uac = False
        paused = getattr(self, "_uac_privacy_paused", False)
        if uac and not paused:
            self._uac_privacy_paused = True
            try:
                self._apply_block_input(False)
            except Exception:
                pass
            try:
                self.stop_input_hooks()
            except Exception:
                pass
            hwnd = getattr(self, "_cover_hwnd", None)
            if hwnd:
                try:
                    import win32gui, win32con
                    win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                except Exception:
                    pass
            print("[Host] UAC prompt: unlocked host mouse/keyboard")
        elif not uac and paused:
            self._uac_privacy_paused = False
            cover_on = bool(
                getattr(self, "head_screen_cover_active", False)
                or getattr(self, "screen_cover_running", False)
            )
            if cover_on:
                try:
                    self._apply_block_input(True)
                except Exception:
                    pass
                if not getattr(self, "is_headless", False):
                    try:
                        self.start_input_hooks()
                    except Exception:
                        pass

    def toggle_screen_cover(self):
        if sys.platform != "win32":
            return
        import win32event, win32api
        
        is_active = not getattr(self, 'head_screen_cover_active', False)
        self.head_screen_cover_active = is_active
        self._apply_block_input(is_active)
        if not getattr(self, "is_headless", False):
            if is_active:
                self.start_input_hooks()
            else:
                self.stop_input_hooks()
            
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

    def disable_screen_cover(self):
        if sys.platform != "win32":
            return
        import win32event, win32api
        
        self.head_screen_cover_active = False
        self._apply_block_input(False)
        if not getattr(self, "is_headless", False):
            self.stop_input_hooks()
            
        try:
            active_session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
        except:
            active_session_id = 1
            
        disable_event_name = f"Global\\AntigravityP2PRemoteDesktopScreenCoverEvent_{active_session_id}_default_disable"
        
        try:
            h_event = win32event.OpenEvent(win32event.EVENT_MODIFY_STATE, False, disable_event_name)
            if h_event:
                win32event.SetEvent(h_event)
                win32api.CloseHandle(h_event)
                print(f"[Host] Signaled ScreenCover Disable Event to GUI Agent at Session {active_session_id}.")
            else:
                if not self.is_headless:
                    self.after(0, self.disable_screen_cover_gui)
        except Exception as e:
            print(f"[Host] Failed to signal ScreenCover Disable Event: {e}")
            if not self.is_headless:
                self.after(0, self.disable_screen_cover_gui)

    def disable_screen_cover_gui(self):
        if hasattr(self, 'screen_cover_running') and self.screen_cover_running:
            self.screen_cover_running = False
            if hasattr(self, '_cover_hwnd') and self._cover_hwnd:
                try:
                    import win32gui, win32con
                    win32gui.PostMessage(self._cover_hwnd, win32con.WM_CLOSE, 0, 0)
                except Exception as e:
                    print(f"[Host] disable_screen_cover_gui error: {e}")
                self._cover_hwnd = None
            self.stop_input_hooks()
            self._apply_block_input(False)
            print("[Host] Screen cover disabled forcefully.")

    def toggle_screen_cover_gui(self):
        if hasattr(self, 'screen_cover_running') and self.screen_cover_running:
            self.screen_cover_running = False
            if hasattr(self, '_cover_hwnd') and self._cover_hwnd:
                try:
                    import win32gui, win32con
                    win32gui.PostMessage(self._cover_hwnd, win32con.WM_CLOSE, 0, 0)
                except Exception as e:
                    print(f"[Host] toggle_screen_cover_gui error: {e}")
                self._cover_hwnd = None
            self.stop_input_hooks()
            self._apply_block_input(False)
            print("[Host] Screen cover disabled.")
            return

        self.screen_cover_running = True
        self.start_input_hooks()
        self._apply_block_input(True)
        print("[Host] Screen cover enabled. Launching Win32 cover thread...")
        import threading
        threading.Thread(target=self._run_cover_win32, daemon=True).start()

    def _create_privacy_cover_hwnd(self, cls_name, ex_style, style, vx, vy, vw, vh, hInst):
        """Tạo cửa sổ che trên ZBID_UIACCESS để đè Start/Taskbar (cần uiAccess + exe ký trong Program Files)."""
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        ZBID_UIACCESS = 2
        hwnd = 0
        try:
            create_in_band = getattr(user32, "CreateWindowInBand")
            create_in_band.restype = ctypes.c_void_p
            create_in_band.argtypes = [
                wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                wintypes.HWND, wintypes.HMENU, ctypes.c_void_p, ctypes.c_void_p,
                wintypes.DWORD,
            ]
            hwnd = create_in_band(
                ex_style, cls_name, "AGCover", style,
                int(vx), int(vy), int(vw), int(vh),
                None, None, ctypes.c_void_p(int(hInst)), None, ZBID_UIACCESS,
            ) or 0
            if hwnd:
                print(f"[Host] Cover CreateWindowInBand(ZBID_UIACCESS) HWND={hex(hwnd)}")
                return int(hwnd)
            print(f"[Host] CreateWindowInBand failed err={ctypes.GetLastError()}")
        except Exception as e:
            print(f"[Host] CreateWindowInBand unavailable: {e}")
        return 0

    def _run_cover_win32(self):
        """Tạo cửa sổ che phủ bằng pywin32 API thuần (không Tkinter).
        Khắc phục hoàn toàn lỗi crash do ctypes 64-bit truncation và lỗi hiển thị trên NVIDIA/AMD."""
        import win32gui, win32con, win32api
        import ctypes
        
        # Bật DPI Awareness cho thread này
        try:
            ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        except:
            pass
        
        # Đo virtual screen
        vx = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        vy = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        vw = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        vh = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        if vw <= 0 or vh <= 0:
            vx, vy, vw, vh = 0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
            
        print(f"[Host] Cover Win32: VirtualScreen={vw}x{vh}+{vx}+{vy}")
        
        self._fade_value = 0
        self._fade_dir = 5
        
        import os, sys
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(sys.executable), "app_icon.ico")
            
        self._cover_hIcon = 0
        try:
            self._cover_hIcon = win32gui.LoadImage(0, icon_path, win32con.IMAGE_ICON, 256, 256, win32con.LR_LOADFROMFILE)
        except:
            pass
            
        def wnd_proc(hwnd, msg, wp, lp):
            try:
                if msg == win32con.WM_ERASEBKGND:
                    return 1
                elif msg == win32con.WM_PAINT:
                    hdc, paintStruct = win32gui.BeginPaint(hwnd)
                    rect = win32gui.GetClientRect(hwnd)
                    vw_rect = rect[2] - rect[0]
                    vh_rect = rect[3] - rect[1]
                    
                    # Background: Fade từ Đen -> Xanh dương đậm -> Đen
                    # Dark Blue = (0, 51, 102)
                    fade = getattr(self, '_fade_value', 255)
                    r_bg = int(0 * (fade / 255.0))
                    g_bg = int(51 * (fade / 255.0))
                    b_bg = int(102 * (fade / 255.0))
                    bg_color = win32api.RGB(r_bg, g_bg, b_bg)
                    
                    brush = win32gui.CreateSolidBrush(bg_color)
                    win32gui.FillRect(hdc, rect, brush)
                    win32gui.DeleteObject(brush)
                    
                    win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
                    
                    # Fade effect cho Logo text (từ Đen -> Trắng -> Đen)
                    r_fg = int(255 * (fade / 255.0))
                    g_fg = int(255 * (fade / 255.0))
                    b_fg = int(255 * (fade / 255.0))
                    win32gui.SetTextColor(hdc, win32api.RGB(r_fg, g_fg, b_fg))
                    
                    # Draw Icon (Centered, Top)
                    icon_size = 256
                    icon_x = (vw_rect - icon_size) // 2
                    icon_y = (vh_rect // 2) - icon_size - 20
                    if getattr(self, '_cover_hIcon', 0):
                        win32gui.DrawIconEx(hdc, icon_x, icon_y, self._cover_hIcon, icon_size, icon_size, 0, 0, win32con.DI_NORMAL)
                    
                    # Create Font using GDI
                    text_y = (vh_rect // 2) + 20
                    text_rect = (0, text_y, vw_rect, text_y + 150)
                    privacy_title = _("CHẾ ĐỘ RIÊNG TƯ")
                    try:
                        font_lf = win32gui.LOGFONT()
                        font_lf.lfHeight = 72
                        font_lf.lfWeight = win32con.FW_BOLD
                        font_lf.lfFaceName = "Segoe UI"
                        font = win32gui.CreateFontIndirect(font_lf)
                        old_font = win32gui.SelectObject(hdc, font)
                        win32gui.DrawText(hdc, privacy_title, -1, text_rect,
                                          win32con.DT_CENTER | win32con.DT_VCENTER | win32con.DT_SINGLELINE)
                        win32gui.SelectObject(hdc, old_font)
                        win32gui.DeleteObject(font)
                    except:
                        pass
                        
                    win32gui.EndPaint(hwnd, paintStruct)
                    return 0
                elif msg == win32con.WM_TIMER:
                    if not getattr(self, 'screen_cover_running', False):
                        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                        return 0

                    # Cover UIAccess + TOPMOST mỗi tick đè hộp UAC → không bấm được Yes/No.
                    try:
                        uac_up = uac_consent_running()
                    except Exception:
                        uac_up = False
                    if uac_up:
                        try:
                            self._sync_privacy_with_uac()
                        except Exception:
                            pass
                        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                        return 0

                    # Fade animation
                    self._fade_value += self._fade_dir
                    if self._fade_value >= 255:
                        self._fade_value = 255
                        self._fade_dir = -5
                    elif self._fade_value <= 0:
                        self._fade_value = 0
                        self._fade_dir = 5
                        
                    win32gui.InvalidateRect(hwnd, None, False)
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                          win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
                    try:
                        if not ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x11):
                            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x01)
                    except:
                        pass
                    return 0
                elif msg == win32con.WM_CLOSE:
                    try:
                        ctypes.windll.user32.KillTimer(hwnd, 1)
                    except:
                        pass
                    win32gui.DestroyWindow(hwnd)
                    return 0
                elif msg == win32con.WM_DESTROY:
                    win32gui.PostQuitMessage(0)
                    return 0
                elif msg == win32con.WM_NCHITTEST:
                    return -1  # HTTRANSPARENT
            except Exception as e:
                print(f"[Host] Cover Win32 wnd_proc error: {e}")
            return win32gui.DefWindowProc(hwnd, msg, wp, lp)
            
        hInst = win32api.GetModuleHandle(None)
        cls_name = f"AGCover_{id(self)}"
        
        wc = win32gui.WNDCLASS()
        wc.style = win32con.CS_HREDRAW | win32con.CS_VREDRAW
        wc.lpfnWndProc = wnd_proc
        wc.cbWndExtra = 0
        wc.hInstance = hInst
        wc.hCursor = 0  # Ẩn cursor
        wc.hbrBackground = 0 # Tự vẽ
        wc.lpszClassName = cls_name
        
        try:
            class_atom = win32gui.RegisterClass(wc)
        except Exception as e:
            print(f"[Host] Cover Win32 RegisterClass error: {e}")
            try:
                win32gui.UnregisterClass(cls_name, hInst)
                class_atom = win32gui.RegisterClass(wc)
            except Exception as ex:
                print(f"[Host] Cover Win32 RegisterClass retry failed: {ex}")
                self.screen_cover_running = False
                return
                
        WS_EX_NOACTIVATE = 0x08000000
        ex_style = (
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_TOOLWINDOW
            | win32con.WS_EX_TOPMOST
            | WS_EX_NOACTIVATE
        )
        style = win32con.WS_POPUP | win32con.WS_VISIBLE
        
        hwnd = self._create_privacy_cover_hwnd(cls_name, ex_style, style, vx, vy, vw, vh, hInst)
        if not hwnd:
            try:
                hwnd = win32gui.CreateWindowEx(
                    ex_style, class_atom, "AGCover", style,
                    vx, vy, vw, vh, 0, 0, hInst, None
                )
            except Exception as e:
                print(f"[Host] Cover Win32 CreateWindowEx error: {e}")
                hwnd = 0
        if not hwnd:
            try:
                win32gui.UnregisterClass(class_atom, hInst)
            except Exception:
                pass
            self.screen_cover_running = False
            return
            
        self._cover_hwnd = hwnd
        print(f"[Host] Cover Win32: HWND={hex(hwnd)}")
        
        try:
            # Alpha 254 (instead of 255) forces DWM to compose the window as layered.
            # This is a critical workaround for Optimus hybrid graphics where WDA_EXCLUDEFROMCAPTURE
            # completely hides the window on the physical display if alpha is 255 or WS_EX_LAYERED is missing.
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 254, win32con.LWA_ALPHA)
        except Exception as e:
            print(f"[Host] Cover Win32 SetLayeredWindowAttributes error: {e}")
        
        try:
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, vx, vy, vw, vh, win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE)
        except:
            pass
            
        try:
            if not ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x11):
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x01)
        except:
            pass
            
        try:
            ctypes.windll.user32.SetTimer(hwnd, 1, 50, None)
        except Exception as e:
            pass
        print("[Host] Cover Win32: Running message pump.")
        
        win32gui.PumpMessages()
        
        self._cover_hwnd = None
        try:
            win32gui.UnregisterClass(class_atom, hInst)
        except:
            pass
        print("[Host] Cover Win32: Closed.")


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
                print("[Host] Failed to open Global\\AntigravityP2P_SAS_Event (event is null). Falling back to SendSAS.")
                import ctypes
                try: ctypes.windll.sas.SendSAS(False)
                except: pass
        except Exception as e:
            print(f"[Host] Failed to signal SAS event: {e}. Falling back to SendSAS.")
            import ctypes
            try: ctypes.windll.sas.SendSAS(False)
            except: pass

    def trigger_terminal(self):
        print("[Host] Received trigger_terminal command. Simulating Ctrl+Alt+T.")
        import sys
        if sys.platform != "win32":
            import os
            os.system("xdotool key ctrl+alt+t")

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
