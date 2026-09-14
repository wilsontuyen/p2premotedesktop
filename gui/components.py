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

from gui.window_icon import install_toplevel_app_icon, set_dialog_app_icon, hide_tk_from_taskbar
install_toplevel_app_icon()

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
        self.resizable(False, False)
        self.configure(bg="#FFFFFF")
        # Không dùng Toplevel.geometry (bị DPI scale) — layout 520x420 bị vỡ, không bấm được.
        
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
        self.title(_("Sao chép tệp"))
        
        lbl_title = tk.Label(
            self, text=_("Đã có tệp cùng tên trong thư mục này."),
            font=(_DIALOG_FONT, 12), fg="#003399", bg="#FFFFFF", anchor="w", justify=tk.LEFT,
            wraplength=460
        )
        lbl_title.pack(fill=tk.X, padx=24, pady=(20, 2))
        
        lbl_sub = tk.Label(
            self, text=_("Bấm vào tệp bạn muốn giữ lại"),
            font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w", wraplength=460
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
                from core.i18n import _current_lang
                dt = datetime.datetime.fromtimestamp(timestamp)
                if _current_lang == "en":
                    return dt.strftime("%m/%d/%Y %I:%M %p")
                return dt.strftime("%d/%m/%Y %H:%M")
            except:
                return _("Không xác định")
                
        def format_location_info(file_path):
            if not file_path:
                return _("Vị trí không xác định")
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
        
        lbl_title1 = tk.Label(right_content1, text=_("Sao chép và thay thế"), font=(_DIALOG_FONT, 10, "bold"), fg="#0066CC", bg="#FFFFFF", anchor="w")
        lbl_title1.pack(fill=tk.X)
        
        lbl_desc1 = tk.Label(right_content1, text=_("Thay thế tệp trong thư mục đích bằng tệp bạn đang sao chép:"), font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w", wraplength=430, justify=tk.LEFT)
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
        tk.Label(info_text1, text=_("Kích thước: {size}").format(size=format_size(source_info.get("size", 0))), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text1, text=_("Ngày sửa đổi: {date}").format(date=format_time(source_info.get("mtime", 0))), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        
        setup_command_link(link1, "replace")
        
        # Link 2: Don't Copy
        link2 = tk.Frame(self, bg="#FFFFFF")
        link2.pack(fill=tk.X, padx=24, pady=5)
        
        lbl_arrow2 = tk.Label(link2, text="→", font=(_DIALOG_FONT, 16, "bold"), fg="#0066CC", bg="#FFFFFF")
        lbl_arrow2.pack(side=tk.LEFT, anchor="n", padx=(5, 5))
        
        right_content2 = tk.Frame(link2, bg="#FFFFFF")
        right_content2.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        lbl_title2 = tk.Label(right_content2, text=_("Không sao chép"), font=(_DIALOG_FONT, 10, "bold"), fg="#0066CC", bg="#FFFFFF", anchor="w")
        lbl_title2.pack(fill=tk.X)
        
        lbl_desc2 = tk.Label(right_content2, text=_("Không thay đổi tệp nào. Giữ nguyên tệp trong thư mục đích:"), font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w", wraplength=430, justify=tk.LEFT)
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
        tk.Label(info_text2, text=_("Kích thước: {size}").format(size=format_size(dest_info.get("size", 0))), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text2, text=_("Ngày sửa đổi: {date}").format(date=format_time(dest_info.get("mtime", 0))), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        
        setup_command_link(link2, "skip")
        
        sep = tk.Frame(self, height=1, bg="#D0D0D0", bd=0)
        sep.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 0))
        
        bottom_bar = tk.Frame(self, bg="#F0F0F0", height=48)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_bar.pack_propagate(False)
        
        self.var_all = tk.BooleanVar()
        if has_multiple:
            chk = tk.Checkbutton(
                bottom_bar, text=_("Áp dụng cho mọi xung đột"), font=(_DIALOG_FONT, 9),
                variable=self.var_all, bg="#F0F0F0", activebackground="#F0F0F0", bd=0
            )
            chk.pack(side=tk.LEFT, padx=24, pady=10)
            
        btn_cancel = tk.Button(
            bottom_bar, text=_("Hủy"), font=(_DIALOG_FONT, 9), width=10,
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

        # Chiều cao theo nội dung (DPI 125%/150% làm 520x420 cắt mất nút Hủy).
        self.update_idletasks()
        w = max(int(self.winfo_reqwidth() or 0), 520)
        h = max(int(self.winfo_reqheight() or 0) + 8, 360)
        ws = int(self.winfo_screenwidth() or w)
        hs = int(self.winfo_screenheight() or h)
        w = min(w, max(400, ws - 40))
        h = min(h, max(320, hs - 80))
        x = max(0, (ws - w) // 2)
        y = max(0, (hs - h) // 2)
        geo = "%dx%d+%d+%d" % (w, h, x, y)
        try:
            self.tk.call("wm", "geometry", self._w, geo)
        except Exception:
            self.geometry(geo)
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            from gui.window_icon import set_dialog_app_icon
            set_dialog_app_icon(self)
        except Exception:
            pass
        
    def on_cancel(self):
        self.choice = "cancel"
        self.destroy()

class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, title_text, filename, total_size, on_cancel=None, host_hwnd=None, embed=False, owner_hwnd=None, dest_dir=None, reserve_finalize=False, stack_index=0, job_id=None):
        super().__init__(parent)
        self.parent_window = parent
        self.host_hwnd = host_hwnd
        # owner_hwnd: cửa sổ client sở hữu dialog (GWLP_HWNDPARENT), không phải vùng remote.
        # embed/SetParent chỉ dùng File Manager (cùng toolkit). Clipboard không kẹp pygame.
        self.owner_hwnd = self._toplevel_hwnd(owner_hwnd)
        self._embed = bool(embed and host_hwnd and sys.platform == "win32")
        parent_mapped = False
        try:
            parent_mapped = bool(parent and parent.winfo_exists() and parent.winfo_ismapped() and parent.state() != "withdrawn")
        except Exception:
            parent_mapped = False
        self._helper_parent = not parent_mapped
        self.withdraw()
        if self._embed:
            self.attributes("-alpha", 0.0)
            self.overrideredirect(True)
        else:
            try:
                self.title(title_text)
            except Exception:
                pass
            self.resizable(False, False)
        self.configure(bg="#FFFFFF", highlightbackground="#CCCCCC", highlightthickness=1)

        self._drag_offset_x = 0
        self._drag_offset_y = 0
        if self._embed:
            title_bg = "#F3F3F3"
            self.title_bar = tk.Frame(self, bg=title_bg, height=28)
            self.title_bar.pack(fill=tk.X, side=tk.TOP)
            self.title_bar.pack_propagate(False)
            self.title_lbl = tk.Label(self.title_bar, text=title_text, bg=title_bg, fg="#333333", font=(_DIALOG_FONT, 9, "bold"))
            self.title_lbl.pack(side=tk.LEFT, padx=10, pady=4)
            for widget in (self.title_bar, self.title_lbl):
                widget.bind("<ButtonPress-1>", self._start_drag)
                widget.bind("<B1-Motion>", self._do_drag)
        else:
            self.title_bar = None
            self.title_lbl = None

        self.attributes("-topmost", True)
        self.total_size = max(0, int(total_size or 0))
        self.filename = str(filename) if filename is not None else "Unknown"
        self._title_text = title_text
        self._received = 0
        self._copied = 0
        self._copy_total = self._guess_copy_total(dest_dir, self.total_size) if reserve_finalize else 0
        self._phase = "download"
        self._done = False
        self._last_ui = 0.0
        self.start_time = time.time()
        self.history = [(self.start_time, 0)]
        self.on_cancel = on_cancel
        self.stack_index = max(0, int(stack_index or 0))
        self.job_id = job_id
        
        top_frame = tk.Frame(self, bg="#FFFFFF")
        top_frame.pack(fill=tk.X, padx=12, pady=(6, 2))
        
        display_name = self._short_copy_label(self.filename, max_len=32)

        self.lbl_action = tk.Label(
            top_frame,
            text=_('Sao chép tệp "{name}"').format(name=display_name),
            font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF",
            anchor="w"
        )
        self.lbl_action.pack(fill=tk.X)

        dest_row = tk.Frame(top_frame, bg="#FFFFFF")
        dest_row.pack(fill=tk.X, pady=(2, 0))
        self.lbl_percent = tk.Label(
            dest_row, text="0%", font=(_DIALOG_FONT, 16, "bold"),
            fg="#0066CC", bg="#FFFFFF", anchor="e"
        )
        self.lbl_percent.pack(side=tk.RIGHT, padx=(8, 0))

        dest_text = self._format_dest_dir(dest_dir)
        if dest_text:
            self.lbl_dest = tk.Label(
                dest_row,
                text=_("Thư mục đích") + ": " + dest_text,
                font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF",
                anchor="w", justify="left", wraplength=300
            )
            self.lbl_dest.pack(side=tk.LEFT, fill=tk.X, expand=True)
        else:
            self.lbl_dest = None
            
        self.lbl_stats1 = tk.Label(
            top_frame,
            text=_("({done} trên {total})  {percent}%  {speed}  {eta}").format(
                done="0 B", total=self.format_size(self._work_total()), percent=0, speed=_("-- MB/s"), eta=_("-- giây")
            ),
            font=(_DIALOG_FONT, 9), fg="#000000", bg="#FFFFFF", anchor="w"
        )
        self.lbl_stats1.pack(fill=tk.X, pady=(2, 2))
        
        self.prog1 = ttk.Progressbar(top_frame, orient="horizontal", length=360, mode="determinate")
        self.prog1.pack(fill=tk.X)
        
        bottom_frame = tk.Frame(self, bg="#F0F0F0", height=34)
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
            btn_cancel.pack(side=tk.RIGHT, padx=12, pady=4)
            def btn_enter(event): btn_cancel.configure(bg="#E5F1FB", bd=1)
            def btn_leave(event): btn_cancel.configure(bg="#E1E1E1", bd=1)
            btn_cancel.bind("<Enter>", btn_enter)
            btn_cancel.bind("<Leave>", btn_leave)
            self.protocol("WM_DELETE_WINDOW", self.trigger_cancel)
            
        self.update_idletasks()
        dialog_w = 400
        dialog_h = max(int(self.winfo_reqheight() or 0), 1)
        
        if self._embed:
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
                ctypes.windll.user32.SetWindowPos(tk_hwnd, 0, x, y, dialog_w, dialog_h, 0x0020)
                self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
            except Exception:
                self._place_on_screen(dialog_w, dialog_h)
        else:
            self._place_on_screen(dialog_w, dialog_h)

        self.deiconify()
        try:
            if parent_mapped:
                self.transient(parent)
        except Exception:
            pass
        try:
            self.state("normal")
        except Exception:
            pass
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass
        try:
            if self._embed:
                hide_tk_from_taskbar(self)
            set_dialog_app_icon(self)
        except Exception:
            pass
        self.update()
        self._apply_owner()
        try:
            set_dialog_app_icon(self)
        except Exception:
            pass
        try:
            self.after(0, self._force_show)
            self.after(80, self._force_show)
        except Exception:
            pass

    def _force_show(self):
        """Parent Tk withdrawn có thể nuốt deiconify lần đầu — hiện lại dialog tiến trình."""
        try:
            if not self.winfo_exists():
                return
            self.deiconify()
            self.attributes("-alpha", 1.0)
            self.attributes("-topmost", True)
            self.lift()
            set_dialog_app_icon(self)
        except Exception:
            pass

    def _toplevel_hwnd(self, hwnd):
        if not hwnd or sys.platform != "win32":
            return hwnd
        try:
            import ctypes
            user32 = ctypes.windll.user32
            root = user32.GetAncestor(ctypes.c_void_p(int(hwnd)), 2)  # GA_ROOT
            return int(root) if root else int(hwnd)
        except Exception:
            return hwnd

    def _apply_owner(self):
        """Gắn dialog thuộc cửa sổ client (owner), không biến thành child của vùng remote."""
        if self._embed or not self.owner_hwnd or sys.platform != "win32":
            return
        hwnd = self._hwnd()
        if not hwnd:
            return
        try:
            import ctypes
            owner = int(self.owner_hwnd)
            GWLP_HWNDPARENT = -8
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                ctypes.windll.user32.SetWindowLongPtrW(ctypes.c_void_p(hwnd), GWLP_HWNDPARENT, ctypes.c_void_p(owner))
            else:
                ctypes.windll.user32.SetWindowLongW(hwnd, GWLP_HWNDPARENT, owner)
        except Exception:
            pass

    def _owner_window_screen_rect(self):
        if not (getattr(self, "owner_hwnd", None) and sys.platform == "win32"):
            return None
        try:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            if not ctypes.windll.user32.GetWindowRect(int(self.owner_hwnd), ctypes.byref(rect)):
                return None
            return (rect.left, rect.top, rect.right, rect.bottom)
        except Exception:
            return None

    def _place_on_screen(self, dialog_w, dialog_h):
        geo = "%dx%d" % (int(dialog_w), int(dialog_h))
        try:
            self.tk.call("wm", "geometry", self._w, geo)
        except Exception:
            self.geometry(geo)
        self.update_idletasks()
        my_w = int(dialog_w)
        my_h = int(dialog_h)
        # Clipboard: căn giữa cửa sổ client (owner), không dùng client-area pygame/host view.
        bounds = None
        if not self._embed:
            bounds = self._owner_window_screen_rect()
        if not bounds:
            bounds = self._host_client_screen_rect()
        if not bounds:
            p = self._usable_tk_parent()
            if p:
                bounds = (p.winfo_rootx(), p.winfo_rooty(),
                          p.winfo_rootx() + p.winfo_width(),
                          p.winfo_rooty() + p.winfo_height())
        if bounds:
            left, top, right, bottom = bounds
            # Parent helper ẩn ngoài màn hình → đừng đặt dialog theo nó.
            if right <= 0 or bottom <= 0 or left < -500 or top < -500:
                bounds = None
        if bounds:
            left, top, right, bottom = bounds
            x = left + max(0, (right - left - my_w) // 2)
            y = top + max(0, (bottom - top - my_h) // 2)
        else:
            x = (self.winfo_screenwidth() - my_w) // 2
            y = (self.winfo_screenheight() - my_h) // 2
        y += int(getattr(self, "stack_index", 0) or 0) * (my_h + 8)
        self._move_to_screen(x, y)

    def trigger_cancel(self):
        cb = self.on_cancel
        self.on_cancel = None
        if cb:
            try:
                cb()
            except Exception:
                pass
        try:
            self.destroy()
        except Exception:
            pass

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

    def _virtual_screen_rect(self):
        if sys.platform != "win32":
            return (0, 0, self.winfo_screenwidth(), self.winfo_screenheight())
        try:
            import ctypes
            user32 = ctypes.windll.user32
            SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
            SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
            left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
            top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            return (left, top, left + user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
                    top + user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
        except Exception:
            return (0, 0, self.winfo_screenwidth(), self.winfo_screenheight())

    def _clamp_screen_pos(self, screen_x, screen_y):
        my_w = max(self.winfo_width(), 1)
        my_h = max(self.winfo_height(), 1)
        bounds = None
        if self._embed:
            bounds = self._host_client_screen_rect()
            if not bounds:
                p = self._usable_tk_parent()
                if p:
                    bounds = (p.winfo_rootx(), p.winfo_rooty(),
                              p.winfo_rootx() + p.winfo_width(),
                              p.winfo_rooty() + p.winfo_height())
        else:
            # Clipboard: thuộc cửa sổ client nhưng kéo tự do trên desktop, không kẹt trong vùng remote.
            bounds = self._virtual_screen_rect()
        if bounds:
            left, top, right, bottom = bounds
            max_x = left if (right - left) <= my_w else right - my_w
            max_y = top if (bottom - top) <= my_h else bottom - my_h
            screen_x = max(left, min(screen_x, max_x))
            screen_y = max(top, min(screen_y, max_y))
        return screen_x, screen_y

    def _move_to_screen(self, screen_x, screen_y):
        screen_x, screen_y = self._clamp_screen_pos(screen_x, screen_y)
        if self._embed:
            try:
                import ctypes
                from ctypes import wintypes
                pt = wintypes.POINT(int(screen_x), int(screen_y))
                ctypes.windll.user32.ScreenToClient(self.host_hwnd, ctypes.byref(pt))
                hwnd = self._hwnd()
                if hwnd:
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

    @staticmethod
    def _short_copy_label(name, max_len=42):
        """Rút gọn tên file, giữ đuôi — không cắt đầu+đuôi (trông như dính 2 tên)."""
        raw = str(name or "Unknown").replace("\\", "/")
        extra = ""
        marker = " và "
        if marker in raw:
            idx = raw.find(marker)
            extra = raw[idx:]
            raw = raw[:idx]
        base = os.path.basename(raw) or raw
        if len(base) + len(extra) <= max_len:
            return base + extra
        root, ext = os.path.splitext(base)
        room = max_len - len(extra) - len(ext) - 3
        if room < 6:
            return (base + extra)[: max_len - 3] + "..."
        return root[:room] + "..." + ext + extra

    @staticmethod
    def _guess_copy_total(dest_dir, file_total):
        """Paste sang ổ khác thư mục tạm thì còn một lượt copy cùng tổng n file."""
        if not dest_dir or file_total <= 0:
            return 0
        try:
            dest_drive = os.path.splitdrive(os.path.abspath(str(dest_dir)))[0].lower()
            temp_drive = os.path.splitdrive(os.path.abspath(os.environ.get("TEMP") or "C:\\"))[0].lower()
            if dest_drive and dest_drive != temp_drive:
                return file_total
        except Exception:
            return file_total
        return 0

    def _work_total(self):
        """Mẫu số MB: dung lượng file thật — không cộng lượt copy nội bộ, không reset về 0."""
        return max(1, int(self.total_size) or 1)

    def _work_done(self):
        recv = min(self._work_total(), max(0, int(self._received or 0)))
        if self._phase in ("finalize", "done"):
            return self._work_total()
        return recv

    def begin_finalize(self, total_bytes=0):
        extra = max(0, int(total_bytes or 0))
        if extra and extra > self._copy_total:
            self._copy_total = extra
        self._phase = "finalize"
        self._received = max(int(self._received or 0), int(self.total_size or 0))
        self._title_text = _("Đang chuyển vào thư mục đích...")
        self._render_progress(status=self._title_text, force=True)

    def add_finalize_bytes(self, n):
        try:
            self._copied += max(0, int(n or 0))
        except Exception:
            return
        self._render_progress(status=self._title_text)

    def mark_complete(self):
        self._done = True
        self._phase = "done"
        self._received = max(self._received, self.total_size)
        self._copied = max(self._copied, self._copy_total)
        self._render_progress(force=True)

    def update_progress(self, sent_bytes, status=None):
        if self._phase in ("finalize", "done"):
            try:
                self._received = max(int(self._received or 0), int(sent_bytes or 0))
            except Exception:
                pass
            return
        try:
            self._received = max(0, int(sent_bytes or 0))
        except Exception:
            return
        self._render_progress(status=status)

    def _bar_percent(self, done, work_total):
        if self._done:
            return 100
        if work_total <= 0:
            return 0
        dl = int(done * 100 / work_total)
        if self._phase != "finalize" or int(self._copy_total or 0) <= 0:
            return max(0, min(99, dl))
        if int(self._copied or 0) >= int(self._copy_total or 0):
            return 100
        return 99

    def _render_progress(self, status=None, force=False):
        now = time.time()
        if not force and (now - self._last_ui) < 0.05:
            return
        self._last_ui = now
        if status:
            self._title_text = status
        status_text = self._title_text

        def _do_update():
            try:
                work_total = self._work_total()
                done = self._work_done()
                if self._done:
                    percent = 100
                    done = work_total
                else:
                    percent = self._bar_percent(done, work_total)

                self.prog1["value"] = percent
                try:
                    self.lbl_percent.config(text=f"{percent}%")
                    title = status_text if status_text else self._title_text
                    full_title = f"{title}  —  {percent}%"
                    if self.title_lbl is not None:
                        self.title_lbl.config(text=full_title)
                    else:
                        self.title(full_title)
                except Exception:
                    pass

                current_time = time.time()
                self.history.append((current_time, done))
                while len(self.history) > 1 and current_time - self.history[0][0] > 2.0:
                    self.history.pop(0)

                elapsed_time = current_time - self.history[0][0]
                bytes_in_window = done - self.history[0][1]
                speed = (bytes_in_window / elapsed_time) if elapsed_time > 0 and bytes_in_window > 0 else 0
                remaining_bytes = max(0, work_total - done)

                if self._done:
                    time_str = _("0 giây")
                    speed_str = f"{self.format_speed(speed)}" if speed > 0 else _("-- MB/s")
                elif speed > 0 and remaining_bytes > 0:
                    remaining_time = remaining_bytes / speed
                    mins = int(remaining_time // 60)
                    secs = int(remaining_time % 60)
                    if mins > 0:
                        time_str = _("{m} phút {n} giây").format(m=mins, n=secs)
                    else:
                        time_str = _("{n} giây").format(n=secs)
                    speed_str = f"{self.format_speed(speed)}"
                else:
                    speed_str = f"{self.format_speed(speed)}" if speed > 0 else _("-- MB/s")
                    time_str = _("-- giây")

                self.lbl_stats1.config(
                    text=_("({done} trên {total})  {percent}%  {speed}  {eta}").format(
                        done=self.format_size(done),
                        total=self.format_size(work_total),
                        percent=percent,
                        speed=speed_str,
                        eta=time_str,
                    )
                )
            except Exception:
                pass
        try:
            self.after(0, _do_update)
        except Exception:
            pass

    def safe_destroy(self):
        try: self.after(0, self.destroy)
        except: pass

    @staticmethod
    def _format_dest_dir(dest_dir):
        if not dest_dir:
            return ""
        path = str(dest_dir).strip().rstrip("\\/")
        if not path:
            return ""
        if len(path) <= 56:
            return path
        return path[:20] + "..." + path[-33:]

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
