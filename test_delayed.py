import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
kernel32.SetLastError.argtypes = [wintypes.DWORD]

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p

if user32.OpenClipboard(None):
    user32.EmptyClipboard()
    
    # Register exclusion formats
    cf_exclude = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
    if cf_exclude:
        hMem = kernel32.GlobalAlloc(0x0002, 4)
        if hMem:
            ptr = kernel32.GlobalLock(hMem)
            if ptr:
                ctypes.memmove(ptr, ctypes.byref(wintypes.DWORD(1)), 4)
                kernel32.GlobalUnlock(hMem)
                user32.SetClipboardData(cf_exclude, hMem)
                print("Exclude format registered")
                
    # Clear error and call SetClipboardData with NULL for delayed rendering
    kernel32.SetLastError(0)
    res = user32.SetClipboardData(15, None)
    err = ctypes.GetLastError()
    print("SetClipboardData CF_HDROP result:", res, "GetLastError:", err)
    
    user32.CloseClipboard()
    print("Clipboard closed.")
else:
    print("Failed to open clipboard.")
