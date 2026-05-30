import win32api
import win32con
import win32gui
from win32com.shell import shell, shellcon

def main():
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = win32gui.DefWindowProc
    wc.lpszClassName = "Notify"
    wc.hInstance = win32api.GetModuleHandle(None)
    class_atom = win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindow(class_atom, "N", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)
    
    pidl = shell.SHGetSpecialFolderLocation(0, shellcon.CSIDL_DESKTOP)
    print("Calling SHChangeNotifyRegister...")
    try:
        # Tuple definition in pywin32: (PIDL, bRecursive) -> represented as a 2-tuple inside the list.
        notify_id = shell.SHChangeNotifyRegister(hwnd, shellcon.SHCNRF_InterruptLevel | shellcon.SHCNRF_ShellLevel, shellcon.SHCNE_CREATE, win32con.WM_USER + 1, [ (pidl, True) ])
        print("Success 1!", notify_id)
    except Exception as e:
        print("Error 1:", repr(e))
        
    try:
        # What if it's just a single tuple?
        notify_id = shell.SHChangeNotifyRegister(hwnd, shellcon.SHCNRF_InterruptLevel | shellcon.SHCNRF_ShellLevel, shellcon.SHCNE_CREATE, win32con.WM_USER + 1, (pidl, True))
        print("Success 2!", notify_id)
    except Exception as e:
        print("Error 2:", repr(e))

main()
