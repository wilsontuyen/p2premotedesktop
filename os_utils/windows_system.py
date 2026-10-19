import sys
import ctypes

def get_session_id():
    try:
        sid = ctypes.c_ulong()
        if ctypes.windll.kernel32.ProcessIdToSessionId(ctypes.windll.kernel32.GetCurrentProcessId(), ctypes.byref(sid)):
            return sid.value
    except:
        pass
    return 1

def get_desktop_name():
    try:
        h_desk = ctypes.windll.user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
        name = ctypes.create_unicode_buffer(256)
        size = ctypes.c_ulong(256)
        if ctypes.windll.user32.GetUserObjectInformationW(h_desk, 2, name, size, None):
            return name.value.lower()
    except:
        pass
    return "default"

# MAXIMUM_ALLOWED, GENERIC_ALL, SWITCH|READ|WRITE|CREATEWINDOW, SWITCHDESKTOP,
# SETTHREADDESKTOP, READOBJECTS, ENUMERATE, GENERIC_READ, then 0.
_DESKTOP_ACCESS_MASKS = (
    0x02000000, 0x01FF, 0x0183, 0x0180, 0x0080, 0x0100, 0x0001, 0x0040, 0x80000000, 0,
)

_THREAD_DESKTOP_ACCESS_MASKS = (
    0x02000000,  # MAXIMUM_ALLOWED
    0x01FF,      # DESKTOP_ALL
    0x0183,      # DESKTOP_SWITCHDESKTOP | DESKTOP_SETTHREADDESKTOP | DESKTOP_CREATEWINDOW | DESKTOP_READOBJECTS
    0x0180,      # DESKTOP_SWITCHDESKTOP | DESKTOP_SETTHREADDESKTOP
    0x0080,      # DESKTOP_SETTHREADDESKTOP
)

_last_input_thread_desktop_handle = None


def boost_process_priority():
    """Tối ưu độ ưu tiên và vô hiệu hóa Power Throttling / EcoQoS cho Host trên Windows."""
    if sys.platform != "win32":
        return
    try:
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        p = kernel32.GetCurrentProcess()

        # 1. Thiết lập độ ưu tiên ABOVE_NORMAL_PRIORITY_CLASS (0x8000)
        kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.SetPriorityClass.restype = wintypes.BOOL
        kernel32.SetPriorityClass(p, 0x00008000)

        # 2. Vô hiệu hóa Power Throttling / EcoQoS (chống Windows bóp CPU khi chạy pin)
        try:
            class PROCESS_POWER_THROTTLING_STATE(ctypes.Structure):
                _fields_ = [
                    ("Version", wintypes.DWORD),
                    ("ControlMask", wintypes.DWORD),
                    ("StateMask", wintypes.DWORD),
                ]

            t = PROCESS_POWER_THROTTLING_STATE()
            t.Version = 1
            t.ControlMask = 0x1 | 0x4  # EXECUTION_SPEED | IGNORE_TIMER_RESOLUTION
            t.StateMask = 0            # 0: tắt power throttling

            kernel32.SetProcessInformation.argtypes = [
                wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
            ]
            kernel32.SetProcessInformation.restype = wintypes.BOOL
            kernel32.SetProcessInformation(p, 4, ctypes.byref(t), ctypes.sizeof(t))
        except Exception:
            pass

        # 3. Yêu cầu Timer Resolution 1ms
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)
        except Exception:
            pass
    except Exception:
        pass


