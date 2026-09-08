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
# READOBJECTS, ENUMERATE, GENERIC_READ, then 0.
_DESKTOP_ACCESS_MASKS = (
    0x02000000, 0x01FF, 0x0183, 0x0100, 0x0001, 0x0040, 0x80000000, 0,
)

def _desktop_name_from_handle(hdesk):
    name = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetUserObjectInformationW(hdesk, 2, name, ctypes.sizeof(name), None)
    return (name.value or "").lower()

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

def check_desktop_change():
    """(needs_switch, is_blocked). Winlogon trên Server vẫn OpenInputDesktop được
    với MAXIMUM_ALLOWED nhưng OpenDesktopW(GENERIC_ALL) hay fail — không được
    đánh blocked nếu đã mở được input desktop (SetThreadDesktop + GDI vẫn capture)."""
    try:
        thread_name = get_desktop_name()
        h_input = open_input_desktop_handle()
        if h_input:
            try:
                input_name = _desktop_name_from_handle(h_input)
            finally:
                ctypes.windll.user32.CloseDesktop(h_input)
            if input_name and input_name != thread_name:
                return True, False
            return False, False

        try:
            v = __import__("sys").getwindowsversion()
            if v.major < 6 or (v.major == 6 and v.minor < 2):
                return False, False
        except Exception:
            pass
        if thread_name not in ("default", "", "agprivacydesk"):
            return False, False
        for name in ("Winlogon", "Default"):
            h_named = open_named_desktop_handle(name)
            if not h_named:
                continue
            try:
                named = _desktop_name_from_handle(h_named)
            finally:
                ctypes.windll.user32.CloseDesktop(h_named)
            if named and named != thread_name:
                return True, False
            if named == thread_name:
                return False, False
        return False, True
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
