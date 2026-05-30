import win32api
import win32con
import win32gui
from win32com.shell import shell, shellcon

def main():
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = win32gui.DefWindowProc
    wc.lpszClassName = "NotifyDrives"
    wc.hInstance = win32api.GetModuleHandle(None)
    class_atom = win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindow(class_atom, "N", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)
    
    pidl = shell.SHGetSpecialFolderLocation(0, shellcon.CSIDL_DRIVES)
    print("Calling SHChangeNotifyRegister for CSIDL_DRIVES...")
    try:
        notify_id = shell.SHChangeNotifyRegister(hwnd, shellcon.SHCNRF_InterruptLevel | shellcon.SHCNRF_ShellLevel, shellcon.SHCNE_CREATE, win32con.WM_USER + 1, (pidl, True))
        print("Success!", notify_id)
    except Exception as e:
        print("Error:", repr(e))

main()
