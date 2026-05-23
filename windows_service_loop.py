import win32ts
import win32api
import win32con
import win32process
import win32security
import sys
import os
import time
import traceback

app_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(app_dir, "service.log")

def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}\n"
    print(log_line, end="")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line)
    except:
        pass

def find_winlogon_pid(session_id):
    try:
        procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
        for p in procs:
            if p[0] == session_id and p[2].lower() == "winlogon.exe":
                return p[1]
    except Exception as e:
        log(f"Error enumerating processes: {e}")
    return None

def get_executable_to_run():
    # Prefer compiled standalone Nuitka binary
    candidates = [
        os.path.join(app_dir, "dist_standalone", "app.dist", "RemoteDesktopP2P.exe"),
        os.path.join(app_dir, "dist", "RemoteDesktopP2P", "RemoteDesktopP2P.exe"),
        os.path.join(app_dir, "dist", "app.exe"),
        os.path.join(app_dir, "RemoteDesktopP2P.exe"),
        os.path.join(app_dir, "app.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            log(f"Found compiled executable for agent: {c}")
            return c, f'"{c}" --headless'

    # Fallback to source
    python_exe = os.path.join(app_dir, ".venv", "Scripts", "python.exe")
    app_py = os.path.join(app_dir, "app.py")
    if os.path.exists(python_exe) and os.path.exists(app_py):
        log(f"Fallback to Python source execution for agent using: {python_exe}")
        return python_exe, f'"{python_exe}" "{app_py}" --headless'

    log("Error: No executable or source app.py found!")
    return None, None

def spawn_agent(session_id, is_logged_in):
    exe_path, cmd_line = get_executable_to_run()
    if not exe_path:
        return None

    h_token = None
    desktop = "winsta0\\default"

    if is_logged_in:
        try:
            h_token = win32ts.WTSQueryUserToken(session_id)
            desktop = "winsta0\\default"
            log(f"Targeting active user desktop for session {session_id}")
        except Exception as e:
            log(f"Failed to query user token: {e}")

    if not h_token:
        # Duplicate winlogon token (lock screen)
        winlogon_pid = find_winlogon_pid(session_id)
        if not winlogon_pid:
            log(f"winlogon.exe not found in session {session_id}. Cannot run agent.")
            return None

        try:
            # Enable SeDebugPrivilege
            h_process_self = win32api.GetCurrentProcess()
            h_token_self = win32security.OpenProcessToken(
                h_process_self, win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY
            )
            privs = [(win32security.LookupPrivilegeValue(None, win32security.SE_DEBUG_NAME), win32security.SE_PRIVILEGE_ENABLED)]
            win32security.AdjustTokenPrivileges(h_token_self, False, privs)
            win32api.CloseHandle(h_token_self)

            # Open winlogon and its token
            h_winlogon = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, winlogon_pid
            )
            h_token = win32security.OpenProcessToken(
                h_winlogon, win32con.TOKEN_DUPLICATE | win32con.TOKEN_QUERY | win32con.TOKEN_ASSIGN_PRIMARY
            )
            win32api.CloseHandle(h_winlogon)
            desktop = "winsta0\\winlogon"
            log(f"Targeting lock screen desktop (Winlogon) for session {session_id}")
        except Exception as e:
            log(f"Failed to acquire Winlogon token: {e}")
            return None

    if h_token:
        try:
            h_token_dup = win32security.DuplicateTokenEx(
                h_token,
                win32security.SecurityImpersonation,
                win32con.TOKEN_ALL_ACCESS,
                win32security.TokenPrimary
            )
            win32api.CloseHandle(h_token)

            startup_info = win32process.STARTUPINFO()
            startup_info.lpDesktop = desktop

            # Run process in active user session context
            h_process, h_thread, dwProcessId, dwThreadId = win32process.CreateProcessAsUser(
                h_token_dup,
                exe_path,
                cmd_line,
                None,
                None,
                False,
                win32con.NORMAL_PRIORITY_CLASS | win32process.CREATE_NO_WINDOW,
                None,
                None,
                startup_info
            )
            win32api.CloseHandle(h_process)
            win32api.CloseHandle(h_thread)
            win32api.CloseHandle(h_token_dup)

            log(f"Agent successfully spawned with PID {dwProcessId} on {desktop}")
            return dwProcessId
        except Exception as e:
            log(f"CreateProcessAsUser failed: {e}")
    return None

def main():
    log("Easy Remote Desktop Agent service loop started.")
    current_agent_pid = None
    last_session_id = None
    last_was_logged_in = None

    while True:
        try:
            active_session_id = win32ts.WTSGetActiveConsoleSessionId()
            if active_session_id == 0xFFFFFFFF or active_session_id == -1:
                time.sleep(5)
                continue

            # Check if user is logged in
            h_token = None
            is_logged_in = False
            try:
                h_token = win32ts.WTSQueryUserToken(active_session_id)
                is_logged_in = True
                win32api.CloseHandle(h_token)
            except Exception:
                pass

            state_changed = (last_session_id != active_session_id or 
                             last_was_logged_in != is_logged_in)

            if state_changed:
                log(f"Session state changed: SessionId={active_session_id}, LoggedIn={is_logged_in}")
                
                # Kill current agent
                if current_agent_pid:
                    log(f"Killing current agent with PID {current_agent_pid}")
                    try:
                        h_proc = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, current_agent_pid)
                        win32api.TerminateProcess(h_proc, 0)
                        win32api.CloseHandle(h_proc)
                    except Exception as e:
                        log(f"Failed to kill agent: {e}")
                    current_agent_pid = None

                last_session_id = active_session_id
                last_was_logged_in = is_logged_in

            # Check if agent is running
            agent_running = False
            if current_agent_pid:
                try:
                    h_proc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, current_agent_pid)
                    code = win32process.GetExitCodeProcess(h_proc)
                    win32api.CloseHandle(h_proc)
                    agent_running = (code == win32con.STILL_ACTIVE)
                except Exception:
                    pass

            if not agent_running:
                pid = spawn_agent(active_session_id, is_logged_in)
                if pid:
                    current_agent_pid = pid

        except Exception as e:
            log(f"Error in main loop: {e}\n{traceback.format_exc()}")

        time.sleep(5)

if __name__ == '__main__':
    main()