def ensure_task_battery_support(task_name=None):
    """Cấu hình Scheduled Task cho phép chạy trên Pin và không bị Windows tự ngắt."""
    if sys.platform != "win32":
        return
    try:
        import subprocess
        import os
        tasks = [task_name] if task_name else ["EasyRemoteDesktopAgent", "EasyRemoteDesktopHostAgent"]
        for tn in tasks:
            if not tn:
                continue
            # 1. PowerShell: cập nhật trực tiếp qua API Task Scheduler
            import base64
            ps_cmd = (
                f"$t = Get-ScheduledTask -TaskName '{tn}' -ErrorAction SilentlyContinue; "
                f"if ($t) {{ "
                f"$t.Settings.DisallowStartIfOnBatteries = $false; "
                f"$t.Settings.StopIfGoingOnBatteries = $false; "
                f"$t.Settings.ExecutionTimeLimit = 'PT0S'; "
                f"Set-ScheduledTask -InputObject $t -ErrorAction SilentlyContinue "
                f"}}"
            )
            b64 = base64.b64encode(ps_cmd.encode("utf-16le")).decode("ascii")
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", b64],
                capture_output=True, timeout=8
            )
            # 2. XML fallback (hỗ trợ cả Windows 7/8/Server)
            try:
                res = subprocess.run(["schtasks.exe", "/query", "/tn", tn, "/xml"], capture_output=True, text=True, timeout=6)
                if res.returncode == 0 and res.stdout:
                    xml = res.stdout
                    needs_fix = False
                    if "<DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>" in xml:
                        xml = xml.replace("<DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>", "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>")
                        needs_fix = True
                    if "<StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>" in xml:
                        xml = xml.replace("<StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>", "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>")
                        needs_fix = True
                    if "<ExecutionTimeLimit>PT72H</ExecutionTimeLimit>" in xml:
                        xml = xml.replace("<ExecutionTimeLimit>PT72H</ExecutionTimeLimit>", "<ExecutionTimeLimit>PT0S</ExecutionTimeLimit>")
                        needs_fix = True
                    if needs_fix:
                        import tempfile
                        tmp_xml = os.path.join(tempfile.gettempdir(), f"{tn}_bat.xml")
                        with open(tmp_xml, "w", encoding="utf-16") as f:
                            f.write(xml)
                        subprocess.run(["schtasks.exe", "/create", "/tn", tn, "/xml", tmp_xml, "/ru", "NT AUTHORITY\\SYSTEM", "/f"], capture_output=True, timeout=6)
                        try: os.remove(tmp_xml)
                        except Exception: pass
            except Exception:
                pass
    except Exception:
        pass


def get_desktop_name_from_handle(hdesk):
    if not hdesk:
        return ""
    name = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetUserObjectInformationW(hdesk, 2, name, ctypes.sizeof(name), None)
    return (name.value or "").lower()

_desktop_name_from_handle = get_desktop_name_from_handle

def open_input_desktop_handle():
    user32 = ctypes.windll.user32
    for access_mask in _DESKTOP_ACCESS_MASKS:
        h_input = user32.OpenInputDesktop(0, False, access_mask)
        if h_input:
            return h_input
    return None

def open_named_desktop_handle(name):
    user32 = ctypes.windll.user32
    for access_mask in _DESKTOP_ACCESS_MASKS:
        hdesk = user32.OpenDesktopW(name, 0, False, access_mask)
        if hdesk:
            return hdesk
    return None

def attach_process_window_station(station="WinSta0"):
    """Gắn process vào WinSta0 (interactive). Cần SYSTEM — Login/Sign-out/UAC."""
    user32 = ctypes.windll.user32
    for access_mask in _DESKTOP_ACCESS_MASKS:
        hwinsta = user32.OpenWindowStationW(station, False, access_mask)
        if not hwinsta:
            continue
        try:
            if user32.SetProcessWindowStation(hwinsta):
                return True
        finally:
            try:
                user32.CloseWindowStation(hwinsta)
            except Exception:
                pass
    return False

def prompt_on_secure_desktop_enabled():
    try:
        from utils.windows_uac import prompt_on_secure_desktop_enabled as _reg
        return bool(_reg())
    except Exception:
        return True


def uac_on_secure_desktop():
    """True only if consent.exe is running AND Windows still uses Secure Desktop."""
    return bool(uac_consent_running() and prompt_on_secure_desktop_enabled())


