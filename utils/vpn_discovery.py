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
            res_rt = subprocess.run(['route', 'print', 'IPv4'], capture_output=True, text=True, startupinfo=startupinfo, timeout=3)
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
                
            vpn_type = None
            is_private = (
                ip.startswith('10.') or 
                ip.startswith('192.168.') or 
                ip.startswith('172.') or 
                (ip.startswith('100.') and 64 <= int(ip.split('.')[1]) <= 127) or 
                ip.startswith('25.') or 
                ip.startswith('26.')
            )
            
            # Check 1: Windows Built-in VPN (rasdial, WAN miniport, or interface name keywords)
            if iface_name in connected_ras or any(k in name_lower for k in ("wan miniport", "ikev2", "l2tp", "sstp", "pptp", "vpn", "aua")):
                vpn_type = f"Windows VPN ({iface_name})"
            # Check 2: Tailscale (100.64.0.0/10)
            elif "tailscale" in name_lower:
                vpn_type = "Tailscale"
            elif ip.startswith('100.'):
                octets = [int(x) for x in ip.split('.')]
                if len(octets) == 4 and octets[0] == 100 and (64 <= octets[1] <= 127):
                    vpn_type = "Tailscale"
            # Check 3: Hamachi (25.0.0.0/8)
            elif "hamachi" in name_lower or ip.startswith('25.'):
                vpn_type = "Hamachi"
            # Check 4: Radmin VPN (26.0.0.0/8)
            elif "radmin" in name_lower or ip.startswith('26.'):
                vpn_type = "Radmin VPN"
            # Check 5: ZeroTier
            elif "zerotier" in name_lower or "zt" in name_lower:
                vpn_type = "ZeroTier"
            # Check 6: WireGuard
            elif "wireguard" in name_lower or "wg" in name_lower:
                vpn_type = "WireGuard"
            # Check 7: OpenVPN / TAP / Wintun
            elif any(k in name_lower for k in ("tap", "tun", "openvpn", "wintun")):
                vpn_type = "OpenVPN"
            # Check 8: PPP / Point-to-Point (Không có MAC trên Windows hoặc netmask 255.255.255.255)
            elif is_private and (a.netmask == '255.255.255.255' or (os.name == 'nt' and not has_mac)):
                vpn_type = f"Windows VPN ({iface_name})"

            if vpn_type:
                octs = ip.split('.')
                base_c = f"{octs[0]}.{octs[1]}.{octs[2]}."
                
                # Tránh trùng lặp cùng dải mạng subnet
                if base_c in seen_prefixes:
                    continue
                seen_prefixes.add(base_c)

                # Tìm gateway hoặc subnet tương ứng trong route table
                target_gateway = None
                target_subnet = None
                for r in route_table:
                    if r['iface'] == ip:
                        if r['dest'] != ip and r['dest'] != '255.255.255.255' and r['dest'] != '0.0.0.0' and not r['dest'].startswith('224.'):
                            target_subnet = f"{r['dest']}/{r['netmask']}"
                            if r['gateway'] != 'On-link' and r['gateway'] != '0.0.0.0':
                                target_gateway = r['gateway']
                            break

                vpn_list.append({
                    "name": iface_name,
                    "vpn_type": vpn_type,
                    "ip": ip,
                    "netmask": a.netmask,
                    "gateway": target_gateway,
                    "target_subnet": target_subnet or f"{base_c}0/24",
                    "base_prefix": base_c,
                    "start": 1,
                    "end": 254
                })

    return vpn_list


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
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((ip, 3389))
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
        if dns_name and not dns_name.lower().startswith('pc-') and dns_name.lower() not in ('unknown', 'không rõ'):
            res = (dns_name, nb_mac or "", "", True)
            with _DNS_LOCK:
                _DNS_CACHE[ip] = res
            return res
    except Exception:
        pass

    # 4. Fallback (không xác thực được tên)
    fallback = f"PC-{ip.split('.')[-1]}"
    res = (fallback, nb_mac or "", "", False)
    with _DNS_LOCK:
        _DNS_CACHE[ip] = res
    return res


def resolve_hostname_safe(ip, timeout=0.6):
    """Phân giải tên máy tính an toàn qua Reverse DNS / NetBIOS với bộ nhớ đệm."""
    info = resolve_host_info_safe(ip, timeout=timeout)
    return info[0]


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
    if not cn or re.match(r"^pc-\d+$", cn) or cn in ("unknown", "không rõ"):
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



