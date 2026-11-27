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
    _PIL_IMPORT_ERROR = None
except Exception as _pil_exc:  # pragma: no cover
    Image = None
    ImageChops = None
    _PIL_IMPORT_ERROR = repr(_pil_exc)

from .xp_config import xp_log

_LOGGED_FALLBACK_NOTICE = False

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DIB_RGB_COLORS = 0

# GDI+ Constants (có sẵn mặc định trong gdiplus.dll từ Windows XP RTM/SP2/SP3 -> Windows 11)
_PIXEL_FORMAT_32BPP_RGB = 0x00022009
_INTERPOLATION_BILINEAR = 3
_ENCODER_PARAM_LONG = 4
_STREAM_SEEK_CUR = 1

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


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _GdiplusStartupInput(ctypes.Structure):
    _fields_ = [
        ("GdiplusVersion", ctypes.c_uint32),
        ("DebugEventCallback", ctypes.c_void_p),
        ("SuppressBackgroundThread", wintypes.BOOL),
        ("SuppressExternalCodecs", wintypes.BOOL),
    ]


class _EncoderParameter(ctypes.Structure):
    _fields_ = [
        ("Guid", _GUID),
        ("NumberOfValues", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
        ("Value", ctypes.c_void_p),
    ]


class _EncoderParameters(ctypes.Structure):
    _fields_ = [
        ("Count", ctypes.c_uint),
        ("Parameter", _EncoderParameter * 1),
    ]


_CLSID_JPEG_ENCODER = _GUID(
    0x557CF401, 0x1A04, 0x11D3, (ctypes.c_ubyte * 8)(0x9A, 0x73, 0x00, 0x00, 0xF8, 0x1E, 0xF3, 0x2E)
)
_GUID_ENCODER_QUALITY = _GUID(
    0x1D5BE4B5, 0xFA4A, 0x452D, (ctypes.c_ubyte * 8)(0x9C, 0xDD, 0x5D, 0xB3, 0x51, 0x05, 0xE7, 0xEB)
)


class _RawBGRXFrame:
    """Khung hình BGRX 32-bit thuần bộ nhớ dùng cho nhánh dự phòng GDI+ khi máy XP không nạp được Pillow."""

    __slots__ = ("width", "height", "raw")

    def __init__(self, width, height, raw_bytes):
        self.width = int(width)
        self.height = int(height)
        self.raw = raw_bytes

    @property
    def size(self):
        return (self.width, self.height)

    def crop(self, bbox):
        x0, y0, x1, y1 = [int(v) for v in bbox]
        x0 = max(0, min(self.width, x0))
        y0 = max(0, min(self.height, y0))
        x1 = max(x0 + 1, min(self.width, x1))
        y1 = max(y0 + 1, min(self.height, y1))
        cw = x1 - x0
        ch = y1 - y0
        if cw == self.width and ch == self.height:
            return self
        stride = self.width * 4
        mv = memoryview(self.raw)
        rows = [
            mv[y * stride + x0 * 4 : y * stride + x1 * 4].tobytes()
            for y in range(y0, y1)
        ]
        return _RawBGRXFrame(cw, ch, b"".join(rows))


class _Win32GdiPlusFallback:
    """Bộ co giãn & nén JPEG bằng gdiplus.dll có sẵn trong Windows XP SP2/SP3 (0% thư viện ngoài)."""

    _token = ctypes.c_size_t(0)
    _ready = False
    _funcs_bound = False

    @classmethod
    def _ensure_ready(cls):
        if cls._ready:
            return
        if sys.platform != "win32":
            raise RuntimeError("GDI+ fallback is only supported on Windows")
        gdip = ctypes.windll.gdiplus
        ole32 = ctypes.windll.ole32
        kernel32 = ctypes.windll.kernel32

        if not cls._funcs_bound:
            gdip.GdiplusStartup.argtypes = [
                ctypes.POINTER(ctypes.c_size_t),
                ctypes.POINTER(_GdiplusStartupInput),
                ctypes.c_void_p,
            ]
            gdip.GdiplusStartup.restype = ctypes.c_int

            gdip.GdipCreateBitmapFromScan0.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            gdip.GdipCreateBitmapFromScan0.restype = ctypes.c_int

            gdip.GdipDisposeImage.argtypes = [ctypes.c_void_p]
            gdip.GdipDisposeImage.restype = ctypes.c_int

            gdip.GdipGetImageGraphicsContext.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
            gdip.GdipGetImageGraphicsContext.restype = ctypes.c_int

            gdip.GdipSetInterpolationMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
            gdip.GdipSetInterpolationMode.restype = ctypes.c_int

            gdip.GdipDrawImageRectI.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
            ]
            gdip.GdipDrawImageRectI.restype = ctypes.c_int

            gdip.GdipFlush.argtypes = [ctypes.c_void_p, ctypes.c_int]
            gdip.GdipFlush.restype = ctypes.c_int

            gdip.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
            gdip.GdipDeleteGraphics.restype = ctypes.c_int

            gdip.GdipSaveImageToStream.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(_GUID),
                ctypes.POINTER(_EncoderParameters),
            ]
            gdip.GdipSaveImageToStream.restype = ctypes.c_int

            ole32.CreateStreamOnHGlobal.argtypes = [ctypes.c_void_p, wintypes.BOOL, ctypes.POINTER(ctypes.c_void_p)]
            ole32.CreateStreamOnHGlobal.restype = ctypes.c_long

            ole32.GetHGlobalFromStream.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
            ole32.GetHGlobalFromStream.restype = ctypes.c_long

            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalUnlock.restype = wintypes.BOOL
            kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
            kernel32.GlobalSize.restype = ctypes.c_size_t
            cls._funcs_bound = True

        si = _GdiplusStartupInput(1, None, False, False)
        tok = ctypes.c_size_t(0)
        st = gdip.GdiplusStartup(ctypes.byref(tok), ctypes.byref(si), None)
        if st != 0:
            raise RuntimeError(f"GdiplusStartup failed (status={st})")
        cls._token = tok
        cls._ready = True

    @classmethod
    def resize_frame(cls, frame: _RawBGRXFrame, dst_w: int, dst_h: int) -> _RawBGRXFrame:
        cls._ensure_ready()
        gdip = ctypes.windll.gdiplus
        src_buf = ctypes.create_string_buffer(frame.raw, len(frame.raw))
        dst_buf = ctypes.create_string_buffer(dst_w * dst_h * 4)
        src_bmp = ctypes.c_void_p(0)
        dst_bmp = ctypes.c_void_p(0)
        gfx = ctypes.c_void_p(0)
        try:
            st = gdip.GdipCreateBitmapFromScan0(
                frame.width, frame.height, frame.width * 4, _PIXEL_FORMAT_32BPP_RGB, src_buf, ctypes.byref(src_bmp)
            )
            if st != 0 or not src_bmp.value:
                raise RuntimeError(f"GdipCreateBitmapFromScan0(src) failed ({st})")
            st = gdip.GdipCreateBitmapFromScan0(
                dst_w, dst_h, dst_w * 4, _PIXEL_FORMAT_32BPP_RGB, dst_buf, ctypes.byref(dst_bmp)
            )
            if st != 0 or not dst_bmp.value:
                raise RuntimeError(f"GdipCreateBitmapFromScan0(dst) failed ({st})")
            st = gdip.GdipGetImageGraphicsContext(dst_bmp, ctypes.byref(gfx))
            if st != 0 or not gfx.value:
                raise RuntimeError(f"GdipGetImageGraphicsContext failed ({st})")
            gdip.GdipSetInterpolationMode(gfx, _INTERPOLATION_BILINEAR)
            st = gdip.GdipDrawImageRectI(gfx, src_bmp, 0, 0, dst_w, dst_h)
            if st != 0:
                raise RuntimeError(f"GdipDrawImageRectI failed ({st})")
            gdip.GdipFlush(gfx, 1)
            return _RawBGRXFrame(dst_w, dst_h, dst_buf.raw)
        finally:
            if gfx.value:
                gdip.GdipDeleteGraphics(gfx)
            if dst_bmp.value:
                gdip.GdipDisposeImage(dst_bmp)
            if src_bmp.value:
                gdip.GdipDisposeImage(src_bmp)

    @classmethod
    def encode_jpeg(cls, frame: _RawBGRXFrame, quality: int = 75) -> bytes:
        cls._ensure_ready()
        gdip = ctypes.windll.gdiplus
        ole32 = ctypes.windll.ole32
        kernel32 = ctypes.windll.kernel32

        q_val = ctypes.c_ulong(max(35, min(95, int(quality))))
        ep = _EncoderParameters()
        ep.Count = 1
        ep.Parameter[0].Guid = _GUID_ENCODER_QUALITY
        ep.Parameter[0].NumberOfValues = 1
        ep.Parameter[0].Type = _ENCODER_PARAM_LONG
        ep.Parameter[0].Value = ctypes.cast(ctypes.pointer(q_val), ctypes.c_void_p)

        src_buf = ctypes.create_string_buffer(frame.raw, len(frame.raw))
        src_bmp = ctypes.c_void_p(0)
        pstream = ctypes.c_void_p(0)
        try:
            st = gdip.GdipCreateBitmapFromScan0(
                frame.width, frame.height, frame.width * 4, _PIXEL_FORMAT_32BPP_RGB, src_buf, ctypes.byref(src_bmp)
            )
            if st != 0 or not src_bmp.value:
                raise RuntimeError(f"GdipCreateBitmapFromScan0 failed ({st})")

            hr = ole32.CreateStreamOnHGlobal(None, True, ctypes.byref(pstream))
            if hr != 0 or not pstream.value:
                raise RuntimeError(f"CreateStreamOnHGlobal failed (0x{hr & 0xFFFFFFFF:08X})")

            st = gdip.GdipSaveImageToStream(
                src_bmp, pstream, ctypes.byref(_CLSID_JPEG_ENCODER), ctypes.byref(ep)
            )
            if st != 0:
                raise RuntimeError(f"GdipSaveImageToStream JPEG failed ({st})")

            # Lấy độ dài byte chính xác qua IStream::Seek(0, STREAM_SEEK_CUR, &pos) (vtable slot 5)
            vtable = ctypes.cast(
                ctypes.cast(pstream, ctypes.POINTER(ctypes.c_void_p))[0],
                ctypes.POINTER(ctypes.c_void_p),
            )
            SEEK_FN = ctypes.WINFUNCTYPE(
                ctypes.c_long,
                ctypes.c_void_p,
                ctypes.c_int64,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint64),
            )
            cur_pos = ctypes.c_uint64(0)
            hr_seek = SEEK_FN(vtable[5])(pstream, 0, _STREAM_SEEK_CUR, ctypes.byref(cur_pos))

            hglob = ctypes.c_void_p(0)
            hr_hg = ole32.GetHGlobalFromStream(pstream, ctypes.byref(hglob))
            if hr_hg != 0 or not hglob.value:
                raise RuntimeError(f"GetHGlobalFromStream failed (0x{hr_hg & 0xFFFFFFFF:08X})")

            byte_len = int(cur_pos.value) if hr_seek == 0 and cur_pos.value > 0 else int(kernel32.GlobalSize(hglob))
            ptr = kernel32.GlobalLock(hglob)
            if not ptr:
                raise RuntimeError("GlobalLock on JPEG stream failed")
            try:
                return ctypes.string_at(ptr, byte_len)
            finally:
                kernel32.GlobalUnlock(hglob)
        finally:
            if pstream.value:
                try:
                    vtable = ctypes.cast(
                        ctypes.cast(pstream, ctypes.POINTER(ctypes.c_void_p))[0],
                        ctypes.POINTER(ctypes.c_void_p),
                    )
                    RELEASE_FN = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
                    RELEASE_FN(vtable[2])(pstream)
                except Exception:
                    pass
            if src_bmp.value:
                gdip.GdipDisposeImage(src_bmp)


