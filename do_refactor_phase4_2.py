import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# Pattern starting from "# Shared client variables" until "def encrypt_text"
pattern = re.compile(
    r"(# Shared client variables.*?)(?=def encrypt_text\()",
    re.DOTALL
)

match = pattern.search(content)
if match:
    viewer_code = match.group(1)
    
    # We need to create core/viewer.py
    os.makedirs("d:/Data/AG/remote_desktop/core", exist_ok=True)
    with open("d:/Data/AG/remote_desktop/core/__init__.py", "w", encoding="utf-8") as f:
        pass
        
    viewer_imports = """import pygame
import threading
import time
import ctypes
from ctypes import wintypes
import sys
import os
import json
import io
import struct
try:
    from PIL import Image
except ImportError:
    pass

from utils.logger import log_debug, log_activity
from network.socket_utils import send_msg, recv_msg
from utils.input_simulator import send_input_keyboard_event, send_input_mouse_click, send_input_mouse_move, send_input_mouse_scroll

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

file_manager_callback = None

"""
    with open("d:/Data/AG/remote_desktop/core/viewer.py", "w", encoding="utf-8") as f:
        f.write(viewer_imports + viewer_code)
        
    # Replace in app.py
    new_content = content[:match.start()] + \
                  "from core.viewer import run_client_viewer_loop, client_latest_frame\n" + \
                  "import core.viewer as viewer_module\n\n" + \
                  content[match.end():]
                  
    with open(app_py, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    print("Extracted Pygame Viewer successfully!")
else:
    print("Could not find the Viewer block!")
