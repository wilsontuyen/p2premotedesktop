"""
Clipboard Agent - Chạy ở quyền User thường.
Lắng nghe Named Pipe từ Service (headless app) để nhận đường dẫn file
và nạp vào Clipboard hệ thống bằng win32clipboard.

Kiến trúc: Service (SYSTEM) -> Named Pipe -> Agent (User) -> Clipboard
"""

import os
import sys
import time
import threading
import logging

# Xác định thư mục ứng dụng
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))

# Cấu hình logging
log_file = os.path.join(app_dir, "agent.log")
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format="[%(asctime)s] [PID %(process)d] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)


def log_print(msg):
    """Log ra cả file và console."""
    log.info(msg)
    try:
        print(msg)
    except:
        pass


# Tên Named Pipe mà Service sẽ gửi đường dẫn file qua
PIPE_NAME = r"\\.\pipe\RemoteDesktopClipboardPipe"


def set_clipboard_files(file_path):
    """
    Nạp đường dẫn file vào Clipboard hệ thống theo chuẩn CF_HDROP.
    Sử dụng win32clipboard (pywin32).
    """
    try:
        import win32clipboard

        if not os.path.exists(file_path):
            log_print(f"[Agent] File không tồn tại, bỏ qua: {file_path}")
            return False

        abs_path = os.path.abspath(file_path)
        log_print(f"[Agent] Đang nạp file vào Clipboard: {abs_path}")

        # Retry loop để chờ ứng dụng khác nhả khóa Clipboard
        opened = False
        for attempt in range(10):
            try:
                win32clipboard.OpenClipboard()
                opened = True
                break
            except Exception:
                time.sleep(0.05)

        if not opened:
            log_print("[Agent] Lỗi: Không thể OpenClipboard sau 10 lần thử.")
            return False

        try:
            win32clipboard.EmptyClipboard()
            # SetClipboardFiles nhận một tuple chứa các đường dẫn file
            win32clipboard.SetClipboardFiles((abs_path,))
            log_print(f"[Agent] Đã nạp thành công file vào Clipboard: {abs_path}")
            return True
        finally:
            win32clipboard.CloseClipboard()

    except ImportError:
        log_print("[Agent] Lỗi: Thư viện win32clipboard (pywin32) chưa được cài đặt!")
        return False
    except Exception as e:
        log_print(f"[Agent] Lỗi khi nạp file vào Clipboard: {e}")
        return False


def pipe_listener_loop():
    """
    Vòng lặp chính: Liên tục kết nối tới Named Pipe và lắng nghe
    đường dẫn file từ Service.
    """
    import win32file
    import win32pipe

    log_print(f"[Agent] Bắt đầu lắng nghe Named Pipe: {PIPE_NAME}")

    while True:
        pipe_handle = None
        try:
            # Chờ đến khi Pipe sẵn sàng (Service đã tạo)
            log_print(f"[Agent] Đang chờ kết nối tới Pipe...")

            while True:
                try:
                    pipe_handle = win32file.CreateFile(
                        PIPE_NAME,
                        win32file.GENERIC_READ,
                        0,        # Không chia sẻ
                        None,     # Security Attributes mặc định (đủ cho User thường)
                        win32file.OPEN_EXISTING,
                        0,
                        None
                    )
                    break  # Kết nối thành công
                except Exception:
                    # Pipe chưa tồn tại hoặc bận, chờ rồi thử lại
                    time.sleep(1.0)

            log_print(f"[Agent] Đã kết nối thành công tới Pipe.")

            # Đặt chế độ đọc message (byte mode)
            win32pipe.SetNamedPipeHandleState(
                pipe_handle,
                win32pipe.PIPE_READMODE_MESSAGE,
                None,
                None
            )

            # Vòng lặp đọc dữ liệu từ Pipe
            while True:
                try:
                    hr, data = win32file.ReadFile(pipe_handle, 4096)
                    if hr == 0:  # ERROR_SUCCESS
                        file_path = data.decode("utf-8").strip()
                        if file_path:
                            log_print(f"[Agent] Nhận được đường dẫn từ Pipe: {file_path}")

                            # Kiểm tra file tồn tại trước khi nạp Clipboard
                            if os.path.exists(file_path):
                                set_clipboard_files(file_path)
                            else:
                                log_print(f"[Agent] File chưa tồn tại trên đĩa, chờ 1 giây rồi thử lại...")
                                time.sleep(1.0)
                                if os.path.exists(file_path):
                                    set_clipboard_files(file_path)
                                else:
                                    log_print(f"[Agent] File vẫn không tồn tại sau khi chờ: {file_path}")
                    else:
                        log_print(f"[Agent] ReadFile trả về mã lỗi: {hr}")
                        break

                except Exception as read_err:
                    err_code = getattr(read_err, 'winerror', 0)
                    if err_code == 109:  # ERROR_BROKEN_PIPE
                        log_print("[Agent] Pipe bị ngắt (Service đóng kết nối). Đang kết nối lại...")
                        break
                    elif err_code == 234:  # ERROR_MORE_DATA
                        # Message lớn hơn buffer, đọc tiếp
                        log_print("[Agent] Buffer nhỏ hơn message, cần đọc tiếp...")
                        continue
                    else:
                        log_print(f"[Agent] Lỗi đọc Pipe: {read_err}")
                        break

        except Exception as e:
            log_print(f"[Agent] Lỗi kết nối Pipe: {e}")

        finally:
            if pipe_handle is not None:
                try:
                    win32file.CloseHandle(pipe_handle)
                except:
                    pass

        # Chờ trước khi thử kết nối lại
        log_print("[Agent] Chờ 2 giây trước khi kết nối lại Pipe...")
        time.sleep(2.0)


def main():
    log_print("=" * 60)
    log_print(f"[Agent] Clipboard Agent khởi động. PID: {os.getpid()}")
    log_print(f"[Agent] Thư mục ứng dụng: {app_dir}")
    log_print("=" * 60)

    # Chạy pipe_listener_loop trực tiếp trên main thread
    # (vì Agent này chỉ có 1 nhiệm vụ duy nhất)
    try:
        pipe_listener_loop()
    except KeyboardInterrupt:
        log_print("[Agent] Nhận Ctrl+C. Đang thoát...")
    except Exception as e:
        log_print(f"[Agent] Lỗi không mong đợi: {e}")


if __name__ == "__main__":
    main()
