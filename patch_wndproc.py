import re
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_wndproc = '''        elif msg == WM_USER_SHNOTIFY:'''
new_wndproc = '''        elif msg == 0x0400 + 101: # WM_SETUP_DELAYED_RENDERING
            log_debug("[WndProc] Nhận WM_SETUP_DELAYED_RENDERING")
            if self.manager:
                if hasattr(self.manager, 'setup_virtual_files'):
                    self.manager.setup_virtual_files(self.manager.pending_remote_files)
            return 0
        elif msg == WM_USER_SHNOTIFY:'''
content = content.replace(old_wndproc, new_wndproc)

old_meta = '''            # Nạp file ảo (Virtual Staging) vào Clipboard
            self.is_paste_triggered = False
            self.setup_virtual_files(self.pending_remote_files)'''
new_meta = '''            # Nạp file ảo (Virtual Staging) vào Clipboard
            self.is_paste_triggered = False
            if self.listener and self.listener.hwnd:
                import ctypes
                ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.listener.hwnd), 0x0400 + 101, 0, 0)
            else:
                self.setup_virtual_files(self.pending_remote_files)'''
content = content.replace(old_meta, new_meta)

# In render_format_hybrid, send_msg needs to be imported properly
old_send = '''            try:
                # App uses global send_msg
                import sys
                send_msg = sys.modules['__main__'].send_msg
                send_msg(self.sock, pkt)
            except Exception as e:
                print("Loi send request:", e)'''
new_send = '''            try:
                # App uses global send_msg
                send_msg(self.sock, pkt)
            except Exception as e:
                print("Loi send request:", e)'''
content = content.replace(old_send, new_send)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Restored WM_SETUP_DELAYED_RENDERING')
