import ctypes
from ctypes import wintypes
import time

CF_HDROP = 15
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE

# Clear last error
kernel32.SetLastError(0)

print("Opening clipboard...")
if user32.OpenClipboard(None):
    try:
        user32.EmptyClipboard()
        # Set last error to 0 first
        kernel32.SetLastError(0)
        res = user32.SetClipboardData(CF_HDROP, None)
        err = kernel32.GetLastError()
        print(f"SetClipboardData returned: {res}, GetLastError: {err}")
    finally:
        user32.CloseClipboard()
else:
    print("Failed to open clipboard")
