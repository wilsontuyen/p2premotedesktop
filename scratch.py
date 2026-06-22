import tkinter as tk

def test_blink():
    root = tk.Tk()
    root.withdraw()
    
    blink_win = tk.Toplevel(root)
    blink_win.attributes("-fullscreen", True)
    blink_win.attributes("-topmost", True)
    blink_win.attributes("-alpha", 0.7)
    blink_win.attributes("-transparentcolor", "black")
    blink_win.configure(bg="black")
    blink_win.overrideredirect(True)
    
    canvas = tk.Canvas(blink_win, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()
    rect_id = canvas.create_rectangle(0, 0, w, h, outline="red", width=30)
    
    def toggle_border(count):
        if count <= 0:
            root.destroy()
            return
        color = "red" if count % 2 != 0 else "black"
        canvas.itemconfig(rect_id, outline=color)
        root.after(400, toggle_border, count - 1)
        
    toggle_border(6)
    root.mainloop()

if __name__ == "__main__":
    test_blink()
