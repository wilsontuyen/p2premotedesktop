# -*- coding: utf-8 -*-
"""
xp_host/xp_clipboard.py
Đồng bộ Clipboard Văn bản & Copy-Paste File 2 chiều (Win 10/11 Client <-> Windows XP Host)
tương thích 100% giao thức gói tin của os_utils/windows_clipboard.py nhưng thiết kế riêng cho nhân XP:

1. Lắng nghe Clipboard bằng SetClipboardViewer (WM_DRAWCLIPBOARD / WM_CHANGECBCHAIN)
   thay cho AddClipboardFormatListener / WM_CLIPBOARDUPDATE (chỉ có từ Windows Vista+).
2. KHÔNG dùng Delayed Rendering SetClipboardData(CF_HDROP, NULL) vì giữ khóa Clipboard chờ mạng
   trên XP sẽ làm treo cứng toàn bộ Taskbar & Desktop của explorer.exe.
   Thay vào đó, khi nhận files_copied_meta từ Client:
     - Tạo file mồi 0 byte trong %TEMP%\\RemoteDesktopTransfers\\_xp_offer_stub và đặt CF_HDROP thật
       để nút 'Paste' chuột phải trên Explorer XP sáng lên ngay lập tức mà không bao giờ khóa Explorer.
     - Khi người dùng nhấn Ctrl+V / Shift+Insert hoặc bấm 'Paste' trên menu chuột phải (#32768),
       tự động dò thư mục Explorer XP đang mở (qua ComboBoxEx32 Address Bar + COM Shell.Application
       + CSIDL_DESKTOPDIRECTORY), gửi request_files tải thẳng luồng chunk vào thư mục đích kèm
       cửa sổ tiến trình Tkinter nhẹ, dọn sạch file mồi 0 byte và gọi SHChangeNotify làm tươi Explorer!
"""

import base64
import ctypes
from ctypes import wintypes
import json
import os
import queue
import shutil
import sys
import tempfile
import threading
import time

from .xp_capture import attach_thread_to_active_desktop
from .xp_config import xp_log
from .xp_socket import is_lan_socket, send_msg, socket_passwords, tune_socket_for_xp_lan

CLIPBOARD_PKT_TYPES = (
    "batch_start", "file_start", "file_chunk", "file_end", "batch_end",
    "files_copied_meta", "request_files", "cancel_transfer", "cancel_ack",
    "clipboard_text", "clipboard_image", "clear_clipboard",
    "resume_query", "resume_state",
    "paste_conflict_query", "paste_conflict_reply",
    "upload_progress_ack",
)

CF_TEXT = 1
CF_UNICODETEXT = 13
CF_HDROP = 15
GHND = 0x0042

WM_DESTROY = 0x0002
WM_DRAWCLIPBOARD = 0x0308
WM_CHANGECBCHAIN = 0x030D
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E
MN_GETHMENU = 0x01E1

CSIDL_DESKTOPDIRECTORY = 0x0010
CSIDL_PERSONAL = 0x0005  # My Documents on XP

SHCNE_CREATE = 0x00000002
SHCNE_UPDATEDIR = 0x00001000
SHCNF_PATHW = 0x0005
SHCNF_FLUSH = 0x1000


class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),
    ]


WPARAM_T = ctypes.c_size_t
LPARAM_T = ctypes.c_ssize_t
LRESULT_T = ctypes.c_ssize_t

if sys.platform == "win32":
    WNDPROCTYPE = ctypes.WINFUNCTYPE(LRESULT_T, wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T)

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROCTYPE),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
            ("hIconSm", wintypes.HICON),
        ]

    _k32 = ctypes.WinDLL("kernel32.dll")
    _u32 = ctypes.WinDLL("user32.dll")
    _s32 = ctypes.WinDLL("shell32.dll")

    _k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    _k32.GlobalAlloc.restype = wintypes.HGLOBAL
    _k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    _k32.GlobalLock.restype = ctypes.c_void_p
    _k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    _k32.GlobalUnlock.restype = wintypes.BOOL
    _k32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    _k32.GlobalFree.restype = wintypes.HGLOBAL

    _u32.OpenClipboard.argtypes = [wintypes.HWND]
    _u32.OpenClipboard.restype = wintypes.BOOL
    _u32.CloseClipboard.argtypes = []
    _u32.CloseClipboard.restype = wintypes.BOOL
    _u32.EmptyClipboard.argtypes = []
    _u32.EmptyClipboard.restype = wintypes.BOOL
    _u32.GetClipboardData.argtypes = [wintypes.UINT]
    _u32.GetClipboardData.restype = wintypes.HANDLE
    _u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    _u32.SetClipboardData.restype = wintypes.HANDLE
    _u32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    _u32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    _u32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T]
    _u32.DefWindowProcW.restype = LRESULT_T
    _u32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, WPARAM_T, LPARAM_T]
    _u32.SendMessageW.restype = LRESULT_T

    _s32.DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    _s32.DragQueryFileW.restype = wintypes.UINT
else:  # pragma: no cover
    _k32 = _u32 = _s32 = None


def _get_staging_base():
    tmp = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
    d = os.path.join(tmp, "RemoteDesktopTransfers")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _get_stub_dir():
    d = os.path.join(_get_staging_base(), "_xp_offer_stub")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def get_clipboard_seq():
    if not _u32:
        return 0
    try:
        return int(_u32.GetClipboardSequenceNumber())
    except Exception:
        return 0


# ==============================================================================
# Win32 Clipboard Read / Write Helpers (try...finally CloseClipboard guaranteed)
# ==============================================================================
def xp_get_clipboard_text():
    if not _u32:
        return ""
    attach_thread_to_active_desktop()
    if not _u32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return ""
    opened = False
    for _ in range(5):
        if _u32.OpenClipboard(0):
            opened = True
            break
        time.sleep(0.02)
    if not opened:
        return ""
    try:
        h_data = _u32.GetClipboardData(CF_UNICODETEXT)
        if not h_data:
            return ""
        ptr = _k32.GlobalLock(h_data)
        if not ptr:
            return ""
        try:
            return ctypes.wstring_at(ptr)
        finally:
            _k32.GlobalUnlock(h_data)
    except Exception:
        return ""
    finally:
        _u32.CloseClipboard()


