import tkinter as tk
from PIL import ImageGrab
import time
import os

root = tk.Tk()
root.title("Test Fonts")
root.geometry("600x300")
root.configure(bg="#2A2A35")

# Test cases
# 1. Segoe UI Emoji (Current)
lbl1 = tk.Label(root, text="Segoe UI Emoji: 📋 Sao chép cả ID & Mật khẩu / 📁 Danh sách máy tính đã lưu", 
                font=("Segoe UI Emoji", 10), fg="#FFFFFF", bg="#2A2A35")
lbl1.pack(pady=10)

# 2. Segoe UI Emoji Bold (Current)
lbl2 = tk.Label(root, text="Segoe UI Emoji Bold: 📋 Sao chép cả ID & Mật khẩu / 📁 Danh sách máy tính đã lưu", 
                font=("Segoe UI Emoji", 10, "bold"), fg="#FFFFFF", bg="#2A2A35")
lbl2.pack(pady=10)

# 3. Segoe UI (Proposed)
lbl3 = tk.Label(root, text="Segoe UI: 📋 Sao chép cả ID & Mật khẩu / 📁 Danh sách máy tính đã lưu", 
                font=("Segoe UI", 10), fg="#FFFFFF", bg="#2A2A35")
lbl3.pack(pady=10)

# 4. Segoe UI Bold (Proposed)
lbl4 = tk.Label(root, text="Segoe UI Bold: 📋 Sao chép cả ID & Mật khẩu / 📁 Danh sách máy tính đã lưu", 
                font=("Segoe UI", 10, "bold"), fg="#FFFFFF", bg="#2A2A35")
lbl4.pack(pady=10)

def capture():
    root.update()
    # Get window coordinates
    x = root.winfo_rootx()
    y = root.winfo_rooty()
    w = root.winfo_width()
    h = root.winfo_height()
    
    # Grab the window image
    img = ImageGrab.grab(bbox=(x, y, x+w, y+h))
    os.makedirs("scratch", exist_ok=True)
    img.save("scratch/font_test.png")
    print("Screenshot saved to scratch/font_test.png")
    root.destroy()

root.after(1000, capture)
root.mainloop()
