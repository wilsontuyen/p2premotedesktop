"""Canonical 104-key names from pygame/SDL constants (physical keys, not unicode)."""

import pygame

# pygame constant name -> protocol key name (host vk_map / linux keycodes)
_CONST_TO_NAME = {
    # Function / lock / sys
    "K_ESCAPE": "escape",
    "K_F1": "f1", "K_F2": "f2", "K_F3": "f3", "K_F4": "f4",
    "K_F5": "f5", "K_F6": "f6", "K_F7": "f7", "K_F8": "f8",
    "K_F9": "f9", "K_F10": "f10", "K_F11": "f11", "K_F12": "f12",
    "K_PRINT": "print screen",
    "K_PRINTSCREEN": "print screen",
    "K_SYSREQ": "print screen",
    "K_SCROLLLOCK": "scroll lock",
    "K_SCROLLOCK": "scroll lock",
    "K_PAUSE": "pause",
    "K_BREAK": "pause",
    "K_NUMLOCK": "numlock",
    "K_NUMLOCKCLEAR": "numlock",
    "K_CAPSLOCK": "caps lock",
    # Editing / nav
    "K_BACKSPACE": "backspace",
    "K_TAB": "tab",
    "K_RETURN": "enter",
    "K_SPACE": "space",
    "K_INSERT": "insert",
    "K_DELETE": "delete",
    "K_HOME": "home",
    "K_END": "end",
    "K_PAGEUP": "page up",
    "K_PAGEDOWN": "page down",
    "K_UP": "up",
    "K_DOWN": "down",
    "K_LEFT": "left",
    "K_RIGHT": "right",
    # Modifiers
    "K_LSHIFT": "left shift",
    "K_RSHIFT": "right shift",
    "K_LCTRL": "left ctrl",
    "K_RCTRL": "right ctrl",
    "K_LALT": "left alt",
    "K_RALT": "right alt",
    "K_MODE": "right alt",  # AltGr
    "K_LGUI": "left windows",
    "K_RGUI": "right windows",
    "K_LMETA": "left windows",
    "K_RMETA": "right windows",
    "K_LSUPER": "left windows",
    "K_RSUPER": "right windows",
    "K_MENU": "menu",
    # Main OEM (ANSI 104)
    "K_BACKQUOTE": "`",
    "K_MINUS": "-",
    "K_EQUALS": "=",
    "K_LEFTBRACKET": "[",
    "K_RIGHTBRACKET": "]",
    "K_BACKSLASH": "\\",
    "K_SEMICOLON": ";",
    "K_QUOTE": "'",
    "K_COMMA": ",",
    "K_PERIOD": ".",
    "K_SLASH": "/",
    # Numpad — never send unicode '*' '+' etc. (VkKeyScan maps * → 8)
    "K_KP0": "[0]", "K_KP_0": "[0]",
    "K_KP1": "[1]", "K_KP_1": "[1]",
    "K_KP2": "[2]", "K_KP_2": "[2]",
    "K_KP3": "[3]", "K_KP_3": "[3]",
    "K_KP4": "[4]", "K_KP_4": "[4]",
    "K_KP5": "[5]", "K_KP_5": "[5]",
    "K_KP6": "[6]", "K_KP_6": "[6]",
    "K_KP7": "[7]", "K_KP_7": "[7]",
    "K_KP8": "[8]", "K_KP_8": "[8]",
    "K_KP9": "[9]", "K_KP_9": "[9]",
    "K_KP_PERIOD": "[.]",
    "K_KP_DIVIDE": "[/]",
    "K_KP_MULTIPLY": "[*]",
    "K_KP_MINUS": "[-]",
    "K_KP_PLUS": "[+]",
    "K_KP_ENTER": "keypad enter",
    "K_KP_EQUALS": "keypad equals",
    "K_CLEAR": "clear",
}

_PYGAME_CODE_TO_NAME = None


def _code_map():
    global _PYGAME_CODE_TO_NAME
    if _PYGAME_CODE_TO_NAME is None:
        m = {}
        for const, name in _CONST_TO_NAME.items():
            code = getattr(pygame, const, None)
            if isinstance(code, int):
                m[code] = name
        for ch in "abcdefghijklmnopqrstuvwxyz":
            code = getattr(pygame, "K_" + ch, None)
            if isinstance(code, int):
                m[code] = ch
        for d in "0123456789":
            code = getattr(pygame, "K_" + d, None)
            if isinstance(code, int):
                m[code] = d
        _PYGAME_CODE_TO_NAME = m
    return _PYGAME_CODE_TO_NAME


def pygame_key_canonical_name(event):
    """Physical 104-key name. Do not use event.unicode (keypad * would become 8)."""
    name = _code_map().get(event.key)
    if name:
        return name
    raw = pygame.key.name(event.key)
    if raw:
        return raw.lower()
    return ""