def are_same_machine(hwid1, p1, hwid2, p2):
    """
    Kiểm tra xem 2 bản ghi có thuộc về cùng 1 máy tính vật lý hay không:
    1. Trùng HWID/ID chính xác (hoặc trùng saved_id).
    2. Trùng địa chỉ MAC vật lý (không phân biệt chữ hoa/thường, dấu gạch nối hay hai chấm).
    3. Trùng tên máy tính đã xác định (không phải tên rỗng, unknown, localhost hay fallback PC-xxx chưa xác thực).
    4. Trùng IP (local_ip hoặc source_ip) kèm tên máy không mâu thuẫn.
    """
    if not p1 or not p2:
        return False

    # 1. Trùng HWID hoặc ID đã lưu (saved_id / signaling host id)
    id_candidates_1 = {''.join(ch for ch in str(x) if ch.isdigit()) for x in (hwid1, p1.get("hwid"), p1.get("saved_id")) if x}
    id_candidates_1.discard('')
    id_candidates_2 = {''.join(ch for ch in str(x) if ch.isdigit()) for x in (hwid2, p2.get("hwid"), p2.get("saved_id")) if x}
    id_candidates_2.discard('')
    if id_candidates_1 and id_candidates_2 and id_candidates_1.intersection(id_candidates_2):
        return True

    # 2. Trùng MAC vật lý
    macs1 = [re.sub(r'[^A-Fa-f0-9]', '', m).upper() for m in str(p1.get("macs", "")).split(",") if m.strip()]
    macs2 = [re.sub(r'[^A-Fa-f0-9]', '', m).upper() for m in str(p2.get("macs", "")).split(",") if m.strip()]
    valid_macs1 = [m for m in macs1 if len(m) >= 12 and not all(c == '0' for c in m) and not all(c.upper() == 'F' for c in m)]
    valid_macs2 = [m for m in macs2 if len(m) >= 12 and not all(c == '0' for c in m) and not all(c.upper() == 'F' for c in m)]
    if valid_macs1 and valid_macs2:
        if any(m in valid_macs2 for m in valid_macs1):
            return True

    # 3. Trùng tên máy tính (không phân biệt hoa/thường, bỏ domain suffix .local/.lan/...)
    n1 = str(p1.get("computer_name") or "").strip().lower()
    n2 = str(p2.get("computer_name") or "").strip().lower()
    n1_clean = n1.split('.')[0].strip()
    n2_clean = n2.split('.')[0].strip()
    if n1_clean and n2_clean and n1_clean == n2_clean:
        if n1_clean not in ("unknown", "không rõ", "localhost") and not re.match(r"^\d+\.\d+\.\d+\.\d+$", n1_clean):
            # Nếu tên dạng PC-xxx (ví dụ PC-48, PC-201) thì cả 2 phải được verified
            if not re.match(r"^pc-\d+$", n1_clean) or (p1.get("name_verified") and p2.get("name_verified")):
                return True

    # 4. Trùng IP và tên máy không mâu thuẫn (hỗ trợ trường hợp máy đổi IP hoặc 2 card mạng, hoặc tên fallback chưa xác thực)
    ips1 = [x.strip() for x in (str(p1.get("local_ip", "")) + "," + str(p1.get("source_ip", ""))).split(",") if x.strip() and not x.strip().startswith("127.")]
    ips2 = [x.strip() for x in (str(p2.get("local_ip", "")) + "," + str(p2.get("source_ip", ""))).split(",") if x.strip() and not x.strip().startswith("127.")]
    common_ips = set(ips1).intersection(set(ips2))
    if common_ips:
        is_fallback_1 = (not p1.get("name_verified")) or re.match(r"^pc-\d+$", n1_clean) or n1_clean in ("unknown", "không rõ")
        is_fallback_2 = (not p2.get("name_verified")) or re.match(r"^pc-\d+$", n2_clean) or n2_clean in ("unknown", "không rõ")
        if is_fallback_1 or is_fallback_2 or n1_clean == n2_clean:
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
    elif (not w_name or w_name.lower() in ("unknown", "không rõ") or re.match(r"^pc-\d+$", w_name.lower())) and l_name and not re.match(r"^pc-\d+$", l_name.lower()):
        res["computer_name"] = l_name
        res["name_verified"] = p_loser.get("name_verified", False)
        if p_loser.get("saved_id") and not res.get("saved_id"):
            res["saved_id"] = p_loser["saved_id"]

    # 4. OS
    if not res.get("os") and p_loser.get("os"):
        res["os"] = p_loser["os"]

    # 5. Saved Password & Saved ID
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

    # 6. Network type (ưu tiên nhãn chi tiết hơn LAN mặc định)
    w_net = str(res.get("network_type") or "").strip()
    l_net = str(p_loser.get("network_type") or "").strip()
    if (not w_net or w_net.upper() == "LAN") and l_net and l_net.upper() != "LAN":
        res["network_type"] = l_net

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
        if cn and cn not in ("UNKNOWN", "KHÔNG RÕ", "LOCALHOST") and not re.match(r"^\d+\.\d+\.\d+\.\d+$", cn) and not re.match(r"^PC-\d+$", cn):
            seed = f"PEER_NAME_{cn}".encode('utf-8')
        else:
            seed = f"VPN_STABLE_{ip}_{comp_name}".encode('utf-8')
    val = int(hashlib.sha256(seed).hexdigest()[:12], 16)
    twelve = (val % 900000000000) + 100000000000
    return str(twelve)


