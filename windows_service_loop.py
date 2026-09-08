import win32ts
import win32api
import win32con
import win32process
import win32security
import win32event
import win32profile
import sys
import os
import time
import traceback
import threading

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
        app_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(app_dir, "service.log")

# Broker architecture (Phase 1): broker Session 0 giu ket noi viewer, agent chay
# --capture-worker va noi toi broker qua IPC. Bat/tat bang file "broker.on" trong
# app_dir de doi che do ma khong can build lai (mac dinh: BAT).
def _broker_mode_enabled():
    try:
        if os.path.exists(os.path.join(app_dir, "broker.off")):
            return False
    except Exception:
        pass
    return True

BROKER_MODE = _broker_mode_enabled()
broker_pid = None

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

def enable_all_privileges():
    try:
        h_process = win32api.GetCurrentProcess()
        h_token = win32security.OpenProcessToken(
            h_process, win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY
        )
        privs = []
        for priv_name in [
            win32security.SE_DEBUG_NAME, 
            win32security.SE_TCB_NAME, 
            win32security.SE_ASSIGNPRIMARYTOKEN_NAME, 
            win32security.SE_INCREASE_QUOTA_NAME,
            win32security.SE_IMPERSONATE_NAME
        ]:
            try:
                luid = win32security.LookupPrivilegeValue(None, priv_name)
                privs.append((luid, win32security.SE_PRIVILEGE_ENABLED))
            except:
                pass
        if privs:
            win32security.AdjustTokenPrivileges(h_token, False, privs)
        win32api.CloseHandle(h_token)
        log("Đã kích hoạt toàn bộ đặc quyền (Privileges) cho tiến trình Service.")
    except Exception as e:
        log(f"Lỗi khi cấp đặc quyền hệ thống: {e}")

