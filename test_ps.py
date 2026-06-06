import subprocess

script_hdd = """
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" | Get-CimAssociatedInstance -ResultClassName Win32_DiskPartition | Get-CimAssociatedInstance -ResultClassName Win32_DiskDrive
if ($disk) { $disk[0].SerialNumber } else { (Get-CimInstance Win32_DiskDrive)[0].SerialNumber }
"""

res = subprocess.run(['powershell', '-Command', script_hdd], capture_output=True, text=True)
print("Output:", res.stdout.strip())
print("Error:", res.stderr.strip())
