import os
import sys
import time
import json
import queue
import threading
import socket
import ctypes
from ctypes import wintypes
import logging
import win32file
import win32pipe
import win32event
import win32api
import win32gui
import psutil
import tkinter as tk
import base64

last_clipboard_set_time = 0.0

from core.config import *
from network.socket_utils import socket_passwords, send_msg, recv_msg, is_lan_socket, tune_socket_for_lan_bulk
from gui.components import ClassicCopyDialog
from gui.windows_ui import ProgressDialog, file_download_dialog_title
from utils.logger import log_file_transfer, log_activity, log_debug
from core.i18n import _

CLIPBOARD_PKT_TYPES = (
    "batch_start", "file_start", "file_chunk", "file_end", "batch_end",
    "files_copied_meta", "request_files", "cancel_transfer", "cancel_ack",
    "clipboard_text", "clipboard_image", "clear_clipboard",
    "resume_query", "resume_state",
    "paste_conflict_query", "paste_conflict_reply",
)

from utils.clipboard_api import (
    ENABLE_CLIPBOARD_SYNC,
    set_clipboard_dword_format,
    setup_clipboard_exclusions,
    clipboard_has_file_formats,
    get_clipboard_files,
    set_clipboard_files,
    get_clipboard_text,
    set_clipboard_text,
    create_hdrop_data,
    fn_SetClipboardData,
    fn_GlobalFree,
    clear_local_clipboard,
    get_clipboard_sequence_number,
    mark_own_clipboard_write,
    is_own_clipboard_write,
    should_preserve_user_clipboard,
)

from clipboardtext import ClipboardTextMixin
from filecopyclient import (
    FileCopyClientMixin,
    HEADLESS_TRANSFER_DIR,
    _cleanup_stale_transfers,
    _pump_messages_except_clipboard_render,
    _incoming_key,
    _xfer_staging_dir,
    _hide_win_path,
    _purge_rdxfer_staging,
    _is_transfer_staging_dir,
    _file_offer_fp,
    _rel_copy_name,
    _copy_batch_kind_and_name,
    _localized_batch_name,
    _same_volume,
    _path_byte_size,
    _copy_file_with_progress,
    relocate_transfer_files,
    _relocate_transfer_files_unlocked,
    _promote_completed_xfer_file,
    _collect_actual_file_sizes,
    _paths_match_expected_sizes,
    query_explorer_folder_path,
    _hwnd_class_name,
    _hwnd_is_context_menu,
    _cursor_over_context_menu,
    _cursor_point,
    _context_menu_root_hwnd,
    _win32_menu_text_at_point,
    _xaml_click_is_show_more_strip,
    _classify_context_menu_item,
    _capture_menu_item_at_cursor,
    _is_windows_11,
    _shell_menu_profile,
    _menu_item_counts_as_paste,
    _win10_rmb_paste_click,
    _pid_image_name,
    _hwnd_process_name,
    _cursor_over_current_process,
    _is_explorer_clipboard_client,
    _cursor_in_explorer_command_bar,
    _retry_remove_path,
    cleanup_probe_stubs,
    _is_paste_placeholder,
    _file_expected_size,
    _is_incomplete_transfer_file,
    _path_in_xfer_staging,
    _is_transfer_junk_at_dest,
    cleanup_incomplete_named_files,
    _probe_stub_paths,
    _is_probe_stub_name,
    _scrub_probe_from_dest,
    _schedule_scrub_probe,
    _offer_empty_hdrop,
    _offer_probe_hdrop,
    _hwnd_looks_like_popup_menu,
    _context_menu_open,
    _double_click_ms,
    _cursor_xy,
    check_is_menu_query,
    _file_io_lock,
    _DUMMY_HDROP_PATH,
    _PROBE_STUB_NAME,
    _PROBE_STUB_DIR,
)
from filecopyhost import (
    FileCopyHostMixin,
    run_clipboard_agent_mode,
    CLIPBOARD_PIPE_NAME,
    _parse_files_pipe_payload,
    create_named_pipe_with_everyone_dacl,
    _low_il_everyone_sa,
    _create_user_signalable_event,
    _install_paste_ll_hooks,
)

if getattr(sys, "frozen", False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- NATIVE CLIPBOARD EVENT LISTENER ---
WM_CLIPBOARDUPDATE = 0x031D
HWND_MESSAGE = -3
_WM_RENDERFORMAT = 0x0305
_WM_RENDERALLFORMATS = 0x0306

# Định nghĩa các kiểu dữ liệu tương thích 64-bit để tránh lỗi OverflowError trên Windows 64-bit
WPARAM_64 = ctypes.c_size_t
LPARAM_64 = ctypes.c_ssize_t
LRESULT_64 = ctypes.c_ssize_t

try:
    WNDPROCTYPE = ctypes.WINFUNCTYPE(LRESULT_64, ctypes.c_void_p, ctypes.c_uint, WPARAM_64, LPARAM_64)
    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("style", ctypes.c_uint), ("lpfnWndProc", WNDPROCTYPE),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                    ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
                    ("hIconSm", ctypes.c_void_p)]
except:
    pass

# Khởi tạo trước thông số kiểu dữ liệu của DefWindowProcW để tránh lỗi trong quá trình tạo cửa sổ
try:
    ctypes.windll.user32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, WPARAM_64, LPARAM_64]
    ctypes.windll.user32.DefWindowProcW.restype = LRESULT_64
except:
    pass

