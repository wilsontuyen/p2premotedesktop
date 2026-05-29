import win32event
import win32con
import win32api
import traceback

mutex_name = "Global\\AntigravityP2PRemoteDesktopAppMutex_1_1_default"
try:
    h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, mutex_name)
    win32api.CloseHandle(h_mutex)
    print("Mutex found!")
except Exception as e:
    err_code = getattr(e, 'winerror', 0)
    if not err_code and hasattr(e, 'args') and len(e.args) > 0:
        err_code = e.args[0]
    print(f"Exception: {e}")
    print(f"Error Code: {err_code}")
    traceback.print_exc()

mutex_name2 = "Global\\AntigravityP2PRemoteDesktopAppMutex_1_1_winlogon"
try:
    h_mutex = win32event.OpenMutex(win32con.SYNCHRONIZE, False, mutex_name2)
    win32api.CloseHandle(h_mutex)
    print("Mutex 2 found!")
except Exception as e:
    err_code = getattr(e, 'winerror', 0)
    if not err_code and hasattr(e, 'args') and len(e.args) > 0:
        err_code = e.args[0]
    print(f"Exception 2: {e}")
    print(f"Error Code 2: {err_code}")
