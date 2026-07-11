import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    app_content = f.read()

# Define the config contents
config_content = """import sys
import hashlib

is_agent_process = "--clipboard-agent" in sys.argv or (sys.argv and "clipboard_agent" in sys.argv[0])
is_clipboard_agent = is_agent_process
is_gui_agent = "--gui-agent" in sys.argv

PORTS_TO_TRY = [12345, 12346, 12347, 12348, 12349]
BOUND_PORT = 12345
LAN_DISCOVERY_PORT = 12399
LAN_BEACON_INTERVAL = 3
LAN_OFFLINE_TIMEOUT = 10
LAN_APP_SIGNATURE = hashlib.sha256(b"EasyRemoteDesktop_LAN_v1").hexdigest()[:16]

SIGNALING_SERVER_HOSTS = [
    "ws://103.20.113.51:8765",
    "wss://vnvps.aegiscloud.net/remote"
]
SIGNALING_SERVER_PORT = 8765

ENABLE_CLIPBOARD_SYNC = True
"""

with open("d:/Data/AG/remote_desktop/core/config.py", "w", encoding="utf-8") as f:
    f.write(config_content)

# Remove the constants from app.py
# 1. PORTS_TO_TRY and BOUND_PORT
app_content = re.sub(r"PORTS_TO_TRY = \[[^\]]+\]\n", "", app_content)
app_content = re.sub(r"BOUND_PORT = \d+\n", "", app_content)
app_content = re.sub(r"LAN_DISCOVERY_PORT = \d+\n", "", app_content)
app_content = re.sub(r"LAN_BEACON_INTERVAL = \d+\n", "", app_content)
app_content = re.sub(r"LAN_OFFLINE_TIMEOUT = \d+\n", "", app_content)
app_content = re.sub(r"LAN_APP_SIGNATURE = [^\n]+\n", "", app_content)
app_content = re.sub(r"SIGNALING_SERVER_HOSTS = \[[^\]]+\]\n", "", app_content)
app_content = re.sub(r"SIGNALING_SERVER_PORT = \d+\n", "", app_content)

# Clean up any leftover blank lines near them
app_content = re.sub(r"\n{3,}", "\n\n", app_content)

with open(app_py, "w", encoding="utf-8") as f:
    f.write(app_content)

print("Constants successfully migrated to core/config.py")
