import tkinter as tk
import ctypes
from ctypes import wintypes
import time

CF_HDROP = 15
WM_RENDERFORMAT = 0x0305
user32 = ctypes.windll.user32
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

root = tk.Tk()
root.title("Delay Render Test")
hwnd = int(root.winfo_id())

print(f"HWND: {hwnd}")

# Subclass
import platform
if platform.architecture()[0] == '64bit':
    SetWindowLong = user32.SetWindowLongPtrW
    SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    SetWindowLong.restype = ctypes.c_void_p
else:
    SetWindowLong = user32.SetWindowLongW
    SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
    SetWindowLong.restype = ctypes.c_void_p

CallWindowProc = user32.CallWindowProcW
CallWindowProc.argtypes = [ctypes.c_void_p, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
CallWindowProc.restype = ctypes.c_void_p

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_void_p, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)

old_wndproc = None
def wndproc(hw, msg, wp, lp):
    if msg == WM_RENDERFORMAT:
        print(f"!!! WM_RENDERFORMAT CALLED FOR FORMAT {wp} !!!")
        # Just return 0 to fail it for now
        return 0
    return CallWindowProc(old_wndproc, hw, msg, wp, lp)

new_wndproc_c = WNDPROC(wndproc)
old_wndproc = SetWindowLong(hwnd, -4, ctypes.cast(new_wndproc_c, ctypes.c_void_p))

if user32.OpenClipboard(hwnd):
    user32.EmptyClipboard()
    user32.SetClipboardData(CF_HDROP, None)
    user32.CloseClipboard()
    print("SetClipboardData Delay Render OK")

root.mainloop()
