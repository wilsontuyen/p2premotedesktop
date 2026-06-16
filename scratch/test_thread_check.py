import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

curr_thread = kernel32.GetCurrentThreadId()
print("Current Thread ID:", curr_thread)

# Create a dummy window
class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HICON),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR)
    ]

# Setup WNDPROC callback
WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_int64, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
def wndproc(hwnd, msg, wp, lp):
    return user32.DefWindowProcW(hwnd, msg, wp, lp)

callback = WNDPROC(wndproc)

wc = WNDCLASSW()
wc.lpfnWndProc = ctypes.cast(callback, ctypes.c_void_p)
wc.lpszClassName = "TestClass"
wc.hInstance = kernel32.GetModuleHandleW(None)

user32.RegisterClassW(ctypes.byref(wc))
hwnd = user32.CreateWindowExW(0, "TestClass", "TestWindow", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)
print("HWND created:", hwnd)

win_thread = user32.GetWindowThreadProcessId(hwnd, None)
print("Window Thread ID:", win_thread)
print("Matches current thread:", win_thread == curr_thread)
