import ctypes
from ctypes import wintypes
user32 = ctypes.windll.user32

def test_uipi():
    try:
        WM_CLIPBOARDUPDATE = 0x031D
        MSGFLT_ALLOW = 1
        res = user32.ChangeWindowMessageFilterEx(None, WM_CLIPBOARDUPDATE, MSGFLT_ALLOW, None)
        print("ChangeWindowMessageFilterEx with None HWND:", res)
    except Exception as e:
        print("Error:", e)

test_uipi()
