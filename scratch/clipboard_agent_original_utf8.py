"""
Clipboard Agent - Chß║íy ß╗ƒ quyß╗ün User th╞░ß╗¥ng.
Lß║»ng nghe Named Pipe tß╗½ Service (headless app) ─æß╗â nhß║¡n ─æ╞░ß╗¥ng dß║½n file
v├á nß║íp v├áo Clipboard hß╗ç thß╗æng bß║▒ng win32clipboard.

Kiß║┐n tr├║c: Service (SYSTEM) -> Named Pipe -> Agent (User) -> Clipboard
"""

import os
import sys
import time
import threading
import logging

# X├íc ─æß╗ïnh th╞░ mß╗Ñc ß╗⌐ng dß╗Ñng
if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))

# Cß║Ñu h├¼nh logging
log_file = os.path.join(app_dir, "agent.log")
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format="[%(asctime)s] [PID %(process)d] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)


def log_print(msg):
    """Log ra cß║ú file v├á console."""
    log.info(msg)
    try:
        print(msg)
    except:
        pass


# T├¬n Named Pipe m├á Service sß║╜ gß╗¡i ─æ╞░ß╗¥ng dß║½n file qua
PIPE_NAME = r"\\.\pipe\RemoteDesktopClipboardPipe"


def set_clipboard_files(file_path):
    """
    Nß║íp ─æ╞░ß╗¥ng dß║½n file v├áo Clipboard hß╗ç thß╗æng theo chuß║⌐n CF_HDROP.
    Sß╗¡ dß╗Ñng win32clipboard (pywin32).
    """
    try:
        import win32clipboard

        if not os.path.exists(file_path):
            log_print(f"[Agent] File kh├┤ng tß╗ôn tß║íi, bß╗Å qua: {file_path}")
            return False

        abs_path = os.path.abspath(file_path)
        log_print(f"[Agent] ─Éang nß║íp file v├áo Clipboard: {abs_path}")

        # Retry loop ─æß╗â chß╗¥ ß╗⌐ng dß╗Ñng kh├íc nhß║ú kh├│a Clipboard
        opened = False
        for attempt in range(10):
            try:
                win32clipboard.OpenClipboard()
                opened = True
                break
            except Exception:
                time.sleep(0.05)

        if not opened:
            log_print("[Agent] Lß╗ùi: Kh├┤ng thß╗â OpenClipboard sau 10 lß║ºn thß╗¡.")
            return False

        try:
            win32clipboard.EmptyClipboard()
            # SetClipboardFiles nhß║¡n mß╗Öt tuple chß╗⌐a c├íc ─æ╞░ß╗¥ng dß║½n file
            win32clipboard.SetClipboardFiles((abs_path,))
            log_print(f"[Agent] ─É├ú nß║íp th├ánh c├┤ng file v├áo Clipboard: {abs_path}")
            return True
        finally:
            win32clipboard.CloseClipboard()

    except ImportError:
        log_print("[Agent] Lß╗ùi: Th╞░ viß╗çn win32clipboard (pywin32) ch╞░a ─æ╞░ß╗úc c├ái ─æß║╖t!")
        return False
    except Exception as e:
        log_print(f"[Agent] Lß╗ùi khi nß║íp file v├áo Clipboard: {e}")
        return False


