# -*- coding: utf-8 -*-
"""
xp_host/xp_capture.py
Chụp màn hình thuần Win32 GDI (BitBlt + GetDIBits) + nén JPEG & Dirty-Rect qua Pillow (PIL).
Không sử dụng dxcam, mss, opencv-python (cv2) hay numpy — chạy ổn định trên mọi CPU Windows XP
(kể cả Pentium 4 / Athlon XP / Atom không có tập lệnh SSE4.2 hay AVX) và hỗ trợ cả màn hình
đăng nhập Windows XP (Winlogon desktop) lẫn đa màn hình.
"""

import ctypes
from ctypes import wintypes
import io
import sys

try:
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover
    Image = None
    ImageChops = None

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DIB_RGB_COLORS = 0

_DESKTOP_ACCESS_MASKS = (
    0x02000000,  # MAXIMUM_ALLOWED
    0x01FF,      # DESKTOP_ALL
    0x0183,      # SWITCH | SETTHREAD | CREATEWINDOW | READOBJECTS
    0x0081,      # SETTHREAD | READOBJECTS
)


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


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def get_thread_desktop_name():
    if sys.platform != "win32":
        return "default"
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        h_desk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
        name = ctypes.create_unicode_buffer(256)
        size = ctypes.c_ulong(256)
        if user32.GetUserObjectInformationW(h_desk, 2, name, ctypes.sizeof(name), ctypes.byref(size)):
            return (name.value or "default").lower()
    except Exception:
        pass
    return "default"


def get_input_desktop_name():
    if sys.platform != "win32":
        return "default"
    user32 = ctypes.windll.user32
    h_desk = 0
    try:
        for mask in _DESKTOP_ACCESS_MASKS:
            h_desk = user32.OpenInputDesktop(0, False, mask)
            if h_desk:
                break
        if not h_desk:
            return get_thread_desktop_name()
        name = ctypes.create_unicode_buffer(256)
        size = ctypes.c_ulong(256)
        if user32.GetUserObjectInformationW(h_desk, 2, name, ctypes.sizeof(name), ctypes.byref(size)):
            return (name.value or "default").lower()
    except Exception:
        pass
    finally:
        if h_desk:
            try:
                user32.CloseDesktop(h_desk)
            except Exception:
                pass
    return "default"


def attach_thread_to_active_desktop():
    """
    Trên Windows XP (Interactive Service chạy ở Session 0):
    Tự động gắn thread hiện tại vào desktop đang nhận input ('Winlogon' khi ở màn hình
    đăng nhập / khóa máy Ctrl+Alt+Del, hoặc 'Default' khi đã vào màn hình Desktop).
    Trả về (switched_or_ok: bool, desktop_name: str).
    """
    if sys.platform != "win32":
        return True, "default"
    user32 = ctypes.windll.user32
    cur_name = get_thread_desktop_name()
    inp_name = get_input_desktop_name()

    if inp_name and cur_name == inp_name:
        return True, cur_name

    # Thử OpenInputDesktop trước
    for mask in _DESKTOP_ACCESS_MASKS:
        h_desk = user32.OpenInputDesktop(0, False, mask)
        if h_desk:
            if user32.SetThreadDesktop(h_desk):
                user32.CloseDesktop(h_desk)
                return True, get_thread_desktop_name()
            user32.CloseDesktop(h_desk)

    # Fallback mở đích danh Winlogon hoặc Default trên WinSta0
    for target in ("Winlogon", "Default"):
        if target.lower() == cur_name:
            continue
        for mask in _DESKTOP_ACCESS_MASKS:
            h_desk = user32.OpenDesktopW(ctypes.c_wchar_p(target), 0, False, mask)
            if h_desk:
                if user32.SetThreadDesktop(h_desk):
                    user32.CloseDesktop(h_desk)
                    return True, target.lower()
                user32.CloseDesktop(h_desk)

    return False, cur_name


