import tkinter as tk
from tkinter import ttk
import threading
def th():
    try:
        r = tk.Tk()
        t = tk.Toplevel(r)
        tv = ttk.Treeview(t)
        print("OK")
        r.destroy()
    except Exception as e:
        print("ERROR:", e)
threading.Thread(target=th).start()