class XPGdiCapturer:
    """
    Bộ chụp màn hình GDI tái sử dụng buffer RAM để giảm cấp phát bộ nhớ trên máy XP RAM thấp.
    Ưu tiên xử lý qua Pillow (PIL); nếu môi trường XP thiếu CRT/SSE2 không nạp được PIL thì tự động
    chuyển sang nhánh dự phòng Win32 GDI+ (gdiplus.dll) có sẵn trong Windows XP.
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
          (frame_or_pil_image, left, top, width, height, desktop_name)
        """
        global _LOGGED_FALLBACK_NOTICE
        if Image is None and not _LOGGED_FALLBACK_NOTICE:
            _LOGGED_FALLBACK_NOTICE = True
            xp_log(
                f"[Capture] Pillow (PIL) unavailable ({_PIL_IMPORT_ERROR}); "
                "using native Win32 GDI+ JPEG capture fallback."
            )

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

            raw_bytes = buf.raw[:raw_len]
            if Image is not None:
                # Chuyển trực tiếp BGRX -> RGB trong C của Pillow (không cần numpy/cv2)
                img = Image.frombuffer("RGB", (w, h), raw_bytes, "raw", "BGRX", 0, 1 if top_down else -1)
                img = img.copy()
                return img, left, top, w, h, desk_name

            # Nhánh dự phòng thuần Win32 GDI+ (khi máy XP không nạp được PIL)
            if not top_down:
                stride = w * 4
                mv = memoryview(raw_bytes)
                raw_bytes = b"".join(mv[y * stride : (y + 1) * stride].tobytes() for y in range(h - 1, -1, -1))
            return _RawBGRXFrame(w, h, raw_bytes), left, top, w, h, desk_name
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
        if isinstance(img, _RawBGRXFrame):
            return _Win32GdiPlusFallback.resize_frame(img, final_w, final_h)
        resample = getattr(Image, "BILINEAR", 2)
        return img.resize((final_w, final_h), resample)
    return img


