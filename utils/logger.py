import os
import time
import sys
import glob
import shutil

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_logs_dir():
    """
    Trả về đường dẫn thư mục Logs của ứng dụng.
    Ưu tiên 1: os.path.join(app_dir, "Logs")
    Fallback: os.path.join(os.environ.get("LOCALAPPDATA", ""), "Easy Remote Desktop", "Logs")
    Fallback cuối: os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "Easy Remote Desktop", "Logs")
    Tự động tạo thư mục và kiểm tra quyền ghi.
    """
    primary_dir = os.path.join(app_dir, "Logs")
    candidates = [primary_dir]
    lad = os.environ.get("LOCALAPPDATA", "")
    if lad:
        candidates.append(os.path.join(lad, "Easy Remote Desktop", "Logs"))
    pd = os.environ.get("PROGRAMDATA", "")
    if pd:
        candidates.append(os.path.join(pd, "Easy Remote Desktop", "Logs"))
    temp = os.environ.get("TEMP", os.path.expanduser("~"))
    candidates.append(os.path.join(temp, "Easy Remote Desktop", "Logs"))

    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            test_f = os.path.join(d, ".perm_test")
            try:
                with open(test_f, "w", encoding="utf-8") as tf:
                    tf.write("ok")
                try:
                    os.remove(test_f)
                except Exception:
                    pass
                return d
            except (PermissionError, OSError):
                continue
        except Exception:
            continue
    return primary_dir


def get_log_filepath(filename):
    """Trả về đường dẫn tuyệt đối của file log nằm trong thư mục Logs của app."""
    return os.path.join(get_logs_dir(), filename)


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
    """Ghi dòng log vào filepath với UTF-8 BOM, fallback sang thư mục Logs an toàn nếu gặp lỗi."""
    try:
        ensure_utf8_bom(filepath)
        with open(filepath, "a", encoding="utf-8-sig") as f:
            f.write(line)
        return True
    except (PermissionError, OSError):
        if fallback_filename:
            try:
                fb_path = get_log_filepath(fallback_filename)
                if os.path.abspath(fb_path) != os.path.abspath(filepath):
                    ensure_utf8_bom(fb_path)
                    with open(fb_path, "a", encoding="utf-8-sig") as f:
                        f.write(line)
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def migrate_legacy_logs():
    """
    Tự động di chuyển các file log nằm rải rác ở thư mục gốc app_dir hoặc TEMP cũ
    vào thư mục Logs tập trung để thư mục app luôn gọn gàng và dễ tìm kiếm.
    """
    try:
        target_dir = get_logs_dir()
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        legacy_names = [
            "gui.log", "agent.log", "service.log", "clipboard_agent.log",
            "overwrite_conflict.log", "broker.log", "activity.log", "activity_log.txt",
            "log.txt", "crash.log", "early_crash.log", "transfer.log",
            "client_error.log", "host_error.log", "task_creation.log",
            "task_run.log", "clipboard_debug.log", "viewer.log",
            "system_crash.log", "native_fault.log", "client_crash.log",
            "domain_debug.log", "agent_crash.txt", "mac_crash.log"
        ]

        # 1. Quét app_dir
        for fname in legacy_names:
            src = os.path.join(app_dir, fname)
            dst = os.path.join(target_dir, fname)
            if os.path.exists(src) and os.path.abspath(src) != os.path.abspath(dst):
                try:
                    if not os.path.exists(dst):
                        shutil.move(src, dst)
                    else:
                        # Append nội dung file cũ vào file mới trong Logs
                        with open(src, "rb") as sf:
                            old_data = sf.read()
                        with open(dst, "ab") as df:
                            df.write(old_data)
                        os.remove(src)
                except Exception:
                    pass

        # Di chuyển / gộp activity_log.txt cũ thành activity.log trong target_dir
        old_act = os.path.join(target_dir, "activity_log.txt")
        new_act = os.path.join(target_dir, "activity.log")
        if os.path.exists(old_act):
            try:
                if not os.path.exists(new_act):
                    shutil.move(old_act, new_act)
                else:
                    with open(old_act, "rb") as sf:
                        old_data = sf.read()
                    with open(new_act, "ab") as df:
                        df.write(old_data)
                    os.remove(old_act)
            except Exception:
                pass

        # Quét các file clipboard_debug_*.log ở app_dir
        for src in glob.glob(os.path.join(app_dir, "clipboard_debug_*.log")):
            dst = os.path.join(target_dir, os.path.basename(src))
            if os.path.abspath(src) != os.path.abspath(dst):
                try:
                    shutil.move(src, dst)
                except Exception:
                    pass

        # 2. Quét TEMP cũ (RemoteDesktopTransfers)
        old_temp = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
        if os.path.exists(old_temp) and os.path.isdir(old_temp):
            for src in glob.glob(os.path.join(old_temp, "*.log")) + glob.glob(os.path.join(old_temp, "*.txt")):
                dst = os.path.join(target_dir, os.path.basename(src))
                if os.path.abspath(src) != os.path.abspath(dst):
                    try:
                        shutil.move(src, dst)
                    except Exception:
                        pass
    except Exception:
        pass


