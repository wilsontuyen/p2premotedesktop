import os

themes_py = "d:/Data/AG/remote_desktop/utils/themes.py"
app_py = "d:/Data/AG/remote_desktop/app.py"

# --- Add new methods to utils/themes.py ---
extra_code = """
def setup_app_theme(app, config_file):
    import os, json
    import tkinter as tk
    
    app.current_theme = tk.StringVar(value="dark")
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                saved_theme = config.get("theme")
                if saved_theme in ["light", "dark", "gray", "pink", "crystal", "orange", "red", "custom"]:
                    app.current_theme.set(saved_theme)
        except Exception:
            pass

    app._last_applied_theme = app.current_theme.get()
    pal = get_theme_palette(app._last_applied_theme)
    app.bg_color = pal["bg_color"]
    app.card_color = pal["card_color"]
    app.text_white = pal["text_white"]
    app.text_gray = pal["text_gray"]
    app.btn_color = pal["btn_color"]
    app.btn_hover = pal["btn_hover"]
    app.entry_bg = pal["entry_bg"]
    app.entry_fg = pal["entry_fg"]
    app.divider_color = pal["divider_color"]
    app.btn_cancel_bg = pal.get("btn_cancel_bg", "#3A3A4A")
    app.btn_cancel_fg = pal.get("btn_cancel_fg", "#FFFFFF")

    app.config(bg=app.bg_color)
    
    if app._last_applied_theme == "crystal":
        try:
            app.attributes("-alpha", 0.88)
        except:
            pass

def change_app_theme(app):
    new_theme = app.current_theme.get()
    if new_theme == getattr(app, '_last_applied_theme', None):
        return
        
    app._last_applied_theme = new_theme
    
    # Save position & theme to config file immediately
    if hasattr(app, 'save_window_position'):
        app.save_window_position()
    
    # We restart the application to apply the theme cleanly without glitches
    import sys, subprocess, os
    
    # Clean existing delay arguments
    args = sys.argv[1:] if getattr(sys, 'frozen', False) else sys.argv
    clean_args = []
    i = 0
    while i < len(args):
        if args[i] == "--delay-startup":
            i += 2
        else:
            clean_args.append(args[i])
            i += 1
            
    # Launch new instance with 2 seconds delay via internal argument
    flags = 0
    if sys.platform == "win32":
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        
    subprocess.Popen([sys.executable] + clean_args + ["--delay-startup", "2.0"], creationflags=flags)
        
    # Close current instance gracefully
    try:
        if hasattr(app, 'signal_socket') and app.signal_socket:
            app.signal_socket.close()
    except:
        pass
        
    try:
        if hasattr(app, 'tray_icon') and app.tray_icon:
            app.tray_icon.visible = False
            app.tray_icon.stop()
    except:
        pass
        
    try:
        app.destroy()
    except:
        pass
        
    os._exit(0)
"""

with open(themes_py, "r", encoding="utf-8") as f:
    content = f.read()

if "def setup_app_theme" not in content:
    with open(themes_py, "a", encoding="utf-8") as f:
        f.write("\n" + extra_code)

# --- Modify app.py ---
with open(app_py, "r", encoding="utf-8") as f:
    app_lines = f.readlines()

new_app = []
skip = False
for i, line in enumerate(app_lines):
    if line.strip() == "# Color Theme Setup":
        skip = True
        new_app.append("        # Color Theme Setup\n")
        new_app.append("        from utils.themes import setup_app_theme\n")
        new_app.append("        setup_app_theme(self, self.config_file)\n")
        continue
    
    if skip:
        # Check if we reached the end of the block
        if "self.my_id_clean, self.my_id_formatted, self.my_macs = get_hwid()" in line:
            skip = False
            new_app.append("        # Host State Variables\n")
            new_app.append("        self.my_id_clean, self.my_id_formatted, self.my_macs = get_hwid()\n")
        continue
    
    # Also replace change_theme method content
    if line.strip() == "def change_theme(self):":
        new_app.append(line)
        new_app.append("        from utils.themes import change_app_theme\n")
        new_app.append("        change_app_theme(self)\n")
        skip = True
        continue
        
    if skip and "def save_window_position(self):" in line:
        skip = False
        new_app.append(line)
        continue
        
    new_app.append(line)

with open(app_py, "w", encoding="utf-8") as f:
    f.writelines(new_app)

print("Theme setup extracted!")
