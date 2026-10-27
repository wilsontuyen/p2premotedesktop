"""File copy/paste client -> host (send worker, UpPipe, clipboard agent)."""
from __future__ import annotations

import base64
import json
import os
import sys
import threading
import time
import ctypes
from ctypes import wintypes
from typing import Any, Callable

try:
    import win32file
    import win32pipe
    import win32event
    import win32security
except ImportError:  # pragma: no cover
    win32file = win32pipe = win32event = win32security = None  # type: ignore

from core.i18n import _
from network.socket_utils import send_msg, is_lan_socket, tune_socket_for_lan_bulk
from utils.logger import log_debug, log_activity, log_file_transfer, log_overwrite_conflict
from utils.clipboard_api import (
    create_hdrop_data,
    fn_SetClipboardData,
    fn_GlobalFree,
    clear_local_clipboard,
    get_clipboard_files,
    get_clipboard_sequence_number,
    get_clipboard_text,
    set_clipboard_text,
    mark_own_clipboard_write,
    is_own_clipboard_write,
    setup_clipboard_exclusions,
    should_preserve_user_clipboard,
)
from gui.windows_ui import ProgressDialog, file_download_dialog_title
from gui.components import ClassicCopyDialog

# Shared file helpers (host -> client module is the home for path/staging/menu)
from filecopyclient import (
    HEADLESS_TRANSFER_DIR,
    _CLIPBOARD_PROBE_PROCS,
    _CONTEXT_MENU_CLASSES,
    _CONTEXT_MENU_HIT_CLASSES,
    _EXPLORER_CLIPBOARD_PROCS,
    _EXPLORER_FOLDER_CLASSES,
    _PROBE_STUB_DIR,
    _capture_menu_item_at_cursor,
    _copy_batch_kind_and_name,
    _context_menu_open,
    _cursor_over_context_menu,
    _cursor_within_any_visible_menu_rect,
    _cursor_over_current_process,
    _cursor_xy,
    _double_click_ms,
    _is_windows_11,
    _menu_item_counts_as_paste,
    _win10_rmb_paste_click,
    _is_recent_rmb_paste_click_unified,
    _cursor_in_explorer_command_bar,
    set_global_rmb_pos,
    _file_expected_size,
    _file_io_lock,
    _file_offer_fp,
    _is_transfer_junk_at_dest,
    _is_transfer_staging_dir,
    _is_probe_stub_name,
    _path_in_xfer_staging,
    _offer_empty_hdrop,
    _offer_probe_hdrop,
    _path_byte_size,
    _paths_match_expected_sizes,
    _purge_rdxfer_staging,
    _notify_explorer_paths_changed,
    _relocate_transfer_files_unlocked,
    _retry_remove_path,
    _same_volume,
    _schedule_scrub_probe,
    check_is_menu_query,
    cleanup_incomplete_named_files,
    query_explorer_folder_path,
    _is_taskbar_or_taskmgr_at_point,
    _is_taskbar_or_taskmgr_hwnd,
    _pid_image_name,
    _hwnd_process_name,
    _is_explorer_clipboard_client,
    _EXPLORER_CLIPBOARD_PROCS,
)

# Injected by windows_clipboard._bind
app_dir: str

# Types for low-level hooks
WPARAM_64 = ctypes.c_size_t
LPARAM_64 = ctypes.c_ssize_t
LRESULT_64 = ctypes.c_ssize_t
_LL_HOOK_KEEPALIVE = []

def _parse_files_pipe_payload(paths_str):
    """FILES: [paste_id|]path|path — paste_id để bỏ gói trễ sau Hủy."""
    parts = [p for p in (paths_str or "").split("|") if p]
    paste_id = None
    if parts and parts[0].isdigit():
        paste_id = int(parts[0])
        parts = parts[1:]
    return paste_id, parts

CLIPBOARD_PIPE_NAME = r"\\.\pipe\RemoteDesktopClipboardPipe"

def _low_il_everyone_sa():
    """SECURITY_ATTRIBUTES: Everyone + Mandatory Label Low — user Medium IL ghi được."""
    import win32security
    sa = win32security.SECURITY_ATTRIBUTES()
    sa.bInheritHandle = 0
    try:
        sd = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
            "D:(A;;GA;;;WD)(A;;GA;;;AN)S:(ML;;NW;;;LW)",
            win32security.SDDL_REVISION_1,
        )
        sa.SECURITY_DESCRIPTOR = sd
    except Exception:
        sd = win32security.SECURITY_DESCRIPTOR()
        sd.Initialize()
        sd.SetSecurityDescriptorDacl(True, None, False)
        sa.SECURITY_DESCRIPTOR = sd
    return sa


def create_named_pipe_with_everyone_dacl():
    """
    Tạo Named Pipe Server với Security Descriptor cho phép nhóm Everyone 
    và các tiến trình ở Medium/Low IL (Session 1 User) kết nối được tới pipe 
    do SYSTEM (Session 0) tạo. TUYỆT ĐỐI KHÔNG truyền None vào Security Attributes.
    """
    import win32pipe
    
    sa = _low_il_everyone_sa()
    
    # Tạo Named Pipe với PIPE_UNLIMITED_INSTANCES
    pipe_handle = win32pipe.CreateNamedPipe(
        CLIPBOARD_PIPE_NAME,
        win32pipe.PIPE_ACCESS_OUTBOUND,                    # Server chỉ ghi (outbound)
        win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,  # Message mode, blocking
        win32pipe.PIPE_UNLIMITED_INSTANCES,                # Cho phép kết nối không giới hạn
        10 * 1024 * 1024,    # Output buffer size (10MB)
        10 * 1024 * 1024,    # Input buffer size (10MB)
        0,                   # Default timeout
        sa                   # Security Attributes với Low IL + Everyone DACL
    )
    
    return pipe_handle


def _create_user_signalable_event(name):
    """Manual-reset event: SetEvent đánh thức MỌI worker (auto-reset chỉ 1 process)."""
    import win32event
    return win32event.CreateEvent(_low_il_everyone_sa(), True, False, name)


def _open_or_create_user_signalable_event(name):
    import win32event, win32con
    try:
        return win32event.OpenEvent(win32con.EVENT_ALL_ACCESS, False, name)
    except Exception:
        return _create_user_signalable_event(name)


_cached_global_shared_dir = None

def get_global_shared_dir():
    """
    Trả về thư mục chia sẻ IPC dùng chung giữa SYSTEM (Session 0/1) và User thường (Session 1).
    Tuyệt đối không dùng get_logs_dir() vì get_logs_dir() trả về thư mục riêng theo từng user profile!
    """
    global _cached_global_shared_dir
    if _cached_global_shared_dir and os.path.isdir(_cached_global_shared_dir):
        return _cached_global_shared_dir

    candidates = []
    pd = os.environ.get("PROGRAMDATA") or os.environ.get("ALLUSERSPROFILE") or r"C:\ProgramData"
    candidates.append(os.path.join(pd, "Easy Remote Desktop", "IPC"))

    pub = os.environ.get("PUBLIC") or r"C:\Users\Public"
    candidates.append(os.path.join(pub, "EasyRemoteDesktop", "IPC"))

    try:
        from utils.logger import app_dir
        candidates.append(os.path.join(app_dir, "Logs"))
    except Exception:
        pass

    try:
        from utils.logger import get_logs_dir
        candidates.append(get_logs_dir())
    except Exception:
        pass

    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            test_f = os.path.join(d, ".perm_test")
            with open(test_f, "w", encoding="utf-8") as tf:
                tf.write("ok")
            try:
                os.remove(test_f)
            except Exception:
                pass
            _cached_global_shared_dir = d
            return d
        except Exception:
            continue

    _cached_global_shared_dir = candidates[0]
    return _cached_global_shared_dir


def get_shared_pending_offer_file():
    return os.path.join(get_global_shared_dir(), "pending_remote_offer.json")


def get_shared_agent_hwnd_file():
    return os.path.join(get_global_shared_dir(), "shared_agent_hwnd.txt")


def write_shared_pending_offer(msg_dict):
    try:
        import json, tempfile, win32event
        dirs_to_write = [get_global_shared_dir()]
        try:
            from utils.logger import get_logs_dir
            ld = get_logs_dir()
            if ld not in dirs_to_write:
                dirs_to_write.append(ld)
        except Exception:
            pass

        written_any = False
        for dirpath in dirs_to_write:
            try:
                os.makedirs(dirpath, exist_ok=True)
                fpath = os.path.join(dirpath, "pending_remote_offer.json")
                tmp_fd, tmp_path = tempfile.mkstemp(dir=dirpath, suffix=".tmp")
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(msg_dict, f, ensure_ascii=False)
                if os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
                shutil.move(tmp_path, fpath)
                written_any = True
            except Exception:
                pass

        try:
            h_evt = _open_or_create_user_signalable_event(r"Global\AntigravityP2P_PendingOffer_Event")
            if h_evt:
                win32event.SetEvent(h_evt)
                win32event.CloseHandle(h_evt)
        except Exception:
            pass
        from utils.logger import log_overwrite_conflict
        log_overwrite_conflict(f"WRITE SHARED OFFER OK: dirs={dirs_to_write} offer={msg_dict.get('offer_id')}")
        return written_any
    except Exception as e:
        try:
            from utils.logger import log_overwrite_conflict
            log_overwrite_conflict(f"WRITE SHARED OFFER FAIL: {e}")
        except Exception:
            pass
        return False


def read_shared_pending_offer(max_age_s=86400.0):
    try:
        import json
        dirs_to_check = [get_global_shared_dir()]
        try:
            from utils.logger import get_logs_dir, app_dir
            ld = get_logs_dir()
            if ld not in dirs_to_check:
                dirs_to_check.append(ld)
            ad_logs = os.path.join(app_dir, "Logs")
            if ad_logs not in dirs_to_check:
                dirs_to_check.append(ad_logs)
            pub = os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "EasyRemoteDesktop", "IPC")
            if pub not in dirs_to_check:
                dirs_to_check.append(pub)
            pd = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Easy Remote Desktop", "IPC")
            if pd not in dirs_to_check:
                dirs_to_check.append(pd)
        except Exception:
            pass

        best_data = None
        best_mtime = 0.0

        for d in dirs_to_check:
            fpath = os.path.join(d, "pending_remote_offer.json")
            if not os.path.exists(fpath):
                continue
            try:
                mt = os.path.getmtime(fpath)
                if time.time() - mt > max_age_s:
                    continue
                if mt > best_mtime:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and (data.get("files") or data.get("names")):
                        best_data = data
                        best_mtime = mt
            except Exception:
                pass

        if best_data:
            return best_data
    except Exception:
        pass
    return None


def write_shared_agent_hwnd(hwnd):
    dirs_to_write = [get_global_shared_dir()]
    try:
        from utils.logger import get_logs_dir
        ld = get_logs_dir()
        if ld not in dirs_to_write:
            dirs_to_write.append(ld)
    except Exception:
        pass
    for d in dirs_to_write:
        try:
            os.makedirs(d, exist_ok=True)
            fpath = os.path.join(d, "shared_agent_hwnd.txt")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(str(int(hwnd)))
        except Exception:
            pass


def read_shared_agent_hwnd():
    try:
        dirs_to_check = [get_global_shared_dir()]
        try:
            from utils.logger import get_logs_dir, app_dir
            ld = get_logs_dir()
            if ld not in dirs_to_check:
                dirs_to_check.append(ld)
            ad_logs = os.path.join(app_dir, "Logs")
            if ad_logs not in dirs_to_check:
                dirs_to_check.append(ad_logs)
            pub = os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "EasyRemoteDesktop", "IPC")
            if pub not in dirs_to_check:
                dirs_to_check.append(pub)
            pd = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Easy Remote Desktop", "IPC")
            if pd not in dirs_to_check:
                dirs_to_check.append(pd)
        except Exception:
            pass

        for d in dirs_to_check:
            fpath = os.path.join(d, "shared_agent_hwnd.txt")
            if not os.path.exists(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    val = int(f.read().strip())
                if val and ctypes.windll.user32.IsWindow(ctypes.c_void_p(val)):
                    return val
            except Exception:
                pass
    except Exception:
        pass
    return None


def write_shared_paste_request(payload):
    try:
        import json, win32event
        dirs_to_write = [get_global_shared_dir()]
        try:
            from utils.logger import get_logs_dir
            ld = get_logs_dir()
            if ld not in dirs_to_write:
                dirs_to_write.append(ld)
        except Exception:
            pass

        tok = int((payload or {}).get("paste_id") or 0)
        for d in dirs_to_write:
            try:
                os.makedirs(d, exist_ok=True)
                fpath = os.path.join(d, f"paste_req_{tok}.json")
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False)
            except Exception:
                pass
        try:
            h_evt = _open_or_create_user_signalable_event(r"Global\AntigravityP2P_PasteRequest_Event")
            if h_evt:
                win32event.SetEvent(h_evt)
                win32event.CloseHandle(h_evt)
        except Exception:
            pass
        return True
    except Exception:
        return False


def read_shared_paste_requests():
    reqs = []
    try:
        import json, glob
        dirs_to_check = [get_global_shared_dir()]
        try:
            from utils.logger import get_logs_dir
            ld = get_logs_dir()
            if ld not in dirs_to_check:
                dirs_to_check.append(ld)
            pub = os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "EasyRemoteDesktop", "IPC")
            if pub not in dirs_to_check:
                dirs_to_check.append(pub)
            pd = os.path.join(os.environ.get("PROGRAMDATA", r"C:\ProgramData"), "Easy Remote Desktop", "IPC")
            if pd not in dirs_to_check:
                dirs_to_check.append(pd)
        except Exception:
            pass

        seen_toks = set()
        for d in dirs_to_check:
            pattern = os.path.join(d, "paste_req_*.json")
            for fpath in glob.glob(pattern):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        tok = data.get("paste_id")
                        if tok not in seen_toks:
                            seen_toks.add(tok)
                            reqs.append((fpath, data))
                except Exception:
                    pass
    except Exception:
        pass
    return reqs




class _KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


_HOOKPROC = ctypes.WINFUNCTYPE(LRESULT_64, ctypes.c_int, WPARAM_64, LPARAM_64)
_CallNextHookEx = ctypes.WINFUNCTYPE(
    LRESULT_64, ctypes.c_void_p, ctypes.c_int, WPARAM_64, LPARAM_64
)(("CallNextHookEx", ctypes.windll.user32))


def _install_paste_ll_hooks(on_ctrl_v, on_lbutton, on_rbutton):
    """Hook LL chỉ cho clipboard-agent (host). Callback phải PostMessage, không OpenClipboard."""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GetModuleHandleW.restype = ctypes.c_void_p
    user32.SetWindowsHookExW.restype = ctypes.c_void_p

    def _kb(nCode, wParam, lParam):
        try:
            if nCode >= 0 and int(wParam) in (0x0100, 0x0104):
                kb = ctypes.cast(int(lParam), ctypes.POINTER(_KBDLLHOOKSTRUCT)).contents
                vk = int(kb.vkCode)
                ctrl = bool(user32.GetAsyncKeyState(0x11) & 0x8000)
                shift = bool(user32.GetAsyncKeyState(0x10) & 0x8000)
                if (vk in (0x56, 0x76) and ctrl) or (vk == 0x2D and shift):
                    on_ctrl_v()
        except Exception:
            pass
        return _CallNextHookEx(None, nCode, wParam, lParam)

    def _mouse(nCode, wParam, lParam):
        try:
            if nCode >= 0:
                msg = int(wParam)
                if msg in (0x0201, 0x0203):
                    on_lbutton()
                elif msg in (0x0204, 0x0206):
                    on_rbutton()
        except Exception:
            pass
        return _CallNextHookEx(None, nCode, wParam, lParam)

    kb_proc = _HOOKPROC(_kb)
    mouse_proc = _HOOKPROC(_mouse)
    hmod = kernel32.GetModuleHandleW(None)
    hk_kb = user32.SetWindowsHookExW(13, kb_proc, hmod, 0)
    hk_mouse = user32.SetWindowsHookExW(14, mouse_proc, hmod, 0)
    _LL_HOOK_KEEPALIVE.extend((kb_proc, mouse_proc, hk_kb, hk_mouse))
    return hk_kb, hk_mouse


