import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"
hwid_py = "d:/Data/AG/remote_desktop/utils/hwid.py"

with open(app_py, "r", encoding="utf-8") as f:
    app_content = f.read()

# 1. Extract get_public_ipv6 and get_public_ip from app.py
pattern_ipv6 = re.compile(r"def get_public_ipv6\(\):.*?return None\n", re.DOTALL)
pattern_ip = re.compile(r"def get_public_ip\(\):.*?return None\n", re.DOTALL)

match_ipv6 = pattern_ipv6.search(app_content)
match_ip = pattern_ip.search(app_content)

ipv6_code = match_ipv6.group(0) if match_ipv6 else ""
ip_code = match_ip.group(0) if match_ip else ""

if match_ipv6: app_content = app_content.replace(match_ipv6.group(0), "")
if match_ip: app_content = app_content.replace(match_ip.group(0), "")

# Append to hwid.py
with open(hwid_py, "a", encoding="utf-8") as f:
    f.write("\nimport urllib.request\nimport urllib.parse\n")
    f.write(ipv6_code + "\n" + ip_code)

# 2. Extract constants from app.py to core/config.py
const_pattern = re.compile(
    r"is_agent_process.*?is_gui_agent = \"--gui-agent\" in sys\.argv\n", re.DOTALL
)
match_const = const_pattern.search(app_content)
const_code1 = match_const.group(0) if match_const else ""
if match_const: app_content = app_content.replace(match_const.group(0), "")

ports_pattern = re.compile(
    r"PORTS_TO_TRY = \[12345, 12346, 12347, 12348, 12349\]\nBOUND_PORT = 12345\nLAN_DISCOVERY_PORT = 12399\nLAN_BEACON_INTERVAL = 3\nLAN_OFFLINE_TIMEOUT = 10\nLAN_APP_SIGNATURE = hashlib\.sha256\(b\"EasyRemoteDesktop_LAN_v1\"\)\.hexdigest\(\)\[:16\]\n"
)
match_ports = ports_pattern.search(app_content)
const_code2 = match_ports.group(0) if match_ports else ""
if match_ports: app_content = app_content.replace(match_ports.group(0), "")

sig_pattern = re.compile(
    r"SIGNALING_SERVER_HOSTS = \[\n    \"ws://103\.20\.113\.51:8765\",\n    \"wss://vnvps\.aegiscloud\.net/remote\"\n\]\nSIGNALING_SERVER_PORT = 8765\n"
)
match_sig = sig_pattern.search(app_content)
const_code3 = match_sig.group(0) if match_sig else ""
if match_sig: app_content = app_content.replace(match_sig.group(0), "")

config_content = f"""import sys
import hashlib

{const_code1}
{const_code2}
{const_code3}
"""
with open("d:/Data/AG/remote_desktop/core/config.py", "w", encoding="utf-8") as f:
    f.write(config_content)

# Add imports to app.py
app_content = app_content.replace(
    "from utils.hwid import get_hwid, get_local_ip",
    "from utils.hwid import get_hwid, get_local_ip, get_public_ip, get_public_ipv6"
)
app_content = "from core.config import *\n" + app_content
with open(app_py, "w", encoding="utf-8") as f:
    f.write(app_content)

print("Constants and hwid methods extracted!")
