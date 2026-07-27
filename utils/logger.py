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

