import os
import re

def append_imports(filepath, extra_imports):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Insert right after the last import block at the top
    # We can just insert it after the first few lines
    parts = content.split('\n\n', 1)
    if len(parts) > 1 and "import " in parts[0]:
        new_content = parts[0] + "\n" + extra_imports + "\n\n" + parts[1]
    else:
        new_content = extra_imports + "\n\n" + content
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

# 1. core/network_manager.py
network_imports = """
from core.config import *
from utils.hwid import get_local_ip, get_public_ip, get_public_ipv6
from network.socket_utils import socket_passwords, force_close_socket, APP_KEY
"""
append_imports("d:/Data/AG/remote_desktop/core/network_manager.py", network_imports)

# 2. core/host.py
host_imports = """
from core.config import *
from network.socket_utils import socket_passwords, force_close_socket, APP_KEY
from utils.input_simulator import INPUT, INPUT_KEYBOARD, KEYEVENTF_UNICODE, KEYEVENTF_KEYUP, _remote_modifier_keys
from PIL import Image
"""
append_imports("d:/Data/AG/remote_desktop/core/host.py", host_imports)

# 3. core/viewer.py
viewer_imports = """
from core.config import *
from network.socket_utils import socket_passwords
from PIL import ImageTk
from gui.components import ProgressDialog
from utils.clipboard_api import get_clipboard_text
import socket
from core.clipboard_agent import ClipboardSyncManager
"""
append_imports("d:/Data/AG/remote_desktop/core/viewer.py", viewer_imports)

# 4. core/clipboard_agent.py
agent_imports = """
from core.config import *
from network.socket_utils import socket_passwords
from gui.components import ProgressDialog, ClassicCopyDialog
from utils.logger import log_file_transfer, log_activity
import base64
"""
append_imports("d:/Data/AG/remote_desktop/core/clipboard_agent.py", agent_imports)

# 5. app.py
app_imports = """
from core.clipboard_agent import ClipboardSyncManager
from core.host import encrypt_text, decrypt_text
from core.viewer import run_client_viewer_loop
"""
append_imports("d:/Data/AG/remote_desktop/app.py", app_imports)

print("Imports appended!")
