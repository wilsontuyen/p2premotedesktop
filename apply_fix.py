import sys, os

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add queue and run_clipboard_agent
run_clipboard_agent_code = """
import queue
clipboard_pipe_queue = queue.Queue()

def run_clipboard_agent():
    import sys, time, json
    import win32file, win32pipe, win32api
    
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        try: sys.stdout.reconfigure(encoding='utf-8')
        except: pass

    pipe_name = r'\\\\.\\pipe\\RemoteAppClipboardPipe'
    print(f"[Agent] Waiting for pipe connection: {pipe_name}")
    
    while True:
        try:
            handle = win32file.CreateFile(
                pipe_name, win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None, win32file.OPEN_EXISTING, 0, None
            )
            win32pipe.SetNamedPipeHandleState(handle, win32pipe.PIPE_READMODE_MESSAGE, None, None)
            
            while True:
                try:
                    result, data = win32file.ReadFile(handle, 65536)
                    if data:
                        msg = json.loads(data.decode('utf-8'))
                        if msg.get('type') == 'files':
                            file_paths = msg.get('data', [])
                            hGlobal = create_hdrop_data(file_paths)
                            if hGlobal:
                                opened = False
                                for _ in range(10):
                                    if fn_OpenClipboard(None): opened = True; break
                                    time.sleep(0.05)
                                if opened:
                                    try: fn_EmptyClipboard(); fn_SetClipboardData(CF_HDROP, hGlobal)
                                    finally: fn_CloseClipboard()
                                else: fn_GlobalFree(hGlobal)
                        elif msg.get('type') == 'text':
                            text = msg.get('data', '')
                            if text is not None:
                                text_bytes = (text + '\\x00').encode('utf-16le')
                                total_size = len(text_bytes)
                                hGlobal = fn_GlobalAlloc(GHND, total_size)
                                if hGlobal:
                                    pMem = fn_GlobalLock(hGlobal)
                                    if pMem:
                                        import ctypes
                                        ctypes.memmove(pMem, text_bytes, total_size)
                                        fn_GlobalUnlock(hGlobal)
                                        opened = False
                                        for _ in range(10):
                                            if fn_OpenClipboard(None): opened = True; break
                                            time.sleep(0.05)
                                        if opened:
                                            try: fn_EmptyClipboard(); fn_SetClipboardData(13, hGlobal)
                                            finally: fn_CloseClipboard()
                                        else: fn_GlobalFree(hGlobal)
                except Exception:
                    try: win32api.CloseHandle(handle)
                    except: pass
                    break
        except Exception:
            time.sleep(1)
"""

old_set_files = '''def set_clipboard_files(file_paths, owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return
    try:
        hGlobal = create_hdrop_data(file_paths)
        if not hGlobal: return
        
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        for _ in range(10):
            if fn_OpenClipboard(hwnd_arg):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            try:
                fn_EmptyClipboard()
                fn_SetClipboardData(CF_HDROP, hGlobal)
            finally:
                fn_CloseClipboard()
        else:
            fn_GlobalFree(hGlobal)
            print("[Clipboard] Lỗi: OpenClipboard thất bại khi ghi dữ liệu.")
    except Exception as e:
        print(f"[Clipboard] Lỗi ghi clipboard Win32: {e}")'''

new_set_files = '''def set_clipboard_files(file_paths, owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC: return
    try:
        if hasattr(sys, "clipboard_pipe_queue"):
            sys.clipboard_pipe_queue.put({"type": "files", "data": file_paths})
        else:
            clipboard_pipe_queue.put({"type": "files", "data": file_paths})
    except Exception as e:
        print(f"[Pipe] Lỗi chuyển tiếp clipboard files: {e}")'''

content = content.replace(old_set_files, run_clipboard_agent_code + '\n' + new_set_files)

