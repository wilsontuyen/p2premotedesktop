import os

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False

for i, line in enumerate(lines):
    if "from pynput.mouse import Controller as MouseController, Button" in line:
        continue
    if "from pynput.keyboard import Controller as KeyboardController, Key" in line:
        continue
        
    if "button_map = {" in line:
        skip = True
        continue
        
    if skip and "key_map = {" in line:
        # already skipping, but just in case
        continue
        
    if skip and line.strip() == "}":
        # Check if the next few lines are key_map
        if i + 2 < len(lines) and "key_map =" in lines[i+2]:
            continue
        elif i + 1 < len(lines) and "key_map =" in lines[i+1]:
            continue
        else:
            skip = False
            continue
            
    if not skip:
        # Also need to check if we hit key_map without being in skip
        if "key_map = {" in line:
            skip = True
            continue
        new_lines.append(line)

with open(app_py, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Cleaned up pynput and legacy maps from app.py!")
