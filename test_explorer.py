import win32com.client
import win32gui
import time
import os

def get_active_explorer_path():
    hwnd = win32gui.GetForegroundWindow()
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        for window in shell.Windows():
            if int(window.HWND) == hwnd:
                doc = window.Document
                if doc:
                    return doc.Folder.Self.Path
    except Exception as e:
        print("COM error:", e)
        
    desktop_hwnd = win32gui.GetDesktopWindow()
    if hwnd == desktop_hwnd or win32gui.GetClassName(hwnd) in ("Progman", "WorkerW"):
        return os.path.join(os.path.expanduser("~"), "Desktop")
        
    return None

print("Please click on an open folder in Windows Explorer within the next 5 seconds...")
time.sleep(5)
path = get_active_explorer_path()
print("Active Explorer Path:", path)