def cleanup_old_debug_logs(max_keep=10):
    """
    Hàm tiện ích dọn dẹp thủ công các file clipboard_debug_*.log và file tạm rác tmp*.tmp.
    Chỉ chạy khi được gọi chủ động (không tự động xóa trong runtime để bảo toàn log xem lỗi).
    """
    try:
        candidate_dirs = set()
        active_logs = get_logs_dir()
        if active_logs:
            candidate_dirs.add(os.path.abspath(active_logs))
        
        primary_dir = os.path.join(app_dir, "Logs")
        if os.path.exists(primary_dir):
            candidate_dirs.add(os.path.abspath(primary_dir))
            
        lad = os.environ.get("LOCALAPPDATA", "")
        if lad:
            user_logs = os.path.join(lad, "Easy Remote Desktop", "Logs")
            if os.path.exists(user_logs):
                candidate_dirs.add(os.path.abspath(user_logs))

        current_pid = os.getpid()
        current_pid_file = f"clipboard_debug_{current_pid}.log"

        for d in candidate_dirs:
            if not os.path.exists(d) or not os.path.isdir(d):
                continue
            
            # 1. Dọn dẹp clipboard_debug_*.log
            debug_files = glob.glob(os.path.join(d, "clipboard_debug_*.log"))
            if len(debug_files) > max_keep:
                debug_files.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0)
                files_to_remove = debug_files[:-max_keep]
                for fpath in files_to_remove:
                    if os.path.basename(fpath) == current_pid_file:
                        continue
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
            
            # 2. Dọn dẹp file tạm tmp*.tmp cũ (nếu có)
            for tmp_file in glob.glob(os.path.join(d, "tmp*.tmp")):
                try:
                    if (time.time() - os.path.getmtime(tmp_file)) > 1800:
                        os.remove(tmp_file)
                except Exception:
                    pass
    except Exception:
        pass


def clear_temp_files():
    """
    Xóa toàn bộ các tệp tạm (*.tmp) trong thư mục Logs.
    Trả về số lượng tệp tạm đã xóa.
    """
    cleaned_count = 0
    try:
        candidate_dirs = set()
        active_logs = get_logs_dir()
        if active_logs:
            candidate_dirs.add(os.path.abspath(active_logs))
        
        primary_dir = os.path.join(app_dir, "Logs")
        if os.path.exists(primary_dir):
            candidate_dirs.add(os.path.abspath(primary_dir))
            
        lad = os.environ.get("LOCALAPPDATA", "")
        if lad:
            user_logs = os.path.join(lad, "Easy Remote Desktop", "Logs")
            if os.path.exists(user_logs):
                candidate_dirs.add(os.path.abspath(user_logs))

        for d in candidate_dirs:
            if not os.path.exists(d) or not os.path.isdir(d):
                continue

            for tmp_file in glob.glob(os.path.join(d, "*.tmp")):
                try:
                    os.remove(tmp_file)
                    cleaned_count += 1
                except Exception:
                    pass
    except Exception:
        pass
    return cleaned_count


