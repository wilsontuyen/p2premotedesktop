import re
import codecs

with codecs.open('d:/Data/AG/remote_desktop/app.py', 'r', 'utf-8') as f:
    content = f.read()

# Edit 1: _handle_uppipe_client
content = re.sub(
    r'if raw == \x22REQUEST_FILES\x22:.*?else:',
    '''if raw.startswith(\"REQUEST_FILES\"):
                    log_debug(\"[_handle_uppipe_client] Nhận REQUEST_FILES từ Clipboard Agent. Bắt đầu tải file...\")
                    
                    parts = raw.split(\"|\", 1)
                    requested_files = []
                    if len(parts) > 1 and parts[1].strip():
                        try:
                            import json
                            requested_files = json.loads(parts[1])
                        except Exception as e:
                            log_debug(f\"[_handle_uppipe_client] Lỗi parse requested_files: {e}\")
                            
                    if not requested_files:
                        requested_files = self.pending_remote_files
                        
                    if requested_files:
                        self.pending_remote_files = requested_files
                        threading.Thread(target=self.request_pending_files, daemon=True).start()
                    else:
                        log_debug(\"[_handle_uppipe_client] Không có pending_remote_files để tải.\")
                        if self.app and getattr(self.app, 'is_headless', False):
                            self._send_progress_signal(\"CANCEL\", \"\")
                            self._close_transfer_pipe()
                else:''',
    content,
    flags=re.DOTALL
)

# Edit 2: files_copied_meta PENDING
content = re.sub(
    r'msg = f\x22\{display_name\}\|\{total_size\}\x22\s*threading\.Thread\(target=self\._send_to_pipe,\s*args=\(\x22PENDING\x22,\s*msg\),\s*daemon=True\)\.start\(\)\s*log_debug\(f\x22\[files_copied_meta\] HEADLESS MODE:[^\n]+\)',
    '''msg_dict = {
                    \"display_name\": display_name,
                    \"total_size\": total_size,
                    \"files\": self.pending_remote_files
                }
                import json
                msg = json.dumps(msg_dict)
                threading.Thread(target=self._send_to_pipe, args=(\"PENDING\", msg), daemon=True).start()
                log_debug(f\"[files_copied_meta] HEADLESS MODE: Đã gửi PENDING tới Agent để chờ Paste.\")''',
    content,
    flags=re.DOTALL
)

# Edit 3: PENDING in Agent _agent_pipe_listener
content = re.sub(
    r'elif ptype == \x22PENDING\x22:\s*agent_print\([^)]+\)\s*parts = payload\.split\(\x22\|\x22\)\s*display_name = parts\[0\]\s*total_size = int\(parts\[1\]\) if len\(parts\) > 1 else 0\s*gui_queue\.put\(\(\x22pending\x22,\s*\(display_name,\s*total_size\)\)\)',
    '''elif ptype == \"PENDING\":
                    agent_print(\"[ClipboardAgent] Nhận PENDING từ Host qua Named Pipe.\")
                    try:
                        import json
                        info = json.loads(payload)
                        display_name = info.get(\"display_name\", \"Files\")
                        total_size = info.get(\"total_size\", 0)
                        files = info.get(\"files\", [])
                    except Exception:
                        parts = payload.split(\"|\")
                        display_name = parts[0]
                        total_size = int(parts[1]) if len(parts) > 1 else 0
                        files = []
                    gui_queue.put((\"pending\", (display_name, total_size, files)))''',
    content,
    flags=re.DOTALL
)

# Edit 4: _send_request_files_to_host
content = re.sub(
    r'def _send_request_files_to_host\(\):.*?win32file\.WriteFile\(pipe_handle,\s*b\x22REQUEST_FILES\x22\)',
    '''def _send_request_files_to_host(files_to_request):
        \"\"\"Gửi cờ REQUEST_FILES cho host qua UpPipe.\"\"\"
        import win32file
        pipe_name = r\"\\\\.\\pipe\\RemoteDesktopClipboardUpPipe\"
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
            msg = \"REQUEST_FILES|\" + json.dumps(files_to_request)
            win32file.WriteFile(pipe_handle, msg.encode('utf-8'))''',
    content,
    flags=re.DOTALL
)

# Edit 5: call _send_request_files_to_host
content = re.sub(
    r'_send_request_files_to_host\(\)\s*deadline = time\.time\(\) \+ 600\.0',
    '''_send_request_files_to_host(info.get(\"files\", []))
                
                deadline = time.time() + 600.0''',
    content,
    flags=re.DOTALL
)

# Edit 6: poll_gui_queue pending
content = re.sub(
    r'elif action == \x22pending\x22:\s*#[^\n]+\s*display_name,\s*total_size = val\s*_pending_info\[\x22display_name\x22\] = display_name\s*_pending_info\[\x22total_size\x22\] = total_size',
    '''elif action == \"pending\":
                    # Host gửi PENDING: setup delayed rendering nếu window đã sẵn sàng
                    display_name, total_size, files = val
                    _pending_info[\"display_name\"] = display_name
                    _pending_info[\"total_size\"] = total_size
                    _pending_info[\"files\"] = files''',
    content,
    flags=re.DOTALL
)

with codecs.open('d:/Data/AG/remote_desktop/app.py', 'w', 'utf-8') as f:
    f.write(content)
print('Done!')