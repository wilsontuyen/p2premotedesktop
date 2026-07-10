import os
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacement = """        # Ch?y event loop c?a Tkinter
        try:
            hidden_root.update()
        except Exception:
            pass
            
        # Ghi nh?n th?i gian ho?t d?ng c?a Viewer
        if clipboard_sync_manager and getattr(clipboard_sync_manager, 'pygame_hwnd', None):
            import ctypes, time
            if ctypes.windll.user32.GetForegroundWindow() == clipboard_sync_manager.pygame_hwnd:
                clipboard_sync_manager.last_viewer_active_time = time.time()
"""

# Find exact block dynamically
import re
match = re.search(r"(\s*# C.p nh.t event loop c.a Tkinter.*?hidden_root\.update\(\)\s*except Exception:\s*pass)", content, re.DOTALL)

if match:
    content = content[:match.start()] + "\n" + replacement + content[match.end():]
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched client_loop successfully")
else:
    print("Could not find client_loop block")
