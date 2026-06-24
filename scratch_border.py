import tkinter as tk
import ctypes

def create_border():
    root = tk.Tk()
    root.withdraw()

    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()
    thickness = 5
    color = "#FF69B4"

    rects = [
        (0, 0, w, thickness),
        (0, h - thickness, w, thickness),
        (0, 0, thickness, h),
        (w - thickness, 0, thickness, h)
    ]

    wins = []
    for x, y, rw, rh in rects:
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.8) # Force WS_EX_LAYERED and set opacity
        win.configure(bg=color)
        win.geometry(f"{rw}x{rh}+{x}+{y}")
        
        # update_idletasks to ensure window is created before winfo_id
        win.update_idletasks()
        try:
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            if not hwnd:
                hwnd = win.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            # Add WS_EX_TRANSPARENT (0x00000020)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x00000020)
        except Exception as e:
            print("Error:", e)
        wins.append(win)

    root.after(5000, root.destroy)
    root.mainloop()

if __name__ == "__main__":
    create_border()
