import tkinter as tk
import ctypes
from ctypes import wintypes
import time
import os

CF_HDROP = 15
user32 = ctypes.windll.user32
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

root = tk.Tk()
hwnd = int(root.winfo_id())

print("Testing Delay-Render CF_HDROP...")
if user32.OpenClipboard(hwnd):
    user32.EmptyClipboard()
    res = user32.SetClipboardData(CF_HDROP, None)
    print("SetClipboardData(15, None) returned:", res)
    user32.CloseClipboard()
else:
    print("OpenClipboard failed")

def check_clip():
    if user32.OpenClipboard(None):
        avail = user32.IsClipboardFormatAvailable(CF_HDROP)
        print("Is CF_HDROP available?", avail)
        user32.CloseClipboard()
    root.after(2000, check_clip)

check_clip()
root.after(6000, root.destroy)
root.mainloop()
