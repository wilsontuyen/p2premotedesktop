import ctypes
import winreg
import traceback

try:
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", 0, winreg.KEY_SET_VALUE)
    winreg.SetValueEx(key, "SoftwareSASGeneration", 0, winreg.REG_DWORD, 3)
    winreg.CloseKey(key)
    print("Registry set successfully.")
except Exception as e:
    print(f"Registry error: {e}")

try:
    sas_dll = ctypes.windll.LoadLibrary("sas.dll")
    print(f"Loaded sas.dll: {sas_dll}")
    # The signature is void SendSAS(BOOL)
    sas_dll.SendSAS.argtypes = [ctypes.c_int]
    sas_dll.SendSAS.restype = None
    sas_dll.SendSAS(0)
    print("Called SendSAS(0) successfully.")
except Exception as e:
    print(f"Error calling SendSAS: {e}")
    traceback.print_exc()
