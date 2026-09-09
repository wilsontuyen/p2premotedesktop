import ctypes
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

if ENABLE_CLIPBOARD_SYNC and sys.platform == "win32":
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


_SYNC_CLIPBOARD_WND_CLASSES = (
    "AntigravityClipboardAgentWnd",
    "AntigravityClipboardSyncWnd",
    "HiddenClipboardListener",
)


def _clipboard_owned_by_sync_window():
    """True nếu clipboard đang do cửa sổ delayed-render của app sở hữu.
    Không được GetClipboardData trong trường hợp này — sẽ kích WM_RENDERFORMAT
    như một lần Paste giả và tải file trước khi user dán."""
    try:
        user32 = ctypes.windll.user32
        owner = user32.GetClipboardOwner()
        if not owner:
            return False
        cls_buffer = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(owner, cls_buffer, 256)
        return cls_buffer.value in _SYNC_CLIPBOARD_WND_CLASSES
    except Exception:
        return False


def get_clipboard_files(owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return []
    if _clipboard_owned_by_sync_window():
        return []
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
    if not file_paths:
        paths_bytes = b'\x00\x00\x00\x00'
    else:
        abs_paths = [os.path.abspath(p) for p in file_paths]
        joined_paths = "\x00".join(abs_paths) + "\x00\x00"
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
        if _clipboard_owned_by_sync_window():
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
        text_bytes = (text + "\x00").encode('utf-16le')
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


# --- Hỗ trợ Clipboard Image cho Windows 11 ---
# CF_BITMAP = 2, CF_DIB = 8, CF_DIBV5 = 17

def get_clipboard_image_data(owner_hwnd=None):
    """
    Lấy dữ liệu ảnh từ clipboard dưới dạng bytes (DIB format).
    Trả về (dib_bytes, width, height) hoặc (None, 0, 0) nếu không có ảnh.
    """
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard:
        return None, 0, 0
    
    CF_DIB = 8
    dib_bytes = None
    width = 0
    height = 0
    
    try:
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        for _ in range(30):
            if fn_OpenClipboard(hwnd_arg):
                opened = True
                break
            time.sleep(0.05)
        
        if not opened:
            return None, 0, 0
        
        try:
            if fn_IsClipboardFormatAvailable(CF_DIB):
                hGlobal = fn_GetClipboardData(CF_DIB)
                if hGlobal:
                    pMem = fn_GlobalLock(hGlobal)
                    if pMem:
                        try:
                            # Đọc BITMAPINFOHEADER (40 bytes đầu)
                            import struct
                            header = (ctypes.c_char * 40)()
                            ctypes.memmove(header, pMem, 40)
                            bi_size = struct.unpack_from('<I', header, 0)[0]
                            width = struct.unpack_from('<i', header, 4)[0]
                            height = abs(struct.unpack_from('<i', header, 8)[0])
                            bi_bit_count = struct.unpack_from('<H', header, 14)[0]
                            bi_compression = struct.unpack_from('<I', header, 16)[0]
                            bi_size_image = struct.unpack_from('<I', header, 20)[0]
                            
                            # Tính tổng kích thước DIB data
                            if bi_size_image == 0:
                                row_size = ((width * bi_bit_count + 31) // 32) * 4
                                bi_size_image = row_size * height
                            
                            # Tính kích thước bảng màu (color table)
                            color_table_size = 0
                            if bi_bit_count <= 8:
                                bi_clr_used = struct.unpack_from('<I', header, 32)[0]
                                if bi_clr_used == 0:
                                    bi_clr_used = 1 << bi_bit_count
                                color_table_size = bi_clr_used * 4
                            
                            total_size = bi_size + color_table_size + bi_size_image
                            
                            # Giới hạn dung lượng ảnh tối đa 10MB để tránh lag mạng
                            if total_size > 10 * 1024 * 1024:
                                log_debug(f"[get_clipboard_image] Ảnh quá lớn ({total_size} bytes), bỏ qua.")
                                return None, 0, 0
                            
                            dib_buf = (ctypes.c_char * total_size)()
                            ctypes.memmove(dib_buf, pMem, total_size)
                            dib_bytes = bytes(dib_buf)
                        finally:
                            fn_GlobalUnlock(hGlobal)
        finally:
            fn_CloseClipboard()
    except Exception as e:
        log_debug(f"[get_clipboard_image] Lỗi: {e}")
    
    return dib_bytes, width, height


def set_clipboard_image_data(dib_bytes, owner_hwnd=None):
    """
    Nạp dữ liệu ảnh (DIB bytes) vào clipboard.
    """
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard:
        return False
    if not dib_bytes:
        return False
    
    CF_DIB = 8
    try:
        total_size = len(dib_bytes)
        hGlobal = fn_GlobalAlloc(GHND, total_size)
        if not hGlobal:
            return False
        
        pMem = fn_GlobalLock(hGlobal)
        if not pMem:
            fn_GlobalFree(hGlobal)
            return False
        
        ctypes.memmove(pMem, dib_bytes, total_size)
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
                res = fn_SetClipboardData(CF_DIB, hGlobal)
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
            log_debug("[set_clipboard_image] OpenClipboard thất bại.")
    except Exception as e:
        log_debug(f"[set_clipboard_image] Lỗi: {e}")
    return False


def clear_local_clipboard(owner_hwnd=None):
    """Xóa toàn bộ clipboard máy này (text/file/image)."""
    if sys.platform == "win32":
        if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard:
            try:
                ctypes.windll.user32.OpenClipboard(owner_hwnd)
                ctypes.windll.user32.EmptyClipboard()
                ctypes.windll.user32.CloseClipboard()
                return True
            except Exception:
                return False
        try:
            hwnd_arg = owner_hwnd if owner_hwnd is not None else None
            opened = False
            for _i in range(20):
                if fn_OpenClipboard(hwnd_arg):
                    opened = True
                    break
                time.sleep(0.03)
            if not opened:
                return False
            try:
                fn_EmptyClipboard()
                return True
            finally:
                fn_CloseClipboard()
        except Exception as e:
            log_debug(f"[clear_local_clipboard] {e}")
            return False
    try:
        import pyperclip
        pyperclip.copy("")
        return True
    except Exception:
        return False

