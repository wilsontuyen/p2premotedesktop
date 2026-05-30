import re
import os

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove ClipboardEventListener class entirely
content = re.sub(r'class ClipboardEventListener:.*?def stop\(self\):.*?(?=\nclass ClipboardSyncManager:)', '', content, flags=re.DOTALL)

# 2. In ClipboardSyncManager.__init__, remove listener init
content = re.sub(r'if ENABLE_CLIPBOARD_SYNC:\s*self\.listener = ClipboardEventListener\(self\.on_clipboard_changed, self\)\s*else:\s*self\.listener = None', 'self.listener = None\n        self.agent_pipe_handle = None', content)

new_handle_packet = """
    def __del__(self):
        if hasattr(self, 'agent_pipe_handle') and self.agent_pipe_handle:
            try:
                import win32file
                win32file.CloseHandle(self.agent_pipe_handle)
            except:
                pass

    def send_to_agent_pipe(self, cmd_byte, data_bytes=b""):
        pipe_name = r'\\\\.\\pipe\\RemoteDesktopClipboardPipe'
        try:
            import win32file
            if not getattr(self, 'agent_pipe_handle', None):
                self.agent_pipe_handle = win32file.CreateFile(
                    pipe_name,
                    win32file.GENERIC_WRITE,
                    0, None,
                    win32file.OPEN_EXISTING,
                    0, None
                )
            
            win32file.WriteFile(self.agent_pipe_handle, cmd_byte + data_bytes)
            
            if cmd_byte == b'\\x03': # FILE_END
                pass
        except Exception as e:
            print(f"[Pipe] Lỗi gửi qua Pipe: {e}")
            if hasattr(self, 'agent_pipe_handle') and self.agent_pipe_handle:
                try: win32file.CloseHandle(self.agent_pipe_handle)
                except: pass
                self.agent_pipe_handle = None

    def handle_received_packet(self, packet):
        ptype = packet.get("type")
        
        if ptype == "cancel_transfer":
            print("[FileTransfer] Nhận tín hiệu hủy truyền tải từ đối tác.")
            self.cancel_active_transfer(remote_triggered=True)
            return
            
        elif ptype == "clipboard_text":
            text = packet.get("text", "")
            print(f"[Clipboard] Đã nhận được text clipboard từ remote. Đang cập nhật...")
            self.last_received_text = text
            try:
                owner_hwnd = None
                if self.app:
                    try: owner_hwnd = self.app.winfo_id()
                    except: pass
                set_clipboard_text(text, owner_hwnd)
            except Exception as e:
                print(e)
            return
            
        elif ptype == "files_copied_meta":
            self.pending_remote_files = packet.get("files", [])
            if not self.pending_remote_files: return
            
            # Yêu cầu tải file ngay lập tức, không qua delayed rendering
            import threading
            threading.Thread(target=self.request_pending_files, daemon=True).start()
            return
            
        elif ptype == "request_files":
            files_to_send = packet.get("files", [])
            import threading
            threading.Thread(target=self._process_send_requests, args=(self.sock, files_to_send), daemon=True).start()
            return
            
        elif ptype == "batch_start":
            self.batch_total_size = packet.get("total_size", 0)
            self.batch_received = 0
            display_name = packet.get("display_name", "Files")
            self.transfer_in_progress = True
            
        elif ptype == "file_start":
            filename = packet.get("name", "")
            if not filename: return
            
            # Đóng pipe cũ nếu có
            if hasattr(self, 'agent_pipe_handle') and self.agent_pipe_handle:
                try: 
                    import win32file
                    win32file.CloseHandle(self.agent_pipe_handle)
                except: pass
                self.agent_pipe_handle = None

            import struct
            name_bytes = filename.encode('utf-8')
            payload = struct.pack(">I", len(name_bytes)) + name_bytes
            self.send_to_agent_pipe(b'\\x01', payload)
            print(f"[FileTransfer] Bắt đầu nhận file: {filename}")

        elif ptype == "file_chunk":
            import base64
            import struct
            chunk_bytes = base64.b64decode(packet.get("data", ""))
            payload = struct.pack(">I", len(chunk_bytes)) + chunk_bytes
            self.send_to_agent_pipe(b'\\x02', payload)
            
            self.batch_received += len(chunk_bytes)
            self.update_dialog(self.batch_received)
                
        elif ptype == "file_end":
            self.send_to_agent_pipe(b'\\x03')
                
        elif ptype == "batch_end":
            self.close_dialog()
            self.transfer_done_event.set()
            
            if hasattr(self, 'agent_pipe_handle') and self.agent_pipe_handle:
                try: 
                    import win32file
                    win32file.CloseHandle(self.agent_pipe_handle)
                except: pass
                self.agent_pipe_handle = None
            print(f"[batch_end] Đã nhận xong toàn bộ file.")
"""

idx = content.find('    def handle_received_packet(self, packet):')
end_idx = content.find('clipboard_sync_manager = ClipboardSyncManager()')

if idx != -1 and end_idx != -1:
    new_content = content[:idx] + new_handle_packet + '\n\nclipboard_sync_manager = ClipboardSyncManager()' + content[end_idx + len('clipboard_sync_manager = ClipboardSyncManager()'):]
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Patched successfully!')
else:
    print('Indices not found!')
