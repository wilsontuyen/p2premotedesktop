import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace _wndproc in ClipboardEventListener
old_wndproc = '''    def _wndproc(self, hwnd, msg, wparam, lparam):
        WM_CLIPBOARDUPDATE = 0x031D
        WM_RENDERFORMAT = 0x0305
        WM_DESTROYCLIPBOARD = 0x0307
        WM_SETUP_DELAYED_RENDERING = 0x0400 + 101
        
        if msg == WM_CLIPBOARDUPDATE:
            log_debug(f"[WndProc] Nhận WM_CLIPBOARDUPDATE")
            self.callback()
            return 0
        elif msg == WM_RENDERFORMAT:
            log_debug(f"[WndProc] Nhận WM_RENDERFORMAT. wparam={wparam}")
            if wparam == 15: # CF_HDROP
                if self.manager:
                    self.manager.render_format(15)
                return 0
        elif msg == WM_DESTROYCLIPBOARD:
            log_debug(f"[WndProc] Nhận WM_DESTROYCLIPBOARD")
            if self.manager:
                self.manager.lost_ownership()
            return 0
        elif msg == WM_SETUP_DELAYED_RENDERING:
            log_debug(f"[WndProc] Nhận WM_SETUP_DELAYED_RENDERING. Đang tiến hành thiết lập delayed rendering...")
            if self.manager:
                self.manager._execute_setup_delayed_rendering()
            return 0
            
        try:
            return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except:
            return 0'''

new_wndproc = '''    def _wndproc(self, hwnd, msg, wparam, lparam):
        WM_CLIPBOARDUPDATE = 0x031D
        WM_USER_SHNOTIFY = 0x0400 + 102
        
        if msg == WM_CLIPBOARDUPDATE:
            log_debug(f"[WndProc] Nhận WM_CLIPBOARDUPDATE")
            self.callback()
            return 0
        elif msg == WM_USER_SHNOTIFY:
            try:
                from win32com.shell import shell, shellcon
                import threading
                pidl, event, _ = shell.SHChangeNotification_Lock(wparam, lparam)
                if event == shellcon.SHCNE_CREATE:
                    path = shell.SHGetPathFromIDList(pidl[0])
                    if isinstance(path, bytes): path = path.decode('utf-8')
                    if self.manager:
                        threading.Thread(target=self.manager.handle_shnotify_create, args=(path,), daemon=True).start()
                shell.SHChangeNotification_Unlock(wparam)
            except Exception as e:
                pass
            return 0
            
        try:
            return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except:
            return 0'''

content = content.replace(old_wndproc, new_wndproc)

# Inject SHChangeNotifyRegister into _run
old_run_listen = '''            add_res = user32.AddClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            log_debug(f"[Listener] AddClipboardFormatListener trả về: {add_res}")
            
            msg = wintypes.MSG()'''

new_run_listen = '''            add_res = user32.AddClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            log_debug(f"[Listener] AddClipboardFormatListener trả về: {add_res}")
            
            try:
                from win32com.shell import shell, shellcon
                pidl = shell.SHGetSpecialFolderLocation(0, shellcon.CSIDL_DESKTOP)
                self.notify_id = shell.SHChangeNotifyRegister(
                    self.hwnd, 
                    shellcon.SHCNRF_InterruptLevel | shellcon.SHCNRF_ShellLevel, 
                    shellcon.SHCNE_CREATE, 
                    0x0400 + 102, 
                    (pidl, True)
                )
            except Exception as e:
                print(f"[Listener] SHChangeNotifyRegister Error: {e}")
                
            msg = wintypes.MSG()'''

content = content.replace(old_run_listen, new_run_listen)

# Clean up _run destroy
old_destroy = '''            user32.RemoveClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            user32.DestroyWindow(ctypes.c_void_p(self.hwnd))'''

new_destroy = '''            try:
                from win32com.shell import shell
                if hasattr(self, 'notify_id'): shell.SHChangeNotifyDeregister(self.notify_id)
            except: pass
            user32.RemoveClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            user32.DestroyWindow(ctypes.c_void_p(self.hwnd))'''
content = content.replace(old_destroy, new_destroy)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Patch 1 done')
