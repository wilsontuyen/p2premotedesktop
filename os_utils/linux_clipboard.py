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

    def handle_received_packet(self, packet):
        pass
        
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
    print("[LinuxClipboard] Clipboard agent mode is not fully implemented on Linux yet.")
    sys.exit(0)
