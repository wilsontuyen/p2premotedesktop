import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add ChangeWindowMessageFilterEx for SHNOTIFY
old_uipi = '''                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), 0x0306, MSGFLT_ALLOW, None) # WM_RENDERALLFORMATS
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), 0x0307, MSGFLT_ALLOW, None) # WM_DESTROYCLIPBOARD
                log_debug("[Listener] Đã cấu hình UIPI (ChangeWindowMessageFilterEx) thành công.")'''

new_uipi = '''                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), 0x0306, MSGFLT_ALLOW, None) # WM_RENDERALLFORMATS
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), 0x0307, MSGFLT_ALLOW, None) # WM_DESTROYCLIPBOARD
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), 0x0400 + 102, MSGFLT_ALLOW, None) # WM_USER_SHNOTIFY
                log_debug("[Listener] Đã cấu hình UIPI (ChangeWindowMessageFilterEx) thành công.")'''
content = content.replace(old_uipi, new_uipi)

# Add log_debug to SHNOTIFY
old_shnotify = '''        elif msg == WM_USER_SHNOTIFY:
            try:
                from win32com.shell import shell, shellcon'''

new_shnotify = '''        elif msg == WM_USER_SHNOTIFY:
            log_debug("[WndProc] Nhận WM_USER_SHNOTIFY")
            try:
                from win32com.shell import shell, shellcon'''
content = content.replace(old_shnotify, new_shnotify)

# Also log SHChangeNotifyRegister result
old_sh_reg = '''                    0x0400 + 102, 
                    (pidl, True)
                )
            except Exception as e:
                print(f"[Listener] SHChangeNotifyRegister Error: {e}")'''

new_sh_reg = '''                    0x0400 + 102, 
                    (pidl, True)
                )
                log_debug(f"[Listener] Đã đăng ký SHChangeNotifyRegister: {self.notify_id}")
            except Exception as e:
                log_debug(f"[Listener] SHChangeNotifyRegister Error: {e}")'''
content = content.replace(old_sh_reg, new_sh_reg)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("UIPI patch applied")
