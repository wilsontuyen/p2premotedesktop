import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]

user32.OpenClipboard(None)
user32.EmptyClipboard()
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
res = user32.SetClipboardData(15, None)
err = ctypes.GetLastError()
print("SetClipboardData CF_HDROP:", res, "Err:", err)

cf_drop_effect = user32.RegisterClipboardFormatW("Preferred DropEffect")
if cf_drop_effect:
    hMem = kernel32.GlobalAlloc(0x0002, 4)
    if hMem:
        ptr = kernel32.GlobalLock(hMem)
        if ptr:
            ctypes.memmove(ptr, ctypes.byref(wintypes.DWORD(5)), 4) # 5 = DROPEFFECT_COPY
            kernel32.GlobalUnlock(hMem)
            user32.SetClipboardData(cf_drop_effect, ctypes.c_void_p(hMem))
            print("Preferred DropEffect set")

user32.CloseClipboard()
print("Clipboard configured for delayed rendering. Check if Paste is active in Explorer.")
time.sleep(10)
