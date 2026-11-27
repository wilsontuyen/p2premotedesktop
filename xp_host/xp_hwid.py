# -*- coding: utf-8 -*-
"""
xp_host/xp_hwid.py
Tạo mã định danh phần cứng 12 số (HWID), lấy MAC vật lý (Wake-on-LAN) và địa chỉ IP
trên Windows XP SP2/SP3 bằng Win32 API gốc (kernel32, advapi32, iphlpapi).
TUYỆT ĐỐI KHÔNG gọi PowerShell hay Get-CimInstance / Get-NetAdapter (không tồn tại trên XP).
"""

import ctypes
from ctypes import wintypes
import hashlib
import os
import socket
import sys
import urllib.request
import uuid

HWID_FILENAME = "host_hwid.txt"


def get_app_base_dir():
    if getattr(sys, "frozen", False) or hasattr(sys, "__compiled__"):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _hwid_data_dir(base_dir=None):
    base = base_dir or get_app_base_dir()
    data_dir = os.path.join(base, "Data")
    try:
        os.makedirs(data_dir, exist_ok=True)
    except Exception:
        pass
    old_p = os.path.join(base, HWID_FILENAME)
    new_p = os.path.join(data_dir, HWID_FILENAME)
    if os.path.isfile(old_p):
        try:
            if not os.path.exists(new_p):
                import shutil
                shutil.copy2(old_p, new_p)
            os.remove(old_p)
        except Exception:
            pass
    return data_dir


def load_saved_hwid(base_dir=None):
    try:
        p = os.path.join(_hwid_data_dir(base_dir), HWID_FILENAME)
        if not os.path.exists(p):
            return ""
        with open(p, "r", encoding="utf-8-sig") as f:
            v = (f.read() or "").strip().split()[0]
        if v.isdigit() and len(v) == 12:
            return v
    except Exception:
        pass
    return ""


def save_hwid(hwid, base_dir=None):
    hwid = str(hwid or "").strip().replace(" ", "")
    if not (hwid.isdigit() and len(hwid) == 12):
        return False
    try:
        p = os.path.join(_hwid_data_dir(base_dir), HWID_FILENAME)
        with open(p, "w", encoding="utf-8") as f:
            f.write(hwid)
        return True
    except Exception:
        return False


def format_hwid_display(hwid):
    s = str(hwid or "").replace(" ", "").strip()
    if len(s) == 12:
        return f"{s[:3]} {s[3:6]} {s[6:9]} {s[9:]}"
    return s


# ==============================================================================
# Native Win32 Hardware & Network Inspection (Windows 2000 / XP compatible)
# ==============================================================================
class _IP_ADDR_STRING(ctypes.Structure):
    pass


_IP_ADDR_STRING._fields_ = [
    ("Next", ctypes.POINTER(_IP_ADDR_STRING)),
    ("IpAddress", ctypes.c_char * 16),
    ("IpMask", ctypes.c_char * 16),
    ("Context", wintypes.DWORD),
]


class _IP_ADAPTER_INFO(ctypes.Structure):
    pass


_IP_ADAPTER_INFO._fields_ = [
    ("Next", ctypes.POINTER(_IP_ADAPTER_INFO)),
    ("ComboIndex", wintypes.DWORD),
    ("AdapterName", ctypes.c_char * 260),
    ("Description", ctypes.c_char * 132),
    ("AddressLength", wintypes.UINT),
    ("Address", ctypes.c_ubyte * 8),
    ("Index", wintypes.DWORD),
    ("Type", wintypes.UINT),
    ("DhcpEnabled", wintypes.UINT),
    ("CurrentIpAddress", ctypes.POINTER(_IP_ADDR_STRING)),
    ("IpAddressList", _IP_ADDR_STRING),
    ("GatewayList", _IP_ADDR_STRING),
    ("DhcpServer", _IP_ADDR_STRING),
    ("HaveWins", wintypes.BOOL),
    ("PrimaryWinsServer", _IP_ADDR_STRING),
    ("SecondaryWinsServer", _IP_ADDR_STRING),
    ("LeaseObtained", ctypes.c_long),  # 32-bit time_t on x86 XP
    ("LeaseExpires", ctypes.c_long),
]

