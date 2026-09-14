"""
Linux input injection using /dev/uinput (kernel-level virtual input device).
Works everywhere including GDM lock screen, login screen, and console TTY.
Falls back to pynput if /dev/uinput is not accessible (e.g. running as non-root user).

Why uinput instead of pynput/Xlib?
- pynput uses XTest extension to inject keyboard events
- GDM lock screen BLOCKS XTest keyboard injection for security
- /dev/uinput creates a kernel-level virtual device that bypasses X11 entirely
- Similar to how Windows service uses SendInput at Secure Desktop
"""

import os
import sys
import struct
import threading
import time

# ============================================================================
# uinput ioctl constants (computed from _IO/_IOW macros)
# ============================================================================
UI_DEV_CREATE  = 0x5501       # _IO('U', 1)
UI_DEV_DESTROY = 0x5502       # _IO('U', 2)
UI_DEV_SETUP   = 0x405c5503   # _IOW('U', 3, sizeof(uinput_setup)=92)
UI_ABS_SETUP   = 0x401c5504   # _IOW('U', 4, sizeof(uinput_abs_setup)=28)
UI_SET_EVBIT   = 0x40045564   # _IOW('U', 100, int)
UI_SET_KEYBIT  = 0x40045565   # _IOW('U', 101, int)
UI_SET_RELBIT  = 0x40045566   # _IOW('U', 102, int)
UI_SET_ABSBIT  = 0x40045567   # _IOW('U', 103, int)

# ============================================================================
# Linux input event constants
# ============================================================================
# Event types
EV_SYN = 0x00
EV_KEY = 0x01
EV_REL = 0x02
EV_ABS = 0x03

SYN_REPORT = 0x00

# Relative axes (for scroll)
REL_X      = 0x00
REL_Y      = 0x01
REL_HWHEEL = 0x06
REL_WHEEL  = 0x08

# Absolute axes (for mouse positioning)
ABS_X = 0x00
ABS_Y = 0x01

# Absolute axis range (fixed, coordinates are scaled to this range)
ABS_MAX_VAL = 65535

# Mouse buttons
BTN_LEFT   = 0x110
BTN_RIGHT  = 0x111
BTN_MIDDLE = 0x112

# Bus type for virtual device
BUS_VIRTUAL = 0x06

# ============================================================================
# Linux key codes (from linux/input-event-codes.h)
# ============================================================================
KEY_ESC         = 1
KEY_1           = 2
KEY_2           = 3
KEY_3           = 4
KEY_4           = 5
KEY_5           = 6
KEY_6           = 7
KEY_7           = 8
KEY_8           = 9
KEY_9           = 10
KEY_0           = 11
KEY_MINUS       = 12
KEY_EQUAL       = 13
KEY_BACKSPACE   = 14
KEY_TAB         = 15
KEY_Q           = 16
KEY_W           = 17
KEY_E           = 18
KEY_R           = 19
KEY_T           = 20
KEY_Y           = 21
KEY_U           = 22
KEY_I           = 23
KEY_O           = 24
KEY_P           = 25
KEY_LEFTBRACE   = 26
KEY_RIGHTBRACE  = 27
KEY_ENTER       = 28
KEY_LEFTCTRL    = 29
KEY_A           = 30
KEY_S           = 31
KEY_D           = 32
KEY_F           = 33
KEY_G           = 34
KEY_H           = 35
KEY_J           = 36
KEY_K           = 37
KEY_L           = 38
KEY_SEMICOLON   = 39
KEY_APOSTROPHE  = 40
KEY_GRAVE       = 41
KEY_LEFTSHIFT   = 42
KEY_BACKSLASH   = 43
KEY_Z           = 44
KEY_X           = 45
KEY_C           = 46
KEY_V           = 47
KEY_B           = 48
KEY_N           = 49
KEY_M           = 50
KEY_COMMA       = 51
KEY_DOT         = 52
KEY_SLASH       = 53
KEY_RIGHTSHIFT  = 54
KEY_KPASTERISK  = 55
KEY_LEFTALT     = 56
KEY_SPACE       = 57
KEY_CAPSLOCK    = 58
KEY_F1          = 59
KEY_F2          = 60
KEY_F3          = 61
KEY_F4          = 62
KEY_F5          = 63
KEY_F6          = 64
KEY_F7          = 65
KEY_F8          = 66
KEY_F9          = 67
KEY_F10         = 68
KEY_NUMLOCK     = 69
KEY_SCROLLLOCK  = 70
KEY_KP7         = 71
KEY_KP8         = 72
KEY_KP9         = 73
KEY_KPMINUS     = 74
KEY_KP4         = 75
KEY_KP5         = 76
KEY_KP6         = 77
KEY_KPPLUS      = 78
KEY_KP1         = 79
KEY_KP2         = 80
KEY_KP3         = 81
KEY_KP0         = 82
KEY_KPDOT       = 83
KEY_F11         = 87
KEY_F12         = 88
KEY_KPENTER     = 96
KEY_RIGHTCTRL   = 97
KEY_KPSLASH     = 98
KEY_SYSRQ       = 99
KEY_KPEQUAL     = 117
KEY_RIGHTALT    = 100
KEY_HOME        = 102
KEY_UP          = 103
KEY_PAGEUP      = 104
KEY_LEFT        = 105
KEY_RIGHT       = 106
KEY_END         = 107
KEY_DOWN        = 108
KEY_PAGEDOWN    = 109
KEY_INSERT      = 110
KEY_DELETE      = 111
KEY_PAUSE       = 119
KEY_LEFTMETA    = 125
KEY_RIGHTMETA   = 126
KEY_COMPOSE     = 127   # Menu/Context key