def clear_all_logs():
    """
    Dọn dẹp và làm sạch toàn bộ các file nhật ký (*.log và *.txt) trong thư mục Logs theo yêu cầu người dùng:
    - Xóa các file *.log (hoặc làm rỗng về 0 bytes nếu file đang được tiến trình mở)
    - Xóa các file *.txt trong Logs (log.txt...)
    Trả về số lượng file nhật ký đã được dọn dẹp.
    """
    cleaned_count = 0
    try:
        candidate_dirs = set()
        active_logs = get_logs_dir()
        if active_logs:
            candidate_dirs.add(os.path.abspath(active_logs))
        
        primary_dir = os.path.join(app_dir, "Logs")
        if os.path.exists(primary_dir):
            candidate_dirs.add(os.path.abspath(primary_dir))
            
        lad = os.environ.get("LOCALAPPDATA", "")
        if lad:
            user_logs = os.path.join(lad, "Easy Remote Desktop", "Logs")
            if os.path.exists(user_logs):
                candidate_dirs.add(os.path.abspath(user_logs))

        current_pid = os.getpid()
        current_pid_file = f"clipboard_debug_{current_pid}.log"

        for d in candidate_dirs:
            if not os.path.exists(d) or not os.path.isdir(d):
                continue

            # 1. Xử lý các file *.log
            for fpath in glob.glob(os.path.join(d, "*.log")):
                try:
                    if os.path.basename(fpath) == current_pid_file:
                        ensure_utf8_bom(fpath)
                        with open(fpath, "w", encoding="utf-8-sig") as f:
                            f.write("")
                    else:
                        try:
                            os.remove(fpath)
                        except (PermissionError, OSError):
                            ensure_utf8_bom(fpath)
                            with open(fpath, "w", encoding="utf-8-sig") as f:
                                f.write("")
                    cleaned_count += 1
                except Exception:
                    pass

            # 2. Xử lý các file *.txt (log.txt, ...)
            for fpath in glob.glob(os.path.join(d, "*.txt")):
                try:
                    try:
                        os.remove(fpath)
                    except (PermissionError, OSError):
                        ensure_utf8_bom(fpath)
                        with open(fpath, "w", encoding="utf-8-sig") as f:
                            f.write("")
                    cleaned_count += 1
                except Exception:
                    pass
    except Exception:
        pass
    return cleaned_count


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
    """Ghi log vào Logs/clipboard_agent.log. throttle_s>0 gộp log trùng."""
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
    filepath = get_log_filepath("clipboard_agent.log")
    written = safe_write_log_line(filepath, line, "clipboard_agent.log")
    try:
        print(f"[ClipTrace] {msg}")
    except Exception:
        pass
    return written


def log_overwrite_conflict(msg, tag="OW"):
    """Ghi log riêng overwrite dialog / client→host paste vào Logs/overwrite_conflict.log."""
    try:
        import socket as _socket
        host = _socket.gethostname()
    except Exception:
        host = "?"
    line = (
        f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [PID {os.getpid()}] "
        f"[host={host}] [{tag}] {msg}\n"
    )
    filepath = get_log_filepath("overwrite_conflict.log")
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
        filepath = get_log_filepath("activity.log")
        safe_write_log_line(filepath, f"{timestamp} - {msg}\n", "activity.log")
    except Exception as e:
        print(f"[Log] Lỗi ghi activity.log: {e}")


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
    Ghi log chi tiết cho hoạt động truyền/nhận file vào Logs/activity.log.
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
        
        filepath = get_log_filepath("activity.log")
        safe_write_log_line(filepath, log_line, "activity.log")
    except Exception as e:
        print(f"[Log] Lỗi ghi activity.log: {e}")


# ==============================================================================
# HỆ THỐNG GHI LOG LỖI & CRASH MỨC HỆ THỐNG (SYSTEM & NATIVE CRASH LOGGING)
# ==============================================================================

