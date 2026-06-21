import codecs

with open('d:/Data/AG/remote_desktop/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Edit 1: _handle_uppipe_client
old1 = '''                if raw == "REQUEST_FILES":
                    log_debug("[_handle_uppipe_client] Nhận REQUEST_FILES từ Clipboard Agent. Bắt đầu tải file...")
                    print("[Clipboard] Clipboard Agent yêu cầu tải file (người dùng đã Paste).")
                    if self.pending_remote_files:
                        threading.Thread(target=self.request_pending_files, daemon=True).start()
                    else:
                        log_debug("[_handle_uppipe_client] Không có pending_remote_files để tải.")
                        if self.app and getattr(self.app, 'is_headless', False):
                            self._send_progress_signal("CANCEL", "")
                            self._close_transfer_pipe()'''
new1 = '''                if raw.startswith("REQUEST_FILES"):
                    log_debug("[_handle_uppipe_client] Nhận REQUEST_FILES từ Clipboard Agent. Bắt đầu tải file...")
                    print("[Clipboard] Clipboard Agent yêu cầu tải file (người dùng đã Paste).")
                    
                    parts = raw.split("|", 1)
                    requested_files = []
                    if len(parts) > 1 and parts[1].strip():
                        try:
                            import json
                            requested_files = json.loads(parts[1])
                        except Exception as e:
                            log_debug(f"[_handle_uppipe_client] Lỗi parse requested_files: {e}")
                            
                    if not requested_files:
                        requested_files = self.pending_remote_files
                        
                    if requested_files:
                        self.pending_remote_files = requested_files
                        threading.Thread(target=self.request_pending_files, daemon=True).start()
                    else:
                        log_debug("[_handle_uppipe_client] Không có pending_remote_files để tải.")
                        if self.app and getattr(self.app, 'is_headless', False):
                            self._send_progress_signal("CANCEL", "")
                            self._close_transfer_pipe()'''

# Edit 2: files_copied_meta PENDING
old2 = '''                msg = f"{display_name}|{total_size}"
                threading.Thread(target=self._send_to_pipe, args=("PENDING", msg), daemon=True).start()
                log_debug(f"[files_copied_meta] HEADLESS MODE: Đã gửi PENDING tới Agent để chờ Paste.")'''
new2 = '''                msg_dict = {
                    "display_name": display_name,
                    "total_size": total_size,
                    "files": self.pending_remote_files
                }
                import json
                msg = json.dumps(msg_dict)
                threading.Thread(target=self._send_to_pipe, args=("PENDING", msg), daemon=True).start()
                log_debug(f"[files_copied_meta] HEADLESS MODE: Đã gửi PENDING tới Agent để chờ Paste.")'''

# Edit 3: PENDING in Agent _agent_pipe_listener
old3 = '''                elif ptype == "PENDING":
                    agent_print("[ClipboardAgent] Nhận PENDING từ Host qua Named Pipe.")
                    parts = payload.split("|")
                    display_name = parts[0]
                    total_size = int(parts[1]) if len(parts) > 1 else 0
                    gui_queue.put(("pending", (display_name, total_size)))'''
new3 = '''                elif ptype == "PENDING":
                    agent_print("[ClipboardAgent] Nhận PENDING từ Host qua Named Pipe.")
                    try:
                        import json
                        info = json.loads(payload)
                        display_name = info.get("display_name", "Files")
                        total_size = info.get("total_size", 0)
                        files = info.get("files", [])
                    except Exception:
                        parts = payload.split("|")
                        display_name = parts[0]
                        total_size = int(parts[1]) if len(parts) > 1 else 0
                        files = []
                    gui_queue.put(("pending", (display_name, total_size, files)))'''

# Edit 4: _send_request_files_to_host definition
old4 = '''    def _send_request_files_to_host():
        """Gửi cờ REQUEST_FILES cho host qua UpPipe."""
        import win32file
        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
        try:
            import win32pipe
            try:
                win32pipe.WaitNamedPipe(pipe_name, 5000)
            except Exception as e:
                pass
            pipe_handle = win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_WRITE, 0, None,
                win32file.OPEN_EXISTING, 0, None
            )
            win32file.WriteFile(pipe_handle, b"REQUEST_FILES")'''
new4 = '''    def _send_request_files_to_host(files_to_request):
        """Gửi cờ REQUEST_FILES cho host qua UpPipe."""
        import win32file
        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
        try:
            import win32pipe
            try:
                win32pipe.WaitNamedPipe(pipe_name, 5000)
            except Exception as e:
                pass
            pipe_handle = win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_WRITE, 0, None,
                win32file.OPEN_EXISTING, 0, None
            )
            import json
            msg = "REQUEST_FILES|" + json.dumps(files_to_request)
            win32file.WriteFile(pipe_handle, msg.encode('utf-8'))'''

# Edit 5: call _send_request_files_to_host
old5 = '''                # Yêu cầu host bắt đầu gửi file
                _files_ready_event.clear()
                _files_ready_paths.clear()
                _send_request_files_to_host()'''
new5 = '''                # Yêu cầu host bắt đầu gửi file
                _files_ready_event.clear()
                _files_ready_paths.clear()
                _send_request_files_to_host(info.get("files", []))'''

# Edit 6: poll_gui_queue pending
old6 = '''                elif action == "pending":
                    # Host gửi PENDING:   setup delayed rendering nếu window đã sẵn sàng
                    display_name, total_size = val
                    _pending_info["display_name"] = display_name
                    _pending_info["total_size"] = total_size'''
new6 = '''                elif action == "pending":
                    # Host gửi PENDING:   setup delayed rendering nếu window đã sẵn sàng
                    display_name, total_size, files = val
                    _pending_info["display_name"] = display_name
                    _pending_info["total_size"] = total_size
                    _pending_info["files"] = files'''

content = content.replace(old1, new1)
content = content.replace(old2, new2)
content = content.replace(old3, new3)
content = content.replace(old4, new4)
content = content.replace(old5, new5)
content = content.replace(old6, new6)

with open('d:/Data/AG/remote_desktop/app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done replacing.')