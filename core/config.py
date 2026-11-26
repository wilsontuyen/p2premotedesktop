import sys
import os
import hashlib
import configparser

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

is_agent_process = "--clipboard-agent" in sys.argv or (sys.argv and "clipboard_agent" in sys.argv[0])
is_clipboard_agent = is_agent_process
is_gui_agent = "--gui-agent" in sys.argv
is_broker_process = "--broker" in sys.argv
is_capture_worker_process = "--capture-worker" in sys.argv or "--headless" in sys.argv

PORTS_TO_TRY = [12345, 12346, 12347, 12348, 12349]
BOUND_PORT = 12345
LAN_DISCOVERY_PORT = 12399
LAN_BEACON_INTERVAL = 3
LAN_OFFLINE_TIMEOUT = 10
LAN_APP_SIGNATURE = hashlib.sha256(b"EasyRemoteDesktop_LAN_v1").hexdigest()[:16]

# Real-time TCP Signaling Server configuration
SIGNALING_SERVER_HOSTS = ["homed.auavn.com"]
SIGNALING_SERVER_PORT = 8765


def parse_signaling_host_entry(entry, default_port=None):
    """Phân tách tên máy chủ và cổng (hỗ trợ cả 'abc.com' và 'abc.com:8765')."""
    if default_port is None:
        default_port = SIGNALING_SERVER_PORT
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


def reload_signaling_config():
    """Đọc lại danh sách máy chủ và cổng Signaling từ server.ini."""
    global SIGNALING_SERVER_HOSTS, SIGNALING_SERVER_PORT
    hosts = ["homed.auavn.com"]
    port = 8765
    try:
        server_config = configparser.ConfigParser()
        ini_path = os.path.join(app_dir, 'server.ini')
        server_config.read(ini_path, encoding='utf-8')
        if 'server' in server_config:
            hosts_str = server_config['server'].get('host', 'homed.auavn.com')
            parsed = [h.strip() for h in str(hosts_str or '').split(',') if h.strip()]
            if parsed:
                hosts = parsed
            port = server_config['server'].getint('port', 8765)
    except Exception as e:
        print(f"[Config] Error reading server.ini: {e}")
    SIGNALING_SERVER_HOSTS = hosts
    SIGNALING_SERVER_PORT = port
    return SIGNALING_SERVER_HOSTS, SIGNALING_SERVER_PORT


def update_signaling_config(hosts_list, port):
    """Cập nhật cấu hình Signaling Server trong bộ nhớ dùng chung."""
    global SIGNALING_SERVER_HOSTS, SIGNALING_SERVER_PORT
    cleaned = [str(h).strip() for h in (hosts_list or []) if str(h).strip()]
    if cleaned:
        SIGNALING_SERVER_HOSTS = cleaned
    if port is not None:
        SIGNALING_SERVER_PORT = int(port)
    return SIGNALING_SERVER_HOSTS, SIGNALING_SERVER_PORT


reload_signaling_config()

ENABLE_CLIPBOARD_SYNC = True


def is_host_only_mode():
    """Incoming-only Host UI (TeamViewer Host style)."""
    if "--host" in sys.argv or "--host-only" in sys.argv:
        return True
    try:
        from host_build_flag import HOST_ONLY_BUILD
        if HOST_ONLY_BUILD:
            return True
    except Exception:
        pass
    try:
        name = os.path.basename(sys.executable if getattr(sys, "frozen", False) else sys.argv[0]).lower()
        return ("host" in name) and ("service" not in name)
    except Exception:
        return False