def xp_set_clipboard_text(text, hwnd=0):
    if not _u32 or text is None:
        return False
    attach_thread_to_active_desktop()
    raw = (str(text) + "\x00").encode("utf-16-le")
    opened = False
    for _ in range(6):
        if _u32.OpenClipboard(hwnd or 0):
            opened = True
            break
        time.sleep(0.02)
    if not opened:
        return False
    try:
        _u32.EmptyClipboard()
        h_mem = _k32.GlobalAlloc(GHND, len(raw))
        if not h_mem:
            return False
        ptr = _k32.GlobalLock(h_mem)
        if not ptr:
            _k32.GlobalFree(h_mem)
            return False
        ctypes.memmove(ptr, raw, len(raw))
        _k32.GlobalUnlock(h_mem)
        if not _u32.SetClipboardData(CF_UNICODETEXT, h_mem):
            _k32.GlobalFree(h_mem)
            return False
        return True
    finally:
        _u32.CloseClipboard()


def xp_get_clipboard_files():
    if not _u32 or not _u32.IsClipboardFormatAvailable(CF_HDROP):
        return []
    attach_thread_to_active_desktop()
    opened = False
    for _ in range(5):
        if _u32.OpenClipboard(0):
            opened = True
            break
        time.sleep(0.02)
    if not opened:
        return []
    files = []
    try:
        h_drop = _u32.GetClipboardData(CF_HDROP)
        if not h_drop:
            return []
        ptr = _k32.GlobalLock(h_drop)
        if not ptr:
            return []
        try:
            count = _s32.DragQueryFileW(ptr, 0xFFFFFFFF, None, 0)
            for i in range(count):
                length = _s32.DragQueryFileW(ptr, i, None, 0)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 2)
                    _s32.DragQueryFileW(ptr, i, buf, length + 2)
                    if buf.value:
                        files.append(buf.value)
        finally:
            _k32.GlobalUnlock(h_drop)
    except Exception:
        pass
    finally:
        _u32.CloseClipboard()
    return files


def xp_set_clipboard_files(paths, hwnd=0):
    """Đặt CF_HDROP thật kèm Preferred DropEffect = DROPEFFECT_COPY (1) — không bao giờ khóa Explorer."""
    if not _u32 or not paths:
        return False
    attach_thread_to_active_desktop()
    joined = "\x00".join(os.path.abspath(p) for p in paths) + "\x00\x00"
    str_bytes = joined.encode("utf-16-le")
    df_size = ctypes.sizeof(DROPFILES)
    total_bytes = df_size + len(str_bytes)

    opened = False
    for _ in range(6):
        if _u32.OpenClipboard(hwnd or 0):
            opened = True
            break
        time.sleep(0.02)
    if not opened:
        return False
    try:
        _u32.EmptyClipboard()
        h_mem = _k32.GlobalAlloc(GHND, total_bytes)
        if not h_mem:
            return False
        ptr = _k32.GlobalLock(h_mem)
        if not ptr:
            _k32.GlobalFree(h_mem)
            return False
        df = DROPFILES()
        df.pFiles = df_size
        df.fWide = 1
        ctypes.memmove(ptr, ctypes.byref(df), df_size)
        ctypes.memmove(ptr + df_size, str_bytes, len(str_bytes))
        _k32.GlobalUnlock(h_mem)
        if not _u32.SetClipboardData(CF_HDROP, h_mem):
            _k32.GlobalFree(h_mem)
            return False

        # Thiết lập Preferred DropEffect = Copy (1)
        cf_effect = _u32.RegisterClipboardFormatW(ctypes.c_wchar_p("Preferred DropEffect"))
        if cf_effect:
            h_eff = _k32.GlobalAlloc(GHND, 4)
            if h_eff:
                p_eff = _k32.GlobalLock(h_eff)
                if p_eff:
                    ctypes.memmove(p_eff, ctypes.byref(wintypes.DWORD(1)), 4)
                    _k32.GlobalUnlock(h_eff)
                    if not _u32.SetClipboardData(cf_effect, h_eff):
                        _k32.GlobalFree(h_eff)
                else:
                    _k32.GlobalFree(h_eff)
        return True
    finally:
        _u32.CloseClipboard()


def xp_clear_clipboard(hwnd=0):
    if not _u32:
        return
    attach_thread_to_active_desktop()
    if _u32.OpenClipboard(hwnd or 0):
        try:
            _u32.EmptyClipboard()
        finally:
            _u32.CloseClipboard()


# ==============================================================================
# Windows XP Explorer Active Folder Detection (Desktop + Address Bar + Shell COM)
# ==============================================================================
def get_xp_special_folder(csidl=CSIDL_DESKTOPDIRECTORY):
    if not _s32:
        return os.path.expanduser("~")
    buf = ctypes.create_unicode_buffer(520)
    if _s32.SHGetFolderPathW(0, csidl, 0, 0, buf) == 0 and buf.value and os.path.isdir(buf.value):
        return os.path.normpath(buf.value)
    user_prof = os.environ.get("USERPROFILE") or r"C:\Documents and Settings\Administrator"
    desk = os.path.join(user_prof, "Desktop")
    return desk if os.path.isdir(desk) else _get_staging_base()


def _hwnd_class(hwnd):
    if not _u32 or not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(128)
    _u32.GetClassNameW(hwnd, buf, 128)
    return buf.value or ""


def _hwnd_text(hwnd):
    if not _u32 or not hwnd:
        return ""
    res = ctypes.c_size_t(0)
    if _u32.SendMessageTimeoutW(hwnd, WM_GETTEXTLENGTH, 0, 0, 0x0002, 150, ctypes.byref(res)):
        ln = int(res.value)
        if 0 < ln < 2048:
            buf = ctypes.create_unicode_buffer(ln + 2)
            _u32.SendMessageTimeoutW(hwnd, WM_GETTEXT, ln + 2, ctypes.addressof(buf), 0x0002, 150, ctypes.byref(res))
            if buf.value:
                return buf.value.strip()
    buf2 = ctypes.create_unicode_buffer(520)
    _u32.GetWindowTextW(hwnd, buf2, 520)
    return (buf2.value or "").strip()


