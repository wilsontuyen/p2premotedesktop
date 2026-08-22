import os

file_path = r'os_utils\windows_clipboard.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Fix _mouse_poll_loop (GUI mode)
old_mouse_poll = '''            if user32.GetAsyncKeyState(0x01) & 0x8000:
                if self.manager:
                    self.manager.last_lbutton_time = time.time()
            if user32.GetAsyncKeyState(0x02) & 0x8000:
                if self.manager:
                    self.manager.last_rbutton_time = time.time()
            if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):'''

new_mouse_poll = '''            if user32.GetAsyncKeyState(0x01) & 0x8000:
                if self.manager:
                    self.manager.last_lbutton_time = time.time()
                    if getattr(self.manager, 'dummy_h_active', False):
                        self.manager.dummy_h_active = False
                        self.manager.setup_delayed_rendering()
            if user32.GetAsyncKeyState(0x02) & 0x8000:
                if self.manager:
                    self.manager.last_rbutton_time = time.time()
                    if getattr(self.manager, 'dummy_h_active', False):
                        self.manager.dummy_h_active = False
                        self.manager.setup_delayed_rendering()
            if user32.GetAsyncKeyState(0x0D) & 0x8000: # Enter
                if self.manager and getattr(self.manager, 'dummy_h_active', False):
                    self.manager.dummy_h_active = False
                    self.manager.setup_delayed_rendering()
            if user32.GetAsyncKeyState(0x1B) & 0x8000: # Esc
                if self.manager and getattr(self.manager, 'dummy_h_active', False):
                    self.manager.dummy_h_active = False
                    self.manager.setup_delayed_rendering()
            if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):'''

content = content.replace(old_mouse_poll, new_mouse_poll)

# 2. Fix re_setup (GUI mode)
old_re_setup = '''            dummy_h = create_hdrop_data(["C:\\RemoteDesktop_Paste_Trigger.tmp"])
            if dummy_h:
                fn_SetClipboardData(15, dummy_h)
            
            # Lập lịch setup lại delayed rendering sau 200ms để chờ menu truy vấn xong
            def re_setup():
                time.sleep(0.2)
                self.setup_delayed_rendering()
            threading.Thread(target=re_setup, daemon=True).start()
            return'''

new_re_setup = '''            dummy_h = create_hdrop_data(["C:\\RemoteDesktop_Paste_Trigger.tmp"])
            if dummy_h:
                fn_SetClipboardData(15, dummy_h)
            self.dummy_h_active = True
            return'''
            
content = content.replace(old_re_setup, new_re_setup)

# 3. Fix batch_start double dialog (GUI mode)
old_batch_start = '''            if not (self.app and getattr(self.app, 'is_headless', False)):
                self.show_dialog("Đang tải file về...", display_name, total_size)
            
            self._send_progress_signal("START", f"{display_name}|{total_size}")'''
            
new_batch_start = '''            # Removed show_dialog since _render_format_process already called it.
            self._send_progress_signal("START", f"{display_name}|{total_size}")'''
            
content = content.replace(old_batch_start, new_batch_start)


# 4. Fix _agent_mouse_poll_loop (Headless mode)
old_agent_mouse = '''            try:
                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    _agent_last_lbutton_time = time.time()
                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    _agent_last_rbutton_time = time.time()
                if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):'''
                
new_agent_mouse = '''            try:
                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    _agent_last_lbutton_time = time.time()
                    if _agent_dummy_h_active and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    _agent_last_rbutton_time = time.time()
                    if _agent_dummy_h_active and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if user32.GetAsyncKeyState(0x0D) & 0x8000: # Enter
                    if _agent_dummy_h_active and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if user32.GetAsyncKeyState(0x1B) & 0x8000: # Esc
                    if _agent_dummy_h_active and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):'''
                        
content = content.replace(old_agent_mouse, new_agent_mouse)


# 5. Fix re_setup_agent (Headless mode)
old_agent_re_setup = '''                dummy_h = create_hdrop_data(["C:\\RemoteDesktop_Paste_Trigger.tmp"])
                if dummy_h:
                    ctypes.windll.user32.SetClipboardData(CF_HDROP, dummy_h)
                
                # Lập lịch setup lại delayed rendering sau 200ms để chờ menu truy vấn xong
                def re_setup_agent():
                    import platform
                    time.sleep(2.0 if platform.release() == "7" else 0.2)
                    if _agent_hwnd and _pending_info:
                        ctypes.windll.user32.PostMessageW(
                            ctypes.c_void_p(_agent_hwnd),
                            WM_USER_SETUP_DELAYED, 0, 0
                        )
                threading.Thread(target=re_setup_agent, daemon=True).start()
                return 0'''
                
new_agent_re_setup = '''                dummy_h = create_hdrop_data(["C:\\RemoteDesktop_Paste_Trigger.tmp"])
                if dummy_h:
                    ctypes.windll.user32.SetClipboardData(CF_HDROP, dummy_h)
                _agent_dummy_h_active = True
                return 0'''
                
content = content.replace(old_agent_re_setup, new_agent_re_setup)


# 6. Fix Headless DownPipe START duplicate dialog
old_agent_downpipe = '''                            elif action == "START":
                                try:
                                    display_name, total_size = val.split("|")
                                    gui_queue.put(("start", (display_name, int(total_size))))
                                except: pass'''
                                
new_agent_downpipe = '''                            elif action == "START":
                                pass # gui_queue already gets 'start' from _agent_wndproc WM_RENDERFORMAT'''
                                
content = content.replace(old_agent_downpipe, new_agent_downpipe)


with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Phase 1 done.')