# Max key code to register with uinput (covers all standard keys)
_KEY_MAX = 256

# ============================================================================
# Key name -> Linux keycode mappings
# ============================================================================

# Special / named keys (from Pygame key names used by the viewer)
_name_to_keycode = {
    # Whitespace / editing
    'space':        KEY_SPACE,
    'enter':        KEY_ENTER,
    'return':       KEY_ENTER,
    'escape':       KEY_ESC,
    'backspace':    KEY_BACKSPACE,
    'tab':          KEY_TAB,
    'delete':       KEY_DELETE,
    'insert':       KEY_INSERT,

    # Modifiers
    'left shift':   KEY_LEFTSHIFT,
    'right shift':  KEY_RIGHTSHIFT,
    'left ctrl':    KEY_LEFTCTRL,
    'right ctrl':   KEY_RIGHTCTRL,
    'left alt':     KEY_LEFTALT,
    'right alt':    KEY_RIGHTALT,
    'left meta':    KEY_LEFTMETA,
    'right meta':   KEY_RIGHTMETA,
    'left windows': KEY_LEFTMETA,
    'right windows':KEY_RIGHTMETA,
    'left super':   KEY_LEFTMETA,
    'right super':  KEY_RIGHTMETA,

    # Arrow keys
    'up':           KEY_UP,
    'down':         KEY_DOWN,
    'left':         KEY_LEFT,
    'right':        KEY_RIGHT,

    # Navigation
    'home':         KEY_HOME,
    'end':          KEY_END,
    'page up':      KEY_PAGEUP,
    'page down':    KEY_PAGEDOWN,

    # Lock keys
    'caps lock':    KEY_CAPSLOCK,
    'capslock':     KEY_CAPSLOCK,
    'num lock':     KEY_NUMLOCK,
    'numlock':      KEY_NUMLOCK,
    'scroll lock':  KEY_SCROLLLOCK,
    'scrolllock':   KEY_SCROLLLOCK,

    # Function keys
    'f1': KEY_F1, 'f2': KEY_F2, 'f3': KEY_F3, 'f4': KEY_F4,
    'f5': KEY_F5, 'f6': KEY_F6, 'f7': KEY_F7, 'f8': KEY_F8,
    'f9': KEY_F9, 'f10': KEY_F10, 'f11': KEY_F11, 'f12': KEY_F12,

    # Misc
    'menu':         KEY_COMPOSE,
    'print screen': KEY_SYSRQ,
    'printscreen':  KEY_SYSRQ,
    'sys req':      KEY_SYSRQ,
    'pause':        KEY_PAUSE,
    'break':        KEY_PAUSE,

    # Numpad (104-key)
    '[0]': KEY_KP0, '[1]': KEY_KP1, '[2]': KEY_KP2, '[3]': KEY_KP3,
    '[4]': KEY_KP4, '[5]': KEY_KP5, '[6]': KEY_KP6, '[7]': KEY_KP7,
    '[8]': KEY_KP8, '[9]': KEY_KP9,
    '[.]': KEY_KPDOT, '[/]': KEY_KPSLASH, '[*]': KEY_KPASTERISK,
    '[-]': KEY_KPMINUS, '[+]': KEY_KPPLUS,
    'keypad 0': KEY_KP0, 'keypad 1': KEY_KP1, 'keypad 2': KEY_KP2,
    'keypad 3': KEY_KP3, 'keypad 4': KEY_KP4, 'keypad 5': KEY_KP5,
    'keypad 6': KEY_KP6, 'keypad 7': KEY_KP7, 'keypad 8': KEY_KP8,
    'keypad 9': KEY_KP9,
    'keypad .': KEY_KPDOT, 'keypad /': KEY_KPSLASH, 'keypad *': KEY_KPASTERISK,
    'keypad -': KEY_KPMINUS, 'keypad +': KEY_KPPLUS,
    'keypad enter': KEY_KPENTER,
    'keypad equals': KEY_KPEQUAL, 'keypad =': KEY_KPEQUAL,
}

