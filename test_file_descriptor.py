import ctypes
from ctypes import wintypes
import win32con
import win32gui
import threading
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Use ctypes to register clipboard formats
RegisterClipboardFormatW = user32.RegisterClipboardFormatW
RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
RegisterClipboardFormatW.restype = wintypes.UINT

cf_file_group_descriptor = RegisterClipboardFormatW("FileGroupDescriptorW")
cf_file_contents = RegisterClipboardFormatW("FileContents")

# Define Structures
class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD)]

class FILEDESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("dwFlags", wintypes.DWORD),
        ("clsid", ctypes.c_byte * 16),
        ("sizel", wintypes.DWORD * 2),
        ("pointl", wintypes.DWORD * 2),
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", FILETIME),
        ("ftLastAccessTime", FILETIME),
        ("ftLastWriteTime", FILETIME),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("cFileName", wintypes.WCHAR * 260)
    ]

class FILEGROUPDESCRIPTOR(ctypes.Structure):
    _fields_ = [
        ("cItems", wintypes.UINT),
        ("fgd", FILEDESCRIPTOR * 1)
    ]

kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
user32.SetClipboardData.restype = ctypes.c_void_p

def create_file_descriptor():
    fgd = FILEGROUPDESCRIPTOR()
    fgd.cItems = 1
    
    fgd.fgd[0].dwFlags = 0x00000044 
    fgd.fgd[0].dwFileAttributes = 0x00000080 
    fgd.fgd[0].nFileSizeHigh = 0
    fgd.fgd[0].nFileSizeLow = 15 
    fgd.fgd[0].cFileName = "TestDelayRender.txt"
    
    total_size = ctypes.sizeof(FILEGROUPDESCRIPTOR)
    hGlobal = kernel32.GlobalAlloc(0x0042, total_size) 
    pGlobal = kernel32.GlobalLock(hGlobal)
    ctypes.memmove(pGlobal, ctypes.addressof(fgd), total_size)
    kernel32.GlobalUnlock(hGlobal)
    return hGlobal

def create_file_contents():
    print(">>> Explorer requested the file content! Delay Render triggered! <<<")
    content = b"Hello World! :D"
    hGlobal = kernel32.GlobalAlloc(0x0042, len(content))
    pGlobal = kernel32.GlobalLock(hGlobal)
    ctypes.memmove(pGlobal, content, len(content))
    kernel32.GlobalUnlock(hGlobal)
    return hGlobal

def wnd_proc(hwnd, msg, wparam, lparam):
    if msg == win32con.WM_RENDERFORMAT:
        print(f"Received WM_RENDERFORMAT for format {wparam}")
        if wparam == cf_file_contents:
            print("Providing FileContents...")
            hGlobal = create_file_contents()
            user32.SetClipboardData(cf_file_contents, hGlobal)
            return 0
    elif msg == win32con.WM_RENDERALLFORMATS:
        print("Received WM_RENDERALLFORMATS")
        user32.OpenClipboard(hwnd)
        user32.EmptyClipboard()
        user32.CloseClipboard()
        return 0
    elif msg == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

def clipboard_server():
    wc = win32gui.WNDCLASS()
    wc.lpszClassName = "DelayRenderTestClass"
    wc.lpfnWndProc = wnd_proc
    class_atom = win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindow(class_atom, "DelayRenderTest", 0, 0, 0, 0, 0, 0, 0, 0, None)
    
    print("Setting clipboard with Delay Render...")
    user32.OpenClipboard(hwnd)
    user32.EmptyClipboard()
    
    hFGD = create_file_descriptor()
    user32.SetClipboardData(cf_file_group_descriptor, hFGD)
    
    user32.SetClipboardData(cf_file_contents, None)
    
    user32.CloseClipboard()
    print("Clipboard ready. Go right-click Paste on your Desktop!")
    
    win32gui.PumpMessages()

if __name__ == "__main__":
    t = threading.Thread(target=clipboard_server)
    t.daemon = True
    t.start()
    
    print("Waiting 30 seconds for you to test...")
    time.sleep(30)
