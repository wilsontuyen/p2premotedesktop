import tkinter as tk
import threading
import time

def th():
    r = tk.Tk()
    r.geometry('200x200')
    print('Ready')
    r.mainloop()
    print('Done')

threading.Thread(target=th, daemon=True).start()
time.sleep(3)
