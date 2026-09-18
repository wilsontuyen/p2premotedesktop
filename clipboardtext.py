"""Text clipboard sync between client <-> host (both directions)."""
from __future__ import annotations

import ctypes
import json
import threading
import time

from network.socket_utils import send_msg, socket_passwords
from utils.logger import log_debug
from utils.clipboard_api import (
    clear_local_clipboard,
    get_clipboard_sequence_number,
    get_clipboard_text,
    is_own_clipboard_write,
    set_clipboard_text,
)


class ClipboardTextMixin:
    """Mixin: copy/paste text client <-> host."""

    def clear_local_and_notify_peers(self):
        """Xóa clipboard máy này và báo client/agent xóa theo."""
        self.pending_remote_files = []
        self.dummy_h_active = False
        hwnd = getattr(self, "cached_app_hwnd", None)
        if not hwnd and getattr(self, "listener", None):
            hwnd = getattr(self.listener, "hwnd", None)
        try:
            clear_local_clipboard(hwnd)
        except Exception as e:
            log_debug(f"[clear_local_and_notify_peers] local: {e}")
        if self.app and getattr(self.app, "is_headless", False):
            try:
                threading.Thread(target=self._send_to_pipe, args=("CLEAR", ""), daemon=True).start()
            except Exception:
                pass
        try:
            pkt = json.dumps({"type": "clear_clipboard"}).encode("utf-8")
            socks = set()
            try:
                socks.update(self.active_sockets)
            except Exception:
                pass
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
        except Exception as e:
            log_debug(f"[clear_local_and_notify_peers] notify: {e}")

    def _host_text_poll_loop(self):
        """Backup: worker poll copy trên host khi agent/WM_CLIPBOARDUPDATE miss."""
        last_seq = 0
        while True:
            time.sleep(0.35)
            try:
                if not self.active_sockets:
                    last_seq = 0
                    continue
                if getattr(self, "dummy_h_active", False):
                    continue
                if getattr(self, "is_rendering", False) or self.transfer_in_progress:
                    continue
                if is_own_clipboard_write():
                    continue
                seq = get_clipboard_sequence_number()
                if not seq or seq == last_seq:
                    continue
                if seq == getattr(self, "_last_sent_clip_seq", 0):
                    continue
                from utils.clipboard_api import clipboard_has_file_formats, get_clipboard_files
                if clipboard_has_file_formats():
                    files = get_clipboard_files(retries=1)
                    if files:
                        last_seq = seq
                        self._process_clipboard_change(provided_files=files, force=True)
                        continue
                text = get_clipboard_text()
                if not text:
                    last_seq = seq
                    continue
                if self._forward_clipboard_text(text):
                    last_seq = seq
                    print("[Clipboard] Host poll: phát hiện text mới, gửi sang client.")
            except Exception:
                pass

    def try_forward_local_clipboard_text(self, owner_hwnd=None):
        """Local copy text (không có file trên clipboard) → gửi sang peer."""
        current_text = get_clipboard_text(owner_hwnd)
        if not current_text:
            return False
        if self._forward_clipboard_text(current_text):
            log_debug(f"[Clipboard] Phát hiện text clipboard mới locally: {current_text[:50]}...")
            print("[Clipboard] Đang gửi text clipboard sang đối tác...")
            return True
        return False

    def _forward_clipboard_text(self, text):
        """Gửi text clipboard sang viewer/host. Cùng nội dung copy lần 2 vẫn gửi (theo sequence)."""
        if not text or not self.active_sockets:
            return False
        if is_own_clipboard_write():
            return False
        seq = get_clipboard_sequence_number()
        if seq and seq == getattr(self, "_last_sent_clip_seq", 0):
            return False
        pkt = json.dumps({"type": "clipboard_text", "text": text}).encode("utf-8")
        sent = False
        with self.lock:
            sockets_to_remove = []
            for s in list(self.active_sockets):
                try:
                    send_msg(s, pkt)
                    sent = True
                except Exception:
                    sockets_to_remove.append(s)
            for s in sockets_to_remove:
                if s in self.active_sockets:
                    self.active_sockets.remove(s)
        if sent:
            self.last_sent_text = text
            if seq:
                self._last_sent_clip_seq = seq
        return sent

    def _apply_remote_clipboard_text(self, text):
        """Ghi CF_UNICODETEXT trên thread của clipboard listener.

        ClipPkt gọi OpenClipboard(Tk hwnd) từ thread khác → fail, clipboard trống,
        Ctrl+V trên Host chỉ ding một tiếng.
        """
        self.pending_remote_files = []
        self._reoffer_files = None
        self.dummy_h_active = False
        hwnd = getattr(self.listener, "hwnd", None) if self.listener else None
        if hwnd:
            self._pending_set_text = text
            self.ignore_destroy_clipboard = True
            try:
                ctypes.windll.user32.SendMessageW(
                    ctypes.c_void_p(hwnd), 0x0400 + 102, 0, 0
                )
                log_debug("[_apply_remote_clipboard_text] SendMessage WM_SET_CLIP_TEXT xong")
                self._allow_delayed = False
                return
            except Exception as e:
                log_debug(f"[_apply_remote_clipboard_text] SendMessage: {e}")
            self.ignore_destroy_clipboard = False
        self.ignore_destroy_clipboard = True
        try:
            ok = set_clipboard_text(text, None)
            log_debug(f"[_apply_remote_clipboard_text] fallback set_clipboard_text={ok}")
            if ok:
                self._allow_delayed = False
        finally:
            self.ignore_destroy_clipboard = False

    def handle_clear_clipboard_packet(self, packet=None):
        """Peer yêu cầu xóa clipboard (type=clear_clipboard)."""
        del packet  # reserved
        self.pending_remote_files = []
        self.dummy_h_active = False
        hwnd = getattr(self, "cached_app_hwnd", None)
        if not hwnd and getattr(self, "listener", None):
            hwnd = getattr(self.listener, "hwnd", None)
        try:
            clear_local_clipboard(hwnd)
        except Exception as e:
            log_debug(f"[handle_clear_clipboard_packet] {e}")
        if self.app and getattr(self.app, "is_headless", False):
            try:
                threading.Thread(target=self._send_to_pipe, args=("CLEAR", ""), daemon=True).start()
            except Exception:
                pass
        print("[Clipboard] Đã xóa clipboard theo yêu cầu đối tác.")

    def handle_clipboard_text_packet(self, packet):
        """Nhận clipboard_text từ peer → ghi local (hoặc pipe agent khi headless)."""
        text = packet.get("text", "") if isinstance(packet, dict) else ""
        log_debug(f"[handle_clipboard_text_packet] Nhận clipboard_text: {str(text)[:50]}...")
        print("[Clipboard] Đã nhận được text clipboard từ remote. Đang cập nhật...")
        self.last_received_text = text
        if self.app and getattr(self.app, "is_headless", False):
            threading.Thread(target=self._send_to_pipe, args=("TEXT", text), daemon=True).start()
            log_debug("[handle_clipboard_text_packet] HEADLESS: gửi text qua Named Pipe cho Clipboard Agent.")
        else:
            self._apply_remote_clipboard_text(text)

    def apply_pending_clip_text_on_listener(self, hwnd):
        """WM_SET_CLIP_TEXT trên listener thread — set CF_UNICODETEXT an toàn."""
        text = getattr(self, "_pending_set_text", None)
        self._pending_set_text = None
        try:
            if text is not None:
                ok = set_clipboard_text(text, hwnd)
                if not ok:
                    ok = set_clipboard_text(text, None)
                log_debug(f"[apply_pending_clip_text_on_listener] ok={ok} n={len(text)}")
        finally:
            self.ignore_destroy_clipboard = False