_VIRTUAL_ADAPTER_KEYWORDS = (
    "vmware", "virtualbox", "vbox", "hyper-v", "tap-", "tap0", "tun",
    "wintun", "hamachi", "radmin", "zerotier", "tailscale", "loopback",
    "ndiswan", "wan miniport", "bluetooth", "pseudo",
)


def _enum_xp_adapters():
    """Trả về (eth_macs, wifi_macs, ipv4_list) bằng iphlpapi.GetAdaptersInfo."""
    eth_macs = []
    wifi_macs = []
    ipv4s = []
    if sys.platform != "win32":
        return eth_macs, wifi_macs, ipv4s

    try:
        iphlpapi = ctypes.windll.iphlpapi
        buflen = wintypes.ULONG(16384)
        buf = ctypes.create_string_buffer(buflen.value)
        ret = iphlpapi.GetAdaptersInfo(ctypes.byref(buf), ctypes.byref(buflen))
        if ret == 111:  # ERROR_BUFFER_OVERFLOW
            buf = ctypes.create_string_buffer(buflen.value)
            ret = iphlpapi.GetAdaptersInfo(ctypes.byref(buf), ctypes.byref(buflen))
        if ret != 0:
            return eth_macs, wifi_macs, ipv4s

        ptr = ctypes.cast(buf, ctypes.POINTER(_IP_ADAPTER_INFO))
        while ptr:
            info = ptr.contents
            desc = info.Description.decode("ascii", errors="ignore").strip().lower()

            # Thu thập IPv4 đang hoạt động (cả LAN lẫn VPN)
            ip_node_ptr = ctypes.pointer(info.IpAddressList)
            while ip_node_ptr:
                ip_node = ip_node_ptr.contents
                ip_str = ip_node.IpAddress.decode("ascii", errors="ignore").strip()
                if ip_str and ip_str not in ("0.0.0.0", "127.0.0.1") and ip_str not in ipv4s:
                    ipv4s.append(ip_str)
                ip_node_ptr = ip_node.Next

            # Thu thập MAC vật lý (loại trừ card mạng ảo)
            is_virtual = any(k in desc for k in _VIRTUAL_ADAPTER_KEYWORDS)
            if not is_virtual and 6 <= info.AddressLength <= 8:
                mac_bytes = [info.Address[i] for i in range(6)]
                if any(b != 0 for b in mac_bytes) and not all(b == 0xFF for b in mac_bytes):
                    mac_str = "-".join(f"{b:02X}" for b in mac_bytes)
                    # MIB_IF_TYPE_ETHERNET = 6, IEEE80211 = 71
                    is_wifi = (info.Type == 71) or any(w in desc for w in ("wireless", "wi-fi", "wlan", "802.11"))
                    if is_wifi:
                        if mac_str not in wifi_macs:
                            wifi_macs.append(mac_str)
                    elif info.Type == 6:
                        if mac_str not in eth_macs:
                            eth_macs.append(mac_str)
            ptr = info.Next
    except Exception:
        pass
    return eth_macs, wifi_macs, ipv4s


def _get_volume_serial_c():
    if sys.platform != "win32":
        return ""
    try:
        serial = wintypes.DWORD(0)
        max_comp = wintypes.DWORD(0)
        fs_flags = wintypes.DWORD(0)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p("C:\\"),
            None, 0,
            ctypes.byref(serial),
            ctypes.byref(max_comp),
            ctypes.byref(fs_flags),
            None, 0,
        )
        if ok and serial.value:
            return f"{serial.value:08X}"
    except Exception:
        pass
    return ""


