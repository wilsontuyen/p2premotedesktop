import re
import os

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

new_csm = """
class ClipboardSyncManager:
    def __init__(self):
        import queue, threading
        self.gui_queue = queue.Queue()
        self.active_sockets = set()
        self.transfer_in_progress = False
        self.lock = threading.Lock()
        
        self.app = None
        self.active_dialog = None
        self.batch_received = 0
        self.batch_total_size = 0
        self.batch_paths = []
        
        self.pending_remote_files = []
        self.sock = None
        self.target_save_dir = ""
        self.is_paste_triggered = False
        self.meta_arrival_time = 0
        
        self.ipc_sock = None
        self.dummy_monitor_started = False
        self.overwrite_event = threading.Event()
        self.overwrite_choice = None
        
        # Determine mode
        import sys
        self.is_headless = "--headless" in sys.argv
        
        if self.is_headless:
            threading.Thread(target=self._ipc_server_loop, daemon=True).start()
        else:
            threading.Thread(target=self._ipc_client_loop, daemon=True).start()

    def register_app(self, app):
        self.app = app
        self.poll_gui_queue()

    def poll_gui_queue(self):
        if not self.app: return
        self.process_gui_queue()
        try:
            self.app.after(50, self.poll_gui_queue)
        except:
            pass

    def process_gui_queue(self):
        if self.app and getattr(self.app, 'is_headless', False):
            import queue
            while not self.gui_queue.empty():
                try: self.gui_queue.get_nowait()
                except queue.Empty: break
            return
        import queue, time
        while not self.gui_queue.empty():
            try:
                action, args = self.gui_queue.get_nowait()
                if action == "create":
                    title_text, filename, total_size = args
                    if self.active_dialog:
                        try: self.active_dialog.destroy()
                        except: pass
                    self.active_dialog = ProgressDialog(
                        self.app, title_text, filename, total_size,
                        on_cancel=lambda: self.cancel_active_transfer(remote_triggered=False)
                    )
                elif action == "update":
                    sent_bytes = args
                    if self.active_dialog:
                        try: self.active_dialog.update_progress(sent_bytes)
                        except: pass
                elif action == "destroy":
                    if self.active_dialog:
                        def _do_destroy():
                            if self.active_dialog:
                                try:
                                    self.active_dialog.on_cancel = None
                                    self.active_dialog.destroy()
                                except: pass
                                self.active_dialog = None
                        self.app.after(500, _do_destroy)
                elif action == "classic_overwrite_dialog":
                    filename, source_info, dest_info, has_multiple = args
                    dialog = ClassicCopyDialog(self.app, filename, source_info, dest_info, has_multiple)
                    def _on_destroy(event):
                        if event.widget == dialog:
                            self.overwrite_choice = dialog.choice if dialog.choice else "cancel"
                            self.overwrite_all = dialog.var_all.get() if hasattr(dialog, 'var_all') else False
                            self.overwrite_event.set()
                    dialog.bind("<Destroy>", _on_destroy)
            except queue.Empty:
                break
            except Exception as e:
                print(f"[process_gui_queue] Lỗi: {e}")

    def add_socket(self, sock):
        with self.lock:
            self.active_sockets.add(sock)
            self.sock = sock
            
    def remove_socket(self, sock):
        with self.lock:
            if sock in self.active_sockets:
                self.active_sockets.remove(sock)

    def show_dialog(self, title_text, filename, total_size):
        self.gui_queue.put(("create", (title_text, filename, total_size)))

    def update_dialog(self, sent_bytes):
        self.gui_queue.put(("update", sent_bytes))

    def close_dialog(self):
        self.gui_queue.put(("destroy", None))

    def cancel_active_transfer(self, remote_triggered=False):
        pass # Optional implementation

    def show_classic_conflict_dialog(self, filename, source_info, dest_info, has_multiple=False):
        if self.app and getattr(self.app, 'is_headless', False):
            return "replace_all" if has_multiple else "replace"
        self.overwrite_event.clear()
        self.overwrite_choice = None
        self.overwrite_all = False
        
        self.gui_queue.put(("classic_overwrite_dialog", (filename, source_info, dest_info, has_multiple)))
        
        import time, ctypes
        from ctypes import wintypes
        start_wait = time.time()
        msg = wintypes.MSG()
        while time.time() - start_wait < 300.0:
            if self.overwrite_event.is_set():
                break
            if ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
            else:
                time.sleep(0.01)
                
        choice = self.overwrite_choice if self.overwrite_choice else "cancel"
        if choice in ("replace", "skip") and self.overwrite_all:
            choice = choice + "_all"
        return choice

    def get_active_explorer_path(self):
        try:
            import win32gui
            import win32com.client
            import ctypes
            from ctypes import wintypes
            
            hwnds_to_check = []
            
            def get_root_hwnd(h):
                if not h: return None
                try:
                    root = ctypes.windll.user32.GetAncestor(h, 2)
                    return root if root else h
                except:
                    return h
            
            try:
                hwnd_clip = ctypes.windll.user32.GetOpenClipboardWindow()
                if hwnd_clip:
                    root_clip = get_root_hwnd(hwnd_clip)
                    if root_clip and root_clip not in hwnds_to_check:
                        hwnds_to_check.append(root_clip)
            except: pass
                
            try:
                hwnd_fg = win32gui.GetForegroundWindow()
                if hwnd_fg:
                    root_fg = get_root_hwnd(hwnd_fg)
                    if root_fg and root_fg not in hwnds_to_check:
                        hwnds_to_check.append(root_fg)
            except: pass
                
            try:
                pt = wintypes.POINT()
                if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                    hwnd_mouse = ctypes.windll.user32.WindowFromPoint(pt)
                    if hwnd_mouse:
                        root_mouse = get_root_hwnd(hwnd_mouse)
                        if root_mouse and root_mouse not in hwnds_to_check:
                            hwnds_to_check.append(root_mouse)
            except: pass
            
            shell = win32com.client.Dispatch("Shell.Application")
            
            import os
            for hwnd in hwnds_to_check:
                if not hwnd: continue
                try:
                    desktop_hwnd = win32gui.GetDesktopWindow()
                    class_name = win32gui.GetClassName(hwnd)
                    if hwnd == desktop_hwnd or class_name in ("Progman", "WorkerW"):
                        return os.path.join(os.path.expanduser("~"), "Desktop")
                except: pass
                    
                for window in shell.Windows():
                    try:
                        if int(window.HWND) == hwnd:
                            doc = window.Document
                            if doc:
                                try:
                                    sel = doc.SelectedItems()
                                    if sel.Count == 1 and sel.Item(0).IsFolder:
                                        return sel.Item(0).Path
                                except: pass
                                return doc.Folder.Self.Path
                    except:
                        continue
        except:
            pass
        return None

    # =========================================================================
    # HEADLESS SERVICE IPC SERVER
    # =========================================================================
    def _ipc_server_loop(self):
        import socket, json, time, struct, base64
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('127.0.0.1', 44444))
        server.listen(1)
        print("[Service IPC] Đang chờ GUI Agent kết nối...")
        
        while True:
            try:
                conn, addr = server.accept()
                print(f"[Service IPC] Đã kết nối với GUI Agent.")
                self.ipc_sock = conn
                
                while True:
                    length_bytes = self._recv_exact(conn, 4)
                    if not length_bytes: break
                    length = struct.unpack(">I", length_bytes)[0]
                    data = self._recv_exact(conn, length)
                    if not data: break
                    packet = json.loads(data.decode('utf-8'))
                    
                    if packet.get("type") == "request_files":
                        if self.sock:
                            pkt = json.dumps({"type": "request_files", "files": packet.get("files")}).encode('utf-8')
                            send_msg(self.sock, pkt)
            except Exception as e:
                print(f"[Service IPC] Lỗi: {e}")
            finally:
                if self.ipc_sock:
                    try: self.ipc_sock.close()
                    except: pass
                    self.ipc_sock = None
                time.sleep(1)

    def _recv_exact(self, sock, length):
        data = b''
        while len(data) < length:
            try:
                packet = sock.recv(length - len(data))
                if not packet: return None
                data += packet
            except:
                return None
        return data

    def send_to_ipc(self, packet):
        import json, struct
        if not self.ipc_sock: return
        try:
            data = json.dumps(packet).encode('utf-8')
            self.ipc_sock.sendall(struct.pack(">I", len(data)) + data)
        except:
            pass

    # =========================================================================
    # GUI AGENT IPC CLIENT
    # =========================================================================
    def _ipc_client_loop(self):
        import socket, json, time, struct, os, base64
        import win32clipboard, ctypes
        
        def _set_dummy_clipboard(path):
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                
                class DROPFILES(ctypes.Structure):
                    _fields_ = [("pFiles", ctypes.wintypes.DWORD), ("pt", ctypes.wintypes.POINT), ("fNC", ctypes.wintypes.BOOL), ("fWide", ctypes.wintypes.BOOL)]
                
                paths_bytes = (path + "\x00\x00").encode('utf-16le')
                struct_size = ctypes.sizeof(DROPFILES)
                k32 = ctypes.WinDLL("kernel32.dll")
                u32 = ctypes.WinDLL("user32.dll")
                
                hGlobal = k32.GlobalAlloc(0x0042, struct_size + len(paths_bytes))
                pMem = k32.GlobalLock(hGlobal)
                dropfiles = DROPFILES()
                dropfiles.pFiles = struct_size
                dropfiles.fWide = True
                
                ctypes.memmove(pMem, ctypes.byref(dropfiles), struct_size)
                ctypes.memmove(pMem + struct_size, paths_bytes, len(paths_bytes))
                k32.GlobalUnlock(hGlobal)
                
                u32.SetClipboardData(15, hGlobal)
                win32clipboard.CloseClipboard()
                print(f"[GUI Agent] Đã nạp dummy file vào Clipboard: {path}")
            except Exception as e:
                print(f"[GUI Agent] Lỗi set clipboard dummy: {e}")

        temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
        os.makedirs(temp_dir, exist_ok=True)
        current_handle = None
        current_path = None
        
        while True:
            try:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.connect(('127.0.0.1', 44444))
                self.ipc_sock = conn
                print("[GUI Agent] Đã kết nối với Service IPC.")
                
                if not self.dummy_monitor_started:
                    self.dummy_monitor_started = True
                    import threading
                    threading.Thread(target=self._dummy_monitor_loop, daemon=True).start()
                
                while True:
                    length_bytes = self._recv_exact(conn, 4)
                    if not length_bytes: break
                    length = struct.unpack(">I", length_bytes)[0]
                    data = self._recv_exact(conn, length)
                    if not data: break
                    packet = json.loads(data.decode('utf-8'))
                    ptype = packet.get("type")
                    
                    if ptype == "files_copied_meta":
                        self.pending_remote_files = packet.get("files", [])
                        dummy_path = os.path.join(temp_dir, "RemoteDesktop_Paste_Trigger.tmp")
                        with open(dummy_path, "w") as f: f.write("PASTE_TRIGGER")
                        _set_dummy_clipboard(dummy_path)
                        
                    elif ptype == "batch_start":
                        self.batch_total_size = packet.get("total_size", 0)
                        self.batch_received = 0
                        self.batch_paths = []
                        self.show_dialog("Đang tải file về...", packet.get("display_name", "Files"), self.batch_total_size)
                        
                    elif ptype == "file_start":
                        filename = packet.get("name", "")
                        current_path = os.path.join(temp_dir, filename)
                        try: current_handle = open(current_path, "wb")
                        except: pass
                        
                    elif ptype == "file_chunk":
                        chunk = base64.b64decode(packet.get("data", ""))
                        if current_handle:
                            current_handle.write(chunk)
                        self.batch_received += len(chunk)
                        self.update_dialog(self.batch_received)
                        
                    elif ptype == "file_end":
                        if current_handle:
                            current_handle.close()
                            current_handle = None
                        if current_path:
                            self.batch_paths.append((packet.get("name"), current_path))
                            current_path = None
                            
                    elif ptype == "batch_end":
                        self.close_dialog()
                        import shutil
                        
                        replace_all = False
                        skip_all = False
                        
                        for filename, tmppath in self.batch_paths:
                            dest_path = os.path.join(self.target_save_dir, filename)
                            if os.path.exists(dest_path):
                                if skip_all: continue
                                if not replace_all:
                                    s_stat = os.stat(tmppath)
                                    source_info = {"size": s_stat.st_size, "mtime": s_stat.st_mtime}
                                    d_stat = os.stat(dest_path)
                                    dest_info = {"size": d_stat.st_size, "mtime": d_stat.st_mtime, "path": dest_path}
                                    
                                    choice = self.show_classic_conflict_dialog(filename, source_info, dest_info, len(self.batch_paths) > 1)
                                    
                                    if choice == "replace_all":
                                        replace_all = True
                                    elif choice == "skip_all":
                                        skip_all = True
                                        continue
                                    elif choice == "skip":
                                        continue
                                    elif choice == "cancel":
                                        break
                                try: os.remove(dest_path)
                                except: pass
                            try:
                                shutil.move(tmppath, dest_path)
                                print(f"[GUI Agent] Đã chuyển file tới: {dest_path}")
                            except Exception as e:
                                print(f"[GUI Agent] Lỗi chuyển file: {e}")
                                
                        print("[GUI Agent] Hoàn thành luồng Paste!")
                        
            except Exception as e:
                pass
            finally:
                if getattr(self, 'ipc_sock', None):
                    try: self.ipc_sock.close()
                    except: pass
                    self.ipc_sock = None
                time.sleep(1)

    def _dummy_monitor_loop(self):
        import time, os, threading
        temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
        
        while True:
            time.sleep(0.5)
            if not self.pending_remote_files:
                continue
                
            dest_dir = self.get_active_explorer_path()
            if dest_dir and os.path.isdir(dest_dir):
                dummy_dest = os.path.join(dest_dir, "RemoteDesktop_Paste_Trigger.tmp")
                if os.path.exists(dummy_dest):
                    print(f"[GUI Agent] Phát hiện Paste tại: {dest_dir}")
                    try: os.remove(dummy_dest)
                    except: pass
                    
                    self.target_save_dir = dest_dir
                    self.send_to_ipc({"type": "request_files", "files": self.pending_remote_files})
                    self.pending_remote_files = []

    # =========================================================================
    # NETWORK PACKET HANDLER (HEADLESS SERVICE)
    # =========================================================================
    def handle_received_packet(self, packet):
        ptype = packet.get("type")
        
        if ptype == "request_files":
            files_to_send = packet.get("files", [])
            import threading
            threading.Thread(target=self._process_send_requests, args=(self.sock, files_to_send), daemon=True).start()
            return
            
        # Các packet nhận file đều được forward sang GUI Agent
        if ptype in ("files_copied_meta", "batch_start", "file_start", "file_chunk", "file_end", "batch_end"):
            self.send_to_ipc(packet)

    def _process_send_requests(self, sock, files):
        import json, base64, os
        try:
            total_size = sum(f.get("size", 0) for f in files)
            display_name = f"{len(files)} tệp tin" if len(files) > 1 else files[0].get("name", "Unknown")
            
            send_msg(sock, json.dumps({
                "type": "batch_start",
                "count": len(files),
                "total_size": total_size,
                "display_name": display_name
            }).encode('utf-8'))
            
            for f in files:
                filepath = f["path"]
                filename = f["name"]
                file_size = f["size"]
                
                if not os.path.exists(filepath): continue
                    
                send_msg(sock, json.dumps({"type": "file_start", "name": filename, "size": file_size}).encode('utf-8'))
                
                try:
                    with open(filepath, "rb") as fh:
                        while True:
                            chunk_data = fh.read(4 * 1024 * 1024)
                            if not chunk_data: break
                            b64 = base64.b64encode(chunk_data).decode('utf-8')
                            send_msg(sock, json.dumps({"type": "file_chunk", "name": filename, "data": b64}).encode('utf-8'))
                except Exception as e:
                    print(f"Lỗi gửi file: {e}")
                    
                send_msg(sock, json.dumps({"type": "file_end", "name": filename}).encode('utf-8'))
                
            send_msg(sock, json.dumps({"type": "batch_end"}).encode('utf-8'))
        except Exception as e:
            print(f"Error processing send request: {e}")
            
clipboard_sync_manager = ClipboardSyncManager()
"""

match = re.search(r'class ClipboardSyncManager:.*?(?=clipboard_sync_manager = ClipboardSyncManager\(\))', content, re.DOTALL)
if match:
    new_content = content[:match.start()] + new_csm + content[match.end() + len('clipboard_sync_manager = ClipboardSyncManager()'):]
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Patched app.py")
else:
    print("Not found")