# Single character -> keycode (lowercase only, for standard US keyboard layout)
_char_to_keycode = {
    'a': 30, 'b': 48, 'c': 46, 'd': 32, 'e': 18, 'f': 33, 'g': 34,
    'h': 35, 'i': 23, 'j': 36, 'k': 37, 'l': 38, 'm': 50, 'n': 49,
    'o': 24, 'p': 25, 'q': 16, 'r': 19, 's': 31, 't': 20, 'u': 22,
    'v': 47, 'w': 17, 'x': 45, 'y': 21, 'z': 44,
    '1': 2, '2': 3, '3': 4, '4': 5, '5': 6, '6': 7, '7': 8, '8': 9,
    '9': 10, '0': 11,
    '-': 12, '=': 13, '[': 26, ']': 27, '\\': 43, ';': 39, "'": 40,
    '`': 41, ',': 51, '.': 52, '/': 53, ' ': 57,
}

# Shifted characters -> base keycode (shift is assumed to already be held)
_shifted_char_to_keycode = {
    '!': 2, '@': 3, '#': 4, '$': 5, '%': 6, '^': 7, '&': 8, '*': 9,
    '(': 10, ')': 11, '_': 12, '+': 13, '{': 26, '}': 27, '|': 43,
    ':': 39, '"': 40, '~': 41, '<': 51, '>': 52, '?': 53,
}

# Mouse button name -> button code
_button_map = {
    'left':   BTN_LEFT,
    'right':  BTN_RIGHT,
    'middle': BTN_MIDDLE,
}


# ============================================================================
# UInput Device Class
# ============================================================================

