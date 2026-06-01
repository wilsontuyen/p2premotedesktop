import win32ts
import win32api
import win32con
import win32process
import win32security
import win32event
import sys
import os
import time
import traceback

if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
    try: sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    except: pass
if sys.stderr is not None and hasattr(sys.stderr, 'reconfigure'):
    try: sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    except: pass

# Determine the application directory robustly across source execution, Nuitka standalone, and Nuitka onefile.
app_dir = os.environ.get("NUITKA_ONEFILE_DIRECTORY")
if not app_dir:
    if getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__'):
        exe_path = sys.argv[0] if (sys.argv and sys.argv[0]) else sys.executable
        app_dir = os.path.dirname(os.path.abspath(exe_path))
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(app_dir, "service.log")

def log(msg):
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {msg}\n"
        try:
            print(log_line, end="")
        except:
            pass
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_line)
    except:
        pass

def is_logon_ui_running(session_id):
    try:
        procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
        for p in procs:
            if p[0] == session_id and p[2].lower() == "logonui.exe":
                return True
    except Exception as e:
        log(f"Error checking LogonUI: {e}")
    return False

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
        os.path.join(app_dir, "dist_nuitka", "app.dist", "RemoteDesktopP2P.exe"),
        os.path.join(app_dir, "dist", "RemoteDesktopP2P.exe"),
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

def spawn_agent(session_id, is_logged_in, is_screen_locked):
    exe_path, cmd_line = get_executable_to_run()
    if not exe_path:
        return None

    h_token = None
    desktop = "winsta0\\default"

    # We ALWAYS use the winlogon token to run the agent as SYSTEM in the user session.
    # This allows the agent to dynamically switch between desktops (winsta0\default and winsta0\winlogon)
    # and control administrative apps / UAC prompts without permission blocks.
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
        
        # Target appropriate initial desktop based on active state
        if is_screen_locked:
            desktop = "winsta0\\winlogon"
            log(f"Targeting lock screen desktop (Winlogon) for session {session_id} using SYSTEM token")
        else:
            desktop = "winsta0\\default"
            log(f"Targeting default user desktop for session {session_id} using SYSTEM token")
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

            # Run process in active user session context with correct working directory
            h_process, h_thread, dwProcessId, dwThreadId = win32process.CreateProcessAsUser(
                h_token_dup,
                exe_path,
                cmd_line,
                None,
                None,
                False,
                win32con.NORMAL_PRIORITY_CLASS | win32process.CREATE_NO_WINDOW,
                None,
                os.path.dirname(exe_path),
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

def spawn_clipboard_agent(session_id):
    """
    Spawn Clipboard Agent ở quyền User thường (sử dụng WTSQueryUserToken).
    Dùng chính RemoteDesktopP2P.exe với flag --clipboard-agent.
    Agent này lắng nghe Named Pipe và nạp file vào Clipboard.
    """
    exe_path, cmd_line = get_executable_to_run()
    if not exe_path:
        return None
    
    cmd_line = cmd_line.replace("--headless", "--clipboard-agent")

    h_user_token = None
    try:
        h_user_token = win32ts.WTSQueryUserToken(session_id)
    except Exception as e:
        log(f"Failed to query user token for Clipboard Agent (session {session_id}): {e}")
        return None

    if h_user_token:
        try:
            h_token_dup = win32security.DuplicateTokenEx(
                h_user_token,
                win32security.SecurityImpersonation,
                win32con.TOKEN_ALL_ACCESS,
                win32security.TokenPrimary
            )
            win32api.CloseHandle(h_user_token)

            startup_info = win32process.STARTUPINFO()
            startup_info.lpDesktop = "winsta0\\default"

            h_process, h_thread, dwProcessId, dwThreadId = win32process.CreateProcessAsUser(
                h_token_dup,
                exe_path,
                cmd_line,
                None,
                None,
                False,
                win32con.NORMAL_PRIORITY_CLASS | win32process.CREATE_NO_WINDOW,
                None,
                os.path.dirname(exe_path),
                startup_info
            )
            win32api.CloseHandle(h_process)
            win32api.CloseHandle(h_thread)
            win32api.CloseHandle(h_token_dup)

            log(f"Clipboard Agent spawned with PID {dwProcessId} on winsta0\\default (User privilege)")
            return dwProcessId
        except Exception as e:
            log(f"CreateProcessAsUser for Clipboard Agent failed: {e}")
    return None

def trigger_sas_system():
    try:
        import winreg
        import ctypes
        
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", 0, winreg.KEY_ALL_ACCESS)
        except WindowsError:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "SoftwareSASGeneration", 0, winreg.REG_DWORD, 3)
        winreg.CloseKey(key)
        log("Configured SoftwareSASGeneration = 3 in registry.")
    except Exception as e:
        log(f"Error configuring SoftwareSASGeneration in service: {e}")

    try:
        h_process = win32api.GetCurrentProcess()
        h_token = win32security.OpenProcessToken(
            h_process, win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY
        )
        privs = []
        for priv_name in [win32security.SE_TCB_NAME, win32security.SE_DEBUG_NAME]:
            try:
                luid = win32security.LookupPrivilegeValue(None, priv_name)
                privs.append((luid, win32security.SE_PRIVILEGE_ENABLED))
            except:
                pass
        if privs:
            win32security.AdjustTokenPrivileges(h_token, False, privs)
        win32api.CloseHandle(h_token)
        log("Adjusted token privileges for SeTcbPrivilege in service.")
    except Exception as priv_err:
        log(f"Failed to adjust privilege in Service: {priv_err}")

    try:
        sas_dll = ctypes.windll.LoadLibrary("sas.dll")
        sas_dll.SendSAS.argtypes = [ctypes.c_int]
        sas_dll.SendSAS.restype = None
        sas_dll.SendSAS(0)
        log("SendSAS(0) executed successfully from Session 0 Service.")
    except Exception as e:
        log(f"Error calling SendSAS in service: {e}")

