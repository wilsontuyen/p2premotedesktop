import tkinter as tk
from tkinter import ttk
import os
import time
import sys
_DIALOG_FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"
from utils.logger import log_debug, log_overwrite_conflict
from core.i18n import _

try:
    from PIL import Image, ImageTk
except ImportError:
    pass

from gui.window_icon import install_toplevel_app_icon, set_dialog_app_icon, hide_tk_from_taskbar
install_toplevel_app_icon()

from gui.windows_ui import ProgressDialog  # re-export; class lives in windows_ui

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
    def __init__(self, parent, filename, source_info, dest_info, has_multiple=False, on_done=None, owner_hwnd=None):
        super().__init__(parent)
        self.withdraw()
        # Viewer full-app: parent là Tk ẩn — dialog phải hiện trên cửa sổ pygame.
        self.owner_hwnd = None
        try:
            if owner_hwnd:
                self.owner_hwnd = int(owner_hwnd)
                if sys.platform == "win32":
                    import ctypes
                    user32 = ctypes.windll.user32
                    if not user32.IsWindow(self.owner_hwnd) or not user32.IsWindowVisible(self.owner_hwnd) or user32.IsIconic(self.owner_hwnd):
                        self.owner_hwnd = None
        except Exception:
            self.owner_hwnd = None
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
        self._on_done = on_done
        self._finished = False
        # Chặn click Paste/menu còn sót — nếu không dialog nháy rồi chọn Replace ngay.
        self._clicks_armed = False
        try:
            log_overwrite_conflict(
                f"ClassicCopyDialog.__init__ file={filename!r} "
                f"dest={(dest_info or {}).get('path')!r} has_multiple={has_multiple}"
            )
        except Exception:
            pass
        
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
                if not getattr(self, "_clicks_armed", False):
                    return "break"
                self._finish(action_val)
                
            for w in get_all_children(frame):
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                # ButtonRelease: tránh nhận ButtonDown từ thao tác Paste trước đó.
                w.bind("<Button-1>", lambda e: "break" if not self._clicks_armed else None)
                w.bind("<ButtonRelease-1>", on_click)
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
        
        target_loc_path = dest_info.get("path") or source_info.get("path")
        tk.Label(info_text1, text=filename, font=(_DIALOG_FONT, 9, "bold"), fg="#000000", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
        tk.Label(info_text1, text=format_location_info(target_loc_path), font=(_DIALOG_FONT, 9), fg="#555555", bg="#FFFFFF", anchor="w").pack(fill=tk.X)
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
        # Chặn Hủy nhận click Paste sót (đóng dialog ngay → không hỏi).
        def _cancel_click(event=None):
            if not getattr(self, "_clicks_armed", False):
                return "break"
            self.on_cancel()
        btn_cancel.configure(command=lambda: None)
        btn_cancel.bind("<ButtonRelease-1>", _cancel_click)
        
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
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except Exception:
            pass
        try:
            from gui.window_icon import set_dialog_app_icon
            set_dialog_app_icon(self)
        except Exception:
            pass
        self._apply_owner()
        self._force_show_over_owner()
        try:
            self.after(0, self._force_show_over_owner)
            self.after(80, self._force_show_over_owner)
        except Exception:
            pass
        # Chỉ nhận click sau khi chuột đã nhả + grace — tránh Paste menu tự chọn Replace.
        self.after(50, self._arm_clicks_when_idle)

    def _hwnd(self):
        try:
            return int(self.frame(), 16)
        except Exception:
            return 0

    def _apply_owner(self):
        """Gắn dialog thuộc cửa sổ viewer — không bị pygame che / parent Tk ẩn nuốt."""
        if not self.owner_hwnd or sys.platform != "win32":
            return
        hwnd = self._hwnd()
        if not hwnd:
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            owner = int(self.owner_hwnd)
            if not user32.IsWindow(owner) or not user32.IsWindowVisible(owner) or user32.IsIconic(owner):
                return
            GWLP_HWNDPARENT = -8
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                ctypes.windll.user32.SetWindowLongPtrW(
                    ctypes.c_void_p(hwnd), GWLP_HWNDPARENT, ctypes.c_void_p(owner)
                )
            else:
                ctypes.windll.user32.SetWindowLongW(hwnd, GWLP_HWNDPARENT, owner)
        except Exception:
            pass

    def _force_show_over_owner(self):
        try:
            if not self.winfo_exists():
                return
            self.attributes("-alpha", 1.0)
            self.attributes("-topmost", True)
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass
        if sys.platform != "win32":
            return
        try:
            import ctypes
            hwnd = self._hwnd()
            if not hwnd:
                return
            user32 = ctypes.windll.user32
            HWND_TOPMOST = -1
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_SHOWWINDOW = 0x0040
            user32.SetWindowPos(
                ctypes.c_void_p(hwnd), HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW,
            )
            user32.BringWindowToTop(ctypes.c_void_p(hwnd))
            user32.ShowWindow(ctypes.c_void_p(hwnd), 5)
            try:
                user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
            except Exception:
                pass
        except Exception:
            pass
        
    def _arm_clicks_when_idle(self):
        """Chờ LMB/RMB nhả rồi mới cho bấm Replace/Skip/Hủy."""
        if self._finished or not self.winfo_exists():
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            lmb = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
            rmb = bool(user32.GetAsyncKeyState(0x02) & 0x8000)
        except Exception:
            lmb = rmb = False
        if lmb or rmb:
            self.after(50, self._arm_clicks_when_idle)
            return
        # Grace thêm: nút vừa nhả vẫn có thể gửi ButtonRelease vào dialog.
        def _arm():
            if self._finished or not self.winfo_exists():
                return
            self._clicks_armed = True
            try:
                log_overwrite_conflict("ClassicCopyDialog clicks ARMED")
            except Exception:
                pass
        self.after(400, _arm)
        
    def _finish(self, action_val):
        if self._finished:
            return
        if action_val != "cancel" and not getattr(self, "_clicks_armed", False):
            try:
                log_overwrite_conflict(
                    f"ClassicCopyDialog IGNORE click (not armed) action={action_val!r}"
                )
            except Exception:
                pass
            return
        self._finished = True
        self.choice = action_val
        try:
            log_overwrite_conflict(
                f"ClassicCopyDialog._finish choice={action_val!r} armed={self._clicks_armed}"
            )
        except Exception:
            pass
        cb = self._on_done
        self._on_done = None
        if cb:
            try:
                cb(action_val)
            except Exception:
                pass
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    def on_cancel(self):
        # Cho phép đóng bằng X ngay; nút Hủy cần armed (tránh click sót).
        if self._finished:
            return
        self._clicks_armed = True
        self._finish("cancel")

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
