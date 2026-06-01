import time
import os
import sys
import ctypes
import threading
import tkinter as tk

res_file = r"C:\Apps\P2P\test_clip_res.txt"

def log_msg(msg):
    try:
        with open(res_file, "a", encoding="utf-8") as f:
            f.write(f"[PID {os.getpid()}] {msg}\n")
            f.flush()
    except:
        pass

log_msg("test_clip_hwnd.py starting...")

try:
    from ctypes import wintypes
    u32 = ctypes.windll.user32
    k32 = ctypes.windll.kernel32

    fn_OpenClipboard = u32.OpenClipboard
    fn_CloseClipboard = u32.CloseClipboard
    fn_OpenClipboard.argtypes = [wintypes.HWND]
    fn_OpenClipboard.restype = wintypes.BOOL
    fn_CloseClipboard.argtypes = []
    fn_CloseClipboard.restype = wintypes.BOOL

    root = tk.Tk()
    root.withdraw()
    hwnd = root.winfo_id()
    log_msg(f"Tkinter root created. HWND = {hwnd}")

    # Test 1: OpenClipboard(hwnd) on main thread
    opened_main = fn_OpenClipboard(hwnd)
    log_msg(f"OpenClipboard(hwnd) on MAIN thread: {opened_main}")
    if opened_main:
        fn_CloseClipboard()

    # Test 2: OpenClipboard(hwnd) on background thread
    def bg_thread():
        try:
            opened_bg = fn_OpenClipboard(hwnd)
            log_msg(f"OpenClipboard(hwnd) on BG thread: {opened_bg}")
            if opened_bg:
                fn_CloseClipboard()
            
            # Test 3: OpenClipboard(None) on background thread
            opened_none = fn_OpenClipboard(None)
            log_msg(f"OpenClipboard(None) on BG thread: {opened_none}")
            if opened_none:
                fn_CloseClipboard()
        except Exception as ex:
            log_msg(f"BG thread exception: {ex}")

    t = threading.Thread(target=bg_thread)
    t.start()
    t.join()

    root.destroy()

except Exception as e:
    import traceback
    log_msg(f"Exception occurred: {e}\n{traceback.format_exc()}")

log_msg("test_clip_hwnd.py exiting.")
