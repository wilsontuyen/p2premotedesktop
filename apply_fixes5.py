import os

file_path = r'os_utils\windows_clipboard.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Modify _process_clipboard_change_debounced
old_debounce = '''    def _process_clipboard_change_debounced(self):
        if getattr(self, '_is_processing_clipboard', False):
            return
        self._is_processing_clipboard = True
        try:
            self._process_clipboard_change()
        finally:
            self._is_processing_clipboard = False'''

new_debounce = '''    def _process_clipboard_change_debounced(self, provided_files=None):
        if getattr(self, '_is_processing_clipboard', False):
            return
        self._is_processing_clipboard = True
        try:
            self._process_clipboard_change(provided_files)
        finally:
            self._is_processing_clipboard = False'''

content = content.replace(old_debounce, new_debounce)

# 2. Modify _process_clipboard_change
old_process = '''    def _process_clipboard_change(self):
        try:
            time.sleep(0.05) # Chờ xíu để Windows thả file lock (giảm delay)
            owner_hwnd = getattr(self, 'cached_app_hwnd', None)
                
            current_files = get_clipboard_files(owner_hwnd)'''

new_process = '''    def _process_clipboard_change(self, provided_files=None):
        try:
            time.sleep(0.05) # Chờ xíu để Windows thả file lock (giảm delay)
            
            if provided_files is not None:
                current_files = provided_files
            else:
                owner_hwnd = getattr(self, 'cached_app_hwnd', None)
                current_files = get_clipboard_files(owner_hwnd)'''

content = content.replace(old_process, new_process)

# 3. Modify _handle_uppipe_client
old_handle = '''                    if not requested_files:
                        return
                    self.batch_paths = requested_files'''
                    
new_handle = '''                    if not requested_files:
                        return
                    self.batch_paths = requested_files
                elif raw.startswith("COPIED_FILES|"):
                    try:
                        import json
                        paths = json.loads(raw.split("|", 1)[1])
                        if paths:
                            log_debug(f"[_handle_uppipe_client] Nhận COPIED_FILES từ Agent: {len(paths)} file")
                            self._process_clipboard_change_debounced(provided_files=paths)
                    except Exception as e:
                        log_debug(f"[_handle_uppipe_client] Lỗi xử lý COPIED_FILES: {e}")'''

content = content.replace(old_handle, new_handle)

# 4. Modify run_clipboard_agent_mode window creation
old_window = '''        win32gui.UpdateWindow(hwnd)
        
        # Start message loop'''

new_window = '''        win32gui.UpdateWindow(hwnd)
        
        try:
            ctypes.windll.user32.AddClipboardFormatListener(ctypes.c_void_p(hwnd))
        except:
            pass
            
        # Start message loop'''

content = content.replace(old_window, new_window)

# 5. Modify _agent_wndproc
old_wndproc = '''        if msg == WM_RENDERFORMAT and wparam == CF_HDROP:'''

new_wndproc = '''        if msg == 0x031D: # WM_CLIPBOARDUPDATE
            if _ignore_destroy:
                return 0
            def _send_clipboard():
                import time
                time.sleep(0.2) # wait for clipboard to settle
                files = get_clipboard_files()
                if files:
                    try:
                        import win32pipe, win32file, json
                        pipe_name = r"\\\\.\\pipe\\AntigravityP2P_Clipboard_UpPipe"
                        win32pipe.WaitNamedPipe(pipe_name, 5000)
                        pipe_handle = win32file.CreateFile(pipe_name, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
                        msg = "COPIED_FILES|" + json.dumps(files)
                        win32file.WriteFile(pipe_handle, msg.encode('utf-8'))
                        win32file.CloseHandle(pipe_handle)
                        agent_print(f"[ClipboardAgent] Đã gửi {len(files)} COPIED_FILES cho Service.")
                    except Exception as e:
                        agent_print(f"Failed to send COPIED_FILES: {e}")
            threading.Thread(target=_send_clipboard, daemon=True).start()
            return 0

        if msg == WM_RENDERFORMAT and wparam == CF_HDROP:'''

content = content.replace(old_wndproc, new_wndproc)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Phase 3 done.")