_KNOWN_WIN_EXIT_CODES = {
    0x00000000: ("NORMAL_EXIT", "Thoát bình thường (OK)"),
    0x00000001: ("PYTHON_ERROR_EXIT", "Thoát do lỗi ngoại lệ Python (Exit Code 1)"),
    0x00000063: ("VIEWER_DISCONNECT_EXIT", "Cửa sổ Viewer đóng do ngắt kết nối mạng (Exit Code 99)"),
    0x00000103: ("STILL_ACTIVE", "Tiến trình vẫn đang chạy (259)"),
    0xC0000005: ("STATUS_ACCESS_VIOLATION", "Lỗi truy cập bộ nhớ trái phép (Segfault / Access Violation tại tầng C/DLL: Tkinter/Pygame/DXCam/ctypes)"),
    0xC0000409: ("STATUS_STACK_BUFFER_OVERRUN", "Lỗi tràn bộ đệm ngăn xếp / FastFail / abort() (thường do Tcl_AsyncDelete gọi Tkinter từ sai luồng hoặc lỗi C runtime)"),
    0xC0000374: ("STATUS_HEAP_CORRUPTION", "Lỗi hỏng vùng nhớ Heap (xung đột bộ nhớ đa luồng tại tầng C/DLL)"),
    0xC00000FD: ("STATUS_STACK_OVERFLOW", "Lỗi tràn ngăn xếp (Stack Overflow / đệ quy vô tận)"),
    0xC0000142: ("STATUS_DLL_INIT_FAILED", "Khởi tạo DLL thất bại (thường do Windows đang Shutdown/Logoff hoặc thiếu quyền Desktop/WinSta0)"),
    0xC000013A: ("STATUS_CONTROL_C_EXIT", "Tiến trình bị đóng bởi tín hiệu Ctrl+C hoặc đóng cửa sổ Console/Logoff"),
    0xC000001D: ("STATUS_ILLEGAL_INSTRUCTION", "Lệnh tập lệnh CPU không hợp lệ (Illegal Instruction)"),
    0xC0000094: ("STATUS_INTEGER_DIVIDE_BY_ZERO", "Lỗi chia cho 0 ở tầng C/Native"),
    0xC0000008: ("STATUS_INVALID_HANDLE", "Sử dụng Handle hệ điều hành không hợp lệ hoặc đã đóng"),
    0xC0000017: ("STATUS_NO_MEMORY", "Tràn bộ nhớ RAM (Out of Memory)"),
    0xE06D7363: ("MSVC_CPP_EXCEPTION", "Ngoại lệ Microsoft Visual C++ (C++ Exception chưa được bắt từ thư viện native)"),
    0x80000003: ("STATUS_BREAKPOINT", "Điểm dừng Debug / Assert ở tầng C/DLL"),
    0x40010004: ("DBG_TERMINATE_PROCESS", "Tiến trình bị đóng cưỡng bức từ bên ngoài (Task Manager / Debugger)"),
    0x40000015: ("STATUS_FATAL_APP_EXIT", "Fatal App Exit (abort() hoặc lỗi nghiêm trọng từ C Runtime)"),
}


def decode_windows_exit_code(exit_code):
    """
    Giải mã mã thoát (Exit Code / NTSTATUS) của tiến trình trên Windows sang chuỗi mô tả chi tiết.
    Trả về tuple: (unsigned_code, hex_str, symbol_name, description).
    """
    if exit_code is None:
        return (None, "None", "UNKNOWN", "Không xác định được mã thoát")
    try:
        u_code = int(exit_code) & 0xFFFFFFFF
    except Exception:
        return (exit_code, str(exit_code), "UNKNOWN", f"Mã thoát: {exit_code}")

    hex_str = f"0x{u_code:08X}"
    if u_code in _KNOWN_WIN_EXIT_CODES:
        sym, desc = _KNOWN_WIN_EXIT_CODES[u_code]
        return (u_code, hex_str, sym, desc)

    if u_code >= 0xC0000000:
        return (u_code, hex_str, "NTSTATUS_FATAL_ERROR", f"Lỗi hệ thống nghiêm trọng mức nhân Windows NTSTATUS ({hex_str})")
    if u_code >= 0x80000000:
        return (u_code, hex_str, "NTSTATUS_WARNING_OR_EXCEPTION", f"Mã ngoại lệ hệ thống Windows ({hex_str})")
    return (u_code, hex_str, f"EXIT_CODE_{u_code}", f"Mã thoát tiến trình: {u_code} ({hex_str})")


