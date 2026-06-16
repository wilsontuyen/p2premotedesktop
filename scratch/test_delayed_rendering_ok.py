import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Set up type definitions
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL

user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL

user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL

user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE

user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
user32.IsClipboardFormatAvailable.restype = wintypes.BOOL

opened = user32.OpenClipboard(None)
print("OpenClipboard:", opened)
if opened:
    empty = user32.EmptyClipboard()
    print("EmptyClipboard:", empty)
    
    res = user32.SetClipboardData(15, None)
    err = ctypes.GetLastError()
    print("SetClipboardData CF_HDROP result:", res, "Err:", err)
    
    avail = user32.IsClipboardFormatAvailable(15)
    print("Is CF_HDROP available:", avail)
    
    user32.CloseClipboard()
