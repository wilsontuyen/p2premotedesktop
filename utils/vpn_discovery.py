# -*- coding: utf-8 -*-
"""
utils/vpn_discovery.py
Hỗ trợ tự động nhận diện và quét mạng VPN (Windows Built-in VPN, Tailscale, 
ZeroTier, Hamachi, Radmin VPN, WireGuard, OpenVPN và Custom Subnet).
"""

import os
import sys
import socket
import subprocess
import re
import time
import hashlib
import json
import struct
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

try:
    import psutil
except ImportError:
    psutil = None

from network.socket_utils import send_msg, recv_msg, APP_KEY
from core.config import LAN_APP_SIGNATURE, BOUND_PORT


def get_all_local_ipv4():
    """Lấy danh sách tất cả IPv4 của máy cục bộ để loại trừ không quét chính mình."""
    local_ips = set()
    try:
        if psutil:
            for _, addrs in psutil.net_if_addrs().items():
                for a in addrs:
                    if a.family == socket.AF_INET:
                        local_ips.add(a.address)
    except Exception:
        pass
    try:
        _, _, ip_list = socket.gethostbyname_ex(socket.gethostname())
        for ip in ip_list:
            local_ips.add(ip)
    except Exception:
        pass
    local_ips.add("127.0.0.1")
    return local_ips


def detect_vpn_interfaces():
    """
    Tự động phát hiện các kết nối VPN đang hoạt động trên máy:
    1. Windows Built-in VPN (SSTP, IKEv2, L2TP, PPTP, Incoming Connections).
    2. Tailscale (100.64.0.0/10 hoặc interface tailscale).
    3. ZeroTier (interface zerotier / zt).
    4. Hamachi (25.0.0.0/8).
    5. Radmin VPN (26.0.0.0/8).
    6. WireGuard (wireguard / wg).
    7. OpenVPN (tap / tun / openvpn / wintun).
    """
    vpn_list = []
    connected_ras = set()
    
    # 1. Kiểm tra Windows rasdial (Windows Built-in VPN)
    startupinfo = None
    if os.name == 'nt':
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
            res = subprocess.run(['rasdial'], capture_output=True, text=True, startupinfo=startupinfo, timeout=3)
            if res and res.stdout:
                lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                collect = False
                for line in lines:
                    low = line.lower()
                    if any(term in low for term in ("command completed", "no connections", "không có kết nối", "lệnh đã hoàn thành")):
                        break
                    if any(term in low for term in ("connected to", "đã kết nối")):
                        collect = True
                        continue
                    if collect and line:
                        connected_ras.add(line)
                # Fallback nếu collect vẫn False nhưng có danh sách kết nối
                if not connected_ras and len(lines) >= 2:
                    for l in lines[1:-1]:
                        if not any(k in l.lower() for k in ("command", "completed", "lệnh", "không")):
                            connected_ras.add(l)
        except Exception:
            pass

    # 2. Đọc bảng định tuyến route print trên Windows để lấy Gateway/Subnet chính xác
    route_table = []
    if os.name == 'nt' and startupinfo:
        try:
            res_rt = subprocess.run(['route', 'print', '-4'], capture_output=True, text=True, startupinfo=startupinfo, timeout=3)
            if res_rt and res_rt.stdout:
                for line in res_rt.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 5:
                        dest, netmask, gateway, iface, metric = parts[0], parts[1], parts[2], parts[3], parts[4]
                        if re.match(r'^\d+\.\d+\.\d+\.\d+$', dest) and re.match(r'^\d+\.\d+\.\d+\.\d+$', netmask):
                            route_table.append({
                                'dest': dest,
                                'netmask': netmask,
                                'gateway': gateway,
                                'iface': iface,
                                'metric': metric
                            })
        except Exception:
            pass

    if not psutil:
        return vpn_list

    try:
        all_addrs = psutil.net_if_addrs()
    except Exception:
        return vpn_list

    seen_prefixes = set()

    for iface_name, addrs in all_addrs.items():
        ipv4_addrs = [a for a in addrs if a.family == socket.AF_INET]
        if not ipv4_addrs:
            continue
        
        name_lower = iface_name.lower()
        has_mac = any(getattr(a.family, 'name', '') == 'AF_LINK' for a in addrs)
        
        for a in ipv4_addrs:
            ip = a.address
            if ip.startswith('127.') or ip.startswith('169.254.'):
                continue
                
            is_vpn = False
            is_private = (
                ip.startswith('10.') or 
                ip.startswith('192.168.') or 
                ip.startswith('172.') or 
                (ip.startswith('100.') and 64 <= int(ip.split('.')[1]) <= 127) or 
                ip.startswith('25.') or 
                ip.startswith('26.')
            )
            
            # Nhận diện giao diện mạng phụ / đường hầm chung (không phân biệt loại kết nối VPN cụ thể)
            win_if_meta = _get_win_if_by_ip(ip) if os.name == 'nt' else None
            if win_if_meta is not None:
                if win_if_meta.get("is_tunnel") or (not win_if_meta.get("is_default_gw") and not win_if_meta.get("is_hypervisor")):
                    is_vpn = True
            if iface_name in connected_ras or any(k in name_lower for k in (
                "wan miniport", "ikev2", "l2tp", "sstp", "pptp", "vpn", "aua",
                "tailscale", "hamachi", "radmin", "zerotier", "zt", "wireguard", "wg",
                "tap", "tun", "openvpn", "wintun", "anyconnect", "forti", "pangp",
                "globalprotect", "softether", "sonicwall", "warp", "nordlynx", "proton"
            )):
                is_vpn = True
            elif ip.startswith('100.'):
                octets = [int(x) for x in ip.split('.')]
                if len(octets) == 4 and octets[0] == 100 and (64 <= octets[1] <= 127):
                    is_vpn = True
            elif ip.startswith('25.') or ip.startswith('26.'):
                is_vpn = True
            elif is_private and (a.netmask == '255.255.255.255' or (os.name == 'nt' and not has_mac)):
                is_vpn = True

            if is_vpn:
                octs = ip.split('.')
                base_c = f"{octs[0]}.{octs[1]}.{octs[2]}."

                # Tìm gateway hoặc subnet đích tương ứng trong route table (nếu VPN định tuyến sang dải IP khác)
                target_gateway = None
                target_subnet = None
                routed_prefix = None
                for r in route_table:
                    if r['iface'] == ip:
                        if r['dest'] != ip and r['dest'] != '255.255.255.255' and r['dest'] != '0.0.0.0' and not r['dest'].startswith('224.'):
                            target_subnet = f"{r['dest']}/{r['netmask']}"
                            r_octs = r['dest'].split('.')
                            if len(r_octs) == 4 and r['netmask'] == '255.255.255.0':
                                routed_prefix = f"{r_octs[0]}.{r_octs[1]}.{r_octs[2]}."
                            if r['gateway'] != 'On-link' and r['gateway'] != '0.0.0.0':
                                target_gateway = r['gateway']
                            break

                effective_prefix = routed_prefix or base_c
                if effective_prefix in seen_prefixes:
                    continue
                seen_prefixes.add(effective_prefix)

                vpn_list.append({
                    "name": iface_name,
                    "vpn_type": "VPN",
                    "ip": ip,
                    "netmask": a.netmask,
                    "gateway": target_gateway,
                    "target_subnet": target_subnet or f"{effective_prefix}0/24",
                    "base_prefix": effective_prefix,
                    "start": 1,
                    "end": 254
                })

    return vpn_list


import ipaddress
import select
_PHYSICAL_LAN_SUBNETS_CACHE = None
_PHYSICAL_LAN_SUBNETS_TIME = 0


def get_physical_lan_subnets():
    """Lấy danh sách subnet IP của card mạng LAN vật lý cục bộ (loại trừ giao diện đường hầm/VPN và loopback)."""
    global _PHYSICAL_LAN_SUBNETS_CACHE, _PHYSICAL_LAN_SUBNETS_TIME
    now = time.time()
    if _PHYSICAL_LAN_SUBNETS_CACHE is not None and (now - _PHYSICAL_LAN_SUBNETS_TIME) < 5.0:
        return _PHYSICAL_LAN_SUBNETS_CACHE
    subnets = []
    vpn_keywords = (
        'wan miniport', 'ikev2', 'l2tp', 'sstp', 'pptp', 'vpn', 'aua',
        'tailscale', 'hamachi', 'radmin', 'zerotier', 'wireguard', 'openvpn',
        'tap', 'tun', 'wintun', 'anyconnect', 'forti', 'pangp', 'globalprotect',
        'softether', 'sonicwall', 'warp', 'nordlynx', 'proton'
    )
    if os.name == 'nt':
        try:
            for item in _query_windows_ipv4_interfaces():
                if item.get("is_tunnel") or item.get("is_hypervisor"):
                    continue
                descr_low = item.get("descr", "").lower()
                if any(k in descr_low for k in vpn_keywords):
                    continue
                net = item.get("network")
                if net is not None:
                    subnets.append(net)
            if subnets:
                _PHYSICAL_LAN_SUBNETS_CACHE = subnets
                _PHYSICAL_LAN_SUBNETS_TIME = now
                return subnets
        except Exception:
            pass
    try:
        import psutil
        for iface_name, addrs in psutil.net_if_addrs().items():
            name_lower = iface_name.lower()
            is_vpn = any(k in name_lower for k in vpn_keywords)
            for a in addrs:
                if getattr(a.family, "name", "") == 'AF_INET' or a.family == 2:
                    ip = a.address
                    if ip.startswith('127.') or ip.startswith('169.254.'):
                        continue
                    netmask = a.netmask or '255.255.255.0'
                    if netmask == '255.255.255.255':
                        is_vpn = True
                    if not is_vpn:
                        try:
                            net = ipaddress.IPv4Network(f'{ip}/{netmask}', strict=False)
                            subnets.append(net)
                        except Exception:
                            pass
    except Exception:
        pass
    _PHYSICAL_LAN_SUBNETS_CACHE = subnets
    _PHYSICAL_LAN_SUBNETS_TIME = now
    return subnets


