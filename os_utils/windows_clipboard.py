last_clipboard_set_time = 0.0
import os
import sys
import time
import json
import queue
import threading
import socket
import ctypes
from ctypes import wintypes
import logging
import win32file
import win32pipe
import win32event
import win32api
import win32gui
import psutil
import tkinter as tk

from core.config import *
from network.socket_utils import socket_passwords
from gui.components import ProgressDialog, ClassicCopyDialog
from utils.logger import log_file_transfer, log_activity
import base64

from utils.logger import log_debug
from core.i18n import _
from network.socket_utils import send_msg, recv_msg, is_lan_socket, tune_socket_for_lan_bulk
CLIPBOARD_PKT_TYPES = (
    "batch_start", "file_start", "file_chunk", "file_end", "batch_end",
    "files_copied_meta", "request_files", "cancel_transfer", "cancel_ack",
    "clipboard_text", "clipboard_image", "clear_clipboard",
    "resume_query", "resume_state",
)

from utils.clipboard_api import (
    ENABLE_CLIPBOARD_SYNC, 
    set_clipboard_dword_format, 
    setup_clipboard_exclusions, 
    clipboard_has_file_formats,
    get_clipboard_files, 
    set_clipboard_files, 
    get_clipboard_text, 
    set_clipboard_text,
    create_hdrop_data,
    fn_SetClipboardData,
    fn_GlobalFree,
    clear_local_clipboard,
    get_clipboard_sequence_number,
    mark_own_clipboard_write,
    is_own_clipboard_write,
    should_preserve_user_clipboard,
)

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Dọn dẹp thư mục tạm từ các phiên chạy trước
def _cleanup_stale_transfers():
    import shutil
    try:
        temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except: pass
    try:
        headless_dir = r"C:\Users\Public\Downloads\RemoteDesktopTransfers"
        if os.path.exists(headless_dir):
            shutil.rmtree(headless_dir, ignore_errors=True)
    except: pass

_cleanup_stale_transfers()


# --- NATIVE CLIPBOARD EVENT LISTENER ---
WM_CLIPBOARDUPDATE = 0x031D
HWND_MESSAGE = -3
_WM_RENDERFORMAT = 0x0305
_WM_RENDERALLFORMATS = 0x0306


def _pump_messages_except_clipboard_render():
    """Bơm message khi đang chờ tải file, nhưng không Dispatch WM_RENDERFORMAT.

    PeekMessage(hwnd=0) + Dispatch sẽ gọi lồng WM_RENDERFORMAT. Handler trùng
    return 0 không SetClipboardData → Explorer Win11 dán PE dở, không hiện dialog.
    Để RENDERFORMAT nằm lại queue, xử lý sau khi lần chờ hiện tại kết thúc.
    """
    user32 = ctypes.windll.user32
    msg = wintypes.MSG()
    PM_REMOVE = 1
    pumped = False
    while user32.PeekMessageW(ctypes.byref(msg), 0, 0, _WM_RENDERFORMAT - 1, PM_REMOVE):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
        pumped = True
    while user32.PeekMessageW(
        ctypes.byref(msg), 0, _WM_RENDERALLFORMATS + 1, 0xFFFFFFFF, PM_REMOVE
    ):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
        pumped = True
    return pumped


def _parse_files_pipe_payload(paths_str):
    """FILES: [paste_id|]path|path — paste_id để bỏ gói trễ sau Hủy."""
    parts = [p for p in (paths_str or "").split("|") if p]
    paste_id = None
    if parts and parts[0].isdigit():
        paste_id = int(parts[0])
        parts = parts[1:]
    return paste_id, parts

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
                    now = time.time()
                    was = getattr(self.manager, "_lmb_held", False)
                    self.manager.last_lbutton_time = now
                    on_self = _cursor_over_current_process()
                    if not was:
                        prev_t = getattr(self.manager, "_prev_lbutton_time", 0.0)
                        px, py = getattr(self.manager, "_prev_lbutton_pos", (0, 0))
                        cx, cy = _cursor_xy()
                        if (now - prev_t) <= (_double_click_ms() / 1000.0) + 0.05 and abs(cx - px) <= 6 and abs(cy - py) <= 6:
                            self.manager.last_dblclick_time = now
                        self.manager._prev_lbutton_time = now
                        self.manager._prev_lbutton_pos = (cx, cy)
                        hit_menu = (not on_self) and _cursor_over_context_menu()
                        if hit_menu:
                            self.manager._lmb_hit_context_menu = True
                            kind, _name = _capture_menu_item_at_cursor()
                            self.manager._lmb_menu_item_kind = kind
                            if kind != "not_paste":
                                self.manager.note_paste_gesture()
                        elif not getattr(self.manager, "_lmb_hit_context_menu", False):
                            self.manager._lmb_hit_context_menu = False
                    self.manager._lmb_held = True
                    if (not on_self) and getattr(self.manager, 'dummy_h_active', False):
                        self.manager.dummy_h_active = False
                        self.manager.setup_delayed_rendering()
            else:
                if self.manager:
                    self.manager._lmb_held = False
            if user32.GetAsyncKeyState(0x02) & 0x8000:
                if self.manager:
                    self.manager.last_rbutton_time = time.time()
                    self.manager._lmb_hit_context_menu = False
                    self.manager._lmb_menu_item_kind = ""
                    if getattr(self.manager, 'dummy_h_active', False):
                        self.manager.dummy_h_active = False
                        self.manager.setup_delayed_rendering()
            if user32.GetAsyncKeyState(0x0D) & 0x8000: # Enter
                if self.manager and getattr(self.manager, 'dummy_h_active', False):
                    self.manager.dummy_h_active = False
                    self.manager.setup_delayed_rendering()
            if user32.GetAsyncKeyState(0x1B) & 0x8000: # Esc
                if self.manager and getattr(self.manager, 'dummy_h_active', False):
                    self.manager.dummy_h_active = False
                    self.manager.setup_delayed_rendering()
            if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):
                if self.manager:
                    if not getattr(self.manager, "_ctrl_v_held", False):
                        self.manager.last_ctrl_v_time = time.time()
                        self.manager.note_paste_gesture()
                    self.manager._ctrl_v_held = True
                    if getattr(self.manager, 'dummy_h_active', False):
                        self.manager.dummy_h_active = False
                        self.manager.setup_delayed_rendering()
            else:
                if self.manager:
                    self.manager._ctrl_v_held = False
            if (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000):
                if self.manager:
                    if not getattr(self.manager, "_shift_ins_held", False):
                        self.manager.last_ctrl_v_time = time.time()
                        self.manager.note_paste_gesture()
                    self.manager._shift_ins_held = True
                    if getattr(self.manager, 'dummy_h_active', False):
                        self.manager.dummy_h_active = False
                        self.manager.setup_delayed_rendering()
            else:
                if self.manager:
                    self.manager._shift_ins_held = False
            # Cùng file: gửi lại metadata đã cache — không GetClipboardData (Explorer chuột xoay).
            if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x43) & 0x8000):
                if self.manager:
                    now = time.time()
                    if now - getattr(self.manager, "_last_ctrl_c_time", 0) > 0.4:
                        self.manager._last_ctrl_c_time = now
                        m = self.manager
                        seq = get_clipboard_sequence_number()
                        last_seq = getattr(m, "_last_sent_file_seq", None)
                        cached = getattr(m, "last_current_files", None)
                        if cached and seq and seq == last_seq:
                            threading.Thread(
                                target=lambda: m._process_clipboard_change(
                                    provided_files=list(cached), force=True
                                ),
                                daemon=True,
                            ).start()
            time.sleep(0.05)

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
            
            # Không còn dùng Low-level Mouse Hook (WH_MOUSE_LL) để tránh lag chuột toàn hệ thống

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
            
            # Cửa sổ ẩn thật (không HWND_MESSAGE): message-only thường không nhận WM_CLIPBOARDUPDATE.
            self.hwnd = user32.CreateWindowExW(0, wndclass.lpszClassName, "HiddenWindow", 0, 0, 0, 0, 0, None, None, wndclass.hInstance, None)
            log_debug(f"[Listener] CreateWindowExW trả về HWND: {self.hwnd}")
            
            try:
                WM_CLIPBOARDUPDATE = 0x031D
                WM_RENDERFORMAT = 0x0305
                WM_DESTROYCLIPBOARD = 0x0307
                MSGFLT_ALLOW = 1
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_CLIPBOARDUPDATE, MSGFLT_ALLOW, None)
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_RENDERFORMAT, MSGFLT_ALLOW, None)
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_DESTROYCLIPBOARD, MSGFLT_ALLOW, None)
                log_debug("[Listener] ChangeWindowMessageFilterEx thành công.")
            except Exception as e:
                log_debug(f"[Listener] ChangeWindowMessageFilterEx thất bại: {e}")

            add_res = user32.AddClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            log_debug(f"[Listener] AddClipboardFormatListener trả về: {add_res}")
            
            EVENT_SYSTEM_FOREGROUND = 0x0003
            WINEVENT_OUTOFCONTEXT = 0x0000
            WINEVENTPROC = ctypes.WINFUNCTYPE(
                None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD
            )
            
            def wineventproc(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
                if event == EVENT_SYSTEM_FOREGROUND:
                    if self.manager and hasattr(self.manager, 'on_foreground_changed'):
                        self.manager.on_foreground_changed(hwnd)

            self.wineventproc_c = WINEVENTPROC(wineventproc)
            hook = user32.SetWinEventHook(
                EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
                None, self.wineventproc_c, 0, 0, WINEVENT_OUTOFCONTEXT
            )
            # Không cài WH_KEYBOARD_LL / WH_MOUSE_LL trên viewer/client:
            # hook nằm cùng thread GetMessage (OpenClipboard/RENDERFORMAT) sẽ treo chuột+phím
            # cả máy local (vd. F2 đổi tên trong Explorer). Agent host vẫn cài LL hook riêng.

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
        if self.hwnd:
            try: ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.hwnd), 0, 0, 0)
            except: pass

# Đường dẫn thư mục lưu file chuyển từ Client (dùng cho headless/SYSTEM mode)
HEADLESS_TRANSFER_DIR = r"C:\Users\Public\Downloads\RemoteDesktopTransfers"


def _incoming_key(xfer_id, filename):
    return (xfer_id, filename) if xfer_id is not None else filename


def _xfer_staging_dir(base_dir, xfer_id):
    if not base_dir:
        return base_dir
    if xfer_id is None:
        return base_dir
    return os.path.join(base_dir, f".rdxfer_{xfer_id}")


def _hide_win_path(path):
    """Ẩn thư mục tạm trên Windows (dấu chấm không ẩn Explorer)."""
    if sys.platform != "win32" or not path:
        return
    try:
        GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
        SetFileAttributesW = ctypes.windll.kernel32.SetFileAttributesW
        GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        GetFileAttributesW.restype = wintypes.DWORD
        SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        attrs = GetFileAttributesW(str(path))
        if attrs == 0xFFFFFFFF:
            return
        SetFileAttributesW(str(path), int(attrs) | 0x02 | 0x04)  # HIDDEN | SYSTEM
    except Exception:
        pass


def _purge_rdxfer_staging(dest_dir=None, xfer_id=None, extra_paths=None):
    """Xóa .rdxfer_* sau khi file đã ra thư mục đích — không để lại folder tạm."""
    targets = []
    keep_nonempty = set()
    if dest_dir and xfer_id is not None:
        targets.append(_xfer_staging_dir(dest_dir, xfer_id))
    for p in extra_paths or []:
        if not p:
            continue
        try:
            ap = os.path.abspath(p)
            base = os.path.basename(ap)
            if base.startswith(".rdxfer_"):
                targets.append(ap)
            else:
                d = os.path.dirname(ap)
                if os.path.basename(d).startswith(".rdxfer_"):
                    targets.append(d)
        except Exception:
            pass
    if dest_dir and os.path.isdir(dest_dir):
        try:
            want = None
            if xfer_id is not None:
                want = f".rdxfer_{int(xfer_id)}"
            for name in os.listdir(dest_dir):
                if not name.startswith(".rdxfer_"):
                    continue
                p = os.path.join(dest_dir, name)
                if want and name == want:
                    targets.append(p)
                    continue
                try:
                    if not os.listdir(p):
                        targets.append(p)
                    else:
                        keep_nonempty.add(os.path.normcase(os.path.abspath(p)))
                except Exception:
                    pass
        except Exception:
            pass
    seen = set()
    for t in targets:
        try:
            key = os.path.normcase(os.path.abspath(t))
        except Exception:
            continue
        if key in seen or key in keep_nonempty:
            continue
        seen.add(key)
        if not os.path.basename(t).startswith(".rdxfer_"):
            continue
        _retry_remove_path(t)


def _is_transfer_staging_dir(path):
    if not path:
        return False
    abs_path = os.path.normcase(os.path.abspath(path))
    staging = [
        os.path.normcase(os.path.abspath(HEADLESS_TRANSFER_DIR)),
        os.path.normcase(os.path.abspath(os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"))),
    ]
    if abs_path in staging:
        return True
    base = os.path.basename(abs_path)
    return base.startswith(".rdxfer_")


def _file_offer_fp(files):
    """Vân tay danh sách file copy — để nhận copy mới dù offer_id bị lặp/reset."""
    parts = []
    for f in files or []:
        if isinstance(f, dict):
            name = os.path.basename(str(f.get("name") or "").replace("\\", "/"))
            path = os.path.normcase(os.path.abspath(str(f.get("path") or ""))) if f.get("path") else ""
            try:
                size = int(f.get("size") or 0)
            except Exception:
                size = 0
            parts.append((name, size, path))
        else:
            p = str(f or "")
            parts.append((os.path.basename(p.replace("\\", "/")), 0, os.path.normcase(os.path.abspath(p)) if p else ""))
    return tuple(parts)


def _rel_copy_name(item):
    if isinstance(item, dict):
        raw = str(item.get("name") or "")
    else:
        raw = str(item or "")
    return raw.replace("\\", "/").strip("/")


def _copy_batch_kind_and_name(files, fallback=""):
    """Paste file → ('file', tên file); paste thư mục → ('folder', tên folder)."""
    files = files or []
    names = []
    for item in files:
        name = _rel_copy_name(item)
        if name:
            names.append(name)
    if not names:
        raw = fallback or _("Tệp tin")
        return "file", os.path.basename(str(raw).replace("\\", "/")) or raw

    folder_tops = []
    seen_folders = set()
    loose = []
    for name in names:
        parts = [p for p in name.split("/") if p]
        if len(parts) >= 2:
            top = parts[0]
            if top not in seen_folders:
                seen_folders.add(top)
                folder_tops.append(top)
        else:
            loose.append(parts[0] if parts else name)

    if folder_tops and not loose:
        label = folder_tops[0]
        extra = len(folder_tops) - 1
        if extra > 0:
            label += _(" và {count} mục khác").format(count=extra)
        return "folder", label

    label = os.path.basename(names[0]) or names[0]
    extra = len(names) - 1
    if extra > 0:
        label += _(" và {count} mục khác").format(count=extra)
    return "file", label


def _localized_batch_name(files, fallback=""):
    _kind, name = _copy_batch_kind_and_name(files, fallback)
    return name


def _same_volume(path_a, path_b):
    try:
        return os.path.splitdrive(os.path.abspath(path_a))[0].lower() == os.path.splitdrive(os.path.abspath(path_b))[0].lower()
    except Exception:
        return False


def _path_byte_size(path):
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        total = 0
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except Exception:
                    pass
        return total
    except Exception:
        return 0


def _copy_file_with_progress(src, dst, on_progress=None, should_stop=None):
    import shutil
    wrote = 0
    completed = False
    try:
        with open(src, "rb") as inf, open(dst, "wb") as outf:
            while True:
                if should_stop and should_stop():
                    raise InterruptedError("cancel")
                buf = inf.read(1024 * 1024)
                if not buf:
                    break
                outf.write(buf)
                wrote += len(buf)
                if on_progress:
                    on_progress(len(buf))
        try:
            shutil.copystat(src, dst, follow_symlinks=True)
        except Exception:
            pass
        completed = True
        try:
            os.remove(src)
        except Exception:
            threading.Thread(target=_retry_remove_path, args=(src,), daemon=True).start()
    except Exception:
        if not completed:
            try:
                _retry_remove_path(dst)
            except Exception:
                pass
        raise


_file_io_lock = threading.Lock()


def relocate_transfer_files(src_paths, dest_dir, on_progress=None, should_stop=None):
    """Chuyển file từ thư mục tạm sang thư mục Explorer đang Paste. Trả về (paths, moved_all)."""
    with _file_io_lock:
        return _relocate_transfer_files_unlocked(src_paths, dest_dir, on_progress, should_stop)


def _relocate_transfer_files_unlocked(src_paths, dest_dir, on_progress=None, should_stop=None):
    """Chuyển file từ thư mục tạm sang thư mục Explorer đang Paste. Trả về (paths, moved_all)."""
    import shutil
    if not dest_dir or not os.path.isdir(dest_dir) or _is_transfer_staging_dir(dest_dir):
        return list(src_paths or []), False
    dest_abs = os.path.normcase(os.path.abspath(dest_dir))
    moved = []
    all_in_dest = True
    for src in src_paths or []:
        if should_stop and should_stop():
            all_in_dest = False
            break
        if not src or not os.path.exists(src):
            continue
        src_abs = os.path.abspath(src)
        if os.path.basename(src_abs).startswith(".rdxfer_") or _is_transfer_staging_dir(src_abs):
            continue
        if _is_probe_stub_name(src_abs):
            continue
        src_dir = os.path.normcase(os.path.dirname(src_abs))
        if src_dir == dest_abs:
            moved.append(src_abs)
            if on_progress:
                on_progress(_path_byte_size(src_abs))
            continue
        dest_path = os.path.join(dest_dir, os.path.basename(src_abs))
        try:
            if should_stop and should_stop():
                raise InterruptedError("cancel")
            # Folder paste: đích đã có file chuyển sớm — gộp, không rmtree xóa file đã xong.
            if os.path.isdir(src_abs) and os.path.isdir(dest_path):
                child_ok = True
                try:
                    names = os.listdir(src_abs)
                except Exception:
                    names = []
                for name in names:
                    child = os.path.join(src_abs, name)
                    _nested, ok = _relocate_transfer_files_unlocked(
                        [child], dest_path, on_progress, should_stop
                    )
                    if not ok:
                        child_ok = False
                if child_ok:
                    try:
                        os.rmdir(src_abs)
                    except Exception:
                        pass
                else:
                    all_in_dest = False
                moved.append(os.path.abspath(dest_path))
                continue
            if os.path.exists(dest_path):
                if os.path.isdir(dest_path) and not os.path.islink(dest_path):
                    shutil.rmtree(dest_path, ignore_errors=True)
                else:
                    os.remove(dest_path)
            if os.path.isdir(src_abs) or _same_volume(src_abs, dest_path):
                shutil.move(src_abs, dest_path)
                if on_progress:
                    on_progress(_path_byte_size(dest_path))
            else:
                _copy_file_with_progress(src_abs, dest_path, on_progress, should_stop=should_stop)
            moved.append(os.path.abspath(dest_path))
        except InterruptedError:
            _retry_remove_path(dest_path)
            all_in_dest = False
            break
        except Exception as e:
            log_debug(f"[relocate_transfer_files] move failed {src_abs} -> {dest_path}: {e}")
            try:
                if should_stop and should_stop():
                    raise InterruptedError("cancel")
                if os.path.isdir(src_abs):
                    shutil.copytree(src_abs, dest_path)
                    shutil.rmtree(src_abs, ignore_errors=True)
                    if on_progress:
                        on_progress(_path_byte_size(dest_path))
                else:
                    _copy_file_with_progress(src_abs, dest_path, on_progress, should_stop=should_stop)
                moved.append(os.path.abspath(dest_path))
            except InterruptedError:
                _retry_remove_path(dest_path)
                all_in_dest = False
                break
            except Exception as e2:
                log_debug(f"[relocate_transfer_files] copy fallback failed: {e2}")
                _retry_remove_path(dest_path)
                moved.append(src_abs)
                all_in_dest = False
    if moved and all_in_dest:
        for p in moved:
            if os.path.normcase(os.path.dirname(os.path.abspath(p))) != dest_abs:
                all_in_dest = False
                break
    return moved, bool(moved) and all_in_dest


def _promote_completed_xfer_file(staging_path, dest_dir, rel_name):
    """Đưa 1 file đã tải xong từ .rdxfer_* ra thư mục đích (giữ cây thư mục). Rename cùng ổ — không copy 4GB."""
    import shutil
    if not staging_path or not dest_dir or not os.path.isfile(staging_path):
        return staging_path
    if _is_transfer_staging_dir(dest_dir) or not os.path.isdir(dest_dir):
        return staging_path
    rel = str(rel_name or os.path.basename(staging_path)).replace("/", os.sep).replace("\\", os.sep)
    rel = rel.lstrip("\\/")
    if not rel:
        rel = os.path.basename(staging_path)
    dest_path = os.path.join(dest_dir, rel)
    try:
        if os.path.normcase(os.path.abspath(staging_path)) == os.path.normcase(os.path.abspath(dest_path)):
            return dest_path
    except Exception:
        pass
    parent = os.path.dirname(dest_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if os.path.exists(dest_path):
        try:
            if os.path.isdir(dest_path) and not os.path.islink(dest_path):
                shutil.rmtree(dest_path, ignore_errors=True)
            else:
                os.remove(dest_path)
        except Exception:
            _retry_remove_path(dest_path)
    try:
        os.replace(staging_path, dest_path)
    except OSError:
        shutil.move(staging_path, dest_path)
    return os.path.abspath(dest_path)


def _collect_actual_file_sizes(paths):
    """Map relative posix path → size. Folder paste: paths là thư mục top-level, không phải từng file."""
    actual = {}
    for p in paths:
        if not p or not os.path.exists(p):
            return None
        if os.path.isfile(p):
            try:
                actual[os.path.basename(p).replace("\\", "/")] = os.path.getsize(p)
            except Exception:
                return None
            continue
        if not os.path.isdir(p):
            return None
        root_parent = os.path.dirname(os.path.abspath(p))
        for dirpath, _dirs, files in os.walk(p):
            for fn in files:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root_parent).replace("\\", "/")
                try:
                    actual[rel] = os.path.getsize(full)
                except Exception:
                    return None
    return actual


def _paths_match_expected_sizes(paths, meta_files, detail=None):
    """False nếu thiếu file hoặc size không khớp metadata — tránh dán PE dở (mất icon).

    So khớp theo đường dẫn tương đối (thư mục/file), không chỉ basename — tránh
    trùng tên trong thư mục con và paste cả folder (paths là dir, không phải file).
    Nếu `detail` là list, append lý do thất bại.
    """
    def _fail(msg):
        if isinstance(detail, list):
            detail.append(msg)
        return False

    if not paths or not meta_files:
        return _fail("thieu paths hoac metadata")
    expected = {}
    for f in meta_files:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name") or "").replace("\\", "/")
        if not name:
            continue
        try:
            expected[name] = int(f.get("size") or 0)
        except Exception:
            return _fail("metadata size khong hop le: %s" % (f.get("name"),))
    if not expected:
        return _fail("metadata khong co file")
    try:
        actual = _collect_actual_file_sizes(paths)
    except Exception as e:
        return _fail("khong doc duoc file da tai: %s" % e)
    if actual is None:
        return _fail("thieu file/thu muc tren disk (paths=%s)" % ([os.path.basename(p) for p in paths[:8]],))
    actual_l = {k.lower(): (k, v) for k, v in actual.items()}
    for name, size in expected.items():
        hit = actual_l.get(name.lower())
        if hit is None:
            base = name.split("/")[-1].lower()
            hits = [v for k, v in actual_l.items() if k.split("/")[-1] == base]
            if len(hits) == 1:
                hit = hits[0]
            else:
                return _fail("thieu %s (expected %s bytes)" % (name, size))
        got = hit[1]
        if got != size:
            return _fail("%s size %s != expected %s" % (name, got, size))
    return True


def query_explorer_folder_path():
    """Thư mục Explorer/Desktop đang focus — gọi từ background thread (không gọi trong WM_RENDERFORMAT)."""
    import win32gui
    import win32process
    try:
        pythoncom = __import__("pythoncom")
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass
        import win32com.client
        shell = win32com.client.Dispatch("Shell.Application")
    except Exception:
        return None

    def related_hwnds(h):
        if not h:
            return []
        res = [h]
        try:
            root = ctypes.windll.user32.GetAncestor(h, 2)
            if root and root not in res:
                res.append(root)
            owner = ctypes.windll.user32.GetWindow(h, 4)
            if owner and owner not in res:
                res.append(owner)
            parent = ctypes.windll.user32.GetParent(h)
            if parent and parent not in res:
                res.append(parent)
        except Exception:
            pass
        return res

    hwnds_to_check = []
    try:
        hwnd_clip = ctypes.windll.user32.GetOpenClipboardWindow()
        if hwnd_clip:
            # Explorer đang Copy/Paste — không enumerate Shell (chuột xoay / mất clipboard).
            return None
    except Exception:
        pass
    try:
        hwnd_fg = win32gui.GetForegroundWindow()
        if hwnd_fg:
            hwnds_to_check.extend(related_hwnds(hwnd_fg))
    except Exception:
        pass
    try:
        pt = wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            hwnd_mouse = ctypes.windll.user32.WindowFromPoint(pt)
            if hwnd_mouse:
                hwnds_to_check.extend(related_hwnds(hwnd_mouse))
    except Exception:
        pass

    seen = set()
    ordered = []
    for h in hwnds_to_check:
        if h and h not in seen:
            seen.add(h)
            ordered.append(h)

    for hwnd in ordered:
        try:
            class_name = win32gui.GetClassName(hwnd)
            if hwnd == win32gui.GetDesktopWindow() or class_name in ("Progman", "WorkerW"):
                return os.path.join(os.path.expanduser("~"), "Desktop")
        except Exception:
            pass

    explorer_windows = []
    try:
        for window in shell.Windows():
            try:
                w_hwnd = int(window.HWND)
                doc = window.Document
                if not doc:
                    continue
                path = ""
                try:
                    path = doc.Folder.Self.Path
                except Exception:
                    pass
                if path:
                    explorer_windows.append((w_hwnd, path))
            except Exception:
                continue
    except Exception:
        pass

    for hwnd in ordered:
        for w_hwnd, path in explorer_windows:
            if hwnd == w_hwnd:
                return path

    for hwnd in ordered:
        try:
            _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
            if psutil.Process(pid).name().lower() != "explorer.exe":
                continue
            class_name = win32gui.GetClassName(hwnd)
            if class_name in ("CabinetWClass", "ExploreWClass"):
                for w_hwnd, path in explorer_windows:
                    if w_hwnd == hwnd:
                        return path
        except Exception:
            pass

    if explorer_windows:
        if len(explorer_windows) == 1:
            return explorer_windows[0][1]
        top_explorer_path = []

        def enum_cb(hwnd, _lparam):
            for w_hwnd, path in explorer_windows:
                if hwnd == w_hwnd:
                    top_explorer_path.append(path)
                    return False
            return True

        try:
            win32gui.EnumWindows(enum_cb, 0)
        except Exception:
            pass
        if top_explorer_path:
            return top_explorer_path[0]
    return None


# Tên Named Pipe để giao tiếp giữa Service (SYSTEM) và Agent (User)
CLIPBOARD_PIPE_NAME = r"\\.\pipe\RemoteDesktopClipboardPipe"

def create_named_pipe_with_everyone_dacl():
    """
    Tạo Named Pipe Server với Security Descriptor cho phép nhóm Everyone 
    có quyền Read/Write. TUYỆT ĐỐI KHÔNG truyền None vào Security Attributes.
    """
    import win32pipe
    import win32file
    import win32security
    import ntsecuritycon as con
    
    # Tạo Security Descriptor với DACL cho Everyone
    sd = win32security.SECURITY_DESCRIPTOR()
    sd.Initialize()
    
    # Tạo DACL
    dacl = win32security.ACL()
    dacl.Initialize()
    
    # Lấy SID của nhóm "Everyone"
    everyone_sid = win32security.CreateWellKnownSid(win32security.WinWorldSid)
    
    # Thêm quyền Read/Write cho Everyone
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION,
        con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE,
        everyone_sid
    )
    
    sd.SetSecurityDescriptorDacl(True, dacl, False)
    
    # Tạo Security Attributes
    sa = win32security.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = False
    sa.SECURITY_DESCRIPTOR = sd
    
    # Tạo Named Pipe
    pipe_handle = win32pipe.CreateNamedPipe(
        CLIPBOARD_PIPE_NAME,
        win32pipe.PIPE_ACCESS_OUTBOUND,                    # Server chỉ ghi (outbound)
        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,  # Message mode, blocking
        4,       # Số instance tối đa
        10 * 1024 * 1024,    # Output buffer size (10MB)
        10 * 1024 * 1024,    # Input buffer size (10MB)
        0,       # Default timeout
        sa       # Security Attributes với DACL cho Everyone
    )
    
    return pipe_handle


def _low_il_everyone_sa():
    """SECURITY_ATTRIBUTES: Everyone + Mandatory Label Low — user Medium IL ghi được."""
    import win32security
    sa = win32security.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = 0
    try:
        sd = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
            "D:(A;;GA;;;WD)(A;;GA;;;AN)S:(ML;;NW;;;LW)",
            win32security.SDDL_REVISION_1,
        )
        sa.SECURITY_DESCRIPTOR = sd
    except Exception:
        sd = win32security.SECURITY_DESCRIPTOR()
        sd.Initialize()
        sd.SetSecurityDescriptorDacl(True, None, False)
        sa.SECURITY_DESCRIPTOR = sd
    return sa


