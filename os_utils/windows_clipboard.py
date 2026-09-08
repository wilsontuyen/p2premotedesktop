last_clipboard_set_time = 0.0
import os
import sys
import time
import json
import queue
import threading
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
                    self.manager.last_ctrl_v_time = time.time()
            if (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000):
                if self.manager:
                    self.manager.last_ctrl_v_time = time.time()
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
            
            self.hwnd = user32.CreateWindowExW(0, wndclass.lpszClassName, "HiddenWindow", 0, 0, 0, 0, 0, ctypes.c_void_p(HWND_MESSAGE), None, wndclass.hInstance, None)
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


def check_is_menu_query(last_lbutton, last_rbutton, meta_arrival_time, last_ctrl_v=0.0):
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
    except Exception as e:
        pass
        
    t_now = time.time()
    time_since_lbutton = t_now - last_lbutton
    time_since_rbutton = t_now - last_rbutton
    meta_age = t_now - meta_arrival_time
    
    # --- 1. KIỂM TRA THAO TÁC PASTE RÕ RÀNG (Ưu tiên cao nhất) ---
    # Phím tắt Ctrl+V hoặc Shift+Insert hoặc phím Enter
    is_ctrl_v = (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000)
    is_shift_ins = (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000)
    is_enter = (user32.GetAsyncKeyState(0x0D) & 0x8000)
    if is_ctrl_v or is_shift_ins or is_enter or (t_now - last_ctrl_v < 2.0):
        log_debug(f"[check_is_menu_query] Tra ve False: Phim dan/lenh duoc nhan")
        return False

    # Chuột trái nhấp vào "Paste" trong Context Menu (phải xảy ra trong vòng 5 giây sau khi nhấp chuột phải)
    if time_since_lbutton < 1.5 and (last_lbutton > last_rbutton) and (last_lbutton - last_rbutton < 5.0) and (last_lbutton >= meta_arrival_time):
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

    # 6. Fallback: coi là Paste thật. Không được mặc định BACKGROUND —
    # user thường dán ngay sau khi nhận metadata; bỏ qua WM_RENDERFORMAT
    # lúc đó làm copy/paste lúc được lúc không.
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
        self._send_cancelled = False
        self._receive_cancelled = False
        self.overwrite_all = False
        
        self.cached_explorer_path = None
        self.dummy_h_active = False
        self._recv_dialog_open = False
        self._reoffer_files = None
        self._gui_poll_gen = 0
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
        import win32pipe, win32file, win32security
        import ntsecuritycon as con
        import time
        while True:
            try:
                sd = win32security.SECURITY_DESCRIPTOR()
                sd.Initialize()
                dacl = win32security.ACL()
                dacl.Initialize()
                everyone_sid = win32security.CreateWellKnownSid(win32security.WinWorldSid)
                dacl.AddAccessAllowedAce(win32security.ACL_REVISION, con.GENERIC_READ | con.GENERIC_WRITE, everyone_sid)
                sd.SetSecurityDescriptorDacl(1, dacl, 0)
                sa = win32security.SECURITY_ATTRIBUTES()
                sa.SECURITY_DESCRIPTOR = sd
                
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
            hr, data = win32file.ReadFile(pipe_handle, 65536)
            if hr == 0 and data:
                raw = data.decode('utf-8').strip()
                # Clipboard Agent gửi REQUEST_FILES khi người dùng thực hiện Paste
                if raw.startswith("REQUEST_FILES"):
                    log_debug("[_handle_uppipe_client] Nhận REQUEST_FILES từ Clipboard Agent. Bắt đầu tải file...")
                    print("[Clipboard] Clipboard Agent yêu cầu tải file (người dùng đã Paste).")
                    
                    parts = raw.split("|", 1)
                    requested_files = []
                    dest_dir = None
                    if len(parts) > 1 and parts[1].strip():
                        try:
                            import json
                            payload = json.loads(parts[1])
                            if isinstance(payload, dict):
                                requested_files = payload.get("files") or []
                                dest_dir = payload.get("dest_dir") or None
                            elif isinstance(payload, list):
                                requested_files = payload
                        except Exception as e:
                            log_debug(f"[_handle_uppipe_client] Lỗi parse requested_files: {e}")
                            
                    if not requested_files:
                        requested_files = self.pending_remote_files

                    if dest_dir and os.path.isdir(dest_dir) and not _is_transfer_staging_dir(dest_dir):
                        try:
                            os.makedirs(dest_dir, exist_ok=True)
                            self.target_save_dir = dest_dir
                            log_debug(f"[_handle_uppipe_client] target_save_dir = dest Explorer: {dest_dir}")
                        except Exception as e:
                            log_debug(f"[_handle_uppipe_client] Không ghi được dest_dir {dest_dir}: {e}")
                        
                    if requested_files:
                        self.pending_remote_files = requested_files
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
            threading.Thread(target=self._cancel_listener_thread, daemon=True).start()
            threading.Thread(target=self._start_uppipe_server, daemon=True).start()

    def _cancel_listener_thread(self):
        import win32event
        import win32security
        
        sa = win32security.SECURITY_ATTRIBUTES()
        sa.bInheritHandle = 1
        sd = win32security.SECURITY_DESCRIPTOR()
        sd.Initialize()
        sd.SetSecurityDescriptorDacl(True, None, False)
        sa.SECURITY_DESCRIPTOR = sd
        
        try:
            h_event = win32event.CreateEvent(sa, False, False, "Global\\AntigravityP2P_CancelTransfer_Event")
        except Exception as e:
            log_debug(f"[_cancel_listener_thread] Lỗi tạo Event: {e}")
            return
            
        log_debug("[_cancel_listener_thread] Bắt đầu lắng nghe Global\\AntigravityP2P_CancelTransfer_Event...")
        while True:
            rc = win32event.WaitForSingleObject(h_event, win32event.INFINITE)
            if rc == win32event.WAIT_OBJECT_0:
                log_debug("[_cancel_listener_thread] Nhận tín hiệu hủy truyền tải từ Agent.")
                self.cancel_active_transfer(remote_triggered=False)

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

    def cancel_active_transfer(self, remote_triggered=False):
        # Thiết lập cờ hủy ngay lập tức để ngắt các tiến trình đang gửi/nhận
        self._receive_cancelled = True
        self._send_cancelled = True
        
        try:
            if hasattr(self, 'batch_display_name'):
                log_activity(_("Truyền file: ") + str(self.batch_display_name) + _(" - Thất bại"))
        except: pass
        
        if not getattr(self, 'transfer_in_progress', False) and not getattr(self, 'incoming_transfers', {}):
            if not getattr(self, 'pending_remote_files', []):
                return
            
        print(f"[FileTransfer] Bắt đầu dọn dẹp hủy truyền tải (remote_triggered={remote_triggered})...")
        
        # Dọn dẹp cache file và trạng thái paste
        self.pending_remote_files = []
        self.is_paste_triggered = False
        self._reoffer_files = None
        self._recv_dialog_open = False
        
        # Giải phóng delayed rendering trên clipboard bằng cách xóa sạch clipboard nếu app đang sở hữu
        try:
            user32 = ctypes.windll.user32
            owner = user32.GetClipboardOwner()
            if self.listener and self.listener.hwnd and owner == self.listener.hwnd:
                opened = False
                for _ in range(30):
                    if user32.OpenClipboard(ctypes.c_void_p(self.listener.hwnd)):
                        opened = True
                        break
                    time.sleep(0.05)
                if opened:
                    self.ignore_destroy_clipboard = True
                    try:
                        user32.EmptyClipboard()
                    finally:
                        self.ignore_destroy_clipboard = False
                    user32.CloseClipboard()
                    log_debug("[cancel_active_transfer] Đã giải phóng/xóa clipboard sở hữu bởi app.")
                else:
                    log_debug("[cancel_active_transfer] Thất bại OpenClipboard để giải phóng clipboard.")
        except Exception as e:
            log_debug(f"[cancel_active_transfer] Lỗi khi giải phóng clipboard: {e}")
        
        # 1. Báo cho remote nếu hủy từ phía local
        if not remote_triggered and self.sock:
            try:
                pkt = json.dumps({"type": "cancel_transfer"}).encode('utf-8')
                send_msg(self.sock, pkt)
            except Exception as e:
                print(f"[FileTransfer] Lỗi gửi tín hiệu hủy: {e}")
                
        # Gửi tín hiệu hủy cho agent nếu ở chế độ headless
        if self.app and getattr(self.app, 'is_headless', False):
            self._send_progress_signal("CANCEL", "")
            self._close_transfer_pipe()
                
        # 2. Tắt cờ truyền tải
        self.transfer_in_progress = False
        self._send_cancelled = True
        
        # 3. Đóng và xóa các file dở dang
        for filename, transfer in list(self.incoming_transfers.items()):
            if transfer.get("handle"):
                try:
                    transfer["handle"].close()
                except:
                    pass
            if transfer.get("path") and os.path.exists(transfer["path"]):
                try:
                    os.remove(transfer["path"])
                    print(f"[FileTransfer] Đã xóa file dở dang: {transfer['path']}")
                except Exception as e:
                    print(f"[FileTransfer] Không thể xóa file dở dang: {e}")
                    
        self.incoming_transfers.clear()
        
        # Xóa các file đã tải xong trong batch hiện tại nếu bị hủy
        if hasattr(self, 'batch_paths') and self.batch_paths:
            for p in list(self.batch_paths):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                        print(f"[FileTransfer] Đã xóa file đã hoàn thành của lô bị hủy: {p}")
                    except Exception as e:
                        print(f"[FileTransfer] Không thể xóa file đã hoàn thành: {e}")
            self.batch_paths = []
        
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
            
        # 6. Mở khóa tiến trình để tiếp tục hoạt động bình thường
        self.transfer_done_event.set()

    def on_foreground_changed(self, hwnd):
        # Hàm này được gọi khi cửa sổ đang active (foreground) thay đổi
        # Nếu chúng ta đang chạy ở mode Client (có Pygame Viewer)
        if getattr(self, 'pygame_hwnd', None) and hwnd == self.pygame_hwnd:
            log_debug("[on_foreground_changed] Cửa sổ Host Viewer vừa được kích hoạt! Kiểm tra đồng bộ Clipboard...")
            # Ném clipboard cho host nếu có thay đổi
            self.on_clipboard_changed(force_sync=True)

    def on_clipboard_changed(self, force_sync=False):
        if not ENABLE_CLIPBOARD_SYNC or self.transfer_in_progress: return
        
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
            
        global last_clipboard_set_time
        if time.time() - last_clipboard_set_time < 0.5:
            log_debug("[on_clipboard_changed] Bỏ qua vì app vừa mới set clipboard.")
            return

        with self.lock:
            if hasattr(self, '_clipboard_timer') and self._clipboard_timer:
                try:
                    self._clipboard_timer.cancel()
                except:
                    pass
            self._clipboard_timer = threading.Timer(0.2, self._process_clipboard_change_debounced)
            self._clipboard_timer.daemon = True
            self._clipboard_timer.start()

    def _process_clipboard_change_debounced(self, provided_files=None):
        if getattr(self, '_is_processing_clipboard', False):
            return
        self._is_processing_clipboard = True
        try:
            self._process_clipboard_change(provided_files)
        finally:
            self._is_processing_clipboard = False

    def _process_clipboard_change(self, provided_files=None):
        try:
            time.sleep(0.05) # Chờ xíu để Windows thả file lock (giảm delay)
            
            owner_hwnd = getattr(self, 'cached_app_hwnd', None)
            if provided_files is not None:
                current_files = provided_files
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
                    
                    if current_files_lower == last_files_lower and (time.time() - getattr(self, 'last_files_time', 0)) < 2.0:
                        return
                    self.last_current_files = current_files
                    self.last_files_time = time.time()
                
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
                if current_text is not None:
                    # Bỏ qua nếu trùng với text vừa nhận hoặc vừa gửi để tránh lặp vô tận
                    if current_text == getattr(self, 'last_received_text', '') or current_text == getattr(self, 'last_sent_text', ''):
                        return
                        
                    self.last_sent_text = current_text
                    if self.active_sockets:
                        log_debug(f"[Clipboard] Phát hiện text clipboard mới locally: {current_text[:50]}...")
                        print(f"[Clipboard] Đang gửi text clipboard sang đối tác...")
                        pkt = json.dumps({"type": "clipboard_text", "text": current_text}).encode('utf-8')
                        with self.lock:
                            sockets_to_remove = []
                            for s in list(self.active_sockets):
                                try:
                                    send_msg(s, pkt)
                                except Exception:
                                    sockets_to_remove.append(s)
                            for s in sockets_to_remove:
                                if s in self.active_sockets: self.active_sockets.remove(s)
        except Exception as e:
            print(f"[FileTransfer] Monitor Error: {e}")

    def setup_delayed_rendering(self):
        log_debug(f"[setup_delayed_rendering] Bắt đầu. self.listener={self.listener}")
        if self.listener and self.listener.hwnd:
            ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.listener.hwnd), 0x0400 + 101, 0, 0)
            log_debug("[setup_delayed_rendering] Đã PostMessageW WM_SETUP_DELAYED_RENDERING")
        else:
            log_debug("[setup_delayed_rendering] Lỗi: listener hoặc hwnd chưa sẵn sàng.")

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
        is_menu = check_is_menu_query(last_l, last_r, meta_time, last_ctrl_v)
        if is_menu == "MENU":
            log_debug("[render_format] Phát hiện truy vấn menu. Cung cấp dummy HDROP và chờ user dán...")
            dummy_h = create_hdrop_data(["C:\\RemoteDesktop_Paste_Trigger.tmp"])
            if dummy_h:
                fn_SetClipboardData(15, dummy_h)
            self.dummy_h_active = True
            return
        elif is_menu == "BACKGROUND":
            log_debug("[render_format] Phát hiện truy vấn nền (VM Tools, clipboard monitor). Bỏ qua để giữ delayed rendering.")
            return
            

            
        if getattr(self, 'is_rendering', False):
            log_debug("[render_format] Bỏ qua WM_RENDERFORMAT trùng lặp (đang render).")
            return
            
        self.is_rendering = True
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
            
            self._receive_cancelled = False
            self.batch_paths = []
            self.transfer_done_event.clear()
            
            # Lấy thư mục đích hoạt động của Explorer (nơi người dùng chuột phải Paste)
            dest_dir = self.get_active_explorer_path()
            log_debug(f"[render_format] Thư mục đích phát hiện: {dest_dir}")
            
            def background_download():
                try:
                    # Nếu có thư mục đích hợp lệ, tải file trực tiếp vào đó
                    # Nếu không, sử dụng thư mục tạm
                    if dest_dir and os.path.isdir(dest_dir):
                        self.target_save_dir = dest_dir
                        log_debug(f"[render_format] Tải file trực tiếp vào thư mục đích: {dest_dir}")
                    else:
                        temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                        os.makedirs(temp_dir, exist_ok=True)
                        self.target_save_dir = temp_dir
                        log_debug(f"[render_format] Không tìm thấy thư mục đích, sử dụng thư mục tạm: {temp_dir}")
            
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
            
                    # Chờ nhận xong file (non-blocking message pump)
                    succeeded = False
                    start_time = time.time()
                    msg = wintypes.MSG()
                    while time.time() - start_time < 600.0:
                        if self.transfer_done_event.is_set():
                            if not getattr(self, '_receive_cancelled', False):
                                succeeded = True
                            break
                        # Process window messages to keep Tkinter/hidden window responsive
                        if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1): # PM_REMOVE = 1
                            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                        else:
                            time.sleep(0.01)
                    
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
                    self.is_rendering = False
                    self.transfer_in_progress = False
                    self.ignore_destroy_clipboard = False
                    
            # Phải SetClipboardData trước khi thoát WM_RENDERFORMAT. Không được
            # spawn thread rồi return — Windows đóng clipboard ngay sau handler.
            background_download()
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

    def request_pending_files(self):
        if not self.pending_remote_files or not self.sock: return
        send_msg(self.sock, json.dumps({"type": "request_files", "files": self.pending_remote_files}).encode('utf-8'))

    def _process_send_requests(self, sock, files):
        self._send_cancelled = False
        self.transfer_in_progress = True
        log_debug(f"[_process_send_requests] Khởi chạy gửi {len(files)} file...")
        try:
            total_size = sum(f.get("size", 0) for f in files)
            display_name = str(len(files)) + _(" tệp tin") if len(files) > 1 else files[0].get("name", "Unknown")
            self.batch_display_name = display_name
            
            log_file_transfer(display_name, total_size)
            
            start_pkt = json.dumps({
                "type": "batch_start",
                "count": len(files),
                "total_size": total_size,
                "display_name": display_name
            }).encode('utf-8')
            send_msg(sock, start_pkt)
            log_debug(f"[_process_send_requests] Đã gửi batch_start. total_size={total_size}")
            
            total_sent = 0
            batch_start_time = time.time()
            for f in files:
                if self._send_cancelled:
                    log_debug(f"[_process_send_requests] Truyền tải bị hủy ngang.")
                    break
                filepath = f["path"]
                filename = f["name"]
                file_size = f["size"]
                
                log_debug(f"[_process_send_requests] Kiểm tra filepath: {filepath}")
                if not os.path.exists(filepath):
                    log_debug(f"[_process_send_requests] File không tồn tại: {filepath}")
                    continue
                    
                f_start_pkt = json.dumps({"type": "file_start", "name": filename, "size": file_size}).encode('utf-8')
                send_msg(sock, f_start_pkt)
                log_debug(f"[_process_send_requests] Đã gửi file_start cho {filename}, size={file_size}")
                
                try:
                    lan = is_lan_socket(sock)
                    if lan:
                        tune_socket_for_lan_bulk(sock)
                        # LAN: không slow-start, chunk lớn, không sleep điều tiết
                        chunk_size = 1024 * 1024
                    else:
                        chunk_size = 256 * 1024
                    file_sent_bytes = 0
                    file_start_time = time.time()
                    
                    with open(filepath, "rb") as fh:
                        while True:
                            if self._send_cancelled:
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
                            send_msg(sock, json.dumps({"type": "file_chunk", "name": filename, "data": b64}).encode('utf-8'))
                            
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
                                        if self._send_cancelled:
                                            break
                                        time.sleep(0.05)
                                    
                    log_debug(f"[_process_send_requests] Đã gửi xong dữ liệu cho {filename}")
                except Exception as e:
                    print(f"[FileTransfer] Lỗi khi gửi file {filename}: {e}")
                    log_debug(f"[_process_send_requests] Lỗi khi gửi file {filename}: {e}")
                    
                if not self._send_cancelled:
                    send_msg(sock, json.dumps({"type": "file_end", "name": filename}).encode('utf-8'))
                    log_debug(f"[_process_send_requests] Đã gửi file_end cho {filename}")
                
            if not self._send_cancelled:
                send_msg(sock, json.dumps({"type": "batch_end"}).encode('utf-8'))
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

        # Text: không ghi đè clipboard máy thật khi user đang làm việc ngoài viewer.
        # File meta: vẫn nhận khi Explorer đang focus — đó là lúc user paste host→client.
        if ptype == "clipboard_text":
            if getattr(self, 'pygame_hwnd', None):
                user32 = ctypes.windll.user32
                user32.GetForegroundWindow.restype = ctypes.c_void_p
                fg_hwnd = user32.GetForegroundWindow()
                if fg_hwnd != self.pygame_hwnd:
                    log_debug(f"[handle_received_packet] Bỏ qua clipboard_text do cửa sổ Viewer không được kích hoạt (Giữ clipboard cho máy thật).")
                    return
                    
        # Nếu đang hủy hoặc đã hủy nhận, bỏ qua các gói tin liên quan đến truyền lô file hiện tại
        if getattr(self, '_receive_cancelled', False) and ptype in ("file_start", "file_chunk", "file_end", "batch_end"):
            log_debug(f"[handle_received_packet] Bỏ qua gói tin {ptype} do tiến trình tải đã bị hủy.")
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
            self._receive_cancelled = False
            self.pending_remote_files = packet.get("files", [])
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
            self._receive_cancelled = False
            
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
            
            # Use target_dir from packet if provided, else use self.target_save_dir
            save_dir = packet.get("target_dir", self.target_save_dir)
            if not save_dir: save_dir = self.target_save_dir
            
            target_path = os.path.join(save_dir, filename)
            log_debug(f"[file_start] Bắt đầu nhận file: {filename}, target_path={target_path}")

            try:
                dirname = os.path.dirname(target_path)
                if dirname:
                    os.makedirs(dirname, exist_ok=True)
                fh = open(target_path, "wb")
                self.incoming_transfers[filename] = {
                    "path": target_path,
                    "handle": fh,
                    "skipped": False,
                    "pending": False,
                }
                log_debug(f"[file_start] Mở thành công file mới: {target_path}")
            except Exception as e:
                print(f"[FileTransfer] Lỗi mở file mới {filename}: {e}")
                log_debug(f"[file_start] Lỗi mở file mới {filename}: {e}")

        elif ptype == "file_chunk":
            filename = packet.get("name", "")
            if filename in self.incoming_transfers:
                transfer = self.incoming_transfers[filename]
                chunk_bytes = base64.b64decode(packet.get("data", ""))

                if transfer.get("handle") is not None:
                    transfer["handle"].write(chunk_bytes)
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
                transfer = self.incoming_transfers.pop(filename, None)
                if transfer:
                    if transfer.get("handle") is not None:
                        try:
                            transfer["handle"].close()
                            log_debug(f"[file_end] Đóng handle file thành công cho: {filename}")
                        except Exception as e:
                            log_debug(f"[file_end] Lỗi đóng handle file {filename}: {e}")
                    
                    top_level_name = filename.replace('\\', '/').split('/')[0]
                    top_level_path = os.path.join(self.target_save_dir, top_level_name)
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
                if self.batch_paths:
                    files_str = "|".join(self.batch_paths)
                    self._send_progress_signal("FILES", files_str)
                    log_debug(f"[batch_end] HEADLESS: Đã gửi FILES tới agent: {files_str[:100]}")
                    
                    if hasattr(self, 'lock'):
                        with self.lock:
                            self.last_current_files = [os.path.abspath(p) for p in self.batch_paths if os.path.exists(p)]
                            self.last_files_time = time.time()
                else:
                    self._send_progress_signal("CANCEL", "")
                    log_debug("[batch_end] HEADLESS: batch_paths trống, đã gửi CANCEL tới agent.")
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
                    _agent_last_ctrl_v_time = time.time()
                if (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000):
                    _agent_last_ctrl_v_time = time.time()
            except:
                pass
            time.sleep(0.05)
            
    threading.Thread(target=_agent_mouse_poll_loop, daemon=True, name="AgentMousePoll").start()

    def _send_request_files_to_host(files_to_request=None, dest_dir=None):
        """Gửi chuỗi REQUEST_FILES cho host qua UpPipe."""
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
            payload = {"files": files_to_request or [], "dest_dir": dest_dir or ""}
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
        nonlocal _is_rendering, _files_ready_paths, _files_ready_event, _ignore_destroy, _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_dummy_h_active, _agent_cached_explorer_path

        if msg == WM_USER_SETUP_DELAYED:
            if _pending_info:
                _execute_agent_delayed_rendering(hwnd)
            return 0

        if msg == 0x031D: # WM_CLIPBOARDUPDATE
            if _ignore_destroy:
                return 0
            def _send_clipboard():
                import time
                time.sleep(0.2) # wait for clipboard to settle
                files = get_clipboard_files()
                if files:
                    try:
                        import win32pipe, win32file, json
                        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
                        win32pipe.WaitNamedPipe(pipe_name, 5000)
                        pipe_handle = win32file.CreateFile(pipe_name, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
                        msg = "COPIED_FILES|" + json.dumps(files)
                        win32file.WriteFile(pipe_handle, msg.encode('utf-8'))
                        win32file.CloseHandle(pipe_handle)
                        agent_print(f"[ClipboardAgent] Đã gửi {len(files)} COPIED_FILES cho Service.")
                    except Exception as e:
                        agent_print(f"Failed to send COPIED_FILES: {e}")
            threading.Thread(target=_send_clipboard, daemon=True).start()
            return 0

        if msg == WM_RENDERFORMAT and wparam == CF_HDROP:
            if _is_rendering:
                agent_print("[ClipboardAgent] WM_RENDERFORMAT trùng lặp, bỏ qua.")
                return 0
                
            # Kiểm tra nếu là truy vấn từ menu chuột phải (context menu) thì tránh tải file thực tế lúc này
            is_menu = check_is_menu_query(_agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_ctrl_v_time)
            if is_menu == "MENU":
                agent_print("[ClipboardAgent] Phát hiện truy vấn menu. Cung cấp dummy HDROP và chờ user dán...")
                dummy_h = create_hdrop_data(["C:\\RemoteDesktop_Paste_Trigger.tmp"])
                if dummy_h:
                    ctypes.windll.user32.SetClipboardData(CF_HDROP, dummy_h)
                _agent_dummy_h_active = True
                return 0
            elif is_menu == "BACKGROUND":
                agent_print("[ClipboardAgent] Phát hiện truy vấn nền (VM Tools). Bỏ qua để giữ delayed rendering.")
                return 0

            _is_rendering = True
            agent_print("[ClipboardAgent] Nhận WM_RENDERFORMAT → người dùng đã Paste. Bắt đầu tải file...")
            try:
                # Hiển thị dialog qua gui_queue ngay lập tức
                info = _pending_info.copy()
                gui_queue.put(("start", (info.get("display_name", "Files"), info.get("total_size", 0))))

                # Yêu cầu host bắt đầu gửi file
                _files_ready_event.clear()
                _files_ready_paths.clear()
                _send_request_files_to_host(info.get("files", []), _agent_cached_explorer_path)

                # Chờ host download xong (tối đa 600 giây, pump Win32 messages)
                user32 = ctypes.windll.user32
                m = wintypes.MSG()
                deadline = time.time() + 600.0
                while time.time() < deadline:
                    if _files_ready_event.is_set():
                        break
                    if user32.PeekMessageW(ctypes.byref(m), 0, 0, 0, 1):
                        user32.TranslateMessage(ctypes.byref(m))
                        user32.DispatchMessageW(ctypes.byref(m))
                    else:
                        time.sleep(0.01)

                if _files_ready_event.is_set() and _files_ready_paths:
                    dest_dir = _agent_cached_explorer_path
                    final_paths = list(_files_ready_paths)
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
                else:
                    agent_print("[ClipboardAgent] Hết thời gian chờ file hoặc bị hủy.")
                    empty_hdrop = create_hdrop_data([])
                    if empty_hdrop:
                        _ignore_destroy = True
                        res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                        if not res: fn_GlobalFree(empty_hdrop)
                        _ignore_destroy = False
                    gui_queue.put(("cancel", None))
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lỗi xử lý WM_RENDERFORMAT: {e}")
                empty_hdrop = create_hdrop_data([])
                if empty_hdrop:
                    _ignore_destroy = True
                    res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                    if not res: fn_GlobalFree(empty_hdrop)
                    _ignore_destroy = False
                gui_queue.put(("cancel", None))
            finally:
                _is_rendering = False
                _pending_info.clear()
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
            ctypes.c_void_p(-3),  # HWND_MESSAGE
            None, wc.hInstance, None
        )
        _agent_hwnd = hwnd
        agent_print(f"[ClipboardAgent] Window ẩn đã tạo. HWND={hwnd}")

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    threading.Thread(target=_create_agent_window, daemon=True, name="AgentWin32MsgLoop").start()
    time.sleep(0.1)  # Chờ window khởi tạo

    def trigger_cancel():
        """Giải phóng luồng chờ WM_RENDERFORMAT và xóa trạng thái pending."""
        nonlocal _pending_info
        _files_ready_paths.clear()
        _pending_info.clear()
        _files_ready_event.set()  # unlock nếu đang chờ trong WM_RENDERFORMAT
        agent_print("[ClipboardAgent] Đã hủy trạng thái pending.")

    def trigger_cancel_win32():
        """Nút Hủy trong dialog → gửi Win32 Event để host service dừng gửi."""
        try:
            h_event = win32event.OpenEvent(win32event.EVENT_MODIFY_STATE, False, "Global\\AntigravityP2P_CancelTransfer_Event")
            win32event.SetEvent(h_event)
            win32api.CloseHandle(h_event)
        except Exception as e:
            agent_print(f"[ClipboardAgent] Không thể gửi sự kiện hủy: {e}")
        trigger_cancel()

    def poll_gui_queue():
        nonlocal active_dialog, _agent_meta_arrival_time
        while not gui_queue.empty():
            try:
                action, val = gui_queue.get_nowait()
                if action == "text":
                    agent_print(f"[ClipboardAgent] Đang nạp text vào Clipboard...")
                    set_clipboard_text(val, owner_hwnd=_agent_hwnd)
                elif action == "files":
                    # Được gửi bởi luồng WM_RENDERFORMAT (cũ giữ lại cho trường hợp khác)
                    paths = [p for p in val.split("|") if os.path.exists(p)]
                    if paths:
                        set_clipboard_files(paths, owner_hwnd=_agent_hwnd)
                        agent_print(f"[ClipboardAgent] Đã nạp {len(paths)} file vào Clipboard.")
                    else:
                        agent_print(f"[ClipboardAgent] File không tồn tại để nạp clipboard.")
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
                    # Cầu hiệu nội bộ: luồng WM_RENDERFORMAT đã nhận FILES: từ host
                    paths_str = val
                    paths = [p for p in paths_str.split("|") if p]
                    _files_ready_paths.clear()
                    _files_ready_paths.extend(paths)
                    _files_ready_event.set()
                    agent_print(f"[ClipboardAgent] files_ready: {len(paths)} file đã sẵn sàng.")
                elif action == "start":
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
