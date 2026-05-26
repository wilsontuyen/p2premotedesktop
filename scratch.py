import tkinter as tk
import time

root = tk.Tk()
root.withdraw()

top = tk.Toplevel(root)
top.title("Test")
top.geometry("300x200")
top.attributes("-topmost", True)
top.deiconify()
top.lift()
top.focus_force()

root.after(5000, root.destroy)
root.mainloop()
