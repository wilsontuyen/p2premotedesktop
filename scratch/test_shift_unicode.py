import ctypes
import time
import subprocess
import os

# Ctypes definitions for SendInput API
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort)
    ]

class INPUT_union(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("union", INPUT_union)
    ]

def send_unicode(char, pressed):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    flags = KEYEVENTF_UNICODE
    if not pressed:
        flags |= KEYEVENTF_KEYUP
    inp.union.ki = KEYBDINPUT(0, ord(char), flags, 0, None)
    res = ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    return res > 0

def send_key_vk(vk, pressed):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    flags = 0
    if not pressed:
        flags |= KEYEVENTF_KEYUP
    scan_code = ctypes.windll.user32.MapVirtualKeyW(vk, 0) & 0xFF
    inp.union.ki = KEYBDINPUT(vk, scan_code, flags, 0, None)
    res = ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    return res > 0

if __name__ == "__main__":
    test_txt = os.path.abspath("scratch/test_shift_out.txt")
    if os.path.exists(test_txt):
        os.remove(test_txt)
        
    proc = subprocess.Popen(["notepad.exe"])
    time.sleep(1.5) # Wait for Notepad to open
    
    # Press Shift
    send_key_vk(0x10, True) # VK_SHIFT
    time.sleep(0.05)
    
    # Send Unicode 'a'
    send_unicode('a', True)
    time.sleep(0.02)
    send_unicode('a', False)
    time.sleep(0.05)
    
    # Release Shift
    send_key_vk(0x10, False)
    time.sleep(0.5)
    
    # Press Ctrl+S
    send_key_vk(0x11, True) # Ctrl
    time.sleep(0.05)
    send_key_vk(0x53, True) # S
    time.sleep(0.05)
    send_key_vk(0x53, False)
    time.sleep(0.05)
    send_key_vk(0x11, False)
    time.sleep(1.0) # Wait for save dialog
    
    # Type filename
    for char in test_txt:
        send_unicode(char, True)
        time.sleep(0.02)
        send_unicode(char, False)
        time.sleep(0.02)
        
    time.sleep(0.5)
    
    # Press Enter
    send_key_vk(0x0D, True) # Enter
    time.sleep(0.05)
    send_key_vk(0x0D, False)
    time.sleep(1.5)
    
    proc.terminate()
    
    if os.path.exists(test_txt):
        with open(test_txt, "r") as f:
            print("File content read successfully:", repr(f.read()))
        os.remove(test_txt)
    else:
        print("Error: File was not created!")