def probe_single_host(ip, port=BOUND_PORT, vpn_type_label="VPN", timeout=0.45, recv_timeout=0.6, known_peer=None):
    """
    Thăm dò một địa chỉ IP xem có đang chạy EasyRemoteDesktop không:
    - Gửi gói tin probe với APP_KEY.
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

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        s.settimeout(recv_timeout)
        probe_packet = json.dumps({"action": "probe", "sig": LAN_APP_SIGNATURE}).encode('utf-8')
        send_msg(s, probe_packet, APP_KEY)
        resp = recv_msg(s, [APP_KEY])
        if resp:
            try:
                data = json.loads(resp.decode('utf-8'))
            except Exception:
                data = {}

            known_name = str(known_peer.get("computer_name") or "").strip() if known_peer else ""
            known_verified = bool(known_peer.get("name_verified")) if known_peer else False
            known_has_real_name = bool(known_name and known_name.lower() not in ("unknown", "không rõ") and not re.match(r"^pc-\d+$", known_name.lower()))
            known_mac = str(known_peer.get("macs") or "").strip() if known_peer else ""
            known_os = str(known_peer.get("os") or "").strip() if known_peer else ""
            known_hwid = str(known_peer.get("hwid") or "").strip() if known_peer else ""
            known_saved_pw = str(known_peer.get("saved_password") or "").strip() if known_peer else ""
            known_saved_id = str(known_peer.get("saved_id") or "").strip() if known_peer else ""

            # Bản mới phản hồi probe_pong
            if data.get("type") == "probe_pong":
                comp_name = data.get("computer_name")
                is_verified = bool(comp_name)
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

                pong_hwid_raw = str(data.get("hwid") or "").strip()
                clean_pong_hwid = ''.join(ch for ch in pong_hwid_raw if ch.isdigit())
                if len(clean_pong_hwid) == 12:
                    hwid = clean_pong_hwid
                    # HWID đã xác thực từ gói tin probe_pong -> Không dùng known_saved_id lỗi thời
                    matched_comp = match_saved_computer(comp_name, hwid, None)
                    saved_pw = matched_comp.get("password", "") if matched_comp else ""
                    saved_id = (matched_comp.get("id", "") if matched_comp else "") or hwid
                    hwid_verified = True
                else:
                    matched_comp = match_saved_computer(comp_name, known_hwid, known_saved_id)
                    m_clean_id = ''.join(ch for ch in str(matched_comp.get("id", "")) if ch.isdigit()) if matched_comp else ""
                    clean_kh = ''.join(ch for ch in str(known_hwid or "") if ch.isdigit())
                    if m_clean_id and len(m_clean_id) == 12:
                        hwid = m_clean_id
                        saved_id = m_clean_id
                        hwid_verified = True
                    elif clean_kh and len(clean_kh) == 12:
                        hwid = clean_kh
                        saved_id = (matched_comp.get("id", "") if matched_comp else "") or known_saved_id or hwid
                        hwid_verified = True
                    else:
                        hwid = make_stable_hwid(ip, comp_name, nb_mac)
                        saved_id = (matched_comp.get("id", "") if matched_comp else "") or known_saved_id or hwid
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
                    "network_type": vpn_type_label,
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
                if known_has_real_name:
                    comp_name = known_name
                    nb_mac = known_mac
                    os_name = known_os
                    is_verified = known_verified or True
                else:
                    comp_name, nb_mac, os_name, is_verified = resolve_host_info_safe(ip)
                    if not nb_mac:
                        nb_mac = known_mac
                    if not os_name:
                        os_name = known_os

                # Thử đối chiếu với saved_computers để lấy ID và mật khẩu chuẩn nếu có
                matched_comp = match_saved_computer(comp_name, known_hwid, known_saved_id)
                saved_pw = matched_comp.get("password", "") if matched_comp else ""
                m_clean_id = ''.join(ch for ch in str(matched_comp.get("id", "")) if ch.isdigit()) if matched_comp else ""
                clean_kh = ''.join(ch for ch in str(known_hwid or "") if ch.isdigit())

                if m_clean_id and len(m_clean_id) == 12:
                    hwid = m_clean_id
                    saved_id = m_clean_id
                    hwid_verified = True
                elif clean_kh and len(clean_kh) == 12:
                    hwid = clean_kh
                    saved_id = (matched_comp.get("id", "") if matched_comp else "") or known_saved_id or hwid
                    hwid_verified = True
                else:
                    hwid = make_stable_hwid(ip, comp_name, nb_mac)
                    saved_id = (matched_comp.get("id", "") if matched_comp else "") or known_saved_id or hwid
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
                    "network_type": vpn_type_label,
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


def probe_peer_direct(peer_info, timeout=0.35):
    """
    Thăm dò trực tiếp trạng thái Online của một máy tính trong mạng LAN / VPN qua TCP:
    - Thử kết nối tới source_ip và các IP trong local_ip trên cổng port (mặc định BOUND_PORT).
    - Gửi gói tin probe với APP_KEY và kiểm tra phản hồi từ host.
    - Không cần thông qua Signaling Server.
    
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
    vpn_label = peer_info.get("network_type") or "LAN"

    for ip in candidate_ips:
        res = probe_single_host(ip, port=port, vpn_type_label=vpn_label, timeout=timeout, recv_timeout=0.45, known_peer=peer_info)
        if res:
            return True, res

    if port != 12345:
        for ip in candidate_ips:
            res = probe_single_host(ip, port=12345, vpn_type_label=vpn_label, timeout=timeout, recv_timeout=0.45, known_peer=peer_info)
            if res:
                return True, res

    return False, None


