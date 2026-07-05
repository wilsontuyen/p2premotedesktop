import tkinter as tk
import threading
def th():
    r = tk.Tk()
    t = tk.Toplevel(r)
    print("OK")
    r.destroy()
threading.Thread(target=th).start()