def _create_user_signalable_event(name):
    """Manual-reset event: SetEvent đánh thức MỌI worker (auto-reset chỉ 1 process)."""
    import win32event
    return win32event.CreateEvent(_low_il_everyone_sa(), True, False, name)


_EXPLORER_CLIPBOARD_PROCS = (
    "explorer.exe",
    "fileexplorer.exe",
    "searchhost.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
)

# Shell extension / COM / RD khác GetData khi dựng menu — không phải Paste.
_CLIPBOARD_PROBE_PROCS = _EXPLORER_CLIPBOARD_PROCS + (
    "dllhost.exe",
    "rundll32.exe",
    "prevhost.exe",
    "verclsid.exe",
    "runtimebroker.exe",
    "applicationframehost.exe",
    "textinputhost.exe",
    "sihost.exe",
    "taskmgr.exe",
    "perfmon.exe",
    "mmc.exe",
    "procexp.exe",
    "procexp64.exe",
    "processhacker.exe",
    "systemsettings.exe",
    "vmtoolsd.exe",
    "vboxtray.exe",
    "rdpclip.exe",
    "mstsc.exe",
    "vncviewer.exe",
    "teamviewer.exe",
    "anydesk.exe",
)

_EXPLORER_FOLDER_CLASSES = (
    "CabinetWClass",
    "ExploreWClass",
)

_CONTEXT_MENU_CLASSES = (
    "#32768",
    "Microsoft.UI.Content.PopupWindowSiteBridge",
)

_CONTEXT_MENU_HIT_CLASSES = frozenset((
    "#32768",
    "XamlExplorerHostIslandWindow",
    "Microsoft.UI.Content.PopupWindowSiteBridge",
))


def _hwnd_class_name(hwnd):
    if not hwnd:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(256)
        n = ctypes.windll.user32.GetClassNameW(ctypes.c_void_p(hwnd), buf, 256)
        return buf.value if n else ""
    except Exception:
        return ""


def _hwnd_is_context_menu(hwnd):
    """Cửa sổ (hoặc cha) là menu chuột phải — không gồm khung Explorer chính."""
    user32 = ctypes.windll.user32
    seen = set()
    cur = hwnd
    for _ in range(8):
        if not cur:
            break
        try:
            key = int(cur)
        except Exception:
            break
        if key in seen:
            break
        seen.add(key)
        cls = _hwnd_class_name(cur)
        if cls in _CONTEXT_MENU_HIT_CLASSES:
            return True
        if cls in (
            "Microsoft.UI.Content.DesktopChildSiteBridge",
            "Windows.UI.Composition.DesktopWindowContentBridge",
        ):
            try:
                user32.GetWindowLongW.restype = ctypes.c_long
                style = int(user32.GetWindowLongW(ctypes.c_void_p(cur), -16) or 0)
                ex = int(user32.GetWindowLongW(ctypes.c_void_p(cur), -20) or 0)
            except Exception:
                style, ex = 0, 0
            ws_popup = bool(style & 0x80000000)
            ws_caption = bool(style & 0x00C00000)
            ws_ex_tool = bool(ex & 0x00000080)
            if ws_popup and (ws_ex_tool or not ws_caption):
                return True
        try:
            user32.GetAncestor.restype = wintypes.HWND
            nxt = user32.GetAncestor(ctypes.c_void_p(cur), 1)
            if not nxt or nxt == cur:
                user32.GetWindow.restype = wintypes.HWND
                nxt = user32.GetWindow(ctypes.c_void_p(cur), 4)
            cur = nxt
        except Exception:
            break
    return False


def _cursor_over_context_menu():
    """LMB đang nhắm vào item trên context menu (Paste), không phải click ra ngoài để đóng menu."""
    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    try:
        if not user32.GetCursorPos(ctypes.byref(pt)):
            return False
        user32.WindowFromPoint.restype = wintypes.HWND
        hwnd = user32.WindowFromPoint(pt)
        return bool(hwnd) and _hwnd_is_context_menu(hwnd)
    except Exception:
        return False


def _cursor_point():
    pt = wintypes.POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
        return None
    return pt


def _context_menu_root_hwnd(hwnd):
    """Cửa sổ menu ngoài cùng chứa hwnd (classic #32768 hoặc flyout XAML)."""
    if not hwnd or not _hwnd_is_context_menu(hwnd):
        return None
    user32 = ctypes.windll.user32
    best = hwnd
    cur = hwnd
    for _ in range(8):
        try:
            user32.GetAncestor.restype = wintypes.HWND
            nxt = user32.GetAncestor(ctypes.c_void_p(cur), 1)
            if not nxt or nxt == cur:
                user32.GetWindow.restype = wintypes.HWND
                nxt = user32.GetWindow(ctypes.c_void_p(cur), 4)
            if not nxt or nxt == cur:
                break
            if _hwnd_is_context_menu(nxt):
                best = nxt
            cur = nxt
        except Exception:
            break
    return best


def _win32_menu_text_at_point(pt):
    """Tên mục menu cổ điển (#32768) — gọi được từ mouse hook, không dùng UIA."""
    user32 = ctypes.windll.user32
    try:
        user32.WindowFromPoint.restype = wintypes.HWND
        hwnd = user32.WindowFromPoint(pt)
        if not hwnd:
            return ""
        cur = hwnd
        hwnd_menu = None
        for _ in range(8):
            if _hwnd_class_name(cur) == "#32768":
                hwnd_menu = cur
                break
            user32.GetAncestor.restype = wintypes.HWND
            nxt = user32.GetAncestor(ctypes.c_void_p(cur), 1)
            if not nxt or nxt == cur:
                break
            cur = nxt
        if not hwnd_menu:
            return ""
        MN_GETHMENU = 0x01E1
        MF_BYPOSITION = 0x0400
        hmenu = user32.SendMessageW(ctypes.c_void_p(hwnd_menu), MN_GETHMENU, 0, 0)
        if not hmenu:
            return ""

        user32.MenuItemFromPoint.argtypes = [wintypes.HWND, wintypes.HMENU, wintypes.POINT]
        user32.MenuItemFromPoint.restype = ctypes.c_int
        idx = user32.MenuItemFromPoint(hwnd_menu, hmenu, pt)
        if idx < 0:
            return ""
        buf = ctypes.create_unicode_buffer(512)
        user32.GetMenuStringW(ctypes.c_void_p(hmenu), idx, buf, 512, MF_BYPOSITION)
        return (buf.value or "").strip()
    except Exception:
        return ""


def _xaml_click_is_show_more_strip(pt, menu_hwnd):
    """Win11 compact menu: Show more nằm dải đáy; Paste là icon/mục phía trên."""
    if not pt or not menu_hwnd:
        return False
    if _hwnd_class_name(menu_hwnd) == "#32768":
        return False
    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long), ("top", ctypes.c_long),
            ("right", ctypes.c_long), ("bottom", ctypes.c_long),
        ]

    rc = RECT()
    if not user32.GetWindowRect(ctypes.c_void_p(menu_hwnd), ctypes.byref(rc)):
        return False
    if not (rc.left <= pt.x <= rc.right and rc.top <= pt.y <= rc.bottom):
        return False
    dpi = 96
    try:
        dpi = int(user32.GetDpiForWindow(ctypes.c_void_p(menu_hwnd)) or 96)
    except Exception:
        dpi = 96
    band = int(40 * dpi / 96.0)
    height = int(rc.bottom - rc.top)
    if height < 140:
        return False
    return pt.y >= rc.bottom - band


_PASTE_MENU_TOKENS = (
    "paste", "dán", "einfügen", "coller", "incolla", "pegar",
    "вставить", "붙여넣기", "貼り付け", "粘贴", "貼上",
)
_NOT_PASTE_MENU_TOKENS = (
    "show more", "more options", "hiển thị thêm", "thêm tùy chọn",
    "weitere optionen", "plus d'options", "más opciones", "altre opzioni",
    "その他のオプション", "더 많은 옵션", "дополнительн",
    "显示更多", "顯示更多", "showmoreoptions", "moreoptions",
    "properties", "thuộc tính", "eigenschaften", "propriétés", "proprietà",
    "delete", "xóa", "cut", "cắt", "copy", "sao chép",
    "rename", "đổi tên", "share", "chia sẻ", "open", "mở",
    "pin", "ghim", "format", "định dạng", "eject", "đẩy ra",
    "new", "mới", "refresh", "làm mới",
)


def _classify_context_menu_item(name):
    """'paste' | 'not_paste' | 'unknown'."""
    raw = (name or "").replace("&", "").replace("…", "").replace("...", "")
    n = " ".join(raw.strip().lower().split())
    if not n:
        return "unknown"
    compact = n.replace(" ", "").replace("+", "")
    if "ctrlv" in compact:
        return "paste"
    for tok in _NOT_PASTE_MENU_TOKENS:
        if tok in n or tok.replace(" ", "") in compact:
            return "not_paste"
    first = n.split("\t", 1)[0].strip()
    for tok in _PASTE_MENU_TOKENS:
        if first == tok or first.startswith(tok + " ") or tok in first.split():
            return "paste"
    return "unknown"


def _capture_menu_item_at_cursor():
    """Phân loại mục lúc click. Không dùng UIA (mouse hook hay fail)."""
    user32 = ctypes.windll.user32
    pt = _cursor_point()
    if not pt:
        return "unknown", ""
    user32.WindowFromPoint.restype = wintypes.HWND
    hwnd = user32.WindowFromPoint(pt)
    root = _context_menu_root_hwnd(hwnd)
    text = _win32_menu_text_at_point(pt)
    kind = _classify_context_menu_item(text)
    if kind == "unknown" and _xaml_click_is_show_more_strip(pt, root):
        kind = "not_paste"
        text = text or "[show-more-strip]"
    elif kind == "unknown":
        kind = "paste"
    try:
        log_debug(f"[menu-item] name={text!r} kind={kind}")
    except Exception:
        pass
    return kind, text


def _is_windows_11():
    try:
        v = sys.getwindowsversion()
        return v.major >= 10 and int(getattr(v, "build", 0) or 0) >= 22000
    except Exception:
        return False


def _pid_image_name(pid):
    try:
        return (psutil.Process(int(pid)).name() or "").lower()
    except Exception:
        return ""


def _hwnd_process_name(hwnd):
    if not hwnd:
        return ""
    try:
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return _pid_image_name(pid.value)
    except Exception:
        return ""


def _cursor_over_current_process():
    """Chuột đang trên cửa sổ process này (dialog tiến trình) — không phải click Paste Explorer."""
    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    try:
        if not user32.GetCursorPos(ctypes.byref(pt)):
            return False
        user32.WindowFromPoint.restype = wintypes.HWND
        hwnd = user32.WindowFromPoint(pt)
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) == int(os.getpid())
    except Exception:
        return False


def _is_explorer_clipboard_client():
    """Win11 Explorer (và host XAML) đang mở clipboard / đang foreground."""
    user32 = ctypes.windll.user32
    try:
        user32.GetOpenClipboardWindow.restype = wintypes.HWND
        opener = user32.GetOpenClipboardWindow()
        name = _hwnd_process_name(opener)
        if name in _EXPLORER_CLIPBOARD_PROCS:
            return True
    except Exception:
        pass
    try:
        user32.GetForegroundWindow.restype = wintypes.HWND
        name = _hwnd_process_name(user32.GetForegroundWindow())
        if name in _EXPLORER_CLIPBOARD_PROCS:
            return True
    except Exception:
        pass
    return False


def _cursor_in_explorer_command_bar():
    """Nút Paste trên thanh lệnh Win11 — chỉ cửa sổ thư mục, không gồm taskbar (cũng là explorer.exe)."""
    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    pt = POINT()
    if not user32.GetCursorPos(ctypes.byref(pt)):
        return False
    hwnd = user32.WindowFromPoint(pt)
    if not hwnd:
        return False
    try:
        root = user32.GetAncestor(hwnd, 2) or hwnd  # GA_ROOT
    except Exception:
        root = hwnd
    if _hwnd_class_name(root) not in _EXPLORER_FOLDER_CLASSES:
        return False
    if _hwnd_process_name(root) not in _EXPLORER_CLIPBOARD_PROCS:
        return False
    rc = RECT()
    if not user32.GetWindowRect(root, ctypes.byref(rc)):
        return False
    dpi = 96
    try:
        dpi = int(user32.GetDpiForWindow(root) or 96)
    except Exception:
        dpi = 96
    bar_h = int(148 * dpi / 96.0)
    return (rc.left <= pt.x <= rc.right) and (rc.top <= pt.y <= rc.top + bar_h)


_DUMMY_HDROP_PATH = r"C:\RemoteDesktop_Paste_Trigger.tmp"
_PROBE_STUB_NAME = ".__rd_clipboard_probe__"
_PROBE_STUB_DIR = os.path.join(
    os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopPasteProbe"
)
_LL_HOOK_KEEPALIVE = []


def _retry_remove_path(path, retries=8):
    """Xóa file/thư mục dở; retry vì Explorer/AV có thể đang khóa file 0 byte."""
    if not path:
        return False
    import shutil
    last_err = None
    for i in range(max(1, int(retries))):
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path, ignore_errors=False)
            elif os.path.lexists(path):
                try:
                    os.chmod(path, 0o666)
                except Exception:
                    pass
                os.remove(path)
            return True
        except FileNotFoundError:
            return True
        except Exception as e:
            last_err = e
            time.sleep(0.05 * (i + 1))
    if last_err:
        log_debug(f"[_retry_remove_path] Khong xoa duoc {path}: {last_err}")
    return False


def cleanup_probe_stubs():
    """Xóa file 0 byte dùng để bật nút Paste (Win11)."""
    try:
        if not os.path.isdir(_PROBE_STUB_DIR):
            return
        for name in os.listdir(_PROBE_STUB_DIR):
            _retry_remove_path(os.path.join(_PROBE_STUB_DIR, name), retries=4)
    except Exception:
        pass


def _is_paste_placeholder(path, expected=None):
    """File 0 byte / stub probe — không hỏi ghi đè, xóa rồi paste đè."""
    if not path or not os.path.lexists(path):
        return False
    try:
        p = os.path.normcase(os.path.abspath(path))
        probe = os.path.normcase(os.path.abspath(_PROBE_STUB_DIR))
        if p == probe or p.startswith(probe + os.sep):
            return True
        parent = os.path.dirname(path)
        if parent and _is_transfer_staging_dir(parent):
            return True
    except Exception:
        pass
    if os.path.isdir(path) and not os.path.islink(path):
        return False
    if not os.path.isfile(path):
        return False
    try:
        return os.path.getsize(path) == 0
    except Exception:
        return True


def _file_expected_size(meta):
    if not isinstance(meta, dict):
        return None
    try:
        if meta.get("size") is None:
            return None
        return int(meta.get("size"))
    except Exception:
        return None


def _is_incomplete_transfer_file(path, expected=None):
    """File dở trong thư mục tạm .rdxfer_* — không dùng cho file sẵn có của user."""
    if not path or not os.path.isfile(path):
        return False
    try:
        sz = os.path.getsize(path)
    except Exception:
        return True
    if expected is None:
        return sz == 0
    try:
        expected = int(expected)
    except Exception:
        return sz == 0
    if expected <= 0:
        return False
    return sz < expected


def _path_in_xfer_staging(path):
    try:
        parent = os.path.dirname(os.path.abspath(path))
        base = os.path.basename(parent)
        return base.startswith(".rdxfer_") or _is_transfer_staging_dir(parent)
    except Exception:
        return False


def _is_transfer_junk_at_dest(path, expected=None):
    """Chỉ xóa stub 0 byte / probe / file trong .rdxfer_*. File user trên đích phải hỏi ghi đè."""
    if not path or not os.path.lexists(path):
        return False
    if _path_in_xfer_staging(path):
        return _is_incomplete_transfer_file(path, expected) or _is_paste_placeholder(path, expected)
    return _is_paste_placeholder(path, expected)


def cleanup_incomplete_named_files(dests, files_meta, extra_paths=None, staging_xids=None, wipe_all_staging=True):
    """Xóa file tạm/dở (kể cả 0 byte) theo tên đang copy và đường dẫn phụ."""
    cleanup_probe_stubs()
    for dest in list(dests or []):
        _scrub_probe_from_dest(dest)
    for p in list(extra_paths or []):
        if p:
            _retry_remove_path(p)
    abort_xids = None
    if staging_xids is not None:
        abort_xids = set()
        for x in staging_xids:
            try:
                abort_xids.add(int(x))
            except Exception:
                pass
    seen = set()
    dest_list = []
    for dest in list(dests or []):
        if not dest:
            continue
        try:
            key = os.path.normcase(os.path.abspath(dest))
        except Exception:
            continue
        if key in seen:
            continue
        seen.add(key)
        dest_list.append(dest)
        if os.path.isdir(dest):
            try:
                for name in os.listdir(dest):
                    if not name.startswith(".rdxfer_"):
                        continue
                    if not wipe_all_staging:
                        try:
                            xid = int(name[8:])
                        except Exception:
                            continue
                        if abort_xids is None or xid not in abort_xids:
                            continue
                    elif abort_xids is not None:
                        try:
                            xid = int(name[8:])
                        except Exception:
                            continue
                        if xid not in abort_xids:
                            continue
                    _retry_remove_path(os.path.join(dest, name))
            except Exception:
                pass
    for f in list(files_meta or []):
        if isinstance(f, dict):
            name = str(f.get("name") or "")
            expected = _file_expected_size(f)
        else:
            name = str(f or "")
            expected = None
        if not name:
            continue
        rel = name.replace("/", os.sep).replace("\\", os.sep).lstrip("\\/")
        for dest in dest_list:
            if not dest or not os.path.isdir(dest):
                continue
            p = os.path.join(dest, rel)
            if _is_transfer_junk_at_dest(p, expected):
                if _retry_remove_path(p):
                    print(f"[FileTransfer] Da xoa file tam/do dang: {p}")


class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


_HOOKPROC = ctypes.WINFUNCTYPE(LRESULT_64, ctypes.c_int, WPARAM_64, LPARAM_64)
_CallNextHookEx = ctypes.WINFUNCTYPE(
    LRESULT_64, ctypes.c_void_p, ctypes.c_int, WPARAM_64, LPARAM_64
)(("CallNextHookEx", ctypes.windll.user32))


def _install_paste_ll_hooks(on_ctrl_v, on_lbutton, on_rbutton):
    """Hook LL chỉ cho clipboard-agent (host). Callback phải PostMessage, không OpenClipboard."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    user32.SetWindowsHookExW.restype = ctypes.c_void_p

    def _kb(nCode, wParam, lParam):
        try:
            if nCode >= 0 and int(wParam) in (0x0100, 0x0104):
                kb = ctypes.cast(int(lParam), ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
                vk = int(kb.vkCode)
                ctrl = bool(user32.GetAsyncKeyState(0x11) & 0x8000)
                shift = bool(user32.GetAsyncKeyState(0x10) & 0x8000)
                if (vk in (0x56, 0x76) and ctrl) or (vk == 0x2D and shift):
                    on_ctrl_v()
        except Exception:
            pass
        return _CallNextHookEx(None, nCode, wParam, lParam)

    def _mouse(nCode, wParam, lParam):
        try:
            if nCode >= 0:
                msg = int(wParam)
                if msg in (0x0201, 0x0203):
                    on_lbutton()
                elif msg in (0x0204, 0x0206):
                    on_rbutton()
        except Exception:
            pass
        return _CallNextHookEx(None, nCode, wParam, lParam)

    kb_proc = _HOOKPROC(_kb)
    mouse_proc = _HOOKPROC(_mouse)
    hmod = kernel32.GetModuleHandleW(None)
    hk_kb = user32.SetWindowsHookExW(13, kb_proc, hmod, 0)
    hk_mouse = user32.SetWindowsHookExW(14, mouse_proc, hmod, 0)
    _LL_HOOK_KEEPALIVE.extend((kb_proc, mouse_proc, hk_kb, hk_mouse))
    return hk_kb, hk_mouse


def _probe_stub_paths(pending_files=None):
    """Một file 0-byte tên giả để Win11 bật Paste. Không dùng tên file đang copy:
    Explorer coi HDROP này là danh sách dán và copy stub vào thư mục đích."""
    del pending_files
    try:
        os.makedirs(_PROBE_STUB_DIR, exist_ok=True)
    except Exception:
        return [_DUMMY_HDROP_PATH]
    path = os.path.join(_PROBE_STUB_DIR, _PROBE_STUB_NAME)
    try:
        if not os.path.exists(path):
            with open(path, "ab"):
                pass
        _hide_win_path(path)
        return [path]
    except Exception:
        return [_DUMMY_HDROP_PATH]


def _is_probe_stub_name(name):
    n = os.path.basename(str(name or "")).lower()
    return n == _PROBE_STUB_NAME.lower() or n.startswith(".__rd_clipboard_probe")


def _scrub_probe_from_dest(dest_dir):
    """Explorer hay copy stub HDROP vào thư mục Paste — xóa ngay."""
    if not dest_dir or not os.path.isdir(dest_dir):
        return
    try:
        names = os.listdir(dest_dir)
    except Exception:
        names = [_PROBE_STUB_NAME]
    for name in names:
        if _is_probe_stub_name(name):
            _retry_remove_path(os.path.join(dest_dir, name), retries=8)


def _schedule_scrub_probe(dest_dir):
    if not dest_dir:
        return
    _scrub_probe_from_dest(dest_dir)
    for delay in (0.15, 0.4, 0.9, 1.8, 3.5):
        try:
            threading.Timer(delay, lambda d=dest_dir: _scrub_probe_from_dest(d)).start()
        except Exception:
            pass


def _offer_empty_hdrop():
    """HDROP rỗng: không tạo file 0 byte trong thư mục dán."""
    dummy_h = create_hdrop_data([])
    if dummy_h:
        fn_SetClipboardData(15, dummy_h)
        return True
    return False


def _offer_probe_hdrop(pending_files=None):
    """Không gắn file thật vào HDROP — Explorer sẽ dán stub vào thư mục đích (lần Paste 2, 3, …)."""
    del pending_files
    return _offer_empty_hdrop()


def _hwnd_looks_like_popup_menu(hwnd):
    """Top-level popup menu (classic hoặc flyout Win11), không phải cửa sổ Explorer."""
    user32 = ctypes.windll.user32
    try:
        if not hwnd or not user32.IsWindowVisible(hwnd):
            return False
    except Exception:
        return False
    cls = _hwnd_class_name(hwnd)
    if cls in _CONTEXT_MENU_CLASSES:
        return True
    if cls not in (
        "XamlExplorerHostIslandWindow",
        "Microsoft.UI.Content.DesktopChildSiteBridge",
        "Windows.UI.Composition.DesktopWindowContentBridge",
    ):
        return False
    try:
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long),
            ]
        rc = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rc)):
            return False
        w, h = rc.right - rc.left, rc.bottom - rc.top
        style = int(user32.GetWindowLongW(ctypes.c_void_p(hwnd), -16) or 0)
        ws_popup = bool(style & 0x80000000)
        return ws_popup and 40 < h < 900 and 80 < w < 720
    except Exception:
        return False


_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _context_menu_open():
    """Menu chuột phải đang hiện: #32768 / popup Win11 (EnumWindows, không FindWindow ẩn)."""
    user32 = ctypes.windll.user32
    found = ctypes.c_int(0)

    def _enum(hwnd, _lparam):
        if _hwnd_looks_like_popup_menu(hwnd):
            found.value = 1
            return 0
        return 1

    try:
        cb = _WNDENUMPROC(_enum)
        user32.EnumWindows(cb, 0)
        if found.value:
            return True
    except Exception:
        pass
    try:
        from ctypes import wintypes

        class RECT_SIMPLE(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long),
            ]

        class GUITHREADINFO_SIMPLE(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong), ("flags", ctypes.c_ulong),
                ("hwndActive", ctypes.c_void_p), ("hwndFocus", ctypes.c_void_p),
                ("hwndCapture", ctypes.c_void_p), ("hwndMenuOwner", ctypes.c_void_p),
                ("hwndMoveSize", ctypes.c_void_p), ("hwndCaret", ctypes.c_void_p),
                ("rcCaret", RECT_SIMPLE),
            ]

        user32.GetOpenClipboardWindow.restype = ctypes.c_void_p
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        for hwnd_check in (user32.GetOpenClipboardWindow(), user32.GetForegroundWindow()):
            if not hwnd_check:
                continue
            pid = wintypes.DWORD()
            tid = user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd_check), ctypes.byref(pid))
            gui_info = GUITHREADINFO_SIMPLE()
            gui_info.cbSize = ctypes.sizeof(GUITHREADINFO_SIMPLE)
            if user32.GetGUIThreadInfo(tid, ctypes.byref(gui_info)):
                if gui_info.flags & (0x04 | 0x10 | 0x08) or gui_info.hwndMenuOwner:
                    return True
    except Exception:
        pass
    return False


def _double_click_ms():
    try:
        return int(ctypes.windll.user32.GetDoubleClickTime() or 500)
    except Exception:
        return 500


def _cursor_xy():
    pt = wintypes.POINT()
    try:
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return int(pt.x), int(pt.y)
    except Exception:
        return 0, 0


