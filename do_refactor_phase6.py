import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# Pattern for NetworkMixin
pattern = re.compile(
    r"    def add_firewall_rule_for_app\(self\):.*?(?=    def click_connect\(self\):)",
    re.DOTALL
)

match = pattern.search(content)

if match:
    mixin_code = match.group(0)
    
    # We need to create core/network_manager.py
    os.makedirs("d:/Data/AG/remote_desktop/core", exist_ok=True)
    
    imports = """import os
import sys
import time
import json
import socket
import struct
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
try:
    from PIL import Image, ImageTk
except ImportError:
    pass

from network.socket_utils import send_msg, recv_msg
from utils.logger import log_debug
from network.upnp import attempt_upnp_forward

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class NetworkMixin:
"""
    with open("d:/Data/AG/remote_desktop/core/network_manager.py", "w", encoding="utf-8") as f:
        f.write(imports + mixin_code)
        
    # Replace in app.py
    new_content = content[:match.start()] + content[match.end():]
    
    # Add Mixin to UnifiedApp
    new_content = new_content.replace("class UnifiedApp(tk.Tk, HostMixin):", "from core.network_manager import NetworkMixin\n\nclass UnifiedApp(tk.Tk, HostMixin, NetworkMixin):")
    
    with open(app_py, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    print("Extracted Network logic successfully!")
else:
    print("Could not find the Network logic block!")
