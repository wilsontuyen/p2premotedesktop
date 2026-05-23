import ctypes
import time
import threading
import tkinter as tk

user32 = ctypes.windll.user32
OpenClipboard = user32.OpenClipboard
CloseClipboard = user32.CloseClipboard

def bg_thread(hwnd):
    print(f"Background thread starting. Trying OpenClipboard({hwnd})")
    for _ in range(5):
        res = OpenClipboard(hwnd)
        if res:
            print("OpenClipboard succeeded!")
            CloseClipboard()
            break
        else:
            print("OpenClipboard failed. Error:", ctypes.GetLastError())
        time.sleep(0.5)

    print(f"Background thread trying OpenClipboard(None)")
    for _ in range(5):
        res = OpenClipboard(None)
        if res:
            print("OpenClipboard(None) succeeded!")
            CloseClipboard()
            break
        else:
            print("OpenClipboard(None) failed. Error:", ctypes.GetLastError())
        time.sleep(0.5)

def main():
    root = tk.Tk()
    hwnd = root.winfo_id()
    print("Main window HWND:", hwnd)
    
    t = threading.Thread(target=bg_thread, args=(hwnd,))
    t.start()
    
    root.after(3000, root.destroy)
    root.mainloop()

if __name__ == "__main__":
    main()
