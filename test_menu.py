import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_CLIPBOARDUPDATE = 0x031D
WM_RENDERFORMAT = 0x0305
WM_DESTROYCLIPBOARD = 0x0307
HWND_MESSAGE = -3

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

class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]

last_rbutton_time = 0

def _mouse_hook_proc(nCode, wParam, lParam):
    global last_rbutton_time
    if nCode >= 0:
        if wParam in (0x0204, 0x0205, 0x00A4, 0x00A5):
            last_rbutton_time = time.time()
            print(f"[Hook] Right click detected at {last_rbutton_time}")
    return user32.CallNextHookEx(None, nCode, wParam, lParam)

def setup_delayed_rendering(hwnd):
    opened = False
    for _ in range(10):
        if user32.OpenClipboard(ctypes.c_void_p(hwnd)):
            opened = True
            break
        time.sleep(0.05)
    if opened:
        user32.EmptyClipboard()
        # CF_HDROP = 15
        user32.SetClipboardData(15, None)
        user32.CloseClipboard()
        print("[Clipboard] Set delayed rendering (CF_HDROP)")
    else:
        print("[Clipboard] Failed to OpenClipboard, error:", ctypes.GetLastError())

def wndproc(hwnd, msg, wparam, lparam):
    if msg == WM_CLIPBOARDUPDATE:
        print("[WndProc] WM_CLIPBOARDUPDATE")
        return 0
    elif msg == WM_RENDERFORMAT:
        if wparam == 15:
            print("\n--- WM_RENDERFORMAT (CF_HDROP) Received ---")
            t_now = time.time()
            dt_hook = t_now - last_rbutton_time
            print(f"Time since mouse hook right-click: {dt_hook:.3f}s")
            
            # 1. FindWindowW #32768
            hwnd_menu = user32.FindWindowW("#32768", None)
            is_visible = user32.IsWindowVisible(hwnd_menu) if hwnd_menu else False
            print(f"FindWindowW('#32768') handle: {hwnd_menu}, IsWindowVisible: {is_visible}")
            
            # 2. GetGUIThreadInfo of foreground window
            hwnd_fg = user32.GetForegroundWindow()
            if hwnd_fg:
                pid = wintypes.DWORD()
                tid = user32.GetWindowThreadProcessId(hwnd_fg, ctypes.byref(pid))
                gui_info = GUITHREADINFO()
                gui_info.cbSize = ctypes.sizeof(GUITHREADINFO)
                if user32.GetGUIThreadInfo(tid, ctypes.byref(gui_info)):
                    print(f"Foreground window thread flags: 0x{gui_info.flags:X} (InMenu: {bool(gui_info.flags & 0x04)}, PopupMode: {bool(gui_info.flags & 0x10)})")
                else:
                    print("GetGUIThreadInfo failed, error:", ctypes.GetLastError())
            else:
                print("No foreground window")
                
            # 3. GetAsyncKeyState VK_RBUTTON
            VK_RBUTTON = 0x02
            state = user32.GetAsyncKeyState(VK_RBUTTON)
            print(f"GetAsyncKeyState(VK_RBUTTON) state: 0x{state:X}")
            
            # 4. Set clipboard data back to None to keep delayed rendering
            user32.SetClipboardData(15, None)
            print("SetClipboardData(15, None) called to keep delayed rendering")
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

def main():
    # Setup kernel32 restypes
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    h_mod = kernel32.GetModuleHandleW(None)
    
    # Setup DefWindowProcW types
    user32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, WPARAM_64, LPARAM_64]
    user32.DefWindowProcW.restype = LRESULT_64

    # Setup CallNextHookEx types
    user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, WPARAM_64, LPARAM_64]
    user32.CallNextHookEx.restype = LRESULT_64

    # Register hook
    HOOKPROC = ctypes.WINFUNCTYPE(LRESULT_64, ctypes.c_int, WPARAM_64, LPARAM_64)
    global hook_callback
    hook_callback = HOOKPROC(_mouse_hook_proc)
    
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HANDLE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HANDLE
    
    mouse_hook = user32.SetWindowsHookExW(14, hook_callback, h_mod, 0)
    print(f"SetWindowsHookExW returned: {mouse_hook}, error: {ctypes.GetLastError()}")
    
    # Create window
    wndproc_ptr = WNDPROCTYPE(wndproc)
    global wndproc_ref
    wndproc_ref = wndproc_ptr
    
    user32.CreateWindowExW.argtypes = [
        ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
        ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
    ]
    user32.CreateWindowExW.restype = ctypes.c_void_p
    
    wndclass = WNDCLASSEX()
    wndclass.cbSize = ctypes.sizeof(WNDCLASSEX)
    wndclass.style = 0
    wndclass.lpfnWndProc = wndproc_ptr
    wndclass.cbClsExtra = 0
    wndclass.cbWndExtra = 0
    wndclass.hInstance = h_mod
    wndclass.hIcon = None
    wndclass.hCursor = None
    wndclass.hbrBackground = None
    wndclass.lpszMenuName = None
    wndclass.lpszClassName = "TestClipboardListener"
    wndclass.hIconSm = None
    
    reg_res = user32.RegisterClassExW(ctypes.byref(wndclass))
    print(f"RegisterClassExW returned: {reg_res}, error: {ctypes.GetLastError()}")
    
    hwnd = user32.CreateWindowExW(0, wndclass.lpszClassName, "TestWindow", 0, 0, 0, 0, 0, ctypes.c_void_p(HWND_MESSAGE), None, h_mod, None)
    print(f"Created HWND: {hwnd}, error: {ctypes.GetLastError()}")
    
    user32.AddClipboardFormatListener(ctypes.c_void_p(hwnd))
    setup_delayed_rendering(hwnd)
    
    print("Listener is running. Please right-click somewhere, and then select Paste (or press Ctrl+V). Press Ctrl+C in this terminal to exit.")
    
    try:
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        if mouse_hook:
            user32.UnhookWindowsHookEx(mouse_hook)
            print("Unhooked mouse hook")
        user32.RemoveClipboardFormatListener(ctypes.c_void_p(hwnd))
        user32.DestroyWindow(ctypes.c_void_p(hwnd))

if __name__ == "__main__":
    main()