def scan_vpn_network(vpn_info, ports=None, max_workers=45, progress_callback=None, cancel_event=None, peer_found_callback=None, known_peers=None):
    """
    Quét toàn bộ dải IP của một mạng VPN.
    vpn_info: dict trả về từ detect_vpn_interfaces().
    ports: danh sách cổng cần quét (mặc định [12345, 12346]).
    peer_found_callback: hàm gọi ngay khi phát hiện 1 máy (để UI cập nhật tức thì).
    known_peers: dict máy đã biết để truyền known_peer vào probe_single_host bảo vệ HWID.
    """
    if ports is None:
        ports = DEFAULT_SCAN_PORTS
    elif isinstance(ports, int):
        ports = [ports]

    base_prefix = vpn_info.get("base_prefix", "")
    start = vpn_info.get("start", 1)
    end = vpn_info.get("end", 254)
    vpn_type = vpn_info.get("vpn_type", "VPN")

    my_ips = get_all_local_ipv4()
    ips_to_scan = []
    for i in range(start, end + 1):
        target_ip = f"{base_prefix}{i}"
        if target_ip not in my_ips:
            ips_to_scan.append(target_ip)

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

        for port in ports:
            if cancel_event and cancel_event.is_set():
                break
            res = probe_single_host(target_ip, port=port, vpn_type_label=vpn_type, timeout=0.45, known_peer=kp)
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
            elif res_name and res_name == my_hostname and res_name not in ("unknown", "không rõ", "localhost"):
                res = None

        should_notify = False
        with _lock:
            current += 1
            if res:
                if not any(p["local_ip"] == res["local_ip"] for p in found_peers):
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


def scan_custom_range(start_ip, end_ip, ports=None, max_workers=45, progress_callback=None, cancel_event=None, peer_found_callback=None, known_peers=None):
    """Quét dải IP tùy chỉnh do người dùng nhập (ví dụ 192.168.1.1 -> 192.168.1.50)."""
    if ports is None:
        ports = DEFAULT_SCAN_PORTS
    elif isinstance(ports, int):
        ports = [ports]

    try:
        s_octets = [int(x) for x in start_ip.strip().split('.')]
        e_octets = [int(x) for x in end_ip.strip().split('.')]
        if len(s_octets) != 4 or len(e_octets) != 4:
            return []
    except Exception:
        return []

    s_int = (s_octets[0] << 24) + (s_octets[1] << 16) + (s_octets[2] << 8) + s_octets[3]
    e_int = (e_octets[0] << 24) + (e_octets[1] << 16) + (e_octets[2] << 8) + e_octets[3]

    if s_int > e_int:
        s_int, e_int = e_int, s_int

    # Giới hạn tối đa 512 IPs để quét nhanh
    if (e_int - s_int) > 512:
        e_int = s_int + 512

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

        for port in ports:
            if cancel_event and cancel_event.is_set():
                break
            res = probe_single_host(target_ip, port=port, vpn_type_label="Custom IP", timeout=0.45, known_peer=kp)
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
            elif res_name and res_name == my_hostname and res_name not in ("unknown", "không rõ", "localhost"):
                res = None

        should_notify = False
        with _lock:
            current += 1
            if res:
                if not any(p["local_ip"] == res["local_ip"] for p in found_peers):
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
