import ctypes
from ctypes import wintypes
import time
import sys

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WPARAM_64 = ctypes.c_size_t
LPARAM_64 = ctypes.c_ssize_t
LRESULT_64 = ctypes.c_ssize_t

WNDPROCTYPE = ctypes.WINFUNCTYPE(LRESULT_64, ctypes.c_void_p, ctypes.c_uint, WPARAM_64, LPARAM_64)

class WNDCLASSEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint), ("style", ctypes.c_uint), ("lpfnWndProc", WNDPROCTYPE),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", ctypes.c_void_p)
    ]

try:
    user32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, WPARAM_64, LPARAM_64]
    user32.DefWindowProcW.restype = LRESULT_64
    
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    
    user32.OpenClipboard.argtypes = [ctypes.c_void_p]
    user32.OpenClipboard.restype = wintypes.BOOL
    
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
except Exception as e:
    print("Failed to set types:", e)

last_err = 0
hwnd = None

def wndproc(h_wnd, msg, wparam, lparam):
    global last_err
    WM_SETUP_DELAYED = 0x0400 + 101
    WM_RENDERFORMAT = 0x0305
    WM_DESTROYCLIPBOARD = 0x0307
    
    if msg == WM_SETUP_DELAYED:
        print("Received WM_SETUP_DELAYED")
        opened = False
        for _ in range(10):
            if user32.OpenClipboard(ctypes.c_void_p(h_wnd)):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            try:
                user32.EmptyClipboard()
                
                cf_exclude = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
                cf_history = user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")
                cf_cloud = user32.RegisterClipboardFormatW("CanUploadToCloudClipboard")
                
                def set_dword(cf, val):
                    hMem = kernel32.GlobalAlloc(0x0002, 4)
                    if hMem:
                        ptr = kernel32.GlobalLock(hMem)
                        if ptr:
                            ctypes.memmove(ptr, ctypes.byref(wintypes.DWORD(val)), 4)
                            kernel32.GlobalUnlock(hMem)
                            user32.SetClipboardData(cf, hMem)
                
                if cf_exclude: set_dword(cf_exclude, 1)
                if cf_history: set_dword(cf_history, 0)
                if cf_cloud: set_dword(cf_cloud, 0)
                
                # Clear error first
                kernel32.SetLastError(0)
                
                res = user32.SetClipboardData(15, None)
                last_err = kernel32.GetLastError()
                print(f"SetClipboardData(15, None) returned: {res}, GetLastError: {last_err}")
            finally:
                user32.CloseClipboard()
        else:
            print("Failed to open clipboard")
        return 0
    elif msg == WM_RENDERFORMAT:
        print(f"Received WM_RENDERFORMAT for format {wparam}")
        return 0
    elif msg == WM_DESTROYCLIPBOARD:
        print("Received WM_DESTROYCLIPBOARD")
        return 0
        
    return user32.DefWindowProcW(h_wnd, msg, wparam, lparam)

def main():
    global hwnd
    h_mod = kernel32.GetModuleHandleW(None)
    
    wndproc_ptr = WNDPROCTYPE(wndproc)
    wndclass = WNDCLASSEX()
    wndclass.cbSize = ctypes.sizeof(WNDCLASSEX)
    wndclass.lpfnWndProc = wndproc_ptr
    wndclass.lpszClassName = "TestDelayedRenderClass"
    wndclass.hInstance = h_mod
    
    reg = user32.RegisterClassExW(ctypes.byref(wndclass))
    print(f"RegisterClassExW: {reg}")
    
    user32.CreateWindowExW.argtypes = [
        ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
        ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
    ]
    user32.CreateWindowExW.restype = ctypes.c_void_p
    
    hwnd = user32.CreateWindowExW(0, wndclass.lpszClassName, "TestWindow", 0, 0, 0, 0, 0, ctypes.c_void_p(-3), None, h_mod, None)
    print(f"CreateWindowExW HWND: {hwnd}")
    
    if hwnd:
        user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0400 + 101, 0, 0)
        
        # Run message loop for a few seconds
        start_time = time.time()
        msg = wintypes.MSG()
        while time.time() - start_time < 3.0:
            if user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)

if __name__ == "__main__":
    main()
