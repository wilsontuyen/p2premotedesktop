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
from utils.clipboard_api import (
    ENABLE_CLIPBOARD_SYNC, 
    set_clipboard_dword_format, 
    setup_clipboard_exclusions, 
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
                    self.manager.last_lbutton_time = time.time()
                    if getattr(self.manager, 'dummy_h_active', False):
                        self.manager.dummy_h_active = False
                        self.manager.setup_delayed_rendering()
            if user32.GetAsyncKeyState(0x02) & 0x8000:
                if self.manager:
                    self.manager.last_rbutton_time = time.time()
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
                    self.manager._shift_ins_held = True
                    if getattr(self.manager, 'dummy_h_active', False):
                        self.manager.dummy_h_active = False
                        self.manager.setup_delayed_rendering()
            else:
                if self.manager:
                    self.manager._shift_ins_held = False
            # Explorer thường không đổi clipboard khi Ctrl+C lại cùng file → host mất CF_HDROP delayed (Paste tắt).
            if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x43) & 0x8000):
                if self.manager:
                    now = time.time()
                    if now - getattr(self.manager, "_last_ctrl_c_time", 0) > 0.4:
                        self.manager._last_ctrl_c_time = now
                        def _resend_copy(m=self.manager):
                            if getattr(m, "pygame_hwnd", None):
                                u = ctypes.windll.user32
                                u.GetForegroundWindow.restype = ctypes.c_void_p
                                if u.GetForegroundWindow() != m.pygame_hwnd:
                                    return
                            m._process_clipboard_change_debounced(force=True)
                        threading.Timer(0.18, _resend_copy).start()
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


def _xfer_staging_dir(base_dir, xfer_id):
    if not base_dir:
        return base_dir
    if xfer_id is None:
        return base_dir
    return os.path.join(base_dir, f".rdxfer_{xfer_id}")


