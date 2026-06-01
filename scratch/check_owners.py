import win32ts
import win32api
import win32con
import win32security
import sys

def get_process_owner(pid):
    try:
        hproc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
        htok = win32security.OpenProcessToken(hproc, win32con.TOKEN_QUERY)
        owner_sid, _ = win32security.GetTokenInformation(htok, win32security.TokenUser)
        name, domain, _ = win32security.LookupAccountSid(None, owner_sid)
        win32api.CloseHandle(htok)
        win32api.CloseHandle(hproc)
        return f"{domain}\\{name}"
    except Exception as e:
        return "Unknown"

procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
for p in procs:
    name = p[2]
    if 'remotedesktop' in name.lower():
        pid = p[1]
        session_id = p[0]
        owner = get_process_owner(pid)
        print(f"PID: {pid} | Name: {name} | Session: {session_id} | Owner: {owner}")
