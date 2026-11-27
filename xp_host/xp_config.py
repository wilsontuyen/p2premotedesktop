# -*- coding: utf-8 -*-
"""
xp_host/xp_config.py
Quản lý cấu hình, mật khẩu phiên, mật khẩu cố định (XML tương thích bản chính),
cấu hình máy chủ Signaling (server.ini) và ghi nhật ký cho Host XP Lite.
"""

import base64
import configparser
import hashlib
import json
import os
import random
import string
import sys
import time
import xml.etree.ElementTree as ET

PORTS_TO_TRY = [12345, 12346, 12347, 12348, 12349]
BOUND_PORT = 12345
LAN_DISCOVERY_PORT = 12399
LAN_BEACON_INTERVAL = 3
LAN_APP_SIGNATURE = hashlib.sha256(b"EasyRemoteDesktop_LAN_v1").hexdigest()[:16]

DEFAULT_SIGNALING_HOSTS = ["homed.auavn.com"]
DEFAULT_SIGNALING_PORT = 8765


def get_base_dir():
    if getattr(sys, "frozen", False) or hasattr(sys, "__compiled__"):
        return os.path.dirname(os.path.abspath(sys.executable))
    # Đặt cấu hình riêng trong thư mục chứa thực thi (hoặc thư mục xp_host khi chạy code nguồn)
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir(base_dir=None):
    d = os.path.join(base_dir or get_base_dir(), "Data")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def get_logs_dir(base_dir=None):
    d = os.path.join(base_dir or get_base_dir(), "Logs")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def xp_log(msg, log_name="xp_host.log", base_dir=None):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    try:
        print(line)
    except Exception:
        pass
    try:
        lp = os.path.join(get_logs_dir(base_dir), log_name)
        # Tự động xoay vòng log nếu vượt quá 2MB để không làm đầy ổ cứng máy XP cũ
        if os.path.exists(lp) and os.path.getsize(lp) > 2 * 1024 * 1024:
            bak = lp + ".old"
            try:
                if os.path.exists(bak):
                    os.remove(bak)
                os.rename(lp, bak)
            except Exception:
                pass
        with open(lp, "a", encoding="utf-8-sig") as f:
            f.write(line + "\n")
    except Exception:
        pass


def encrypt_xor_text(text, key="AntigravityP2P"):
    if not text:
        return ""
    xored = "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(str(text)))
    return base64.b64encode(xored.encode("utf-8")).decode("utf-8")


def decrypt_xor_text(encrypted_text, key="AntigravityP2P"):
    if not encrypted_text:
        return ""
    try:
        decoded = base64.b64decode(str(encrypted_text).encode("utf-8")).decode("utf-8")
        return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(decoded))
    except Exception:
        return ""


def parse_signaling_host_entry(entry, default_port=DEFAULT_SIGNALING_PORT):
    raw = str(entry or "").strip()
    if not raw:
        return "", int(default_port)
    for prefix in ("tcp://", "ws://", "wss://", "http://", "https://"):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix):]
            break
    raw = raw.split("/", 1)[0].strip()
    if ":" in raw and raw.count(":") == 1:
        h_part, p_part = raw.rsplit(":", 1)
        if p_part.strip().isdigit():
            return h_part.strip(), int(p_part.strip())
    return raw, int(default_port)


def load_signaling_config(base_dir=None):
    bdir = base_dir or get_base_dir()
    hosts = list(DEFAULT_SIGNALING_HOSTS)
    port = DEFAULT_SIGNALING_PORT
    candidates = [
        os.path.join(bdir, "server.ini"),
        os.path.join(os.path.dirname(bdir), "server.ini"),
    ]
    for ini_path in candidates:
        if not os.path.isfile(ini_path):
            continue
        try:
            cfg = configparser.ConfigParser()
            cfg.read(ini_path, encoding="utf-8-sig")
            for sec in cfg.sections():
                if sec.lower() == "server":
                    h_str = cfg[sec].get("host", "")
                    parsed = [h.strip() for h in str(h_str or "").split(",") if h.strip()]
                    if parsed:
                        hosts = parsed
                    port = cfg[sec].getint("port", DEFAULT_SIGNALING_PORT)
                    return hosts, port
        except Exception:
            continue
    return hosts, port


