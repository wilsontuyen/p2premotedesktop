import ctypes
import ctypes.wintypes as wintypes
import threading
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_CLIPBOARDUPDATE = 0x031D
HWND_MESSAGE = -3

WNDPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)

class WNDCLASSEX(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint),
                ("style", ctypes.c_uint),
                ("lpfnWndProc", WNDPROCTYPE),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm", wintypes.HICON)]

class ClipboardListener:
    def __init__(self, callback):
        self.callback = callback
        self.hwnd = None
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_CLIPBOARDUPDATE:
            print("WM_CLIPBOARDUPDATE received!")
            self.callback()
            return 0
        user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = ctypes.c_long
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run(self):
        user32.CreateWindowExW.argtypes = [
            ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
            ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        
        wndproc = WNDPROCTYPE(self._wndproc)
        
        wndclass = WNDCLASSEX()
        wndclass.cbSize = ctypes.sizeof(WNDCLASSEX)
        wndclass.lpfnWndProc = wndproc
        wndclass.lpszClassName = "HiddenClipboardListener"
        kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        wndclass.hInstance = kernel32.GetModuleHandleW(None)
        
        user32.RegisterClassExW(ctypes.byref(wndclass))
        
        self.hwnd = user32.CreateWindowExW(
            0,
            wndclass.lpszClassName,
            "HiddenWindow",
            0, 0, 0, 0, 0,
            HWND_MESSAGE, 0, wndclass.hInstance, 0
        )
        
        print("Window created, hwnd:", self.hwnd)
        user32.AddClipboardFormatListener(self.hwnd)
        
        msg = wintypes.MSG()
        # Message loop
        while self.running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
            
        print("Stopping listener...")
        user32.RemoveClipboardFormatListener(self.hwnd)
        user32.DestroyWindow(self.hwnd)
        user32.UnregisterClassW(wndclass.lpszClassName, wndclass.hInstance)

def on_clipboard_change():
    print("Clipboard changed!")

if __name__ == "__main__":
    listener = ClipboardListener(on_clipboard_change)
    print("Listening for 15 seconds. Try copying something!")
    time.sleep(15)
    listener.running = False
    print("Done")
