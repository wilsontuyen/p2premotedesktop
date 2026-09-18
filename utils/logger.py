import os
import time
import sys

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_log_filepath(filename):
    temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except:
        pass
    return os.path.join(temp_dir, filename)

def log_file_transfer(filename, file_size):
    try:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.2f} KB"
        elif file_size < 1024 * 1024 * 1024:
            size_str = f"{file_size / (1024 * 1024):.2f} MB"
        else:
            size_str = f"{file_size / (1024 * 1024 * 1024):.2f} GB"
            
        log_line = f"{timestamp} File: {filename} | Size: {size_str}\n"
        filepath = get_log_filepath("log.txt")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"[Log] Lỗi ghi log.txt: {e}")

def log_debug(msg):
    try:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        filepath = get_log_filepath(f"clipboard_debug_{os.getpid()}.log")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} [PID {os.getpid()}] {msg}\n")
    except:
        pass


_clip_trace_last = {}  # key -> (monotonic_ts, count_suppressed)


def clip_trace(msg, throttle_s=0.0, key=None):
    """Ghi clipboard_agent.log (TEMP + LOCALAPPDATA). throttle_s>0 gộp log trùng."""
    try:
        k = key
        if k is None and throttle_s > 0:
            # Gộp theo prefix tới hết token thứ 2: "[render_format] → BACKGROUND..."
            parts = (msg or "").split(" ", 2)
            k = " ".join(parts[:2]) if len(parts) >= 2 else (msg or "")[:64]
        if throttle_s > 0 and k:
            now = time.monotonic()
            prev = _clip_trace_last.get(k)
            if prev and (now - prev[0]) < throttle_s:
                _clip_trace_last[k] = (prev[0], prev[1] + 1)
                return False
            suppressed = prev[1] if prev else 0
            _clip_trace_last[k] = (now, 0)
            if suppressed:
                msg = f"{msg} (+{suppressed} suppressed)"
    except Exception:
        pass

    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [PID {os.getpid()}] {msg}\n"
    # Chỉ TEMP + LocalAppData — tránh ghi 4 bản (Program Files) làm phình + chậm.
    paths = []
    try:
        paths.append(get_log_filepath("clipboard_agent.log"))
    except Exception:
        pass
    try:
        lad = os.environ.get("LOCALAPPDATA", "")
        if lad:
            paths.append(os.path.join(lad, "Easy Remote Desktop", "clipboard_agent.log"))
    except Exception:
        pass
    written = False
    for filepath in paths:
        if not filepath:
            continue
        try:
            parent = os.path.dirname(filepath)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(line)
            written = True
        except Exception:
            continue
    try:
        print(f"[ClipTrace] {msg}")
    except Exception:
        pass
    return written


def log_overwrite_conflict(msg, tag="OW"):
    """Log riêng overwrite dialog / client→host paste.

    File (máy HOST khi paste client→host — Agent + headless):
      %TEMP%\\RemoteDesktopTransfers\\overwrite_conflict.log
      %LOCALAPPDATA%\\Easy Remote Desktop\\overwrite_conflict.log
      %ProgramData%\\Easy Remote Desktop\\overwrite_conflict.log
    """
    try:
        import socket as _socket
        host = _socket.gethostname()
    except Exception:
        host = "?"
    line = (
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [PID {os.getpid()}] "
        f"[host={host}] [{tag}] {msg}\n"
    )
    paths = []
    try:
        paths.append(get_log_filepath("overwrite_conflict.log"))
    except Exception:
        pass
    try:
        lad = os.environ.get("LOCALAPPDATA", "")
        if lad:
            paths.append(os.path.join(lad, "Easy Remote Desktop", "overwrite_conflict.log"))
    except Exception:
        pass
    try:
        pd = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        if pd:
            paths.append(os.path.join(pd, "Easy Remote Desktop", "overwrite_conflict.log"))
    except Exception:
        pass
    # Cạnh exe (khi ghi được) — dễ tìm trên máy host.
    try:
        paths.append(os.path.join(app_dir, "overwrite_conflict.log"))
    except Exception:
        pass
    for filepath in paths:
        if not filepath:
            continue
        try:
            parent = os.path.dirname(filepath)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            continue
    try:
        print(f"[OW] {msg}")
    except Exception:
        pass
    try:
        log_debug(f"[OW] {msg}")
    except Exception:
        pass


def log_activity(msg):
    try:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        filepath = os.path.join(app_dir, "activity_log.txt")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} - {msg}\n")
    except Exception as e:
        print(f"[Log] Lỗi ghi activity_log.txt: {e}")

def _format_size_log(size_bytes):
    """Format dung lượng file cho log."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def log_file_activity(action, filename, file_size, source_dir="", dest_dir="", status="Thành công"):
    """
    Ghi log chi tiết cho hoạt động truyền/nhận file.
    Format: [ngày giờ] - action | File: filename | Size: dung_lượng | Nguồn: source_dir | Đích: dest_dir | Trạng thái: status
    """
    try:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        size_str = _format_size_log(file_size) if file_size else "N/A"
        source_str = source_dir if source_dir else "N/A"
        dest_str = dest_dir if dest_dir else "N/A"
        
        log_line = (
            f"{timestamp} - {action} | File: {filename} | "
            f"Size: {size_str} | Nguồn: {source_str} | "
            f"Đích: {dest_str} | Trạng thái: {status}\n"
        )
        
        filepath = os.path.join(app_dir, "activity_log.txt")
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"[Log] Lỗi ghi activity_log.txt: {e}")

