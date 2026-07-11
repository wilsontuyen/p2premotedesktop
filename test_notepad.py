import tkinter as tk
import time

def test():
    root = tk.Tk()
    root.geometry("400x300")
    
    def simulate_event():
        def show_notepad():
            try:
                np_win = tk.Toplevel(root)
                np_win.title("Notepad")
                np_win.geometry("800x600")
                np_win.transient(root)
                np_win.attributes('-topmost', True)
                text_area = tk.Text(np_win, wrap="word", font=("Consolas", 11))
                text_area.pack(expand=True, fill="both")
                text_area.insert("1.0", "Hello World")
                btn_frame = tk.Frame(np_win)
                btn_frame.pack(fill=tk.X)
                tk.Button(btn_frame, text=_("Lưu")).pack(side=tk.RIGHT, padx=5, pady=5)
                print("Notepad created successfully")
            except Exception as e:
                print("Error in show_notepad:", e)
        
        root.after(0, show_notepad)
    
    tk.Button(root, text="Test", command=simulate_event).pack(pady=50)
    root.after(1000, simulate_event) # Auto click after 1 sec
    root.after(3000, root.destroy)   # Auto close after 3 secs
    root.mainloop()

test()
