"""File copy/paste host -> client (viewer delayed CF_HDROP sink / receive)."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import ctypes
from ctypes import wintypes
from typing import Any, Callable

import psutil

from core.i18n import _
from network.socket_utils import send_msg
from utils.logger import log_debug, log_activity, clip_trace, log_overwrite_conflict
from utils.clipboard_api import (
    clipboard_has_file_formats,
    create_hdrop_data,
    fn_SetClipboardData,
    fn_GlobalFree,
    mark_own_clipboard_write,
    setup_clipboard_exclusions,
    get_clipboard_sequence_number,
)

# Still injected by windows_clipboard._bind for edge symbols / CSM coupling
last_clipboard_set_time = 0.0

# Menu / Explorer class tables (shared; used by paste-gesture helpers below)
_EXPLORER_CLIPBOARD_PROCS = (
    "explorer.exe",
    "fileexplorer.exe",
    "searchhost.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
)

# Shell extension / COM / RD khác GetData khi dựng menu — không phải Paste.
_CLIPBOARD_PROBE_PROCS = _EXPLORER_CLIPBOARD_PROCS + (
    "dllhost.exe",
    "rundll32.exe",
    "prevhost.exe",
    "verclsid.exe",
    "runtimebroker.exe",
    "applicationframehost.exe",
    "textinputhost.exe",
    "sihost.exe",
    "taskmgr.exe",
    "perfmon.exe",
    "mmc.exe",
    "procexp.exe",
    "procexp64.exe",
    "processhacker.exe",
    "systemsettings.exe",
    "vmtoolsd.exe",
    "vboxtray.exe",
    "rdpclip.exe",
    "mstsc.exe",
    "vncviewer.exe",
    "teamviewer.exe",
    "anydesk.exe",
)

_EXPLORER_FOLDER_CLASSES = (
    "CabinetWClass",
    "ExploreWClass",
)

_CONTEXT_MENU_CLASSES = (
    "#32768",
    "Microsoft.UI.Content.PopupWindowSiteBridge",
    "XamlExplorerHostIslandWindow",
)

_CONTEXT_MENU_HIT_CLASSES = frozenset((
    "#32768",
    "XamlExplorerHostIslandWindow",
    "Microsoft.UI.Content.PopupWindowSiteBridge",
    "Microsoft.UI.Content.DesktopChildSiteBridge",
    "Windows.UI.Composition.DesktopWindowContentBridge",
))


def _cleanup_stale_transfers():
    import shutil
    try:
        temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
    except: pass
    try:
        headless_dir = r"C:\Users\Public\Downloads\RemoteDesktopTransfers"
        if os.path.exists(headless_dir):
            shutil.rmtree(headless_dir, ignore_errors=True)
    except: pass



WM_CLIPBOARDUPDATE = 0x031D
_WM_RENDERFORMAT = 0x0305
_WM_RENDERALLFORMATS = 0x0306

def _pump_messages_except_clipboard_render():
    """Bơm message khi đang chờ tải file, nhưng không Dispatch WM_RENDERFORMAT.

    PeekMessage(hwnd=0) + Dispatch sẽ gọi lồng WM_RENDERFORMAT. Handler trùng
    return 0 không SetClipboardData → Explorer Win11 dán PE dở, không hiện dialog.
    Để RENDERFORMAT nằm lại queue, xử lý sau khi lần chờ hiện tại kết thúc.
    """
    user32 = ctypes.windll.user32
    msg = wintypes.MSG()
    PM_REMOVE = 1
    pumped = False
    while user32.PeekMessageW(ctypes.byref(msg), 0, 0, _WM_RENDERFORMAT - 1, PM_REMOVE):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
        pumped = True
    while user32.PeekMessageW(
        ctypes.byref(msg), 0, _WM_RENDERALLFORMATS + 1, 0xFFFFFFFF, PM_REMOVE
    ):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
        pumped = True
    return pumped

HEADLESS_TRANSFER_DIR = r"C:\Users\Public\Downloads\RemoteDesktopTransfers"

def _incoming_key(xfer_id, filename):
    return (xfer_id, filename) if xfer_id is not None else filename


def _xfer_staging_dir(base_dir, xfer_id):
    if not base_dir:
        return base_dir
    if xfer_id is None:
        return base_dir
    return os.path.join(base_dir, f".rdxfer_{xfer_id}")


def _hide_win_path(path):
    """Ẩn thư mục tạm trên Windows (dấu chấm không ẩn Explorer)."""
    if sys.platform != "win32" or not path:
        return
    try:
        GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
        SetFileAttributesW = ctypes.windll.kernel32.SetFileAttributesW
        GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        GetFileAttributesW.restype = wintypes.DWORD
        SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        attrs = GetFileAttributesW(str(path))
        if attrs == 0xFFFFFFFF:
            return
        SetFileAttributesW(str(path), int(attrs) | 0x02 | 0x04)  # HIDDEN | SYSTEM
    except Exception:
        pass


def _purge_rdxfer_staging(dest_dir=None, xfer_id=None, extra_paths=None, force_all=False):
    """Xóa .rdxfer_* sau khi file đã ra thư mục đích — không để lại folder tạm."""
    targets = []
    if dest_dir and xfer_id is not None:
        targets.append(_xfer_staging_dir(dest_dir, xfer_id))
    for p in extra_paths or []:
        if not p:
            continue
        try:
            ap = os.path.abspath(p)
            if os.path.basename(ap).startswith(".rdxfer_"):
                targets.append(ap)
                continue
            cur = ap if os.path.isdir(ap) else os.path.dirname(ap)
            for _ in range(10):
                if not cur:
                    break
                if os.path.basename(cur).startswith(".rdxfer_"):
                    targets.append(cur)
                    break
                parent = os.path.dirname(cur)
                if not parent or parent == cur:
                    break
                cur = parent
        except Exception:
            pass
    if dest_dir and os.path.isdir(dest_dir):
        try:
            want = f".rdxfer_{int(xfer_id)}" if xfer_id is not None else None
            for name in os.listdir(dest_dir):
                if not name.startswith(".rdxfer_"):
                    continue
                p = os.path.join(dest_dir, name)
                if force_all or (want and name == want):
                    targets.append(p)
                    continue
                # Không đúng xfer này: chỉ xóa nếu rỗng (sót sau paste).
                try:
                    if not os.listdir(p):
                        targets.append(p)
                except Exception:
                    pass
        except Exception:
            pass
    seen = set()
    for t in targets:
        try:
            key = os.path.normcase(os.path.abspath(t))
        except Exception:
            continue
        if key in seen:
            continue
        seen.add(key)
        if not os.path.basename(t).startswith(".rdxfer_"):
            continue
        _retry_remove_path(t, retries=12)
        if os.path.lexists(t):
            try:
                threading.Timer(0.6, lambda p=t: _retry_remove_path(p, retries=8)).start()
                threading.Timer(2.0, lambda p=t: _retry_remove_path(p, retries=8)).start()
            except Exception:
                pass


def _is_transfer_staging_dir(path):
    if not path:
        return False
    abs_path = os.path.normcase(os.path.abspath(path))
    staging = [
        os.path.normcase(os.path.abspath(HEADLESS_TRANSFER_DIR)),
        os.path.normcase(os.path.abspath(os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers"))),
    ]
    if abs_path in staging:
        return True
    base = os.path.basename(abs_path)
    return base.startswith(".rdxfer_")


def _file_offer_fp(files):
    """Vân tay danh sách file copy — để nhận copy mới dù offer_id bị lặp/reset."""
    parts = []
    for f in files or []:
        if isinstance(f, dict):
            name = os.path.basename(str(f.get("name") or "").replace("\\", "/"))
            path = os.path.normcase(os.path.abspath(str(f.get("path") or ""))) if f.get("path") else ""
            try:
                size = int(f.get("size") or 0)
            except Exception:
                size = 0
            parts.append((name, size, path))
        else:
            p = str(f or "")
            parts.append((os.path.basename(p.replace("\\", "/")), 0, os.path.normcase(os.path.abspath(p)) if p else ""))
    return tuple(parts)


def _rel_copy_name(item):
    if isinstance(item, dict):
        raw = str(item.get("name") or "")
    else:
        raw = str(item or "")
    return raw.replace("\\", "/").strip("/")


def _copy_batch_kind_and_name(files, fallback=""):
    """Paste file → ('file', tên file); paste thư mục → ('folder', tên folder)."""
    files = files or []
    names = []
    for item in files:
        name = _rel_copy_name(item)
        if name:
            names.append(name)
    if not names:
        raw = fallback or _("Tệp tin")
        return "file", os.path.basename(str(raw).replace("\\", "/")) or raw

    folder_tops = []
    seen_folders = set()
    loose = []
    for name in names:
        parts = [p for p in name.split("/") if p]
        if len(parts) >= 2:
            top = parts[0]
            if top not in seen_folders:
                seen_folders.add(top)
                folder_tops.append(top)
        else:
            loose.append(parts[0] if parts else name)

    if folder_tops and not loose:
        label = folder_tops[0]
        extra = len(folder_tops) - 1
        if extra > 0:
            label += _(" và {count} mục khác").format(count=extra)
        return "folder", label

    label = os.path.basename(names[0]) or names[0]
    extra = len(names) - 1
    if extra > 0:
        label += _(" và {count} mục khác").format(count=extra)
    return "file", label


def _localized_batch_name(files, fallback=""):
    _kind, name = _copy_batch_kind_and_name(files, fallback)
    return name


def _same_volume(path_a, path_b):
    try:
        return os.path.splitdrive(os.path.abspath(path_a))[0].lower() == os.path.splitdrive(os.path.abspath(path_b))[0].lower()
    except Exception:
        return False


def _path_byte_size(path):
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        total = 0
        for root, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(root, name))
                except Exception:
                    pass
        return total
    except Exception:
        return 0


def _copy_file_with_progress(src, dst, on_progress=None, should_stop=None):
    import shutil
    wrote = 0
    completed = False
    try:
        with open(src, "rb") as inf, open(dst, "wb") as outf:
            while True:
                if should_stop and should_stop():
                    raise InterruptedError("cancel")
                buf = inf.read(1024 * 1024)
                if not buf:
                    break
                outf.write(buf)
                wrote += len(buf)
                if on_progress:
                    on_progress(len(buf))
        try:
            shutil.copystat(src, dst, follow_symlinks=True)
        except Exception:
            pass
        completed = True
        try:
            os.remove(src)
        except Exception:
            threading.Thread(target=_retry_remove_path, args=(src,), daemon=True).start()
    except Exception:
        if not completed:
            try:
                _retry_remove_path(dst)
            except Exception:
                pass
        raise


_file_io_lock = threading.Lock()


def relocate_transfer_files(src_paths, dest_dir, on_progress=None, should_stop=None):
    """Chuyển file từ thư mục tạm sang thư mục Explorer đang Paste. Trả về (paths, moved_all)."""
    with _file_io_lock:
        return _relocate_transfer_files_unlocked(src_paths, dest_dir, on_progress, should_stop)


def _relocate_transfer_files_unlocked(src_paths, dest_dir, on_progress=None, should_stop=None, replace_keys=None):
    """Chuyển file từ thư mục tạm sang thư mục Explorer đang Paste. Trả về (paths, moved_all).

    replace_keys: set đường dẫn đích (normcase abspath) được phép ghi đè.
    Nếu đích đã có file thật mà không nằm trong replace_keys → KHÔNG xóa/ghi đè.
    """
    import shutil
    if not dest_dir or not os.path.isdir(dest_dir) or _is_transfer_staging_dir(dest_dir):
        return list(src_paths or []), False
    allow_replace = set()
    for k in (replace_keys or []):
        try:
            allow_replace.add(os.path.normcase(os.path.abspath(k)))
        except Exception:
            allow_replace.add(k)
    dest_abs = os.path.normcase(os.path.abspath(dest_dir))
    moved = []
    all_in_dest = True
    for src in src_paths or []:
        if should_stop and should_stop():
            all_in_dest = False
            break
        if not src or not os.path.exists(src):
            continue
        src_abs = os.path.abspath(src)
        if os.path.basename(src_abs).startswith(".rdxfer_") or _is_transfer_staging_dir(src_abs):
            continue
        if _is_probe_stub_name(src_abs):
            continue
        src_dir = os.path.normcase(os.path.dirname(src_abs))
        if src_dir == dest_abs:
            moved.append(src_abs)
            if on_progress:
                on_progress(_path_byte_size(src_abs))
            continue
        dest_path = os.path.join(dest_dir, os.path.basename(src_abs))
        try:
            dest_key = os.path.normcase(os.path.abspath(dest_path))
        except Exception:
            dest_key = dest_path
        try:
            if should_stop and should_stop():
                raise InterruptedError("cancel")
            # Folder paste: đích đã có file chuyển sớm — gộp, không rmtree xóa file đã xong.
            if os.path.isdir(src_abs) and os.path.isdir(dest_path):
                child_ok = True
                try:
                    names = os.listdir(src_abs)
                except Exception:
                    names = []
                for name in names:
                    child = os.path.join(src_abs, name)
                    _nested, ok = _relocate_transfer_files_unlocked(
                        [child], dest_path, on_progress, should_stop, replace_keys=allow_replace
                    )
                    if not ok:
                        child_ok = False
                if child_ok:
                    try:
                        os.rmdir(src_abs)
                    except Exception:
                        pass
                else:
                    all_in_dest = False
                moved.append(os.path.abspath(dest_path))
                continue
            if os.path.exists(dest_path):
                if not _is_transfer_junk_at_dest(dest_path) and dest_key not in allow_replace:
                    log_debug(f"[relocate] Bo ghi de (chua hoi Replace): {dest_path}")
                    # Giữ bản staging — caller (agent) sẽ relocate sau khi có replace_keys.
                    moved.append(src_abs)
                    all_in_dest = False
                    continue
                if os.path.isdir(dest_path) and not os.path.islink(dest_path):
                    shutil.rmtree(dest_path, ignore_errors=True)
                else:
                    os.remove(dest_path)
            if os.path.isdir(src_abs) or _same_volume(src_abs, dest_path):
                shutil.move(src_abs, dest_path)
                if on_progress:
                    on_progress(_path_byte_size(dest_path))
            else:
                _copy_file_with_progress(src_abs, dest_path, on_progress, should_stop=should_stop)
            moved.append(os.path.abspath(dest_path))
        except InterruptedError:
            _retry_remove_path(dest_path)
            all_in_dest = False
            break
        except Exception as e:
            log_debug(f"[relocate_transfer_files] move failed {src_abs} -> {dest_path}: {e}")
            try:
                if should_stop and should_stop():
                    raise InterruptedError("cancel")
                if os.path.exists(dest_path) and not _is_transfer_junk_at_dest(dest_path) and dest_key not in allow_replace:
                    raise RuntimeError("dest exists, no replace")
                if os.path.isdir(src_abs):
                    shutil.copytree(src_abs, dest_path)
                    shutil.rmtree(src_abs, ignore_errors=True)
                    if on_progress:
                        on_progress(_path_byte_size(dest_path))
                else:
                    _copy_file_with_progress(src_abs, dest_path, on_progress, should_stop=should_stop)
                moved.append(os.path.abspath(dest_path))
            except InterruptedError:
                _retry_remove_path(dest_path)
                all_in_dest = False
                break
            except Exception as e2:
                log_debug(f"[relocate_transfer_files] copy fallback failed: {e2}")
                _retry_remove_path(dest_path)
                moved.append(src_abs)
                all_in_dest = False
    if moved and all_in_dest:
        for p in moved:
            if os.path.normcase(os.path.dirname(os.path.abspath(p))) != dest_abs:
                all_in_dest = False
                break
    return moved, bool(moved) and all_in_dest


def _promote_completed_xfer_file(staging_path, dest_dir, rel_name, replace_keys=None):
    """Đưa 1 file đã tải xong từ .rdxfer_* ra thư mục đích (giữ cây thư mục). Rename cùng ổ — không copy 4GB."""
    import shutil
    if not staging_path or not dest_dir or not os.path.isfile(staging_path):
        return staging_path
    if _is_transfer_staging_dir(dest_dir) or not os.path.isdir(dest_dir):
        return staging_path
    rel = str(rel_name or os.path.basename(staging_path)).replace("/", os.sep).replace("\\", os.sep)
    rel = rel.lstrip("\\/")
    if not rel:
        rel = os.path.basename(staging_path)
    dest_path = os.path.join(dest_dir, rel)
    try:
        if os.path.normcase(os.path.abspath(staging_path)) == os.path.normcase(os.path.abspath(dest_path)):
            return dest_path
    except Exception:
        pass
    parent = os.path.dirname(dest_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    allow_replace = set()
    for k in (replace_keys or []):
        try:
            allow_replace.add(os.path.normcase(os.path.abspath(k)))
        except Exception:
            allow_replace.add(k)
    if os.path.exists(dest_path):
        try:
            dest_key = os.path.normcase(os.path.abspath(dest_path))
        except Exception:
            dest_key = dest_path
        top_key = None
        try:
            top = rel.replace("\\", "/").strip("/").split("/")[0]
            top_key = os.path.normcase(os.path.abspath(os.path.join(dest_dir, top)))
        except Exception:
            pass
        may_replace = dest_key in allow_replace or (top_key and top_key in allow_replace)
        # Không im lặng ghi đè file user — chỉ xóa stub/junk; file thật cần replace_keys
        # (user đã chọn Replace trên ClassicCopyDialog).
        if not _is_transfer_junk_at_dest(dest_path) and not may_replace:
            log_debug(f"[promote] Giữ file đích đã có, không ghi đè: {dest_path}")
            try:
                log_overwrite_conflict(
                    f"PROMOTE keep existing (no overwrite): {dest_path} "
                    f"staging={staging_path}"
                )
            except Exception:
                pass
            return staging_path
        try:
            log_overwrite_conflict(
                f"PROMOTE remove junk then write: {dest_path}"
            )
            if os.path.isdir(dest_path) and not os.path.islink(dest_path):
                shutil.rmtree(dest_path, ignore_errors=True)
            else:
                os.remove(dest_path)
        except Exception:
            _retry_remove_path(dest_path)
    try:
        os.replace(staging_path, dest_path)
        try:
            log_overwrite_conflict(f"PROMOTE ok → {dest_path}")
        except Exception:
            pass
    except OSError:
        shutil.move(staging_path, dest_path)
        try:
            log_overwrite_conflict(f"PROMOTE move → {dest_path}")
        except Exception:
            pass
    return os.path.abspath(dest_path)


def _collect_actual_file_sizes(paths):
    """Map relative posix path → size. Folder paste: paths là thư mục top-level, không phải từng file."""
    actual = {}
    for p in paths:
        if not p or not os.path.exists(p):
            return None
        if os.path.isfile(p):
            try:
                actual[os.path.basename(p).replace("\\", "/")] = os.path.getsize(p)
            except Exception:
                return None
            continue
        if not os.path.isdir(p):
            return None
        root_parent = os.path.dirname(os.path.abspath(p))
        for dirpath, _dirs, files in os.walk(p):
            for fn in files:
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, root_parent).replace("\\", "/")
                try:
                    actual[rel] = os.path.getsize(full)
                except Exception:
                    return None
    return actual


def _paths_match_expected_sizes(paths, meta_files, detail=None):
    """False nếu thiếu file hoặc size không khớp metadata — tránh dán PE dở (mất icon).

    So khớp theo đường dẫn tương đối (thư mục/file), không chỉ basename — tránh
    trùng tên trong thư mục con và paste cả folder (paths là dir, không phải file).
    Nếu `detail` là list, append lý do thất bại.
    """
    def _fail(msg):
        if isinstance(detail, list):
            detail.append(msg)
        return False

    if not paths or not meta_files:
        return _fail("thieu paths hoac metadata")
    expected = {}
    for f in meta_files:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name") or "").replace("\\", "/")
        if not name:
            continue
        try:
            expected[name] = int(f.get("size") or 0)
        except Exception:
            return _fail("metadata size khong hop le: %s" % (f.get("name"),))
    if not expected:
        return _fail("metadata khong co file")
    try:
        actual = _collect_actual_file_sizes(paths)
    except Exception as e:
        return _fail("khong doc duoc file da tai: %s" % e)
    if actual is None:
        return _fail("thieu file/thu muc tren disk (paths=%s)" % ([os.path.basename(p) for p in paths[:8]],))
    actual_l = {k.lower(): (k, v) for k, v in actual.items()}
    for name, size in expected.items():
        hit = actual_l.get(name.lower())
        if hit is None:
            base = name.split("/")[-1].lower()
            hits = [v for k, v in actual_l.items() if k.split("/")[-1] == base]
            if len(hits) == 1:
                hit = hits[0]
            else:
                return _fail("thieu %s (expected %s bytes)" % (name, size))
        got = hit[1]
        if got != size:
            return _fail("%s size %s != expected %s" % (name, got, size))
    return True


def _notify_explorer_paths_changed(paths):
    """Báo Explorer vẽ lại ngay sau khi app tự đặt file (tránh ding + phải đổi thư mục mới thấy)."""
    if not paths:
        return
    try:
        shell32 = ctypes.windll.shell32
        SHCNE_CREATE = 0x00000002
        SHCNE_UPDATEITEM = 0x00002000
        SHCNF_PATHW = 0x0005
        SHCNF_FLUSH = 0x1000
        for p in paths:
            if not p:
                continue
            try:
                ap = os.path.abspath(p)
            except Exception:
                continue
            try:
                shell32.SHChangeNotify(SHCNE_CREATE, SHCNF_PATHW | SHCNF_FLUSH, ap, None)
                shell32.SHChangeNotify(SHCNE_UPDATEITEM, SHCNF_PATHW | SHCNF_FLUSH, ap, None)
            except Exception:
                pass
            parent = os.path.dirname(ap)
            if parent:
                try:
                    shell32.SHChangeNotify(SHCNE_UPDATEITEM, SHCNF_PATHW | SHCNF_FLUSH, parent, None)
                except Exception:
                    pass
    except Exception as e:
        log_debug(f"[_notify_explorer_paths_changed] {e}")


def query_explorer_folder_path(allow_open_clipboard=False):
    """Thư mục Explorer/Desktop đang focus — gọi từ background thread (không gọi trong WM_RENDERFORMAT)."""
    import win32gui
    import win32process
    try:
        pythoncom = __import__("pythoncom")
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass
        import win32com.client
        shell = win32com.client.Dispatch("Shell.Application")
    except Exception:
        return None

    def related_hwnds(h):
        if not h:
            return []
        res = [h]
        try:
            root = ctypes.windll.user32.GetAncestor(h, 2)
            if root and root not in res:
                res.append(root)
            owner = ctypes.windll.user32.GetWindow(h, 4)
            if owner and owner not in res:
                res.append(owner)
            parent = ctypes.windll.user32.GetParent(h)
            if parent and parent not in res:
                res.append(parent)
        except Exception:
            pass
        return res

    hwnds_to_check = []
    try:
        hwnd_clip = ctypes.windll.user32.GetOpenClipboardWindow()
        if hwnd_clip and not allow_open_clipboard:
            # Explorer đang Copy/Paste — không enumerate Shell (chuột xoay / mất clipboard).
            return None
    except Exception:
        pass
    try:
        hwnd_fg = win32gui.GetForegroundWindow()
        if hwnd_fg:
            hwnds_to_check.extend(related_hwnds(hwnd_fg))
    except Exception:
        pass
    try:
        pt = wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
            hwnd_mouse = ctypes.windll.user32.WindowFromPoint(pt)
            if hwnd_mouse:
                hwnds_to_check.extend(related_hwnds(hwnd_mouse))
    except Exception:
        pass

    seen = set()
    ordered = []
    for h in hwnds_to_check:
        if h and h not in seen:
            seen.add(h)
            ordered.append(h)

    for hwnd in ordered:
        try:
            class_name = win32gui.GetClassName(hwnd)
            if hwnd == win32gui.GetDesktopWindow() or class_name in ("Progman", "WorkerW"):
                return os.path.join(os.path.expanduser("~"), "Desktop")
        except Exception:
            pass

    explorer_windows = []
    try:
        for window in shell.Windows():
            try:
                w_hwnd = int(window.HWND)
                doc = window.Document
                if not doc:
                    continue
                path = ""
                try:
                    path = doc.Folder.Self.Path
                except Exception:
                    pass
                if path:
                    explorer_windows.append((w_hwnd, path))
            except Exception:
                continue
    except Exception:
        pass

    for hwnd in ordered:
        for w_hwnd, path in explorer_windows:
            if hwnd == w_hwnd:
                return path

    for hwnd in ordered:
        try:
            _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
            if psutil.Process(pid).name().lower() != "explorer.exe":
                continue
            class_name = win32gui.GetClassName(hwnd)
            if class_name in ("CabinetWClass", "ExploreWClass"):
                for w_hwnd, path in explorer_windows:
                    if w_hwnd == hwnd:
                        return path
        except Exception:
            pass

    if explorer_windows:
        if len(explorer_windows) == 1:
            return explorer_windows[0][1]
        top_explorer_path = []

        def enum_cb(hwnd, _lparam):
            for w_hwnd, path in explorer_windows:
                if hwnd == w_hwnd:
                    top_explorer_path.append(path)
                    return False
            return True

        try:
            win32gui.EnumWindows(enum_cb, 0)
        except Exception:
            pass
        if top_explorer_path:
            return top_explorer_path[0]
    return None


# Tên Named Pipe để giao tiếp giữa Service (SYSTEM) và Agent (User)

def _hwnd_class_name(hwnd):
    if not hwnd:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(256)
        n = ctypes.windll.user32.GetClassNameW(ctypes.c_void_p(hwnd), buf, 256)
        return buf.value if n else ""
    except Exception:
        return ""


def _hwnd_is_context_menu(hwnd):
    """Cửa sổ (hoặc cha) là menu chuột phải — không gồm khung Explorer chính."""
    user32 = ctypes.windll.user32
    seen = set()
    cur = hwnd
    for _ in range(12):
        if not cur:
            break
        try:
            key = int(cur)
        except Exception:
            break
        if key in seen:
            break
        seen.add(key)
        cls = _hwnd_class_name(cur)
        if cls in _CONTEXT_MENU_HIT_CLASSES:
            # CabinetWClass / ExploreWClass không bao giờ là menu.
            if cls in ("CabinetWClass", "ExploreWClass", "WorkerW", "Progman"):
                return False
            return True
        if cls in (
            "Microsoft.UI.Content.DesktopChildSiteBridge",
            "Windows.UI.Composition.DesktopWindowContentBridge",
        ):
            try:
                user32.GetWindowLongW.restype = ctypes.c_long
                style = int(user32.GetWindowLongW(ctypes.c_void_p(cur), -16) or 0)
                ex = int(user32.GetWindowLongW(ctypes.c_void_p(cur), -20) or 0)
            except Exception:
                style, ex = 0, 0
            ws_popup = bool(style & 0x80000000)
            ws_caption = bool(style & 0x00C00000)
            ws_ex_tool = bool(ex & 0x00000080)
            ws_child = bool(style & 0x40000000)
            # Win11 XAML: item menu thường là child bridge trong popup host.
            if ws_popup and (ws_ex_tool or not ws_caption):
                return True
            if ws_child and not ws_caption:
                # Leo thêm — nếu tổ tiên là XamlExplorerHostIslandWindow thì là menu.
                pass
        try:
            user32.GetAncestor.restype = wintypes.HWND
            nxt = user32.GetAncestor(ctypes.c_void_p(cur), 1)
            if not nxt or nxt == cur:
                user32.GetWindow.restype = wintypes.HWND
                nxt = user32.GetWindow(ctypes.c_void_p(cur), 4)
            cur = nxt
        except Exception:
            break
    return False


def _cursor_over_context_menu():
    """LMB đang nhắm vào item trên context menu (Paste), không phải click ra ngoài để đóng menu."""
    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    try:
        if not user32.GetCursorPos(ctypes.byref(pt)):
            return False
        user32.WindowFromPoint.restype = wintypes.HWND
        hwnd = user32.WindowFromPoint(pt)
        return bool(hwnd) and _hwnd_is_context_menu(hwnd)
    except Exception:
        return False


def _cursor_point():
    pt = wintypes.POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
        return None
    return pt


def _context_menu_root_hwnd(hwnd):
    """Cửa sổ menu ngoài cùng chứa hwnd (classic #32768 hoặc flyout XAML)."""
    if not hwnd or not _hwnd_is_context_menu(hwnd):
        return None
    user32 = ctypes.windll.user32
    best = hwnd
    cur = hwnd
    for _ in range(8):
        try:
            user32.GetAncestor.restype = wintypes.HWND
            nxt = user32.GetAncestor(ctypes.c_void_p(cur), 1)
            if not nxt or nxt == cur:
                user32.GetWindow.restype = wintypes.HWND
                nxt = user32.GetWindow(ctypes.c_void_p(cur), 4)
            if not nxt or nxt == cur:
                break
            if _hwnd_is_context_menu(nxt):
                best = nxt
            cur = nxt
        except Exception:
            break
    return best


def _win32_menu_text_at_point(pt):
    """Tên mục menu cổ điển (#32768) — gọi được từ mouse hook, không dùng UIA."""
    user32 = ctypes.windll.user32
    try:
        user32.WindowFromPoint.restype = wintypes.HWND
        hwnd = user32.WindowFromPoint(pt)
        if not hwnd:
            return ""
        cur = hwnd
        hwnd_menu = None
        for _ in range(8):
            if _hwnd_class_name(cur) == "#32768":
                hwnd_menu = cur
                break
            user32.GetAncestor.restype = wintypes.HWND
            nxt = user32.GetAncestor(ctypes.c_void_p(cur), 1)
            if not nxt or nxt == cur:
                break
            cur = nxt
        if not hwnd_menu:
            return ""
        MN_GETHMENU = 0x01E1
        MF_BYPOSITION = 0x0400
        hmenu = user32.SendMessageW(ctypes.c_void_p(hwnd_menu), MN_GETHMENU, 0, 0)
        if not hmenu:
            return ""

        user32.MenuItemFromPoint.argtypes = [wintypes.HWND, wintypes.HMENU, wintypes.POINT]
        user32.MenuItemFromPoint.restype = ctypes.c_int
        idx = user32.MenuItemFromPoint(hwnd_menu, hmenu, pt)
        if idx < 0:
            return ""
        buf = ctypes.create_unicode_buffer(512)
        user32.GetMenuStringW(ctypes.c_void_p(hmenu), idx, buf, 512, MF_BYPOSITION)
        return (buf.value or "").strip()
    except Exception:
        return ""


def _xaml_click_is_show_more_strip(pt, menu_hwnd):
    """Win11 compact menu: Show more nằm dải đáy; Paste là icon/mục phía trên."""
    if not pt or not menu_hwnd:
        return False
    if _hwnd_class_name(menu_hwnd) == "#32768":
        return False
    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long), ("top", ctypes.c_long),
            ("right", ctypes.c_long), ("bottom", ctypes.c_long),
        ]

    rc = RECT()
    if not user32.GetWindowRect(ctypes.c_void_p(menu_hwnd), ctypes.byref(rc)):
        return False
    if not (rc.left <= pt.x <= rc.right and rc.top <= pt.y <= rc.bottom):
        return False
    dpi = 96
    try:
        dpi = int(user32.GetDpiForWindow(ctypes.c_void_p(menu_hwnd)) or 96)
    except Exception:
        dpi = 96
    band = int(40 * dpi / 96.0)
    height = int(rc.bottom - rc.top)
    if height < 140:
        return False
    return pt.y >= rc.bottom - band


