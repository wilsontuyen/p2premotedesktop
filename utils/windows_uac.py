"""HKLM policy so UAC appears on the user desktop (remote viewer can click Yes/No)."""
import sys
import time

_POLICY_PATH = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"


def prompt_on_secure_desktop_enabled():
    """True = Windows default: UAC on Winlogon. False = hộp UAC trên desktop người dùng."""
    now = time.time()
    cache = getattr(prompt_on_secure_desktop_enabled, "_c", (0.0, True))
    if now - cache[0] < 2.0:
        return cache[1]
    enabled = True
    if sys.platform == "win32":
        try:
            import winreg
            access = winreg.KEY_READ
            try:
                access |= winreg.KEY_WOW64_64KEY
            except Exception:
                pass
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _POLICY_PATH, 0, access) as key:
                val, _ = winreg.QueryValueEx(key, "PromptOnSecureDesktop")
                enabled = int(val) != 0
        except Exception:
            enabled = True
    prompt_on_secure_desktop_enabled._c = (now, enabled)
    return enabled


def apply_remote_uac_desktop_policy():
    """PromptOnSecureDesktop=0, SoftwareSASGeneration=3. Needs admin. Uses 64-bit registry view."""
    if sys.platform != "win32":
        return False, "not-windows"
    import winreg
    path = _POLICY_PATH
    accesses = []
    try:
        accesses.append(winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY)
        accesses.append(winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY)
    except Exception:
        pass
    accesses.extend([winreg.KEY_SET_VALUE, winreg.KEY_ALL_ACCESS])
    last_err = None
    for access in accesses:
        key = None
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, access)
            winreg.SetValueEx(key, "PromptOnSecureDesktop", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "SoftwareSASGeneration", 0, winreg.REG_DWORD, 3)
            # Cho phép exe đã ký (không chỉ Program Files) nhận UIAccess — bấm Yes/No UAC.
            try:
                winreg.SetValueEx(key, "EnableSecureUIAPaths", 0, winreg.REG_DWORD, 0)
            except Exception:
                pass
            winreg.CloseKey(key)
            prompt_on_secure_desktop_enabled._c = (0.0, False)
            return True, None
        except Exception as e:
            last_err = e
            if key:
                try:
                    winreg.CloseKey(key)
                except Exception:
                    pass
    return False, last_err