def create_process_robust(h_token, exe_path, cmd_line, desktop, creation_flags, cwd, environment=None):
    """
    Attempts to create a process using CreateProcessAsUser. 
    If it fails with ERROR_PRIVILEGE_NOT_HELD (1314) on Windows 7,
    it automatically falls back to CreateProcessWithTokenW.
    """
    startup_info = win32process.STARTUPINFO()
    startup_info.lpDesktop = desktop
    if environment is not None:
        startup_info.dwFlags = win32process.STARTF_USESHOWWINDOW
        startup_info.wShowWindow = win32con.SW_HIDE

    try:
        h_process, h_thread, dwProcessId, dwThreadId = win32process.CreateProcessAsUser(
            h_token,
            exe_path,
            cmd_line,
            None, None, False,
            creation_flags,
            environment,
            cwd,
            startup_info
        )
        win32api.CloseHandle(h_process)
        win32api.CloseHandle(h_thread)
        return dwProcessId
    except Exception as e:
        err_code = getattr(e, 'winerror', 0)
        if not err_code and hasattr(e, 'args') and len(e.args) > 0:
            err_code = e.args[0]
            
        if err_code == 1314:
            log(f"CreateProcessAsUser bị từ chối đặc quyền (1314). Kích hoạt CreateProcessWithTokenW (Win 7 fallback)...")
            try:
                import ctypes
                from ctypes import wintypes
                
                ADVAPI32 = ctypes.WinDLL('advapi32', use_last_error=True)
                CreateProcessWithTokenW = ADVAPI32.CreateProcessWithTokenW
                CreateProcessWithTokenW.argtypes = [
                    wintypes.HANDLE, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPWSTR,
                    wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p
                ]
                CreateProcessWithTokenW.restype = wintypes.BOOL
                
                class STARTUPINFOW(ctypes.Structure):
                    _fields_ = [("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR), ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR), ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD), ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD), ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD), ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD), ("lpReserved2", wintypes.LPBYTE), ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE)]
                
                class PROCESS_INFORMATION(ctypes.Structure):
                    _fields_ = [("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE), ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD)]
                    
                si = STARTUPINFOW()
                si.cb = ctypes.sizeof(STARTUPINFOW)
                si.lpDesktop = desktop
                if environment is not None:
                    si.dwFlags = win32process.STARTF_USESHOWWINDOW
                    si.wShowWindow = win32con.SW_HIDE
                
                pi = PROCESS_INFORMATION()
                
                LOGON_WITH_PROFILE = 1
                cmd_line_buf = ctypes.create_unicode_buffer(cmd_line) if cmd_line else None
                
                # Convert environment block to LPVOID
                env_ptr = None
                if environment is not None:
                    # Actually passing environment to CreateProcessWithTokenW via ctypes is complex, 
                    # we will just pass None for fallback. The process will inherit the token's environment.
                    pass
                
                res = CreateProcessWithTokenW(
                    int(h_token),
                    LOGON_WITH_PROFILE,
                    exe_path,
                    cmd_line_buf,
                    creation_flags,
                    None,
                    cwd,
                    ctypes.byref(si),
                    ctypes.byref(pi)
                )
                
                if not res:
                    log(f"CreateProcessWithTokenW cũng thất bại với lỗi: {ctypes.get_last_error()}")
                    raise e
                
                ctypes.windll.kernel32.CloseHandle(pi.hProcess)
                ctypes.windll.kernel32.CloseHandle(pi.hThread)
                return pi.dwProcessId
            except Exception as fb_err:
                log(f"Lỗi khi chạy fallback: {fb_err}")
                raise e
        else:
            raise e


def configure_uac_registry():
    """
    Configure registry to disable UAC secure desktop switching (PromptOnSecureDesktop = 0).
    This ensures that on virtual machines (or when GPU display drivers are limited),
    UAC prompt windows are displayed on the default user desktop where they can be captured
    and controlled without session freeze or connection loss.
    """
    try:
        import winreg
        path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_ALL_ACCESS)
        except WindowsError:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_SET_VALUE)
        
        winreg.SetValueEx(key, "PromptOnSecureDesktop", 0, winreg.REG_DWORD, 0)
        winreg.SetValueEx(key, "SoftwareSASGeneration", 0, winreg.REG_DWORD, 3)
        winreg.CloseKey(key)
        log("Đã cấu hình thành công Registry (PromptOnSecureDesktop=0, SoftwareSASGeneration=3).")
    except Exception as e:
        log(f"Thất bại khi cấu hình Registry: {e}")

def get_active_session_id():
    try:
        sessions = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE, 1, 0)
        for s in sessions:
            if s['State'] == 0:  # WTSActive
                return s['SessionId']
    except Exception as e:
        log(f"Lỗi liệt kê các session WTS: {e}")
    # Fallback
    return win32ts.WTSGetActiveConsoleSessionId()

def is_logon_ui_running(session_id):
    try:
        procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
        for p in procs:
            if p[0] == session_id and p[2].lower() == "logonui.exe":
                return True
    except Exception as e:
        log(f"Lỗi kiểm tra LogonUI: {e}")
    return False

def find_winlogon_pid(session_id):
    try:
        procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
        for p in procs:
            if p[0] == session_id and p[2].lower() == "winlogon.exe":
                return p[1]
    except Exception as e:
        log(f"Lỗi liệt kê các tiến trình: {e}")
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
            log(f"Đã tìm thấy file thực thi biên dịch của Agent: {c}")
            return c, f'"{c}" --headless'

    # Fallback to source
    python_exe = os.path.join(app_dir, ".venv", "Scripts", "python.exe")
    app_py = os.path.join(app_dir, "app.py")
    if os.path.exists(python_exe) and os.path.exists(app_py):
        log(f"Sử dụng nguồn Python dự phòng để chạy Agent bằng: {python_exe}")
        return python_exe, f'"{python_exe}" "{app_py}" --headless'

    log("Lỗi: Không tìm thấy file thực thi hoặc file nguồn app.py!")
    return None, None

def ensure_broker_running():
    """Giu 1 tien trinh broker song trong Session 0 (bat tu qua doi session)."""
    global broker_pid
    if broker_pid and is_process_alive(broker_pid):
        return
    exe_path, cmd_line = get_executable_to_run()
    if not exe_path:
        return
    b_cmd = cmd_line.replace("--headless", "--broker")
    try:
        si = win32process.STARTUPINFO()
        handles = win32process.CreateProcess(
            None, b_cmd, None, None, False,
            win32con.NORMAL_PRIORITY_CLASS | win32process.CREATE_NO_WINDOW,
            None, os.path.dirname(exe_path), si
        )
        broker_pid = handles[2]
        try:
            win32api.CloseHandle(handles[0]); win32api.CloseHandle(handles[1])
        except Exception:
            pass
        log(f"Broker (Session 0) da khoi chay voi PID {broker_pid}")
    except Exception as e:
        log(f"Khoi chay Broker that bai: {e}")

def spawn_agent(session_id, is_logged_in, is_screen_locked, force_winlogon=False):
    exe_path, cmd_line = get_executable_to_run()
    if not exe_path:
        return None
    if BROKER_MODE:
        # Che do broker: agent chi capture/input, noi toi broker qua IPC noi bo.
        cmd_line = cmd_line.replace("--headless", "--capture-worker")

    h_token = None
    desktop = "winsta0\\default"

    # We ALWAYS use the winlogon token to run the agent as SYSTEM in the user session.
    # This allows the agent to dynamically switch between desktops (winsta0\default and winsta0\winlogon)
    # and control administrative apps / UAC prompts without permission blocks.
    winlogon_pid = find_winlogon_pid(session_id)
    if not winlogon_pid:
        log(f"Không tìm thấy winlogon.exe trong session {session_id}. Không thể chạy Agent.")
        return None

    try:
        # Open winlogon and its token
        h_winlogon = win32api.OpenProcess(
            win32con.PROCESS_QUERY_INFORMATION, False, winlogon_pid
        )
        h_token = win32security.OpenProcessToken(
            h_winlogon, win32con.TOKEN_DUPLICATE | win32con.TOKEN_QUERY | win32con.TOKEN_ASSIGN_PRIMARY
        )
        win32api.CloseHandle(h_winlogon)
        
        # Target desktop: Sign-out/lock/logon = Winlogon (process MỚI, không reuse DXGI Default).
        if force_winlogon or (not is_logged_in) or is_screen_locked:
            desktop = "winsta0\\winlogon"
            log(f"Nhắm desktop Winlogon cho session {session_id} (LoggedIn={is_logged_in}, Locked={is_screen_locked}, Force={force_winlogon})")
        else:
            desktop = "winsta0\\default"
            log(f"Nhắm desktop Default cho session {session_id} bằng token SYSTEM")
    except Exception as e:
        log(f"Thất bại khi lấy token Winlogon: {e}")
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

            # Set TokenUIAccess = 1 (True) to bypass UIPI and allow simulated inputs on UAC prompts
            try:
                import ctypes
                from ctypes import wintypes
                ADVAPI32 = ctypes.WinDLL('advapi32', use_last_error=True)
                SetTokenInformation = ADVAPI32.SetTokenInformation
                SetTokenInformation.argtypes = [
                    wintypes.HANDLE,
                    ctypes.c_int,
                    ctypes.c_void_p,
                    wintypes.DWORD
                ]
                SetTokenInformation.restype = wintypes.BOOL
                
                ui_access_val = ctypes.c_ulong(1)
                res = SetTokenInformation(
                    int(h_token_dup),
                    26, # TokenUIAccess
                    ctypes.byref(ui_access_val),
                    ctypes.sizeof(ui_access_val)
                )
                if res:
                    log("[Service] Đã kích hoạt TokenUIAccess = 1 cho token SYSTEM nhân bản thành công bằng ctypes.")
                else:
                    log(f"[Service] Cảnh báo: SetTokenInformation thất bại qua ctypes với mã lỗi: {ctypes.get_last_error()}")
            except Exception as uae:
                log(f"[Service] Cảnh báo: Lỗi khi kích hoạt TokenUIAccess qua ctypes: {uae}")

            # Run process in active user session context with robust fallback
            dwProcessId = create_process_robust(
                h_token_dup,
                exe_path,
                cmd_line,
                desktop,
                win32con.NORMAL_PRIORITY_CLASS | win32process.CREATE_NO_WINDOW,
                os.path.dirname(exe_path)
            )
            win32api.CloseHandle(h_token_dup)

            log(f"Đã khởi chạy Agent thành công với PID {dwProcessId} trên desktop {desktop}")
            return dwProcessId
        except Exception as e:
            log(f"Khởi chạy Agent thất bại toàn diện: {e}")
            try: win32api.CloseHandle(h_token_dup)
            except: pass
    return None

def spawn_clipboard_agent(session_id):
    """
    Spawn Clipboard Agent ở quyền User thường.
    """
    exe_path, cmd_line = get_executable_to_run()
    if not exe_path:
        return None
    
    cmd_line = cmd_line.replace("--headless", "--clipboard-agent")

    h_user_token = None
    try:
        h_user_token = win32ts.WTSQueryUserToken(session_id)
    except Exception as e:
        log(f"Thất bại khi truy vấn token người dùng cho Clipboard Agent (session {session_id}): {e}")
        return None

    if h_user_token:
        try:
            h_token_dup = win32security.DuplicateTokenEx(
                h_user_token,
                win32security.SecurityImpersonation,
                win32con.TOKEN_ALL_ACCESS,
                win32security.TokenPrimary
            )
            
            environment = win32profile.CreateEnvironmentBlock(h_token_dup, False)
            
            creation_flags = win32process.CREATE_UNICODE_ENVIRONMENT | win32process.CREATE_NEW_CONSOLE

            dwProcessId = create_process_robust(
                h_token_dup,
                exe_path,
                cmd_line,
                "winsta0\\default",
                creation_flags,
                os.path.dirname(exe_path),
                environment
            )
            win32api.CloseHandle(h_token_dup)

            log(f"Đã khởi chạy Clipboard Agent với PID {dwProcessId} trên winsta0\\default (quyền User thường)")
            return dwProcessId
        except Exception as e:
            log(f"Khởi chạy Clipboard Agent thất bại toàn diện: {e}")
            try: win32api.CloseHandle(h_token_dup)
            except: pass
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
        log("Đã cấu hình SoftwareSASGeneration = 3 trong Registry.")
    except Exception as e:
        log(f"Lỗi khi cấu hình SoftwareSASGeneration trong service: {e}")

    try:
        sas_dll = ctypes.windll.LoadLibrary("sas.dll")
        sas_dll.SendSAS.argtypes = [ctypes.c_int]
        sas_dll.SendSAS.restype = None
        sas_dll.SendSAS(0)
        log("SendSAS(0) thực thi thành công từ Service Session 0.")
    except Exception as e:
        log(f"Lỗi khi gọi SendSAS trong service: {e}")

def spawn_taskmgr_system():
    try:
        active_session_id = get_active_session_id()
        if active_session_id == 0xFFFFFFFF or active_session_id == -1:
            return

        is_screen_locked = is_logon_ui_running(active_session_id)
        if is_screen_locked:
            log("Màn hình đang khóa, bỏ qua việc chạy Task Manager.")
            return

        try:
            h_user_token = win32ts.WTSQueryUserToken(active_session_id)
        except Exception as e:
            log(f"Thất bại khi truy vấn token người dùng cho Task Manager (session {active_session_id}): {e}")
            return

        try:
            elevation_type = win32security.GetTokenInformation(h_user_token, win32security.TokenElevationType)
            if elevation_type == 3: # TokenElevationTypeLimited
                linked_token = win32security.GetTokenInformation(h_user_token, win32security.TokenLinkedToken)
                if linked_token:
                    win32api.CloseHandle(h_user_token)
                    h_user_token = linked_token
        except Exception as e:
            log(f"Thất bại khi lấy linked token: {e}")

        if h_user_token:
            h_token_dup = win32security.DuplicateTokenEx(
                h_user_token,
                win32security.SecurityImpersonation,
                win32con.TOKEN_ALL_ACCESS,
                win32security.TokenPrimary
            )
            win32api.CloseHandle(h_user_token)

            dwProcessId = create_process_robust(
                h_token_dup,
                taskmgr_exe,
                None,
                desktop,
                win32con.NORMAL_PRIORITY_CLASS,
                sys32
            )
            win32api.CloseHandle(h_token_dup)
            log(f"Đã khởi chạy thành công Task Manager với PID {dwProcessId} trên desktop {desktop} dưới quyền SYSTEM")
    except Exception as e:
        log(f"Thất bại khi chạy Task Manager: {e}")

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
        log(f"Thất bại khi tạo event: {e}")
        return

    log("Luồng lắng nghe sự kiện của Service đã khởi động và đang chờ...")
    handles = [h_sas_event, h_taskmgr_event]
    while True:
        rc = win32event.WaitForMultipleObjects(handles, False, win32event.INFINITE)
        if rc == win32event.WAIT_OBJECT_0:
            log("Nhận được tín hiệu sự kiện SAS từ Agent. Đang kích hoạt SendSAS.")
            trigger_sas_system()
        elif rc == win32event.WAIT_OBJECT_0 + 1:
            log("Nhận được tín hiệu sự kiện TaskMgr từ Agent. Đang kích hoạt Task Manager.")
            spawn_taskmgr_system()

_session_event_lock = threading.Lock()
_session_events = []
_wts_wndproc_ref = None

def _push_session_event(kind, session_id):
    with _session_event_lock:
        _session_events.append({"kind": kind, "session_id": int(session_id), "ts": time.time()})

def pop_session_events():
    with _session_event_lock:
        evs = list(_session_events)
        del _session_events[:]
        return evs

def agent_mutex_present(session_id, desktop_name):
    mutex_name = f"Global\\AntigravityP2PRemoteDesktopAppMutex_1_{session_id}_{desktop_name}"
    try:
        h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, mutex_name)
        win32api.CloseHandle(h_mutex)
        return True
    except Exception as e:
        err_code = getattr(e, "winerror", 0) or (e.args[0] if getattr(e, "args", None) else 0)
        return err_code != 2