def _xaml_click_is_menu_body(pt, menu_hwnd):
    """Win11 XAML menu: Dải giữa (View, Sort, Refresh, New...) KHÔNG bao giờ là Paste.
    Paste là nút icon ở dải đỉnh (~48px) hoặc dải đáy (khi menu lật).
    Dải giữa luôn là danh sách text menu items thông thường."""
    if not pt or not menu_hwnd:
        return False
    if _hwnd_class_name(menu_hwnd) == "#32768":
        return False
    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long), ("top", ctypes.c_long),
            ("right", ctypes.c_long), ("bottom", ctypes.c_long),
        ]

    rc = RECT()
    if not user32.GetWindowRect(ctypes.c_void_p(menu_hwnd), ctypes.byref(rc)):
        return False
    if not (rc.left <= pt.x <= rc.right and rc.top <= pt.y <= rc.bottom):
        return False
    height = int(rc.bottom - rc.top)
    if height < 140:
        return False
    dpi = 96
    try:
        dpi = int(user32.GetDpiForWindow(ctypes.c_void_p(menu_hwnd)) or 96)
    except Exception:
        dpi = 96
    top_band = int(48 * dpi / 96.0)
    bottom_band = int(44 * dpi / 96.0)
    return (rc.top + top_band) < pt.y < (rc.bottom - bottom_band)