class FileCopyHostMixin:
    """Mixin: gửi file / agent paste trên host."""

    def _shared_paste_request_watcher(self):
        import win32event, time
        h_evt = None
        try:
            h_evt = _open_or_create_user_signalable_event(r"Global\AntigravityP2P_PasteRequest_Event")
        except Exception:
            pass
        while True:
            try:
                if h_evt:
                    win32event.WaitForSingleObject(h_evt, 400)
                    win32event.ResetEvent(h_evt)
                else:
                    time.sleep(0.4)
                reqs = read_shared_paste_requests()
                for fpath, data in reqs:
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
                    files_req = data.get("files") or []
                    tok = int(data.get("paste_id") or 0)
                    dest_dir = data.get("dest_dir") or ""
                    if files_req and tok:
                        now = time.time()
                        last_req_time = getattr(self, "_last_request_files_time", 0)
                        last_tok = getattr(self, "_last_request_files_tok", None)
                        if tok == last_tok and (now - last_req_time) < 1.0:
                            continue
                        self._last_request_files_time = now
                        self._last_request_files_tok = tok
                        self._last_request_files_list = files_req
                        log_debug(f"[SharedPasteRequestWatcher] Kích hoạt tải paste_id={tok} n={len(files_req)} dest={dest_dir}")
                        self._allow_file_xfer = True
                        self._send_cancelled = False
                        self._receive_cancelled = False
                        threading.Thread(
                            target=self.request_pending_files,
                            args=(files_req, tok),
                            daemon=True,
                        ).start()
            except Exception as e:
                time.sleep(1.0)

    def _start_uppipe_server(self):
        import win32pipe, win32file
        import time
        print(r"[Clipboard] UpPipe server bat dau (\\.\pipe\RemoteDesktopClipboardUpPipe).")
        threading.Thread(target=self._shared_paste_request_watcher, daemon=True, name="SharedPasteReqWatcher").start()
        while True:
            try:
                sa = _low_il_everyone_sa()
                pipe_handle = win32pipe.CreateNamedPipe(
                    r"\\.\pipe\RemoteDesktopClipboardUpPipe",
                    win32pipe.PIPE_ACCESS_INBOUND,
                    win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
                    win32pipe.PIPE_UNLIMITED_INSTANCES,
                    65536, 65536, 0, sa
                )
                if pipe_handle != -1:
                    win32pipe.ConnectNamedPipe(pipe_handle, None)
                    threading.Thread(target=self._handle_uppipe_client, args=(pipe_handle,), daemon=True).start()
            except Exception as e:
                time.sleep(1)

    def _handle_uppipe_client(self, pipe_handle):
        import win32file, json
        try:
            hr, data = win32file.ReadFile(pipe_handle, 1024 * 1024)
            if hr == 0 and data:
                raw = data.decode('utf-8').strip()
                if raw.startswith("CANCEL_TRANSFER") or raw == "CANCEL:" or raw.startswith("CANCEL:"):
                    paste_id = None
                    all_jobs = True
                    try:
                        if "|" in raw:
                            paste_id = int(raw.split("|", 1)[1].strip())
                            all_jobs = False
                    except Exception:
                        paste_id = None
                        all_jobs = True
                    log_debug("[_handle_uppipe_client] Nhận CANCEL_TRANSFER từ Clipboard Agent.")
                    print("[Clipboard] Agent hủy truyền file (nút Hủy).")
                    self.cancel_active_transfer(remote_triggered=False, paste_id=paste_id, all_jobs=all_jobs)
                    return
                if raw.startswith("COPIED_TEXT|"):
                    parts = raw.split("|", 1)
                    text = ""
                    try:
                        text = json.loads(parts[1]) if len(parts) > 1 else ""
                    except Exception:
                        text = parts[1] if len(parts) > 1 else ""
                    if text and self.active_sockets:
                        self._forward_clipboard_text(text)
                        print("[Clipboard] Host→client: đã gửi text từ Clipboard Agent.")
                    return
                # Agent hỏi ghi đè — đưa vào packet loop (headless forward → client GUI).
                if raw.startswith("CONFLICT_QUERY|"):
                    try:
                        payload = json.loads(raw.split("|", 1)[1])
                    except Exception as e:
                        log_debug(f"[_handle_uppipe_client] CONFLICT_QUERY parse: {e}")
                        return
                    try:
                        log_overwrite_conflict(
                            f"HOST_HEADLESS UpPipe CONFLICT_QUERY → enqueue "
                            f"paste_id={payload.get('paste_id')} "
                            f"n={len(payload.get('conflicts') or [])}"
                        )
                    except Exception:
                        pass
                    self.enqueue_packet({
                        "type": "paste_conflict_query",
                        "paste_id": payload.get("paste_id"),
                        "conflicts": payload.get("conflicts") or [],
                        "has_multiple": bool(payload.get("has_multiple")),
                    })
                    return
                # Clipboard Agent gửi REQUEST_FILES khi người dùng thực hiện Paste
                if raw.startswith("REQUEST_FILES"):
                    log_debug("[_handle_uppipe_client] Nhận REQUEST_FILES từ Clipboard Agent. Bắt đầu tải file...")
                    print("[Clipboard] Clipboard Agent yêu cầu tải file (người dùng đã Paste).")
                    try:
                        log_overwrite_conflict(
                            f"HOST_HEADLESS recv REQUEST_FILES raw_len={len(raw)} "
                            f"(neu truoc do khong co DIALOG SHOWN=YES / conflict_check → bug)"
                        )
                    except Exception:
                        pass
                    
                    parts = raw.split("|", 1)
                    requested_files = []
                    dest_dir = None
                    paste_id = None
                    if len(parts) > 1 and parts[1].strip():
                        try:
                            import json
                            payload = json.loads(parts[1])
                            if isinstance(payload, dict):
                                requested_files = payload.get("files") or []
                                dest_dir = payload.get("dest_dir") or None
                                paste_id = payload.get("paste_id")
                            elif isinstance(payload, list):
                                requested_files = payload
                        except Exception as e:
                            log_debug(f"[_handle_uppipe_client] Lỗi parse requested_files: {e}")
                    if paste_id is not None:
                        try:
                            self._clipboard_paste_id = int(paste_id)
                        except Exception:
                            pass
                            
                    if not requested_files:
                        requested_files = self.pending_remote_files

                    if requested_files:
                        tok = int(getattr(self, "_clipboard_paste_id", 0) or 0)
                        if tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
                            print(f"[FileTransfer] Bo REQUEST_FILES paste_id={tok} (blacklist Huy).")
                            return
                        files_req = list(requested_files)
                        now = time.time()
                        last_req_time = float(getattr(self, "_last_request_files_time", 0.0) or 0.0)
                        last_req_tok = getattr(self, "_last_request_files_tok", None)
                        last_req_files = getattr(self, "_last_request_files_list", None)
                        if (tok and tok == last_req_tok and (now - last_req_time) < 5.0) or (
                            (now - last_req_time) < 10.0 and files_req == last_req_files
                        ):
                            log_debug(
                                f"[_handle_uppipe_client] Bo REQUEST_FILES trung lap tok={tok} (elapsed={now - last_req_time:.2f}s)."
                            )
                            print(f"[FileTransfer] Bo REQUEST_FILES trung lap tok={tok} (elapsed={now - last_req_time:.2f}s).")
                            return
                        self._last_request_files_time = now
                        self._last_request_files_tok = tok
                        self._last_request_files_list = files_req
                        expected = getattr(self, "_xfer_expected_files", None)
                        if expected is None:
                            self._xfer_expected_files = {}
                            expected = self._xfer_expected_files
                        if tok:
                            expected[tok] = files_req
                        # Client→host: nhận vào staging. KHÔNG gắn dest Explorer vào
                        # job nhận — nếu gắn, promote/relocate sẽ ghi vào đích trước khi
                        # agent hỏi Replace. Agent đã có job["dest"] + replace_keys.
                        if dest_dir and os.path.isdir(dest_dir) and not _is_transfer_staging_dir(dest_dir):
                            log_debug(
                                f"[_handle_uppipe_client] dest ghi nhan paste_id={tok}: {dest_dir} "
                                f"(giu staging, khong promote)"
                            )
                        living = bool(getattr(self, "_xfer_jobs", None))
                        if not living:
                            self.target_save_dir = HEADLESS_TRANSFER_DIR if (
                                self.app and getattr(self.app, "is_headless", False)
                            ) else getattr(self, "target_save_dir", None)
                        # Không ghi đè pending_remote_files — đó là copy mới nhất trên clipboard, không phải file đang Paste.
                        # Đây là nhận file (agent Paste trên host), không arm send-id — tránh phantom _active_send_ids.
                        self._allow_file_xfer = True
                        self._send_cancelled = False
                        self._receive_cancelled = False
                        threading.Thread(
                            target=self.request_pending_files,
                            args=(files_req, tok),
                            daemon=True,
                        ).start()
                    else:
                        log_debug("[_handle_uppipe_client] Không có pending_remote_files để tải.")
                        if self.app and getattr(self.app, 'is_headless', False):
                            self._send_progress_signal("CANCEL", "")
                            self._close_transfer_pipe()
                else:
                    # Metadata file do Clipboard Agent gửi lên (copy file từ phía user)
                    if raw.startswith("COPIED_FILES|"):
                        parts = raw.split("|", 1)
                        offer_id = None
                        paths = json.loads(parts[1]) if len(parts) > 1 else []
                        if isinstance(paths, dict):
                            offer_id = paths.get("offer_id")
                            paths = paths.get("files") or []
                        metadata = []
                        for f in paths:
                            try:
                                if os.path.isfile(f):
                                    metadata.append({
                                        "name": os.path.basename(f),
                                        "path": f,
                                        "size": os.path.getsize(f) if os.path.exists(f) else 0,
                                        "mtime": os.path.getmtime(f) if os.path.exists(f) else 0
                                    })
                                elif os.path.isdir(f):
                                    parent_dir = os.path.dirname(f)
                                    for root, _, files in os.walk(f):
                                        for file in files:
                                            full_path = os.path.join(root, file)
                                            rel_path = os.path.relpath(full_path, parent_dir).replace('\\', '/')
                                            sz = 0
                                            mt = 0
                                            try:
                                                sz = os.path.getsize(full_path)
                                                mt = os.path.getmtime(full_path)
                                            except Exception:
                                                pass
                                            metadata.append({
                                                "name": rel_path,
                                                "path": full_path,
                                                "size": sz,
                                                "mtime": mt
                                            })
                            except Exception as ex_stat:
                                log_debug(f"[_handle_uppipe_client] Lỗi đọc path {f}: {ex_stat}")
                    else:
                        metadata = json.loads(raw)
                        offer_id = None
                    if metadata and self.active_sockets:
                        self._clip_offer_id = int(getattr(self, "_clip_offer_id", 0) or 0) + 1
                        oid = int(offer_id or 0) or self._clip_offer_id
                        names = [m.get("name") for m in metadata[:8]]
                        try:
                            from utils.logger import clip_trace
                            clip_trace(f"[host] SEND files_copied_meta offer={oid} n={len(metadata)} {names}")
                        except Exception:
                            pass
                        pkt = json.dumps({
                            "type": "files_copied_meta",
                            "files": metadata,
                            "offer_id": oid,
                        }).encode('utf-8')
                        with self.lock:
                            for s in list(self.active_sockets):
                                try: send_msg(s, pkt)
                                except: pass
                        print(f"[Clipboard] Host→client files_copied_meta offer={oid}: {names}")
        except Exception as e:
            log_debug(f"[_handle_uppipe_client] Lỗi: {e}")
        finally:
            try:
                win32file.CloseHandle(pipe_handle)
            except: pass


    def _send_progress_signal(self, data_type, payload):
        """PROGRESS/FILES/CANCEL đi cùng pipe persistent xuống agent."""
        self._send_to_pipe(data_type, payload)

    def _close_transfer_pipe(self):
        # Không ngắt pipe sau mỗi lần tải — agent giữ kết nối để PENDING lần sau hiện Paste ngay.
        return

    def _send_to_pipe(self, data_type, payload):
        """Gửi TYPE:payload xuống Clipboard Agent qua pipe giữ kết nối."""
        self._ensure_down_pipe()
        self._down_pipe_q.put((data_type, payload))
        log_debug(f"[_send_to_pipe] Hàng đợi {data_type} ({len(str(payload))} bytes).")
        if data_type == "PENDING":
            try:
                log_overwrite_conflict(
                    f"HOST_HEADLESS queue PENDING to agent ({len(str(payload))} bytes)"
                )
            except Exception:
                pass

    def _repush_pending_offer_to_agent(self, reason=""):
        """Gửi lại PENDING xuống agent nếu headless đang giữ offer client→host."""
        if not (self.app and getattr(self.app, "is_headless", False)):
            return
        files = list(
            getattr(self, "pending_remote_files", None)
            or getattr(self, "_reoffer_files", None)
            or []
        )
        if not files:
            try:
                log_overwrite_conflict(f"HOST_HEADLESS repush skip (no offer) reason={reason}")
            except Exception:
                pass
            return
        total_size = sum((f.get("size", 0) if isinstance(f, dict) else 0) for f in files)
        item_kind, display_name = _copy_batch_kind_and_name(files, _("Tệp tin"))
        oid = int(getattr(self, "_clip_offer_applied", 0) or 0)
        msg_dict = {
            "display_name": display_name,
            "item_kind": item_kind,
            "total_size": total_size,
            "files": files,
            "offer_id": oid,
        }
        names = [f.get("name") if isinstance(f, dict) else str(f) for f in files[:8]]
        try:
            log_overwrite_conflict(
                f"HOST_HEADLESS REPUSH PENDING reason={reason} offer={oid} "
                f"n={len(files)} names={names}"
            )
        except Exception:
            pass
        self._send_to_pipe("PENDING", json.dumps(msg_dict))

    def _ensure_down_pipe(self):
        if getattr(self, "_down_pipe_started", False):
            return
        self._down_pipe_started = True
        threading.Thread(target=self._down_pipe_loop, daemon=True, name="ClipDownPipe").start()

    def _down_pipe_loop(self):
        """Giữ 1 kết nối Named Pipe xuống agent — không tạo/đóng pipe mỗi lần PENDING (trễ 0.5–1.5s)."""
        while True:
            pipe_handle = None
            try:
                pipe_handle = create_named_pipe_with_everyone_dacl()
                if pipe_handle is None or pipe_handle == -1:
                    time.sleep(0.15)
                    continue
                log_debug("[_down_pipe_loop] Đang chờ Clipboard Agent kết nối...")
                try:
                    log_overwrite_conflict("HOST_HEADLESS DownPipe WAITING for agent to connect...")
                except Exception:
                    pass
                try:
                    win32pipe.ConnectNamedPipe(pipe_handle, None)
                except Exception as ce:
                    err = getattr(ce, "winerror", 0) or (ce.args[0] if ce.args else 0)
                    if err != 535:
                        raise
                log_debug("[_down_pipe_loop] Agent đã kết nối. Giữ pipe để gửi PENDING/TEXT.")
                try:
                    log_overwrite_conflict("HOST_HEADLESS DownPipe AGENT CONNECTED — flush PENDING if any")
                except Exception:
                    pass
                # Agent mới (sau cài/restart) — gửi lại offer đang giữ, tránh paste client→host mất PENDING.
                try:
                    self._repush_pending_offer_to_agent("down_pipe_connected")
                except Exception as re:
                    log_debug(f"[_down_pipe_loop] repush PENDING: {re}")
                while True:
                    data_type, payload = self._down_pipe_q.get()
                    msg = f"{data_type}:{payload}\x00"
                    try:
                        win32file.WriteFile(pipe_handle, msg.encode("utf-8"))
                        if data_type == "PENDING":
                            try:
                                log_overwrite_conflict(
                                    f"HOST_HEADLESS WriteFile PENDING OK ({len(msg)} bytes) → agent"
                                )
                            except Exception:
                                pass
                    except Exception as we:
                        log_debug(f"[_down_pipe_loop] WriteFile lỗi: {we}")
                        try:
                            log_overwrite_conflict(f"HOST_HEADLESS WriteFile {data_type} FAIL: {we}")
                        except Exception:
                            pass
                        try:
                            self._down_pipe_q.put((data_type, payload))
                        except Exception:
                            pass
                        break
            except Exception as e:
                log_debug(f"[_down_pipe_loop] {e}")
                try:
                    log_overwrite_conflict(f"HOST_HEADLESS DownPipe LOOP EXCEPTION: {e}")
                except Exception:
                    pass
            finally:
                if pipe_handle is not None and pipe_handle != -1:
                    try:
                        win32file.FlushFileBuffers(pipe_handle)
                    except Exception:
                        pass
                    try:
                        win32pipe.DisconnectNamedPipe(pipe_handle)
                    except Exception:
                        pass
                    try:
                        win32file.CloseHandle(pipe_handle)
                    except Exception:
                        pass
            time.sleep(0.05)

    def _send_path_to_pipe(self, file_path):
        """
        Gửi đường dẫn file qua Named Pipe cho Clipboard Agent.
        """
        self._send_to_pipe("FILE", file_path)

    def _schedule_copied_files_sync(self):
        """Đọc file list sau khi seq clipboard ổn định; không gửi list cũ khi user đã copy file mới."""
        gen = getattr(self, "_clip_sync_gen", 0) + 1
        self._clip_sync_gen = gen
        old = getattr(self, "_clip_sync_timer", None)
        if old is not None:
            try:
                old.cancel()
            except Exception:
                pass

        is_client = bool(getattr(self, "pygame_hwnd", None) or getattr(self, "is_client", False))

        def _pass(g=gen, tries=0):
            if g != getattr(self, "_clip_sync_gen", 0):
                return
            seq_before = get_clipboard_sequence_number()
            # Client ưu tiên CIDA; nếu rỗng thì đọc HDROP (Win11 Explorer đôi khi thiếu Shell IDList).
            files = get_clipboard_files(retries=1, allow_hdrop=not is_client)
            if is_client and not files:
                files = get_clipboard_files(retries=2, allow_hdrop=True)
            seq_after = get_clipboard_sequence_number()
            if seq_before and seq_after and seq_before != seq_after and tries < 4:
                t = threading.Timer(0.12, lambda: _pass(g, tries + 1))
                t.daemon = True
                t.start()
                self._clip_sync_timer = t
                return
            if files:
                probe_dir_abs = os.path.abspath(_PROBE_STUB_DIR).lower()
                if any(os.path.abspath(f).lower().startswith(probe_dir_abs) or _is_probe_stub_name(f) for f in files):
                    return
                fp = tuple(os.path.abspath(f).lower() for f in files)
                last_fp = getattr(self, "_last_sent_file_fp", None)
                last_seq = getattr(self, "_last_sent_file_seq", None)
                # Trùng file + chưa đổi seq clipboard → không gửi lại (tránh offer 2,3,4 spam).
                if last_fp and fp == last_fp and (not seq_after or seq_after == last_seq):
                    return
                if last_fp and fp == last_fp and seq_after and seq_after != last_seq and tries < 4:
                    t = threading.Timer(0.12, lambda: _pass(g, tries + 1))
                    t.daemon = True
                    t.start()
                    self._clip_sync_timer = t
                    return
                if is_client:
                    try:
                        log_overwrite_conflict(
                            f"CLIENT clip_sync files n={len(files)} "
                            f"names={[os.path.basename(f) for f in files[:8]]}"
                        )
                    except Exception:
                        pass
                self._process_clipboard_change(provided_files=files, force=True)
                return
            if is_client and tries < 2:
                t = threading.Timer(0.18, lambda: _pass(g, tries + 1))
                t.daemon = True
                t.start()
                self._clip_sync_timer = t
                return
            if is_client:
                try:
                    log_overwrite_conflict(
                        f"CLIENT clip_sync EMPTY after retries "
                        f"(khong gui files_copied_meta — Paste host se khong co PENDING)"
                    )
                except Exception:
                    pass

        t = threading.Timer(0.22, lambda: _pass(gen, 0))
        t.daemon = True
        t.start()
        self._clip_sync_timer = t

    def _attach_xfer_id(self, payload, xfer_id, paste_id=None):
        payload["xfer_id"] = xfer_id
        if paste_id is not None:
            payload["paste_id"] = paste_id
        return payload

    def _xfer_packet_ok(self, packet, ptype):
        xid = packet.get("xfer_id")
        aborted = getattr(self, "_aborted_xfer_ids", None) or set()
        if xid is not None and xid in aborted:
            return False
        return True

    def _ensure_send_worker(self):
        with self._send_worker_boot_lock:
            if getattr(self, "_send_worker_started", False):
                return
            self._send_worker_started = True
            threading.Thread(target=self._send_job_loop, daemon=True, name="ClipSendQ").start()

    def _enqueue_send_job(self, files, my_id, paste_id):
        """Hàng đợi FIFO — paste trước gửi xong mới tới paste sau (không tranh băng thông)."""
        self._ensure_send_worker()
        files_list = list(files or [])
        try:
            tok = int(paste_id or 0)
        except Exception:
            tok = 0
        send_dlg_id = tok or my_id
        active_n = len(getattr(self, "_active_send_ids", None) or [])
        # Đang có batch khác trên dây / trong hàng → dialog này chờ lượt.
        waiting = self._send_job_q.qsize() > 0 or active_n > 1
        # Không mở dialog tiến trình ở phía gửi (Client) — phía nhận (Host)
        # đã có ClipboardAgent hiển thị dialog với Thư mục đích. Mở ở cả 2 phía sẽ làm xuất hiện 2 dialog cho 1 file.
        self._send_job_q.put({
            "files": files_list,
            "my_id": my_id,
            "paste_id": paste_id,
        })
        print(f"[FileTransfer] Xep hang gui FIFO paste_id={paste_id} xfer_id={my_id} (cho={self._send_job_q.qsize()})")

    def _send_job_loop(self):
        """Một lúc chỉ gửi một batch — paste sau đợi paste trước xong."""
        while True:
            job = self._send_job_q.get()
            if job is None:
                break
            paste_id = job.get("paste_id")
            my_id = job.get("my_id")
            try:
                tok = int(paste_id or 0)
            except Exception:
                tok = 0
            cancelled = getattr(self, "_cancelled_paste_ids", None) or set()
            if tok and tok in cancelled:
                print(f"[FileTransfer] Bo hang doi paste_id={tok} (da Huy).")
                try:
                    getattr(self, "_active_send_ids", set()).discard(my_id)
                except Exception:
                    pass
                try:
                    self.close_dialog(job_id=tok or my_id, reason="bo hang doi da huy")
                except Exception:
                    pass
                continue
            sock = self._live_xfer_sock()
            if not sock:
                for _ in range(240):
                    if tok and tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
                        break
                    if self._send_should_stop(my_id):
                        break
                    sock = self._live_xfer_sock()
                    if sock:
                        break
                    time.sleep(0.25)
            if not sock:
                print("[FileTransfer] Bo hang doi — khong co socket sau khi cho reconnect.")
                try:
                    getattr(self, "_active_send_ids", set()).discard(my_id)
                except Exception:
                    pass
                try:
                    self.close_dialog(job_id=tok or my_id, reason="khong co socket")
                except Exception:
                    pass
                continue
            print(f"[FileTransfer] Bat dau gui FIFO paste_id={tok} xfer_id={my_id}")
            try:
                try:
                    self.gui_queue.put(("status", (file_download_dialog_title(), tok or my_id)))
                except Exception:
                    pass
                with self._send_run_lock:
                    self._process_send_requests(sock, job.get("files") or [], my_id, tok)
            except Exception as e:
                print(f"[FileTransfer] Loi hang doi gui: {e}")

    def _process_send_requests(self, sock, files, my_id=None, paste_id=None):
        if my_id is None:
            my_id = getattr(self, "_send_xfer_id", 0)
        if paste_id is None:
            paste_id = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        if not getattr(self, "_allow_file_xfer", False):
            print("[FileTransfer] Bo qua gui file (allow_file_xfer=False).")
            return
        if self._send_should_stop(my_id):
            print("[FileTransfer] Huy luc bat dau gui — khong gui.")
            return
        self.transfer_in_progress = True
        print(f"[FileTransfer] Bat dau gui {len(files)} file xfer_id={my_id} paste_id={paste_id}")
        log_debug(f"[_process_send_requests] Khởi chạy gửi {len(files)} file... xfer_id={my_id}")
        show_send_dlg = False
        send_dlg_id = my_id
        total_size = 0
        try:
            total_size = sum(f.get("size", 0) for f in files)
            item_kind, display_name = _copy_batch_kind_and_name(files, _("Tệp tin"))
            self.batch_display_name = display_name
            self.batch_item_kind = item_kind
            
            log_file_transfer(display_name, total_size)
            
            start_pkt = json.dumps(self._attach_xfer_id({
                "type": "batch_start",
                "count": len(files),
                "total_size": total_size,
                "display_name": display_name,
                "item_kind": item_kind,
                "paste_id": paste_id,
            }, my_id, paste_id)).encode('utf-8')
            self._xfer_need_resync = False
            # Phía gửi không mở dialog tiến trình (phía nhận đã mở dialog tại thư mục đích).
            send_dlg_id = int(paste_id or 0) or my_id
            show_send_dlg = False
            if not self._send_file_msg(sock, start_pkt, my_id):
                print("[FileTransfer] Huy truoc/luc batch_start — dung gui.")
                if show_send_dlg:
                    try:
                        self.close_dialog(job_id=send_dlg_id, reason="huy truoc batch_start")
                    except Exception:
                        pass
                return
            log_debug(f"[_process_send_requests] Đã gửi batch_start. total_size={total_size}")
            
            total_sent = 0
            batch_start_time = time.time()
            last_dlg_at = 0.0

            def _lookup_resume_offset(state, name, size):
                fmap = (state or {}).get("files") or {}
                key = str(name or "").replace("\\", "/")
                val = fmap.get(key)
                if val is None:
                    val = fmap.get(name)
                if val is None:
                    val = fmap.get(os.path.basename(key))
                try:
                    already = int(val or 0)
                except Exception:
                    already = 0
                try:
                    size = int(size or 0)
                except Exception:
                    size = 0
                return max(0, min(already, size)) if size else max(0, already)

            for f in files:
                if self._send_should_stop(my_id):
                    log_debug(f"[_process_send_requests] Truyền tải bị hủy ngang.")
                    break
                if isinstance(f, dict):
                    filepath = f.get("path") or f.get("name")
                    filename = f.get("name") or os.path.basename(filepath or "")
                    file_size = f.get("size", 0)
                elif isinstance(f, str):
                    filepath = f
                    filename = os.path.basename(f)
                    file_size = os.path.getsize(f) if os.path.exists(f) else 0
                else:
                    continue
                if not filepath or not filename:
                    continue
                
                log_debug(f"[_process_send_requests] Kiểm tra filepath: {filepath}")
                if not os.path.exists(filepath):
                    log_debug(f"[_process_send_requests] File không tồn tại: {filepath}")
                    continue
                if self._send_should_stop(my_id):
                    log_debug(f"[_process_send_requests] Truyền tải bị hủy ngang.")
                    break
                f_start_pkt = json.dumps(self._attach_xfer_id({
                    "type": "file_start", "name": filename, "size": file_size, "offset": 0
                }, my_id, paste_id)).encode('utf-8')
                if not self._send_file_msg(sock, f_start_pkt, my_id):
                    log_debug(f"[_process_send_requests] Truyền tải bị hủy ngang.")
                    break
                log_debug(f"[_process_send_requests] Đã gửi file_start cho {filename}, size={file_size}")
                file_sent_bytes = 0
                try:
                    live = self._live_xfer_sock() or sock
                    lan = is_lan_socket(live)
                    if lan:
                        tune_socket_for_lan_bulk(live)
                    chunk_size = 64 * 1024
                    file_sent_bytes = 0
                    file_start_time = time.time()
                    
                    with open(filepath, "rb") as fh:
                        while True:
                            if self._send_should_stop(my_id):
                                print("[FileTransfer] Huy — dung doc file phia client.")
                                break

                            if getattr(self, "_xfer_need_resync", False):
                                self._xfer_need_resync = False
                                state = self._query_resume_state(my_id, paste_id, timeout=6.0)
                                if not state.get("has_job"):
                                    print("[FileTransfer] May nhan mat job — gui lai batch_start.")
                                    if not self._send_file_msg(sock, start_pkt, my_id):
                                        break
                                already = _lookup_resume_offset(state, filename, file_size)
                                print(f"[FileTransfer] Resume {filename} offset {file_sent_bytes} -> {already}")
                                try:
                                    fh.seek(already)
                                except Exception:
                                    fh.seek(0)
                                    already = 0
                                file_sent_bytes = already
                                live = self._live_xfer_sock() or sock
                                lan = is_lan_socket(live)
                                if lan:
                                    tune_socket_for_lan_bulk(live)
                                resume_start = json.dumps(self._attach_xfer_id({
                                    "type": "file_start", "name": filename, "size": file_size, "offset": already
                                }, my_id, paste_id)).encode('utf-8')
                                if not self._send_file_msg(sock, resume_start, my_id):
                                    break
                                continue
                            
                            if not lan:
                                elapsed_total = time.time() - batch_start_time
                                current_limit = 500 * 1024 + int(500 * 1024 * elapsed_total)
                                max_limit = 1000 * 1024 * 1024
                                if current_limit > max_limit:
                                    current_limit = max_limit
                            else:
                                current_limit = None
                                
                            chunk_data = fh.read(chunk_size)
                            if not chunk_data:
                                break
                            if self._send_should_stop(my_id):
                                print("[FileTransfer] Huy sau read — khong encode/gui chunk tiep.")
                                break
                                
                            chunk_offset = file_sent_bytes
                            b64 = base64.b64encode(chunk_data).decode('utf-8')
                            if not self._send_file_msg(sock, json.dumps(self._attach_xfer_id({
                                "type": "file_chunk", "name": filename, "data": b64, "offset": chunk_offset
                            }, my_id, paste_id)).encode('utf-8'), my_id):
                                print("[FileTransfer] Huy luc gui — dong file, ngung doc.")
                                break
                            
                            file_sent_bytes += len(chunk_data)
                            total_sent += len(chunk_data)
                            if show_send_dlg:
                                now = time.time()
                                if (now - last_dlg_at) >= 0.05 or total_sent >= total_size:
                                    last_dlg_at = now
                                    try:
                                        self.update_dialog(total_sent, job_id=send_dlg_id)
                                    except Exception:
                                        pass
                            
                            if current_limit:
                                target_time = file_sent_bytes / current_limit
                                actual_time = time.time() - file_start_time
                                if actual_time < target_time:
                                    sleep_dur = target_time - actual_time
                                    if sleep_dur > 2.0:
                                        sleep_dur = 2.0
                                        
                                    sleep_end = time.time() + sleep_dur
                                    while time.time() < sleep_end:
                                        if self._send_should_stop(my_id):
                                            break
                                        time.sleep(0.05)
                                    
                    log_debug(f"[_process_send_requests] Đã gửi xong dữ liệu cho {filename} ({file_sent_bytes}/{file_size})")
                except Exception as e:
                    print(f"[FileTransfer] Lỗi khi gửi file {filename}: {e}")
                    log_debug(f"[_process_send_requests] Lỗi khi gửi file {filename}: {e}")
                    
                if self._send_should_stop(my_id):
                    break
                if file_sent_bytes < int(file_size or 0):
                    print(f"[FileTransfer] {filename} chua du ({file_sent_bytes}/{file_size}) — khong gui file_end.")
                    self._xfer_need_resync = True
                    break
                if self._send_file_msg(sock, json.dumps(self._attach_xfer_id({
                    "type": "file_end", "name": filename
                }, my_id, paste_id)).encode('utf-8'), my_id):
                    log_debug(f"[_process_send_requests] Đã gửi file_end cho {filename}")
                else:
                    print(f"[FileTransfer] {filename} gui file_end that bai.")
                    break
            else:
                # for-loop hết file (không break) — chỉ lúc này mới batch_end.
                if not self._send_should_stop(my_id):
                    if self._send_file_msg(sock, json.dumps(self._attach_xfer_id({"type": "batch_end"}, my_id, paste_id)).encode('utf-8'), my_id):
                        log_debug(f"[_process_send_requests] Đã gửi batch_end.")
                    try: log_activity(_("Truyền file: ") + str(self.batch_display_name) + " - " + str(total_size) + _(" byte - Thành công"))
                    except: pass
                    if show_send_dlg:
                        try:
                            self.update_dialog(total_size or total_sent, job_id=send_dlg_id)
                            self.complete_dialog(job_id=send_dlg_id)
                            self.close_dialog(job_id=send_dlg_id, reason="gui xong client→host")
                        except Exception:
                            pass
                else:
                    print("[FileTransfer] Huy — khong gui batch_end.")
                    if show_send_dlg:
                        try:
                            self.close_dialog(job_id=send_dlg_id, reason="huy giua gui")
                        except Exception:
                            pass
            if self._send_should_stop(my_id):
                print("[FileTransfer] Gui dung giua chung — khong gui batch_end.")
                if show_send_dlg:
                    try:
                        self.close_dialog(job_id=send_dlg_id, reason="huy giua gui")
                    except Exception:
                        pass
            elif show_send_dlg and send_dlg_id in (getattr(self, "xfer_dialogs", None) or {}):
                try:
                    self.close_dialog(job_id=send_dlg_id, reason="gui dut giua")
                except Exception:
                    pass
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"Error processing send request: {e}")
            log_debug(f"[_process_send_requests] Lỗi tổng quát:\n{tb}")
            try:
                log_activity(_("Truyền file: ") + str(self.batch_display_name) + " - " + str(total_size) + _(" byte - Thất bại"))
            except: pass
            if show_send_dlg:
                try:
                    self.close_dialog(job_id=send_dlg_id, reason="loi gui")
                except Exception:
                    pass
        finally:
            try:
                getattr(self, "_active_send_ids", set()).discard(my_id)
            except Exception:
                pass
            if not getattr(self, "_active_send_ids", None):
                self.transfer_in_progress = False
            log_debug(f"[_process_send_requests] Kết thúc hàm gửi file xfer_id={my_id}.")



