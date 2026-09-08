import threading
import time
import sys
import json
import pyperclip

# Stub variables to match Windows signatures
ENABLE_CLIPBOARD_SYNC = True

class ClipboardSyncManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.active_sockets = set()
        self.app = None
        self.last_text = ""
        self.running = True
        
        # Start a simple polling thread for text clipboard changes
        self.poll_thread = threading.Thread(target=self._poll_clipboard, daemon=True)
        self.poll_thread.start()

    def register_app(self, app):
        self.app = app

    def add_socket(self, sock):
        with self.lock:
            self.active_sockets.add(sock)

    def remove_socket(self, sock):
        with self.lock:
            if sock in self.active_sockets:
                self.active_sockets.remove(sock)

    def cancel_active_transfer(self, remote_triggered=False):
        pass

    def clear_local_and_notify_peers(self):
        try:
            pyperclip.copy("")
            self.last_text = ""
        except Exception:
            pass
        try:
            from network.socket_utils import socket_passwords, send_msg
            pkt = json.dumps({"type": "clear_clipboard"}).encode("utf-8")
            socks = set(self.active_sockets)
            try:
                socks.update(socket_passwords.keys())
            except Exception:
                pass
            for conn in list(socks):
                try:
                    pw = socket_passwords.get(conn)
                    if pw is not None:
                        send_msg(conn, pkt, pw)
                except Exception:
                    pass
        except Exception:
            pass

    def process_clipboard_event(self, packet):
        self.handle_received_packet(packet)

    def handle_received_packet(self, packet):
        try:
            ptype = packet.get("type")
            if ptype == "clear_clipboard":
                try:
                    pyperclip.copy("")
                    self.last_text = ""
                except Exception:
                    pass
                return
            if getattr(self, '_receive_cancelled', False) and ptype in ("file_start", "file_chunk", "file_end", "batch_end"):
                return

            if ptype == "batch_start":
                self.batch_total_size = packet.get("total_size", 0)
                self.batch_received = 0
            elif ptype == "file_start":
                import os
                self.current_filename = packet.get("name")
                self.current_target_dir = packet.get("target_dir", getattr(self, "target_save_dir", ""))
                if not os.path.exists(self.current_target_dir):
                    os.makedirs(self.current_target_dir, exist_ok=True)
                path = os.path.join(self.current_target_dir, self.current_filename)
                self.current_file = open(path, "wb")
            elif ptype == "file_chunk":
                if hasattr(self, 'current_file') and self.current_file:
                    import base64
                    data = base64.b64decode(packet.get("data", ""))
                    self.current_file.write(data)
                    self.batch_received += len(data)
                    if hasattr(self, 'active_dialog') and self.active_dialog:
                        try:
                            self.active_dialog.after(0, lambda v=self.batch_received: getattr(self, 'active_dialog') and self.active_dialog.update_progress(v))
                        except: pass
            elif ptype == "file_end":
                if hasattr(self, 'current_file') and self.current_file:
                    self.current_file.close()
                    self.current_file = None
                
                if not getattr(self, 'incoming_transfers', False) and getattr(self, 'active_batch', False) and getattr(self, 'batch_total_size', 0) > 0 and getattr(self, 'batch_received', 0) >= self.batch_total_size:
                    if hasattr(self, 'active_dialog') and self.active_dialog:
                        try:
                            self.active_dialog.after(0, lambda d=self.active_dialog: d.destroy())
                        except: pass
                        self.active_dialog = None
                    try:
                        import core.viewer
                        if core.viewer.file_manager_callback:
                            core.viewer.file_manager_callback({"type": "trigger_local_refresh"})
                    except: pass
                    self.active_batch = False
            elif ptype == "batch_end":
                if hasattr(self, 'active_dialog') and self.active_dialog:
                    try:
                        self.active_dialog.after(0, lambda d=self.active_dialog: d.destroy())
                    except: pass
                self.active_dialog = None
                self._receive_cancelled = False
                try:
                    import core.viewer
                    if core.viewer.file_manager_callback:
                        core.viewer.file_manager_callback({"type": "trigger_local_refresh"})
                except: pass
        except Exception as e:
            print(f"[MacClipboard] Lỗi xử lý packet {packet.get('type')}: {e}")
        
    def _poll_clipboard(self):
        while self.running:
            try:
                current_text = pyperclip.paste()
                if current_text and current_text != self.last_text:
                    self.last_text = current_text
                    self._send_text_to_remotes(current_text)
            except Exception:
                pass
            time.sleep(1)
            
    def _send_text_to_remotes(self, text):
        from network.socket_utils import send_msg
        with self.lock:
            if not self.active_sockets:
                return
            try:
                import base64
                encoded_text = base64.b64encode(text.encode('utf-8')).decode('utf-8')
                pkt = json.dumps({"type": "clipboard_text", "data": encoded_text}).encode('utf-8')
                for s in list(self.active_sockets):
                    try:
                        send_msg(s, pkt)
                    except Exception:
                        pass
            except Exception:
                pass

clipboard_sync_manager = ClipboardSyncManager()

def run_clipboard_agent_mode():
    print("[MacClipboard] Clipboard agent mode is not fully implemented on Mac yet.")
    sys.exit(0)
