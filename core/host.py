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
from network.socket_utils import socket_passwords, force_close_socket, APP_KEY
from utils.input_simulator import INPUT, INPUT_KEYBOARD, KEYEVENTF_UNICODE, KEYEVENTF_KEYUP, _remote_modifier_keys
from PIL import Image


from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from utils.logger import log_debug, log_activity, log_file_transfer
from network.socket_utils import send_msg, recv_msg, is_lan_socket, tune_socket_for_lan_bulk
from utils.input_simulator import send_input_keyboard_event, send_input_mouse_click, send_input_mouse_move, send_input_mouse_scroll
from core.clipboard_agent import ClipboardSyncManager, clipboard_sync_manager, run_clipboard_agent_mode

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
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
    is_secure_desktop,
    check_desktop_change,
    is_machine_domain_joined
)

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


_MAX_SEND_EDGE_LAN = 4096
_MAX_SEND_EDGE_WAN = 2560
_MAX_SEND_EDGE_LEGACY = 1920


def _is_legacy_windows_host():
    """Windows 7/Vista: không có DXGI Desktop Duplication; JPEG 4:4:4 cũng quá nặng."""
    if sys.platform != "win32":
        return False
    try:
        v = sys.getwindowsversion()
        return v.major < 6 or (v.major == 6 and v.minor < 2)
    except Exception:
        return str(platform.release()) in ("7", "Vista", "XP")


def _windows_has_dxgi_duplication():
    return sys.platform == "win32" and not _is_legacy_windows_host()


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


def _clip_tile_onto_canvas(canvas, tile, x, y):
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
    dst[:] = src
    return True


