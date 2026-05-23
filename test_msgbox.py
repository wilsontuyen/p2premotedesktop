import ctypes
import time
import threading

def force_popup_test():
    print("Test will trigger in 5 seconds. Please switch to another app (like Chrome or Notepad) and cover this window completely!")
    time.sleep(5)
    
    MB_YESNO = 0x04
    MB_ICONQUESTION = 0x20
    MB_SYSTEMMODAL = 0x1000
    MB_SETFOREGROUND = 0x10000
    MB_TOPMOST = 0x40000
    
    flags = MB_YESNO | MB_ICONQUESTION | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
    
    msg = "Đây là hộp thoại System Modal.\nNó có đè lên mọi cửa sổ khác không?"
    print("Triggering MessageBox NOW!")
    
    ctypes.windll.user32.MessageBoxW(0, msg, "Test Popup", flags)
    print("Done!")

if __name__ == "__main__":
    force_popup_test()