class ClipboardEventListener:
    def __init__(self, callback, manager=None):
        self.callback = callback
        self.manager = manager
        self.hwnd = None
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.poll_thread = threading.Thread(target=self._mouse_poll_loop, daemon=True)
        self.poll_thread.start()

    def _mouse_poll_loop(self):
        user32 = ctypes.windll.user32
        while self.running:
            if user32.GetAsyncKeyState(0x01) & 0x8000:
                if self.manager:
                    now = time.time()
                    was = getattr(self.manager, "_lmb_held", False)
                    self.manager.last_lbutton_time = now
                    on_self = _cursor_over_current_process()
                    hit_menu = False
                    if not was:
                        prev_t = getattr(self.manager, "_prev_lbutton_time", 0.0)
                        px, py = getattr(self.manager, "_prev_lbutton_pos", (0, 0))
                        cx, cy = _cursor_xy()
                        if (now - prev_t) <= (_double_click_ms() / 1000.0) + 0.05 and abs(cx - px) <= 6 and abs(cy - py) <= 6:
                            self.manager.last_dblclick_time = now
                        self.manager._prev_lbutton_time = now
                        self.manager._prev_lbutton_pos = (cx, cy)
                        hit_menu = (not on_self) and _cursor_over_context_menu()
                        paste_from_menu = False
                        last_r = float(getattr(self.manager, "last_rbutton_time", 0) or 0)
                        age_r = now - last_r
                        if hit_menu:
                            self.manager._lmb_hit_context_menu = True
                            kind, name = _capture_menu_item_at_cursor()
                            self.manager._lmb_menu_item_kind = kind
                            # Win10: chữ Paste nếu đọc được; unknown trên #32768 sau RMB vẫn là RMP.
                            if _menu_item_counts_as_paste(kind) or (
                                (not _is_windows_11())
                                and kind != "not_paste"
                                and 0.12 < age_r < 8.0
                            ):
                                paste_from_menu = True
                                try:
                                    from utils.logger import clip_trace
                                    clip_trace(
                                        f"[LMB menu] profile={_shell_menu_profile()} "
                                        f"kind={kind!r} name={name!r} → paste gesture"
                                    )
                                except Exception:
                                    pass
                            else:
                                try:
                                    from utils.logger import clip_trace
                                    clip_trace(
                                        f"[LMB menu] profile={_shell_menu_profile()} "
                                        f"kind={kind!r} name={name!r} → not paste"
                                    )
                                except Exception:
                                    pass
                        else:
                            # Win11 XAML: hit-test menu thường fail — dùng near_rmb.
                            # Sau paste xong _clear_paste_gesture_flags xóa _rmb_cursor_pos
                            # → click đổi thư mục không còn bị nhận là Paste lần 2.
                            pend = getattr(self.manager, "pending_remote_files", None) or []
                            last_r = float(getattr(self.manager, "last_rbutton_time", 0) or 0)
                            age_r = now - last_r
                            rpos = getattr(self.manager, "_rmb_cursor_pos", None)
                            near_rmb = bool(
                                rpos
                                and abs(cx - rpos[0]) <= 360
                                and abs(cy - rpos[1]) <= 360
                            )
                            recent_dbl = bool(
                                getattr(self.manager, "last_dblclick_time", 0)
                                and (now - float(self.manager.last_dblclick_time)) < 0.7
                            )
                            menu_open = False
                            try:
                                menu_open = _context_menu_open()
                            except Exception:
                                menu_open = False
                            if menu_open:
                                self.manager._context_menu_seen_at = now
                            menu_seen = float(getattr(self.manager, "_context_menu_seen_at", 0) or 0)
                            menu_just_closed = bool(
                                menu_seen
                                and (now - menu_seen) < 0.7
                                and not menu_open
                            )
                            if (
                                (not on_self)
                                and _is_windows_11()
                                and pend
                                and 0.15 < age_r < 8.0
                                and not recent_dbl
                                and near_rmb
                                and (menu_open or menu_just_closed or near_rmb)
                            ):
                                paste_from_menu = True
                                self.manager._lmb_hit_context_menu = True
                                self.manager._lmb_menu_item_kind = "paste"
                                try:
                                    from utils.logger import clip_trace
                                    clip_trace(
                                        f"[LMB menu] win11 heuristic near_rmb={near_rmb} "
                                        f"menu_open={menu_open} just_closed={menu_just_closed} "
                                        f"age_r={age_r:.2f} → paste gesture"
                                    )
                                except Exception:
                                    pass
                            else:
                                # Click Explorer xa chỗ RMB / không phải Paste — xóa cờ cũ.
                                self.manager._lmb_hit_context_menu = False
                                self.manager._lmb_menu_item_kind = ""
                        if paste_from_menu:
                            if getattr(self.manager, "_conflict_ui_active", False):
                                try:
                                    from utils.logger import clip_trace
                                    clip_trace("[LMB menu] ignore paste gesture — conflict dialog open")
                                except Exception:
                                    pass
                            else:
                                self.manager.note_paste_gesture()
                                self.manager.snapshot_paste_dest("menu_paste")
                                try:
                                    self.manager._ensure_delayed_for_gesture()
                                except Exception:
                                    pass
                    self.manager._lmb_held = True
                    # Không EmptyClipboard / rearm delayed khi LMB thường — gây vòng BACKGROUND.
            else:
                if self.manager:
                    self.manager._lmb_held = False
            if user32.GetAsyncKeyState(0x02) & 0x8000:
                if self.manager:
                    was_rmb = getattr(self.manager, "_rmb_held", False)
                    self.manager.last_rbutton_time = time.time()
                    self.manager._lmb_hit_context_menu = False
                    self.manager._lmb_menu_item_kind = ""
                    self.manager._rmb_held = True
                    if not was_rmb:
                        try:
                            self.manager._rmb_cursor_pos = _cursor_xy()
                        except Exception:
                            self.manager._rmb_cursor_pos = None
                        # Chốt path sync trước khi Explorer mở clipboard vẽ menu Paste.
                        self.manager.snapshot_paste_dest("rmb", sync=True)
                        pend = getattr(self.manager, "pending_remote_files", None) or []
                        try:
                            from utils.logger import clip_trace
                            clip_trace(
                                f"[RMB] down pending_n={len(pend)} "
                                f"dummy_h={getattr(self.manager,'dummy_h_active',False)} "
                                f"profile={_shell_menu_profile()} "
                                f"snap={getattr(self.manager,'_paste_dest_snapshot',None)}"
                            )
                        except Exception:
                            pass
                        # Menu sắp mở — cần delayed CF_HDROP để Explorer bật Paste.
                        if pend or getattr(self.manager, "_hdrop_materialized", False) or getattr(
                            self.manager, "dummy_h_active", False
                        ):
                            try:
                                self.manager._ensure_delayed_for_gesture()
                            except Exception:
                                pass
            else:
                if self.manager:
                    self.manager._rmb_held = False
            # Poll nhanh hơn khi đang chờ Paste menu (Win11 race GetData).
            _sleep = 0.05
            try:
                if self.manager and (
                    getattr(self.manager, "pending_remote_files", None)
                    and (time.time() - float(getattr(self.manager, "last_rbutton_time", 0) or 0)) < 8.0
                ):
                    _sleep = 0.015
            except Exception:
                pass
            if user32.GetAsyncKeyState(0x0D) & 0x8000: # Enter
                if self.manager and not getattr(self.manager, "_enter_held", False):
                    self.manager._enter_held = True
                    if getattr(self.manager, "dummy_h_active", False) or getattr(
                        self.manager, "_hdrop_materialized", False
                    ):
                        try:
                            self.manager._ensure_delayed_for_gesture()
                        except Exception:
                            pass
            else:
                if self.manager:
                    self.manager._enter_held = False
            if user32.GetAsyncKeyState(0x1B) & 0x8000: # Esc
                pass  # đừng EmptyClipboard vì Esc — tránh vòng probe
            if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):
                if self.manager:
                    if not getattr(self.manager, "_ctrl_v_held", False):
                        self.manager.last_ctrl_v_time = time.time()
                        self.manager.note_paste_gesture()
                        self.manager.snapshot_paste_dest("ctrl_v")
                        try:
                            self.manager._ensure_delayed_for_gesture()
                        except Exception:
                            pass
                    self.manager._ctrl_v_held = True
            else:
                if self.manager:
                    self.manager._ctrl_v_held = False
            if (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000):
                if self.manager:
                    if not getattr(self.manager, "_shift_ins_held", False):
                        self.manager.last_ctrl_v_time = time.time()
                        self.manager.note_paste_gesture()
                        self.manager.snapshot_paste_dest("shift_ins")
                        try:
                            self.manager._ensure_delayed_for_gesture()
                        except Exception:
                            pass
                    self.manager._shift_ins_held = True
            else:
                if self.manager:
                    self.manager._shift_ins_held = False
            # Cùng file: gửi lại metadata đã cache — không GetClipboardData (Explorer chuột xoay).
            if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x43) & 0x8000):
                if self.manager:
                    now = time.time()
                    if now - getattr(self.manager, "_last_ctrl_c_time", 0) > 0.4:
                        self.manager._last_ctrl_c_time = now
                        m = self.manager
                        seq = get_clipboard_sequence_number()
                        last_seq = getattr(m, "_last_sent_file_seq", None)
                        cached = getattr(m, "last_current_files", None)
                        if cached and seq and seq == last_seq:
                            threading.Thread(
                                target=lambda: m._process_clipboard_change(
                                    provided_files=list(cached), force=True
                                ),
                                daemon=True,
                            ).start()
            time.sleep(_sleep)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        WM_CLIPBOARDUPDATE = 0x031D
        WM_RENDERFORMAT = 0x0305
        WM_DESTROYCLIPBOARD = 0x0307
        WM_SETUP_DELAYED_RENDERING = 0x0400 + 101
        WM_SET_CLIP_TEXT = 0x0400 + 102
        
        if msg == WM_CLIPBOARDUPDATE:
            log_debug(f"[WndProc] Nhận WM_CLIPBOARDUPDATE")
            self.callback()
            return 0
        elif msg == WM_RENDERFORMAT:
            log_debug(f"[WndProc] Nhận WM_RENDERFORMAT. wparam={wparam}")
            if wparam == 15: # CF_HDROP
                if self.manager:
                    self.manager.render_format(15)
                return 0
        elif msg == WM_DESTROYCLIPBOARD:
            log_debug(f"[WndProc] Nhận WM_DESTROYCLIPBOARD")
            if self.manager:
                self.manager.lost_ownership()
            return 0
        elif msg == WM_SETUP_DELAYED_RENDERING:
            log_debug(f"[WndProc] Nhận WM_SETUP_DELAYED_RENDERING. Đang tiến hành thiết lập delayed rendering...")
            if self.manager:
                self.manager._execute_setup_delayed_rendering()
            return 0
        elif msg == WM_SET_CLIP_TEXT:
            if self.manager:
                self.manager.apply_pending_clip_text_on_listener(hwnd)
            return 0
            
        try:
            return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        except:
            return 0

    def _run(self):
        try:
            log_debug("[Listener] Bắt đầu thread đăng ký Clipboard listener.")
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            # Định nghĩa types cho GetModuleHandleW trước khi gọi
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p
            h_mod = kernel32.GetModuleHandleW(None)
            
            # Không còn dùng Low-level Mouse Hook (WH_MOUSE_LL) để tránh lag chuột toàn hệ thống

            user32.CreateWindowExW.argtypes = [
                ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
                ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
            ]
            user32.CreateWindowExW.restype = ctypes.c_void_p
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p

            wndproc = WNDPROCTYPE(self._wndproc)
            self.wndproc_ref = wndproc  # Giữ reference để tránh bị garbage collected
            wndclass = WNDCLASSEX()
            wndclass.cbSize = ctypes.sizeof(WNDCLASSEX)
            wndclass.lpfnWndProc = wndproc
            wndclass.lpszClassName = "HiddenClipboardListener"
            wndclass.hInstance = kernel32.GetModuleHandleW(None)
            
            reg_res = user32.RegisterClassExW(ctypes.byref(wndclass))
            log_debug(f"[Listener] RegisterClassExW trả về: {reg_res}")
            
            # Cửa sổ ẩn thật (không HWND_MESSAGE): message-only thường không nhận WM_CLIPBOARDUPDATE.
            self.hwnd = user32.CreateWindowExW(0, wndclass.lpszClassName, "HiddenWindow", 0, 0, 0, 0, 0, None, None, wndclass.hInstance, None)
            log_debug(f"[Listener] CreateWindowExW trả về HWND: {self.hwnd}")
            
            try:
                WM_CLIPBOARDUPDATE = 0x031D
                WM_RENDERFORMAT = 0x0305
                WM_DESTROYCLIPBOARD = 0x0307
                MSGFLT_ALLOW = 1
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_CLIPBOARDUPDATE, MSGFLT_ALLOW, None)
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_RENDERFORMAT, MSGFLT_ALLOW, None)
                user32.ChangeWindowMessageFilterEx(ctypes.c_void_p(self.hwnd), WM_DESTROYCLIPBOARD, MSGFLT_ALLOW, None)
                log_debug("[Listener] ChangeWindowMessageFilterEx thành công.")
            except Exception as e:
                log_debug(f"[Listener] ChangeWindowMessageFilterEx thất bại: {e}")

            add_res = user32.AddClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            log_debug(f"[Listener] AddClipboardFormatListener trả về: {add_res}")
            
            EVENT_SYSTEM_FOREGROUND = 0x0003
            WINEVENT_OUTOFCONTEXT = 0x0000
            WINEVENTPROC = ctypes.WINFUNCTYPE(
                None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD
            )
            
            def wineventproc(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
                if event == EVENT_SYSTEM_FOREGROUND:
                    if self.manager and hasattr(self.manager, 'on_foreground_changed'):
                        self.manager.on_foreground_changed(hwnd)

            self.wineventproc_c = WINEVENTPROC(wineventproc)
            hook = user32.SetWinEventHook(
                EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
                None, self.wineventproc_c, 0, 0, WINEVENT_OUTOFCONTEXT
            )
            # Không cài WH_KEYBOARD_LL / WH_MOUSE_LL trên viewer/client:
            # hook nằm cùng thread GetMessage (OpenClipboard/RENDERFORMAT) sẽ treo chuột+phím
            # cả máy local (vd. F2 đổi tên trong Explorer). Agent host vẫn cài LL hook riêng.

            msg = wintypes.MSG()
            while self.running and user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
                
            user32.RemoveClipboardFormatListener(ctypes.c_void_p(self.hwnd))
            user32.DestroyWindow(ctypes.c_void_p(self.hwnd))
            user32.UnregisterClassW(wndclass.lpszClassName, wndclass.hInstance)
        except Exception as e:
            print("[ClipboardEvent] Lỗi Listener:", e)

    def stop(self):
        self.running = False
        if self.hwnd:
            try: ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.hwnd), 0, 0, 0)
            except: pass

# Đường dẫn thư mục lưu file chuyển từ Client (dùng cho headless/SYSTEM mode)

