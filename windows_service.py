import win32serviceutil
import win32service
import win32event
import win32ts
import win32api
import win32con
import win32process
import win32security
import win32timezone
import sys
import os
import time
import traceback
import subprocess

# Setup logging
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
    if os.path.basename(app_dir).lower() == "dist":
        root_dir = os.path.dirname(app_dir)
    else:
        root_dir = app_dir
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = app_dir
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

class EasyRemoteDesktopService(win32serviceutil.ServiceFramework):
    _svc_name_ = "EasyRemoteDesktopService"
    _svc_display_name_ = "Easy Remote Desktop Service"
    _svc_description_ = "Maintains remote desktop connectivity before Windows user logon."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        self.current_agent_pid = None
        self.last_session_id = None
        self.last_was_logged_in = None
        self.last_was_screen_locked = None

    def SvcStop(self):
        log("Stop signal received. Stopping service...")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False
        self.kill_current_agent()

    def SvcDoRun(self):
        log("Service starting...")
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        try:
            self.main_loop()
        except Exception as e:
            log(f"Error in main loop: {e}\n{traceback.format_exc()}")
        log("Service stopped.")

    def kill_current_agent(self):
        if self.current_agent_pid:
            log(f"Killing current agent with PID {self.current_agent_pid}")
            try:
                h_proc = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, self.current_agent_pid)
                win32api.TerminateProcess(h_proc, 0)
                win32api.CloseHandle(h_proc)
            except Exception as e:
                log(f"Failed to kill agent: {e}")
            self.current_agent_pid = None

    def is_agent_running(self):
        if not self.current_agent_pid:
            return False
        try:
            h_proc = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, self.current_agent_pid)
            code = win32process.GetExitCodeProcess(h_proc)
            win32api.CloseHandle(h_proc)
            return code == win32con.STILL_ACTIVE
        except Exception:
            return False

    def is_logon_ui_running(self, session_id):
        try:
            procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
            for p in procs:
                if p[0] == session_id and p[2].lower() == "logonui.exe":
                    return True
        except Exception as e:
            log(f"Error checking LogonUI: {e}")
        return False

    def find_winlogon_pid(self, session_id):
        try:
            procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
            for p in procs:
                if p[0] == session_id and p[2].lower() == "winlogon.exe":
                    return p[1]
        except Exception as e:
            log(f"Error enumerating processes: {e}")
        return None

    def get_executable_to_run(self):
        # Look for executable builds in the dist or workspace folder
        candidates = [
            os.path.join(root_dir, "dist_nuitka", "app.dist", "RemoteDesktopP2P.exe"),
            os.path.join(root_dir, "dist", "RemoteDesktopP2P.exe"),
            os.path.join(root_dir, "dist", "RemoteDesktopP2P", "RemoteDesktopP2P.exe"),
            os.path.join(root_dir, "dist_standalone", "app.dist", "RemoteDesktopP2P.exe"),
            os.path.join(root_dir, "dist", "app.exe"),
            os.path.join(root_dir, "RemoteDesktopP2P.exe"),
            os.path.join(root_dir, "app.exe"),
        ]
        for c in candidates:
            if os.path.exists(c):
                log(f"Found compiled executable: {c}")
                return c, f'"{c}" --headless'

        # Fallback to python source code run
        python_exe = os.path.join(root_dir, ".venv", "Scripts", "python.exe")
        app_py = os.path.join(root_dir, "app.py")
        if os.path.exists(python_exe) and os.path.exists(app_py):
            log(f"Fallback to Python source execution using: {python_exe}")
            return python_exe, f'"{python_exe}" "{app_py}" --headless'

        log("Error: No executable or source app.py found!")
        return None, None

    def main_loop(self):
        while self.running:
            # Check stop event (wait 5000ms)
            rc = win32event.WaitForSingleObject(self.hWaitStop, 5000)
            if rc == win32event.WAIT_OBJECT_0:
                break

            try:
                active_session_id = win32ts.WTSGetActiveConsoleSessionId()
                # If no session is active (e.g. headless boot, RDP disconnected state), skip
                if active_session_id == 0xFFFFFFFF or active_session_id == -1:
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

                # Check if screen is locked (LogonUI is running)
                is_screen_locked = self.is_logon_ui_running(active_session_id)

                # Check if state has changed
                state_changed = (self.last_session_id != active_session_id or 
                                 self.last_was_logged_in != is_logged_in or
                                 self.last_was_screen_locked != is_screen_locked)

                if state_changed:
                    log(f"Session state changed: SessionId={active_session_id}, LoggedIn={is_logged_in}, Locked={is_screen_locked}")
                    self.kill_current_agent()
                    self.last_session_id = active_session_id
                    self.last_was_logged_in = is_logged_in
                    self.last_was_screen_locked = is_screen_locked

                # Start agent if it's not running
                if not self.is_agent_running():
                    self.spawn_agent(active_session_id, is_logged_in, is_screen_locked)

            except Exception as e:
                log(f"Error in checking session: {e}")

    def spawn_agent(self, session_id, is_logged_in, is_screen_locked):
        exe_path, cmd_line = self.get_executable_to_run()
        if not exe_path:
            return

        h_token = None
        desktop = "winsta0\\default"

        # If logged in and NOT locked, target user session
        if is_logged_in and not is_screen_locked:
            try:
                h_token = win32ts.WTSQueryUserToken(session_id)
                desktop = "winsta0\\default"
                log(f"Targeting active user desktop for session {session_id}")
            except Exception as e:
                log(f"Failed to query user token: {e}")

        if not h_token:
            # Duplicate winlogon token (lock screen)
            winlogon_pid = self.find_winlogon_pid(session_id)
            if not winlogon_pid:
                log(f"winlogon.exe not found in session {session_id}. Cannot run agent.")
                return

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
                return

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

                self.current_agent_pid = dwProcessId
                log(f"Agent successfully spawned with PID {dwProcessId} on {desktop}")
            except Exception as e:
                log(f"CreateProcessAsUser failed: {e}")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ['install', 'update', 'remove', 'start', 'stop']:
        win32serviceutil.HandleCommandLine(EasyRemoteDesktopService)
    else:
        import servicemanager
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(EasyRemoteDesktopService)
        servicemanager.StartServiceCtrlDispatcher()
