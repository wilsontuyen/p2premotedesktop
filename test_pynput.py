import ctypes
import threading
import time
from pynput import keyboard

class PasteInterceptor:
    def __init__(self):
        self.listener = None
        self.pending = True
        
    def is_ctrl_pressed(self):
        return (ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000) != 0

    def win32_event_filter(self, msg, data):
        # 256 = WM_KEYDOWN
        if msg == 256 and data.vkCode == 0x56: # 'V'
            if self.is_ctrl_pressed() and self.pending:
                print(">>> INTERCEPTED CTRL+V! SUPPRESSING! <<<")
                self.pending = False
                # Simulate the delay of downloading
                threading.Thread(target=self.simulate_download, daemon=True).start()
                self.listener.suppress_event()
                return False
        return True
        
    def simulate_download(self):
        print("Downloading...")
        time.sleep(2)
        print("Download done! Synthesizing Ctrl+V...")
        
        # We must use ctypes to send key events because pynput Controller might be caught by our own hook!
        # Wait, if we use pynput to send Ctrl+V, will it be intercepted again?
        # Yes, unless self.pending is False!
        ctrl = keyboard.Controller()
        with ctrl.pressed(keyboard.Key.ctrl):
            ctrl.press('v')
            ctrl.release('v')
        print("Synthesized Ctrl+V!")
        
        # Reset pending after a delay
        time.sleep(1)
        self.pending = True

    def start(self):
        self.listener = keyboard.Listener(win32_event_filter=self.win32_event_filter)
        self.listener.start()
        print("Interceptor started! Go anywhere and press Ctrl+V.")

if __name__ == "__main__":
    interceptor = PasteInterceptor()
    interceptor.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
