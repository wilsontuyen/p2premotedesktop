import sys
import os

with open('clipboard_agent.py', 'r', encoding='utf-8') as f:
    agent_code = f.read()

# Extract run_clipboard_agent logic
run_clipboard_agent_code = """
import queue
clipboard_pipe_queue = queue.Queue()

def run_clipboard_agent():
    import sys, time, json
    import win32file, win32pipe
    
    if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
        try: sys.stdout.reconfigure(encoding='utf-8')
        except: pass

    pipe_name = r'\\\\.\\pipe\\RemoteAppClipboardPipe'
    
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
                    break
        except Exception:
            time.sleep(1)

def _clipboard_pipe_server_thread():
    import win32pipe, win32file, win32security, json, subprocess, sys, os
    import threading
    pipe_name = r'\\\\.\\pipe\\RemoteAppClipboardPipe'
    
    try:
        import win32ts, win32process, win32con
        exe_path = sys.executable if not getattr(sys, 'frozen', False) else sys.executable
        script_path = os.path.abspath(sys.argv[0])
        cmd_line = f'"{exe_path}" "{script_path}" --clipboard-agent' if not getattr(sys, 'frozen', False) else f'"{exe_path}" --clipboard-agent'
        
        session_id = win32ts.WTSGetActiveConsoleSessionId()
        h_token = win32ts.WTSQueryUserToken(session_id)
        h_token_dup = win32security.DuplicateTokenEx(h_token, win32security.SecurityImpersonation, win32con.TOKEN_ALL_ACCESS, win32security.TokenPrimary)
        startup_info = win32process.STARTUPINFO()
        startup_info.lpDesktop = 'winsta0\\\\default'
        win32process.CreateProcessAsUser(h_token_dup, None, cmd_line, None, None, False, win32con.NORMAL_PRIORITY_CLASS | win32process.CREATE_NO_WINDOW, None, os.path.dirname(script_path), startup_info)
    except Exception:
        try:
            exe_path = sys.executable if not getattr(sys, 'frozen', False) else sys.executable
            script_path = os.path.abspath(sys.argv[0])
            if not getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable, script_path, '--clipboard-agent'], creationflags=0x08000000)
            else:
                subprocess.Popen([exe_path, '--clipboard-agent'], creationflags=0x08000000)
        except:
            pass
            
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

import threading
threading.Thread(target=_clipboard_pipe_server_thread, daemon=True).start()
"""

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_set_files = '''def set_clipboard_files(file_paths, owner_hwnd=None):
    if not ENABLE_CLIPBOARD_SYNC: return
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
                res = fn_SetClipboardData(CF_HDROP, hGlobal)
                if not res:
                    fn_GlobalFree(hGlobal)
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
            
        import ctypes
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
        clipboard_pipe_queue.put({"type": "text", "data": text})
        return True
    except Exception as e:
        print(f"[Pipe] Lỗi chuyển tiếp clipboard text: {e}")
    return False'''

content = content.replace(old_set_text, new_set_text)

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
print('Done integrating agent!')
