import tkinter as tk
from tkinter import ttk
import os
import time
import sys
_DIALOG_FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"
from utils.logger import log_debug
from core.i18n import _

try:
    from PIL import Image, ImageTk
except ImportError:
    pass

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class PremiumProgressBar(tk.Canvas):
    def __init__(self, parent, width=320, height=12, bg="#15151B", fg="#00ADB5", **kwargs):
        super().__init__(parent, width=width, height=height, bg=parent["bg"], highlightthickness=0, bd=0, **kwargs)
        self.width = width
        self.height = height
        self.fg = fg
        self.bg_color = bg
        
        self.draw_rounded_rect(0, 0, width, height, radius=5, fill=bg)
        self.fill_id = None

    def draw_rounded_rect(self, x1, y1, x2, y2, radius=5, **kwargs):
        points = [x1+radius, y1,
                  x2-radius, y1,
                  x2, y1,
                  x2, y1+radius,
                  x2, y2-radius,
                  x2, y2,
                  x2-radius, y2,
                  x1+radius, y2,
                  x1, y2,
                  x1, y2-radius,
                  x1, y1+radius,
                  x1, y1]
        return self.create_polygon(points, **kwargs, smooth=True)

    def set_progress(self, percent):
        percent = max(0, min(100, percent))
        if self.fill_id:
            self.delete(self.fill_id)
            self.fill_id = None
            
        if percent > 0:
            fill_width = int(self.width * (percent / 100))
            if fill_width > 10:
                self.fill_id = self.draw_rounded_rect(0, 0, fill_width, self.height, radius=5, fill=self.fg)
            elif fill_width > 0:
                self.fill_id = self.create_rectangle(0, 0, fill_width, self.height, fill=self.fg, width=0)

from os_utils.ui import get_file_icon_as_image