def wts_session_notification_thread():
    """WTS 6 = Signing out, WTS 7 = khóa LogonUI — xử lý tách."""
    global _wts_wndproc_ref
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
    wtsapi32.WTSRegisterSessionNotification.argtypes = [wintypes.HWND, wintypes.DWORD]
    wtsapi32.WTSRegisterSessionNotification.restype = wintypes.BOOL

    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HANDLE),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HANDLE),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
        ]

    WM_WTSSESSION_CHANGE = 0x02B1
    WM_DESTROY = 0x0002
    HWND_MESSAGE = wintypes.HWND(-3)
    names = {
        1: "console_connect",
        2: "console_disconnect",
        5: "logon",
        6: "logoff",
        7: "lock",
        8: "unlock",
    }

    def wndproc(hwnd, msg, wparam, lparam):
        if msg == WM_WTSSESSION_CHANGE:
            code = int(wparam)
            sid = int(lparam)
            kind = names.get(code, f"wts_{code}")
            log(f"WTS session event: {kind} session={sid}")
            # 6 = LOGOFF (Signing out), 7 = LOCK (LogonUI khóa) — không gộp.
            if code == 6:
                _push_session_event("logoff", sid)
            elif code == 7:
                _push_session_event("lock", sid)
            elif code in (5, 8):
                _push_session_event("interactive", sid)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    _wts_wndproc_ref = WNDPROC(wndproc)
    wc = WNDCLASSW()
    wc.lpfnWndProc = _wts_wndproc_ref
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.lpszClassName = "EasyRDWTSNotify"
    atom = user32.RegisterClassW(ctypes.byref(wc))
    if not atom and ctypes.get_last_error() not in (0, 1410):
        log(f"RegisterClassW WTS notify thất bại: {ctypes.get_last_error()}")
        return
    hwnd = user32.CreateWindowExW(
        0, wc.lpszClassName, "EasyRDWTSNotify", 0,
        0, 0, 0, 0, HWND_MESSAGE, None, wc.hInstance, None
    )
    if not hwnd:
        log(f"CreateWindowExW message-only thất bại: {ctypes.get_last_error()}")
        return
    if not wtsapi32.WTSRegisterSessionNotification(hwnd, 1):
        log(f"WTSRegisterSessionNotification thất bại: {ctypes.get_last_error()}")
        return
    log("Đã đăng ký WTSRegisterSessionNotification (LOGOFF=Signing out, LOCK=LogonUI).")
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