_PASTE_MENU_TOKENS = (
    "paste", "dán", "einfügen", "coller", "incolla", "pegar",
    "вставить", "붙여넣기", "貼り付け", "粘贴", "貼上",
)
_NOT_PASTE_MENU_TOKENS = (
    "show more", "more options", "hiển thị thêm", "thêm tùy chọn",
    "weitere optionen", "plus d'options", "más opciones", "altre opzioni",
    "その他のオプション", "더 많은 옵션", "дополнительн",
    "显示更多", "顯示更多", "showmoreoptions", "moreoptions",
    "properties", "thuộc tính", "eigenschaften", "propriétés", "proprietà",
    "delete", "xóa", "cut", "cắt", "copy", "sao chép",
    "rename", "đổi tên", "share", "chia sẻ", "open", "mở",
    "pin", "ghim", "format", "định dạng", "eject", "đẩy ra",
    "new", "mới", "refresh", "làm mới",
    "folder", "new folder", "thư mục", "thư mục mới", "thu muc", "thu muc moi",
    "ordner", "neuer ordner", "dossier", "nouveau dossier", "carpeta", "nueva carpeta",
    "cartella", "nuova cartella", "pasta", "nova pasta", "папка", "новая папка",
    "폴더", "새 폴더", "フォルダー", "新しいフォルダー", "新建文件夹", "文件夹", "新增資料夾", "資料夾",
    "shortcut", "lối tắt", "loi tat", "verknüpfung", "raccourci", "acceso directo", "collegamento", "atalho",
    "ярлык", "바로 가기", "ショートカット", "快捷方式", "捷徑",
    "document", "tài liệu", "văn bản", "rich text", "bitmap", "text document", "archive", "zip", "rar", "7-zip",
    "view", "xem", "sort", "sắp xếp", "group", "nhóm", "next desktop background", "hình nền tiếp theo",
    "terminal", "powershell", "command prompt", "cmd",
    "display settings", "cài đặt hiển thị", "personalize", "cá nhân hóa", "undo", "hoàn tác", "redo",
    "task manager", "trình quản lý tác vụ", "task-manager", "taskmgr",
    "taskbar", "thanh tác vụ", "taskbar settings", "cài đặt thanh tác vụ",
    "cascade windows", "show windows stacked", "show windows side by side",
    "show the desktop", "cortana", "news and interests", "search", "tìm kiếm",
    "toolbars", "thanh công cụ", "settings", "cài đặt",
)


def _classify_context_menu_item(name):
    """'paste' | 'not_paste' | 'unknown'."""
    raw = (name or "").replace("&", "").replace("…", "").replace("...", "")
    n = " ".join(raw.strip().lower().split())
    if not n:
        return "unknown"
    compact = n.replace(" ", "").replace("+", "")
    if "ctrlv" in compact:
        return "paste"
    first = n.split("\t", 1)[0].strip()
    for tok in _PASTE_MENU_TOKENS:
        if first == tok or first.startswith(tok + " ") or tok in first.split():
            return "paste"
    for tok in _NOT_PASTE_MENU_TOKENS:
        if tok in n or tok.replace(" ", "") in compact:
            return "not_paste"
    return "unknown"


def _capture_menu_item_at_cursor():
    """Phân loại mục lúc click. Không dùng UIA (mouse hook hay fail)."""
    user32 = ctypes.windll.user32
    pt = _cursor_point()
    if not pt:
        return "unknown", ""
    if _is_taskbar_or_taskmgr_at_point(pt):
        return "not_paste", "[taskbar-or-taskmgr]"
    user32.WindowFromPoint.restype = wintypes.HWND
    hwnd = user32.WindowFromPoint(pt)
    root = _context_menu_root_hwnd(hwnd)
    text = _win32_menu_text_at_point(pt)
    kind = _classify_context_menu_item(text)
    if kind == "unknown" and _xaml_click_is_show_more_strip(pt, root):
        kind = "not_paste"
        text = text or "[show-more-strip]"
    elif kind == "unknown" and _xaml_click_is_menu_body(pt, root):
        kind = "not_paste"
        text = text or "[xaml-menu-body]"
    elif kind == "unknown":
        # Không mặc định "paste" — Win11 XAML thường không đọc được tên mục;
        # coi unknown = paste khiến copy host tự dán vào Explorer client.
        kind = "unknown"
    try:
        log_debug(f"[menu-item] name={text!r} kind={kind}")
    except Exception:
        pass
    return kind, text


def _is_windows_11():
    try:
        v = sys.getwindowsversion()
        return v.major >= 10 and int(getattr(v, "build", 0) or 0) >= 22000
    except Exception:
        return False


def _shell_menu_profile():
    """Win10 = classic #32768 (đọc được chữ Paste); Win11 = XAML (thường kind=unknown)."""
    return "win11_xaml" if _is_windows_11() else "win10_classic"


def _menu_item_counts_as_paste(kind):
    """True nếu click mục menu được coi là Paste — khác nhau Win10 / Win11."""
    k = (kind or "").strip().lower()
    if k == "not_paste":
        return False
    if k == "paste":
        return True
    # Win11 XAML: GetMenuString thường trống → unknown; vẫn là Paste nếu không phải Show more.
    if _is_windows_11() and k in ("unknown", ""):
        return True
    # Win10 classic: chỉ tin khi đọc đúng chữ Paste/Dán/...
    return False


def _win10_rmb_paste_click(
    last_lbutton,
    last_rbutton,
    menu_item_kind="",
    last_dblclick=0.0,
    lmb_on_menu=False,
    lmb_down=False,
    menu_visible=False,
):
    """Win10 classic #32768: coi là RMP khi LMB sau RMB.

    GetMenuString / MenuItemFromPoint hay trống (DPI, SendInput remote, menu đóng
    trước poll) nên không đòi kind=='paste'. Menu-paint lúc RMB bị loại vì
    last_lbutton phải sau last_rbutton.
    """
    if _is_windows_11():
        return False
    if (menu_item_kind or "").strip().lower() == "not_paste":
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


def _pid_image_name(pid):
    try:
        return (psutil.Process(int(pid)).name() or "").lower()
    except Exception:
        return ""


def _hwnd_process_name(hwnd):
    if not hwnd:
        return ""
    try:
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return _pid_image_name(pid.value)
    except Exception:
        return ""


def _is_taskbar_or_taskmgr_hwnd(hwnd):
    """Kiểm tra xem hwnd có thuộc Taskbar, System Tray, Start Menu, hoặc Task Manager."""
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    cur = hwnd
    for _ in range(8):
        if not cur:
            break
        buf = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(ctypes.c_void_p(cur), buf, 128)
        cls = buf.value
        if cls in (
            "Shell_TrayWnd",
            "Shell_SecondaryTrayWnd",
            "TrayNotifyWnd",
            "NotifyIconOverflowWindow",
            "TaskManagerWindow",
            "TrayClockWClass",
            "Taskbar.TaskListButtonHWND",
            "ReBarWindow32",
            "MSTaskSwWClass",
        ):
            return True
        pname = _hwnd_process_name(cur)
        if pname in ("taskmgr.exe", "perfmon.exe", "procexp.exe", "procexp64.exe", "processhacker.exe"):
            return True
        parent = user32.GetAncestor(ctypes.c_void_p(cur), 2)  # GA_ROOT
        if parent == cur:
            parent = user32.GetParent(ctypes.c_void_p(cur))
        if not parent or parent == cur:
            break
        cur = parent
    return False


def _is_taskbar_or_taskmgr_at_point(pt):
    """Kiểm tra xem tọa độ pt có nằm trên Taskbar hoặc Task Manager."""
    user32 = ctypes.windll.user32
    if isinstance(pt, (tuple, list)):
        p = wintypes.POINT(int(pt[0]), int(pt[1]))
    else:
        p = pt
    user32.WindowFromPoint.restype = wintypes.HWND
    hwnd = user32.WindowFromPoint(p)
    if not hwnd:
        return False
    return _is_taskbar_or_taskmgr_hwnd(hwnd)


def _cursor_over_current_process():
    """Chuột đang trên cửa sổ process này (dialog tiến trình) — không phải click Paste Explorer."""
    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT()
    try:
        if not user32.GetCursorPos(ctypes.byref(pt)):
            return False
        user32.WindowFromPoint.restype = wintypes.HWND
        hwnd = user32.WindowFromPoint(pt)
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return int(pid.value) == int(os.getpid())
    except Exception:
        return False


def _is_explorer_clipboard_client():
    """Win11 Explorer (và host XAML) đang mở clipboard / đang foreground."""
    user32 = ctypes.windll.user32
    try:
        user32.GetOpenClipboardWindow.restype = wintypes.HWND
        opener = user32.GetOpenClipboardWindow()
        name = _hwnd_process_name(opener)
        if name in _EXPLORER_CLIPBOARD_PROCS:
            return True
    except Exception:
        pass
    try:
        user32.GetForegroundWindow.restype = wintypes.HWND
        name = _hwnd_process_name(user32.GetForegroundWindow())
        if name in _EXPLORER_CLIPBOARD_PROCS:
            return True
    except Exception:
        pass
    return False


def _cursor_in_explorer_command_bar():
    """Nút Paste trên thanh lệnh Win11 — chỉ cửa sổ thư mục, không gồm taskbar (cũng là explorer.exe)."""
    user32 = ctypes.windll.user32

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    pt = POINT()
    if not user32.GetCursorPos(ctypes.byref(pt)):
        return False
    hwnd = user32.WindowFromPoint(pt)
    if not hwnd:
        return False
    try:
        root = user32.GetAncestor(hwnd, 2) or hwnd  # GA_ROOT
    except Exception:
        root = hwnd
    if _hwnd_class_name(root) not in _EXPLORER_FOLDER_CLASSES:
        return False
    if _hwnd_process_name(root) not in _EXPLORER_CLIPBOARD_PROCS:
        return False
    rc = RECT()
    if not user32.GetWindowRect(root, ctypes.byref(rc)):
        return False
    dpi = 96
    try:
        dpi = int(user32.GetDpiForWindow(root) or 96)
    except Exception:
        dpi = 96
    bar_h = int(148 * dpi / 96.0)
    return (rc.left <= pt.x <= rc.right) and (rc.top <= pt.y <= rc.top + bar_h)


_DUMMY_HDROP_PATH = r"C:\RemoteDesktop_Paste_Trigger.tmp"
_PROBE_STUB_NAME = ".__rd_clipboard_probe__"
_PROBE_STUB_DIR = os.path.join(
    os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopPasteProbe"
)

def _clear_win_attrs(path):
    """Bỏ HIDDEN|SYSTEM|READONLY trước khi xóa (staging .rdxfer_* từng bị gắn ẩn)."""
    if sys.platform != "win32" or not path:
        return
    try:
        SetFileAttributesW = ctypes.windll.kernel32.SetFileAttributesW
        SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
        SetFileAttributesW(str(path), 0x80)  # FILE_ATTRIBUTE_NORMAL
    except Exception:
        pass


def _retry_remove_path(path, retries=8):
    """Xóa file/thư mục dở; retry vì Explorer/AV có thể đang khóa file 0 byte."""
    if not path:
        return False
    import shutil
    last_err = None
    for i in range(max(1, int(retries))):
        try:
            if not os.path.lexists(path):
                return True
            if os.path.isdir(path) and not os.path.islink(path):
                # Gỡ HIDDEN|SYSTEM trên cả cây — nếu không rmtree dễ fail / để lại .rdxfer_*.
                try:
                    for root, dirs, files in os.walk(path, topdown=False):
                        for name in files:
                            fp = os.path.join(root, name)
                            _clear_win_attrs(fp)
                            try:
                                os.chmod(fp, 0o666)
                            except Exception:
                                pass
                        for name in dirs:
                            _clear_win_attrs(os.path.join(root, name))
                    _clear_win_attrs(path)
                except Exception:
                    _clear_win_attrs(path)
                shutil.rmtree(path, ignore_errors=False)
            else:
                _clear_win_attrs(path)
                try:
                    os.chmod(path, 0o666)
                except Exception:
                    pass
                os.remove(path)
            return True
        except FileNotFoundError:
            return True
        except Exception as e:
            last_err = e
            time.sleep(0.05 * (i + 1))
    # Lần cuối: ignore_errors để không để lại thư mục tạm nhìn thấy.
    try:
        _clear_win_attrs(path)
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
            if not os.path.lexists(path):
                return True
        elif os.path.lexists(path):
            os.remove(path)
            return True
    except Exception as e:
        last_err = e
    if last_err:
        log_debug(f"[_retry_remove_path] Khong xoa duoc {path}: {last_err}")
    return False


def cleanup_probe_stubs():
    """Xóa file 0 byte dùng để bật nút Paste (Win11)."""
    try:
        if not os.path.isdir(_PROBE_STUB_DIR):
            return
        for name in os.listdir(_PROBE_STUB_DIR):
            _retry_remove_path(os.path.join(_PROBE_STUB_DIR, name), retries=4)
    except Exception:
        pass


def _is_paste_placeholder(path, expected=None):
    """File 0 byte / stub probe — không hỏi ghi đè, xóa rồi paste đè."""
    if not path or not os.path.lexists(path):
        return False
    try:
        p = os.path.normcase(os.path.abspath(path))
        probe = os.path.normcase(os.path.abspath(_PROBE_STUB_DIR))
        if p == probe or p.startswith(probe + os.sep):
            return True
        parent = os.path.dirname(path)
        if parent and _is_transfer_staging_dir(parent):
            return True
    except Exception:
        pass
    if os.path.isdir(path) and not os.path.islink(path):
        return False
    if not os.path.isfile(path):
        return False
    try:
        return os.path.getsize(path) == 0
    except Exception:
        return True


def _file_expected_size(meta):
    if not isinstance(meta, dict):
        return None
    try:
        if meta.get("size") is None:
            return None
        return int(meta.get("size"))
    except Exception:
        return None


def _is_incomplete_transfer_file(path, expected=None):
    """File dở trong thư mục tạm .rdxfer_* — không dùng cho file sẵn có của user."""
    if not path or not os.path.isfile(path):
        return False
    try:
        sz = os.path.getsize(path)
    except Exception:
        return True
    if expected is None:
        return sz == 0
    try:
        expected = int(expected)
    except Exception:
        return sz == 0
    if expected <= 0:
        return False
    return sz < expected


def _path_in_xfer_staging(path):
    try:
        parent = os.path.dirname(os.path.abspath(path))
        base = os.path.basename(parent)
        return base.startswith(".rdxfer_") or _is_transfer_staging_dir(parent)
    except Exception:
        return False


def _is_transfer_junk_at_dest(path, expected=None):
    """Chỉ xóa stub 0 byte / probe / file trong .rdxfer_*. File user trên đích phải hỏi ghi đè."""
    if not path or not os.path.lexists(path):
        return False
    if _path_in_xfer_staging(path):
        return _is_incomplete_transfer_file(path, expected) or _is_paste_placeholder(path, expected)
    return _is_paste_placeholder(path, expected)


def cleanup_incomplete_named_files(dests, files_meta, extra_paths=None, staging_xids=None, wipe_all_staging=True):
    """Xóa file tạm/dở (kể cả 0 byte) theo tên đang copy và đường dẫn phụ.

    extra_paths chỉ xóa nếu là staging / stub / 0-byte — không bao giờ xóa file
    đã hoàn tất tại thư mục đích (bug: FILES trễ / cleanup sau Paste xóa luôn file vừa dán).
    """
    cleanup_probe_stubs()
    for dest in list(dests or []):
        _scrub_probe_from_dest(dest)
    for p in list(extra_paths or []):
        if not p:
            continue
        try:
            if _path_in_xfer_staging(p) or _is_probe_stub_name(p):
                _retry_remove_path(p)
            elif _is_transfer_junk_at_dest(p):
                _retry_remove_path(p)
            # else: file hoàn chỉnh ngoài staging — giữ nguyên
        except Exception:
            pass
    abort_xids = None
    if staging_xids is not None:
        abort_xids = set()
        for x in staging_xids:
            try:
                abort_xids.add(int(x))
            except Exception:
                pass
    seen = set()
    dest_list = []
    for dest in list(dests or []):
        if not dest:
            continue
        try:
            key = os.path.normcase(os.path.abspath(dest))
        except Exception:
            continue
        if key in seen:
            continue
        seen.add(key)
        dest_list.append(dest)
        if os.path.isdir(dest):
            try:
                for name in os.listdir(dest):
                    if not name.startswith(".rdxfer_"):
                        continue
                    if not wipe_all_staging:
                        try:
                            xid = int(name[8:])
                        except Exception:
                            continue
                        if abort_xids is None or xid not in abort_xids:
                            continue
                    elif abort_xids is not None:
                        try:
                            xid = int(name[8:])
                        except Exception:
                            continue
                        if xid not in abort_xids:
                            continue
                    _retry_remove_path(os.path.join(dest, name))
            except Exception:
                pass
    for f in list(files_meta or []):
        if isinstance(f, dict):
            name = str(f.get("name") or "")
            expected = _file_expected_size(f)
        else:
            name = str(f or "")
            expected = None
        if not name:
            continue
        rel = name.replace("/", os.sep).replace("\\", os.sep).lstrip("\\/")
        for dest in dest_list:
            if not dest or not os.path.isdir(dest):
                continue
            p = os.path.join(dest, rel)
            if _is_transfer_junk_at_dest(p, expected):
                if _retry_remove_path(p):
                    print(f"[FileTransfer] Da xoa file tam/do dang: {p}")


def _probe_stub_paths(pending_files=None):
    """Một file 0-byte tên giả để Win11 bật Paste. Không dùng tên file đang copy:
    Explorer coi HDROP này là danh sách dán và copy stub vào thư mục đích."""
    del pending_files
    try:
        os.makedirs(_PROBE_STUB_DIR, exist_ok=True)
    except Exception:
        return [_DUMMY_HDROP_PATH]
    path = os.path.join(_PROBE_STUB_DIR, _PROBE_STUB_NAME)
    try:
        if not os.path.exists(path):
            with open(path, "ab"):
                pass
        _hide_win_path(path)
        return [path]
    except Exception:
        return [_DUMMY_HDROP_PATH]