def check_is_menu_query(last_lbutton, last_rbutton, meta_arrival_time, last_ctrl_v=0.0, expect_repaste=False, lmb_on_menu=False, menu_item_kind="", last_dblclick=0.0):
    """
    WM_RENDERFORMAT: 'MENU' / 'BACKGROUND' = chỉ trả dummy HDROP.
    False = Paste thật (Ctrl+V / click Paste trên menu / nút Paste thanh lệnh).
    """
    user32 = ctypes.windll.user32
    from ctypes import wintypes

    try:
        user32.GetOpenClipboardWindow.restype = wintypes.HWND
        hwnd_clip = user32.GetOpenClipboardWindow()
        if hwnd_clip:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd_clip, ctypes.byref(pid))
            if pid.value == os.getpid():
                log_debug("[check_is_menu_query] BACKGROUND: process nay dang mo clipboard")
                return "BACKGROUND"
            proc_name = _pid_image_name(pid.value)
            if proc_name in _CLIPBOARD_PROBE_PROCS and proc_name not in _EXPLORER_CLIPBOARD_PROCS:
                log_debug(f"[check_is_menu_query] BACKGROUND: probe {proc_name}")
                return "BACKGROUND"
    except Exception:
        pass

    t_now = time.time()
    time_since_lbutton = t_now - (last_lbutton or 0)
    time_since_rbutton = t_now - (last_rbutton or 0)
    meta_age = t_now - (meta_arrival_time or 0)
    lmb_down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
    rmb_down = bool(user32.GetAsyncKeyState(0x02) & 0x8000)
    menu_visible = _context_menu_open()
    is_ctrl_v = (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000)
    is_shift_ins = (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000)
    recent_ctrl_v = bool(last_ctrl_v and (t_now - last_ctrl_v) < 2.0)
    # Double-click (mở file trong Explorer) không bao giờ là Paste. Ô lệnh Win11 nằm
    # sát hàng file đầu tiên nên double-click dễ bị nhận nhầm là bấm nút Paste.
    recent_dblclick = bool(last_dblclick and (t_now - last_dblclick) < 0.7)

    # Chuột phải đang giữ: Explorer GetData để vẽ mục Paste — chưa phải Paste.
    if rmb_down:
        log_debug("[check_is_menu_query] MENU: RMB dang giu")
        return "MENU"
    if lmb_on_menu and menu_item_kind == "not_paste":
        log_debug("[check_is_menu_query] MENU: click khong phai Paste (Show more / muc khac)")
        return "MENU"

    if is_ctrl_v or is_shift_ins or recent_ctrl_v:
        log_debug("[check_is_menu_query] Paste: phim Ctrl+V / Shift+Ins")
        return False

    clicked_paste_item = bool(
        lmb_on_menu
        and menu_item_kind != "not_paste"
        and time_since_lbutton < 3.0
    )
    rmb_then_lmb = bool(
        (last_lbutton or 0) > (last_rbutton or 0) > 0
        and time_since_lbutton < 3.0
        and time_since_rbutton < 12.0
        and menu_item_kind != "not_paste"
    )
    cmd_bar_paste = bool(
        (not lmb_on_menu)
        and _is_windows_11() and lmb_down and _cursor_in_explorer_command_bar()
        and time_since_rbutton > 0.2
        and not recent_dblclick
    )

    if clicked_paste_item or rmb_then_lmb:
        log_debug("[check_is_menu_query] Paste: click muc Paste tren menu")
        return False
    if cmd_bar_paste:
        log_debug("[check_is_menu_query] Paste: Win11 command-bar")
        return False
    if menu_visible:
        log_debug("[check_is_menu_query] MENU: context menu dang mo (chua click Paste)")
        return "MENU"

    try:
        import win32gui
        hwnd_fg = win32gui.GetForegroundWindow()
        if hwnd_fg:
            title = win32gui.GetWindowText(hwnd_fg)
            if title and ("Remote Desktop" in title or "Easy Remote" in title):
                log_debug(f"[check_is_menu_query] BACKGROUND: cua so app ({title})")
                return "BACKGROUND"
    except Exception:
        pass

    if _is_explorer_clipboard_client():
        log_debug("[check_is_menu_query] BACKGROUND: Explorer probe (khong phai Paste)")
        return "BACKGROUND"

    log_debug(f"[check_is_menu_query] BACKGROUND: khong co cu chi Paste (meta_age={meta_age:.3f}s)")
    return "BACKGROUND"


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
        self.last_ctrl_v_time = 0
        self._lmb_hit_context_menu = False
        self._lmb_menu_item_kind = ""
        self._paste_gesture_id = 0
        self._consumed_paste_gesture_id = 0
        self._paste_gesture_inc_at = 0.0
        self._lmb_held = False
        self._prev_lbutton_time = 0.0
        self._prev_lbutton_pos = (0, 0)
        self.last_dblclick_time = 0.0
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
        self._down_pipe_q = queue.Queue()
        self._down_pipe_started = False
        self._delayed_setup_tries = 0
        self._allow_delayed = True
        self._force_delayed_setup = False
        self._clip_seq_at_pending = None
        self._last_sent_clip_seq = 0
        self._send_cancelled = False
        self._receive_cancelled = False
        self._send_abort_event = threading.Event()
        self._send_xfer_id = 0
        self._recv_xfer_id = None
        self._aborted_xfer_ids = set()
        self.overwrite_all = False
        
        self.cached_explorer_path = None
        self.dummy_h_active = False
        self._recv_dialog_open = False
        self._reoffer_files = None
        self._rearm_delayed_after_render = False
        self._suppress_render_until = 0.0
        self._expect_repaste_until = 0.0
        self._last_sent_file_seq = None
        self._last_sent_file_fp = None
        self._clip_resync = False
        self._clip_sync_gen = 0
        self._clip_offer_id = 0
        self._clip_offer_in = 0
        self._clip_offer_applied = 0
        self._clip_offer_q = []
        self._clip_offer_lock = threading.Lock()
        self._clip_offer_evt = threading.Event()
        self._clip_offer_worker = threading.Thread(
            target=self._clip_offer_loop, daemon=True, name="ClipOfferQ"
        )
        self._clip_offer_worker.start()
        self._last_ctrl_c_time = 0.0
        self._paste_dest_dir = None
        self._partial_output_paths = []
        self._gui_poll_gen = 0
        self._clipboard_paste_id = 0
        self._cancel_gen = 0
        self._suppress_request_files_until = 0.0
        self._allow_file_xfer = False
        self._xfer_cancel_token = 0
        self._xfer_cancel_at = 0.0
        self._ctrl_v_held = False
        self._shift_ins_held = False
        self._cancelled_paste_ids = set()
        self._active_send_ids = set()
        self._aborted_send_ids = set()
        self._send_id_by_paste = {}
        self._xfer_jobs = {}
        self.xfer_dialogs = {}
        self._xfer_expected_files = {}
        self._fm_send_abort = threading.Event()
        self._last_cancel_ack_time = 0.0
        self._pkt_queue = queue.Queue()
        self._pkt_worker = threading.Thread(target=self._packet_loop, daemon=True, name="ClipPkt")
        self._pkt_worker.start()
        self._send_job_q = queue.Queue()
        self._send_worker_started = False
        self._send_worker_boot_lock = threading.Lock()
        self._send_run_lock = threading.Lock()
        self._xfer_need_resync = False
        self._resume_waiters = {}
        self._xfer_sock_gen = 0
        self.cacher_thread = threading.Thread(target=self._explorer_path_cacher_loop, daemon=True)
        self.cacher_thread.start()
        threading.Thread(target=self._xfer_watchdog_loop, daemon=True, name="ClipXferWatch").start()
        
        # Named Pipe handle cho headless mode (giao tiếp với Clipboard Agent)
        self._pipe_handle = None
        self._pipe_lock = threading.Lock()
        
        # Không cần luồng theo dõi paste vì dùng delayed rendering thực tế
        pass

    def enqueue_packet(self, packet):
        """Nhận packet clipboard/file ngoài luồng input — tránh kẹt chuột viewer khi ghi pipe/file."""
        try:
            self._pkt_queue.put(packet)
        except Exception:
            pass

    def _packet_loop(self):
        while True:
            try:
                packet = self._pkt_queue.get()
            except Exception:
                continue
            if packet is None:
                break
            try:
                self.handle_received_packet(packet)
            except Exception as e:
                print(f"[Clipboard] Packet worker: {e}")

    def clear_local_and_notify_peers(self):
        """Xóa clipboard máy này và báo client/agent xóa theo."""
        self.pending_remote_files = []
        self.dummy_h_active = False
        hwnd = getattr(self, "cached_app_hwnd", None)
        if not hwnd and getattr(self, "listener", None):
            hwnd = getattr(self.listener, "hwnd", None)
        try:
            clear_local_clipboard(hwnd)
        except Exception as e:
            log_debug(f"[clear_local_and_notify_peers] local: {e}")
        if self.app and getattr(self.app, "is_headless", False):
            try:
                threading.Thread(target=self._send_to_pipe, args=("CLEAR", ""), daemon=True).start()
            except Exception:
                pass
        try:
            from network.socket_utils import socket_passwords, send_msg
            pkt = json.dumps({"type": "clear_clipboard"}).encode("utf-8")
            socks = set()
            try:
                socks.update(self.active_sockets)
            except Exception:
                pass
            try:
                socks.update(socket_passwords.keys())
            except Exception:
                pass
            for conn in list(socks):
                try:
                    pw = socket_passwords.get(conn)
                    if pw is not None:
                        send_msg(conn, pkt, pw)
                except Exception:
                    pass
        except Exception as e:
            log_debug(f"[clear_local_and_notify_peers] notify: {e}")

    def _start_uppipe_server(self):
        import win32pipe, win32file
        import time
        print("[Clipboard] UpPipe server bat dau (\\.\pipe\RemoteDesktopClipboardUpPipe).")
        while True:
            try:
                sa = _low_il_everyone_sa()
                pipe_handle = win32pipe.CreateNamedPipe(
                    r"\\.\pipe\RemoteDesktopClipboardUpPipe",
                    win32pipe.PIPE_ACCESS_INBOUND,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    65536, 65536, 0, sa
                )
                if pipe_handle != -1:
                    win32pipe.ConnectNamedPipe(pipe_handle, None)
                    threading.Thread(target=self._handle_uppipe_client, args=(pipe_handle,), daemon=True).start()
            except Exception as e:
                time.sleep(1)

    def _handle_uppipe_client(self, pipe_handle):
        import win32file, json
        try:
            hr, data = win32file.ReadFile(pipe_handle, 1024 * 1024)
            if hr == 0 and data:
                raw = data.decode('utf-8').strip()
                if raw.startswith("CANCEL_TRANSFER") or raw == "CANCEL:" or raw.startswith("CANCEL:"):
                    paste_id = None
                    all_jobs = True
                    try:
                        if "|" in raw:
                            paste_id = int(raw.split("|", 1)[1].strip())
                            all_jobs = False
                    except Exception:
                        paste_id = None
                        all_jobs = True
                    log_debug("[_handle_uppipe_client] Nhận CANCEL_TRANSFER từ Clipboard Agent.")
                    print("[Clipboard] Agent hủy truyền file (nút Hủy).")
                    self.cancel_active_transfer(remote_triggered=False, paste_id=paste_id, all_jobs=all_jobs)
                    return
                if raw.startswith("COPIED_TEXT|"):
                    parts = raw.split("|", 1)
                    text = ""
                    try:
                        text = json.loads(parts[1]) if len(parts) > 1 else ""
                    except Exception:
                        text = parts[1] if len(parts) > 1 else ""
                    if text and self.active_sockets:
                        self._forward_clipboard_text(text)
                        print("[Clipboard] Host→client: đã gửi text từ Clipboard Agent.")
                    return
                # Clipboard Agent gửi REQUEST_FILES khi người dùng thực hiện Paste
                if raw.startswith("REQUEST_FILES"):
                    log_debug("[_handle_uppipe_client] Nhận REQUEST_FILES từ Clipboard Agent. Bắt đầu tải file...")
                    print("[Clipboard] Clipboard Agent yêu cầu tải file (người dùng đã Paste).")
                    
                    parts = raw.split("|", 1)
                    requested_files = []
                    dest_dir = None
                    paste_id = None
                    if len(parts) > 1 and parts[1].strip():
                        try:
                            import json
                            payload = json.loads(parts[1])
                            if isinstance(payload, dict):
                                requested_files = payload.get("files") or []
                                dest_dir = payload.get("dest_dir") or None
                                paste_id = payload.get("paste_id")
                            elif isinstance(payload, list):
                                requested_files = payload
                        except Exception as e:
                            log_debug(f"[_handle_uppipe_client] Lỗi parse requested_files: {e}")
                    if paste_id is not None:
                        try:
                            self._clipboard_paste_id = int(paste_id)
                        except Exception:
                            pass
                            
                    if not requested_files:
                        requested_files = self.pending_remote_files

                    # Tải vào .rdxfer_* ngay trên ổ đích (tránh copy C:→D: xong rồi đứng dialog 1 phút).
                    if dest_dir and os.path.isdir(dest_dir) and not _is_transfer_staging_dir(dest_dir):
                        self._paste_dest_dir = dest_dir
                        self.target_save_dir = dest_dir
                        log_debug(f"[_handle_uppipe_client] paste dest (sau khi tải xong): {dest_dir}")
                        
                    if requested_files:
                        tok = int(getattr(self, "_clipboard_paste_id", 0) or 0)
                        if tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
                            print(f"[FileTransfer] Bo REQUEST_FILES paste_id={tok} (blacklist Huy).")
                            return
                        files_req = list(requested_files)
                        expected = getattr(self, "_xfer_expected_files", None)
                        if expected is None:
                            self._xfer_expected_files = {}
                            expected = self._xfer_expected_files
                        if tok:
                            expected[tok] = files_req
                        # Không ghi đè pending_remote_files — đó là copy mới nhất trên clipboard, không phải file đang Paste.
                        if not self._arm_file_xfer("agent_REQUEST_FILES"):
                            return
                        threading.Thread(
                            target=self.request_pending_files,
                            args=(files_req, tok),
                            daemon=True,
                        ).start()
                    else:
                        log_debug("[_handle_uppipe_client] Không có pending_remote_files để tải.")
                        if self.app and getattr(self.app, 'is_headless', False):
                            self._send_progress_signal("CANCEL", "")
                            self._close_transfer_pipe()
                else:
                    # Metadata file do Clipboard Agent gửi lên (copy file từ phía user)
                    if raw.startswith("COPIED_FILES|"):
                        parts = raw.split("|", 1)
                        offer_id = None
                        paths = json.loads(parts[1]) if len(parts) > 1 else []
                        if isinstance(paths, dict):
                            offer_id = paths.get("offer_id")
                            paths = paths.get("files") or []
                        metadata = []
                        for f in paths:
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
                    else:
                        metadata = json.loads(raw)
                        offer_id = None
                    if metadata and self.active_sockets:
                        self._clip_offer_id = int(getattr(self, "_clip_offer_id", 0) or 0) + 1
                        oid = int(offer_id or 0) or self._clip_offer_id
                        pkt = json.dumps({
                            "type": "files_copied_meta",
                            "files": metadata,
                            "offer_id": oid,
                        }).encode('utf-8')
                        with self.lock:
                            for s in list(self.active_sockets):
                                try: send_msg(s, pkt)
                                except: pass
        except Exception as e:
            log_debug(f"[_handle_uppipe_client] Lỗi: {e}")
        finally:
            try:
                win32file.CloseHandle(pipe_handle)
            except: pass

    def register_app(self, app):
        self.app = app
        self.cached_app_hwnd = None
        if not getattr(self.app, 'is_headless', False):
            try: self.cached_app_hwnd = self.app.winfo_id()
            except: pass
        self._gui_poll_gen = getattr(self, "_gui_poll_gen", 0) + 1
        self.poll_gui_queue(self._gui_poll_gen)
        if getattr(self.app, 'is_headless', False):
            if not getattr(self, "_uppipe_started", False):
                self._uppipe_started = True
                threading.Thread(target=self._cancel_listener_thread, daemon=True).start()
                threading.Thread(target=self._start_uppipe_server, daemon=True).start()
                threading.Thread(target=self._host_text_poll_loop, daemon=True, name="HostClipPoll").start()
            self._ensure_down_pipe()

    def _cancel_listener_thread(self):
        import win32event
        try:
            h_event = _create_user_signalable_event(r"Global\AntigravityP2P_CancelTransfer_Event")
        except Exception as e:
            log_debug(f"[_cancel_listener_thread] Lỗi tạo Event: {e}")
            return
            
        log_debug("[_cancel_listener_thread] Bắt đầu lắng nghe Global\\AntigravityP2P_CancelTransfer_Event...")
        print("[Clipboard] Cancel event listener da bat.")
        while True:
            rc = win32event.WaitForSingleObject(h_event, win32event.INFINITE)
            if rc == win32event.WAIT_OBJECT_0:
                log_debug("[_cancel_listener_thread] Nhận tín hiệu hủy truyền tải từ Agent.")
                print("[Clipboard] Nhan event Huy tu Agent.")
                try:
                    self.cancel_active_transfer(remote_triggered=False)
                except Exception as e:
                    print(f"[Clipboard] cancel_active_transfer loi: {e}")
                try:
                    win32event.ResetEvent(h_event)
                except Exception:
                    pass
                time.sleep(0.05)

    def _host_text_poll_loop(self):
        """Backup: SYSTEM/worker có thể không nhận WM_CLIPBOARDUPDATE — poll text khi đang có viewer."""
        last_seq = 0
        while True:
            time.sleep(0.35)
            try:
                if not self.active_sockets:
                    last_seq = 0
                    continue
                if getattr(self, "dummy_h_active", False):
                    continue
                if getattr(self, "is_rendering", False) or self.transfer_in_progress:
                    continue
                if is_own_clipboard_write():
                    continue
                seq = get_clipboard_sequence_number()
                if not seq or seq == last_seq or seq == getattr(self, "_last_sent_clip_seq", 0):
                    continue
                text = get_clipboard_text()
                if not text:
                    last_seq = seq
                    continue
                last_seq = seq
                print("[Clipboard] Host poll: phát hiện text mới, gửi sang client.")
                self._forward_clipboard_text(text)
            except Exception:
                pass

    def _send_progress_signal(self, data_type, payload):
        """PROGRESS/FILES/CANCEL đi cùng pipe persistent xuống agent."""
        self._send_to_pipe(data_type, payload)

    def _close_transfer_pipe(self):
        # Không ngắt pipe sau mỗi lần tải — agent giữ kết nối để PENDING lần sau hiện Paste ngay.
        return

    def _send_to_pipe(self, data_type, payload):
        """Gửi TYPE:payload xuống Clipboard Agent qua pipe giữ kết nối."""
        self._ensure_down_pipe()
        self._down_pipe_q.put((data_type, payload))
        log_debug(f"[_send_to_pipe] Hàng đợi {data_type} ({len(str(payload))} bytes).")

    def _ensure_down_pipe(self):
        if getattr(self, "_down_pipe_started", False):
            return
        self._down_pipe_started = True
        threading.Thread(target=self._down_pipe_loop, daemon=True, name="ClipDownPipe").start()

    def _down_pipe_loop(self):
        """Giữ 1 kết nối Named Pipe xuống agent — không tạo/đóng pipe mỗi lần PENDING (trễ 0.5–1.5s)."""
        while True:
            pipe_handle = None
            try:
                pipe_handle = create_named_pipe_with_everyone_dacl()
                if pipe_handle is None or pipe_handle == -1:
                    time.sleep(0.15)
                    continue
                log_debug("[_down_pipe_loop] Đang chờ Clipboard Agent kết nối...")
                try:
                    win32pipe.ConnectNamedPipe(pipe_handle, None)
                except Exception as ce:
                    err = getattr(ce, "winerror", 0) or (ce.args[0] if ce.args else 0)
                    if err != 535:
                        raise
                log_debug("[_down_pipe_loop] Agent đã kết nối. Giữ pipe để gửi PENDING/TEXT.")
                while True:
                    data_type, payload = self._down_pipe_q.get()
                    msg = f"{data_type}:{payload}\x00"
                    try:
                        win32file.WriteFile(pipe_handle, msg.encode("utf-8"))
                    except Exception as we:
                        log_debug(f"[_down_pipe_loop] WriteFile lỗi: {we}")
                        try:
                            self._down_pipe_q.put((data_type, payload))
                        except Exception:
                            pass
                        break
            except Exception as e:
                log_debug(f"[_down_pipe_loop] {e}")
            finally:
                if pipe_handle is not None and pipe_handle != -1:
                    try:
                        win32file.FlushFileBuffers(pipe_handle)
                    except Exception:
                        pass
                    try:
                        win32pipe.DisconnectNamedPipe(pipe_handle)
                    except Exception:
                        pass
                    try:
                        win32file.CloseHandle(pipe_handle)
                    except Exception:
                        pass
            time.sleep(0.05)

    def _send_path_to_pipe(self, file_path):
        """
        Gửi đường dẫn file qua Named Pipe cho Clipboard Agent.
        """
        self._send_to_pipe("FILE", file_path)

    def poll_gui_queue(self, gen=None):
        if not self.app:
            return
        if gen is None:
            gen = getattr(self, "_gui_poll_gen", 0)
        if gen != getattr(self, "_gui_poll_gen", 0):
            return
        self.process_gui_queue()
        try:
            self.app.after(50, lambda g=gen: self.poll_gui_queue(g))
        except Exception:
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
                    title_text, filename, total_size = args[0], args[1], args[2]
                    dest_dir = args[3] if len(args) > 3 else None
                    reserve_finalize = args[4] if len(args) > 4 else False
                    job_id = args[5] if len(args) > 5 else None
                    item_kind = args[6] if len(args) > 6 else "file"
                    dialogs = getattr(self, "xfer_dialogs", None)
                    if dialogs is None:
                        self.xfer_dialogs = {}
                        dialogs = self.xfer_dialogs
                    owner_hwnd = getattr(self, "pygame_hwnd", None)
                    if not owner_hwnd and self.app:
                        try:
                            owner_hwnd = int(self.app.winfo_id())
                        except Exception:
                            owner_hwnd = None
                    stack = len([d for d in dialogs.values() if d])
                    jid = job_id if job_id is not None else ("j%d" % (stack + 1))
                    if dialogs.get(jid):
                        continue
                    dlg = ProgressDialog(
                        self.app, title_text, filename, total_size,
                        on_cancel=lambda j=jid: self.cancel_active_transfer(remote_triggered=False, paste_id=j, all_jobs=False),
                        owner_hwnd=owner_hwnd,
                        dest_dir=dest_dir,
                        reserve_finalize=reserve_finalize,
                        stack_index=stack,
                        job_id=jid,
                        item_kind=item_kind,
                    )
                    dialogs[jid] = dlg
                    self.active_dialog = dlg
                elif action == "finalize_start":
                    dlg = self._dialog_by_job(args[1] if isinstance(args, (tuple, list)) and len(args) > 1 else None)
                    if dlg:
                        try: dlg.begin_finalize((args[0] if isinstance(args, (tuple, list)) else args) or 0)
                        except: pass
                elif action == "finalize_progress":
                    dlg = self._dialog_by_job(args[1] if isinstance(args, (tuple, list)) and len(args) > 1 else None)
                    if dlg:
                        try: dlg.add_finalize_bytes((args[0] if isinstance(args, (tuple, list)) else args) or 0)
                        except: pass
                elif action == "complete":
                    dlg = self._dialog_by_job(args if not isinstance(args, (tuple, list)) else (args[0] if args else None))
                    if dlg:
                        try: dlg.mark_complete()
                        except: pass
                elif action == "update":
                    if isinstance(args, (tuple, list)):
                        sent_bytes, job_id = args[0], (args[1] if len(args) > 1 else None)
                    else:
                        sent_bytes, job_id = args, None
                    dlg = self._dialog_by_job(job_id)
                    if dlg:
                        try: dlg.update_progress(sent_bytes)
                        except: pass
                elif action == "status":
                    if isinstance(args, (tuple, list)):
                        status, job_id = args[0], (args[1] if len(args) > 1 else None)
                    else:
                        status, job_id = args, None
                    dlg = self._dialog_by_job(job_id)
                    if dlg:
                        try:
                            dlg.update_progress(getattr(dlg, "_received", 0), status=status)
                        except Exception:
                            pass
                elif action == "destroy":
                    job_id = args
                    def _do_destroy(j=job_id):
                        dialogs = getattr(self, "xfer_dialogs", None) or {}
                        targets = []
                        if j is None:
                            targets = list(dialogs.items())
                        elif j in dialogs:
                            targets = [(j, dialogs.get(j))]
                        else:
                            targets = []
                        for k, dlg in targets:
                            try:
                                if dlg:
                                    dlg.on_cancel = None
                                    dlg.destroy()
                            except: pass
                            dialogs.pop(k, None)
                        self.active_dialog = next(iter(dialogs.values()), None) if dialogs else None
                    self.app.after(0, _do_destroy)
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
            self._xfer_sock_gen = getattr(self, "_xfer_sock_gen", 0) + 1

    def _forward_clipboard_text(self, text):
        """Gửi text clipboard sang viewer. Cùng nội dung copy lần 2 vẫn gửi (theo sequence)."""
        if not text or not self.active_sockets:
            return False
        if is_own_clipboard_write():
            return False
        seq = get_clipboard_sequence_number()
        if seq and seq == getattr(self, "_last_sent_clip_seq", 0):
            return False
        self.last_sent_text = text
        if seq:
            self._last_sent_clip_seq = seq
        pkt = json.dumps({"type": "clipboard_text", "text": text}).encode("utf-8")
        sent = False
        with self.lock:
            sockets_to_remove = []
            for s in list(self.active_sockets):
                try:
                    send_msg(s, pkt)
                    sent = True
                except Exception:
                    sockets_to_remove.append(s)
            for s in sockets_to_remove:
                if s in self.active_sockets:
                    self.active_sockets.remove(s)
        return sent
            
    def remove_socket(self, sock):
        with self.lock:
            if sock in self.active_sockets:
                self.active_sockets.remove(sock)
            if self.sock == sock:
                self.sock = list(self.active_sockets)[0] if self.active_sockets else None
            # Also clean up socket passwords
            socket_passwords.pop(sock, None)

    def _dialog_by_job(self, job_id=None):
        dialogs = getattr(self, "xfer_dialogs", None) or {}
        if job_id is not None:
            return dialogs.get(job_id)
        return self.active_dialog

    def note_paste_gesture(self):
        now = time.time()
        if now - getattr(self, "_paste_gesture_inc_at", 0) < 0.08:
            return
        self._paste_gesture_inc_at = now
        self._paste_gesture_id = getattr(self, "_paste_gesture_id", 0) + 1

    def open_paste_progress_dialog(self, filename, total_size, dest_dir=None, reserve_finalize=True, job_id=None, item_kind="file"):
        """Một lần Paste (job_id) → tối đa một dialog tiến trình."""
        if self.app and getattr(self.app, "is_headless", False):
            return
        dialogs = getattr(self, "xfer_dialogs", None)
        if dialogs is None:
            self.xfer_dialogs = {}
            dialogs = self.xfer_dialogs
        if job_id is not None and dialogs.get(job_id):
            return
        self._recv_dialog_open = True
        self.gui_queue.put((
            "create",
            (_("Đang tải file về..."), filename, total_size, dest_dir, reserve_finalize, job_id, item_kind),
        ))

    def show_dialog(self, title_text, filename, total_size, dest_dir=None, reserve_finalize=False, job_id=None, item_kind="file"):
        self.open_paste_progress_dialog(filename, total_size, dest_dir, reserve_finalize, job_id, item_kind)

    def update_dialog(self, sent_bytes, job_id=None):
        import time
        current_time = time.time()
        times = getattr(self, "_last_update_times", None)
        if times is None:
            self._last_update_times = {}
            times = self._last_update_times
        key = job_id if job_id is not None else "_default"
        last = times.get(key, 0)
        if current_time - last >= 0.05:
            self.gui_queue.put(("update", (sent_bytes, job_id)))
            times[key] = current_time

    def close_dialog(self, job_id=None, reason=None):
        if reason:
            print(f"[Clipboard] Dong dialog job_id={job_id} ly_do={reason}")
        if job_id is None:
            self._recv_dialog_open = False
        self.gui_queue.put(("destroy", job_id))

    def begin_dialog_finalize(self, total_bytes=0, job_id=None):
        self.gui_queue.put(("finalize_start", (total_bytes, job_id)))

    def add_dialog_finalize(self, n, job_id=None):
        self.gui_queue.put(("finalize_progress", (n, job_id)))

    def complete_dialog(self):
        self.gui_queue.put(("complete", None))

    def _coerce_paste_id(self, val):
        if val is None or val is False or val is True:
            return None
        try:
            return int(val)
        except Exception:
            return None

    def _other_xfer_jobs_remain(self, tok):
        jobs = getattr(self, "_xfer_jobs", None) or {}
        for xid, job in jobs.items():
            try:
                pid = int(job.get("paste_id") or 0)
            except Exception:
                pid = 0
            if pid != tok and xid != tok:
                return True
        return False

    def _note_cancelled_paste_id(self, tok):
        try:
            tok = int(tok)
        except Exception:
            return
        if not tok:
            return
        ids = getattr(self, "_cancelled_paste_ids", None)
        if ids is None:
            self._cancelled_paste_ids = set()
            ids = self._cancelled_paste_ids
        ids.add(tok)
        if len(ids) > 64:
            self._cancelled_paste_ids = set(sorted(ids)[-32:])

    def _arm_file_xfer(self, reason=""):
        """Cho phép gửi/nhận file. Paste mới không hủy phiên đang chạy."""
        tok = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        if tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
            print(f"[FileTransfer] Khong arm — paste_id={tok} nam trong blacklist Huy.")
            return False
        self._send_xfer_id = getattr(self, "_send_xfer_id", 0) + 1
        sid = self._send_xfer_id
        ids = getattr(self, "_active_send_ids", None)
        if ids is None:
            self._active_send_ids = set()
            ids = self._active_send_ids
        ids.add(sid)
        mp = getattr(self, "_send_id_by_paste", None)
        if mp is None:
            self._send_id_by_paste = {}
            mp = self._send_id_by_paste
        if tok:
            mp.setdefault(tok, set()).add(sid)
        self._allow_file_xfer = True
        self._send_cancelled = False
        self._receive_cancelled = False
        try:
            if not ids or len(ids) <= 1:
                self._send_abort_event.clear()
        except Exception:
            pass
        self._send_loop_gen = getattr(self, "_cancel_gen", 0)
        self._suppress_request_files_until = 0.0
        print(f"[FileTransfer] Arm xfer ({reason}) id={sid} paste_id={tok} active={list(ids)}")
        return True

    def _disarm_file_xfer(self, reason="", cancelled_paste_id=None, all_jobs=False):
        """Hủy một paste_id, hoặc mọi phiên nếu all_jobs."""
        tok = self._coerce_paste_id(cancelled_paste_id)
        if tok is None:
            tok = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        self._xfer_cancel_token = tok
        if tok:
            self._note_cancelled_paste_id(tok)
        abort_ids = set()
        mp = getattr(self, "_send_id_by_paste", None) or {}
        if all_jobs:
            abort_ids = set(getattr(self, "_active_send_ids", None) or [])
        else:
            abort_ids = set(mp.get(tok) or [])
        aborted = getattr(self, "_aborted_send_ids", None)
        if aborted is None:
            self._aborted_send_ids = set()
            aborted = self._aborted_send_ids
        aborted.update(abort_ids)
        active = getattr(self, "_active_send_ids", None)
        if active is None:
            self._active_send_ids = set()
            active = self._active_send_ids
        active.difference_update(abort_ids)
        for t, sids in list(mp.items()):
            sids.difference_update(abort_ids)
            if not sids:
                mp.pop(t, None)
        still = bool(active) or (not all_jobs and self._other_xfer_jobs_remain(tok))
        if not still:
            self._allow_file_xfer = False
            self._send_cancelled = True
            self._receive_cancelled = True
            try:
                self._send_abort_event.set()
            except Exception:
                pass
            try:
                self._fm_send_abort.set()
            except Exception:
                pass
            self._cancel_gen = getattr(self, "_cancel_gen", 0) + 1
        print(f"[FileTransfer] Disarm ({reason}) token={tok} abort={list(abort_ids)} remain={list(active)}")

    def _send_should_stop(self, my_id):
        if my_id in (getattr(self, "_aborted_send_ids", None) or set()):
            return True
        active = getattr(self, "_active_send_ids", None)
        if active is not None and my_id not in active:
            return True
        return False

    def _cleanup_partial_incoming(self):
        """Đóng handle và xóa file dở (cancel / drain stale) — tránh .exe nửa file + lá chắn UAC."""
        extra = []
        for filename, transfer in list(getattr(self, "incoming_transfers", {}) or {}).items():
            if transfer.get("handle"):
                try:
                    transfer["handle"].close()
                except Exception:
                    pass
            path = transfer.get("path")
            if path:
                extra.append(path)
                if _retry_remove_path(path):
                    print(f"[FileTransfer] Đã xóa file dở dang: {path}")
        self.incoming_transfers = {}

        if hasattr(self, "batch_paths") and self.batch_paths:
            extra.extend(list(self.batch_paths))
            self.batch_paths = []

        extra.extend(list(getattr(self, "_partial_output_paths", None) or []))
        self._partial_output_paths = []

        saved = list(getattr(self, "pending_remote_files", None) or getattr(self, "_reoffer_files", None) or [])
        dests = [
            getattr(self, "target_save_dir", None),
            getattr(self, "_paste_dest_dir", None),
            getattr(self, "cached_explorer_path", None),
            HEADLESS_TRANSFER_DIR,
            os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"),
            _PROBE_STUB_DIR,
        ]
        cleanup_incomplete_named_files(dests, saved, extra_paths=extra)

    def _cleanup_incoming_for_xids(self, abort_xids):
        abort_xids = set(x for x in (abort_xids or []) if x is not None)
        if not abort_xids:
            return
        extra = []
        for key, transfer in list((getattr(self, "incoming_transfers", None) or {}).items()):
            if transfer.get("xfer_id") not in abort_xids:
                continue
            if transfer.get("handle"):
                try:
                    transfer["handle"].close()
                except Exception:
                    pass
            path = transfer.get("path")
            if path:
                extra.append(path)
                _retry_remove_path(path)
            self.incoming_transfers.pop(key, None)
        dests = [
            getattr(self, "_paste_dest_dir", None),
            getattr(self, "cached_explorer_path", None),
            getattr(self, "target_save_dir", None),
            HEADLESS_TRANSFER_DIR,
            os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"),
            _PROBE_STUB_DIR,
        ]
        cleanup_incomplete_named_files(
            dests, [], extra_paths=extra, staging_xids=abort_xids, wipe_all_staging=False
        )

    def _live_xfer_sock(self):
        sock = getattr(self, "sock", None)
        if sock is not None:
            return sock
        try:
            socks = list(self.active_sockets or [])
            if socks:
                return socks[0]
        except Exception:
            pass
        return None

    def _xfer_dialog_status(self, my_id, status):
        jobs = getattr(self, "_xfer_jobs", None) or {}
        job = jobs.get(my_id)
        try:
            pid = int((job or {}).get("paste_id") or getattr(self, "_clipboard_paste_id", 0) or 0)
        except Exception:
            pid = 0
        try:
            self.gui_queue.put(("status", (status, pid or my_id)))
        except Exception:
            pass

    def _xfer_watchdog_loop(self):
        """Khi không nhận chunk > 3s (mạng đứt), đổi tiêu đề dialog sang đang thử lại."""
        while True:
            time.sleep(1.0)
            try:
                jobs = getattr(self, "_xfer_jobs", None) or {}
                now = time.time()
                for xid, job in list(jobs.items()):
                    rec = int(job.get("received") or 0)
                    total = int(job.get("total") or 0)
                    if total and rec >= total:
                        continue
                    last = float(job.get("last_chunk_at") or 0)
                    if not last:
                        continue
                    waiting = (now - last) > 3.0
                    if waiting and not job.get("retry_ui"):
                        job["retry_ui"] = True
                        self._xfer_dialog_status(xid, _("Đang thử kết nối lại, tiếp tục tải..."))
                    elif (not waiting) and job.get("retry_ui"):
                        job["retry_ui"] = False
                        self._xfer_dialog_status(xid, _("Đang tải file về..."))
            except Exception:
                pass

    def _send_file_msg(self, sock, data_bytes, my_id):
        """Gửi gói file; nếu mạng đứt thì chờ socket mới rồi gửi lại cùng gói (chunk có offset nên an toàn)."""
        if not getattr(self, "_allow_file_xfer", False) or self._send_should_stop(my_id):
            return False
        waiting = False
        last_log = 0.0
        sock_gen = getattr(self, "_xfer_sock_gen", 0)
        while True:
            if self._send_should_stop(my_id):
                return False
            live = self._live_xfer_sock() or sock
            if live:
                if send_msg(live, data_bytes):
                    if waiting or getattr(self, "_xfer_sock_gen", 0) != sock_gen:
                        self._xfer_need_resync = True
                        if waiting:
                            print("[FileTransfer] Resume gui sau khi ket noi lai.")
                    return True
            now = time.time()
            if not waiting:
                waiting = True
                print("[FileTransfer] Mat ket noi luc gui — cho reconnect de resume...")
            elif now - last_log > 5.0:
                last_log = now
                print("[FileTransfer] Van cho ket noi lai de resume...")
            time.sleep(0.35)

    def _query_resume_state(self, my_id, paste_id, timeout=8.0):
        """Hỏi máy nhận đã ghi bao nhiêu byte từng file — để seek tiếp, không gửi lại từ đầu."""
        ev = threading.Event()
        box = {"state": {}}
        waiters = getattr(self, "_resume_waiters", None)
        if waiters is None:
            self._resume_waiters = {}
            waiters = self._resume_waiters
        waiters[my_id] = (ev, box)
        pkt = json.dumps({
            "type": "resume_query",
            "xfer_id": my_id,
            "paste_id": paste_id,
        }).encode("utf-8")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._send_should_stop(my_id):
                break
            live = self._live_xfer_sock()
            if live:
                try:
                    send_msg(live, pkt)
                except Exception:
                    pass
                if ev.wait(1.2):
                    break
            else:
                time.sleep(0.3)
        waiters.pop(my_id, None)
        return box.get("state") or {}

    def _resume_snapshot(self, xid):
        files = {}
        for t in (getattr(self, "incoming_transfers", None) or {}).values():
            if t.get("xfer_id") != xid:
                continue
            name = t.get("name")
            written = int(t.get("written") or 0)
            handle = t.get("handle")
            if handle is not None:
                try:
                    handle.flush()
                    written = int(handle.tell())
                    t["written"] = written
                except Exception:
                    pass
            if name:
                files[str(name).replace("\\", "/")] = written
        job = (getattr(self, "_xfer_jobs", None) or {}).get(xid)
        if job:
            stg = _xfer_staging_dir(job.get("save_dir") or HEADLESS_TRANSFER_DIR, xid)
            if os.path.isdir(stg):
                for root, _dirs, fnames in os.walk(stg):
                    for fn in fnames:
                        full = os.path.join(root, fn)
                        rel = os.path.relpath(full, stg).replace("\\", "/")
                        try:
                            sz = os.path.getsize(full)
                        except Exception:
                            continue
                        files[rel] = max(int(files.get(rel) or 0), int(sz))
        return {
            "type": "resume_state",
            "xfer_id": xid,
            "has_job": job is not None,
            "files": files,
            "received": int((job or {}).get("received") or 0),
        }

    def _maybe_send_cancel_ack(self):
        """Báo máy gửi dừng vòng chunk; máy nhận vẫn recv/drain socket."""
        now = time.time()
        if now - getattr(self, "_last_cancel_ack_time", 0) < 0.15:
            return
        self._last_cancel_ack_time = now
        sock = getattr(self, "sock", None)
        if not sock:
            return
        try:
            send_msg(
                sock,
                json.dumps({
                    "type": "cancel_ack",
                    "paste_id": int(getattr(self, "_xfer_cancel_token", 0) or getattr(self, "_clipboard_paste_id", 0) or 0),
                }).encode("utf-8"),
                lock_timeout=0.05,
            )
        except Exception:
            pass

    def cancel_active_transfer(self, remote_triggered=False, paste_id=None, all_jobs=None):
        cur = self._coerce_paste_id(paste_id)
        if all_jobs is None:
            all_jobs = cur is None
        if cur is None:
            cur = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        if cur:
            self._note_cancelled_paste_id(cur)
        self._disarm_file_xfer("Huy", cancelled_paste_id=cur, all_jobs=all_jobs)
        self._maybe_send_cancel_ack()
        if all_jobs:
            self._suppress_request_files_until = time.time() + 8.0
            self._suppress_render_until = max(getattr(self, "_suppress_render_until", 0), time.time() + 1.5)
            self._xfer_cancel_at = time.time()
            self.last_ctrl_v_time = 0.0
            self._ctrl_v_held = False
        print(f"[FileTransfer] Huy paste_id={cur} all={all_jobs}")
        jobs = getattr(self, "_xfer_jobs", None) or {}
        abort_xids = []
        if all_jobs:
            abort_xids = list(jobs.keys())
        else:
            for xid, job in list(jobs.items()):
                try:
                    jpid = int(job.get("paste_id") or 0)
                except Exception:
                    jpid = 0
                if jpid and jpid == cur:
                    abort_xids.append(xid)
                elif not jpid and xid == cur:
                    abort_xids.append(xid)
        aborted = getattr(self, "_aborted_xfer_ids", None)
        if aborted is None:
            self._aborted_xfer_ids = set()
            aborted = self._aborted_xfer_ids
        for xid in abort_xids:
            aborted.add(xid)
            jobs.pop(xid, None)
        self._cleanup_incoming_for_xids(abort_xids)
        
        try:
            if hasattr(self, 'batch_display_name'):
                log_activity(_("Truyền file: ") + str(self.batch_display_name) + _(" - Thất bại"))
        except: pass

        # Báo viewer dừng NGAY — không return sớm trước bước này.
        if not remote_triggered:
            pkt = json.dumps({"type": "cancel_transfer", "paste_id": cur}).encode("utf-8")
            socks = set()
            if getattr(self, "sock", None):
                socks.add(self.sock)
            try:
                socks.update(self.active_sockets)
            except Exception:
                pass
            for conn in list(socks):
                try:
                    send_msg(conn, pkt, lock_timeout=0.5)
                except Exception as e:
                    print(f"[FileTransfer] Lỗi gửi tín hiệu hủy: {e}")
        if self.app and getattr(self.app, 'is_headless', False):
            try:
                if all_jobs:
                    self._send_progress_signal("CANCEL", "")
                    self._close_transfer_pipe()
                else:
                    self._send_progress_signal("CANCEL", str(int(cur)))
            except Exception:
                pass
        self.close_dialog(job_id=None if all_jobs else cur, reason="cancel_active_transfer")
        if not all_jobs and (getattr(self, "_xfer_jobs", None) or getattr(self, "_active_send_ids", None)):
            return
        
        if not getattr(self, 'transfer_in_progress', False) and not getattr(self, 'incoming_transfers', {}):
            if not getattr(self, 'pending_remote_files', []):
                self._cleanup_partial_incoming()
                self.transfer_done_event.set()
                return
            
        print(f"[FileTransfer] Bắt đầu dọn dẹp hủy truyền tải (remote_triggered={remote_triggered})...")
        
        saved_pending = list(getattr(self, "pending_remote_files", None) or getattr(self, "_reoffer_files", None) or [])
        self.is_paste_triggered = False
        self._recv_dialog_open = False
        # Giữ metadata để Paste lại. Đừng EmptyClipboard — đang trong WM_RENDERFORMAT
        # thì handler sẽ SetClipboardData delayed; ngoài handler thì setup lại bên dưới.
        if saved_pending:
            self._reoffer_files = saved_pending
            self.pending_remote_files = saved_pending
            self._expect_repaste_until = time.time() + 60.0
        else:
            self.pending_remote_files = []
            self._reoffer_files = None
        
        # 2. Tắt cờ truyền tải
        self.transfer_in_progress = False
        self._send_cancelled = True
        self._cleanup_partial_incoming()
        cancel_gen = getattr(self, "_cancel_gen", 0)

        def _delayed_cleanup(gen=cancel_gen):
            if getattr(self, "_allow_file_xfer", False):
                return
            if getattr(self, "_cancel_gen", 0) != gen:
                return
            self._cleanup_partial_incoming()

        try:
            threading.Timer(0.4, _delayed_cleanup).start()
            threading.Timer(1.2, _delayed_cleanup).start()
        except Exception:
            pass

        # 4. Đóng progress dialog
        if self.active_dialog:
            try:
                self.active_dialog.on_cancel = None
            except:
                pass
        self.close_dialog(reason="huy truyen tai")
        if self.app:
            try:
                if hasattr(self.app, 'update_status'):
                    self.app.after(0, lambda: self.app.update_status(_("Đã hủy truyền tải file.")))
            except:
                pass
            
        # 6. Mở khóa vòng chờ paste; GIỮ cờ hủy để bỏ chunk còn trên socket.
        # Worker headless không chạy WM_RENDERFORMAT — không được xóa _receive_cancelled.
        self.transfer_done_event.set()
        self.transfer_in_progress = False
        if not getattr(self, "is_rendering", False):
            if saved_pending:
                log_debug("[cancel_active_transfer] Đăng ký lại delayed CF_HDROP để Paste lại.")
                self._schedule_delayed_rearm(0.45)

    def on_foreground_changed(self, hwnd):
        # Hàm này được gọi khi cửa sổ đang active (foreground) thay đổi
        # Nếu chúng ta đang chạy ở mode Client (có Pygame Viewer)
        if getattr(self, 'pygame_hwnd', None) and hwnd == self.pygame_hwnd:
            log_debug("[on_foreground_changed] Cửa sổ Host Viewer vừa được kích hoạt! Kiểm tra đồng bộ Clipboard...")
            # Ném clipboard cho host nếu có thay đổi
            self.on_clipboard_changed(force_sync=True)

    def on_clipboard_changed(self, force_sync=False):
        if not ENABLE_CLIPBOARD_SYNC: return
        if is_own_clipboard_write() and not force_sync:
            return
        hwnd = getattr(self.listener, "hwnd", None) if self.listener else None
        if should_preserve_user_clipboard(hwnd):
            # Chỉ nhả delayed khi user copy SAU offer remote. Preserve mọi lúc
            # sẽ tắt delayed ngay lúc files_copied_meta (host→client) vừa tới.
            if self._user_clipboard_wins():
                self._allow_delayed = False
        
        # Copy file trên Explorer máy client: đọc lại clipboard sau khi Explorer xong SetClipboard.
        self._last_clip_event_at = time.time()
        if clipboard_has_file_formats():
            self._schedule_copied_files_sync()
            if getattr(self, "pygame_hwnd", None) and not force_sync:
                return
        if getattr(self, 'pygame_hwnd', None) and not force_sync:
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            fg_hwnd = user32.GetForegroundWindow()
            if fg_hwnd != self.pygame_hwnd:
                log_debug("[on_clipboard_changed] Ngoài viewer: đồng bộ file copy, giữ text/ảnh máy thật.")
                return
        
        # Tránh tự kích hoạt vòng lặp khi chính ứng dụng thiết lập delayed rendering
        try:
            user32 = ctypes.windll.user32
            user32.GetClipboardOwner.restype = ctypes.c_void_p
            owner = user32.GetClipboardOwner()
            if owner:
                buffer = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ctypes.c_void_p(owner), buffer, 256)
                class_name = buffer.value
                if class_name in ("AntigravityClipboardAgentWnd", "HiddenClipboardListener"):
                    log_debug(f"[on_clipboard_changed] Bỏ qua sự kiện thay đổi clipboard do cửa sổ lớp {class_name} sở hữu (delayed rendering).")
                    return
            if self.listener and self.listener.hwnd and owner == self.listener.hwnd:
                log_debug("[on_clipboard_changed] Bỏ qua sự kiện thay đổi clipboard do chính mình sở hữu (listener hwnd).")
                return
        except Exception as e:
            log_debug(f"[on_clipboard_changed] Lỗi kiểm tra GetClassName/GetClipboardOwner: {e}")

        with self.lock:
            if hasattr(self, '_clipboard_timer') and self._clipboard_timer:
                try:
                    self._clipboard_timer.cancel()
                except:
                    pass
            self._clipboard_timer = threading.Timer(
                0.15,
                lambda fs=force_sync: self._process_clipboard_change_debounced(force=fs),
            )
            self._clipboard_timer.daemon = True
            self._clipboard_timer.start()

    def _schedule_copied_files_sync(self):
        """Đọc file list sau khi seq clipboard ổn định; không gửi list cũ khi user đã copy file mới."""
        gen = getattr(self, "_clip_sync_gen", 0) + 1
        self._clip_sync_gen = gen
        old = getattr(self, "_clip_sync_timer", None)
        if old is not None:
            try:
                old.cancel()
            except Exception:
                pass

        is_client = bool(getattr(self, "pygame_hwnd", None))

        def _pass(g=gen, tries=0):
            if g != getattr(self, "_clip_sync_gen", 0):
                return
            seq_before = get_clipboard_sequence_number()
            files = get_clipboard_files(retries=1, allow_hdrop=not is_client)
            seq_after = get_clipboard_sequence_number()
            if seq_before and seq_after and seq_before != seq_after and tries < 4:
                t = threading.Timer(0.12, lambda: _pass(g, tries + 1))
                t.daemon = True
                t.start()
                self._clip_sync_timer = t
                return
            if files:
                fp = tuple(os.path.abspath(f).lower() for f in files)
                last_fp = getattr(self, "_last_sent_file_fp", None)
                last_seq = getattr(self, "_last_sent_file_seq", None)
                if last_fp and fp == last_fp and seq_after and seq_after != last_seq and tries < 4:
                    t = threading.Timer(0.12, lambda: _pass(g, tries + 1))
                    t.daemon = True
                    t.start()
                    self._clip_sync_timer = t
                    return
                self._process_clipboard_change(provided_files=files, force=True)
            if g == getattr(self, "_clip_sync_gen", 0):
                now_seq = get_clipboard_sequence_number()
                if now_seq and seq_after and now_seq != seq_after:
                    self._schedule_copied_files_sync()

        t = threading.Timer(0.22, lambda: _pass(gen, 0))
        t.daemon = True
        t.start()
        self._clip_sync_timer = t

    def _process_clipboard_change_debounced(self, provided_files=None, force=False):
        if getattr(self, '_is_processing_clipboard', False) and not force:
            self._clip_resync = True
            return
        self._is_processing_clipboard = True
        try:
            self._process_clipboard_change(provided_files, force=force)
        finally:
            self._is_processing_clipboard = False
            if getattr(self, "_clip_resync", False):
                self._clip_resync = False
                threading.Timer(
                    0.05,
                    lambda: self._process_clipboard_change_debounced(force=True),
                ).start()

    def _process_clipboard_change(self, provided_files=None, force=False):
        try:
            time.sleep(0.02) # Chờ xíu để Windows thả file lock (giảm delay)
            
            owner_hwnd = getattr(self, 'cached_app_hwnd', None)
            if provided_files is not None:
                current_files = provided_files
            elif any(
                (t or {}).get("handle")
                for t in (getattr(self, "incoming_transfers", None) or {}).values()
            ):
                current_files = []
            elif getattr(self, "pygame_hwnd", None):
                # Client: HDROP/CIDA chỉ đọc qua _schedule_copied_files_sync.
                current_files = []
            else:
                current_files = get_clipboard_files(retries=1)
                if not current_files:
                    time.sleep(0.05)
                    current_files = get_clipboard_files(retries=1)
            if current_files:
                # Bỏ qua nếu có bất kỳ file nào nằm trong thư mục tạm RemoteDesktopTransfers (để tránh vòng lặp clipboard)
                temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                temp_dir_abs = os.path.abspath(temp_dir).lower()
                headless_dir_abs = os.path.abspath(HEADLESS_TRANSFER_DIR).lower()
                if any(os.path.abspath(f).lower().startswith(temp_dir_abs) or os.path.abspath(f).lower().startswith(headless_dir_abs) for f in current_files):
                    log_debug("[_process_clipboard_change] Bỏ qua vì phát hiện tệp tin trong thư mục tạm (tránh lặp clipboard).")
                    return
                    
                with self.lock:
                    current_files_lower = [os.path.abspath(f).lower() for f in current_files]
                    last_fp = getattr(self, "_last_sent_file_fp", None)
                    seq = get_clipboard_sequence_number()
                    files_changed = tuple(current_files_lower) != last_fp
                    seq_changed = bool(seq) and seq != getattr(self, "_last_sent_file_seq", None)
                    if not files_changed:
                        if not force and not seq_changed:
                            return
                        if not seq_changed and (time.time() - getattr(self, "last_files_time", 0)) < 0.4:
                            log_debug("[_process_clipboard_change] Bỏ qua: copy trùng (cùng file).")
                            return
                    self.last_current_files = current_files
                    self.last_files_time = time.time()
                    self._last_sent_file_seq = seq
                    self._last_sent_file_fp = tuple(current_files_lower)
                
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
                if metadata:
                    self._clip_offer_id = int(getattr(self, "_clip_offer_id", 0) or 0) + 1
                    names = [m.get("name") or os.path.basename(m.get("path") or "") for m in metadata]
                    if self.active_sockets:
                        print(f"[Clipboard] Gửi files_copied_meta offer={self._clip_offer_id}: {names}")
                        pkt = json.dumps({
                            "type": "files_copied_meta",
                            "files": metadata,
                            "offer_id": self._clip_offer_id,
                        }).encode('utf-8')
                        sockets_to_remove = []
                        with self.lock:
                            socks = list(self.active_sockets)
                        for s in socks:
                            try:
                                send_msg(s, pkt)
                            except Exception:
                                sockets_to_remove.append(s)
                        if sockets_to_remove:
                            with self.lock:
                                for s in sockets_to_remove:
                                    if s in self.active_sockets:
                                        self.active_sockets.remove(s)
                    else:
                        try:
                            import win32file
                            pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
                            try:
                                import win32pipe
                                win32pipe.WaitNamedPipe(pipe_name, 5000)
                            except Exception:
                                pass
                            pipe_handle = win32file.CreateFile(
                                pipe_name,
                                win32file.GENERIC_WRITE, 0, None,
                                win32file.OPEN_EXISTING, 0, None
                            )
                            win32file.WriteFile(pipe_handle, json.dumps(metadata).encode('utf-8'))
                            win32file.CloseHandle(pipe_handle)
                            log_debug("[_process_clipboard_change] Đã gửi metadata lên Service qua UpPipe.")
                        except Exception as e:
                            log_debug(f"[_process_clipboard_change] Không gửi được metadata lên Service: {e}")
            else:
                # Nếu không phải copy file, kiểm tra xem có phải copy text không
                current_text = get_clipboard_text(owner_hwnd)
                if current_text:
                    if self._forward_clipboard_text(current_text):
                        log_debug(f"[Clipboard] Phát hiện text clipboard mới locally: {current_text[:50]}...")
                        print(f"[Clipboard] Đang gửi text clipboard sang đối tác...")
        except Exception as e:
            print(f"[FileTransfer] Monitor Error: {e}")

    def _user_clipboard_wins(self):
        """User vừa copy file/ảnh/text sau lần PENDING — không được EmptyClipboard."""
        hwnd = getattr(self.listener, "hwnd", None) if self.listener else None
        if not should_preserve_user_clipboard(hwnd):
            return False
        seq = get_clipboard_sequence_number()
        at = getattr(self, "_clip_seq_at_pending", None)
        if at is None:
            return True
        return (not seq) or seq != at

    def setup_delayed_rendering(self):
        log_debug(f"[setup_delayed_rendering] Bắt đầu. self.listener={self.listener}")
        force = getattr(self, "_force_delayed_setup", False)
        if not force:
            if self._user_clipboard_wins():
                self._allow_delayed = False
                log_debug("[setup_delayed_rendering] Giữ clipboard local của user.")
                return
            if not getattr(self, "_allow_delayed", True):
                return
        else:
            self._allow_delayed = True
        if self.listener and self.listener.hwnd:
            ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.listener.hwnd), 0x0400 + 101, 0, 0)
            log_debug("[setup_delayed_rendering] Đã PostMessageW WM_SETUP_DELAYED_RENDERING")
        else:
            log_debug("[setup_delayed_rendering] Lỗi: listener hoặc hwnd chưa sẵn sàng.")

    def _schedule_delayed_rearm(self, delay_s=0.45):
        """Sau Hủy: đợi Explorer xong paste hiện tại rồi mới hứa CF_HDROP lại."""
        self._suppress_render_until = max(getattr(self, "_suppress_render_until", 0), time.time() + delay_s)
        def _go():
            if self.pending_remote_files or self._reoffer_files:
                if not self.pending_remote_files:
                    self.pending_remote_files = list(self._reoffer_files or [])
                log_debug("[delayed_rearm] Đăng ký lại delayed CF_HDROP.")
                self.setup_delayed_rendering()
        threading.Timer(delay_s, _go).start()

    def _execute_setup_delayed_rendering(self):
        if not self.listener or not self.listener.hwnd:
            log_debug("[_execute_setup_delayed_rendering] Lỗi: hwnd chưa sẵn sàng.")
            return
        force = getattr(self, "_force_delayed_setup", False)
        if not force:
            if self._user_clipboard_wins():
                self._allow_delayed = False
                log_debug("[_execute_setup_delayed_rendering] Bỏ EmptyClipboard — clipboard đang thuộc user.")
                return
        else:
            self._allow_delayed = True

        user32 = ctypes.windll.user32
        hwnd = ctypes.c_void_p(self.listener.hwnd)
        log_debug(f"[_execute_setup_delayed_rendering] Đang cố gắng OpenClipboard với HWND: {self.listener.hwnd}")
        if not user32.OpenClipboard(hwnd):
            self._delayed_setup_tries = getattr(self, "_delayed_setup_tries", 0) + 1
            if self._delayed_setup_tries <= 40:
                if force:
                    self._force_delayed_setup = True
                threading.Timer(0.025, self.setup_delayed_rendering).start()
            else:
                err = ctypes.GetLastError()
                log_debug(f"[_execute_setup_delayed_rendering] OpenClipboard THẤT BẠI sau retry. GetLastError: {err}")
            return
        self._delayed_setup_tries = 0
        self._force_delayed_setup = False
        if not force and self._user_clipboard_wins():
            user32.CloseClipboard()
            self._allow_delayed = False
            log_debug("[_execute_setup_delayed_rendering] OpenClipboard xong nhưng clipboard thuộc user — đóng, không EmptyClipboard.")
            return
        log_debug("[_execute_setup_delayed_rendering] OpenClipboard thành công. Đang EmptyClipboard...")
        self.ignore_destroy_clipboard = True
        try:
            user32.EmptyClipboard()
        finally:
            self.ignore_destroy_clipboard = False
            
        # Thiết lập các format loại trừ Clipboard History và Cloud Clipboard
        setup_clipboard_exclusions()
        
        res = fn_SetClipboardData(15, None) # CF_HDROP với delayed rendering (None handle)
        if res:
            global last_clipboard_set_time
            last_clipboard_set_time = time.time()
        err = ctypes.GetLastError()
        log_debug(f"[_execute_setup_delayed_rendering] SetClipboardData CF_HDROP trả về: {res}, GetLastError: {err}")
        user32.CloseClipboard()
        mark_own_clipboard_write()
        print("[Clipboard] Đã thiết lập delayed rendering (CF_HDROP) trên Clipboard và loại trừ Clipboard History.")

    def lost_ownership(self):
        if getattr(self, 'ignore_destroy_clipboard', False):
            log_debug("[lost_ownership] Bỏ qua WM_DESTROYCLIPBOARD vì tự thực hiện EmptyClipboard.")
            return
        self._allow_delayed = False
        print("[Clipboard] Đã mất quyền sở hữu clipboard (người dùng copy dữ liệu khác).")

    def get_active_explorer_path(self):
        # Trả về giá trị đã được cache bởi background thread
        # để tránh lỗi RPC_E_CANTCALLOUT_ININPUTSYNCCALL khi gọi COM trong WM_RENDERFORMAT
        return getattr(self, 'cached_explorer_path', None)

    def _explorer_path_cacher_loop(self):
        """Host paste cần path Explorer. Không gọi COM lúc vừa copy (chuột xoay)."""
        while True:
            time.sleep(0.35)
            try:
                if time.time() - float(getattr(self, "_last_clip_event_at", 0) or 0) < 2.0:
                    continue
                found_path = query_explorer_folder_path()
                if found_path:
                    self.cached_explorer_path = found_path
            except Exception:
                pass

    def show_classic_conflict_dialog(self, filename, source_info, dest_info, has_multiple=False):
        if self.app and getattr(self.app, 'is_headless', False):
            return "replace_all" if has_multiple else "replace"
        self.overwrite_event.clear()
        self.overwrite_choice = None
        self.overwrite_all = False
        
        self.gui_queue.put(("classic_overwrite_dialog", (filename, source_info, dest_info, has_multiple)))
        
        # Chờ luồng GUI; không PeekMessage toàn cục — sẽ nuốt chuột của dialog Tk.
        start_wait = time.time()
        while time.time() - start_wait < 300.0:
            if self.overwrite_event.is_set():
                break
            time.sleep(0.02)
                
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
        last_l = getattr(self, 'last_lbutton_time', 0.0)
        last_r = getattr(self, 'last_rbutton_time', 0.0)
        meta_time = getattr(self, 'meta_arrival_time', 0.0)
        last_ctrl_v = getattr(self, 'last_ctrl_v_time', 0.0)
        is_menu = check_is_menu_query(
            last_l, last_r, meta_time, last_ctrl_v,
            expect_repaste=time.time() < getattr(self, "_expect_repaste_until", 0),
            lmb_on_menu=bool(getattr(self, "_lmb_hit_context_menu", False)),
            menu_item_kind=getattr(self, "_lmb_menu_item_kind", "") or "",
            last_dblclick=getattr(self, "last_dblclick_time", 0.0),
        )
        if is_menu == "MENU":
            log_debug("[render_format] Phát hiện truy vấn menu. Cung cấp dummy HDROP và chờ user dán...")
            if _offer_probe_hdrop(self.pending_remote_files):
                self.dummy_h_active = True
                self.setup_delayed_rendering()
            dest = getattr(self, "cached_explorer_path", None) or self.get_active_explorer_path()
            _schedule_scrub_probe(dest)
            return
        elif is_menu == "BACKGROUND":
            log_debug("[render_format] Probe/menu Explorer — HDROP rỗng (không dán stub 0 byte).")
            if _offer_empty_hdrop():
                self.dummy_h_active = True
                self.setup_delayed_rendering()
            return

        cancel_at = float(getattr(self, "_xfer_cancel_at", 0) or 0)
        if cancel_at:
            new_kb = getattr(self, "last_ctrl_v_time", 0) > cancel_at + 0.15
            new_menu = (
                bool(getattr(self, "_lmb_hit_context_menu", False))
                and getattr(self, "last_lbutton_time", 0) > cancel_at + 0.15
                and getattr(self, "last_rbutton_time", 0) > cancel_at
                and getattr(self, "last_lbutton_time", 0) > getattr(self, "last_rbutton_time", 0)
            )
            if not new_kb and not new_menu:
                log_debug("[render_format] Sau Hủy chưa có thao tác Paste mới — HDROP rỗng.")
                if _offer_empty_hdrop():
                    self.dummy_h_active = True
                    self.setup_delayed_rendering()
                return

        if time.time() < getattr(self, "_suppress_render_until", 0):
            log_debug("[render_format] Ngay sau Hủy — HDROP rỗng, không tải ngầm.")
            if _offer_empty_hdrop():
                self.dummy_h_active = True
                self.setup_delayed_rendering()
            return
            
        if getattr(self, 'is_rendering', False):
            log_debug("[render_format] WM_RENDERFORMAT trùng — HDROP rỗng (tránh dán stub 0 byte).")
            if _offer_empty_hdrop():
                self.dummy_h_active = True
                self.setup_delayed_rendering()
            return

        dest_dir = self.get_active_explorer_path()
        living = any(d for d in (getattr(self, "xfer_dialogs", None) or {}).values() if d)
        if living and getattr(self, "_paste_gesture_id", 0) <= getattr(self, "_consumed_paste_gesture_id", 0):
            log_debug("[render_format] GetData trùng (chưa có Paste mới) — không mở dialog thêm.")
            if _offer_empty_hdrop():
                self.dummy_h_active = True
            return
            
        self.is_rendering = True
        self._expect_repaste_until = 0.0
        self._rearm_delayed_after_render = False
        self._clipboard_paste_id = getattr(self, "_clipboard_paste_id", 0) + 1
        self._consumed_paste_gesture_id = getattr(self, "_paste_gesture_id", 0)
        self._arm_file_xfer("gui_paste")
        self.transfer_in_progress = True # Đặt cờ truyền tải để chặn các sự kiện thay đổi clipboard trong quá trình render
        try:
            print("[Clipboard] Nhận WM_RENDERFORMAT. Đang bắt đầu kiểm tra tệp tin ghi đè...")
            log_debug("[render_format] Nhận WM_RENDERFORMAT. Đang bắt đầu kiểm tra tệp tin ghi đè...")
            
            item_kind, display_name = _copy_batch_kind_and_name(self.pending_remote_files, _("Tệp tin"))
            total_size = sum(f.get("size", 0) for f in self.pending_remote_files)
            log_debug(f"[render_format] Hiển thị dialog truyền tải: {item_kind} {display_name}, size={total_size}")
            log_debug(f"[render_format] Thư mục đích phát hiện: {dest_dir}")
            if not (self.app and getattr(self.app, 'is_headless', False)):
                self.open_paste_progress_dialog(
                    display_name, total_size, dest_dir,
                    reserve_finalize=True, job_id=self._clipboard_paste_id,
                    item_kind=item_kind,
                )
            
            # Giữ _receive_cancelled cho đến batch_start mới (xfer_id) để khỏi ghi chunk lần gửi cũ.
            self.batch_paths = []
            self.transfer_done_event.clear()
            
            def background_download():
                try:
                    temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                    os.makedirs(temp_dir, exist_ok=True)
                    self.target_save_dir = temp_dir
                    log_debug(f"[render_format] Tải vào thư mục tạm rồi chuyển sang đích: {temp_dir}")
            
                    files_to_download = []
                    files_to_replace = []
                    replace_all = False
                    skip_all = False
            
                    if dest_dir and os.path.isdir(dest_dir):
                        cleanup_incomplete_named_files([dest_dir], self.pending_remote_files)
                        _schedule_scrub_probe(dest_dir)
                        recent = getattr(self, "_recent_direct_paste", None)
                        recent_paths = set()
                        if recent and (time.time() - recent[0] < 15.0):
                            recent_paths = recent[1]
                        for f in self.pending_remote_files:
                            filename = f.get("name")
                            dest_file_path = os.path.join(dest_dir, filename)
                    
                            if os.path.exists(dest_file_path):
                                if _is_transfer_junk_at_dest(dest_file_path, f.get("size")):
                                    _retry_remove_path(dest_file_path)
                                    files_to_download.append(f)
                                    continue
                                if os.path.normcase(os.path.abspath(dest_file_path)) in recent_paths:
                                    log_debug(f"[render_format] Bỏ qua conflict {filename}: vừa tải xong vào đích.")
                                    continue
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
                                        dest_info = {"size": dest_stat.st_size, "mtime": dest_stat.st_mtime, "path": dest_file_path}
                                    except:
                                        dest_info = {"size": 0, "mtime": 0, "path": dest_file_path}
                                
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
                                        empty_hdrop = create_hdrop_data([])
                                        if empty_hdrop:
                                            self.ignore_destroy_clipboard = True
                                            res = fn_SetClipboardData(15, empty_hdrop)
                                            if not res: fn_GlobalFree(empty_hdrop)
                                        self.pending_remote_files = []
                                        self.close_dialog(reason="overwrite cancel")
                                        if self.app and getattr(self.app, 'is_headless', False):
                                            self._send_progress_signal("CANCEL", "")
                                            self._close_transfer_pipe()
                                        return
                            else:
                                files_to_download.append(f)
                    else:
                        files_to_download = list(self.pending_remote_files)
                
                    if not files_to_download:
                        log_debug("[render_format] Không có tệp tin nào được chọn để tải (người dùng bỏ qua tất cả).")
                        empty_hdrop = create_hdrop_data([])
                        if empty_hdrop:
                            self.ignore_destroy_clipboard = True
                            res = fn_SetClipboardData(15, empty_hdrop)
                            if not res: fn_GlobalFree(empty_hdrop)
                        self.pending_remote_files = []
                        self.close_dialog(reason="khong co file de tai")
                        if self.app and getattr(self.app, 'is_headless', False):
                            self._send_progress_signal("CANCEL", "")
                            self._close_transfer_pipe()
                        return
                
                    # Đặt lại danh sách tệp tin thực tế cần tải
                    self.pending_remote_files = files_to_download
            
                    # Xóa các file cần ghi đè TRƯỚC khi bắt đầu tải (để tránh xung đột ghi)
                    for p in files_to_replace:
                        try: os.remove(p)
                        except: pass
            
                    # Yêu cầu truyền file thực tế từ đối tác
                    self.request_pending_files(files_to_download)
            
                    # Chờ nhận xong file (không cắt 600s — folder lớn / file >4GB có thể tải lâu hơn).
                    succeeded = False
                    wait_start = time.time()
                    last_hb = wait_start
                    while True:
                        if not getattr(self, "_allow_file_xfer", False) or getattr(self, "_receive_cancelled", False):
                            print("[Clipboard] Dung cho tai file: Huy / allow_xfer=False.")
                            break
                        if self.transfer_done_event.is_set():
                            if not getattr(self, '_receive_cancelled', False):
                                succeeded = True
                            break
                        now = time.time()
                        if now - last_hb >= 60.0:
                            last_hb = now
                            rec = int(getattr(self, "batch_received", 0) or 0)
                            tot = int(getattr(self, "batch_total_size", 0) or 0)
                            print(f"[Clipboard] Dang cho tai xong ({rec}/{tot} bytes, {int(now - wait_start)}s) — dialog van mo.")
                        if not _pump_messages_except_clipboard_render():
                            time.sleep(0.01)
                    
                    if succeeded and self.batch_paths:
                        meta = list(getattr(self, "_reoffer_files", None) or self.pending_remote_files or [])
                        why = []
                        if not _paths_match_expected_sizes(self.batch_paths, meta, detail=why):
                            print("[Clipboard] File chua du dung luong / thieu metadata — khong dan. " + "; ".join(why))
                            log_debug("[render_format] File chưa đủ dung lượng / thiếu metadata — không dán.")
                            succeeded = False
                    if succeeded and self.batch_paths:
                        print(f"[Clipboard] Tải thành công {len(self.batch_paths)} file vào: {self.target_save_dir}")
                        log_debug(f"[render_format] Tải thành công {len(self.batch_paths)} file.")
                
                        temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                        dest_now = dest_dir or getattr(self, "cached_explorer_path", None)
                        if dest_now and os.path.isdir(dest_now) and _is_transfer_staging_dir(self.target_save_dir):
                            fin_id = int(getattr(self, "_clipboard_paste_id", 0) or 0)
                            need_copy = any(not _same_volume(p, dest_now) for p in self.batch_paths)
                            with _file_io_lock:
                                if need_copy:
                                    self.begin_dialog_finalize(
                                        sum(_path_byte_size(p) for p in self.batch_paths),
                                        job_id=fin_id or None,
                                    )
                                orig_paths = list(self.batch_paths)
                                relocated, moved_all = _relocate_transfer_files_unlocked(
                                    self.batch_paths, dest_now,
                                    on_progress=lambda n, j=fin_id: self.add_dialog_finalize(n, j or None),
                                    should_stop=lambda: (
                                        not getattr(self, "_allow_file_xfer", False)
                                        or getattr(self, "_receive_cancelled", False)
                                    ),
                                )
                                try:
                                    _purge_rdxfer_staging(dest_dir=dest_now, extra_paths=orig_paths + list(relocated or []))
                                except Exception:
                                    pass
                            self.batch_paths = relocated
                            if not getattr(self, "_allow_file_xfer", False) or getattr(self, "_receive_cancelled", False):
                                self._cleanup_partial_incoming()
                                succeeded = False
                            elif moved_all:
                                self.target_save_dir = dest_now
                                log_debug(f"[render_format] Đã chuyển file từ thư mục tạm sang: {dest_now}")
                        if succeeded:
                            is_direct_dest = not _is_transfer_staging_dir(self.target_save_dir)
                            if is_direct_dest:
                                log_debug("[render_format] Tải trực tiếp vào đích. Hủy paste của Explorer để tránh lỗi same-file bằng empty HDROP.")
                                empty_hdrop = create_hdrop_data([])
                                if empty_hdrop:
                                    self.ignore_destroy_clipboard = True
                                    res = fn_SetClipboardData(15, empty_hdrop)
                                    if not res: fn_GlobalFree(empty_hdrop)
                                self._reoffer_files = None
                                self.pending_remote_files = []
                                self.dummy_h_active = False
                                self._recent_direct_paste = (
                                    time.time(),
                                    {os.path.normcase(os.path.abspath(p)) for p in self.batch_paths if p}
                                )
                            else:
                                hGlobal = create_hdrop_data(self.batch_paths)
                                if hGlobal:
                                    self.ignore_destroy_clipboard = True
                                    try:
                                        res = fn_SetClipboardData(15, hGlobal)
                                        if not res:
                                            err = ctypes.GetLastError()
                                            log_debug(f"[render_format] Lỗi SetClipboardData: res={res}, GetLastError={err}")
                                            fn_GlobalFree(hGlobal)
                                        else:
                                            log_debug(f"[render_format] Đã nạp thành công CF_HDROP vào Clipboard. res={res}")
                                            if hasattr(self, 'lock'):
                                                with self.lock:
                                                    self.last_current_files = [os.path.abspath(p) for p in self.batch_paths if os.path.exists(p)]
                                                    self.last_files_time = time.time()
                                            seq_after = ctypes.windll.user32.GetClipboardSequenceNumber()
                                            log_debug(f"[render_format] Đã nạp thành công CF_HDROP vào Clipboard. seq_after={seq_after} (Bỏ dọn dẹp để hỗ trợ copy liên tiếp)")
                                    finally:
                                        self.ignore_destroy_clipboard = False
                                        self.pending_remote_files = []
                                else:
                                    log_debug("[render_format] Không tạo được hGlobal, hủy render.")
                                    self.pending_remote_files = []
                            self.complete_dialog()
                            self.close_dialog(reason="render_format xong")
                    if not succeeded:
                        print(f"[Clipboard] Dong dialog paste: that bai/huy succeeded={succeeded} allow={getattr(self, '_allow_file_xfer', None)} cancelled={getattr(self, '_receive_cancelled', None)}")
                        log_debug(f"[render_format] Tải file thất bại. succeeded={succeeded}")
                        reoffer = list(getattr(self, "_reoffer_files", None) or self.pending_remote_files or [])
                        # Trong WM_RENDERFORMAT không được SetClipboardData(NULL): Explorer
                        # vẫn dán xong và tạo file ma (vd. .exe installer với icon lá chắn).
                        empty_hdrop = create_hdrop_data([])
                        if empty_hdrop:
                            self.ignore_destroy_clipboard = True
                            res = fn_SetClipboardData(15, empty_hdrop)
                            if not res:
                                fn_GlobalFree(empty_hdrop)
                            log_debug(f"[render_format] Hủy/thất bại: HDROP rỗng (hủy paste Explorer). res={res}")
                        if reoffer:
                            self.pending_remote_files = reoffer
                            self._reoffer_files = reoffer
                            self._rearm_delayed_after_render = True
                            self._suppress_render_until = time.time() + 0.3
                            self._expect_repaste_until = time.time() + 60.0
                        self.close_dialog(reason="render_format that bai/huy")
                        if self.app and getattr(self.app, 'is_headless', False):
                            self._send_progress_signal("CANCEL", "")
                            self._close_transfer_pipe()
                        # Không bật lại nhận ở đây — chunk lần gửi cũ còn trên socket.
                finally:
                    self.is_rendering = False
                    self.transfer_in_progress = False
                    self.ignore_destroy_clipboard = False
                    
            # Phải SetClipboardData trước khi thoát WM_RENDERFORMAT. Không được
            # spawn thread rồi return — Windows đóng clipboard ngay sau handler.
            background_download()
            if getattr(self, "_rearm_delayed_after_render", False):
                self._rearm_delayed_after_render = False
                if self.pending_remote_files or self._reoffer_files:
                    if not self.pending_remote_files:
                        self.pending_remote_files = list(self._reoffer_files)
                    log_debug("[render_format] Hẹn đăng ký lại delayed CF_HDROP sau hủy.")
                    self._schedule_delayed_rearm(0.45)
            else:
                self._reoffer_files = None
            return
        except Exception as e:
            log_debug(f"[render_format] Lỗi khi xử lý render format: {e}")
            empty_hdrop = create_hdrop_data([])
            if empty_hdrop:
                self.ignore_destroy_clipboard = True
                res = fn_SetClipboardData(15, empty_hdrop)
                if not res: fn_GlobalFree(empty_hdrop)
            self.close_dialog(reason="render_format exception")
            if self.app and getattr(self.app, 'is_headless', False):
                self._send_progress_signal("CANCEL", "")
                self._close_transfer_pipe()
        finally:
            self.transfer_in_progress = False
            self.is_rendering = False
            self.ignore_destroy_clipboard = False

    def _attach_xfer_id(self, payload, xfer_id, paste_id=None):
        payload["xfer_id"] = xfer_id
        if paste_id is not None:
            payload["paste_id"] = paste_id
        return payload

    def _xfer_packet_ok(self, packet, ptype):
        xid = packet.get("xfer_id")
        aborted = getattr(self, "_aborted_xfer_ids", None) or set()
        if xid is not None and xid in aborted:
            return False
        return True

    def _ensure_send_worker(self):
        with self._send_worker_boot_lock:
            if getattr(self, "_send_worker_started", False):
                return
            self._send_worker_started = True
            threading.Thread(target=self._send_job_loop, daemon=True, name="ClipSendQ").start()

    def _enqueue_send_job(self, files, my_id, paste_id):
        """Một lúc chỉ gửi một batch — tránh 2 luồng send_msg/ghi đĩa làm sập máy."""
        self._ensure_send_worker()
        self._send_job_q.put({
            "files": list(files or []),
            "my_id": my_id,
            "paste_id": paste_id,
        })
        print(f"[FileTransfer] Xep hang gui paste_id={paste_id} xfer_id={my_id} (cho={self._send_job_q.qsize()})")

    def _send_job_loop(self):
        while True:
            job = self._send_job_q.get()
            if job is None:
                break
            paste_id = job.get("paste_id")
            my_id = job.get("my_id")
            try:
                tok = int(paste_id or 0)
            except Exception:
                tok = 0
            cancelled = getattr(self, "_cancelled_paste_ids", None) or set()
            if tok and tok in cancelled:
                print(f"[FileTransfer] Bo hang doi paste_id={tok} (da Huy).")
                try:
                    getattr(self, "_active_send_ids", set()).discard(my_id)
                except Exception:
                    pass
                continue
            sock = self._live_xfer_sock()
            if not sock:
                for _ in range(240):
                    if tok and tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
                        break
                    if self._send_should_stop(my_id):
                        break
                    sock = self._live_xfer_sock()
                    if sock:
                        break
                    time.sleep(0.25)
            if not sock:
                print("[FileTransfer] Bo hang doi — khong co socket sau khi cho reconnect.")
                try:
                    getattr(self, "_active_send_ids", set()).discard(my_id)
                except Exception:
                    pass
                continue
            print(f"[FileTransfer] Bat dau gui (hang doi) paste_id={tok} xfer_id={my_id}")
            try:
                with self._send_run_lock:
                    self._process_send_requests(sock, job.get("files") or [], my_id, tok)
            except Exception as e:
                print(f"[FileTransfer] Loi hang doi gui: {e}")

    def request_pending_files(self, files=None, paste_id=None):
        files_req = list(files) if files else list(self.pending_remote_files or [])
        if not files_req or not self.sock:
            return
        if not getattr(self, "_allow_file_xfer", False):
            print("[FileTransfer] Bo request_pending_files (allow_file_xfer=False).")
            return
        try:
            pid = int(paste_id) if paste_id is not None else int(getattr(self, "_clipboard_paste_id", 0) or 0)
        except Exception:
            pid = 0
        if pid in (getattr(self, "_cancelled_paste_ids", None) or set()):
            print(f"[FileTransfer] Bo request_pending_files paste_id={pid} (blacklist Huy).")
            return
        send_msg(self.sock, json.dumps({
            "type": "request_files",
            "files": files_req,
            "paste_id": pid,
        }).encode('utf-8'))

    def _process_send_requests(self, sock, files, my_id=None, paste_id=None):
        if my_id is None:
            my_id = getattr(self, "_send_xfer_id", 0)
        if paste_id is None:
            paste_id = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        if not getattr(self, "_allow_file_xfer", False):
            print("[FileTransfer] Bo qua gui file (allow_file_xfer=False).")
            return
        if self._send_should_stop(my_id):
            print("[FileTransfer] Huy luc bat dau gui — khong gui.")
            return
        self.transfer_in_progress = True
        print(f"[FileTransfer] Bat dau gui {len(files)} file xfer_id={my_id} paste_id={paste_id}")
        log_debug(f"[_process_send_requests] Khởi chạy gửi {len(files)} file... xfer_id={my_id}")
        try:
            total_size = sum(f.get("size", 0) for f in files)
            item_kind, display_name = _copy_batch_kind_and_name(files, _("Tệp tin"))
            self.batch_display_name = display_name
            self.batch_item_kind = item_kind
            
            log_file_transfer(display_name, total_size)
            
            start_pkt = json.dumps(self._attach_xfer_id({
                "type": "batch_start",
                "count": len(files),
                "total_size": total_size,
                "display_name": display_name,
                "item_kind": item_kind,
                "paste_id": paste_id,
            }, my_id, paste_id)).encode('utf-8')
            self._xfer_need_resync = False
            if not self._send_file_msg(sock, start_pkt, my_id):
                print("[FileTransfer] Huy truoc/luc batch_start — dung gui.")
                return
            log_debug(f"[_process_send_requests] Đã gửi batch_start. total_size={total_size}")
            
            total_sent = 0
            batch_start_time = time.time()

            def _lookup_resume_offset(state, name, size):
                fmap = (state or {}).get("files") or {}
                key = str(name or "").replace("\\", "/")
                val = fmap.get(key)
                if val is None:
                    val = fmap.get(name)
                if val is None:
                    val = fmap.get(os.path.basename(key))
                try:
                    already = int(val or 0)
                except Exception:
                    already = 0
                try:
                    size = int(size or 0)
                except Exception:
                    size = 0
                return max(0, min(already, size)) if size else max(0, already)

            for f in files:
                if self._send_should_stop(my_id):
                    log_debug(f"[_process_send_requests] Truyền tải bị hủy ngang.")
                    break
                filepath = f["path"]
                filename = f["name"]
                file_size = f["size"]
                
                log_debug(f"[_process_send_requests] Kiểm tra filepath: {filepath}")
                if not os.path.exists(filepath):
                    log_debug(f"[_process_send_requests] File không tồn tại: {filepath}")
                    continue
                if self._send_should_stop(my_id):
                    log_debug(f"[_process_send_requests] Truyền tải bị hủy ngang.")
                    break
                f_start_pkt = json.dumps(self._attach_xfer_id({
                    "type": "file_start", "name": filename, "size": file_size, "offset": 0
                }, my_id, paste_id)).encode('utf-8')
                if not self._send_file_msg(sock, f_start_pkt, my_id):
                    log_debug(f"[_process_send_requests] Truyền tải bị hủy ngang.")
                    break
                log_debug(f"[_process_send_requests] Đã gửi file_start cho {filename}, size={file_size}")
                file_sent_bytes = 0
                try:
                    live = self._live_xfer_sock() or sock
                    lan = is_lan_socket(live)
                    if lan:
                        tune_socket_for_lan_bulk(live)
                    chunk_size = 64 * 1024
                    file_sent_bytes = 0
                    file_start_time = time.time()
                    
                    with open(filepath, "rb") as fh:
                        while True:
                            if self._send_should_stop(my_id):
                                print("[FileTransfer] Huy — dung doc file phia client.")
                                break

                            if getattr(self, "_xfer_need_resync", False):
                                self._xfer_need_resync = False
                                state = self._query_resume_state(my_id, paste_id, timeout=6.0)
                                if not state.get("has_job"):
                                    print("[FileTransfer] May nhan mat job — gui lai batch_start.")
                                    if not self._send_file_msg(sock, start_pkt, my_id):
                                        break
                                already = _lookup_resume_offset(state, filename, file_size)
                                print(f"[FileTransfer] Resume {filename} offset {file_sent_bytes} -> {already}")
                                try:
                                    fh.seek(already)
                                except Exception:
                                    fh.seek(0)
                                    already = 0
                                file_sent_bytes = already
                                live = self._live_xfer_sock() or sock
                                lan = is_lan_socket(live)
                                if lan:
                                    tune_socket_for_lan_bulk(live)
                                resume_start = json.dumps(self._attach_xfer_id({
                                    "type": "file_start", "name": filename, "size": file_size, "offset": already
                                }, my_id, paste_id)).encode('utf-8')
                                if not self._send_file_msg(sock, resume_start, my_id):
                                    break
                                continue
                            
                            if not lan:
                                elapsed_total = time.time() - batch_start_time
                                current_limit = 500 * 1024 + int(500 * 1024 * elapsed_total)
                                max_limit = 1000 * 1024 * 1024
                                if current_limit > max_limit:
                                    current_limit = max_limit
                            else:
                                current_limit = None
                                
                            chunk_data = fh.read(chunk_size)
                            if not chunk_data:
                                break
                            if self._send_should_stop(my_id):
                                print("[FileTransfer] Huy sau read — khong encode/gui chunk tiep.")
                                break
                                
                            chunk_offset = file_sent_bytes
                            b64 = base64.b64encode(chunk_data).decode('utf-8')
                            if not self._send_file_msg(sock, json.dumps(self._attach_xfer_id({
                                "type": "file_chunk", "name": filename, "data": b64, "offset": chunk_offset
                            }, my_id, paste_id)).encode('utf-8'), my_id):
                                print("[FileTransfer] Huy luc gui — dong file, ngung doc.")
                                break
                            
                            file_sent_bytes += len(chunk_data)
                            total_sent += len(chunk_data)
                            
                            if current_limit:
                                target_time = file_sent_bytes / current_limit
                                actual_time = time.time() - file_start_time
                                if actual_time < target_time:
                                    sleep_dur = target_time - actual_time
                                    if sleep_dur > 2.0:
                                        sleep_dur = 2.0
                                        
                                    sleep_end = time.time() + sleep_dur
                                    while time.time() < sleep_end:
                                        if self._send_should_stop(my_id):
                                            break
                                        time.sleep(0.05)
                                    
                    log_debug(f"[_process_send_requests] Đã gửi xong dữ liệu cho {filename} ({file_sent_bytes}/{file_size})")
                except Exception as e:
                    print(f"[FileTransfer] Lỗi khi gửi file {filename}: {e}")
                    log_debug(f"[_process_send_requests] Lỗi khi gửi file {filename}: {e}")
                    
                if self._send_should_stop(my_id):
                    break
                if file_sent_bytes < int(file_size or 0):
                    print(f"[FileTransfer] {filename} chua du ({file_sent_bytes}/{file_size}) — khong gui file_end.")
                    self._xfer_need_resync = True
                    break
                if self._send_file_msg(sock, json.dumps(self._attach_xfer_id({
                    "type": "file_end", "name": filename
                }, my_id, paste_id)).encode('utf-8'), my_id):
                    log_debug(f"[_process_send_requests] Đã gửi file_end cho {filename}")
                else:
                    print(f"[FileTransfer] {filename} gui file_end that bai.")
                    break
            else:
                # for-loop hết file (không break) — chỉ lúc này mới batch_end.
                if not self._send_should_stop(my_id):
                    if self._send_file_msg(sock, json.dumps(self._attach_xfer_id({"type": "batch_end"}, my_id, paste_id)).encode('utf-8'), my_id):
                        log_debug(f"[_process_send_requests] Đã gửi batch_end.")
                    try: log_activity(_("Truyền file: ") + str(self.batch_display_name) + " - " + str(total_size) + _(" byte - Thành công"))
                    except: pass
                else:
                    print("[FileTransfer] Huy — khong gui batch_end.")
            if self._send_should_stop(my_id):
                print("[FileTransfer] Gui dung giua chung — khong gui batch_end.")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error processing send request: {e}")
            log_debug(f"[_process_send_requests] Lỗi tổng quát:\n{tb}")
            try:
                log_activity(_("Truyền file: ") + str(self.batch_display_name) + " - " + str(total_size) + _(" byte - Thất bại"))
            except: pass
        finally:
            try:
                getattr(self, "_active_send_ids", set()).discard(my_id)
            except Exception:
                pass
            if not getattr(self, "_active_send_ids", None):
                self.transfer_in_progress = False
            log_debug(f"[_process_send_requests] Kết thúc hàm gửi file xfer_id={my_id}.")

    def _enqueue_file_offer(self, files, offer_id=None):
        """Hàng đợi copy file (RAM). Áp từng offer; nếu xếp hàng thì lấy cái mới nhất."""
        if not files:
            return
        snap = []
        for f in files:
            snap.append(dict(f) if isinstance(f, dict) else f)
        oid = 0
        try:
            oid = int(offer_id or 0)
        except Exception:
            oid = 0
        with self._clip_offer_lock:
            if oid <= 0:
                self._clip_offer_in = int(getattr(self, "_clip_offer_in", 0) or 0) + 1
                oid = self._clip_offer_in
            else:
                self._clip_offer_in = max(int(getattr(self, "_clip_offer_in", 0) or 0), oid)
            q = self._clip_offer_q
            last_fp = getattr(self, "_clip_offer_fp", None)
            fp = _file_offer_fp(snap)
            applied = int(getattr(self, "_clip_offer_applied", 0) or 0)
            if oid and oid <= applied and fp == last_fp:
                log_debug(f"[_enqueue_file_offer] Bỏ offer trùng {oid} (đã áp {applied}).")
                return
            if oid and oid <= applied and fp != last_fp:
                oid = applied + 1
                self._clip_offer_in = oid
                print(f"[Clipboard] Offer id cũ nhưng file mới — nhận copy mới oid={oid}")
            self._clip_offer_fp = fp
            q.append({"offer_id": oid, "files": snap})
            while len(q) > 24:
                q.pop(0)
        names = []
        for f in snap[:6]:
            if isinstance(f, dict):
                names.append(f.get("name") or os.path.basename(str(f.get("path") or "")))
        print(f"[Clipboard] Queue offer={oid} n={len(snap)} {names} (q={len(self._clip_offer_q)})")
        self._clip_offer_evt.set()

    def _clip_offer_loop(self):
        while True:
            self._clip_offer_evt.wait(timeout=1.0)
            self._clip_offer_evt.clear()
            while True:
                with self._clip_offer_lock:
                    q = self._clip_offer_q
                    if not q:
                        break
                    if len(q) == 1:
                        item = q.pop(0)
                    else:
                        # Copy dồn: bỏ offer giữa, áp file mới nhất.
                        item = q[-1]
                        q.clear()
                self._apply_file_offer(item)
                time.sleep(0.06)

    def _apply_file_offer(self, item):
        oid = int((item or {}).get("offer_id") or 0)
        files = list((item or {}).get("files") or [])
        if not files:
            return
        with self._clip_offer_lock:
            applied = int(getattr(self, "_clip_offer_applied", 0) or 0)
            fp = _file_offer_fp(files)
            last_fp = getattr(self, "_clip_offer_fp", None)
            if oid and oid < applied and fp == last_fp:
                return
            self._clip_offer_applied = max(applied, oid)
            self._clip_offer_fp = fp
        self.pending_remote_files = files
        self._reoffer_files = list(files)
        self.meta_arrival_time = time.time()
        self._allow_delayed = True
        self._force_delayed_setup = True
        self._clip_seq_at_pending = get_clipboard_sequence_number()
        names = [f.get("name") if isinstance(f, dict) else str(f) for f in files[:8]]
        print(f"[Clipboard] Áp offer={oid} n={len(files)} {names}")
        log_debug(f"[_apply_file_offer] offer={oid} files={len(files)}")

        if self.app and getattr(self.app, "is_headless", False):
            # Đừng đổi target_save_dir khi đang tải paste khác (lần copy N làm lệch lần paste đang chạy).
            if not getattr(self, "_xfer_jobs", None):
                self.target_save_dir = HEADLESS_TRANSFER_DIR
                self.batch_paths = []
            self.transfer_done_event.clear()
            total_size = sum((f.get("size", 0) if isinstance(f, dict) else 0) for f in files)
            item_kind, display_name = _copy_batch_kind_and_name(files, _("Tệp tin"))
            msg_dict = {
                "display_name": display_name,
                "item_kind": item_kind,
                "total_size": total_size,
                "files": files,
                "offer_id": oid,
            }
            self._send_to_pipe("PENDING", json.dumps(msg_dict))
            return

        temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
        self.target_save_dir = temp_dir
        self.setup_delayed_rendering()

    def _paste_dest_for_job(self, job):
        dest = (job or {}).get("paste_dest") or getattr(self, "_paste_dest_dir", None)
        if dest and os.path.isdir(dest) and not _is_transfer_staging_dir(dest):
            return dest
        return None

    def _ensure_dest_tree(self, dest, rel_name):
        if not dest or not rel_name:
            return
        rel = str(rel_name).replace("\\", "/").strip("/")
        top = rel.split("/")[0] if "/" in rel else None
        if top:
            try:
                os.makedirs(os.path.join(dest, top), exist_ok=True)
            except Exception:
                pass

    def _finalize_incoming_file(self, transfer, job, filename):
        """close + kiểm size + đưa file ra thư mục đích. Chạy ngoài ClipPkt (tránh kẹt AV/close 4GB)."""
        path = transfer.get("path")
        expected = transfer.get("expected_size")
        written = int(transfer.get("written") or 0)
        handle = transfer.get("handle")
        if handle is not None:
            try:
                handle.flush()
            except Exception:
                pass
            try:
                handle.close()
            except Exception as e:
                print(f"[FileTransfer] Lỗi đóng handle {filename}: {e}")
        actual = -1
        if path:
            try:
                actual = os.path.getsize(path) if os.path.exists(path) else -1
            except Exception:
                actual = -1
        if expected is not None and actual != expected and written != int(expected or 0):
            print(f"[FileTransfer] Sai kich thuoc {filename}: disk={actual} written={written} expected={expected}, xoa file.")
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
            return
        dest = self._paste_dest_for_job(job)
        final_path = path
        if dest and path and os.path.isfile(path):
            try:
                final_path = _promote_completed_xfer_file(path, dest, filename)
                print(f"[FileTransfer] Da chép {filename} -> {final_path}")
            except Exception as e:
                print(f"[FileTransfer] Promote {filename} loi: {e}")
                final_path = path
        xid = transfer.get("xfer_id")
        job = job or (getattr(self, "_xfer_jobs", None) or {}).get(xid)
        paths = job["paths"] if job is not None else self.batch_paths
        top_level_name = str(filename or "").replace("\\", "/").split("/")[0]
        if dest:
            top_level_path = os.path.join(dest, top_level_name)
        else:
            base_save = (job or {}).get("save_dir") or self.target_save_dir
            top_level_path = os.path.join(_xfer_staging_dir(base_save, xid), top_level_name)
        if top_level_path not in paths:
            paths.append(top_level_path)
        log_debug(f"[file_end] Đã xử lý xong file: {filename} dest={final_path}")

    def _complete_batch_after_files(self, packet):
        xid = packet.get("xfer_id")
        jobs = getattr(self, "_xfer_jobs", None) or {}
        job = jobs.get(xid) if xid is not None else None
        for ev in list((job or {}).get("finish_events") or []):
            while not ev.wait(0.4):
                if (xid is not None and xid in (getattr(self, "_aborted_xfer_ids", None) or set())):
                    return
                pid = (job or {}).get("paste_id")
                try:
                    pid = int(pid or 0)
                except Exception:
                    pid = 0
                if pid and pid in (getattr(self, "_cancelled_paste_ids", None) or set()):
                    return
        self._finish_batch_end(packet)

    def _finish_batch_end(self, packet):
        xid = packet.get("xfer_id")
        jobs = getattr(self, "_xfer_jobs", None) or {}
        job = jobs.get(xid) if xid is not None else None
        paste_id = 0
        try:
            paste_id = int((job or {}).get("paste_id") or packet.get("paste_id") or 0)
        except Exception:
            paste_id = 0
        aborted = getattr(self, "_aborted_xfer_ids", None) or set()
        if (xid is not None and xid in aborted) or (paste_id and paste_id in (getattr(self, "_cancelled_paste_ids", None) or set())):
            log_debug("[batch_end] Đã hủy — bỏ qua FILES.")
            self.close_dialog(job_id=paste_id or xid, reason="batch_end da huy")
            jobs.pop(xid, None)
            if not jobs:
                self.transfer_done_event.set()
                self.transfer_in_progress = False
            return
        ok_paths = list((job or {}).get("paths") or getattr(self, "batch_paths", None) or [])
        self.close_dialog(job_id=paste_id or xid, reason="batch_end xong")
        if not jobs or len(jobs) <= 1:
            self.transfer_done_event.set()
        try:
            import core.viewer
            if core.viewer.file_manager_callback:
                core.viewer.file_manager_callback({"type": "trigger_local_refresh"})
        except: pass
        print(f"[FileTransfer] batch_end xfer_id={xid} paste_id={paste_id} n={len(ok_paths)}")
        log_debug(f"[batch_end] Đã nhận xong xfer_id={xid} paste_id={paste_id} n={len(ok_paths)}")
        try:
            name = (job or {}).get("display_name") or self.batch_display_name
            total = (job or {}).get("total") or self.batch_total_size
            log_activity(_("Nhận file: ") + str(name) + " - " + str(total) + _(" byte - Thành công"))
        except: pass
        try:
            if self.sock:
                send_msg(self.sock, json.dumps({"type": "upload_batch_ack", "xfer_id": xid}).encode('utf-8'))
        except Exception:
            pass
        if self.app and getattr(self.app, 'is_headless', False):
            meta = list((job or {}).get("expected_files") or [])
            why = []
            if meta and not _paths_match_expected_sizes(ok_paths, meta, detail=why):
                print("[FileTransfer] batch_end: size khong khop snapshot paste, khong gui FILES. " + "; ".join(why))
                log_debug("[batch_end] HEADLESS: size không khớp snapshot paste, không gửi FILES.")
                ok_paths = []
            dest = (job or {}).get("paste_dest") or getattr(self, "_paste_dest_dir", None)
            if ok_paths and dest and os.path.isdir(dest) and not _is_transfer_staging_dir(dest):
                try:
                    ok_paths, _moved = _relocate_transfer_files_unlocked(ok_paths, dest)
                except Exception as e:
                    log_debug(f"[batch_end] relocate dest={dest}: {e}")
            try:
                stg_base = (job or {}).get("save_dir") or getattr(self, "target_save_dir", None)
                _purge_rdxfer_staging(
                    dest_dir=dest or stg_base,
                    xfer_id=xid,
                    extra_paths=list((job or {}).get("paths") or []) + list(ok_paths or []),
                )
                _purge_rdxfer_staging(dest_dir=stg_base, xfer_id=xid)
                _schedule_scrub_probe(dest)
            except Exception as e:
                log_debug(f"[batch_end] purge staging: {e}")
            if ok_paths:
                files_str = str(paste_id) + "|" + "|".join(ok_paths)
                self._send_progress_signal("FILES", files_str)
                if hasattr(self, 'lock'):
                    with self.lock:
                        self.last_current_files = [os.path.abspath(p) for p in ok_paths if os.path.exists(p)]
                        self.last_files_time = time.time()
            else:
                self._send_progress_signal("CANCEL", str(paste_id) if paste_id else "")
            self._close_transfer_pipe()
        jobs.pop(xid, None)
        if not jobs:
            self.transfer_in_progress = False
            self._paste_dest_dir = None
            if self.app and getattr(self.app, "is_headless", False):
                self.target_save_dir = HEADLESS_TRANSFER_DIR

    def handle_received_packet(self, packet):
        ptype = packet.get("type")
        
        if ptype == "clear_clipboard":
            self.pending_remote_files = []
            self.dummy_h_active = False
            hwnd = getattr(self, "cached_app_hwnd", None)
            if not hwnd and getattr(self, "listener", None):
                hwnd = getattr(self.listener, "hwnd", None)
            try:
                clear_local_clipboard(hwnd)
            except Exception as e:
                log_debug(f"[handle_received_packet] clear_clipboard: {e}")
            if self.app and getattr(self.app, "is_headless", False):
                try:
                    threading.Thread(target=self._send_to_pipe, args=("CLEAR", ""), daemon=True).start()
                except Exception:
                    pass
            print("[Clipboard] Đã xóa clipboard theo yêu cầu đối tác.")
            return

        # Text host→client: luôn nhận khi đang có phiên viewer (giống RDP).
        # Nếu chỉ nhận lúc pygame đang focus thì Alt+Tab sang Notepad để dán sẽ mất text. 
        if ptype in ("batch_start", "file_start", "file_chunk", "file_end", "batch_end"):
            xid = packet.get("xfer_id")
            aborted = getattr(self, "_aborted_xfer_ids", None) or set()
            jobs = getattr(self, "_xfer_jobs", None) or {}
            stale = (xid is not None and xid in aborted) or not self._xfer_packet_ok(packet, ptype)
            if (
                not stale
                and not getattr(self, "_allow_file_xfer", False)
                and xid not in jobs
            ):
                stale = True
            if stale:
                log_debug(f"[handle_received_packet] Drain/discard {ptype} xfer_id={xid} (Huy — van doc socket).")
                return

        if ptype == "cancel_ack":
            print("[FileTransfer] Nhan cancel_ack — ngat vong gui.")
            ack_id = self._coerce_paste_id(packet.get("paste_id"))
            self._disarm_file_xfer("cancel_ack", cancelled_paste_id=ack_id, all_jobs=ack_id is None)
            return

        if ptype == "cancel_transfer":
            print("[FileTransfer] Nhận tín hiệu hủy truyền tải từ đối tác.")
            pid = self._coerce_paste_id(packet.get("paste_id")) if "paste_id" in packet else None
            self.cancel_active_transfer(remote_triggered=True, paste_id=pid, all_jobs=pid is None)
            return

        elif ptype == "resume_query":
            xid = packet.get("xfer_id")
            snap = self._resume_snapshot(xid)
            live = self._live_xfer_sock()
            if live:
                try:
                    send_msg(live, json.dumps(snap).encode("utf-8"))
                    print(f"[FileTransfer] resume_state xfer_id={xid} files={list((snap.get('files') or {}).keys())[:8]}")
                except Exception as e:
                    print(f"[FileTransfer] Gui resume_state loi: {e}")
            return

        elif ptype == "resume_state":
            xid = packet.get("xfer_id")
            waiters = getattr(self, "_resume_waiters", None) or {}
            pair = waiters.get(xid)
            if pair:
                ev, box = pair
                box["state"] = packet
                ev.set()
            return
            
        elif ptype == "clipboard_text":
            text = packet.get("text", "")
            log_debug(f"[handle_received_packet] Nhận clipboard_text: {text[:50]}...")
            print(f"[Clipboard] Đã nhận được text clipboard từ remote. Đang cập nhật...")
            self.last_received_text = text
            self.ignore_destroy_clipboard = True
            try:
                owner_hwnd = getattr(self, 'cached_app_hwnd', None)
                
                if self.app and getattr(self.app, 'is_headless', False):
                    # Gửi text qua Named Pipe cho Clipboard Agent
                    threading.Thread(target=self._send_to_pipe, args=("TEXT", text), daemon=True).start()
                    log_debug("[handle_received_packet] HEADLESS: Đang gửi text qua Named Pipe cho Clipboard Agent.")
                else:
                    set_clipboard_text(text, owner_hwnd)
            finally:
                self.ignore_destroy_clipboard = False
            return
            
        elif ptype == "files_copied_meta":
            files = packet.get("files", [])
            print(f"[Clipboard] Nhận files_copied_meta offer={packet.get('offer_id')} n={len(files)} {[f.get('name') for f in (files or [])[:8]]}")
            self._enqueue_file_offer(files, packet.get("offer_id"))
            return
            
        elif ptype == "request_files":
            try:
                tok = int(packet.get("paste_id") or 0)
            except Exception:
                tok = 0
            cancelled = getattr(self, "_cancelled_paste_ids", None) or set()
            if tok and tok in cancelled:
                print(f"[FileTransfer] Bo request_files paste_id={tok} (blacklist Huy).")
                return
            if not tok and time.time() < getattr(self, "_suppress_request_files_until", 0):
                print("[FileTransfer] Bo request_files khong paste_id sau Huy.")
                return
            if tok:
                self._clipboard_paste_id = tok
            if not self._arm_file_xfer("peer_request_files"):
                return
            files_to_send = packet.get("files", [])
            sid = getattr(self, "_send_xfer_id", 0)
            self._enqueue_send_job(files_to_send, sid, tok)
            return
            
        elif ptype == "batch_start":
            xid = packet.get("xfer_id")
            if xid is not None and xid in (getattr(self, "_aborted_xfer_ids", None) or set()):
                log_debug(f"[batch_start] Bo xfer da huy {xid}")
                return
            jobs = getattr(self, "_xfer_jobs", None)
            if jobs is None:
                self._xfer_jobs = {}
                jobs = self._xfer_jobs
            existing = jobs.get(xid) if xid is not None else None
            if existing:
                existing["last_chunk_at"] = time.time()
                existing["retry_ui"] = False
                log_debug(f"[batch_start] Giu job cu de resume xfer_id={xid} received={existing.get('received')}")
                self.transfer_in_progress = True
                self._receive_cancelled = False
                if xid is not None:
                    self._recv_xfer_id = xid
                return
            paste_id = packet.get("paste_id")
            try:
                paste_id = int(paste_id) if paste_id is not None else int(getattr(self, "_clipboard_paste_id", 0) or 0)
            except Exception:
                paste_id = 0
            display_name = packet.get("display_name", "Files")
            item_kind = packet.get("item_kind") or "file"
            total_size = packet.get("total_size", 0)
            job = {
                "xfer_id": xid,
                "paste_id": paste_id,
                "received": 0,
                "total": total_size,
                "paths": [],
                "display_name": display_name,
                "item_kind": item_kind,
                "last_progress": 0.0,
                "last_chunk_at": time.time(),
                "retry_ui": False,
                "expected_files": list((getattr(self, "_xfer_expected_files", None) or {}).get(paste_id) or []),
                "save_dir": getattr(self, "target_save_dir", None) or HEADLESS_TRANSFER_DIR,
                "paste_dest": getattr(self, "_paste_dest_dir", None),
            }
            jobs[xid] = job
            self.batch_total_size = total_size
            self.batch_received = 0
            self.batch_paths = job["paths"]
            self.batch_display_name = display_name
            self.transfer_in_progress = True
            self._receive_cancelled = False
            if xid is not None:
                self._recv_xfer_id = xid
            try:
                os.makedirs(job.get("save_dir") or HEADLESS_TRANSFER_DIR, exist_ok=True)
            except Exception:
                pass
            log_file_transfer(display_name, total_size)
            log_debug(f"[batch_start] Bắt đầu nhận batch xfer_id={xid} paste_id={paste_id} total={total_size}")
            if not (self.app and getattr(self.app, 'is_headless', False)):
                dest_dir = getattr(self, "_paste_dest_dir", None) or getattr(self, "cached_explorer_path", None)
                if dest_dir and _is_transfer_staging_dir(dest_dir):
                    dest_dir = None
                if not dest_dir:
                    save = getattr(self, "target_save_dir", None)
                    if save and not _is_transfer_staging_dir(save):
                        dest_dir = save
                expected = job.get("expected_files") or []
                kind, name = _copy_batch_kind_and_name(expected, display_name)
                if not expected:
                    kind = item_kind if item_kind in ("file", "folder") else kind
                    name = display_name or name
                self.open_paste_progress_dialog(
                    name, total_size, dest_dir, job_id=paste_id or xid, item_kind=kind,
                )
            return

        elif ptype == "file_start":
            filename = packet.get("name", "")
            if not filename: return
            
            xid = packet.get("xfer_id")
            job = (getattr(self, "_xfer_jobs", None) or {}).get(xid) if xid is not None else None
            save_dir = (job or {}).get("save_dir") or self.target_save_dir
            pkt_dir = packet.get("target_dir")
            if pkt_dir and _is_transfer_staging_dir(pkt_dir):
                save_dir = pkt_dir
            if not save_dir:
                save_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
            key = _incoming_key(xid, filename)
            resume_from = packet.get("offset")
            try:
                resume_from = int(resume_from) if resume_from is not None else 0
            except Exception:
                resume_from = 0
            existing = self.incoming_transfers.get(key)
            if (
                existing
                and existing.get("handle")
                and xid is not None
                and existing.get("xfer_id") == xid
            ):
                if resume_from > 0:
                    try:
                        existing["handle"].seek(resume_from)
                        existing["written"] = resume_from
                    except Exception:
                        pass
                    log_debug(f"[file_start] Resume handle {filename} offset={resume_from}")
                else:
                    log_debug(f"[file_start] Bỏ file_start trùng (tránh cắt file) xfer_id={xid} {filename}")
                return
            save_dir = _xfer_staging_dir(save_dir, xid)
            
            target_path = os.path.join(save_dir, filename)
            log_debug(f"[file_start] Bắt đầu nhận file: {filename}, target_path={target_path} offset={resume_from}")

            try:
                dirname = os.path.dirname(target_path)
                if dirname:
                    os.makedirs(dirname, exist_ok=True)
                    stg = save_dir if os.path.basename(save_dir).startswith(".rdxfer_") else dirname
                    if os.path.basename(stg).startswith(".rdxfer_"):
                        _hide_win_path(stg)
                old = self.incoming_transfers.pop(key, None)
                if old and old.get("handle"):
                    try:
                        old["handle"].close()
                    except Exception:
                        pass
                exists = os.path.exists(target_path)
                mode = "r+b" if (resume_from > 0 and exists) else "wb"
                fh = open(target_path, mode, buffering=1024 * 1024)
                dest_now = self._paste_dest_for_job(job)
                self._ensure_dest_tree(dest_now, filename)
                written = 0
                if resume_from > 0:
                    try:
                        actual = os.path.getsize(target_path) if exists else 0
                    except Exception:
                        actual = 0
                    written = min(resume_from, actual)
                    try:
                        fh.seek(written)
                    except Exception:
                        fh.seek(0)
                        written = 0
                expected = packet.get("size")
                try:
                    expected = int(expected) if expected is not None else None
                except Exception:
                    expected = None
                self.incoming_transfers[key] = {
                    "path": target_path,
                    "handle": fh,
                    "skipped": False,
                    "pending": False,
                    "xfer_id": xid,
                    "expected_size": expected,
                    "written": written,
                    "name": filename,
                }
                try:
                    self._partial_output_paths = list(getattr(self, "_partial_output_paths", None) or [])
                    self._partial_output_paths.append(target_path)
                except Exception:
                    pass
                log_debug(f"[file_start] Mở thành công file mới: {target_path} expected={expected}")
            except Exception as e:
                print(f"[FileTransfer] Lỗi mở file mới {filename}: {e}")
                log_debug(f"[file_start] Lỗi mở file mới {filename}: {e}")

        elif ptype == "file_chunk":
            filename = packet.get("name", "")
            xid = packet.get("xfer_id")
            key = _incoming_key(xid, filename)
            if key in self.incoming_transfers:
                transfer = self.incoming_transfers[key]
                if xid is not None and transfer.get("xfer_id") is not None and xid != transfer.get("xfer_id"):
                    log_debug(f"[file_chunk] Bỏ chunk xfer_id cũ cho {filename}")
                    return
                chunk_bytes = base64.b64decode(packet.get("data", ""))
                expected = transfer.get("expected_size")
                written = int(transfer.get("written") or 0)
                chunk_offset = packet.get("offset")
                try:
                    chunk_offset = int(chunk_offset) if chunk_offset is not None else None
                except Exception:
                    chunk_offset = None
                start = written if chunk_offset is None else max(0, chunk_offset)
                if expected is not None and start >= expected:
                    return
                if expected is not None and start + len(chunk_bytes) > expected:
                    chunk_bytes = chunk_bytes[: max(0, expected - start)]
                if not chunk_bytes:
                    return

                if transfer.get("handle") is not None:
                    if chunk_offset is not None:
                        try:
                            transfer["handle"].seek(start)
                        except Exception:
                            pass
                    transfer["handle"].write(chunk_bytes)
                    new_written = start + len(chunk_bytes)
                    delta = max(0, new_written - written)
                    transfer["written"] = max(written, new_written)
                    job = (getattr(self, "_xfer_jobs", None) or {}).get(xid)
                    if job is None:
                        self.batch_received += delta
                        rec = self.batch_received
                        total = getattr(self, "batch_total_size", 0)
                        paste_id = int(getattr(self, "_clipboard_paste_id", 0) or 0)
                    else:
                        job["received"] = int(job.get("received") or 0) + delta
                        job["last_chunk_at"] = time.time()
                        rec = job["received"]
                        total = job.get("total") or 0
                        paste_id = int(job.get("paste_id") or 0)
                    self.update_dialog(rec, job_id=paste_id or xid)
                    if self.app and getattr(self.app, 'is_headless', False):
                        now = time.time()
                        last = float(job.get("last_progress") or 0) if job else getattr(self, "_last_progress_time", 0)
                        if (now - last >= 0.05) or (total and rec >= total):
                            payload = f"{paste_id}|{rec}" if paste_id else str(rec)
                            self._send_progress_signal("PROGRESS", payload)
                            if job is not None:
                                job["last_progress"] = now
                            else:
                                self._last_progress_time = now
                    current_time_ack = time.time()
                    if not hasattr(self, '_last_upload_ack_time'):
                        self._last_upload_ack_time = 0
                    if (current_time_ack - self._last_upload_ack_time >= 0.2) or (total and rec >= total):
                        self._last_upload_ack_time = current_time_ack
                        if getattr(self, 'sock', None):
                            try:
                                send_msg(self.sock, json.dumps({"type": "upload_progress_ack", "received": rec, "xfer_id": xid}).encode('utf-8'))
                            except: pass

        elif ptype == "file_end":
            filename = packet.get("name", "")
            xid = packet.get("xfer_id")
            key = _incoming_key(xid, filename)
            if key in self.incoming_transfers:
                transfer = self.incoming_transfers[key]
                if xid is not None and transfer.get("xfer_id") is not None and xid != transfer.get("xfer_id"):
                    log_debug(f"[file_end] Bỏ file_end xfer_id cũ cho {filename}")
                    return
                transfer = self.incoming_transfers.pop(key, None)
                if transfer:
                    job = (getattr(self, "_xfer_jobs", None) or {}).get(transfer.get("xfer_id") if transfer.get("xfer_id") is not None else xid)
                    ev = threading.Event()
                    if job is not None:
                        job.setdefault("finish_events", []).append(ev)
                    def _finish(t=transfer, j=job, e=ev, fn=filename):
                        try:
                            self._finalize_incoming_file(t, j, fn)
                        except Exception as ex:
                            print(f"[FileTransfer] Finalize {fn} loi: {ex}")
                        finally:
                            e.set()
                    threading.Thread(target=_finish, daemon=True, name="XferFinish").start()
            
        elif ptype == "batch_end":
            threading.Thread(
                target=self._complete_batch_after_files,
                args=(packet,),
                daemon=True,
                name="XferBatchEnd",
            ).start()
            return



