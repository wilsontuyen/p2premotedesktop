import ctypes
import time
import subprocess
import os

# Ctypes definitions for SendInput API
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

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

def send_scancode(vk, pressed):
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    flags = KEYEVENTF_SCANCODE
    if not pressed:
        flags |= KEYEVENTF_KEYUP
    scan_code = ctypes.windll.user32.MapVirtualKeyW(vk, 0) & 0xFF
    inp.union.ki = KEYBDINPUT(0, scan_code, flags, 0, None)
    res = ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    return res > 0

if __name__ == "__main__":
    if os.path.exists("a.txt"):
        os.remove("a.txt")
        
    proc = subprocess.Popen(["notepad.exe"])
    time.sleep(1.5) # Wait for Notepad to open
    
    # 1. Type "a" (using scan code)
    send_scancode(0x41, True)
    time.sleep(0.05)
    send_scancode(0x41, False)
    time.sleep(0.5)
    
    # 2. Press Ctrl+S (using scan code)
    send_scancode(0x11, True) # Ctrl
    time.sleep(0.05)
    send_scancode(0x53, True) # S
    time.sleep(0.05)
    send_scancode(0x53, False)
    time.sleep(0.05)
    send_scancode(0x11, False)
    time.sleep(1.0) # Wait for save dialog
    
    # 3. Type "a.txt" (using scan code)
    # 'a' (0x41), '.' (0xBE), 't' (0x54), 'x' (0x58), 't' (0x54)
    vks = [0x41, 0xBE, 0x54, 0x58, 0x54]
    for vk in vks:
        send_scancode(vk, True)
        time.sleep(0.02)
        send_scancode(vk, False)
        time.sleep(0.02)
        
    time.sleep(0.5)
    
    # 4. Press Enter to confirm saving (using scan code)
    send_scancode(0x0D, True) # Enter
    time.sleep(0.05)
    send_scancode(0x0D, False)
    time.sleep(1.5) # Wait for Notepad to save the file
    
    proc.terminate()
    
    # Check if file exists and read it
    if os.path.exists("a.txt"):
        with open("a.txt", "r") as f:
            print("Scancode file content read successfully:", repr(f.read()))
        os.remove("a.txt")
    else:
        print("Error: Scancode file was not created!")
