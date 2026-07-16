import tkinter as tk
from PIL import ImageGrab
import time
import os

print("Creating Tk...")
root = tk.Tk()
root.title("Test Fonts")
root.geometry("400x150")
root.configure(bg="#2A2A35")

lbl = tk.Label(root, text="Segoe UI: 📋 Sao chép cả ID & Mật khẩu / 📁 Danh sách máy tính đã lưu", 
               font=("Segoe UI", 10), fg="#FFFFFF", bg="#2A2A35")
lbl.pack(pady=20)

root.update()
print("Window updated.")

# Let the window render
time.sleep(0.5)

print("Grabbing image...")
try:
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = root.winfo_width()
    h = root.winfo_height()
    print(f"Geometry: {w}x{h} at {x},{y}")
    img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
    print("Image grabbed successfully.")
    os.makedirs("scratch", exist_ok=True)
    img.save("scratch/font_test_segoe.png")
    print("Saved successfully.")
except Exception as e:
    print(f"Error during grab: {e}")

root.destroy()
print("Done.")
