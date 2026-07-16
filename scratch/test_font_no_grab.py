import tkinter as tk
import time

print("Starting tkinter...")
root = tk.Tk()
root.title("Test Fonts No Grab")
root.geometry("200x100")
lbl = tk.Label(root, text="Test 📋 📁 á ẩ ó ế ố", font=("Segoe UI", 10))
lbl.pack()
root.update()
print("Tkinter window updated successfully!")
root.after(500, root.destroy)
root.mainloop()
print("Tkinter mainloop exited successfully!")
