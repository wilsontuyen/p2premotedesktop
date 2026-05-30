import ctypes
from ctypes import wintypes
import time

user32 = ctypes.windll.user32

def test_menu_item():
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    hwnd = user32.WindowFromPoint(pt)
    
    class_name = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_name, 256)
    
    if class_name.value == "#32768":
        hmenu = user32.SendMessageW(hwnd, 0x01E1, 0, 0)
        if hmenu:
            pos = user32.MenuItemFromPoint(hwnd, hmenu, pt)
            if pos >= 0:
                class MENUITEMINFOW(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.UINT),
                        ("fMask", wintypes.UINT),
                        ("fType", wintypes.UINT),
                        ("fState", wintypes.UINT),
                        ("wID", wintypes.UINT),
                        ("hSubMenu", wintypes.HMENU),
                        ("hbmpChecked", wintypes.HBITMAP),
                        ("hbmpUnchecked", wintypes.HBITMAP),
                        ("dwItemData", wintypes.ULONG),
                        ("dwTypeData", wintypes.LPWSTR),
                        ("cch", wintypes.UINT),
                        ("hbmpItem", wintypes.HBITMAP),
                    ]
                mii = MENUITEMINFOW()
                mii.cbSize = ctypes.sizeof(MENUITEMINFOW)
                mii.fMask = 2 # MIIM_STRING
                mii.cch = 256
                buf = ctypes.create_unicode_buffer(256)
                mii.dwTypeData = ctypes.cast(buf, wintypes.LPWSTR)
                
                res = user32.GetMenuItemInfoW(hmenu, pos, True, ctypes.byref(mii))
                if res:
                    print("Clicked menu item:", buf.value)
                    return buf.value
    return None

if __name__ == "__main__":
    print("Waiting for 5 seconds... Please open a context menu and hover over Paste.")
    for i in range(5):
        time.sleep(1)
        print("Time:", i)
        test_menu_item()
