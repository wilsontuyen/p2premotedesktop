import tkinter as tk
from tkinter import ttk
import os
import sys
import time

from core.i18n import _, get_available_languages, get_language_name
from gui.window_icon import set_dialog_app_icon, hide_tk_from_taskbar

_DIALOG_FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"


def file_download_dialog_title():
    """Title cho dialog paste/clipboard: Đang tải file về..."""
    return _("Đang tải file về...")


class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, title_text, filename, total_size, on_cancel=None, host_hwnd=None, embed=False, owner_hwnd=None, dest_dir=None, reserve_finalize=False, stack_index=0, job_id=None, item_kind="file"):
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

        if not self._embed:
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
        
        self.item_kind = "folder" if str(item_kind or "").lower() == "folder" else "file"
        display_name = self._short_copy_label(
            self.filename, max_len=32, is_folder=(self.item_kind == "folder"),
        )
        if self.item_kind == "folder":
            action_text = _('Sao chép thư mục "{name}"').format(name=display_name)
        else:
            action_text = _('Sao chép tệp "{name}"').format(name=display_name)

        self.lbl_action = tk.Label(
            top_frame,
            text=action_text,
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
                try:
                    ctypes.windll.user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
                    ctypes.windll.user32.SetParent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                    ctypes.windll.user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
                except Exception:
                    pass
                tk_hwnd = int(self.frame(), 16)
                style = ctypes.windll.user32.GetWindowLongW(tk_hwnd, -16)
                style = (style | 0x40000000) & ~0x80000000
                ctypes.windll.user32.SetWindowLongW(tk_hwnd, -16, style)
                ctypes.windll.user32.SetParent(tk_hwnd, int(self.host_hwnd))
                
                rect = wintypes.RECT()
                ctypes.windll.user32.GetClientRect(int(self.host_hwnd), ctypes.byref(rect))
                py_w = rect.right - rect.left
                py_h = rect.bottom - rect.top
                
                x = max(0, (py_w - dialog_w) // 2)
                y = max(0, (py_h - dialog_h) // 2)
                ctypes.windll.user32.SetWindowPos(tk_hwnd, 0, x, y, dialog_w, dialog_h, 0x0020 | 0x0040)
                self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
            except Exception:
                self._place_on_screen(dialog_w, dialog_h)
        else:
            self._place_on_screen(dialog_w, dialog_h)

        self.deiconify()
        try:
            if parent_mapped and not self._embed:
                self.transient(parent)
        except Exception:
            pass
        try:
            self.state("normal")
        except Exception:
            pass
        if not self._embed:
            self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        try:
            self.attributes("-alpha", 1.0)
        except Exception:
            pass
        try:
            if not self._embed:
                set_dialog_app_icon(self)
        except Exception:
            pass
        self.update()
        self._apply_owner()
        try:
            if not self._embed:
                set_dialog_app_icon(self)
        except Exception:
            pass
        if not self._embed:
            try:
                self.after(0, self._force_show)
                self.after(80, self._force_show)
            except Exception:
                pass

    def _force_show(self):
        """Parent Tk withdrawn có thể nuốt deiconify lần đầu — hiện lại dialog tiến trình."""
        if self._embed:
            return
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
            user32.ShowWindow(ctypes.c_void_p(hwnd), 5)  # SW_SHOW
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
            h_hwnd = int(self.host_hwnd)
            if not user32.GetClientRect(h_hwnd, ctypes.byref(rect)):
                return None
            pt = wintypes.POINT(rect.left, rect.top)
            user32.ClientToScreen(h_hwnd, ctypes.byref(pt))
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
                ctypes.windll.user32.ScreenToClient(int(self.host_hwnd), ctypes.byref(pt))
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
    def _short_copy_label(name, max_len=42, is_folder=False):
        """Rút gọn tên file (giữ đuôi) hoặc tên folder — không cắt đầu+đuôi."""
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
        if is_folder:
            keep = max_len - len(extra) - 3
            if keep < 6:
                return (base + extra)[: max_len - 3] + "..."
            return base[:keep] + "..." + extra
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


def E(text):
    if sys.platform == "darwin":
        return text
    import platform
    if sys.platform != "win32" or platform.release() in ["7", "8", "8.1"]:
        mapping = {
            "📋": "❐", "📁": "≡", "📡": "⌂", "🔧": "¤",
            "🔄": "↻", "🔍": "⌕", "➕": "+", "❌": "X"
        }
        for k, v in mapping.items():
            text = text.replace(k, v)
    return text

def setup_windows_ui(self):
    from gui.components import ToolTip
    if getattr(self, "is_host_only", False):
        from gui.host_ui import setup_host_ui
        setup_host_ui(self)
        return
    APP_FONT_NAME = "Segoe UI" if sys.platform == "win32" else "Helvetica"
    EMOJI_FONT_10 = (APP_FONT_NAME, 10)
    EMOJI_FONT_BOLD = (APP_FONT_NAME, 9, "bold")
    EMOJI_FONT = (APP_FONT_NAME, 9)
    EMOJI_FONT_LARGE = (APP_FONT_NAME, 12, "bold")

    def setup_ui(self):
        def create_flat_button(parent, **kwargs):
            cmd = kwargs.pop('command', None)
            active_bg = kwargs.pop('activebackground', kwargs.get('bg'))
            kwargs.pop('relief', None)
            kwargs.pop('bd', None)
            kwargs.pop('highlightthickness', None)
            kwargs.pop('highlightbackground', None)
            if 'cursor' not in kwargs:
                kwargs['cursor'] = 'hand2'
            pady = kwargs.pop('pady', 5)
            padx = kwargs.pop('padx', 5)
            
            text = kwargs.get('text', '')
            if text and len(text) > 2 and text[0] in ['📋', '📁', '📡', '🔧', '🔄', '🔍', '➕', '❌', '❐', '≡', '⌂', '¤', '↻', '⌕']:
                icon_char = text[0]
                label_text = text[1:].strip()
                kwargs.pop('text')
                
                frame = tk.Frame(parent, bg=kwargs.get('bg'), cursor=kwargs.get('cursor'))
                inner = tk.Frame(frame, bg=kwargs.get('bg'), cursor=kwargs.get('cursor'))
                inner.pack(expand=True, pady=pady)
                
                font = kwargs.get('font')
                fg = kwargs.get('fg')
                bg = kwargs.get('bg')
                
                lbl_icon = tk.Label(inner, text=icon_char, font=font, fg=fg, bg=bg)
                lbl_text = tk.Label(inner, text=label_text, font=font, fg=fg, bg=bg)
                
                lbl_icon.pack(side=tk.LEFT, padx=(padx, 2), pady=(0, 4), anchor=tk.CENTER)
                lbl_text.pack(side=tk.LEFT, padx=(0, padx), anchor=tk.CENTER)
                
                def on_enter(e):
                    frame.config(bg=active_bg)
                    inner.config(bg=active_bg)
                    lbl_icon.config(bg=active_bg)
                    lbl_text.config(bg=active_bg)
                def on_leave(e):
                    frame.config(bg=bg)
                    inner.config(bg=bg)
                    lbl_icon.config(bg=bg)
                    lbl_text.config(bg=bg)
                    
                frame.bind("<Enter>", on_enter)
                inner.bind("<Enter>", on_enter)
                lbl_icon.bind("<Enter>", on_enter)
                lbl_text.bind("<Enter>", on_enter)
                frame.bind("<Leave>", on_leave)
                inner.bind("<Leave>", on_leave)
                lbl_icon.bind("<Leave>", on_leave)
                lbl_text.bind("<Leave>", on_leave)
                
                if cmd:
                    frame.bind("<Button-1>", lambda e: cmd())
                    inner.bind("<Button-1>", lambda e: cmd())
                    lbl_icon.bind("<Button-1>", lambda e: cmd())
                    lbl_text.bind("<Button-1>", lambda e: cmd())
                    
                return frame

            lbl = tk.Label(parent, pady=pady, padx=padx, **kwargs)
            lbl.bind("<Enter>", lambda e, l=lbl, c=active_bg: l.config(bg=c))
            lbl.bind("<Leave>", lambda e, l=lbl, c=kwargs.get('bg'): l.config(bg=c))
            if cmd:
                lbl.bind("<Button-1>", lambda e, c=cmd: c())
            return lbl

        # Setup Window Menu Bar
        menubar = tk.Menu(self)
        
        # 1. File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=_("Danh sách (Saved Computers)"), command=self.show_saved_computers_dialog)
        file_menu.add_command(label=E(_("Quét mạng LAN (LAN Discovery)")), command=self.show_lan_computers_dialog)
        file_menu.add_separator()
        file_menu.add_command(label=_("Nhập khẩu (Import Saved Computers)"), command=self.import_saved_computers)
        file_menu.add_command(label=_("Xuất khẩu (Export Saved Computers)"), command=self.export_saved_computers)
        file_menu.add_separator()
        file_menu.add_command(label=_("Thoát (Exit)"), command=self.destroy)
        menubar.add_cascade(label=_("File"), menu=file_menu)
        
        # 2. Options Menu
        options_menu = tk.Menu(menubar, tearoff=0)

        # Submenu: Password type
        password_menu = tk.Menu(options_menu, tearoff=0)
        password_menu.add_radiobutton(
            label=_("4 chữ số"),
            variable=self.pass_type_var, value=_("4 chữ số"),
            command=self.refresh_password
        )
        password_menu.add_radiobutton(
            label=_("5 chữ số"),
            variable=self.pass_type_var, value=_("5 chữ số"),
            command=self.refresh_password
        )
        password_menu.add_radiobutton(
            label=_("8 ký tự (chữ + số)"),
            variable=self.pass_type_var, value=_("8 ký tự (chữ + số)"),
            command=self.refresh_password
        )
        password_menu.add_separator()
        password_menu.add_command(
            label=_("Cài mật khẩu cố định..."),
            command=self.open_set_fixed_password_dialog
        )
        options_menu.add_cascade(label=_("Mật khẩu (Password)"), menu=password_menu)
        options_menu.add_separator()
        options_menu.add_checkbutton(
            label=_("Chạy khi mở máy (Run on Startup)"),
            variable=self.startup_var,
            command=self.toggle_startup
        )
        options_menu.add_command(
            label=_("Cài Zalo / Điện thoại"),
            command=self.open_set_zalo_phone_dialog
        )
        options_menu.add_separator()
        options_menu.add_command(
            label=_("Cài đặt máy chủ..."),
            command=self.show_server_settings_dialog
        )
        if sys.platform == "darwin":
            options_menu.add_separator()
            options_menu.add_command(
                label=_("Sửa lỗi quyền macOS..."),
                command=self.fix_mac_permissions
            )
        options_menu.add_separator()
        
        
        # Submenu: Language
        lang_menu = tk.Menu(options_menu, tearoff=0)
        langs = get_available_languages()
        for l in langs:
            lang_menu.add_radiobutton(label=get_language_name(l), variable=self.current_lang, value=l, command=self.change_language)
        
        # Export template
        lang_menu.add_separator()
        lang_menu.add_command(label=_("Xuất tệp ngôn ngữ mẫu..."), command=self.export_lang_template)
        lang_menu.add_command(label=_("Ngôn ngữ riêng của bạn"), command=self.import_custom_language)
        options_menu.add_cascade(label=_("Ngôn ngữ (Language)"), menu=lang_menu) # Tạm thay thế
        options_menu.add_separator()

        # Submenu: Image Quality Mode
        quality_menu = tk.Menu(options_menu, tearoff=0)
        quality_menu.add_radiobutton(label=_("Chất lượng 4K"), variable=self.quality_mode, value="quality", command=self.save_window_position)
        quality_menu.add_radiobutton(label=_("Tốc độ"), variable=self.quality_mode, value="speed", command=self.save_window_position)
        options_menu.add_cascade(label=_("Chất lượng hình ảnh"), menu=quality_menu)
        options_menu.add_separator()

        # Submenu: Theme
        theme_menu = tk.Menu(options_menu, tearoff=0)
        theme_menu.add_radiobutton(label=_("Sáng"), variable=self.current_theme, value="light", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Tối"), variable=self.current_theme, value="dark", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Xám"), variable=self.current_theme, value="gray", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Hồng"), variable=self.current_theme, value="pink", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Pha lê"), variable=self.current_theme, value="crystal", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Cam"), variable=self.current_theme, value="orange", command=self.change_theme)
        theme_menu.add_radiobutton(label=_("Đỏ"), variable=self.current_theme, value="red", command=self.change_theme)
        theme_menu.add_separator()
        theme_menu.add_radiobutton(label=_("Tùy chỉnh"), variable=self.current_theme, value="custom", command=self.change_theme)
        options_menu.add_cascade(label=_("Giao diện"), menu=theme_menu)
 
        menubar.add_cascade(label=_("Options"), menu=options_menu)
        
        # 3. Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=_("Zalo"), command=self.open_zalo)
        help_menu.add_command(label=_("Điện thoại"), command=self.open_phone_dialog)
        help_menu.add_command(label=_("About"), command=self.show_about_dialog)
        menubar.add_cascade(label=_("Help"), menu=help_menu)
        
        self.config(menu=menubar)
        

        # Header Label
        header = tk.Label(self, text=_("P2P REMOTE DESKTOP"), font=(APP_FONT_NAME, 16, "bold"), fg=self.btn_color, bg=self.bg_color)
        header.pack(pady=(15, 5))
        
        # Sub-header
        subheader = tk.Label(self, text=_("Điều khiển trực tuyến máy tính bằng HWID"), font=(APP_FONT_NAME, 9, "italic"), fg=self.text_gray, bg=self.bg_color)
        subheader.pack(pady=(0, 15))
        
        # Main Panels Container
        container = tk.Frame(self, bg=self.bg_color)
        self._main_container = container
        container.pack(fill=tk.BOTH, expand=True, padx=20)
        
        # LEFT PANEL: Allow Remote Control
        left_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        self._left_panel = left_panel
        left_panel.place(relx=0.0, rely=0.0, relwidth=0.47, relheight=0.92)
        
        lbl_allow = tk.Label(left_panel, text=_("CHO PHÉP ĐIỀU KHIỂN"), font=(APP_FONT_NAME, 11, "bold"), fg=self.btn_color, bg=self.card_color)
        lbl_allow.pack(pady=(15, 10))
        
        lbl_id = tk.Label(left_panel, text=_("Mã ID của bạn:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_id.pack(anchor=tk.W, padx=20)
        
        id_frame = tk.Frame(left_panel, bg=self.card_color)
        self._id_frame = id_frame
        id_frame.pack(fill=tk.X, padx=20, pady=(5, 12))
        
        self.my_id_label = tk.Label(id_frame, text=self.my_id_formatted, font=(APP_FONT_NAME, 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0, height=1)
        self.my_id_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_id_btn = create_flat_button(id_frame, text=E("📋"), font=EMOJI_FONT_10, fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, padx=2, pady=1, width=3, command=lambda: self.copy_to_clipboard(self.my_id_formatted))
        copy_id_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(copy_id_btn, _("Sao chép"))
        
        lbl_pass = tk.Label(left_panel, text=_("Mật khẩu kết nối:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_pass.pack(anchor=tk.W, padx=20)
        
        pass_frame = tk.Frame(left_panel, bg=self.card_color)
        self._pass_frame = pass_frame
        pass_frame.pack(fill=tk.X, padx=20, pady=(5, 5))
        
        self.my_pass_label = tk.Label(pass_frame, text=self.my_password, font=(APP_FONT_NAME, 16, "bold"), fg=self.text_white, bg=self.entry_bg, bd=0)
        self.my_pass_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        copy_pass_btn = create_flat_button(pass_frame, text=E("📋"), font=EMOJI_FONT_10, fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, padx=2, pady=1, width=3, command=lambda: self.copy_to_clipboard(self.my_password))
        copy_pass_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(copy_pass_btn, _("Sao chép"))
        
        refresh_btn = create_flat_button(pass_frame, text="↻", font=(APP_FONT_NAME, 10, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, padx=2, pady=1, width=3, command=self.refresh_password)
        refresh_btn.pack(side=tk.RIGHT, padx=(5, 0))
        ToolTip(refresh_btn, _("Đổi mật khẩu"))

        # Nhãn hiển thị trạng thái mật khẩu cố định
        self.fixed_pass_indicator = tk.Label(left_panel, text="", font=(APP_FONT_NAME, 8, "italic"), fg="#2ECC71", bg=self.card_color)
        self.fixed_pass_indicator.pack(anchor=tk.W, padx=20, pady=0)
        self.update_fixed_password_indicator()

        # Button to Copy both ID & Password at once
        copy_all_btn = create_flat_button(left_panel, text=E(_("📋 Sao chép cả ID & Mật khẩu")), font=EMOJI_FONT_BOLD, fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, command=self.copy_id_and_password)
        copy_all_btn.pack(side=tk.TOP, padx=20, fill=tk.X, pady=(0, 5))

        # Nút gọi Danh sách máy tính đã lưu
        saved_list_btn = create_flat_button(left_panel, text=E(_("📁 Danh sách máy tính đã lưu")), font=EMOJI_FONT, fg="#FFFFFF", bg="#5B2C8E", activebackground="#7B3FA8", command=self.show_saved_computers_dialog)
        saved_list_btn.pack(side=tk.TOP, padx=20, fill=tk.X, pady=(0, 10))
        
        # RIGHT PANEL: Control Remote Computer
        right_panel = tk.Frame(container, bg=self.card_color, bd=0, relief=tk.FLAT)
        self._right_panel = right_panel
        right_panel.place(relx=0.53, rely=0.0, relwidth=0.47, relheight=0.92)
        
        lbl_control = tk.Label(right_panel, text=_("ĐIỀU KHIỂN ĐỐI TÁC"), font=(APP_FONT_NAME, 11, "bold"), fg=self.btn_color, bg=self.card_color)
        lbl_control.pack(pady=(15, 10))
        
        lbl_p_id = tk.Label(right_panel, text=_("Nhập ID đối tác:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_p_id.pack(anchor=tk.W, padx=20)
        
        self.entry_p_id = tk.Entry(right_panel, textvariable=self.partner_id_var, font=(APP_FONT_NAME, 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, relief=tk.FLAT, bd=0, highlightthickness=0, highlightbackground=self.card_color)
        self.entry_p_id.pack(pady=(5, 10), padx=20, fill=tk.X)
        
        lbl_p_pass = tk.Label(right_panel, text=_("Nhập Mật khẩu đối tác:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color)
        lbl_p_pass.pack(anchor=tk.W, padx=20)
        
        self.entry_p_pass = tk.Entry(right_panel, textvariable=self.partner_pass_var, font=(APP_FONT_NAME, 13), fg=self.entry_fg, bg=self.entry_bg, insertbackground=self.text_white, show="*", relief=tk.FLAT, bd=0, highlightthickness=0, highlightbackground=self.card_color)
        self.entry_p_pass.pack(pady=(5, 35), padx=20, fill=tk.X)
        
        # Bind Enter keys to trigger Connection immediately
        self.entry_p_id.bind("<Return>", lambda event: self.click_connect())
        self.entry_p_id.bind("<KP_Enter>", lambda event: self.click_connect())
        self.entry_p_pass.bind("<Return>", lambda event: self.click_connect())
        self.entry_p_pass.bind("<KP_Enter>", lambda event: self.click_connect())
        
        # Container to hold CONNECT & ADD (+) buttons
        btn_container = tk.Frame(right_panel, bg=self.card_color)
        btn_container.pack(padx=20, fill=tk.X)
        
        self.connect_btn = create_flat_button(btn_container, text=_("KẾT NỐI (CONNECT)"), font=(APP_FONT_NAME, 11, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, padx=10, pady=2, command=self.click_connect)
        self.connect_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Add button with a blue "+"
        self.add_partner_btn = create_flat_button(btn_container, text=E("➕"), font=EMOJI_FONT_LARGE, fg=self.text_white, bg="#007ACC", activebackground="#005A9E", pady=2, width=4, command=self.add_current_partner_to_saved)
        self.add_partner_btn.pack(side=tk.RIGHT, padx=(8, 0))
        ToolTip(self.add_partner_btn, _("Thêm máy tính"))

        # LAN Discovery button - Quét máy trong mạng nội bộ
        lan_btn = create_flat_button(right_panel, text=E(_("📡 Quét mạng LAN (LAN Only)")), font=EMOJI_FONT_BOLD, fg="#FFFFFF", bg="#5B2C8E", activebackground="#7B3FA8", pady=3, command=self.show_lan_computers_dialog)
        lan_btn.pack(side=tk.TOP, padx=20, fill=tk.X, pady=(5, 10))

        # Attach Context Menus for Copy & Paste
        self.make_context_menu(self.entry_p_id)
        self.make_context_menu(self.entry_p_pass)
        
        # BOTTOM STATUS BAR
        status_bar = tk.Frame(self, bg=self.entry_bg, height=25)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl_status = tk.Label(status_bar, textvariable=self.status_var, font=(APP_FONT_NAME, 8, "italic"), fg="#8A8A9A", bg=self.entry_bg, anchor=tk.W)
        self.lbl_status.pack(fill=tk.BOTH, padx=10, pady=2)
        
        # Khởi chạy icon khay hệ thống ngay khi bật ứng dụng
        if not self.is_headless:
            self.setup_tray_icon()
            
    setup_ui(self)
        
    # Auto formatting spaces inside ID: "123 456 789 012"