def attach_thread_for_remote_input():
    """Gắn thread hiện tại (worker thread) vào input desktop đang nhận chuột/phím (UAC Yes/No hoặc Logon)."""
    global _last_input_thread_desktop_handle
    attach_process_window_station("WinSta0")
    user32 = ctypes.windll.user32
    h_input = None
    for access_mask in _THREAD_DESKTOP_ACCESS_MASKS:
        try:
            h_input = user32.OpenInputDesktop(0, False, access_mask)
            if h_input:
                break
        except Exception:
            pass
    if not h_input:
        thread_name = get_desktop_name()
        target_name = "Winlogon" if thread_name == "default" else "Default"
        for access_mask in _THREAD_DESKTOP_ACCESS_MASKS:
            try:
                h_input = user32.OpenDesktopW(target_name, 0, False, access_mask)
                if h_input:
                    break
            except Exception:
                pass
    if not h_input:
        return False
    try:
        name_input = _desktop_name_from_handle(h_input)
        name_thread = get_desktop_name()
        if name_input and name_input != name_thread:
            result = user32.SetThreadDesktop(h_input)
            if result:
                old_h = _last_input_thread_desktop_handle
                _last_input_thread_desktop_handle = h_input
                if old_h:
                    try:
                        user32.CloseDesktop(old_h)
                    except Exception:
                        pass
                return True
            else:
                try:
                    user32.CloseDesktop(h_input)
                except Exception:
                    pass
                return False
        else:
            try:
                user32.CloseDesktop(h_input)
            except Exception:
                pass
            return True
    except Exception:
        if h_input:
            try:
                user32.CloseDesktop(h_input)
            except Exception:
                pass
        return False


def get_input_desktop_name():
    try:
        h_input = open_input_desktop_handle()
        if not h_input:
            return get_desktop_name()
        try:
            return _desktop_name_from_handle(h_input) or get_desktop_name()
        finally:
            ctypes.windll.user32.CloseDesktop(h_input)
    except Exception:
        return get_desktop_name()

def is_secure_desktop():
    try:
        hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0001)
        if not hdesk:
            return True
        name = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetUserObjectInformationW(hdesk, 2, name, ctypes.sizeof(name), None)
        ctypes.windll.user32.CloseDesktop(hdesk)
        desktop_name = name.value.lower()
        return desktop_name not in ("default", "")
    except:
        return False

def uac_consent_running():
    """consent.exe = hộp thoại UAC (cài phần mềm, Run as admin) trên Secure Desktop."""
    if sys.platform != "win32":
        return False
    now = __import__("time").time()
    cache = getattr(uac_consent_running, "_c", (0.0, False))
    if now - cache[0] < 0.15:
        return cache[1]
    found = False
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            if str(p.info.get("name") or "").lower() == "consent.exe":
                found = True
                break
    except Exception:
        found = False
    uac_consent_running._c = (now, found)
    return found


def is_logonui_running():
    """True nếu LogonUI.exe đang chạy (máy đang ở màn hình khóa / đăng nhập)."""
    if sys.platform != "win32":
        return False
    now = __import__("time").time()
    cache = getattr(is_logonui_running, "_c", (0.0, False))
    if now - cache[0] < 0.2:
        return cache[1]
    found = False
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            if str(p.info.get("name") or "").lower() == "logonui.exe":
                found = True
                break
    except Exception:
        found = False
    is_logonui_running._c = (now, found)
    return found


def is_explorer_running():
    """True nếu explorer.exe đang chạy trong session người dùng."""
    if sys.platform != "win32":
        return False
    now = __import__("time").time()
    cache = getattr(is_explorer_running, "_c", (0.0, False))
    if now - cache[0] < 0.2:
        return cache[1]
    found = False
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            if str(p.info.get("name") or "").lower() == "explorer.exe":
                found = True
                break
    except Exception:
        found = False
    is_explorer_running._c = (now, found)
    return found


