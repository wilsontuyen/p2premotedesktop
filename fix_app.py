import os
import re

app_path = "d:/Data/AG/remote_desktop/app.py"
with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove pynput imports
content = re.sub(r'from pynput\.mouse import Controller as MouseController\n?', '', content)
content = re.sub(r'from pynput\.keyboard import Controller as KeyboardController, Key\n?', '', content)
content = re.sub(r'mouse = MouseController\(\)\n?', '', content)
content = re.sub(r'keyboard = KeyboardController\(\)\n?', '', content)

# 2. Remove key_map and button_map
# We find "# Key mapping from Pygame key names to pynput Key" and remove until "def _parse_geometry" or similar
# Wait, let's just use regex to remove the dictionaries
content = re.sub(r'# Key mapping from Pygame.*?button_map = \{.*?\n\}\n', '', content, flags=re.DOTALL)

# 3. Replace Color Theme Setup
# Find # Color Theme Setup until self.my_id_clean
theme_setup_pattern = r'# Color Theme Setup.*?(?=self\.my_id_clean, self\.my_id_formatted)'
replacement1 = 'from gui.themes import setup_app_theme\n        setup_app_theme(self)\n        \n        '
content = re.sub(theme_setup_pattern, replacement1, content, flags=re.DOTALL)

# 4. Replace change_theme
change_theme_pattern = r'def change_theme\(self\):.*?(?=\n    def save_window_position)'
replacement2 = 'def change_theme(self):\n        from gui.themes import change_app_theme\n        change_app_theme(self)'
content = re.sub(change_theme_pattern, replacement2, content, flags=re.DOTALL)

# 5. Fix import in app.py if needed (utils.hwid -> gui.themes import get_theme_palette)
if 'from gui.themes import get_theme_palette' not in content:
    content = content.replace('from utils.hwid import', 'from gui.themes import get_theme_palette\nfrom utils.hwid import')

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed app.py safely!")