def _get_xp_cpu_and_machine_guid():
    cpu_id = ""
    machine_guid = ""
    if sys.platform != "win32":
        return cpu_id, machine_guid
    try:
        import winreg
        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                0,
                winreg.KEY_READ,
            ) as k:
                ident = ""
                pname = ""
                vendor = ""
                try:
                    ident = str(winreg.QueryValueEx(k, "Identifier")[0]).strip()
                except Exception:
                    pass
                try:
                    pname = str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
                except Exception:
                    pass
                try:
                    vendor = str(winreg.QueryValueEx(k, "VendorIdentifier")[0]).strip()
                except Exception:
                    pass
                cpu_id = "|".join(x for x in (vendor, ident, pname) if x)
        except Exception:
            pass

        for flags in (winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0), winreg.KEY_READ):
            try:
                with winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography",
                    0,
                    flags,
                ) as k:
                    val, _ = winreg.QueryValueEx(k, "MachineGuid")
                    if val:
                        machine_guid = str(val).strip()
                        break
            except Exception:
                continue
    except Exception:
        pass
    return cpu_id, machine_guid


def get_hwid(base_dir=None):
    """
    Trả về (hwid_12_digits, formatted_hwid, macs_csv).
    Ưu tiên đọc host_hwid.txt đã lưu để ID cố định vĩnh viễn trên máy XP.
    """
    eth_macs, wifi_macs, _ = _enum_xp_adapters()
    macs_all = []
    for m in eth_macs + wifi_macs:
        if m and m not in macs_all:
            macs_all.append(m)
    if not macs_all:
        try:
            node = uuid.getnode()
            if node and ((node >> 40) & 1) == 0:
                macs_all.append("-".join(f"{(node >> (8 * i)) & 0xFF:02X}" for i in range(5, -1, -1)))
        except Exception:
            pass
    macs_csv = ",".join(macs_all)

    saved = load_saved_hwid(base_dir)
    if saved:
        return saved, format_hwid_display(saved), macs_csv

    cpu_id, machine_guid = _get_xp_cpu_and_machine_guid()
    hdd_serial = _get_volume_serial_c()

    cpu_part = cpu_id or "XP_CPU_FALLBACK"
    hdd_part = hdd_serial or "XP_HDD_FALLBACK"
    guid_part = machine_guid or "XP_GUID_FALLBACK"
    eth_part = ",".join(eth_macs) if eth_macs else (macs_all[0] if macs_all else "XP_MAC_FALLBACK")
    wifi_part = ",".join(wifi_macs) if wifi_macs else "XP_WIFI_NONE"

    combined = f"{cpu_part}_{hdd_part}_{guid_part}_{eth_part}_{wifi_part}".strip()
    sha = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    val = int(sha[:12], 16)
    twelve_digit_val = (val % 900000000000) + 100000000000
    s = str(twelve_digit_val)
    save_hwid(s, base_dir)
    return s, format_hwid_display(s), macs_csv


def get_local_ip():
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.8)
        s.connect(("8.8.8.8", 80))
        primary = s.getsockname()[0]
        s.close()
        if primary and not primary.startswith("127."):
            ips.append(primary)
    except Exception:
        pass

    _, _, adapter_ips = _enum_xp_adapters()
    for ip in adapter_ips:
        if ip not in ips and not ip.startswith("127."):
            ips.append(ip)

    try:
        _, _, host_ips = socket.gethostbyname_ex(socket.gethostname())
        for ip in host_ips:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass

    if not ips:
        ips.append("127.0.0.1")
    return ",".join(ips)


def get_public_ip():
    """Ưu tiên HTTP thuần trước HTTPS vì Windows XP SP3 thường thiếu chứng chỉ Root CA mới."""
    urls = [
        "http://checkip.amazonaws.com",
        "http://api.ipify.org",
        "http://icanhazip.com",
        "https://checkip.amazonaws.com",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                ip = resp.read().decode("utf-8", errors="ignore").strip()
                if ip and "." in ip and len(ip) <= 45:
                    return ip
        except Exception:
            continue
    return "127.0.0.1"