def spawn_taskmgr_system():
    try:
        active_session_id = win32ts.WTSGetActiveConsoleSessionId()
        if active_session_id == 0xFFFFFFFF or active_session_id == -1:
            return

        is_screen_locked = is_logon_ui_running(active_session_id)
        desktop = "winsta0\\winlogon" if is_screen_locked else "winsta0\\default"

        winlogon_pid = find_winlogon_pid(active_session_id)
        if not winlogon_pid:
            return

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

        if h_token:
            h_token_dup = win32security.DuplicateTokenEx(
                h_token,
                win32security.SecurityImpersonation,
                win32con.TOKEN_ALL_ACCESS,
                win32security.TokenPrimary
            )
            win32api.CloseHandle(h_token)

            startup_info = win32process.STARTUPINFO()
            startup_info.lpDesktop = desktop

            sys32 = os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32")
            taskmgr_exe = os.path.join(sys32, "taskmgr.exe")
            if not os.path.exists(taskmgr_exe):
                taskmgr_exe = "taskmgr.exe"

            h_process, h_thread, dwProcessId, dwThreadId = win32process.CreateProcessAsUser(
                h_token_dup,
                None,
                taskmgr_exe,
                None,
                None,
                False,
                win32con.NORMAL_PRIORITY_CLASS,
                None,
                sys32,
                startup_info
            )
            win32api.CloseHandle(h_process)
            win32api.CloseHandle(h_thread)
            win32api.CloseHandle(h_token_dup)
            log(f"Task Manager successfully spawned with PID {dwProcessId} on {desktop} as SYSTEM")
    except Exception as e:
        log(f"Failed to spawn Task Manager: {e}")

def service_events_listener_thread():
    # Setup security attributes with NULL DACL to allow user processes to trigger
    sa = win32security.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = 1
    sd = win32security.SECURITY_DESCRIPTOR()
    sd.Initialize()
    sd.SetSecurityDescriptorDacl(True, None, False)
    sa.SECURITY_DESCRIPTOR = sd

    try:
        h_sas_event = win32event.CreateEvent(sa, False, False, "Global\\AntigravityP2P_SAS_Event")
        h_taskmgr_event = win32event.CreateEvent(sa, False, False, "Global\\AntigravityP2P_TaskMgr_Event")
    except Exception as e:
        log(f"Failed to create events: {e}")
        return

    log("Service Events Listener Thread started and waiting...")
    handles = [h_sas_event, h_taskmgr_event]
    while True:
        rc = win32event.WaitForMultipleObjects(handles, False, win32event.INFINITE)
        if rc == win32event.WAIT_OBJECT_0:
            log("Received SAS event signal from Agent. Triggering SendSAS.")
            trigger_sas_system()
        elif rc == win32event.WAIT_OBJECT_0 + 1:
            log("Received TaskMgr event signal from Agent. Triggering Task Manager.")
            spawn_taskmgr_system()

def terminate_process_with_pid(pid):
    if not pid:
        return
    log(f"Attempting to terminate process {pid}")
    try:
        h_process_self = win32api.GetCurrentProcess()
        h_token_self = win32security.OpenProcessToken(
            h_process_self, win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY
        )
        privs = [(win32security.LookupPrivilegeValue(None, win32security.SE_DEBUG_NAME), win32security.SE_PRIVILEGE_ENABLED)]
        win32security.AdjustTokenPrivileges(h_token_self, False, privs)
        win32api.CloseHandle(h_token_self)
    except Exception as e:
        log(f"Failed to enable SeDebugPrivilege for termination: {e}")

    success = False
    try:
        h_proc = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, pid)
        win32api.TerminateProcess(h_proc, 0)
        win32api.CloseHandle(h_proc)
        log(f"Terminated process {pid} via Windows API.")
        success = True
    except Exception as e:
        log(f"Failed to kill agent {pid} via Windows API: {e}")

    if not success:
        try:
            import subprocess
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log(f"Terminated process {pid} via taskkill.")
            success = True
        except Exception as e:
            log(f"Failed to kill agent {pid} via taskkill: {e}")

