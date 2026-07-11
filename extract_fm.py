import os

viewer_py = "d:/Data/AG/remote_desktop/core/viewer.py"
fm_py = "d:/Data/AG/remote_desktop/gui/file_manager.py"

with open(viewer_py, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if "def open_transfer_window():" in line:
        start_idx = i
        indent = len(line) - len(line.lstrip())
        break

for i in range(start_idx + 1, len(lines)):
    line = lines[i]
    stripped = line.lstrip()
    if stripped and not stripped.startswith('#'):
        cur_indent = len(line) - len(stripped)
        if cur_indent <= indent:
            end_idx = i
            break

func_lines = lines[start_idx:end_idx]

# Clean indentation
cleaned = []
for line in func_lines:
    if len(line.strip()) == 0:
        cleaned.append("\n")
    elif line.startswith(" " * indent):
        cleaned.append(line[indent:])
    else:
        cleaned.append(line.lstrip())
        
code = "".join(cleaned)

# Modify signature
code = code.replace("def open_transfer_window():", "def open_transfer_window(computer_name, is_android, send_event):")

# Add imports for gui/file_manager.py
imports = """import os
import time
import base64
import threading
import pygame
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from gui.components import ProgressDialog

"""

with open(fm_py, "w", encoding="utf-8") as f:
    f.write(imports + code)
    
# Replace in viewer.py
# At end_idx, it has: threading.Thread(target=open_transfer_window, daemon=True).start()
# We'll replace the definition and the call.

new_viewer_lines = lines[:start_idx]
new_viewer_lines.append(" " * indent + "from gui.file_manager import open_transfer_window\n")

# Now skip everything up to end_idx.
# Find the start() call and replace its args.
for i in range(end_idx, len(lines)):
    line = lines[i]
    if "threading.Thread(target=open_transfer_window" in line:
        line = line.replace("target=open_transfer_window", "target=open_transfer_window, args=(computer_name, is_android, send_event)")
    new_viewer_lines.append(line)

with open(viewer_py, "w", encoding="utf-8") as f:
    f.writelines(new_viewer_lines)

print("Extracted File Manager successfully!")
