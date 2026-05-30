import win32api
import win32con
import win32gui
import ctypes
from win32com.shell import shell, shellcon

def wndproc(hwnd, msg, wparam, lparam):
    if msg == win32con.WM_USER + 1:
        pidl, event, _ = shell.SHChangeNotification_Lock(wparam, lparam)
        if event == shellcon.SHCNE_CREATE:
            path = shell.SHGetPathFromIDList(pidl[0])
            print(f"File created: {path}")
        shell.SHChangeNotification_Unlock(wparam)
        return 0
    elif msg == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

def main():
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = wndproc
    wc.lpszClassName = "ShellNotifyApp"
    wc.hInstance = win32api.GetModuleHandle(None)
    class_atom = win32gui.RegisterClass(wc)
    
    hwnd = win32gui.CreateWindow(
        class_atom, "Shell Notify", 0,
        0, 0, 0, 0, 0, 0, wc.hInstance, None
    )
    
    pidl = shell.SHGetSpecialFolderLocation(0, shellcon.CSIDL_DESKTOP)
    
    # Register to receive notifications globally
    class SHChangeNotifyEntry(ctypes.Structure):
        _fields_ = [("pidl", ctypes.c_void_p), ("fRecursive", ctypes.c_int)]
        
    notify_id = shell.SHChangeNotifyRegister(
        hwnd,
        shellcon.SHCNRF_InterruptLevel | shellcon.SHCNRF_ShellLevel,
        shellcon.SHCNE_CREATE,
        win32con.WM_USER + 1,
        [(pidl, True)] # True means recursive
    )
    
    print("Listening for file creations. Press Ctrl+C to exit.")
    
    import threading
    def dummy_create():
        import time
        time.sleep(2)
        with open("C:\\Users\\Tuyen\\AppData\\Local\\Temp\\test_notify.txt", "w") as f:
            f.write("test")
        print("Created test file")
        time.sleep(1)
        win32gui.PostMessage(hwnd, win32con.WM_DESTROY, 0, 0)
        
    threading.Thread(target=dummy_create, daemon=True).start()
    
    win32gui.PumpMessages()
    
    shell.SHChangeNotifyDeregister(notify_id)

if __name__ == '__main__':
    main()
