import win32ts
import win32api
import win32con
import win32process
import win32security
import win32event
import win32profile
import win32service
import ctypes
from ctypes import wintypes
import sys
import os
import time
import json
import socket
import traceback
import threading

try:
    import psutil
except Exception:
    psutil = None

try:
    import win32com.client
except Exception:
    pass

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
try:
    from utils.logger import get_log_filepath, ensure_utf8_bom
    log_file = get_log_filepath("service.log")
    ensure_utf8_bom(log_file)
except Exception:
    log_file = os.path.join(app_dir, "Logs", "service.log")


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
_broker_thread = None
BROKER_IPC_PORT = 12400

def notify_broker_power_event(kind="shutdown"):
    """Bao broker: host shutdown/restart — viewer dong cua so, khong hien mat ket noi."""
    if not BROKER_MODE:
        return
    kind = (kind or "shutdown").lower()
    if kind not in ("shutdown", "restart"):
        kind = "shutdown"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.8)
        s.connect(("127.0.0.1", BROKER_IPC_PORT))
        s.sendall(json.dumps({"role": "power_event", "kind": kind}).encode("utf-8") + b"\n")
        try:
            s.close()
        except Exception:
            pass
        log(f"Đã báo broker power_event={kind}")
    except Exception as e:
        log(f"Báo broker power_event thất bại: {e}")


_shutdown_ctrl_handler = None

def install_power_event_handler():
    """CTRL_SHUTDOWN_EVENT = shutdown hoac restart. Bo qua CTRL_LOGOFF (Signing Out)."""
    global _shutdown_ctrl_handler
    try:
        import ctypes
        from ctypes import wintypes
        CTRL_LOGOFF_EVENT = 5
        CTRL_SHUTDOWN_EVENT = 6
        HandlerRoutine = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

        def _ctrl(ctrl_type):
            if ctrl_type == CTRL_LOGOFF_EVENT:
                return False
            if ctrl_type == CTRL_SHUTDOWN_EVENT:
                log("CTRL_SHUTDOWN_EVENT: shutdown/restart — báo broker đóng viewer")
                notify_broker_power_event("shutdown")
                return True
            return False

        _shutdown_ctrl_handler = HandlerRoutine(_ctrl)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_shutdown_ctrl_handler, True)
        log("Đã cài SetConsoleCtrlHandler cho shutdown/restart.")
    except Exception as e:
        log(f"SetConsoleCtrlHandler thất bại: {e}")


def notify_broker_session_event(kind, session_id):
    """Bao broker/worker Default: PrintWindow Winlogon ngay, khong cho spawn process moi."""
    if not BROKER_MODE:
        return
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(("127.0.0.1", BROKER_IPC_PORT))
        payload = json.dumps({
            "role": "session_event",
            "kind": kind,
            "session": int(session_id) if session_id is not None else 0,
        }) + "\n"
        s.sendall(payload.encode("utf-8"))
        try:
            s.close()
        except Exception:
            pass
        log(f"Đã báo broker session_event={kind} session={session_id}")
    except Exception as e:
        log(f"Báo broker {kind} thất bại: {e}")

def _write_service_log(target_file, log_line):
    try:
        parent = os.path.dirname(target_file)
        if parent:
            os.makedirs(parent, exist_ok=True)
        need_bom = False
        if not os.path.exists(target_file) or os.path.getsize(target_file) == 0:
            need_bom = True
        else:
            try:
                with open(target_file, "rb") as rf:
                    if rf.read(3) != b"\xef\xbb\xbf":
                        need_bom = True
            except Exception:
                pass
        if need_bom and os.path.exists(target_file) and os.path.getsize(target_file) > 0:
            try:
                with open(target_file, "rb") as rf:
                    c = rf.read()
                with open(target_file, "wb") as wf:
                    wf.write(b"\xef\xbb\xbf" + c)
                need_bom = False
            except Exception:
                pass
        data = log_line.encode("utf-8")
        if need_bom:
            data = b"\xef\xbb\xbf" + data
        with open(target_file, "ab") as f:
            f.write(data)
        return True
    except Exception:
        return False

