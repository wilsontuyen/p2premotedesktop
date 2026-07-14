
import os, subprocess
def get_details():
    cpu = "FALLBACK_CPUID_888"
    hdd = "FALLBACK_HDD_999"
    machine_guid = "FALLBACK_GUID_666"
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
    try:
        res_cpu = subprocess.run(["powershell", "-Command", "(Get-CimInstance Win32_Processor).ProcessorId"], capture_output=True, text=True, check=True, startupinfo=startupinfo)
        if res_cpu and res_cpu.stdout: cpu = res_cpu.stdout.strip()
    except Exception as e: print("CPU:", e)
    try:
        script_hdd = "$disk = Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\" | Get-CimAssociatedInstance -ResultClassName Win32_DiskPartition -ErrorAction SilentlyContinue | Get-CimAssociatedInstance -ResultClassName Win32_DiskDrive -ErrorAction SilentlyContinue; if ($disk) { $disk[0].SerialNumber } else { (Get-CimInstance Win32_DiskDrive)[0].SerialNumber }"
        res_hdd = subprocess.run(["powershell", "-Command", script_hdd], capture_output=True, text=True, check=True, startupinfo=startupinfo)
        if res_hdd and res_hdd.stdout: hdd = res_hdd.stdout.strip()
    except Exception as e: print("HDD:", e)
    try:
        res_guid = subprocess.run(["powershell", "-Command", "(Get-ItemProperty -Path \"HKLM:\\SOFTWARE\\Microsoft\\Cryptography\" -Name \"MachineGuid\").MachineGuid"], capture_output=True, text=True, check=True, startupinfo=startupinfo)
        if res_guid and res_guid.stdout: machine_guid = res_guid.stdout.strip()
    except Exception as e: print("GUID:", e)
    print("CPU:", cpu)
    print("HDD:", hdd)
    print("GUID:", machine_guid)
get_details()