old_set_text = '''def set_clipboard_text(text, owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC or not fn_OpenClipboard: return False
    if text is None: return False
    try:
        text_bytes = (text + "\\x00").encode('utf-16le')
        total_size = len(text_bytes)
        
        hGlobal = fn_GlobalAlloc(GHND, total_size)
        if not hGlobal: return False
            
        pMem = fn_GlobalLock(hGlobal)
        if not pMem:
            fn_GlobalFree(hGlobal)
            return False
            
        ctypes.memmove(pMem, text_bytes, total_size)
        fn_GlobalUnlock(hGlobal)
        
        hwnd_arg = owner_hwnd if owner_hwnd is not None else None
        opened = False
        for _ in range(10):
            if fn_OpenClipboard(hwnd_arg):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            try:
                fn_EmptyClipboard()
                res = fn_SetClipboardData(13, hGlobal)
                if not res:
                    fn_GlobalFree(hGlobal)
                    return False
                return True
            finally:
                fn_CloseClipboard()
        else:
            fn_GlobalFree(hGlobal)
            print("[Clipboard] Lỗi: OpenClipboard thất bại khi ghi dữ liệu text.")
    except Exception as e:
        print(f"[Clipboard] Lỗi ghi text clipboard Win32: {e}")
    return False'''

new_set_text = '''def set_clipboard_text(text, owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC: return False
    if text is None: return False
    try:
        if hasattr(sys, "clipboard_pipe_queue"):
            sys.clipboard_pipe_queue.put({"type": "text", "data": text})
        else:
            clipboard_pipe_queue.put({"type": "text", "data": text})
        return True
    except Exception as e:
        print(f"[Pipe] Lỗi chuyển tiếp clipboard text: {e}")
    return False'''

content = content.replace(old_set_text, new_set_text)

# 2. Modify ClipboardEventListener
old_listener_run = '''            add_res = user32.AddClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            log_debug(f"[Listener] AddClipboardFormatListener trả về: {add_res}")
            
            msg = wintypes.MSG()'''

new_listener_run = '''            add_res = user32.AddClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            log_debug(f"[Listener] AddClipboardFormatListener trả về: {add_res}")
            
            try:
                import win32ts
                win32ts.WTSRegisterSessionNotification(self.hwnd, 1) # NOTIFY_FOR_ALL_SESSIONS = 1
                log_debug("[Listener] Đã đăng ký WTSRegisterSessionNotification")
            except Exception as e:
                log_debug(f"[Listener] Lỗi WTSRegisterSessionNotification: {e}")
            
            msg = wintypes.MSG()'''
content = content.replace(old_listener_run, new_listener_run)

old_wndproc = '''        WM_CLIPBOARDUPDATE = 0x031D
        WM_RENDERFORMAT = 0x0305
        WM_DESTROYCLIPBOARD = 0x0307
        WM_SETUP_DELAYED_RENDERING = 0x0400 + 101
        
        if msg == WM_CLIPBOARDUPDATE:'''

new_wndproc = '''        WM_CLIPBOARDUPDATE = 0x031D
        WM_RENDERFORMAT = 0x0305
        WM_DESTROYCLIPBOARD = 0x0307
        WM_SETUP_DELAYED_RENDERING = 0x0400 + 101
        WM_WTSSESSION_CHANGE = 0x02B1
        
        if msg == WM_WTSSESSION_CHANGE:
            if wparam in (1, 5): # WTS_CONSOLE_CONNECT, WTS_SESSION_LOGON
                log_debug(f"[WndProc] Nhận WM_WTSSESSION_CHANGE Logon/Connect. session_id={lparam}")
                if self.manager:
                    try:
                        self.manager.on_session_logon(lparam)
                    except Exception as e:
                        log_debug(f"Error on session logon: {e}")
            return 0
        elif msg == WM_CLIPBOARDUPDATE:'''
content = content.replace(old_wndproc, new_wndproc)

# 3. Modify ClipboardSyncManager
old_manager_init = '''        self.last_rbutton_time = 0
        self.last_lbutton_time = 0
        if ENABLE_CLIPBOARD_SYNC:'''

new_manager_init = '''        self.last_rbutton_time = 0
        self.last_lbutton_time = 0
        
        self.current_pipe = None
        sys.clipboard_pipe_queue = clipboard_pipe_queue
        threading.Thread(target=self._pipe_server_thread_func, daemon=True).start()
        
        import win32ts
        try:
            current_session = win32ts.WTSGetActiveConsoleSessionId()
            if current_session != 0xFFFFFFFF and current_session != -1:
                self.spawn_clipboard_agent(current_session)
        except:
            pass
            
        if ENABLE_CLIPBOARD_SYNC:'''