def query_xp_explorer_folder_path():
    """
    Xác định thư mục đích nơi người dùng vừa bấm Ctrl+V hoặc chuột phải Paste trên Windows XP:
      1. Nếu đang focus Desktop XP (Progman / WorkerW chứa SHELLDLL_DefView) -> trả về Desktop XP.
      2. Nếu đang focus cửa sổ Explorer XP (CabinetWClass / ExploreWClass):
         - Thử đọc qua COM Shell.Application (chính xác 100% kể cả khi XP ẩn full path trên tiêu đề).
         - Thử đọc thanh địa chỉ ComboBoxEx32 -> ComboBox -> Edit trên cây cửa sổ Win32.
         - Thử đối chiếu tiêu đề cửa sổ với đường dẫn ổ đĩa / My Documents / Desktop.
    """
    if not _u32:
        return _get_staging_base()
    attach_thread_to_active_desktop()

    fg = _u32.GetForegroundWindow()
    if not fg:
        return get_xp_special_folder(CSIDL_DESKTOPDIRECTORY)

    root = _u32.GetAncestor(fg, 2) or fg  # GA_ROOT = 2
    r_cls = _hwnd_class(root)

    # 1. Màn hình Desktop của Windows XP
    if r_cls == "Progman":
        return get_xp_special_folder(CSIDL_DESKTOPDIRECTORY)
    if r_cls == "WorkerW":
        if _u32.FindWindowExW(root, 0, ctypes.c_wchar_p("SHELLDLL_DefView"), None):
            return get_xp_special_folder(CSIDL_DESKTOPDIRECTORY)

    # Nếu đang mở menu chuột phải (#32768), kiểm tra cửa sổ dưới con trỏ chuột
    if r_cls == "#32768":
        pt = wintypes.POINT()
        if _u32.GetCursorPos(ctypes.byref(pt)):
            under = _u32.WindowFromPoint(pt)
            if under:
                u_root = _u32.GetAncestor(under, 2) or under
                u_cls = _hwnd_class(u_root)
                if u_cls == "Progman":
                    return get_xp_special_folder(CSIDL_DESKTOPDIRECTORY)
                if u_cls in ("CabinetWClass", "ExploreWClass"):
                    root = u_root
                    r_cls = u_cls

    if r_cls in ("CabinetWClass", "ExploreWClass"):
        # 2A. Thử COM Shell.Application (nếu có pywin32 / comtypes trong user context)
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            shell = win32com.client.Dispatch("Shell.Application")
            for w in shell.Windows():
                try:
                    if int(w.HWND) == int(root):
                        p = str(w.Document.Folder.Self.Path or "").strip()
                        if p and os.path.isdir(p):
                            return os.path.normpath(p)
                except Exception:
                    continue
        except Exception:
            pass

        # 2B. Đọc thanh địa chỉ ComboBoxEx32 -> ComboBox -> Edit bằng Win32 thuần (chạy được cả từ SYSTEM!)
        found_paths = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, LPARAM_T)

        def _enum_child(ch, _lp):
            cls = _hwnd_class(ch)
            if cls in ("Edit", "ComboBox", "ComboBoxEx32", "ToolbarWindow32"):
                txt = _hwnd_text(ch)
                if txt:
                    if (len(txt) >= 3 and txt[1:3] in (":\\", ":/")) or txt.startswith("\\\\"):
                        if os.path.isdir(txt):
                            found_paths.append(os.path.normpath(txt))
                            return False
            return True

        try:
            _u32.EnumChildWindows(root, WNDENUMPROC(_enum_child), 0)
        except Exception:
            pass
        if found_paths:
            return found_paths[0]

        # 2C. Kiểm tra tiêu đề cửa sổ Explorer XP
        title = _hwnd_text(root)
        if title:
            if (len(title) >= 3 and title[1:3] in (":\\", ":/")) or title.startswith("\\\\"):
                if os.path.isdir(title):
                    return os.path.normpath(title)
            low_t = title.lower()
            if low_t in ("my documents", "documents", "tài liệu"):
                return get_xp_special_folder(CSIDL_PERSONAL)
            if low_t in ("desktop", "màn hình nền"):
                return get_xp_special_folder(CSIDL_DESKTOPDIRECTORY)

    return get_xp_special_folder(CSIDL_DESKTOPDIRECTORY)


def _check_xp_menu_item_is_paste(pt_x, pt_y):
    """Kiểm tra cú click chuột trái trên menu ngữ cảnh cổ điển #32768 của XP có phải mục Paste / Dán không."""
    if not _u32:
        return False
    pt = wintypes.POINT(int(pt_x), int(pt_y))
    hwnd = _u32.WindowFromPoint(pt)
    if not hwnd:
        return False
    cls = _hwnd_class(hwnd)
    if cls != "#32768":
        parent = _u32.GetParent(hwnd)
        if not parent or _hwnd_class(parent) != "#32768":
            return False
        hwnd = parent

    hmenu = _u32.SendMessageW(hwnd, MN_GETHMENU, 0, 0)
    if not hmenu:
        return False
    idx = _u32.MenuItemFromPoint(0, wintypes.HMENU(hmenu), pt)
    if idx < 0:
        return False
    buf = ctypes.create_unicode_buffer(128)
    MF_BYPOSITION = 0x0400
    _u32.GetMenuStringW(wintypes.HMENU(hmenu), idx, buf, 128, MF_BYPOSITION)
    label = (buf.value or "").replace("&", "").strip().lower()
    if not label:
        return False
    if "shortcut" in label or "special" in label:
        return False
    paste_words = ("paste", "dán", "dan", "coller", "einfügen", "pegar", "вставить", "粘贴", "貼上", "貼り付け")
    return any(label == w or label.startswith(w + "\t") or label.startswith(w + " ") for w in paste_words)


