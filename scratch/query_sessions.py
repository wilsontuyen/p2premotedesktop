import win32ts
import win32api
import win32con
import win32process
import os

def check_sessions():
    active_id = win32ts.WTSGetActiveConsoleSessionId()
    print(f"Active Console Session ID: {active_id}")
    
    try:
        procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
        print("\nAll Winlogon & LogonUI processes:")
        for p in procs:
            sess_id, pid, name = p[0], p[1], p[2]
            if name.lower() in ("winlogon.exe", "logonui.exe", "remotedesktoptp2p.exe", "remotedesktopservice.exe", "app.exe", "windows_service_loop.exe"):
                print(f"Session {sess_id} | PID {pid} | Name: {name}")
    except Exception as e:
        print(f"Error enumerating processes: {e}")

if __name__ == "__main__":
    check_sessions()
