import tkinter as tk
from tkinter import ttk
import time

class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, title_text, filename, total_size, on_cancel=None):
        super().__init__(parent)
        self.withdraw()
        self.title('File Transfer')
        self.resizable(False, False)
        self.configure(bg='#FFFFFF')
        
        self.total_size = total_size
        self.filename = filename
        self.start_time = time.time()
        self.on_cancel = on_cancel
        
        top_frame = tk.Frame(self, bg='#FFFFFF')
        top_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        display_name = filename
        if len(display_name) > 40:
            display_name = display_name[:20] + '...' + display_name[-15:]
            
        self.lbl_action = tk.Label(top_frame, text=f'Copy file \"{display_name}\"', font=('Segoe UI', 9), fg='#000000', bg='#FFFFFF', anchor='w')
        self.lbl_action.pack(fill=tk.X)
        
        self.lbl_stats1 = tk.Label(top_frame, text=f'(0 B of {self.format_size(total_size)})  -- MB/s  -- sec(s)', font=('Segoe UI', 9), fg='#000000', bg='#FFFFFF', anchor='w')
        self.lbl_stats1.pack(fill=tk.X, padx=5, pady=(2, 5))
        
        self.prog1 = ttk.Progressbar(top_frame, orient='horizontal', length=360, mode='determinate')
        self.prog1.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_files = tk.Label(top_frame, text='Copy 1 of 1 file(s)', font=('Segoe UI', 9), fg='#000000', bg='#FFFFFF', anchor='w')
        self.lbl_files.pack(fill=tk.X)
        
        self.lbl_stats2 = tk.Label(top_frame, text=f'0 B of {self.format_size(total_size)}  -- sec(s)', font=('Segoe UI', 9), fg='#000000', bg='#FFFFFF', anchor='w')
        self.lbl_stats2.pack(fill=tk.X, padx=5, pady=(2, 5))
        
        self.prog2 = ttk.Progressbar(top_frame, orient='horizontal', length=360, mode='determinate')
        self.prog2.pack(fill=tk.X)
        
        bottom_frame = tk.Frame(self, bg='#F0F0F0', height=45)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_frame.pack_propagate(False)
        
        sep = tk.Frame(self, height=1, bg='#DFDFDF', bd=0)
        sep.pack(fill=tk.X, side=tk.BOTTOM)
        
        if self.on_cancel:
            btn_cancel = tk.Button(
                bottom_frame, text='Cancel', font=('Segoe UI', 9),
                fg='#000000', bg='#E1E1E1', activeforeground='#000000', activebackground='#E5F1FB',
                relief=tk.FLAT, bd=1, width=10, command=self.trigger_cancel
            )
            btn_cancel.pack(side=tk.RIGHT, padx=15, pady=10)
            def btn_enter(event): btn_cancel.configure(bg='#E5F1FB', bd=1)
            def btn_leave(event): btn_cancel.configure(bg='#E1E1E1', bd=1)
            btn_cancel.bind('<Enter>', btn_enter)
            btn_cancel.bind('<Leave>', btn_leave)
            self.protocol('WM_DELETE_WINDOW', self.trigger_cancel)
            dialog_h = 240
        else:
            dialog_h = 195
            
        self.update_idletasks()
        dialog_w = 400
        
        is_parent_minimized = False
        try:
            if parent is None or parent.state() == 'iconic' or parent.winfo_viewable() == 0 or parent.winfo_x() < -10000:
                is_parent_minimized = True
        except:
            pass
            
        if is_parent_minimized or parent is None:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = (screen_w - dialog_w) // 2
            y = (screen_h - dialog_h) // 2
        else:
            parent_x = parent.winfo_x()
            parent_y = parent.winfo_y()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            x = parent_x + (parent_w - dialog_w) // 2
            y = parent_y + (parent_h - dialog_h) // 2
            
        self.geometry(f'{dialog_w}x{dialog_h}+{x}+{y}')
        self.deiconify()

    def trigger_cancel(self):
        pass

    def update_progress(self, sent_bytes):
        pass

    def format_size(self, size_bytes):
        return '1 MB'

    def format_speed(self, speed):
        return '1 MB/s'

root = tk.Tk()
try:
    d = ProgressDialog(root, 'Test', 'test.txt', 1000)
    print('Dialog instantiated successfully with parent')
except Exception as e:
    import traceback
    traceback.print_exc()

try:
    d2 = ProgressDialog(None, 'Test', 'test.txt', 1000)
    print('Dialog instantiated successfully without parent')
except Exception as e:
    import traceback
    traceback.print_exc()
