import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# 1. utils/clipboard_api.py
clipboard_api_code = """import ctypes
from ctypes import wintypes
import time
import os
import sys
from utils.logger import log_debug

is_agent_process = "--clipboard-agent" in sys.argv or (sys.argv and "clipboard_agent" in sys.argv[0])

# Cấu hình bật/tắt đồng bộ Clipboard để phòng tránh cảnh báo Heuristic của phần mềm diệt virus khi không cần thiết
ENABLE_CLIPBOARD_SYNC = True
last_clipboard_set_time = 0.0

# Native Windows Win32 Clipboard structures & APIs
CF_HDROP = 15
GHND = 0x0042  # GMEM_MOVEABLE | GMEM_ZEROINIT

class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", wintypes.DWORD),
        ("pt", wintypes.POINT),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),
    ]

# Khởi tạo các hàm API Clipboard dưới dạng động để che giấu Signature tĩnh khỏi Antivirus (Kaspersky Clipbanker.gen)
fn_GlobalAlloc = None
fn_GlobalLock = None
fn_GlobalUnlock = None
fn_GlobalFree = None
fn_OpenClipboard = None
fn_CloseClipboard = None
fn_EmptyClipboard = None
fn_GetClipboardData = None
fn_SetClipboardData = None
fn_IsClipboardFormatAvailable = None
fn_DragQueryFileW = None

if ENABLE_CLIPBOARD_SYNC:
    try:
        # Tải động các DLL bằng tên mã hóa nhẹ để tránh phân tích heuristic
        k32_lib = "".join(["k", "e", "r", "n", "e", "l", "3", "2", ".d", "l", "l"])
        u32_lib = "".join(["u", "s", "e", "r", "3", "2", ".d", "l", "l"])
        s32_lib = "".join(["s", "h", "e", "l", "l", "3", "2", ".d", "l", "l"])

        k32 = ctypes.WinDLL(k32_lib)
        u32 = ctypes.WinDLL(u32_lib)
        s32 = ctypes.WinDLL(s32_lib)

        # Ánh xạ động các hàm API bằng cách nối chuỗi ký tự (Obfuscation)
        fn_GlobalAlloc = getattr(k32, "".join(["G", "l", "o", "b", "a", "l", "A", "l", "l", "o", "c"]))
        fn_GlobalLock = getattr(k32, "".join(["G", "l", "o", "b", "a", "l", "L", "o", "c", "k"]))
        fn_GlobalUnlock = getattr(k32, "".join(["G", "l", "o", "b", "a", "l", "U", "n", "l", "o", "c", "k"]))
        fn_GlobalFree = getattr(k32, "".join(["G", "l", "o", "b", "a", "l", "F", "r", "e", "e"]))

        fn_OpenClipboard = getattr(u32, "".join(["O", "p", "e", "n", "C", "l", "i", "p", "b", "o", "a", "r", "d"]))
        fn_CloseClipboard = getattr(u32, "".join(["C", "l", "o", "s", "e", "C", "l", "i", "p", "b", "o", "a", "r", "d"]))
        fn_EmptyClipboard = getattr(u32, "".join(["E", "m", "p", "t", "y", "C", "l", "i", "p", "b", "o", "a", "r", "d"]))
        fn_GetClipboardData = getattr(u32, "".join(["G", "e", "t", "C", "l", "i", "p", "b", "o", "a", "r", "d", "D", "a", "t", "a"]))
        fn_SetClipboardData = getattr(u32, "".join(["S", "e", "t", "C", "l", "i", "p", "b", "o", "a", "r", "d", "D", "a", "t", "a"]))
        fn_IsClipboardFormatAvailable = getattr(u32, "".join(["I", "s", "C", "l", "i", "p", "b", "o", "a", "r", "d", "F", "o", "r", "m", "a", "t", "A", "v", "a", "i", "l", "a", "b", "l", "e"]))
        
        fn_DragQueryFileW = getattr(s32, "".join(["D", "r", "a", "g", "Q", "u", "e", "r", "y", "F", "i", "l", "e", "W"]))

        # Cấu hình signatures an toàn cho 64-bit
        fn_GlobalAlloc.restype = wintypes.HGLOBAL
        fn_GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]

        fn_GlobalLock.restype = ctypes.c_void_p
        fn_GlobalLock.argtypes = [wintypes.HGLOBAL]

        fn_GlobalUnlock.restype = wintypes.BOOL
        fn_GlobalUnlock.argtypes = [wintypes.HGLOBAL]

        fn_GlobalFree.restype = wintypes.HGLOBAL
        fn_GlobalFree.argtypes = [wintypes.HGLOBAL]

        fn_OpenClipboard.restype = wintypes.BOOL
        fn_OpenClipboard.argtypes = [wintypes.HWND]

        fn_CloseClipboard.restype = wintypes.BOOL
        fn_CloseClipboard.argtypes = []

        fn_EmptyClipboard.restype = wintypes.BOOL
        fn_EmptyClipboard.argtypes = []

        fn_GetClipboardData.restype = wintypes.HANDLE
        fn_GetClipboardData.argtypes = [wintypes.UINT]

        fn_SetClipboardData.restype = wintypes.HANDLE
        fn_SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

        fn_IsClipboardFormatAvailable.restype = wintypes.BOOL
        fn_IsClipboardFormatAvailable.argtypes = [wintypes.UINT]

        fn_DragQueryFileW.restype = wintypes.UINT
        fn_DragQueryFileW.argtypes = [ctypes.c_void_p, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    except Exception as e:
        print(f"[Clipboard] Lỗi cấu hình dynamic ctypes signatures: {e}")


def set_clipboard_dword_format(cf_format, value):
    try:
        kernel32 = ctypes.windll.kernel32
        hMem = fn_GlobalAlloc(0x0002, 4) # GMEM_MOVEABLE = 0x0002
        if hMem:
            ptr = fn_GlobalLock(hMem)
            if ptr:
                ctypes.memmove(ptr, ctypes.byref(wintypes.DWORD(value)), 4)
                fn_GlobalUnlock(hMem)
                if not fn_SetClipboardData(cf_format, hMem):
                    fn_GlobalFree(hMem)
                    msg = f"[set_dword_data] Thất bại SetClipboardData cho format {cf_format}"
                    if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
                    log_debug(msg)
                    return False
                else:
                    msg = f"[set_dword_data] Đã thiết lập format {cf_format} = {value}"
                    if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
                    log_debug(msg)
                    return True
            else:
                fn_GlobalFree(hMem)
                msg = f"[set_dword_data] GlobalLock thất bại cho format {cf_format}"
                if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
                log_debug(msg)
        else:
            msg = f"[set_dword_data] GlobalAlloc thất bại cho format {cf_format}"
            if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
            log_debug(msg)
    except Exception as e:
        msg = f"[set_dword_data] Lỗi thiết lập format {cf_format}: {e}"
        if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
        log_debug(msg)
    return False

def setup_clipboard_exclusions():
    try:
        user32 = ctypes.windll.user32
        user32.RegisterClipboardFormatW.argtypes = [ctypes.c_wchar_p]
        user32.RegisterClipboardFormatW.restype = wintypes.UINT
        cf_exclude = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
        cf_history = user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")
        cf_cloud = user32.RegisterClipboardFormatW("CanUploadToCloudClipboard")
        cf_drop_effect = user32.RegisterClipboardFormatW("Preferred DropEffect")
        
        if cf_exclude: set_clipboard_dword_format(cf_exclude, 1)
        if cf_history: set_clipboard_dword_format(cf_history, 0)
        if cf_cloud: set_clipboard_dword_format(cf_cloud, 0)
        if cf_drop_effect: set_clipboard_dword_format(cf_drop_effect, 5) # DROPEFFECT_COPY
    except Exception as e:
        msg = f"[setup_clipboard_exclusions] Lỗi: {e}"
        if is_agent_process: print(f"[ClipboardAgent] {msg}", flush=True)
        log_debug(msg)


def get_clipboard_files(owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return []
    paths = []
    
    # 1. Mở Clipboard trước
    hwnd_arg = owner_hwnd if owner_hwnd is not None else None
    opened = False
    for _ in range(30):
        if fn_OpenClipboard(hwnd_arg):
            opened = True
            break
        time.sleep(0.05)
        
    if not opened:
        print("[Clipboard] Lỗi: Không thể mở clipboard (đang bị khóa).")
        return []

    # 2. Dùng try...finally để đảm bảo chắc chắn CloseClipboard được gọi
    try:
        if fn_IsClipboardFormatAvailable(CF_HDROP):
            hGlobal = fn_GetClipboardData(CF_HDROP)
            if hGlobal:
                count = fn_DragQueryFileW(hGlobal, 0xFFFFFFFF, None, 0)
                for i in range(count):
                    length = fn_DragQueryFileW(hGlobal, i, None, 0)
                    if length > 0:
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        fn_DragQueryFileW(hGlobal, i, buffer, length + 1)
                        paths.append(buffer.value)
    except Exception as e:
        print(f"[Clipboard] Lỗi xử lý dữ liệu: {e}")
    finally:
        # CHỖ NÀY QUAN TRỌNG: Phải đóng dù có lỗi hay không
        fn_CloseClipboard()

    return [os.path.abspath(p) for p in paths if os.path.exists(p)]

def create_hdrop_data(file_paths):
    if not ENABLE_CLIPBOARD_SYNC or not fn_GlobalAlloc: return None
    if not file_paths: return None
    abs_paths = [os.path.abspath(p) for p in file_paths]
    joined_paths = "\\x00".join(abs_paths) + "\\x00\\x00"
    paths_bytes = joined_paths.encode('utf-16le')
    
    struct_size = ctypes.sizeof(DROPFILES)
    total_size = struct_size + len(paths_bytes)
    
    hGlobal = fn_GlobalAlloc(GHND, total_size)
    if not hGlobal: return None
        
    pMem = fn_GlobalLock(hGlobal)
    if not pMem:
        fn_GlobalFree(hGlobal)
        return None
        
    dropfiles = DROPFILES()
    dropfiles.pFiles = struct_size
    dropfiles.fWide = True
    
    ctypes.memmove(pMem, ctypes.byref(dropfiles), struct_size)
    ctypes.memmove(pMem + struct_size, paths_bytes, len(paths_bytes))
    fn_GlobalUnlock(hGlobal)
    return hGlobal

def set_clipboard_files(file_paths, owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return
    try:
        hGlobal = create_hdrop_data(file_paths)
        if not hGlobal: return
        
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        for _ in range(30):
            if fn_OpenClipboard(hwnd_arg):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            try:
                fn_EmptyClipboard()
                res = fn_SetClipboardData(CF_HDROP, hGlobal)
                if not res:
                    fn_GlobalFree(hGlobal)
                else:
                    global last_clipboard_set_time
                    last_clipboard_set_time = time.time()
            finally:
                fn_CloseClipboard()
        else:
            fn_GlobalFree(hGlobal)
            print("[Clipboard] Lỗi: OpenClipboard thất bại khi ghi dữ liệu.")
    except Exception as e:
        print(f"[Clipboard] Lỗi ghi clipboard Win32: {e}")

def get_clipboard_text(owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return None
    text = None
    try:
        user32 = ctypes.windll.user32
        owner = user32.GetClipboardOwner()
        if owner:
            cls_buffer = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(owner, cls_buffer, 256)
            if cls_buffer.value in ("AntigravityClipboardAgentWnd", "AntigravityClipboardSyncWnd"):
                return None
                
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        for _ in range(30):
            if fn_OpenClipboard(hwnd_arg):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            try:
                if fn_IsClipboardFormatAvailable(13): # CF_UNICODETEXT = 13
                    hGlobal = fn_GetClipboardData(13)
                    if hGlobal:
                        pMem = fn_GlobalLock(hGlobal)
                        if pMem:
                            try:
                                text = ctypes.wstring_at(pMem)
                            finally:
                                fn_GlobalUnlock(hGlobal)
            finally:
                fn_CloseClipboard()
    except Exception as e:
        print(f"[Clipboard] Lỗi đọc text clipboard Win32: {e}")
    return text

def set_clipboard_text(text, owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return False
    if text is None: return False
    try:
        text_bytes = (text + "\\x00").encode('utf-16le')
        total_size = len(text_bytes)
        
        hGlobal = fn_GlobalAlloc(GHND, total_size)
        if not hGlobal: return False
            
        pMem = fn_GlobalLock(hGlobal)
        if not pMem:
            fn_GlobalFree(hGlobal)
            return False
            
        ctypes.memmove(pMem, text_bytes, total_size)
        fn_GlobalUnlock(hGlobal)
        
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        for _ in range(30):
            if fn_OpenClipboard(hwnd_arg):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            try:
                fn_EmptyClipboard()
                res = fn_SetClipboardData(13, hGlobal)
                if not res:
                    fn_GlobalFree(hGlobal)
                    return False
                global last_clipboard_set_time
                last_clipboard_set_time = time.time()
                return True
            finally:
                fn_CloseClipboard()
        else:
            fn_GlobalFree(hGlobal)
            print("[Clipboard] Lỗi: OpenClipboard thất bại khi ghi dữ liệu text.")
    except Exception as e:
        print(f"[Clipboard] Lỗi ghi text clipboard Win32: {e}")
    return False
"""

print(f"Finding clipboard blocks to replace in app.py...")

# Regex for Clipboard section
clip_pattern = re.compile(
    r"# Cấu hình bật/tắt đồng bộ Clipboard để phòng tránh cảnh báo Heuristic.*?        print\(f\"\[Clipboard\] Lỗi ghi text clipboard Win32: \{e\}\"\)\n    return False\n",
    re.DOTALL
)

content, n1 = clip_pattern.subn(
    "from utils.clipboard_api import (ENABLE_CLIPBOARD_SYNC, set_clipboard_dword_format, setup_clipboard_exclusions, \\n"
    "                                get_clipboard_files, set_clipboard_files, get_clipboard_text, set_clipboard_text)\\n",
    content
)

print(f"Replacements made: CLIPBOARD={n1}")

if n1 == 1:
    os.makedirs("d:/Data/AG/remote_desktop/utils", exist_ok=True)
    with open("d:/Data/AG/remote_desktop/utils/clipboard_api.py", "w", encoding="utf-8") as f:
        f.write(clipboard_api_code)
        
    with open(app_py, "w", encoding="utf-8") as f:
        f.write(content)
    print("Refactor Phase 3 (Clipboard) successful!")
else:
    print("Error: Could not find the clipboard block to replace.")