def notify_xp_shell_created(paths):
    if not _s32 or not paths:
        return
    parent_dirs = set()
    for p in paths:
        if not p:
            continue
        ap = os.path.abspath(p)
        try:
            _s32.SHChangeNotify(SHCNE_CREATE, SHCNF_PATHW | SHCNF_FLUSH, ctypes.c_wchar_p(ap), None)
        except Exception:
            pass
        par = os.path.dirname(ap)
        if par:
            parent_dirs.add(par)
    for par in parent_dirs:
        try:
            _s32.SHChangeNotify(SHCNE_UPDATEDIR, SHCNF_PATHW | SHCNF_FLUSH, ctypes.c_wchar_p(par), None)
        except Exception:
            pass


# ==============================================================================
# Thread-safe Tkinter Transfer Progress Window for XP (Tahoma Classic Style)
# ==============================================================================
class XPProgressWindow:
    def __init__(self, root_tk, title, display_name, total_size, dest_dir, on_cancel):
        import tkinter as tk
        self.on_cancel = on_cancel
        self.total_size = max(1, int(total_size or 1))
        self.win = tk.Toplevel(root_tk)
        self.win.title(title)
        self.win.geometry("380x135")
        self.win.resizable(False, False)
        self.win.configure(bg="#ECE9D8")  # Màu nền chuẩn Luna Classic của Windows XP
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        self.win.protocol("WM_DELETE_WINDOW", self._cancel_clicked)

        lbl_font = ("Tahoma", 8)
        bold_font = ("Tahoma", 8, "bold")

        tk.Label(self.win, text=f"Đang tải: {display_name}", font=bold_font, bg="#ECE9D8", fg="#000000", anchor="w").pack(
            fill="x", padx=12, pady=(10, 2)
        )
        short_dest = dest_dir if len(str(dest_dir)) <= 48 else ("..." + str(dest_dir)[-45:])
        tk.Label(self.win, text=f"Thư mục đích: {short_dest}", font=lbl_font, bg="#ECE9D8", fg="#333333", anchor="w").pack(
            fill="x", padx=12, pady=(0, 6)
        )

        bar_frame = tk.Frame(self.win, bg="#FFFFFF", bd=1, relief="sunken", height=18)
        bar_frame.pack(fill="x", padx=12, pady=2)
        bar_frame.pack_propagate(False)
        self.bar_fill = tk.Frame(bar_frame, bg="#316AC5", width=0, height=16)
        self.bar_fill.pack(side="left", fill="y")
        self._bar_max_w = 352

        bottom = tk.Frame(self.win, bg="#ECE9D8")
        bottom.pack(fill="x", padx=12, pady=(8, 6))
        self.pct_lbl = tk.Label(bottom, text="0%", font=lbl_font, bg="#ECE9D8", fg="#000000")
        self.pct_lbl.pack(side="left")
        tk.Button(
            bottom, text="Hủy (Cancel)", font=lbl_font, width=12, bg="#ECE9D8", command=self._cancel_clicked
        ).pack(side="right")

    def _cancel_clicked(self):
        if callable(self.on_cancel):
            try:
                self.on_cancel()
            except Exception:
                pass
        self.close()

    def update_bytes(self, received_bytes):
        try:
            ratio = max(0.0, min(1.0, float(received_bytes) / float(self.total_size)))
            w = int(self._bar_max_w * ratio)
            self.bar_fill.configure(width=w)
            mb_cur = received_bytes / (1024.0 * 1024.0)
            mb_tot = self.total_size / (1024.0 * 1024.0)
            self.pct_lbl.configure(text=f"{int(ratio * 100)}% ({mb_cur:.1f} / {mb_tot:.1f} MB)")
        except Exception:
            pass

    def close(self):
        try:
            self.win.destroy()
        except Exception:
            pass