class ClipboardSyncManager(ClipboardTextMixin, FileCopyClientMixin, FileCopyHostMixin):
    def __init__(self):
        import queue
        self.gui_queue = queue.Queue()
        self.last_files = []
        self.last_files_time = 0
        self.active_sockets = set()
        self.transfer_in_progress = False
        self.lock = threading.Lock()
        self.transfer_done_event = threading.Event()
        self.overwrite_event = threading.Event()
        self.overwrite_choice = None
        self.last_rbutton_time = 0
        self.last_lbutton_time = 0
        self.last_ctrl_v_time = 0
        self._lmb_hit_context_menu = False
        self._lmb_menu_item_kind = ""
        self._paste_gesture_id = 0
        self._consumed_paste_gesture_id = 0
        self._paste_gesture_inc_at = 0.0
        self._lmb_held = False
        self._prev_lbutton_time = 0.0
        self._prev_lbutton_pos = (0, 0)
        self.last_dblclick_time = 0.0
        if ENABLE_CLIPBOARD_SYNC:
            self.listener = ClipboardEventListener(self.on_clipboard_changed, self)
        else:
            self.listener = None
        self.incoming_transfers = {}
        self.app = None
        self.active_dialog = None
        self.batch_received = 0
        self.batch_total_size = 0
        self.batch_paths = []
        self.ignore_destroy_clipboard = False
        
        self.pending_remote_files = []
        self.sock = None
        self.target_save_dir = ""
        self.is_paste_triggered = False
        self.meta_arrival_time = 0
        self.last_sent_text = ""
        self.last_received_text = ""
        self._pending_set_text = None
        self._down_pipe_q = queue.Queue()
        self._down_pipe_started = False
        self._delayed_setup_tries = 0
        self._allow_delayed = True
        self._force_delayed_setup = False
        self._clip_seq_at_pending = None
        self._last_sent_clip_seq = 0
        self._send_cancelled = False
        self._receive_cancelled = False
        self._send_abort_event = threading.Event()
        self._send_xfer_id = 0
        self._recv_xfer_id = None
        self._aborted_xfer_ids = set()
        self.overwrite_all = False
        
        self.cached_explorer_path = None
        self._paste_dest_snapshot = None
        self._last_good_explorer_path = None
        self._paste_dest_frozen = False
        self._xfer_dest_by_paste_id = {}
        self._rmb_held = False
        self.dummy_h_active = False
        self._recv_dialog_open = False
        self._reoffer_files = None
        self._rearm_delayed_after_render = False
        self._suppress_render_until = 0.0
        self._expect_repaste_until = 0.0
        self._last_sent_file_seq = None
        self._last_sent_file_fp = None
        self._clip_resync = False
        self._clip_sync_gen = 0
        self._clip_offer_id = 0
        self._clip_offer_in = 0
        self._clip_offer_applied = 0
        self._clip_offer_q = []
        self._clip_offer_lock = threading.Lock()
        self._clip_offer_evt = threading.Event()
        self._clip_offer_worker = threading.Thread(
            target=self._clip_offer_loop, daemon=True, name="ClipOfferQ"
        )
        self._clip_offer_worker.start()
        self._last_ctrl_c_time = 0.0
        self._paste_dest_dir = None
        self._partial_output_paths = []
        self._gui_poll_gen = 0
        self._clipboard_paste_id = 0
        self._cancel_gen = 0
        self._suppress_request_files_until = 0.0
        self._allow_file_xfer = False
        self._xfer_cancel_token = 0
        self._xfer_cancel_at = 0.0
        self._ctrl_v_held = False
        self._shift_ins_held = False
        self._cancelled_paste_ids = set()
        self._active_send_ids = set()
        self._aborted_send_ids = set()
        self._send_id_by_paste = {}
        self._xfer_jobs = {}
        self.xfer_dialogs = {}
        self._xfer_expected_files = {}
        self._paste_done = {}          # paste_id -> Event (chờ batch_end theo từng Paste)
        self._paste_result_paths = {}  # paste_id -> paths khi xong
        self._fm_send_abort = threading.Event()
        self._last_cancel_ack_time = 0.0
        self._pkt_queue = queue.Queue()
        self._pkt_worker = threading.Thread(target=self._packet_loop, daemon=True, name="ClipPkt")
        self._pkt_worker.start()
        self._send_job_q = queue.Queue()
        self._send_worker_started = False
        self._send_worker_boot_lock = threading.Lock()
        self._send_run_lock = threading.Lock()  # FIFO: một lúc chỉ một batch gửi client→host
        self._send_sem = threading.Semaphore(1)
        self._xfer_need_resync = False
        self._resume_waiters = {}
        self._xfer_sock_gen = 0
        self.cacher_thread = threading.Thread(target=self._explorer_path_cacher_loop, daemon=True)
        self.cacher_thread.start()
        threading.Thread(target=self._xfer_watchdog_loop, daemon=True, name="ClipXferWatch").start()
        
        # Named Pipe handle cho headless mode (giao tiếp với Clipboard Agent)
        self._pipe_handle = None
        self._pipe_lock = threading.Lock()
        
        try:
            from utils.logger import clip_trace
            clip_trace("[ClipboardSyncManager] init — paste host→client tracing ON (clipboard_agent.log)")
        except Exception:
            pass

        # Không cần luồng theo dõi paste vì dùng delayed rendering thực tế
        pass

    def enqueue_packet(self, packet):
        """Nhận packet clipboard/file ngoài luồng input — tránh kẹt chuột viewer khi ghi pipe/file."""
        try:
            self._pkt_queue.put(packet)
        except Exception:
            pass

    def _packet_loop(self):
        while True:
            try:
                packet = self._pkt_queue.get()
            except Exception:
                continue
            if packet is None:
                break
            try:
                self.handle_received_packet(packet)
            except Exception as e:
                print(f"[Clipboard] Packet worker: {e}")

    def register_app(self, app):
        self.app = app
        self.cached_app_hwnd = None
        if not getattr(self.app, 'is_headless', False):
            try: self.cached_app_hwnd = self.app.winfo_id()
            except: pass
        self._gui_poll_gen = getattr(self, "_gui_poll_gen", 0) + 1
        self.poll_gui_queue(self._gui_poll_gen)
        if getattr(self.app, 'is_headless', False):
            if not getattr(self, "_uppipe_started", False):
                self._uppipe_started = True
                threading.Thread(target=self._cancel_listener_thread, daemon=True).start()
                threading.Thread(target=self._start_uppipe_server, daemon=True).start()
                threading.Thread(target=self._host_text_poll_loop, daemon=True, name="HostClipPoll").start()
            self._ensure_down_pipe()

    def _cancel_listener_thread(self):
        import win32event
        try:
            h_event = _create_user_signalable_event(r"Global\AntigravityP2P_CancelTransfer_Event")
        except Exception as e:
            log_debug(f"[_cancel_listener_thread] Lỗi tạo Event: {e}")
            return
            
        log_debug("[_cancel_listener_thread] Bắt đầu lắng nghe Global\\AntigravityP2P_CancelTransfer_Event...")
        print("[Clipboard] Cancel event listener da bat.")
        while True:
            rc = win32event.WaitForSingleObject(h_event, win32event.INFINITE)
            if rc == win32event.WAIT_OBJECT_0:
                log_debug("[_cancel_listener_thread] Nhận tín hiệu hủy truyền tải từ Agent.")
                print("[Clipboard] Nhan event Huy tu Agent.")
                try:
                    self.cancel_active_transfer(remote_triggered=False)
                except Exception as e:
                    print(f"[Clipboard] cancel_active_transfer loi: {e}")
                try:
                    win32event.ResetEvent(h_event)
                except Exception:
                    pass
                time.sleep(0.05)

    def poll_gui_queue(self, gen=None):
        if not self.app:
            return
        if gen is None:
            gen = getattr(self, "_gui_poll_gen", 0)
        if gen != getattr(self, "_gui_poll_gen", 0):
            return
        self.process_gui_queue()
        try:
            self.app.after(50, lambda g=gen: self.poll_gui_queue(g))
        except Exception:
            pass

    def process_gui_queue(self):
        if self.app and getattr(self.app, 'is_headless', False):
            import queue
            while not self.gui_queue.empty():
                try: self.gui_queue.get_nowait()
                except queue.Empty: break
            return
        import queue
        while not self.gui_queue.empty():
            try:
                action, args = self.gui_queue.get_nowait()
                if action == "create":
                    title_text, filename, total_size = args[0], args[1], args[2]
                    dest_dir = args[3] if len(args) > 3 else None
                    reserve_finalize = args[4] if len(args) > 4 else False
                    job_id = args[5] if len(args) > 5 else None
                    item_kind = args[6] if len(args) > 6 else "file"
                    dialogs = getattr(self, "xfer_dialogs", None)
                    if dialogs is None:
                        self.xfer_dialogs = {}
                        dialogs = self.xfer_dialogs
                    owner_hwnd = getattr(self, "pygame_hwnd", None)
                    if not owner_hwnd and self.app:
                        try:
                            owner_hwnd = int(self.app.winfo_id())
                        except Exception:
                            owner_hwnd = None
                    stack = len([d for d in dialogs.values() if d])
                    jid = job_id if job_id is not None else ("j%d" % (stack + 1))
                    if dialogs.get(jid):
                        continue
                    dlg = ProgressDialog(
                        self.app, title_text, filename, total_size,
                        on_cancel=lambda j=jid: self.cancel_active_transfer(remote_triggered=False, paste_id=j, all_jobs=False),
                        owner_hwnd=owner_hwnd,
                        dest_dir=dest_dir,
                        reserve_finalize=reserve_finalize,
                        stack_index=stack,
                        job_id=jid,
                        item_kind=item_kind,
                    )
                    dialogs[jid] = dlg
                    self.active_dialog = dlg
                elif action == "finalize_start":
                    dlg = self._dialog_by_job(args[1] if isinstance(args, (tuple, list)) and len(args) > 1 else None)
                    if dlg:
                        try: dlg.begin_finalize((args[0] if isinstance(args, (tuple, list)) else args) or 0)
                        except: pass
                elif action == "finalize_progress":
                    dlg = self._dialog_by_job(args[1] if isinstance(args, (tuple, list)) and len(args) > 1 else None)
                    if dlg:
                        try: dlg.add_finalize_bytes((args[0] if isinstance(args, (tuple, list)) else args) or 0)
                        except: pass
                elif action == "complete":
                    dlg = self._dialog_by_job(args if not isinstance(args, (tuple, list)) else (args[0] if args else None))
                    if dlg:
                        try: dlg.mark_complete()
                        except: pass
                elif action == "update":
                    if isinstance(args, (tuple, list)):
                        sent_bytes, job_id = args[0], (args[1] if len(args) > 1 else None)
                    else:
                        sent_bytes, job_id = args, None
                    dlg = self._dialog_by_job(job_id)
                    if dlg:
                        try: dlg.update_progress(sent_bytes)
                        except: pass
                elif action == "status":
                    if isinstance(args, (tuple, list)):
                        status, job_id = args[0], (args[1] if len(args) > 1 else None)
                    else:
                        status, job_id = args, None
                    dlg = self._dialog_by_job(job_id)
                    if dlg:
                        try:
                            dlg.update_progress(getattr(dlg, "_received", 0), status=status)
                        except Exception:
                            pass
                elif action == "destroy":
                    job_id = args
                    def _do_destroy(j=job_id):
                        dialogs = getattr(self, "xfer_dialogs", None) or {}
                        targets = []
                        if j is None:
                            targets = list(dialogs.items())
                        elif j in dialogs:
                            targets = [(j, dialogs.get(j))]
                        else:
                            targets = []
                        for k, dlg in targets:
                            try:
                                if dlg:
                                    dlg.on_cancel = None
                                    dlg.destroy()
                            except: pass
                            dialogs.pop(k, None)
                        self.active_dialog = next(iter(dialogs.values()), None) if dialogs else None
                    self.app.after(0, _do_destroy)
                elif action == "classic_overwrite_dialog":
                    filename, source_info, dest_info, has_multiple = args
                    finished = {"done": False}

                    def _finish_overwrite(choice, _f=finished):
                        if _f["done"]:
                            return
                        _f["done"] = True
                        self.overwrite_choice = choice if choice else "cancel"
                        try:
                            # var_all đọc trước destroy nếu còn dialog
                            pass
                        except Exception:
                            pass
                        self._conflict_ui_active = False
                        self.overwrite_event.set()

                    def _on_done(choice, _f=finished):
                        try:
                            # ClassicCopyDialog gọi on_done trước destroy
                            dlg = getattr(self, "_active_overwrite_dialog", None)
                            if dlg is not None and hasattr(dlg, "var_all"):
                                self.overwrite_all = bool(dlg.var_all.get())
                            else:
                                self.overwrite_all = False
                        except Exception:
                            self.overwrite_all = False
                        _finish_overwrite(choice)

                    owner_hwnd = getattr(self, "pygame_hwnd", None)
                    if not owner_hwnd and self.app:
                        try:
                            owner_hwnd = int(self.app.winfo_id())
                        except Exception:
                            owner_hwnd = None
                    dialog = ClassicCopyDialog(
                        self.app, filename, source_info, dest_info, has_multiple,
                        on_done=_on_done, owner_hwnd=owner_hwnd,
                    )
                    self._active_overwrite_dialog = dialog
                    self._conflict_ui_active = True

                    def _on_destroy(event, _f=finished):
                        if event.widget == dialog:
                            try:
                                if hasattr(dialog, "var_all") and not _f["done"]:
                                    self.overwrite_all = bool(dialog.var_all.get())
                            except Exception:
                                pass
                            self._active_overwrite_dialog = None
                            _finish_overwrite(dialog.choice if dialog.choice else "cancel")

                    dialog.bind("<Destroy>", _on_destroy)
            except queue.Empty:
                break
            except Exception as e:
                log_debug(f"[process_gui_queue] Lỗi: {e}")

    def add_socket(self, sock):
        if not ENABLE_CLIPBOARD_SYNC: return
        with self.lock:
            self.active_sockets.add(sock)
            self.sock = sock
            self._xfer_sock_gen = getattr(self, "_xfer_sock_gen", 0) + 1
        try:
            role = "HOST_HEADLESS" if (self.app and getattr(self.app, "is_headless", False)) else "CLIENT"
            log_overwrite_conflict(
                f"{role} add_socket ok n_socks={len(self.active_sockets)} "
                f"(tu day moi nhan/gui files_copied_meta)"
            )
        except Exception:
            pass

    def remove_socket(self, sock):
        if not ENABLE_CLIPBOARD_SYNC: return
        with self.lock:
            if sock in self.active_sockets:
                self.active_sockets.remove(sock)
            if self.sock == sock:
                self.sock = list(self.active_sockets)[0] if self.active_sockets else None
            # Also clean up socket passwords
            socket_passwords.pop(sock, None)
        try:
            role = "HOST_HEADLESS" if (self.app and getattr(self.app, "is_headless", False)) else "CLIENT"
            log_overwrite_conflict(
                f"{role} remove_socket n_socks={len(getattr(self, 'active_sockets', []) or [])}"
            )
        except Exception:
            pass

    def _dialog_by_job(self, job_id=None):
        dialogs = getattr(self, "xfer_dialogs", None) or {}
        if job_id is not None:
            return dialogs.get(job_id)
        return self.active_dialog

    def note_paste_gesture(self):
        # Đang hiện dialog ghi đè — click vào dialog không được tính là Paste mới.
        if getattr(self, "_conflict_ui_active", False):
            return
        now = time.time()
        if now - getattr(self, "_paste_gesture_inc_at", 0) < 0.08:
            return
        self._paste_gesture_inc_at = now
        self._paste_gesture_id = getattr(self, "_paste_gesture_id", 0) + 1

    def _clear_paste_gesture_flags(self, suppress_s=1.0):
        """Sau paste xong / Hủy: đừng để click Explorer bị nhận là Paste lần 2."""
        self._lmb_hit_context_menu = False
        self._lmb_menu_item_kind = ""
        self._rmb_cursor_pos = None
        self._context_menu_seen_at = 0.0
        self._consumed_paste_gesture_id = getattr(self, "_paste_gesture_id", 0)
        if suppress_s > 0:
            self._suppress_render_until = max(
                getattr(self, "_suppress_render_until", 0),
                time.time() + float(suppress_s),
            )

    def open_paste_progress_dialog(self, filename, total_size, dest_dir=None, reserve_finalize=True, job_id=None, item_kind="file"):
        """Một lần Paste (job_id) → tối đa một dialog tiến trình."""
        if self.app and getattr(self.app, "is_headless", False):
            return
        dialogs = getattr(self, "xfer_dialogs", None)
        if dialogs is None:
            self.xfer_dialogs = {}
            dialogs = self.xfer_dialogs
        if job_id is not None and dialogs.get(job_id):
            return
        self._recv_dialog_open = True
        self.gui_queue.put((
            "create",
            (file_download_dialog_title(), filename, total_size, dest_dir, reserve_finalize, job_id, item_kind),
        ))

    def show_dialog(self, title_text, filename, total_size, dest_dir=None, reserve_finalize=False, job_id=None, item_kind="file"):
        self.open_paste_progress_dialog(filename, total_size, dest_dir, reserve_finalize, job_id, item_kind)

    def update_dialog(self, sent_bytes, job_id=None):
        import time
        current_time = time.time()
        times = getattr(self, "_last_update_times", None)
        if times is None:
            self._last_update_times = {}
            times = self._last_update_times
        key = job_id if job_id is not None else "_default"
        last = times.get(key, 0)
        if current_time - last >= 0.05:
            self.gui_queue.put(("update", (sent_bytes, job_id)))
            times[key] = current_time

    def close_dialog(self, job_id=None, reason=None):
        if reason:
            print(f"[Clipboard] Dong dialog job_id={job_id} ly_do={reason}")
        if job_id is None:
            self._recv_dialog_open = False
        self.gui_queue.put(("destroy", job_id))

    def begin_dialog_finalize(self, total_bytes=0, job_id=None):
        self.gui_queue.put(("finalize_start", (total_bytes, job_id)))

    def add_dialog_finalize(self, n, job_id=None):
        self.gui_queue.put(("finalize_progress", (n, job_id)))

    def complete_dialog(self, job_id=None):
        self.gui_queue.put(("complete", job_id))

    def _coerce_paste_id(self, val):
        if val is None or val is False or val is True:
            return None
        try:
            return int(val)
        except Exception:
            return None

    def _other_xfer_jobs_remain(self, tok):
        jobs = getattr(self, "_xfer_jobs", None) or {}
        for xid, job in jobs.items():
            try:
                pid = int(job.get("paste_id") or 0)
            except Exception:
                pid = 0
            if pid != tok and xid != tok:
                return True
        return False

    def _note_cancelled_paste_id(self, tok):
        try:
            tok = int(tok)
        except Exception:
            return
        if not tok:
            return
        ids = getattr(self, "_cancelled_paste_ids", None)
        if ids is None:
            self._cancelled_paste_ids = set()
            ids = self._cancelled_paste_ids
        ids.add(tok)
        if len(ids) > 64:
            self._cancelled_paste_ids = set(sorted(ids)[-32:])

    def _arm_file_xfer(self, reason=""):
        """Cho phép gửi/nhận file. Paste mới không hủy phiên đang chạy."""
        tok = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        if tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
            print(f"[FileTransfer] Khong arm — paste_id={tok} nam trong blacklist Huy.")
            return False
        self._send_xfer_id = getattr(self, "_send_xfer_id", 0) + 1
        sid = self._send_xfer_id
        ids = getattr(self, "_active_send_ids", None)
        if ids is None:
            self._active_send_ids = set()
            ids = self._active_send_ids
        ids.add(sid)
        mp = getattr(self, "_send_id_by_paste", None)
        if mp is None:
            self._send_id_by_paste = {}
            mp = self._send_id_by_paste
        if tok:
            mp.setdefault(tok, set()).add(sid)
        self._allow_file_xfer = True
        self._send_cancelled = False
        self._receive_cancelled = False
        try:
            if not ids or len(ids) <= 1:
                self._send_abort_event.clear()
        except Exception:
            pass
        self._send_loop_gen = getattr(self, "_cancel_gen", 0)
        self._suppress_request_files_until = 0.0
        print(f"[FileTransfer] Arm xfer ({reason}) id={sid} paste_id={tok} active={list(ids)}")
        return True

    def _disarm_file_xfer(self, reason="", cancelled_paste_id=None, all_jobs=False):
        """Hủy một paste_id, hoặc mọi phiên nếu all_jobs."""
        tok = self._coerce_paste_id(cancelled_paste_id)
        if tok is None:
            tok = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        self._xfer_cancel_token = tok
        if tok:
            self._note_cancelled_paste_id(tok)
        abort_ids = set()
        mp = getattr(self, "_send_id_by_paste", None) or {}
        if all_jobs:
            abort_ids = set(getattr(self, "_active_send_ids", None) or [])
        else:
            abort_ids = set(mp.get(tok) or [])
        aborted = getattr(self, "_aborted_send_ids", None)
        if aborted is None:
            self._aborted_send_ids = set()
            aborted = self._aborted_send_ids
        aborted.update(abort_ids)
        active = getattr(self, "_active_send_ids", None)
        if active is None:
            self._active_send_ids = set()
            active = self._active_send_ids
        active.difference_update(abort_ids)
        for t, sids in list(mp.items()):
            sids.difference_update(abort_ids)
            if not sids:
                mp.pop(t, None)
        still = bool(active) or (not all_jobs and self._other_xfer_jobs_remain(tok))
        if not still:
            self._allow_file_xfer = False
            self._send_cancelled = True
            self._receive_cancelled = True
            try:
                self._send_abort_event.set()
            except Exception:
                pass
            try:
                self._fm_send_abort.set()
            except Exception:
                pass
            self._cancel_gen = getattr(self, "_cancel_gen", 0) + 1
        print(f"[FileTransfer] Disarm ({reason}) token={tok} abort={list(abort_ids)} remain={list(active)}")

    def _send_should_stop(self, my_id):
        if my_id in (getattr(self, "_aborted_send_ids", None) or set()):
            return True
        active = getattr(self, "_active_send_ids", None)
        if active is not None and my_id not in active:
            return True
        return False

    def _cleanup_partial_incoming(self):
        """Đóng handle và xóa file dở (cancel / drain stale) — tránh .exe nửa file + lá chắn UAC."""
        extra = []
        for filename, transfer in list(getattr(self, "incoming_transfers", {}) or {}).items():
            if transfer.get("handle"):
                try:
                    transfer["handle"].close()
                except Exception:
                    pass
            path = transfer.get("path")
            if path:
                # Chỉ xóa path tạm / stub — không đụng file đã promote ra thư mục đích.
                if (
                    _path_in_xfer_staging(path)
                    or _is_probe_stub_name(path)
                    or _is_transfer_junk_at_dest(path)
                ):
                    extra.append(path)
                    if _retry_remove_path(path):
                        print(f"[FileTransfer] Đã xóa file dở dang: {path}")
                else:
                    extra.append(path)  # vẫn đưa vào cleanup_incomplete (nó sẽ bỏ qua file hoàn chỉnh)
        self.incoming_transfers = {}

        if hasattr(self, "batch_paths") and self.batch_paths:
            # Chỉ dọn path tạm — batch_paths sau Paste thường đã trỏ vào thư mục đích.
            for p in list(self.batch_paths):
                if not p:
                    continue
                if _path_in_xfer_staging(p) or _is_probe_stub_name(p) or _is_transfer_junk_at_dest(p):
                    extra.append(p)
            self.batch_paths = []

        for p in list(getattr(self, "_partial_output_paths", None) or []):
            if not p:
                continue
            if _path_in_xfer_staging(p) or _is_probe_stub_name(p) or _is_transfer_junk_at_dest(p):
                extra.append(p)
        self._partial_output_paths = []

        saved = list(getattr(self, "pending_remote_files", None) or getattr(self, "_reoffer_files", None) or [])
        dests = [
            getattr(self, "target_save_dir", None),
            getattr(self, "_paste_dest_dir", None),
            getattr(self, "cached_explorer_path", None),
            HEADLESS_TRANSFER_DIR,
            os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"),
            _PROBE_STUB_DIR,
        ]
        cleanup_incomplete_named_files(dests, saved, extra_paths=extra)

    def _cleanup_incoming_for_xids(self, abort_xids):
        abort_xids = set(x for x in (abort_xids or []) if x is not None)
        if not abort_xids:
            return
        extra = []
        for key, transfer in list((getattr(self, "incoming_transfers", None) or {}).items()):
            if transfer.get("xfer_id") not in abort_xids:
                continue
            if transfer.get("handle"):
                try:
                    transfer["handle"].close()
                except Exception:
                    pass
            path = transfer.get("path")
            if path:
                extra.append(path)
                _retry_remove_path(path)
            self.incoming_transfers.pop(key, None)
        dests = [
            getattr(self, "_paste_dest_dir", None),
            getattr(self, "cached_explorer_path", None),
            getattr(self, "target_save_dir", None),
            HEADLESS_TRANSFER_DIR,
            os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"),
            _PROBE_STUB_DIR,
        ]
        cleanup_incomplete_named_files(
            dests, [], extra_paths=extra, staging_xids=abort_xids, wipe_all_staging=False
        )

    def _live_xfer_sock(self):
        sock = getattr(self, "sock", None)
        if sock is not None:
            return sock
        try:
            socks = list(self.active_sockets or [])
            if socks:
                return socks[0]
        except Exception:
            pass
        return None

    def _xfer_dialog_status(self, my_id, status):
        jobs = getattr(self, "_xfer_jobs", None) or {}
        job = jobs.get(my_id)
        try:
            pid = int((job or {}).get("paste_id") or getattr(self, "_clipboard_paste_id", 0) or 0)
        except Exception:
            pid = 0
        try:
            self.gui_queue.put(("status", (status, pid or my_id)))
        except Exception:
            pass

    def _xfer_watchdog_loop(self):
        """Khi không nhận chunk > 3s (mạng đứt), đổi tiêu đề dialog sang đang thử lại."""
        while True:
            time.sleep(1.0)
            try:
                jobs = getattr(self, "_xfer_jobs", None) or {}
                now = time.time()
                for xid, job in list(jobs.items()):
                    rec = int(job.get("received") or 0)
                    total = int(job.get("total") or 0)
                    if total and rec >= total:
                        continue
                    last = float(job.get("last_chunk_at") or 0)
                    if not last:
                        continue
                    waiting = (now - last) > 3.0
                    if waiting and not job.get("retry_ui"):
                        job["retry_ui"] = True
                        self._xfer_dialog_status(xid, _("Đang thử kết nối lại, tiếp tục tải..."))
                    elif (not waiting) and job.get("retry_ui"):
                        job["retry_ui"] = False
                        self._xfer_dialog_status(xid, file_download_dialog_title())
            except Exception:
                pass

    def _send_file_msg(self, sock, data_bytes, my_id):
        """Gửi gói file; nếu mạng đứt thì chờ socket mới rồi gửi lại cùng gói (chunk có offset nên an toàn)."""
        if not getattr(self, "_allow_file_xfer", False) or self._send_should_stop(my_id):
            return False
        waiting = False
        last_log = 0.0
        sock_gen = getattr(self, "_xfer_sock_gen", 0)
        while True:
            if self._send_should_stop(my_id):
                return False
            live = self._live_xfer_sock() or sock
            if live:
                if send_msg(live, data_bytes):
                    if waiting or getattr(self, "_xfer_sock_gen", 0) != sock_gen:
                        self._xfer_need_resync = True
                        if waiting:
                            print("[FileTransfer] Resume gui sau khi ket noi lai.")
                    return True
            now = time.time()
            if not waiting:
                waiting = True
                print("[FileTransfer] Mat ket noi luc gui — cho reconnect de resume...")
            elif now - last_log > 5.0:
                last_log = now
                print("[FileTransfer] Van cho ket noi lai de resume...")
            time.sleep(0.35)

    def _query_resume_state(self, my_id, paste_id, timeout=8.0):
        """Hỏi máy nhận đã ghi bao nhiêu byte từng file — để seek tiếp, không gửi lại từ đầu."""
        ev = threading.Event()
        box = {"state": {}}
        waiters = getattr(self, "_resume_waiters", None)
        if waiters is None:
            self._resume_waiters = {}
            waiters = self._resume_waiters
        waiters[my_id] = (ev, box)
        pkt = json.dumps({
            "type": "resume_query",
            "xfer_id": my_id,
            "paste_id": paste_id,
        }).encode("utf-8")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._send_should_stop(my_id):
                break
            live = self._live_xfer_sock()
            if live:
                try:
                    send_msg(live, pkt)
                except Exception:
                    pass
                if ev.wait(1.2):
                    break
            else:
                time.sleep(0.3)
        waiters.pop(my_id, None)
        return box.get("state") or {}

    def _resume_snapshot(self, xid):
        files = {}
        for t in (getattr(self, "incoming_transfers", None) or {}).values():
            if t.get("xfer_id") != xid:
                continue
            name = t.get("name")
            written = int(t.get("written") or 0)
            handle = t.get("handle")
            if handle is not None:
                try:
                    handle.flush()
                    written = int(handle.tell())
                    t["written"] = written
                except Exception:
                    pass
            if name:
                files[str(name).replace("\\", "/")] = written
        job = (getattr(self, "_xfer_jobs", None) or {}).get(xid)
        if job:
            stg = _xfer_staging_dir(job.get("save_dir") or HEADLESS_TRANSFER_DIR, xid)
            if os.path.isdir(stg):
                for root, _dirs, fnames in os.walk(stg):
                    for fn in fnames:
                        full = os.path.join(root, fn)
                        rel = os.path.relpath(full, stg).replace("\\", "/")
                        try:
                            sz = os.path.getsize(full)
                        except Exception:
                            continue
                        files[rel] = max(int(files.get(rel) or 0), int(sz))
        return {
            "type": "resume_state",
            "xfer_id": xid,
            "has_job": job is not None,
            "files": files,
            "received": int((job or {}).get("received") or 0),
        }

    def _maybe_send_cancel_ack(self):
        """Báo máy gửi dừng vòng chunk; máy nhận vẫn recv/drain socket."""
        now = time.time()
        if now - getattr(self, "_last_cancel_ack_time", 0) < 0.15:
            return
        self._last_cancel_ack_time = now
        sock = getattr(self, "sock", None)
        if not sock:
            return
        try:
            send_msg(
                sock,
                json.dumps({
                    "type": "cancel_ack",
                    "paste_id": int(getattr(self, "_xfer_cancel_token", 0) or getattr(self, "_clipboard_paste_id", 0) or 0),
                }).encode("utf-8"),
                lock_timeout=0.05,
            )
        except Exception:
            pass

    def cancel_active_transfer(self, remote_triggered=False, paste_id=None, all_jobs=None):
        cur = self._coerce_paste_id(paste_id)
        if all_jobs is None:
            all_jobs = cur is None
        if cur is None:
            cur = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        if cur:
            self._note_cancelled_paste_id(cur)
        self._disarm_file_xfer("Huy", cancelled_paste_id=cur, all_jobs=all_jobs)
        self._maybe_send_cancel_ack()
        if all_jobs:
            self._suppress_request_files_until = time.time() + 8.0
            self._suppress_render_until = max(getattr(self, "_suppress_render_until", 0), time.time() + 1.5)
            self._xfer_cancel_at = time.time()
            self.last_ctrl_v_time = 0.0
            self._ctrl_v_held = False
        print(f"[FileTransfer] Huy paste_id={cur} all={all_jobs}")
        jobs = getattr(self, "_xfer_jobs", None) or {}
        abort_xids = []
        if all_jobs:
            abort_xids = list(jobs.keys())
        else:
            for xid, job in list(jobs.items()):
                try:
                    jpid = int(job.get("paste_id") or 0)
                except Exception:
                    jpid = 0
                if jpid and jpid == cur:
                    abort_xids.append(xid)
                elif not jpid and xid == cur:
                    abort_xids.append(xid)
        aborted = getattr(self, "_aborted_xfer_ids", None)
        if aborted is None:
            self._aborted_xfer_ids = set()
            aborted = self._aborted_xfer_ids
        for xid in abort_xids:
            aborted.add(xid)
            jobs.pop(xid, None)
        self._cleanup_incoming_for_xids(abort_xids)
        
        try:
            if hasattr(self, 'batch_display_name'):
                log_activity(_("Truyền file: ") + str(self.batch_display_name) + _(" - Thất bại"))
        except: pass

        # Báo viewer dừng NGAY — không return sớm trước bước này.
        if not remote_triggered:
            pkt = json.dumps({"type": "cancel_transfer", "paste_id": cur}).encode("utf-8")
            socks = set()
            if getattr(self, "sock", None):
                socks.add(self.sock)
            try:
                socks.update(self.active_sockets)
            except Exception:
                pass
            for conn in list(socks):
                try:
                    send_msg(conn, pkt, lock_timeout=0.5)
                except Exception as e:
                    print(f"[FileTransfer] Lỗi gửi tín hiệu hủy: {e}")
        if self.app and getattr(self.app, 'is_headless', False):
            try:
                if all_jobs:
                    self._send_progress_signal("CANCEL", "")
                    self._close_transfer_pipe()
                else:
                    self._send_progress_signal("CANCEL", str(int(cur)))
            except Exception:
                pass
        self.close_dialog(job_id=None if all_jobs else cur, reason="cancel_active_transfer")
        if not all_jobs and (getattr(self, "_xfer_jobs", None) or getattr(self, "_active_send_ids", None)):
            return
        
        if not getattr(self, 'transfer_in_progress', False) and not getattr(self, 'incoming_transfers', {}):
            if not getattr(self, 'pending_remote_files', []):
                self._cleanup_partial_incoming()
                self.transfer_done_event.set()
                return
            
        print(f"[FileTransfer] Bắt đầu dọn dẹp hủy truyền tải (remote_triggered={remote_triggered})...")
        
        saved_pending = list(getattr(self, "pending_remote_files", None) or getattr(self, "_reoffer_files", None) or [])
        self.is_paste_triggered = False
        self._recv_dialog_open = False
        # Giữ metadata để Paste lại. Đừng EmptyClipboard — đang trong WM_RENDERFORMAT
        # thì handler sẽ SetClipboardData delayed; ngoài handler thì setup lại bên dưới.
        if saved_pending:
            self._reoffer_files = saved_pending
            self.pending_remote_files = saved_pending
            self._expect_repaste_until = time.time() + 86400.0
        else:
            self.pending_remote_files = []
            self._reoffer_files = None
        
        # 2. Tắt cờ truyền tải
        self.transfer_in_progress = False
        self._send_cancelled = True
        self._cleanup_partial_incoming()
        cancel_gen = getattr(self, "_cancel_gen", 0)

        def _delayed_cleanup(gen=cancel_gen):
            if getattr(self, "_allow_file_xfer", False):
                return
            if getattr(self, "_cancel_gen", 0) != gen:
                return
            self._cleanup_partial_incoming()

        try:
            threading.Timer(0.4, _delayed_cleanup).start()
            threading.Timer(1.2, _delayed_cleanup).start()
        except Exception:
            pass

        # 4. Đóng progress dialog
        if self.active_dialog:
            try:
                self.active_dialog.on_cancel = None
            except:
                pass
        self.close_dialog(reason="huy truyen tai")
        if self.app:
            try:
                if hasattr(self.app, 'update_status'):
                    self.app.after(0, lambda: self.app.update_status(_("Đã hủy truyền tải file.")))
            except:
                pass
            
        # 6. Mở khóa vòng chờ paste; GIỮ cờ hủy để bỏ chunk còn trên socket.
        # Worker headless không chạy WM_RENDERFORMAT — không được xóa _receive_cancelled.
        self.transfer_done_event.set()
        self.transfer_in_progress = False
        if not getattr(self, "is_rendering", False):
            if saved_pending:
                log_debug("[cancel_active_transfer] Đăng ký lại delayed CF_HDROP để Paste lại.")
                self._schedule_delayed_rearm(0.45)

    def on_foreground_changed(self, hwnd):
        # Hàm này được gọi khi cửa sổ đang active (foreground) thay đổi
        # Nếu chúng ta đang chạy ở mode Client (có Pygame Viewer)
        if getattr(self, 'pygame_hwnd', None) and hwnd == self.pygame_hwnd:
            log_debug("[on_foreground_changed] Cửa sổ Host Viewer vừa được kích hoạt! Kiểm tra đồng bộ Clipboard...")
            # Ném clipboard cho host nếu có thay đổi
            self.on_clipboard_changed(force_sync=True)

    def on_clipboard_changed(self, force_sync=False):
        if not ENABLE_CLIPBOARD_SYNC: return
        if is_own_clipboard_write() and not force_sync:
            return
        hwnd = getattr(self.listener, "hwnd", None) if self.listener else None
        if should_preserve_user_clipboard(hwnd):
            # Chỉ nhả delayed khi user copy SAU offer remote. Preserve mọi lúc
            # sẽ tắt delayed ngay lúc files_copied_meta (host→client) vừa tới.
            if self._user_clipboard_wins():
                self._allow_delayed = False
                # Viewer: clipboard local (file) thay offer remote → nhả để copy client→host.
                if getattr(self, "pygame_hwnd", None) and clipboard_has_file_formats():
                    if self.pending_remote_files or getattr(self, "_reoffer_files", None):
                        try:
                            from utils.clipboard_api import _clipboard_owned_by_sync_window
                            if not _clipboard_owned_by_sync_window():
                                self._release_remote_file_offer("on_clipboard_changed")
                        except Exception:
                            pass
        
        # Copy file trên Explorer máy client: đọc lại clipboard sau khi Explorer xong SetClipboard.
        self._last_clip_event_at = time.time()
        if clipboard_has_file_formats():
            self._schedule_copied_files_sync()
            if getattr(self, "pygame_hwnd", None) and not force_sync:
                return
        if getattr(self, 'pygame_hwnd', None) and not force_sync:
            user32 = ctypes.windll.user32
            user32.GetForegroundWindow.restype = ctypes.c_void_p
            fg_hwnd = user32.GetForegroundWindow()
            if fg_hwnd != self.pygame_hwnd:
                log_debug("[on_clipboard_changed] Ngoài viewer: đồng bộ file copy, giữ text/ảnh máy thật.")
                return
        
        # Tránh tự kích hoạt vòng lặp khi chính ứng dụng thiết lập delayed rendering
        try:
            user32 = ctypes.windll.user32
            user32.GetClipboardOwner.restype = ctypes.c_void_p
            owner = user32.GetClipboardOwner()
            if owner:
                buffer = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ctypes.c_void_p(owner), buffer, 256)
                class_name = buffer.value
                if class_name in ("AntigravityClipboardAgentWnd", "HiddenClipboardListener"):
                    log_debug(f"[on_clipboard_changed] Bỏ qua sự kiện thay đổi clipboard do cửa sổ lớp {class_name} sở hữu (delayed rendering).")
                    return
            if self.listener and self.listener.hwnd and owner == self.listener.hwnd:
                log_debug("[on_clipboard_changed] Bỏ qua sự kiện thay đổi clipboard do chính mình sở hữu (listener hwnd).")
                return
        except Exception as e:
            log_debug(f"[on_clipboard_changed] Lỗi kiểm tra GetClassName/GetClipboardOwner: {e}")

        with self.lock:
            if hasattr(self, '_clipboard_timer') and self._clipboard_timer:
                try:
                    self._clipboard_timer.cancel()
                except:
                    pass
            self._clipboard_timer = threading.Timer(
                0.15,
                lambda fs=force_sync: self._process_clipboard_change_debounced(force=fs),
            )
            self._clipboard_timer.daemon = True
            self._clipboard_timer.start()

    def _process_clipboard_change_debounced(self, provided_files=None, force=False):
        if getattr(self, '_is_processing_clipboard', False) and not force:
            self._clip_resync = True
            return
        self._is_processing_clipboard = True
        try:
            self._process_clipboard_change(provided_files, force=force)
        finally:
            self._is_processing_clipboard = False
            if getattr(self, "_clip_resync", False):
                self._clip_resync = False
                threading.Timer(
                    0.05,
                    lambda: self._process_clipboard_change_debounced(force=True),
                ).start()

    def _process_clipboard_change(self, provided_files=None, force=False):
        try:
            time.sleep(0.02) # Chờ xíu để Windows thả file lock (giảm delay)
            
            owner_hwnd = getattr(self, 'cached_app_hwnd', None)
            if provided_files is not None:
                current_files = provided_files
            elif any(
                (t or {}).get("handle")
                for t in (getattr(self, "incoming_transfers", None) or {}).values()
            ):
                current_files = []
            elif getattr(self, "pygame_hwnd", None):
                # Client: HDROP/CIDA chỉ đọc qua _schedule_copied_files_sync.
                current_files = []
            else:
                current_files = get_clipboard_files(retries=1)
                if not current_files:
                    time.sleep(0.05)
                    current_files = get_clipboard_files(retries=1)
            if current_files:
                # Bỏ qua nếu có bất kỳ file nào nằm trong thư mục tạm RemoteDesktopTransfers (để tránh vòng lặp clipboard)
                temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                temp_dir_abs = os.path.abspath(temp_dir).lower()
                headless_dir_abs = os.path.abspath(HEADLESS_TRANSFER_DIR).lower()
                if any(os.path.abspath(f).lower().startswith(temp_dir_abs) or os.path.abspath(f).lower().startswith(headless_dir_abs) for f in current_files):
                    log_debug("[_process_clipboard_change] Bỏ qua vì phát hiện tệp tin trong thư mục tạm (tránh lặp clipboard).")
                    return
                    
                with self.lock:
                    current_files_lower = [os.path.abspath(f).lower() for f in current_files]
                    last_fp = getattr(self, "_last_sent_file_fp", None)
                    seq = get_clipboard_sequence_number()
                    files_changed = tuple(current_files_lower) != last_fp
                    seq_changed = bool(seq) and seq != getattr(self, "_last_sent_file_seq", None)
                    if not files_changed:
                        if not force and not seq_changed:
                            return
                        if not seq_changed and (time.time() - getattr(self, "last_files_time", 0)) < 0.4:
                            log_debug("[_process_clipboard_change] Bỏ qua: copy trùng (cùng file).")
                            return
                    self.last_current_files = current_files
                    self.last_files_time = time.time()
                    self._last_sent_file_seq = seq
                    self._last_sent_file_fp = tuple(current_files_lower)
                
                metadata = []
                for f in current_files:
                    if os.path.isfile(f):
                        metadata.append({
                            "name": os.path.basename(f),
                            "path": f,
                            "size": os.path.getsize(f),
                            "mtime": os.path.getmtime(f)
                        })
                    elif os.path.isdir(f):
                        parent_dir = os.path.dirname(f)
                        for root, _, files in os.walk(f):
                            for file in files:
                                full_path = os.path.join(root, file)
                                rel_path = os.path.relpath(full_path, parent_dir).replace('\\', '/')
                                metadata.append({
                                    "name": rel_path,
                                    "path": full_path,
                                    "size": os.path.getsize(full_path),
                                    "mtime": os.path.getmtime(full_path)
                                })
                                
                if not metadata: return
                if metadata:
                    # Client viewer: copy file local → nhả offer Paste host→client còn sót.
                    if getattr(self, "pygame_hwnd", None) and (
                        self.pending_remote_files or getattr(self, "_reoffer_files", None)
                    ):
                        try:
                            self._release_remote_file_offer("local_files_meta")
                        except Exception:
                            pass
                    self._clip_offer_id = int(getattr(self, "_clip_offer_id", 0) or 0) + 1
                    names = [m.get("name") or os.path.basename(m.get("path") or "") for m in metadata]
                    if self.active_sockets:
                        print(f"[Clipboard] Gửi files_copied_meta offer={self._clip_offer_id}: {names}")
                        try:
                            from utils.logger import log_overwrite_conflict
                            log_overwrite_conflict(
                                f"CLIENT SEND files_copied_meta offer={self._clip_offer_id} "
                                f"n={len(metadata)} names={names[:8]}"
                            )
                        except Exception:
                            pass
                        pkt = json.dumps({
                            "type": "files_copied_meta",
                            "files": metadata,
                            "offer_id": self._clip_offer_id,
                        }).encode('utf-8')
                        sockets_to_remove = []
                        with self.lock:
                            socks = list(self.active_sockets)
                        for s in socks:
                            try:
                                send_msg(s, pkt)
                            except Exception:
                                sockets_to_remove.append(s)
                        if sockets_to_remove:
                            with self.lock:
                                for s in sockets_to_remove:
                                    if s in self.active_sockets:
                                        self.active_sockets.remove(s)
                    else:
                        # Fork / process phu khong co socket — khong spam FAIL.
                        if not getattr(self, "pygame_hwnd", None) and not (
                            self.app and getattr(self.app, "is_headless", False)
                        ):
                            return
                        try:
                            from utils.logger import log_overwrite_conflict
                            log_overwrite_conflict(
                                f"CLIENT SEND FAIL no active_sockets offer={self._clip_offer_id} "
                                f"n={len(metadata)} names={names[:8]} "
                                f"(chua ket noi host — PENDING se khong toi agent)"
                            )
                        except Exception:
                            pass
                        try:
                            import win32file
                            pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
                            try:
                                import win32pipe
                                win32pipe.WaitNamedPipe(pipe_name, 5000)
                            except Exception:
                                pass
                            pipe_handle = win32file.CreateFile(
                                pipe_name,
                                win32file.GENERIC_WRITE, 0, None,
                                win32file.OPEN_EXISTING, 0, None
                            )
                            win32file.WriteFile(pipe_handle, json.dumps(metadata).encode('utf-8'))
                            win32file.CloseHandle(pipe_handle)
                            log_debug("[_process_clipboard_change] Đã gửi metadata lên Service qua UpPipe.")
                        except Exception as e:
                            log_debug(f"[_process_clipboard_change] Không gửi được metadata lên Service: {e}")
            else:
                # Không phải file → nhánh text (ClipboardTextMixin)
                self.try_forward_local_clipboard_text(owner_hwnd)
        except Exception as e:
            print(f"[FileTransfer] Monitor Error: {e}")

    def _user_clipboard_wins(self):
        """User vừa copy file/ảnh/text sau lần PENDING — không được EmptyClipboard."""
        hwnd = getattr(self.listener, "hwnd", None) if self.listener else None
        if not should_preserve_user_clipboard(hwnd):
            return False
        seq = get_clipboard_sequence_number()
        at = getattr(self, "_clip_seq_at_pending", None)
        if at is None:
            return True
        return (not seq) or seq != at

    def handle_received_packet(self, packet):
        ptype = packet.get("type")
        
        if ptype == "clear_clipboard":
            self.handle_clear_clipboard_packet(packet)
            return

        if ptype == "clipboard_text":
            # Text host↔client: luôn nhận khi đang có phiên (giống RDP).
            self.handle_clipboard_text_packet(packet)
            return

        if ptype in ("batch_start", "file_start", "file_chunk", "file_end", "batch_end"):
            xid = packet.get("xfer_id")
            aborted = getattr(self, "_aborted_xfer_ids", None) or set()
            jobs = getattr(self, "_xfer_jobs", None) or {}
            stale = (xid is not None and xid in aborted) or not self._xfer_packet_ok(packet, ptype)
            if (
                not stale
                and not getattr(self, "_allow_file_xfer", False)
                and xid not in jobs
            ):
                stale = True
            if stale:
                log_debug(f"[handle_received_packet] Drain/discard {ptype} xfer_id={xid} (Huy — van doc socket).")
                return

        if ptype == "cancel_ack":
            print("[FileTransfer] Nhan cancel_ack — ngat vong gui.")
            ack_id = self._coerce_paste_id(packet.get("paste_id"))
            self._disarm_file_xfer("cancel_ack", cancelled_paste_id=ack_id, all_jobs=ack_id is None)
            return

        if ptype == "cancel_transfer":
            print("[FileTransfer] Nhận tín hiệu hủy truyền tải từ đối tác.")
            pid = self._coerce_paste_id(packet.get("paste_id")) if "paste_id" in packet else None
            self.cancel_active_transfer(remote_triggered=True, paste_id=pid, all_jobs=pid is None)
            return

        elif ptype == "resume_query":
            xid = packet.get("xfer_id")
            snap = self._resume_snapshot(xid)
            live = self._live_xfer_sock()
            if live:
                try:
                    send_msg(live, json.dumps(snap).encode("utf-8"))
                    print(f"[FileTransfer] resume_state xfer_id={xid} files={list((snap.get('files') or {}).keys())[:8]}")
                except Exception as e:
                    print(f"[FileTransfer] Gui resume_state loi: {e}")
            return

        elif ptype == "resume_state":
            xid = packet.get("xfer_id")
            waiters = getattr(self, "_resume_waiters", None) or {}
            pair = waiters.get(xid)
            if pair:
                ev, box = pair
                box["state"] = packet
                ev.set()
            return
            
        elif ptype == "files_copied_meta":
            files = packet.get("files", [])
            print(f"[Clipboard] Nhận files_copied_meta offer={packet.get('offer_id')} n={len(files)} {[f.get('name') for f in (files or [])[:8]]}")
            try:
                from utils.logger import clip_trace, log_overwrite_conflict
                clip_trace(
                    f"[client] RECV files_copied_meta offer={packet.get('offer_id')} "
                    f"n={len(files)} names={[f.get('name') for f in (files or [])[:8]]} "
                    f"cache={getattr(self,'cached_explorer_path',None)} "
                    f"last={getattr(self,'_last_good_explorer_path',None)} "
                    f"frozen={getattr(self,'_paste_dest_frozen',False)}"
                )
                role = "HOST_HEADLESS" if (self.app and getattr(self.app, "is_headless", False)) else "CLIENT_GUI"
                log_overwrite_conflict(
                    f"{role} RECV files_copied_meta offer={packet.get('offer_id')} "
                    f"n={len(files)} names={[f.get('name') for f in (files or [])[:8]]}"
                )
            except Exception:
                pass
            self._enqueue_file_offer(files, packet.get("offer_id"))
            return
            
        elif ptype == "request_files":
            try:
                tok = int(packet.get("paste_id") or 0)
            except Exception:
                tok = 0
            cancelled = getattr(self, "_cancelled_paste_ids", None) or set()
            if tok and tok in cancelled:
                print(f"[FileTransfer] Bo request_files paste_id={tok} (blacklist Huy).")
                return
            if not tok and time.time() < getattr(self, "_suppress_request_files_until", 0):
                print("[FileTransfer] Bo request_files khong paste_id sau Huy.")
                return
            if tok:
                self._clipboard_paste_id = tok
            if not self._arm_file_xfer("peer_request_files"):
                return
            files_to_send = packet.get("files", [])
            sid = getattr(self, "_send_xfer_id", 0)
            self._enqueue_send_job(files_to_send, sid, tok)
            return

        elif ptype == "paste_conflict_query":
            # Host agent hỏi ghi đè — hiện dialog trên client (nơi user đang nhìn).
            threading.Thread(
                target=self._handle_paste_conflict_query,
                args=(packet,),
                daemon=True,
                name="PasteConflictAsk",
            ).start()
            return

        elif ptype == "paste_conflict_reply":
            # Client trả lời → chuyển xuống Clipboard Agent trên host.
            try:
                payload = {
                    "paste_id": packet.get("paste_id"),
                    "cancelled": bool(packet.get("cancelled")),
                    "skip_keys": list(packet.get("skip_keys") or []),
                    "replace_keys": list(packet.get("replace_keys") or []),
                }
                self._send_to_pipe("CONFLICT_REPLY", json.dumps(payload))
                print(
                    f"[Clipboard] CONFLICT_REPLY → agent paste_id={payload.get('paste_id')} "
                    f"cancelled={payload.get('cancelled')}"
                )
            except Exception as e:
                print(f"[Clipboard] CONFLICT_REPLY forward loi: {e}")
            return
            
        elif ptype == "batch_start":
            xid = packet.get("xfer_id")
            if xid is not None and xid in (getattr(self, "_aborted_xfer_ids", None) or set()):
                log_debug(f"[batch_start] Bo xfer da huy {xid}")
                return
            jobs = getattr(self, "_xfer_jobs", None)
            if jobs is None:
                self._xfer_jobs = {}
                jobs = self._xfer_jobs
            existing = jobs.get(xid) if xid is not None else None
            if existing:
                existing["last_chunk_at"] = time.time()
                existing["retry_ui"] = False
                log_debug(f"[batch_start] Giu job cu de resume xfer_id={xid} received={existing.get('received')}")
                self.transfer_in_progress = True
                self._receive_cancelled = False
                if xid is not None:
                    self._recv_xfer_id = xid
                return
            paste_id = packet.get("paste_id")
            try:
                paste_id = int(paste_id) if paste_id is not None else int(getattr(self, "_clipboard_paste_id", 0) or 0)
            except Exception:
                paste_id = 0
            display_name = packet.get("display_name", "Files")
            item_kind = packet.get("item_kind") or "file"
            total_size = packet.get("total_size", 0)
            # Host headless (client→host): không lấy Explorer dest cho job nhận.
            # Ghi dest vào đây → promote từng file vào thư mục đích, dialog ghi đè vô nghĩa.
            if self.app and getattr(self.app, "is_headless", False):
                paste_dest = None
                save_dir = getattr(self, "target_save_dir", None) or HEADLESS_TRANSFER_DIR
            else:
                paste_dest = getattr(self, "_paste_dest_dir", None)
                if paste_id:
                    paste_dest = (getattr(self, "_xfer_dest_by_paste_id", None) or {}).get(paste_id) or paste_dest
                if paste_dest and _is_transfer_staging_dir(paste_dest):
                    paste_dest = None
                save_dir = paste_dest or getattr(self, "target_save_dir", None) or HEADLESS_TRANSFER_DIR
            job = {
                "xfer_id": xid,
                "paste_id": paste_id,
                "received": 0,
                "total": total_size,
                "paths": [],
                "display_name": display_name,
                "item_kind": item_kind,
                "last_progress": 0.0,
                "last_chunk_at": time.time(),
                "retry_ui": False,
                "expected_files": list((getattr(self, "_xfer_expected_files", None) or {}).get(paste_id) or []),
                "save_dir": save_dir,
                "paste_dest": paste_dest,
            }
            jobs[xid] = job
            self.batch_total_size = total_size
            self.batch_received = 0
            self.batch_paths = job["paths"]
            self.batch_display_name = display_name
            self.transfer_in_progress = True
            self._receive_cancelled = False
            if xid is not None:
                self._recv_xfer_id = xid
            try:
                os.makedirs(job.get("save_dir") or HEADLESS_TRANSFER_DIR, exist_ok=True)
            except Exception:
                pass
            log_file_transfer(display_name, total_size)
            log_debug(f"[batch_start] Bắt đầu nhận batch xfer_id={xid} paste_id={paste_id} total={total_size} dest={paste_dest}")
            try:
                from utils.logger import clip_trace
                clip_trace(
                    f"[batch_start] xfer_id={xid} paste_id={paste_id} total={total_size} "
                    f"paste_dest={paste_dest!r} save_dir={job.get('save_dir')!r} "
                    f"live_cache={getattr(self,'cached_explorer_path',None)!r} "
                    f"frozen={getattr(self,'_paste_dest_frozen',False)}"
                )
            except Exception:
                pass
            if not (self.app and getattr(self.app, 'is_headless', False)):
                dest_dir = paste_dest
                if not dest_dir:
                    # Không fallback cached_explorer_path sống — sẽ dán nhầm folder đang mở lúc packet tới.
                    save = getattr(self, "target_save_dir", None)
                    if save and not _is_transfer_staging_dir(save):
                        dest_dir = save
                expected = job.get("expected_files") or []
                kind, name = _copy_batch_kind_and_name(expected, display_name)
                if not expected:
                    kind = item_kind if item_kind in ("file", "folder") else kind
                    name = display_name or name
                # Dialog đã mở từ render_format — chỉ mở thêm nếu chưa có.
                if paste_id not in (getattr(self, "xfer_dialogs", None) or {}):
                    self.open_paste_progress_dialog(
                        name, total_size, dest_dir, job_id=paste_id or xid, item_kind=kind,
                    )
            return

        elif ptype == "file_start":
            filename = packet.get("name", "")
            if not filename: return
            
            xid = packet.get("xfer_id")
            job = (getattr(self, "_xfer_jobs", None) or {}).get(xid) if xid is not None else None
            save_dir = (job or {}).get("save_dir") or self.target_save_dir
            pkt_dir = packet.get("target_dir")
            if pkt_dir and _is_transfer_staging_dir(pkt_dir):
                save_dir = pkt_dir
            if not save_dir:
                save_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
            key = _incoming_key(xid, filename)
            resume_from = packet.get("offset")
            try:
                resume_from = int(resume_from) if resume_from is not None else 0
            except Exception:
                resume_from = 0
            existing = self.incoming_transfers.get(key)
            if (
                existing
                and existing.get("handle")
                and xid is not None
                and existing.get("xfer_id") == xid
            ):
                if resume_from > 0:
                    try:
                        existing["handle"].seek(resume_from)
                        existing["written"] = resume_from
                    except Exception:
                        pass
                    log_debug(f"[file_start] Resume handle {filename} offset={resume_from}")
                else:
                    log_debug(f"[file_start] Bỏ file_start trùng (tránh cắt file) xfer_id={xid} {filename}")
                return
            save_dir = _xfer_staging_dir(save_dir, xid)
            
            target_path = os.path.join(save_dir, filename)
            log_debug(f"[file_start] Bắt đầu nhận file: {filename}, target_path={target_path} offset={resume_from}")

            try:
                dirname = os.path.dirname(target_path)
                if dirname:
                    os.makedirs(dirname, exist_ok=True)
                    stg = save_dir if os.path.basename(save_dir).startswith(".rdxfer_") else dirname
                    if os.path.basename(stg).startswith(".rdxfer_"):
                        _hide_win_path(stg)
                old = self.incoming_transfers.pop(key, None)
                if old and old.get("handle"):
                    try:
                        old["handle"].close()
                    except Exception:
                        pass
                exists = os.path.exists(target_path)
                mode = "r+b" if (resume_from > 0 and exists) else "wb"
                fh = open(target_path, mode, buffering=1024 * 1024)
                dest_now = self._paste_dest_for_job(job)
                self._ensure_dest_tree(dest_now, filename)
                written = 0
                if resume_from > 0:
                    try:
                        actual = os.path.getsize(target_path) if exists else 0
                    except Exception:
                        actual = 0
                    written = min(resume_from, actual)
                    try:
                        fh.seek(written)
                    except Exception:
                        fh.seek(0)
                        written = 0
                expected = packet.get("size")
                try:
                    expected = int(expected) if expected is not None else None
                except Exception:
                    expected = None
                self.incoming_transfers[key] = {
                    "path": target_path,
                    "handle": fh,
                    "skipped": False,
                    "pending": False,
                    "xfer_id": xid,
                    "expected_size": expected,
                    "written": written,
                    "name": filename,
                }
                try:
                    self._partial_output_paths = list(getattr(self, "_partial_output_paths", None) or [])
                    self._partial_output_paths.append(target_path)
                except Exception:
                    pass
                log_debug(f"[file_start] Mở thành công file mới: {target_path} expected={expected}")
            except Exception as e:
                print(f"[FileTransfer] Lỗi mở file mới {filename}: {e}")
                log_debug(f"[file_start] Lỗi mở file mới {filename}: {e}")

        elif ptype == "file_chunk":
            filename = packet.get("name", "")
            xid = packet.get("xfer_id")
            key = _incoming_key(xid, filename)
            if key in self.incoming_transfers:
                transfer = self.incoming_transfers[key]
                if xid is not None and transfer.get("xfer_id") is not None and xid != transfer.get("xfer_id"):
                    log_debug(f"[file_chunk] Bỏ chunk xfer_id cũ cho {filename}")
                    return
                chunk_bytes = base64.b64decode(packet.get("data", ""))
                expected = transfer.get("expected_size")
                written = int(transfer.get("written") or 0)
                chunk_offset = packet.get("offset")
                try:
                    chunk_offset = int(chunk_offset) if chunk_offset is not None else None
                except Exception:
                    chunk_offset = None
                start = written if chunk_offset is None else max(0, chunk_offset)
                if expected is not None and start >= expected:
                    return
                if expected is not None and start + len(chunk_bytes) > expected:
                    chunk_bytes = chunk_bytes[: max(0, expected - start)]
                if not chunk_bytes:
                    return

                if transfer.get("handle") is not None:
                    if chunk_offset is not None:
                        try:
                            transfer["handle"].seek(start)
                        except Exception:
                            pass
                    transfer["handle"].write(chunk_bytes)
                    new_written = start + len(chunk_bytes)
                    delta = max(0, new_written - written)
                    transfer["written"] = max(written, new_written)
                    job = (getattr(self, "_xfer_jobs", None) or {}).get(xid)
                    if job is None:
                        self.batch_received += delta
                        rec = self.batch_received
                        total = getattr(self, "batch_total_size", 0)
                        paste_id = int(getattr(self, "_clipboard_paste_id", 0) or 0)
                    else:
                        job["received"] = int(job.get("received") or 0) + delta
                        job["last_chunk_at"] = time.time()
                        rec = job["received"]
                        total = job.get("total") or 0
                        paste_id = int(job.get("paste_id") or 0)
                    self.update_dialog(rec, job_id=paste_id or xid)
                    if self.app and getattr(self.app, 'is_headless', False):
                        now = time.time()
                        last = float(job.get("last_progress") or 0) if job else getattr(self, "_last_progress_time", 0)
                        if (now - last >= 0.05) or (total and rec >= total):
                            payload = f"{paste_id}|{rec}" if paste_id else str(rec)
                            self._send_progress_signal("PROGRESS", payload)
                            if job is not None:
                                job["last_progress"] = now
                            else:
                                self._last_progress_time = now
                    current_time_ack = time.time()
                    if not hasattr(self, '_last_upload_ack_time'):
                        self._last_upload_ack_time = 0
                    if (current_time_ack - self._last_upload_ack_time >= 0.2) or (total and rec >= total):
                        self._last_upload_ack_time = current_time_ack
                        if getattr(self, 'sock', None):
                            try:
                                send_msg(self.sock, json.dumps({"type": "upload_progress_ack", "received": rec, "xfer_id": xid}).encode('utf-8'))
                            except: pass

        elif ptype == "file_end":
            filename = packet.get("name", "")
            xid = packet.get("xfer_id")
            key = _incoming_key(xid, filename)
            if key in self.incoming_transfers:
                transfer = self.incoming_transfers[key]
                if xid is not None and transfer.get("xfer_id") is not None and xid != transfer.get("xfer_id"):
                    log_debug(f"[file_end] Bỏ file_end xfer_id cũ cho {filename}")
                    return
                transfer = self.incoming_transfers.pop(key, None)
                if transfer:
                    job = (getattr(self, "_xfer_jobs", None) or {}).get(transfer.get("xfer_id") if transfer.get("xfer_id") is not None else xid)
                    ev = threading.Event()
                    if job is not None:
                        job.setdefault("finish_events", []).append(ev)
                    def _finish(t=transfer, j=job, e=ev, fn=filename):
                        try:
                            self._finalize_incoming_file(t, j, fn)
                        except Exception as ex:
                            print(f"[FileTransfer] Finalize {fn} loi: {ex}")
                        finally:
                            e.set()
                    threading.Thread(target=_finish, daemon=True, name="XferFinish").start()
            
        elif ptype == "batch_end":
            threading.Thread(
                target=self._complete_batch_after_files,
                args=(packet,),
                daemon=True,
                name="XferBatchEnd",
            ).start()
            return


