import ctypes
from ctypes import wintypes
import threading
import time
import sys

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_int64, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_int64

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalUnlock.restype = wintypes.BOOL

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", wintypes.INT),
        ("cbWndExtra", wintypes.INT),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HICON),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON)
    ]

# Global state
hwnd = None
running = True

def wndproc(hWnd, message, wParam, lParam):
    if message == 15:  # WM_PAINT
        return 0
    elif message == 2:  # WM_DESTROY
        user32.PostQuitMessage(0)
        return 0
    elif message == 0x0306:  # WM_RENDERFORMAT
        print(f"[{time.time():.3f}] Received WM_RENDERFORMAT for format {wParam}")
        # CF_HDROP = 15
        if wParam == 15:
            print("Rendering dummy CF_HDROP")
            paths_bytes = "C:\\dummy_test_file.txt\x00\x00".encode('utf-16le')
            struct_size = 20 # sizeof(DROPFILES)
            total_size = struct_size + len(paths_bytes)
            
            hGlobal = kernel32.GlobalAlloc(0x0042, total_size) # GHND
            if hGlobal:
                pMem = kernel32.GlobalLock(hGlobal)
                if pMem:
                    # Write DROPFILES struct
                    # pFiles = 20, fWide = True (1)
                    ctypes.memmove(pMem, ctypes.byref(wintypes.DWORD(20)), 4)
                    ctypes.memmove(pMem + 16, ctypes.byref(wintypes.BOOL(True)), 4)
                    ctypes.memmove(pMem + struct_size, paths_bytes, len(paths_bytes))
                    kernel32.GlobalUnlock(hGlobal)
                    
                    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
                    res = user32.SetClipboardData(15, hGlobal)
                    print(f"SetClipboardData dummy CF_HDROP returned: {res}")
        return 0
    elif message == 0x0307:  # WM_RENDERALLFORMATS
        print(f"[{time.time():.3f}] Received WM_RENDERALLFORMATS")
        return 0
    elif message == 0x0308:  # WM_DESTROYCLIPBOARD
        print(f"[{time.time():.3f}] Received WM_DESTROYCLIPBOARD")
        return 0
    elif message == 0x031D:  # WM_CLIPBOARDUPDATE
        print(f"[{time.time():.3f}] Received WM_CLIPBOARDUPDATE")
        return 0
    return user32.DefWindowProcW(hWnd, message, wParam, lParam)

def run_loop():
    global hwnd, running
    
    # Register window class
    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.style = 0
    wc.lpfnWndProc = WNDPROC(wndproc)
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.hIcon = 0
    wc.hCursor = 0
    wc.hbrBackground = 0
    wc.lpszMenuName = None
    wc.lpszClassName = "TestDelayedClass"
    wc.hIconSm = 0
    
    reg = user32.RegisterClassExW(ctypes.byref(wc))
    if not reg:
        print("Failed to register window class")
        return
        
    hwnd = user32.CreateWindowExW(
        0, "TestDelayedClass", "TestDelayedWindow",
        0, 0, 0, 0, 0,
        0, None, wc.hInstance, None
    )
    if not hwnd:
        print("Failed to create window")
        return
        
    print(f"Window created. HWND: {hwnd}")
    
    # Register clipboard format listener
    user32.AddClipboardFormatListener(hwnd)
    
    # Configure delayed rendering
    user32.OpenClipboard(hwnd)
    user32.EmptyClipboard()
    
    # Preferred DropEffect
    cf_drop_effect = user32.RegisterClipboardFormatW("Preferred DropEffect")
    if cf_drop_effect:
        hMem = kernel32.GlobalAlloc(0x0042, 4)
        if hMem:
            ptr = kernel32.GlobalLock(hMem)
            if ptr:
                ctypes.memmove(ptr, ctypes.byref(wintypes.DWORD(5)), 4) # 5 = DROPEFFECT_COPY
                kernel32.GlobalUnlock(hMem)
                user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
                user32.SetClipboardData(cf_drop_effect, hMem)
                print("Preferred DropEffect set")
                
    # CF_HDROP delayed rendering
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    res = user32.SetClipboardData(15, None)
    print("SetClipboardData CF_HDROP delayed rendering result:", res)
    user32.CloseClipboard()
    
    msg = wintypes.MSG()
    while running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

if __name__ == "__main__":
    t = threading.Thread(target=run_loop)
    t.start()
    
    print("Waiting 15 seconds. Try right-clicking in Explorer or doing copy/paste.")
    time.sleep(15)
    running = False
    if hwnd:
        user32.PostMessageW(hwnd, 18, 0, 0) # WM_QUIT = 18
    t.join()
    print("Test finished.")