def read_log_tail(filename, max_lines=20, max_bytes=16384):
    """Đọc các dòng cuối cùng của một file log trong thư mục Logs để đính kèm vào báo cáo crash."""
    try:
        fpath = get_log_filepath(filename)
        if not os.path.exists(fpath):
            return ""
        size = os.path.getsize(fpath)
        if size == 0:
            return ""
        with open(fpath, "rb") as rf:
            if size > max_bytes:
                rf.seek(size - max_bytes)
            raw = rf.read()
        text = raw.decode("utf-8-sig", errors="replace")
        lines = [ln.rstrip("\r") for ln in text.splitlines() if ln.strip()]
        if not lines:
            return ""
        return "\n".join(lines[-max_lines:])
    except Exception:
        return ""


def log_system_crash(title, role="App", pid=None, exit_code=None, details=None, extra_logs=None):
    """
    Ghi báo cáo lỗi / sập ứng dụng chi tiết vào Logs/system_crash.log và Logs/crash.log.
    Được gọi từ cả bên trong ứng dụng (excepthook, threading hook, Tkinter hook)
    lẫn từ Windows Service (giám sát tiến trình mức hệ thống + Windows Event Log).
    """
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        actual_pid = pid if pid is not None else os.getpid()
        lines = [
            f"\n================================================================================",
            f"[{timestamp}] [SYSTEM CRASH REPORT] {title}",
            f"  - Thành phần (Role) : {role}",
            f"  - PID               : {actual_pid}",
        ]
        if exit_code is not None:
            _, hex_str, sym, desc = decode_windows_exit_code(exit_code)
            lines.append(f"  - Mã thoát (Exit)   : {exit_code} ({hex_str} - {sym})")
            lines.append(f"  - Giải thích mã lỗi : {desc}")

        if details:
            if isinstance(details, dict):
                for k, v in details.items():
                    if v is not None and str(v).strip() != "":
                        lines.append(f"  - {k:<18}: {v}")
            else:
                lines.append("  - Chi tiết lỗi:")
                for d_line in str(details).rstrip().splitlines():
                    lines.append(f"      {d_line}")

        if extra_logs and isinstance(extra_logs, dict):
            for log_name, tail_content in extra_logs.items():
                if tail_content and str(tail_content).strip():
                    lines.append(f"  --- Dòng log cuối từ [{log_name}] ---")
                    for t_line in str(tail_content).rstrip().splitlines():
                        lines.append(f"      {t_line}")

        lines.append("================================================================================\n")
        report_text = "\n".join(lines)

        sys_crash_path = get_log_filepath("system_crash.log")
        safe_write_log_line(sys_crash_path, report_text, "system_crash.log")

        crash_path = get_log_filepath("crash.log")
        safe_write_log_line(crash_path, report_text, "crash.log")
        return True
    except Exception:
        return False


_fault_log_file_handle = None
_crash_handlers_installed = False