def _is_transfer_staging_dir(path):
    if not path:
        return False
    abs_path = os.path.normcase(os.path.abspath(path))
    staging = [
        os.path.normcase(os.path.abspath(HEADLESS_TRANSFER_DIR)),
        os.path.normcase(os.path.abspath(os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"))),
    ]
    return abs_path in staging


def relocate_transfer_files(src_paths, dest_dir):
    """Chuyển file từ thư mục tạm sang thư mục Explorer đang Paste. Trả về (paths, moved_all)."""
    import shutil
    if not dest_dir or not os.path.isdir(dest_dir) or _is_transfer_staging_dir(dest_dir):
        return list(src_paths or []), False
    dest_abs = os.path.normcase(os.path.abspath(dest_dir))
    moved = []
    all_in_dest = True
    for src in src_paths or []:
        if not src or not os.path.exists(src):
            continue
        src_abs = os.path.abspath(src)
        src_dir = os.path.normcase(os.path.dirname(src_abs))
        if src_dir == dest_abs:
            moved.append(src_abs)
            continue
        dest_path = os.path.join(dest_dir, os.path.basename(src_abs))
        try:
            if os.path.exists(dest_path):
                if os.path.isdir(dest_path) and not os.path.islink(dest_path):
                    shutil.rmtree(dest_path, ignore_errors=True)
                else:
                    os.remove(dest_path)
            shutil.move(src_abs, dest_path)
            moved.append(os.path.abspath(dest_path))
        except Exception as e:
            log_debug(f"[relocate_transfer_files] move failed {src_abs} -> {dest_path}: {e}")
            try:
                if os.path.isdir(src_abs):
                    shutil.copytree(src_abs, dest_path)
                    shutil.rmtree(src_abs, ignore_errors=True)
                else:
                    shutil.copy2(src_abs, dest_path)
                    os.remove(src_abs)
                moved.append(os.path.abspath(dest_path))
            except Exception as e2:
                log_debug(f"[relocate_transfer_files] copy fallback failed: {e2}")
                moved.append(src_abs)
                all_in_dest = False
    if moved and all_in_dest:
        for p in moved:
            if os.path.normcase(os.path.dirname(os.path.abspath(p))) != dest_abs:
                all_in_dest = False
                break
    return moved, bool(moved) and all_in_dest


def _paths_match_expected_sizes(paths, meta_files):
    """False nếu thiếu file hoặc size không khớp metadata — tránh dán PE dở (mất icon)."""
    if not paths or not meta_files:
        return False
    by_base = {}
    for f in meta_files:
        name = str(f.get("name") or "").replace("\\", "/").split("/")[-1]
        if not name:
            continue
        try:
            by_base[name.lower()] = int(f.get("size") or 0)
        except Exception:
            return False
    for p in paths:
        if not p or not os.path.isfile(p):
            return False
        base = os.path.basename(p).lower()
        exp = by_base.get(base)
        if exp is None:
            return False
        try:
            if os.path.getsize(p) != exp:
                return False
        except Exception:
            return False
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
            hwnds_to_check.extend(related_hwnds(hwnd_clip))
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
                    sel = doc.SelectedItems()
                    if sel.Count == 1 and sel.Item(0).IsFolder:
                        path = sel.Item(0).Path
                    else:
                        path = doc.Folder.Self.Path
                except Exception:
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
        1,       # Số instance tối đa
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
    """Nút Paste trên thanh lệnh Win11 nằm gần đỉnh cửa sổ Explorer — khác click chọn thư mục."""
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


def _offer_probe_hdrop():
    """Luôn SetClipboardData khi Explorer GetData — return không data = menu chuột phải treo hàng giây."""
    dummy_h = create_hdrop_data([_DUMMY_HDROP_PATH])
    if dummy_h:
        fn_SetClipboardData(15, dummy_h)
        return True
    return False


def check_is_menu_query(last_lbutton, last_rbutton, meta_arrival_time, last_ctrl_v=0.0, expect_repaste=False):
    """
    Kiểm tra xem yêu cầu WM_RENDERFORMAT hiện tại có phải là do menu chuột phải (context menu)
    hoặc tiến trình quét tự động trong nền truy vấn hay không, hay là thao tác Paste thực tế.
    Trả về 'MENU', 'BACKGROUND', hoặc False.
    """
    user32 = ctypes.windll.user32
    from ctypes import wintypes
    
    # 0. CHẶN TUYỆT ĐỐI CÁC TIẾN TRÌNH QUÉT CLIPBOARD CỦA MÁY ẢO/REMOTE DESKTOP KHÁC
    try:
        user32.GetOpenClipboardWindow.restype = wintypes.HWND
        hwnd_clip = user32.GetOpenClipboardWindow()
        if hwnd_clip:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd_clip, ctypes.byref(pid))
            import psutil
            proc_name = psutil.Process(pid.value).name().lower()
            if proc_name in ("vmtoolsd.exe", "vboxtray.exe", "rdpclip.exe", "mstsc.exe", "vncviewer.exe", "teamviewer.exe", "anydesk.exe"):
                log_debug(f"[check_is_menu_query] Tra ve BACKGROUND: Phat hien {proc_name} dang mo clipboard")
                return "BACKGROUND"
            if pid.value == os.getpid():
                log_debug("[check_is_menu_query] Tra ve BACKGROUND: chinh process nay dang mo clipboard (poll/scanner)")
                return "BACKGROUND"
    except Exception as e:
        pass
        
    t_now = time.time()
    time_since_lbutton = t_now - last_lbutton
    time_since_rbutton = t_now - last_rbutton
    meta_age = t_now - meta_arrival_time
    
    # --- 1. KIỂM TRA THAO TÁC PASTE RÕ RÀNG (Ưu tiên cao nhất) ---
    # Không dùng phím Enter: Explorer dùng Enter để mở thư mục — GetData lúc đó không phải Paste.
    is_ctrl_v = (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000)
    is_shift_ins = (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000)
    if is_ctrl_v or is_shift_ins or (last_ctrl_v >= meta_arrival_time and t_now - last_ctrl_v < 2.0):
        log_debug(f"[check_is_menu_query] Tra ve False: Phim dan/lenh duoc nhan")
        return False

    # Chuột trái chọn Paste trên context menu — RMB phải xảy ra SAU khi đã có file trên clipboard.
    if (time_since_lbutton < 1.5 and (last_lbutton > last_rbutton)
            and (last_lbutton - last_rbutton < 5.0)
            and last_rbutton >= meta_arrival_time and last_lbutton >= meta_arrival_time):
        log_debug(f"[check_is_menu_query] Tra ve False: Vua click chuot trai chon Paste sau khi click chuot phai ({last_lbutton - last_rbutton:.2f}s)")
        return False

    # --- 2. LOẠI TRỪ CỬA SỔ GUI CỦA APP ---
    try:
        import win32gui
        hwnd_fg = win32gui.GetForegroundWindow()
        if hwnd_fg:
            title = win32gui.GetWindowText(hwnd_fg)
            if title and ("Remote Desktop" in title or "Easy Remote" in title):
                log_debug(f"[check_is_menu_query] Tra ve BACKGROUND: Cua so hien hanh la Remote Desktop ({title})")
                return "BACKGROUND"
    except Exception as e:
        pass
        
    # --- 3. KIỂM TRA CỬA SỔ MENU (CONTEXT MENU) ---
    hwnd_menu = user32.FindWindowW("#32768", None)
    if hwnd_menu and user32.IsWindowVisible(hwnd_menu):
        log_debug(f"[check_is_menu_query] Tra ve MENU: Cua so menu (#32768) dang ton tai")
        return "MENU"
        
    try:
        class RECT_SIMPLE(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)
            ]
        class GUITHREADINFO_SIMPLE(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("flags", ctypes.c_ulong),
                ("hwndActive", ctypes.c_void_p),
                ("hwndFocus", ctypes.c_void_p),
                ("hwndCapture", ctypes.c_void_p),
                ("hwndMenuOwner", ctypes.c_void_p),
                ("hwndMoveSize", ctypes.c_void_p),
                ("hwndCaret", ctypes.c_void_p),
                ("rcCaret", RECT_SIMPLE)
            ]
        
        user32.GetOpenClipboardWindow.restype = ctypes.c_void_p
        hwnd_clip = user32.GetOpenClipboardWindow()
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        hwnd_fg = user32.GetForegroundWindow()
        
        for hwnd_check in (hwnd_clip, hwnd_fg):
            if hwnd_check:
                pid = wintypes.DWORD()
                tid = user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd_check), ctypes.byref(pid))
                gui_info = GUITHREADINFO_SIMPLE()
                gui_info.cbSize = ctypes.sizeof(GUITHREADINFO_SIMPLE)
                if user32.GetGUIThreadInfo(tid, ctypes.byref(gui_info)):
                    if gui_info.flags & (0x04 | 0x10 | 0x08):
                        log_debug(f"[check_is_menu_query] Tra ve MENU: Phat hien Menu Loop tu GetGUIThreadInfo flags={gui_info.flags}")
                        return "MENU"
    except Exception as e:
        pass
        
    # 5. Nếu chuột phải vừa được click gần đây (< 1.5s) và chưa có click trái sau đó
    if time_since_rbutton < 1.5 and last_rbutton >= last_lbutton:
        log_debug(f"[check_is_menu_query] Tra ve MENU: Vua click chuot phai gan day (age={time_since_rbutton:.3f}s)")
        return "MENU"

    # 6. Win11 Explorer GetData(CF_HDROP) khi mở cửa sổ / chọn thư mục để vẽ nút Paste
    # (Win10 chỉ EnumClipboardFormats nên không vào WM_RENDERFORMAT).
    if _is_windows_11() and _is_explorer_clipboard_client():
        # Không dùng expect_repaste để biến mọi GetData sau Hủy thành Paste thật —
        # chuột phải mở menu cũng GetData, sẽ tải ngầm + treo menu.
        lmb_down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
        if lmb_down and _cursor_in_explorer_command_bar():
            log_debug("[check_is_menu_query] Tra ve False: Win11 Explorer command-bar Paste")
            return False
        # Không coi mọi click trái (mở thư mục / chọn file) là Paste — Win11 GetData khi click.
        log_debug("[check_is_menu_query] Tra ve BACKGROUND: Win11 Explorer probe clipboard (khong phai Paste)")
        return "BACKGROUND"

    # 7. Fallback: coi là Paste thật (Win10 / app khác).
    log_debug(f"[check_is_menu_query] Tra ve False: Khong phai menu/scanner, xu ly nhu Paste (meta_age={meta_age:.3f}s)")
    return False


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
        self._last_ctrl_c_time = 0.0
        self._paste_dest_dir = None
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
        self._fm_send_abort = threading.Event()
        self._last_cancel_ack_time = 0.0
        self.cacher_thread = threading.Thread(target=self._explorer_path_cacher_loop, daemon=True)
        self.cacher_thread.start()
        
        # Named Pipe handle cho headless mode (giao tiếp với Clipboard Agent)
        self._pipe_handle = None
        self._pipe_lock = threading.Lock()
        
        # Không cần luồng theo dõi paste vì dùng delayed rendering thực tế
        pass

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
                    log_debug("[_handle_uppipe_client] Nhận CANCEL_TRANSFER từ Clipboard Agent.")
                    print("[Clipboard] Agent hủy truyền file (nút Hủy).")
                    self.cancel_active_transfer(remote_triggered=False)
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

                    # Không ghi thẳng vào thư mục Explorer — file dở (.exe) hiện icon lá chắn.
                    if dest_dir and os.path.isdir(dest_dir) and not _is_transfer_staging_dir(dest_dir):
                        self._paste_dest_dir = dest_dir
                        log_debug(f"[_handle_uppipe_client] paste dest (sau khi tải xong): {dest_dir}")
                        
                    if requested_files:
                        tok = int(getattr(self, "_clipboard_paste_id", 0) or 0)
                        if tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
                            print(f"[FileTransfer] Bo REQUEST_FILES paste_id={tok} (blacklist Huy).")
                            return
                        self.pending_remote_files = requested_files
                        if not self._arm_file_xfer("agent_REQUEST_FILES"):
                            return
                        threading.Thread(target=self.request_pending_files, daemon=True).start()
                    else:
                        log_debug("[_handle_uppipe_client] Không có pending_remote_files để tải.")
                        if self.app and getattr(self.app, 'is_headless', False):
                            self._send_progress_signal("CANCEL", "")
                            self._close_transfer_pipe()
                else:
                    # Metadata file do Clipboard Agent gửi lên (copy file từ phía user)
                    if raw.startswith("COPIED_FILES|"):
                        parts = raw.split("|", 1)
                        paths = json.loads(parts[1]) if len(parts) > 1 else []
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
                    if metadata and self.active_sockets:
                        pkt = json.dumps({"type": "files_copied_meta", "files": metadata}).encode('utf-8')
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
        """
        Gửi tín hiệu tiến trình qua Named Pipe đang mở hoặc tạo mới nếu chưa có.
        """
        import win32file
        import win32pipe
        
        if not hasattr(self, '_transfer_pipe') or self._transfer_pipe is None:
            try:
                log_debug("[_send_progress_signal] Đang tạo Named Pipe cho tiến trình tải file...")
                self._transfer_pipe = create_named_pipe_with_everyone_dacl()
                if self._transfer_pipe is None or self._transfer_pipe == -1:
                    self._transfer_pipe = None
                    log_debug("[_send_progress_signal] Lỗi: Không tạo được Named Pipe.")
                    return
                log_debug("[_send_progress_signal] Đang chờ Clipboard Agent kết nối...")
                
                try:
                    win32pipe.ConnectNamedPipe(self._transfer_pipe, None)
                except Exception as ce:
                    if getattr(ce, 'winerror', 0) == 535 or (len(ce.args) > 0 and ce.args[0] == 535):
                        log_debug("[_send_progress_signal] Client đã kết nối trước khi ConnectNamedPipe được gọi.")
                    else:
                        raise
                        
                log_debug("[_send_progress_signal] Clipboard Agent đã kết nối.")
            except Exception as e:
                log_debug(f"[_send_progress_signal] Lỗi tạo/kết nối Pipe: {e}")
                if getattr(self, '_transfer_pipe', None) is not None and self._transfer_pipe != -1:
                    try: win32file.CloseHandle(self._transfer_pipe)
                    except: pass
                self._transfer_pipe = None
                return
                
        if self._transfer_pipe:
            try:
                msg = f"{data_type}:{payload}\x00"
                data = msg.encode("utf-8")
                win32file.WriteFile(self._transfer_pipe, data)
            except Exception as e:
                log_debug(f"[_send_progress_signal] Lỗi ghi Pipe: {e}. Đang dọn dẹp để kết nối lại...")
                try:
                    win32pipe.DisconnectNamedPipe(self._transfer_pipe)
                    win32file.CloseHandle(self._transfer_pipe)
                except:
                    pass
                self._transfer_pipe = None

    def _close_transfer_pipe(self):
        if hasattr(self, '_transfer_pipe') and self._transfer_pipe is not None:
            try:
                import win32pipe
                import win32file
                win32file.FlushFileBuffers(self._transfer_pipe)
                win32pipe.DisconnectNamedPipe(self._transfer_pipe)
                win32file.CloseHandle(self._transfer_pipe)
                log_debug("[_close_transfer_pipe] Đã đóng Pipe tiến trình tải file.")
            except Exception as e:
                log_debug(f"[_close_transfer_pipe] Lỗi đóng Pipe: {e}")
            self._transfer_pipe = None

    def _send_to_pipe(self, data_type, payload):
        """
        Gửi dữ liệu (file hoặc text) qua Named Pipe cho Clipboard Agent.
        Format gửi: "TYPE:payload"
        """
        import win32pipe
        import win32file

        pipe_handle = None
        try:
            log_debug(f"[_send_to_pipe] Đang tạo Named Pipe để gửi {data_type}...")
            pipe_handle = create_named_pipe_with_everyone_dacl()

            if pipe_handle is None or pipe_handle == -1:
                log_debug("[_send_to_pipe] Lỗi: Không tạo được Named Pipe.")
                return

            log_debug(f"[_send_to_pipe] Đang chờ Clipboard Agent kết nối tới Pipe...")
            # Chờ Agent kết nối (blocking call)
            try:
                win32pipe.ConnectNamedPipe(pipe_handle, None)
            except Exception as ce:
                if getattr(ce, 'winerror', 0) == 535 or (len(ce.args) > 0 and ce.args[0] == 535):
                    log_debug("[_send_to_pipe] Client đã kết nối trước khi ConnectNamedPipe được gọi.")
                else:
                    raise
            log_debug(f"[_send_to_pipe] Agent đã kết nối. Đang gửi {data_type}...")

            # Gửi dữ liệu dưới dạng "TYPE:payload" encoded in UTF-8
            msg = f"{data_type}:{payload}\x00"
            data = msg.encode("utf-8")
            win32file.WriteFile(pipe_handle, data)

            log_debug(f"[_send_to_pipe] Đã gửi thành công qua Pipe: {data_type}")
            print(f"[Pipe] Đã gửi {data_type} qua Named Pipe.")

        except Exception as e:
            log_debug(f"[_send_to_pipe] Lỗi gửi qua Pipe: {e}")
            print(f"[Pipe] Lỗi gửi qua Pipe: {e}")
        finally:
            if pipe_handle is not None and pipe_handle != -1:
                try:
                    win32file.FlushFileBuffers(pipe_handle)
                    win32pipe.DisconnectNamedPipe(pipe_handle)
                    win32file.CloseHandle(pipe_handle)
                except:
                    pass

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
                    title_text, filename, total_size = args
                    existing = self.active_dialog
                    if existing:
                        try:
                            if existing.winfo_exists():
                                continue
                        except Exception:
                            pass
                        try:
                            existing.destroy()
                        except Exception:
                            pass
                        self.active_dialog = None
                    owner_hwnd = getattr(self, "pygame_hwnd", None)
                    if not owner_hwnd and self.app:
                        try:
                            owner_hwnd = int(self.app.winfo_id())
                        except Exception:
                            owner_hwnd = None
                    self.active_dialog = ProgressDialog(
                        self.app, title_text, filename, total_size,
                        on_cancel=lambda: self.cancel_active_transfer(remote_triggered=False),
                        owner_hwnd=owner_hwnd
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

    def show_dialog(self, title_text, filename, total_size):
        self.gui_queue.put(("create", (title_text, filename, total_size)))

    def update_dialog(self, sent_bytes):
        import time
        current_time = time.time()
        if not hasattr(self, '_last_update_time'):
            self._last_update_time = 0
            self._last_update_bytes = 0
        
        # Chỉ cập nhật tối đa 20 lần / giây (50ms) hoặc khi đã tải xong
        if (current_time - self._last_update_time >= 0.05) or (hasattr(self, 'batch_total_size') and sent_bytes >= self.batch_total_size):
            self.gui_queue.put(("update", sent_bytes))
            self._last_update_time = current_time
            self._last_update_bytes = sent_bytes

    def close_dialog(self):
        self._recv_dialog_open = False
        self.gui_queue.put(("destroy", None))

    def _note_cancelled_paste_id(self, tok):
        try:
            tok = int(tok or 0)
        except Exception:
            return
        ids = getattr(self, "_cancelled_paste_ids", None)
        if ids is None:
            self._cancelled_paste_ids = set()
            ids = self._cancelled_paste_ids
        ids.add(tok)
        if len(ids) > 64:
            self._cancelled_paste_ids = set(sorted(ids)[-32:])

    def _arm_file_xfer(self, reason=""):
        """Cho phép gửi/nhận file — chỉ gọi khi Paste thật hoặc peer request_files mới."""
        tok = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        if tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
            print(f"[FileTransfer] Khong arm — paste_id={tok} nam trong blacklist Huy.")
            return False
        self._send_xfer_id = getattr(self, "_send_xfer_id", 0) + 1
        self._allow_file_xfer = True
        self._send_cancelled = False
        self._receive_cancelled = False
        try:
            self._send_abort_event.clear()
        except Exception:
            pass
        self._send_loop_gen = getattr(self, "_cancel_gen", 0)
        self._suppress_request_files_until = 0.0
        print(f"[FileTransfer] Arm xfer ({reason}) id={self._send_xfer_id} paste_id={tok}")
        return True

    def _disarm_file_xfer(self, reason=""):
        """Hủy: tắt cờ, vòng gửi phải dừng ngay."""
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
        self._send_xfer_id = getattr(self, "_send_xfer_id", 0) + 1
        self._xfer_cancel_token = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        self._note_cancelled_paste_id(self._xfer_cancel_token)
        print(f"[FileTransfer] Disarm xfer ({reason}) token={self._xfer_cancel_token} id={self._send_xfer_id}")

    def _cleanup_partial_incoming(self):
        """Đóng handle và xóa file dở (cancel / drain stale) — tránh .exe nửa file + lá chắn UAC."""
        for filename, transfer in list(getattr(self, "incoming_transfers", {}) or {}).items():
            if transfer.get("handle"):
                try:
                    transfer["handle"].close()
                except Exception:
                    pass
            path = transfer.get("path")
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"[FileTransfer] Đã xóa file dở dang: {path}")
                except Exception as e:
                    print(f"[FileTransfer] Không thể xóa file dở dang: {e}")
        self.incoming_transfers = {}

        try:
            import shutil
            bases = [
                getattr(self, "target_save_dir", None),
                getattr(self, "_paste_dest_dir", None),
                HEADLESS_TRANSFER_DIR,
                os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"),
            ]
            seen = set()
            for base in bases:
                if not base:
                    continue
                try:
                    key = os.path.normcase(os.path.abspath(base))
                except Exception:
                    continue
                if key in seen or not os.path.isdir(base):
                    continue
                seen.add(key)
                for name in os.listdir(base):
                    if not name.startswith(".rdxfer_"):
                        continue
                    shutil.rmtree(os.path.join(base, name), ignore_errors=True)
        except Exception:
            pass

        if hasattr(self, "batch_paths") and self.batch_paths:
            import shutil
            for p in list(self.batch_paths):
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=True)
                    elif os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
            self.batch_paths = []

        saved = list(getattr(self, "pending_remote_files", None) or getattr(self, "_reoffer_files", None) or [])
        dests = [
            getattr(self, "target_save_dir", None),
            getattr(self, "_paste_dest_dir", None),
            getattr(self, "cached_explorer_path", None),
        ]
        for dest in dests:
            if not dest or not os.path.isdir(dest):
                continue
            for f in saved:
                name = f.get("name")
                if not name:
                    continue
                p = os.path.join(dest, name)
                try:
                    expected = int(f.get("size") or 0)
                    if os.path.isfile(p) and expected > 0 and os.path.getsize(p) < expected:
                        os.remove(p)
                        print(f"[FileTransfer] Đã xóa file chưa đủ: {p}")
                except Exception:
                    pass

    def _send_file_msg(self, sock, data_bytes, my_id):
        """Gửi gói file; timeout 2s. Timeout + Hủy → False; timeout do lag → retry cùng gói."""
        if not getattr(self, "_allow_file_xfer", False) or self._send_should_stop(my_id):
            return False
        old_to = None
        try:
            try:
                old_to = sock.gettimeout()
            except Exception:
                old_to = None
            sock.settimeout(2.0)
            for _ in range(3):
                if not getattr(self, "_allow_file_xfer", False) or self._send_should_stop(my_id):
                    return False
                try:
                    send_msg(sock, data_bytes)
                    break
                except socket.timeout:
                    if not getattr(self, "_allow_file_xfer", False) or self._send_should_stop(my_id):
                        return False
                    continue
                except Exception as e:
                    print(f"[FileTransfer] send_msg loi: {e}")
                    return False
            else:
                return False
        finally:
            try:
                sock.settimeout(old_to)
            except Exception:
                pass
        return not (not getattr(self, "_allow_file_xfer", False) or self._send_should_stop(my_id))

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
            send_msg(sock, json.dumps({
                "type": "cancel_ack",
                "paste_id": int(getattr(self, "_clipboard_paste_id", 0) or 0),
            }).encode("utf-8"))
        except Exception:
            pass

    def cancel_active_transfer(self, remote_triggered=False):
        # Tắt cờ gửi ngay — vòng _process_send_requests / send_msg phải dừng.
        cur = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        self._note_cancelled_paste_id(cur)
        self._clipboard_paste_id = cur + 1
        self._disarm_file_xfer("Huy")
        self._maybe_send_cancel_ack()
        self._suppress_request_files_until = time.time() + 8.0
        self._suppress_render_until = max(getattr(self, "_suppress_render_until", 0), time.time() + 1.5)
        self._xfer_cancel_at = time.time()
        self.last_ctrl_v_time = 0.0
        self._ctrl_v_held = False
        print("[FileTransfer] Huy: allow_file_xfer=False, chan request_files/gui file.")
        if getattr(self, "_recv_xfer_id", None) is not None:
            self._aborted_xfer_ids.add(self._recv_xfer_id)
            if len(self._aborted_xfer_ids) > 32:
                self._aborted_xfer_ids = set(list(self._aborted_xfer_ids)[-16:])
        self._recv_xfer_id = None
        
        try:
            if hasattr(self, 'batch_display_name'):
                log_activity(_("Truyền file: ") + str(self.batch_display_name) + _(" - Thất bại"))
        except: pass

        # Báo viewer dừng NGAY — không return sớm trước bước này.
        if not remote_triggered:
            pkt = json.dumps({"type": "cancel_transfer"}).encode("utf-8")
            socks = set()
            if getattr(self, "sock", None):
                socks.add(self.sock)
            try:
                socks.update(self.active_sockets)
            except Exception:
                pass
            for conn in list(socks):
                try:
                    send_msg(conn, pkt)
                except Exception as e:
                    print(f"[FileTransfer] Lỗi gửi tín hiệu hủy: {e}")
        if self.app and getattr(self.app, 'is_headless', False):
            try:
                self._send_progress_signal("CANCEL", "")
                self._close_transfer_pipe()
            except Exception:
                pass
        
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
        if is_own_clipboard_write():
            return
        
        # Nếu đang ở Client Mode, kiểm tra xem cửa sổ hiện tại có phải là Viewer không
        # Nếu không phải Viewer (người dùng đang xài máy thật) -> giữ lại, không gửi cho Host!
        if getattr(self, 'pygame_hwnd', None) and not force_sync:
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            fg_hwnd = user32.GetForegroundWindow()
            if fg_hwnd != self.pygame_hwnd:
                log_debug("[on_clipboard_changed] Bỏ qua vì đang thao tác ngoài cửa sổ Host Viewer (Giữ clipboard cho máy thật).")
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

    def _process_clipboard_change_debounced(self, provided_files=None, force=False):
        if getattr(self, '_is_processing_clipboard', False) and not force:
            return
        self._is_processing_clipboard = True
        try:
            self._process_clipboard_change(provided_files, force=force)
        finally:
            self._is_processing_clipboard = False

    def _process_clipboard_change(self, provided_files=None, force=False):
        try:
            time.sleep(0.05) # Chờ xíu để Windows thả file lock (giảm delay)
            
            owner_hwnd = getattr(self, 'cached_app_hwnd', None)
            if provided_files is not None:
                current_files = provided_files
            elif self.transfer_in_progress:
                current_files = []
            else:
                current_files = get_clipboard_files(owner_hwnd)
                # Explorer đôi khi vẫn giữ clipboard lúc WM_CLIPBOARDUPDATE; thử lại trước khi bỏ qua
                if not current_files:
                    for _ in range(4):
                        time.sleep(0.1)
                        current_files = get_clipboard_files(owner_hwnd)
                        if current_files:
                            break
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
                    last_files_lower = [os.path.abspath(f).lower() for f in getattr(self, 'last_current_files', [])]
                    seq = get_clipboard_sequence_number()
                    if not force:
                        last_seq = getattr(self, "_last_sent_file_seq", None)
                        if seq and last_seq and seq == last_seq:
                            log_debug("[_process_clipboard_change] Bỏ qua: cùng clipboard sequence (không phải lần Copy mới).")
                            return
                        if current_files_lower == last_files_lower and (time.time() - getattr(self, 'last_files_time', 0)) < 0.4:
                            log_debug("[_process_clipboard_change] Bỏ qua: debounce copy trùng.")
                            return
                    self.last_current_files = current_files
                    self.last_files_time = time.time()
                    self._last_sent_file_seq = seq
                
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
                    if self.active_sockets:
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

    def setup_delayed_rendering(self):
        log_debug(f"[setup_delayed_rendering] Bắt đầu. self.listener={self.listener}")
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
            
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        opened = False
        log_debug(f"[_execute_setup_delayed_rendering] Đang cố gắng OpenClipboard với HWND: {self.listener.hwnd}")
        for _ in range(30):
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
        else:
            err = ctypes.GetLastError()
            log_debug(f"[_execute_setup_delayed_rendering] OpenClipboard THẤT BẠI. GetLastError: {err}")
            print("[Clipboard] Không thể OpenClipboard để thiết lập delayed rendering.")

    def lost_ownership(self):
        if getattr(self, 'ignore_destroy_clipboard', False):
            log_debug("[lost_ownership] Bỏ qua WM_DESTROYCLIPBOARD vì tự thực hiện EmptyClipboard.")
            return
        # self.pending_remote_files = []  # Đã gỡ bỏ để tránh mất metadata khi có race condition
        print("[Clipboard] Đã mất quyền sở hữu clipboard (người dùng copy dữ liệu khác).")

    def get_active_explorer_path(self):
        # Trả về giá trị đã được cache bởi background thread
        # để tránh lỗi RPC_E_CANTCALLOUT_ININPUTSYNCCALL khi gọi COM trong WM_RENDERFORMAT
        return getattr(self, 'cached_explorer_path', None)

    def _explorer_path_cacher_loop(self):
        while True:
            time.sleep(0.35)
            try:
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
        )
        if is_menu == "MENU":
            log_debug("[render_format] Phát hiện truy vấn menu. Cung cấp dummy HDROP và chờ user dán...")
            if _offer_probe_hdrop():
                self.dummy_h_active = True
                self.setup_delayed_rendering()
            return
        elif is_menu == "BACKGROUND":
            log_debug("[render_format] Probe/menu Explorer — dummy HDROP (không tải, không treo GetData).")
            if _offer_probe_hdrop():
                self.dummy_h_active = True
                self.setup_delayed_rendering()
            return

        cancel_at = float(getattr(self, "_xfer_cancel_at", 0) or 0)
        if cancel_at:
            new_kb = getattr(self, "last_ctrl_v_time", 0) > cancel_at + 0.15
            new_menu = (
                getattr(self, "last_lbutton_time", 0) > cancel_at + 0.15
                and getattr(self, "last_rbutton_time", 0) > cancel_at
                and getattr(self, "last_lbutton_time", 0) > getattr(self, "last_rbutton_time", 0)
            )
            if not new_kb and not new_menu:
                log_debug("[render_format] Sau Hủy chưa có thao tác Paste mới — dummy HDROP.")
                if _offer_probe_hdrop():
                    self.dummy_h_active = True
                    self.setup_delayed_rendering()
                return

        if time.time() < getattr(self, "_suppress_render_until", 0):
            log_debug("[render_format] Ngay sau Hủy — dummy HDROP, không tải ngầm.")
            if _offer_probe_hdrop():
                self.dummy_h_active = True
                self.setup_delayed_rendering()
            return
            
        if getattr(self, 'is_rendering', False):
            log_debug("[render_format] WM_RENDERFORMAT trùng — dummy HDROP (tránh treo Explorer).")
            if _offer_probe_hdrop():
                self.dummy_h_active = True
                self.setup_delayed_rendering()
            return
            
        self.is_rendering = True
        self._expect_repaste_until = 0.0
        self._rearm_delayed_after_render = False
        self._clipboard_paste_id = getattr(self, "_clipboard_paste_id", 0) + 1
        self._arm_file_xfer("gui_paste")
        self.transfer_in_progress = True # Đặt cờ truyền tải để chặn các sự kiện thay đổi clipboard trong quá trình render
        try:
            print("[Clipboard] Nhận WM_RENDERFORMAT. Đang bắt đầu kiểm tra tệp tin ghi đè...")
            log_debug("[render_format] Nhận WM_RENDERFORMAT. Đang bắt đầu kiểm tra tệp tin ghi đè...")
            
            # --- HIỂN THỊ DIALOG TIẾN TRÌNH (chỉ GUI mode) ---
            display_name = self.pending_remote_files[0].get("name") if self.pending_remote_files else "Files"
            total_size = sum(f.get("size", 0) for f in self.pending_remote_files)
            log_debug(f"[render_format] Hiển thị dialog truyền tải: {display_name}, size={total_size}")
            # render_format chỉ chạy trong GUI mode (WM_RENDERFORMAT từ ClipboardEventListener)
            # HEADLESS mode xử lý dialog riêng trong Clipboard Agent (WM_RENDERFORMAT của agent)
            if not (self.app and getattr(self.app, 'is_headless', False)):
                self._recv_dialog_open = True
                self.show_dialog("Đang tải file về...", display_name, total_size)
            
            # Giữ _receive_cancelled cho đến batch_start mới (xfer_id) để khỏi ghi chunk lần gửi cũ.
            self.batch_paths = []
            self.transfer_done_event.clear()
            
            # Lấy thư mục đích hoạt động của Explorer (nơi người dùng chuột phải Paste)
            dest_dir = self.get_active_explorer_path()
            log_debug(f"[render_format] Thư mục đích phát hiện: {dest_dir}")
            
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
                        recent = getattr(self, "_recent_direct_paste", None)
                        recent_paths = set()
                        if recent and (time.time() - recent[0] < 15.0):
                            recent_paths = recent[1]
                        for f in self.pending_remote_files:
                            filename = f.get("name")
                            dest_file_path = os.path.join(dest_dir, filename)
                    
                            if os.path.exists(dest_file_path):
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
                                        self.close_dialog()
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
                        self.close_dialog()
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
                    self.request_pending_files()
            
                    # Chờ nhận xong file (non-blocking message pump, không lồng RENDERFORMAT)
                    succeeded = False
                    start_time = time.time()
                    while time.time() - start_time < 600.0:
                        if not getattr(self, "_allow_file_xfer", False) or getattr(self, "_receive_cancelled", False):
                            break
                        if self.transfer_done_event.is_set():
                            if not getattr(self, '_receive_cancelled', False):
                                succeeded = True
                            break
                        if not _pump_messages_except_clipboard_render():
                            time.sleep(0.01)
                    
                    if succeeded and self.batch_paths:
                        meta = list(getattr(self, "_reoffer_files", None) or self.pending_remote_files or [])
                        if not _paths_match_expected_sizes(self.batch_paths, meta):
                            log_debug("[render_format] File chưa đủ dung lượng / thiếu metadata — không dán.")
                            succeeded = False
                    if succeeded and self.batch_paths:
                        print(f"[Clipboard] Tải thành công {len(self.batch_paths)} file vào: {self.target_save_dir}")
                        log_debug(f"[render_format] Tải thành công {len(self.batch_paths)} file.")
                
                        temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                        dest_now = dest_dir or getattr(self, "cached_explorer_path", None)
                        if dest_now and os.path.isdir(dest_now) and _is_transfer_staging_dir(self.target_save_dir):
                            relocated, moved_all = relocate_transfer_files(self.batch_paths, dest_now)
                            self.batch_paths = relocated
                            if moved_all:
                                self.target_save_dir = dest_now
                                log_debug(f"[render_format] Đã chuyển file từ thư mục tạm sang: {dest_now}")
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
                    
                            # Bỏ qua update_clip để tránh việc Explorer đang treo bỗng nhiên nhận được data thật và tự động chép đè lên chính nó.
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
                    else:
                        log_debug(f"[render_format] Tải file thất bại hoặc hết thời gian chờ. succeeded={succeeded}")
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
                        self.close_dialog()
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
            self.close_dialog()
            if self.app and getattr(self.app, 'is_headless', False):
                self._send_progress_signal("CANCEL", "")
                self._close_transfer_pipe()
        finally:
            self.transfer_in_progress = False
            self.is_rendering = False
            self.ignore_destroy_clipboard = False

    def _attach_xfer_id(self, payload, xfer_id):
        payload["xfer_id"] = xfer_id
        return payload

    def _xfer_packet_ok(self, packet, ptype):
        xid = packet.get("xfer_id")
        aborted = getattr(self, "_aborted_xfer_ids", None) or set()
        if xid is not None and xid in aborted:
            return False
        if ptype == "batch_start":
            return True
        if getattr(self, "_receive_cancelled", False):
            cur = getattr(self, "_recv_xfer_id", None)
            if xid is None or xid != cur:
                return False
        cur = getattr(self, "_recv_xfer_id", None)
        if xid is not None and cur is not None and xid != cur:
            return False
        return True

    def request_pending_files(self):
        if not self.pending_remote_files or not self.sock: return
        if not getattr(self, "_allow_file_xfer", False):
            print("[FileTransfer] Bo request_pending_files (allow_file_xfer=False).")
            return
        if time.time() < getattr(self, "_suppress_request_files_until", 0):
            print("[FileTransfer] Bo request_pending_files (vua Huy).")
            return
        pid = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        send_msg(self.sock, json.dumps({
            "type": "request_files",
            "files": self.pending_remote_files,
            "paste_id": pid,
        }).encode('utf-8'))

    def _send_should_stop(self, my_id):
        return (
            not getattr(self, "_allow_file_xfer", False)
            or bool(self._send_cancelled)
            or self._send_abort_event.is_set()
            or self._send_xfer_id != my_id
            or getattr(self, "_cancel_gen", 0) != getattr(self, "_send_loop_gen", 0)
        )

    def _process_send_requests(self, sock, files):
        if not getattr(self, "_allow_file_xfer", False):
            print("[FileTransfer] Bo qua gui file (allow_file_xfer=False).")
            return
        if time.time() < getattr(self, "_suppress_request_files_until", 0):
            print("[FileTransfer] Bo qua gui file (vua Huy).")
            return
        my_id = getattr(self, "_send_xfer_id", 0)
        self._send_loop_gen = getattr(self, "_cancel_gen", 0)
        if self._send_should_stop(my_id):
            print("[FileTransfer] Huy luc bat dau gui — khong gui.")
            return
        self.transfer_in_progress = True
        print(f"[FileTransfer] Bat dau gui {len(files)} file xfer_id={my_id}")
        log_debug(f"[_process_send_requests] Khởi chạy gửi {len(files)} file... xfer_id={my_id}")
        try:
            total_size = sum(f.get("size", 0) for f in files)
            display_name = str(len(files)) + _(" tệp tin") if len(files) > 1 else files[0].get("name", "Unknown")
            self.batch_display_name = display_name
            
            log_file_transfer(display_name, total_size)
            
            start_pkt = json.dumps(self._attach_xfer_id({
                "type": "batch_start",
                "count": len(files),
                "total_size": total_size,
                "display_name": display_name
            }, my_id)).encode('utf-8')
            if not self._send_file_msg(sock, start_pkt, my_id):
                print("[FileTransfer] Huy truoc/luc batch_start — dung gui.")
                return
            log_debug(f"[_process_send_requests] Đã gửi batch_start. total_size={total_size}")
            
            total_sent = 0
            batch_start_time = time.time()
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
                    "type": "file_start", "name": filename, "size": file_size
                }, my_id)).encode('utf-8')
                if not self._send_file_msg(sock, f_start_pkt, my_id):
                    log_debug(f"[_process_send_requests] Truyền tải bị hủy ngang.")
                    break
                log_debug(f"[_process_send_requests] Đã gửi file_start cho {filename}, size={file_size}")
                
                try:
                    lan = is_lan_socket(sock)
                    if lan:
                        tune_socket_for_lan_bulk(sock)
                    chunk_size = 64 * 1024
                    file_sent_bytes = 0
                    file_start_time = time.time()
                    
                    with open(filepath, "rb") as fh:
                        while True:
                            if self._send_should_stop(my_id):
                                break
                            
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
                                
                            b64 = base64.b64encode(chunk_data).decode('utf-8')
                            if not self._send_file_msg(sock, json.dumps(self._attach_xfer_id({
                                "type": "file_chunk", "name": filename, "data": b64
                            }, my_id)).encode('utf-8'), my_id):
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
                                    
                    log_debug(f"[_process_send_requests] Đã gửi xong dữ liệu cho {filename}")
                except Exception as e:
                    print(f"[FileTransfer] Lỗi khi gửi file {filename}: {e}")
                    log_debug(f"[_process_send_requests] Lỗi khi gửi file {filename}: {e}")
                    
                if not self._send_should_stop(my_id):
                    if self._send_file_msg(sock, json.dumps(self._attach_xfer_id({
                        "type": "file_end", "name": filename
                    }, my_id)).encode('utf-8'), my_id):
                        log_debug(f"[_process_send_requests] Đã gửi file_end cho {filename}")
                
            if not self._send_should_stop(my_id):
                if self._send_file_msg(sock, json.dumps(self._attach_xfer_id({"type": "batch_end"}, my_id)).encode('utf-8'), my_id):
                    log_debug(f"[_process_send_requests] Đã gửi batch_end.")
                try: log_activity(_("Truyền file: ") + str(self.batch_display_name) + " - " + str(total_size) + _(" byte - Thành công"))
                except: pass
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error processing send request: {e}")
            log_debug(f"[_process_send_requests] Lỗi tổng quát:\n{tb}")
            try:
                log_activity(_("Truyền file: ") + str(self.batch_display_name) + " - " + str(total_size) + _(" byte - Thất bại"))
            except: pass
            try:
                send_msg(sock, json.dumps({"type": "cancel_transfer"}).encode('utf-8'))
            except:
                pass
        finally:
            self.transfer_in_progress = False
            log_debug(f"[_process_send_requests] Kết thúc hàm gửi file.")

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
            stale = (
                not getattr(self, "_allow_file_xfer", False)
                or (xid is not None and xid in aborted)
                or not self._xfer_packet_ok(packet, ptype)
            )
            if stale:
                log_debug(f"[handle_received_packet] Drain/discard {ptype} xfer_id={xid} (Huy — van doc socket).")
                self._cleanup_partial_incoming()
                self._maybe_send_cancel_ack()
                return

        if ptype == "cancel_ack":
            print("[FileTransfer] Nhan cancel_ack — ngat vong gui.")
            self._disarm_file_xfer("cancel_ack")
            return

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
            self.pending_remote_files = packet.get("files", [])
            self._reoffer_files = list(self.pending_remote_files)
            self.meta_arrival_time = time.time()
            log_debug(f"[handle_received_packet] Nhận files_copied_meta. Số file: {len(self.pending_remote_files)}")
            print(f"[Clipboard] Đã nhận được files_copied_meta. Số file: {len(self.pending_remote_files)}")
            if not self.pending_remote_files: return
            
            # --- HEADLESS MODE (SYSTEM/Service): Gửi PENDING cho Clipboard Agent ---
            if self.app and getattr(self.app, 'is_headless', False):
                transfer_dir = HEADLESS_TRANSFER_DIR
                try:
                    os.makedirs(transfer_dir, exist_ok=True)
                    for item in os.listdir(transfer_dir):
                        item_path = os.path.join(transfer_dir, item)
                        if os.path.isfile(item_path):
                            try: os.remove(item_path)
                            except: pass
                except Exception as e:
                    log_debug(f"[files_copied_meta] Lỗi dọn dẹp thư mục transfer: {e}")
                self.target_save_dir = transfer_dir
                self.batch_paths = []
                self.transfer_done_event.clear()
                
                # Gửi PENDING: tới agent để nó chờ Paste và hiện dialog, thay vì tải ngay im lặng.
                total_size = sum(f.get("size", 0) for f in self.pending_remote_files)
                display_name = "Files"
                if self.pending_remote_files:
                    display_name = self.pending_remote_files[0].get("name", "Files")
                    if len(self.pending_remote_files) > 1:
                        display_name += f" and {len(self.pending_remote_files) - 1} others"
                        
                msg_dict = {
                    "display_name": display_name,
                    "total_size": total_size,
                    "files": self.pending_remote_files
                }
                import json
                msg = json.dumps(msg_dict)
                threading.Thread(target=self._send_to_pipe, args=("PENDING", msg), daemon=True).start()
                log_debug(f"[files_copied_meta] HEADLESS MODE: Đã gửi PENDING tới Agent để chờ Paste.")
                return
            
            # --- GUI MODE (User): Sử dụng delayed rendering như bình thường ---
            temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
            self.target_save_dir = temp_dir
            
            # Đăng ký delayed rendering NGAY LẬP TỨC để sáng nút Paste sớm nhất có thể
            self.setup_delayed_rendering()
            
            # Dọn dẹp thư mục tạm trong luồng nền để không block việc sáng nút Paste
            def cleanup_temp():
                try:
                    import shutil
                    os.makedirs(temp_dir, exist_ok=True)
                    for item in os.listdir(temp_dir):
                        item_path = os.path.join(temp_dir, item)
                        try:
                            if os.path.isfile(item_path) or os.path.islink(item_path):
                                os.remove(item_path)
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path, ignore_errors=True)
                        except: pass
                except Exception as e:
                    log_debug(f"[files_copied_meta] Lỗi dọn dẹp thư mục tạm: {e}")
            threading.Thread(target=cleanup_temp, daemon=True).start()
            return
            
        elif ptype == "request_files":
            if time.time() < getattr(self, "_suppress_request_files_until", 0):
                print("[FileTransfer] Bo request_files sau Huy (tranh gui ngam).")
                return
            try:
                tok = int(packet.get("paste_id") or 0)
            except Exception:
                tok = 0
            if tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
                print(f"[FileTransfer] Bo request_files paste_id={tok} (blacklist Huy).")
                return
            cancel_tok = int(getattr(self, "_xfer_cancel_token", 0) or 0)
            if not getattr(self, "_allow_file_xfer", False) and tok <= cancel_tok:
                print(f"[FileTransfer] Bo request_files sau Huy (paste_id={tok} <= token={cancel_tok}).")
                return
            if tok:
                self._clipboard_paste_id = tok
            if not self._arm_file_xfer("peer_request_files"):
                return
            files_to_send = packet.get("files", [])
            threading.Thread(target=self._process_send_requests, args=(self.sock, files_to_send), daemon=True).start()
            return
            
        elif ptype == "batch_start":
            self.batch_total_size = packet.get("total_size", 0)
            self.batch_received = 0
            self.batch_paths = []
            display_name = packet.get("display_name", "Files")
            self.batch_display_name = display_name
            
            self.transfer_in_progress = True
            xid = packet.get("xfer_id")
            if xid is not None and xid in (getattr(self, "_aborted_xfer_ids", None) or set()):
                log_debug(f"[batch_start] Bo xfer da huy {xid}")
                return
            self._receive_cancelled = False
            if xid is not None:
                self._recv_xfer_id = xid
            self.batch_received = 0
            
            os.makedirs(self.target_save_dir, exist_ok=True)
            log_file_transfer(display_name, self.batch_total_size)
            log_debug(f"[batch_start] Bắt đầu nhận batch, total_size={self.batch_total_size}, target_save_dir={self.target_save_dir}")
            # GUI mode: hiện dialog khi bắt đầu nhận (File Manager / nhận không qua paste).
            # Paste host→client đã gọi show_dialog trong render_format — không tạo dialog thứ 2.
            if not (self.app and getattr(self.app, 'is_headless', False)):
                if not getattr(self, "_recv_dialog_open", False):
                    self.show_dialog("Đang tải file về...", display_name, self.batch_total_size)
            
        elif ptype == "file_start":
            filename = packet.get("name", "")
            if not filename: return
            
            # Luôn ghi vào thư mục tạm. Không dùng target_dir từ packet nếu là thư mục Explorer
            # (file dở .exe sẽ hiện icon setup + lá chắn).
            save_dir = self.target_save_dir
            pkt_dir = packet.get("target_dir")
            if pkt_dir and _is_transfer_staging_dir(pkt_dir):
                save_dir = pkt_dir
            if not save_dir:
                save_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
            xid = packet.get("xfer_id")
            existing = self.incoming_transfers.get(filename)
            if (
                existing
                and existing.get("handle")
                and xid is not None
                and existing.get("xfer_id") == xid
            ):
                log_debug(f"[file_start] Bỏ file_start trùng (tránh cắt file) xfer_id={xid} {filename}")
                return
            save_dir = _xfer_staging_dir(save_dir, xid)
            
            target_path = os.path.join(save_dir, filename)
            log_debug(f"[file_start] Bắt đầu nhận file: {filename}, target_path={target_path}")

            try:
                dirname = os.path.dirname(target_path)
                if dirname:
                    os.makedirs(dirname, exist_ok=True)
                old = self.incoming_transfers.pop(filename, None)
                if old and old.get("handle"):
                    try:
                        old["handle"].close()
                    except Exception:
                        pass
                fh = open(target_path, "wb")
                expected = packet.get("size")
                try:
                    expected = int(expected) if expected is not None else None
                except Exception:
                    expected = None
                self.incoming_transfers[filename] = {
                    "path": target_path,
                    "handle": fh,
                    "skipped": False,
                    "pending": False,
                    "xfer_id": packet.get("xfer_id"),
                    "expected_size": expected,
                    "written": 0,
                }
                log_debug(f"[file_start] Mở thành công file mới: {target_path} expected={expected}")
            except Exception as e:
                print(f"[FileTransfer] Lỗi mở file mới {filename}: {e}")
                log_debug(f"[file_start] Lỗi mở file mới {filename}: {e}")

        elif ptype == "file_chunk":
            filename = packet.get("name", "")
            if filename in self.incoming_transfers:
                transfer = self.incoming_transfers[filename]
                xid = packet.get("xfer_id")
                if xid is not None and transfer.get("xfer_id") is not None and xid != transfer.get("xfer_id"):
                    log_debug(f"[file_chunk] Bỏ chunk xfer_id cũ cho {filename}")
                    return
                chunk_bytes = base64.b64decode(packet.get("data", ""))
                expected = transfer.get("expected_size")
                written = int(transfer.get("written") or 0)
                if expected is not None and written >= expected:
                    return
                if expected is not None and written + len(chunk_bytes) > expected:
                    chunk_bytes = chunk_bytes[: max(0, expected - written)]
                if not chunk_bytes:
                    return

                if transfer.get("handle") is not None:
                    transfer["handle"].write(chunk_bytes)
                    transfer["written"] = written + len(chunk_bytes)
                    self.batch_received += len(chunk_bytes)
                    self.update_dialog(self.batch_received)
                    if self.app and getattr(self.app, 'is_headless', False):
                        current_time = time.time()
                        if not hasattr(self, '_last_progress_time'):
                            self._last_progress_time = 0
                            self._last_progress_bytes = 0
                        if (current_time - self._last_progress_time >= 0.05) or (hasattr(self, 'batch_total_size') and self.batch_received >= self.batch_total_size):
                            self._send_progress_signal("PROGRESS", str(self.batch_received))
                            self._last_progress_time = current_time
                            self._last_progress_bytes = self.batch_received
                    
                    # Luôn gửi ACK tiến độ về cho Client để cập nhật UI mượt mà theo đúng lượng đã nhận
                    current_time_ack = time.time()
                    if not hasattr(self, '_last_upload_ack_time'):
                        self._last_upload_ack_time = 0
                    if (current_time_ack - self._last_upload_ack_time >= 0.2) or (hasattr(self, 'batch_total_size') and self.batch_received >= self.batch_total_size):
                        self._last_upload_ack_time = current_time_ack
                        if getattr(self, 'sock', None):
                            try:
                                send_msg(self.sock, json.dumps({"type": "upload_progress_ack", "received": self.batch_received}).encode('utf-8'))
                            except: pass
                
        elif ptype == "file_end":
            filename = packet.get("name", "")
            if filename in self.incoming_transfers:
                transfer = self.incoming_transfers[filename]
                xid = packet.get("xfer_id")
                if xid is not None and transfer.get("xfer_id") is not None and xid != transfer.get("xfer_id"):
                    log_debug(f"[file_end] Bỏ file_end xfer_id cũ cho {filename}")
                    return
                transfer = self.incoming_transfers.pop(filename, None)
                if transfer:
                    if transfer.get("handle") is not None:
                        try:
                            transfer["handle"].close()
                            log_debug(f"[file_end] Đóng handle file thành công cho: {filename}")
                        except Exception as e:
                            log_debug(f"[file_end] Lỗi đóng handle file {filename}: {e}")

                    path = transfer.get("path")
                    expected = transfer.get("expected_size")
                    if path and expected is not None:
                        try:
                            actual = os.path.getsize(path) if os.path.exists(path) else -1
                        except Exception:
                            actual = -1
                        if actual != expected:
                            log_debug(f"[file_end] Sai kích thước {filename}: {actual} != {expected}, xóa file.")
                            try:
                                if path and os.path.exists(path):
                                    os.remove(path)
                            except Exception:
                                pass
                            return
                    
                    xid = transfer.get("xfer_id")
                    top_level_name = filename.replace('\\', '/').split('/')[0]
                    top_level_path = os.path.join(_xfer_staging_dir(self.target_save_dir, xid), top_level_name)
                    if top_level_path not in self.batch_paths:
                        self.batch_paths.append(top_level_path)
                    log_debug(f"[file_end] Đã xử lý xong file: {filename}")
                    
                    if not self.incoming_transfers and getattr(self, 'active_batch', False) and getattr(self, 'batch_total_size', 0) > 0 and getattr(self, 'batch_received', 0) >= self.batch_total_size:
                        if hasattr(self, 'active_dialog') and self.active_dialog:
                            try:
                                if hasattr(self.active_dialog, 'safe_destroy'):
                                    self.active_dialog.safe_destroy()
                                else:
                                    self.active_dialog.destroy()
                                self.active_dialog = None
                            except: pass
                        try:
                            import core.viewer
                            if core.viewer.file_manager_callback:
                                core.viewer.file_manager_callback({"type": "trigger_local_refresh"})
                        except: pass
                
        elif ptype == "batch_end":
            if getattr(self, "_receive_cancelled", False):
                log_debug("[batch_end] Đã hủy — bỏ qua FILES.")
                self.close_dialog()
                self.transfer_done_event.set()
                if self.app and getattr(self.app, "is_headless", False):
                    self._send_progress_signal("CANCEL", "")
                    self._close_transfer_pipe()
                self.transfer_in_progress = False
                return
            self.close_dialog()
            self.transfer_done_event.set()
            try:
                import core.viewer
                if core.viewer.file_manager_callback:
                    core.viewer.file_manager_callback({"type": "trigger_local_refresh"})
            except: pass
            log_debug(f"[batch_end] Đã nhận xong toàn bộ file trong thư mục tạm.")
            try: log_activity(_("Nhận file: ") + str(self.batch_display_name) + " - " + str(self.batch_total_size) + _(" byte - Thành công"))
            except: pass
            # Gửi ACK về client xác nhận đã nhận đủ file
            try:
                if self.sock:
                    send_msg(self.sock, json.dumps({"type": "upload_batch_ack"}).encode('utf-8'))
                    log_debug("[batch_end] Đã gửi upload_batch_ack về client.")
            except Exception as ack_err:
                log_debug(f"[batch_end] Lỗi gửi upload_batch_ack: {ack_err}")
            
            # --- HEADLESS MODE: Gửi đường dẫn file qua Named Pipe cho Clipboard Agent ---
            if self.app and getattr(self.app, 'is_headless', False):
                ok_paths = list(self.batch_paths)
                meta = list(getattr(self, "_reoffer_files", None) or self.pending_remote_files or [])
                if not _paths_match_expected_sizes(ok_paths, meta):
                    log_debug("[batch_end] HEADLESS: size không khớp hoặc thiếu metadata, không gửi FILES.")
                    ok_paths = []
                if ok_paths:
                    paste_id = int(getattr(self, "_clipboard_paste_id", 0) or 0)
                    files_str = str(paste_id) + "|" + "|".join(ok_paths)
                    self._send_progress_signal("FILES", files_str)
                    log_debug(f"[batch_end] HEADLESS: Đã gửi FILES tới agent: {files_str[:100]}")
                    
                    if hasattr(self, 'lock'):
                        with self.lock:
                            self.last_current_files = [os.path.abspath(p) for p in ok_paths if os.path.exists(p)]
                            self.last_files_time = time.time()
                else:
                    self._send_progress_signal("CANCEL", "")
                    log_debug("[batch_end] HEADLESS: batch_paths trống hoặc chưa đủ size, đã gửi CANCEL tới agent.")
                self._close_transfer_pipe()
                
            # self.pending_remote_files = [] # Bỏ clear để tránh race condition ở lần copy N+1
            self.transfer_in_progress = False



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
                        time.sleep(0.5)

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
                                            gui_queue.put(("pending", info))
                                        except Exception as e:
                                            agent_print(f"[ClipboardAgent] Lỗi parse PENDING JSON: {e}")
                                    elif msg.startswith("PROGRESS:"):
                                        try:
                                            val = int(msg[9:])
                                            gui_queue.put(("progress", val))
                                        except:
                                            pass
                                    elif msg.startswith("CANCEL:"):
                                        gui_queue.put(("pipe_cancel", None))
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
            time.sleep(0.1)

    # Khởi tạo Tkinter GUI
    root = tk.Tk()
    root.attributes('-alpha', 0.0) # Tránh nháy cửa sổ
    root.withdraw()
    
    active_dialog = None

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
    _files_ready_event = threading.Event()  # set khi host gửi FILES: xong
    _files_ready_paths = []        # các đưỜng dẫn file đã download
    _ignore_destroy = False        # tránh phản ứng WM_DESTROYCLIPBOARD do chính mình gây ra
    _is_rendering = False          # chống race condition WM_RENDERFORMAT
    
    _agent_last_lbutton_time = 0.0
    _agent_last_rbutton_time = 0.0
    _agent_last_ctrl_v_time = 0.0
    _agent_meta_arrival_time = 0.0
    _agent_dummy_h_active = False
    _agent_cached_explorer_path = None
    _agent_suppress_render_until = 0.0
    _agent_expect_repaste_until = 0.0
    _agent_last_copied_seq = None
    _agent_last_ctrl_c_time = 0.0
    _agent_paste_id = 0
    _agent_accept_files = False
    _agent_allow_xfer = False
    _agent_xfer_cancel_at = 0.0
    _agent_ctrl_v_held = False
    _agent_shift_ins_held = False

    def _agent_emit_copied_files(force=False):
        nonlocal _agent_last_copied_seq
        try:
            if _is_rendering or (not force and is_own_clipboard_write()):
                return
            files = get_clipboard_files()
            if not files:
                return
            seq = get_clipboard_sequence_number()
            if not force and seq and seq == _agent_last_copied_seq:
                return
            _agent_last_copied_seq = seq
            import win32pipe, win32file, json
            pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
            win32pipe.WaitNamedPipe(pipe_name, 5000)
            pipe_handle = win32file.CreateFile(pipe_name, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
            msg = "COPIED_FILES|" + json.dumps(files)
            win32file.WriteFile(pipe_handle, msg.encode("utf-8"))
            win32file.CloseHandle(pipe_handle)
            agent_print(f"[ClipboardAgent] Đã gửi {len(files)} COPIED_FILES cho Service (force={force}).")
        except Exception as e:
            agent_print(f"Failed to send COPIED_FILES: {e}")

    def _agent_schedule_rearm(delay_s=0.45):
        nonlocal _agent_suppress_render_until
        _agent_suppress_render_until = max(_agent_suppress_render_until, time.time() + delay_s)
        def _go():
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
                found = query_explorer_folder_path()
                if found:
                    _agent_cached_explorer_path = found
            except Exception:
                pass
            time.sleep(0.35)

    threading.Thread(target=_agent_explorer_path_cacher, daemon=True, name="AgentExplorerPath").start()

    def _agent_mouse_poll_loop():
        nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_ctrl_v_time, _agent_dummy_h_active
        nonlocal _agent_last_ctrl_c_time, _agent_last_copied_seq, _agent_ctrl_v_held, _agent_shift_ins_held
        user32 = ctypes.windll.user32
        while True:
            try:
                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    _agent_last_lbutton_time = time.time()
                    if _agent_dummy_h_active and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    _agent_last_rbutton_time = time.time()
                    if _agent_dummy_h_active and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if user32.GetAsyncKeyState(0x0D) & 0x8000: # Enter
                    if _agent_dummy_h_active and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if user32.GetAsyncKeyState(0x1B) & 0x8000: # Esc
                    if _agent_dummy_h_active and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):
                    if not _agent_ctrl_v_held:
                        _agent_last_ctrl_v_time = time.time()
                    _agent_ctrl_v_held = True
                    if _agent_dummy_h_active and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                else:
                    _agent_ctrl_v_held = False
                if (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000):
                    if not _agent_shift_ins_held:
                        _agent_last_ctrl_v_time = time.time()
                    _agent_shift_ins_held = True
                    if _agent_dummy_h_active and _agent_hwnd:
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

    def _send_cancel_to_host():
        """Báo worker dừng gửi/nhận. Event Global dễ fail (SYSTEM vs Medium IL)."""
        import win32file
        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
        sent_pipe = False
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
                win32file.WriteFile(pipe_handle, b"CANCEL_TRANSFER")
                win32file.CloseHandle(pipe_handle)
                sent_pipe = True
                agent_print("[ClipboardAgent] Đã gửi CANCEL_TRANSFER tới host (UpPipe).")
                break
            except Exception as e:
                if attempt == 7:
                    agent_print(f"[ClipboardAgent] Lỗi gửi CANCEL_TRANSFER qua pipe: {e}")
                time.sleep(0.08)
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

    def _send_request_files_to_host(files_to_request=None, dest_dir=None, paste_id=0):
        """Gửi chuỗi REQUEST_FILES cho host qua UpPipe."""
        if not _agent_allow_xfer:
            agent_print("[ClipboardAgent] Bo REQUEST_FILES (allow_xfer=False / da Huy).")
            return
        import win32file, json
        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
        try:
            import win32pipe
            try:
                win32pipe.WaitNamedPipe(pipe_name, 5000)
            except Exception as e:
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
            agent_print("[ClipboardAgent] Đã gửi REQUEST_FILES tới host.")
        except Exception as e:
            agent_print(f"[ClipboardAgent] Lỗi gửi REQUEST_FILES: {e}")

    def _execute_agent_delayed_rendering(hwnd):
        """Chạy trong WndProc thread: mở clipboard, đăng ký deferred CF_HDROP."""
        nonlocal _ignore_destroy
        if not _pending_info:
            agent_print("[ClipboardAgent] Không có pending_info, bỏ qua setup delayed rendering.")
            return
            
        try:
            _ignore_destroy = True
            user32 = ctypes.windll.user32
            opened = False
            for _ in range(30):
                if user32.OpenClipboard(hwnd):
                    opened = True
                    break
                time.sleep(0.05)
            if opened:
                user32.EmptyClipboard()
                
                # Thiết lập loại trừ Clipboard History và Cloud Clipboard
                setup_clipboard_exclusions()
                
                # SetClipboardData với NULL = hứa cung cấp dữ liệu khi được yêu cầu
                res = fn_SetClipboardData(CF_HDROP, None)
                user32.CloseClipboard()
                mark_own_clipboard_write()
                agent_print(f"[ClipboardAgent] Đã setup delayed rendering CF_HDROP. res={res}")
            else:
                err = ctypes.GetLastError()
                agent_print(f"[ClipboardAgent] OpenClipboard thất bại khi setup (10 lần). Err={err}")
        except Exception as e:
            agent_print(f"[ClipboardAgent] Lỗi setup delayed rendering: {e}")
        finally:
            _ignore_destroy = False

    def _agent_wndproc(hwnd, msg, wparam, lparam):
        """WndProc cho hidden window của agent. Xử lý WM_RENDERFORMAT (Paste xảy ra)."""
        nonlocal _is_rendering, _files_ready_paths, _files_ready_event, _ignore_destroy, _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_dummy_h_active, _agent_cached_explorer_path, _agent_suppress_render_until, _agent_expect_repaste_until, _agent_paste_id, _agent_accept_files, _agent_allow_xfer, _agent_xfer_cancel_at

        if msg == WM_USER_SETUP_DELAYED:
            if _pending_info:
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
            def _send_clipboard():
                import time
                time.sleep(0.15)
                if _is_rendering or is_own_clipboard_write():
                    return
                files = get_clipboard_files()
                if files:
                    _agent_emit_copied_files(force=False)
                    return
                text = get_clipboard_text()
                if text:
                    if _pending_info:
                        _pending_info.clear()
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
            if _is_rendering:
                agent_print("[ClipboardAgent] WM_RENDERFORMAT trùng — dummy HDROP.")
                if _offer_probe_hdrop():
                    _agent_dummy_h_active = True
                    ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                return 0
            if time.time() < _agent_suppress_render_until:
                agent_print("[ClipboardAgent] Ngay sau Hủy — dummy HDROP, không tải ngầm.")
                if _offer_probe_hdrop():
                    _agent_dummy_h_active = True
                    ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                return 0
                
            # Kiểm tra nếu là truy vấn từ menu chuột phải (context menu) thì tránh tải file thực tế lúc này
            is_menu = check_is_menu_query(
                _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_ctrl_v_time,
                expect_repaste=time.time() < _agent_expect_repaste_until,
            )
            if is_menu == "MENU":
                agent_print("[ClipboardAgent] Phát hiện truy vấn menu. Dummy HDROP, chờ user dán...")
                if _offer_probe_hdrop():
                    _agent_dummy_h_active = True
                    ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                return 0
            elif is_menu == "BACKGROUND":
                agent_print("[ClipboardAgent] Probe Explorer — dummy HDROP (không tải, không treo menu).")
                if _offer_probe_hdrop():
                    _agent_dummy_h_active = True
                    ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                return 0

            if _agent_xfer_cancel_at:
                new_kb = _agent_last_ctrl_v_time > _agent_xfer_cancel_at + 0.15
                new_menu = (
                    _agent_last_lbutton_time > _agent_xfer_cancel_at + 0.15
                    and _agent_last_rbutton_time > _agent_xfer_cancel_at
                    and _agent_last_lbutton_time > _agent_last_rbutton_time
                )
                if not new_kb and not new_menu:
                    agent_print("[ClipboardAgent] Sau Hủy chưa có Paste mới — dummy, không mở dialog.")
                    if _offer_probe_hdrop():
                        _agent_dummy_h_active = True
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                    return 0

            _is_rendering = True
            _agent_expect_repaste_until = 0.0
            _agent_paste_id += 1
            _agent_accept_files = True
            _agent_allow_xfer = True
            agent_print("[ClipboardAgent] Nhận WM_RENDERFORMAT → người dùng đã Paste. Bắt đầu tải file...")
            try:
                # Hiển thị dialog qua gui_queue ngay lập tức
                info = _pending_info.copy()
                gui_queue.put(("start", (info.get("display_name", "Files"), info.get("total_size", 0))))

                # Yêu cầu host bắt đầu gửi file
                _files_ready_event.clear()
                _files_ready_paths.clear()
                _send_request_files_to_host(
                    info.get("files", []), _agent_cached_explorer_path, _agent_paste_id
                )

                deadline = time.time() + 600.0
                while time.time() < deadline:
                    if not _agent_allow_xfer:
                        agent_print("[ClipboardAgent] Huy — dung cho file.")
                        break
                    if _files_ready_event.is_set():
                        break
                    if not _pump_messages_except_clipboard_render():
                        time.sleep(0.01)

                if _files_ready_event.is_set() and _files_ready_paths:
                    dest_dir = _agent_cached_explorer_path
                    final_paths = list(_files_ready_paths)
                    meta_files = (info.get("files") if info else None) or _pending_info.get("files") or []
                    if not _paths_match_expected_sizes(final_paths, meta_files):
                        agent_print("[ClipboardAgent] File chưa đủ dung lượng / thiếu metadata — không dán.")
                        final_paths = []
                    if final_paths:
                        moved_all = False
                        if dest_dir:
                            final_paths, moved_all = relocate_transfer_files(final_paths, dest_dir)
                            agent_print(f"[ClipboardAgent] Paste dest={dest_dir} moved_all={moved_all} n={len(final_paths)}")
                        if moved_all:
                            empty_hdrop = create_hdrop_data([])
                            if empty_hdrop:
                                _ignore_destroy = True
                                try:
                                    res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                                    if not res:
                                        fn_GlobalFree(empty_hdrop)
                                    agent_print(f"[ClipboardAgent] Đã chuyển file tới đích, hủy paste Explorer. res={res}")
                                finally:
                                    _ignore_destroy = False
                        else:
                            hGlobal = create_hdrop_data(final_paths)
                            if hGlobal:
                                _ignore_destroy = True
                                try:
                                    res = fn_SetClipboardData(CF_HDROP, hGlobal)
                                    if not res:
                                        fn_GlobalFree(hGlobal)
                                    agent_print(f"[ClipboardAgent] Đã nạp HDROP vào clipboard. res={res}")
                                except Exception as e:
                                    agent_print(f"[ClipboardAgent] Lỗi SetClipboardData: {e}")
                                    fn_GlobalFree(hGlobal)
                                finally:
                                    _ignore_destroy = False
                        gui_queue.put(("end", None))
                        agent_print("[ClipboardAgent] Đã nạp data thực thành công.")
                        _pending_info.clear()
                    else:
                        _files_ready_paths.clear()
                if not (_files_ready_event.is_set() and _files_ready_paths):
                    agent_print("[ClipboardAgent] Hết thời gian chờ file hoặc bị hủy — HDROP rỗng, rồi delayed lại.")
                    empty_hdrop = create_hdrop_data([])
                    if empty_hdrop:
                        _ignore_destroy = True
                        try:
                            res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                            if not res:
                                fn_GlobalFree(empty_hdrop)
                            agent_print(f"[ClipboardAgent] HDROP rỗng sau hủy. res={res}")
                        finally:
                            _ignore_destroy = False
                    if _pending_info:
                        _agent_schedule_rearm(0.45)
                    gui_queue.put(("cancel", None))
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lỗi xử lý WM_RENDERFORMAT: {e}")
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
                gui_queue.put(("cancel", None))
            finally:
                _is_rendering = False
                _agent_accept_files = False
                _agent_allow_xfer = False
                _files_ready_event.clear()
                _files_ready_paths.clear()
            return 0

        if msg == WM_DESTROYCLIPBOARD and not _ignore_destroy:
            # Clipboard bị xóa bởi app khác → hủy trạng thái pending
            if _pending_info:
                agent_print("[ClipboardAgent] WM_DESTROYCLIPBOARD → hủy pending.")
                _pending_info.clear()
                _files_ready_event.set()  # unlock nếu đang chờ
                _files_ready_paths.clear()
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

    def trigger_cancel():
        """Dừng tải hiện tại nhưng giữ PENDING để user Paste lại."""
        nonlocal _agent_expect_repaste_until, _agent_accept_files, _agent_paste_id, _agent_allow_xfer
        nonlocal _agent_xfer_cancel_at, _agent_suppress_render_until, _agent_last_ctrl_v_time, _agent_ctrl_v_held
        _agent_allow_xfer = False
        _agent_accept_files = False
        _agent_paste_id += 1
        _files_ready_paths.clear()
        _files_ready_event.set()
        _agent_xfer_cancel_at = time.time()
        _agent_suppress_render_until = max(_agent_suppress_render_until, time.time() + 1.5)
        _agent_last_ctrl_v_time = 0.0
        _agent_ctrl_v_held = False
        _agent_expect_repaste_until = time.time() + 60.0
        # Không OpenClipboard/EmptyClipboard từ luồng dialog (Explorer đang GetData).
        # PostMessage → SetClipboardData HDROP rỗng trên thread cửa sổ clipboard.
        if _is_rendering and _agent_hwnd:
            try:
                ctypes.windll.user32.PostMessageW(
                    ctypes.c_void_p(_agent_hwnd), WM_USER_UNBLOCK_PASTE, 0, 0
                )
            except Exception:
                pass
        agent_print("[ClipboardAgent] Đã hủy tải; allow_xfer=False.")

    def trigger_cancel_win32():
        """Nút Hủy trong dialog → host dừng gửi/nhận và xóa file tạm."""
        _send_cancel_to_host()
        trigger_cancel()

    def poll_gui_queue():
        nonlocal active_dialog, _agent_meta_arrival_time, _agent_allow_xfer, _agent_suppress_render_until
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
                    _pending_info.update(info)
                    display_name = info.get("display_name", "Files")
                    total_size = info.get("total_size", 0)
                    _files_ready_event.clear()
                    _files_ready_paths.clear()
                    _agent_meta_arrival_time = time.time()
                    agent_print(f"[ClipboardAgent] Nhận PENDING: '{display_name}' ({total_size} bytes). Đang setup delayed rendering...")
                    if _agent_hwnd:
                        ctypes.windll.user32.PostMessageW(
                            ctypes.c_void_p(_agent_hwnd),
                            WM_USER_SETUP_DELAYED, 0, 0
                        )
                    else:
                        agent_print("[ClipboardAgent] HWND chưa sẵn sàng, bỏ qua PENDING.")
                elif action == "pipe_cancel":
                    agent_print("[ClipboardAgent] Nhận tín hiệu CANCEL từ Pipe. Đang hủy...")
                    trigger_cancel()
                elif action == "files_ready":
                    paste_tok, paths = _parse_files_pipe_payload(val)
                    if not _agent_accept_files:
                        agent_print("[ClipboardAgent] Bỏ FILES trễ (đã hủy / không đang paste).")
                        continue
                    if paste_tok is not None and paste_tok != _agent_paste_id:
                        agent_print(
                            f"[ClipboardAgent] Bỏ FILES paste_id={paste_tok} (hiện {_agent_paste_id})."
                        )
                        continue
                    _files_ready_paths.clear()
                    _files_ready_paths.extend(paths)
                    _files_ready_event.set()
                    agent_print(f"[ClipboardAgent] files_ready: {len(paths)} file đã sẵn sàng.")
                elif action == "start":
                    if (not _agent_allow_xfer) or (time.time() < _agent_suppress_render_until):
                        agent_print("[ClipboardAgent] Bo dialog start (sau Huy / chua Paste moi).")
                        continue
                    display_name, total_size = val
                    if active_dialog:
                        try: active_dialog.destroy()
                        except: pass
                    active_dialog = ProgressDialog(
                        root, _("Đang tải file về..."), display_name, total_size,
                        on_cancel=trigger_cancel_win32
                    )
                elif action == "progress":
                    if active_dialog:
                        try: active_dialog.update_progress(val)
                        except: pass
                elif action == "end":
                    if active_dialog:
                        def _close():
                            nonlocal active_dialog
                            if active_dialog:
                                try: active_dialog.destroy()
                                except: pass
                                active_dialog = None
                        root.after(500, _close)
                elif action == "cancel":
                    if active_dialog:
                        try: active_dialog.destroy()
                        except: pass
                        active_dialog = None
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
