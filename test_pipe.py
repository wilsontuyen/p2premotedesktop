import ctypes
from ctypes import wintypes
import os
import win32pipe
import win32file
import threading

def create_hdrop_data(file_paths):
    class DROPFILES(ctypes.Structure):
        _fields_ = [
            ("pFiles", wintypes.DWORD),
            ("pt", wintypes.POINT),
            ("fNC", wintypes.BOOL),
            ("fWide", wintypes.BOOL)
        ]
    
    offset = ctypes.sizeof(DROPFILES)
    files_str = "\0".join(file_paths) + "\0\0"
    files_buf = files_str.encode("utf-16le")
    total_size = offset + len(files_buf)
    
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.restype = ctypes.c_void_p
    
    GMEM_MOVEABLE = 0x0002
    GMEM_ZEROINIT = 0x0040
    
    hGlobal = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, total_size)
    pGlobal = kernel32.GlobalLock(hGlobal)
    
    dropfiles = DROPFILES()
    dropfiles.pFiles = offset
    dropfiles.fWide = True
    
    ctypes.memmove(pGlobal, ctypes.addressof(dropfiles), offset)
    ctypes.memmove(pGlobal + offset, files_buf, len(files_buf))
    kernel32.GlobalUnlock(hGlobal)
    return hGlobal

def set_clipboard(path):
    hGlobal = create_hdrop_data([path])
    ctypes.windll.user32.OpenClipboard(None)
    ctypes.windll.user32.EmptyClipboard()
    ctypes.windll.user32.SetClipboardData(15, hGlobal)
    ctypes.windll.user32.CloseClipboard()
    print("Clipboard set to", path)

def pipe_server():
    pipe_name = r'\\.\pipe\TestPipe.txt'
    pipe = win32pipe.CreateNamedPipe(
        pipe_name,
        win32pipe.PIPE_ACCESS_OUTBOUND,
        win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
        1, 65536, 65536,
        0,
        None
    )
    print("Pipe server waiting for Explorer to paste...")
    win32pipe.ConnectNamedPipe(pipe, None)
    print("Explorer connected! Streaming data...")
    win32file.WriteFile(pipe, b"Hello from named pipe!" * 1000)
    win32file.CloseHandle(pipe)
    print("Streaming done.")

t = threading.Thread(target=pipe_server, daemon=True)
t.start()

import time
time.sleep(1)
set_clipboard(r'\\.\pipe\TestPipe.txt')

print("Now go to Desktop, Right Click -> Paste.")
print("Waiting 15 seconds...")
time.sleep(15)