def is_in_physical_lan_subnet(target_ip):
    """Kiểm tra xem một hoặc nhiều IP có nằm trong subnet LAN vật lý không."""
    if not target_ip:
        return False
    try:
        subnets = get_physical_lan_subnets()
        if not subnets:
            return False
        for raw in str(target_ip).split(","):
            clean_ip = raw.strip()
            if not clean_ip or clean_ip.startswith("127.") or clean_ip.startswith("169.254."):
                continue
            try:
                ip_obj = ipaddress.IPv4Address(clean_ip)
                if any(ip_obj in net for net in subnets):
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


import threading
_DNS_CACHE = {}
_DNS_LOCK = threading.Lock()
_RESOLVER_POOL = ThreadPoolExecutor(max_workers=8)
DEFAULT_SCAN_PORTS = [12345, 12346]


def get_netbios_info(ip, timeout=0.6):
    """
    Gửi truy vấn NetBIOS Node Status Query (UDP 137) để lấy tên máy Windows và địa chỉ MAC.
    Hoạt động cực nhanh (10-20ms) và trả về tên máy tính thực sự của Windows.
    """
    query = (
        b'\xa2\x48\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00'
        b'\x20CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\x00'
        b'\x00\x21\x00\x01'
    )
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    name = None
    mac = ""
    try:
        sock.sendto(query, (ip, 137))
        data, _ = sock.recvfrom(1024)
        if len(data) > 56:
            num = data[56]
            for i in range(num):
                off = 57 + i * 18
                if off + 18 <= len(data):
                    flags = struct.unpack('>H', data[off+16:off+18])[0]
                    is_group = bool(flags & 0x8000)
                    if data[off+15] == 0x00 and not is_group and not name:
                        raw_name = data[off:off+15].decode('latin1', 'ignore').strip()
                        if raw_name:
                            name = raw_name
            mac_offset = 57 + num * 18
            if mac_offset + 6 <= len(data):
                raw_mac = data[mac_offset:mac_offset+6]
                if any(raw_mac):
                    mac = '-'.join(f'{b:02X}' for b in raw_mac)
    except Exception:
        pass
    finally:
        try: sock.close()
        except: pass
    return name, mac


def get_rdp_name(ip, timeout=0.8):
    """
    Lấy tên máy tính Windows từ chứng chỉ TLS tự ký của cổng RDP (TCP 3389).
    Đặc biệt hữu ích khi máy tính TẮT 'Network Discovery' (khiến UDP 137 bị chặn).
    """
    try:
        import ssl
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        s, _ = connect_tcp_any_route(ip, 3389, timeout=timeout)
        if not s:
            return None
        s.settimeout(timeout)
        # Gói tin RDP Connection Request packet (TPKT + X.224 Connection Request)
        s.send(b'\x03\x00\x00\x13\x0e\xe0\x00\x00\x00\x00\x00\x01\x00\x08\x00\x03\x00\x00\x00')
        resp = s.recv(1024)
        if not resp:
            s.close()
            return None
        ss = ctx.wrap_socket(s)
        cert_bin = ss.getpeercert(binary_form=True)
        ss.close()
        c = x509.load_der_x509_certificate(cert_bin, default_backend())
        for attr in c.subject:
            if attr.oid == x509.oid.NameOID.COMMON_NAME:
                val = str(attr.value).split('.')[0].strip()
                if val and not val.lower().startswith("pc-") and val.lower() not in ("unknown", "không rõ"):
                    return val
    except Exception:
        pass
    return None


def get_mac_from_arp(ip):
    """Lấy địa chỉ MAC từ bảng ARP của hệ điều hành nếu NetBIOS bị chặn hoặc trên LAN."""
    if not ip or ip.startswith('127.') or ip.startswith('169.254.'):
        return ""
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        res = subprocess.run(['arp', '-a', ip], capture_output=True, text=True, startupinfo=startupinfo, timeout=0.5)
        if res and res.stdout:
            m = re.search(r'([0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5})', res.stdout)
            if m:
                mac = m.group(1).replace(':', '-').upper()
                if mac not in ("FF-FF-FF-FF-FF-FF", "00-00-00-00-00-00"):
                    return mac
    except Exception:
        pass
    return ""


def format_mac_address(raw):
    """Chuân hoa dia chi MAC nguoi dung nhap (ho tro dau :, -, khoang trang, hoac dinh lien)."""
    if not raw:
        return ""
    parts = []
    for piece in str(raw).split(","):
        p = piece.strip()
        if not p:
            continue
        cleaned = re.sub(r"[^0-9A-Fa-f]", "", p)
        if len(cleaned) == 12:
            parts.append("-".join(cleaned[i:i+2].upper() for i in range(0, 12, 2)))
        elif p:
            parts.append(p.upper().replace(":", "-"))
    return ",".join(dict.fromkeys(parts))


def resolve_host_info_safe(ip, timeout=0.8):
    """
    Phân giải thông tin máy tính an toàn:
    1. Ưu tiên NetBIOS UDP 137 (cho kết quả tên máy Windows + MAC chính xác nhất)
    2. Thử RDP TLS Certificate cổng 3389 (khi máy tắt Network Discovery như CAMERAPC2025)
    3. Thử bảng ARP của OS để tìm MAC nếu NetBIOS không có
    4. Fallback sang Reverse DNS (socket.gethostbyaddr)
    Trả về: (computer_name, mac, os_name, is_verified)
    """
    with _DNS_LOCK:
        if ip in _DNS_CACHE:
            return _DNS_CACHE[ip]

    # 1. Thử NetBIOS trước (cực kỳ hiệu quả trên mạng Windows VPN & LAN)
    nb_name, nb_mac = get_netbios_info(ip, timeout=0.4)
    if not nb_mac:
        nb_mac = get_mac_from_arp(ip)

    if nb_name:
        res = (nb_name, nb_mac or "", "Windows", True)
        with _DNS_LOCK:
            _DNS_CACHE[ip] = res
        return res

    # 2. Thử RDP TLS Certificate (cực kỳ hữu ích khi Network Discovery bị TẮT như CAMERAPC2025)
    rdp_name = get_rdp_name(ip, timeout=0.5)
    if rdp_name:
        res = (rdp_name, nb_mac or "", "Windows", True)
        with _DNS_LOCK:
            _DNS_CACHE[ip] = res
        return res

    # 3. Thử DNS
    def _do_dns():
        try:
            name, _, _ = socket.gethostbyaddr(ip)
            return name.split('.')[0] if name else None
        except Exception:
            return None

    try:
        f = _RESOLVER_POOL.submit(_do_dns)
        dns_name = f.result(timeout=0.4)
        if dns_name and not dns_name.lower().startswith('pc-') and not dns_name.lower().startswith('unknown-') and dns_name.lower() not in ('unknown', 'không rõ'):
            res = (dns_name, nb_mac or "", "", True)
            with _DNS_LOCK:
                _DNS_CACHE[ip] = res
            return res
    except Exception:
        pass

    # 4. Fallback (không xác thực được tên)
    fallback = f"Unknown-{ip.split('.')[-1]}"
    res = (fallback, nb_mac or "", "", False)
    with _DNS_LOCK:
        _DNS_CACHE[ip] = res
    return res


def resolve_hostname_safe(ip, timeout=0.6):
    """Phân giải tên máy tính an toàn qua Reverse DNS / NetBIOS với bộ nhớ đệm."""
    info = resolve_host_info_safe(ip, timeout=timeout)
    return info[0]


def get_all_lan_peers_json_paths():
    """Trả về tất cả các đường dẫn lan_peers.json tiềm năng (APPDATA, thư mục app, Program Files) để hợp nhất không bao giờ mất máy."""
    paths = []
    appdata = os.environ.get('APPDATA', '')
    if appdata:
        paths.append(os.path.join(appdata, "EasyRemoteDesktop", "lan_peers.json"))
    if getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__') or ("__compiled__" in globals()):
        app_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    inst = os.path.join(app_dir, "lan_peers.json")
    if inst not in paths:
        paths.append(inst)
    if sys.platform == "win32":
        pf_inst = r"C:\Program Files (x86)\Easy Remote Desktop\lan_peers.json"
        if pf_inst not in paths:
            paths.append(pf_inst)
    return paths


def get_lan_peers_json_path():
    """Lấy đường dẫn đầy đủ tới file lan_peers.json, ưu tiên thư mục cài đặt app rồi tới APPDATA."""
    candidates = []
    if getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__') or ("__compiled__" in globals()):
        app_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    inst = os.path.join(app_dir, "lan_peers.json")
    candidates.append(inst)

    if sys.platform == "win32":
        pf_inst = r"C:\Program Files (x86)\Easy Remote Desktop\lan_peers.json"
        if pf_inst not in candidates:
            candidates.append(pf_inst)

    appdata = os.environ.get('APPDATA', '')
    if appdata:
        user_path = os.path.join(appdata, "EasyRemoteDesktop", "lan_peers.json")
        candidates.append(user_path)
    else:
        user_path = inst

    for c_path in candidates:
        if os.path.exists(c_path):
            if os.access(c_path, os.W_OK):
                return c_path
            else:
                try:
                    os.makedirs(os.path.dirname(user_path), exist_ok=True)
                    if not os.path.exists(user_path):
                        import shutil
                        shutil.copy2(c_path, user_path)
                    return user_path
                except Exception:
                    return c_path

    # Nếu chưa có file nào tồn tại, kiểm tra quyền ghi của thư mục app_dir trước
    if os.access(app_dir, os.W_OK):
        return inst
    try:
        os.makedirs(os.path.dirname(user_path), exist_ok=True)
        return user_path
    except Exception:
        return inst


