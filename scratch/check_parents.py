import win32ts
import win32api
import win32con
import win32security
import sys

def get_process_info(pid):
    try:
        hproc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
        # We can try to query parent process ID using NtQueryInformationProcess or wmic
        # Let's just get owner
        htok = win32security.OpenProcessToken(hproc, win32con.TOKEN_QUERY)
        owner_sid, _ = win32security.GetTokenInformation(htok, win32security.TokenUser)
        name, domain, _ = win32security.LookupAccountSid(None, owner_sid)
        win32api.CloseHandle(htok)
        win32api.CloseHandle(hproc)
        owner = f"{domain}\\{name}"
    except Exception:
        owner = "Unknown"
    
    # Try to get command line and parent process via wmic
    try:
        import subprocess
        out = subprocess.check_output(f'wmic process where "ProcessID={pid}" get ParentProcessId,CommandLine', shell=True)
        lines = out.decode('utf-8', errors='ignore').strip().split('\n')
        if len(lines) > 1:
            parts = lines[1].split()
            ppid = parts[-1]
            cmd = " ".join(parts[:-1])
            return owner, ppid, cmd
    except Exception:
        pass
    return owner, "Unknown", "Unknown"

procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
for p in procs:
    name = p[2]
    if 'remotedesktop' in name.lower():
        pid = p[1]
        owner, ppid, cmd = get_process_info(pid)
        print(f"PID: {pid} | Name: {name} | Parent: {ppid} | Owner: {owner} | Cmd: {cmd}")