def install_crash_handlers(role_name="App"):
    """
    Cài đặt bộ bắt lỗi toàn diện cho tiến trình hiện tại:
    1. faulthandler (bắt lỗi C-level Segfault, Access Violation, Abort, Illegal Instruction, Stack Overflow
       và tự động xuất callstack của toàn bộ luồng Python ra Logs/native_fault.log).
    2. sys.excepthook (bắt mọi ngoại lệ chưa xử lý trên luồng chính).
    3. threading.excepthook (bắt mọi ngoại lệ chưa xử lý trên các luồng nền threading.Thread).
    4. sys.unraisablehook (bắt lỗi phát sinh trong C callback như ctypes WndProc / Hook hoặc __del__).
    5. Win32 SetErrorMode (ngăn hộp thoại 'Application has stopped working' làm treo tiến trình nền,
       nhưng vẫn cho phép Windows Event Log ghi nhận Event ID 1000).
    """
    global _fault_log_file_handle, _crash_handlers_installed
    if _crash_handlers_installed:
        return
    _crash_handlers_installed = True

    # 1. Cài đặt Win32 Error Mode để không bị treo bởi hộp thoại WER UI khi crash
    if sys.platform == "win32":
        try:
            import ctypes
            SEM_FAILCRITICALERRORS = 0x0001
            SEM_NOGPFAULTERRORBOX = 0x0002
            SEM_NOOPENFILEERRORBOX = 0x8000
            prev_mode = ctypes.windll.kernel32.SetErrorMode(0)
            ctypes.windll.kernel32.SetErrorMode(
                prev_mode | SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX
            )
        except Exception:
            pass

    # 2. Kích hoạt faulthandler cho lỗi tầng C/DLL (Access Violation / Abort / Segfault)
    try:
        import faulthandler
        fault_path = get_log_filepath("native_fault.log")
        ensure_utf8_bom(fault_path)
        _fault_log_file_handle = open(fault_path, "a", encoding="utf-8", buffering=1)
        _fault_log_file_handle.write(
            f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Faulthandler Armed] "
            f"Role={role_name} PID={os.getpid()} argv={sys.argv}\n"
        )
        _fault_log_file_handle.flush()
        faulthandler.enable(file=_fault_log_file_handle, all_threads=True)
    except Exception:
        pass

    # 3. Hook sys.excepthook (Main thread uncaught exceptions)
    import traceback
    import threading

    def _custom_excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        except Exception:
            pass
        log_system_crash(
            title=f"Uncaught Exception in Main Thread ({exc_type.__name__}: {exc_value})",
            role=role_name,
            pid=os.getpid(),
            details=tb_str,
        )

    sys.excepthook = _custom_excepthook

    # 4. Hook threading.excepthook (Background thread uncaught exceptions, Python 3.8+)
    if hasattr(threading, "excepthook"):
        _orig_thread_hook = threading.excepthook

        def _custom_threading_excepthook(args):
            try:
                if issubclass(args.exc_type, SystemExit):
                    return
                t_name = getattr(args.thread, "name", "UnknownThread")
                tb_str = "".join(
                    traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
                )
                log_system_crash(
                    title=f"Uncaught Exception in Background Thread '{t_name}' ({args.exc_type.__name__}: {args.exc_value})",
                    role=role_name,
                    pid=os.getpid(),
                    details=tb_str,
                )
            except Exception:
                pass
            try:
                _orig_thread_hook(args)
            except Exception:
                pass

        threading.excepthook = _custom_threading_excepthook

    # 5. Hook sys.unraisablehook (Exceptions in ctypes callbacks / WndProc / __del__)
    if hasattr(sys, "unraisablehook"):
        _orig_unraisable_hook = sys.unraisablehook

        def _custom_unraisablehook(unraisable):
            try:
                obj_repr = repr(getattr(unraisable, "object", None))
                err_msg = getattr(unraisable, "err_msg", "") or ""
                tb_str = "".join(
                    traceback.format_exception(
                        unraisable.exc_type, unraisable.exc_value, unraisable.exc_traceback
                    )
                )
                log_system_crash(
                    title=f"Unraisable Exception in C Callback / Finalizer ({unraisable.exc_type.__name__})",
                    role=role_name,
                    pid=os.getpid(),
                    details=f"Object: {obj_repr} | Msg: {err_msg}\n{tb_str}",
                )
            except Exception:
                pass
            try:
                _orig_unraisable_hook(unraisable)
            except Exception:
                pass

        sys.unraisablehook = _custom_unraisablehook


def install_tkinter_exception_hook(tk_root, role_name="GUI"):
    """
    Bắt toàn bộ các ngoại lệ phát sinh bên trong sự kiện giao diện Tkinter (Button click, Event bind, root.after)
    vốn mặc định bị Tkinter nuốt hoặc chỉ in ra stderr mà không gọi sys.excepthook.
    """
    if tk_root is None:
        return
    import traceback

    def _tk_report_callback_exception(exc_type, exc_value, exc_tb):
        try:
            tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            print(f"[Tkinter Exception] {exc_type.__name__}: {exc_value}\n{tb_str}")
            log_system_crash(
                title=f"Unhandled Tkinter UI Callback Exception ({exc_type.__name__}: {exc_value})",
                role=role_name,
                pid=os.getpid(),
                details=tb_str,
            )
        except Exception:
            pass

    try:
        tk_root.report_callback_exception = _tk_report_callback_exception
    except Exception:
        pass