def terminate_process_with_pid(pid):
    if not pid:
        return
    log(f"Đang cố gắng dừng tiến trình {pid}")
    success = False
    try:
        h_proc = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, pid)
        win32api.TerminateProcess(h_proc, 0)
        win32api.CloseHandle(h_proc)
        log(f"Đã dừng tiến trình {pid} qua Windows API.")
        success = True
    except Exception as e:
        log(f"Không thể dừng Agent {pid} qua Windows API: {e}")

    if not success:
        try:
            import subprocess
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            log(f"Đã dừng tiến trình {pid} qua lệnh taskkill.")
            success = True
        except Exception as e:
            log(f"Không thể dừng Agent {pid} qua lệnh taskkill: {e}")

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
            if exit_code != 259:
                log(f"[DEBUG] Tiến trình {pid} đã thoát với mã: {exit_code}")
            return exit_code == 259
    except Exception:
        pass
    return False

def main():
    enable_all_privileges()
    log("Vòng lặp service Easy Remote Desktop Agent bắt đầu chạy.")
    configure_uac_registry()
    
    # Clean up any lingering agent processes
    try:
        import subprocess
        subprocess.run("taskkill /F /IM RemoteDesktopP2P.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("Đã dọn dẹp các tiến trình RemoteDesktopP2P.exe còn sót lại.")
    except Exception as e:
        log(f"Lỗi khi dọn dẹp tiến trình lúc khởi động: {e}")

    # Start Service Events Listener thread
    import threading
    t = threading.Thread(target=service_events_listener_thread, daemon=True)
    t.start()
    t_wts = threading.Thread(target=wts_session_notification_thread, daemon=True)
    t_wts.start()

    current_agent_pid = None
    gui_agent_pid = None
    clipboard_agent_pid = None
    last_session_id = None
    was_logged_in = None
    is_logged_in = False
    is_screen_locked = False
    force_logoff_until = 0.0
    lock_pending_until = 0.0
    in_signing_out = False
    in_lock_transition = False
    last_agent_spawn_ts = 0.0
    winlogon_standby_pid = None

    while True:
        try:
            if BROKER_MODE:
                ensure_broker_running()

            active_session_id = get_active_session_id()
            if active_session_id == 0xFFFFFFFF or active_session_id == -1:
                # Khoảng console_disconnect → connect: không ngủ 5s (hụt màn Signing out).
                time.sleep(0.15)
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

            for ev in pop_session_events():
                kind = ev.get("kind")
                if kind == "logoff":
                    # Signing out: token/user desktop còn, LogonUI chưa chắc đã chạy.
                    force_logoff_until = time.time() + 20.0
                    lock_pending_until = 0.0
                    log(
                        f"WTS_SESSION_LOGOFF session={ev.get('session_id')}: "
                        "giữ Agent, vòng capture PrintWindow trên Winlogon (không kill)."
                    )
                elif kind == "lock":
                    # Khóa máy: LogonUI, không phải khoảng Signing out.
                    lock_pending_until = time.time() + 8.0
                    force_logoff_until = 0.0
                    log(f"WTS_SESSION_LOCK session={ev.get('session_id')}: chuyển Winlogon cho màn hình khóa.")
                elif kind == "interactive":
                    force_logoff_until = 0.0
                    lock_pending_until = 0.0
                    log(f"WTS logon/unlock session={ev.get('session_id')}: hết logoff/lock.")

            session_changed = (last_session_id is not None and last_session_id != active_session_id)
            in_signing_out = time.time() < force_logoff_until
            in_lock_transition = (time.time() < lock_pending_until) or is_screen_locked
            want_winlogon = (not is_logged_in) or in_signing_out or in_lock_transition
            target_desktop = "winlogon" if want_winlogon else "default"

            if session_changed:
                if BROKER_MODE:
                    # Worker cũ chết theo session Windows. Không taskkill — broker giữ
                    # viewer; chỉ quên PID cũ để spawn worker session mới ngay.
                    log(f"Session ID đổi {last_session_id} -> {active_session_id}. Broker: spawn worker mới (không kill).")
                    current_agent_pid = None
                    if gui_agent_pid:
                        terminate_process_with_pid(gui_agent_pid)
                        gui_agent_pid = None
                    if clipboard_agent_pid:
                        terminate_process_with_pid(clipboard_agent_pid)
                        clipboard_agent_pid = None
                else:
                    log(f"Session ID đổi {last_session_id} -> {active_session_id}. Tắt Agent để chuyển session.")
                    old_pid = current_agent_pid
                    if current_agent_pid:
                        terminate_process_with_pid(current_agent_pid)
                        current_agent_pid = None
                    if gui_agent_pid:
                        terminate_process_with_pid(gui_agent_pid)
                        gui_agent_pid = None
                    if clipboard_agent_pid:
                        terminate_process_with_pid(clipboard_agent_pid)
                        clipboard_agent_pid = None
                    wait_until = time.time() + 2.0
                    while old_pid and is_process_alive(old_pid) and time.time() < wait_until:
                        time.sleep(0.05)
            elif BROKER_MODE and (not want_winlogon):
                # Sau logon: GIU worker dang capture (thuong la Winlogon), spawn Default
                # song song. Khong doi mutex winlogon (ten mutex co the lech desktop).
                if agent_mutex_present(active_session_id, "default"):
                    if winlogon_standby_pid and is_process_alive(winlogon_standby_pid):
                        log(f"Default đã sẵn sàng. Tắt Winlogon standby PID {winlogon_standby_pid}.")
                        terminate_process_with_pid(winlogon_standby_pid)
                    winlogon_standby_pid = None
                elif current_agent_pid and is_process_alive(current_agent_pid):
                    already_spawning_default = (
                        winlogon_standby_pid
                        and current_agent_pid != winlogon_standby_pid
                        and is_process_alive(current_agent_pid)
                    )
                    if not already_spawning_default:
                        winlogon_standby_pid = current_agent_pid
                        log(f"Logon xong: spawn Default song song, giữ PID {winlogon_standby_pid}.")
                        pid = spawn_agent(
                            active_session_id, is_logged_in, False, force_winlogon=False
                        )
                        if pid:
                            current_agent_pid = pid
                            last_agent_spawn_ts = time.time()
            elif (not BROKER_MODE) and (not want_winlogon) and agent_mutex_present(active_session_id, "winlogon") and not agent_mutex_present(active_session_id, "default"):
                # Da logon nhung agent van o Winlogon: spawn Default de broker handoff.
                log("Agent vẫn ở Winlogon sau khi đã logon. Tắt để spawn lại trên Default.")
                if current_agent_pid:
                    terminate_process_with_pid(current_agent_pid)
                    wait_until = time.time() + 1.0
                    while is_process_alive(current_agent_pid) and time.time() < wait_until:
                        time.sleep(0.05)
                    current_agent_pid = None
                if clipboard_agent_pid:
                    terminate_process_with_pid(clipboard_agent_pid)
                    clipboard_agent_pid = None
            elif in_lock_transition and (not in_signing_out) and agent_mutex_present(active_session_id, "default"):
                log("Agent đang ở Default lúc màn hình khóa. Tắt để spawn lại trên Winlogon.")
                if current_agent_pid:
                    terminate_process_with_pid(current_agent_pid)
                    wait_until = time.time() + 2.0
                    while is_process_alive(current_agent_pid) and time.time() < wait_until:
                        time.sleep(0.05)
                    current_agent_pid = None
                if clipboard_agent_pid:
                    terminate_process_with_pid(clipboard_agent_pid)
                    clipboard_agent_pid = None

            last_session_id = active_session_id
            was_logged_in = is_logged_in

            if current_agent_pid and not is_process_alive(current_agent_pid):
                log(f"Agent với PID {current_agent_pid} đã dừng hoạt động. Sẽ khởi chạy lại.")
                current_agent_pid = None

            if in_signing_out:
                agent_running = (
                    agent_mutex_present(active_session_id, "default")
                    or agent_mutex_present(active_session_id, "winlogon")
                )
            else:
                agent_running = agent_mutex_present(active_session_id, target_desktop)

            if not agent_running:
                other_desk = "winlogon" if target_desktop == "default" else "default"
                has_other = agent_mutex_present(active_session_id, other_desk)
                live = current_agent_pid and is_process_alive(current_agent_pid)
                # Chi coi la "kẹt" khi PID sống mà KHÔNG có mutex desktop nào — đừng
                # giết worker Winlogon đang capture chỉ vì chưa có mutex Default.
                stuck_starting = (
                    live
                    and last_agent_spawn_ts
                    and (time.time() - last_agent_spawn_ts) > 8.0
                    and not has_other
                    and current_agent_pid != winlogon_standby_pid
                )
                if stuck_starting:
                    log(f"Agent PID {current_agent_pid} khởi động quá 8s mà mutex {target_desktop} chưa sẵn sàng. Kill và spawn lại.")
                    terminate_process_with_pid(current_agent_pid)
                    current_agent_pid = None
                    live = False
                if live and (has_other or current_agent_pid == winlogon_standby_pid):
                    # Worker kia dang capture desktop khac — khong cho, spawn da xu ly o tren.
                    pass
                elif live:
                    log(f"Mutex của Agent chưa sẵn sàng nhưng tiến trình {current_agent_pid} vẫn đang khởi động. Chờ đợi...")
                elif (not (BROKER_MODE and session_changed)) and (in_signing_out or session_changed) and (time.time() - last_agent_spawn_ts) < 2.0:
                    # Tránh "respawn storm" khi session đang bị hủy: agent spawn vào
                    # session đang chết sẽ chết ngay. Chờ session ổn định rồi mới spawn.
                    pass
                else:
                    log(
                        f"Khởi chạy Agent session {active_session_id} desktop={target_desktop} "
                        f"(LoggedIn={is_logged_in}, Locked={is_screen_locked}, "
                        f"SigningOut={in_signing_out})"
                    )
                    pid = spawn_agent(
                        active_session_id,
                        is_logged_in,
                        is_screen_locked or in_lock_transition,
                        force_winlogon=want_winlogon,
                    )
                    if pid:
                        current_agent_pid = pid
                        last_agent_spawn_ts = time.time()

            # Clipboard: không chạy lúc lock, cũng không lúc Signing out.
            if is_logged_in and not is_screen_locked and not in_signing_out:
                if clipboard_agent_pid and not is_process_alive(clipboard_agent_pid):
                    log(f"Clipboard Agent với PID {clipboard_agent_pid} đã dừng hoạt động. Sẽ khởi chạy lại.")
                    clipboard_agent_pid = None

                clipboard_agent_running = False
                mutex_name_global_cb = f"Global\\AntigravityP2PClipboardAgentMutex_{active_session_id}"
                mutex_name_session_cb = f"Session\\{active_session_id}\\AntigravityP2PClipboardAgentMutex_{active_session_id}"
                
                try:
                    h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, mutex_name_global_cb)
                    win32api.CloseHandle(h_mutex)
                    clipboard_agent_running = True
                except Exception as e:
                    if getattr(e, 'winerror', 0) != 2:
                        clipboard_agent_running = True
                        
                if not clipboard_agent_running:
                    try:
                        h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, mutex_name_session_cb)
                        win32api.CloseHandle(h_mutex)
                        clipboard_agent_running = True
                    except Exception as e:
                        if getattr(e, 'winerror', 0) != 2:
                            clipboard_agent_running = True
                            
                if not clipboard_agent_running:
                    log(f"Không tìm thấy Mutex của Clipboard Agent cho session {active_session_id}. Đang khởi chạy.")
                    pid = spawn_clipboard_agent(active_session_id)
                    if pid:
                        clipboard_agent_pid = pid
            else:
                if clipboard_agent_pid:
                    terminate_process_with_pid(clipboard_agent_pid)
                    clipboard_agent_pid = None



        except Exception as e:
            log(f"Lỗi trong vòng lặp chính: {e}\n{traceback.format_exc()}")

        # Sign-out / logon: poll nhanh hơn để agent Winlogon lên kịp màn hình khóa.
        if not is_logged_in or is_screen_locked or in_signing_out or in_lock_transition:
            time.sleep(0.15)
        else:
            time.sleep(1)

if __name__ == '__main__':
    main()