# ==============================================================================
# Main XP Clipboard & 2-Way File Copy-Paste Manager
# ==============================================================================
class XPClipboardSyncManager:
    def __init__(self, tk_root=None):
        self.tk_root = tk_root
        self.lock = threading.Lock()
        self.active_sockets = set()
        self._socket_order = []
        self.sock = None

        self._last_own_seq = 0
        self._last_seen_seq = 0
        self._last_sent_text = None
        self._clip_offer_id = 0
        self._copied_files_map = {}

        # Remote file offer state (Client Win10/11 -> Host XP)
        self.pending_remote_files = []
        self.pending_offer_id = 0
        self._stub_paths = []
        self._paste_seq = int(time.time() * 1000) % 800000000 + 100000000
        self._last_paste_ts = 0.0

        # Active incoming / outgoing transfer tracking
        self._xfer_jobs = {}
        self.incoming_transfers = {}
        self._cancelled_paste_ids = set()
        self._active_send_ids = set()
        self._send_xfer_seq = 0
        self._pkt_queue = queue.Queue()
        self.gui_queue = queue.Queue()
        self._dialogs = {}

        self.running = True
        self._hwnd = 0
        self._next_viewer = 0
        self._wndproc_ref = None

        threading.Thread(target=self._packet_worker_loop, daemon=True, name="XPClipPktWorker").start()
        if sys.platform == "win32":
            threading.Thread(target=self._win32_viewer_chain_loop, daemon=True, name="XPClipViewerChain").start()
            threading.Thread(target=self._xp_gesture_and_poll_loop, daemon=True, name="XPPasteGestureWatch").start()

    def bind_tk_root(self, tk_root):
        self.tk_root = tk_root

    def process_gui_queue(self):
        """Được gọi định kỳ từ root.after() của giao diện chính Tkinter (đảm bảo thread-safe 100%)."""
        if not self.tk_root:
            return
        while True:
            try:
                cmd, payload = self.gui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                if cmd == "open_dlg":
                    job_id, name, total, dest_dir = payload
                    if job_id not in self._dialogs:
                        self._dialogs[job_id] = XPProgressWindow(
                            self.tk_root,
                            "Truyền tệp từ xa (EasyRemoteDesktop XP)",
                            name,
                            total,
                            dest_dir,
                            on_cancel=lambda j=job_id: self.cancel_transfer(paste_id=j),
                        )
                elif cmd == "upd_dlg":
                    job_id, rec = payload
                    dlg = self._dialogs.get(job_id)
                    if dlg:
                        dlg.update_bytes(rec)
                elif cmd == "close_dlg":
                    dlg = self._dialogs.pop(payload, None)
                    if dlg:
                        dlg.close()
            except Exception:
                pass

    # ---------- Socket management ----------
    def add_socket(self, sock):
        if not sock:
            return
        with self.lock:
            self.active_sockets.add(sock)
            self._socket_order = [s for s in self._socket_order if s is not sock and s in self.active_sockets]
            self._socket_order.append(sock)
            self.sock = sock

    def remove_socket(self, sock):
        with self.lock:
            self.active_sockets.discard(sock)
            self._socket_order = [s for s in self._socket_order if s is not sock and s in self.active_sockets]
            self.sock = self._socket_order[-1] if self._socket_order else None

    def _broadcast_json(self, obj):
        raw = json.dumps(obj).encode("utf-8")
        with self.lock:
            socks = list(self.active_sockets)
        dead = []
        sent_any = False
        for s in socks:
            pw = socket_passwords.get(s)
            if send_msg(s, raw, pw):
                sent_any = True
            else:
                dead.append(s)
        for d in dead:
            self.remove_socket(d)
        return sent_any

    # ---------- Win32 SetClipboardViewer Chain (Windows XP Native) ----------
    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_CHANGECBCHAIN:
            if wparam == self._next_viewer:
                self._next_viewer = lparam
            elif self._next_viewer:
                _u32.SendMessageW(self._next_viewer, msg, wparam, lparam)
            return 0
        if msg == WM_DRAWCLIPBOARD:
            if self._next_viewer:
                try:
                    _u32.SendMessageW(self._next_viewer, msg, wparam, lparam)
                except Exception:
                    pass
            seq = get_clipboard_seq()
            if seq and seq != self._last_own_seq and seq != self._last_seen_seq:
                self._last_seen_seq = seq
                threading.Thread(target=self._handle_local_clipboard_change, daemon=True).start()
            return 0
        if msg == WM_DESTROY:
            if self._next_viewer:
                try:
                    _u32.ChangeClipboardChain(hwnd, self._next_viewer)
                except Exception:
                    pass
                self._next_viewer = 0
            return 0
        return _u32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _win32_viewer_chain_loop(self):
        try:
            attach_thread_to_active_desktop()
            h_inst = _k32.GetModuleHandleW(None)
            self._wndproc_ref = WNDPROCTYPE(self._wndproc)
            cls_name = f"ERD_XPClipViewer_{os.getpid()}"
            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.lpfnWndProc = self._wndproc_ref
            wc.hInstance = h_inst
            wc.lpszClassName = cls_name
            _u32.RegisterClassExW(ctypes.byref(wc))

            # Cửa sổ ẩn thường (không dùng HWND_MESSAGE để nhận đầy đủ WM_DRAWCLIPBOARD trên XP)
            self._hwnd = _u32.CreateWindowExW(
                0, cls_name, "ERD_XPClip", 0, 0, 0, 0, 0, 0, 0, h_inst, None
            )
            if self._hwnd:
                self._last_own_seq = get_clipboard_seq()
                self._next_viewer = _u32.SetClipboardViewer(self._hwnd)
                xp_log(f"[XPClipboard] SetClipboardViewer registered hwnd={self._hwnd}")
                msg = wintypes.MSG()
                while self.running and _u32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                    _u32.TranslateMessage(ctypes.byref(msg))
                    _u32.DispatchMessageW(ctypes.byref(msg))
        except Exception as e:
            xp_log(f"[XPClipboard] Viewer chain error: {e}")

    # ---------- Gesture & Backup Poll Loop (Ctrl+V / Shift+Ins / Menu Paste) ----------
    def _xp_gesture_and_poll_loop(self):
        ctrl_v_held = False
        shift_ins_held = False
        lmb_held = False
        last_rmb_time = 0.0
        last_poll_ts = 0.0

        while self.running:
            try:
                now = time.time()
                if not self.active_sockets:
                    time.sleep(0.3)
                    continue

                # Backup poll mỗi 0.5s phòng khi desktop vừa đổi Default <-> Winlogon
                if now - last_poll_ts >= 0.5:
                    last_poll_ts = now
                    seq = get_clipboard_seq()
                    if seq and seq != self._last_own_seq and seq != self._last_seen_seq:
                        self._last_seen_seq = seq
                        threading.Thread(target=self._handle_local_clipboard_change, daemon=True).start()

                if not self.pending_remote_files:
                    time.sleep(0.08)
                    continue

                # Theo dõi chuột phải (chuẩn bị mở menu ngữ cảnh #32768)
                if _u32.GetAsyncKeyState(0x02) & 0x8000:
                    last_rmb_time = now

                # Theo dõi click trái vào mục 'Paste' / 'Dán' trên menu chuột phải XP (#32768)
                if _u32.GetAsyncKeyState(0x01) & 0x8000:
                    if not lmb_held:
                        lmb_held = True
                        if (now - last_rmb_time) < 10.0:
                            pt = wintypes.POINT()
                            if _u32.GetCursorPos(ctypes.byref(pt)) and _check_xp_menu_item_is_paste(pt.x, pt.y):
                                dest = query_xp_explorer_folder_path()
                                threading.Thread(
                                    target=self.trigger_remote_file_paste,
                                    args=(dest, "xp_context_menu"),
                                    daemon=True,
                                ).start()
                else:
                    lmb_held = False

                # Theo dõi phím tắt Ctrl + V
                is_ctrl_v = bool((_u32.GetAsyncKeyState(0x11) & 0x8000) and (_u32.GetAsyncKeyState(0x56) & 0x8000))
                if is_ctrl_v:
                    if not ctrl_v_held:
                        ctrl_v_held = True
                        dest = query_xp_explorer_folder_path()
                        threading.Thread(
                            target=self.trigger_remote_file_paste,
                            args=(dest, "ctrl_v"),
                            daemon=True,
                        ).start()
                else:
                    ctrl_v_held = False

                # Theo dõi phím tắt Shift + Insert
                is_shift_ins = bool((_u32.GetAsyncKeyState(0x10) & 0x8000) and (_u32.GetAsyncKeyState(0x2D) & 0x8000))
                if is_shift_ins:
                    if not shift_ins_held:
                        shift_ins_held = True
                        dest = query_xp_explorer_folder_path()
                        threading.Thread(
                            target=self.trigger_remote_file_paste,
                            args=(dest, "shift_ins"),
                            daemon=True,
                        ).start()
                else:
                    shift_ins_held = False

            except Exception:
                pass
            time.sleep(0.03)

    # ---------- Local Copy on XP -> Send to Win10/11 Client ----------
    def _is_our_stub_files(self, paths):
        stub_dir = os.path.normcase(os.path.abspath(_get_stub_dir()))
        for p in paths:
            try:
                if os.path.normcase(os.path.abspath(p)).startswith(stub_dir):
                    return True
            except Exception:
                pass
        return False

    def _handle_local_clipboard_change(self):
        if not self.active_sockets:
            return
        files = xp_get_clipboard_files()
        if files:
            if self._is_our_stub_files(files):
                return
            # Người dùng vừa Copy file thật trên máy XP -> hủy offer cũ từ Client và gửi metadata sang Client
            self.pending_remote_files = []
            metadata = self._scan_local_files_for_meta(files)
            if metadata:
                self._clip_offer_id += 1
                self._last_sent_text = None
                self._broadcast_json({
                    "type": "files_copied_meta",
                    "files": metadata,
                    "offer_id": self._clip_offer_id,
                })
                xp_log(f"[XPClipboard] Sent files_copied_meta ({len(metadata)} items) to Client")
            return

        txt = xp_get_clipboard_text()
        if txt and txt != self._last_sent_text:
            self.pending_remote_files = []
            self._last_sent_text = txt
            self._broadcast_json({"type": "clipboard_text", "text": txt})

    def _scan_local_files_for_meta(self, paths):
        metadata = []
        name_map = {}
        for f in paths:
            if not f or not os.path.exists(f):
                continue
            try:
                if os.path.isfile(f):
                    sz = os.path.getsize(f)
                    mt = os.path.getmtime(f)
                    bn = os.path.basename(f)
                    entry = {"path": f, "name": bn, "size": sz, "mtime": mt}
                    metadata.append(entry)
                    name_map[bn] = f
                    name_map[os.path.normcase(bn)] = f
                elif os.path.isdir(f):
                    base_parent = os.path.dirname(os.path.abspath(f))
                    for root, _dirs, fnames in os.walk(f):
                        for fn in fnames:
                            full = os.path.join(root, fn)
                            if os.path.isfile(full):
                                rel = os.path.relpath(full, base_parent).replace("\\", "/")
                                sz = os.path.getsize(full)
                                mt = os.path.getmtime(full)
                                metadata.append({"path": full, "name": rel, "size": sz, "mtime": mt})
                                name_map[rel] = full
                                name_map[os.path.normcase(rel)] = full
            except Exception:
                continue
        if name_map:
            self._copied_files_map.update(name_map)
        return metadata

    # ---------- Remote Offer Arm & Paste Trigger (Win10/11 Client -> XP) ----------
    def _arm_remote_file_offer(self, files, offer_id):
        if not files:
            return
        self.pending_remote_files = list(files)
        self.pending_offer_id = int(offer_id or 0)

        # Tạo 1 file mồi rỗng trong _xp_offer_stub để nút 'Paste' chuột phải của Explorer XP sáng lên
        stub_dir = _get_stub_dir()
        try:
            for old_name in os.listdir(stub_dir):
                old_p = os.path.join(stub_dir, old_name)
                try:
                    if os.path.isdir(old_p):
                        shutil.rmtree(old_p, ignore_errors=True)
                    else:
                        os.remove(old_p)
                except Exception:
                    pass
        except Exception:
            pass

        top_names = []
        for item in files:
            raw_name = str((item.get("name") if isinstance(item, dict) else item) or "").replace("\\", "/").strip("/")
            if not raw_name:
                continue
            top = raw_name.split("/")[0]
            if top and top not in top_names:
                top_names.append(top)

        stub_paths = []
        for top in top_names[:16]:
            sp = os.path.join(stub_dir, f".erd_fetching_{top}.tmp")
            try:
                with open(sp, "wb"):
                    pass
                ctypes.windll.kernel32.SetFileAttributesW(ctypes.c_wchar_p(sp), 0x02)  # FILE_ATTRIBUTE_HIDDEN
                stub_paths.append(sp)
            except Exception:
                pass

        if stub_paths:
            self._stub_paths = stub_paths
            if xp_set_clipboard_files(stub_paths, self._hwnd):
                self._last_own_seq = get_clipboard_seq()
                self._last_seen_seq = self._last_own_seq

    def _scrub_stub_in_dest(self, dest_dir):
        if not dest_dir or not os.path.isdir(dest_dir):
            return
        try:
            for fn in os.listdir(dest_dir):
                if fn.startswith(".erd_fetching_") and fn.endswith(".tmp"):
                    fp = os.path.join(dest_dir, fn)
                    try:
                        ctypes.windll.kernel32.SetFileAttributesW(ctypes.c_wchar_p(fp), 0x80)
                        os.remove(fp)
                    except Exception:
                        pass
        except Exception:
            pass

    def trigger_remote_file_paste(self, dest_dir, reason="ctrl_v"):
        now = time.time()
        with self.lock:
            if not self.pending_remote_files or (now - self._last_paste_ts) < 0.8:
                return
            self._last_paste_ts = now
            self._paste_seq += 1
            paste_id = self._paste_seq
            req_files = list(self.pending_remote_files)
            sock = self.sock

        if not sock:
            return
        if not dest_dir or not os.path.isdir(dest_dir):
            dest_dir = get_xp_special_folder(CSIDL_DESKTOPDIRECTORY)

        # Dọn file mồi ẩn .erd_fetching_*.tmp nếu Explorer XP vừa chép sang dest_dir
        threading.Timer(0.25, lambda: self._scrub_stub_in_dest(dest_dir)).start()
        threading.Timer(1.0, lambda: self._scrub_stub_in_dest(dest_dir)).start()

        total_sz = sum(int(f.get("size") or 0) for f in req_files if isinstance(f, dict))
        first_name = str((req_files[0].get("name") if isinstance(req_files[0], dict) else req_files[0]) or "Files")
        disp = first_name.split("/")[0] if len(req_files) == 1 else f"{len(req_files)} tệp ({first_name.split('/')[0]}...)"

        with self.lock:
            self._xfer_jobs[paste_id] = {
                "paste_id": paste_id,
                "dest_dir": dest_dir,
                "total": total_sz,
                "received": 0,
                "display_name": disp,
                "paths": [],
            }

        self.gui_queue.put(("open_dlg", (paste_id, disp, total_sz, dest_dir)))
        pw = socket_passwords.get(sock)
        pkt = json.dumps({
            "type": "request_files",
            "files": req_files,
            "paste_id": paste_id,
        }).encode("utf-8")
        send_msg(sock, pkt, pw)
        xp_log(f"[XPClipboard] Requested {len(req_files)} files -> dest={dest_dir} (paste_id={paste_id}, via={reason})")

    def cancel_transfer(self, paste_id=None, remote_triggered=False):
        if paste_id is not None:
            self._cancelled_paste_ids.add(int(paste_id))
            self.gui_queue.put(("close_dlg", int(paste_id)))
        for k, tr in list(self.incoming_transfers.items()):
            try:
                if tr.get("handle"):
                    tr["handle"].close()
                if tr.get("path") and os.path.exists(tr["path"]):
                    os.remove(tr["path"])
            except Exception:
                pass
            self.incoming_transfers.pop(k, None)
        if not remote_triggered:
            self._broadcast_json({"type": "cancel_transfer", "paste_id": paste_id})

    # ---------- Packet Queue & Incoming / Outgoing Streaming ----------
    def enqueue_packet(self, packet):
        self._pkt_queue.put(packet)

    def _packet_worker_loop(self):
        while self.running:
            try:
                pkt = self._pkt_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._handle_packet(pkt)
            except Exception as e:
                xp_log(f"[XPClipboard] Packet error: {e}")

    def _safe_rel_path(self, raw_name):
        """Chống Path Traversal tuyệt đối khi nhận file từ mạng."""
        clean = str(raw_name or "").replace("\\", "/").lstrip("/")
        parts = [p for p in clean.split("/") if p and p not in (".", "..") and ":" not in p]
        return os.path.join(*parts) if parts else ""

    def _handle_packet(self, packet):
        peer_sock = packet.pop("_peer_sock", None) if isinstance(packet, dict) else None
        if peer_sock is not None:
            self.add_socket(peer_sock)

        ptype = packet.get("type")
        if ptype == "clipboard_text":
            txt = packet.get("text", "")
            if txt:
                self._last_sent_text = txt
                if xp_set_clipboard_text(txt, self._hwnd):
                    self._last_own_seq = get_clipboard_seq()
                    self._last_seen_seq = self._last_own_seq
            return

        if ptype == "clear_clipboard":
            self.pending_remote_files = []
            xp_clear_clipboard(self._hwnd)
            self._last_own_seq = get_clipboard_seq()
            return

        if ptype == "files_copied_meta":
            self._arm_remote_file_offer(packet.get("files") or [], packet.get("offer_id"))
            return

        if ptype == "cancel_transfer":
            pid = packet.get("paste_id")
            self.cancel_transfer(paste_id=pid, remote_triggered=True)
            self._broadcast_json({"type": "cancel_ack", "paste_id": pid})
            return

        if ptype == "cancel_ack":
            pid = packet.get("paste_id")
            if pid is not None:
                self._cancelled_paste_ids.add(int(pid))
            return

        if ptype == "request_files":
            tok = int(packet.get("paste_id") or 0)
            if tok and tok in self._cancelled_paste_ids:
                return
            files_req = packet.get("files") or []
            target_sock = peer_sock or self.sock
            if target_sock and files_req:
                self._send_xfer_seq += 1
                my_xid = self._send_xfer_seq
                threading.Thread(
                    target=self._send_files_worker,
                    args=(target_sock, files_req, my_xid, tok),
                    daemon=True,
                    name=f"XPSendFiles_{my_xid}",
                ).start()
            return

        if ptype == "batch_start":
            xid = packet.get("xfer_id")
            paste_id = int(packet.get("paste_id") or 0)
            job = self._xfer_jobs.get(paste_id)
            dest_dir = (job or {}).get("dest_dir") or get_xp_special_folder(CSIDL_DESKTOPDIRECTORY)
            total_sz = int(packet.get("total_size") or (job or {}).get("total") or 0)
            disp = packet.get("display_name") or (job or {}).get("display_name") or "Files"
            rec_job = {
                "xfer_id": xid,
                "paste_id": paste_id,
                "dest_dir": dest_dir,
                "staging_dir": os.path.join(_get_staging_base(), f".rdxfer_{xid or paste_id or int(time.time())}"),
                "total": total_sz,
                "received": 0,
                "paths": [],
            }
            os.makedirs(rec_job["staging_dir"], exist_ok=True)
            if xid is not None:
                self._xfer_jobs[f"x_{xid}"] = rec_job
            if paste_id:
                self._xfer_jobs[paste_id] = rec_job
                self.gui_queue.put(("open_dlg", (paste_id, disp, total_sz, dest_dir)))
            return

        if ptype == "file_start":
            xid = packet.get("xfer_id")
            paste_id = int(packet.get("paste_id") or 0)
            rel_name = self._safe_rel_path(packet.get("name"))
            if not rel_name:
                return
            job = self._xfer_jobs.get(f"x_{xid}") or self._xfer_jobs.get(paste_id)
            pkt_target_dir = packet.get("target_dir")
            if job:
                base_save = job["staging_dir"]
            elif pkt_target_dir and os.path.isdir(pkt_target_dir):
                base_save = pkt_target_dir
            else:
                base_save = _get_staging_base()

            full_target = os.path.join(base_save, rel_name)
            os.makedirs(os.path.dirname(full_target), exist_ok=True)
            offset = int(packet.get("offset") or 0)
            mode = "r+b" if (offset > 0 and os.path.exists(full_target)) else "wb"
            fh = open(full_target, mode)
            if offset > 0:
                fh.seek(offset)
            key = (xid, packet.get("name"))
            self.incoming_transfers[key] = {
                "handle": fh,
                "path": full_target,
                "rel_name": rel_name,
                "job": job,
                "paste_id": paste_id,
            }
            return

        if ptype == "file_chunk":
            xid = packet.get("xfer_id")
            key = (xid, packet.get("name"))
            tr = self.incoming_transfers.get(key)
            if not tr or not tr.get("handle"):
                return
            raw = base64.b64decode(packet.get("data") or "")
            if raw:
                tr["handle"].write(raw)
                job = tr.get("job")
                if job is not None:
                    job["received"] = int(job.get("received") or 0) + len(raw)
                    dlg_id = job.get("paste_id") or xid
                    if dlg_id:
                        self.gui_queue.put(("upd_dlg", (dlg_id, job["received"])))
            return

        if ptype == "file_end":
            xid = packet.get("xfer_id")
            key = (xid, packet.get("name"))
            tr = self.incoming_transfers.pop(key, None)
            if not tr:
                return
            try:
                tr["handle"].flush()
                tr["handle"].close()
            except Exception:
                pass
            job = tr.get("job")
            if job is not None:
                dest_dir = job["dest_dir"]
                final_dst = os.path.join(dest_dir, tr["rel_name"])
                os.makedirs(os.path.dirname(final_dst), exist_ok=True)
                try:
                    if os.path.exists(final_dst):
                        ctypes.windll.kernel32.SetFileAttributesW(ctypes.c_wchar_p(final_dst), 0x80)
                        os.remove(final_dst)
                    shutil.move(tr["path"], final_dst)
                    job["paths"].append(final_dst)
                except Exception as e:
                    xp_log(f"[XPClipboard] Move {tr['path']} -> {final_dst} failed: {e}")
            else:
                notify_xp_shell_created([tr["path"]])
            return

        if ptype == "batch_end":
            xid = packet.get("xfer_id")
            paste_id = int(packet.get("paste_id") or 0)
            job = self._xfer_jobs.pop(f"x_{xid}", None) or self._xfer_jobs.pop(paste_id, None)
            if paste_id:
                self._xfer_jobs.pop(paste_id, None)
                self.gui_queue.put(("close_dlg", paste_id))
            if job:
                self._scrub_stub_in_dest(job["dest_dir"])
                notify_xp_shell_created(job.get("paths") or [])
                try:
                    shutil.rmtree(job["staging_dir"], ignore_errors=True)
                except Exception:
                    pass
                # Cài lại file mồi vào Clipboard XP để người dùng có thể bấm Ctrl+V dán tiếp sang thư mục khác!
                if self.pending_remote_files and self._stub_paths:
                    if xp_set_clipboard_files(self._stub_paths, self._hwnd):
                        self._last_own_seq = get_clipboard_seq()
            return

    def _send_files_worker(self, sock, files, xfer_id, paste_id):
        pw = socket_passwords.get(sock)
        if is_lan_socket(sock):
            tune_socket_for_xp_lan(sock)
            chunk_sz = 131072
        else:
            chunk_sz = 65536

        resolved = []
        total_size = 0
        for item in files:
            if isinstance(item, dict):
                fp = item.get("path") or ""
                fn = item.get("name") or os.path.basename(fp)
            else:
                fp = str(item)
                fn = os.path.basename(fp)
            if (not fp or not os.path.isfile(fp)) and fn:
                fp = self._copied_files_map.get(fn) or self._copied_files_map.get(os.path.normcase(fn)) or ""
            if fp and os.path.isfile(fp):
                sz = os.path.getsize(fp)
                resolved.append((fp, fn, sz))
                total_size += sz

        if not resolved:
            send_msg(sock, json.dumps({"type": "batch_end", "xfer_id": xfer_id, "paste_id": paste_id}).encode("utf-8"), pw)
            return

        disp = resolved[0][1].split("/")[0]
        batch_pkt = {
            "type": "batch_start",
            "count": len(resolved),
            "total_size": total_size,
            "display_name": disp,
            "item_kind": "folder" if ("/" in resolved[0][1] or len(resolved) > 1) else "file",
            "xfer_id": xfer_id,
            "paste_id": paste_id,
        }
        if not send_msg(sock, json.dumps(batch_pkt).encode("utf-8"), pw):
            return

        for fp, fn, sz in resolved:
            if paste_id and paste_id in self._cancelled_paste_ids:
                return
            if not send_msg(
                sock,
                json.dumps({
                    "type": "file_start",
                    "name": fn,
                    "size": sz,
                    "offset": 0,
                    "xfer_id": xfer_id,
                    "paste_id": paste_id,
                }).encode("utf-8"),
                pw,
            ):
                return
            sent_off = 0
            try:
                with open(fp, "rb") as fh:
                    while True:
                        if paste_id and paste_id in self._cancelled_paste_ids:
                            return
                        chunk = fh.read(chunk_sz)
                        if not chunk:
                            break
                        b64 = base64.b64encode(chunk).decode("ascii")
                        ok = send_msg(
                            sock,
                            json.dumps({
                                "type": "file_chunk",
                                "name": fn,
                                "data": b64,
                                "offset": sent_off,
                                "xfer_id": xfer_id,
                                "paste_id": paste_id,
                            }).encode("utf-8"),
                            pw,
                        )
                        if not ok:
                            return
                        sent_off += len(chunk)
            except Exception as e:
                xp_log(f"[XPClipboard] Send file {fn} error: {e}")
                return

            if not send_msg(
                sock,
                json.dumps({"type": "file_end", "name": fn, "xfer_id": xfer_id, "paste_id": paste_id}).encode("utf-8"),
                pw,
            ):
                return

        send_msg(
            sock,
            json.dumps({"type": "batch_end", "xfer_id": xfer_id, "paste_id": paste_id}).encode("utf-8"),
            pw,
        )