def enum_xp_monitors():
    """Liệt kê danh sách màn hình vật lý [(left, top, width, height), ...] sắp xếp trái -> phải."""
    if sys.platform != "win32":
        return [(0, 0, 1024, 768)]
    user32 = ctypes.windll.user32
    rects = []
    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
    )

    def _cb(hmon, _hdc, lprc, _lparam):
        try:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcMonitor
            elif lprc:
                r = lprc.contents
            else:
                return True
            w = int(r.right - r.left)
            h = int(r.bottom - r.top)
            if w > 0 and h > 0:
                rects.append((int(r.left), int(r.top), w, h))
        except Exception:
            pass
        return True

    try:
        user32.EnumDisplayMonitors(0, None, MONITORENUMPROC(_cb), 0)
    except Exception:
        pass

    if not rects:
        sw = int(user32.GetSystemMetrics(0)) or 1024
        sh = int(user32.GetSystemMetrics(1)) or 768
        rects.append((0, 0, sw, sh))

    rects.sort(key=lambda r: (r[0], r[1]))
    return rects


def get_capture_geometry(monitor_mode="both"):
    """Trả về (left, top, width, height, monitors_list) tương ứng với chế độ màn hình."""
    rects = enum_xp_monitors()
    if len(rects) >= 2 and monitor_mode in ("left", "right"):
        idx = 0 if monitor_mode == "left" else 1
        l, t, w, h = rects[idx]
        return l, t, w, h, rects

    if len(rects) == 1:
        l, t, w, h = rects[0]
        return l, t, w, h, rects

    left = min(r[0] for r in rects)
    top = min(r[1] for r in rects)
    right = max(r[0] + r[2] for r in rects)
    bottom = max(r[1] + r[3] for r in rects)
    return left, top, max(1, right - left), max(1, bottom - top), rects