if is_clipboard_agent or is_gui_agent:
    clipboard_sync_manager = None
else:
    clipboard_sync_manager = ClipboardSyncManager()







def run_clipboard_agent_mode():
    """
    Chế độ Clipboard Agent: Chạy ở quyền User thường.
    Lắng nghe Named Pipe từ Service/headless app để nhận đường dẫn file
    và nạp vào Clipboard hệ thống.
    
    Kiến trúc: App Headless (SYSTEM) -> Named Pipe -> App ClipboardAgent (User) -> Clipboard
    """
    import logging
    import queue
    import win32file
    import win32pipe
    import win32event
    import win32api
    import time
    import tkinter as tk
    
    log_path = os.path.join(app_dir, "clipboard_agent.log")
    agent_log = logging.getLogger("clipboard_agent")
    agent_log.setLevel(logging.DEBUG)
    
    # Xoá các handler cũ nếu có để tránh ghi lặp
    for h in list(agent_log.handlers):
        agent_log.removeHandler(h)
        
    formatter = logging.Formatter("[%(asctime)s] [PID %(process)d] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    
    # Ghi file với UTF-8
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(formatter)
    agent_log.addHandler(fh)
    
    # Chỉ ghi ra console nếu stdout không phải là chính file log đó (tránh lặp 2 dòng trong file)
    is_stdout_log = False
    try:
        if sys.stdout and hasattr(sys.stdout, 'name'):
            is_stdout_log = (os.path.abspath(sys.stdout.name) == os.path.abspath(log_path))
    except:
        pass
        
    if not is_stdout_log and sys.stdout:
        import io; sh = logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')) if hasattr(sys.stdout, 'buffer') else logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        agent_log.addHandler(sh)

    def agent_print(msg):
        agent_log.info(msg)

    agent_print("=" * 60)
    agent_print(f"[ClipboardAgent] Khởi động. PID: {os.getpid()}")
    agent_print(f"[ClipboardAgent] Thư mục ứng dụng: {app_dir}")
    agent_print("=" * 60)

    pipe_name = CLIPBOARD_PIPE_NAME
    gui_queue = queue.Queue()

    def pipe_listener_loop():
        while True:
            pipe_handle = None
            try:
                agent_print(f"[ClipboardAgent] Đang chờ kết nối tới Pipe: {pipe_name}")
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
                        time.sleep(0.05)

                agent_print(f"[ClipboardAgent] Đã kết nối thành công tới Pipe.")

                try:
                    win32pipe.SetNamedPipeHandleState(
                        pipe_handle,
                        win32pipe.PIPE_READMODE_MESSAGE,
                        None,
                        None
                    )
                except Exception as se:
                    agent_print(f"[ClipboardAgent] Cảnh báo SetNamedPipeHandleState: {se}. Tiếp tục ở chế độ byte mode.")

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
                                    agent_print(f"[ClipboardAgent] Nhận tin nhắn từ Pipe (độ dài {len(msg)}): {msg[:100]}...")
                                    if msg.startswith("TEXT:"):
                                        gui_queue.put(("text", msg[5:]))
                                    elif msg.startswith("FILES:"):
                                        gui_queue.put(("files_ready", msg[6:]))
                                    elif msg.startswith("PENDING:"):
                                        try:
                                            import json
                                            info = json.loads(msg[8:])
                                            try:
                                                _pending_info.clear()
                                                if isinstance(info, dict):
                                                    _pending_info.update(info)
                                                    files = info.get("files")
                                                    if isinstance(files, list):
                                                        _pending_info["files"] = [dict(f) if isinstance(f, dict) else f for f in files]
                                            except Exception:
                                                pass
                                            gui_queue.put(("pending", info))
                                        except Exception as e:
                                            agent_print(f"[ClipboardAgent] Lỗi parse PENDING JSON: {e}")
                                    elif msg.startswith("PROGRESS:"):
                                        try:
                                            rest = msg[9:]
                                            if "|" in rest:
                                                pid_s, nbytes_s = rest.split("|", 1)
                                                gui_queue.put(("progress", (int(pid_s), int(nbytes_s))))
                                            else:
                                                gui_queue.put(("progress", int(rest)))
                                        except:
                                            pass
                                    elif msg.startswith("CANCEL:"):
                                        rest = msg[7:].strip()
                                        pid = None
                                        try:
                                            if rest:
                                                pid = int(rest)
                                        except Exception:
                                            pid = None
                                        gui_queue.put(("pipe_cancel", pid))
                                    elif msg.startswith("CLEAR:"):
                                        gui_queue.put(("clear_clip", None))
                                    else:
                                        agent_print(f"[ClipboardAgent] Bỏ qua tin nhắn không nhận dạng: {msg[:50]}")
                        else:
                            agent_print(f"[ClipboardAgent] ReadFile trả về mã lỗi: {hr}")
                            break
                    except Exception as read_err:
                        err_code = getattr(read_err, 'winerror', 0)
                        if err_code == 109:
                            agent_print("[ClipboardAgent] Pipe bị ngắt. Đang kết nối lại...")
                            break
                        elif err_code == 234:
                            continue
                        else:
                            agent_print(f"[ClipboardAgent] Lỗi đọc Pipe: {read_err}")
                            break
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lỗi kết nối Pipe: {e}")
            finally:
                if pipe_handle is not None:
                    try:
                        win32file.CloseHandle(pipe_handle)
                    except:
                        pass
            time.sleep(0.02)
    root = tk.Tk()
    root.withdraw()
    try:
        from gui.window_icon import hide_tk_from_taskbar, set_dialog_app_icon
        hide_tk_from_taskbar(root)
        set_dialog_app_icon(root)
    except Exception:
        pass
    try:
        root.wm_attributes("-toolwindow", True)
    except Exception:
        pass
    
    active_dialog = None
    active_dialogs = {}
    _agent_jobs = {}
    _agent_req_lock = threading.Lock()
    _agent_req_q = queue.Queue()
    _agent_req_inflight = [False]

    # -----------------------------------------------------------------------
    # Delayed-rendering Win32 cho HEADLESS mode
    # -----------------------------------------------------------------------
    # Khi host gửi PENDING:, agent tạo cửa sổ ẩn và trở thành chủ sở hữu clipboard
    # với dạng delayed render (CF_HDROP = NULL). Windows sẽ gửi WM_RENDERFORMAT
    # đúng lúc người dùng thực sự Paste, lúc đó agent mới yêu cầu host tải file.
    # -----------------------------------------------------------------------
    from ctypes import wintypes

    CF_HDROP        = 15
    WM_RENDERFORMAT = 0x0305
    WM_RENDERALLFORMATS = 0x0306
    WM_DESTROYCLIPBOARD = 0x0307
    WM_USER_SETUP_DELAYED = 0x0400 + 201  # tin nhắn nội bộ để setup từ luồng khác
    WM_USER_UNBLOCK_PASTE = 0x0400 + 202  # Hủy giữa Paste: HDROP rỗng để Explorer không treo

    _agent_hwnd = None              # HWND cửa sổ ẩn của agent
    _pending_info = {}              # {'display_name': ..., 'total_size': ...}
    _agent_setup_tries = 0
    _files_ready_event = threading.Event()  # set khi host gửi FILES: xong
    _files_ready_paths = []        # các đưỜng dẫn file đã download
    _ignore_destroy = False        # tránh phản ứng WM_DESTROYCLIPBOARD do chính mình gây ra
    _is_rendering = False          # chống race condition WM_RENDERFORMAT
    
    _agent_last_lbutton_time = 0.0
    _agent_last_rbutton_time = 0.0
    _agent_last_ctrl_v_time = 0.0
    _agent_lmb_hit_context_menu = False
    _agent_lmb_menu_item_kind = ""
    _agent_meta_arrival_time = 0.0
    _agent_dummy_h_active = False
    _agent_cached_explorer_path = None
    _agent_suppress_render_until = 0.0
    _agent_expect_repaste_until = 0.0
    _agent_last_copied_seq = None
    _agent_last_copied_fp = None
    _agent_offer_id = 0
    _agent_pending_offer_id = 0
    _agent_last_ctrl_c_time = 0.0
    _agent_paste_id = 0
    _agent_accept_files = False
    _agent_allow_xfer = False
    _agent_xfer_cancel_at = 0.0
    _agent_ctrl_v_held = False
    _agent_shift_ins_held = False
    _agent_download_active = False
    _agent_conflict_event = threading.Event()
    _agent_conflict_choice = "replace"
    _agent_conflict_skip = set()

    _agent_allow_delayed = True
    _agent_clip_seq_at_pending = None
    _agent_force_delayed_setup = False
    _agent_paste_coalesce_until = 0.0
    _agent_paste_gesture_id = 0
    _agent_consumed_gesture_id = 0
    _agent_gesture_inc_at = 0.0
    _agent_lmb_held = False
    _agent_prev_lbutton_time = 0.0
    _agent_prev_lbutton_pos = (0, 0)
    _agent_last_dblclick_time = 0.0

    def _note_paste_gesture():
        """Ctrl+V / click Paste — coalesced 80ms để hook+poll không đếm 2 lần."""
        nonlocal _agent_paste_gesture_id, _agent_gesture_inc_at
        now = time.time()
        if now - _agent_gesture_inc_at < 0.08:
            return
        _agent_gesture_inc_at = now
        _agent_paste_gesture_id += 1

    def _register_lmb_down():
        """Ghi nhận 1 cú nhấn chuột trái; phát hiện double-click (mở file, KHÔNG phải Paste).

        Poll 50ms và low-level hook có thể cùng báo 1 cú nhấn nên gộp trong 60ms để
        không nhầm 1 click thành double-click.
        """
        nonlocal _agent_prev_lbutton_time, _agent_prev_lbutton_pos, _agent_last_dblclick_time
        nonlocal _agent_last_lbutton_time
        now = time.time()
        if now - _agent_prev_lbutton_time < 0.06:
            _agent_last_lbutton_time = now
            return
        cx, cy = _cursor_xy()
        px, py = _agent_prev_lbutton_pos
        if (now - _agent_prev_lbutton_time) <= (_double_click_ms() / 1000.0) + 0.05 and abs(cx - px) <= 6 and abs(cy - py) <= 6:
            _agent_last_dblclick_time = now
        _agent_prev_lbutton_time = now
        _agent_prev_lbutton_pos = (cx, cy)
        _agent_last_lbutton_time = now

    def _paths_are_probe_or_xfer(files):
        dirs = []
        for d in (
            _PROBE_STUB_DIR,
            HEADLESS_TRANSFER_DIR,
            os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"),
        ):
            try:
                dirs.append(os.path.abspath(d).lower())
            except Exception:
                pass
        for f in files or []:
            try:
                p = os.path.abspath(f).lower()
            except Exception:
                continue
            if any(p.startswith(d) for d in dirs):
                return True
        return False

    def _yield_clipboard_to_user(reason=""):
        """User copy local — đừng EmptyClipboard/delayed HDROP (mất copy, chuột xoay)."""
        nonlocal _agent_allow_delayed
        _agent_allow_delayed = False
        agent_print(f"[ClipboardAgent] Nha clipboard cho user ({reason}).")

    def _agent_user_clipboard_wins():
        if not should_preserve_user_clipboard(_agent_hwnd):
            return False
        seq = get_clipboard_sequence_number()
        at = _agent_clip_seq_at_pending
        if at is None:
            return True
        return (not seq) or seq != at

    def _agent_emit_copied_files(force=False):
        nonlocal _agent_last_copied_seq, _agent_last_copied_fp, _agent_offer_id
        try:
            if _is_rendering or (not force and is_own_clipboard_write()):
                return
            files = None
            seq = 0
            for _try in range(5):
                seq_b = get_clipboard_sequence_number()
                files = get_clipboard_files()
                seq = get_clipboard_sequence_number()
                if seq_b and seq and seq_b != seq:
                    time.sleep(0.1)
                    continue
                if not files:
                    return
                if _paths_are_probe_or_xfer(files):
                    return
                fp = tuple(os.path.abspath(f).lower() for f in files)
                if (
                    _agent_last_copied_fp
                    and fp == _agent_last_copied_fp
                    and seq
                    and seq != _agent_last_copied_seq
                    and _try < 4
                ):
                    time.sleep(0.1)
                    continue
                break
            if not files:
                return
            if not force and seq and seq == _agent_last_copied_seq:
                return
            fp = tuple(os.path.abspath(f).lower() for f in files)
            _agent_last_copied_seq = seq
            _agent_last_copied_fp = fp
            _agent_offer_id += 1
            import win32pipe, win32file, json
            pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
            win32pipe.WaitNamedPipe(pipe_name, 5000)
            pipe_handle = win32file.CreateFile(pipe_name, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
            msg = "COPIED_FILES|" + json.dumps({"offer_id": _agent_offer_id, "files": files})
            win32file.WriteFile(pipe_handle, msg.encode("utf-8"))
            win32file.CloseHandle(pipe_handle)
            agent_print(f"[ClipboardAgent] Đã gửi {len(files)} COPIED_FILES offer={_agent_offer_id} (force={force}).")
        except Exception as e:
            agent_print(f"Failed to send COPIED_FILES: {e}")

    def _agent_schedule_rearm(delay_s=0.45):
        nonlocal _agent_suppress_render_until
        if not _agent_allow_delayed or _agent_user_clipboard_wins():
            return
        _agent_suppress_render_until = max(_agent_suppress_render_until, time.time() + delay_s)
        def _go():
            if not _agent_allow_delayed:
                return
            if _pending_info and _agent_hwnd:
                ctypes.windll.user32.PostMessageW(
                    ctypes.c_void_p(_agent_hwnd),
                    WM_USER_SETUP_DELAYED, 0, 0
                )
        threading.Timer(delay_s, _go).start()

    def _agent_explorer_path_cacher():
        nonlocal _agent_cached_explorer_path
        while True:
            try:
                try:
                    if ctypes.windll.user32.GetOpenClipboardWindow():
                        time.sleep(0.35)
                        continue
                except Exception:
                    pass
                found = query_explorer_folder_path()
                if found:
                    _agent_cached_explorer_path = found
            except Exception:
                pass
            time.sleep(0.35)

    threading.Thread(target=_agent_explorer_path_cacher, daemon=True, name="AgentExplorerPath").start()

    def _agent_mouse_poll_loop():
        nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_ctrl_v_time, _agent_dummy_h_active
        nonlocal _agent_last_ctrl_c_time, _agent_last_copied_seq, _agent_ctrl_v_held, _agent_shift_ins_held, _agent_lmb_held
        nonlocal _agent_lmb_hit_context_menu, _agent_lmb_menu_item_kind
        user32 = ctypes.windll.user32
        while True:
            try:
                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    now = time.time()
                    on_self = _cursor_over_current_process()
                    if not _agent_lmb_held:
                        _register_lmb_down()
                        hit_menu = (not on_self) and _cursor_over_context_menu()
                        if hit_menu:
                            _agent_lmb_hit_context_menu = True
                            kind, name = _capture_menu_item_at_cursor()
                            _agent_lmb_menu_item_kind = kind
                            agent_print(f"[ClipboardAgent] LMB menu item name={name!r} kind={kind}")
                            if kind != "not_paste":
                                _note_paste_gesture()
                    else:
                        _agent_last_lbutton_time = now
                    _agent_lmb_held = True
                    if (not on_self) and _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                else:
                    _agent_lmb_held = False
                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    _agent_last_rbutton_time = time.time()
                    _agent_lmb_hit_context_menu = False
                    _agent_lmb_menu_item_kind = ""
                    if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if user32.GetAsyncKeyState(0x0D) & 0x8000: # Enter
                    if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if user32.GetAsyncKeyState(0x1B) & 0x8000: # Esc
                    if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):
                    if not _agent_ctrl_v_held:
                        _agent_last_ctrl_v_time = time.time()
                        _note_paste_gesture()
                    _agent_ctrl_v_held = True
                    if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                else:
                    _agent_ctrl_v_held = False
                if (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000):
                    if not _agent_shift_ins_held:
                        _agent_last_ctrl_v_time = time.time()
                        _note_paste_gesture()
                    _agent_shift_ins_held = True
                    if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                else:
                    _agent_shift_ins_held = False
                if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x43) & 0x8000):
                    now = time.time()
                    if now - _agent_last_ctrl_c_time > 0.4:
                        _agent_last_ctrl_c_time = now
                        threading.Timer(0.18, lambda: _agent_emit_copied_files(force=True)).start()
            except:
                pass
            time.sleep(0.05)
            
    threading.Thread(target=_agent_mouse_poll_loop, daemon=True, name="AgentMousePoll").start()

    def _send_cancel_to_host(paste_id=None):
        """Báo worker dừng gửi/nhận. Event Global dễ fail (SYSTEM vs Medium IL)."""
        import win32file
        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
        sent_pipe = False
        if paste_id is not None:
            body = ("CANCEL_TRANSFER|" + str(int(paste_id))).encode("utf-8")
        else:
            body = b"CANCEL_TRANSFER"
        for attempt in range(8):
            try:
                import win32pipe
                try:
                    win32pipe.WaitNamedPipe(pipe_name, 400)
                except Exception:
                    pass
                pipe_handle = win32file.CreateFile(
                    pipe_name,
                    win32file.GENERIC_WRITE, 0, None,
                    win32file.OPEN_EXISTING, 0, None
                )
                win32file.WriteFile(pipe_handle, body)
                win32file.CloseHandle(pipe_handle)
                sent_pipe = True
                agent_print("[ClipboardAgent] Đã gửi CANCEL_TRANSFER tới host (UpPipe).")
                break
            except Exception as e:
                if attempt == 7:
                    agent_print(f"[ClipboardAgent] Lỗi gửi CANCEL_TRANSFER qua pipe: {e}")
                time.sleep(0.08)
        if paste_id is not None:
            return
        try:
            h_event = win32event.OpenEvent(
                win32event.EVENT_MODIFY_STATE, False,
                r"Global\AntigravityP2P_CancelTransfer_Event",
            )
            win32event.SetEvent(h_event)
            time.sleep(0.2)
            try:
                win32event.ResetEvent(h_event)
            except Exception:
                pass
            win32api.CloseHandle(h_event)
            agent_print("[ClipboardAgent] Đã SetEvent hủy truyền tải.")
        except Exception as e:
            agent_print(f"[ClipboardAgent] Event hủy không Set được (pipe={sent_pipe}): {e}")

    def _write_request_files_pipe(files_to_request, dest_dir, paste_id):
        import win32file, json
        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
        try:
            import win32pipe
            try:
                win32pipe.WaitNamedPipe(pipe_name, 5000)
            except Exception:
                pass
            pipe_handle = win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_WRITE, 0, None,
                win32file.OPEN_EXISTING, 0, None
            )
            payload = {
                "files": files_to_request or [],
                "dest_dir": dest_dir or "",
                "paste_id": int(paste_id or 0),
            }
            msg = "REQUEST_FILES|" + json.dumps(payload)
            win32file.WriteFile(pipe_handle, msg.encode('utf-8'))
            win32file.CloseHandle(pipe_handle)
            agent_print(f"[ClipboardAgent] Đã gửi REQUEST_FILES paste_id={paste_id}.")
        except Exception as e:
            agent_print(f"[ClipboardAgent] Lỗi gửi REQUEST_FILES: {e}")
            _release_agent_file_request()

    def _flush_agent_file_request():
        """Một lúc chỉ một REQUEST_FILES trên dây — paste sau chờ paste trước xong."""
        while True:
            with _agent_req_lock:
                if _agent_req_inflight[0]:
                    return
                try:
                    files, dest_dir, paste_id = _agent_req_q.get_nowait()
                except queue.Empty:
                    return
                try:
                    pid = int(paste_id or 0)
                except Exception:
                    pid = 0
                job = _agent_jobs.get(pid) if pid else None
                if job is not None:
                    if not job.get("allow"):
                        agent_print(f"[ClipboardAgent] Bo REQUEST_FILES hang doi paste_id={pid} (da Huy).")
                        continue
                elif not _agent_allow_xfer:
                    agent_print("[ClipboardAgent] Bo REQUEST_FILES hang doi (allow_xfer=False).")
                    continue
                _agent_req_inflight[0] = True
            _write_request_files_pipe(files, dest_dir, paste_id)
            return

    def _release_agent_file_request():
        with _agent_req_lock:
            _agent_req_inflight[0] = False
        _flush_agent_file_request()

    def _send_request_files_to_host(files_to_request=None, dest_dir=None, paste_id=0):
        """Xếp hàng REQUEST_FILES — không gửi paste sau khi paste trước còn trên dây."""
        try:
            pid = int(paste_id or 0)
        except Exception:
            pid = 0
        job = _agent_jobs.get(pid) if pid else None
        if job is not None:
            if not job.get("allow"):
                agent_print("[ClipboardAgent] Bo REQUEST_FILES (job da Huy).")
                return
        elif not _agent_allow_xfer:
            agent_print("[ClipboardAgent] Bo REQUEST_FILES (allow_xfer=False / da Huy).")
            return
        _agent_req_q.put((list(files_to_request or []), dest_dir or "", pid))
        agent_print(f"[ClipboardAgent] Xep hang REQUEST_FILES paste_id={pid} (cho={_agent_req_q.qsize()})")
        _flush_agent_file_request()

    def _execute_agent_delayed_rendering(hwnd):
        """Chạy trong WndProc thread: mở clipboard, đăng ký deferred CF_HDROP."""
        nonlocal _ignore_destroy, _agent_setup_tries, _agent_force_delayed_setup, _agent_allow_delayed
        force = _agent_force_delayed_setup
        _agent_force_delayed_setup = False
        if not force:
            if not _agent_allow_delayed:
                agent_print("[ClipboardAgent] Bo setup delayed — clipboard dang thuoc user.")
                return
            if _agent_user_clipboard_wins():
                _yield_clipboard_to_user("local after pending")
                return
        else:
            _agent_allow_delayed = True
        if not _pending_info:
            agent_print("[ClipboardAgent] Không có pending_info, bỏ qua setup delayed rendering.")
            return
            
        try:
            user32 = ctypes.windll.user32
            if not user32.OpenClipboard(hwnd):
                _agent_setup_tries += 1
                if (
                    _agent_setup_tries <= 40
                    and _agent_allow_delayed
                    and (force or not _agent_user_clipboard_wins())
                ):
                    _agent_force_delayed_setup = force
                    threading.Timer(
                        0.025,
                        lambda h=hwnd: ctypes.windll.user32.PostMessageW(
                            ctypes.c_void_p(h), WM_USER_SETUP_DELAYED, 0, 0
                        ),
                    ).start()
                else:
                    err = ctypes.GetLastError()
                    agent_print(f"[ClipboardAgent] OpenClipboard thất bại khi setup (hết retry). Err={err}")
                return
            _agent_setup_tries = 0
            if not force and _agent_user_clipboard_wins():
                user32.CloseClipboard()
                _yield_clipboard_to_user("opened but user owns")
                return
            _ignore_destroy = True
            try:
                user32.EmptyClipboard()
                setup_clipboard_exclusions()
                res = fn_SetClipboardData(CF_HDROP, None)
                user32.CloseClipboard()
                mark_own_clipboard_write()
                agent_print(f"[ClipboardAgent] Đã setup delayed rendering CF_HDROP. res={res}")
            finally:
                _ignore_destroy = False
        except Exception as e:
            agent_print(f"[ClipboardAgent] Lỗi setup delayed rendering: {e}")
            _ignore_destroy = False

    def _agent_cleanup_partial(extra_paths=None, files_meta=None, wipe_all_staging=True, staging_xids=None):
        dests = [
            _agent_cached_explorer_path,
            HEADLESS_TRANSFER_DIR,
            os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"),
            _PROBE_STUB_DIR,
        ]
        if files_meta is None:
            meta = (_pending_info.get("files") if _pending_info else None) or []
        else:
            meta = files_meta
        paths = list(extra_paths or [])
        cleanup_incomplete_named_files(
            dests, meta, extra_paths=paths,
            staging_xids=staging_xids, wipe_all_staging=wipe_all_staging,
        )

    def _agent_complete_download(job):
        """Chờ FILES rồi chuyển vào thư mục Explorer — KHÔNG chạy trong WM_RENDERFORMAT (tránh deadlock OLE)."""
        nonlocal _agent_allow_xfer, _agent_accept_files, _agent_download_active, _pending_info
        pid = job.get("paste_id")
        info = job.get("info") or {}
        dest_dir = job.get("dest")
        try:
            while job.get("allow") and not job["conflict_event"].is_set():
                job["conflict_event"].wait(0.2)
            if (not job.get("allow")) or job.get("conflict_choice") == "cancel":
                agent_print("[ClipboardAgent] Huy do ghi de / conflict.")
                _agent_cleanup_partial(list(job.get("paths") or []))
                gui_queue.put(("cancel", pid))
                return

            wait_start = time.time()
            last_hb = wait_start
            while job.get("allow") and not job["event"].is_set():
                job["event"].wait(0.5)
                now = time.time()
                if now - last_hb >= 60.0:
                    last_hb = now
                    nbytes = int(job.get("last_progress_bytes") or 0)
                    agent_print(
                        f"[ClipboardAgent] Dang cho FILES paste_id={pid} received={nbytes} "
                        f"({int(now - wait_start)}s) — dialog van mo."
                    )
            if not job.get("allow"):
                agent_print("[ClipboardAgent] Huy luc cho file (nguoi dung / CANCEL).")
                leftover = list(job.get("paths") or [])
                _agent_cleanup_partial(leftover)
                gui_queue.put(("cancel", pid))
                return
            if job.get("event").is_set() and not job.get("paths"):
                agent_print("[ClipboardAgent] Paste khong tai file (skip / khong con file).")
                gui_queue.put(("end", pid))
                return
            if job.get("event").is_set() and job.get("paths"):
                final_paths = list(job["paths"])
                meta_files = list(job.get("requested_files") or (info.get("files") if info else None) or [])
                why = []
                if not _paths_match_expected_sizes(final_paths, meta_files, detail=why):
                    agent_print("[ClipboardAgent] File chưa đủ dung lượng — không chuyển. " + "; ".join(why))
                    _agent_cleanup_partial(final_paths)
                    gui_queue.put(("cancel", pid))
                else:
                    skip = set(job.get("conflict_skip") or [])
                    to_move = []
                    for p in final_paths:
                        dest_p = os.path.join(dest_dir, os.path.basename(p)) if dest_dir else p
                        try:
                            dest_key = os.path.normcase(os.path.abspath(dest_p))
                        except Exception:
                            dest_key = dest_p
                        if dest_key in skip:
                            try:
                                if os.path.isdir(p):
                                    import shutil
                                    shutil.rmtree(p, ignore_errors=True)
                                elif os.path.isfile(p):
                                    os.remove(p)
                            except Exception:
                                pass
                            continue
                        to_move.append(p)
                    already_in_dest = False
                    if dest_dir and to_move:
                        try:
                            dest_abs = os.path.normcase(os.path.abspath(dest_dir))
                            already_in_dest = all(
                                os.path.normcase(os.path.dirname(os.path.abspath(p))) == dest_abs
                                for p in to_move
                            )
                        except Exception:
                            already_in_dest = False
                    if dest_dir and to_move and not already_in_dest:
                        move_total = sum(_path_byte_size(p) for p in to_move)
                        need_copy = any(not _same_volume(p, dest_dir) for p in to_move)
                        with _file_io_lock:
                            if need_copy:
                                gui_queue.put(("finalize_start", (move_total, pid)))
                            to_move, moved_all = _relocate_transfer_files_unlocked(
                                to_move, dest_dir,
                                on_progress=lambda n, j=pid: gui_queue.put(("finalize_progress", (n, j))),
                                should_stop=lambda: not job.get("allow"),
                            )
                        agent_print(f"[ClipboardAgent] Paste dest={dest_dir} moved_all={moved_all} n={len(to_move)}")
                        if not job.get("allow"):
                            _agent_cleanup_partial(to_move)
                            gui_queue.put(("cancel", pid))
                            return
                    elif already_in_dest:
                        agent_print(f"[ClipboardAgent] File da o dest={dest_dir}, bo copy lan 2.")
                    elif not to_move:
                        agent_print("[ClipboardAgent] Khong chuyen file (skip het / Huy).")
                    try:
                        _purge_rdxfer_staging(dest_dir=dest_dir, extra_paths=list(final_paths) + list(to_move or []))
                        _schedule_scrub_probe(dest_dir)
                    except Exception:
                        pass
                    gui_queue.put(("end", pid))
                    agent_print("[ClipboardAgent] Da chuyen file xong (sau khi thoat RENDERFORMAT).")
            else:
                agent_print(
                    f"[ClipboardAgent] Cho FILES ket thuc bat thuong "
                    f"event={job['event'].is_set()} allow={job.get('allow')} "
                    f"n_paths={len(job.get('paths') or [])}."
                )
                leftover = list(job.get("paths") or [])
                _agent_cleanup_partial(leftover)
                gui_queue.put(("cancel", pid))
                _send_cancel_to_host(pid)
        except Exception as e:
            agent_print(f"[ClipboardAgent] Loi hoan tat paste nen: {e}")
            _agent_cleanup_partial(list(job.get("paths") or []))
            gui_queue.put(("cancel", pid))
            try:
                _send_cancel_to_host(pid)
            except Exception:
                pass
        finally:
            _agent_jobs.pop(pid, None)
            if not _agent_jobs:
                _agent_accept_files = False
                _agent_allow_xfer = False
                _agent_download_active = False
            else:
                _agent_accept_files = True
                _agent_allow_xfer = True
                _agent_download_active = True
            _release_agent_file_request()
            if _pending_info:
                _agent_schedule_rearm(0.45)

    def _agent_wndproc(hwnd, msg, wparam, lparam):
        """WndProc cho hidden window của agent. Xử lý WM_RENDERFORMAT (Paste xảy ra)."""
        nonlocal _is_rendering, _files_ready_paths, _files_ready_event, _ignore_destroy, _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_dummy_h_active, _agent_cached_explorer_path, _agent_suppress_render_until, _agent_expect_repaste_until, _agent_paste_id, _agent_accept_files, _agent_allow_xfer, _agent_xfer_cancel_at, _agent_download_active, _agent_conflict_choice, _agent_conflict_skip, _agent_allow_delayed, _agent_paste_gesture_id, _agent_consumed_gesture_id, _agent_paste_coalesce_until, _agent_force_delayed_setup

        if msg == WM_USER_SETUP_DELAYED:
            if not _agent_force_delayed_setup and _agent_user_clipboard_wins():
                _yield_clipboard_to_user("setup skipped")
                return 0
            if (_agent_allow_delayed or _agent_force_delayed_setup) and _pending_info:
                _execute_agent_delayed_rendering(hwnd)
            return 0

        if msg == WM_USER_UNBLOCK_PASTE:
            # Đang trong WM_RENDERFORMAT (pump) hoặc vừa Hủy: trả HDROP rỗng, không EmptyClipboard.
            empty_hdrop = create_hdrop_data([])
            if empty_hdrop:
                _ignore_destroy = True
                try:
                    res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                    if not res:
                        fn_GlobalFree(empty_hdrop)
                    agent_print(f"[ClipboardAgent] Unblock Explorer sau Huy. HDROP rong res={res}")
                except Exception as e:
                    agent_print(f"[ClipboardAgent] Unblock Explorer loi: {e}")
                    try:
                        fn_GlobalFree(empty_hdrop)
                    except Exception:
                        pass
                finally:
                    _ignore_destroy = False
            return 0

        if msg == 0x031D: # WM_CLIPBOARDUPDATE
            if _ignore_destroy or _is_rendering:
                return 0
            if is_own_clipboard_write():
                return 0
            if should_preserve_user_clipboard(hwnd):
                _yield_clipboard_to_user("local clipboard")
            def _send_clipboard():
                import time
                time.sleep(0.35)
                if _is_rendering or is_own_clipboard_write():
                    return
                if should_preserve_user_clipboard(_agent_hwnd):
                    _yield_clipboard_to_user("local clipboard poll")
                files = get_clipboard_files(retries=3)
                if files:
                    if _paths_are_probe_or_xfer(files):
                        return
                    _yield_clipboard_to_user("local files")
                    _agent_emit_copied_files(force=True)
                    return
                text = get_clipboard_text()
                if text:
                    _yield_clipboard_to_user("local text")
                    try:
                        import win32pipe, win32file, json
                        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
                        win32pipe.WaitNamedPipe(pipe_name, 5000)
                        pipe_handle = win32file.CreateFile(pipe_name, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
                        msg = "COPIED_TEXT|" + json.dumps(text)
                        win32file.WriteFile(pipe_handle, msg.encode('utf-8'))
                        win32file.CloseHandle(pipe_handle)
                        agent_print("[ClipboardAgent] Đã gửi COPIED_TEXT cho Service.")
                    except Exception as e:
                        agent_print(f"Failed to send COPIED_TEXT: {e}")
            threading.Thread(target=_send_clipboard, daemon=True).start()
            return 0

        if msg == WM_RENDERFORMAT and wparam == CF_HDROP:
            if not _pending_info or not _agent_allow_delayed:
                empty_hdrop = create_hdrop_data([])
                if empty_hdrop:
                    _ignore_destroy = True
                    try:
                        res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                        if not res:
                            fn_GlobalFree(empty_hdrop)
                    finally:
                        _ignore_destroy = False
                return 0
            if _is_rendering:
                agent_print("[ClipboardAgent] WM_RENDERFORMAT trung (cung GetData) — HDROP rỗng.")
                if _offer_empty_hdrop():
                    _agent_dummy_h_active = True
                return 0
            if time.time() < _agent_suppress_render_until and _agent_paste_gesture_id <= _agent_consumed_gesture_id:
                agent_print("[ClipboardAgent] Ngay sau Hủy — HDROP rỗng, không tải ngầm.")
                if _offer_empty_hdrop():
                    _agent_dummy_h_active = True
                    ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                return 0
                
            # Kiểm tra nếu là truy vấn từ menu chuột phải (context menu) thì tránh tải file thực tế lúc này
            is_menu = check_is_menu_query(
                _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_ctrl_v_time,
                expect_repaste=time.time() < _agent_expect_repaste_until,
                lmb_on_menu=_agent_lmb_hit_context_menu,
                menu_item_kind=_agent_lmb_menu_item_kind,
                last_dblclick=_agent_last_dblclick_time,
            )
            if is_menu == "MENU":
                agent_print("[ClipboardAgent] Phát hiện truy vấn menu. Dummy HDROP, chờ user dán...")
                if _offer_probe_hdrop(_pending_info.get("files")):
                    _agent_dummy_h_active = True
                    ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                _schedule_scrub_probe(_agent_cached_explorer_path)
                return 0
            elif is_menu == "BACKGROUND":
                agent_print("[ClipboardAgent] Probe Explorer — HDROP rỗng (không dán stub).")
                if _offer_empty_hdrop():
                    _agent_dummy_h_active = True
                    ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                return 0

            living = any(j.get("allow") for j in _agent_jobs.values())
            same_gesture = _agent_paste_gesture_id <= _agent_consumed_gesture_id
            if same_gesture and (living or time.time() < _agent_paste_coalesce_until):
                agent_print("[ClipboardAgent] GetData trùng (chưa có Paste mới) — không mở dialog thêm.")
                if _offer_empty_hdrop():
                    _agent_dummy_h_active = True
                return 0
            if _agent_xfer_cancel_at and not living:
                new_kb = _agent_last_ctrl_v_time > _agent_xfer_cancel_at + 0.15
                new_menu = (
                    _agent_lmb_hit_context_menu
                    and _agent_lmb_menu_item_kind == "paste"
                    and _agent_last_lbutton_time > _agent_xfer_cancel_at + 0.15
                    and _agent_last_rbutton_time > _agent_xfer_cancel_at
                    and _agent_last_lbutton_time > _agent_last_rbutton_time
                )
                if not new_kb and not new_menu:
                    agent_print("[ClipboardAgent] Sau Hủy chưa có Paste mới — HDROP rỗng, không mở dialog.")
                    if _offer_empty_hdrop():
                        _agent_dummy_h_active = True
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                    return 0

            _is_rendering = True
            _agent_download_active = True
            _agent_expect_repaste_until = 0.0
            _agent_paste_id += 1
            paste_id = _agent_paste_id
            _agent_consumed_gesture_id = _agent_paste_gesture_id
            _agent_paste_coalesce_until = time.time() + 0.35
            _agent_accept_files = True
            _agent_allow_xfer = True
            agent_print(f"[ClipboardAgent] Nhận WM_RENDERFORMAT → Paste. Job paste_id={paste_id} (song song={len(_agent_jobs)}).")
            try:
                info = {
                    "display_name": _pending_info.get("display_name", "Files"),
                    "item_kind": _pending_info.get("item_kind") or "file",
                    "total_size": _pending_info.get("total_size", 0),
                    "files": [dict(f) if isinstance(f, dict) else f for f in (_pending_info.get("files") or [])],
                }
                job = {
                    "paste_id": paste_id,
                    "info": info,
                    "dest": _agent_cached_explorer_path,
                    "event": threading.Event(),
                    "paths": [],
                    "allow": True,
                    "accept": True,
                    "conflict_event": threading.Event(),
                    "conflict_choice": "replace",
                    "conflict_skip": set(),
                    "requested_files": [],
                    "last_progress_bytes": 0,
                    "last_progress_at": time.time(),
                }
                _agent_jobs[paste_id] = job
                gui_queue.put(("conflict_check", (
                    _agent_cached_explorer_path,
                    list(info.get("files") or []),
                    info.get("display_name", "Files"),
                    info.get("total_size", 0),
                    paste_id,
                )))
                # Trả HDROP rỗng NGAY — không chờ 100% trong GetData (move file lúc Explorer lock thư mục = treo máy).
                empty_hdrop = create_hdrop_data([])
                if empty_hdrop:
                    _ignore_destroy = True
                    try:
                        res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                        if not res:
                            fn_GlobalFree(empty_hdrop)
                        agent_print(f"[ClipboardAgent] Unblock Explorer, tai file o nen. res={res}")
                    finally:
                        _ignore_destroy = False
                _schedule_scrub_probe(_agent_cached_explorer_path)
                dest = _agent_cached_explorer_path
                threading.Thread(
                    target=_agent_complete_download,
                    args=(job,),
                    daemon=True,
                    name="AgentPasteFinish",
                ).start()
                if _pending_info:
                    _agent_schedule_rearm(0.35)
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lỗi xử lý WM_RENDERFORMAT: {e}")
                _agent_jobs.pop(paste_id, None)
                if not _agent_jobs:
                    _agent_download_active = False
                    _agent_allow_xfer = False
                    _agent_accept_files = False
                empty_hdrop = create_hdrop_data([])
                if empty_hdrop:
                    _ignore_destroy = True
                    try:
                        res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                        if not res:
                            fn_GlobalFree(empty_hdrop)
                    finally:
                        _ignore_destroy = False
                if _pending_info:
                    _agent_schedule_rearm(0.45)
                gui_queue.put(("cancel", paste_id))
            finally:
                _is_rendering = False
            return 0

        if msg == WM_DESTROYCLIPBOARD and not _ignore_destroy:
            if is_own_clipboard_write():
                return 0
            _yield_clipboard_to_user("destroy")
            agent_print("[ClipboardAgent] WM_DESTROYCLIPBOARD → không cướp clipboard user; giữ PENDING từ client.")
            return 0

        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _create_agent_window():
        """Tạo hidden Win32 window cho agent, chạy trong luồng riêng với message loop."""
        nonlocal _agent_hwnd
        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_uint,
            ctypes.c_size_t, ctypes.c_size_t
        )
        _wndproc_ref = WNDPROC(_agent_wndproc)

        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize",        wintypes.UINT),
                ("style",         wintypes.UINT),
                ("lpfnWndProc",   WNDPROC),
                ("cbClsExtra",    ctypes.c_int),
                ("cbWndExtra",    ctypes.c_int),
                ("hInstance",     ctypes.c_void_p),
                ("hIcon",         ctypes.c_void_p),
                ("hCursor",       ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName",  wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm",       ctypes.c_void_p),
            ]

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Định nghĩa kiểu dữ liệu chuẩn Win32 API cho môi trường 64-bit
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p

        user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
        user32.RegisterClassExW.restype = wintypes.ATOM

        user32.CreateWindowExW.argtypes = [
            ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
            ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        ]
        user32.CreateWindowExW.restype = ctypes.c_void_p

        cls_name = "AntigravityClipboardAgentWnd"
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = _wndproc_ref
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = cls_name
        user32.RegisterClassExW(ctypes.byref(wc))

        hwnd = user32.CreateWindowExW(
            0, cls_name, "ClipboardAgent",
            0, 0, 0, 0, 0,
            None, None, wc.hInstance, None
        )
        _agent_hwnd = hwnd
        agent_print(f"[ClipboardAgent] Window ẩn đã tạo. HWND={hwnd}")
        try:
            add_ok = user32.AddClipboardFormatListener(ctypes.c_void_p(hwnd))
            agent_print(f"[ClipboardAgent] AddClipboardFormatListener={add_ok}")
        except Exception as e:
            agent_print(f"[ClipboardAgent] AddClipboardFormatListener lỗi: {e}")

        def _stamp_ctrl_v():
            nonlocal _agent_last_ctrl_v_time, _agent_dummy_h_active
            _agent_last_ctrl_v_time = time.time()
            _note_paste_gesture()
            if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                _agent_dummy_h_active = False
                ctypes.windll.user32.PostMessageW(
                    ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0
                )

        def _stamp_lbutton():
            nonlocal _agent_last_lbutton_time, _agent_dummy_h_active, _agent_lmb_hit_context_menu
            nonlocal _agent_lmb_menu_item_kind
            _register_lmb_down()
            if _cursor_over_current_process():
                return
            if _cursor_over_context_menu():
                _agent_lmb_hit_context_menu = True
                kind, name = _capture_menu_item_at_cursor()
                _agent_lmb_menu_item_kind = kind
                agent_print(f"[ClipboardAgent] LMB menu item name={name!r} kind={kind}")
                if kind != "not_paste":
                    _note_paste_gesture()
            if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                _agent_dummy_h_active = False
                ctypes.windll.user32.PostMessageW(
                    ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0
                )

        def _stamp_rbutton():
            nonlocal _agent_last_rbutton_time, _agent_dummy_h_active, _agent_lmb_hit_context_menu
            nonlocal _agent_lmb_menu_item_kind
            _agent_last_rbutton_time = time.time()
            _agent_lmb_hit_context_menu = False
            _agent_lmb_menu_item_kind = ""
            if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                _agent_dummy_h_active = False
                ctypes.windll.user32.PostMessageW(
                    ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0
                )

        hk_kb, hk_mouse = _install_paste_ll_hooks(_stamp_ctrl_v, _stamp_lbutton, _stamp_rbutton)
        agent_print(f"[ClipboardAgent] LL hooks kb={hk_kb} mouse={hk_mouse}")

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    threading.Thread(target=_create_agent_window, daemon=True, name="AgentWin32MsgLoop").start()
    time.sleep(0.1)  # Chờ window khởi tạo

    def _agent_text_poll_loop():
        last_seq = 0
        while True:
            time.sleep(0.4)
            try:
                if _is_rendering or is_own_clipboard_write():
                    continue
                if should_preserve_user_clipboard(_agent_hwnd):
                    _yield_clipboard_to_user("poll local")
                    last_seq = get_clipboard_sequence_number() or last_seq
                    continue
                seq = get_clipboard_sequence_number()
                if not seq or seq == last_seq:
                    continue
                text = get_clipboard_text()
                if not text:
                    last_seq = seq
                    continue
                try:
                    import win32pipe, win32file, json
                    pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
                    win32pipe.WaitNamedPipe(pipe_name, 3000)
                    pipe_handle = win32file.CreateFile(pipe_name, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
                    win32file.WriteFile(pipe_handle, ("COPIED_TEXT|" + json.dumps(text)).encode("utf-8"))
                    win32file.CloseHandle(pipe_handle)
                    last_seq = seq
                    agent_print("[ClipboardAgent] Poll: đã gửi COPIED_TEXT.")
                except Exception:
                    pass
            except Exception:
                pass

    threading.Thread(target=_agent_text_poll_loop, daemon=True, name="AgentClipPoll").start()

    def trigger_cancel(paste_id=None):
        """Dừng một (hoặc mọi) lần tải; giữ PENDING để user Paste lại."""
        nonlocal _agent_expect_repaste_until, _agent_accept_files, _agent_allow_xfer
        nonlocal _agent_xfer_cancel_at, _agent_suppress_render_until, _agent_last_ctrl_v_time, _agent_ctrl_v_held
        nonlocal _agent_download_active

        def _stop_job(pid, job):
            leftover = list(job.get("paths") or [])
            job["allow"] = False
            job["accept"] = False
            job["conflict_choice"] = "cancel"
            try:
                job["conflict_event"].set()
            except Exception:
                pass
            try:
                job["event"].set()
            except Exception:
                pass
            job_meta = list(((job.get("info") or {}).get("files") if job else None) or [])
            _agent_cleanup_partial(leftover, files_meta=job_meta, wipe_all_staging=False)
            try:
                threading.Timer(
                    0.4,
                    lambda p=list(leftover), m=job_meta: _agent_cleanup_partial(p, files_meta=m, wipe_all_staging=False),
                ).start()
                threading.Timer(
                    1.2,
                    lambda p=list(leftover), m=job_meta: _agent_cleanup_partial(p, files_meta=m, wipe_all_staging=False),
                ).start()
            except Exception:
                pass
            gui_queue.put(("cancel", pid))

        if paste_id is None:
            for pid, job in list(_agent_jobs.items()):
                _stop_job(pid, job)
        else:
            try:
                paste_id = int(paste_id)
            except Exception:
                pass
            job = _agent_jobs.get(paste_id)
            if job:
                _stop_job(paste_id, job)
            else:
                gui_queue.put(("cancel", paste_id))

        leftover = list(_files_ready_paths)
        if leftover and paste_id is None:
            _files_ready_paths.clear()
            _files_ready_event.set()
            _agent_cleanup_partial(leftover)

        still_allow = any(j.get("allow") for j in _agent_jobs.values())
        if not still_allow:
            _agent_allow_xfer = False
            _agent_accept_files = False
            _agent_download_active = False
            _agent_xfer_cancel_at = time.time()
            _agent_suppress_render_until = max(_agent_suppress_render_until, time.time() + 1.5)
            _agent_last_ctrl_v_time = 0.0
            _agent_ctrl_v_held = False
            _agent_expect_repaste_until = time.time() + 60.0
        if (not still_allow) and _is_rendering and _agent_hwnd:
            try:
                ctypes.windll.user32.PostMessageW(
                    ctypes.c_void_p(_agent_hwnd), WM_USER_UNBLOCK_PASTE, 0, 0
                )
            except Exception:
                pass
        agent_print(f"[ClipboardAgent] Đã hủy tải paste_id={paste_id}; jobs={list(_agent_jobs.keys())}.")

    def trigger_cancel_win32(paste_id=None):
        """Nút Hủy trong dialog → host dừng gửi/nhận và xóa file tạm."""
        _send_cancel_to_host(paste_id)
        trigger_cancel(paste_id)

    def _open_paste_progress_dialog(paste_id, display_name, total_size, dest_dir):
        """Một paste_id → một dialog. Chỉ gọi khi có Paste mới (không gọi từ GetData trùng)."""
        nonlocal active_dialog
        if paste_id is not None and active_dialogs.get(paste_id):
            return active_dialogs[paste_id]
        job = _agent_jobs.get(paste_id) if paste_id is not None else None
        if job is not None and not job.get("allow"):
            agent_print("[ClipboardAgent] Bo dialog (job da Huy).")
            return None
        job_files = ((job.get("info") or {}).get("files") if job else None) or []
        if not job_files and job is not None:
            job_files = job.get("requested_files") or []
        kind, name = _copy_batch_kind_and_name(job_files, display_name)
        pending_kind = ((job.get("info") or {}).get("item_kind") if job else None) or (
            _pending_info.get("item_kind") if _pending_info else None
        )
        if pending_kind in ("file", "folder") and not job_files:
            kind = pending_kind
        stack = len([d for d in active_dialogs.values() if d])
        dlg = ProgressDialog(
            root, _("Đang tải file về..."), name, total_size,
            on_cancel=lambda p=paste_id: trigger_cancel_win32(p),
            dest_dir=dest_dir,
            reserve_finalize=True,
            stack_index=stack,
            job_id=paste_id,
            item_kind=kind,
        )
        if paste_id is not None:
            active_dialogs[paste_id] = dlg
        active_dialog = dlg
        agent_print(f"[ClipboardAgent] Mo dialog tien trinh paste_id={paste_id} dest={dest_dir} stack={stack}")
        return dlg

    def poll_gui_queue():
        nonlocal active_dialog, _agent_meta_arrival_time, _agent_allow_xfer, _agent_suppress_render_until
        nonlocal _agent_conflict_choice, _agent_conflict_skip, _agent_allow_delayed, _agent_clip_seq_at_pending, _agent_paste_coalesce_until, _agent_force_delayed_setup, _agent_pending_offer_id
        while not gui_queue.empty():
            try:
                action, val = gui_queue.get_nowait()
                if action == "text":
                    agent_print(f"[ClipboardAgent] Đang nạp text vào Clipboard...")
                    set_clipboard_text(val, owner_hwnd=_agent_hwnd)
                elif action == "files":
                    agent_print("[ClipboardAgent] Bỏ qua action files (không dán HDROP im lặng).")
                elif action == "pending":
                    # Host gửi PENDING: → setup delayed rendering nếu window đã sẵn sàng
                    info = val
                    oid = 0
                    try:
                        oid = int((info or {}).get("offer_id") or 0) if isinstance(info, dict) else 0
                    except Exception:
                        oid = 0
                    if oid and oid < _agent_pending_offer_id:
                        same = _file_offer_fp((info or {}).get("files") if isinstance(info, dict) else None) == _file_offer_fp(_pending_info.get("files"))
                        if same:
                            agent_print(f"[ClipboardAgent] Bỏ PENDING cũ offer={oid} (đang giữ {_agent_pending_offer_id}).")
                            continue
                        agent_print(f"[ClipboardAgent] PENDING offer={oid} < {_agent_pending_offer_id} nhưng file khác — nhận copy mới.")
                    if oid:
                        _agent_pending_offer_id = oid
                    _pending_info.clear()
                    if isinstance(info, dict):
                        _pending_info.update(info)
                        files = info.get("files")
                        if isinstance(files, list):
                            _pending_info["files"] = [dict(f) if isinstance(f, dict) else f for f in files]
                    _agent_clip_seq_at_pending = get_clipboard_sequence_number()
                    # Copy mới từ client luôn cập nhật delayed clipboard (file 2, 3, n).
                    _agent_force_delayed_setup = True
                    _agent_allow_delayed = True
                    display_name = info.get("display_name", "Files") if isinstance(info, dict) else "Files"
                    total_size = info.get("total_size", 0) if isinstance(info, dict) else 0
                    if not _agent_jobs:
                        _files_ready_event.clear()
                        _files_ready_paths.clear()
                    _agent_meta_arrival_time = time.time()
                    agent_print(f"[ClipboardAgent] Nhận PENDING: '{display_name}' ({total_size} bytes). Đang setup delayed rendering...")
                    if _agent_allow_delayed and _agent_hwnd:
                        ctypes.windll.user32.PostMessageW(
                            ctypes.c_void_p(_agent_hwnd),
                            WM_USER_SETUP_DELAYED, 0, 0
                        )
                    elif not _agent_hwnd:
                        agent_print("[ClipboardAgent] HWND chưa sẵn sàng, bỏ qua PENDING.")
                elif action == "pipe_cancel":
                    agent_print("[ClipboardAgent] Nhận tín hiệu CANCEL từ Pipe. Đang hủy...")
                    trigger_cancel(val)
                elif action == "files_ready":
                    paste_tok, paths = _parse_files_pipe_payload(val)
                    job = _agent_jobs.get(paste_tok) if paste_tok is not None else None
                    if job is None:
                        got = [os.path.basename(p).lower() for p in paths]
                        for cand in _agent_jobs.values():
                            if not cand.get("accept"):
                                continue
                            meta = ((cand.get("requested_files") or None) or (cand.get("info") or {}).get("files") or [])
                            exp = [
                                os.path.basename(str(f.get("name") or "").replace("\\", "/")).lower()
                                for f in meta
                                if isinstance(f, dict)
                            ]
                            exp_top = {
                                str(f.get("name") or "").replace("\\", "/").split("/")[0].lower()
                                for f in meta
                                if isinstance(f, dict) and f.get("name")
                            }
                            if got and (
                                (exp and set(got) <= set(exp))
                                or (exp_top and set(got) <= exp_top)
                            ):
                                job = cand
                                break
                    if job is None or not job.get("accept"):
                        agent_print("[ClipboardAgent] Bỏ FILES trễ (đã hủy / không đang paste).")
                        _agent_cleanup_partial(paths, files_meta=[], wipe_all_staging=False)
                        continue
                    job["paths"][:] = paths
                    job["event"].set()
                    agent_print(f"[ClipboardAgent] files_ready paste_id={job.get('paste_id')}: {len(paths)} file đã sẵn sàng.")
                elif action == "start":
                    display_name, total_size = val[0], val[1]
                    dest_dir = val[2] if len(val) > 2 else None
                    paste_id = val[3] if len(val) > 3 else None
                    _open_paste_progress_dialog(paste_id, display_name, total_size, dest_dir)
                elif action == "progress":
                    if isinstance(val, (tuple, list)):
                        pid, nbytes = (val[0] if val else None), (val[1] if len(val) > 1 else 0)
                    else:
                        pid, nbytes = None, val
                    dlg = active_dialogs.get(pid) if pid is not None else active_dialog
                    if dlg:
                        try: dlg.update_progress(nbytes)
                        except: pass
                    job = _agent_jobs.get(pid) if pid is not None else None
                    if job is not None:
                        job["last_progress_at"] = time.time()
                        try:
                            job["last_progress_bytes"] = int(nbytes or 0)
                        except Exception:
                            pass
                elif action == "finalize_start":
                    if isinstance(val, (tuple, list)):
                        n, pid = (val[0] if val else 0), (val[1] if len(val) > 1 else None)
                    else:
                        n, pid = val, None
                    dlg = active_dialogs.get(pid) if pid is not None else active_dialog
                    if dlg:
                        try: dlg.begin_finalize(n or 0)
                        except: pass
                elif action == "finalize_progress":
                    if isinstance(val, (tuple, list)):
                        n, pid = (val[0] if val else 0), (val[1] if len(val) > 1 else None)
                    else:
                        n, pid = val, None
                    dlg = active_dialogs.get(pid) if pid is not None else active_dialog
                    if dlg:
                        try: dlg.add_finalize_bytes(n or 0)
                        except: pass
                elif action == "end":
                    pid = val
                    dlg = active_dialogs.pop(pid, None) if pid is not None else None
                    if dlg:
                        try: dlg.mark_complete()
                        except: pass
                        def _close(d=dlg, j=pid):
                            nonlocal active_dialog
                            try: d.destroy()
                            except: pass
                            if active_dialog is d:
                                active_dialog = next(iter(active_dialogs.values()), None)
                        root.after(0, _close)
                elif action == "conflict_check":
                    dest_dir, files, display_name, total_size, paste_id = val
                    job = _agent_jobs.get(paste_id)
                    if job is None:
                        continue
                    job["conflict_choice"] = "replace"
                    job["conflict_skip"] = set()

                    def _file_dest_key(f_or_path):
                        if isinstance(f_or_path, dict):
                            filename = str(f_or_path.get("name") or "")
                            dest_path = os.path.join(dest_dir, filename.replace("/", os.sep)) if dest_dir else filename
                        else:
                            dest_path = f_or_path
                        try:
                            return os.path.normcase(os.path.abspath(dest_path))
                        except Exception:
                            return dest_path

                    def _files_not_skipped():
                        skip = set(job.get("conflict_skip") or [])
                        out = []
                        size = 0
                        for f in files:
                            if _file_dest_key(f) in skip:
                                continue
                            out.append(f)
                            try:
                                size += int(f.get("size") or 0)
                            except Exception:
                                pass
                        return out, size

                    def _begin_download(files_req=None, size=None):
                        req = files if files_req is None else files_req
                        sz = total_size if size is None else size
                        if not req:
                            return False
                        job["requested_files"] = [dict(f) if isinstance(f, dict) else f for f in req]
                        _open_paste_progress_dialog(
                            paste_id,
                            display_name,
                            sz,
                            dest_dir,
                        )
                        _send_request_files_to_host(req, dest_dir, paste_id)
                        return True

                    def _done_conflict():
                        nonlocal _agent_paste_coalesce_until
                        _agent_paste_coalesce_until = time.time() + 0.35
                        job["conflict_event"].set()

                    try:
                        if not dest_dir or not os.path.isdir(dest_dir) or not files:
                            _begin_download()
                            _done_conflict()
                            continue
                        cleanup_incomplete_named_files([dest_dir], files)
                        _schedule_scrub_probe(dest_dir)
                        conflicts = []
                        for f in files:
                            filename = str(f.get("name") or "")
                            if not filename:
                                continue
                            dest_path = os.path.join(dest_dir, filename.replace("/", os.sep))
                            if not os.path.exists(dest_path):
                                continue
                            expected = _file_expected_size(f)
                            if _is_transfer_junk_at_dest(dest_path, expected):
                                _retry_remove_path(dest_path)
                                continue
                            try:
                                st = os.stat(dest_path)
                            except Exception:
                                continue
                            source_info = {
                                "size": f.get("size", 0),
                                "mtime": f.get("mtime", 0),
                                "path": f.get("path") or filename,
                            }
                            dest_info = {"size": st.st_size, "mtime": st.st_mtime, "path": dest_path}
                            conflicts.append((os.path.basename(filename.replace("\\", "/")), source_info, dest_info, dest_path))
                        if not conflicts:
                            req, sz = _files_not_skipped()
                            if req:
                                _begin_download(req, sz)
                            else:
                                job["event"].set()
                            _done_conflict()
                            continue
                        replace_all = False
                        skip_all = False
                        has_multiple = len(files) > 1
                        cancelled = False
                        idx = 0
                        while idx < len(conflicts):
                            filename, source_info, dest_info, dest_path = conflicts[idx]
                            def _skip_path(dp, j=job):
                                try:
                                    j["conflict_skip"].add(os.path.normcase(os.path.abspath(dp)))
                                except Exception:
                                    j["conflict_skip"].add(dp)
                            if skip_all:
                                _skip_path(dest_path)
                                idx += 1
                                continue
                            if replace_all:
                                idx += 1
                                continue
                            dialog = ClassicCopyDialog(root, filename, source_info, dest_info, has_multiple)
                            try:
                                dialog.grab_set()
                            except Exception:
                                pass
                            root.wait_window(dialog)
                            choice = dialog.choice if dialog.choice else "cancel"
                            apply_all = bool(getattr(dialog, "var_all", None) and dialog.var_all.get())
                            if choice == "replace_all" or (choice == "replace" and apply_all):
                                replace_all = True
                                idx += 1
                                continue
                            if choice == "replace":
                                idx += 1
                                continue
                            if choice == "skip_all" or (choice == "skip" and apply_all):
                                for j in range(idx, len(conflicts)):
                                    _skip_path(conflicts[j][3])
                                break
                            if choice == "skip":
                                _skip_path(dest_path)
                                idx += 1
                                continue
                            cancelled = True
                            break
                        if cancelled:
                            job["conflict_choice"] = "cancel"
                            trigger_cancel_win32(paste_id)
                        else:
                            req, sz = _files_not_skipped()
                            if not req:
                                job["conflict_choice"] = "cancel"
                                agent_print("[ClipboardAgent] Don't copy — khong tai, khong mo dialog tien trinh.")
                                _agent_schedule_rearm(0.45)
                            else:
                                job["conflict_choice"] = "replace"
                                _begin_download(req, sz)
                    except Exception as e:
                        agent_print(f"[ClipboardAgent] Lỗi dialog ghi đè: {e}")
                        job["conflict_choice"] = "replace"
                        _begin_download()
                    _done_conflict()
                elif action == "cancel":
                    pid = val
                    targets = []
                    if pid is None:
                        targets = list(active_dialogs.items())
                        active_dialogs.clear()
                        if active_dialog:
                            targets.append((None, active_dialog))
                    elif pid in active_dialogs:
                        targets = [(pid, active_dialogs.pop(pid))]
                    else:
                        targets = []
                    for _, dlg in targets:
                        try:
                            if dlg:
                                dlg.on_cancel = None
                                dlg.destroy()
                        except: pass
                    active_dialog = next(iter(active_dialogs.values()), None)
                elif action == "clear_clip":
                    try:
                        clear_local_clipboard(_agent_hwnd)
                        agent_print("[ClipboardAgent] Đã xóa clipboard theo lệnh host đóng cửa sổ.")
                    except Exception as e:
                        agent_print(f"[ClipboardAgent] Lỗi xóa clipboard: {e}")
            except queue.Empty:
                break
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lỗi xử lý hàng đợi GUI: {e}")
        root.after(50, poll_gui_queue)

    t = threading.Thread(target=pipe_listener_loop, daemon=True)
    t.start()
    
    poll_gui_queue()
    root.mainloop()
