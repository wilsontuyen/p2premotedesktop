import ctypes
import win32gui

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

wc = win32gui.WNDCLASS()
wc.lpfnWndProc = win32gui.DefWindowProc
wc.lpszClassName = "TestClip"
wc.hInstance = kernel32.GetModuleHandleW(None)
class_atom = win32gui.RegisterClass(wc)
hwnd = win32gui.CreateWindow(class_atom, "N", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)

print("HWND:", hwnd)

opened = user32.OpenClipboard(hwnd)
print("OpenClipboard(hwnd):", opened, "LastError:", ctypes.GetLastError())
if opened:
    user32.EmptyClipboard()
    user32.CloseClipboard()