class XPGdiCapturer:
    """
    Bộ chụp màn hình GDI tái sử dụng buffer RAM để giảm cấp phát bộ nhớ trên máy XP RAM thấp.
    """

    def __init__(self):
        self._buf = None
        self._buf_size = 0

    def _ensure_buffer(self, byte_len):
        if self._buf is None or self._buf_size < byte_len:
            self._buf = ctypes.create_string_buffer(byte_len)
            self._buf_size = byte_len
        return self._buf

    def grab_pil(self, monitor_mode="both"):
        """
        Chụp màn hình hiện tại (kể cả Winlogon XP) và trả về:
          (pil_rgb_image, left, top, width, height, desktop_name)
        """
        if Image is None:
            raise RuntimeError("Pillow (PIL) is required for XP screen capture")

        _, desk_name = attach_thread_to_active_desktop()
        left, top, w, h, _ = get_capture_geometry(monitor_mode)

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        hdc = user32.GetDC(0)
        hwnd_used = 0
        if not hdc:
            hwnd_used = user32.GetDesktopWindow()
            hdc = user32.GetWindowDC(hwnd_used)
        if not hdc:
            raise RuntimeError("GDI GetDC(0) failed")

        memdc = gdi32.CreateCompatibleDC(hdc)
        hbmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
        old_obj = gdi32.SelectObject(memdc, hbmp)
        try:
            # CAPTUREBLT (có từ Win2000/XP) giúp chụp được cả cửa sổ trong suốt / tooltip
            ok = gdi32.BitBlt(memdc, 0, 0, w, h, hdc, left, top, SRCCOPY | CAPTUREBLT)
            if not ok:
                ok = gdi32.BitBlt(memdc, 0, 0, w, h, hdc, left, top, SRCCOPY)
            if not ok:
                raise RuntimeError("GDI BitBlt failed")

            bmi = BITMAPINFO()
            bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.bmiHeader.biWidth = w
            bmi.bmiHeader.biHeight = -h  # Top-down DIB
            bmi.bmiHeader.biPlanes = 1
            bmi.bmiHeader.biBitCount = 32
            bmi.bmiHeader.biCompression = 0

            raw_len = w * h * 4
            buf = self._ensure_buffer(raw_len)
            got = gdi32.GetDIBits(memdc, hbmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
            top_down = True
            if got == 0:
                bmi.bmiHeader.biHeight = h
                got = gdi32.GetDIBits(memdc, hbmp, 0, h, buf, ctypes.byref(bmi), DIB_RGB_COLORS)
                top_down = False
            if got == 0:
                raise RuntimeError("GDI GetDIBits failed")

            # Chuyển trực tiếp BGRX -> RGB trong C của Pillow (không cần numpy/cv2)
            img = Image.frombuffer("RGB", (w, h), buf.raw[:raw_len], "raw", "BGRX", 0, 1 if top_down else -1)
            # Copy sang vùng nhớ riêng để lần chụp tới ghi đè self._buf an toàn
            img = img.copy()
            return img, left, top, w, h, desk_name
        finally:
            if old_obj:
                gdi32.SelectObject(memdc, old_obj)
            if hbmp:
                gdi32.DeleteObject(hbmp)
            if memdc:
                gdi32.DeleteDC(memdc)
            user32.ReleaseDC(hwnd_used, hdc)


def resize_pil_if_needed(img, target_w, target_h, dyn_scale=-1.0, max_edge=1920):
    w, h = img.size
    final_w, final_h = w, h

    if dyn_scale is not None and dyn_scale > 0:
        tw = max(16, int(target_w * dyn_scale))
        th = max(16, int(target_h * dyn_scale))
        cap_ratio = w / float(h) if h > 0 else 1.0
        tgt_ratio = tw / float(th) if th > 0 else 1.0
        if cap_ratio > tgt_ratio:
            final_w = min(w, tw)
            final_h = max(10, int(final_w / cap_ratio))
        else:
            final_h = min(h, th)
            final_w = max(10, int(final_h * cap_ratio))

    longest = max(final_w, final_h)
    if max_edge and longest > max_edge:
        scale = max_edge / float(longest)
        final_w = max(10, int(final_w * scale))
        final_h = max(10, int(final_h * scale))

    if (final_w, final_h) != (w, h):
        resample = getattr(Image, "BILINEAR", 2)
        return img.resize((final_w, final_h), resample)
    return img


def compute_dirty_rect(cur_img, prev_img):
    """
    So sánh khung hình mới với khung trước bằng Pillow ImageChops (C speed):
      - Trả về ('static', None) nếu khung hình đứng yên 100%.
      - Trả về ('partial', (x0, y0, x1, y1)) nếu vùng thay đổi < 70% diện tích màn hình.
      - Trả về ('full', None) nếu thay đổi lớn hoặc kích thước thay đổi.
    """
    if prev_img is None or prev_img.size != cur_img.size or ImageChops is None:
        return "full", None
    diff = ImageChops.difference(cur_img, prev_img)
    bbox = diff.getbbox()
    if bbox is None:
        return "static", None
    x0, y0, x1, y1 = bbox
    fw, fh = cur_img.size
    # Nới biên 2px cho JPEG macroblock để viền chữ không bị nhòe
    x0 = max(0, x0 - 2)
    y0 = max(0, y0 - 2)
    x1 = min(fw, x1 + 2)
    y1 = min(fh, y1 + 2)
    if (x1 - x0) * (y1 - y0) < (fw * fh * 0.70):
        return "partial", (x0, y0, x1, y1)
    return "full", None


def encode_pil_jpeg(img, quality=75, quality_mode="quality"):
    q = max(35, min(95, int(quality)))
    bio = io.BytesIO()
    # subsampling=2 (4:2:0) cho chế độ tốc độ, subsampling=0 (4:4:4) khi Q>=75 cho chữ sắc nét
    subsampling = 2 if quality_mode == "speed" or q < 75 else 0
    try:
        img.save(bio, format="JPEG", quality=q, subsampling=subsampling)
    except TypeError:
        img.save(bio, format="JPEG", quality=q)
    return bio.getvalue()
