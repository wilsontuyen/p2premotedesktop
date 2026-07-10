import os
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """        # Ch?n nh?n clipboard t? Host n?u c?a s? Client Viewer khng du?c kch ho?t
        if ptype in ("clipboard_text", "files_copied_meta"):
            if getattr(self, 'pygame_hwnd', None):
                user32 = ctypes.windll.user32
                user32.GetForegroundWindow.restype = ctypes.c_void_p
                fg_hwnd = user32.GetForegroundWindow()
                if fg_hwnd != self.pygame_hwnd:
                    log_debug(f"[handle_received_packet] B? qua gi tin {ptype} do c?a s? Viewer khng du?c kch ho?t (Gi? clipboard cho my th?t).")
                    return"""

replacement = """        # Chọn nhận clipboard từ Host nếu cửa sổ Client Viewer đang được kích hoạt (hoặc vừa được kích hoạt trong 2 giây)
        if ptype in ("clipboard_text", "files_copied_meta"):
            if getattr(self, 'pygame_hwnd', None):
                user32 = ctypes.windll.user32
                user32.GetForegroundWindow.restype = ctypes.c_void_p
                fg_hwnd = user32.GetForegroundWindow()
                last_active = getattr(self, 'last_viewer_active_time', 0.0)
                import time
                # Nếu viewer mất focus nhưng vừa active trong vòng 2.0s qua, vẫn chấp nhận (giải quyết vụ delay 200-300ms lúc copy)
                if fg_hwnd != self.pygame_hwnd and (time.time() - last_active > 2.0):
                    log_debug(f"[handle_received_packet] Bỏ qua gói tin {ptype} do cửa sổ Viewer không được kích hoạt (Giữ clipboard cho máy thật).")
                    return"""

# Find exact block dynamically
import re
match = re.search(r"(\s*# Ch.n nh.n clipboard t. Host n.u c.a s. Client Viewer kh.ng .*?k.ch ho.t\s*if ptype in \(\"clipboard_text\", \"files_copied_meta\"\):\s*if getattr\(self, 'pygame_hwnd', None\):\s*user32 = ctypes\.windll\.user32\s*user32\.GetForegroundWindow\.restype = ctypes\.c_void_p\s*fg_hwnd = user32\.GetForegroundWindow\(\)\s*if fg_hwnd != self\.pygame_hwnd:\s*log_debug\(f\"\[handle_received_packet\].*?\"\)\s*return)", content, re.DOTALL)

if match:
    content = content[:match.start()] + "\n" + replacement + content[match.end():]
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched handle_received_packet successfully")
else:
    print("Could not find handle_received_packet block")
