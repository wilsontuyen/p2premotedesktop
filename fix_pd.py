import codecs

content = codecs.open('app.py', 'r', 'utf-8').read()

new_code = '''class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, title_text, filename, total_size, on_cancel=None):
        super().__init__(parent)
        self.withdraw()
        self.title("File Transfer")
        self.resizable(False, False)
        self.configure(bg="#FFFFFF")
        
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(False, icon_img)
                self._dialog_icon_img = icon_img
        except Exception:
            pass
            
        self.attributes("-topmost", True)
        self.lift()
        
        self.total_size = total_size
        self.filename = str(filename) if filename is not None else "Unknown"
        self.start_time = time.time()
        self.on_cancel = on_cancel
        
        top_frame = tk.Frame(self, bg="#FFFFFF")
        top_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        display_name = self.filename
        if len(display_name) > 40:
            display_name = display_name[:20] + "..." + display_name[-15:]
            
        self.lbl_action = tk.Label(top_frame, text=f'Copy file "{display_name}"', font=("Segoe UI", 9), fg="#000000", bg="#FFFFFF", anchor="w")
        self.lbl_action.pack(fill=tk.X)
        
        self.lbl_stats1 = tk.Label(top_frame, text=f"(0 B of {self.format_size(total_size)})  -- MB/s  -- sec(s)", font=("Segoe UI", 9), fg="#000000", bg="#FFFFFF", anchor="w")
        self.lbl_stats1.pack(fill=tk.X, padx=5, pady=(2, 5))
        
        self.prog1 = ttk.Progressbar(top_frame, orient="horizontal", length=360, mode="determinate")
        self.prog1.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_files = tk.Label(top_frame, text="Copy 1 of 1 file(s)", font=("Segoe UI", 9), fg="#000000", bg="#FFFFFF", anchor="w")
        self.lbl_files.pack(fill=tk.X)
        
        self.lbl_stats2 = tk.Label(top_frame, text=f"0 B of {self.format_size(total_size)}  -- sec(s)", font=("Segoe UI", 9), fg="#000000", bg="#FFFFFF", anchor="w")
        self.lbl_stats2.pack(fill=tk.X, padx=5, pady=(2, 5))
        
        self.prog2 = ttk.Progressbar(top_frame, orient="horizontal", length=360, mode="determinate")
        self.prog2.pack(fill=tk.X)
        
        bottom_frame = tk.Frame(self, bg="#F0F0F0", height=45)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_frame.pack_propagate(False)
        
        sep = tk.Frame(self, height=1, bg="#DFDFDF", bd=0)
        sep.pack(fill=tk.X, side=tk.BOTTOM)
        
        if self.on_cancel:
            btn_cancel = tk.Button(
                bottom_frame, text="Cancel", font=("Segoe UI", 9),
                fg="#000000", bg="#E1E1E1", activeforeground="#000000", activebackground="#E5F1FB",
                relief=tk.FLAT, bd=1, width=10, command=self.trigger_cancel
            )
            btn_cancel.pack(side=tk.RIGHT, padx=15, pady=10)
            def btn_enter(event): btn_cancel.configure(bg="#E5F1FB", bd=1)
            def btn_leave(event): btn_cancel.configure(bg="#E1E1E1", bd=1)
            btn_cancel.bind("<Enter>", btn_enter)
            btn_cancel.bind("<Leave>", btn_leave)
            self.protocol("WM_DELETE_WINDOW", self.trigger_cancel)
            dialog_h = 240
        else:
            dialog_h = 195
            
        self.update_idletasks()
        dialog_w = 400
        
        is_parent_minimized = False
        try:
            if parent is None or parent.state() == "iconic" or parent.winfo_viewable() == 0 or parent.winfo_x() < -10000:
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
            
        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        self.deiconify()

    def trigger_cancel(self):
        try: self.destroy()
        except: pass
        if self.on_cancel:
            try: self.on_cancel()
            except: pass

    def update_progress(self, sent_bytes):
        percent = int(sent_bytes * 100 / self.total_size) if self.total_size > 0 else 100
        percent = max(0, min(100, percent))
        
        self.prog1["value"] = percent
        self.prog2["value"] = percent
        
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 0 and sent_bytes > 0:
            speed = sent_bytes / elapsed_time
            if speed > 0:
                remaining_bytes = self.total_size - sent_bytes
                remaining_time = remaining_bytes / speed
                mins = int(remaining_time // 60)
                secs = int(remaining_time % 60)
                if mins > 0:
                    time_str = f"{mins} min {secs} sec(s)"
                else:
                    time_str = f"{secs} sec(s)"
            else:
                time_str = "-- sec(s)"
            speed_str = f"{self.format_speed(speed)}"
        else:
            speed_str = "-- MB/s"
            time_str = "-- sec(s)"
            
        sent_str = self.format_size(sent_bytes)
        total_str = self.format_size(self.total_size)
        
        self.lbl_stats1.config(text=f"({sent_str} of {total_str})  {speed_str}  {time_str}")
        self.lbl_stats2.config(text=f"{sent_str} of {total_str}  {time_str}")
        self.update_idletasks()

    def format_size(self, size_bytes):
        if size_bytes < 1024: return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024: return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 * 1024 * 1024: return f"{size_bytes / (1024 * 1024):.2f} MB"
        else: return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def format_speed(self, speed_bytes_per_sec):
        if speed_bytes_per_sec < 1024: return f"{speed_bytes_per_sec:.0f} B/s"
        elif speed_bytes_per_sec < 1024 * 1024: return f"{speed_bytes_per_sec / 1024:.2f} KB/s"
        elif speed_bytes_per_sec < 1024 * 1024 * 1024: return f"{speed_bytes_per_sec / (1024 * 1024):.2f} MB/s"
        else: return f"{speed_bytes_per_sec / (1024 * 1024 * 1024):.2f} GB/s"
'''

idx_start = content.find('class ProgressDialog(tk.Toplevel):')
idx_end_class = content.find('class ConfirmDialog(tk.Toplevel):', idx_start)

if idx_start != -1 and idx_end_class != -1:
    content = content[:idx_start] + new_code + "\n" + content[idx_end_class:]
    codecs.open('app.py', 'w', 'utf-8').write(content)
    print("Success replacing ProgressDialog")
else:
    print("Not found")

'''
We also need to fix create_dialog in do_upload to print exceptions if it fails
'''
upload_fix = """                                                        def create_dialog():
                                                            nonlocal dialog
                                                            try:
                                                                dialog = ProgressDialog(top, "Upload files...", n, sz, on_cancel=on_upload_cancel)
                                                                dialog.update_progress(0)
                                                            except Exception as e:
                                                                import traceback
                                                                print("Error creating dialog:", e)
                                                                traceback.print_exc()"""

old_upload = """                                                        def create_dialog():
                                                            nonlocal dialog
                                                            dialog = ProgressDialog(top, "Upload files...", n, sz, on_cancel=on_upload_cancel)
                                                            dialog.update_progress(0)"""

content = codecs.open('app.py', 'r', 'utf-8').read()
if old_upload in content:
    content = content.replace(old_upload, upload_fix)
    codecs.open('app.py', 'w', 'utf-8').write(content)
    print("Success fixing upload dialog creation")