def _compute_dirty_rect_raw(cur_frame: _RawBGRXFrame, prev_frame: _RawBGRXFrame):
    if cur_frame.raw == prev_frame.raw:
        return "static", None
    fw, fh = cur_frame.width, cur_frame.height
    stride = fw * 4
    mv_cur = memoryview(cur_frame.raw)
    mv_prev = memoryview(prev_frame.raw)

    y0 = -1
    for y in range(fh):
        rs = y * stride
        if mv_cur[rs : rs + stride] != mv_prev[rs : rs + stride]:
            y0 = y
            break
    if y0 < 0:
        return "static", None

    y1 = y0
    for y in range(fh - 1, y0 - 1, -1):
        rs = y * stride
        if mv_cur[rs : rs + stride] != mv_prev[rs : rs + stride]:
            y1 = y
            break

    changed_h = y1 - y0 + 1
    if changed_h >= int(fh * 0.75):
        return "full", None

    # Dò biên trái/phải theo khối 32 pixel (128 byte) để cực nhẹ CPU trên máy XP
    block_px = 32
    block_bytes = block_px * 4
    n_blocks = (fw + block_px - 1) // block_px
    min_bx = n_blocks
    max_bx = -1
    for y in range(y0, y1 + 1):
        rs = y * stride
        if mv_cur[rs : rs + stride] == mv_prev[rs : rs + stride]:
            continue
        for bx in range(min_bx):
            bs = rs + bx * block_bytes
            be = min(rs + stride, bs + block_bytes)
            if mv_cur[bs:be] != mv_prev[bs:be]:
                min_bx = bx
                break
        for bx in range(n_blocks - 1, max_bx, -1):
            bs = rs + bx * block_bytes
            be = min(rs + stride, bs + block_bytes)
            if mv_cur[bs:be] != mv_prev[bs:be]:
                max_bx = bx
                break

    if max_bx < min_bx:
        return "static", None

    x0 = max(0, min_bx * block_px - 2)
    x1 = min(fw, (max_bx + 1) * block_px + 2)
    y0 = max(0, y0 - 2)
    y1 = min(fh, y1 + 3)
    if (x1 - x0) * (y1 - y0) < (fw * fh * 0.70):
        return "partial", (x0, y0, x1, y1)
    return "full", None


