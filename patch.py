import os
import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Inject the ClipboardEventListener class before ClipboardSyncManager
listener_code = """
# --- NATIVE CLIPBOARD EVENT LISTENER ---
WM_CLIPBOARDUPDATE = 0x031D
HWND_MESSAGE = -3
try:
    WNDPROCTYPE = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)
    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("style", ctypes.c_uint), ("lpfnWndProc", WNDPROCTYPE),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
                    ("hIconSm", wintypes.HICON)]
except:
    pass

class ClipboardEventListener:
    def __init__(self, callback):
        self.callback = callback
        self.hwnd = None
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_CLIPBOARDUPDATE:
            self.callback()
            return 0
        try:
            return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except:
            return 0

    def _run(self):
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.CreateWindowExW.argtypes = [
                ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
                ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
            ]
            user32.CreateWindowExW.restype = wintypes.HWND
            user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
            user32.DefWindowProcW.restype = ctypes.c_long
            kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

            wndproc = WNDPROCTYPE(self._wndproc)
            wndclass = WNDCLASSEX()
            wndclass.cbSize = ctypes.sizeof(WNDCLASSEX)
            wndclass.lpfnWndProc = wndproc
            wndclass.lpszClassName = "HiddenClipboardListener"
            wndclass.hInstance = kernel32.GetModuleHandleW(None)
            
            user32.RegisterClassExW(ctypes.byref(wndclass))
            self.hwnd = user32.CreateWindowExW(0, wndclass.lpszClassName, "HiddenWindow", 0, 0, 0, 0, 0, HWND_MESSAGE, 0, wndclass.hInstance, 0)
            user32.AddClipboardFormatListener(self.hwnd)
            
            msg = wintypes.MSG()
            while self.running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
                
            user32.RemoveClipboardFormatListener(self.hwnd)
            user32.DestroyWindow(self.hwnd)
            user32.UnregisterClassW(wndclass.lpszClassName, wndclass.hInstance)
        except Exception as e:
            print("[ClipboardEvent] Lỗi Listener:", e)

    def stop(self):
        self.running = False
        if self.hwnd:
            try: ctypes.windll.user32.PostMessageW(self.hwnd, 0, 0, 0)
            except: pass

class ClipboardSyncManager:"""

content = content.replace("class ClipboardSyncManager:", listener_code)

# 2. Update ClipboardSyncManager init
old_init = """    def __init__(self):
        self.last_files = []
        self.last_clipboard_seqs = {}  # Theo dõi Windows Clipboard Sequence Number theo từng socket (client)
        self.transfer_in_progress = False  # Cờ khóa: chặn monitor khi đang truyền file
        self.lock = threading.Lock()"""

new_init = """    def __init__(self):
        self.last_files = []
        self.active_sockets = set()
        self.transfer_in_progress = False
        self.lock = threading.Lock()
        if ENABLE_CLIPBOARD_SYNC:
            self.listener = ClipboardEventListener(self.on_clipboard_changed)
        else:
            self.listener = None"""

content = content.replace(old_init, new_init)

# 3. Add add_socket and remove_socket
add_remove = """    def register_app(self, app):
        self.app = app

    def add_socket(self, sock):
        if not ENABLE_CLIPBOARD_SYNC: return
        with self.lock:
            self.active_sockets.add(sock)
            
    def remove_socket(self, sock):
        with self.lock:
            if sock in self.active_sockets:
                self.active_sockets.remove(sock)"""

content = content.replace("""    def register_app(self, app):
        self.app = app""", add_remove)

