import winreg
import win32api

def get_reg_value(hive, subkey, value_name):
    try:
        key = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, value_name)
        winreg.CloseKey(key)
        return str(val).strip()
    except Exception as e:
        return f"ERROR: {e}"

print("MachineGuid:", get_reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", "MachineGuid"))
print("SystemSerialNumber:", get_reg_value(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS", "SystemSerialNumber"))
print("BaseBoardProduct:", get_reg_value(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS", "BaseBoardProduct"))
print("Processor Identifier:", get_reg_value(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "Identifier"))
print("Processor Name:", get_reg_value(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0", "ProcessorNameString"))

try:
    vol_info = win32api.GetVolumeInformation("C:\\")
    print("C: Volume Serial:", hex(vol_info[1]))
except Exception as e:
    print("C: Volume Serial ERROR:", e)