def pipe_listener_loop():
    """
    V├▓ng lß║╖p ch├¡nh: Li├¬n tß╗Ñc kß║┐t nß╗æi tß╗¢i Named Pipe v├á lß║»ng nghe
    ─æ╞░ß╗¥ng dß║½n file tß╗½ Service.
    """
    import win32file
    import win32pipe

    log_print(f"[Agent] Bß║»t ─æß║ºu lß║»ng nghe Named Pipe: {PIPE_NAME}")

    while True:
        pipe_handle = None
        try:
            # Chß╗¥ ─æß║┐n khi Pipe sß║╡n s├áng (Service ─æ├ú tß║ío)
            log_print(f"[Agent] ─Éang chß╗¥ kß║┐t nß╗æi tß╗¢i Pipe...")

            while True:
                try:
                    pipe_handle = win32file.CreateFile(
                        PIPE_NAME,
                        win32file.GENERIC_READ,
                        0,        # Kh├┤ng chia sß║╗
                        None,     # Security Attributes mß║╖c ─æß╗ïnh (─æß╗º cho User th╞░ß╗¥ng)
                        win32file.OPEN_EXISTING,
                        0,
                        None
                    )
                    break  # Kß║┐t nß╗æi th├ánh c├┤ng
                except Exception:
                    # Pipe ch╞░a tß╗ôn tß║íi hoß║╖c bß║¡n, chß╗¥ rß╗ôi thß╗¡ lß║íi
                    time.sleep(1.0)

            log_print(f"[Agent] ─É├ú kß║┐t nß╗æi th├ánh c├┤ng tß╗¢i Pipe.")

            # ─Éß║╖t chß║┐ ─æß╗Ö ─æß╗ìc message (byte mode)
            win32pipe.SetNamedPipeHandleState(
                pipe_handle,
                win32pipe.PIPE_READMODE_MESSAGE,
                None,
                None
            )

            # V├▓ng lß║╖p ─æß╗ìc dß╗» liß╗çu tß╗½ Pipe
            while True:
                try:
                    hr, data = win32file.ReadFile(pipe_handle, 4096)
                    if hr == 0:  # ERROR_SUCCESS
                        file_path = data.decode("utf-8").strip()
                        if file_path:
                            log_print(f"[Agent] Nhß║¡n ─æ╞░ß╗úc ─æ╞░ß╗¥ng dß║½n tß╗½ Pipe: {file_path}")

                            # Kiß╗âm tra file tß╗ôn tß║íi tr╞░ß╗¢c khi nß║íp Clipboard
                            if os.path.exists(file_path):
                                set_clipboard_files(file_path)
                            else:
                                log_print(f"[Agent] File ch╞░a tß╗ôn tß║íi tr├¬n ─æ─⌐a, chß╗¥ 1 gi├óy rß╗ôi thß╗¡ lß║íi...")
                                time.sleep(1.0)
                                if os.path.exists(file_path):
                                    set_clipboard_files(file_path)
                                else:
                                    log_print(f"[Agent] File vß║½n kh├┤ng tß╗ôn tß║íi sau khi chß╗¥: {file_path}")
                    else:
                        log_print(f"[Agent] ReadFile trß║ú vß╗ü m├ú lß╗ùi: {hr}")
                        break

                except Exception as read_err:
                    err_code = getattr(read_err, 'winerror', 0)
                    if err_code == 109:  # ERROR_BROKEN_PIPE
                        log_print("[Agent] Pipe bß╗ï ngß║»t (Service ─æ├│ng kß║┐t nß╗æi). ─Éang kß║┐t nß╗æi lß║íi...")
                        break
                    elif err_code == 234:  # ERROR_MORE_DATA
                        # Message lß╗¢n h╞ín buffer, ─æß╗ìc tiß║┐p
                        log_print("[Agent] Buffer nhß╗Å h╞ín message, cß║ºn ─æß╗ìc tiß║┐p...")
                        continue
                    else:
                        log_print(f"[Agent] Lß╗ùi ─æß╗ìc Pipe: {read_err}")
                        break

        except Exception as e:
            log_print(f"[Agent] Lß╗ùi kß║┐t nß╗æi Pipe: {e}")

        finally:
            if pipe_handle is not None:
                try:
                    win32file.CloseHandle(pipe_handle)
                except:
                    pass

        # Chß╗¥ tr╞░ß╗¢c khi thß╗¡ kß║┐t nß╗æi lß║íi
        log_print("[Agent] Chß╗¥ 2 gi├óy tr╞░ß╗¢c khi kß║┐t nß╗æi lß║íi Pipe...")
        time.sleep(2.0)


def main():
    log_print("=" * 60)
    log_print(f"[Agent] Clipboard Agent khß╗ƒi ─æß╗Öng. PID: {os.getpid()}")
    log_print(f"[Agent] Th╞░ mß╗Ñc ß╗⌐ng dß╗Ñng: {app_dir}")
    log_print("=" * 60)

    # Chß║íy pipe_listener_loop trß╗▒c tiß║┐p tr├¬n main thread
    # (v├¼ Agent n├áy chß╗ë c├│ 1 nhiß╗çm vß╗Ñ duy nhß║Ñt)
    try:
        pipe_listener_loop()
    except KeyboardInterrupt:
        log_print("[Agent] Nhß║¡n Ctrl+C. ─Éang tho├ít...")
    except Exception as e:
        log_print(f"[Agent] Lß╗ùi kh├┤ng mong ─æß╗úi: {e}")


if __name__ == "__main__":
    main()