def log(msg):
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {msg}\n"
        try:
            print(log_line, end="")
        except:
            pass
        if not _write_service_log(log_file, log_line):
            try:
                from utils.logger import get_log_filepath
                fb_path = get_log_filepath("service.log")
                if os.path.abspath(fb_path) != os.path.abspath(log_file):
                    _write_service_log(fb_path, log_line)
            except Exception:
                pass
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
        try:
            _register_spawned_pid(dwProcessId, cmd_line=cmd_line, desktop=desktop)
        except Exception:
            pass
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
                
                # dwLogonFlags = 0 (No logon options): khong load user profile.
                # Tren Windows 7 voi token SYSTEM, co LOGON_WITH_PROFILE (1) khien ProfSvc
                # bi deadlock/timeout 120s-180s (2-3 phut) moi spawn xong process!
                dw_logon_flags = 0
                cmd_line_buf = ctypes.create_unicode_buffer(cmd_line) if cmd_line else None
                
                # Convert environment block to LPVOID
                env_ptr = None
                if environment is not None:
                    # Actually passing environment to CreateProcessWithTokenW via ctypes is complex, 
                    # we will just pass None for fallback. The process will inherit the token's environment.
                    pass
                
                pi = PROCESS_INFORMATION()
                
                res = CreateProcessWithTokenW(
                    int(h_token),
                    dw_logon_flags,
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
    PromptOnSecureDesktop=0: hộp UAC hiện trên desktop người dùng (không Secure Desktop)
    để viewer capture và bấm được Yes/No.
    """
    from utils.windows_uac import apply_remote_uac_desktop_policy
    ok, err = apply_remote_uac_desktop_policy()
    if ok:
        log("Đã cấu hình thành công Registry (PromptOnSecureDesktop=0, SoftwareSASGeneration=3).")
    else:
        log(f"Thất bại khi cấu hình Registry: {err}")

def get_tscon_exe_path():
    """Tìm đường dẫn thực tế tới tscon.exe, xử lý chuyển hướng WOW64 trên Windows 64-bit."""
    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    # Tiến trình 32-bit (x86) trên Windows 64-bit: System32 bị chuyển hướng sang SysWOW64
    # (không có tscon.exe). Cần dùng Sysnative để trỏ tới System32 64-bit thực tế.
    sysnative_tscon = os.path.join(sys_root, "Sysnative", "tscon.exe")
    if os.path.exists(sysnative_tscon):
        return sysnative_tscon
    system32_tscon = os.path.join(sys_root, "System32", "tscon.exe")
    if os.path.exists(system32_tscon):
        return system32_tscon
    return "tscon.exe"

def connect_session_to_console(source_session_id):
    """Kết nối session về console desktop mà không chạy qua cmd.exe / shell=True.
    Ưu tiên gọi trực tiếp Win32 Terminal Services API (WTSConnectSessionW),
    nếu không thành công mới gọi trực tiếp tscon.exe với shell=False (tránh Windows Defender Persistence heuristic)."""
    try:
        sid_int = int(source_session_id)
    except Exception:
        return False
    if sid_int in (0, 0xFFFFFFFF, -1):
        return False

    # 1. Thử WTSConnectSessionW nếu target console ID khác source session ID
    try:
        import ctypes
        from ctypes import wintypes
        wtsapi32 = ctypes.WinDLL("wtsapi32", use_last_error=True)
        wtsapi32.WTSConnectSessionW.argtypes = [
            wintypes.ULONG, wintypes.ULONG, wintypes.LPCWSTR, wintypes.BOOL
        ]
        wtsapi32.WTSConnectSessionW.restype = wintypes.BOOL

        target_console_id = 0xFFFFFFFF
        try:
            target_console_id = win32ts.WTSGetActiveConsoleSessionId()
        except Exception:
            pass
        if target_console_id in (0xFFFFFFFF, -1):
            target_console_id = 1

        ok = wtsapi32.WTSConnectSessionW(int(target_console_id), sid_int, "", False)
        if ok:
            log(f"[Service] WTSConnectSessionW thành công: session {sid_int} -> console {target_console_id}")
            return True
    except Exception as e:
        log(f"[Service] WTSConnectSessionW thất bại ({e}), dùng fallback tscon.exe")

    # 2. Gọi trực tiếp tscon.exe với đường dẫn chuẩn (xử lý Sysnative/WOW64)
    try:
        tscon_exe = get_tscon_exe_path()
        import subprocess
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

        old_val = ctypes.c_void_p()
        redir_disabled = False
        try:
            if hasattr(ctypes.windll.kernel32, "Wow64DisableWow64FsRedirection"):
                redir_disabled = bool(ctypes.windll.kernel32.Wow64DisableWow64FsRedirection(ctypes.byref(old_val)))
        except Exception:
            pass

        try:
            res = subprocess.run(
                [tscon_exe, str(sid_int), "/dest:console"],
                shell=False,
                startupinfo=startupinfo,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
                capture_output=True,
                timeout=3
            )
            log(f"[Service] tscon.exe (shell=False /dest:console): returncode={res.returncode}")
            if res.returncode == 0:
                return True
            if target_console_id not in (0xFFFFFFFF, -1, sid_int):
                res2 = subprocess.run(
                    [tscon_exe, str(sid_int), f"/dest:{target_console_id}"],
                    shell=False,
                    startupinfo=startupinfo,
                    creationflags=0x08000000,
                    capture_output=True,
                    timeout=3
                )
                log(f"[Service] tscon.exe (/dest:{target_console_id}): returncode={res2.returncode}")
                if res2.returncode == 0:
                    return True
            return False
        finally:
            if redir_disabled:
                try:
                    ctypes.windll.kernel32.Wow64RevertWow64FsRedirection(old_val)
                except Exception:
                    pass
    except Exception as te:
        log(f"[Service] tscon.exe lỗi: {te}")
    return False

def get_active_session_id(preferred_sid=None):
    """Session tương tác (khác Session 0).
    Ưu tiên:
    0. preferred_sid nếu hợp lệ và đang Active hoặc Connected.
    1. Session RDP (WinStationName chứa 'rdp' hoặc 'tcp#') đang Active hoặc Connected/ConnectQuery (Windows Server/Client multi-session).
    2. Session đang Active (người dùng đang tương tác, console).
    3. Session Console từ WTSGetActiveConsoleSessionId.
    4. Session WTSConnected (đang kết nối).
    5. Session WTSDisconnected có token user.
    6. Bất kỳ session WTSDisconnected nào còn lại.
    TUYỆT ĐỐI không gọi connect_session_to_console ở đây để tránh cướp session khi Ms RDP đang kết nối.
    """
    WTSActive = 0
    WTSConnected = 1
    WTSConnectQuery = 2
    WTSDisconnected = 4
    invalid = {0xFFFFFFFF, -1, 0}

    sessions = []
    try:
        sessions = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE, 1, 0)
    except Exception as e:
        log(f"Lỗi liệt kê các session WTS: {e}")

    sess_map = {}
    for s in sessions:
        sid = s.get("SessionId")
        if sid not in invalid:
            sess_map[sid] = s

    # 0. Kiểm tra preferred_sid (từ sự kiện WTS connect/logon vừa xảy ra)
    if preferred_sid is not None and preferred_sid not in invalid:
        ps = sess_map.get(preferred_sid)
        if ps and ps.get("State") in (WTSActive, WTSConnected, WTSConnectQuery):
            return preferred_sid

    # 1. Ưu tiên phiên RDP (Remote Desktop) đang Active hoặc Connected/ConnectQuery
    # Trên Windows Server, phiên Ms RDP nằm ở Session riêng (ví dụ Session 2, 'RDP-Tcp#0')
    # trong khi Console (Session 1) vẫn tồn tại. Phải ưu tiên phiên RDP này để bám theo màn hình RDP!
    for s in sessions:
        sid = s.get("SessionId")
        if sid in invalid:
            continue
        s_name = (s.get("WinStationName") or "").lower()
        is_rdp = ("rdp" in s_name or "tcp#" in s_name) and s_name != "rdp-tcp"
        if is_rdp and s.get("State") in (WTSActive, WTSConnected, WTSConnectQuery):
            return sid

    # 2. Tìm session đang Active (người dùng đang tương tác trực tiếp ở console)
    for s in sessions:
        sid = s.get("SessionId")
        if sid in invalid:
            continue
        if s.get("State") == WTSActive:
            return sid

    # 3. Kiểm tra Console Session nếu có
    console = 0xFFFFFFFF
    try:
        console = win32ts.WTSGetActiveConsoleSessionId()
    except Exception:
        pass
    if console not in invalid:
        cs = sess_map.get(console)
        if cs and cs.get("State") in (WTSActive, WTSConnected, WTSConnectQuery, WTSDisconnected):
            return console
        elif not cs:
            return console

    # 4. Kiểm tra session WTSConnected (đang kết nối)
    for s in sessions:
        sid = s.get("SessionId")
        if sid in invalid:
            continue
        if s.get("State") in (WTSConnected, WTSConnectQuery):
            return sid

    # 5. Session Disconnected có token user (sau khi RDP đóng hoặc user khóa máy)
    for s in sessions:
        sid = s.get("SessionId")
        if sid in invalid:
            continue
        if s.get("State") == WTSDisconnected:
            has_user = False
            try:
                h_tok = win32ts.WTSQueryUserToken(sid)
                win32api.CloseHandle(h_tok)
                has_user = True
            except Exception:
                pass
            if has_user:
                return sid

    # 6. Bất kỳ session Disconnected nào còn lại
    for s in sessions:
        sid = s.get("SessionId")
        if sid in invalid:
            continue
        if s.get("State") == WTSDisconnected:
            return sid

    return 0xFFFFFFFF

def is_logon_ui_running(session_id):
    try:
        procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
        for p in procs:
            if p[0] == session_id and p[2].lower() == "logonui.exe":
                return True
    except Exception as e:
        log(f"Lỗi kiểm tra LogonUI: {e}")
    return False

def is_session_locked(session_id):
    """
    Kiểm tra chính xác xem session có đang bị khóa màn hình (Lock Screen) hay không.
    Sử dụng WTSQuerySessionInformationW với WTSSessionInfoEx (25).
    SessionFlags: 0 = WTS_SESSIONSTATE_LOCK, 1 = WTS_SESSIONSTATE_UNLOCK.
    """
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.c_void_p()
        bytes_ret = wintypes.DWORD()
        if ctypes.windll.wtsapi32.WTSQuerySessionInformationW(0, session_id, 25, ctypes.byref(buf), ctypes.byref(bytes_ret)):
            try:
                flags = ctypes.c_long.from_address(buf.value + 16).value
                if flags == 0:  # WTS_SESSIONSTATE_LOCK
                    return True
                elif flags == 1:  # WTS_SESSIONSTATE_UNLOCK
                    return False
            finally:
                ctypes.windll.wtsapi32.WTSFreeMemory(buf)
    except Exception:
        pass
    # Fallback: chỉ coi là lock khi có LogonUI mà KHÔNG có explorer
    return is_logon_ui_running(session_id) and (not is_explorer_running_in_session(session_id))

def is_explorer_running_in_session(session_id):
    try:
        procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
        for p in procs:
            if p[0] == session_id and p[2].lower() == "explorer.exe":
                return True
    except Exception:
        pass
    return False

def find_winlogon_pid(session_id, retries=3):
    for attempt in range(max(1, retries)):
        try:
            procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
            for p in procs:
                if p[0] == session_id and p[2].lower() == "winlogon.exe":
                    return p[1]
        except Exception as e:
            log(f"Lỗi liệt kê các tiến trình: {e}")
        if attempt < retries - 1:
            time.sleep(0.2)
    return None

def _is_host_service():
    """True when this loop is the Host product (not the full RemoteDesktopP2P agent)."""
    if "--host" in sys.argv or "--host-service" in sys.argv:
        return True
    try:
        exe = os.path.basename(sys.executable).lower()
        if "host" in exe:
            return True
    except Exception:
        pass
    try:
        # Marker file in Host install dir — do not infer from Host.exe sitting in the source repo.
        if os.path.exists(os.path.join(app_dir, "host.mode")):
            return True
    except Exception:
        pass
    return False


HOST_PRODUCT = _is_host_service()


def get_executable_to_run():
    extra = " --host" if HOST_PRODUCT else ""
    if HOST_PRODUCT:
        candidates = [
            os.path.join(app_dir, "RemoteDesktopHost.exe"),
            os.path.join(app_dir, "dist_nuitka_host", "app.dist", "RemoteDesktopHost.exe"),
        ]
        log("Chế độ Host: tìm RemoteDesktopHost.exe để spawn broker/Winlogon worker.")
    else:
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
            return c, f'"{c}" --headless{extra}'

    python_exe = os.path.join(app_dir, ".venv", "Scripts", "python.exe")
    app_py = os.path.join(app_dir, "app.py")
    if os.path.exists(python_exe) and os.path.exists(app_py):
        log(f"Sử dụng nguồn Python dự phòng để chạy Agent bằng: {python_exe}")
        return python_exe, f'"{python_exe}" "{app_py}" --headless{extra}'

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
        try:
            _register_spawned_pid(broker_pid, cmd_line=b_cmd, desktop="Session0")
        except Exception:
            pass
        log(f"Broker (Session 0) da khoi chay voi PID {broker_pid}")
    except Exception as e:
        log(f"Khoi chay Broker that bai: {e}")


def cleanup_stale_agent_processes():
    """Dọn dẹp các tiến trình helper cũ (--broker, --capture-worker, --clipboard-agent, --headless) qua Win32 API, giữ nguyên GUI của người dùng."""
    target_exe = "remotedesktophost.exe" if HOST_PRODUCT else "remotedesktopp2p.exe"
    my_pid = os.getpid()
    try:
        if psutil is not None:
            helper_flags = ("--broker", "--capture-worker", "--clipboard-agent", "--headless")
            killed = 0
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    pid = proc.info.get("pid")
                    if not pid or pid == my_pid:
                        continue
                    name = (proc.info.get("name") or "").lower()
                    if name != target_exe:
                        continue
                    cmd = proc.info.get("cmdline") or []
                    joined = " ".join(str(x) for x in cmd).lower()
                    if not any(f in joined for f in helper_flags):
                        continue  # Giữ cửa sổ GUI người dùng
                    terminate_process_with_pid(pid)
                    killed += 1
                except Exception:
                    continue
            log(f"Đã dọn dẹp {killed} tiến trình helper {target_exe} còn sót lại (giữ GUI).")
            return

        # Fallback Win32 API thuần (không gọi taskkill.exe) nếu không có psutil
        procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
        killed = 0
        for p in procs:
            sid, pid, p_name = p[0], p[1], (p[2] or "").lower()
            if pid and pid != my_pid and p_name == target_exe and sid == 0:
                terminate_process_with_pid(pid)
                killed += 1
        log(f"Đã dọn dẹp {killed} tiến trình Session 0 {target_exe} qua WTSEnumerateProcesses.")
    except Exception as e:
        log(f"Lỗi khi dọn dẹp tiến trình lúc khởi động: {e}")


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
            
            creation_flags = win32process.CREATE_UNICODE_ENVIRONMENT | win32process.CREATE_NO_WINDOW

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
        finally:
            if h_user_token:
                try: win32api.CloseHandle(h_user_token)
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

        sys32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
        taskmgr_exe = os.path.join(sys32, "taskmgr.exe")
        desktop = r"WinSta0\Default"

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
_wake_service = threading.Event()

def _push_session_event(kind, session_id):
    with _session_event_lock:
        _session_events.append({"kind": kind, "session_id": int(session_id), "ts": time.time()})
    _wake_service.set()
    # Bao worker ngay trong callback WTS — không đợi vòng lặp service (sleep 1s).
    if kind in ("logoff", "lock", "interactive", "connect", "remote_disconnect"):
        notify_broker_session_event(kind, session_id)
    # Signing out: spawn Winlogon ngay, ke ca khi console session dang 0xFFFFFFFF
    # (neu doi vong lap main continue, hu man Signing out).
    if kind == "logoff" and BROKER_MODE:
        spawn_winlogon_for_logoff(session_id)


def _handle_session_disconnect(session_id):
    """Khi người dùng đóng cửa sổ Microsoft RDP (WTS remote_disconnect),
    chờ 1.5s để tránh can thiệp nhầm vào phiên RDP đang reconnect/kết nối lại,
    sau đó nếu session thực sự vẫn Disconnected thì mới khôi phục về console desktop."""
    def _worker():
        try:
            time.sleep(1.5)

            sid_val = int(session_id)
            if sid_val in (0, 0xFFFFFFFF, -1):
                return

            # Kiểm tra xem có phiên RDP nào đang Active hoặc Connected không
            try:
                sessions = win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE, 1, 0)
                for s in sessions:
                    s_id = s.get("SessionId")
                    s_state = s.get("State")
                    s_name = (s.get("WinStationName") or "").lower()
                    if s_state in (win32ts.WTSActive, win32ts.WTSConnected):
                        if "rdp" in s_name or "tcp" in s_name:
                            log(f"[Service] Có phiên RDP (session {s_id}, {s_name}) đang kết nối. Bỏ qua.")
                            return
            except Exception:
                pass

            # Kiểm tra trạng thái hiện tại của session
            cur_state = None
            try:
                cur_state = win32ts.WTSQuerySessionInformation(
                    win32ts.WTS_CURRENT_SERVER_HANDLE, sid_val, win32ts.WTSConnectState
                )
            except Exception:
                pass

            # CHỈ gọi nếu session vẫn đang là Disconnected (4)
            if cur_state == win32ts.WTSDisconnected:
                log(f"[Service] Khôi phục session {sid_val} về console desktop sau khi đóng RDP...")
                ok = connect_session_to_console(sid_val)
                if ok:
                    notify_broker_session_event("interactive", sid_val)
        except Exception as e:
            log(f"[Service] _handle_session_disconnect lỗi: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def spawn_winlogon_for_logoff(session_id):
    try:
        sid = int(session_id)
    except Exception:
        return None
    if sid in (0xFFFFFFFF, -1, 0):
        return None
    if agent_mutex_present(sid, "winlogon"):
        log(f"Winlogon worker đã có mutex session={sid}, không spawn lại.")
        return None
    log(f"LOGOFF: spawn Winlogon ngay session={sid}")
    return spawn_agent(sid, False, True, force_winlogon=True)

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
    """WTS 6 = Signing out, WTS 7 = khóa LogonUI, WTS 4 = RDP disconnect — xử lý tách."""
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
    names = {
        1: "console_connect",
        2: "console_disconnect",
        3: "remote_connect",
        4: "remote_disconnect",
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
            elif code in (1, 3):  # console_connect (1) hoặc remote_connect (3 - Ms RDP kết nối)
                _push_session_event("connect", sid)
            elif code in (5, 8):  # logon (5) hoặc unlock (8)
                _push_session_event("interactive", sid)
            elif code == 4:  # remote_disconnect (CHỈ khi người dùng đóng cửa sổ Ms RDP)
                _handle_session_disconnect(sid)
                _push_session_event("remote_disconnect", sid)
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
        0, 0, 0, 0, 0, None, wc.hInstance, None
    )
    if not hwnd:
        log(f"CreateWindowExW WTS notify thất bại: {ctypes.get_last_error()}")
        return
    if not wtsapi32.WTSRegisterSessionNotification(hwnd, 1):
        log(f"WTSRegisterSessionNotification thất bại: {ctypes.get_last_error()}")
        return
    global _wts_notify_registered
    _wts_notify_registered = True
    log("Đã đăng ký WTSRegisterSessionNotification (LOGOFF=Signing out, LOCK=LogonUI).")
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

_wts_notify_registered = False

# ==============================================================================
# GIÁM SÁT SẬP TIẾN TRÌNH & THU THẬP LOG LỖI MỨC HỆ THỐNG (SERVICE CRASH MONITOR)
# ==============================================================================

_crash_watch_lock = threading.Lock()
_tracked_procs = {}               # pid -> dict(h_proc, role, cmdline, session_id, desktop, start_ts, exe_name)
_intentionally_stopped_pids = {}  # pid -> ts_marked
_logged_event_records = set()     # EventLog RecordNumber đã ghi nhận để tránh lặp
_last_evt_record_num = None


def _classify_process_role(name_lower, cmdline_str, desktop_hint=""):
    cmd_l = (cmdline_str or "").lower()
    if "--broker" in cmd_l:
        return "Broker (Session 0)", "broker.log"
    if "--capture-worker" in cmd_l:
        desk = desktop_hint or ("winlogon" if "winlogon" in cmd_l else "default")
        return f"CaptureWorker ({desk})", "agent.log"
    if "--clipboard-agent" in cmd_l:
        return "ClipboardAgent", "clipboard_agent.log"
    if "--headless" in cmd_l:
        return "HeadlessAgent", "agent.log"
    if "--service" in cmd_l or "service" in name_lower:
        return "WindowsService", "service.log"
    if "multiprocessing-fork" in cmd_l or "--multiprocessing-fork" in cmd_l:
        return "Viewer (Cửa sổ điều khiển Pygame)", "viewer.log"
    return "GUI (Giao diện chính người dùng)", "gui.log"


def _open_process_watch_handle(pid):
    """Mở và giữ handle tiến trình để đảm bảo đọc được ExitCode kể cả sau khi tiến trình sập đột ngột."""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SYNCHRONIZE = 0x00100000
    for access in (
        PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
        win32con.PROCESS_QUERY_INFORMATION | SYNCHRONIZE,
        PROCESS_QUERY_LIMITED_INFORMATION,
        win32con.PROCESS_QUERY_INFORMATION,
    ):
        try:
            h = win32api.OpenProcess(access, False, int(pid))
            if h:
                return h
        except Exception:
            continue
    return None


def _get_pid_session_id(pid):
    try:
        sid = wintypes.DWORD(0)
        if ctypes.windll.kernel32.ProcessIdToSessionId(int(pid), ctypes.byref(sid)):
            return int(sid.value)
    except Exception:
        pass
    return -1


def _register_spawned_pid(pid, cmd_line="", desktop=""):
    if not pid or int(pid) == os.getpid():
        return
    pid = int(pid)
    with _crash_watch_lock:
        if pid in _tracked_procs:
            return
        h_proc = _open_process_watch_handle(pid)
        if not h_proc:
            return
        role, log_fname = _classify_process_role("", cmd_line, desktop)
        _tracked_procs[pid] = {
            "h_proc": h_proc,
            "role": role,
            "log_file": log_fname,
            "cmdline": cmd_line or "",
            "session_id": _get_pid_session_id(pid),
            "desktop": desktop or "",
            "start_ts": time.time(),
            "exe_name": os.path.basename(sys.executable),
        }


def configure_wer_local_dumps():
    """
    Cấu hình Windows Error Reporting (WER LocalDumps) trong Registry HKLM để khi ứng dụng
    bị crash ở mức C/DLL (Access Violation 0xC0000005, Stack Overrun 0xC0000409, Heap Corruption 0xC0000374),
    nhân Windows tự động lưu file MiniDump (.dmp) vào thư mục Logs/CrashDumps.
    """
    try:
        import winreg
        import glob
        from utils.logger import get_logs_dir

        dump_dir = os.path.join(get_logs_dir(), "CrashDumps")
        os.makedirs(dump_dir, exist_ok=True)

        # Dọn dẹp nếu có quá 5 file .dmp cũ để tránh tốn dung lượng đĩa
        dmp_files = glob.glob(os.path.join(dump_dir, "*.dmp"))
        if len(dmp_files) > 5:
            dmp_files.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)
            for old_dmp in dmp_files[:-5]:
                try:
                    os.remove(old_dmp)
                except Exception:
                    pass

        for exe_name in ("RemoteDesktopP2P.exe", "RemoteDesktopHost.exe", "RemoteDesktopService.exe", "RemoteDesktopHostService.exe"):
            key_path = rf"SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps\{exe_name}"
            try:
                key = winreg.CreateKeyEx(
                    winreg.HKEY_LOCAL_MACHINE,
                    key_path,
                    0,
                    winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY,
                )
                winreg.SetValueEx(key, "DumpFolder", 0, winreg.REG_EXPAND_SZ, dump_dir)
                winreg.SetValueEx(key, "DumpCount", 0, winreg.REG_DWORD, 5)
                winreg.SetValueEx(key, "DumpType", 0, winreg.REG_DWORD, 1)  # 1 = MiniDump
                winreg.CloseKey(key)
            except Exception:
                pass
        log(f"Đã cấu hình WER LocalDumps tự động lưu crash dump vào: {dump_dir}")
    except Exception as e:
        log(f"Không thể cấu hình WER LocalDumps (bỏ qua): {e}")


def _query_windows_event_log_crashes(target_pid=None, max_scan=60):
    """
    Đọc trực tiếp Windows Event Log (Application) bằng Win32 API (win32evtlog)
    để trích xuất thông tin lỗi mức hệ thống từ:
      - Application Error (Event ID 1000: Faulting application, Faulting module, Exception code, Fault offset)
      - Windows Error Reporting (Event ID 1001: WER bucket / Crash dump path)
      - Application Hang (Event ID 1002: treo giao diện / Not Responding)
    """
    global _last_evt_record_num
    results = []
    h_evt = None
    try:
        import win32evtlog
        h_evt = win32evtlog.OpenEventLog(None, "Application")
        if not h_evt:
            return results
        flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        scanned = 0
        newest_rec_seen = _last_evt_record_num
        app_keywords = (
            "remotedesktopp2p",
            "remotedesktophost",
            "remotedesktopservice",
            "easy remote desktop",
            os.path.abspath(app_dir).lower(),
        )
        now_ts = time.time()

        while scanned < max_scan:
            events = win32evtlog.ReadEventLog(h_evt, flags, 0)
            if not events:
                break
            for ev in events:
                scanned += 1
                rec_num = getattr(ev, "RecordNumber", 0)
                if newest_rec_seen is None or rec_num > newest_rec_seen:
                    newest_rec_seen = rec_num

                # Nếu đang poll định kỳ (target_pid=None) và gặp bản ghi cũ đã quét qua thì dừng sớm
                if target_pid is None and _last_evt_record_num is not None and rec_num <= _last_evt_record_num:
                    scanned = max_scan
                    break

                src = getattr(ev, "SourceName", "") or ""
                if src not in ("Application Error", "Windows Error Reporting", "Application Hang"):
                    continue

                # Kiểm tra thời gian sự kiện (chỉ lấy trong vòng 180 giây gần nhất)
                try:
                    ev_ts = ev.TimeGenerated.timestamp()
                    if abs(now_ts - ev_ts) > 180:
                        continue
                except Exception:
                    pass

                inserts = [str(x) for x in (getattr(ev, "StringInserts", None) or [])]
                joined_lower = " | ".join(inserts).lower()
                if not any(k in joined_lower for k in app_keywords):
                    # Nếu chạy bằng python.exe trong môi trường dev và khớp target_pid
                    if target_pid is not None and "python" in joined_lower and (
                        str(target_pid) in joined_lower or f"{int(target_pid):x}" in joined_lower
                    ):
                        pass
                    else:
                        continue

                if target_pid is not None:
                    pid_hex = f"{int(target_pid):x}".lower()
                    pid_dec = str(int(target_pid))
                    # Trong Event 1000, inserts[8] thường là PID (hex hoặc dec)
                    if len(inserts) >= 9:
                        ev_pid_str = inserts[8].lower().replace("0x", "")
                        if ev_pid_str not in (pid_hex, pid_dec) and pid_dec not in joined_lower:
                            continue

                if rec_num in _logged_event_records and target_pid is None:
                    continue
                _logged_event_records.add(rec_num)

                ev_id = int(getattr(ev, "EventID", 0)) & 0xFFFF
                ev_time_str = str(getattr(ev, "TimeGenerated", ""))
                if src == "Application Error" and ev_id == 1000 and len(inserts) >= 12:
                    summary = (
                        f"[EventID 1000 - Application Error @ {ev_time_str}] "
                        f"App={inserts[0]} (v{inserts[1]}), "
                        f"FaultModule={inserts[3]} (v{inserts[4]}), "
                        f"ExceptionCode=0x{inserts[6]}, FaultOffset=0x{inserts[7]}, "
                        f"PID={inserts[8]}, AppPath={inserts[10]}, ModulePath={inserts[11]}"
                    )
                elif src == "Application Hang" and ev_id == 1002 and len(inserts) >= 6:
                    summary = (
                        f"[EventID 1002 - Application Hang @ {ev_time_str}] "
                        f"App={inserts[0]} (v{inserts[1]}), PID={inserts[2]}, "
                        f"HangType={inserts[4]}, AppPath={inserts[5]}"
                    )
                else:
                    summary = f"[EventID {ev_id} - {src} @ {ev_time_str}] {' | '.join(inserts[:10])}"
                results.append(summary)

        if newest_rec_seen is not None:
            _last_evt_record_num = newest_rec_seen
    except Exception:
        pass
    finally:
        if h_evt:
            try:
                import win32evtlog
                win32evtlog.CloseEventLog(h_evt)
            except Exception:
                pass
    return results


def _record_unexpected_process_exit(pid, info, exit_code, intentional=False):
    """Ghi nhận chi tiết khi một tiến trình của ứng dụng bị sập hoặc thoát bất thường."""
    try:
        from utils.logger import decode_windows_exit_code, log_system_crash, read_log_tail, get_logs_dir
        import glob

        u_code, hex_str, sym, desc = decode_windows_exit_code(exit_code)
        role = info.get("role", "Unknown")
        uptime_s = max(0.0, time.time() - float(info.get("start_ts", time.time())))
        is_ntstatus_crash = (u_code is not None and u_code >= 0x80000000 and u_code not in (0xC000013A, 0x40010004))

        # Nếu do Service chủ động đóng (chuyển session/desktop) và không phải lỗi crash bộ nhớ C/DLL thì chỉ ghi debug nhẹ
        if intentional and not is_ntstatus_crash:
            log(f"[ProcessMonitor] Tiến trình {role} (PID {pid}) đã dừng chủ động bởi Service (Exit={hex_str}, Uptime={uptime_s:.1f}s).")
            return

        # Mã thoát 0 (bình thường) hoặc 99 (Viewer đóng do ngắt kết nối) của GUI / Viewer không phải là sập app
        if u_code in (0, 99) and ("GUI" in role or "Viewer" in role):
            log(f"[ProcessMonitor] Tiến trình {role} (PID {pid}) đã đóng bình thường (Exit={u_code}, Uptime={uptime_s:.1f}s).")
            return

        # Chờ ngắn 0.25s để Windows WER / faulthandler kịp ghi Event Log & native_fault.log
        time.sleep(0.25)
        evt_logs = _query_windows_event_log_crashes(target_pid=pid, max_scan=40)

        # Kiểm tra xem có file CrashDump (.dmp) nào vừa sinh ra trong 30 giây gần nhất không
        recent_dumps = []
        try:
            dump_dir = os.path.join(get_logs_dir(), "CrashDumps")
            if os.path.isdir(dump_dir):
                now_t = time.time()
                for dmp in glob.glob(os.path.join(dump_dir, "*.dmp")):
                    if (now_t - os.path.getmtime(dmp)) <= 30.0:
                        recent_dumps.append(f"{os.path.basename(dmp)} ({os.path.getsize(dmp)} bytes)")
        except Exception:
            pass

        details = {
            "Vai trò tiến trình": role,
            "Session ID": info.get("session_id", -1),
            "Desktop": info.get("desktop") or "default",
            "Thời gian chạy": f"{uptime_s:.2f} giây",
            "Lệnh khởi chạy": info.get("cmdline") or info.get("exe_name", ""),
            "Chủ động dừng": "Có (Service kill)" if intentional else "Không (Tự thoát / Sập đột ngột)",
            "Windows Event Log": " ; ".join(evt_logs) if evt_logs else "Không có bản ghi Event ID 1000/1001/1002",
            "Crash Minidump": ", ".join(recent_dumps) if recent_dumps else "Không có",
        }

        role_log_file = info.get("log_file", "gui.log")
        extra_logs = {
            "native_fault.log": read_log_tail("native_fault.log", max_lines=15),
            "crash.log": read_log_tail("crash.log", max_lines=15),
            role_log_file: read_log_tail(role_log_file, max_lines=15),
        }

        title = f"Phát hiện tiến trình {role} (PID {pid}) dừng bất thường với mã {hex_str} ({sym})"
        log(f"[CRASH DETECTED] {title} — {desc}")
        if evt_logs:
            for el in evt_logs:
                log(f"  -> {el}")

        log_system_crash(
            title=title,
            role=f"ServiceMonitor -> {role}",
            pid=pid,
            exit_code=exit_code,
            details=details,
            extra_logs=extra_logs,
        )
    except Exception as e:
        log(f"[ProcessMonitor] Lỗi khi ghi báo cáo crash cho PID {pid}: {e}")


def system_crash_monitor_thread(stop_event=None):
    """
    Luồng chạy ngầm trong Windows Service (quyền SYSTEM):
    1. Tự động phát hiện và giữ Handle của mọi tiến trình thuộc ứng dụng (GUI, Viewer, Broker, CaptureWorker, ClipboardAgent).
    2. Ngay khi bất kỳ tiến trình nào bị sập (kể cả sập ở mức C/DLL không có log Python), đọc chính xác mã thoát
       từ Kernel Handle + truy vấn Windows Event Log (Event ID 1000/1001/1002) + trích xuất đuôi log để ghi vào Logs/system_crash.log.
    """
    log("Luồng giám sát sập ứng dụng mức hệ thống (System Crash Monitor) đã khởi động.")
    # Khởi tạo mốc Event Log hiện tại để không báo cáo lại các sự kiện cũ từ trước khi Service chạy
    try:
        _query_windows_event_log_crashes(target_pid=None, max_scan=10)
    except Exception:
        pass

    my_pid = os.getpid()
    target_exes = {"remotedesktopp2p.exe", "remotedesktophost.exe"}
    last_evt_poll_ts = time.time()

    while not (stop_event is not None and stop_event.is_set()):
        try:
            now_ts = time.time()
            # 1. Dọn dẹp danh sách _intentionally_stopped_pids quá hạn (> 30s)
            with _crash_watch_lock:
                expired_pids = [p for p, ts in _intentionally_stopped_pids.items() if (now_ts - ts) > 30.0]
                for p in expired_pids:
                    _intentionally_stopped_pids.pop(p, None)

            # 2. Quét phát hiện các tiến trình mới của ứng dụng (bao gồm cả GUI và Viewer do người dùng mở)
            if psutil is not None:
                for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                    try:
                        pid = proc.info.get("pid")
                        if not pid or pid == my_pid:
                            continue
                        with _crash_watch_lock:
                            if pid in _tracked_procs:
                                continue
                        name_l = (proc.info.get("name") or "").lower()
                        cmd_list = proc.info.get("cmdline") or []
                        cmd_str = " ".join(str(x) for x in cmd_list)
                        is_our_proc = False
                        if name_l in target_exes:
                            is_our_proc = True
                        elif name_l in ("python.exe", "pythonw.exe") and "app.py" in cmd_str.lower():
                            is_our_proc = True

                        if not is_our_proc:
                            continue

                        h_proc = _open_process_watch_handle(pid)
                        if not h_proc:
                            continue
                        role, log_fname = _classify_process_role(name_l, cmd_str)
                        with _crash_watch_lock:
                            _tracked_procs[pid] = {
                                "h_proc": h_proc,
                                "role": role,
                                "log_file": log_fname,
                                "cmdline": cmd_str,
                                "session_id": _get_pid_session_id(pid),
                                "desktop": "",
                                "start_ts": now_ts,
                                "exe_name": proc.info.get("name") or name_l,
                            }
                    except Exception:
                        continue
            else:
                try:
                    procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
                    for p in procs:
                        sid, pid, p_name = p[0], p[1], (p[2] or "").lower()
                        if not pid or pid == my_pid or p_name not in target_exes:
                            continue
                        with _crash_watch_lock:
                            if pid in _tracked_procs:
                                continue
                        h_proc = _open_process_watch_handle(pid)
                        if h_proc:
                            with _crash_watch_lock:
                                _tracked_procs[pid] = {
                                    "h_proc": h_proc,
                                    "role": f"AppProcess (Session {sid})",
                                    "log_file": "gui.log",
                                    "cmdline": p_name,
                                    "session_id": sid,
                                    "desktop": "",
                                    "start_ts": now_ts,
                                    "exe_name": p_name,
                                }
                except Exception:
                    pass

            # 3. Kiểm tra trạng thái các tiến trình đang theo dõi qua Kernel Handle đã giữ
            dead_entries = []
            with _crash_watch_lock:
                for pid, info in list(_tracked_procs.items()):
                    h_proc = info.get("h_proc")
                    if not h_proc:
                        _tracked_procs.pop(pid, None)
                        continue
                    try:
                        exit_code = win32process.GetExitCodeProcess(h_proc)
                        if exit_code != 259:  # 259 = STILL_ACTIVE
                            try:
                                win32api.CloseHandle(h_proc)
                            except Exception:
                                pass
                            _tracked_procs.pop(pid, None)
                            intentional = pid in _intentionally_stopped_pids
                            _intentionally_stopped_pids.pop(pid, None)
                            dead_entries.append((pid, info, exit_code, intentional))
                    except Exception:
                        try:
                            win32api.CloseHandle(h_proc)
                        except Exception:
                            pass
                        _tracked_procs.pop(pid, None)

            for pid, info, exit_code, intentional in dead_entries:
                threading.Thread(
                    target=_record_unexpected_process_exit,
                    args=(pid, info, exit_code, intentional),
                    daemon=True,
                ).start()

            # 4. Định kỳ mỗi 5 giây quét Windows Event Log để bắt các tiến trình vừa mở đã sập ngay (< 0.8s)
            if (now_ts - last_evt_poll_ts) >= 5.0:
                last_evt_poll_ts = now_ts
                new_evts = _query_windows_event_log_crashes(target_pid=None, max_scan=25)
                if new_evts:
                    from utils.logger import log_system_crash, read_log_tail
                    for ev_summary in new_evts:
                        log(f"[WindowsEventLog] Phát hiện sự kiện lỗi ứng dụng: {ev_summary}")
                        log_system_crash(
                            title="Sự kiện lỗi ứng dụng ghi nhận trong Windows Event Log (Application Error / WER)",
                            role="WindowsEventLog",
                            pid=0,
                            details=ev_summary,
                            extra_logs={
                                "native_fault.log": read_log_tail("native_fault.log", max_lines=10),
                                "crash.log": read_log_tail("crash.log", max_lines=10),
                                "gui.log": read_log_tail("gui.log", max_lines=10),
                            },
                        )

        except Exception as me:
            log(f"[ProcessMonitor] Lỗi vòng lặp giám sát crash: {me}")

        time.sleep(0.8)


def terminate_process_with_pid(pid):
    if not pid or pid == os.getpid():
        return
    with _crash_watch_lock:
        _intentionally_stopped_pids[int(pid)] = time.time()
    log(f"Đang cố gắng dừng tiến trình {pid}")
    try:
        h_proc = win32api.OpenProcess(win32con.PROCESS_TERMINATE, False, int(pid))
        win32api.TerminateProcess(h_proc, 0)
        win32api.CloseHandle(h_proc)
        log(f"Đã dừng tiến trình {pid} qua Windows API.")
        return
    except Exception as e:
        log(f"Không thể dừng tiến trình {pid} qua win32api: {e}")

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        h_proc = kernel32.OpenProcess(0x0001, False, int(pid))  # PROCESS_TERMINATE
        if h_proc:
            try:
                if kernel32.TerminateProcess(h_proc, 0):
                    log(f"Đã dừng tiến trình {pid} qua kernel32.TerminateProcess.")
            finally:
                kernel32.CloseHandle(h_proc)
    except Exception as e:
        log(f"Không thể dừng tiến trình {pid} qua kernel32: {e}")

def is_process_alive(pid):
    """Check if a process with the given PID is still running."""
    if not pid:
        return False
    pid_int = int(pid)
    # Ưu tiên kiểm tra qua handle đang được giữ trong _tracked_procs để không bị mất ExitCode khi tiến trình vừa chết
    with _crash_watch_lock:
        tracked = _tracked_procs.get(pid_int)
        if tracked and tracked.get("h_proc"):
            try:
                exit_code = win32process.GetExitCodeProcess(tracked["h_proc"])
                if exit_code != 259:
                    from utils.logger import decode_windows_exit_code
                    _, hex_str, sym, desc = decode_windows_exit_code(exit_code)
                    log(f"[DEBUG] Tiến trình {pid_int} ({tracked.get('role')}) đã thoát với mã: {exit_code} ({hex_str} - {sym}: {desc})")
                return exit_code == 259
            except Exception:
                pass
    try:
        h_proc = _open_process_watch_handle(pid_int)
        if h_proc:
            exit_code = win32process.GetExitCodeProcess(h_proc)
            win32api.CloseHandle(h_proc)
            # STILL_ACTIVE = 259
            if exit_code != 259:
                from utils.logger import decode_windows_exit_code
                _, hex_str, sym, desc = decode_windows_exit_code(exit_code)
                log(f"[DEBUG] Tiến trình {pid_int} đã thoát với mã: {exit_code} ({hex_str} - {sym}: {desc})")
            return exit_code == 259
    except Exception:
        pass
    return False

def main(stop_event=None):
    global broker_pid
    enable_all_privileges()
    try:
        from utils.logger import install_crash_handlers
        install_crash_handlers("WindowsService")
    except Exception:
        pass
    try:
        from os_utils.windows_system import boost_process_priority
        boost_process_priority()
    except Exception:
        pass
    product = "Host Agent" if HOST_PRODUCT else "Agent"
    log(f"Vòng lặp service Easy Remote Desktop {product} bắt đầu chạy. HOST_PRODUCT={HOST_PRODUCT}")
    install_power_event_handler()
    configure_uac_registry()
    configure_wer_local_dumps()
    
    # Clean up lingering helper processes (keeps user GUI alive).
    cleanup_stale_agent_processes()

    # Start Service Events Listener thread
    t = threading.Thread(target=service_events_listener_thread, daemon=True)
    t.start()
    t_wts = threading.Thread(target=wts_session_notification_thread, daemon=True)
    t_wts.start()
    t_crash = threading.Thread(target=system_crash_monitor_thread, args=(stop_event,), daemon=True)
    t_crash.start()

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
    last_winlogon_spawn_ts = 0.0
    winlogon_standby_pid = None
    preferred_session_id = None

    while not (stop_event is not None and stop_event.is_set()):
        try:
            if BROKER_MODE:
                ensure_broker_running()

            active_session_id = get_active_session_id(preferred_sid=preferred_session_id)

            # Drain WTS TRUOC khi continue (console_disconnect = 0xFFFFFFFF luc Signing out).
            for ev in pop_session_events():
                kind = ev.get("kind")
                ev_sid = ev.get("session_id")
                try:
                    ev_sid_int = int(ev_sid)
                except Exception:
                    ev_sid_int = None

                if kind == "logoff":
                    has_exp = is_explorer_running_in_session(active_session_id)
                    if not has_exp:
                        force_logoff_until = time.time() + 20.0
                        lock_pending_until = 0.0
                        log(
                            f"WTS_SESSION_LOGOFF session={ev_sid_int}: "
                            "explorer đã tắt, spawn Winlogon song song."
                        )
                        if BROKER_MODE:
                            sids = []
                            if ev_sid_int not in (None, 0xFFFFFFFF, -1, 0):
                                sids.append(ev_sid_int)
                            if active_session_id not in (None, 0xFFFFFFFF, -1, 0) and active_session_id not in sids:
                                sids.append(active_session_id)
                            for sid in sids:
                                pid = spawn_winlogon_for_logoff(sid)
                                last_winlogon_spawn_ts = time.time()
                                if pid:
                                    current_agent_pid = pid
                                    last_agent_spawn_ts = time.time()
                    else:
                        log(
                            f"WTS_SESSION_LOGOFF session={ev_sid_int}: "
                            "explorer vẫn sống (BSDR hoặc app chặn shutdown), giữ Default desktop."
                        )
                elif kind == "lock":
                    # Khóa máy: LogonUI, không phải khoảng Signing out.
                    lock_pending_until = time.time() + 8.0
                    force_logoff_until = 0.0
                    log(f"WTS_SESSION_LOCK session={ev_sid_int}: chuyển Winlogon cho màn hình khóa.")
                elif kind in ("interactive", "connect"):
                    force_logoff_until = 0.0
                    lock_pending_until = 0.0
                    if ev_sid_int not in (None, 0xFFFFFFFF, -1, 0):
                        preferred_session_id = ev_sid_int
                    log(f"WTS {kind} session={ev_sid_int}: bám theo session đăng nhập (preferred={preferred_session_id}).")
                elif kind == "remote_disconnect":
                    log(f"WTS remote_disconnect session={ev_sid_int}: đảm bảo khôi phục console desktop.")
                    if preferred_session_id == ev_sid_int:
                        preferred_session_id = None
                    _handle_session_disconnect(ev_sid_int)
                elif kind == "console_disconnect":
                    log(f"WTS console_disconnect session={ev_sid_int}")
                    if preferred_session_id == ev_sid_int:
                        preferred_session_id = None

            # Tính lại active_session_id sau khi nhận sự kiện WTS mới
            active_session_id = get_active_session_id(preferred_sid=preferred_session_id)
            if preferred_session_id is not None and active_session_id != preferred_session_id:
                preferred_session_id = None

            if active_session_id in (0xFFFFFFFF, -1, 0):
                # Chua co session console (boot som / console_disconnect) hoac Session 0.
                _wake_service.wait(0.15)
                _wake_service.clear()
                continue

            # Check if user is logged in
            is_logged_in = False
            try:
                h_token = win32ts.WTSQueryUserToken(active_session_id)
                is_logged_in = True
                win32api.CloseHandle(h_token)
            except Exception:
                pass

            # Check if screen is locked (Lock screen vs interactive)
            is_screen_locked = is_session_locked(active_session_id) if is_logged_in else True
            has_explorer = is_explorer_running_in_session(active_session_id)

            session_changed = (last_session_id is not None and last_session_id != active_session_id)
            in_signing_out = (time.time() < force_logoff_until) and (not has_explorer)
            in_lock_transition = (time.time() < lock_pending_until) or (is_screen_locked and not in_signing_out)
            want_winlogon = (not is_logged_in) or in_signing_out or in_lock_transition
            target_desktop = "winlogon" if want_winlogon else "default"

            if session_changed:
                log(f"Session ID đổi {last_session_id} -> {active_session_id}. Chuyển capture worker sang session mới.")
                if BROKER_MODE:
                    # Dừng worker của session cũ để nhường chỗ hoàn toàn cho session mới (đặc biệt cần thiết
                    # trên Windows Server khi Console session cũ vẫn chạy song song với Ms RDP session mới).
                    old_pid = current_agent_pid
                    if old_pid and is_process_alive(old_pid):
                        log(f"Dừng worker session cũ {last_session_id} PID {old_pid} để chuyển sang session {active_session_id}.")
                        terminate_process_with_pid(old_pid)
                    current_agent_pid = None
                    if winlogon_standby_pid and is_process_alive(winlogon_standby_pid):
                        terminate_process_with_pid(winlogon_standby_pid)
                        winlogon_standby_pid = None
                    if gui_agent_pid:
                        terminate_process_with_pid(gui_agent_pid)
                        gui_agent_pid = None
                    if clipboard_agent_pid:
                        terminate_process_with_pid(clipboard_agent_pid)
                        clipboard_agent_pid = None
                    notify_broker_session_event("session_switch", active_session_id)
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
                # Mutex Default van con luc logoff KHONG du — Signing Out o Winlogon.
                agent_running = agent_mutex_present(active_session_id, "winlogon")
            else:
                agent_running = agent_mutex_present(active_session_id, target_desktop)

            need_winlogon_parallel = (
                BROKER_MODE
                and in_signing_out
                and not agent_mutex_present(active_session_id, "winlogon")
            )

            if need_winlogon_parallel:
                if last_winlogon_spawn_ts and (time.time() - last_winlogon_spawn_ts) < 1.0:
                    pass
                else:
                    log(
                        f"Signing out: spawn Winlogon song song session {active_session_id} "
                        f"(Default vẫn sống={agent_mutex_present(active_session_id, 'default')})"
                    )
                    pid = spawn_agent(
                        active_session_id,
                        is_logged_in,
                        True,
                        force_winlogon=True,
                    )
                    last_winlogon_spawn_ts = time.time()
                    if pid:
                        current_agent_pid = pid
                        last_agent_spawn_ts = time.time()
            elif not agent_running:
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
                        if want_winlogon:
                            last_winlogon_spawn_ts = time.time()

            # Clipboard: không chạy lúc lock, cũng không lúc Signing out.
            if is_logged_in and not is_screen_locked and not in_signing_out:
                if clipboard_agent_pid and not is_process_alive(clipboard_agent_pid):
                    log(f"Clipboard Agent với PID {clipboard_agent_pid} đã dừng hoạt động. Sẽ khởi chạy lại.")
                    clipboard_agent_pid = None

                clipboard_agent_running = bool(clipboard_agent_pid and is_process_alive(clipboard_agent_pid))
                if not clipboard_agent_running:
                    mutex_name_global_cb = f"Global\\AntigravityP2PClipboardAgentMutex_{active_session_id}"
                    mutex_name_session_cb = f"Session\\{active_session_id}\\AntigravityP2PClipboardAgentMutex_{active_session_id}"
                    
                    for m_name in (mutex_name_global_cb, mutex_name_session_cb):
                        try:
                            h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, m_name)
                            win32api.CloseHandle(h_mutex)
                            clipboard_agent_running = True
                            break
                        except Exception as e:
                            err = getattr(e, 'winerror', 0)
                            if err == 5: # ERROR_ACCESS_DENIED means mutex exists in user namespace
                                clipboard_agent_running = True
                                break
                            
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

        if stop_event is not None and stop_event.is_set():
            break

        # Sign-out / logon: WTS callback đánh thức ngay (đừng sleep 1s lúc desktop bình thường).
        _wake_service.wait(0.15 if (not is_logged_in or is_screen_locked or in_signing_out or in_lock_transition) else 1.0)
        _wake_service.clear()

    log("Đang dừng vòng lặp Service và dọn dẹp các tiến trình worker...")
    for pid_to_stop in (current_agent_pid, winlogon_standby_pid, gui_agent_pid, clipboard_agent_pid, broker_pid):
        if pid_to_stop and is_process_alive(pid_to_stop):
            terminate_process_with_pid(pid_to_stop)
    broker_pid = None
    log("Vòng lặp Service đã dừng hoàn toàn.")


def _get_service_spec():
    if HOST_PRODUCT:
        return {
            "service_name": "EasyRemoteDesktopHostService",
            "display_name": "Easy Remote Desktop Host Service",
            "description": "Provides unattended P2P remote desktop access, UAC, and sign-in screen support for Easy Remote Desktop Host.",
            "legacy_task": "EasyRemoteDesktopHostAgent",
            "app_exe": "RemoteDesktopHost.exe",
            "svc_exe": "RemoteDesktopHostService.exe",
            "fw_app_rule": "EasyRemoteDesktopHostAgent",
            "fw_svc_rule": "EasyRemoteDesktopHostService",
        }
    return {
        "service_name": "EasyRemoteDesktopService",
        "display_name": "Easy Remote Desktop Service",
        "description": "Provides unattended P2P remote desktop access, UAC, and sign-in screen support for Easy Remote Desktop.",
        "legacy_task": "EasyRemoteDesktopAgent",
        "app_exe": "RemoteDesktopP2P.exe",
        "svc_exe": "RemoteDesktopService.exe",
        "fw_app_rule": "EasyRemoteDesktopAgent",
        "fw_svc_rule": "EasyRemoteDesktopService",
    }


def _remove_legacy_scheduled_task(task_name):
    """Dừng và xóa Scheduled Task thế hệ cũ qua COM API (không gọi schtasks.exe)."""
    if not task_name:
        return
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        import win32com.client
        sched = win32com.client.Dispatch("Schedule.Service")
        sched.Connect()
        folder = sched.GetFolder("\\")
        try:
            t = folder.GetTask(task_name)
            try:
                t.Stop(0)
            except Exception:
                pass
            folder.DeleteTask(task_name, 0)
            log(f"Đã xóa Scheduled Task cũ '{task_name}' qua COM API.")
        except Exception:
            pass
    except Exception as e:
        log(f"Bỏ qua dọn dẹp Scheduled Task cũ '{task_name}': {e}")


def _configure_firewall_rules(spec, add=True):
    """Thêm hoặc xóa quy tắc Windows Firewall trực tiếp qua COM HNetCfg.FwPolicy2 (không gọi netsh.exe)."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        import win32com.client
        fw_policy = win32com.client.Dispatch("HNetCfg.FwPolicy2")
        rules = fw_policy.Rules
        entries = [
            (spec["fw_app_rule"], os.path.join(app_dir, spec["app_exe"])),
            (spec["fw_svc_rule"], os.path.join(app_dir, spec["svc_exe"])),
        ]
        for rule_name, prog_path in entries:
            for _ in range(5):
                try:
                    rules.Remove(rule_name)
                except Exception:
                    break
            if add and os.path.exists(prog_path):
                rule = win32com.client.Dispatch("HNetCfg.FWRule")
                rule.Name = rule_name
                rule.Description = f"{spec['display_name']} ({os.path.basename(prog_path)})"
                rule.ApplicationName = os.path.abspath(prog_path)
                rule.Protocol = 256        # NET_FW_IP_PROTOCOL_ANY
                rule.Direction = 1         # NET_FW_RULE_DIR_IN
                rule.Action = 1            # NET_FW_ACTION_ALLOW
                rule.Profiles = 0x7FFFFFFF # NET_FW_PROFILE2_ALL
                rule.Enabled = True
                rules.Add(rule)
                log(f"Đã cấu hình Firewall rule '{rule_name}' qua COM API cho {prog_path}")
    except Exception as e:
        log(f"Cấu hình Firewall COM gặp lỗi (không chặn cài đặt): {e}")


def _wait_service_state(h_svc, desired_state, timeout_sec=8.0):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            st = win32service.QueryServiceStatus(h_svc)
            if st[1] == desired_state:
                return True
        except Exception:
            break
        time.sleep(0.2)
    return False


def install_windows_service():
    """Đăng ký và khởi chạy Windows SCM Service native + cấu hình Firewall COM."""
    enable_all_privileges()
    spec = _get_service_spec()
    svc_name = spec["service_name"]
    log(f"Bắt đầu cài đặt Windows Service '{svc_name}'...")

    # 1. Xóa Scheduled Task thế hệ cũ nếu có
    _remove_legacy_scheduled_task(spec["legacy_task"])

    # 2. Cấu hình Windows Firewall qua COM API
    _configure_firewall_rules(spec, add=True)

    # 3. Xác định đường dẫn thực thi cho SCM
    if getattr(sys, "frozen", False) or hasattr(sys, "__compiled__"):
        svc_exe_path = os.path.abspath(sys.executable)
    else:
        cand = os.path.join(app_dir, spec["svc_exe"])
        if os.path.exists(cand):
            svc_exe_path = os.path.abspath(cand)
        else:
            svc_exe_path = None

    if svc_exe_path:
        bin_path = f'"{svc_exe_path}" --service'
    else:
        bin_path = f'"{os.path.abspath(sys.executable)}" "{os.path.abspath(__file__)}" --service'

    h_scm = None
    h_svc = None
    try:
        h_scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
        try:
            h_svc = win32service.OpenService(h_scm, svc_name, win32service.SERVICE_ALL_ACCESS)
            st = win32service.QueryServiceStatus(h_svc)
            if st[1] != win32service.SERVICE_STOPPED:
                try:
                    win32service.ControlService(h_svc, win32service.SERVICE_CONTROL_STOP)
                except Exception:
                    pass
                _wait_service_state(h_svc, win32service.SERVICE_STOPPED, timeout_sec=8.0)

            win32service.ChangeServiceConfig(
                h_svc,
                win32service.SERVICE_WIN32_OWN_PROCESS,
                win32service.SERVICE_AUTO_START,
                win32service.SERVICE_ERROR_NORMAL,
                bin_path,
                None,
                0,
                None,
                "LocalSystem",
                "",
                spec["display_name"],
            )
            log(f"Đã cập nhật cấu hình Windows Service '{svc_name}' -> {bin_path}")
        except Exception:
            h_svc = win32service.CreateService(
                h_scm,
                svc_name,
                spec["display_name"],
                win32service.SERVICE_ALL_ACCESS,
                win32service.SERVICE_WIN32_OWN_PROCESS,
                win32service.SERVICE_AUTO_START,
                win32service.SERVICE_ERROR_NORMAL,
                bin_path,
                None,
                0,
                None,
                "LocalSystem",
                None,
            )
            log(f"Đã tạo mới Windows Service '{svc_name}' -> {bin_path}")

        try:
            win32service.ChangeServiceConfig2(
                h_svc, win32service.SERVICE_CONFIG_DESCRIPTION, spec["description"]
            )
        except Exception:
            pass

        try:
            win32service.ChangeServiceConfig2(
                h_svc, win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO, False
            )
        except Exception:
            pass

        try:
            failure_actions = {
                "ResetPeriod": 86400,
                "RebootMsg": "",
                "Command": "",
                "Actions": [
                    (win32service.SC_ACTION_RESTART, 3000),
                    (win32service.SC_ACTION_RESTART, 5000),
                    (win32service.SC_ACTION_RESTART, 10000),
                ],
            }
            win32service.ChangeServiceConfig2(
                h_svc, win32service.SERVICE_CONFIG_FAILURE_ACTIONS, failure_actions
            )
        except Exception as fe:
            log(f"Không đặt được FailureActions (bỏ qua): {fe}")

        try:
            win32service.StartService(h_svc, None)
            log(f"Đã gửi lệnh StartService cho '{svc_name}'.")
        except Exception as se:
            if getattr(se, "winerror", 0) != 1056:  # ERROR_SERVICE_ALREADY_RUNNING
                log(f"StartService '{svc_name}' lỗi: {se}")
                return False

        _wait_service_state(h_svc, win32service.SERVICE_RUNNING, timeout_sec=6.0)
        log(f"Cài đặt và khởi chạy Windows Service '{svc_name}' thành công.")
        return True
    except Exception as e:
        log(f"Lỗi cài đặt Windows Service '{svc_name}': {e}\n{traceback.format_exc()}")
        return False
    finally:
        if h_svc:
            try:
                win32service.CloseServiceHandle(h_svc)
            except Exception:
                pass
        if h_scm:
            try:
                win32service.CloseServiceHandle(h_scm)
            except Exception:
                pass


def uninstall_windows_service():
    """Gỡ bỏ Windows SCM Service, xóa Firewall rules COM và tắt toàn bộ tiến trình liên quan qua Win32 API."""
    enable_all_privileges()
    spec = _get_service_spec()
    svc_name = spec["service_name"]
    log(f"Bắt đầu gỡ bỏ Windows Service '{svc_name}'...")

    # 1. Dừng và xóa Windows Service
    h_scm = None
    h_svc = None
    try:
        h_scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
        try:
            h_svc = win32service.OpenService(h_scm, svc_name, win32service.SERVICE_ALL_ACCESS)
            try:
                st = win32service.QueryServiceStatus(h_svc)
                if st[1] != win32service.SERVICE_STOPPED:
                    win32service.ControlService(h_svc, win32service.SERVICE_CONTROL_STOP)
                    _wait_service_state(h_svc, win32service.SERVICE_STOPPED, timeout_sec=8.0)
            except Exception:
                pass
            win32service.DeleteService(h_svc)
            log(f"Đã xóa Windows Service '{svc_name}'.")
        except Exception as se:
            log(f"Bỏ qua xóa Service '{svc_name}': {se}")
    except Exception as e:
        log(f"Không mở được SCM khi gỡ '{svc_name}': {e}")
    finally:
        if h_svc:
            try:
                win32service.CloseServiceHandle(h_svc)
            except Exception:
                pass
        if h_scm:
            try:
                win32service.CloseServiceHandle(h_scm)
            except Exception:
                pass

    # 2. Xóa Scheduled Task cũ nếu có
    _remove_legacy_scheduled_task(spec["legacy_task"])

    # 3. Gỡ bỏ quy tắc Windows Firewall
    _configure_firewall_rules(spec, add=False)

    # 4. Dừng các tiến trình ứng dụng/service còn chạy để bộ gỡ cài đặt xóa sạch file không bị khóa
    my_pid = os.getpid()
    target_names = {spec["app_exe"].lower(), spec["svc_exe"].lower()}
    try:
        if psutil is not None:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pid = proc.info.get("pid")
                    name = (proc.info.get("name") or "").lower()
                    if pid and pid != my_pid and name in target_names:
                        terminate_process_with_pid(pid)
                except Exception:
                    continue
        else:
            procs = win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
            for p in procs:
                pid, p_name = p[1], (p[2] or "").lower()
                if pid and pid != my_pid and p_name in target_names:
                    terminate_process_with_pid(pid)
    except Exception as pe:
        log(f"Dọn tiến trình khi gỡ gặp lỗi: {pe}")

    time.sleep(0.5)
    log(f"Hoàn tất gỡ bỏ '{svc_name}'.")
    return True


# --- Native Win32 SCM Service Dispatcher (ctypes advapi32, tương thích 100% Nuitka standalone) ---
_scm_service_main_ref = None
_scm_ctrl_handler_ref = None
_scm_service_name_buf = None
_scm_dispatch_table = None
_scm_status_handle = None
_service_stop_event = threading.Event()


class _SCM_SERVICE_STATUS(ctypes.Structure):
    _fields_ = [
        ("dwServiceType", wintypes.DWORD),
        ("dwCurrentState", wintypes.DWORD),
        ("dwControlsAccepted", wintypes.DWORD),
        ("dwWin32ExitCode", wintypes.DWORD),
        ("dwServiceSpecificExitCode", wintypes.DWORD),
        ("dwCheckPoint", wintypes.DWORD),
        ("dwWaitHint", wintypes.DWORD),
    ]


class _SCM_TABLE_ENTRYW(ctypes.Structure):
    _fields_ = [
        ("lpServiceName", ctypes.c_void_p),
        ("lpServiceProc", ctypes.c_void_p),
    ]


class _WTSSESSION_NOTIFICATION(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("dwSessionId", wintypes.DWORD),
    ]


def run_scm_service():
    """Chạy tiến trình dưới quyền quản lý trực tiếp của Windows Service Control Manager (SCM)."""
    global _scm_service_main_ref, _scm_ctrl_handler_ref, _scm_service_name_buf
    global _scm_dispatch_table, _scm_status_handle

    spec = _get_service_spec()
    svc_name = spec["service_name"]

    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    LPSERVICE_MAIN_FUNCTIONW = ctypes.WINFUNCTYPE(None, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR))
    LPHANDLER_FUNCTION_EX = ctypes.WINFUNCTYPE(wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.LPVOID)

    advapi32.RegisterServiceCtrlHandlerExW.argtypes = [wintypes.LPCWSTR, LPHANDLER_FUNCTION_EX, wintypes.LPVOID]
    advapi32.RegisterServiceCtrlHandlerExW.restype = wintypes.HANDLE
    advapi32.SetServiceStatus.argtypes = [wintypes.HANDLE, ctypes.POINTER(_SCM_SERVICE_STATUS)]
    advapi32.SetServiceStatus.restype = wintypes.BOOL
    advapi32.StartServiceCtrlDispatcherW.argtypes = [ctypes.POINTER(_SCM_TABLE_ENTRYW)]
    advapi32.StartServiceCtrlDispatcherW.restype = wintypes.BOOL

    SERVICE_WIN32_OWN_PROCESS = 0x00000010
    SERVICE_STOPPED = 0x00000001
    SERVICE_START_PENDING = 0x00000002
    SERVICE_STOP_PENDING = 0x00000003
    SERVICE_RUNNING = 0x00000004

    SERVICE_ACCEPT_STOP = 0x00000001
    SERVICE_ACCEPT_SHUTDOWN = 0x00000004
    SERVICE_ACCEPT_SESSIONCHANGE = 0x00000080
    SERVICE_ACCEPT_PRESHUTDOWN = 0x00000100

    SERVICE_CONTROL_STOP = 0x00000001
    SERVICE_CONTROL_INTERROGATE = 0x00000004
    SERVICE_CONTROL_SHUTDOWN = 0x00000005
    SERVICE_CONTROL_SESSIONCHANGE = 0x0000000E
    SERVICE_CONTROL_PRESHUTDOWN = 0x0000000F

    NO_ERROR = 0
    ERROR_CALL_NOT_IMPLEMENTED = 120

    def _report_status(state, controls=0, exit_code=0, checkpoint=0, wait_hint=0):
        if not _scm_status_handle:
            return
        st = _SCM_SERVICE_STATUS()
        st.dwServiceType = SERVICE_WIN32_OWN_PROCESS
        st.dwCurrentState = state
        st.dwControlsAccepted = controls
        st.dwWin32ExitCode = exit_code
        st.dwServiceSpecificExitCode = 0
        st.dwCheckPoint = checkpoint
        st.dwWaitHint = wait_hint
        advapi32.SetServiceStatus(_scm_status_handle, ctypes.byref(st))

    def _ctrl_handler_ex(dw_control, dw_event_type, lp_event_data, lp_context):
        try:
            if dw_control == SERVICE_CONTROL_INTERROGATE:
                return NO_ERROR
            if dw_control in (SERVICE_CONTROL_PRESHUTDOWN, SERVICE_CONTROL_SHUTDOWN):
                log(f"SCM nhận sự kiện tắt máy (control={dw_control}) — thông báo broker và dừng service.")
                notify_broker_power_event("shutdown")
                _report_status(SERVICE_STOP_PENDING, controls=0, checkpoint=1, wait_hint=5000)
                _service_stop_event.set()
                _wake_service.set()
                return NO_ERROR
            if dw_control == SERVICE_CONTROL_STOP:
                log("SCM nhận lệnh SERVICE_CONTROL_STOP.")
                _report_status(SERVICE_STOP_PENDING, controls=0, checkpoint=1, wait_hint=5000)
                _service_stop_event.set()
                _wake_service.set()
                return NO_ERROR
            if dw_control == SERVICE_CONTROL_SESSIONCHANGE:
                _wake_service.set()
                if (not _wts_notify_registered) and lp_event_data:
                    try:
                        notif = ctypes.cast(lp_event_data, ctypes.POINTER(_WTSSESSION_NOTIFICATION)).contents
                        sid = int(notif.dwSessionId)
                        code = int(dw_event_type)
                        if code == 6:
                            _push_session_event("logoff", sid)
                        elif code == 7:
                            _push_session_event("lock", sid)
                        elif code in (1, 3):
                            _push_session_event("connect", sid)
                        elif code in (5, 8):
                            _push_session_event("interactive", sid)
                        elif code == 4:
                            _handle_session_disconnect(sid)
                            _push_session_event("remote_disconnect", sid)
                    except Exception:
                        pass
                return NO_ERROR
        except Exception as ce:
            log(f"Lỗi trong SCM HandlerEx: {ce}")
        return ERROR_CALL_NOT_IMPLEMENTED

    def _service_main(dw_argc, lpsz_argv):
        global _scm_status_handle
        _service_stop_event.clear()
        _scm_status_handle = advapi32.RegisterServiceCtrlHandlerExW(svc_name, _scm_ctrl_handler_ref, None)
        if not _scm_status_handle:
            log(f"RegisterServiceCtrlHandlerExW thất bại: {ctypes.get_last_error()}")
            return

        _report_status(SERVICE_START_PENDING, controls=0, checkpoint=1, wait_hint=10000)
        accepted = (
            SERVICE_ACCEPT_STOP
            | SERVICE_ACCEPT_SHUTDOWN
            | SERVICE_ACCEPT_PRESHUTDOWN
            | SERVICE_ACCEPT_SESSIONCHANGE
        )
        _report_status(SERVICE_RUNNING, controls=accepted, checkpoint=0, wait_hint=0)
        log(f"SCM Service '{svc_name}' đã chuyển sang trạng thái SERVICE_RUNNING.")
        try:
            main(stop_event=_service_stop_event)
        except Exception as me:
            log(f"Lỗi nghiêm trọng trong SCM ServiceMain: {me}\n{traceback.format_exc()}")
        finally:
            _report_status(SERVICE_STOPPED, controls=0, exit_code=0, checkpoint=0, wait_hint=0)

    _scm_ctrl_handler_ref = LPHANDLER_FUNCTION_EX(_ctrl_handler_ex)
    _scm_service_main_ref = LPSERVICE_MAIN_FUNCTIONW(_service_main)
    _scm_service_name_buf = ctypes.create_unicode_buffer(svc_name)

    table = (_SCM_TABLE_ENTRYW * 2)()
    table[0].lpServiceName = ctypes.addressof(_scm_service_name_buf)
    table[0].lpServiceProc = ctypes.cast(_scm_service_main_ref, ctypes.c_void_p).value
    table[1].lpServiceName = None
    table[1].lpServiceProc = None
    _scm_dispatch_table = table

    ok = advapi32.StartServiceCtrlDispatcherW(_scm_dispatch_table)
    if not ok:
        err = ctypes.get_last_error()
        # ERROR_FAILED_SERVICE_CONTROLLER_CONNECT (1063): chạy trực tiếp từ dòng lệnh thay vì SCM
        if err == 1063:
            log("Chạy trực tiếp ngoài SCM (err=1063) — chuyển sang vòng lặp main() trực tiếp.")
            main()
        else:
            log(f"StartServiceCtrlDispatcherW thất bại với mã lỗi: {err}")


if __name__ == '__main__':
    if "--install-service" in sys.argv:
        sys.exit(0 if install_windows_service() else 1)
    elif "--uninstall-service" in sys.argv:
        sys.exit(0 if uninstall_windows_service() else 1)
    elif "--service" in sys.argv:
        run_scm_service()
    else:
        main()
