import subprocess
import os

cpu = "FALLBACK_CPUID_888"
hdd = "FALLBACK_HDD_999"
mac_eth = "FALLBACK_ETH_777"
mac_wifi = "FALLBACK_WIFI_777"
machine_guid = "FALLBACK_GUID_666"

startupinfo = None
if os.name == 'nt':
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE

try:
    # Get physical MACs (Ethernet and Wi-Fi) excluding virtual adapters
    script = """
    $adapters = Get-NetAdapter -Physical -ErrorAction SilentlyContinue
    $eth = @()
    $wifi = @()
    if ($adapters) {
        foreach ($a in $adapters) {
            if ($a.MediaType -match '802.3' -or $a.Name -match 'Ethernet') { $eth += $a.MacAddress }
            if ($a.MediaType -match 'Native 802.11' -or $a.Name -match 'Wi-Fi' -or $a.Name -match 'Wireless') { $wifi += $a.MacAddress }
        }
    }
    Write-Output ('ETH:' + ($eth -join ','))
    Write-Output ('WIFI:' + ($wifi -join ','))
    """
    res_mac = subprocess.run(
        ['powershell', '-Command', script],
        capture_output=True, text=True, startupinfo=startupinfo
    )
    if res_mac and res_mac.stdout:
        for line in res_mac.stdout.split('\n'):
            line = line.strip()
            if line.startswith('ETH:') and len(line) > 4:
                mac_eth = line[4:].strip()
            if line.startswith('WIFI:') and len(line) > 5:
                mac_wifi = line[5:].strip()
except Exception as e:
    print(e)
    pass

print(f"mac_eth: {mac_eth}")
print(f"mac_wifi: {mac_wifi}")

macs = []
for m in (mac_eth + "," + mac_wifi).split(","):
    m = m.strip()
    if m and "FALLBACK" not in m:
        macs.append(m)

print(f"macs list: {macs}")
print(f"macs joined: {','.join(macs)}")