def check_desktop_change():
    """(needs_switch, is_blocked). Tránh ping-pong desktop loop khi:
    - Màn hình ngủ qua đêm (DPMS off)
    - Windows Server đang log off (không có explorer.exe)
    - Máy đang ở màn hình khóa / đăng nhập của MS RDP hoặc Windows Server."""
    try:
        thread_name = get_desktop_name()
        h_input = open_input_desktop_handle()
        if h_input:
            try:
                input_name = _desktop_name_from_handle(h_input)
            finally:
                ctypes.windll.user32.CloseDesktop(h_input)
            if input_name and input_name != thread_name:
                for access_mask in (0x01FF, 0x02000000, 0x80000000, 0x0001, 0x0040, 0):
                    try:
                        h_target = ctypes.windll.user32.OpenDesktopW(input_name, 0, False, access_mask)
                        if h_target:
                            ctypes.windll.user32.CloseDesktop(h_target)
                            return True, False
                    except Exception:
                        pass
                return False, True
            return False, False

        # Khi OpenInputDesktop trả về None (màn hình ngủ DPMS / tắt hiển thị / RDP ngắt kết nối / Logoff):
        # Trạng thái đăng nhập:
        # Nếu LogonUI đang chạy HOẶC không có explorer.exe -> máy đang ở màn hình khóa / đăng nhập / logoff (Winlogon)
        has_explorer = is_explorer_running()
        logon_active = is_logonui_running() or (not has_explorer)

        if not logon_active:
            # Người dùng đang đăng nhập bình thường (explorer đang chạy, không có LogonUI)
            if thread_name in ("default", "", "agprivacydesk"):
                return False, False
            # Nếu thread đang kẹt ở winlogon mà người dùng đã vào Default -> chuyển về Default
            return True, False
        else:
            # Màn hình đang ở Winlogon (máy bị khóa, logoff, hoặc đang ở màn hình đăng nhập của RDP/Server)
            if thread_name == "winlogon":
                return False, False
            # Thread đang ở default nhưng máy bị khóa/logoff -> chuyển sang winlogon
            return True, False
    except Exception as e:
        print(f"[DesktopCheck] Error: {e}")
        return False, False

def is_machine_domain_joined():
    debug_messages = []
    try:
        is_server_metric = ctypes.windll.user32.GetSystemMetrics(89)
        if is_server_metric != 0:
            return True, f"Windows Server detection (SystemMetrics 89): {is_server_metric}"
    except Exception:
        pass

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
            install_type, _ = winreg.QueryValueEx(key, "InstallationType")
            if install_type and "server" in install_type.lower():
                return True, f"Windows Server detection (registry): {install_type}"
    except Exception:
        pass

    try:
        import platform
        win_ver = platform.win32_ver()
        release_ver = platform.release()
        if "server" in win_ver[1].lower() or "server" in release_ver.lower():
            return True, f"Windows Server detection (platform): win_ver={win_ver}, release={release_ver}"
    except Exception:
        pass

    try:
        class NETSETUP_JOIN_STATUS:
            NetSetupUnknownStatus = 0
            NetSetupUnjoined = 1
            NetSetupWorkgroupName = 2
            NetSetupDomainName = 3

        NetGetJoinInformation = ctypes.windll.netapi32.NetGetJoinInformation
        NetGetJoinInformation.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32)]
        NetGetJoinInformation.restype = ctypes.c_uint32
        NetApiBufferFree = ctypes.windll.netapi32.NetApiBufferFree

        name_buffer = ctypes.c_void_p()
        status = ctypes.c_uint32()

        result = NetGetJoinInformation(None, ctypes.byref(name_buffer), ctypes.byref(status))

        if result == 0:
            domain_joined = (status.value == NETSETUP_JOIN_STATUS.NetSetupDomainName)
            if name_buffer:
                NetApiBufferFree(name_buffer)
            return domain_joined, f"NetGetJoinInformation returned domain_joined={domain_joined}, status={status.value}"
        else:
            if name_buffer:
                NetApiBufferFree(name_buffer)
            return False, f"NetGetJoinInformation failed with code {result}"
    except Exception as e:
        return False, f"NetGetJoinInformation check failed: {e}"
