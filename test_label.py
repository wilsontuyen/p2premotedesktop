import tkinter as tk
from tkinter import ttk

class MacLabel(ttk.Label):
    def __init__(self, master=None, **kw):
        self._style_name = f"MacLabel_{id(self)}.TLabel"
        self._style = ttk.Style()
        
        ttk_kw = {}
        style_kw = {}
        for k, v in kw.items():
            if k == 'bg': style_kw['background'] = v
            elif k == 'fg': style_kw['foreground'] = v
            elif k == 'font': style_kw['font'] = v
            elif k in ('bd', 'relief', 'height', 'width'): pass
            else: ttk_kw[k] = v
            
        self._style.configure(self._style_name, **style_kw)
        ttk_kw['style'] = self._style_name
        super().__init__(master, **ttk_kw)

root = tk.Tk()
root.geometry("200x200")
lbl = MacLabel(root, text="HELLO WORLD", bg="red", fg="white", font=("Arial", 20))
lbl.pack(pady=20)
btn = tk.Button(root, text="Button")
btn.pack()
root.update()
import time
time.sleep(1)