class UInputDevice:
    """Creates a kernel-level virtual input device via /dev/uinput.
    Supports keyboard, mouse absolute positioning, and scroll wheel.
    Works at GDM lock screen, login screen, and console TTY."""

    def __init__(self):
        self._fd = None
        self._screen_w = 1920
        self._screen_h = 1080
        self._lock = threading.Lock()
        self._detect_resolution()
        self._create_device()

    def _detect_resolution(self):
        """Detect screen resolution for absolute mouse positioning."""
        # Try mss (already a project dependency)
        try:
            import mss
            with mss.mss() as sct:
                m = sct.monitors[0]  # Combined virtual screen
                self._screen_w = m['width']
                self._screen_h = m['height']
                return
        except Exception:
            pass

        # Try xrandr
        try:
            import subprocess
            out = subprocess.check_output(
                ['xrandr', '--current'],
                stderr=subprocess.DEVNULL, timeout=3
            ).decode()
            for line in out.split('\n'):
                if ' connected' in line:
                    # Look for resolution like "1920x1080+0+0"
                    for part in line.split():
                        if 'x' in part and '+' in part:
                            res = part.split('+')[0]
                            w, h = res.split('x')
                            self._screen_w = int(w)
                            self._screen_h = int(h)
                            return
        except Exception:
            pass

        # Default 1920x1080

    def _create_device(self):
        """Create the uinput virtual device."""
        import fcntl

        self._fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)

        # Enable event types
        fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_KEY)
        fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_REL)
        fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_ABS)
        fcntl.ioctl(self._fd, UI_SET_EVBIT, EV_SYN)

        # Enable all standard keyboard keys
        for code in range(_KEY_MAX):
            try:
                fcntl.ioctl(self._fd, UI_SET_KEYBIT, code)
            except OSError:
                pass

        # Enable mouse buttons
        for btn in (BTN_LEFT, BTN_RIGHT, BTN_MIDDLE):
            fcntl.ioctl(self._fd, UI_SET_KEYBIT, btn)

        # Enable relative axes (scroll wheel)
        fcntl.ioctl(self._fd, UI_SET_RELBIT, REL_WHEEL)
        fcntl.ioctl(self._fd, UI_SET_RELBIT, REL_HWHEEL)

        # Enable absolute axes (mouse positioning)
        fcntl.ioctl(self._fd, UI_SET_ABSBIT, ABS_X)
        fcntl.ioctl(self._fd, UI_SET_ABSBIT, ABS_Y)

        # Configure ABS axes: struct uinput_abs_setup { u16 code; u16 pad; input_absinfo(6xi32) }
        # Format: H=code, xx=padding, 6i=value,minimum,maximum,fuzz,flat,resolution
        abs_x = struct.pack('=Hxx6i', ABS_X, 0, 0, ABS_MAX_VAL, 0, 0, 0)
        fcntl.ioctl(self._fd, UI_ABS_SETUP, abs_x)

        abs_y = struct.pack('=Hxx6i', ABS_Y, 0, 0, ABS_MAX_VAL, 0, 0, 0)
        fcntl.ioctl(self._fd, UI_ABS_SETUP, abs_y)

        # Setup device identity: struct uinput_setup { input_id(4xH), name(80s), ff_effects(I) }
        name = b'EasyRemoteDesktop Virtual Input'
        setup = struct.pack('=4H80sI',
            BUS_VIRTUAL, 0x1234, 0x5678, 1,    # bustype, vendor, product, version
            name.ljust(80, b'\0'),               # name padded to 80 chars
            0                                    # ff_effects_max
        )
        fcntl.ioctl(self._fd, UI_DEV_SETUP, setup)

        # Create the device
        fcntl.ioctl(self._fd, UI_DEV_CREATE)

        # Small delay for the kernel to register the device
        time.sleep(0.1)

        print(f"[LinuxInput/uinput] Virtual input device created (screen: {self._screen_w}x{self._screen_h})")

    def _write_event(self, ev_type, code, value):
        """Write a single input event to /dev/uinput.
        struct input_event { timeval(ll), u16 type, u16 code, s32 value }"""
        event = struct.pack('@llHHi', 0, 0, ev_type, code, value)
        os.write(self._fd, event)

    def _syn(self):
        """Send SYN_REPORT to flush the event."""
        self._write_event(EV_SYN, SYN_REPORT, 0)

    def key_event(self, keycode, pressed):
        """Send a keyboard key press (1) or release (0) event."""
        with self._lock:
            self._write_event(EV_KEY, keycode, 1 if pressed else 0)
            self._syn()

    def mouse_move_abs(self, x, y):
        """Move mouse cursor to absolute screen position (x, y in pixels)."""
        # Scale pixel coordinates to the ABS range [0, ABS_MAX_VAL]
        abs_x = min(ABS_MAX_VAL, max(0, x * ABS_MAX_VAL // max(1, self._screen_w)))
        abs_y = min(ABS_MAX_VAL, max(0, y * ABS_MAX_VAL // max(1, self._screen_h)))
        with self._lock:
            self._write_event(EV_ABS, ABS_X, abs_x)
            self._write_event(EV_ABS, ABS_Y, abs_y)
            self._syn()

    def mouse_button(self, button_code, pressed):
        """Press or release a mouse button."""
        with self._lock:
            self._write_event(EV_KEY, button_code, 1 if pressed else 0)
            self._syn()

    def mouse_scroll(self, dx, dy):
        """Scroll the mouse wheel. dy>0 = up, dy<0 = down."""
        with self._lock:
            if dy != 0:
                self._write_event(EV_REL, REL_WHEEL, int(dy))
            if dx != 0:
                self._write_event(EV_REL, REL_HWHEEL, int(dx))
            self._syn()

    def update_resolution(self, width, height):
        """Update the screen resolution used for coordinate scaling.
        No device recreation needed - only the scaling factor changes."""
        self._screen_w = width
        self._screen_h = height

    def close(self):
        """Destroy the virtual device and close the fd."""
        if self._fd is not None:
            try:
                import fcntl
                fcntl.ioctl(self._fd, UI_DEV_DESTROY)
            except Exception:
                pass
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None

    def __del__(self):
        self.close()


# ============================================================================
# Module-level state & lazy initialization
# ============================================================================

# Dummy constants for cross-platform compatibility with existing code
INPUT = None
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 4
KEYEVENTF_KEYUP = 2

# Track remote modifier key state (mirrors windows_input.py behavior)
_remote_modifier_keys = set()
_remote_modifier_names = {
    'left ctrl', 'right ctrl', 'left alt', 'right alt',
    'left meta', 'right meta', 'left windows', 'right windows',
    'left super', 'right super'
}

# uinput device (lazy init)
_uinput_dev = None
_uinput_init_lock = threading.Lock()
_use_uinput = True

# pynput fallback controllers (lazy init)
_pynput_mouse = None
_pynput_keyboard = None
_pynput_vk_map = None


def _get_uinput():
    """Get or create the uinput device. Returns None if unavailable."""
    global _uinput_dev, _use_uinput
    if not _use_uinput:
        return None
    if _uinput_dev is not None:
        return _uinput_dev
    with _uinput_init_lock:
        if _uinput_dev is not None:
            return _uinput_dev
        if not _use_uinput:
            return None
        try:
            _uinput_dev = UInputDevice()
            print("[LinuxInput] Using /dev/uinput for input injection (works at GDM lock screen)")
            return _uinput_dev
        except Exception as e:
            print(f"[LinuxInput] /dev/uinput not available ({e}), falling back to pynput")
            print("[LinuxInput] WARNING: Keyboard input will NOT work at GDM lock screen with pynput fallback")
            _use_uinput = False
            return None


def _init_pynput():
    """Initialize pynput controllers for fallback."""
    global _pynput_mouse, _pynput_keyboard, _pynput_vk_map
    if _pynput_keyboard is not None:
        return

    from pynput.mouse import Controller as MouseController, Button
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
    print("[LinuxInput] pynput fallback initialized")


def _resolve_keycode(key_name):
    """Resolve a key name string to a Linux keycode. Returns None if unresolvable."""
    # Check named keys first
    kc = _name_to_keycode.get(key_name)
    if kc is not None:
        return kc

    # Single character
    if len(key_name) == 1:
        ch = key_name.lower()
        kc = _char_to_keycode.get(ch)
        if kc is not None:
            return kc
        # Try shifted chars (e.g. '!' -> KEY_1)
        kc = _shifted_char_to_keycode.get(key_name)
        if kc is not None:
            return kc

    return None


# ============================================================================
# Public API (matches the interface expected by host.py / input_simulator.py)
# ============================================================================

def send_input_keyboard_event(key_name, pressed):
    """Inject a keyboard key press/release event."""
    try:
        # Track modifier state (mirrors windows_input.py)
        if key_name in _remote_modifier_names:
            if pressed:
                _remote_modifier_keys.add(key_name)
            else:
                _remote_modifier_keys.discard(key_name)

        dev = _get_uinput()
        if dev is not None:
            keycode = _resolve_keycode(key_name)
            if keycode is not None:
                dev.key_event(keycode, pressed)
            else:
                print(f"[LinuxInput/uinput] Unknown key: '{key_name}'")
        else:
            # Fallback: pynput (won't work at lock screen)
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
        print(f"[LinuxInput] Keyboard injection failed: {e}")


def send_input_mouse_click(button_name, pressed):
    """Inject a mouse button press/release event."""
    try:
        dev = _get_uinput()
        if dev is not None:
            btn_code = _button_map.get(button_name)
            if btn_code is not None:
                dev.mouse_button(btn_code, pressed)
        else:
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
        print(f"[LinuxInput] Mouse click injection failed: {e}")


def send_input_mouse_click_at(x, y, button_name, pressed):
    send_input_mouse_move(x, y)
    send_input_mouse_click(button_name, pressed)


def send_input_mouse_scroll(dx, dy):
    """Inject a mouse scroll event."""
    try:
        dev = _get_uinput()
        if dev is not None:
            dev.mouse_scroll(dx, dy)
        else:
            _init_pynput()
            _pynput_mouse.scroll(dx, dy)
    except Exception as e:
        print(f"[LinuxInput] Mouse scroll injection failed: {e}")


def send_input_mouse_move(x, y):
    """Move mouse cursor to absolute pixel position."""
    try:
        dev = _get_uinput()
        if dev is not None:
            dev.mouse_move_abs(x, y)
        else:
            _init_pynput()
            _pynput_mouse.position = (x, y)
    except Exception as e:
        print(f"[LinuxInput] Mouse move injection failed: {e}")