def _bind_clipboard_mixin_globals():
    """Cho mixin methods resolve helpers (tránh circular import lúc định nghĩa)."""
    import clipboardtext as _ct
    import filecopyclient as _fc
    import filecopyhost as _fh
    import sys
    src = sys.modules[__name__]
    skip = {"ClipboardSyncManager", "ClipboardTextMixin", "FileCopyClientMixin", "FileCopyHostMixin"}
    for name, obj in list(globals().items()):
        if name in skip or name.startswith("__"):
            continue
        setattr(_ct, name, obj)
        setattr(_fc, name, obj)
        setattr(_fh, name, obj)
    # Đảm bảo mixin modules thấy cả import của module này
    for mod in (_ct, _fc, _fh):
        for name in (
            "os", "sys", "time", "json", "queue", "threading", "socket", "ctypes",
            "base64", "tk", "win32file", "win32pipe", "win32event", "win32api", "win32gui",
            "send_msg", "recv_msg", "is_lan_socket", "tune_socket_for_lan_bulk", "socket_passwords",
            "ProgressDialog", "ClassicCopyDialog", "file_download_dialog_title",
            "log_debug", "log_file_transfer", "log_activity",
            "get_clipboard_text", "set_clipboard_text", "get_clipboard_files", "set_clipboard_files",
            "create_hdrop_data", "fn_SetClipboardData", "fn_GlobalFree", "clear_local_clipboard",
            "get_clipboard_sequence_number", "mark_own_clipboard_write", "is_own_clipboard_write",
            "should_preserve_user_clipboard", "clipboard_has_file_formats", "ENABLE_CLIPBOARD_SYNC",
            "set_clipboard_dword_format", "setup_clipboard_exclusions",
            "_", "app_dir", "CLIPBOARD_PKT_TYPES",
            "WM_CLIPBOARDUPDATE", "HWND_MESSAGE", "_WM_RENDERFORMAT", "_WM_RENDERALLFORMATS",
            "WPARAM_64", "LPARAM_64", "LRESULT_64", "WNDPROCTYPE", "WNDCLASSEX",
            "ClipboardEventListener", "ClipboardSyncManager",
        ):
            if name in globals():
                setattr(mod, name, globals()[name])
            elif hasattr(src, name):
                setattr(mod, name, getattr(src, name))

_bind_clipboard_mixin_globals()

if is_clipboard_agent or is_gui_agent:
    clipboard_sync_manager = None
else:
    clipboard_sync_manager = ClipboardSyncManager()