def hash_password_md5(pw):
    """Mã hóa mật khẩu bằng MD5 (32 ký tự hex) để không lưu mật khẩu dạng plaintext trong lan_peers.json."""
    if not pw:
        return ""
    pw_str = str(pw).strip()
    if len(pw_str) == 32 and all(c in "0123456789abcdefABCDEF" for c in pw_str):
        return pw_str.lower()
    return hashlib.md5(pw_str.encode('utf-8')).hexdigest()


def get_last_seen_epoch(val):
    """Chuyển đổi last_seen (float/int hoặc chuỗi datetime full 'YYYY-MM-DD HH:MM:SS') thành timestamp float an toàn."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return 0.0
        try:
            return datetime.strptime(val, "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            try:
                return float(val)
            except Exception:
                return 0.0
    return 0.0


def format_last_seen_str(val=None):
    """Định dạng timestamp thành chuỗi ngày giờ full 'YYYY-MM-DD HH:MM:SS' để lưu vào lan_peers.json."""
    if val is None:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, str) and "-" in val and ":" in val:
        return val
    try:
        ts = float(val)
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_name_tokens(s):
    """Chuẩn hóa tên máy thành các token cốt lõi (bỏ qua tag generic như server, pc, laptop, năm 20xx, số thứ tự)."""
    s = str(s or '').strip().lower()
    s = re.sub(r'[@_\-\.\(\)\:\/]+', ' ', s).strip()
    s = re.sub(r'(?<=[a-zA-Z])(?=\d)', ' ', s)
    s = re.sub(r'(?<=\d)(?=[a-zA-Z])', ' ', s)
    # Tách các âm ghép tiếng Việt phổ biến (như hathuong -> ha thuong, minhthuong -> minh thuong)
    s = re.sub(r'([aeiouy])(?=(?:th|ch|tr|nh|ngh|ng|kh|ph|gh|gi)[aeiouy])', r'\1 ', s)
    for tag in ['server', 'laptop', 'desktop', 'office', 'pc', 'home', 'ketoan', 'thukho', 'vanphong', 'kythuat', 'kinhdoanh', 'nhansu', 'baove', 'admin', 'letan', 'banhang', 'thuquy']:
        s = re.sub(rf'(?<=[a-zA-Z]){tag}\b', f' {tag}', s)
    tokens = [t for t in s.split() if t]
    filtered = [
        t for t in tokens
        if t not in ('server', 'office', 'pc', 'laptop', 'desktop', 'home', 'may', 'test', 'new', 'old', 'ketoan', 'thukho', 'vanphong', 'kythuat', 'kinhdoanh', 'nhansu', 'baove', 'admin', 'letan', 'banhang', 'thuquy')
        and not (t.isdigit() and len(t) == 4 and t.startswith('20'))
        and not (t.isdigit() and len(t) <= 3)
    ]
    return filtered, ''.join(filtered)


def match_saved_computer(comp_name=None, hwid=None, saved_id=None):
    """Tìm máy tính trong danh sách đã lưu:
    1. Trùng HWID/ID chính xác (100% an toàn theo đúng yêu cầu).
    2. Trùng tên máy tính chính xác (case-insensitive).
    3. Trùng khớp token tên cốt lõi (ví dụ: CAMERAPC2025 <-> CAMERA SERVER, VMAS2025 <-> VMAS2026).
    4. Trùng khớp token tên ghép cốt lõi có ý nghĩa (ví dụ: HATHUONG2024 <-> THUONG DN, VANKETOAN <-> VAN OFFICE).
    TUYỆT ĐỐI không dùng chuỗi con (substring) đơn thuần để tránh nhận diện nhầm (ví dụ: BINHDINH002 thành BINH LAPTOP).
    """
    try:
        from pclist import SavedListMixin
        saved = SavedListMixin().load_saved_computers()
    except Exception:
        return None

    if not saved:
        return None

    # 1. Khớp theo HWID hoặc saved_id chính xác (ưu tiên HWID thực tế trước, ưu tiên bản ghi mới nhất ở cuối danh sách nếu trùng ID)
    id_candidates = [''.join(ch for ch in str(x or '') if ch.isdigit()) for x in (hwid, saved_id) if x]
    id_candidates = [x for x in id_candidates if x]
    for cand_id in id_candidates:
        for c in reversed(saved):
            c_clean_id = ''.join(ch for ch in c.get('id', '') if ch.isdigit())
            if c_clean_id and c_clean_id == cand_id and c.get('password'):
                return c
        for c in reversed(saved):
            c_clean_id = ''.join(ch for ch in c.get('id', '') if ch.isdigit())
            if c_clean_id and c_clean_id == cand_id:
                return c

    if not comp_name:
        return None
    cn = str(comp_name).strip().lower()
    if not cn or re.match(r"^(unknown|pc)-\d+$", cn) or cn in ("unknown", "không rõ"):
        return None

    # 2. Khớp tên chính xác hoàn toàn (case-insensitive, ưu tiên bản ghi mới nhất có mật khẩu)
    for c in reversed(saved):
        c_raw = c.get("name", "").strip().lower()
        if c_raw and c_raw == cn and c.get("password"):
            return c
    for c in reversed(saved):
        c_raw = c.get("name", "").strip().lower()
        if c_raw and c_raw == cn:
            return c

    # 3. Khớp theo token tên cốt lõi (loại trừ các hậu tố/tiền tố generic: server, pc, laptop, năm 20xx)
    cn_tokens, cn_str = normalize_name_tokens(cn)
    if cn_tokens:
        # Ưu tiên khớp tập token giống hệt nhau 100% (ưu tiên có password mới nhất)
        for c in reversed(saved):
            sn_tokens, sn_str = normalize_name_tokens(c.get("name", ""))
            if sn_tokens and cn_tokens == sn_tokens and c.get("password"):
                return c
        for c in reversed(saved):
            sn_tokens, sn_str = normalize_name_tokens(c.get("name", ""))
            if sn_tokens and cn_tokens == sn_tokens:
                return c

        # Khớp chuỗi ký tự cốt lõi (ví dụ 'binhdinh' vs 'binh dinh')
        if len(cn_str) >= 4:
            for c in reversed(saved):
                sn_tokens, sn_str = normalize_name_tokens(c.get("name", ""))
                if sn_str and cn_str == sn_str and c.get("password"):
                    return c
            for c in reversed(saved):
                sn_tokens, sn_str = normalize_name_tokens(c.get("name", ""))
                if sn_str and cn_str == sn_str:
                    return c

        # 4. Khớp theo token cốt lõi mang ý nghĩa định danh (độ dài >= 4 ký tự, ví dụ 'thuong' trong HATHUONG <-> THUONG DN)
        candidates = []
        for c in reversed(saved):
            sn_tokens, sn_str = normalize_name_tokens(c.get("name", ""))
            common = set(cn_tokens).intersection(set(sn_tokens))
            meaningful_common = [t for t in common if len(t) >= 4 and t not in ('dinh', 'quang', 'ninh', 'nam')]
            if meaningful_common:
                candidates.append((c, meaningful_common))

        if candidates:
            # Nếu có nhiều ứng viên (ví dụ THUONG DN và THUONG LAPTOP):
            # Ưu tiên khớp đúng chủng loại thiết bị (laptop vs desktop) và có password
            is_laptop = 'laptop' in cn
            matched_c = None
            for c, _ in candidates:
                c_name_lower = c.get('name', '').lower()
                c_is_laptop = 'laptop' in c_name_lower
                if is_laptop == c_is_laptop and c.get('password'):
                    matched_c = c
                    break
            if not matched_c:
                for c, _ in candidates:
                    c_name_lower = c.get('name', '').lower()
                    c_is_laptop = 'laptop' in c_name_lower
                    if is_laptop == c_is_laptop:
                        matched_c = c
                        break
            if not matched_c:
                matched_c = candidates[0][0]
            return matched_c

    return None



_SHARED_VIRTUAL_MAC_PREFIXES = (
    "0A0027",        # VirtualBox Host-Only
    "005056C0",      # VMware VMnet1 / VMnet8
    "02004C4F4F50",  # Npcap / Wireshark Loopback Adapter
    "00FF",          # TAP-Windows / OpenVPN Virtual Adapter
    "0242AC",        # Docker Bridge
    "00155D",        # Hyper-V / WSL Virtual Switch
)


def _is_valid_unique_physical_mac(hex_mac):
    if not hex_mac or len(hex_mac) != 12:
        return False
    u = hex_mac.upper()
    if all(c == '0' for c in u) or all(c == 'F' for c in u):
        return False
    if any(u.startswith(pfx) for pfx in _SHARED_VIRTUAL_MAC_PREFIXES):
        return False
    return True


def _is_real_verified_name(peer_dict):
    if not peer_dict or not peer_dict.get("name_verified"):
        return False
    nm = str(peer_dict.get("computer_name") or "").strip().lower().split('.')[0].strip()
    if not nm or nm in ("unknown", "không rõ", "localhost"):
        return False
    if re.match(r"^unknown-\d+$", nm) or re.match(r"^\d+\.\d+\.\d+\.\d+$", nm):
        return False
    return True


def _is_exact_saved_match(matched_comp, comp_name=None, hwid=None):
    """Chỉ trả về True khi bản ghi trong saved_computers khớp CHÍNH XÁC 100% theo ID 12 số hoặc tên máy (không khớp mờ theo từ đơn)."""
    if not matched_comp:
        return False
    m_id = ''.join(ch for ch in str(matched_comp.get("id") or "") if ch.isdigit())
    h_id = ''.join(ch for ch in str(hwid or "") if ch.isdigit())
    if len(m_id) == 12 and len(h_id) == 12 and m_id == h_id:
        return True
    m_name = str(matched_comp.get("name") or "").strip().lower()
    c_name = str(comp_name or "").strip().lower()
    if m_name and c_name and m_name == c_name:
        return True
    return False


def are_same_machine(hwid1, p1, hwid2, p2):
    """
    Kiểm tra xem 2 bản ghi có thuộc về cùng 1 máy tính vật lý hay không.
    Nguyên tắc an toàn tuyệt đối (không tự động gộp nhầm làm mất máy):
    - Nếu cả 2 có HWID 12 số đã xác thực khác nhau -> CHẮC CHẮN là 2 máy khác nhau (kể cả trùng tên ADMIN hay trùng IP cũ).
    - Nếu cả 2 có tên máy tính đã xác thực khác nhau (và không cùng HWID 12 số đã xác thực) -> CHẮC CHẮN là 2 máy khác nhau.
    """
    if not p1 or not p2:
        return False

    h1_ver = ''.join(ch for ch in str(p1.get("hwid") or hwid1 or "") if ch.isdigit())
    h2_ver = ''.join(ch for ch in str(p2.get("hwid") or hwid2 or "") if ch.isdigit())

    # Bảo vệ 1: Hai HWID 12 số đã xác thực khác nhau -> tuyệt đối KHÔNG bao giờ gộp (dù trùng tên máy hay trùng IP DHCP cũ)
    if p1.get("hwid_verified") and p2.get("hwid_verified") and len(h1_ver) == 12 and len(h2_ver) == 12:
        return h1_ver == h2_ver

    n1 = str(p1.get("computer_name") or "").strip().lower()
    n2 = str(p2.get("computer_name") or "").strip().lower()
    n1_clean = n1.split('.')[0].strip()
    n2_clean = n2.split('.')[0].strip()
    real_v1 = _is_real_verified_name(p1)
    real_v2 = _is_real_verified_name(p2)

    # 1. Trùng HWID chính xác (khi cả 2 không mâu thuẫn tên đã xác thực)
    id_set_1 = {''.join(ch for ch in str(x) if ch.isdigit()) for x in (hwid1, p1.get("hwid")) if x}
    id_set_1.discard('')
    id_set_2 = {''.join(ch for ch in str(x) if ch.isdigit()) for x in (hwid2, p2.get("hwid")) if x}
    id_set_2.discard('')
    if id_set_1 and id_set_2 and id_set_1.intersection(id_set_2):
        # Nếu một bên chỉ là synthetic hash mà hai tên máy xác thực lại khác nhau -> không gộp nhầm
        if real_v1 and real_v2 and n1_clean != n2_clean and not (p1.get("hwid_verified") and p2.get("hwid_verified")):
            return False
        return True

    # Bảo vệ 2: Hai tên máy tính thực sự đã xác thực khác nhau -> KHÔNG gộp theo MAC ảo, saved_id mờ hay IP DHCP cũ
    if real_v1 and real_v2 and n1_clean != n2_clean:
        return False

    # 2. Trùng MAC vật lý 6-byte duy nhất (loại trừ toàn bộ MAC card ảo VirtualBox/VMware/Npcap/TAP/Docker/Hyper-V)
    macs1 = [re.sub(r'[^A-Fa-f0-9]', '', m).upper() for m in str(p1.get("macs", "")).split(",") if m.strip()]
    macs2 = [re.sub(r'[^A-Fa-f0-9]', '', m).upper() for m in str(p2.get("macs", "")).split(",") if m.strip()]
    valid_macs1 = [m for m in macs1 if _is_valid_unique_physical_mac(m)]
    valid_macs2 = [m for m in macs2 if _is_valid_unique_physical_mac(m)]
    if valid_macs1 and valid_macs2:
        if any(m in valid_macs2 for m in valid_macs1):
            return True

    # 3. Trùng tên máy tính đã xác thực (ví dụ cùng 1 máy đổi IP DHCP/VPN mới)
    if n1_clean and n2_clean and n1_clean == n2_clean:
        if n1_clean not in ("unknown", "không rõ", "localhost") and not re.match(r"^\d+\.\d+\.\d+\.\d+$", n1_clean):
            if not re.match(r"^unknown-\d+$", n1_clean):
                if not re.match(r"^pc-\d+$", n1_clean) or (p1.get("name_verified") and p2.get("name_verified")):
                    return True

    # 4. Trùng IP thực tế CHỈ khi cả 2 cùng là fallback chưa xác thực trên cùng source_ip
    # (Tuyệt đối KHÔNG gộp một IP fallback Unknown-xxx vào một máy đã có tên xác thực để tránh mất máy cũ khi DHCP cấp lại IP)
    src1 = str(p1.get("source_ip") or "").strip()
    src2 = str(p2.get("source_ip") or "").strip()
    if not real_v1 and not real_v2:
        ips1 = [x.strip() for x in (str(p1.get("local_ip", "")) + "," + src1).split(",") if x.strip() and not x.strip().startswith("127.") and x.strip() != "192.168.56.1"]
        ips2 = [x.strip() for x in (str(p2.get("local_ip", "")) + "," + src2).split(",") if x.strip() and not x.strip().startswith("127.") and x.strip() != "192.168.56.1"]
        if set(ips1).intersection(set(ips2)) and (not src1 or not src2 or src1 == src2):
            return True

    return False


def merge_peers(p_winner, p_loser):
    """
    Gộp thông tin của 2 bản ghi cùng máy tính:
    - p_winner là bản ghi ưu tiên (ví dụ: bản ghi vừa probe online thành công hoặc có last_seen mới hơn).
    - p_loser là bản ghi cũ cần gộp vào.
    - Giữ lại các IP cũ bổ sung vào local_ip (không xóa IP nào, đặt IP mới lên đầu).
    - Giữ lại MAC, mật khẩu đã lưu (saved_password), saved_id, tên verified từ bản ghi cũ nếu winner bị thiếu.
    """
    res = dict(p_winner)

    # 1. Gộp local_ip (IP mới nhất của winner đứng trước, sau đó là các IP khác)
    winner_ips = [x.strip() for x in (str(p_winner.get("local_ip", "")) + "," + str(p_winner.get("source_ip", ""))).split(",") if x.strip() and not x.strip().startswith("127.")]
    loser_ips = [x.strip() for x in (str(p_loser.get("local_ip", "")) + "," + str(p_loser.get("source_ip", ""))).split(",") if x.strip() and not x.strip().startswith("127.")]
    merged_ips = list(dict.fromkeys(winner_ips + loser_ips))
    if merged_ips:
        res["local_ip"] = ",".join(merged_ips)

    # 2. Gộp MAC
    w_macs = [x.strip() for x in str(p_winner.get("macs", "")).split(",") if x.strip()]
    l_macs = [x.strip() for x in str(p_loser.get("macs", "")).split(",") if x.strip()]
    merged_macs = list(dict.fromkeys(w_macs + l_macs))
    if merged_macs:
        res["macs"] = ",".join(merged_macs)

    # 3. Tên máy tính (ưu tiên tên đã verified hoặc tên rõ ràng, không generic)
    w_name = str(res.get("computer_name") or "").strip()
    l_name = str(p_loser.get("computer_name") or "").strip()
    loser_is_verified = bool(p_loser.get("name_verified"))
    winner_is_verified = bool(res.get("name_verified"))
    if loser_is_verified and not winner_is_verified and l_name:
        res["computer_name"] = l_name
        res["name_verified"] = True
        # Nếu loser đã có danh tính verified còn winner chỉ là probe fallback unverified,
        # giữ lại HWID và saved_id chuẩn của loser
        if p_loser.get("hwid"):
            res["hwid"] = p_loser["hwid"]
        if p_loser.get("saved_id"):
            res["saved_id"] = p_loser["saved_id"]
    elif (not w_name or w_name.lower() in ("unknown", "không rõ") or re.match(r"^(unknown|pc)-\d+$", w_name.lower())) and l_name and not re.match(r"^(unknown|pc)-\d+$", l_name.lower()):
        res["computer_name"] = l_name
        res["name_verified"] = p_loser.get("name_verified", False)
        if p_loser.get("saved_id") and not res.get("saved_id"):
            res["saved_id"] = p_loser["saved_id"]

    # 4. OS
    if not res.get("os") and p_loser.get("os"):
        res["os"] = p_loser["os"]

    # 5. Saved Password & Saved ID
    if not res.get("lan_password_enc") and p_loser.get("lan_password_enc"):
        res["lan_password_enc"] = p_loser["lan_password_enc"]
    if not res.get("saved_password") and p_loser.get("saved_password"):
        res["saved_password"] = p_loser["saved_password"]
    w_hwid = ''.join(ch for ch in str(res.get("hwid") or "") if ch.isdigit())
    l_hwid = ''.join(ch for ch in str(p_loser.get("hwid") or "") if ch.isdigit())
    winner_is_synthetic = (res.get("hwid_verified") is False)
    loser_is_synthetic = (p_loser.get("hwid_verified") is False)

    # Bảo vệ HWID đã xác thực không bao giờ bị ghi đè bởi synthetic hash
    if winner_is_synthetic and not loser_is_synthetic and len(l_hwid) == 12:
        res["hwid"] = l_hwid
        res["saved_id"] = p_loser.get("saved_id") or l_hwid
        res["hwid_verified"] = True
    elif w_hwid and len(w_hwid) == 12:
        l_sid = ''.join(ch for ch in str(p_loser.get("saved_id") or "") if ch.isdigit())
        if l_sid == w_hwid:
            res["saved_id"] = p_loser["saved_id"]
        elif not res.get("saved_id") or ''.join(ch for ch in str(res.get("saved_id") or "") if ch.isdigit()) != w_hwid:
            res["saved_id"] = w_hwid
    else:
        if not res.get("saved_id") and p_loser.get("saved_id"):
            res["saved_id"] = p_loser["saved_id"]

    # 6. Network type (chuẩn hóa chung thành LAN hoặc VPN, không phân biệt giao thức VPN cụ thể)
    w_net = str(res.get("network_type") or "").strip()
    l_net = str(p_loser.get("network_type") or "").strip()
    if (not w_net or w_net.upper() == "LAN") and l_net and l_net.upper() != "LAN":
        res["network_type"] = "VPN"
    elif w_net and w_net.upper() != "LAN":
        res["network_type"] = "VPN"

    return res


def deduplicate_lan_peers(peers_dict):
    """
    Khử trùng lặp danh sách máy tính trong mạng LAN & VPN:
    - Nếu 1 máy tính có nhiều bản ghi (do đổi IP VPN/DHCP hoặc nhiều card mạng),
      gộp lại thành 1 dòng duy nhất.
    - Giữ lại bản ghi có last_seen mới nhất làm bản ghi gốc (winner) và bổ sung
      đầy đủ các IP, MAC, mật khẩu đã lưu từ các bản ghi cũ.
    """
    if not peers_dict or not isinstance(peers_dict, dict):
        return {}

    items = list(peers_dict.items())
    # Sắp xếp theo epoch giảm dần: máy có last_seen gần nhất sẽ đứng trước và làm winner
    items.sort(key=lambda x: get_last_seen_epoch(x[1].get("last_seen", 0)), reverse=True)

    deduped = {}
    for hwid, p in items:
        matched_key = None
        for m_key, m_p in deduped.items():
            if are_same_machine(m_key, m_p, hwid, p):
                matched_key = m_key
                break

        if matched_key:
            deduped[matched_key] = merge_peers(deduped[matched_key], p)
        else:
            deduped[hwid] = dict(p)

    return deduped


def make_stable_hwid(ip, comp_name="", mac=""):
    """
    Tạo HWID 12 chữ số cố định cho máy từ xa nếu máy đó là bản cũ chưa gửi HWID:
    - Ưu tiên 1: Địa chỉ MAC vật lý cố định (không đổi theo IP).
    - Ưu tiên 2: Tên máy tính đã xác định (không đổi khi đổi IP DHCP/VPN).
    - Ưu tiên 3: IP cục bộ (khi hoàn toàn không có MAC và tên máy).
    """
    clean_mac = re.sub(r'[^A-Fa-f0-9]', '', (mac or "").split(',')[0]).upper()
    if len(clean_mac) >= 12:
        seed = f"PEER_MAC_{clean_mac[:12]}".encode('utf-8')
    else:
        cn = (comp_name or "").strip().upper()
        # Loại trừ tên generic hoặc IP
        if cn and cn not in ("UNKNOWN", "KHÔNG RÕ", "LOCALHOST") and not re.match(r"^\d+\.\d+\.\d+\.\d+$", cn) and not re.match(r"^(PC|UNKNOWN)-\d+$", cn):
            seed = f"PEER_NAME_{cn}".encode('utf-8')
        else:
            seed = f"VPN_STABLE_{ip}_{comp_name}".encode('utf-8')
    val = int(hashlib.sha256(seed).hexdigest()[:12], 16)
    twelve = (val % 900000000000) + 100000000000
    return str(twelve)


_WIN_IF_CACHE = None
_WIN_IF_TIME = 0
_TUNNEL_IF_CACHE = None
_TUNNEL_IF_TIME = 0


def _query_windows_ipv4_interfaces():
    """
    Đọc danh sách toàn bộ giao diện IPv4 đang hoạt động từ iphlpapi (GetIpAddrTable + GetIfEntry + GetBestInterface)
    hoàn toàn không phụ thuộc tên phần mềm VPN hay loại kết nối VPN (PPTP, L2TP, SSTP, IKEv2, WireGuard,
    OpenVPN TUN/TAP/Wintun, Tailscale, ZeroTier, Radmin, Hamachi, SoftEther, AnyConnect, FortiClient...).
    """
    global _WIN_IF_CACHE, _WIN_IF_TIME
    if os.name != 'nt':
        return []
    now = time.time()
    if _WIN_IF_CACHE is not None and (now - _WIN_IF_TIME) < 5.0:
        return _WIN_IF_CACHE

    items = []
    try:
        import ctypes
        iphlp = ctypes.windll.iphlpapi

        # Xác định interface mặc định đi Internet hiện tại (nếu có)
        default_gw_if = 0
        try:
            best_inet = ctypes.c_ulong(0)
            inet_dword = struct.unpack('<I', socket.inet_aton('8.8.8.8'))[0]
            if iphlp.GetBestInterface(inet_dword, ctypes.byref(best_inet)) == 0:
                default_gw_if = int(best_inet.value)
        except Exception:
            default_gw_if = 0

        sz = ctypes.c_ulong(0)
        iphlp.GetIpAddrTable(None, ctypes.byref(sz), 0)
        if sz.value > 0:
            buf = ctypes.create_string_buffer(sz.value)
            if iphlp.GetIpAddrTable(buf, ctypes.byref(sz), 0) == 0:
                n = struct.unpack_from('<I', buf, 0)[0]
                for i in range(n):
                    off = 4 + i * 24
                    if off + 12 > len(buf.raw):
                        continue
                    addr_str = socket.inet_ntoa(buf.raw[off:off + 4])
                    if_idx = int(struct.unpack_from('<I', buf, off + 4)[0])
                    mask_str = socket.inet_ntoa(buf.raw[off + 8:off + 12])
                    if (
                        not addr_str
                        or addr_str == '0.0.0.0'
                        or addr_str.startswith('127.')
                        or addr_str.startswith('169.254.')
                    ):
                        continue

                    if_type = 0
                    phys_len = 0
                    descr = ""
                    try:
                        # MIB_IFROW chuẩn 860 bytes trên cả x86 & x64
                        ifrow = ctypes.create_string_buffer(860)
                        struct.pack_into('<I', ifrow, 512, if_idx)
                        if iphlp.GetIfEntry(ifrow) == 0:
                            if_type = int(struct.unpack_from('<I', ifrow, 516)[0])
                            phys_len = int(struct.unpack_from('<I', ifrow, 528)[0])
                            dlen = min(256, int(struct.unpack_from('<I', ifrow, 600)[0]))
                            descr = ifrow.raw[604:604 + dlen].rstrip(b'\x00').decode('latin1', 'ignore').strip()
                    except Exception:
                        pass

                    descr_low = descr.lower()
                    is_hypervisor = any(h in descr_low for h in (
                        'virtualbox host-only', 'vmware virtual ethernet', 'vmnet',
                        'hyper-v virtual ethernet', 'wsl', 'loopback'
                    )) or addr_str == '192.168.56.1'

                    # MIB_IF_TYPE_PPP=23, IF_TYPE_PROP_VIRTUAL=53, IF_TYPE_TUNNEL=131, hoặc /32 point-to-point, hoặc không có MAC vật lý
                    is_tunnel_type = (
                        mask_str == '255.255.255.255'
                        or if_type in (23, 53, 131)
                        or phys_len == 0
                        or any(k in descr_low for k in (
                            'miniport', 'vpn', 'tap', 'tun', 'wintun', 'wireguard',
                            'zerotier', 'tailscale', 'radmin', 'hamachi', 'anyconnect',
                            'forti', 'pangp', 'globalprotect', 'softether', 'sonicwall',
                            'warp', 'nordlynx', 'proton'
                        ))
                    ) and not is_hypervisor

                    net_obj = None
                    if mask_str and mask_str != '255.255.255.255':
                        try:
                            net_obj = ipaddress.IPv4Network(f"{addr_str}/{mask_str}", strict=False)
                        except Exception:
                            net_obj = None

                    items.append({
                        "if_idx": if_idx,
                        "ip": addr_str,
                        "mask": mask_str,
                        "network": net_obj,
                        "if_type": if_type,
                        "descr": descr,
                        "is_tunnel": is_tunnel_type,
                        "is_hypervisor": is_hypervisor,
                        "is_default_gw": (if_idx == default_gw_if),
                    })
    except Exception:
        pass

    _WIN_IF_CACHE = items
    _WIN_IF_TIME = now
    return items


def _get_win_if_by_ip(ip):
    for item in _query_windows_ipv4_interfaces():
        if item.get("ip") == ip:
            return item
    return None


def _get_best_if_index_win(target_ip):
    """Truy vấn nhanh interface index mà Windows OS sẽ định tuyến mặc định cho target_ip."""
    if os.name != 'nt':
        return 0
    try:
        import ctypes
        best_idx = ctypes.c_ulong(0)
        dest_dword = struct.unpack('<I', socket.inet_aton(target_ip))[0]
        if ctypes.windll.iphlpapi.GetBestInterface(dest_dword, ctypes.byref(best_idx)) == 0:
            return int(best_idx.value)
    except Exception:
        pass
    return 0


def get_vpn_tunnel_if_indices():
    """
    Lấy danh sách (if_index, ip) của mọi giao diện đường hầm / mạng phụ đang hoạt động trên Windows
    (hoàn toàn không phân biệt kiểu kết nối VPN: PPTP, L2TP, SSTP, IKEv2, WireGuard, OpenVPN TUN/TAP/Wintun,
    Tailscale, ZeroTier, Radmin, Hamachi, SoftEther, Cisco AnyConnect, FortiClient...).
    """
    global _TUNNEL_IF_CACHE, _TUNNEL_IF_TIME
    if os.name != 'nt':
        return []
    now = time.time()
    if _TUNNEL_IF_CACHE is not None and (now - _TUNNEL_IF_TIME) < 5.0:
        return _TUNNEL_IF_CACHE

    tunnels = []
    seen_idx = set()
    for item in _query_windows_ipv4_interfaces():
        if item.get("is_hypervisor"):
            continue
        if item.get("is_tunnel") or not item.get("is_default_gw"):
            idx = item["if_idx"]
            if idx not in seen_idx:
                seen_idx.add(idx)
                tunnels.append((idx, item["ip"]))

    _TUNNEL_IF_CACHE = tunnels
    _TUNNEL_IF_TIME = now
    return tunnels


def _get_alternate_route_candidates(target_ip):
    """
    Trả về danh sách (if_idx, if_ip, is_tunnel_bool) các giao diện mạng thay thế cần thử song song
    nếu định tuyến mặc định của hệ điều hành (best_if_idx) không kết nối được tới target_ip.
    Hỗ trợ đầy đủ:
    - Split-tunnel VPN không đẩy default gateway / route cho subnet từ xa (IKEv2, L2TP, PPTP, WireGuard, OpenVPN...).
    - Nhiều kết nối VPN bật đồng thời (ví dụ cả IKEv2 lẫn L2TP cùng hoạt động).
    - Trùng lặp dải IP giữa mạng LAN cục bộ và mạng từ xa qua bất kỳ loại VPN nào (/32 hoặc /24).
    """
    if os.name != 'nt':
        return [], False

    all_ifs = _query_windows_ipv4_interfaces()
    if not all_ifs:
        return [], False

    best_if = _get_best_if_index_win(target_ip)
    best_is_tunnel = False
    for item in all_ifs:
        if item["if_idx"] == best_if:
            best_is_tunnel = bool(item.get("is_tunnel"))
            break

    try:
        ip_obj = ipaddress.IPv4Address(target_ip)
    except Exception:
        return [], best_is_tunnel

    candidates = []
    seen_idx = set()
    for item in all_ifs:
        idx = item["if_idx"]
        if idx == best_if or idx in seen_idx or item["ip"] == target_ip:
            continue
        net_obj = item.get("network")
        in_subnet = bool(net_obj is not None and ip_obj in net_obj)
        if item.get("is_hypervisor") and not in_subnet:
            continue
        # Thử giao diện này nếu:
        # 1) Nó là giao diện đường hầm/VPN bất kỳ, HOẶC
        # 2) target_ip nằm trực tiếp trong subnet của giao diện (ví dụ LAN cục bộ bị route VPN metric thấp đè lên), HOẶC
        # 3) Nó là card mạng phụ (không phải cổng Internet mặc định)
        if item.get("is_tunnel") or in_subnet or not item.get("is_default_gw"):
            seen_idx.add(idx)
            candidates.append((idx, item["ip"], bool(item.get("is_tunnel") or not in_subnet)))

    return candidates, best_is_tunnel


def connect_tcp_any_route(ip, port, timeout=1.05):
    """
    Kết nối TCP đa tuyến (Happy-Eyeballs) tới (ip, port) hoàn toàn không phân biệt kiểu kết nối VPN:
    1. Khởi tạo kết nối theo định tuyến mặc định của hệ điều hành ngay lập tức (0ms).
       Nếu kết nối thành công nhanh trong 120ms đầu (99% trường hợp LAN / VPN thông thường), trả về ngay mà không mở thêm socket phụ.
    2. Nếu quá 120ms chưa hoàn tất hoặc bị từ chối sớm trên tuyến mặc định, tự động kích hoạt song song (non-blocking select)
       qua tất cả các giao diện đường hầm / mạng phụ hợp lệ bằng IP_UNICAST_IF trong cùng khung thời gian timeout.
       Tuyến nào bắt tay TCP thành công trước sẽ thắng ngay lập tức và đóng các socket còn lại.
    Trả về: (connected_socket, used_vpn_tunnel_bool) hoặc (None, False)
    """
    if not ip:
        return None, False

    if os.name != 'nt':
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((ip, port))
            return s, False
        except Exception:
            try:
                s.close()
            except Exception:
                pass
            return None, False

    alt_candidates, best_is_tunnel = _get_alternate_route_candidates(ip)

    # Nếu không có giao diện thay thế nào khác -> dùng connect chuẩn gọn nhẹ
    if not alt_candidates:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect((ip, port))
            return s, best_is_tunnel
        except Exception:
            try:
                s.close()
            except Exception:
                pass
            return None, False

    # Non-blocking Staggered Happy-Eyeballs trên tuyến mặc định + các giao diện thay thế
    active = {}  # sock -> is_tunnel_bool
    deadline = time.monotonic() + max(0.25, float(timeout))

    def _close_all(except_sock=None):
        for sk in list(active.keys()):
            if sk is not except_sock:
                try:
                    sk.close()
                except Exception:
                    pass
        active.clear()

    def _start_nb_socket(if_idx=None, is_tun=False):
        sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sk.setblocking(False)
            if if_idx is not None:
                # IPPROTO_IP = 0, IP_UNICAST_IF = 31 (network byte order)
                sk.setsockopt(socket.IPPROTO_IP, 31, struct.pack('!I', int(if_idx)))
            rc = sk.connect_ex((ip, int(port)))
            if rc == 0:
                sk.setblocking(True)
                sk.settimeout(timeout)
                return sk  # Kết nối tức thì
            # WSAEWOULDBLOCK=10035, EINPROGRESS=10036/115
            if rc in (10035, 10036, 115):
                active[sk] = is_tun
                return None
        except Exception:
            pass
        try:
            sk.close()
        except Exception:
            pass
        return None

    try:
        # Bước 1: Thử tuyến mặc định của OS trước trong tối đa 120ms
        imm = _start_nb_socket(if_idx=None, is_tun=best_is_tunnel)
        if imm is not None:
            return imm, best_is_tunnel

        if active:
            head_start = min(0.12, max(0.02, deadline - time.monotonic()))
            sk_list = list(active.keys())
            _, wlist, xlist = select.select([], sk_list, sk_list, head_start)
            for sk in wlist:
                if sk in active and sk.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0:
                    won_tun = active[sk]
                    _close_all(except_sock=sk)
                    sk.setblocking(True)
                    sk.settimeout(timeout)
                    return sk, won_tun
            for sk in set(wlist + xlist):
                if sk in active:
                    active.pop(sk, None)
                    try:
                        sk.close()
                    except Exception:
                        pass

        # Bước 2: Mở song song trên các giao diện đường hầm / mạng thay thế trong phần thời gian còn lại
        for if_idx, _if_ip, is_tun in alt_candidates:
            imm_alt = _start_nb_socket(if_idx=if_idx, is_tun=is_tun)
            if imm_alt is not None:
                _close_all(except_sock=imm_alt)
                return imm_alt, is_tun

        while active:
            rem = deadline - time.monotonic()
            if rem <= 0:
                break
            sk_list = list(active.keys())
            _, wlist, xlist = select.select([], sk_list, sk_list, min(rem, 0.25))
            for sk in wlist:
                if sk in active and sk.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR) == 0:
                    won_tun = active[sk]
                    _close_all(except_sock=sk)
                    sk.setblocking(True)
                    sk.settimeout(timeout)
                    return sk, won_tun
            for sk in set(wlist + xlist):
                if sk in active:
                    active.pop(sk, None)
                    try:
                        sk.close()
                    except Exception:
                        pass
    finally:
        _close_all()

    return None, False


def parse_ip_range_input(start_raw, end_raw=""):
    """
    Chuẩn hóa dải IP người dùng nhập vào (hỗ trợ cả dạng đầy đủ lẫn viết tắt):
    - '192.168.10.1' .. '192.168.10.254'
    - '192.168.10.xxx', '192.168.10.*', '192.168.10.', '192.168.10' -> ('192.168.10.1', '192.168.10.254')
    - '192.168.10.0/24' -> ('192.168.10.1', '192.168.10.254')
    """
    s = str(start_raw or "").strip()
    e = str(end_raw or "").strip()
    if not s:
        return None, None

    # Cho phép nhập "192.168.10.1 - 192.168.10.254" ngay trong ô đầu
    if "-" in s and not e:
        parts_dash = [p.strip() for p in s.split("-", 1)]
        if len(parts_dash) == 2:
            s, e = parts_dash[0], parts_dash[1]

    # Hỗ trợ CIDR (ví dụ: 192.168.10.0/24)
    if "/" in s:
        try:
            net = ipaddress.IPv4Network(s, strict=False)
            hosts = list(net.hosts())
            if hosts:
                return str(hosts[0]), str(hosts[-1])
            return str(net.network_address), str(net.broadcast_address)
        except Exception:
            return None, None

    # Hỗ trợ dạng viết tắt: 192.168.10.xxx, 192.168.10.*, 192.168.10., 192.168.10
    m_wild = re.match(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?:\.(?:[xX*]+|\d{0}))?$', s)
    if m_wild:
        o1, o2, o3 = int(m_wild.group(1)), int(m_wild.group(2)), int(m_wild.group(3))
        if all(0 <= x <= 255 for x in (o1, o2, o3)):
            prefix = f"{o1}.{o2}.{o3}"
            e_match = re.match(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$', e)
            if e_match and (int(e_match.group(1)), int(e_match.group(2)), int(e_match.group(3))) == (o1, o2, o3):
                e_last = int(e_match.group(4))
                if 0 <= e_last <= 255:
                    return f"{prefix}.1", f"{prefix}.{e_last}"
            return f"{prefix}.1", f"{prefix}.254"

    # Kiểm tra start_ip dạng A.B.C.D
    try:
        s_octs = [int(x) for x in s.split('.')]
        if len(s_octs) != 4 or not all(0 <= x <= 255 for x in s_octs):
            return None, None
    except Exception:
        return None, None

    prefix_s = f"{s_octs[0]}.{s_octs[1]}.{s_octs[2]}"

    # Nếu end_ip trống -> nếu start_ip kết thúc bằng .0 hoặc .1 thì quét cả dải .1->.254, ngược lại quét đúng IP đó
    if not e:
        if s_octs[3] in (0, 1):
            return f"{prefix_s}.1", f"{prefix_s}.254"
        return s, s

    # Nếu end_ip là dạng wildcard (192.168.10.xxx / *) hoặc chỉ số cuối (ví dụ "254")
    if e.isdigit() and 0 <= int(e) <= 255:
        e = f"{prefix_s}.{int(e)}"
    else:
        m_ewild = re.match(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(?:[xX*]+)?$', e)
        if m_ewild:
            e = f"{int(m_ewild.group(1))}.{int(m_ewild.group(2))}.{int(m_ewild.group(3))}.254"

    try:
        e_octs = [int(x) for x in e.split('.')]
        if len(e_octs) != 4 or not all(0 <= x <= 255 for x in e_octs):
            return s, f"{prefix_s}.254"
    except Exception:
        return s, f"{prefix_s}.254"

    # Nếu người dùng đổi Từ IP sang dải mạng mới (VD: 192.168.10.1) nhưng quên sửa Đến IP cũ (VD: 192.168.0.254)
    s_int = (s_octs[0] << 24) + (s_octs[1] << 16) + (s_octs[2] << 8) + s_octs[3]
    e_int = (e_octs[0] << 24) + (e_octs[1] << 16) + (e_octs[2] << 8) + e_octs[3]
    if (e_int < s_int or (e_int - s_int) > 1024) and s_octs[:3] != e_octs[:3]:
        e = f"{prefix_s}.{e_octs[3] if e_octs[3] >= s_octs[3] else 254}"

    if s_octs[3] == 0:
        s = f"{prefix_s}.1"
    return s, e


def normalize_network_label(label, ip="", forced_tunnel=False):
    """Chuẩn hóa nhãn mạng thành 'LAN' hoặc 'VPN' (không phân biệt loại giao thức VPN cụ thể)."""
    if forced_tunnel:
        return "VPN"
    lbl = str(label or "").strip()
    if not lbl:
        return "LAN" if (ip and is_in_physical_lan_subnet(ip)) else "VPN"
    low = lbl.lower()
    if low == "lan":
        return "LAN"
    return "VPN"


def probe_single_host(ip, port=BOUND_PORT, vpn_type_label="VPN", timeout=1.05, recv_timeout=2.5, known_peer=None):
    """
    Thăm dò một địa chỉ IP xem có đang chạy EasyRemoteDesktop không:
    - Gửi gói tin probe với APP_KEY (không phân biệt loại kết nối VPN IKEv2 / PPTP / L2TP...).
    - Hỗ trợ cả bản mới (trả về probe_pong kèm computer_name, hwid)
      lẫn bản cũ (trả về error 'Sai mật khẩu kết nối!' hoặc 'Sai mat khau').
    - Nếu truyền known_peer (khi kiểm tra trạng thái Online của máy đã biết), giữ lại
      thông tin tên máy đã xác thực, HWID, MAC và mật khẩu đã lưu để không gọi nbtstat chậm
      và không bao giờ ghi đè mất dữ liệu cũ.
    """
    if not ip or ip.startswith('127.'):
        return None
    try:
        if ip in get_all_local_ipv4():
            return None
    except Exception:
        pass

    s, used_tunnel = connect_tcp_any_route(ip, port, timeout=timeout)
    if not s:
        return None

    net_label = normalize_network_label(vpn_type_label, ip=ip, forced_tunnel=used_tunnel)
    try:
        s.settimeout(recv_timeout)
        probe_packet = json.dumps({"action": "probe", "sig": LAN_APP_SIGNATURE}).encode('utf-8')
        send_msg(s, probe_packet, APP_KEY)
        resp = recv_msg(s, [APP_KEY])
        if resp:
            try:
                data = json.loads(resp.decode('utf-8'))
            except Exception:
                data = {}

            def _known_matches_peer(resp_hwid_clean="", resp_name="", resp_name_ver=False):
                if not known_peer:
                    return False
                kh_c = ''.join(ch for ch in str(known_peer.get("hwid") or "") if ch.isdigit())
                if len(resp_hwid_clean) == 12 and known_peer.get("hwid_verified") and len(kh_c) == 12 and resp_hwid_clean != kh_c:
                    return False
                kn_c = str(known_peer.get("computer_name") or "").strip().lower().split('.')[0].strip()
                rn_c = str(resp_name or "").strip().lower().split('.')[0].strip()
                if (
                    resp_name_ver and rn_c and rn_c not in ("unknown", "không rõ") and not re.match(r"^unknown-\d+$", rn_c)
                    and _is_real_verified_name(known_peer) and kn_c and rn_c != kn_c
                    and not (len(resp_hwid_clean) == 12 and known_peer.get("hwid_verified") and resp_hwid_clean == kh_c)
                ):
                    return False
                return True

            known_name = str(known_peer.get("computer_name") or "").strip() if known_peer else ""
            known_verified = bool(known_peer.get("name_verified")) if known_peer else False
            known_has_real_name = bool(known_name and known_name.lower() not in ("unknown", "không rõ") and not re.match(r"^unknown-\d+$", known_name.lower()))
            known_mac = str(known_peer.get("macs") or "").strip() if known_peer else ""
            known_os = str(known_peer.get("os") or "").strip() if known_peer else ""
            known_hwid = str(known_peer.get("hwid") or "").strip() if known_peer else ""
            known_saved_pw = str(known_peer.get("saved_password") or "").strip() if known_peer else ""
            known_saved_id = str(known_peer.get("saved_id") or "").strip() if known_peer else ""

            # Bản mới phản hồi probe_pong
            if data.get("type") == "probe_pong":
                pong_hwid_raw = str(data.get("hwid") or "").strip()
                clean_pong_hwid = ''.join(ch for ch in pong_hwid_raw if ch.isdigit())
                comp_name = data.get("computer_name")
                is_verified = bool(comp_name)

                # Nếu IP này nay đã được DHCP/VPN cấp cho một máy tính KHÁC với known_peer -> hủy liên kết known_peer ngay để không ghi đè/xóa máy cũ!
                if known_peer and not _known_matches_peer(clean_pong_hwid, comp_name, is_verified):
                    known_peer = None
                    known_name = known_mac = known_os = known_hwid = known_saved_pw = known_saved_id = ""
                    known_verified = known_has_real_name = False

                nb_mac = data.get("macs", "") or known_mac
                os_name = data.get("os", "") or known_os
                if not comp_name:
                    if known_has_real_name:
                        comp_name = known_name
                        is_verified = known_verified or True
                    else:
                        r_name, r_mac, r_os, r_ver = resolve_host_info_safe(ip)
                        comp_name = r_name
                        is_verified = r_ver
                        if not nb_mac:
                            nb_mac = r_mac
                        if not os_name:
                            os_name = r_os
                # Host cũ / broker chưa nạp xong MAC trả về macs rỗng -> thử bảng ARP (cùng LAN) để nút WOL hoạt động
                if not nb_mac:
                    nb_mac = get_mac_from_arp(ip)

                if len(clean_pong_hwid) == 12:
                    hwid = clean_pong_hwid
                    matched_comp = match_saved_computer(comp_name, hwid, None)
                    saved_pw = matched_comp.get("password", "") if matched_comp else ""
                    saved_id = hwid
                    hwid_verified = True
                else:
                    matched_comp = match_saved_computer(comp_name, known_hwid, known_saved_id)
                    m_clean_id = ''.join(ch for ch in str(matched_comp.get("id", "")) if ch.isdigit()) if matched_comp else ""
                    clean_kh = ''.join(ch for ch in str(known_hwid or "") if ch.isdigit())
                    exact_match = _is_exact_saved_match(matched_comp, comp_name, known_hwid)
                    if exact_match and m_clean_id and len(m_clean_id) == 12:
                        hwid = m_clean_id
                        saved_id = m_clean_id
                        hwid_verified = True
                    elif clean_kh and len(clean_kh) == 12:
                        hwid = clean_kh
                        saved_id = known_saved_id or hwid
                        hwid_verified = bool(known_peer and known_peer.get("hwid_verified"))
                    else:
                        hwid = make_stable_hwid(ip, comp_name, nb_mac)
                        saved_id = known_saved_id or hwid
                        hwid_verified = False
                    saved_pw = matched_comp.get("password", "") if matched_comp else ""

                full_local_ip = data.get("local_ip") or ip
                # Đảm bảo IP đang thăm dò nằm trong danh sách local_ip
                if ip not in [x.strip() for x in full_local_ip.split(',')]:
                    full_local_ip = f"{full_local_ip},{ip}"

                final_pw_hash = hash_password_md5(saved_pw) if saved_pw else known_saved_pw

                res_dict = {
                    "computer_name": comp_name,
                    "name_verified": is_verified,
                    "os": os_name,
                    "local_ip": full_local_ip,
                    "port": int(data.get("port", port)),
                    "hwid": hwid,
                    "macs": nb_mac,
                    "network_type": net_label,
                    "last_seen": format_last_seen_str(),
                    "source_ip": ip,
                    "saved_password": final_pw_hash,
                    "saved_id": saved_id,
                    "hwid_verified": hwid_verified
                }
                if known_peer:
                    res_dict = merge_peers(res_dict, known_peer)
                return res_dict

            # Bản cũ hoặc phản hồi mật khẩu sai (xác nhận 100% đang chạy app)
            if data.get("status") == "error":
                r_name, r_mac, r_os, r_ver = resolve_host_info_safe(ip)
                if known_peer and r_ver and not _known_matches_peer("", r_name, r_ver):
                    known_peer = None
                    known_name = known_mac = known_os = known_hwid = known_saved_pw = known_saved_id = ""
                    known_verified = known_has_real_name = False

                if r_ver and r_name and not re.match(r"^unknown-\d+$", r_name.lower()):
                    comp_name = r_name
                    nb_mac = r_mac or known_mac
                    os_name = r_os or known_os
                    is_verified = True
                elif known_has_real_name:
                    comp_name = known_name
                    nb_mac = known_mac or r_mac
                    os_name = known_os or r_os
                    is_verified = known_verified or True
                else:
                    comp_name, nb_mac, os_name, is_verified = r_name, (r_mac or known_mac), (r_os or known_os), r_ver
                if not nb_mac:
                    nb_mac = get_mac_from_arp(ip)

                # Thử đối chiếu với saved_computers để lấy ID và mật khẩu chuẩn nếu có (chỉ lấy ID khi khớp chính xác)
                matched_comp = match_saved_computer(comp_name, known_hwid, known_saved_id)
                saved_pw = matched_comp.get("password", "") if matched_comp else ""
                m_clean_id = ''.join(ch for ch in str(matched_comp.get("id", "")) if ch.isdigit()) if matched_comp else ""
                clean_kh = ''.join(ch for ch in str(known_hwid or "") if ch.isdigit())
                exact_match = _is_exact_saved_match(matched_comp, comp_name, known_hwid)

                if exact_match and m_clean_id and len(m_clean_id) == 12:
                    hwid = m_clean_id
                    saved_id = m_clean_id
                    hwid_verified = True
                elif clean_kh and len(clean_kh) == 12:
                    hwid = clean_kh
                    saved_id = known_saved_id or hwid
                    hwid_verified = bool(known_peer and known_peer.get("hwid_verified"))
                else:
                    hwid = make_stable_hwid(ip, comp_name, nb_mac)
                    saved_id = known_saved_id or hwid
                    hwid_verified = False

                final_pw_hash = hash_password_md5(saved_pw) if saved_pw else known_saved_pw

                res_dict = {
                    "computer_name": comp_name,
                    "name_verified": is_verified,
                    "hwid_verified": hwid_verified,
                    "os": os_name,
                    "local_ip": ip,
                    "port": port,
                    "hwid": hwid,
                    "macs": nb_mac,
                    "network_type": net_label,
                    "last_seen": format_last_seen_str(),
                    "source_ip": ip,
                    "saved_password": final_pw_hash,
                    "saved_id": saved_id
                }
                if known_peer:
                    res_dict = merge_peers(res_dict, known_peer)
                return res_dict
    except Exception:
        pass
    finally:
        try:
            s.close()
        except Exception:
            pass
    return None


def probe_peer_direct(peer_info, timeout=0.85):
    """
    Thăm dò trực tiếp trạng thái Online của một máy tính trong mạng LAN / VPN qua TCP:
    - Thử kết nối tới source_ip và các IP trong local_ip trên cổng port (mặc định BOUND_PORT).
    - Kiểm tra danh tính máy phản hồi khớp với peer_info (nếu IP cũ đã bị DHCP cấp cho máy khác thì bỏ qua IP đó,
      trả về Offline chứ TUYỆT ĐỐI không ghi đè hay làm mất peer_info).
    
    Trả về: (is_online: bool, updated_info: dict hoặc None)
    """
    candidate_ips = []
    # 1. Thử source_ip trước vì đây là IP thực tế mà máy này đã gửi tin tới ta gần nhất
    src_ip = str(peer_info.get("source_ip") or "").strip()
    if src_ip and not src_ip.startswith("127."):
        candidate_ips.append(src_ip)

    # 2. Thử các IP trong local_ip
    for raw in [peer_info.get("local_ip", "")]:
        for part in str(raw).split(","):
            ip = part.strip()
            if ip and ip not in candidate_ips and not ip.startswith("127."):
                candidate_ips.append(ip)

    if not candidate_ips:
        return False, None

    port = int(peer_info.get("port") or BOUND_PORT)
    raw_net = str(peer_info.get("network_type") or "").strip()
    vpn_label = "LAN" if (not raw_net or raw_net.upper() == "LAN") else "VPN"
    peer_hwid = peer_info.get("hwid") or peer_info.get("saved_id") or ""

    for ip in candidate_ips:
        res = probe_single_host(ip, port=port, vpn_type_label=vpn_label, timeout=timeout, recv_timeout=max(timeout, 1.5), known_peer=peer_info)
        if res and are_same_machine(peer_hwid, peer_info, res.get("hwid"), res):
            return True, res

    if port != 12345:
        for ip in candidate_ips:
            res = probe_single_host(ip, port=12345, vpn_type_label=vpn_label, timeout=timeout, recv_timeout=max(timeout, 1.5), known_peer=peer_info)
            if res and are_same_machine(peer_hwid, peer_info, res.get("hwid"), res):
                return True, res

    return False, None


def scan_vpn_network(vpn_info, ports=None, max_workers=75, progress_callback=None, cancel_event=None, peer_found_callback=None, known_peers=None):
    """
    Quét toàn bộ dải IP của một mạng VPN (ủy quyền sang scan_custom_range theo dải IP, không phân biệt loại VPN).
    """
    base_prefix = vpn_info.get("base_prefix", "")
    start = vpn_info.get("start", 1)
    end = vpn_info.get("end", 254)
    if not base_prefix:
        return []
    return scan_custom_range(
        f"{base_prefix}{start}",
        f"{base_prefix}{end}",
        ports=ports,
        max_workers=max_workers,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
        peer_found_callback=peer_found_callback,
        known_peers=known_peers,
    )


def scan_custom_range(start_ip, end_ip, ports=None, max_workers=75, progress_callback=None, cancel_event=None, peer_found_callback=None, known_peers=None):
    """
    Quét trực tiếp theo dải IP người dùng nhập vào (ví dụ 192.168.10.1 -> 192.168.10.254),
    hoàn toàn độc lập và không phân biệt loại kết nối VPN hiện tại (IKEv2, PPTP, L2TP, SSTP, OpenVPN...).
    """
    if ports is None:
        ports = DEFAULT_SCAN_PORTS
    elif isinstance(ports, int):
        ports = [ports]

    norm_start, norm_end = parse_ip_range_input(start_ip, end_ip)
    if not norm_start or not norm_end:
        return []

    try:
        s_octets = [int(x) for x in norm_start.split('.')]
        e_octets = [int(x) for x in norm_end.split('.')]
        if len(s_octets) != 4 or len(e_octets) != 4:
            return []
    except Exception:
        return []

    s_int = (s_octets[0] << 24) + (s_octets[1] << 16) + (s_octets[2] << 8) + s_octets[3]
    e_int = (e_octets[0] << 24) + (e_octets[1] << 16) + (e_octets[2] << 8) + e_octets[3]

    if s_int > e_int:
        s_int, e_int = e_int, s_int

    # Giới hạn tối đa 1024 IPs để quét nhanh và tránh treo
    if (e_int - s_int) > 1024:
        e_int = s_int + 1024

    my_ips = get_all_local_ipv4()
    ips_to_scan = []
    for cur in range(s_int, e_int + 1):
        ip_str = f"{(cur >> 24) & 255}.{(cur >> 16) & 255}.{(cur >> 8) & 255}.{cur & 255}"
        if ip_str not in my_ips:
            ips_to_scan.append(ip_str)

    total = len(ips_to_scan)
    current = 0
    found_peers = []
    _lock = threading.Lock()

    def _worker(target_ip):
        nonlocal current
        if cancel_event and cancel_event.is_set():
            return None
        res = None
        kp = None
        if known_peers and isinstance(known_peers, dict):
            for p_info in known_peers.values():
                p_ips = [x.strip() for x in (str(p_info.get("local_ip", "")) + "," + str(p_info.get("source_ip", ""))).split(",") if x.strip()]
                if target_ip in p_ips:
                    kp = p_info
                    break

        vpn_lbl = "LAN" if is_in_physical_lan_subnet(target_ip) else "VPN"
        for port in ports:
            if cancel_event and cancel_event.is_set():
                break
            res = probe_single_host(target_ip, port=port, vpn_type_label=vpn_lbl, timeout=1.05, recv_timeout=2.5, known_peer=kp)
            if res:
                break

        if res:
            my_clean = ""
            try:
                from utils.hwid import load_saved_hwid, get_hwid
                my_clean = ''.join(ch for ch in str(load_saved_hwid() or get_hwid()[0] or "") if ch.isdigit())
            except Exception:
                pass
            res_hwid = ''.join(ch for ch in str(res.get("hwid") or "") if ch.isdigit())
            res_saved_id = ''.join(ch for ch in str(res.get("saved_id") or "") if ch.isdigit())
            res_name = str(res.get("computer_name") or "").strip().lower()
            my_hostname = socket.gethostname().strip().lower()
            if my_clean and (my_clean == res_hwid or my_clean == res_saved_id):
                res = None
            elif (
                not (res.get("hwid_verified") and len(res_hwid) == 12 and len(my_clean) == 12 and res_hwid != my_clean)
                and res_name and res_name == my_hostname and res_name not in ("unknown", "không rõ", "localhost")
            ):
                res = None

        should_notify = False
        with _lock:
            current += 1
            if res:
                res_key = (res.get("hwid"), res.get("source_ip"))
                if not any((p.get("hwid"), p.get("source_ip")) == res_key for p in found_peers):
                    found_peers.append(res)
                    should_notify = True

        if should_notify and peer_found_callback:
            try:
                peer_found_callback(res)
            except Exception:
                pass

        if progress_callback:
            try:
                progress_callback(current, total, target_ip)
            except Exception:
                pass
        return res

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(_worker, ips_to_scan))

    return found_peers
