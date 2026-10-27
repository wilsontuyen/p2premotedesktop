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


def match_saved_computer(comp_name=None, hwid=None):
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

    # 1. Khớp theo HWID/ID chính xác (chính xác từng chữ số)
    clean_hwid = ''.join(ch for ch in str(hwid or '') if ch.isdigit())
    if clean_hwid:
        for c in saved:
            c_clean_id = ''.join(ch for ch in c.get('id', '') if ch.isdigit())
            if c_clean_id and c_clean_id == clean_hwid:
                return c

    if not comp_name:
        return None
    cn = str(comp_name).strip().lower()
    if not cn or re.match(r"^pc-\d+$", cn) or cn in ("unknown", "không rõ"):
        return None

    # 2. Khớp tên chính xác hoàn toàn (case-insensitive)
    for c in saved:
        c_raw = c.get("name", "").strip().lower()
        if c_raw and c_raw == cn:
            return c

    # 3. Khớp theo token tên cốt lõi (loại trừ các hậu tố/tiền tố generic: server, pc, laptop, năm 20xx)
    cn_tokens, cn_str = normalize_name_tokens(cn)
    if cn_tokens:
        # Ưu tiên khớp tập token giống hệt nhau 100%
        for c in saved:
            sn_tokens, sn_str = normalize_name_tokens(c.get("name", ""))
            if sn_tokens and cn_tokens == sn_tokens:
                return c

        # Khớp chuỗi ký tự cốt lõi (ví dụ 'binhdinh' vs 'binh dinh')
        if len(cn_str) >= 4:
            for c in saved:
                sn_tokens, sn_str = normalize_name_tokens(c.get("name", ""))
                if sn_str and cn_str == sn_str:
                    return c

        # 4. Khớp theo token cốt lõi mang ý nghĩa định danh (độ dài >= 4 ký tự, ví dụ 'thuong' trong HATHUONG <-> THUONG DN)
        candidates = []
        for c in saved:
            sn_tokens, sn_str = normalize_name_tokens(c.get("name", ""))
            common = set(cn_tokens).intersection(set(sn_tokens))
            meaningful_common = [t for t in common if len(t) >= 4 and t not in ('dinh', 'quang', 'ninh', 'nam')]
            if meaningful_common:
                candidates.append((c, meaningful_common))

        if candidates:
            # Nếu có nhiều ứng viên (ví dụ THUONG DN và THUONG LAPTOP):
            # Ưu tiên khớp đúng chủng loại thiết bị (laptop vs desktop)
            is_laptop = 'laptop' in cn
            matched_c = None
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


def make_stable_hwid(ip, comp_name=""):
    """Tạo HWID 12 chữ số cố định cho máy từ xa nếu máy đó là bản cũ chưa gửi HWID."""
    seed = f"VPN_STABLE_{ip}_{comp_name}".encode('utf-8')
    val = int(hashlib.sha256(seed).hexdigest()[:12], 16)
    twelve = (val % 900000000000) + 100000000000
    return str(twelve)


def probe_single_host(ip, port=BOUND_PORT, vpn_type_label="VPN", timeout=0.45):
    """
    Thăm dò một địa chỉ IP xem có đang chạy EasyRemoteDesktop không:
    - Gửi gói tin probe với APP_KEY.
    - Hỗ trợ cả bản mới (trả về probe_pong kèm computer_name, hwid)
      lẫn bản cũ (trả về error 'Sai mật khẩu kết nối!' hoặc 'Sai mat khau').
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        s.settimeout(0.8)
        probe_packet = json.dumps({"action": "probe", "sig": LAN_APP_SIGNATURE}).encode('utf-8')
        send_msg(s, probe_packet, APP_KEY)
        resp = recv_msg(s, [APP_KEY])
        if resp:
            try:
                data = json.loads(resp.decode('utf-8'))
            except Exception:
                data = {}

            # Bản mới phản hồi probe_pong
            if data.get("type") == "probe_pong":
                comp_name = data.get("computer_name")
                is_verified = bool(comp_name)
                nb_mac = data.get("macs", "")
                os_name = data.get("os", "")
                if not comp_name:
                    r_name, r_mac, r_os, r_ver = resolve_host_info_safe(ip)
                    comp_name = r_name
                    is_verified = r_ver
                    if not nb_mac:
                        nb_mac = r_mac
                    if not os_name:
                        os_name = r_os

                hwid = data.get("hwid") or make_stable_hwid(ip, comp_name)
                full_local_ip = data.get("local_ip") or ip
                # Đảm bảo IP đang thăm dò nằm trong danh sách local_ip
                if ip not in [x.strip() for x in full_local_ip.split(',')]:
                    full_local_ip = f"{full_local_ip},{ip}"

                # Thử đối chiếu với saved_computers để lấy ID và mật khẩu chuẩn nếu có
                matched_comp = match_saved_computer(comp_name, hwid)
                saved_pw = matched_comp.get("password", "") if matched_comp else ""
                saved_id = (matched_comp.get("id", "") if matched_comp else "") or hwid

                return {
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
                    "saved_password": hash_password_md5(saved_pw),
                    "saved_id": saved_id
                }

            # Bản cũ hoặc phản hồi mật khẩu sai (xác nhận 100% đang chạy app)
            if data.get("status") == "error":
                comp_name, nb_mac, os_name, is_verified = resolve_host_info_safe(ip)
                hwid = make_stable_hwid(ip, comp_name)

                # Thử đối chiếu với saved_computers để lấy ID và mật khẩu chuẩn nếu có
                matched_comp = match_saved_computer(comp_name, hwid)
                saved_pw = matched_comp.get("password", "") if matched_comp else ""
                saved_id = (matched_comp.get("id", "") if matched_comp else "") or hwid

                return {
                    "computer_name": comp_name,
                    "name_verified": is_verified,
                    "os": os_name,
                    "local_ip": ip,
                    "port": port,
                    "hwid": hwid,
                    "macs": nb_mac,
                    "network_type": vpn_type_label,
                    "last_seen": format_last_seen_str(),
                    "source_ip": ip,
                    "saved_password": hash_password_md5(saved_pw),
                    "saved_id": saved_id
                }
    except Exception:
        pass
    finally:
        try:
            s.close()
        except Exception:
            pass
    return None


def scan_vpn_network(vpn_info, ports=None, max_workers=45, progress_callback=None, cancel_event=None, peer_found_callback=None):
    """
    Quét toàn bộ dải IP của một mạng VPN.
    vpn_info: dict trả về từ detect_vpn_interfaces().
    ports: danh sách cổng cần quét (mặc định [12345, 12346]).
    peer_found_callback: hàm gọi ngay khi phát hiện 1 máy (để UI cập nhật tức thì).
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
        for port in ports:
            if cancel_event and cancel_event.is_set():
                break
            res = probe_single_host(target_ip, port=port, vpn_type_label=vpn_type, timeout=0.45)
            if res:
                break

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


def scan_custom_range(start_ip, end_ip, ports=None, max_workers=45, progress_callback=None, cancel_event=None, peer_found_callback=None):
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
        for port in ports:
            if cancel_event and cancel_event.is_set():
                break
            res = probe_single_host(target_ip, port=port, vpn_type_label="Custom IP", timeout=0.45)
            if res:
                break

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