def compute_dirty_rect(cur_img, prev_img):
    """
    So sánh khung hình mới với khung trước bằng Pillow ImageChops (C speed) hoặc bộ so sánh BGRX:
      - Trả về ('static', None) nếu khung hình đứng yên 100%.
      - Trả về ('partial', (x0, y0, x1, y1)) nếu vùng thay đổi < 70% diện tích màn hình.
      - Trả về ('full', None) nếu thay đổi lớn hoặc kích thước thay đổi.
    """
    if prev_img is None or prev_img.size != cur_img.size:
        return "full", None
    if isinstance(cur_img, _RawBGRXFrame) and isinstance(prev_img, _RawBGRXFrame):
        return _compute_dirty_rect_raw(cur_img, prev_img)
    if ImageChops is None:
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
    if isinstance(img, _RawBGRXFrame):
        return _Win32GdiPlusFallback.encode_jpeg(img, quality=q)
    bio = io.BytesIO()
    # subsampling=2 (4:2:0) cho chế độ tốc độ, subsampling=0 (4:4:4) khi Q>=75 cho chữ sắc nét
    subsampling = 2 if quality_mode == "speed" or q < 75 else 0
    try:
        img.save(bio, format="JPEG", quality=q, subsampling=subsampling)
    except TypeError:
        img.save(bio, format="JPEG", quality=q)
    return bio.getvalue()
