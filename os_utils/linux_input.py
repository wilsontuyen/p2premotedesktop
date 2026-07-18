from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key

mouse = MouseController()
keyboard = KeyboardController()

# Dummy constants for cross-platform compatibility with existing code
INPUT = None
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 4
KEYEVENTF_KEYUP = 2
_remote_modifier_keys = set()

vk_map = {
    'space': Key.space,
    'enter': Key.enter,
    'return': Key.enter,
    'escape': Key.esc,
    'backspace': Key.backspace,
    'tab': Key.tab,
    'left shift': Key.shift,
    'right shift': Key.shift_r,
    'left ctrl': Key.ctrl,
    'right ctrl': Key.ctrl_r,
    'left alt': Key.alt,
    'right alt': Key.alt_gr,
    'up': Key.up,
    'down': Key.down,
    'left': Key.left,
    'right': Key.right,
    'caps lock': Key.caps_lock,
    'capslock': Key.caps_lock,
    'delete': Key.delete,
    'home': Key.home,
    'end': Key.end,
    'page up': Key.page_up,
    'page down': Key.page_down,
    'f1': Key.f1,
    'f2': Key.f2,
    'f3': Key.f3,
    'f4': Key.f4,
    'f5': Key.f5,
    'f6': Key.f6,
    'f7': Key.f7,
    'f8': Key.f8,
    'f9': Key.f9,
    'f10': Key.f10,
    'f11': Key.f11,
    'f12': Key.f12,
    'left meta': Key.cmd,
    'right meta': Key.cmd_r,
    'left windows': Key.cmd,
    'right windows': Key.cmd_r,
    'left super': Key.cmd,
    'right super': Key.cmd_r,
    'menu': Key.menu,
    'insert': Key.insert,
}

def send_input_keyboard_event(key_name, pressed):
    try:
        if key_name in vk_map:
            key = vk_map[key_name]
            if pressed:
                keyboard.press(key)
            else:
                keyboard.release(key)
        else:
            # Handle standard characters
            char = key_name
            if len(char) == 1:
                if pressed:
                    keyboard.press(char)
                else:
                    keyboard.release(char)
    except Exception as e:
        print(f"[LinuxInput] Keyboard injection failed: {e}")

def send_input_mouse_click(button_name, pressed):
    try:
        button = None
        if button_name == 'left':
            button = Button.left
        elif button_name == 'right':
            button = Button.right
        elif button_name == 'middle':
            button = Button.middle
            
        if button:
            if pressed:
                mouse.press(button)
            else:
                mouse.release(button)
    except Exception as e:
        print(f"[LinuxInput] Mouse click injection failed: {e}")

def send_input_mouse_scroll(dx, dy):
    try:
        # pynput scroll takes (dx, dy)
        mouse.scroll(dx, dy)
    except Exception as e:
        print(f"[LinuxInput] Mouse scroll injection failed: {e}")

def send_input_mouse_move(x, y):
    try:
        mouse.position = (x, y)
    except Exception as e:
        print(f"[LinuxInput] Mouse move injection failed: {e}")