content = content.replace(old_manager_init, new_manager_init)

manager_funcs = '''
    def _pipe_server_thread_func(self):
        import win32pipe, win32file, win32security, json, time
        pipe_name = r'\\\\.\\pipe\\RemoteAppClipboardPipe'
        
        sa = win32security.SECURITY_ATTRIBUTES()
        sa.bInheritHandle = 1
        sd = win32security.SECURITY_DESCRIPTOR()
        sd.Initialize()
        sd.SetSecurityDescriptorDacl(1, None, 0)
        sa.SECURITY_DESCRIPTOR = sd
        
        while True:
            pipe = None
            try:
                pipe = win32pipe.CreateNamedPipe(
                    pipe_name,
                    win32pipe.PIPE_ACCESS_DUPLEX,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                    1, 65536, 65536,
                    0,
                    sa
                )
                self.current_pipe = pipe
                win32pipe.ConnectNamedPipe(pipe, None)
                
                while True:
                    msg = clipboard_pipe_queue.get()
                    data = json.dumps(msg).encode('utf-8')
                    try:
                        win32file.WriteFile(pipe, data)
                    except Exception as e:
                        clipboard_pipe_queue.put(msg)
                        break
            except Exception as e:
                time.sleep(1)
            finally:
                if pipe:
                    try:
                        win32pipe.DisconnectNamedPipe(pipe)
                        win32file.CloseHandle(pipe)
                    except:
                        pass
                self.current_pipe = None

    def on_session_logon(self, session_id):
        import subprocess
        log_debug(f"[Agent] Session changed, killing old agent and spawning new one for session {session_id}")
        try:
            subprocess.run('taskkill /F /IM RemoteDesktopP2P.exe /FI "COMMANDLINE eq *--clipboard-agent*"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run('taskkill /F /IM python.exe /FI "COMMANDLINE eq *--clipboard-agent*"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass
        
        if self.current_pipe:
            try:
                import win32pipe
                win32pipe.DisconnectNamedPipe(self.current_pipe)
            except: pass
            
        self.spawn_clipboard_agent(session_id)

    def spawn_clipboard_agent(self, session_id):
        import win32ts
        import win32security
        import win32process
        import win32con
        import win32api
        import sys, os
        
        try:
            h_token = win32ts.WTSQueryUserToken(session_id)
            h_token_dup = win32security.DuplicateTokenEx(
                h_token,
                win32security.SecurityImpersonation,
                win32con.TOKEN_ALL_ACCESS,
                win32security.TokenPrimary
            )
            
            exe_path = sys.executable
            if getattr(sys, 'frozen', False) or hasattr(sys, '__compiled__'):
                cmd_line = f'"{exe_path}" --clipboard-agent'
                work_dir = os.path.dirname(exe_path)
            else:
                script_path = os.path.abspath(sys.argv[0])
                cmd_line = f'"{exe_path}" "{script_path}" --clipboard-agent'
                work_dir = os.path.dirname(script_path)
                
            startup_info = win32process.STARTUPINFO()
            startup_info.lpDesktop = 'winsta0\\\\default'
            
            h_process, h_thread, dw_pid, dw_tid = win32process.CreateProcessAsUser(
                h_token_dup,
                None,
                cmd_line,
                None,
                None,
                False,
                win32con.NORMAL_PRIORITY_CLASS | win32process.CREATE_NO_WINDOW,
                None,
                work_dir,
                startup_info
            )
            
            win32api.CloseHandle(h_process)
            win32api.CloseHandle(h_thread)
            win32api.CloseHandle(h_token)
            win32api.CloseHandle(h_token_dup)
            log_debug(f"[Agent] Đã spawn clipboard agent thành công, PID: {dw_pid}")
        except Exception as e:
            log_debug(f"[Agent] Lỗi spawn clipboard agent: {e}")

    def register_app(self, app):'''

content = content.replace("    def register_app(self, app):", manager_funcs)

# 4. Modify main
old_main = '''if __name__ == '__main__':
    import multiprocessing as mp'''

new_main = '''if __name__ == '__main__':
    import sys
    if "--clipboard-agent" in sys.argv:
        run_clipboard_agent()
        sys.exit(0)

    import multiprocessing as mp'''
content = content.replace(old_main, new_main)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Fix applied.")
