import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# Pattern for HostUtils
pattern_utils = re.compile(
    r"def encrypt_text\(.*?(?=class UnifiedApp\(tk\.Tk\):)",
    re.DOTALL
)

# Pattern for HostMixin
pattern_mixin = re.compile(
    r"    def start_host_server\(self\):.*?(?=    def click_connect\(self\):)",
    re.DOTALL
)

match_utils = pattern_utils.search(content)
match_mixin = pattern_mixin.search(content)

if match_utils and match_mixin:
    utils_code = match_utils.group(0)
    mixin_code = match_mixin.group(0)
    
    # We need to create core/host.py
    os.makedirs("d:/Data/AG/remote_desktop/core", exist_ok=True)
    
    imports = """import os
import sys
import time
import json
import queue
import threading
import socket
import ctypes
import struct
import base64
import winreg
import zlib
from ctypes import wintypes
import mss
import tkinter as tk

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from utils.logger import log_debug, log_activity, log_file_transfer
from network.socket_utils import send_msg, recv_msg
from utils.input_simulator import send_input_keyboard_event, send_input_mouse_click, send_input_mouse_move, send_input_mouse_scroll
from core.clipboard_agent import ClipboardSyncManager

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Host Utilities
"""
    mixin_header = "\n\nclass HostMixin:\n"
    
    with open("d:/Data/AG/remote_desktop/core/host.py", "w", encoding="utf-8") as f:
        f.write(imports + utils_code + mixin_header + mixin_code)
        
    # Replace in app.py
    # 1. Replace Utils
    new_content = content[:match_utils.start()] + \
                  "from core.host import HostMixin, check_desktop_change\n" + \
                  content[match_utils.end():]
                  
    # 2. Replace Mixin
    # We have to re-search because indices changed
    match_mixin = pattern_mixin.search(new_content)
    if match_mixin:
        new_content = new_content[:match_mixin.start()] + new_content[match_mixin.end():]
        
    # 3. Add Mixin to UnifiedApp
    new_content = new_content.replace("class UnifiedApp(tk.Tk):", "class UnifiedApp(tk.Tk, HostMixin):")
    
    with open(app_py, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    print("Extracted Host Server logic successfully!")
else:
    print("Could not find the Host logic blocks!")
    if not match_utils: print("Missing Utils block")
    if not match_mixin: print("Missing Mixin block")