# 4. Replace check_and_send with on_clipboard_changed and _process_clipboard_change
old_check = """    def check_and_send(self, sock):
        self.sock = sock
        try:
            # Khóa: không gửi clipboard khi đang có phiên truyền file để tránh loop
            if self.transfer_in_progress:
                return

            # Dùng Windows Clipboard Sequence Number để phát hiện mọi thay đổi clipboard,
            # kể cả khi người dùng copy lại đúng cùng 1 file sau khi đã bỏ qua.
            if not ENABLE_CLIPBOARD_SYNC or not fn_GetClipboardSequenceNumber:
                return
            current_seq = fn_GetClipboardSequenceNumber()
            sock_id = id(sock)
            with self.lock:
                last_seq = self.last_clipboard_seqs.get(sock_id, -1)
                if current_seq == last_seq:
                    return
            
            # Gắn kết OpenClipboard với HWND của Tkinter Window chính để hoạt động bình thường kể cả khi app chạy ẩn ở khay hệ thống
            owner_hwnd = None
            if self.app:
                try:
                    owner_hwnd = self.app.winfo_id()
                except:
                    pass
                    
            current_files = get_clipboard_files(owner_hwnd)
            if not current_files:
                # Cập nhật seq dù clipboard không có file để tránh check lại
                with self.lock:
                    self.last_clipboard_seqs[sock_id] = current_seq
                return

            with self.lock:
                self.last_clipboard_seqs[sock_id] = current_seq

            valid_files = [f for f in current_files if os.path.isfile(f)]
            if not valid_files: return
            
            metadata = []
            for filepath in valid_files:
                metadata.append({
                    "name": os.path.basename(filepath),
                    "size": os.path.getsize(filepath),
                    "path": filepath
                })
            
            if metadata:
                print(f"[Clipboard] Đã gửi tín hiệu files_copied_meta cho {len(metadata)} file.")
                pkt = json.dumps({"type": "files_copied_meta", "files": metadata}).encode('utf-8')
                send_msg(sock, pkt)
            
        except Exception as e:
            print(f"[FileTransfer] Monitor Error: {e}")"""

new_check = """    def on_clipboard_changed(self):
        if not ENABLE_CLIPBOARD_SYNC or self.transfer_in_progress: return
        threading.Thread(target=self._process_clipboard_change, daemon=True).start()

    def _process_clipboard_change(self):
        try:
            time.sleep(0.2) # Chờ xíu để Windows thả file lock
            owner_hwnd = None
            if self.app:
                try: owner_hwnd = self.app.winfo_id()
                except: pass
                
            current_files = get_clipboard_files(owner_hwnd)
            if not current_files: return
            
            valid_files = [f for f in current_files if os.path.isfile(f)]
            if not valid_files: return
            
            with self.lock:
                if valid_files == self.last_files: return
                self.last_files = valid_files
                
            metadata = [{"name": os.path.basename(f), "size": os.path.getsize(f), "path": f} for f in valid_files]
            if metadata and self.active_sockets:
                print(f"[Clipboard] Đã gửi tín hiệu files_copied_meta cho {len(metadata)} file qua EventListener.")
                pkt = json.dumps({"type": "files_copied_meta", "files": metadata}).encode('utf-8')
                with self.lock:
                    sockets_to_remove = []
                    for s in list(self.active_sockets):
                        try:
                            send_msg(s, pkt)
                        except Exception:
                            sockets_to_remove.append(s)
                    for s in sockets_to_remove:
                        if s in self.active_sockets: self.active_sockets.remove(s)
        except Exception as e:
            print(f"[FileTransfer] Monitor Error: {e}")"""

content = content.replace(old_check, new_check)

# 5. Remove loops
content = re.sub(r'def client_clipboard_monitor_loop\(sock\):.*?print\("\[Client\] Clipboard Monitor Thread Stopped\."\)', '', content, flags=re.DOTALL)

host_loop_old = """    def host_clipboard_monitor_loop(self, conn, client_state):
        if not ENABLE_CLIPBOARD_SYNC:
            print("[Host] Clipboard Monitor is disabled.")
            return
        print("[Host] Started Clipboard Monitor Thread.")
        while client_state.get("running", False):
            clipboard_sync_manager.check_and_send(conn)
            time.sleep(1.0)
        print("[Host] Clipboard Monitor Thread Stopped.")"""
content = content.replace(host_loop_old, "")

# 6. Change caller lines
content = content.replace("threading.Thread(target=client_clipboard_monitor_loop, args=(client_sock,), daemon=True).start()", "clipboard_sync_manager.add_socket(client_sock)")
content = content.replace("threading.Thread(target=self.host_clipboard_monitor_loop, args=(conn, client_state), daemon=True).start()", "clipboard_sync_manager.add_socket(conn)")

# 7. Remove GetClipboardSequenceNumber syncs
content = re.sub(r'\s*if ENABLE_CLIPBOARD_SYNC and fn_GetClipboardSequenceNumber and self\.sock:.*?self\.last_clipboard_seqs\[id\(self\.sock\)\] = fn_GetClipboardSequenceNumber\(\)', '', content, flags=re.DOTALL)
content = re.sub(r'\s*seq = ctypes\.windll\.user32\.GetClipboardSequenceNumber\(\)\s*if self\.sock:\s*self\.last_clipboard_seqs\[id\(self\.sock\)\] = seq', '', content, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied successfully.")
