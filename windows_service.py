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

# Determine the application directory robustly across source execution, Nuitka standalone, and Nuitka onefile.
app_dir = os.environ.get("NUITKA_ONEFILE_DIRECTORY")
if not app_dir:
    if getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__'):
        exe_path = sys.argv[0] if (sys.argv and sys.argv[0]) else sys.executable
        app_dir = os.path.dirname(os.path.abspath(exe_path))
        if os.path.basename(app_dir).lower() == "dist":
            root_dir = os.path.dirname(app_dir)
        else:
            root_dir = app_dir
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = app_dir
else:
    root_dir = app_dir
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

def trigger_sas_system():
    try:
        import winreg
        import ctypes
        
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "SoftwareSASGeneration", 0, winreg.REG_DWORD, 3)
            winreg.CloseKey(key)
        except Exception as reg_err:
            log(f"[Service] Failed to set SoftwareSASGeneration: {reg_err}")
            
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
        except Exception as priv_err:
            log(f"[Service] Failed to adjust privilege in Service: {priv_err}")
            
        sas_dll = ctypes.windll.LoadLibrary("sas.dll")
        sas_dll.SendSAS.argtypes = [ctypes.c_int]
        sas_dll.SendSAS.restype = None
        sas_dll.SendSAS(0)
        log("[Service] SendSAS(0) successfully executed.")
    except Exception as sas_err:
        log(f"[Service] Error executing SendSAS in Service: {sas_err}")

