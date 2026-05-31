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
            
            # Đặt Preferred DropEffect là 2 (DROPEFFECT_MOVE) để file bị di chuyển thay vì copy
            try:
                cf_drop_effect = win32clipboard.RegisterClipboardFormat("Preferred DropEffect")
                import struct
                # Đóng gói giá trị 2 (DWORD)
                win32clipboard.SetClipboardData(cf_drop_effect, struct.pack("I", 2))
            except Exception as e:
                log_print(f"[Agent] Không thể đặt Preferred DropEffect: {e}")
                
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


def set_clipboard_text(text):
    """
    Nạp text vào Clipboard hệ thống.
    """
    try:
        import win32clipboard
        import win32con

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
            # 13 is CF_UNICODETEXT
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            log_print(f"[Agent] Đã nạp thành công text vào Clipboard (độ dài {len(text)})")
            return True
        finally:
            win32clipboard.CloseClipboard()

    except ImportError:
        log_print("[Agent] Lỗi: Thư viện win32clipboard (pywin32) hoặc win32con chưa được cài đặt!")
        return False
    except Exception as e:
        log_print(f"[Agent] Lỗi khi nạp text vào Clipboard: {e}")
        return False


def pipe_listener_loop(gui_queue):
    import win32file
    import win32pipe

    log_print(f"[Agent] Bắt đầu lắng nghe Named Pipe: {PIPE_NAME}")

    while True:
        pipe_handle = None
        try:
            log_print(f"[Agent] Đang chờ kết nối tới Pipe...")

            while True:
                try:
                    pipe_handle = win32file.CreateFile(
                        PIPE_NAME,
                        win32file.GENERIC_READ,
                        0,
                        None,
                        win32file.OPEN_EXISTING,
                        0,
                        None
                    )
                    break
                except Exception:
                    time.sleep(0.5)

            log_print(f"[Agent] Đã kết nối thành công tới Pipe.")

            try:
                win32pipe.SetNamedPipeHandleState(
                    pipe_handle,
                    win32pipe.PIPE_READMODE_MESSAGE,
                    None,
                    None
                )
            except Exception as se:
                log_print(f"[Agent] Cảnh báo SetNamedPipeHandleState: {se}. Tiếp tục ở chế độ byte mode.")

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
                                log_print(f"[Agent] Nhận được tin nhắn từ Pipe (độ dài {len(msg)}): {msg[:100]}...")
                                if msg.startswith("TEXT:"):
                                    text_val = msg[5:]
                                    gui_queue.put(("text", text_val))
                                elif msg.startswith("START:"):
                                    parts = msg[6:].split("|")
                                    display_name = parts[0]
                                    total_size = int(parts[1]) if len(parts) > 1 else 0
                                    gui_queue.put(("start", (display_name, total_size)))
                                elif msg.startswith("PROGRESS:"):
                                    received = int(msg[9:])
                                    gui_queue.put(("progress", received))
                                elif msg.startswith("END"):
                                    gui_queue.put(("end", None))
                                elif msg.startswith("CANCEL"):
                                    gui_queue.put(("cancel", None))
                                elif msg.startswith("FILE:"):
                                    gui_queue.put(("file", msg[5:]))
                                else:
                                    gui_queue.put(("file", msg))
                    else:
                        log_print(f"[Agent] ReadFile trả về mã lỗi: {hr}")
                        break
                except Exception as read_err:
                    err_code = getattr(read_err, 'winerror', 0)
                    if err_code == 109:
                        log_print("[Agent] Pipe bị ngắt (Service đóng kết nối). Đang kết nối lại...")
                        break
                    elif err_code == 234:
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
        time.sleep(0.1)


def main():
    import queue
    import tkinter as tk
    import win32event
    import win32api
    try:
        from app import ProgressDialog
    except ImportError:
        class ProgressDialog:
            def __init__(self, *args, **kwargs): pass
            def update_progress(self, *args, **kwargs): pass
            def destroy(self): pass

    log_print("=" * 60)
    log_print(f"[Agent] Clipboard Agent khởi động. PID: {os.getpid()}")
    log_print(f"[Agent] Thư mục ứng dụng: {app_dir}")
    log_print("=" * 60)

    gui_queue = queue.Queue()
    t = threading.Thread(target=pipe_listener_loop, args=(gui_queue,), daemon=True)
    t.start()

    root = tk.Tk()
    root.withdraw()
    active_dialog = None

    def trigger_cancel():
        log_print("[Agent] Người dùng ấn Hủy truyền tải.")
        try:
            h_event = win32event.OpenEvent(win32event.EVENT_MODIFY_STATE, False, "Global\\AntigravityP2P_CancelTransfer_Event")
            win32event.SetEvent(h_event)
            win32api.CloseHandle(h_event)
        except Exception as e:
            log_print(f"[Agent] Không thể gửi sự kiện hủy: {e}")

    def poll_gui_queue():
        nonlocal active_dialog
        while not gui_queue.empty():
            try:
                action, val = gui_queue.get_nowait()
                if action == "text":
                    set_clipboard_text(val)
                elif action == "file":
                    if os.path.exists(val):
                        set_clipboard_files(val)
                    else:
                        log_print(f"[Agent] File không tồn tại để nạp clipboard: {val}")
                elif action == "start":
                    display_name, total_size = val
                    if active_dialog:
                        try: active_dialog.destroy()
                        except: pass
                    active_dialog = ProgressDialog(
                        root, "Đang tải file về...", display_name, total_size,
                        on_cancel=trigger_cancel
                    )
                elif action == "progress":
                    if active_dialog:
                        try: active_dialog.update_progress(val)
                        except: pass
                elif action == "end":
                    if active_dialog:
                        def _close():
                            nonlocal active_dialog
                            if active_dialog:
                                try: active_dialog.destroy()
                                except: pass
                                active_dialog = None
                        root.after(500, _close)
                elif action == "cancel":
                    if active_dialog:
                        try: active_dialog.destroy()
                        except: pass
                        active_dialog = None
            except queue.Empty:
                break
            except Exception as e:
                log_print(f"[Agent] Lỗi xử lý hàng đợi GUI: {e}")
        root.after(50, poll_gui_queue)

    try:
        poll_gui_queue()
        root.mainloop()
    except KeyboardInterrupt:
        log_print("[Agent] Nhận Ctrl+C. Đang thoát...")
    except Exception as e:
        log_print(f"[Agent] Lỗi không mong đợi: {e}")


if __name__ == "__main__":
    main()
