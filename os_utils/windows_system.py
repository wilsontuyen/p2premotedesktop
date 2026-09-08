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
    try:
        h_input = None
        for access_mask in [0x02000000, 0x80000000, 0x0001, 0x0040, 0]:
            h_input = ctypes.windll.user32.OpenInputDesktop(0, False, access_mask)
            if h_input:
                break
        
        if not h_input:
            # Windows 7: OpenInputDesktop hay fail (kể cả desktop Default) → đừng coi là Secure Desktop.
            try:
                v = __import__("sys").getwindowsversion()
                if v.major < 6 or (v.major == 6 and v.minor < 2):
                    return False, False
            except Exception:
                pass
            thread_name = get_desktop_name()
            if thread_name == "winlogon":
                return False, False
            for access_mask in [0x01FF, 0x02000000, 0x80000000, 0x0001, 0x0040, 0]:
                h_winlogon = ctypes.windll.user32.OpenDesktopW("Winlogon", 0, False, access_mask)
                if h_winlogon:
                    ctypes.windll.user32.CloseDesktop(h_winlogon)
                    return True, False
            return False, True
            
        name_input = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetUserObjectInformationW(h_input, 2, name_input, ctypes.sizeof(name_input), None)
        ctypes.windll.user32.CloseDesktop(h_input)
        input_name = name_input.value.lower()
        
        thread_name = get_desktop_name()
            
        if input_name != thread_name:
            for access_mask in [0x01FF, 0x02000000, 0x80000000, 0x0001, 0x0040, 0]:
                try:
                    h_target = ctypes.windll.user32.OpenDesktopW(input_name, 0, False, access_mask)
                    if h_target:
                        ctypes.windll.user32.CloseDesktop(h_target)
                        return True, False
                except:
                    pass
            return False, True
            
        return False, False
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