def grab_gdi_primary_bgr():
    """BitBlt màn chính — ổn định trên Windows 7 (không DXGI, không mss virtual desktop)."""
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    w = int(user32.GetSystemMetrics(0))
    h = int(user32.GetSystemMetrics(1))
    if w < 1 or h < 1:
        raise RuntimeError("GDI invalid screen size")
    hwnd = user32.GetDesktopWindow()
    hdc = user32.GetDC(hwnd)
    if not hdc:
        raise RuntimeError("GDI GetDC failed")
    memdc = gdi32.CreateCompatibleDC(hdc)
    hbmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(memdc, hbmp)
    try:
        if not gdi32.BitBlt(memdc, 0, 0, w, h, hdc, 0, 0, 0x00CC0020):
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
        return frame, w, h, (0, 0)
    finally:
        gdi32.SelectObject(memdc, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(hwnd, hdc)


def _open_dxcam_outputs():
    cams = []
    if not _windows_has_dxgi_duplication():
        print("[Host] Skip dxcam (Windows 7/Vista không hỗ trợ Desktop Duplication)")
        return cams
    try:
        import dxcam
        fac = dxcam.DXFactory()
    except Exception as e:
        print(f"[Host] dxcam factory failed: {e}")
        return cams
    for di, outputs in enumerate(getattr(fac, "outputs", []) or []):
        for oi, output in enumerate(outputs):
            try:
                if hasattr(output, "attached_to_desktop") and not output.attached_to_desktop:
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


def grab_dxcam_virtual_bgr(cams, canvas=None):
    left0, top0, w, h = _virtual_screen_rect()
    if canvas is None or canvas.shape[0] != h or canvas.shape[1] != w:
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
    any_ok = False
    for cam in cams:
        try:
            tile = cam.grab()
            if tile is None:
                continue
            try:
                cam._output.update_desc()
                rc = cam._output.desc.DesktopCoordinates
                x, y = int(rc.left) - left0, int(rc.top) - top0
            except Exception:
                x, y = 0, 0
            if _clip_tile_onto_canvas(canvas, tile, x, y):
                any_ok = True
        except Exception as e:
            print(f"[Host] dxcam grab failed: {e}")
    return canvas, w, h, (left0, top0), any_ok


def grab_virtual_desktop_bgr(sct, canvas=None):
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
    if canvas is None or canvas.shape[0] != h or canvas.shape[1] != w:
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
    parts = mons[1:] if mons and len(mons) > 1 else (mons[:1] if mons else [])
    any_ok = False
    for mon in parts:
        try:
            raw = sct.grab(mon)
            tile = np.array(raw, dtype=np.uint8)
            if _clip_tile_onto_canvas(
                canvas, tile,
                int(mon.get("left", 0)) - left0,
                int(mon.get("top", 0)) - top0,
            ):
                any_ok = True
        except Exception as e:
            print(f"[Host] Monitor grab failed ({mon}): {e}")
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


class HostMixin:
    def ensure_input_thread_desktop(self, force=False):
        if getattr(self, 'is_headless', False) is False and sys.platform != "win32":
            return
            
        now = time.time()
        last_check = getattr(self, '_last_input_desktop_check', 0)
        if not force and (now - last_check < 0.2):
            return
        self._last_input_desktop_check = now
        
        try:
            h_input = None
            # Try specific desktop rights (0x01FF) first, as it is more likely to succeed for SYSTEM than GENERIC_ALL
            for access_mask in [0x01FF, 0x02000000, 0x80000000, 0x0001, 0]:
                try:
                    h_input = ctypes.windll.user32.OpenInputDesktop(0, False, access_mask)
                    if h_input:
                        break
                except:
                    pass
                    
            if not h_input:
                # Fallback: if OpenInputDesktop fails, try opening the opposite desktop by name
                thread_name = get_desktop_name()
                target_name = "Winlogon" if thread_name == "default" else "Default"
                for access_mask in [0x01FF, 0x02000000, 0x80000000, 0x0001, 0]:
                    try:
                        h_input = ctypes.windll.user32.OpenDesktopW(target_name, 0, False, access_mask)
                        if h_input:
                            print(f"[Host Input] Opened {target_name} desktop by name (fallback)")
                            break
                    except:
                        pass

            if h_input:
                name_input = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetUserObjectInformationW(h_input, 2, name_input, ctypes.sizeof(name_input), None)
                
                h_thread = ctypes.windll.user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
                name_thread = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetUserObjectInformationW(h_thread, 2, name_thread, ctypes.sizeof(name_thread), None)
                
                if name_input.value.lower() != name_thread.value.lower():
                    print(f"[Host Input] Desktop changed from {name_thread.value} to {name_input.value}. Switching input thread...")
                    result = ctypes.windll.user32.SetThreadDesktop(h_input)
                    if not result:
                        print(f"[Host Input] SetThreadDesktop failed. Error code: {ctypes.get_last_error()}")
                ctypes.windll.user32.CloseDesktop(h_input)
        except Exception as e:
            print(f"[Host Input] Error in ensure_input_thread_desktop: {e}")

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
                
    def show_host_connection_border(self):
        if sys.platform != "win32":
            return
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
            
            # Use a SINGLE window with a border-shaped region instead of 4 windows
            win = tk.Toplevel(self)
            win.withdraw()
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.attributes("-alpha", 0.8)
            win.configure(bg=color)
            win.geometry(f"{w}x{h}+0+0")
            win.update_idletasks()
            
            try:
                import ctypes
                tk_hwnd = win.winfo_id()
                
                # Collect ALL unique HWNDs in the parent chain
                # On Win10, Tkinter creates a wrapper frame that shows on taskbar
                hwnds_to_style = set()
                hwnds_to_style.add(tk_hwnd)
                
                parent = ctypes.windll.user32.GetParent(tk_hwnd)
                if parent:
                    hwnds_to_style.add(parent)
                
                GA_ROOT = 2
                root = ctypes.windll.user32.GetAncestor(tk_hwnd, GA_ROOT)
                if root and root != ctypes.windll.user32.GetDesktopWindow():
                    hwnds_to_style.add(root)
                
                GA_ROOTOWNER = 3
                root_owner = ctypes.windll.user32.GetAncestor(tk_hwnd, GA_ROOTOWNER)
                if root_owner and root_owner != ctypes.windll.user32.GetDesktopWindow():
                    hwnds_to_style.add(root_owner)
                
                try:
                    frame_id = win.wm_frame()
                    fh = int(frame_id, 0) if isinstance(frame_id, str) else int(frame_id)
                    if fh:
                        hwnds_to_style.add(fh)
                except:
                    pass
                
                # Set border region on the Tk widget HWND
                outer = ctypes.windll.gdi32.CreateRectRgn(0, 0, w, h)
                inner = ctypes.windll.gdi32.CreateRectRgn(thickness, thickness, w - thickness, h - thickness)
                ctypes.windll.gdi32.CombineRgn(outer, outer, inner, 4)  # RGN_DIFF
                ctypes.windll.user32.SetWindowRgn(tk_hwnd, outer, True)
                ctypes.windll.gdi32.DeleteObject(inner)
                
                # Also set region on root HWND if different
                if root and root != tk_hwnd and root != ctypes.windll.user32.GetDesktopWindow():
                    outer2 = ctypes.windll.gdi32.CreateRectRgn(0, 0, w, h)
                    inner2 = ctypes.windll.gdi32.CreateRectRgn(thickness, thickness, w - thickness, h - thickness)
                    ctypes.windll.gdi32.CombineRgn(outer2, outer2, inner2, 4)
                    ctypes.windll.user32.SetWindowRgn(root, outer2, True)
                    ctypes.windll.gdi32.DeleteObject(inner2)
                
                # Apply WS_EX_TOOLWINDOW on ALL HWNDs to guarantee taskbar hiding
                GWL_EXSTYLE = -20
                WS_EX_TRANSPARENT = 0x00000020
                WS_EX_TOOLWINDOW = 0x00000080
                WS_EX_APPWINDOW = 0x00040000
                WS_EX_NOACTIVATE = 0x08000000
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOZORDER = 0x0004
                SWP_FRAMECHANGED = 0x0020
                
                for hwnd in hwnds_to_style:
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    new_style = (style & ~WS_EX_APPWINDOW) | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
                    
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
                    print(f"[Host] Win7 GDI handshake size {host_w}x{host_h}")
                else:
                    with mss.mss() as sct:
                        monitor = sct.monitors[0]
                        host_w = monitor['width']
                        host_h = monitor['height']
                        self._capture_origin = (int(monitor.get('left', 0)), int(monitor.get('top', 0)))
                    
                import platform
                computer_name = platform.node()
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
                    "chk_reason": chk_reason,
                    "os_release": platform.release()
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
                            print(f"[Host] Speed test finished. Class: {net_class}, Bandwidth: {bandwidth:.2f} Mbps")
                            if not _is_legacy_windows_host():
                                if net_class == "high":
                                    set_windows_graphics_effects(True)
                                else:
                                    set_windows_graphics_effects(False)
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
                self.after(0, lambda: self.show_custom_info(_("Kết nối từ xa"), msg_text, auto_close_sec=15))
                if not _is_legacy_windows_host():
                    self.after(0, self.show_host_connection_border)
                self.wake_display()
                
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
                if _is_legacy_windows_host():
                    print("[Host] Using GDI BitBlt capture (Windows 7)")
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
                    raise RuntimeError("no screen capture backend")
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                for cam in self.dx_cams:
                    try:
                        cam.release()
                    except Exception:
                        pass
                self.dx_cams = []
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
        while client_state.get("running", False):
            try:
                if time.time() - _last_hb >= 2.5:
                    try:
                        send_msg(conn, json.dumps({"type": "pong"}).encode("utf-8"), password)
                        _last_hb = time.time()
                    except Exception:
                        pass
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
                        hdesk = None
                        for access_mask in [0x01FF, 0x02000000, 0x80000000, 0x0001, 0]:
                            try:
                                hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, access_mask)
                                if hdesk:
                                    break
                            except:
                                pass
                        
                        # Fallback: if OpenInputDesktop fails, try opening desktop by name
                        if not hdesk:
                            thread_name = get_desktop_name()
                            # Try the opposite desktop
                            target_name = "Winlogon" if thread_name == "default" else "Default"
                            for access_mask in [0x01FF, 0x02000000, 0x80000000, 0x0001, 0]:
                                try:
                                    hdesk = ctypes.windll.user32.OpenDesktopW(target_name, 0, False, access_mask)
                                    if hdesk:
                                        print(f"[Host] Opened {target_name} desktop by name (fallback)")
                                        break
                                except:
                                    pass
                                
                        if hdesk:
                            result = ctypes.windll.user32.SetThreadDesktop(hdesk)
                            ctypes.windll.user32.CloseDesktop(hdesk)
                            if not result:
                                print("[Host] SetThreadDesktop() failed (thread may have existing windows). Retrying...")
                                time.sleep(0.3)
                                continue
                        else:
                            print("[Host] OpenInputDesktop failed for all access masks.")
                            time.sleep(0.3)
                            continue
                    except Exception as e:
                        print(f"[Host] SetThreadDesktop exception: {e}")
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
                        
                    while client_state.get("running", False):
                        try:
                            if time.time() - _last_hb >= 2.0:
                                try:
                                    send_msg(conn, json.dumps({"type": "pong"}).encode("utf-8"), password)
                                    _last_hb = time.time()
                                except Exception:
                                    pass
                            # Check for mid-session desktop transitions
                            if not _legacy_host:
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
                                
                            grabbed = False
                            if _legacy_host:
                                frame_bgr, cap_w, cap_h, origin = grab_gdi_primary_bgr()
                                self._capture_origin = origin
                                grabbed = True
                            if dx_cams and not grabbed:
                                retries = 8 if not client_state.get("_got_frame") else 1
                                for _try in range(retries):
                                    frame_bgr, cap_w, cap_h, origin, grabbed = grab_dxcam_virtual_bgr(
                                        dx_cams, client_state.get("_stitch_canvas")
                                    )
                                    client_state["_stitch_canvas"] = frame_bgr
                                    self._capture_origin = origin
                                    if grabbed:
                                        break
                                    time.sleep(0.01)
                            if not grabbed:
                                if sct is None:
                                    frame_bgr, cap_w, cap_h, origin = grab_gdi_primary_bgr()
                                    self._capture_origin = origin
                                else:
                                    frame_bgr, cap_w, cap_h, origin = grab_virtual_desktop_bgr(
                                        sct, client_state.get("_stitch_canvas")
                                    )
                                    client_state["_stitch_canvas"] = frame_bgr
                                    self._capture_origin = origin
                            
                            target_w = getattr(self, 'client_viewer_w', 1280)
                            target_h = getattr(self, 'client_viewer_h', 720)
                            
                            force_update = client_state.pop("force_update", False)
                            if not client_state.get("_first_sent"):
                                force_update = True
                            if client_state.get("last_target_w") != target_w or client_state.get("last_target_h") != target_h:
                                force_update = True
                                client_state["last_target_w"] = target_w
                                client_state["last_target_h"] = target_h

                            net_class = client_state.get("net_class", "medium")
                            q_mode = getattr(self, 'client_quality_mode', 'quality')
                            if _legacy_host:
                                q_mode = "speed"
                            
                            if q_mode == "quality":
                                base_quality = 96
                                fps_limit = 25
                                res_scale = -1.0
                            elif net_class == "high":
                                base_quality = 98
                                fps_limit = 60
                                res_scale = -1.0
                            elif net_class == "low" or _legacy_host:
                                base_quality = 55 if _legacy_host else 40
                                fps_limit = 10 if _legacy_host else 12
                                res_scale = 0.7 if _legacy_host else 0.6
                            else:
                                base_quality = 75
                                fps_limit = 30
                                res_scale = 1.0

                            quality = client_state.get("dyn_quality", base_quality)
                            sleep_time = client_state.get("dyn_sleep_time", 1.0 / fps_limit)
                            dyn_scale = client_state.get("dyn_scale", res_scale)

                            if "start_time" not in client_state:
                                client_state["start_time"] = time.time()
                                
                            if (not _legacy_host) and time.time() - client_state["start_time"] < 5.0 and cap_w * cap_h <= (1920 * 1200):
                                quality = min(98, quality + 10)
                                if dyn_scale >= 0:
                                    dyn_scale = min(1.0, dyn_scale + 0.1)
                                client_state["dyn_quality"] = quality
                                client_state["dyn_scale"] = dyn_scale

                            if client_state.get("last_cap_w") != cap_w or client_state.get("last_cap_h") != cap_h:
                                client_state["last_cap_w"] = cap_w
                                client_state["last_cap_h"] = cap_h
                                force_update = True
                                try:
                                    res_meta = {"type": "resolution_change", "w": cap_w, "h": cap_h}
                                    send_msg(conn, json.dumps(res_meta).encode('utf-8'), password)
                                except Exception:
                                    pass

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
                                target_scale = -1.0 if net_class == "high" else 1.0
                                if current_q < 98 or (current_s >= 0 and current_s < target_scale) or (current_s >= 0 and target_scale < 0):
                                    client_state["dyn_quality"] = min(98, current_q + 15)
                                    if target_scale < 0:
                                        client_state["dyn_scale"] = -1.0  # Phục hồi về full resolution
                                    else:
                                        client_state["dyn_scale"] = min(target_scale, current_s + 0.1)
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
                                frame_h_cur, frame_w_cur = frame_bgr.shape[:2]
                                if box_w * box_h < (frame_w_cur * frame_h_cur) * 0.7:
                                    frame_bgr = frame_bgr[diff_bbox[1]:diff_bbox[3], diff_bbox[0]:diff_bbox[2]]
                                    partial_meta = {"type": "partial_frame", "bbox": diff_bbox}
                                    send_msg(conn, json.dumps(partial_meta).encode('utf-8'), password)
                            
                            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
                            if (not _legacy_host) and hasattr(cv2, "IMWRITE_JPEG_OPTIMIZE"):
                                encode_param.extend([int(cv2.IMWRITE_JPEG_OPTIMIZE), 1])
                            if (not _legacy_host) and quality >= 88 and hasattr(cv2, "IMWRITE_JPEG_SAMPLING_FACTOR") and hasattr(cv2, "IMWRITE_JPEG_SAMPLING_FACTOR_444"):
                                encode_param.extend([int(cv2.IMWRITE_JPEG_SAMPLING_FACTOR), int(cv2.IMWRITE_JPEG_SAMPLING_FACTOR_444)])
                            result, encimg = cv2.imencode('.jpg', frame_bgr, encode_param)
                            if not result:
                                time.sleep(0.05)
                                continue
                            jpeg_data = encimg.tobytes()
                            
                            t_start_send = time.time()
                            send_msg(conn, jpeg_data, password)
                            send_time = time.time() - t_start_send
                            _last_hb = time.time()
                            
                            if "send_ema" not in client_state:
                                client_state["send_ema"] = send_time
                            else:
                                client_state["send_ema"] = 0.8 * client_state["send_ema"] + 0.2 * send_time
                                
                            ema = client_state["send_ema"]
                            
                            if q_mode == "quality":
                                quality = max(94, min(98, int(quality)))
                                if ema > 0.45:
                                    sleep_time = min(0.12, sleep_time + 0.02)
                                elif ema < 0.20:
                                    sleep_time = max(1.0 / 30, sleep_time - 0.005)
                                dyn_scale = -1.0
                            elif ema > 0.35:
                                # Mạng chậm: Chỉ giảm chất lượng ảnh, hạn chế bóp scale để tránh vỡ khối pixel
                                quality = max(max(35, base_quality - 20), quality - 5)
                                sleep_time = min(0.3, sleep_time + 0.05)
                                if ema > 0.6 and dyn_scale >= 0:
                                    dyn_scale = max(max(0.5, res_scale if res_scale > 0 else 0.5), dyn_scale - 0.05)
                            elif ema < 0.20:
                                # Mạng tốt: Tăng dần chất lượng và scale
                                quality = min(98, quality + 1)
                                sleep_time = max(1.0 / 60, sleep_time - 0.005)
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
                            time.sleep(sleep_time)
                        except mss.exception.ScreenShotError as e:
                            print(f"[Host] Screen capture error (re-initializing): {e}")
                            time.sleep(0.3)
                            break
                        except Exception as e:
                            import traceback
                            try:
                                with open("host_error.log", "a", encoding="utf-8") as f:
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
                    if sys.platform == "win32":
                        try:
                            import ctypes as _ct
                            # Lấy tên desktop hiện tại để phát hiện thay đổi (UAC/Winlogon)
                            _buf = _ct.create_unicode_buffer(256)
                            _hd_cur = _ct.windll.user32.GetThreadDesktop(_ct.windll.kernel32.GetCurrentThreadId())
                            _ct.windll.user32.GetUserObjectInformationW(_hd_cur, 2, _buf, _ct.sizeof(_buf), None)
                            _cur_name = _buf.value.lower() if _buf.value else None

                            _hdesk_new = None
                            # Try multiple access masks (Win11 blocks GENERIC_ALL for elevated windows)
                            for _am in [0x01FF, 0x02000000, 0x80000000, 0x0001, 0x0040, 0]:
                                _hdesk_new = _ct.windll.user32.OpenInputDesktop(0, False, _am)
                                if _hdesk_new:
                                    break
                            
                            # Fallback: open desktop by name if OpenInputDesktop fails
                            if not _hdesk_new:
                                _target_name = "Winlogon" if _cur_name == "default" else "Default"
                                for _am in [0x01FF, 0x02000000, 0x80000000, 0x0001, 0]:
                                    _hdesk_new = _ct.windll.user32.OpenDesktopW(_target_name, 0, False, _am)
                                    if _hdesk_new:
                                        break
                            
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
                r, _, _ = select.select([conn], [], [], 0.2)
                
                if getattr(self, 'head_screen_cover_active', False):
                    try:
                        import ctypes
                        # Luôn re-apply BlockInput mỗi 0.2s để chống lại SAS (Ctrl+Alt+Del)
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
                    if evt_type in ("batch_start", "file_start", "file_chunk", "file_end", "batch_end", "files_copied_meta", "request_files", "cancel_transfer", "clipboard_text", "clipboard_image"):
                        if clipboard_sync_manager:
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
        print("[Host] Client disconnected, forcing screen cover to disable.")
        self.disable_screen_cover()
        
    def host_handle_event(self, event, conn, password):
        ev_type = event.get('type')
        if ev_type == 'mouse_move':
            self.ensure_input_thread_desktop(force=False)
            x, y = event['x'], event['y']
            ox, oy = getattr(self, "_capture_origin", (0, 0))
            send_input_mouse_move(x + ox, y + oy)
                
        elif ev_type == 'mouse_click':
            self.ensure_input_thread_desktop(force=True)
            button_name = event.get('button')
            pressed = event.get('pressed')
            # Primary simulation using standard SendInput API
            send_input_mouse_click(button_name, pressed)
            try:
                if pressed and clipboard_sync_manager:
                    if button_name == 'right':
                        clipboard_sync_manager.last_rbutton_time = time.time()
                    elif button_name == 'left':
                        clipboard_sync_manager.last_lbutton_time = time.time()
            except Exception as e:
                pass
                
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
                                
                        end_msg = {"type": "file_end", "name": name}
                        send_msg(c, json.dumps(end_msg).encode('utf-8'), pwd)
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
                        send_msg(c, json.dumps(batch_end_msg).encode('utf-8'), pwd)
                        return
                        
                    display_name = all_files[0][1]
                    if len(pts) > 1:
                        display_name += f" và {len(pts)-1} mục khác"
                        
                    batch_start_msg = {"type": "batch_start", "total_size": total_sz, "display_name": display_name}
                    send_msg(c, json.dumps(batch_start_msg).encode('utf-8'), pwd)
                    time.sleep(0.5)
                        
                    for fpath, rname, sz in all_files:
                        parts = rname.split('/')
                        fname = parts[-1]
                        sub_dir = "/".join(parts[:-1])
                        
                        final_t_dir = t_dir
                        if not final_t_dir.endswith("/"): final_t_dir += "/"
                        if sub_dir:
                            final_t_dir += sub_dir
                            
                        start_msg = {"type": "file_start", "name": fname, "size": sz, "target_dir": final_t_dir}
                        send_msg(c, json.dumps(start_msg).encode('utf-8'), pwd)
                        time.sleep(0.5)
                        
                        with open(fpath, "rb") as f:
                            while True:
                                chunk = f.read(65536)
                                if not chunk: break
                                chunk_msg = {
                                    "type": "file_chunk",
                                    "name": fname,
                                    "data": base64.b64encode(chunk).decode('utf-8')
                                }
                                send_msg(c, json.dumps(chunk_msg).encode('utf-8'), pwd)
                                time.sleep(0.01)
                                
                        end_msg = {"type": "file_end", "name": fname}
                        send_msg(c, json.dumps(end_msg).encode('utf-8'), pwd)
                        time.sleep(0.1)
                        
                    batch_end_msg = {"type": "batch_end"}
                    send_msg(c, json.dumps(batch_end_msg).encode('utf-8'), pwd)
                        
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

    def _run_input_hooks(self):
        import ctypes
        from ctypes import wintypes
        import win32con
        
        user32 = ctypes.windll.user32
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
        LLMHF_INJECTED = 0x00000001
        
        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        
        def keyboard_hook_proc(nCode, wParam, lParam):
            if nCode == 0:
                flags = ctypes.c_uint.from_address(lParam + 8).value
                if not (flags & LLKHF_INJECTED):
                    return 1
            return user32.CallNextHookEx(None, nCode, wParam, lParam)
            
        def mouse_hook_proc(nCode, wParam, lParam):
            if nCode == 0:
                flags = ctypes.c_uint.from_address(lParam + 12).value
                if not (flags & LLMHF_INJECTED):
                    return 1
            return user32.CallNextHookEx(None, nCode, wParam, lParam)
            
        self._kb_hook_ref = HOOKPROC(keyboard_hook_proc)
        self._ms_hook_ref = HOOKPROC(mouse_hook_proc)
        
        h_mod = ctypes.windll.kernel32.GetModuleHandleW(None)
        kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_hook_ref, h_mod, 0)
        ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._ms_hook_ref, h_mod, 0)
        
        def timer_proc(hwnd, msg, timer_id, time):
            if not getattr(self, 'host_block_input_active', False):
                user32.PostQuitMessage(0)
                
        TIMERPROC = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint)
        timer_ref = TIMERPROC(timer_proc)
        timer_id = user32.SetTimer(None, 0, 200, timer_ref)
        
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
            
        user32.KillTimer(None, timer_id)
        user32.UnhookWindowsHookEx(kb_hook)
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

    def toggle_screen_cover(self):
        if sys.platform != "win32":
            return
        import win32event, win32api, ctypes
        
        is_active = not getattr(self, 'head_screen_cover_active', False)
        self.head_screen_cover_active = is_active
        
        try:
            ctypes.windll.user32.BlockInput(is_active)
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

    def disable_screen_cover(self):
        if sys.platform != "win32":
            return
        import win32event, win32api, ctypes
        
        self.head_screen_cover_active = False
        try:
            ctypes.windll.user32.BlockInput(False)
        except:
            pass
            
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
            print("[Host] Screen cover disabled.")
            return

        self.screen_cover_running = True
        self.start_input_hooks()
        print("[Host] Screen cover enabled. Launching Win32 cover thread...")
        import threading
        threading.Thread(target=self._run_cover_win32, daemon=True).start()

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
                    try:
                        font_lf = win32gui.LOGFONT()
                        font_lf.lfHeight = 80
                        font_lf.lfWeight = win32con.FW_BOLD
                        font_lf.lfFaceName = "Segoe UI"
                        font = win32gui.CreateFontIndirect(font_lf)
                        old_font = win32gui.SelectObject(hdc, font)
                        win32gui.DrawText(hdc, "P2P REMOTE DESKTOP PRIVACY MODE", -1, text_rect,
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
                
        ex_style = win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TOPMOST
        style = win32con.WS_POPUP | win32con.WS_VISIBLE
        
        try:
            hwnd = win32gui.CreateWindowEx(
                ex_style, class_atom, "AGCover", style,
                vx, vy, vw, vh, 0, 0, hInst, None
            )
        except Exception as e:
            print(f"[Host] Cover Win32 CreateWindowEx error: {e}")
            win32gui.UnregisterClass(class_atom, hInst)
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
