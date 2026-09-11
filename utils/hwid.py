import os
import sys
import subprocess
import hashlib
import socket

HWID_FILENAME = "host_hwid.txt"


def _hwid_data_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_saved_hwid():
    """HWID 12 so da ghi luc GUI/worker chay — broker dung luc boot chua login."""
    try:
        p = os.path.join(_hwid_data_dir(), HWID_FILENAME)
        if not os.path.exists(p):
            return ""
        with open(p, "r", encoding="utf-8-sig") as f:
            v = (f.read() or "").strip().split()[0]
        if v.isdigit() and len(v) == 12:
            return v
    except Exception:
        pass
    return ""


def canonical_hwid(hwid):
    """12-digit ID, stripping GUI suffix like _12346 used when service owns 12345."""
    t = str(hwid or "").replace(" ", "").strip()
    if "_" in t:
        left, right = t.rsplit("_", 1)
        if left.isdigit() and len(left) == 12 and right.isdigit():
            return left
    return t


def signaling_lookup_ids(target):
    """Canonical HWID plus port-suffixed IDs the GUI registers when broker holds 12345."""
    base = canonical_hwid(target)
    ids = []
    if base:
        ids.append(base)
    if base.isdigit() and len(base) == 12:
        for p in (12345, 12346, 12347, 12348, 12349):
            a = f"{base}_{p}"
            if a not in ids:
                ids.append(a)
    return ids


def save_hwid(hwid):
    hwid = str(hwid or "").strip().replace(" ", "")
    if not (hwid.isdigit() and len(hwid) == 12):
        return False
    try:
        p = os.path.join(_hwid_data_dir(), HWID_FILENAME)
        with open(p, "w", encoding="utf-8") as f:
            f.write(hwid)
        return True
    except Exception:
        return False

def get_hwid():
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
            # Get CPUID
            res_cpu = subprocess.run(
                ['powershell', '-Command', '(Get-CimInstance Win32_Processor).ProcessorId'],
                capture_output=True, text=True, check=True, startupinfo=startupinfo
            )
            if res_cpu and res_cpu.stdout:
                cpu = res_cpu.stdout.strip()
        except Exception:
            pass
            
        try:
            # Get HDD Serial (C: drive prioritized, fallback to first drive)
            script_hdd = """
            $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'" | Get-CimAssociatedInstance -ResultClassName Win32_DiskPartition -ErrorAction SilentlyContinue | Get-CimAssociatedInstance -ResultClassName Win32_DiskDrive -ErrorAction SilentlyContinue
            if ($disk) { $disk[0].SerialNumber } else { (Get-CimInstance Win32_DiskDrive)[0].SerialNumber }
            """
            res_hdd = subprocess.run(
                ['powershell', '-Command', script_hdd],
                capture_output=True, text=True, check=True, startupinfo=startupinfo
            )
            if res_hdd and res_hdd.stdout:
                hdd = res_hdd.stdout.strip()
        except Exception:
            pass

        try:
            import winreg
            # Always read from the 64-bit registry view if available to prevent WOW6432Node redirection in 32-bit apps
            access_flags = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, access_flags)
            except FileNotFoundError:
                # Fallback to standard read if KEY_WOW64_64KEY fails (e.g., on actual 32-bit OS)
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ)
                
            machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            if machine_guid:
                machine_guid = str(machine_guid).strip()
        except Exception:
            pass

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
        except Exception:
            pass
    else:
        # Linux specific ID generation
        try:
            with open('/etc/machine-id', 'r') as f:
                machine_guid = f.read().strip()
        except Exception:
            pass
            
        # Get physical MACs safely without relying on uuid.getnode() which might pick volatile virtual interfaces
        try:
            eth_macs = []
            wifi_macs = []
            for iface in os.listdir('/sys/class/net/'):
                iface_lower = iface.lower()
                # Skip loopback and common virtual/bridge interfaces
                if iface_lower.startswith(('lo', 'docker', 'veth', 'br', 'tun', 'tap', 'virbr', 'vmnet')):
                    continue
                    
                addr_path = f'/sys/class/net/{iface}/address'
                if os.path.exists(addr_path):
                    with open(addr_path, 'r') as f:
                        mac = f.read().strip()
                        if mac and mac != '00:00:00:00:00:00':
                            if iface_lower.startswith(('wl', 'wlan')):
                                wifi_macs.append(mac)
                            else:
                                eth_macs.append(mac)
            if eth_macs:
                mac_eth = eth_macs[0]
            if wifi_macs:
                mac_wifi = wifi_macs[0]
        except Exception:
            pass

    try:
        import uuid
        mac_fallback = str(uuid.getnode())
    except:
        mac_fallback = "FALLBACK_MAC_777"

    if mac_eth == "FALLBACK_ETH_777" and mac_wifi == "FALLBACK_WIFI_777":
        mac_eth = mac_fallback

    if os.name != 'nt' and machine_guid != "FALLBACK_GUID_666":
        # On Linux, rely exclusively on machine-id if available to guarantee stability across network interface changes
        combined = f"LINUX_{machine_guid}".strip()
    else:
        combined = f"{cpu}_{hdd}_{machine_guid}_{mac_eth}_{mac_wifi}".strip()
        
    sha = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    # Take first 12 hex characters (48-bit int)
    val = int(sha[:12], 16)
    # Generate stable 12-digit ID
    twelve_digit_val = (val % 900000000000) + 100000000000
    s = str(twelve_digit_val)
    
    # Get clean list of macs
    macs = []
    for m in (mac_eth + "," + mac_wifi).split(","):
        m = m.strip()
        if m and "FALLBACK" not in m:
            macs.append(m)
            
    return s, f"{s[:3]} {s[3:6]} {s[6:9]} {s[9:]}", ",".join(macs)

def get_local_ip():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.append(s.getsockname()[0])
        s.close()
    except: pass
    try:
        _, _, ip_list = socket.gethostbyname_ex(socket.gethostname())
        for ip in ip_list:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except: pass
    if not ips: ips.append("127.0.0.1")
    return ",".join(ips)

import urllib.request
import urllib.parse
def get_public_ipv6():
    urls = ["https://ipv6.icanhazip.com", "https://v6.ident.me"]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                ip = response.read().decode('utf-8').strip()
                if ":" in ip:
                    return ip
        except Exception:
            continue
    return None


def get_public_ip():
    urls = ["https://checkip.amazonaws.com", "https://icanhazip.com", "https://ifconfig.me/ip"]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                ip = response.read().decode('utf-8').strip()
                if ip:
                    return ip
        except Exception:
            continue
    return "127.0.0.1"
