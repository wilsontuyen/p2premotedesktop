import tkinter as tk
import time
import threading

def run_test():
    root = tk.Tk()
    root.title("Main Window")
    
    print("Withdrawing main window...")
    root.withdraw()
    
    def show_dialog():
        print("Creating Toplevel dialog...")
        top = tk.Toplevel(root)
        top.title("Dialog")
        top.geometry("200x100")
        tk.Label(top, text="I am a dialog!").pack()
        top.attributes("-topmost", True)
        
        # Try to make it visible
        top.deiconify()
        top.lift()
        top.focus_force()
        print("Dialog should be visible now.")
        
    root.after(2000, show_dialog)
    root.mainloop()

t = threading.Thread(target=run_test, daemon=True)
t.start()
time.sleep(5)
print("Done.")
