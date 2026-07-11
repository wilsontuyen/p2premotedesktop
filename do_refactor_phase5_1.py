import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# Pattern for ClipboardEventListener up to ClipboardSyncManager end (which is before `def encrypt_text`)
pattern1 = re.compile(
    r"# --- NATIVE CLIPBOARD EVENT LISTENER ---.*?(?=def encrypt_text\()",
    re.DOTALL
)

# Pattern for run_clipboard_agent_mode (from def run_clipboard_agent_mode to the end of the file or next major section)
pattern2 = re.compile(
    r"def run_clipboard_agent_mode\(\):.*?root\.mainloop\(\)\n?",
    re.DOTALL
)

match1 = pattern1.search(content)
match2 = pattern2.search(content)

if match1 and match2:
    clipboard_core_code = match1.group(0)
    agent_mode_code = match2.group(0)
    
    # We need to create core/clipboard_agent.py
    os.makedirs("d:/Data/AG/remote_desktop/core", exist_ok=True)
    
    imports = """import os
import sys
import time
import json
import queue
import threading
import ctypes
from ctypes import wintypes
import logging
import win32file
import win32pipe
import win32event
import win32api
import win32gui
import psutil
import tkinter as tk

from utils.logger import log_debug
from network.socket_utils import send_msg, recv_msg
from utils.clipboard_api import (
    ENABLE_CLIPBOARD_SYNC, 
    set_clipboard_dword_format, 
    setup_clipboard_exclusions, 
    get_clipboard_files, 
    set_clipboard_files, 
    get_clipboard_text, 
    set_clipboard_text,
    create_hdrop_data,
    fn_SetClipboardData,
    fn_GlobalFree
)

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

"""
    with open("d:/Data/AG/remote_desktop/core/clipboard_agent.py", "w", encoding="utf-8") as f:
        f.write(imports + "\n" + clipboard_core_code + "\n" + agent_mode_code)
        
    # Replace in app.py
    new_content = content[:match1.start()] + \
                  "from core.clipboard_agent import ClipboardSyncManager, run_clipboard_agent_mode\n\n" + \
                  content[match1.end():match2.start()] + \
                  content[match2.end():]
                  
    with open(app_py, "w", encoding="utf-8") as f:
        f.write(new_content)
        
    print("Extracted Clipboard Agent successfully!")
else:
    print("Could not find the Clipboard Agent blocks!")
    if not match1: print("Missing block 1")
    if not match2: print("Missing block 2")
