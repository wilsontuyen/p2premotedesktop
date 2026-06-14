import ctypes
from ctypes import wintypes
import time
import threading

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def wndproc(hwnd, msg, wparam, lparam):
    if msg == 0x0400 + 101:
        if not user32.OpenClipboard(hwnd):
            print("Open failed")
            return 0
        user32.EmptyClipboard()
        res = user32.SetClipboardData(15, 0)
        print("SetClipboardData CF_HDROP:", res, "LastError:", ctypes.GetLastError())
        user32.CloseClipboard()
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

def test_clipboard():
    wndclass = wintypes.WNDCLASSW()
    wndclass.lpfnWndProc = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)(wndproc)
    wndclass.lpszClassName = "TestClip"
    user32.RegisterClassW(ctypes.byref(wndclass))
    
    hwnd = user32.CreateWindowExW(0, "TestClip", "TestClip", 0, 0, 0, 0, 0, 0, 0, 0, 0)
    print("HWND:", hwnd)
    
    user32.PostMessageW(hwnd, 0x0400 + 101, 0, 0)
    
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
        if msg.message == 0x0400 + 101:
            break

test_clipboard()
