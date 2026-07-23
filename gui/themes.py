def get_theme_palette(theme_name):
    if theme_name == "light":
        return {
            "bg_color": "#F0F2F5",
            "card_color": "#FFFFFF",
            "text_white": "#1C1C21",
            "text_gray": "#606070",
            "btn_color": "#00ADB5",
            "btn_hover": "#008B90",
            "entry_bg": "#EAECEF",
            "entry_fg": "#1C1C22",
            "divider_color": "#D1D5DB",
            "btn_cancel_bg": "#3A3A4A",
            "btn_cancel_fg": "#FFFFFC"
        }
    elif theme_name == "gray":
        return {
            "bg_color": "#525962",
            "card_color": "#636A73",
            "text_white": "#FFFFFF",
            "text_gray": "#C5CBD1",
            "btn_color": "#00ADB5",
            "btn_hover": "#008B90",
            "entry_bg": "#42474E",
            "entry_fg": "#FFFFFE",
            "divider_color": "#7D848C",
            "btn_cancel_bg": "#3A3A4A",
            "btn_cancel_fg": "#FFFFFD"
        }
    elif theme_name == "pink":
        return {
            "bg_color": "#FFF0F5",
            "card_color": "#FFFFFF",
            "text_white": "#3B2F36",
            "text_gray": "#8C7A86",
            "btn_color": "#FF69B4",
            "btn_hover": "#FF1493",
            "entry_bg": "#FFE4E1",
            "entry_fg": "#3B2F37",
            "divider_color": "#FFC0CB",
            "btn_cancel_bg": "#3A3A4A",
            "btn_cancel_fg": "#FF69B4"
        }
    elif theme_name == "crystal":
        return {
            "bg_color": "#E0F7FA",
            "card_color": "#B2EBF2",
            "text_white": "#006064",
            "text_gray": "#00838F",
            "btn_color": "#00BCD4",
            "btn_hover": "#26C6DA",
            "entry_bg": "#E0F7FA",
            "entry_fg": "#006064",
            "divider_color": "#80DEEA",
            "btn_cancel_bg": "#80DEEA",
            "btn_cancel_fg": "#006064"
        }
    elif theme_name == "orange":
        return {
            "bg_color": "#FFF3E0",
            "card_color": "#FFE0B2",
            "text_white": "#4E342E",
            "text_gray": "#5D4037",
            "btn_color": "#FF9800",
            "btn_hover": "#F57C00",
            "entry_bg": "#FFF3E0",
            "entry_fg": "#3E2723",
            "divider_color": "#FFB74D",
            "btn_cancel_bg": "#FFB74D",
            "btn_cancel_fg": "#4E342E"
        }
    elif theme_name == "red":
        return {
            "bg_color": "#FFEBEE",
            "card_color": "#FFCDD2",
            "text_white": "#B71C1C",
            "text_gray": "#D32F2F",
            "btn_color": "#F44336",
            "btn_hover": "#E53935",
            "entry_bg": "#FFEBEE",
            "entry_fg": "#B71C1C",
            "divider_color": "#EF9A9A",
            "btn_cancel_bg": "#EF9A9A",
            "btn_cancel_fg": "#B71C1C"
        }

    elif theme_name == "custom":
        custom_pal = {
            "bg_color": "#1E1E24",
            "card_color": "#2A2A35",
            "text_white": "#FFFFFF",
            "text_gray": "#A0A0B0",
            "btn_color": "#00ADB5",
            "btn_hover": "#008B90",
            "entry_bg": "#15151B",
            "entry_fg": "#FFFFFE",
            "divider_color": "#3A3A4A",
            "btn_cancel_bg": "#3A3A4B",
            "btn_cancel_fg": "#FFFFFD"
        }
        try:
            import configparser, os
            ini_path = "color.ini"
            if not os.path.exists(ini_path):
                config = configparser.ConfigParser()
                config['COLORS'] = custom_pal
                with open(ini_path, 'w', encoding="utf-8") as configfile:
                    config.write(configfile)
            else:
                config = configparser.ConfigParser()
                config.read(ini_path)
                if 'COLORS' in config:
                    for k in custom_pal:
                        if k in config['COLORS']:
                            custom_pal[k] = config['COLORS'][k]
        except:
            pass
        return custom_pal
    else:
        return {
            "bg_color": "#1E1E24",
            "card_color": "#2A2A35",
            "text_white": "#FFFFFF",
            "text_gray": "#A0A0B0",
            "btn_color": "#00ADB5",
            "btn_hover": "#008B90",
            "entry_bg": "#15151B",
            "entry_fg": "#FFFFFE",
            "divider_color": "#3A3A4A",
            "btn_cancel_bg": "#3A3A4B",
            "btn_cancel_fg": "#FFFFFD"
        }


def setup_app_theme(app, config_file):
    import os, json, sys
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
            
    if sys.platform == "darwin":
        app.current_theme.set("light")

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
    popen_kwargs = {}
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        
    subprocess.Popen([sys.executable] + clean_args + ["--delay-startup", "2.0"], **popen_kwargs)
        
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
