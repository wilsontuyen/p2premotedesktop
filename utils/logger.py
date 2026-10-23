import os
import time
import sys

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_utf8_bom(filepath):
    """
    Đảm bảo file log bắt đầu bằng UTF-8 BOM (b'\xef\xbb\xbf').
    - Nếu file chưa có hoặc rỗng: ghi b'\xef\xbb\xbf'.
    - Nếu file đã có nội dung nhưng chưa có BOM: tự động chèn b'\xef\xbb\xbf' vào đầu file.
    Giúp Notepad và các trình xem log trên Windows luôn hiển thị tiếng Việt chuẩn 100%, không bị lỗi font.
    """
    try:
        parent = os.path.dirname(filepath)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            with open(filepath, "wb") as bf:
                bf.write(b"\xef\xbb\xbf")
        else:
            with open(filepath, "rb") as rf:
                header = rf.read(3)
            if header != b"\xef\xbb\xbf":
                with open(filepath, "rb") as rf:
                    content = rf.read()
                with open(filepath, "wb") as wf:
                    wf.write(b"\xef\xbb\xbf" + content)
    except Exception:
        pass

def safe_write_log_line(filepath, line, fallback_filename=None):
    """Ghi dòng log vào filepath với UTF-8 BOM, fallback sang TEMP nếu bị PermissionError."""
    try:
        ensure_utf8_bom(filepath)
        with open(filepath, "a", encoding="utf-8-sig") as f:
            f.write(line)
        return True
    except (PermissionError, OSError):
        if fallback_filename:
            try:
                fb_path = get_log_filepath(fallback_filename)
                ensure_utf8_bom(fb_path)
                with open(fb_path, "a", encoding="utf-8-sig") as f:
                    f.write(line)
                return True
            except Exception:
                pass
    except Exception:
        pass
    return False

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
        safe_write_log_line(filepath, log_line, "log.txt")
    except Exception as e:
        print(f"[Log] Lỗi ghi log.txt: {e}")

def log_debug(msg):
    try:
        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
        filename = f"clipboard_debug_{os.getpid()}.log"
        filepath = get_log_filepath(filename)
        safe_write_log_line(filepath, f"{timestamp} [PID {os.getpid()}] {msg}\n", filename)
    except:
        pass


_clip_trace_last = {}  # key -> (monotonic_ts, count_suppressed)


def clip_trace(msg, throttle_s=0.0, key=None):
    """Ghi clipboard_agent.log (TEMP + LOCALAPPDATA). throttle_s>0 gộp log trùng."""
    try:
        k = key
        if k is None and throttle_s > 0:
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
        if safe_write_log_line(filepath, line, "clipboard_agent.log"):
            written = True
    try:
        print(f"[ClipTrace] {msg}")
    except Exception:
        pass
    return written


def log_overwrite_conflict(msg, tag="OW"):
    """Log riêng overwrite dialog / client→host paste."""
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
    try:
        paths.append(os.path.join(app_dir, "overwrite_conflict.log"))
    except Exception:
        pass
    for filepath in paths:
        if not filepath:
            continue
        safe_write_log_line(filepath, line, "overwrite_conflict.log")
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
        safe_write_log_line(filepath, f"{timestamp} - {msg}\n", "activity_log.txt")
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
        safe_write_log_line(filepath, log_line, "activity_log.txt")
    except Exception as e:
        print(f"[Log] Lỗi ghi activity_log.txt: {e}")