def save_signaling_config(hosts_list, port, base_dir=None):
    bdir = base_dir or get_base_dir()
    ini_path = os.path.join(bdir, "server.ini")
    cleaned = [str(h).strip() for h in (hosts_list or []) if str(h).strip()] or list(DEFAULT_SIGNALING_HOSTS)
    cfg = configparser.ConfigParser()
    cfg["server"] = {
        "host": ", ".join(cleaned),
        "port": str(int(port or DEFAULT_SIGNALING_PORT)),
    }
    with open(ini_path, "w", encoding="utf-8") as f:
        cfg.write(f)
    return cleaned, int(port or DEFAULT_SIGNALING_PORT)


def generate_session_password(mode="4digits"):
    if mode == "5digits":
        return "".join(random.choice(string.digits) for _ in range(5))
    if mode == "8alnum":
        alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
        return "".join(random.choice(alphabet) for _ in range(8))
    return "".join(random.choice(string.digits) for _ in range(4))


def load_or_create_session_password(mode="4digits", base_dir=None):
    p = os.path.join(get_data_dir(base_dir), "session_pass.txt")
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                val = (f.read() or "").strip()
            if val:
                return val
        except Exception:
            pass
    pw = generate_session_password(mode)
    save_session_password(pw, base_dir)
    return pw


def save_session_password(pw, base_dir=None):
    pw = str(pw or "").strip()
    if not pw:
        return False
    try:
        p = os.path.join(get_data_dir(base_dir), "session_pass.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(pw)
        return True
    except Exception:
        return False


def _xml_path(base_dir=None):
    return os.path.join(get_data_dir(base_dir), "saved_computers.xml")


def load_fixed_password(base_dir=None):
    xp = _xml_path(base_dir)
    if not os.path.isfile(xp):
        return ""
    try:
        root = ET.parse(xp).getroot()
        node = root.find("fixed_password")
        if node is not None and node.text:
            return (decrypt_xor_text(node.text) or "").strip()
    except Exception:
        pass
    return ""


def save_fixed_password(password, base_dir=None):
    xp = _xml_path(base_dir)
    password = str(password or "").strip()
    try:
        if os.path.isfile(xp):
            tree = ET.parse(xp)
            root = tree.getroot()
        else:
            root = ET.Element("computers")
            tree = ET.ElementTree(root)
        old = root.find("fixed_password")
        if old is not None:
            root.remove(old)
        if password:
            node = ET.Element("fixed_password")
            node.text = encrypt_xor_text(password)
            root.insert(0, node)
        tree.write(xp, encoding="utf-8", xml_declaration=True)
        return True
    except Exception:
        return False


def load_zalo_phone(base_dir=None):
    xp = _xml_path(base_dir)
    if not os.path.isfile(xp):
        return ""
    try:
        root = ET.parse(xp).getroot()
        node = root.find("zalo_phone")
        if node is not None and node.text:
            return node.text.strip()
    except Exception:
        pass
    return ""


def save_zalo_phone(phone_str, base_dir=None):
    xp = _xml_path(base_dir)
    phone_str = str(phone_str or "").strip()
    try:
        if os.path.isfile(xp):
            tree = ET.parse(xp)
            root = tree.getroot()
        else:
            root = ET.Element("computers")
            tree = ET.ElementTree(root)
        old = root.find("zalo_phone")
        if old is not None:
            root.remove(old)
        if phone_str:
            node = ET.Element("zalo_phone")
            node.text = phone_str
            root.append(node)
        tree.write(xp, encoding="utf-8", xml_declaration=True)
        return True
    except Exception:
        return False


def load_ui_prefs(base_dir=None):
    p = os.path.join(get_data_dir(base_dir), "xp_prefs.json")
    default = {"pass_mode": "4digits", "theme": "classic_xp", "lang": "vi"}
    if not os.path.isfile(p):
        return default
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            default.update(data)
    except Exception:
        pass
    return default


def save_ui_prefs(prefs, base_dir=None):
    p = os.path.join(get_data_dir(base_dir), "xp_prefs.json")
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
