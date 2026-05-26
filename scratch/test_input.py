import ctypes
import time
import subprocess

# Ctypes definitions for SendInput API
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
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

def send_input_key(vk, pressed):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    flags = 0
    if not pressed:
        flags |= KEYEVENTF_KEYUP
    scan_code = ctypes.windll.user32.MapVirtualKeyW(vk, 0) & 0xFF
    inp.union.ki = KEYBDINPUT(vk, scan_code, flags, 0, None)
    res = ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    return res > 0

def send_input_unicode(char, pressed):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    flags = KEYEVENTF_UNICODE
    if not pressed:
        flags |= KEYEVENTF_KEYUP
    inp.union.ki = KEYBDINPUT(0, ord(char), flags, 0, None)
    res = ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    return res > 0

if __name__ == "__main__":
    # Open Notepad to type into
    proc = subprocess.Popen(["notepad.exe"])
    time.sleep(1.0) # Wait for Notepad to open and focus
    
    print("Testing send_input_key for 'a'...")
    # 'A' key vk is 0x41
    send_input_key(0x41, True)
    time.sleep(0.05)
    send_input_key(0x41, False)
    
    time.sleep(0.5)
    
    print("Testing send_input_unicode for 'b'...")
    send_input_unicode('b', True)
    time.sleep(0.05)
    send_input_unicode('b', False)
    
    time.sleep(1.0)
    proc.terminate()
