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

PORTS_TO_TRY = [12345, 12346, 12347, 12348, 12349]
BOUND_PORT = 12345
LAN_DISCOVERY_PORT = 12399
LAN_BEACON_INTERVAL = 3
LAN_OFFLINE_TIMEOUT = 10
LAN_APP_SIGNATURE = hashlib.sha256(b"EasyRemoteDesktop_LAN_v1").hexdigest()[:16]

# Real-time TCP Signaling Server configuration
SIGNALING_SERVER_HOSTS = ["homed.auavn.com"]
SIGNALING_SERVER_PORT = 8765

try:
    server_config = configparser.ConfigParser()
    ini_path = os.path.join(app_dir, 'server.ini')
    server_config.read(ini_path, encoding='utf-8')
    if 'server' in server_config:
        hosts_str = server_config['server'].get('host', 'homed.auavn.com')
        if hosts_str:
            SIGNALING_SERVER_HOSTS = [h.strip() for h in hosts_str.split(',') if h.strip()]
        SIGNALING_SERVER_PORT = server_config['server'].getint('port', 8765)
except Exception as e:
    print(f"[Config] Error reading server.ini: {e}")

ENABLE_CLIPBOARD_SYNC = True
