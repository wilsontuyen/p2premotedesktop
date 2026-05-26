import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32
MN_GETHMENU = 0x01E1

def get_menu_item_text():
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    hwnd = user32.WindowFromPoint(pt)
    
    # Get class name
    class_name = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_name, 256)
    
    if class_name.value == "#32768":
        hmenu = user32.SendMessageW(hwnd, MN_GETHMENU, 0, 0)
        if hmenu:
            count = user32.GetMenuItemCount(hmenu)
            print(f"Menu count: {count}")
            # MenuItemFromPoint!
            res = user32.MenuItemFromPoint(hwnd, hmenu, pt)
            if res >= 0:
                buf = ctypes.create_unicode_buffer(256)
                user32.GetMenuStringW(hmenu, res, buf, 256, 0x0400) # MF_BYPOSITION = 0x0400
                print(f"Item text: {buf.value}")

while True:
    get_menu_item_text()
    time.sleep(0.5)