class ClassicCopyDialog(tk.Toplevel):
    def __init__(self, parent, filename, source_info, dest_info, has_multiple=False):
        super().__init__(parent)
        self.withdraw()
        self.title("Copy File")
        self.geometry("520x420")
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
            
        self.choice = None
        self.has_multiple = has_multiple
        
        self.attributes("-topmost", True)
        self.focus_force()
        
        self.update_idletasks()
        w = 520
        h = 420
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = (ws - w) // 2
        y = (hs - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        
        self.grab_set()
        
        lbl_title = tk.Label(
            self, text="There is already a file with the same name in this location.",
            font=(_DIALOG_FONT, 12), fg="#003399", bg="#FFFFFF", anchor="w", justify=tk.LEFT
        )
        lbl_title.pack(fill=tk.X, padx=24, pady=(20, 2))
        
        lbl_sub = tk.Label(
            self, text="Click the file you want to keep",
            font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w"
        )
        lbl_sub.pack(fill=tk.X, padx=24, pady=(0, 15))
        
        def format_size(bytes_size):
            if bytes_size < 1024:
                return f"{bytes_size} bytes"
            elif bytes_size < 1024 * 1024:
                return f"{bytes_size / 1024:.1f} KB"
            else:
                return f"{bytes_size / (1024 * 1024):.1f} MB"

        def format_time(timestamp):
            try:
                import datetime
                dt = datetime.datetime.fromtimestamp(timestamp)
                return dt.strftime("%m/%d/%Y %I:%M %p")
            except:
                return "Unknown"
                
        def format_location_info(file_path):
            if not file_path:
                return "Unknown location"
            parent_dir = os.path.dirname(file_path)
            parent_folder_name = os.path.basename(parent_dir)
            if not parent_folder_name:
                parent_folder_name = parent_dir
            return f"{parent_folder_name} ({parent_dir})"
            
        src_icon_img = get_file_icon_as_image(filename)
        dest_icon_img = get_file_icon_as_image(dest_info.get("path", filename))
        
        self.src_icon = ImageTk.PhotoImage(src_icon_img) if src_icon_img else None
        self.dest_icon = ImageTk.PhotoImage(dest_icon_img) if dest_icon_img else None
        
        def get_all_children(w):
            children = [w]
            for child in w.winfo_children():
                children.extend(get_all_children(child))
            return children
            
        def setup_command_link(frame, action_val):
            normal_bg = "#FFFFFF"
            hover_bg = "#E5F1FB"
            normal_border = "#FFFFFF"
            hover_border = "#B8D6F3"
            
            frame.configure(background=normal_bg, highlightbackground=normal_border, highlightthickness=1, bd=0)
            
            def on_enter(event):
                frame.configure(background=hover_bg, highlightbackground=hover_border)
                for child in get_all_children(frame):
                    try: child.configure(background=hover_bg)
                    except: pass
                    
            def on_leave(event):
                x, y = frame.winfo_pointerx() - frame.winfo_rootx(), frame.winfo_pointery() - frame.winfo_rooty()
                if x < 0 or x >= frame.winfo_width() or y < 0 or y >= frame.winfo_height():
                    frame.configure(background=normal_bg, highlightbackground=normal_border)
                    for child in get_all_children(frame):
                        try: child.configure(background=normal_bg)
                        except: pass
                        
            def on_click(event):
                self.choice = action_val
                self.destroy()
                
            for w in get_all_children(frame):
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.bind("<Button-1>", on_click)
                w.configure(cursor="hand2")
                
        # Link 1: Copy and Replace
        link1 = tk.Frame(self, bg="#FFFFFF")
        link1.pack(fill=tk.X, padx=24, pady=5)
        
        lbl_arrow1 = tk.Label(link1, text="→", font=(_DIALOG_FONT, 16, "bold"), fg="#0066CC", bg="#FFFFFF")
        lbl_arrow1.pack(side=tk.LEFT, anchor="n", padx=(5, 5))
        
        right_content1 = tk.Frame(link1, bg="#FFFFFF")
        right_content1.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        lbl_title1 = tk.Label(right_content1, text="Copy and Replace", font=(_DIALOG_FONT, 10, "bold"), fg="#0066CC", bg="#FFFFFF", anchor="w")
        lbl_title1.pack(fill=tk.X)
        
        lbl_desc1 = tk.Label(right_content1, text="Replace the file in the destination folder with the file you are copying:", font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w")
        lbl_desc1.pack(fill=tk.X, pady=(0, 5))
        
        info_frame1 = tk.Frame(right_content1, bg="#FFFFFF")
        info_frame1.pack(fill=tk.X, padx=(10, 0))
        
        if self.src_icon:
            lbl_icon1 = tk.Label(info_frame1, image=self.src_icon, bg="#FFFFFF")
            lbl_icon1.pack(side=tk.LEFT, anchor="n", padx=(0, 10))
            
        info_text1 = tk.Frame(info_frame1, bg="#FFFFFF")
        info_text1.pack(side=tk.LEFT, fill=tk.X)
        
        tk.Label(info_text1, text=filename, font=(_DIALOG_FONT, 9, "bold"), fg="#000000", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text1, text=format_location_info(source_info.get("path")), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text1, text=f"Size: {format_size(source_info.get('size', 0))}", font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text1, text=f"Date modified: {format_time(source_info.get('mtime', 0))}", font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        
        setup_command_link(link1, "replace")
        
        # Link 2: Don't Copy
        link2 = tk.Frame(self, bg="#FFFFFF")
        link2.pack(fill=tk.X, padx=24, pady=5)
        
        lbl_arrow2 = tk.Label(link2, text="→", font=(_DIALOG_FONT, 16, "bold"), fg="#0066CC", bg="#FFFFFF")
        lbl_arrow2.pack(side=tk.LEFT, anchor="n", padx=(5, 5))
        
        right_content2 = tk.Frame(link2, bg="#FFFFFF")
        right_content2.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        lbl_title2 = tk.Label(right_content2, text="Don't copy", font=(_DIALOG_FONT, 10, "bold"), fg="#0066CC", bg="#FFFFFF", anchor="w")
        lbl_title2.pack(fill=tk.X)
        
        lbl_desc2 = tk.Label(right_content2, text="No files will be changed. Leave this file in the destination folder:", font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w")
        lbl_desc2.pack(fill=tk.X, pady=(0, 5))
        
        info_frame2 = tk.Frame(right_content2, bg="#FFFFFF")
        info_frame2.pack(fill=tk.X, padx=(10, 0))
        
        if self.dest_icon:
            lbl_icon2 = tk.Label(info_frame2, image=self.dest_icon, bg="#FFFFFF")
            lbl_icon2.pack(side=tk.LEFT, anchor="n", padx=(0, 10))
            
        info_text2 = tk.Frame(info_frame2, bg="#FFFFFF")
        info_text2.pack(side=tk.LEFT, fill=tk.X)
        
        tk.Label(info_text2, text=filename, font=(_DIALOG_FONT, 9, "bold"), fg="#000000", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text2, text=format_location_info(dest_info.get("path")), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text2, text=f"Size: {format_size(dest_info.get('size', 0))}", font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text2, text=f"Date modified: {format_time(dest_info.get('mtime', 0))}", font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        
        setup_command_link(link2, "skip")
        
        sep = tk.Frame(self, height=1, bg="#D0D0D0", bd=0)
        sep.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 0))
        
        bottom_bar = tk.Frame(self, bg="#F0F0F0", height=48)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_bar.pack_propagate(False)
        
        self.var_all = tk.BooleanVar()
        if has_multiple:
            chk = tk.Checkbutton(
                bottom_bar, text="Do this for all conflicts", font=(_DIALOG_FONT, 9),
                variable=self.var_all, bg="#F0F0F0", activebackground="#F0F0F0", bd=0
            )
            chk.pack(side=tk.LEFT, padx=24, pady=10)
            
        btn_cancel = tk.Button(
            bottom_bar, text="Cancel", font=(_DIALOG_FONT, 9), width=10,
            bg="#E1E1E1", fg="#000000", relief=tk.FLAT, bd=1, highlightthickness=0,
            command=self.on_cancel
        )
        btn_cancel.pack(side=tk.RIGHT, padx=24, pady=10)
        
        def btn_enter(event):
            btn_cancel.configure(bg="#E5F1FB", bd=1)
        def btn_leave(event):
            btn_cancel.configure(bg="#E1E1E1", bd=1)
        btn_cancel.bind("<Enter>", btn_enter)
        btn_cancel.bind("<Leave>", btn_leave)
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
    def on_cancel(self):
        self.choice = "cancel"
        self.destroy()

class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, title_text, filename, total_size, on_cancel=None, host_hwnd=None):
        super().__init__(parent)
        self.parent_window = parent
        self.host_hwnd = host_hwnd
        self.withdraw()
        self.attributes("-alpha", 0.0)
        self.overrideredirect(True)
        self.configure(bg="#FFFFFF", highlightbackground="#CCCCCC", highlightthickness=1)

        title_bg = "#F3F3F3"
        self.title_bar = tk.Frame(self, bg=title_bg, height=28)
        self.title_bar.pack(fill=tk.X, side=tk.TOP)
        self.title_bar.pack_propagate(False)
        self.title_lbl = tk.Label(self.title_bar, text=title_text, bg=title_bg, fg="#333333", font=(_DIALOG_FONT, 9, "bold"))
        self.title_lbl.pack(side=tk.LEFT, padx=10, pady=4)

        # Cho phép kéo thả hộp thoại bằng chuột trên thanh tiêu đề
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        for widget in (self.title_bar, self.title_lbl):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._do_drag)

        self.attributes("-topmost", True)
        self.lift()
        self.total_size = total_size
        self.filename = str(filename) if filename is not None else "Unknown"
        self.start_time = time.time()
        self.history = [(self.start_time, 0)]
        self.on_cancel = on_cancel
        
        top_frame = tk.Frame(self, bg="#FFFFFF")
        top_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        display_name = self.filename
        if len(display_name) > 40:
            display_name = display_name[:20] + "..." + display_name[-15:]
            
        self.lbl_action = tk.Label(top_frame, text=f'Copy file "{display_name}"', font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w")
        self.lbl_action.pack(fill=tk.X)
        
        self.lbl_stats1 = tk.Label(top_frame, text=f"(0 B of {self.format_size(total_size)})  -- MB/s  -- sec(s)", font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w")
        self.lbl_stats1.pack(fill=tk.X, padx=5, pady=(2, 5))
        
        self.prog1 = ttk.Progressbar(top_frame, orient="horizontal", length=360, mode="determinate")
        self.prog1.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_files = tk.Label(top_frame, text="Copy 1 of 1 file(s)", font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w")
        self.lbl_files.pack(fill=tk.X)
        
        self.lbl_stats2 = tk.Label(top_frame, text=f"0 B of {self.format_size(total_size)}  -- sec(s)", font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w")
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
                bottom_frame, text=_("Hủy"), font=(_DIALOG_FONT, 9),
                fg="#000000", bg="#E1E1E1", activeforeground="#000000", activebackground="#E5F1FB",
                relief=tk.FLAT, bd=1, width=10, command=self.trigger_cancel
            )
            btn_cancel.pack(side=tk.RIGHT, padx=15, pady=10)
            def btn_enter(event): btn_cancel.configure(bg="#E5F1FB", bd=1)
            def btn_leave(event): btn_cancel.configure(bg="#E1E1E1", bd=1)
            btn_cancel.bind("<Enter>", btn_enter)
            btn_cancel.bind("<Leave>", btn_leave)
            self.protocol("WM_DELETE_WINDOW", self.trigger_cancel)
            dialog_h = 270
        else:
            dialog_h = 225
            
        self.update_idletasks()
        dialog_w = 400
        
        if self.host_hwnd and sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                tk_hwnd = int(self.frame(), 16)
                style = ctypes.windll.user32.GetWindowLongW(tk_hwnd, -16)
                style = (style | 0x40000000) & ~0x80000000
                ctypes.windll.user32.SetWindowLongW(tk_hwnd, -16, style)
                ctypes.windll.user32.SetParent(tk_hwnd, self.host_hwnd)
                
                rect = wintypes.RECT()
                ctypes.windll.user32.GetClientRect(self.host_hwnd, ctypes.byref(rect))
                py_w = rect.right - rect.left
                py_h = rect.bottom - rect.top
                
                x = max(0, (py_w - dialog_w) // 2)
                y = max(0, (py_h - dialog_h) // 2)
                # Use HWND_TOP (0) and do NOT use SWP_NOZORDER (0x0004) so it stays on top of siblings
                ctypes.windll.user32.SetWindowPos(tk_hwnd, 0, x, y, dialog_w, dialog_h, 0x0020)
                self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
            except Exception:
                screen_w = self.winfo_screenwidth()
                screen_h = self.winfo_screenheight()
                x = (screen_w - dialog_w) // 2
                y = (screen_h - dialog_h) // 2
                self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        else:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = (screen_w - dialog_w) // 2
            y = (screen_h - dialog_h) // 2
            self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")

        self.deiconify()
        self.lift()
        self.focus_force()
        self.attributes("-alpha", 1.0)
        self.update()

    def trigger_cancel(self):
        try: self.destroy()
        except: pass
        if self.on_cancel:
            try: self.on_cancel()
            except: pass

    def _hwnd(self):
        try:
            return int(self.frame(), 16)
        except Exception:
            return 0

    def _usable_tk_parent(self):
        p = getattr(self, "parent_window", None)
        if not p:
            return None
        try:
            if str(p) == str(self):
                return None
            if not p.winfo_exists() or not p.winfo_ismapped() or not p.winfo_viewable():
                return None
            if p.winfo_width() < 80 or p.winfo_height() < 80:
                return None
            return p
        except Exception:
            return None

    def _host_client_screen_rect(self):
        """(left, top, right, bottom) màn hình của client area cửa sổ host/viewer."""
        if not (getattr(self, "host_hwnd", None) and sys.platform == "win32"):
            return None
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            rect = wintypes.RECT()
            if not user32.GetClientRect(self.host_hwnd, ctypes.byref(rect)):
                return None
            pt = wintypes.POINT(rect.left, rect.top)
            user32.ClientToScreen(self.host_hwnd, ctypes.byref(pt))
            return (pt.x, pt.y, pt.x + (rect.right - rect.left), pt.y + (rect.bottom - rect.top))
        except Exception:
            return None

    def _clamp_screen_pos(self, screen_x, screen_y):
        my_w = max(self.winfo_width(), 1)
        my_h = max(self.winfo_height(), 1)
        bounds = self._host_client_screen_rect()
        if not bounds:
            p = self._usable_tk_parent()
            if p:
                bounds = (p.winfo_rootx(), p.winfo_rooty(),
                          p.winfo_rootx() + p.winfo_width(),
                          p.winfo_rooty() + p.winfo_height())
        if bounds:
            left, top, right, bottom = bounds
            max_x = left if (right - left) <= my_w else right - my_w
            max_y = top if (bottom - top) <= my_h else bottom - my_h
            screen_x = max(left, min(screen_x, max_x))
            screen_y = max(top, min(screen_y, max_y))
        return screen_x, screen_y

    def _move_to_screen(self, screen_x, screen_y):
        screen_x, screen_y = self._clamp_screen_pos(screen_x, screen_y)
        if getattr(self, "host_hwnd", None) and sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                pt = wintypes.POINT(int(screen_x), int(screen_y))
                ctypes.windll.user32.ScreenToClient(self.host_hwnd, ctypes.byref(pt))
                hwnd = self._hwnd()
                if hwnd:
                    # SWP_NOSIZE | SWP_NOZORDER
                    ctypes.windll.user32.SetWindowPos(hwnd, 0, pt.x, pt.y, 0, 0, 0x0001 | 0x0004)
                    return
            except Exception:
                pass
        try:
            self.tk.call("wm", "geometry", self._w, "+%d+%d" % (int(screen_x), int(screen_y)))
        except Exception:
            self.geometry("+%d+%d" % (int(screen_x), int(screen_y)))

    def _start_drag(self, event):
        self._drag_offset_x = event.x_root - self.winfo_rootx()
        self._drag_offset_y = event.y_root - self.winfo_rooty()

    def _do_drag(self, event):
        x = event.x_root - self._drag_offset_x
        y = event.y_root - self._drag_offset_y
        self._move_to_screen(x, y)

    def update_progress(self, sent_bytes):
        def _do_update():
            try:
                percent = int(sent_bytes * 100 / self.total_size) if self.total_size > 0 else 100
                percent = max(0, min(100, percent))

                self.prog1["value"] = percent
                self.prog2["value"] = percent

                current_time = time.time()
                self.history.append((current_time, sent_bytes))
                while len(self.history) > 1 and current_time - self.history[0][0] > 2.0:
                    self.history.pop(0)

                elapsed_time = current_time - self.history[0][0]
                bytes_in_window = sent_bytes - self.history[0][1]
                
                if elapsed_time > 0 and bytes_in_window > 0:
                    speed = bytes_in_window / elapsed_time
                else:
                    speed = 0

                if speed > 0:
                    remaining_bytes = self.total_size - sent_bytes
                    remaining_time = remaining_bytes / speed
                    mins = int(remaining_time // 60)
                    secs = int(remaining_time % 60)
                    if mins > 0:
                        time_str = f"{mins} min {secs} sec(s)"
                    else:
                        time_str = f"{secs} sec(s)"
                if speed > 0:
                    speed_str = f"{self.format_speed(speed)}"
                else:
                    speed_str = "-- MB/s"
                    time_str = "-- sec(s)"

                sent_str = self.format_size(sent_bytes)
                total_str = self.format_size(self.total_size)

                self.lbl_stats1.config(text=f"({sent_str} of {total_str})  {speed_str}  {time_str}")
                self.lbl_stats2.config(text=f"{sent_str} of {total_str}  {time_str}")
            except: pass
        try:
            self.after(0, _do_update)
        except: pass

    def safe_destroy(self):
        try: self.after(0, self.destroy)
        except: pass

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

class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent, title, message, on_yes, on_no):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg="#1E1E24")
        
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(False, icon_img)
                self._dialog_icon_img = icon_img
        except Exception:
            pass
            
        # Thiết lập thuộc tính Modal & Topmost
        self.attributes("-topmost", True)
        # Chỉ liên kết transient nếu cửa sổ cha đang hiển thị, nếu không hộp thoại sẽ bị ẩn theo cha.
        if parent and parent.state() != "withdrawn":
            self.transient(parent)
        else:
            # Ép hiển thị vì nếu parent ẩn, Toplevel có thể bị ẩn theo mặc định
            self.deiconify()
            self.lift()
            self.focus_force()
        # Bỏ grab_set() để tránh xung đột Focus & Event routing trên một số hệ thống Windows
        
        lbl_title = tk.Label(self, text=title.upper(), font=(_DIALOG_FONT, 11, "bold"), fg="#00ADB5", bg="#1E1E24")
        lbl_title.pack(pady=(15, 10), padx=20, anchor=tk.W)
        
        lbl_msg = tk.Label(self, text=message, font=(_DIALOG_FONT, 9), fg="#FFFFFF", bg="#1E1E24", justify=tk.LEFT, wraplength=380)
        lbl_msg.pack(pady=(0, 15), padx=20, anchor=tk.W)
        
        btn_frame = tk.Frame(self, bg="#1E1E24")
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15), side=tk.BOTTOM)
        
        self.decision_made = False
        self.on_yes_cb = on_yes
        self.on_no_cb = on_no
        
        def _yes():
            self.decision_made = True
            self.destroy()
            if self.on_yes_cb:
                self.on_yes_cb()
                
        def _no():
            self.decision_made = True
            self.destroy()
            if self.on_no_cb:
                self.on_no_cb()
                
        btn_yes = tk.Button(
            btn_frame, text=_("Đồng ý (Yes)"), font=(_DIALOG_FONT, 9, "bold"),
            fg="#FFFFFF", bg="#00ADB5", activeforeground="#FFFFFF", activebackground="#008B90",
            relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=_yes
        )
        btn_yes.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        btn_no = tk.Button(
            btn_frame, text=_("Bỏ qua (No)"), font=(_DIALOG_FONT, 9, "bold"),
            fg="#FFFFFF", bg="#3A3A4A", activeforeground="#FFFFFF", activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=_no
        )
        btn_no.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
        
        self.protocol("WM_DELETE_WINDOW", _no)
        
        self.update_idletasks()
        dialog_w = 420
        dialog_h = 160
        
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        
        x = parent_x + (parent_w - dialog_w) // 2
        y = parent_y + (parent_h - dialog_h) // 2
        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")

class InfoDialog(tk.Toplevel):
    def __init__(self, parent, title, message, button_text=None, show_cancel=False, cancel_text=None, on_ok=None, on_cancel=None):
        super().__init__(parent)
        self.withdraw()  # Ẩn tạm thời để tránh nháy
        self.title(title)
        self.resizable(False, False)
        self.configure(bg="#1E1E24")
        
        try:
            icon_path = os.path.join(app_dir, "app_icon.png")
            if os.path.exists(icon_path):
                icon_img = ImageTk.PhotoImage(Image.open(icon_path))
                self.iconphoto(False, icon_img)
                self._dialog_icon_img = icon_img
        except Exception:
            pass
            
        self.attributes("-topmost", True)
        if parent and parent.state() != "withdrawn":
            self.transient(parent)
        else:
            self.lift()
            self.focus_force()
        
        lbl_title = tk.Label(self, text=title.upper(), font=(_DIALOG_FONT, 11, "bold"), fg="#00ADB5", bg="#1E1E24")
        lbl_title.pack(pady=(15, 10), padx=20, anchor=tk.W)
        
        lbl_msg = tk.Label(self, text=message, font=(_DIALOG_FONT, 9), fg="#FFFFFF", bg="#1E1E24", justify=tk.LEFT, wraplength=440)
        lbl_msg.pack(pady=(0, 15), padx=20, anchor=tk.W)
        
        btn_frame = tk.Frame(self, bg="#1E1E24")
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15), side=tk.BOTTOM)
        
        def _ok():
            self.destroy()
            if on_ok:
                on_ok()
                
        def _cancel():
            self.destroy()
            if on_cancel:
                on_cancel()
                
        if button_text is None:
            button_text = _("Đồng ý (OK)")
            
        btn_ok = tk.Button(
            btn_frame, text=button_text, font=(_DIALOG_FONT, 9, "bold"),
            fg="#FFFFFF", bg="#00ADB5", activeforeground="#FFFFFF", activebackground="#008B90",
            relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=_ok
        )
        btn_ok.pack(side=tk.RIGHT if not show_cancel else tk.LEFT, fill=tk.X if show_cancel else tk.NONE, expand=show_cancel, padx=(0, 5) if show_cancel else 0)
        
        if show_cancel:
            if cancel_text is None:
                cancel_text = _("Hủy (Cancel)")
            btn_cancel = tk.Button(
                btn_frame, text=cancel_text, font=(_DIALOG_FONT, 9, "bold"),
                fg="#FFFFFF", bg="#3A3A4A", activeforeground="#FFFFFF", activebackground="#2A2A35",
                relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=_cancel
            )
            btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
            self.protocol("WM_DELETE_WINDOW", _cancel)
        else:
            self.protocol("WM_DELETE_WINDOW", _ok)
        
        self.update_idletasks()
        # Tính toán chiều cao tự động dựa trên nội dung
        req_height = self.winfo_reqheight()
        dialog_w = 480
        dialog_h = max(160, req_height + 20)
        
        if parent:
            parent_x = parent.winfo_x()
            parent_y = parent.winfo_y()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            
            x = parent_x + (parent_w - dialog_w) // 2
            y = parent_y + (parent_h - dialog_h) // 2
            self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        else:
            self.geometry(f"{dialog_w}x{dialog_h}")
            
        self.deiconify() # Hiển thị sau khi set geometry


class ToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.close)
        self.tw = None

    def enter(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(self.tw, text=self.text, justify='left',
                         background='#ffffe0', relief='solid', borderwidth=1,
                         font=(_DIALOG_FONT, "8", "normal"), padx=2, pady=1)
        label.pack(ipadx=1)

    def close(self, event=None):
        if self.tw:
            self.tw.destroy()
            self.tw = None