def _is_probe_stub_name(name):
    n = os.path.basename(str(name or "")).lower()
    return n == _PROBE_STUB_NAME.lower() or n.startswith(".__rd_clipboard_probe")


def _scrub_probe_from_dest(dest_dir):
    """Explorer hay copy stub HDROP vào thư mục Paste — xóa ngay."""
    if not dest_dir or not os.path.isdir(dest_dir):
        return
    try:
        names = os.listdir(dest_dir)
    except Exception:
        names = [_PROBE_STUB_NAME]
    for name in names:
        if _is_probe_stub_name(name):
            _retry_remove_path(os.path.join(dest_dir, name), retries=8)


def _schedule_scrub_probe(dest_dir):
    if not dest_dir:
        return
    _scrub_probe_from_dest(dest_dir)
    for delay in (0.15, 0.4, 0.9, 1.8, 3.5):
        try:
            threading.Timer(delay, lambda d=dest_dir: _scrub_probe_from_dest(d)).start()
        except Exception:
            pass


def _offer_empty_hdrop():
    """HDROP rỗng: không tạo file 0 byte trong thư mục dán."""
    dummy_h = create_hdrop_data([])
    if dummy_h:
        fn_SetClipboardData(15, dummy_h)
        return True
    return False


def _offer_probe_hdrop(pending_files=None):
    """Không gắn file thật vào HDROP — Explorer sẽ dán stub vào thư mục đích (lần Paste 2, 3, …)."""
    del pending_files
    return _offer_empty_hdrop()


def _hwnd_looks_like_popup_menu(hwnd):
    """Top-level popup menu (classic hoặc flyout Win11), không phải cửa sổ Explorer."""
    user32 = ctypes.windll.user32
    try:
        if not hwnd or not user32.IsWindowVisible(hwnd):
            return False
    except Exception:
        return False
    cls = _hwnd_class_name(hwnd)
    if cls in _CONTEXT_MENU_CLASSES:
        return True
    if cls not in (
        "XamlExplorerHostIslandWindow",
        "Microsoft.UI.Content.DesktopChildSiteBridge",
        "Windows.UI.Composition.DesktopWindowContentBridge",
    ):
        return False
    try:
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long),
            ]
        rc = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rc)):
            return False
        w, h = rc.right - rc.left, rc.bottom - rc.top
        style = int(user32.GetWindowLongW(ctypes.c_void_p(hwnd), -16) or 0)
        ws_popup = bool(style & 0x80000000)
        return ws_popup and 40 < h < 900 and 80 < w < 720
    except Exception:
        return False


_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _context_menu_open():
    """Menu chuột phải đang hiện: #32768 / popup Win11 (EnumWindows, không FindWindow ẩn)."""
    user32 = ctypes.windll.user32
    found = ctypes.c_int(0)

    def _enum(hwnd, _lparam):
        if _hwnd_looks_like_popup_menu(hwnd):
            found.value = 1
            return 0
        return 1

    try:
        cb = _WNDENUMPROC(_enum)
        user32.EnumWindows(cb, 0)
        if found.value:
            return True
    except Exception:
        pass
    try:
        from ctypes import wintypes

        class RECT_SIMPLE(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long),
            ]

        class GUITHREADINFO_SIMPLE(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong), ("flags", ctypes.c_ulong),
                ("hwndActive", ctypes.c_void_p), ("hwndFocus", ctypes.c_void_p),
                ("hwndCapture", ctypes.c_void_p), ("hwndMenuOwner", ctypes.c_void_p),
                ("hwndMoveSize", ctypes.c_void_p), ("hwndCaret", ctypes.c_void_p),
                ("rcCaret", RECT_SIMPLE),
            ]

        user32.GetOpenClipboardWindow.restype = ctypes.c_void_p
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        for hwnd_check in (user32.GetOpenClipboardWindow(), user32.GetForegroundWindow()):
            if not hwnd_check:
                continue
            pid = wintypes.DWORD()
            tid = user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd_check), ctypes.byref(pid))
            gui_info = GUITHREADINFO_SIMPLE()
            gui_info.cbSize = ctypes.sizeof(GUITHREADINFO_SIMPLE)
            if user32.GetGUIThreadInfo(tid, ctypes.byref(gui_info)):
                if gui_info.flags & (0x04 | 0x10 | 0x08) or gui_info.hwndMenuOwner:
                    return True
    except Exception:
        pass
    return False


def _double_click_ms():
    try:
        return int(ctypes.windll.user32.GetDoubleClickTime() or 500)
    except Exception:
        return 500


def _cursor_xy():
    pt = wintypes.POINT()
    try:
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return int(pt.x), int(pt.y)
    except Exception:
        return 0, 0


def check_is_menu_query(last_lbutton, last_rbutton, meta_arrival_time, last_ctrl_v=0.0, expect_repaste=False, lmb_on_menu=False, menu_item_kind="", last_dblclick=0.0):
    """
    WM_RENDERFORMAT: 'MENU' / 'BACKGROUND' = chỉ trả dummy HDROP.
    False = Paste thật (Ctrl+V / click Paste trên menu / nút Paste thanh lệnh).
    """
    user32 = ctypes.windll.user32
    from ctypes import wintypes

    try:
        user32.GetOpenClipboardWindow.restype = wintypes.HWND
        hwnd_clip = user32.GetOpenClipboardWindow()
        if hwnd_clip:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd_clip, ctypes.byref(pid))
            if pid.value == os.getpid():
                log_debug("[check_is_menu_query] BACKGROUND: process nay dang mo clipboard")
                return "BACKGROUND"
            proc_name = _pid_image_name(pid.value)
            if proc_name in _CLIPBOARD_PROBE_PROCS and proc_name not in _EXPLORER_CLIPBOARD_PROCS:
                log_debug(f"[check_is_menu_query] PROBE: probe {proc_name}")
                return "PROBE"
    except Exception:
        pass

    try:
        user32.GetForegroundWindow.restype = wintypes.HWND
        hwnd_fg = user32.GetForegroundWindow()
        if hwnd_fg:
            pid_fg = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd_fg, ctypes.byref(pid_fg))
            if pid_fg.value:
                proc_fg = _pid_image_name(pid_fg.value)
                if proc_fg in _CLIPBOARD_PROBE_PROCS and proc_fg not in _EXPLORER_CLIPBOARD_PROCS:
                    log_debug(f"[check_is_menu_query] PROBE: foreground probe {proc_fg}")
                    return "PROBE"
            if _is_taskbar_or_taskmgr_hwnd(hwnd_fg):
                log_debug("[check_is_menu_query] PROBE: foreground taskbar/taskmgr")
                return "PROBE"
    except Exception:
        pass

    t_now = time.time()
    time_since_lbutton = t_now - (last_lbutton or 0)
    time_since_rbutton = t_now - (last_rbutton or 0)
    meta_age = t_now - (meta_arrival_time or 0)
    lmb_down = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
    rmb_down = bool(user32.GetAsyncKeyState(0x02) & 0x8000)
    menu_visible = _context_menu_open()
    is_ctrl_v = (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000)
    is_shift_ins = (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000)
    recent_ctrl_v = bool(last_ctrl_v and (t_now - last_ctrl_v) < 2.0)
    # Double-click (mở file trong Explorer) không bao giờ là Paste. Ô lệnh Win11 nằm
    # sát hàng file đầu tiên nên double-click dễ bị nhận nhầm là bấm nút Paste.
    recent_dblclick = bool(last_dblclick and (t_now - last_dblclick) < 0.7)

    # Chuột phải đang giữ: Explorer GetData để vẽ mục Paste — chưa phải Paste.
    if rmb_down:
        log_debug("[check_is_menu_query] MENU: RMB dang giu")
        return "MENU"
    if lmb_on_menu and menu_item_kind == "not_paste":
        log_debug("[check_is_menu_query] MENU: click khong phai Paste (Show more / muc khac)")
        return "MENU"

    if is_ctrl_v or is_shift_ins or recent_ctrl_v:
        # Ctrl+V chỉ coi là Paste file khi cửa sổ đích là Explorer VÀ clipboard không chứa định dạng Text
        has_text = bool(user32.IsClipboardFormatAvailable(13) or user32.IsClipboardFormatAvailable(1))
        is_explorer = _is_explorer_clipboard_client()
        if is_explorer and not has_text:
            log_debug("[check_is_menu_query] Paste: phim Ctrl+V / Shift+Ins trong Explorer")
            return False
        else:
            log_debug(f"[check_is_menu_query] Bỏ qua Ctrl+V: is_explorer={is_explorer} has_text={has_text}")
            return "BACKGROUND"

    win11 = _is_windows_11()
    profile = _shell_menu_profile()

    # --- Win10 classic: chỉ Paste khi đọc đúng tên mục (paste/dán/...). ---
    # --- Win11 XAML: chấp nhận unknown (không đọc được chữ trên menu). ---
    clicked_paste_item = bool(
        lmb_on_menu
        and _menu_item_counts_as_paste(menu_item_kind)
        and time_since_lbutton < 3.0
        and time_since_rbutton > 0.12
        and time_since_rbutton < 8.0
    )
    if win11:
        # Win11: LMB đang giữ trên menu (poll có thể chưa kịp set kind=paste).
        lmb_menu_paste_now = bool(
            lmb_down
            and lmb_on_menu
            and menu_item_kind != "not_paste"
            and time_since_rbutton > 0.12
            and time_since_lbutton < 2.0
        )
    else:
        # Win10: kind==paste nếu đọc được chữ; không thì LMB sau RMB trên #32768.
        lmb_menu_paste_now = bool(
            lmb_down
            and lmb_on_menu
            and menu_item_kind != "not_paste"
            and time_since_rbutton > 0.12
            and time_since_lbutton < 2.0
        ) or _win10_rmb_paste_click(
            last_lbutton, last_rbutton, menu_item_kind, last_dblclick,
            lmb_on_menu=lmb_on_menu, lmb_down=lmb_down, menu_visible=menu_visible,
        )
    cmd_bar_paste = bool(
        (not lmb_on_menu)
        and win11 and lmb_down and _cursor_in_explorer_command_bar()
        and time_since_rbutton > 0.2
        and not recent_dblclick
    )

    if clicked_paste_item or lmb_menu_paste_now:
        log_debug(
            f"[check_is_menu_query] Paste: menu click profile={profile} "
            f"kind={menu_item_kind!r} now={lmb_menu_paste_now}"
        )
        return False
    if cmd_bar_paste:
        log_debug("[check_is_menu_query] Paste: Win11 command-bar")
        return False
    # Race RENDERFORMAT trước mouse-poll — Win11 XAML và Win10 #32768.
    if (
        lmb_down
        and menu_visible
        and not rmb_down
        and time_since_rbutton > 0.12
        and time_since_rbutton < 8.0
        and menu_item_kind != "not_paste"
    ):
        log_debug(f"[check_is_menu_query] Paste: {profile} LMB+menu visible (race trước poll)")
        return False
    if (not win11) and _win10_rmb_paste_click(
        last_lbutton, last_rbutton, menu_item_kind, last_dblclick,
        lmb_on_menu=lmb_on_menu, lmb_down=lmb_down, menu_visible=menu_visible,
    ):
        log_debug(f"[check_is_menu_query] Paste: Win10 LMB-after-RMB kind={menu_item_kind!r}")
        return False
    # Win11 XAML: hit-test menu hay fail — LMB sau RMB + Explorer GetData = Paste.
    # (gesture_ok ở render_format vẫn chặn paste giả sau khi đã clear _rmb_cursor_pos).
    if win11 and (
        lmb_down
        and not rmb_down
        and not recent_dblclick
        and menu_item_kind != "not_paste"
        and time_since_rbutton > 0.18
        and time_since_rbutton < 8.0
        and time_since_lbutton < 1.5
        and _is_explorer_clipboard_client()
    ):
        log_debug("[check_is_menu_query] Paste: Win11 LMB after RMB (XAML heuristic)")
        return False
    if menu_visible:
        # Menu còn mở nhưng chưa click Paste (chỉ hover / RMB) — dummy HDROP.
        log_debug(f"[check_is_menu_query] MENU: context menu dang mo profile={profile}")
        return "MENU"
    # Vừa RMB xong (menu đang mở / vừa vẽ) — chưa phải Paste.
    if time_since_rbutton < 1.2 and not lmb_down:
        log_debug("[check_is_menu_query] MENU: vua RMB (menu paint)")
        return "MENU"

    try:
        import win32gui
        hwnd_fg = win32gui.GetForegroundWindow()
        if hwnd_fg:
            title = win32gui.GetWindowText(hwnd_fg)
            if title and ("Remote Desktop" in title or "Easy Remote" in title):
                log_debug(f"[check_is_menu_query] BACKGROUND: cua so app ({title})")
                return "BACKGROUND"
    except Exception:
        pass

    if _is_explorer_clipboard_client():
        log_debug("[check_is_menu_query] BACKGROUND: Explorer probe (khong phai Paste)")
        return "BACKGROUND"

    log_debug(f"[check_is_menu_query] BACKGROUND: khong co cu chi Paste (meta_age={meta_age:.3f}s)")
    return "BACKGROUND"


_cleanup_stale_transfers()


