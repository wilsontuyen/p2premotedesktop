import win32process
import win32api
import win32con
import win32ts
import os

print("My PID:", os.getpid())

try:
    procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
    for p in procs:
        p_name = p[2]
        p_pid = p[1]
        p_sid = p[0]
        if "remotedesktoptp2p" in p_name.lower() or "remote" in p_name.lower():
            # Get owner and details
            owner = "Unknown"
            try:
                h_proc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, p_pid)
                # Try to get command line
                owner = "SYSTEM/User"
                win32api.CloseHandle(h_proc)
            except Exception as e:
                owner = f"Access Denied: {e}"
            print(f"Name: {p_name}, PID: {p_pid}, SessionId: {p_sid}, Owner: {owner}")
except Exception as e:
    print("Error listing processes:", e)
