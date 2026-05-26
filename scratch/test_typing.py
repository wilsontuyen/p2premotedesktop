import ctypes
import time
import subprocess
import os

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

def send_input_keyboard_event(key_name, pressed):
    try:
        vk = None
        # Simplified map for testing
        vk_map = {
            'enter': 0x0D,
            'ctrl': 0x11,
            's': 0x53
        }
        if key_name in vk_map:
            vk = vk_map[key_name]
        elif len(key_name) == 1:
            res_vk = ctypes.windll.user32.VkKeyScanW(ord(key_name))
            if res_vk == -1 or res_vk == 0xFFFF:
                inp = INPUT()
                inp.type = INPUT_KEYBOARD
                flags = KEYEVENTF_UNICODE
                if not pressed:
                    flags |= KEYEVENTF_KEYUP
                inp.union.ki = KEYBDINPUT(0, ord(key_name), flags, 0, None)
                res = ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
                return res > 0
            else:
                vk = res_vk & 0xFF
            
        if vk is not None:
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            flags = 0
            if not pressed:
                flags |= KEYEVENTF_KEYUP
            scan_code = ctypes.windll.user32.MapVirtualKeyW(vk, 0) & 0xFF
            inp.union.ki = KEYBDINPUT(vk, scan_code, flags, 0, None)
            res = ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            return res > 0
    except Exception as e:
        print(f"Error: {e}")
    return False

if __name__ == "__main__":
    test_txt = os.path.abspath("scratch/test_out.txt")
    if os.path.exists(test_txt):
        os.remove(test_txt)
        
    proc = subprocess.Popen(["notepad.exe"])
    time.sleep(1.5) # Wait for Notepad to open
    
    # 1. Type "a" (using our VkKeyScanW path)
    send_input_keyboard_event('a', True)
    time.sleep(0.05)
    send_input_keyboard_event('a', False)
    time.sleep(0.5)
    
    # 2. Press Ctrl+S
    send_input_keyboard_event('ctrl', True)
    time.sleep(0.05)
    send_input_keyboard_event('s', True)
    time.sleep(0.05)
    send_input_keyboard_event('s', False)
    time.sleep(0.05)
    send_input_keyboard_event('ctrl', False)
    time.sleep(1.0) # Wait for save dialog
    
    # 3. Type the filename and path: "test_out.txt"
    # Wait, instead of typing full path which could be layout dependent, let's type standard keys using send_input_keyboard_event
    for char in test_txt:
        send_input_keyboard_event(char, True)
        time.sleep(0.02)
        send_input_keyboard_event(char, False)
        time.sleep(0.02)
        
    time.sleep(0.5)
    
    # 4. Press Enter to confirm saving
    send_input_keyboard_event('enter', True)
    time.sleep(0.05)
    send_input_keyboard_event('enter', False)
    time.sleep(1.5) # Wait for Notepad to save the file
    
    proc.terminate()
    
    # Check if file exists and read it
    if os.path.exists(test_txt):
        with open(test_txt, "r") as f:
            print("File content read successfully:", repr(f.read()))
    else:
        print("Error: File was not created!")