class FileCopyClientMixin:
    """Mixin: nhận file từ host khi paste trên client."""

    def setup_delayed_rendering(self):
        log_debug(f"[setup_delayed_rendering] Bắt đầu. self.listener={self.listener}")
        force = getattr(self, "_force_delayed_setup", False)
        if not force:
            if self._user_clipboard_wins():
                self._allow_delayed = False
                log_debug("[setup_delayed_rendering] Giữ clipboard local của user.")
                return
            if not getattr(self, "_allow_delayed", True):
                return
        else:
            self._allow_delayed = True
        if self.listener and self.listener.hwnd:
            self._suppress_render_until = max(getattr(self, "_suppress_render_until", 0), time.time() + 2.0)
            user32 = ctypes.windll.user32
            hwnd = ctypes.c_void_p(self.listener.hwnd)
            msg = 0x0400 + 101
            # Host→client: SendMessage để CF_HDROP sẵn sàng trước khi user mở menu Paste.
            if force:
                user32.SendMessageW(hwnd, msg, 0, 0)
                log_debug("[setup_delayed_rendering] SendMessage WM_SETUP_DELAYED_RENDERING (force)")
            else:
                user32.PostMessageW(hwnd, msg, 0, 0)
                log_debug("[setup_delayed_rendering] PostMessage WM_SETUP_DELAYED_RENDERING")
        else:
            log_debug("[setup_delayed_rendering] Lỗi: listener hoặc hwnd chưa sẵn sàng.")

    def _schedule_delayed_rearm(self, delay_s=0.45):
        """Sau paste/Hủy: đợi Explorer xong rồi hứa CF_HDROP lại (nếu vẫn còn offer)."""
        gen = int(getattr(self, "_rearm_gen", 0) or 0) + 1
        self._rearm_gen = gen
        self._suppress_render_until = max(getattr(self, "_suppress_render_until", 0), time.time() + delay_s + 2.5)

        def _go(g=gen):
            if g != getattr(self, "_rearm_gen", 0):
                return
            if not getattr(self, "_allow_delayed", True):
                return
            try:
                if self._user_clipboard_wins():
                    return
            except Exception:
                pass
            if self.pending_remote_files or self._reoffer_files:
                if not self.pending_remote_files:
                    self.pending_remote_files = list(self._reoffer_files or [])
                log_debug("[delayed_rearm] Đăng ký lại delayed CF_HDROP.")
                self.setup_delayed_rendering()

        threading.Timer(delay_s, _go).start()

    def _release_remote_file_offer(self, reason=""):
        """User copy local trên client → bỏ offer host→client (tránh lẫn với copy client→host)."""
        had = bool(self.pending_remote_files or getattr(self, "_reoffer_files", None))
        self._rearm_gen = int(getattr(self, "_rearm_gen", 0) or 0) + 1
        self.pending_remote_files = []
        self._reoffer_files = None
        self._allow_delayed = False
        self._force_delayed_setup = False
        self._expect_repaste_until = 0.0
        self.dummy_h_active = False
        self._hdrop_materialized = True
        self._lmb_hit_context_menu = False
        self._lmb_menu_item_kind = ""
        self._rmb_cursor_pos = None
        if had:
            print(f"[Clipboard] Nhả offer host→client ({reason}).")
            clip_trace(f"[release_remote_offer] {reason}")

    def _offer_empty_and_rearm(self, delay_s=0.2, offer=True, rearm=False):
        """Trong WM_RENDERFORMAT: SetClipboardData HDROP rỗng.
        Mặc định KHÔNG rearm delayed — rearm gây vòng BACKGROUND ↔ EmptyClipboard.
        Delayed chỉ đăng ký lại lúc RMB / Ctrl+V / LMB-Paste / apply_file_offer."""
        if offer:
            ok = _offer_empty_hdrop()
            if not ok:
                self.dummy_h_active = True
                return False
        self.dummy_h_active = True
        self._hdrop_materialized = True  # đã có HDROP thật (rỗng), không còn delayed
        if not rearm:
            self._empty_rearm_due = 0.0
            return True
        now = time.time()
        due = getattr(self, "_empty_rearm_due", 0.0) or 0.0
        if due > now:
            return True
        self._empty_rearm_due = now + max(delay_s, 0.5)
        def _go():
            self._empty_rearm_due = 0.0
            if not (self.pending_remote_files or getattr(self, "_reoffer_files", None)):
                return
            try:
                self._force_delayed_setup = True
                self.setup_delayed_rendering()
            except Exception:
                pass
        try:
            threading.Timer(max(delay_s, 0.5), _go).start()
        except Exception:
            pass
        return True

    def _ensure_delayed_for_gesture(self):
        """Trước Paste thật: nếu HDROP đã materialize, đăng ký lại delayed (SendMessage)."""
        if not (self.pending_remote_files or getattr(self, "_reoffer_files", None)):
            return
        try:
            if self._user_clipboard_wins():
                return
        except Exception:
            pass
        self.dummy_h_active = False
        self._hdrop_materialized = False
        self._force_delayed_setup = True
        try:
            self.setup_delayed_rendering()
        except Exception:
            pass

    def _execute_setup_delayed_rendering(self):
        if not self.listener or not self.listener.hwnd:
            log_debug("[_execute_setup_delayed_rendering] Lỗi: hwnd chưa sẵn sàng.")
            return
        force = getattr(self, "_force_delayed_setup", False)
        if not force:
            if self._user_clipboard_wins():
                self._allow_delayed = False
                log_debug("[_execute_setup_delayed_rendering] Bỏ EmptyClipboard — clipboard đang thuộc user.")
                return
        else:
            self._allow_delayed = True

        user32 = ctypes.windll.user32
        hwnd = ctypes.c_void_p(self.listener.hwnd)
        log_debug(f"[_execute_setup_delayed_rendering] Đang cố gắng OpenClipboard với HWND: {self.listener.hwnd}")
        if not user32.OpenClipboard(hwnd):
            self._delayed_setup_tries = getattr(self, "_delayed_setup_tries", 0) + 1
            if self._delayed_setup_tries <= 40:
                if force:
                    self._force_delayed_setup = True
                threading.Timer(0.025, self.setup_delayed_rendering).start()
            else:
                err = ctypes.GetLastError()
                log_debug(f"[_execute_setup_delayed_rendering] OpenClipboard THẤT BẠI sau retry. GetLastError: {err}")
            return
        self._delayed_setup_tries = 0
        self._force_delayed_setup = False
        if not force and self._user_clipboard_wins():
            user32.CloseClipboard()
            self._allow_delayed = False
            log_debug("[_execute_setup_delayed_rendering] OpenClipboard xong nhưng clipboard thuộc user — đóng, không EmptyClipboard.")
            return
        log_debug("[_execute_setup_delayed_rendering] OpenClipboard thành công. Đang EmptyClipboard...")
        self.ignore_destroy_clipboard = True
        try:
            user32.EmptyClipboard()
        finally:
            self.ignore_destroy_clipboard = False
            
        # Thiết lập các format loại trừ Clipboard History và Cloud Clipboard
        setup_clipboard_exclusions()
        
        res = fn_SetClipboardData(15, None) # CF_HDROP với delayed rendering (None handle)
        if res:
            global last_clipboard_set_time
            last_clipboard_set_time = time.time()
        err = ctypes.GetLastError()
        log_debug(f"[_execute_setup_delayed_rendering] SetClipboardData CF_HDROP trả về: {res}, GetLastError: {err}")
        user32.CloseClipboard()
        mark_own_clipboard_write()
        self._hdrop_materialized = False
        self.dummy_h_active = False
        print("[Clipboard] Đã thiết lập delayed rendering (CF_HDROP) trên Clipboard và loại trừ Clipboard History.")

    def lost_ownership(self):
        if getattr(self, 'ignore_destroy_clipboard', False):
            log_debug("[lost_ownership] Bỏ qua WM_DESTROYCLIPBOARD vì tự thực hiện EmptyClipboard.")
            return
        self._allow_delayed = False
        print("[Clipboard] Đã mất quyền sở hữu clipboard (người dùng copy dữ liệu khác).")
        # Viewer còn mở + còn offer host→client: user copy local → nhả offer ngay.
        if getattr(self, "pygame_hwnd", None) and (
            self.pending_remote_files or getattr(self, "_reoffer_files", None)
        ):
            try:
                from utils.clipboard_api import _clipboard_owned_by_sync_window
                if not _clipboard_owned_by_sync_window():
                    self._release_remote_file_offer("lost_ownership")
            except Exception:
                self._release_remote_file_offer("lost_ownership")

    def get_active_explorer_path(self):
        """Chỉ dùng path đã chốt / last-good — không hỏi COM trong WM_RENDERFORMAT."""
        for key in ("_paste_dest_snapshot", "_last_good_explorer_path", "cached_explorer_path", "_paste_dest_dir"):
            p = getattr(self, key, None)
            if p and os.path.isdir(p) and not _is_transfer_staging_dir(p):
                clip_trace(f"[get_active_explorer_path] pick {key}={p}")
                return p
        clip_trace("[get_active_explorer_path] NONE "
                   f"dir={getattr(self,'_paste_dest_dir',None)} "
                   f"snap={getattr(self,'_paste_dest_snapshot',None)} "
                   f"last={getattr(self,'_last_good_explorer_path',None)} "
                   f"cache={getattr(self,'cached_explorer_path',None)} "
                   f"frozen={getattr(self,'_paste_dest_frozen',False)}")
        return None

    def snapshot_paste_dest(self, reason="", sync=False):
        """Chốt thư mục Paste cho lần Paste sắp tới.

        Khi đang tải (frozen) vẫn cập nhật snapshot — Paste song song cần thư mục mới;
        không ghi đè _paste_dest_dir của job đang chạy.
        """
        def _go(why=reason):
            if why == "rmb" and _is_taskbar_or_taskmgr_at_point(_cursor_xy()):
                clip_trace("[snapshot_paste_dest] skip rmb on taskbar/taskmgr")
                return
            frozen = bool(getattr(self, "_paste_dest_frozen", False))
            # Ưu tiên path đang cache (không COM) — RMB lúc clipboard mở hay fail COM.
            instant = getattr(self, "_last_good_explorer_path", None) or getattr(self, "cached_explorer_path", None)
            if instant and os.path.isdir(instant) and not _is_transfer_staging_dir(instant):
                self._paste_dest_snapshot = instant
                clip_trace(f"[snapshot_paste_dest] instant cache reason={why} path={instant} frozen={frozen}")
            try:
                found = query_explorer_folder_path(allow_open_clipboard=False)
                if not found:
                    found = query_explorer_folder_path(allow_open_clipboard=True)
                if found and os.path.isdir(found) and not _is_transfer_staging_dir(found):
                    self._paste_dest_snapshot = found
                    self._last_good_explorer_path = found
                    self.cached_explorer_path = found
                    # Không đụng _paste_dest_dir khi frozen — job đang chạy giữ dest riêng.
                    log_debug(f"[snapshot_paste_dest] {why}: {found}")
                    clip_trace(f"[snapshot_paste_dest] OK reason={why} path={found} frozen={frozen}")
                    print(f"[Clipboard] Chốt thư mục Paste ({why}): {found}")
                elif instant:
                    clip_trace(f"[snapshot_paste_dest] COM miss, keep cache reason={why} path={instant}")
                    print(f"[Clipboard] Chốt thư mục Paste ({why}, cache): {instant}")
                else:
                    clip_trace(f"[snapshot_paste_dest] FAIL reason={why} no path")
            except Exception as e:
                log_debug(f"[snapshot_paste_dest] {why}: {e}")
                clip_trace(f"[snapshot_paste_dest] ERR reason={why}: {e}")

        if sync:
            _go()
        else:
            threading.Thread(target=_go, daemon=True, name="SnapPasteDest").start()

    def _lock_paste_dest(self, dest, paste_id=None):
        """Đóng băng thư mục đích cho 1 lần Paste — không cho cacher/đổi folder ghi đè."""
        if not dest or not os.path.isdir(dest) or _is_transfer_staging_dir(dest):
            clip_trace(f"[lock_paste_dest] REJECT dest={dest!r} paste_id={paste_id}")
            return None
        self._paste_dest_dir = dest
        self._paste_dest_snapshot = dest
        self._last_good_explorer_path = dest
        self.cached_explorer_path = dest
        self._paste_dest_frozen = True
        try:
            pid = int(paste_id if paste_id is not None else getattr(self, "_clipboard_paste_id", 0) or 0)
        except Exception:
            pid = 0
        if pid:
            mp = getattr(self, "_xfer_dest_by_paste_id", None)
            if mp is None:
                self._xfer_dest_by_paste_id = {}
                mp = self._xfer_dest_by_paste_id
            mp[pid] = dest
        print(f"[Clipboard] Lock Paste dest paste_id={pid}: {dest}")
        clip_trace(f"[lock_paste_dest] LOCK paste_id={pid} dest={dest}")
        return dest

    def _unlock_paste_dest(self):
        was = getattr(self, "_paste_dest_dir", None)
        self._paste_dest_frozen = False
        clip_trace(f"[unlock_paste_dest] was_dest={was}")

    def _explorer_path_cacher_loop(self):
        """Cache path Explorer. Khi đang Paste/frozen: chỉ cập nhật last-good, KHÔNG đụng dest paste."""
        while True:
            time.sleep(0.3)
            try:
                frozen = bool(
                    getattr(self, "_paste_dest_frozen", False)
                    or getattr(self, "transfer_in_progress", False)
                )
                if (
                    not frozen
                    and time.time() - float(getattr(self, "_last_clip_event_at", 0) or 0) < 1.0
                ):
                    continue
                found_path = query_explorer_folder_path(allow_open_clipboard=False)
                if not found_path and not frozen:
                    found_path = query_explorer_folder_path(allow_open_clipboard=True)
                if not found_path or not os.path.isdir(found_path):
                    continue
                if _is_transfer_staging_dir(found_path):
                    continue
                prev = getattr(self, "cached_explorer_path", None)
                # Luôn nhớ path đang xem (để RMB chốt ngay), nhưng không ghi đè dest đang tải.
                self.cached_explorer_path = found_path
                if not frozen:
                    self._last_good_explorer_path = found_path
                elif prev != found_path:
                    clip_trace(f"[cacher] navigate while FROZEN/xfer live={found_path} locked={getattr(self,'_paste_dest_dir',None)} (ignored for paste)")
            except Exception:
                pass

    def show_classic_conflict_dialog(self, filename, source_info, dest_info, has_multiple=False):
        # Headless không có UI — tuyệt đối không tự Replace (trước đây return replace
        # → client→host ghi đè im lặng nếu đi nhầm vào nhánh này).
        if self.app and getattr(self.app, 'is_headless', False):
            try:
                log_overwrite_conflict(
                    f"show_classic_conflict_dialog HEADLESS → cancel "
                    f"(no auto-replace) file={filename!r} multi={has_multiple}"
                )
            except Exception:
                pass
            print(
                f"[Clipboard] HEADLESS conflict → cancel (khong auto-replace): {filename}"
            )
            return "cancel"
        self.overwrite_event.clear()
        self.overwrite_choice = None
        self.overwrite_all = False
        self._conflict_ui_active = True
        
        self.gui_queue.put(("classic_overwrite_dialog", (filename, source_info, dest_info, has_multiple)))
        
        # Chờ luồng GUI; không PeekMessage toàn cục — sẽ nuốt chuột của dialog Tk.
        start_wait = time.time()
        try:
            while time.time() - start_wait < 300.0:
                if self.overwrite_event.is_set():
                    break
                time.sleep(0.02)
        finally:
            self._conflict_ui_active = False
                
        choice = self.overwrite_choice if self.overwrite_choice else "cancel"
        if choice in ("replace", "skip") and self.overwrite_all:
            choice = choice + "_all"
        return choice

    def _handle_paste_conflict_query(self, packet):
        """Client→host: hỏi ghi đè bằng CÙNG show_classic_conflict_dialog như host→client.

        Headless: không có UI — forward sang client; nếu không có socket thì CONFLICT_REPLY
        cancelled để agent fallback dialog HOST (không được return im lặng).
        """
        try:
            paste_id = int(packet.get("paste_id") or 0)
        except Exception:
            paste_id = 0
        conflicts = list(packet.get("conflicts") or [])
        has_multiple = bool(packet.get("has_multiple")) or len(conflicts) > 1

        # Host (headless worker / GUI host): luôn chuyển sang viewer — user đang nhìn pygame.
        # Không hỏi trên Tk ẩn/tray của host (dialog bị che → “paste trùng tên không hoạt động”).
        is_viewer = bool(getattr(self, "pygame_hwnd", None))
        is_host_side = bool(
            (self.app and (
                getattr(self.app, "is_headless", False)
                or getattr(self.app, "is_host_only", False)
            ))
            or (not is_viewer and getattr(self, "active_sockets", None))
        )
        if is_host_side and not is_viewer:
            pkt = json.dumps({
                "type": "paste_conflict_query",
                "paste_id": paste_id,
                "conflicts": conflicts,
                "has_multiple": has_multiple,
            }).encode("utf-8")
            sent = 0
            with self.lock:
                socks = list(self.active_sockets or [])
            for s in socks:
                try:
                    send_msg(s, pkt)
                    sent += 1
                except Exception:
                    pass
            try:
                log_overwrite_conflict(
                    f"HOST_HEADLESS forward paste_conflict_query paste_id={paste_id} "
                    f"n={len(conflicts)} sent_socks={sent}"
                )
            except Exception:
                pass
            print(
                f"[Clipboard] CONFLICT_QUERY → client paste_id={paste_id} "
                f"n={len(conflicts)} socks={sent}"
            )
            if sent <= 0:
                # Không có socket client — agent hiện ClassicCopyDialog trên HOST.
                try:
                    self._send_to_pipe(
                        "CONFLICT_REPLY",
                        json.dumps({
                            "paste_id": paste_id,
                            "unavailable": True,
                            "cancelled": False,
                            "skip_keys": [],
                            "replace_keys": [],
                        }),
                    )
                    log_overwrite_conflict(
                        f"HOST_HEADLESS no client socket → CONFLICT_REPLY unavailable "
                        f"paste_id={paste_id}"
                    )
                except Exception as e:
                    print(f"[Clipboard] CONFLICT_REPLY unavailable (no sock) loi: {e}")
            return

        skip_keys = []
        replace_keys = []
        cancelled = False
        replace_all = False
        skip_all = False
        print(f"[Clipboard] paste_conflict_query (client→host) paste_id={paste_id} n={len(conflicts)}")
        try:
            log_overwrite_conflict(
                f"CLIENT_GUI paste_conflict_query paste_id={paste_id} n={len(conflicts)} "
                f"→ show ClassicCopyDialog"
            )
        except Exception:
            pass
        try:
            # Không lift Tk ẩn của viewer (alpha=0) — kéo parent xuống sẽ che dialog dưới pygame.
            for i, item in enumerate(conflicts):
                if not isinstance(item, dict):
                    continue
                filename = item.get("filename") or ""
                source_info = item.get("source_info") or {}
                dest_info = item.get("dest_info") or {}
                dest_path = item.get("dest_path") or (dest_info.get("path") if isinstance(dest_info, dict) else "")
                try:
                    key = os.path.normcase(os.path.abspath(dest_path)) if dest_path else dest_path
                except Exception:
                    key = dest_path
                if skip_all:
                    if key:
                        skip_keys.append(key)
                    continue
                if replace_all:
                    if key:
                        replace_keys.append(key)
                    continue
                # Cùng API với paste host→client trong render_format.
                choice = self.show_classic_conflict_dialog(
                    filename, source_info, dest_info, has_multiple
                )
                log_debug(f"[paste_conflict_query] {filename}: {choice}")
                try:
                    log_overwrite_conflict(
                        f"CLIENT_GUI conflict choice={choice!r} file={filename!r}"
                    )
                except Exception:
                    pass
                apply_all = choice.endswith("_all") if choice else False
                base = choice[:-4] if apply_all else choice
                if base == "replace":
                    if key:
                        replace_keys.append(key)
                    if apply_all:
                        replace_all = True
                elif base == "skip":
                    if key:
                        skip_keys.append(key)
                    if apply_all:
                        skip_all = True
                        for j in range(i + 1, len(conflicts)):
                            it = conflicts[j]
                            if not isinstance(it, dict):
                                continue
                            dp = it.get("dest_path") or ((it.get("dest_info") or {}).get("path"))
                            try:
                                skip_keys.append(os.path.normcase(os.path.abspath(dp)) if dp else dp)
                            except Exception:
                                if dp:
                                    skip_keys.append(dp)
                        break
                else:
                    cancelled = True
                    break
        except Exception as e:
            print(f"[Clipboard] paste_conflict_query loi: {e}")
            cancelled = True
        reply = {
            "type": "paste_conflict_reply",
            "paste_id": paste_id,
            "cancelled": cancelled,
            "skip_keys": skip_keys,
            "replace_keys": replace_keys,
        }
        try:
            sock = self._live_xfer_sock() if hasattr(self, "_live_xfer_sock") else getattr(self, "sock", None)
            if sock:
                send_msg(sock, json.dumps(reply).encode("utf-8"))
                print(
                    f"[Clipboard] paste_conflict_reply paste_id={paste_id} "
                    f"cancelled={cancelled} skip={len(skip_keys)} replace={len(replace_keys)}"
                )
                try:
                    log_overwrite_conflict(
                        f"CLIENT_GUI paste_conflict_reply paste_id={paste_id} "
                        f"cancelled={cancelled} replace={len(replace_keys)} skip={len(skip_keys)}"
                    )
                except Exception:
                    pass
            else:
                print("[Clipboard] paste_conflict_reply — khong co socket")
                try:
                    log_overwrite_conflict(
                        f"CLIENT_GUI paste_conflict_reply FAIL no socket paste_id={paste_id}"
                    )
                except Exception:
                    pass
        except Exception as e:
            print(f"[Clipboard] Gui paste_conflict_reply loi: {e}")

    def render_format(self, fmt_id):
        if fmt_id != 15: # CF_HDROP
            return

        pending = self.pending_remote_files or []
        if not pending:
            # Vẫn log — Paste không có offer thì clipboard_agent.log trước đây “im thin thít”.
            clip_trace(
                f"[render_format] ENTER no-pending profile={_shell_menu_profile()} "
                f"lmb_menu={getattr(self,'_lmb_hit_context_menu',False)} "
                f"kind={getattr(self,'_lmb_menu_item_kind',None)!r} "
                f"snap={getattr(self,'_paste_dest_snapshot',None)}",
                throttle_s=1.0,
                key="rf_no_pending",
            )
            return
            
        # Kiểm tra nếu là truy vấn từ menu chuột phải (context menu) thì tránh tải file thực tế lúc này
        last_l = getattr(self, 'last_lbutton_time', 0.0)
        last_r = getattr(self, 'last_rbutton_time', 0.0)
        meta_time = getattr(self, 'meta_arrival_time', 0.0)
        last_ctrl_v = getattr(self, 'last_ctrl_v_time', 0.0)
        is_menu = check_is_menu_query(
            last_l, last_r, meta_time, last_ctrl_v,
            expect_repaste=time.time() < getattr(self, "_expect_repaste_until", 0),
            lmb_on_menu=bool(getattr(self, "_lmb_hit_context_menu", False)),
            menu_item_kind=getattr(self, "_lmb_menu_item_kind", "") or "",
            last_dblclick=getattr(self, "last_dblclick_time", 0.0),
        )
        clip_trace(
            f"[render_format] ENTER profile={_shell_menu_profile()} is_menu={is_menu!r} "
            f"gesture={getattr(self,'_paste_gesture_id',0)}/{getattr(self,'_consumed_paste_gesture_id',0)} "
            f"lmb_menu={getattr(self,'_lmb_hit_context_menu',False)} kind={getattr(self,'_lmb_menu_item_kind',None)!r} "
            f"pending_n={len(pending)} "
            f"snap={getattr(self,'_paste_dest_snapshot',None)} "
            f"last={getattr(self,'_last_good_explorer_path',None)} "
            f"cache={getattr(self,'cached_explorer_path',None)} "
            f"frozen={getattr(self,'_paste_dest_frozen',False)}",
            throttle_s=0.5 if is_menu in ("MENU", "BACKGROUND") else 0.0,
            key=f"rf_enter_{is_menu}",
        )
        if is_menu == "MENU":
            log_debug("[render_format] Phát hiện truy vấn menu. Cung cấp dummy HDROP và chờ user dán...")
            clip_trace("[render_format] → MENU (dummy HDROP, chưa tải)", throttle_s=0.5, key="rf_menu")
            if not getattr(self, "_paste_dest_snapshot", None):
                self.snapshot_paste_dest("menu_query")
            if _offer_probe_hdrop(self.pending_remote_files):
                self._offer_empty_and_rearm(0.25, offer=False)
            dest = self.get_active_explorer_path()
            _schedule_scrub_probe(dest)
            return
        elif is_menu in ("BACKGROUND", "PROBE"):
            log_debug(f"[render_format] Probe/menu Explorer ({is_menu}) — HDROP rỗng (không dán stub 0 byte).")
            clip_trace(f"[render_format] → {is_menu} (empty HDROP)", throttle_s=1.0, key=f"rf_{is_menu.lower()}")
            self._offer_empty_and_rearm(0.25)
            return

        # is_menu is False (coi là Paste) — vẫn đòi cử chỉ Paste thật để tránh
        # Explorer GetData / click mơ hồ tự tải vào thư mục đang mở (vd. D:\).
        has_clip_text = bool(
            ctypes.windll.user32.IsClipboardFormatAvailable(13)
            or ctypes.windll.user32.IsClipboardFormatAvailable(1)
        )
        gesture_ok = (
            getattr(self, "_paste_gesture_id", 0) > getattr(self, "_consumed_paste_gesture_id", 0)
            or (last_ctrl_v and (time.time() - last_ctrl_v) < 2.5 and _is_explorer_clipboard_client() and not has_clip_text)
        )
        if not gesture_ok:
            # RENDERFORMAT có thể tới trước khi poll kịp note_paste_gesture.
            kind = getattr(self, "_lmb_menu_item_kind", "") or ""
            try:
                user32 = ctypes.windll.user32
                lmb = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
            except Exception:
                lmb = False
            age_r = (time.time() - last_r) if last_r else 999.0
            age_l = (time.time() - (last_l or 0)) if last_l else 999.0
            lmb_after_rmb = bool(
                last_r
                and last_l
                and last_l > last_r
                and 0.12 < age_r < 8.0
                and age_l < 3.0
                and kind != "not_paste"
                and (
                    bool(getattr(self, "_lmb_hit_context_menu", False))
                    or kind == "paste"
                    or lmb
                    or _is_explorer_clipboard_client()
                )
            )
            if _is_windows_11() and lmb and last_r and getattr(self, "_rmb_cursor_pos", None) and (
                0.18 < age_r < 8.0
                and age_l < 1.5
                and kind != "not_paste"
                and (
                    bool(getattr(self, "_lmb_hit_context_menu", False))
                    or kind == "paste"
                    or _is_explorer_clipboard_client()
                )
            ):
                gesture_ok = True
                self.note_paste_gesture()
                clip_trace(
                    f"[render_format] gesture_ok via win11 LMB-after-RMB "
                    f"age_r={age_r:.2f} kind={kind!r}"
                )
            elif (not _is_windows_11()) and lmb_after_rmb:
                gesture_ok = True
                self.note_paste_gesture()
                clip_trace(
                    f"[render_format] gesture_ok via win10 LMB-after-RMB "
                    f"age_r={age_r:.2f} age_l={age_l:.2f} kind={kind!r}"
                )
        if not gesture_ok:
            try:
                user32 = ctypes.windll.user32
                lmb = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
                if (
                    _is_windows_11()
                    and lmb
                    and _cursor_in_explorer_command_bar()
                    and (time.time() - (last_r or 0)) > 0.2
                ):
                    gesture_ok = True
            except Exception:
                pass
        if not gesture_ok:
            log_debug("[render_format] Chưa có cử chỉ Paste (Ctrl+V / mục Paste) — không tải file.")
            clip_trace("[render_format] → no gesture (empty HDROP)", throttle_s=1.0, key="rf_nogesture")
            self._offer_empty_and_rearm(0.25)
            return

        cancel_at = float(getattr(self, "_xfer_cancel_at", 0) or 0)
        if cancel_at:
            new_kb = getattr(self, "last_ctrl_v_time", 0) > cancel_at + 0.15
            new_menu = (
                bool(getattr(self, "_lmb_hit_context_menu", False))
                and getattr(self, "_lmb_menu_item_kind", "") == "paste"
                and getattr(self, "last_lbutton_time", 0) > cancel_at + 0.15
                and getattr(self, "last_rbutton_time", 0) > cancel_at
                and getattr(self, "last_lbutton_time", 0) > getattr(self, "last_rbutton_time", 0)
            )
            if not new_kb and not new_menu:
                log_debug("[render_format] Sau Hủy chưa có thao tác Paste mới — HDROP rỗng.")
                self._offer_empty_and_rearm(0.25)
                return

        if (
            (
                time.time() < getattr(self, "_suppress_render_until", 0)
                or time.time() < (getattr(self, "_last_paste_finish_time", 0) or 0) + 2.5
            )
            and getattr(self, "_paste_gesture_id", 0) <= getattr(self, "_consumed_paste_gesture_id", 0)
        ):
            log_debug("[render_format] Ngay sau Hủy / Hoàn tất paste — HDROP rỗng, không tải ngầm.")
            self._offer_empty_and_rearm(0.25)
            return
            
        if getattr(self, "_conflict_ui_active", False):
            log_debug("[render_format] Đang hiện dialog ghi đè — HDROP rỗng.")
            self._offer_empty_and_rearm(0.25)
            return

        # Chỉ chặn trùng GetData trong lúc handler sync — KHÔNG giữ is_rendering suốt lúc tải
        # (trước đây chặn Paste 2 khi dialog 1 còn mở).
        if getattr(self, 'is_rendering', False):
            log_debug("[render_format] WM_RENDERFORMAT trùng — HDROP rỗng (tránh dán stub 0 byte).")
            self._offer_empty_and_rearm(0.25)
            return

        same_gesture = getattr(self, "_paste_gesture_id", 0) <= getattr(self, "_consumed_paste_gesture_id", 0)
        fresh_input = (
            getattr(self, "last_ctrl_v_time", 0) > (getattr(self, "_last_paste_start", 0) or 0) + 0.08
            or (
                getattr(self, "last_lbutton_time", 0) > (getattr(self, "_last_paste_start", 0) or 0) + 0.08
                and getattr(self, "last_lbutton_time", 0) > (getattr(self, "last_rbutton_time", 0) or 0)
                and (
                    getattr(self, "_lmb_hit_context_menu", False)
                    or getattr(self, "_lmb_menu_item_kind", "") == "paste"
                )
            )
        )
        if same_gesture and not fresh_input:
            log_debug("[render_format] GetData trùng (chưa có Paste mới) — không mở dialog thêm.")
            clip_trace("[render_format] → same gesture no fresh input, skip", throttle_s=1.0, key="rf_same_gesture")
            self._offer_empty_and_rearm(0.25)
            return
            
        self.is_rendering = True
        self._expect_repaste_until = 0.0
        self._rearm_delayed_after_render = False
        self._clipboard_paste_id = getattr(self, "_clipboard_paste_id", 0) + 1
        self._consumed_paste_gesture_id = getattr(self, "_paste_gesture_id", 0)
        self._last_paste_start = time.time()
        paste_tok = int(getattr(self, "_clipboard_paste_id", 0) or 0)
        clip_trace(f"[render_format] PASTE START paste_id={paste_tok} dest_before_lock={dest_dir!r} living={living}")
        dest_dir = self._lock_paste_dest(dest_dir, paste_tok) or dest_dir
        if not dest_dir:
            print("[Clipboard] Paste host→client: KHÔNG có thư mục đích — bỏ qua (tránh dán theo folder sau này).")
            clip_trace("[render_format] ABORT no dest — empty HDROP")
            self._offer_empty_and_rearm(0.25)
            self.is_rendering = False
            return
        print(f"[Clipboard] Paste host→client vào: {dest_dir} (song song dialog={living})")
        clip_trace(f"[render_format] PASTE GO paste_id={paste_tok} locked_dest={dest_dir}")
        self._arm_file_xfer("gui_paste")
        self.transfer_in_progress = True
        try:
            print("[Clipboard] Nhận WM_RENDERFORMAT. Đang bắt đầu kiểm tra tệp tin ghi đè...")
            log_debug("[render_format] Nhận WM_RENDERFORMAT. Đang bắt đầu kiểm tra tệp tin ghi đè...")
            
            item_kind, display_name = _copy_batch_kind_and_name(self.pending_remote_files, _("Tệp tin"))
            total_size = sum(f.get("size", 0) for f in self.pending_remote_files)
            log_debug(f"[render_format] Thư mục đích phát hiện: {dest_dir}")
            clip_trace(f"[render_format] paste {item_kind}/{display_name} size={total_size} dest={dest_dir}")
            
            # Event riêng từng paste — không clear event của paste đang chạy.
            done_ev = threading.Event()
            pd = getattr(self, "_paste_done", None)
            if pd is None:
                self._paste_done = {}
                pd = self._paste_done
            pd[paste_tok] = done_ev
            if not living:
                self.transfer_done_event.clear()

            # Unblock Explorer ngay (empty HDROP) — tải nền vào thư mục đã LOCK lúc Paste.
            empty_now = create_hdrop_data([])
            if empty_now:
                self.ignore_destroy_clipboard = True
                try:
                    res0 = fn_SetClipboardData(15, empty_now)
                    if not res0:
                        fn_GlobalFree(empty_now)
                    log_debug(f"[render_format] Unblock Explorer empty HDROP res={res0} dest={dest_dir}")
                    clip_trace(f"[render_format] empty HDROP SetClipboardData res={res0} (Explorer may ding)")
                finally:
                    self.ignore_destroy_clipboard = False
            _schedule_scrub_probe(dest_dir)
            files_for_job = [dict(f) if isinstance(f, dict) else f for f in (self.pending_remote_files or [])]
            dest_for_job = dest_dir  # frozen — không đọc lại cache sau khi user đổi folder
            paste_ui = {
                "display_name": display_name,
                "total_size": total_size,
                "item_kind": item_kind,
            }
            clip_trace(f"[render_format] spawn ClientPasteFinish dest_for_job={dest_for_job} files={len(files_for_job)}")
            
            def background_download(
                dest_dir=dest_for_job,
                pending_files=files_for_job,
                paste_tok=paste_tok,
                ui=paste_ui,
            ):
                def _keep_offer(files_list):
                    keep = [dict(f) if isinstance(f, dict) else f for f in (files_list or [])]
                    if keep:
                        self._reoffer_files = keep
                        self.pending_remote_files = list(keep)
                        # Giữ offer đến khi host copy bộ file mới (không timeout ngắn).
                        self._expect_repaste_until = time.time() + 86400.0
                        self.dummy_h_active = True
                        self._hdrop_materialized = True
                    return keep

                def _open_progress_if_needed(files_list):
                    if self.app and getattr(self.app, "is_headless", False):
                        return
                    # Chỉ mở khi thật sự tải/sao chép — sau ghi đè.
                    name = (ui or {}).get("display_name") or _("Tệp tin")
                    kind = (ui or {}).get("item_kind") or "file"
                    size = sum((f.get("size", 0) if isinstance(f, dict) else 0) for f in (files_list or []))
                    if not size:
                        size = int((ui or {}).get("total_size") or 0)
                    self.open_paste_progress_dialog(
                        name, size, dest_dir,
                        reserve_finalize=True, job_id=paste_tok,
                        item_kind=kind,
                    )

                try:
                    clip_trace(f"[ClientPasteFinish] START paste_id={paste_tok} dest={dest_dir!r} n={len(pending_files or [])}")
                    offer_keep = [dict(f) if isinstance(f, dict) else f for f in (pending_files or [])]
                    self.pending_remote_files = list(offer_keep)
                    temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
                    os.makedirs(temp_dir, exist_ok=True)
                    self.target_save_dir = temp_dir
                    log_debug(f"[render_format] Tải vào thư mục tạm rồi chuyển sang đích: {temp_dir} → {dest_dir}")
                    clip_trace(f"[ClientPasteFinish] staging={temp_dir} → dest={dest_dir}")

                    files_to_download = []
                    files_to_replace = []
                    replace_names = set()  # basename đã chọn Replace — không short-circuit same-path
                    replace_all = False
                    skip_all = False
                    # Giữ full offer suốt phiên paste (không thu hẹp khi chỉ tải 1 phần).
                    self._reoffer_files = list(offer_keep)
            
                    if dest_dir and os.path.isdir(dest_dir):
                        cleanup_incomplete_named_files([dest_dir], self.pending_remote_files)
                        _schedule_scrub_probe(dest_dir)
                        for f in self.pending_remote_files:
                            filename = f.get("name")
                            if not filename:
                                continue
                            dest_file_path = os.path.join(dest_dir, filename.replace("/", os.sep))
                            top = str(filename).replace("\\", "/").strip("/").split("/")[0]
                    
                            if os.path.exists(dest_file_path):
                                if _is_transfer_junk_at_dest(dest_file_path, f.get("size")):
                                    _retry_remove_path(dest_file_path)
                                    files_to_download.append(f)
                                    continue
                                # File đã tồn tại → hỏi trước, rồi mới tải/copy (như TeamViewer).
                                if replace_all:
                                    files_to_download.append(f)
                                    files_to_replace.append(dest_file_path)
                                    replace_names.add(os.path.normcase(top))
                                elif skip_all:
                                    continue
                                else:
                                    source_info = {"size": f.get("size", 0), "mtime": f.get("mtime", 0)}
                                    try:
                                        dest_stat = os.stat(dest_file_path)
                                        dest_info = {"size": dest_stat.st_size, "mtime": dest_stat.st_mtime, "path": dest_file_path}
                                    except Exception:
                                        dest_info = {"size": 0, "mtime": 0, "path": dest_file_path}
                                
                                    has_multiple = len(self.pending_remote_files) > 1
                                    choice = self.show_classic_conflict_dialog(filename, source_info, dest_info, has_multiple)
                                    log_debug(f"[render_format] Kết quả lựa chọn ghi đè cho {filename}: {choice}")
                            
                                    if choice == "replace":
                                        files_to_download.append(f)
                                        files_to_replace.append(dest_file_path)
                                        replace_names.add(os.path.normcase(top))
                                    elif choice == "replace_all":
                                        replace_all = True
                                        files_to_download.append(f)
                                        files_to_replace.append(dest_file_path)
                                        replace_names.add(os.path.normcase(top))
                                    elif choice == "skip":
                                        continue
                                    elif choice == "skip_all":
                                        skip_all = True
                                        continue
                                    else: # cancel
                                        log_debug("[render_format] Hủy bỏ truyền tải từ hộp thoại ghi đè.")
                                        _keep_offer(offer_keep)
                                        self.close_dialog(reason="overwrite cancel")
                                        self._clear_paste_gesture_flags(1.0)
                                        self._schedule_delayed_rearm(0.6)
                                        if self.app and getattr(self.app, 'is_headless', False):
                                            self._send_progress_signal("CANCEL", "")
                                            self._close_transfer_pipe()
                                        return
                            else:
                                files_to_download.append(f)
                    else:
                        files_to_download = list(self.pending_remote_files)
                
                    if not files_to_download:
                        # Skip hết — vẫn giữ clipboard để Paste thư mục khác.
                        log_debug("[render_format] Không có tệp cần tải (skip). Giữ offer.")
                        _keep_offer(offer_keep)
                        self.close_dialog(reason="khong co file de tai")
                        self._clear_paste_gesture_flags(0.8)
                        self._schedule_delayed_rearm(0.5)
                        if self.app and getattr(self.app, 'is_headless', False):
                            self._send_progress_signal("CANCEL", "")
                            self._close_transfer_pipe()
                        return

                    # Ưu tiên copy local (Paste lần 2+ sang thư mục khác) — chỉ tải mạng phần còn thiếu.
                    # Replace cùng path: tải lại từ host (không short-circuit).
                    local_map = getattr(self, "_repaste_local_by_name", None) or {}
                    local_done = []
                    still_need = []
                    for f in files_to_download:
                        name = f.get("name") if isinstance(f, dict) else str(f)
                        top = str(name).replace("\\", "/").strip("/").split("/")[0]
                        top_key = os.path.normcase(top)
                        src = local_map.get(top_key) or local_map.get(top)
                        try:
                            dest_path = os.path.join(dest_dir, top) if dest_dir else None
                            same_as_dest = bool(
                                src
                                and dest_path
                                and os.path.exists(src)
                                and os.path.normcase(os.path.abspath(src))
                                == os.path.normcase(os.path.abspath(dest_path))
                            )
                        except Exception:
                            same_as_dest = False
                        if same_as_dest:
                            # Replace đúng chỗ đang đứng → tải lại từ host.
                            still_need.append(f)
                            continue
                        if src and os.path.exists(src):
                            local_done.append((f, src, top))
                        else:
                            still_need.append(f)

                    if local_done and not still_need:
                        # Chỉ local — không mở dialog tải mạng.
                        clip_trace(f"[ClientPasteFinish] LOCAL REPASTE only n={len(local_done)} → {dest_dir}")
                        placed = []
                        try:
                            import shutil
                            for _f, src, top in local_done:
                                dst = os.path.join(dest_dir, top)
                                if os.path.exists(dst):
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
                                local_map[os.path.normcase(top)] = os.path.abspath(dst)
                            self._repaste_local_by_name = local_map
                            self.batch_paths = placed
                            _keep_offer(offer_keep)
                            _notify_explorer_paths_changed(placed + [dest_dir])
                            clip_trace(f"[ClientPasteFinish] LOCAL REPASTE DONE → {placed[:8]}")
                            self._clear_paste_gesture_flags(0.8)
                            self._schedule_delayed_rearm(0.5)
                            return
                        except Exception as e:
                            clip_trace(f"[ClientPasteFinish] LOCAL REPASTE err: {e} — fallback network")
                            still_need = list(files_to_download)
                            local_done = []

                    if local_done and still_need:
                        # Copy phần local trước, phần còn lại tải mạng.
                        try:
                            import shutil
                            for _f, src, top in local_done:
                                dst = os.path.join(dest_dir, top)
                                if os.path.exists(dst):
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
                                local_map[os.path.normcase(top)] = os.path.abspath(dst)
                            self._repaste_local_by_name = local_map
                            clip_trace(f"[ClientPasteFinish] local partial {len(local_done)}, net {len(still_need)}")
                        except Exception as e:
                            clip_trace(f"[ClientPasteFinish] local partial err: {e}")
                            still_need = list(files_to_download)

                    files_to_download = still_need
                    # Giữ full offer trên clipboard; chỉ request_pending_files dùng subset.
                    _keep_offer(offer_keep)

                    # Xóa các file cần ghi đè TRƯỚC khi bắt đầu tải (để tránh xung đột ghi)
                    replace_key_set = set()
                    for p in files_to_replace:
                        try:
                            replace_key_set.add(os.path.normcase(os.path.abspath(p)))
                        except Exception:
                            if p:
                                replace_key_set.add(p)
                    for n in (replace_names or []):
                        if dest_dir and n:
                            try:
                                replace_key_set.add(
                                    os.path.normcase(os.path.abspath(os.path.join(dest_dir, n)))
                                )
                            except Exception:
                                pass
                    if paste_tok:
                        mp = getattr(self, "_xfer_replace_keys_by_paste", None)
                        if mp is None:
                            self._xfer_replace_keys_by_paste = {}
                            mp = self._xfer_replace_keys_by_paste
                        mp[paste_tok] = set(replace_key_set)
                    for p in files_to_replace:
                        try:
                            base = os.path.basename(str(p).rstrip("\\/"))
                            if any(
                                (f.get("name") if isinstance(f, dict) else str(f)) == base
                                or str(f.get("name") if isinstance(f, dict) else f).replace("\\", "/").split("/")[0] == base
                                for f in files_to_download
                            ):
                                if os.path.isdir(p) and not os.path.islink(p):
                                    import shutil
                                    shutil.rmtree(p, ignore_errors=True)
                                else:
                                    os.remove(p)
                        except Exception:
                            try:
                                _retry_remove_path(p)
                            except Exception:
                                pass

                    if not files_to_download:
                        _notify_explorer_paths_changed([dest_dir] if dest_dir else [])
                        self._clear_paste_gesture_flags(0.8)
                        self._schedule_delayed_rearm(0.5)
                        return

                    # Mở dialog tiến trình CHỈ khi bắt đầu tải từ host (sau conflict).
                    _open_progress_if_needed(files_to_download)
            
                    # Yêu cầu truyền file thực tế từ đối tác
                    self.request_pending_files(files_to_download, paste_id=paste_tok)
            
                    # Chờ batch_end của paste_id này (không dùng event chung).
                    succeeded = False
                    wait_start = time.time()
                    last_hb = wait_start
                    my_done = (getattr(self, "_paste_done", None) or {}).get(paste_tok) or self.transfer_done_event
                    while True:
                        if paste_tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
                            print(f"[Clipboard] Dung cho tai file: paste_id={paste_tok} da Huy.")
                            break
                        if not getattr(self, "_allow_file_xfer", False) and paste_tok not in (getattr(self, "_xfer_dest_by_paste_id", None) or {}):
                            # Disarm toàn cục — chỉ dừng nếu job này cũng bị abort.
                            if paste_tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
                                break
                        if my_done.is_set():
                            if paste_tok not in (getattr(self, "_cancelled_paste_ids", None) or set()):
                                succeeded = True
                            break
                        now = time.time()
                        if now - last_hb >= 60.0:
                            last_hb = now
                            rec = 0
                            tot = 0
                            for j in (getattr(self, "_xfer_jobs", None) or {}).values():
                                try:
                                    if int(j.get("paste_id") or 0) == int(paste_tok):
                                        rec = int(j.get("received") or 0)
                                        tot = int(j.get("total") or 0)
                                        break
                                except Exception:
                                    pass
                            print(f"[Clipboard] Dang cho tai xong paste_id={paste_tok} ({rec}/{tot} bytes, {int(now - wait_start)}s) — dialog van mo.")
                        time.sleep(0.02)

                    job_paths = list((getattr(self, "_paste_result_paths", None) or {}).pop(paste_tok, None) or [])
                    if not job_paths:
                        # Fallback: job còn trong map hoặc batch_paths cũ.
                        for j in (getattr(self, "_xfer_jobs", None) or {}).values():
                            try:
                                if int(j.get("paste_id") or 0) == int(paste_tok):
                                    job_paths = list(j.get("paths") or [])
                                    break
                            except Exception:
                                pass
                    if succeeded and job_paths:
                        meta = list(files_to_download or [])
                        if not meta:
                            meta = list(getattr(self, "_reoffer_files", None) or pending_files or [])
                        why = []
                        if not _paths_match_expected_sizes(job_paths, meta, detail=why):
                            print("[Clipboard] File chua du dung luong / thieu metadata — khong dan. " + "; ".join(why))
                            log_debug("[render_format] File chưa đủ dung lượng / thiếu metadata — không dán.")
                            succeeded = False
                    if succeeded and job_paths:
                        print(f"[Clipboard] Tải thành công {len(job_paths)} file paste_id={paste_tok}")
                        log_debug(f"[render_format] Tải thành công {len(job_paths)} file.")
                
                        dest_now = dest_dir
                        if not dest_now:
                            dest_now = (getattr(self, "_xfer_dest_by_paste_id", None) or {}).get(paste_tok)
                        clip_trace(
                            f"[ClientPasteFinish] relocate decide paste_id={paste_tok} "
                            f"frozen_dest={dest_dir!r} map_dest={dest_now!r} "
                            f"paths={list(job_paths)[:6]}"
                        )
                        staging_need = dest_now and os.path.isdir(dest_now) and any(
                            _path_in_xfer_staging(p) or _is_transfer_staging_dir(os.path.dirname(p) if p else "")
                            for p in job_paths
                        )
                        if staging_need:
                            fin_id = int(paste_tok or 0)
                            need_copy = any(not _same_volume(p, dest_now) for p in job_paths)
                            with _file_io_lock:
                                if need_copy:
                                    self.begin_dialog_finalize(
                                        sum(_path_byte_size(p) for p in job_paths),
                                        job_id=fin_id or None,
                                    )
                                orig_paths = list(job_paths)
                                relocated, moved_all = _relocate_transfer_files_unlocked(
                                    job_paths, dest_now,
                                    on_progress=lambda n, j=fin_id: self.add_dialog_finalize(n, j or None),
                                    should_stop=lambda: paste_tok in (getattr(self, "_cancelled_paste_ids", None) or set()),
                                    replace_keys=set(
                                        os.path.normcase(os.path.abspath(p))
                                        for p in (files_to_replace or [])
                                        if p
                                    ) | set(
                                        os.path.normcase(os.path.abspath(os.path.join(dest_now, n)))
                                        for n in (replace_names or [])
                                        if n and dest_now
                                    ),
                                )
                                try:
                                    _purge_rdxfer_staging(dest_dir=dest_now, extra_paths=orig_paths + list(relocated or []))
                                    def _late(d=dest_now, xp=list(orig_paths) + list(relocated or [])):
                                        try:
                                            _purge_rdxfer_staging(dest_dir=d, extra_paths=xp)
                                        except Exception:
                                            pass
                                    threading.Timer(0.8, _late).start()
                                    threading.Timer(2.5, _late).start()
                                except Exception:
                                    pass
                            job_paths = relocated
                            clip_trace(f"[ClientPasteFinish] relocated moved_all={moved_all} → {list(relocated or [])[:8]}")
                            if paste_tok in (getattr(self, "_cancelled_paste_ids", None) or set()):
                                self._cleanup_partial_incoming()
                                succeeded = False
                            elif moved_all:
                                log_debug(f"[render_format] Đã chuyển file từ thư mục tạm sang: {dest_now}")
                        elif not dest_now:
                            clip_trace("[ClientPasteFinish] NO DEST — files stay in staging")
                        if succeeded:
                            # Giữ offer trên clipboard đến khi host copy bộ file mới.
                            keep = []
                            for f in (getattr(self, "_reoffer_files", None) or pending_files or []):
                                keep.append(dict(f) if isinstance(f, dict) else f)
                            if keep:
                                self._reoffer_files = keep
                                self.pending_remote_files = list(keep)
                                self._expect_repaste_until = time.time() + 86400.0
                                self._rearm_delayed_after_render = True
                                self.dummy_h_active = True
                                self._hdrop_materialized = True
                                local_map = dict(getattr(self, "_repaste_local_by_name", None) or {})
                                for p in (job_paths or []):
                                    if not p:
                                        continue
                                    try:
                                        if os.path.exists(p):
                                            base = os.path.basename(p.rstrip("\\/"))
                                            if base:
                                                local_map[os.path.normcase(base)] = os.path.abspath(p)
                                    except Exception:
                                        pass
                                self._repaste_local_by_name = local_map
                            else:
                                self._reoffer_files = None
                                self.pending_remote_files = []
                                self.dummy_h_active = False
                            self._recent_direct_paste = (
                                time.time(),
                                {os.path.normcase(os.path.abspath(p)) for p in job_paths if p}
                            )
                            placed = list(job_paths or [])
                            if dest_now:
                                placed.append(dest_now)
                            _notify_explorer_paths_changed(placed)
                            print(f"[Clipboard] Đã đặt file vào {dest_now} (Explorer refresh).")
                            clip_trace(
                                f"[ClientPasteFinish] DONE placed_in={dest_now} "
                                f"paths={placed[:8]} keep_offer={len(keep)}"
                            )
                            self.complete_dialog(job_id=paste_tok)
                            self.close_dialog(job_id=paste_tok, reason="render_format xong")
                            self._clear_paste_gesture_flags(1.0)
                            if keep:
                                clip_trace(f"[ClientPasteFinish] rearm delayed for repaste n={len(keep)}")
                                self._schedule_delayed_rearm(0.6)
                            else:
                                self._schedule_delayed_rearm(0.5)
                    if not succeeded:
                        print(f"[Clipboard] Dong dialog paste_id={paste_tok}: that bai/huy")
                        log_debug(f"[render_format] Tải file thất bại. succeeded={succeeded}")
                        clip_trace(f"[ClientPasteFinish] FAIL paste_id={paste_tok} succeeded={succeeded}")
                        reoffer = list(
                            getattr(self, "_reoffer_files", None)
                            or pending_files
                            or self.pending_remote_files
                            or []
                        )
                        if reoffer:
                            self.pending_remote_files = reoffer
                            self._reoffer_files = reoffer
                            self._rearm_delayed_after_render = True
                            self._expect_repaste_until = time.time() + 86400.0
                            self._clear_paste_gesture_flags(0.8)
                            self._schedule_delayed_rearm(0.5)
                        else:
                            self._clear_paste_gesture_flags(0.5)
                        self.close_dialog(job_id=paste_tok, reason="render_format that bai/huy")
                finally:
                    try:
                        (getattr(self, "_paste_done", None) or {}).pop(paste_tok, None)
                    except Exception:
                        pass
                    try:
                        (getattr(self, "_xfer_dest_by_paste_id", None) or {}).pop(paste_tok, None)
                    except Exception:
                        pass
                    try:
                        (getattr(self, "_xfer_replace_keys_by_paste", None) or {}).pop(paste_tok, None)
                    except Exception:
                        pass
                    still = bool(getattr(self, "_xfer_jobs", None)) or any(
                        d for d in (getattr(self, "xfer_dialogs", None) or {}).values() if d
                    ) or any(
                        not e.is_set() for e in (getattr(self, "_paste_done", None) or {}).values()
                    )
                    self._last_paste_finish_time = time.time()
                    if not still:
                        self.transfer_in_progress = False
                        self._unlock_paste_dest()
                    self.ignore_destroy_clipboard = False
                    try:
                        self._lmb_hit_context_menu = False
                        self._lmb_menu_item_kind = ""
                        self._rmb_cursor_pos = None
                    except Exception:
                        pass
                    clip_trace(f"[ClientPasteFinish] END paste_id={paste_tok} still_xfer={still}")
                    
            threading.Thread(target=background_download, daemon=True, name="ClientPasteFinish").start()
            # Cho phép Paste song song ngay — không giữ is_rendering đến hết tải.
            self.is_rendering = False
            return
        except Exception as e:
            log_debug(f"[render_format] Lỗi khi xử lý render format: {e}")
            empty_hdrop = create_hdrop_data([])
            if empty_hdrop:
                self.ignore_destroy_clipboard = True
                res = fn_SetClipboardData(15, empty_hdrop)
                if not res: fn_GlobalFree(empty_hdrop)
            self.close_dialog(reason="render_format exception")
            if self.app and getattr(self.app, 'is_headless', False):
                self._send_progress_signal("CANCEL", "")
                self._close_transfer_pipe()
            self.transfer_in_progress = False
            self.is_rendering = False
            self._unlock_paste_dest()
        finally:
            self.ignore_destroy_clipboard = False

    def request_pending_files(self, files=None, paste_id=None):
        files_req = list(files) if files else list(self.pending_remote_files or [])
        if not files_req or not self.sock:
            return
        if not getattr(self, "_allow_file_xfer", False):
            print("[FileTransfer] Bo request_pending_files (allow_file_xfer=False).")
            return
        try:
            pid = int(paste_id) if paste_id is not None else int(getattr(self, "_clipboard_paste_id", 0) or 0)
        except Exception:
            pid = 0
        if pid in (getattr(self, "_cancelled_paste_ids", None) or set()):
            print(f"[FileTransfer] Bo request_pending_files paste_id={pid} (blacklist Huy).")
            return
        send_msg(self.sock, json.dumps({
            "type": "request_files",
            "files": files_req,
            "paste_id": pid,
        }).encode('utf-8'))

    def _enqueue_file_offer(self, files, offer_id=None):
        """Hàng đợi copy file (RAM). Áp từng offer; nếu xếp hàng thì lấy cái mới nhất."""
        if not files:
            return
        snap = []
        for f in files:
            snap.append(dict(f) if isinstance(f, dict) else f)
        oid = 0
        try:
            oid = int(offer_id or 0)
        except Exception:
            oid = 0
        with self._clip_offer_lock:
            if oid <= 0:
                self._clip_offer_in = int(getattr(self, "_clip_offer_in", 0) or 0) + 1
                oid = self._clip_offer_in
            else:
                self._clip_offer_in = max(int(getattr(self, "_clip_offer_in", 0) or 0), oid)
            q = self._clip_offer_q
            last_fp = getattr(self, "_clip_offer_fp", None)
            fp = _file_offer_fp(snap)
            applied = int(getattr(self, "_clip_offer_applied", 0) or 0)
            if oid and oid <= applied and fp == last_fp:
                log_debug(f"[_enqueue_file_offer] Bỏ offer trùng {oid} (đã áp {applied}).")
                return
            if oid and oid <= applied and fp != last_fp:
                oid = applied + 1
                self._clip_offer_in = oid
                print(f"[Clipboard] Offer id cũ nhưng file mới — nhận copy mới oid={oid}")
            self._clip_offer_fp = fp
            q.append({"offer_id": oid, "files": snap})
            while len(q) > 24:
                q.pop(0)
        names = []
        for f in snap[:6]:
            if isinstance(f, dict):
                names.append(f.get("name") or os.path.basename(str(f.get("path") or "")))
        print(f"[Clipboard] Queue offer={oid} n={len(snap)} {names} (q={len(self._clip_offer_q)})")
        self._clip_offer_evt.set()

    def _clip_offer_loop(self):
        while True:
            self._clip_offer_evt.wait(timeout=1.0)
            self._clip_offer_evt.clear()
            while True:
                with self._clip_offer_lock:
                    q = self._clip_offer_q
                    if not q:
                        break
                    if len(q) == 1:
                        item = q.pop(0)
                    else:
                        # Copy dồn: bỏ offer giữa, áp file mới nhất.
                        item = q[-1]
                        q.clear()
                self._apply_file_offer(item)
                time.sleep(0.06)

    def _apply_file_offer(self, item):
        oid = int((item or {}).get("offer_id") or 0)
        files = list((item or {}).get("files") or [])
        if not files:
            return
        with self._clip_offer_lock:
            applied = int(getattr(self, "_clip_offer_applied", 0) or 0)
            fp = _file_offer_fp(files)
            last_fp = getattr(self, "_clip_offer_fp", None)
            if oid and oid < applied and fp == last_fp:
                return
            self._clip_offer_applied = max(applied, oid)
            self._clip_offer_fp = fp
        self.pending_remote_files = files
        self._reoffer_files = list(files)
        # Copy mới từ host → xóa cache paste local của offer cũ.
        if fp != last_fp:
            self._repaste_local_by_name = {}
        self.meta_arrival_time = time.time()
        self._allow_delayed = True
        self._force_delayed_setup = True
        self._expect_repaste_until = time.time() + 86400.0
        self._clip_seq_at_pending = get_clipboard_sequence_number()
        names = [f.get("name") if isinstance(f, dict) else str(f) for f in files[:8]]
        print(f"[Clipboard] Áp offer={oid} n={len(files)} {names}")
        log_debug(f"[_apply_file_offer] offer={oid} files={len(files)}")
        clip_trace(f"[apply_file_offer] offer={oid} n={len(files)} {names} "
                   f"cache={getattr(self,'cached_explorer_path',None)} "
                   f"last={getattr(self,'_last_good_explorer_path',None)}")

        if self.app and getattr(self.app, "is_headless", False):
            # Đừng đổi target_save_dir / clear done khi đang tải paste khác.
            if not getattr(self, "_xfer_jobs", None):
                self.target_save_dir = HEADLESS_TRANSFER_DIR
                self.batch_paths = []
                self.transfer_done_event.clear()
            total_size = sum((f.get("size", 0) if isinstance(f, dict) else 0) for f in files)
            item_kind, display_name = _copy_batch_kind_and_name(files, _("Tệp tin"))
            msg_dict = {
                "display_name": display_name,
                "item_kind": item_kind,
                "total_size": total_size,
                "files": files,
                "offer_id": oid,
            }
            log_overwrite_conflict(
                f"HOST_HEADLESS SEND PENDING offer={oid} display={display_name!r} "
                f"size={total_size} n={len(files)} names={names} → agent pipe"
            )
            self._send_to_pipe("PENDING", json.dumps(msg_dict))
            return

        log_overwrite_conflict(
            f"{'CLIENT_VIEWER' if getattr(self, 'pygame_hwnd', None) else 'HOST_GUI'} "
            f"apply offer={oid} n={len(files)} names={names} (delayed CF_HDROP, not agent PENDING)"
        )
        temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
        self.target_save_dir = temp_dir
        self.setup_delayed_rendering()
        if not clipboard_has_file_formats():
            log_debug("[_apply_file_offer] CF_HDROP chưa có sau setup — thử lại.")
            self._force_delayed_setup = True
            self.setup_delayed_rendering()

    def _paste_dest_for_job(self, job):
        """Chỉ lấy dest đã gắn vào job / paste_id — không đọc cached_explorer_path sống."""
        dest = None
        if job:
            dest = job.get("paste_dest")
        if not dest:
            try:
                pid = int((job or {}).get("paste_id") or 0)
            except Exception:
                pid = 0
            if pid:
                dest = (getattr(self, "_xfer_dest_by_paste_id", None) or {}).get(pid)
        if not dest:
            # Chỉ dùng _paste_dest_dir khi đang frozen (đang paste), không dùng path cũ lệch.
            if getattr(self, "_paste_dest_frozen", False):
                dest = getattr(self, "_paste_dest_dir", None)
        if dest and os.path.isdir(dest) and not _is_transfer_staging_dir(dest):
            return dest
        return None

    def _ensure_dest_tree(self, dest, rel_name):
        if not dest or not rel_name:
            return
        rel = str(rel_name).replace("\\", "/").strip("/")
        top = rel.split("/")[0] if "/" in rel else None
        if top:
            try:
                os.makedirs(os.path.join(dest, top), exist_ok=True)
            except Exception:
                pass

    def _finalize_incoming_file(self, transfer, job, filename):
        """close + kiểm size + đưa file ra thư mục đích. Chạy ngoài ClipPkt (tránh kẹt AV/close 4GB)."""
        path = transfer.get("path")
        expected = transfer.get("expected_size")
        written = int(transfer.get("written") or 0)
        handle = transfer.get("handle")
        if handle is not None:
            try:
                handle.flush()
            except Exception:
                pass
            try:
                handle.close()
            except Exception as e:
                print(f"[FileTransfer] Lỗi đóng handle {filename}: {e}")
        actual = -1
        if path:
            try:
                actual = os.path.getsize(path) if os.path.exists(path) else -1
            except Exception:
                actual = -1
        if expected is not None and actual != expected and written != int(expected or 0):
            print(f"[FileTransfer] Sai kich thuoc {filename}: disk={actual} written={written} expected={expected}, xoa file.")
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
            return
        dest = self._paste_dest_for_job(job)
        final_path = path
        if dest and path and os.path.isfile(path):
            try:
                pid = 0
                try:
                    pid = int((job or {}).get("paste_id") or 0)
                except Exception:
                    pid = 0
                rk = (getattr(self, "_xfer_replace_keys_by_paste", None) or {}).get(pid) or set()
                final_path = _promote_completed_xfer_file(path, dest, filename, replace_keys=rk)
                print(f"[FileTransfer] Da chép {filename} -> {final_path}")
                clip_trace(f"[finalize] promote {filename} → {final_path} (job_dest={dest})")
            except Exception as e:
                print(f"[FileTransfer] Promote {filename} loi: {e}")
                clip_trace(f"[finalize] promote FAIL {filename}: {e}")
                final_path = path
        else:
            clip_trace(f"[finalize] NO promote {filename} dest={dest!r} path={path!r} "
                       f"job_paste_dest={(job or {}).get('paste_dest')!r} "
                       f"frozen={getattr(self,'_paste_dest_frozen',False)} "
                       f"live_cache={getattr(self,'cached_explorer_path',None)!r}")
        xid = transfer.get("xfer_id")
        job = job or (getattr(self, "_xfer_jobs", None) or {}).get(xid)
        paths = job["paths"] if job is not None else self.batch_paths
        top_level_name = str(filename or "").replace("\\", "/").split("/")[0]
        if dest:
            top_level_path = os.path.join(dest, top_level_name)
        else:
            base_save = (job or {}).get("save_dir") or self.target_save_dir
            top_level_path = os.path.join(_xfer_staging_dir(base_save, xid), top_level_name)
        if top_level_path not in paths:
            paths.append(top_level_path)
        log_debug(f"[file_end] Đã xử lý xong file: {filename} dest={final_path}")

    def _complete_batch_after_files(self, packet):
        xid = packet.get("xfer_id")
        jobs = getattr(self, "_xfer_jobs", None) or {}
        job = jobs.get(xid) if xid is not None else None
        for ev in list((job or {}).get("finish_events") or []):
            while not ev.wait(0.4):
                if (xid is not None and xid in (getattr(self, "_aborted_xfer_ids", None) or set())):
                    return
                pid = (job or {}).get("paste_id")
                try:
                    pid = int(pid or 0)
                except Exception:
                    pid = 0
                if pid and pid in (getattr(self, "_cancelled_paste_ids", None) or set()):
                    return
        self._finish_batch_end(packet)

    def _finish_batch_end(self, packet):
        xid = packet.get("xfer_id")
        jobs = getattr(self, "_xfer_jobs", None) or {}
        job = jobs.get(xid) if xid is not None else None
        paste_id = 0
        try:
            paste_id = int((job or {}).get("paste_id") or packet.get("paste_id") or 0)
        except Exception:
            paste_id = 0
        aborted = getattr(self, "_aborted_xfer_ids", None) or set()
        if (xid is not None and xid in aborted) or (paste_id and paste_id in (getattr(self, "_cancelled_paste_ids", None) or set())):
            log_debug("[batch_end] Đã hủy — bỏ qua FILES.")
            self.close_dialog(job_id=paste_id or xid, reason="batch_end da huy")
            jobs.pop(xid, None)
            if not jobs:
                self.transfer_done_event.set()
                self.transfer_in_progress = False
            if paste_id:
                ev = (getattr(self, "_paste_done", None) or {}).get(paste_id)
                if ev is not None:
                    ev.set()
            return
        ok_paths = list((job or {}).get("paths") or getattr(self, "batch_paths", None) or [])
        if paste_id:
            pr = getattr(self, "_paste_result_paths", None)
            if pr is None:
                self._paste_result_paths = {}
                pr = self._paste_result_paths
            pr[paste_id] = list(ok_paths)
            ev = (getattr(self, "_paste_done", None) or {}).get(paste_id)
            if ev is not None:
                ev.set()
        # Chỉ đóng dialog của paste này — không destroy hết stack.
        self.close_dialog(job_id=paste_id or xid, reason="batch_end xong")
        jobs.pop(xid, None)
        if not jobs:
            self.transfer_done_event.set()
            self.transfer_in_progress = False
        try:
            dest = self._paste_dest_for_job(job)
            notify = list(ok_paths)
            if dest:
                notify.append(dest)
            _notify_explorer_paths_changed(notify)
        except Exception:
            pass
        try:
            import core.viewer
            if core.viewer.file_manager_callback:
                core.viewer.file_manager_callback({"type": "trigger_local_refresh"})
        except: pass
        print(f"[FileTransfer] batch_end xfer_id={xid} paste_id={paste_id} n={len(ok_paths)}")
        log_debug(f"[batch_end] Đã nhận xong xfer_id={xid} paste_id={paste_id} n={len(ok_paths)}")
        try:
            name = (job or {}).get("display_name") or self.batch_display_name
            total = (job or {}).get("total") or self.batch_total_size
            log_activity(_("Nhận file: ") + str(name) + " - " + str(total) + _(" byte - Thành công"))
        except: pass
        try:
            if self.sock:
                send_msg(self.sock, json.dumps({"type": "upload_batch_ack", "xfer_id": xid}).encode('utf-8'))
        except Exception:
            pass
        if self.app and getattr(self.app, 'is_headless', False):
            log_overwrite_conflict(
                f"HOST_HEADLESS batch_end paste_id={paste_id} xfer_id={xid} "
                f"n={len(ok_paths)} dest={(job or {}).get('paste_dest')!r}"
            )
            meta = list((job or {}).get("expected_files") or [])
            why = []
            if meta and not _paths_match_expected_sizes(ok_paths, meta, detail=why):
                print("[FileTransfer] batch_end: size khong khop snapshot paste, khong gui FILES. " + "; ".join(why))
                log_debug("[batch_end] HEADLESS: size không khớp snapshot paste, không gửi FILES.")
                ok_paths = []
            # Không relocate vào Explorer dest tại đây. Agent đã hỏi Replace
            # và sẽ relocate với replace_keys. Ghi dest ở đây = đè file trước khi hỏi.
            dest = None
            log_overwrite_conflict(
                f"HOST_HEADLESS batch_end keep staging n={len(ok_paths)} "
                f"(agent relocate sau conflict)"
            )
            try:
                stg_base = (job or {}).get("save_dir") or getattr(self, "target_save_dir", None)
                paths_snap = list((job or {}).get("paths") or []) + list(ok_paths or [])
                still_staging = any(_path_in_xfer_staging(p) for p in (ok_paths or []) if p)
                if still_staging:
                    # Còn file trong .rdxfer_* chờ agent relocate (sau Replace) — không purge.
                    log_debug("[batch_end] Giữ staging (cho agent relocate / conflict).")
                else:
                    _purge_rdxfer_staging(
                        dest_dir=dest or stg_base,
                        xfer_id=xid,
                        extra_paths=paths_snap,
                    )
                    _purge_rdxfer_staging(dest_dir=stg_base, xfer_id=xid, extra_paths=paths_snap)
                    def _late_purge(d=dest or stg_base, sb=stg_base, x=xid, xp=paths_snap):
                        try:
                            _purge_rdxfer_staging(dest_dir=d, xfer_id=x, extra_paths=xp)
                            _purge_rdxfer_staging(dest_dir=sb, xfer_id=x, extra_paths=xp)
                        except Exception:
                            pass
                    threading.Timer(0.8, _late_purge).start()
                    threading.Timer(2.5, _late_purge).start()
                _schedule_scrub_probe(dest)
            except Exception as e:
                log_debug(f"[batch_end] purge staging: {e}")
            if ok_paths:
                files_str = str(paste_id) + "|" + "|".join(ok_paths)
                self._send_progress_signal("FILES", files_str)
                if hasattr(self, 'lock'):
                    with self.lock:
                        self.last_current_files = [os.path.abspath(p) for p in ok_paths if os.path.exists(p)]
                        self.last_files_time = time.time()
                # Đã xong — đừng để cleanup sau này xóa nhầm path đích.
                self._partial_output_paths = []
            else:
                self._send_progress_signal("CANCEL", str(paste_id) if paste_id else "")
            self._close_transfer_pipe()
        jobs.pop(xid, None)
        if not jobs:
            self.transfer_in_progress = False
            self._paste_dest_dir = None
            self._paste_dest_frozen = False
            if paste_id:
                try:
                    (getattr(self, "_xfer_dest_by_paste_id", None) or {}).pop(paste_id, None)
                except Exception:
                    pass
            if self.app and getattr(self.app, "is_headless", False):
                self.target_save_dir = HEADLESS_TRANSFER_DIR