class EasyRemoteDesktopService(win32serviceutil.ServiceFramework):
    _svc_name_ = "EasyRemoteDesktopService"
    _svc_display_name_ = "Easy Remote Desktop Service"
    _svc_description_ = "Maintains remote desktop connectivity before Windows user logon."

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.running = True
        self.current_agent_pid = None
        self.clipboard_agent_pid = None
        self.last_session_id = None
        self.last_was_logged_in = None
        self.last_was_screen_locked = None
        self.last_spawn_time = 0.0
        self.spawn_cooldown = 15.0

    def SvcStop(self):
        log("Stop signal received. Stopping service...")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.running = False
        self.kill_current_agent()
        self.kill_clipboard_agent()

    def SvcDoRun(self):
        log("Service starting...")
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        
        # Clean up any lingering agent processes
        try:
            import subprocess
            subprocess.run("taskkill /F /IM RemoteDesktopP2P.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log("Cleaned up lingering RemoteDesktopP2P.exe processes.")
        except Exception as e:
            log(f"Error cleaning up processes on startup: {e}")

        # Start SAS Listener thread using Windows Event
        import threading
        def sas_listener_thread():
            sa = win32security.SECURITY_ATTRIBUTES()
            sa.bInheritHandle = 1
            sd = win32security.SECURITY_DESCRIPTOR()
            sd.Initialize()
            sd.SetSecurityDescriptorDacl(True, None, False)
            sa.SECURITY_DESCRIPTOR = sd

            try:
                h_event = win32event.CreateEvent(sa, False, False, "Global\\AntigravityP2P_SAS_Event")
            except Exception as e:
                log(f"Failed to create SAS event: {e}")
                return

            log("SAS Listener Thread started and waiting on Global\\AntigravityP2P_SAS_Event...")
            while True:
                rc = win32event.WaitForSingleObject(h_event, win32event.INFINITE)
                if rc == win32event.WAIT_OBJECT_0:
                    log("Received SAS event signal from Agent. Triggering SendSAS.")
                    trigger_sas_system()

        t = threading.Thread(target=sas_listener_thread, daemon=True)
        t.start()
        
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

    def kill_clipboard_agent(self):
        if self.clipboard_agent_pid:
            log(f"Killing clipboard agent with PID {self.clipboard_agent_pid}")
            try:
                h_proc = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, self.clipboard_agent_pid)
                win32api.TerminateProcess(h_proc, 0)
                win32api.CloseHandle(h_proc)
            except Exception as e:
                log(f"Failed to kill clipboard agent: {e}")
            self.clipboard_agent_pid = None

    def is_agent_running(self, session_id, is_screen_locked):
        target_desktop = 'winlogon' if is_screen_locked else 'default'
        mutex_name_1 = f"Global\\AntigravityP2PRemoteDesktopAppMutex_1_{session_id}_{target_desktop}"
        mutex_name_2 = f"Global\\AntigravityP2PRemoteDesktopAppMutex_2_{session_id}_{target_desktop}"
        
        for m_name in [mutex_name_1, mutex_name_2]:
            try:
                h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, m_name)
                win32api.CloseHandle(h_mutex)
                return True
            except Exception as e:
                err_code = 0
                if hasattr(e, 'winerror'):
                    err_code = e.winerror
                elif hasattr(e, 'args') and len(e.args) > 0:
                    err_code = e.args[0]
                
                if err_code != 2: # winerror.ERROR_FILE_NOT_FOUND
                    return True
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
            # Check stop event (wait 1000ms)
            rc = win32event.WaitForSingleObject(self.hWaitStop, 1000)
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

                # Check if state has changed (Session ID only).
                # We MUST restart the agent when session ID changes (e.g., RDP or Fast User Switching).
                # But if logon state or screen lock state changes within the same session, 
                # we keep the agent alive so the P2P connection doesn't drop.
                session_changed = (self.last_session_id != active_session_id)

                if session_changed:
                    log(f"Session state changed: SessionId={active_session_id} (Previous: {self.last_session_id}). LoggedIn={is_logged_in}, Locked={is_screen_locked}")
                    self.kill_current_agent()
                    self.kill_clipboard_agent()
                    self.last_session_id = active_session_id
                    self.last_was_logged_in = is_logged_in
                    self.last_was_screen_locked = is_screen_locked
                    self.last_spawn_time = 0.0 # Force immediate spawn on state change
                else:
                    # Update states without killing the agent
                    if self.last_was_screen_locked != is_screen_locked or self.last_was_logged_in != is_logged_in:
                        log(f"Lock/Logon state changed (Locked={is_screen_locked}, LoggedIn={is_logged_in}). Keeping agent alive to maintain P2P connection.")
                        self.last_was_screen_locked = is_screen_locked
                        self.last_was_logged_in = is_logged_in

                # Start agent if it's not running
                if not self.is_agent_running(active_session_id, is_screen_locked):
                    now = time.time()
                    if now - self.last_spawn_time >= self.spawn_cooldown:
                        self.spawn_agent(active_session_id, is_logged_in, is_screen_locked)
                        self.last_spawn_time = now

                # Spawn Clipboard Agent ở quyền User thường (chỉ khi user đã đăng nhập)
                if is_logged_in and not is_screen_locked and self.clipboard_agent_pid is None:
                    self.spawn_clipboard_agent(active_session_id)

            except Exception as e:
                log(f"Error in checking session: {e}")

    def spawn_agent(self, session_id, is_logged_in, is_screen_locked):
        exe_path, cmd_line = self.get_executable_to_run()
        if not exe_path:
            return

        h_token = None
        desktop = "winsta0\\default"

        # We ALWAYS use the winlogon token to run the agent as SYSTEM in the user session.
        # This allows the agent to dynamically switch between desktops (winsta0\default and winsta0\winlogon)
        # and control administrative apps / UAC prompts without permission blocks.
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
                win32con.PROCESS_QUERY_INFORMATION, False, winlogon_pid
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

    def spawn_clipboard_agent(self, session_id):
        """
        Spawn Clipboard Agent ở quyền User thường (sử dụng WTSQueryUserToken).
        Dùng chính RemoteDesktopP2P.exe với flag --clipboard-agent.
        Agent này lắng nghe Named Pipe và nạp file vào Clipboard.
        """
        exe_path, cmd_line = self.get_executable_to_run()
        if not exe_path:
            return
        
        # Thay flag --headless bằng --clipboard-agent
        cmd_line = cmd_line.replace("--headless", "--clipboard-agent")

        h_user_token = None
        try:
            h_user_token = win32ts.WTSQueryUserToken(session_id)
        except Exception as e:
            log(f"Failed to query user token for Clipboard Agent (session {session_id}): {e}")
            return

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

                self.clipboard_agent_pid = dwProcessId
                log(f"Clipboard Agent spawned with PID {dwProcessId} on winsta0\\default (User privilege)")
            except Exception as e:
                log(f"CreateProcessAsUser for Clipboard Agent failed: {e}")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] in ['install', 'update', 'remove', 'start', 'stop']:
        win32serviceutil.HandleCommandLine(EasyRemoteDesktopService)
    else:
        import servicemanager
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(EasyRemoteDesktopService)
        servicemanager.StartServiceCtrlDispatcher()