def is_process_alive(pid):
    """Check if a process with the given PID is still running."""
    if not pid:
        return False
    try:
        h_proc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
        if h_proc:
            exit_code = win32process.GetExitCodeProcess(h_proc)
            win32api.CloseHandle(h_proc)
            # STILL_ACTIVE = 259
            return exit_code == 259
    except Exception:
        pass
    return False

def main():
    log("Easy Remote Desktop Agent service loop started.")
    
    # Clean up any lingering agent processes
    try:
        import subprocess
        subprocess.run("taskkill /F /IM RemoteDesktopP2P.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("Cleaned up lingering RemoteDesktopP2P.exe processes.")
    except Exception as e:
        log(f"Error cleaning up processes on startup: {e}")

    # Start Service Events Listener thread
    import threading
    t = threading.Thread(target=service_events_listener_thread, daemon=True)
    t.start()

    current_agent_pid = None
    clipboard_agent_pid = None
    last_session_id = None

    while True:
        try:
            active_session_id = win32ts.WTSGetActiveConsoleSessionId()
            if active_session_id == 0xFFFFFFFF or active_session_id == -1:
                time.sleep(5)
                continue

            # Check if user is logged in
            is_logged_in = False
            try:
                h_token = win32ts.WTSQueryUserToken(active_session_id)
                is_logged_in = True
                win32api.CloseHandle(h_token)
            except Exception:
                pass

            # Check if screen is locked (LogonUI is running)
            is_screen_locked = is_logon_ui_running(active_session_id)

            # Only kill and respawn the agent if the Windows SESSION ID changes
            # (e.g., fast user switching). Lock/unlock and login transitions are
            # handled dynamically by the agent via OpenInputDesktop + SetThreadDesktop,
            # so we do NOT kill the agent on those events to preserve active connections.
            session_changed = (last_session_id is not None and last_session_id != active_session_id)

            if session_changed:
                log(f"Session ID changed from {last_session_id} to {active_session_id}. Killing agent to switch session.")
                if current_agent_pid:
                    terminate_process_with_pid(current_agent_pid)
                    current_agent_pid = None
                if clipboard_agent_pid:
                    terminate_process_with_pid(clipboard_agent_pid)
                    clipboard_agent_pid = None

            last_session_id = active_session_id

            # Check if the current agent process has died on its own
            if current_agent_pid and not is_process_alive(current_agent_pid):
                log(f"Agent PID {current_agent_pid} is no longer running. Will respawn.")
                current_agent_pid = None

            # Check if agent is running using Mutex (check BOTH desktops)
            agent_running = False
            for desktop_name in ['default', 'winlogon']:
                mutex_name = f"Global\\AntigravityP2PRemoteDesktopAppMutex_1_{active_session_id}_{desktop_name}"
                try:
                    h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, mutex_name)
                    win32api.CloseHandle(h_mutex)
                    agent_running = True
                    break
                except Exception as e:
                    err_code = 0
                    if hasattr(e, 'winerror'):
                        err_code = e.winerror
                    elif hasattr(e, 'args') and len(e.args) > 0:
                        err_code = e.args[0]
                    
                    if err_code != 2: # winerror.ERROR_FILE_NOT_FOUND
                        agent_running = True
                        break

            if not agent_running:
                log(f"No agent mutex found for session {active_session_id}. Spawning new agent. (LoggedIn={is_logged_in}, Locked={is_screen_locked})")
                pid = spawn_agent(active_session_id, is_logged_in, is_screen_locked)
                if pid:
                    current_agent_pid = pid

            # Spawn or check Clipboard Agent (only when user is logged in and not locked)
            if is_logged_in and not is_screen_locked:
                clipboard_agent_running = False
                mutex_name = f"Global\\AntigravityP2PClipboardAgentMutex_{active_session_id}"
                try:
                    h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, mutex_name)
                    win32api.CloseHandle(h_mutex)
                    clipboard_agent_running = True
                except Exception as e:
                    err_code = getattr(e, 'winerror', 0)
                    if err_code != 2:
                        clipboard_agent_running = True
                        
                if not clipboard_agent_running:
                    log(f"No Clipboard Agent mutex found for session {active_session_id}. Spawning new Clipboard Agent.")
                    clipboard_agent_pid = spawn_clipboard_agent(active_session_id)
            else:
                if clipboard_agent_pid:
                    log(f"User logged out or locked. Terminating Clipboard Agent.")
                    terminate_process_with_pid(clipboard_agent_pid)
                    clipboard_agent_pid = None

        except Exception as e:
            log(f"Error in main loop: {e}\n{traceback.format_exc()}")

        time.sleep(1)

if __name__ == '__main__':
    main()