def run_clipboard_agent_mode():
    """
    Chế độ Clipboard Agent: Chạy ở quyền User thường.
    Lắng nghe Named Pipe từ Service/headless app để nhận đường dẫn file
    và nạp vào Clipboard hệ thống.
    
    Kiến trúc: App Headless (SYSTEM) -> Named Pipe -> App ClipboardAgent (User) -> Clipboard
    """
    import logging
    import queue
    import win32file
    import win32pipe
    import win32event
    import win32api
    import time
    import tkinter as tk
    
    from utils.logger import ensure_utf8_bom, get_log_filepath
    log_path = get_log_filepath("clipboard_agent.log")
    agent_log = logging.getLogger("clipboard_agent")
    agent_log.setLevel(logging.DEBUG)
    
    # Xoá các handler cũ nếu có để tránh ghi lặp
    for h in list(agent_log.handlers):
        agent_log.removeHandler(h)
        
    formatter = logging.Formatter("[%(asctime)s] [PID %(process)d] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    
    fh = None
    try:
        ensure_utf8_bom(log_path)
        fh = logging.FileHandler(log_path, encoding="utf-8-sig")
    except Exception:
        pass
    if fh is not None:
        fh.setFormatter(formatter)
        agent_log.addHandler(fh)
    
    # Chỉ ghi ra console nếu stdout không phải là chính file log đó (tránh lặp 2 dòng trong file)
    is_stdout_log = False
    try:
        if sys.stdout and hasattr(sys.stdout, 'name'):
            is_stdout_log = (os.path.abspath(sys.stdout.name) == os.path.abspath(log_path))
    except:
        pass
        
    if not is_stdout_log and sys.stdout:
        import io; sh = logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')) if hasattr(sys.stdout, 'buffer') else logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        agent_log.addHandler(sh)

    def agent_print(msg):
        agent_log.info(msg)

    agent_print("=" * 60)
    agent_print(f"[ClipboardAgent] Khởi động. PID: {os.getpid()}")
    agent_print(f"[ClipboardAgent] Thư mục ứng dụng: {app_dir}")
    try:
        from utils.logger import get_log_filepath
        ow_path = get_log_filepath("overwrite_conflict.log")
        agent_print(f"[ClipboardAgent] Overwrite conflict log: {ow_path}")
        log_overwrite_conflict(f"AGENT START pid={os.getpid()} log={ow_path}")
    except Exception:
        pass
    agent_print("=" * 60)

    pipe_name = CLIPBOARD_PIPE_NAME
    gui_queue = queue.Queue()

    def pipe_listener_loop():
        while True:
            pipe_handle = None
            try:
                agent_print(f"[ClipboardAgent] Đang chờ kết nối tới Pipe: {pipe_name}")
                _last_err_logged = None
                _err_count = 0
                while True:
                    try:
                        pipe_handle = win32file.CreateFile(
                            pipe_name,
                            win32file.GENERIC_READ,
                            0,
                            None,
                            win32file.OPEN_EXISTING,
                            0,
                            None
                        )
                        break
                    except Exception as ex:
                        err = getattr(ex, 'winerror', 0) or (ex.args[0] if ex.args else 0)
                        if err != 2:  # 2 = ERROR_FILE_NOT_FOUND (pipe server chưa tạo)
                            if err != _last_err_logged or _err_count % 100 == 0:
                                _last_err_logged = err
                                agent_print(f"[ClipboardAgent] CreateFile Pipe loi (winerror={err}): {ex}")
                                try:
                                    log_overwrite_conflict(f"AGENT PIPE CreateFile FAIL winerror={err}: {ex}")
                                except Exception:
                                    pass
                        _err_count += 1
                        time.sleep(0.05)

                agent_print(f"[ClipboardAgent] Đã kết nối thành công tới Pipe.")
                try:
                    log_overwrite_conflict("AGENT PIPE CONNECTED (cho PENDING client→host)")
                except Exception:
                    pass

                try:
                    win32pipe.SetNamedPipeHandleState(
                        pipe_handle,
                        win32pipe.PIPE_READMODE_MESSAGE,
                        None,
                        None
                    )
                except Exception as se:
                    agent_print(f"[ClipboardAgent] Cảnh báo SetNamedPipeHandleState: {se}. Tiếp tục ở chế độ byte mode.")

                buffer = bytearray()
                while True:
                    try:
                        hr, data = win32file.ReadFile(pipe_handle, 10 * 1024 * 1024)
                        if hr == 0:
                            buffer.extend(data)
                            while b"\x00" in buffer:
                                idx = buffer.index(b"\x00")
                                msg_bytes = buffer[:idx]
                                del buffer[:idx + 1]
                                msg = msg_bytes.decode("utf-8").strip()
                                if msg:
                                    agent_print(f"[ClipboardAgent] Nhận tin nhắn từ Pipe (độ dài {len(msg)}): {msg[:100]}...")
                                    if msg.startswith("TEXT:"):
                                        gui_queue.put(("text", msg[5:]))
                                    elif msg.startswith("FILES:"):
                                        gui_queue.put(("files_ready", msg[6:]))
                                    elif msg.startswith("PENDING:"):
                                        try:
                                            log_overwrite_conflict(
                                                f"AGENT PIPE recv PENDING raw_len={len(msg)}"
                                            )
                                        except Exception:
                                            pass
                                        try:
                                            import json
                                            info = json.loads(msg[8:])
                                            try:
                                                _pending_info.clear()
                                                if isinstance(info, dict):
                                                    _pending_info.update(info)
                                                    files = info.get("files")
                                                    if isinstance(files, list):
                                                        _pending_info["files"] = [dict(f) if isinstance(f, dict) else f for f in files]
                                                flist = _pending_info.get("files") or []
                                                try:
                                                    from os_utils.windows_clipboard import clipboard_sync_manager
                                                    if clipboard_sync_manager:
                                                        clipboard_sync_manager.pending_remote_files = list(flist)
                                                        clipboard_sync_manager._reoffer_files = list(flist)
                                                        clipboard_sync_manager._allow_delayed = True
                                                        clipboard_sync_manager._force_delayed_setup = True
                                                        clipboard_sync_manager.meta_arrival_time = time.time()
                                                        clipboard_sync_manager._expect_repaste_until = time.time() + 86400.0
                                                except Exception:
                                                    pass
                                            except Exception:
                                                pass
                                            gui_queue.put(("pending", info))
                                        except Exception as e:
                                            agent_print(f"[ClipboardAgent] Lỗi parse PENDING JSON: {e}")
                                            try:
                                                log_overwrite_conflict(f"AGENT PIPE PENDING parse FAIL: {e}")
                                            except Exception:
                                                pass
                                    elif msg.startswith("PROGRESS:"):
                                        try:
                                            rest = msg[9:]
                                            if "|" in rest:
                                                pid_s, nbytes_s = rest.split("|", 1)
                                                gui_queue.put(("progress", (int(pid_s), int(nbytes_s))))
                                            else:
                                                gui_queue.put(("progress", int(rest)))
                                        except:
                                            pass

                                    elif msg.startswith("START:"):
                                        rest = msg[6:].strip()
                                        try:
                                            parts = rest.split("|")
                                            disp_name = parts[0] if len(parts) > 0 else ""
                                            tot_sz = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                                            dst_dir = parts[2] if len(parts) > 2 and parts[2] else None
                                            pst_id = int(parts[3]) if len(parts) > 3 and parts[3] else None
                                            gui_queue.put(("start", (disp_name, tot_sz, dst_dir, pst_id)))
                                            agent_print(f"[ClipboardAgent] Pipe START: name={disp_name} size={tot_sz} paste_id={pst_id}")
                                        except Exception as e_start:
                                            agent_print(f"[ClipboardAgent] Pipe START loi: {e_start}")
                                    elif msg.startswith("END:"):
                                        rest = msg[4:].strip()
                                        pst_id = None
                                        try:
                                            if rest:
                                                pst_id = int(rest)
                                        except Exception:
                                            pst_id = None
                                        gui_queue.put(("end", pst_id))
                                        agent_print(f"[ClipboardAgent] Pipe END: paste_id={pst_id}")
                                    elif msg.startswith("CANCEL:"):
                                        rest = msg[7:].strip()
                                        pid = None
                                        try:
                                            if rest:
                                                pid = int(rest)
                                        except Exception:
                                            pid = None
                                        gui_queue.put(("pipe_cancel", pid))
                                    elif msg.startswith("CLEAR:"):
                                        gui_queue.put(("clear_clip", None))
                                    elif msg.startswith("CONFLICT_REPLY:"):
                                        # Áp ngay từ pipe thread — conflict_check đang wait Event
                                        # (không phụ thuộc poll_gui_queue, tránh deadlock).
                                        try:
                                            _apply_conflict_reply_raw(msg[15:])
                                        except Exception as e_cr:
                                            agent_print(f"[ClipboardAgent] CONFLICT_REPLY apply: {e_cr}")
                                        gui_queue.put(("conflict_reply", msg[15:]))
                                    else:
                                        agent_print(f"[ClipboardAgent] Bỏ qua tin nhắn không nhận dạng: {msg[:50]}")
                        else:
                            agent_print(f"[ClipboardAgent] ReadFile trả về mã lỗi: {hr}")
                            break
                    except Exception as read_err:
                        err_code = getattr(read_err, 'winerror', 0)
                        if err_code == 109:
                            agent_print("[ClipboardAgent] Pipe bị ngắt. Đang kết nối lại...")
                            # Khi pipe đứt (peer disconnect / session end) → xóa pending offer cũ
                            # để tránh clipboard cũ kích hoạt Paste nhầm sau khi phiên kết thúc.
                            if _pending_info:
                                _pending_info.clear()
                                agent_print("[ClipboardAgent] Đã xóa PENDING offer (pipe disconnect).")
                            _clear_agent_paste_gesture_flags(0.0)
                            # Xóa cả HDROP delayed-render trên Windows clipboard
                            # (dùng gui_queue để chạy trên GUI thread của Tkinter).
                            try:
                                gui_queue.put(("clear_clip", None))
                            except Exception:
                                pass
                            break
                        elif err_code == 234:
                            continue
                        else:
                            agent_print(f"[ClipboardAgent] Lỗi đọc Pipe: {read_err}")
                            break
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lỗi kết nối Pipe: {e}")
            finally:
                if pipe_handle is not None:
                    try:
                        win32file.CloseHandle(pipe_handle)
                    except:
                        pass
            time.sleep(0.02)
    root = tk.Tk()
    root.withdraw()
    try:
        from gui.window_icon import hide_tk_from_taskbar, set_dialog_app_icon
        hide_tk_from_taskbar(root)
        set_dialog_app_icon(root)
    except Exception:
        pass
    # Không gắn -toolwindow cho root — ProgressDialog con dễ bị ẩn / không capture. 
    active_dialog = None
    active_dialogs = {}
    _agent_jobs = {}
    _agent_req_lock = threading.Lock()
    _agent_req_q = queue.Queue()
    _agent_req_inflight = [False]
    _active_conflict_job = None
    _active_conflict_lock = threading.Lock()
    _in_poll_gui_queue = False

    def _apply_conflict_reply_raw(raw):
        """Pipe/GUI → set Event cho conflict_check đang chờ (client đã chọn Replace/Skip/Hủy)."""
        import json as _json
        try:
            data = _json.loads(raw) if isinstance(raw, str) else (raw or {})
        except Exception:
            data = {}
        try:
            pid = int((data or {}).get("paste_id") or 0)
        except Exception:
            pid = 0

        job = None
        # 1. Tra cứu theo _active_conflict_job (ưu tiên hàng đầu vì đang trực tiếp chờ reply)
        with _active_conflict_lock:
            act = _active_conflict_job
            if act:
                act_pid = int(act.get("paste_id") or 0)
                if (not pid) or pid == act_pid or act.get("ow_waiting_client"):
                    job = act

        # 2. Tra cứu theo _agent_jobs dict
        if not job and pid:
            job = _agent_jobs.get(pid)

        # 3. Fallback quét tất cả jobs đang chờ
        if not job:
            for j in list(_agent_jobs.values()):
                if j and not (j.get("conflict_reply_event") or threading.Event()).is_set():
                    if j.get("conflict_reply") is None and j.get("ow_waiting_client"):
                        job = j
                        break

        if not job:
            agent_print(f"[ClipboardAgent] CONFLICT_REPLY khong map job paste_id={pid}")
            try:
                with _active_conflict_lock:
                    act_p = _active_conflict_job.get("paste_id") if _active_conflict_job else None
                log_overwrite_conflict(
                    f"CONFLICT_REPLY no job paste_id={pid} "
                    f"active_pid={act_p} jobs_keys={list(_agent_jobs.keys())}"
                )
            except Exception:
                pass
            return False

        job["conflict_reply"] = data if isinstance(data, dict) else {}
        try:
            log_overwrite_conflict(
                f"CONFLICT_REPLY recv paste_id={job.get('paste_id')} "
                f"cancelled={bool((data or {}).get('cancelled'))} "
                f"replace={len((data or {}).get('replace_keys') or [])} "
                f"skip={len((data or {}).get('skip_keys') or [])}"
            )
        except Exception:
            pass
        try:
            ev = job.get("conflict_reply_event")
            if ev:
                ev.set()
        except Exception:
            pass
        return True

    # -----------------------------------------------------------------------
    # Delayed-rendering Win32 cho HEADLESS mode
    # -----------------------------------------------------------------------
    # Khi host gửi PENDING:, agent tạo cửa sổ ẩn và trở thành chủ sở hữu clipboard
    # với dạng delayed render (CF_HDROP = NULL). Windows sẽ gửi WM_RENDERFORMAT
    # đúng lúc người dùng thực sự Paste, lúc đó agent mới yêu cầu host tải file.
    # -----------------------------------------------------------------------
    from ctypes import wintypes

    CF_HDROP        = 15
    WM_RENDERFORMAT = 0x0305
    WM_RENDERALLFORMATS = 0x0306
    WM_DESTROYCLIPBOARD = 0x0307
    WM_USER_SETUP_DELAYED = 0x0400 + 201  # tin nhắn nội bộ để setup từ luồng khác
    WM_USER_UNBLOCK_PASTE = 0x0400 + 202  # Hủy giữa Paste: HDROP rỗng để Explorer không treo

    _agent_hwnd = None              # HWND cửa sổ ẩn của agent
    _pending_info = {}              # {'display_name': ..., 'total_size': ...}
    _agent_setup_tries = 0
    _files_ready_event = threading.Event()  # set khi host gửi FILES: xong
    _files_ready_paths = []        # các đưỜng dẫn file đã download
    _ignore_destroy = False        # tránh phản ứng WM_DESTROYCLIPBOARD do chính mình gây ra
    _is_rendering = False          # chống race condition WM_RENDERFORMAT
    
    _agent_last_lbutton_time = 0.0
    _agent_last_rbutton_time = 0.0
    _agent_last_ctrl_v_time = 0.0
    _agent_lmb_hit_context_menu = False
    _agent_lmb_menu_item_kind = ""
    _agent_lmb_menu_item_name = ""
    _agent_meta_arrival_time = 0.0
    _agent_dummy_h_active = False
    _agent_cached_explorer_path = None
    _agent_suppress_render_until = 0.0
    _agent_expect_repaste_until = 0.0
    _agent_repaste_local_by_name = {}  # basename -> abs path (Paste lại không cần tải client)
    _agent_last_copied_seq = None
    _agent_last_copied_fp = None
    _agent_offer_id = 0
    _agent_pending_offer_id = 0
    _agent_last_ctrl_c_time = 0.0
    _agent_paste_id = 0
    _agent_accept_files = False
    _agent_allow_xfer = False
    _agent_xfer_cancel_at = 0.0
    _agent_ctrl_v_held = False
    _agent_shift_ins_held = False
    _agent_download_active = False
    _agent_conflict_event = threading.Event()
    _agent_conflict_choice = "replace"
    _agent_conflict_skip = set()

    _agent_allow_delayed = True
    _agent_send_clip_timer = None
    _agent_send_clip_gen = 0
    _agent_last_sent_text = None
    _agent_clip_seq_at_pending = None
    _agent_force_delayed_setup = False
    _agent_paste_coalesce_until = 0.0
    _agent_paste_gesture_id = 0
    _agent_consumed_gesture_id = 0
    _agent_gesture_inc_at = 0.0
    _agent_last_paste_start = 0.0
    _agent_last_paste_finish_time = 0.0
    _agent_last_menu_paste_trigger_time = 0.0
    _agent_paste_trigger_lock = threading.Lock()
    _agent_lmb_held = False
    _agent_prev_lbutton_time = 0.0
    _agent_prev_lbutton_pos = (0, 0)
    _agent_last_dblclick_time = 0.0
    _agent_rmb_cursor_pos = None
    _agent_rmb_is_taskbar = False
    _agent_context_menu_seen_at = 0.0
    _agent_lmb_dismiss_at = 0.0  # Thời điểm phát hiện click ra ngoài menu để đóng nó

    def _clear_agent_paste_gesture_flags(suppress_s=1.0):
        nonlocal _agent_lmb_hit_context_menu, _agent_lmb_menu_item_kind, _agent_lmb_menu_item_name
        nonlocal _agent_rmb_cursor_pos, _agent_rmb_is_taskbar, _agent_context_menu_seen_at
        nonlocal _agent_consumed_gesture_id, _agent_suppress_render_until, _agent_lmb_dismiss_at
        _agent_lmb_hit_context_menu = False
        _agent_lmb_menu_item_kind = ""
        _agent_lmb_menu_item_name = ""
        _agent_rmb_cursor_pos = None
        _agent_rmb_is_taskbar = False
        _agent_context_menu_seen_at = 0.0
        _agent_lmb_dismiss_at = 0.0
        _agent_consumed_gesture_id = _agent_paste_gesture_id
        if suppress_s > 0:
            _agent_suppress_render_until = max(_agent_suppress_render_until, time.time() + suppress_s)

    def _note_paste_gesture():
        """Ctrl+V / click Paste — coalesced 80ms để hook+poll không đếm 2 lần."""
        nonlocal _agent_paste_gesture_id, _agent_gesture_inc_at
        now = time.time()
        if now - _agent_gesture_inc_at < 0.08:
            return
        _agent_gesture_inc_at = now
        _agent_paste_gesture_id += 1

    def _register_lmb_down():
        """Ghi nhận 1 cú nhấn chuột trái; phát hiện double-click (mở file, KHÔNG phải Paste).

        Poll 50ms và low-level hook có thể cùng báo 1 cú nhấn nên gộp trong 60ms để
        không nhầm 1 click thành double-click.
        """
        nonlocal _agent_prev_lbutton_time, _agent_prev_lbutton_pos, _agent_last_dblclick_time
        nonlocal _agent_last_lbutton_time
        now = time.time()
        if now - _agent_prev_lbutton_time < 0.06:
            _agent_last_lbutton_time = now
            return
        cx, cy = _cursor_xy()
        px, py = _agent_prev_lbutton_pos
        if (now - _agent_prev_lbutton_time) <= (_double_click_ms() / 1000.0) + 0.05 and abs(cx - px) <= 6 and abs(cy - py) <= 6:
            _agent_last_dblclick_time = now
        _agent_prev_lbutton_time = now
        _agent_prev_lbutton_pos = (cx, cy)
        _agent_last_lbutton_time = now

    def _is_recent_rmb_paste_click_unified(
        last_lbutton,
        last_rbutton,
        menu_item_kind="",
        menu_item_name="",
        last_dblclick=0.0,
        lmb_on_menu=False,
        lmb_down=False,
        menu_visible=False,
    ):
        """Hỗ trợ nhận diện click Paste sau RMB cho cả Windows 10 và Windows 11."""
        if not _is_windows_11():
            return _win10_rmb_paste_click(
                last_lbutton,
                last_rbutton,
                menu_item_kind,
                last_dblclick,
                lmb_on_menu=lmb_on_menu,
                lmb_down=lmb_down,
                menu_visible=menu_visible,
            )
        # Windows 11 XAML
        k = (menu_item_kind or "").strip().lower()
        if k == "not_paste":
            # Nếu có tên rõ ràng của mục khác (View, Sort, Refresh, Properties, New...) mới loại bỏ
            if menu_item_name and menu_item_name not in ("[xaml-not-paste]", "[xaml-pos-not_paste]", "[show-more-strip]", ""):
                return False
        now = time.time()
        last_l = float(last_lbutton or 0)
        last_r = float(last_rbutton or 0)
        if last_l <= last_r or last_r <= 0:
            return False
        if last_dblclick and (now - float(last_dblclick)) < 0.7:
            return False
        age_l = now - last_l
        age_r = now - last_r
        if not (age_l < 3.0 and 0.12 < age_r < 8.0):
            return False
        if lmb_on_menu or menu_visible or lmb_down:
            return True
        try:
            if _is_explorer_clipboard_client():
                return True
        except Exception:
            pass
        return False

    def _agent_lmb_is_context_paste(on_self):
        """Win11 XAML: hit-test menu hay fail — LMB gần chỗ RMB + PENDING = click Paste."""
        nonlocal _agent_lmb_hit_context_menu, _agent_lmb_menu_item_kind, _agent_lmb_menu_item_name
        nonlocal _agent_context_menu_seen_at, _agent_rmb_is_taskbar, _agent_rmb_cursor_pos
        nonlocal _agent_lmb_dismiss_at
        if on_self or _agent_rmb_is_taskbar:
            return False
        cx, cy = _cursor_xy()
        if _is_taskbar_or_taskmgr_at_point((cx, cy)):
            _agent_lmb_hit_context_menu = False
            _agent_lmb_menu_item_kind = ""
            _agent_lmb_menu_item_name = ""
            return False
        # Không capture menu / không ghi gesture khi chưa có offer — Win11 XAML island
        # hay bị nhận nhầm là menu (kind=unknown) → Ctrl+V/RMB paste chết.
        pend = bool(_pending_info.get("files") if _pending_info else None)
        if not pend:
            _agent_lmb_hit_context_menu = False
            _agent_lmb_menu_item_kind = ""
            _agent_lmb_menu_item_name = ""
            return False
        now = time.time()
        last_r = float(_agent_last_rbutton_time or 0)
        age_r = now - last_r
        hit_menu = _cursor_over_context_menu()
        if hit_menu:
            kind, name = _capture_menu_item_at_cursor(rmb_pos=_agent_rmb_cursor_pos)
            _agent_lmb_menu_item_kind = kind
            _agent_lmb_menu_item_name = name
            _agent_lmb_hit_context_menu = True
            agent_print(f"[ClipboardAgent] LMB menu item name={name!r} kind={kind}")
            try:
                log_overwrite_conflict(
                    f"AGENT LMB menu kind={kind!r} name={name!r} counts_paste={_menu_item_counts_as_paste(kind)}"
                )
            except Exception:
                pass
            if kind == "not_paste" and name and name not in ("[xaml-not-paste]", "[xaml-pos-not_paste]", "[show-more-strip]", ""):
                return False
            if _menu_item_counts_as_paste(kind):
                _note_paste_gesture()
                return True
            # Win11 XAML: click trên menu sau RMB (0.12 < age_r < 8.0) -> là Paste!
            if _is_windows_11() and 0.12 < age_r < 8.0:
                _agent_lmb_menu_item_kind = "paste"
                _note_paste_gesture()
                agent_print(f"[ClipboardAgent] LMB Win11 XAML menu -> paste name={name!r}")
                try:
                    log_overwrite_conflict(
                        f"AGENT LMB win11 xaml menu -> paste kind={kind!r} name={name!r} age_r={age_r:.2f}"
                    )
                except Exception:
                    pass
                return True
            # Win10: đứng trên #32768 sau RMB nhưng không đọc được chữ → vẫn là RMP.
            if (not _is_windows_11()) and 0.12 < age_r < 8.0:
                _agent_lmb_menu_item_kind = kind or "paste"
                _note_paste_gesture()
                agent_print(f"[ClipboardAgent] LMB Win10 #32768 unknown → paste name={name!r}")
                try:
                    log_overwrite_conflict(
                        f"AGENT LMB win10 classic menu → paste kind={kind!r} name={name!r} age_r={age_r:.2f}"
                    )
                except Exception:
                    pass
                return True
            return False
        rpos = _agent_rmb_cursor_pos
        near_rmb = bool(
            rpos
            and not _agent_rmb_is_taskbar
            and abs(cx - rpos[0]) <= 360
            and abs(cy - rpos[1]) <= 360
        )
        recent_dbl = bool(_agent_last_dblclick_time and (now - float(_agent_last_dblclick_time)) < 0.7)
        menu_open = False
        try:
            menu_open = _context_menu_open()
        except Exception:
            menu_open = False
        if menu_open:
            _agent_context_menu_seen_at = now
        menu_just_closed = bool(
            _agent_context_menu_seen_at
            and (now - _agent_context_menu_seen_at) < 0.7
            and not menu_open
        )
        if not (0.12 < age_r < 8.0 and not recent_dbl and (menu_open or menu_just_closed or near_rmb)):
            _agent_lmb_hit_context_menu = False
            _agent_lmb_menu_item_kind = ""
            _agent_lmb_menu_item_name = ""
            return False

        chk_kind, chk_name = _capture_menu_item_at_cursor(rmb_pos=_agent_rmb_cursor_pos)
        _agent_lmb_menu_item_name = chk_name
        if chk_kind == "not_paste" and chk_name and chk_name not in ("[xaml-not-paste]", "[xaml-pos-not_paste]", "[show-more-strip]", ""):
            _agent_lmb_hit_context_menu = False
            _agent_lmb_menu_item_kind = "not_paste"
            return False
        # Nếu menu đang mở nhưng WindowFromPoint không nhận ra cửa sổ menu (hit_menu=False),
        # kiểm tra bổ sung: cursor có nằm trong vùng rect của bất kỳ menu nào đang hiện không?
        if menu_open and not hit_menu:
            if not _cursor_within_any_visible_menu_rect(cx, cy):
                agent_print(
                    f"[ClipboardAgent] LMB cursor ngoài menu rect (cx={cx},cy={cy}) "
                    f"→ dismiss click, không phải Paste"
                )
                _agent_lmb_dismiss_at = now  # Ghi nhận thời điểm dismiss để lọc menu_just_closed
                _agent_lmb_hit_context_menu = False
                _agent_lmb_menu_item_kind = "not_paste"
                return False
        if menu_just_closed and not menu_open and not hit_menu:
            if _agent_lmb_dismiss_at and (now - _agent_lmb_dismiss_at) < 1.0:
                agent_print(
                    f"[ClipboardAgent] LMB menu_just_closed nhưng dismiss_at={now - _agent_lmb_dismiss_at:.3f}s trước "
                    f"→ không phải Paste"
                )
                _agent_lmb_hit_context_menu = False
                _agent_lmb_menu_item_kind = "not_paste"
                return False
        if (
            pend
            and 0.12 < age_r < 8.0
            and not recent_dbl
            and near_rmb
            and not _agent_rmb_is_taskbar
            and (menu_open or menu_just_closed)
        ):
            profile = "win11" if _is_windows_11() else "win10"
            _agent_lmb_hit_context_menu = True
            _agent_lmb_menu_item_kind = "paste"
            _note_paste_gesture()
            agent_print(
                f"[ClipboardAgent] LMB {profile} near_rmb paste age_r={age_r:.2f} "
                f"menu_open={menu_open} just_closed={menu_just_closed}"
            )
            try:
                log_overwrite_conflict(
                    f"AGENT LMB {profile} near_rmb → paste age_r={age_r:.2f} "
                    f"menu_open={menu_open} just_closed={menu_just_closed}"
                )
            except Exception:
                pass
            return True
        # Win11: Nút Paste trên thanh lệnh (Command Bar) trong Explorer
        if _is_windows_11() and pend and not recent_dbl and _cursor_in_explorer_command_bar():
            _agent_lmb_hit_context_menu = True
            _agent_lmb_menu_item_kind = "paste"
            _note_paste_gesture()
            agent_print("[ClipboardAgent] LMB Win11 command bar paste button clicked")
            return True
        _agent_lmb_hit_context_menu = False
        _agent_lmb_menu_item_kind = ""
        return False

    def _paths_are_probe_or_xfer(files):
        dirs = []
        for d in (
            _PROBE_STUB_DIR,
            HEADLESS_TRANSFER_DIR,
            os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"),
        ):
            try:
                dirs.append(os.path.abspath(d).lower())
            except Exception:
                pass
        for f in files or []:
            try:
                p = os.path.abspath(f).lower()
            except Exception:
                continue
            if any(p.startswith(d) for d in dirs):
                return True
        return False

    def _yield_clipboard_to_user(reason=""):
        """User copy local — đừng EmptyClipboard/delayed HDROP (mất copy, chuột xoay)."""
        nonlocal _agent_allow_delayed
        was_holding = _agent_allow_delayed or bool(_pending_info)
        _agent_allow_delayed = False
        _pending_info.clear()
        if was_holding:
            agent_print(f"[ClipboardAgent] Nhả clipboard cho user ({reason}).")

    def _agent_user_clipboard_wins():
        if not should_preserve_user_clipboard(_agent_hwnd):
            return False
        seq = get_clipboard_sequence_number()
        at = _agent_clip_seq_at_pending
        if at is None:
            return True
        return (not seq) or seq != at

    def _agent_emit_copied_files(force=False):
        nonlocal _agent_last_copied_seq, _agent_last_copied_fp, _agent_offer_id
        nonlocal _pending_info, _agent_allow_delayed, _agent_expect_repaste_until, _agent_repaste_local_by_name
        try:
            if _is_rendering or (not force and is_own_clipboard_write()):
                return
            files = None
            seq = 0
            for _try in range(5):
                seq_b = get_clipboard_sequence_number()
                files = get_clipboard_files()
                seq = get_clipboard_sequence_number()
                if seq_b and seq and seq_b != seq:
                    time.sleep(0.1)
                    continue
                if not files:
                    return
                if _paths_are_probe_or_xfer(files):
                    return
                fp = tuple(os.path.abspath(f).lower() for f in files)
                if (
                    _agent_last_copied_fp
                    and fp == _agent_last_copied_fp
                    and seq
                    and seq != _agent_last_copied_seq
                    and _try < 4
                ):
                    time.sleep(0.1)
                    continue
                break
            if not files:
                return
            if not force and seq and seq == _agent_last_copied_seq:
                return
            fp = tuple(os.path.abspath(f).lower() for f in files)
            if _agent_last_copied_fp and fp == _agent_last_copied_fp and seq and seq == _agent_last_copied_seq:
                return
            _agent_last_copied_seq = seq
            _agent_last_copied_fp = fp
            # Copy local trên host → nhả PENDING client→host còn sót (tránh Paste nhầm).
            if _pending_info:
                _pending_info.clear()
                _agent_allow_delayed = False
                _agent_expect_repaste_until = 0.0
                _agent_repaste_local_by_name = {}
                agent_print("[ClipboardAgent] Nhả PENDING client→host (host vừa copy local).")
            _agent_offer_id += 1
            import win32pipe, win32file, json
            pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
            win32pipe.WaitNamedPipe(pipe_name, 5000)
            pipe_handle = win32file.CreateFile(pipe_name, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
            msg = "COPIED_FILES|" + json.dumps({"offer_id": _agent_offer_id, "files": files})
            win32file.WriteFile(pipe_handle, msg.encode("utf-8"))
            win32file.CloseHandle(pipe_handle)
            agent_print(f"[ClipboardAgent] Đã gửi {len(files)} COPIED_FILES offer={_agent_offer_id} (force={force}).")
        except Exception as e:
            agent_print(f"Failed to send COPIED_FILES: {e}")

    def _agent_schedule_rearm(delay_s=0.45):
        nonlocal _agent_suppress_render_until
        if not _agent_allow_delayed or _agent_user_clipboard_wins():
            return
        _agent_suppress_render_until = max(_agent_suppress_render_until, time.time() + delay_s + 2.5)
        def _go():
            if not _agent_allow_delayed:
                return
            if _pending_info and _agent_hwnd:
                ctypes.windll.user32.PostMessageW(
                    ctypes.c_void_p(_agent_hwnd),
                    WM_USER_SETUP_DELAYED, 0, 0
                )
        threading.Timer(delay_s, _go).start()

    def _agent_explorer_path_cacher():
        nonlocal _agent_cached_explorer_path
        while True:
            try:
                try:
                    if ctypes.windll.user32.GetOpenClipboardWindow():
                        time.sleep(0.35)
                        continue
                except Exception:
                    pass
                found = query_explorer_folder_path()
                if found:
                    _agent_cached_explorer_path = found
            except Exception:
                pass
            time.sleep(0.35)

    threading.Thread(target=_agent_explorer_path_cacher, daemon=True, name="AgentExplorerPath").start()

    def _agent_mouse_poll_loop():
        nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_ctrl_v_time, _agent_dummy_h_active
        nonlocal _agent_last_ctrl_c_time, _agent_last_copied_seq, _agent_ctrl_v_held, _agent_shift_ins_held, _agent_lmb_held
        nonlocal _agent_lmb_hit_context_menu, _agent_lmb_menu_item_kind, _agent_rmb_cursor_pos, _agent_allow_delayed
        nonlocal _agent_last_menu_paste_trigger_time, _agent_rmb_is_taskbar, _agent_lmb_dismiss_at
        user32 = ctypes.windll.user32
        while True:
            try:
                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    now = time.time()
                    on_self = _cursor_over_current_process()
                    is_paste = False
                    if not _agent_lmb_held:
                        _register_lmb_down()
                        if not on_self:
                            is_paste = _agent_lmb_is_context_paste(on_self)
                    else:
                        _agent_last_lbutton_time = now
                    _agent_lmb_held = True
                    if is_paste:
                        now_trig = time.time()
                        if now_trig - _agent_last_menu_paste_trigger_time >= 0.8:
                            _agent_last_menu_paste_trigger_time = now_trig
                            threading.Thread(
                                target=_agent_trigger_paste,
                                args=("menu_paste",),
                                kwargs={"dest_override": _agent_cached_explorer_path},
                                daemon=True,
                                name="AgentMenuPasteTrigger",
                            ).start()
                    if (not on_self) and _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd and not clipboard_has_file_formats():
                        if not is_paste:
                            _agent_dummy_h_active = False
                            ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                else:
                    _agent_lmb_held = False
                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    _agent_last_rbutton_time = time.time()
                    _agent_lmb_hit_context_menu = False
                    _agent_lmb_menu_item_kind = ""
                    _agent_lmb_dismiss_at = 0.0  # Reset khi có RMB mới
                    cxy = None
                    try:
                        cxy = _cursor_xy()
                    except Exception:
                        cxy = None
                    if cxy and _is_taskbar_or_taskmgr_at_point(cxy):
                        _agent_rmb_is_taskbar = True
                        _agent_rmb_cursor_pos = None
                    else:
                        _agent_rmb_is_taskbar = False
                        _agent_rmb_cursor_pos = cxy
                        try:
                            set_global_rmb_pos(cxy)
                        except Exception:
                            pass
                        try:
                            p = query_explorer_folder_path(allow_open_clipboard=False)
                            if p and os.path.isdir(p) and not _is_transfer_staging_dir(p):
                                _agent_cached_explorer_path = p
                        except Exception:
                            pass

                if user32.GetAsyncKeyState(0x0D) & 0x8000: # Enter
                    if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if user32.GetAsyncKeyState(0x1B) & 0x8000: # Esc
                    if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):
                    if not _agent_ctrl_v_held:
                        has_text = bool(user32.IsClipboardFormatAvailable(13) or user32.IsClipboardFormatAvailable(1))
                        is_exp = _is_explorer_clipboard_client()
                        if is_exp and not has_text:
                            _agent_last_ctrl_v_time = time.time()
                            _agent_suppress_render_until = 0.0
                            _note_paste_gesture()
                            if _pending_info:
                                _agent_allow_delayed = True
                    _agent_ctrl_v_held = True
                    if not has_text and is_exp and _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                else:
                    _agent_ctrl_v_held = False
                if (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000):
                    if not _agent_shift_ins_held:
                        has_text = bool(user32.IsClipboardFormatAvailable(13) or user32.IsClipboardFormatAvailable(1))
                        is_exp = _is_explorer_clipboard_client()
                        if is_exp and not has_text:
                            _agent_last_ctrl_v_time = time.time()
                            _agent_suppress_render_until = 0.0
                            _note_paste_gesture()
                            if _pending_info:
                                _agent_allow_delayed = True
                    _agent_shift_ins_held = True
                    if not has_text and is_exp and _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                        _agent_dummy_h_active = False
                        ctypes.windll.user32.PostMessageW(ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0)
                else:
                    _agent_shift_ins_held = False
                if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x43) & 0x8000):
                    now = time.time()
                    if now - _agent_last_ctrl_c_time > 0.4:
                        _agent_last_ctrl_c_time = now
                        threading.Timer(0.18, lambda: _agent_emit_copied_files(force=True)).start()
            except:
                pass
            time.sleep(0.05)
            
    threading.Thread(target=_agent_mouse_poll_loop, daemon=True, name="AgentMousePoll").start()

    def _send_cancel_to_host(paste_id=None):
        """Báo worker dừng gửi/nhận. Event Global dễ fail (SYSTEM vs Medium IL)."""
        import win32file
        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
        sent_pipe = False
        if paste_id is not None:
            body = ("CANCEL_TRANSFER|" + str(int(paste_id))).encode("utf-8")
        else:
            body = b"CANCEL_TRANSFER"
        for attempt in range(8):
            try:
                import win32pipe
                try:
                    win32pipe.WaitNamedPipe(pipe_name, 400)
                except Exception:
                    pass
                pipe_handle = win32file.CreateFile(
                    pipe_name,
                    win32file.GENERIC_WRITE, 0, None,
                    win32file.OPEN_EXISTING, 0, None
                )
                win32file.WriteFile(pipe_handle, body)
                win32file.CloseHandle(pipe_handle)
                sent_pipe = True
                agent_print("[ClipboardAgent] Đã gửi CANCEL_TRANSFER tới host (UpPipe).")
                break
            except Exception as e:
                if attempt == 7:
                    agent_print(f"[ClipboardAgent] Lỗi gửi CANCEL_TRANSFER qua pipe: {e}")
                time.sleep(0.08)
        if paste_id is not None:
            return
        try:
            h_event = win32event.OpenEvent(
                win32event.EVENT_MODIFY_STATE, False,
                r"Global\AntigravityP2P_CancelTransfer_Event",
            )
            win32event.SetEvent(h_event)
            time.sleep(0.2)
            try:
                win32event.ResetEvent(h_event)
            except Exception:
                pass
            win32api.CloseHandle(h_event)
            agent_print("[ClipboardAgent] Đã SetEvent hủy truyền tải.")
        except Exception as e:
            agent_print(f"[ClipboardAgent] Event hủy không Set được (pipe={sent_pipe}): {e}")

    def _write_request_files_pipe(files_to_request, dest_dir, paste_id):
        import win32file, json
        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
        try:
            import win32pipe
            try:
                win32pipe.WaitNamedPipe(pipe_name, 5000)
            except Exception:
                pass
            pipe_handle = win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_WRITE, 0, None,
                win32file.OPEN_EXISTING, 0, None
            )
            payload = {
                "files": files_to_request or [],
                "dest_dir": dest_dir or "",
                "paste_id": int(paste_id or 0),
            }
            write_shared_paste_request(payload)
            msg = "REQUEST_FILES|" + json.dumps(payload)
            win32file.WriteFile(pipe_handle, msg.encode('utf-8'))
            win32file.CloseHandle(pipe_handle)
            agent_print(f"[ClipboardAgent] Đã gửi REQUEST_FILES paste_id={paste_id}.")
        except Exception as e:
            agent_print(f"[ClipboardAgent] Lỗi gửi REQUEST_FILES qua Pipe: {e}")
            try:
                write_shared_paste_request({
                    "files": files_to_request or [],
                    "dest_dir": dest_dir or "",
                    "paste_id": int(paste_id or 0),
                })
            except Exception:
                pass

    def _write_conflict_query_pipe(paste_id, conflicts, has_multiple):
        """Gửi CONFLICT_QUERY lên host → client hiện ClassicCopyDialog."""
        import win32file, json
        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
        try:
            import win32pipe
            try:
                win32pipe.WaitNamedPipe(pipe_name, 5000)
            except Exception:
                pass
            pipe_handle = win32file.CreateFile(
                pipe_name,
                win32file.GENERIC_WRITE, 0, None,
                win32file.OPEN_EXISTING, 0, None
            )
            items = []
            for filename, source_info, dest_info, dest_path in conflicts or []:
                items.append({
                    "filename": filename,
                    "source_info": source_info or {},
                    "dest_info": dest_info or {},
                    "dest_path": dest_path,
                })
            payload = {
                "paste_id": int(paste_id or 0),
                "conflicts": items,
                "has_multiple": bool(has_multiple),
            }
            msg = "CONFLICT_QUERY|" + json.dumps(payload)
            win32file.WriteFile(pipe_handle, msg.encode("utf-8"))
            win32file.CloseHandle(pipe_handle)
            agent_print(f"[ClipboardAgent] CONFLICT_QUERY paste_id={paste_id} n={len(items)}")
            return True
        except Exception as e:
            agent_print(f"[ClipboardAgent] Lỗi CONFLICT_QUERY: {e}")
            return False

    def _flush_agent_file_request():
        """Một lúc chỉ một REQUEST_FILES trên dây — paste sau chờ paste trước xong."""
        while True:
            with _agent_req_lock:
                if _agent_req_inflight[0]:
                    return
                try:
                    files, dest_dir, paste_id = _agent_req_q.get_nowait()
                except queue.Empty:
                    return
                try:
                    pid = int(paste_id or 0)
                except Exception:
                    pid = 0
                job = _agent_jobs.get(pid) if pid else None
                if job is not None:
                    if not job.get("allow"):
                        agent_print(f"[ClipboardAgent] Bo REQUEST_FILES hang doi paste_id={pid} (da Huy).")
                        continue
                elif not _agent_allow_xfer:
                    agent_print("[ClipboardAgent] Bo REQUEST_FILES hang doi (allow_xfer=False).")
                    continue
                _agent_req_inflight[0] = True
            _write_request_files_pipe(files, dest_dir, paste_id)
            return

    def _release_agent_file_request():
        with _agent_req_lock:
            _agent_req_inflight[0] = False
        _flush_agent_file_request()

    def _send_request_files_to_host(files_to_request=None, dest_dir=None, paste_id=0):
        """Xếp hàng REQUEST_FILES — không gửi paste sau khi paste trước còn trên dây."""
        try:
            pid = int(paste_id or 0)
        except Exception:
            pid = 0
        job = _agent_jobs.get(pid) if pid else None
        if job is not None:
            if not job.get("allow"):
                agent_print("[ClipboardAgent] Bo REQUEST_FILES (job da Huy).")
                return
        elif not _agent_allow_xfer:
            agent_print("[ClipboardAgent] Bo REQUEST_FILES (allow_xfer=False / da Huy).")
            return
        _agent_req_q.put((list(files_to_request or []), dest_dir or "", pid))
        agent_print(f"[ClipboardAgent] Xep hang REQUEST_FILES paste_id={pid} (cho={_agent_req_q.qsize()})")
        _flush_agent_file_request()

    def _execute_agent_delayed_rendering(hwnd):
        """Chạy trong WndProc thread: mở clipboard, đăng ký deferred CF_HDROP."""
        nonlocal _ignore_destroy, _agent_setup_tries, _agent_force_delayed_setup, _agent_allow_delayed
        nonlocal _agent_suppress_render_until
        force = _agent_force_delayed_setup
        _agent_force_delayed_setup = False
        if not force:
            if not _agent_allow_delayed:
                agent_print("[ClipboardAgent] Bo setup delayed — clipboard dang thuoc user.")
                return
            if _agent_user_clipboard_wins():
                _yield_clipboard_to_user("local after pending")
                return
        else:
            _agent_allow_delayed = True
        if not _pending_info:
            info = read_shared_pending_offer()
            if info:
                _pending_info.clear()
                _pending_info.update(info)
                flist = _pending_info.get("files") or []
                try:
                    from os_utils.windows_clipboard import clipboard_sync_manager
                    if clipboard_sync_manager:
                        clipboard_sync_manager.pending_remote_files = list(flist)
                        clipboard_sync_manager._reoffer_files = list(flist)
                        clipboard_sync_manager._allow_delayed = True
                        clipboard_sync_manager._force_delayed_setup = True
                except Exception:
                    pass
                agent_print(f"[ClipboardAgent] Nạp _pending_info từ shared file: {len(flist)} files.")
        if not _pending_info:
            agent_print("[ClipboardAgent] Không có pending_info, bỏ qua setup delayed rendering.")
            return
            
        try:
            user32 = ctypes.windll.user32
            if not user32.OpenClipboard(hwnd):
                _agent_setup_tries += 1
                if (
                    _agent_setup_tries <= 40
                    and _agent_allow_delayed
                    and (force or not _agent_user_clipboard_wins())
                ):
                    _agent_force_delayed_setup = force
                    threading.Timer(
                        0.025,
                        lambda h=hwnd: ctypes.windll.user32.PostMessageW(
                            ctypes.c_void_p(h), WM_USER_SETUP_DELAYED, 0, 0
                        ),
                    ).start()
                else:
                    err = ctypes.GetLastError()
                    agent_print(f"[ClipboardAgent] OpenClipboard thất bại khi setup (hết retry). Err={err}")
                return
            _agent_setup_tries = 0
            if not force and _agent_user_clipboard_wins():
                user32.CloseClipboard()
                _yield_clipboard_to_user("opened but user owns")
                return
            _ignore_destroy = True
            try:
                user32.EmptyClipboard()
                setup_clipboard_exclusions()
                res = fn_SetClipboardData(CF_HDROP, None)
                user32.CloseClipboard()
                mark_own_clipboard_write()
                _agent_suppress_render_until = max(_agent_suppress_render_until, time.time() + 2.0)
                agent_print(f"[ClipboardAgent] Đã setup delayed rendering CF_HDROP. res={res}")
            finally:
                _ignore_destroy = False
        except Exception as e:
            agent_print(f"[ClipboardAgent] Lỗi setup delayed rendering: {e}")
            _ignore_destroy = False

    def _agent_cleanup_partial(extra_paths=None, files_meta=None, wipe_all_staging=True, staging_xids=None):
        dests = [
            _agent_cached_explorer_path,
            HEADLESS_TRANSFER_DIR,
            os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"),
            _PROBE_STUB_DIR,
        ]
        if files_meta is None:
            meta = (_pending_info.get("files") if _pending_info else None) or []
        else:
            meta = files_meta
        paths = list(extra_paths or [])
        cleanup_incomplete_named_files(
            dests, meta, extra_paths=paths,
            staging_xids=staging_xids, wipe_all_staging=wipe_all_staging,
        )

    def _agent_complete_download(job):
        """Chờ FILES rồi chuyển vào thư mục Explorer — KHÔNG chạy trong WM_RENDERFORMAT (tránh deadlock OLE)."""
        nonlocal _agent_allow_xfer, _agent_accept_files, _agent_download_active, _pending_info
        nonlocal _agent_expect_repaste_until, _agent_dummy_h_active, _agent_allow_delayed, _agent_repaste_local_by_name
        nonlocal _agent_last_paste_finish_time
        pid = job.get("paste_id")
        info = job.get("info") or {}
        dest_dir = job.get("dest")
        try:
            log_overwrite_conflict(f"AgentPasteFinish START paste_id={pid} dest={dest_dir!r}")
            while job.get("allow") and not job["conflict_event"].is_set():
                job["conflict_event"].wait(0.2)
            dest_dir = job.get("dest") or dest_dir
            log_overwrite_conflict(
                f"AgentPasteFinish conflict_wait_end paste_id={pid} allow={job.get('allow')} "
                f"choice={job.get('conflict_choice')!r} conflict_set={job['conflict_event'].is_set()} dest={dest_dir!r}"
            )
            if (not job.get("allow")) or job.get("conflict_choice") == "cancel":
                agent_print("[ClipboardAgent] Huy do ghi de / conflict.")
                log_overwrite_conflict(f"AgentPasteFinish CANCEL exit paste_id={pid}")
                _agent_cleanup_partial(list(job.get("paths") or []))
                gui_queue.put(("cancel", pid))
                return

            wait_start = time.time()
            last_hb = wait_start
            while job.get("allow") and not job["event"].is_set():
                job["event"].wait(0.5)
                now = time.time()
                if now - last_hb >= 60.0:
                    last_hb = now
                    nbytes = int(job.get("last_progress_bytes") or 0)
                    agent_print(
                        f"[ClipboardAgent] Dang cho FILES paste_id={pid} received={nbytes} "
                        f"({int(now - wait_start)}s) — dialog van mo."
                    )
            if not job.get("allow"):
                agent_print("[ClipboardAgent] Huy luc cho file (nguoi dung / CANCEL).")
                leftover = list(job.get("paths") or [])
                _agent_cleanup_partial(leftover)
                gui_queue.put(("cancel", pid))
                return
            if job.get("event").is_set() and not job.get("paths"):
                agent_print("[ClipboardAgent] Paste khong tai file (skip / khong con file).")
                gui_queue.put(("end", pid))
                return
            if job.get("event").is_set() and job.get("paths"):
                final_paths = list(job["paths"])
                meta_files = list(job.get("requested_files") or (info.get("files") if info else None) or [])
                why = []
                if not _paths_match_expected_sizes(final_paths, meta_files, detail=why):
                    agent_print("[ClipboardAgent] File chưa đủ dung lượng — không chuyển. " + "; ".join(why))
                    _agent_cleanup_partial(final_paths)
                    gui_queue.put(("cancel", pid))
                else:
                    skip = set(job.get("conflict_skip") or [])
                    to_move = []
                    for p in final_paths:
                        dest_p = os.path.join(dest_dir, os.path.basename(p)) if dest_dir else p
                        try:
                            dest_key = os.path.normcase(os.path.abspath(dest_p))
                        except Exception:
                            dest_key = dest_p
                        if dest_key in skip:
                            try:
                                if os.path.isdir(p):
                                    import shutil
                                    shutil.rmtree(p, ignore_errors=True)
                                elif os.path.isfile(p):
                                    os.remove(p)
                            except Exception:
                                pass
                            continue
                        to_move.append(p)
                    already_in_dest = False
                    if dest_dir and to_move:
                        try:
                            dest_abs = os.path.normcase(os.path.abspath(dest_dir))
                            already_in_dest = all(
                                os.path.normcase(os.path.dirname(os.path.abspath(p))) == dest_abs
                                for p in to_move
                            )
                        except Exception:
                            already_in_dest = False
                    if dest_dir and to_move and not already_in_dest:
                        move_total = sum(_path_byte_size(p) for p in to_move)
                        need_copy = any(not _same_volume(p, dest_dir) for p in to_move)
                        replace_keys = set(job.get("replace_keys") or [])
                        with _file_io_lock:
                            if need_copy:
                                gui_queue.put(("finalize_start", (move_total, pid)))
                            to_move, moved_all = _relocate_transfer_files_unlocked(
                                to_move, dest_dir,
                                on_progress=lambda n, j=pid: gui_queue.put(("finalize_progress", (n, j))),
                                should_stop=lambda: not job.get("allow"),
                                replace_keys=replace_keys,
                            )
                        agent_print(f"[ClipboardAgent] Paste dest={dest_dir} moved_all={moved_all} n={len(to_move)}")
                        if not job.get("allow"):
                            _agent_cleanup_partial(to_move)
                            gui_queue.put(("cancel", pid))
                            return
                    elif already_in_dest:
                        agent_print(f"[ClipboardAgent] File da o dest={dest_dir}, bo copy lan 2.")
                    elif not to_move:
                        agent_print("[ClipboardAgent] Khong chuyen file (skip het / Huy).")
                    # Đóng dialog ngay khi file đã vào đích — dọn staging (AV/Explorer có thể
                    # giữ khóa vài giây) chạy nền, không giữ dialog ở 100%.
                    gui_queue.put(("end", pid))
                    def _bg_purge(d=dest_dir, xp=list(final_paths) + list(to_move or [])):
                        try:
                            _purge_rdxfer_staging(dest_dir=d, extra_paths=xp)
                            # Delayed: Explorer/AV đôi khi giữ khóa .rdxfer_* vừa HIDDEN|SYSTEM.
                            threading.Timer(0.8, lambda: _purge_rdxfer_staging(dest_dir=d, extra_paths=xp)).start()
                            threading.Timer(2.5, lambda: _purge_rdxfer_staging(dest_dir=d, extra_paths=xp)).start()
                            _schedule_scrub_probe(d)
                        except Exception:
                            pass
                    threading.Thread(target=_bg_purge, daemon=True, name="AgentPurge").start()
                    # Giữ PENDING + cache local để Paste tiếp thư mục khác (không cần copy lại trên client).
                    keep_files = []
                    for f in (
                        (_pending_info.get("files") if _pending_info else None)
                        or (info.get("files") if info else None)
                        or meta_files
                        or []
                    ):
                        keep_files.append(dict(f) if isinstance(f, dict) else f)
                    if keep_files:
                        if not _pending_info:
                            _pending_info.update(info or {})
                        _pending_info["files"] = keep_files
                        _agent_expect_repaste_until = time.time() + 86400.0
                        _agent_allow_delayed = True
                        _agent_dummy_h_active = True
                        local_map = dict(_agent_repaste_local_by_name or {})
                        for p in (to_move or final_paths or []):
                            if not p:
                                continue
                            try:
                                if os.path.exists(p):
                                    base = os.path.basename(str(p).rstrip("\\/"))
                                    if base:
                                        local_map[os.path.normcase(base)] = os.path.abspath(p)
                            except Exception:
                                pass
                        _agent_repaste_local_by_name = local_map
                        agent_print(
                            f"[ClipboardAgent] Giữ clipboard offer n={len(keep_files)} "
                            f"local_cache={len(local_map)} (repaste OK)."
                        )
                    gui_queue.put(("end", pid))
                    agent_print("[ClipboardAgent] Da chuyen file xong (sau khi thoat RENDERFORMAT).")
            else:
                agent_print(
                    f"[ClipboardAgent] Cho FILES ket thuc bat thuong "
                    f"event={job['event'].is_set()} allow={job.get('allow')} "
                    f"n_paths={len(job.get('paths') or [])}."
                )
                leftover = list(job.get("paths") or [])
                _agent_cleanup_partial(leftover)
                gui_queue.put(("cancel", pid))
                _send_cancel_to_host(pid)
        except Exception as e:
            agent_print(f"[ClipboardAgent] Loi hoan tat paste nen: {e}")
            _agent_cleanup_partial(list(job.get("paths") or []))
            gui_queue.put(("cancel", pid))
            try:
                _send_cancel_to_host(pid)
            except Exception:
                pass
        finally:
            log_overwrite_conflict(f"AgentPasteFinish FINALLY pop paste_id={pid}")
            try:
                _clear_agent_paste_gesture_flags(1.0)
                _agent_last_paste_finish_time = time.time()
                _agent_jobs.pop(pid, None)
                if not _agent_jobs:
                    _agent_accept_files = False
                    _agent_allow_xfer = False
                    _agent_download_active = False
                else:
                    _agent_accept_files = True
                    _agent_allow_xfer = True
                    _agent_download_active = True
                _release_agent_file_request()
                if _pending_info:
                    _agent_expect_repaste_until = max(_agent_expect_repaste_until, time.time() + 86400.0)
                    _agent_allow_delayed = True
                    _agent_dummy_h_active = True
                    _agent_schedule_rearm(0.45)
                    agent_print("[ClipboardAgent] Rearm delayed CF_HDROP cho Paste lai.")
            except Exception as e_fin:
                agent_print(f"[ClipboardAgent] Loi cleanup finally: {e_fin}")

    def _agent_trigger_paste(source="render_format", dest_override=None):
        """Kích hoạt dán file (từ WM_RENDERFORMAT hoặc LMB context menu Paste)."""
        nonlocal _agent_download_active, _agent_expect_repaste_until, _agent_paste_id
        nonlocal _agent_consumed_gesture_id, _agent_paste_coalesce_until, _agent_last_paste_start
        nonlocal _agent_accept_files, _agent_allow_xfer, _agent_cached_explorer_path, _ignore_destroy
        nonlocal _agent_allow_delayed, _agent_last_paste_finish_time
        nonlocal _agent_last_lbutton_time, _agent_last_ctrl_v_time, _agent_lmb_hit_context_menu, _agent_lmb_menu_item_kind

        with _agent_paste_trigger_lock:
            # Người dùng thực hiện dán khi có file PENDING từ client → luôn mở allow_delayed
            if _pending_info and not _agent_allow_delayed:
                log_overwrite_conflict(
                    f"TRIGGER_PASTE re-arm allow_delayed=True source={source} (files pending from client)"
                )
                _agent_allow_delayed = True

            now = time.time()
            time_since_last_paste = now - float(_agent_last_paste_start or 0)
            time_since_last_finish = now - float(_agent_last_paste_finish_time or 0)
            same_gesture = _agent_paste_gesture_id <= _agent_consumed_gesture_id

            log_overwrite_conflict(
                f"TRIGGER_PASTE source={source} enter pending={bool(_pending_info)} "
                f"allow_delayed={_agent_allow_delayed} "
                f"elapsed_start={time_since_last_paste:.2f}s elapsed_finish={time_since_last_finish:.2f}s "
                f"same_gesture={same_gesture} gesture_id={_agent_paste_gesture_id} "
                f"consumed={_agent_consumed_gesture_id}"
            )

            if not _pending_info:
                info = read_shared_pending_offer()
                if info and isinstance(info, dict):
                    _pending_info.clear()
                    _pending_info.update(info)
                    _agent_allow_delayed = True
                    flist = _pending_info.get("files") or []
                    try:
                        from os_utils.windows_clipboard import clipboard_sync_manager
                        if clipboard_sync_manager:
                            clipboard_sync_manager.pending_remote_files = list(flist)
                            clipboard_sync_manager._reoffer_files = list(flist)
                            clipboard_sync_manager._allow_delayed = True
                            clipboard_sync_manager._force_delayed_setup = True
                    except Exception:
                        pass
                    agent_print(f"[ClipboardAgent] TRIGGER_PASTE nap _pending_info tu shared file: {len(flist)} files.")

            if not _pending_info or not _agent_allow_delayed:
                log_overwrite_conflict(
                    f"TRIGGER_PASTE EXIT early: no_pending_or_delayed source={source} "
                    f"pending={bool(_pending_info)} allow_delayed={_agent_allow_delayed}"
                )
                if source == "render_format":
                    empty_hdrop = create_hdrop_data([])
                    if empty_hdrop:
                        _ignore_destroy = True
                        try:
                            res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                            if not res:
                                fn_GlobalFree(empty_hdrop)
                        finally:
                            _ignore_destroy = False
                return False

            # Chặn trùng lặp:
            # 1) Nếu có job đang chạy (living_jobs) -> không kích hoạt thêm job trùng
            # 2) Cùng gesture đã tiêu thụ -> bỏ qua
            # 3) Hoặc debounce nhanh trong 0.6s để tránh OLE gọi đúp cùng 1 lần paste
            living_jobs = any(
                j.get("allow") and not (j.get("event") and j["event"].is_set())
                for j in _agent_jobs.values()
            )
            if living_jobs or same_gesture or time_since_last_paste < 0.6 or (same_gesture and time_since_last_finish < 0.5):
                log_overwrite_conflict(
                    f"TRIGGER_PASTE IGNORE duplicate source={source} same_gesture={same_gesture} "
                    f"living={living_jobs} elapsed_start={time_since_last_paste:.2f}s "
                    f"elapsed_finish={time_since_last_finish:.2f}s"
                )
                if source == "render_format":
                    empty_hdrop = create_hdrop_data([])
                    if empty_hdrop:
                        _ignore_destroy = True
                        try:
                            res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                            if not res:
                                fn_GlobalFree(empty_hdrop)
                        finally:
                            _ignore_destroy = False
                return False

            log_overwrite_conflict(
                f"TRIGGER_PASTE source={source} launch paste_id={_agent_paste_id + 1} (active={len(_agent_jobs)})"
            )
            _agent_expect_repaste_until = 0.0
            _agent_paste_id += 1
            paste_id = _agent_paste_id
            _agent_last_lbutton_time = 0.0
            _agent_last_ctrl_v_time = 0.0
            _agent_lmb_hit_context_menu = False
            _agent_lmb_menu_item_kind = ""
            _agent_consumed_gesture_id = _agent_paste_gesture_id
            _agent_paste_coalesce_until = now + 0.35
            _agent_last_paste_start = now
            _agent_accept_files = True
            _agent_allow_xfer = True
            _agent_download_active = True

            agent_print(
                f"[ClipboardAgent] Kích hoạt Paste ({source}). "
                f"Job paste_id={paste_id} (song song={len(_agent_jobs)})."
            )

            try:
                # Chốt dest Explorer ngay lúc Paste (tránh cache cũ / staging).
                if dest_override and os.path.isdir(dest_override) and not _is_transfer_staging_dir(dest_override):
                    _agent_cached_explorer_path = dest_override
                else:
                    try:
                        found = query_explorer_folder_path(allow_open_clipboard=False)
                        if found and os.path.isdir(found) and not _is_transfer_staging_dir(found):
                            _agent_cached_explorer_path = found
                    except Exception:
                        pass
                paste_dest = _agent_cached_explorer_path
                if not paste_dest or not os.path.isdir(paste_dest) or _is_transfer_staging_dir(paste_dest):
                    desktop = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
                    if os.path.isdir(desktop):
                        paste_dest = desktop
                    else:
                        paste_dest = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                    _agent_cached_explorer_path = paste_dest
                info = {
                    "display_name": _pending_info.get("display_name", "Files"),
                    "item_kind": _pending_info.get("item_kind") or "file",
                    "total_size": _pending_info.get("total_size", 0),
                    "files": [dict(f) if isinstance(f, dict) else f for f in (_pending_info.get("files") or [])],
                }
                job = {
                    "paste_id": paste_id,
                    "info": info,
                    "dest": paste_dest,
                    "event": threading.Event(),
                    "paths": [],
                    "allow": True,
                    "accept": True,
                    "conflict_event": threading.Event(),
                    "conflict_choice": "replace",
                    "conflict_skip": set(),
                    "replace_keys": set(),
                    "conflict_reply_event": threading.Event(),
                    "conflict_reply": None,
                    "requested_files": [],
                    "last_progress_bytes": 0,
                    "last_progress_at": time.time(),
                }
                _agent_jobs[paste_id] = job
                agent_print(f"[ClipboardAgent] Paste dest={paste_dest!r} files={len(info.get('files') or [])}")

                # Trả HDROP rỗng NGAY — không chờ 100% trong GetData.
                if source == "render_format":
                    empty_hdrop = create_hdrop_data([])
                    if empty_hdrop:
                        _ignore_destroy = True
                        try:
                            res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                            if not res:
                                fn_GlobalFree(empty_hdrop)
                            agent_print(f"[ClipboardAgent] Unblock Explorer, tai file o nen. res={res}")
                        finally:
                            _ignore_destroy = False

                _schedule_scrub_probe(paste_dest)

                # Bắt đầu conflict_check + download
                gui_queue.put(("conflict_check", (
                    paste_dest,
                    list(info.get("files") or []),
                    info.get("display_name", "Files"),
                    info.get("total_size", 0),
                    paste_id,
                )))
                threading.Thread(
                    target=_agent_complete_download,
                    args=(job,),
                    daemon=True,
                    name=f"AgentPasteFinish_{paste_id}",
                ).start()

                if _pending_info:
                    _agent_schedule_rearm(0.35)
                return True
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lỗi xử lý Paste ({source}): {e}")
                _agent_jobs.pop(paste_id, None)
                if not _agent_jobs:
                    _agent_download_active = False
                    _agent_allow_xfer = False
                    _agent_accept_files = False
                if source == "render_format":
                    empty_hdrop = create_hdrop_data([])
                    if empty_hdrop:
                        _ignore_destroy = True
                        try:
                            res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                            if not res:
                                fn_GlobalFree(empty_hdrop)
                        finally:
                            _ignore_destroy = False
                if _pending_info:
                    _agent_schedule_rearm(0.45)
                gui_queue.put(("cancel", paste_id))
                return False

    def _agent_wndproc(hwnd, msg, wparam, lparam):
        """WndProc cho hidden window của agent. Xử lý WM_RENDERFORMAT (Paste xảy ra)."""
        nonlocal _is_rendering, _files_ready_paths, _files_ready_event, _ignore_destroy, _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_dummy_h_active, _agent_cached_explorer_path, _agent_suppress_render_until, _agent_expect_repaste_until, _agent_paste_id, _agent_accept_files, _agent_allow_xfer, _agent_xfer_cancel_at, _agent_download_active, _agent_conflict_choice, _agent_conflict_skip, _agent_allow_delayed, _agent_paste_gesture_id, _agent_consumed_gesture_id, _agent_paste_coalesce_until, _agent_force_delayed_setup, _agent_last_paste_start
        nonlocal _agent_last_paste_finish_time, _agent_lmb_menu_item_name

        if msg == WM_USER_SETUP_DELAYED:
            if wparam == 1:
                _agent_force_delayed_setup = True
            if not _pending_info:
                info = read_shared_pending_offer()
                if info and isinstance(info, dict):
                    _pending_info.clear()
                    _pending_info.update(info)
                    flist = _pending_info.get("files") or []
                    _agent_clip_seq_at_pending = get_clipboard_sequence_number()
                    _agent_allow_delayed = True
                    _agent_force_delayed_setup = True
                    try:
                        from os_utils.windows_clipboard import clipboard_sync_manager
                        if clipboard_sync_manager:
                            clipboard_sync_manager.pending_remote_files = list(flist)
                            clipboard_sync_manager._reoffer_files = list(flist)
                            clipboard_sync_manager._allow_delayed = True
                            clipboard_sync_manager._force_delayed_setup = True
                    except Exception:
                        pass
            if not _agent_force_delayed_setup and _agent_user_clipboard_wins():
                _yield_clipboard_to_user("setup skipped")
                return 0
            if _agent_allow_delayed or _agent_force_delayed_setup:
                _execute_agent_delayed_rendering(hwnd)
            return 0

        if msg == WM_USER_UNBLOCK_PASTE:
            # Đang trong WM_RENDERFORMAT (pump) hoặc vừa Hủy: trả HDROP rỗng, không EmptyClipboard.
            empty_hdrop = create_hdrop_data([])
            if empty_hdrop:
                _ignore_destroy = True
                try:
                    res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                    if not res:
                        fn_GlobalFree(empty_hdrop)
                    agent_print(f"[ClipboardAgent] Unblock Explorer sau Huy. HDROP rong res={res}")
                except Exception as e:
                    agent_print(f"[ClipboardAgent] Unblock Explorer loi: {e}")
                    try:
                        fn_GlobalFree(empty_hdrop)
                    except Exception:
                        pass
                finally:
                    _ignore_destroy = False
            return 0

        if msg == 0x031D: # WM_CLIPBOARDUPDATE
            if _ignore_destroy or _is_rendering:
                return 0
            if is_own_clipboard_write():
                return 0
            if should_preserve_user_clipboard(hwnd):
                _yield_clipboard_to_user("local clipboard")

            nonlocal _agent_send_clip_timer, _agent_send_clip_gen, _agent_last_sent_text
            _agent_send_clip_gen += 1
            my_gen = _agent_send_clip_gen
            if _agent_send_clip_timer is not None:
                try:
                    _agent_send_clip_timer.cancel()
                except Exception:
                    pass

            def _send_clipboard(g=my_gen):
                nonlocal _agent_last_sent_text
                if g != _agent_send_clip_gen:
                    return
                if _is_rendering or is_own_clipboard_write():
                    return
                if not should_preserve_user_clipboard(_agent_hwnd):
                    return
                if _agent_allow_delayed and _pending_info:
                    return
                _yield_clipboard_to_user("local clipboard poll")
                files = get_clipboard_files(retries=3)
                if files:
                    if _paths_are_probe_or_xfer(files):
                        return
                    _yield_clipboard_to_user("local files")
                    _agent_emit_copied_files(force=True)
                    return
                text = get_clipboard_text()
                if text and text != _agent_last_sent_text:
                    _yield_clipboard_to_user("local text")
                    try:
                        import win32pipe, win32file, json
                        pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
                        win32pipe.WaitNamedPipe(pipe_name, 5000)
                        pipe_handle = win32file.CreateFile(pipe_name, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
                        msg_payload = "COPIED_TEXT|" + json.dumps(text)
                        win32file.WriteFile(pipe_handle, msg_payload.encode('utf-8'))
                        win32file.CloseHandle(pipe_handle)
                        _agent_last_sent_text = text
                        agent_print("[ClipboardAgent] Đã gửi COPIED_TEXT cho Service.")
                    except Exception as e:
                        agent_print(f"Failed to send COPIED_TEXT: {e}")

            t = threading.Timer(0.35, _send_clipboard)
            t.daemon = True
            _agent_send_clip_timer = t
            t.start()
            return 0

        if msg == WM_RENDERFORMAT and wparam == CF_HDROP:
            log_overwrite_conflict(
                f"RENDERFORMAT enter pending={bool(_pending_info)} "
                f"allow_delayed={_agent_allow_delayed} "
                f"dest_cache={_agent_cached_explorer_path!r} "
                f"gesture={_agent_paste_gesture_id}/{_agent_consumed_gesture_id} "
                f"ctrl_v_age={(time.time()-_agent_last_ctrl_v_time) if _agent_last_ctrl_v_time else None}"
            )
            opener_hwnd = ctypes.windll.user32.GetOpenClipboardWindow()
            fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
            opener_p = (_hwnd_process_name(opener_hwnd) or "").lower() if opener_hwnd else ""
            fg_p = (_hwnd_process_name(fg_hwnd) or "").lower() if fg_hwnd else ""
            has_clip_text = bool(ctypes.windll.user32.IsClipboardFormatAvailable(13) or ctypes.windll.user32.IsClipboardFormatAvailable(1))
            is_exp_target = fg_p in _EXPLORER_CLIPBOARD_PROCS or opener_p in _EXPLORER_CLIPBOARD_PROCS
            recent_ctrl = bool(
                _agent_last_ctrl_v_time
                and (time.time() - _agent_last_ctrl_v_time) < 2.5
                and is_exp_target
                and not has_clip_text
            )
            recent_paste_click = (
                (
                    _agent_paste_gesture_id > _agent_consumed_gesture_id
                    and (_agent_lmb_menu_item_kind or "") != "not_paste"
                    and (time.time() - (_agent_last_lbutton_time or 0)) < 3.0
                    and (_agent_last_lbutton_time or 0) > (_agent_last_rbutton_time or 0)
                    and (time.time() - (_agent_last_rbutton_time or 0)) > 0.12
                    and (time.time() - (_agent_last_rbutton_time or 0)) < 8.0
                )
                or _is_recent_rmb_paste_click_unified(
                    _agent_last_lbutton_time,
                    _agent_last_rbutton_time,
                    _agent_lmb_menu_item_kind,
                    _agent_lmb_menu_item_name,
                    _agent_last_dblclick_time,
                    lmb_on_menu=_agent_lmb_hit_context_menu,
                )
            )
            # Win11 Command Bar paste button
            if _is_windows_11() and not recent_paste_click:
                if _cursor_in_explorer_command_bar() and (time.time() - (_agent_last_lbutton_time or 0)) < 2.0:
                    recent_paste_click = True
            is_user_paste = recent_ctrl or recent_paste_click

            if not _pending_info:
                info = read_shared_pending_offer()
                if info and isinstance(info, dict):
                    _pending_info.clear()
                    _pending_info.update(info)
                    _agent_allow_delayed = True
                    flist = _pending_info.get("files") or []
                    try:
                        from os_utils.windows_clipboard import clipboard_sync_manager
                        if clipboard_sync_manager:
                            clipboard_sync_manager.pending_remote_files = list(flist)
                            clipboard_sync_manager._reoffer_files = list(flist)
                            clipboard_sync_manager._allow_delayed = True
                            clipboard_sync_manager._force_delayed_setup = True
                    except Exception:
                        pass
                    agent_print(f"[ClipboardAgent] RENDERFORMAT nap _pending_info tu shared file: {len(flist)} files.")

            if _pending_info and not _agent_allow_delayed:
                log_overwrite_conflict(
                    f"RENDERFORMAT re-arm allow_delayed=True (files pending from client)"
                )
                _agent_allow_delayed = True
            if not _pending_info or not _agent_allow_delayed:
                log_overwrite_conflict(
                    f"RENDERFORMAT EXIT early: no_pending_or_delayed "
                    f"pending={bool(_pending_info)} allow_delayed={_agent_allow_delayed}"
                )
                empty_hdrop = create_hdrop_data([])
                if empty_hdrop:
                    _ignore_destroy = True
                    try:
                        res = fn_SetClipboardData(CF_HDROP, empty_hdrop)
                        if not res:
                            fn_GlobalFree(empty_hdrop)
                    finally:
                        _ignore_destroy = False
                return 0
            if _is_rendering:
                agent_print("[ClipboardAgent] WM_RENDERFORMAT trung (cung GetData) — HDROP rỗng.")
                log_overwrite_conflict("RENDERFORMAT EXIT: is_rendering trung")
                if _offer_empty_hdrop():
                    _agent_dummy_h_active = True
                return 0

            # Nếu là thao tác Paste thực tế của user (Ctrl+V hoặc click Paste) thì KHÔNG bị chặn bởi suppress/finish.
            if not is_user_paste:
                if (
                    time.time() < _agent_suppress_render_until
                    or time.time() < (_agent_last_paste_finish_time or 0) + 0.8
                ):
                    agent_print("[ClipboardAgent] Sau Rearm / Hoàn tất paste — HDROP rỗng, không tải ngầm.")
                    log_overwrite_conflict("RENDERFORMAT EXIT: suppress_after_finish_or_rearm")
                    if _offer_empty_hdrop():
                        _agent_dummy_h_active = True
                    return 0
            else:
                _agent_suppress_render_until = 0.0

            # Kiểm tra nếu là truy vấn từ menu chuột phải (context menu) thì tránh tải file thực tế lúc này
            is_menu = check_is_menu_query(
                _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_ctrl_v_time,
                expect_repaste=time.time() < _agent_expect_repaste_until,
                lmb_on_menu=_agent_lmb_hit_context_menu,
                menu_item_kind=_agent_lmb_menu_item_kind,
                last_dblclick=_agent_last_dblclick_time,
            )
            is_probe_proc = (
                (opener_p in _CLIPBOARD_PROBE_PROCS and opener_p not in _EXPLORER_CLIPBOARD_PROCS)
                or (fg_p in _CLIPBOARD_PROBE_PROCS and fg_p not in _EXPLORER_CLIPBOARD_PROCS)
                or _is_taskbar_or_taskmgr_hwnd(opener_hwnd)
                or _is_taskbar_or_taskmgr_hwnd(fg_hwnd)
            )
            if (not is_exp_target) or is_probe_proc or is_menu == "PROBE" or has_clip_text:
                agent_print(f"[ClipboardAgent] Probe/non-explorer tu process {opener_p or fg_p or 'probe'} — empty HDROP.")
                log_overwrite_conflict(f"RENDERFORMAT EXIT: non-explorer/probe opener={opener_p} fg={fg_p} has_text={has_clip_text}")
                if _offer_empty_hdrop():
                    _agent_dummy_h_active = True
                return 0

            if is_menu in ("MENU", "BACKGROUND"):
                if is_user_paste:
                    is_menu = False
                    log_overwrite_conflict(
                        f"RENDERFORMAT {is_menu} → PASTE (gesture "
                        f"{_agent_paste_gesture_id}>{_agent_consumed_gesture_id} "
                        f"kind={_agent_lmb_menu_item_kind!r} ctrl_v={recent_ctrl} rmb_paste={recent_paste_click})"
                    )
                else:
                    if is_menu == "MENU":
                        agent_print("[ClipboardAgent] Phát hiện truy vấn menu. Dummy HDROP, chờ user dán...")
                        log_overwrite_conflict(
                            f"RENDERFORMAT EXIT: MENU probe (chua paste) kind={_agent_lmb_menu_item_kind!r}"
                        )
                        if _offer_probe_hdrop(_pending_info.get("files")):
                            _agent_dummy_h_active = True
                        _schedule_scrub_probe(_agent_cached_explorer_path)
                    else:
                        agent_print("[ClipboardAgent] Probe Explorer — probe HDROP.")
                        log_overwrite_conflict("RENDERFORMAT EXIT: BACKGROUND probe")
                        if _offer_probe_hdrop(_pending_info.get("files")):
                            _agent_dummy_h_active = True
                    return 0

            living = any(
                j.get("allow") and not (j.get("event") and j["event"].is_set())
                for j in _agent_jobs.values()
            )
            same_gesture = _agent_paste_gesture_id <= _agent_consumed_gesture_id
            time_since_paste = time.time() - float(_agent_last_paste_start or 0)
            time_since_finish = time.time() - float(_agent_last_paste_finish_time or 0)
            if living or (same_gesture and time_since_paste < 0.8) or (same_gesture and time_since_finish < 0.8):
                agent_print(
                    f"[ClipboardAgent] WM_RENDERFORMAT coalesce (living={living}, "
                    f"elapsed_start={time_since_paste:.2f}s, elapsed_finish={time_since_finish:.2f}s) — trả empty HDROP."
                )
                log_overwrite_conflict(
                    f"RENDERFORMAT EXIT: living={living} recent paste elapsed_start={time_since_paste:.2f}s "
                    f"elapsed_finish={time_since_finish:.2f}s"
                )
                if _offer_empty_hdrop():
                    _agent_dummy_h_active = True
                return 0

            # Paste mới: gesture mới HOẶC Ctrl+V / click Paste sau lần paste trước.
            fresh_input = (
                _agent_last_ctrl_v_time > _agent_last_paste_start + 0.08
                or (
                    _agent_last_lbutton_time > _agent_last_paste_start + 0.08
                    and _agent_last_lbutton_time > (_agent_last_rbutton_time or 0)
                    and (
                        _agent_lmb_hit_context_menu
                        or _menu_item_counts_as_paste(_agent_lmb_menu_item_kind)
                        or _is_recent_rmb_paste_click_unified(
                            _agent_last_lbutton_time,
                            _agent_last_rbutton_time,
                            _agent_lmb_menu_item_kind,
                            _agent_lmb_menu_item_name,
                            _agent_last_dblclick_time,
                            lmb_on_menu=_agent_lmb_hit_context_menu,
                        )
                    )
                )
            )
            if same_gesture and not fresh_input:
                agent_print("[ClipboardAgent] GetData trùng (chưa có Paste mới) — không mở dialog thêm.")
                log_overwrite_conflict(
                    f"RENDERFORMAT EXIT: coalesce same_gesture living={living} fresh={fresh_input}"
                )
                if _offer_empty_hdrop():
                    _agent_dummy_h_active = True
                return 0
            if _agent_xfer_cancel_at and not living:
                new_kb = _agent_last_ctrl_v_time > _agent_xfer_cancel_at + 0.15
                new_menu = (
                    _agent_last_lbutton_time > _agent_xfer_cancel_at + 0.15
                    and _agent_last_rbutton_time > _agent_xfer_cancel_at
                    and _agent_last_lbutton_time > _agent_last_rbutton_time
                    and (
                        _agent_lmb_hit_context_menu
                        or _menu_item_counts_as_paste(_agent_lmb_menu_item_kind)
                        or _is_recent_rmb_paste_click_unified(
                            _agent_last_lbutton_time,
                            _agent_last_rbutton_time,
                            _agent_lmb_menu_item_kind,
                            _agent_lmb_menu_item_name,
                            _agent_last_dblclick_time,
                            lmb_on_menu=_agent_lmb_hit_context_menu,
                        )
                    )
                )
                if not new_kb and not new_menu:
                    agent_print("[ClipboardAgent] Sau Hủy chưa có Paste mới — HDROP rỗng, không mở dialog.")
                    log_overwrite_conflict("RENDERFORMAT EXIT: after_cancel no new paste")
                    if _offer_empty_hdrop():
                        _agent_dummy_h_active = True
                    return 0

            log_overwrite_conflict(
                f"RENDERFORMAT → PASTE OK is_menu={is_menu!r} fresh={fresh_input} "
                f"living={living} → conflict_check"
            )
            if fresh_input and (not living) and (time_since_finish >= 0.5 or not same_gesture):
                _note_paste_gesture()
            _is_rendering = True
            try:
                _agent_trigger_paste(source="render_format")
            finally:
                _is_rendering = False
            return 0

        if msg == WM_DESTROYCLIPBOARD and not _ignore_destroy:
            if is_own_clipboard_write():
                return 0
            _yield_clipboard_to_user("destroy")
            agent_print("[ClipboardAgent] WM_DESTROYCLIPBOARD → không cướp clipboard user; giữ PENDING từ client.")
            return 0

        return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _bridge_paste_trigger(source="menu_paste", dest=None):
        nonlocal _agent_paste_gesture_id, _agent_consumed_gesture_id, _agent_lmb_hit_context_menu
        nonlocal _agent_lmb_menu_item_kind, _agent_last_lbutton_time, _agent_last_ctrl_v_time
        nonlocal _agent_cached_explorer_path, _agent_last_menu_paste_trigger_time
        nonlocal _agent_suppress_render_until, _agent_allow_delayed
        now = time.time()
        _agent_paste_gesture_id += 1
        _agent_suppress_render_until = 0.0
        if not _pending_info:
            info = read_shared_pending_offer()
            if info:
                _pending_info.clear()
                _pending_info.update(info)
                flist = _pending_info.get("files") or []
                try:
                    from os_utils.windows_clipboard import clipboard_sync_manager
                    if clipboard_sync_manager:
                        clipboard_sync_manager.pending_remote_files = list(flist)
                except Exception:
                    pass
        if _pending_info:
            _agent_allow_delayed = True
        if source in ("ctrl_v", "shift_ins"):
            _agent_last_ctrl_v_time = now
        else:
            _agent_last_lbutton_time = now
            _agent_lmb_hit_context_menu = True
            _agent_lmb_menu_item_kind = "paste"
        if dest and os.path.isdir(dest) and not _is_transfer_staging_dir(dest):
            _agent_cached_explorer_path = dest
        try:
            from utils.logger import log_overwrite_conflict
            log_overwrite_conflict(
                f"BRIDGE PASTE TRIGGER source={source!r} dest={dest!r} "
                f"gesture={_agent_paste_gesture_id}/{_agent_consumed_gesture_id} "
                f"pending={bool(_pending_info)}"
            )
        except Exception:
            pass
        if not _pending_info:
            info = read_shared_pending_offer()
            if info:
                _pending_info.clear()
                _pending_info.update(info)
        if _pending_info:
            if now - float(_agent_last_menu_paste_trigger_time or 0) >= 0.5:
                _agent_last_menu_paste_trigger_time = now
                threading.Thread(
                    target=_agent_trigger_paste,
                    args=(source,),
                    kwargs={"dest_override": dest},
                    daemon=True,
                    name="AgentBridgedPasteTrigger",
                ).start()

    def _create_agent_window():
        """Tạo hidden Win32 window cho agent, chạy trong luồng riêng với message loop."""
        nonlocal _agent_hwnd
        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, ctypes.c_void_p, ctypes.c_uint,
            ctypes.c_size_t, ctypes.c_size_t
        )
        _wndproc_ref = WNDPROC(_agent_wndproc)

        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize",        wintypes.UINT),
                ("style",         wintypes.UINT),
                ("lpfnWndProc",   WNDPROC),
                ("cbClsExtra",    ctypes.c_int),
                ("cbWndExtra",    ctypes.c_int),
                ("hInstance",     ctypes.c_void_p),
                ("hIcon",         ctypes.c_void_p),
                ("hCursor",       ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName",  wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
                ("hIconSm",       ctypes.c_void_p),
            ]

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # Định nghĩa kiểu dữ liệu chuẩn Win32 API cho môi trường 64-bit
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p

        user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
        user32.RegisterClassExW.restype = wintypes.ATOM

        user32.CreateWindowExW.argtypes = [
            ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR,
            ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        ]
        user32.CreateWindowExW.restype = ctypes.c_void_p

        cls_name = "AntigravityClipboardAgentWnd"
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = _wndproc_ref
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = cls_name
        user32.RegisterClassExW(ctypes.byref(wc))

        hwnd = user32.CreateWindowExW(
            0, cls_name, "ClipboardAgent",
            0, 0, 0, 0, 0,
            None, None, wc.hInstance, None
        )
        _agent_hwnd = hwnd
        write_shared_agent_hwnd(hwnd)
        agent_print(f"[ClipboardAgent] Window ẩn đã tạo. HWND={hwnd}")
        try:
            from os_utils.windows_clipboard import clipboard_sync_manager
            if clipboard_sync_manager:
                clipboard_sync_manager._agent_hwnd = hwnd
                clipboard_sync_manager._agent_paste_callback = _bridge_paste_trigger
                agent_print(f"[ClipboardAgent] Bridge registered with clipboard_sync_manager (hwnd={hwnd})")
        except Exception as e:
            agent_print(f"[ClipboardAgent] Bridge register error: {e}")
        try:
            add_ok = user32.AddClipboardFormatListener(ctypes.c_void_p(hwnd))
            agent_print(f"[ClipboardAgent] AddClipboardFormatListener={add_ok}")
        except Exception as e:
            agent_print(f"[ClipboardAgent] AddClipboardFormatListener lỗi: {e}")
        if _pending_info and _agent_allow_delayed:
            user32.PostMessageW(ctypes.c_void_p(hwnd), WM_USER_SETUP_DELAYED, 0, 0)

        def _stamp_ctrl_v():
            nonlocal _agent_last_ctrl_v_time, _agent_dummy_h_active, _agent_allow_delayed, _agent_suppress_render_until
            _agent_last_ctrl_v_time = time.time()
            _agent_suppress_render_until = 0.0
            _note_paste_gesture()
            if _pending_info:
                _agent_allow_delayed = True
            if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                _agent_dummy_h_active = False
                ctypes.windll.user32.PostMessageW(
                    ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0
                )

        def _stamp_lbutton():
            nonlocal _agent_last_lbutton_time, _agent_dummy_h_active, _agent_lmb_hit_context_menu
            nonlocal _agent_lmb_menu_item_kind, _agent_last_menu_paste_trigger_time
            _register_lmb_down()
            on_self = _cursor_over_current_process()
            is_paste = False
            if not on_self:
                is_paste = _agent_lmb_is_context_paste(on_self)
            if is_paste:
                now_trig = time.time()
                if now_trig - _agent_last_menu_paste_trigger_time >= 0.8:
                    _agent_last_menu_paste_trigger_time = now_trig
                    threading.Thread(
                        target=_agent_trigger_paste,
                        args=("menu_paste",),
                        daemon=True,
                        name="AgentMenuPasteTrigger",
                    ).start()
            if not is_paste and _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                _agent_dummy_h_active = False
                ctypes.windll.user32.PostMessageW(
                    ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0
                )

        def _stamp_rbutton():
            nonlocal _agent_last_rbutton_time, _agent_dummy_h_active, _agent_lmb_hit_context_menu
            nonlocal _agent_lmb_menu_item_kind, _agent_rmb_cursor_pos, _agent_rmb_is_taskbar, _agent_cached_explorer_path
            _agent_last_rbutton_time = time.time()
            _agent_lmb_hit_context_menu = False
            _agent_lmb_menu_item_kind = ""
            cxy = None
            try:
                cxy = _cursor_xy()
            except Exception:
                cxy = None
            if cxy and _is_taskbar_or_taskmgr_at_point(cxy):
                _agent_rmb_is_taskbar = True
                _agent_rmb_cursor_pos = None
            else:
                _agent_rmb_is_taskbar = False
                _agent_rmb_cursor_pos = cxy
                try:
                    set_global_rmb_pos(cxy)
                except Exception:
                    pass
                try:
                    p = query_explorer_folder_path(allow_open_clipboard=False)
                    if p and os.path.isdir(p) and not _is_transfer_staging_dir(p):
                        _agent_cached_explorer_path = p
                except Exception:
                    pass
            if _agent_dummy_h_active and _agent_allow_delayed and _agent_hwnd:
                _agent_dummy_h_active = False
                ctypes.windll.user32.PostMessageW(
                    ctypes.c_void_p(_agent_hwnd), WM_USER_SETUP_DELAYED, 0, 0
                )

        hk_kb, hk_mouse = _install_paste_ll_hooks(_stamp_ctrl_v, _stamp_lbutton, _stamp_rbutton)
        agent_print(f"[ClipboardAgent] LL hooks kb={hk_kb} mouse={hk_mouse}")

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    threading.Thread(target=_create_agent_window, daemon=True, name="AgentWin32MsgLoop").start()
    time.sleep(0.1)  # Chờ window khởi tạo

    def _agent_text_poll_loop():
        last_seq = 0
        last_sent_text = None
        while True:
            time.sleep(0.4)
            try:
                if _is_rendering or is_own_clipboard_write():
                    continue
                if not should_preserve_user_clipboard(_agent_hwnd):
                    continue
                if _agent_allow_delayed and _pending_info:
                    continue
                seq = get_clipboard_sequence_number()
                if not seq or seq == last_seq:
                    continue
                files = get_clipboard_files(retries=1)
                if files and not _paths_are_probe_or_xfer(files):
                    _agent_emit_copied_files(force=True)
                    last_seq = seq
                    agent_print("[ClipboardAgent] Poll: đã gửi COPIED_FILES.")
                    continue
                text = get_clipboard_text()
                if not text or text == last_sent_text:
                    last_seq = seq
                    continue
                _yield_clipboard_to_user("local text poll")
                try:
                    import win32pipe, win32file, json
                    pipe_name = r"\\.\pipe\RemoteDesktopClipboardUpPipe"
                    win32pipe.WaitNamedPipe(pipe_name, 3000)
                    pipe_handle = win32file.CreateFile(pipe_name, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, None)
                    win32file.WriteFile(pipe_handle, ("COPIED_TEXT|" + json.dumps(text)).encode("utf-8"))
                    win32file.CloseHandle(pipe_handle)
                    last_seq = seq
                    last_sent_text = text
                    agent_print("[ClipboardAgent] Poll: đã gửi COPIED_TEXT.")
                except Exception:
                    pass
            except Exception:
                pass

    threading.Thread(target=_agent_text_poll_loop, daemon=True, name="AgentClipPoll").start()

    def trigger_cancel(paste_id=None):
        """Dừng một (hoặc mọi) lần tải; giữ PENDING để user Paste lại."""
        nonlocal _agent_expect_repaste_until, _agent_accept_files, _agent_allow_xfer
        nonlocal _agent_xfer_cancel_at, _agent_suppress_render_until, _agent_last_ctrl_v_time, _agent_ctrl_v_held
        nonlocal _agent_download_active

        def _stop_job(pid, job):
            leftover = [
                p for p in list(job.get("paths") or [])
                if p and (
                    _path_in_xfer_staging(p)
                    or _is_probe_stub_name(p)
                    or _is_transfer_junk_at_dest(p)
                )
            ]
            job["allow"] = False
            job["accept"] = False
            job["conflict_choice"] = "cancel"
            try:
                job["conflict_event"].set()
            except Exception:
                pass
            try:
                job["event"].set()
            except Exception:
                pass
            job_meta = list(((job.get("info") or {}).get("files") if job else None) or [])
            _agent_cleanup_partial(leftover, files_meta=job_meta, wipe_all_staging=False)
            try:
                threading.Timer(
                    0.4,
                    lambda p=list(leftover), m=job_meta: _agent_cleanup_partial(p, files_meta=m, wipe_all_staging=False),
                ).start()
                threading.Timer(
                    1.2,
                    lambda p=list(leftover), m=job_meta: _agent_cleanup_partial(p, files_meta=m, wipe_all_staging=False),
                ).start()
            except Exception:
                pass
            gui_queue.put(("cancel", pid))
            _release_agent_file_request()

        if paste_id is None:
            for pid, job in list(_agent_jobs.items()):
                _stop_job(pid, job)
        else:
            try:
                paste_id = int(paste_id)
            except Exception:
                pass
            job = _agent_jobs.get(paste_id)
            if job:
                _stop_job(paste_id, job)
            else:
                gui_queue.put(("cancel", paste_id))

        leftover = list(_files_ready_paths)
        if leftover and paste_id is None:
            _files_ready_paths.clear()
            _files_ready_event.set()
            _agent_cleanup_partial(leftover)

        still_allow = any(j.get("allow") for j in _agent_jobs.values())
        if not still_allow:
            _clear_agent_paste_gesture_flags(1.5)
            _agent_allow_xfer = False
            _agent_accept_files = False
            _agent_download_active = False
            _agent_xfer_cancel_at = time.time()
            _agent_suppress_render_until = max(_agent_suppress_render_until, time.time() + 1.5)
            _agent_last_ctrl_v_time = 0.0
            _agent_ctrl_v_held = False
            _agent_expect_repaste_until = time.time() + 86400.0
        if (not still_allow) and _is_rendering and _agent_hwnd:
            try:
                ctypes.windll.user32.PostMessageW(
                    ctypes.c_void_p(_agent_hwnd), WM_USER_UNBLOCK_PASTE, 0, 0
                )
            except Exception:
                pass
        agent_print(f"[ClipboardAgent] Đã hủy tải paste_id={paste_id}; jobs={list(_agent_jobs.keys())}.")

    def trigger_cancel_win32(paste_id=None):
        """Nút Hủy trong dialog → host dừng gửi/nhận và xóa file tạm."""
        _send_cancel_to_host(paste_id)
        trigger_cancel(paste_id)

    def _open_paste_progress_dialog(paste_id, display_name, total_size, dest_dir):
        """Một paste_id → một dialog. Paste song song = nhiều dialog (stack_index)."""
        nonlocal active_dialog
        if paste_id is not None and active_dialogs.get(paste_id):
            dlg = active_dialogs[paste_id]
            try:
                dlg.deiconify()
                dlg.lift()
                dlg.attributes("-topmost", True)
                dlg.update_progress(0, status="")
            except Exception:
                pass
            return dlg
        job = _agent_jobs.get(paste_id) if paste_id is not None else None
        if job is not None and not job.get("allow"):
            agent_print("[ClipboardAgent] Bo dialog (job da Huy).")
            return None
        job_files = ((job.get("info") or {}).get("files") if job else None) or []
        if not job_files and job is not None:
            job_files = job.get("requested_files") or []
        kind, name = _copy_batch_kind_and_name(job_files, display_name)
        pending_kind = ((job.get("info") or {}).get("item_kind") if job else None) or (
            _pending_info.get("item_kind") if _pending_info else None
        )
        if pending_kind in ("file", "folder") and not job_files:
            kind = pending_kind
        stack = len([d for d in active_dialogs.values() if d])
        try:
            sz = int(total_size or 0)
        except Exception:
            sz = 0
        if sz <= 0:
            sz = 1
        dlg = ProgressDialog(
            root, file_download_dialog_title(), name or display_name or _("Tệp tin"), sz,
            on_cancel=lambda p=paste_id: trigger_cancel_win32(p),
            dest_dir=dest_dir,
            reserve_finalize=True,
            stack_index=stack,
            job_id=paste_id,
            item_kind=kind,
        )
        if paste_id is not None:
            active_dialogs[paste_id] = dlg
        active_dialog = dlg
        try:
            dlg.after(0, getattr(dlg, "_force_show", lambda: None))
            dlg.after(100, getattr(dlg, "_force_show", lambda: None))
            dlg.after(300, getattr(dlg, "_force_show", lambda: None))
            dlg.after(800, getattr(dlg, "_force_show", lambda: None))
        except Exception:
            pass
        try:
            # Ép hiện ngay trên desktop user (capture remote sẽ thấy).
            dlg.update_idletasks()
            dlg.deiconify()
            dlg.lift()
            dlg.attributes("-topmost", True)
            if hasattr(dlg, "_force_show"):
                dlg._force_show()
        except Exception:
            pass
        agent_print(
            f"[ClipboardAgent] Mo dialog tien trinh paste_id={paste_id} "
            f"dest={dest_dir} stack={stack} size={sz} living={list(active_dialogs.keys())}"
        )
        return dlg

    def poll_gui_queue():
        nonlocal active_dialog, _agent_meta_arrival_time, _agent_allow_xfer, _agent_suppress_render_until
        nonlocal _agent_conflict_choice, _agent_conflict_skip, _agent_allow_delayed, _agent_clip_seq_at_pending, _agent_paste_coalesce_until, _agent_force_delayed_setup, _agent_pending_offer_id
        nonlocal _agent_repaste_local_by_name, _agent_expect_repaste_until, _in_poll_gui_queue, _active_conflict_job
        if _in_poll_gui_queue:
            return
        _in_poll_gui_queue = True
        while not gui_queue.empty():
            try:
                action, val = gui_queue.get_nowait()
                if action == "text":
                    agent_print(f"[ClipboardAgent] Đang nạp text vào Clipboard...")
                    _pending_info.clear()
                    _agent_allow_delayed = False
                    set_clipboard_text(val, owner_hwnd=_agent_hwnd)
                elif action == "files":
                    agent_print("[ClipboardAgent] Bỏ qua action files (không dán HDROP im lặng).")
                elif action == "pending":
                    # Host gửi PENDING: → setup delayed rendering nếu window đã sẵn sàng
                    info = val
                    oid = 0
                    try:
                        oid = int((info or {}).get("offer_id") or 0) if isinstance(info, dict) else 0
                    except Exception:
                        oid = 0
                    new_files = (info.get("files") if isinstance(info, dict) else None) or []
                    new_fp = _file_offer_fp(new_files)
                    old_fp = _file_offer_fp(_pending_info.get("files") if _pending_info else None)
                    if oid and oid < _agent_pending_offer_id:
                        same = new_fp == old_fp
                        if same:
                            agent_print(f"[ClipboardAgent] Bỏ PENDING cũ offer={oid} (đang giữ {_agent_pending_offer_id}).")
                            continue
                        agent_print(f"[ClipboardAgent] PENDING offer={oid} < {_agent_pending_offer_id} nhưng file khác — nhận copy mới.")
                    if oid:
                        _agent_pending_offer_id = oid
                    # Copy bộ file mới → xóa cache paste local của offer cũ.
                    if new_fp != old_fp:
                        _agent_repaste_local_by_name = {}
                    _pending_info.clear()
                    if isinstance(info, dict):
                        _pending_info.update(info)
                        files = info.get("files")
                        if isinstance(files, list):
                            _pending_info["files"] = [dict(f) if isinstance(f, dict) else f for f in files]
                    try:
                        flist = _pending_info.get("files") or []
                        from os_utils.windows_clipboard import clipboard_sync_manager
                        if clipboard_sync_manager:
                            clipboard_sync_manager.pending_remote_files = list(flist)
                            clipboard_sync_manager._reoffer_files = list(flist)
                            clipboard_sync_manager._allow_delayed = True
                            clipboard_sync_manager._force_delayed_setup = True
                            clipboard_sync_manager.meta_arrival_time = time.time()
                            clipboard_sync_manager._expect_repaste_until = time.time() + 86400.0
                    except Exception:
                        pass
                    _agent_clip_seq_at_pending = get_clipboard_sequence_number()
                    # Copy mới từ client luôn cập nhật delayed clipboard (file 2, 3, n).
                    _agent_force_delayed_setup = True
                    _agent_allow_delayed = True
                    _agent_expect_repaste_until = time.time() + 86400.0
                    display_name = info.get("display_name", "Files") if isinstance(info, dict) else "Files"
                    total_size = info.get("total_size", 0) if isinstance(info, dict) else 0
                    if not _agent_jobs:
                        _files_ready_event.clear()
                        _files_ready_paths.clear()
                    _agent_meta_arrival_time = time.time()
                    agent_print(f"[ClipboardAgent] Nhận PENDING: '{display_name}' ({total_size} bytes). Đang setup delayed rendering...")
                    try:
                        names = []
                        for f in (info.get("files") or [])[:8]:
                            if isinstance(f, dict):
                                names.append(f.get("name"))
                        log_overwrite_conflict(
                            f"PENDING recv display={display_name!r} size={total_size} "
                            f"n={len(info.get('files') or [])} names={names} "
                            f"→ delayed CF_HDROP (cho Paste tren HOST)"
                        )
                    except Exception:
                        pass
                    if _agent_allow_delayed and _agent_hwnd:
                        ctypes.windll.user32.PostMessageW(
                            ctypes.c_void_p(_agent_hwnd),
                            WM_USER_SETUP_DELAYED, 0, 0
                        )
                    elif not _agent_hwnd:
                        agent_print("[ClipboardAgent] HWND chưa sẵn sàng, lên lịch thử lại setup.")
                        def _retry_setup():
                            if _agent_hwnd and _agent_allow_delayed:
                                ctypes.windll.user32.PostMessageW(
                                    ctypes.c_void_p(_agent_hwnd),
                                    WM_USER_SETUP_DELAYED, 0, 0
                                )
                        root.after(100, _retry_setup)
                elif action == "pipe_cancel":
                    agent_print("[ClipboardAgent] Nhận tín hiệu CANCEL từ Pipe. Đang hủy...")
                    trigger_cancel(val)
                elif action == "files_ready":
                    paste_tok, paths = _parse_files_pipe_payload(val)
                    job = None
                    if paste_tok is not None:
                        job = _agent_jobs.get(paste_tok)
                        if job is None:
                            try:
                                job = _agent_jobs.get(int(paste_tok))
                            except Exception:
                                pass
                    if job is None:
                        got = [os.path.basename(p).lower() for p in paths]
                        for cand in _agent_jobs.values():
                            if not cand.get("accept"):
                                continue
                            meta = ((cand.get("requested_files") or None) or (cand.get("info") or {}).get("files") or [])
                            exp = [
                                os.path.basename(str(f.get("name") or "").replace("\\", "/")).lower()
                                for f in meta
                                if isinstance(f, dict)
                            ]
                            exp_top = {
                                str(f.get("name") or "").replace("\\", "/").split("/")[0].lower()
                                for f in meta
                                if isinstance(f, dict) and f.get("name")
                            }
                            if got and (
                                (exp and set(got) <= set(exp))
                                or (exp_top and set(got) <= exp_top)
                            ):
                                job = cand
                                break
                    if job is None or not job.get("accept"):
                        agent_print(f"[ClipboardAgent] Bỏ FILES trễ (paste_tok={paste_tok}, không tìm thấy job / đã hủy).")
                        # Chỉ dọn staging — paths có thể đã là file đích sau Paste xong.
                        staging_only = [
                            p for p in (paths or [])
                            if p and (
                                _path_in_xfer_staging(p)
                                or _is_transfer_staging_dir(os.path.dirname(os.path.abspath(p)))
                            )
                        ]
                        if staging_only:
                            _agent_cleanup_partial(staging_only, files_meta=[], wipe_all_staging=False)
                        _release_agent_file_request()
                        continue
                    job["paths"][:] = paths
                    job["event"].set()
                    agent_print(f"[ClipboardAgent] files_ready paste_id={job.get('paste_id')}: {len(paths)} file đã sẵn sàng.")
                    _release_agent_file_request()
                elif action == "start":
                    display_name, total_size = val[0], val[1]
                    dest_dir = val[2] if len(val) > 2 else None
                    paste_id = val[3] if len(val) > 3 else None
                    _open_paste_progress_dialog(paste_id, display_name, total_size, dest_dir)
                elif action == "progress":
                    if isinstance(val, (tuple, list)):
                        pid, nbytes = (val[0] if val else None), (val[1] if len(val) > 1 else 0)
                    else:
                        pid, nbytes = None, val
                    dlg = None
                    if pid is not None:
                        dlg = active_dialogs.get(pid)
                        if dlg is None:
                            try: dlg = active_dialogs.get(int(pid))
                            except Exception: pass
                        if dlg is None:
                            dlg = active_dialogs.get(str(pid))
                    if dlg is None:
                        dlg = active_dialog
                    if dlg is None and len(active_dialogs) == 1:
                        dlg = next(iter(active_dialogs.values()), None)
                    if dlg:
                        try: dlg.update_progress(nbytes)
                        except: pass
                    job = _agent_jobs.get(pid) if pid is not None else None
                    if job is not None:
                        job["last_progress_at"] = time.time()
                        try:
                            job["last_progress_bytes"] = int(nbytes or 0)
                        except Exception:
                            pass
                elif action == "finalize_start":
                    if isinstance(val, (tuple, list)):
                        n, pid = (val[0] if val else 0), (val[1] if len(val) > 1 else None)
                    else:
                        n, pid = val, None
                    dlg = active_dialogs.get(pid) if pid is not None else active_dialog
                    if dlg is None and pid is not None:
                        try: dlg = active_dialogs.get(int(pid))
                        except Exception: pass
                    if dlg is None and pid is not None:
                        dlg = active_dialogs.get(str(pid))
                    if dlg is None and len(active_dialogs) == 1:
                        dlg = next(iter(active_dialogs.values()), None)
                    if dlg:
                        try: dlg.begin_finalize(n or 0)
                        except: pass
                elif action == "finalize_progress":
                    if isinstance(val, (tuple, list)):
                        n, pid = (val[0] if val else 0), (val[1] if len(val) > 1 else None)
                    else:
                        n, pid = val, None
                    dlg = active_dialogs.get(pid) if pid is not None else active_dialog
                    if dlg is None and pid is not None:
                        try: dlg = active_dialogs.get(int(pid))
                        except Exception: pass
                    if dlg is None and pid is not None:
                        dlg = active_dialogs.get(str(pid))
                    if dlg is None and len(active_dialogs) == 1:
                        dlg = next(iter(active_dialogs.values()), None)
                    if dlg:
                        try: dlg.add_finalize_bytes(n or 0)
                        except: pass
                elif action == "end":
                    pid = val
                    dlg = None
                    if pid is not None:
                        dlg = active_dialogs.pop(pid, None)
                        if dlg is None:
                            try:
                                dlg = active_dialogs.pop(int(pid), None)
                            except Exception:
                                pass
                        if dlg is None:
                            dlg = active_dialogs.pop(str(pid), None)
                    if dlg is None and pid is not None:
                        for k, d in list(active_dialogs.items()):
                            if getattr(d, "job_id", None) in (pid, str(pid)):
                                dlg = active_dialogs.pop(k, None)
                                break
                    if dlg is None and pid is None:
                        if len(active_dialogs) == 1:
                            _, dlg = active_dialogs.popitem()
                        elif active_dialog:
                            dlg = active_dialog
                    if dlg:
                        try: dlg.mark_complete()
                        except: pass
                        def _close(d=dlg, j=pid):
                            nonlocal active_dialog
                            try:
                                d.on_cancel = None  # destroy ≠ Hủy — tránh xóa file vừa dán
                            except Exception:
                                pass
                            try: d.destroy()
                            except: pass
                            if active_dialog is d:
                                active_dialog = next(iter(active_dialogs.values()), None)
                        root.after(350, _close)
                elif action == "conflict_check":
                    dest_dir, files, display_name, total_size, paste_id = val
                    job = _agent_jobs.get(paste_id)
                    if job is None:
                        log_overwrite_conflict(
                            f"SKIP dialog: conflict_check paste_id={paste_id} — job KHONG CON"
                        )
                        continue
                    log_overwrite_conflict(
                        f"===== conflict_check START paste_id={paste_id} "
                        f"dest={dest_dir!r} files={len(files or [])} display={display_name!r} ====="
                    )
                    job["conflict_choice"] = "replace"
                    job["conflict_skip"] = set()
                    job["replace_keys"] = set()
                    job["ow_dialog_shown"] = False
                    job["ow_dialog_choice"] = None

                    def _file_dest_key(f_or_path):
                        """Key theo top-level (file/thư mục) — khớp conflict_skip."""
                        if isinstance(f_or_path, dict):
                            filename = str(f_or_path.get("name") or "")
                            top = filename.replace("\\", "/").strip("/").split("/")[0]
                            dest_path = os.path.join(dest_dir, top) if dest_dir else top
                        else:
                            dest_path = f_or_path
                        try:
                            return os.path.normcase(os.path.abspath(dest_path))
                        except Exception:
                            return dest_path

                    def _try_local_repaste(files_req=None, force_replace=False):
                        """Paste lại từ bản đã có trên host — không REQUEST_FILES lên client."""
                        nonlocal _agent_repaste_local_by_name
                        local_map = _agent_repaste_local_by_name or {}
                        use_files = files if files_req is None else files_req
                        if not dest_dir or not os.path.isdir(dest_dir) or not use_files or not local_map:
                            return False
                        local_srcs = []
                        already = []
                        for f in use_files:
                            name = f.get("name") if isinstance(f, dict) else str(f)
                            top = str(name).replace("\\", "/").strip("/").split("/")[0]
                            src = local_map.get(os.path.normcase(top)) or local_map.get(top)
                            if not src or not os.path.exists(src):
                                return False
                            try:
                                dst_guess = os.path.join(dest_dir, top)
                                if os.path.normcase(os.path.abspath(src)) == os.path.normcase(
                                    os.path.abspath(dst_guess)
                                ):
                                    if force_replace:
                                        # User chọn Replace cùng thư mục → phải tải lại.
                                        return False
                                    already.append(os.path.abspath(src))
                                    continue
                            except Exception:
                                return False
                            local_srcs.append(src)
                        if not local_srcs and not already:
                            return False
                        if already and not local_srcs:
                            job["paths"][:] = already
                            job["requested_files"] = [
                                dict(f) if isinstance(f, dict) else f for f in use_files
                            ]
                            job["event"].set()
                            agent_print(
                                f"[ClipboardAgent] LOCAL REPASTE already-in-place n={len(already)} → {dest_dir}"
                            )
                            try:
                                _notify_explorer_paths_changed(already + [dest_dir])
                            except Exception:
                                pass
                            return True
                        try:
                            import shutil
                            placed = list(already)
                            for src in local_srcs:
                                base = os.path.basename(str(src).rstrip("\\/"))
                                dst = os.path.join(dest_dir, base)
                                if os.path.exists(dst):
                                    if not force_replace:
                                        # Chưa hỏi Replace — không xóa file đích.
                                        agent_print(f"[ClipboardAgent] LOCAL REPASTE bo ghi de: {dst}")
                                        return False
                                    try:
                                        if os.path.isdir(dst):
                                            shutil.rmtree(dst)
                                        else:
                                            os.remove(dst)
                                    except Exception:
                                        pass
                                if os.path.isdir(src):
                                    shutil.copytree(src, dst)
                                else:
                                    shutil.copy2(src, dst)
                                placed.append(dst)
                                local_map[os.path.normcase(base)] = os.path.abspath(dst)
                            _agent_repaste_local_by_name = local_map
                            job["paths"][:] = placed
                            job["requested_files"] = [
                                dict(f) if isinstance(f, dict) else f for f in use_files
                            ]
                            job["event"].set()
                            agent_print(
                                f"[ClipboardAgent] LOCAL REPASTE n={len(placed)} → {dest_dir}"
                            )
                            try:
                                _notify_explorer_paths_changed(placed + [dest_dir])
                            except Exception:
                                pass
                            return True
                        except Exception as e:
                            agent_print(f"[ClipboardAgent] LOCAL REPASTE loi: {e}")
                            return False

                    def _files_not_skipped():
                        skip = set(job.get("conflict_skip") or [])
                        out = []
                        size = 0
                        for f in files:
                            if _file_dest_key(f) in skip:
                                continue
                            out.append(f)
                            try:
                                size += int(f.get("size") or 0)
                            except Exception:
                                pass
                        return out, size

                    def _begin_download(files_req=None, size=None):
                        req = files if files_req is None else files_req
                        sz = total_size if size is None else size
                        if not req:
                            agent_print(f"[ClipboardAgent] _begin_download: khong co file paste_id={paste_id}")
                            log_overwrite_conflict(
                                f"begin_download SKIP: khong co file paste_id={paste_id}"
                            )
                            return False
                        shown = bool(job.get("ow_dialog_shown"))
                        choice = job.get("ow_dialog_choice")
                        n_replace = len(job.get("replace_keys") or [])
                        n_skip = len(job.get("conflict_skip") or [])
                        log_overwrite_conflict(
                            f"begin_download paste_id={paste_id} n={len(req)} "
                            f"dialog_shown={shown} last_choice={choice!r} "
                            f"replace_keys={n_replace} skip={n_skip} dest={dest_dir!r}"
                        )
                        if not shown and n_replace == 0:
                            log_overwrite_conflict(
                                f"WARN: bat dau tai MA KHONG co dialog ghi de "
                                f"(co the khong conflict / thieu dest). paste_id={paste_id}"
                            )
                        job["requested_files"] = [dict(f) if isinstance(f, dict) else f for f in req]
                        # Đảm bảo dialog đang mở (start có thể tới trước / bị miss).
                        _open_paste_progress_dialog(
                            paste_id,
                            display_name,
                            sz,
                            dest_dir,
                        )
                        agent_print(
                            f"[ClipboardAgent] REQUEST_FILES paste_id={paste_id} "
                            f"n={len(req)} dest={dest_dir} dialogs={list(active_dialogs.keys())}"
                        )
                        _send_request_files_to_host(req, dest_dir, paste_id)
                        return True

                    def _done_conflict():
                        nonlocal _agent_paste_coalesce_until
                        _agent_paste_coalesce_until = time.time() + 0.35
                        log_overwrite_conflict(
                            f"conflict_done paste_id={paste_id} "
                            f"choice={job.get('conflict_choice')!r} "
                            f"dialog_shown={job.get('ow_dialog_shown')} "
                            f"dialog_choice={job.get('ow_dialog_choice')!r} "
                            f"replace={len(job.get('replace_keys') or [])} "
                            f"skip={len(job.get('conflict_skip') or [])}"
                        )
                        job["conflict_event"].set()

                    try:
                        if not dest_dir or not os.path.isdir(dest_dir) or _is_transfer_staging_dir(dest_dir):
                            if _agent_cached_explorer_path and os.path.isdir(_agent_cached_explorer_path) and not _is_transfer_staging_dir(_agent_cached_explorer_path):
                                dest_dir = _agent_cached_explorer_path
                                job['dest'] = dest_dir
                            else:
                                for _try in range(6):
                                    try:
                                        found = query_explorer_folder_path(allow_open_clipboard=False)
                                        if not found:
                                            found = query_explorer_folder_path(allow_open_clipboard=True)
                                        if found and os.path.isdir(found) and not _is_transfer_staging_dir(found):
                                            dest_dir = found
                                            job["dest"] = found
                                            agent_print(f"[ClipboardAgent] conflict: lay lai dest={found}")
                                            break
                                    except Exception:
                                        pass
                                    time.sleep(0.05)
                        if not dest_dir or not os.path.isdir(dest_dir) or _is_transfer_staging_dir(dest_dir):
                            if _agent_cached_explorer_path and os.path.isdir(_agent_cached_explorer_path) and not _is_transfer_staging_dir(_agent_cached_explorer_path):
                                dest_dir = _agent_cached_explorer_path
                                job['dest'] = dest_dir
                            else:
                                desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop")
                                if os.path.isdir(desktop_dir):
                                    dest_dir = desktop_dir
                                    job['dest'] = dest_dir
                                    agent_print(f"[ClipboardAgent] conflict: fallback dest=Desktop ({dest_dir})")
                        if not dest_dir or not os.path.isdir(dest_dir) or not files:
                            agent_print(
                                f"[ClipboardAgent] conflict: khong co dest hop le "
                                f"dest={dest_dir!r} — van tai, khong ghi de im lang."
                            )
                            log_overwrite_conflict(
                                f"NO DIALOG: thieu dest hop le dest={dest_dir!r} "
                                f"files={len(files or [])} → begin_download (khong hoi)"
                            )
                            if not _try_local_repaste():
                                _begin_download()
                            _done_conflict()
                            continue
                        cleanup_incomplete_named_files([dest_dir], files)
                        _schedule_scrub_probe(dest_dir)
                        conflicts = []
                        seen_conflict = set()
                        exists_checked = []
                        for f in files:
                            filename = str(f.get("name") or "")
                            if not filename:
                                continue
                            # Hỏi theo top-level (file hoặc thư mục) — giống Explorer.
                            top = filename.replace("\\", "/").strip("/").split("/")[0]
                            dest_path = os.path.join(dest_dir, top)
                            try:
                                key = os.path.normcase(os.path.abspath(dest_path))
                            except Exception:
                                key = dest_path
                            if key in seen_conflict:
                                continue
                            exists = os.path.exists(dest_path)
                            exists_checked.append(f"{top}:exists={exists}")
                            if not exists:
                                continue
                            expected = _file_expected_size(f) if top == filename.replace("\\", "/").strip("/") else None
                            # Không coi file user là junk chỉ vì size khác — chỉ stub/0-byte/probe.
                            if _is_transfer_junk_at_dest(dest_path, expected):
                                agent_print(f"[ClipboardAgent] conflict: xoa stub/junk {dest_path}")
                                log_overwrite_conflict(
                                    f"junk/stub xoa (khong hoi): {dest_path} expected={expected}"
                                )
                                _retry_remove_path(dest_path)
                                continue
                            try:
                                st = os.stat(dest_path)
                            except Exception as e:
                                log_overwrite_conflict(f"stat fail {dest_path}: {e}")
                                continue
                            seen_conflict.add(key)
                            source_info = {
                                "size": f.get("size", 0) if "/" not in filename.replace("\\", "/") else 0,
                                "mtime": f.get("mtime", 0),
                                "path": f.get("path") or filename,
                            }
                            # Folder paste: cộng size các file trong cùng top.
                            if os.path.isdir(dest_path) or "/" in filename.replace("\\", "/"):
                                try:
                                    source_info["size"] = sum(
                                        int(x.get("size") or 0)
                                        for x in files
                                        if isinstance(x, dict)
                                        and str(x.get("name") or "").replace("\\", "/").strip("/").split("/")[0] == top
                                    )
                                except Exception:
                                    pass
                            dest_info = {"size": st.st_size if os.path.isfile(dest_path) else source_info.get("size", 0), "mtime": st.st_mtime, "path": dest_path}
                            if os.path.isdir(dest_path):
                                try:
                                    dest_info["size"] = sum(
                                        os.path.getsize(os.path.join(r, n))
                                        for r, _d, ns in os.walk(dest_path)
                                        for n in ns
                                    )
                                except Exception:
                                    pass
                            conflicts.append((top, source_info, dest_info, dest_path))
                            agent_print(f"[ClipboardAgent] conflict detect: {top} @ {dest_path}")
                        log_overwrite_conflict(
                            f"scan dest={dest_dir} checked=[{'; '.join(exists_checked[:12])}] "
                            f"conflicts={len(conflicts)}"
                        )
                        agent_print(
                            f"[ClipboardAgent] conflict_check dest={dest_dir} "
                            f"files={len(files)} conflicts={len(conflicts)}"
                        )
                        if not conflicts:
                            log_overwrite_conflict(
                                f"NO DIALOG: khong co conflict (file dich chua ton tai "
                                f"hoac da bi coi junk). → begin_download"
                            )
                            # Không xung đột — local trước, không mở dialog tải nếu copy tại chỗ xong.
                            req, sz = _files_not_skipped()
                            if req:
                                if not _try_local_repaste(req):
                                    _begin_download(req, sz)
                            else:
                                job["event"].set()
                            _done_conflict()
                            continue
                        # Ẩn dialog tiến trình (nếu đã mở) để hộp ghi đè không bị che.
                        try:
                            pd = active_dialogs.get(paste_id)
                            if pd:
                                pd.withdraw()
                        except Exception:
                            pass
                        replace_all = False
                        skip_all = False
                        has_multiple = len(files) > 1 or len(conflicts) > 1
                        cancelled = False
                        idx = 0

                        def _skip_path(dp, j=job):
                            try:
                                j["conflict_skip"].add(os.path.normcase(os.path.abspath(dp)))
                            except Exception:
                                j["conflict_skip"].add(dp)

                        def _allow_replace(dp, j=job):
                            try:
                                j["replace_keys"].add(os.path.normcase(os.path.abspath(dp)))
                            except Exception:
                                j["replace_keys"].add(dp)

                        def _wait_mouse_idle():
                            try:
                                user32 = ctypes.windll.user32
                                idle_deadline = time.time() + 2.0
                                while time.time() < idle_deadline:
                                    lmb = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
                                    rmb = bool(user32.GetAsyncKeyState(0x02) & 0x8000)
                                    if not lmb and not rmb:
                                        break
                                    try:
                                        root.update()
                                    except Exception:
                                        pass
                                    time.sleep(0.02)
                                settle = time.time() + 0.45
                                while time.time() < settle:
                                    try:
                                        root.update()
                                    except Exception:
                                        pass
                                    time.sleep(0.02)
                            except Exception:
                                pass

                        def _ask_on_host():
                            """Fallback: ClassicCopyDialog trên desktop host (session remote)."""
                            nonlocal replace_all, skip_all, cancelled, idx
                            agent_print(
                                f"[ClipboardAgent] {len(conflicts)} xung đột — ClassicCopyDialog HOST "
                                f"paste_id={paste_id}"
                            )
                            log_overwrite_conflict(
                                f"WILL SHOW HOST DIALOG paste_id={paste_id} n_conflicts={len(conflicts)} "
                                f"names={[c[0] for c in conflicts]}"
                            )
                            _wait_mouse_idle()
                            while idx < len(conflicts):
                                filename, source_info, dest_info, dest_path = conflicts[idx]
                                if skip_all:
                                    _skip_path(dest_path)
                                    idx += 1
                                    continue
                                if replace_all:
                                    _allow_replace(dest_path)
                                    idx += 1
                                    continue
                                agent_print(f"[ClipboardAgent] Hoi ghi de HOST: {filename} → {dest_path}")
                                t0 = time.time()
                                log_overwrite_conflict(
                                    f"DIALOG CREATE start file={filename!r} dest={dest_path!r}"
                                )
                                dlg_retries = 0
                                dialog = None
                                choice = "cancel"
                                while True:
                                    try:
                                        dialog = ClassicCopyDialog(root, filename, source_info, dest_info, has_multiple)
                                        job["ow_dialog_shown"] = True
                                        log_overwrite_conflict(
                                            f"DIALOG SHOWN=YES file={filename!r} "
                                            f"winfo_exists={dialog.winfo_exists()} "
                                            f"try={dlg_retries}"
                                        )
                                        try:
                                            dialog.attributes("-topmost", True)
                                            dialog.lift()
                                            dialog.focus_force()
                                            dialog.grab_set()
                                            try:
                                                hwnd = int(dialog._hwnd() if hasattr(dialog, "_hwnd") else dialog.winfo_id())
                                                ctypes.windll.user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
                                            except Exception:
                                                pass
                                        except Exception as e_vis:
                                            log_overwrite_conflict(f"DIALOG raise/focus loi: {e_vis}")
                                        root.wait_window(dialog)
                                        choice = dialog.choice if dialog.choice else "cancel"
                                        elapsed = time.time() - t0
                                        job["ow_dialog_choice"] = choice
                                        log_overwrite_conflict(
                                            f"DIALOG CLOSED file={filename!r} choice={choice!r} "
                                            f"elapsed={elapsed:.2f}s"
                                        )
                                        if (
                                            elapsed < 0.5
                                            and choice in ("cancel", None, "")
                                            and dlg_retries < 1
                                        ):
                                            log_overwrite_conflict(
                                                f"WARN: dialog dong rat nhanh ({elapsed:.2f}s) — hoi lai"
                                            )
                                            dlg_retries += 1
                                            t0 = time.time()
                                            continue
                                        break
                                    except Exception as e_dlg:
                                        log_overwrite_conflict(
                                            f"DIALOG SHOWN=NO / EXCEPTION file={filename!r}: {e_dlg}"
                                        )
                                        choice = "cancel"
                                        job["ow_dialog_choice"] = "exception"
                                        dialog = None
                                        break
                                apply_all = False
                                try:
                                    if dialog is not None and getattr(dialog, "var_all", None):
                                        apply_all = bool(dialog.var_all.get())
                                except Exception:
                                    apply_all = False
                                if choice == "replace_all" or (choice == "replace" and apply_all):
                                    replace_all = True
                                    _allow_replace(dest_path)
                                    idx += 1
                                    continue
                                if choice == "replace":
                                    _allow_replace(dest_path)
                                    idx += 1
                                    continue
                                if choice == "skip_all" or (choice == "skip" and apply_all):
                                    for j in range(idx, len(conflicts)):
                                        _skip_path(conflicts[j][3])
                                    break
                                if choice == "skip":
                                    _skip_path(dest_path)
                                    idx += 1
                                    continue
                                cancelled = True
                                break

                        def _apply_client_reply(data):
                            nonlocal cancelled
                            if not isinstance(data, dict):
                                return False
                            if data.get("unavailable"):
                                return False
                            job["ow_dialog_shown"] = True
                            job["ow_dialog_choice"] = "client_reply"
                            if data.get("cancelled"):
                                cancelled = True
                                return True
                            for k in (data.get("replace_keys") or []):
                                _allow_replace(k)
                            for k in (data.get("skip_keys") or []):
                                _skip_path(k)
                            return True

                        # Hiện dialog ghi đè trực tiếp trên HOST (máy bị remote) — user đang nhìn
                        # màn hình host qua viewer. KHÔNG đi vòng CONFLICT_QUERY → client: nếu gói
                        # không tới viewer, agent chờ 300s mà không có dialog nào (bug d9bcc39).
                        try:
                            _ask_on_host()
                        except Exception as e_host:
                            log_overwrite_conflict(f"HOST dialog loi: {e_host}")
                            cancelled = True
                        if cancelled:
                            job["conflict_choice"] = "cancel"
                            log_overwrite_conflict(f"USER CANCEL paste_id={paste_id}")
                            trigger_cancel_win32(paste_id)
                        else:
                            req, sz = _files_not_skipped()
                            if not req:
                                job["conflict_choice"] = "cancel"
                                agent_print("[ClipboardAgent] Don't copy — khong tai, khong mo dialog tien trinh.")
                                log_overwrite_conflict(f"SKIP ALL — khong tai paste_id={paste_id}")
                                _agent_schedule_rearm(0.45)
                            else:
                                job["conflict_choice"] = "replace"
                                log_overwrite_conflict(
                                    f"USER REPLACE/continue paste_id={paste_id} "
                                    f"req={len(req)} replace_keys={len(job.get('replace_keys') or [])}"
                                )
                                if not _try_local_repaste(req, force_replace=True):
                                    _begin_download(req, sz)
                    except Exception as e:
                        agent_print(f"[ClipboardAgent] Lỗi dialog ghi đè: {e}")
                        log_overwrite_conflict(f"EXCEPTION conflict_check: {e}")
                        job["conflict_choice"] = "cancel"
                        try:
                            trigger_cancel_win32(paste_id)
                        except Exception:
                            pass
                    _done_conflict()
                elif action == "conflict_reply":
                    try:
                        _apply_conflict_reply_raw(val)
                    except Exception:
                        pass
                    continue
                elif action == "cancel":
                    pid = val
                    targets = []
                    if pid is None:
                        targets = list(active_dialogs.items())
                        active_dialogs.clear()
                        if active_dialog:
                            targets.append((None, active_dialog))
                    else:
                        cand_keys = [pid]
                        try:
                            cand_keys.append(int(pid))
                        except Exception:
                            pass
                        cand_keys.append(str(pid))
                        found_k = None
                        for ck in cand_keys:
                            if ck in active_dialogs:
                                found_k = ck
                                break
                        if found_k is not None:
                            targets = [(found_k, active_dialogs.pop(found_k))]
                        else:
                            for k, d in list(active_dialogs.items()):
                                if getattr(d, "job_id", None) in cand_keys:
                                    targets = [(k, active_dialogs.pop(k))]
                                    break
                    for _, dlg in targets:
                        try:
                            if dlg:
                                dlg.on_cancel = None
                                dlg.destroy()
                        except: pass
                    active_dialog = next(iter(active_dialogs.values()), None)
                elif action == "clear_clip":
                    try:
                        clear_local_clipboard(_agent_hwnd)
                        agent_print("[ClipboardAgent] Đã xóa clipboard theo lệnh host đóng cửa sổ.")
                    except Exception as e:
                        agent_print(f"[ClipboardAgent] Lỗi xóa clipboard: {e}")
            except queue.Empty:
                break
            except Exception as e:
                agent_print(f"[ClipboardAgent] Lỗi xử lý hàng đợi GUI: {e}")
        _in_poll_gui_queue = False
        root.after(50, poll_gui_queue)

    def _shared_pending_watcher_loop():
        import win32event
        h_evt = None
        try:
            h_evt = _open_or_create_user_signalable_event(r"Global\AntigravityP2P_PendingOffer_Event")
        except Exception:
            pass
        last_applied_offer_id = None
        while True:
            try:
                if h_evt:
                    win32event.WaitForSingleObject(h_evt, 300)
                    win32event.ResetEvent(h_evt)
                else:
                    time.sleep(0.3)
                info = read_shared_pending_offer()
                if info and isinstance(info, dict):
                    oid = info.get("offer_id")
                    if oid != last_applied_offer_id:
                        last_applied_offer_id = oid
                        gui_queue.put(("pending", info))
                        agent_print(f"[ClipboardAgent] Shared pending offer phát hiện từ file (offer={oid}).")
            except Exception as e:
                time.sleep(0.5)

    t = threading.Thread(target=pipe_listener_loop, daemon=True)
    t.start()
    t2 = threading.Thread(target=_shared_pending_watcher_loop, daemon=True, name="SharedPendingWatcher")
    t2.start()
    
    poll_gui_queue()
    root.mainloop()
