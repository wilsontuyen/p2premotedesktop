import threading

INPUT = None
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 4
KEYEVENTF_KEYUP = 2

_remote_modifier_keys = set()
_remote_modifier_names = {
    'left ctrl', 'right ctrl', 'left alt', 'right alt',
    'left meta', 'right meta', 'left windows', 'right windows',
    'left super', 'right super'
}

_pynput_mouse = None
_pynput_keyboard = None
_pynput_vk_map = None

def _init_pynput():
    global _pynput_mouse, _pynput_keyboard, _pynput_vk_map
    if _pynput_keyboard is not None:
        return

    from pynput.mouse import Controller as MouseController
    from pynput.keyboard import Controller as KeyboardController, Key

    _pynput_mouse = MouseController()
    _pynput_keyboard = KeyboardController()
    _pynput_vk_map = {
        'space': Key.space, 'enter': Key.enter, 'return': Key.enter,
        'escape': Key.esc, 'backspace': Key.backspace, 'tab': Key.tab,
        'left shift': Key.shift, 'right shift': Key.shift_r,
        'left ctrl': Key.ctrl, 'right ctrl': Key.ctrl_r,
        'left alt': Key.alt, 'right alt': Key.alt_gr,
        'up': Key.up, 'down': Key.down, 'left': Key.left, 'right': Key.right,
        'caps lock': Key.caps_lock, 'capslock': Key.caps_lock,
        'delete': Key.delete, 'home': Key.home, 'end': Key.end,
        'page up': Key.page_up, 'page down': Key.page_down,
        'f1': Key.f1, 'f2': Key.f2, 'f3': Key.f3, 'f4': Key.f4,
        'f5': Key.f5, 'f6': Key.f6, 'f7': Key.f7, 'f8': Key.f8,
        'f9': Key.f9, 'f10': Key.f10, 'f11': Key.f11, 'f12': Key.f12,
        'left meta': Key.cmd, 'right meta': Key.cmd_r,
        'left windows': Key.cmd, 'right windows': Key.cmd_r,
        'left super': Key.cmd, 'right super': Key.cmd_r,
        'menu': Key.menu, 'insert': Key.insert,
    }
    print("[MacInput] pynput initialized")

def send_input_keyboard_event(key_name, pressed):
    try:
        if key_name in _remote_modifier_names:
            if pressed:
                _remote_modifier_keys.add(key_name)
            else:
                _remote_modifier_keys.discard(key_name)

        _init_pynput()
        if key_name in _pynput_vk_map:
            key = _pynput_vk_map[key_name]
            if pressed:
                _pynput_keyboard.press(key)
            else:
                _pynput_keyboard.release(key)
        elif len(key_name) == 1:
            if pressed:
                _pynput_keyboard.press(key_name)
            else:
                _pynput_keyboard.release(key_name)
    except Exception as e:
        print(f"[MacInput] Keyboard injection failed: {e}")

def send_input_mouse_click(button_name, pressed):
    try:
        _init_pynput()
        from pynput.mouse import Button
        btn_map = {'left': Button.left, 'right': Button.right, 'middle': Button.middle}
        btn = btn_map.get(button_name)
        if btn:
            if pressed:
                _pynput_mouse.press(btn)
            else:
                _pynput_mouse.release(btn)
    except Exception as e:
        print(f"[MacInput] Mouse click injection failed: {e}")

def send_input_mouse_scroll(dx, dy):
    try:
        _init_pynput()
        _pynput_mouse.scroll(dx, dy)
    except Exception as e:
        print(f"[MacInput] Mouse scroll injection failed: {e}")

def send_input_mouse_move(x, y):
    try:
        _init_pynput()
        _pynput_mouse.position = (x, y)
    except Exception as e:
        print(f"[MacInput] Mouse move injection failed: {e}")
