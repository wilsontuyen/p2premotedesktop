"""Saved computers list: XML I/O, dialog UI, and online-status scan workers."""
import os
import sys
import json
import shutil
import time
import queue
import threading
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import messagebox

from core.i18n import _
from core.host import encrypt_text, decrypt_text
from gui.components import InfoDialog
from network.socket_utils import APP_KEY, send_msg

if sys.platform == "darwin":
    APP_FONT_NAME = "Helvetica"
else:
    APP_FONT_NAME = "Segoe UI"

EMOJI_FONT = (APP_FONT_NAME, 9)
EMOJI_FONT_BOLD = (APP_FONT_NAME, 9, "bold")


def E(text):
    if sys.platform == "darwin":
        return text
    import platform
    if sys.platform != "win32" or platform.release() in ["7", "8", "8.1"]:
        mapping = {
            "📋": "❐", "📁": "≡", "📡": "⌂", "🔧": "¤",
            "🔄": "↻", "🔍": "⌕", "➕": "+", "❌": "X",
        }
        for k, v in mapping.items():
            text = text.replace(k, v)
    return text


def get_app_data_dir():
    """App data / config directory (shared with window_config.json path in app)."""
    if sys.platform != "win32":
        if sys.platform == "darwin":
            path = os.path.expanduser("~/Library/Application Support/RemoteDesktopP2P")
        else:
            if os.path.exists("/opt/p2p_remote"):
                path = "/opt/p2p_remote/config"
            else:
                path = os.path.expanduser("~/.config/RemoteDesktopP2P")
        try:
            os.makedirs(path, exist_ok=True)
            os.chmod(path, 0o777)
        except Exception:
            pass
        return path

    # Windows: ưu tiên thư mục cài đặt của app nếu có quyền ghi, chỉ fallback sang APPDATA khi bị chặn quyền ghi
    if getattr(sys, "frozen", False) or getattr(sys, "__compiled__", False) or ("__compiled__" in globals()):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))

    if os.path.exists(exe_dir) and os.access(exe_dir, os.W_OK):
        return exe_dir

    appdata = os.environ.get("APPDATA")
    if appdata:
        path = os.path.join(appdata, "EasyRemoteDesktop")
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except Exception:
            pass

    return exe_dir


def get_computers_xml_path():
    """Resolve saved_computers.xml (ưu tiên thư mục của app/installed copy, sau đó là user APPDATA)."""
    # Thu thập các đường dẫn file saved_computers.xml trong thư mục của app
    candidates = []
    if getattr(sys, "frozen", False) or getattr(sys, "__compiled__", False) or ("__compiled__" in globals()):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(exe_dir, "saved_computers.xml"))

    try:
        cwd_xml = os.path.join(os.getcwd(), "saved_computers.xml")
        if cwd_xml not in candidates:
            candidates.append(cwd_xml)
    except Exception:
        pass

    if sys.platform == "win32":
        candidates.append(r"C:\Program Files (x86)\Easy Remote Desktop\saved_computers.xml")
        candidates.append(r"C:\Program Files\Easy Remote Desktop\saved_computers.xml")
    else:
        candidates.append("/opt/p2p_remote/config/saved_computers.xml")

    # 1. Kiểm tra các thư mục của app trước: nếu có file, ưu tiên sử dụng
    for inst in candidates:
        if os.path.exists(inst):
            if os.access(inst, os.W_OK):
                return inst

    # Nếu chưa có file nhưng thư mục exe_dir có quyền ghi, tạo tại exe_dir
    if os.path.exists(exe_dir) and os.access(exe_dir, os.W_OK):
        return os.path.join(exe_dir, "saved_computers.xml")

    user_path = os.path.join(get_app_data_dir(), "saved_computers.xml")
    return user_path


class SavedListMixin:
    """Mixin: danh sách máy đã lưu (UI + XML + quét trạng thái)."""

    def _init_saved_list_state(self):
        self.status_dots_widgets = {}
        self._saved_computers_cache = None
        self._saved_computers_mtime = None
        self._saved_list_reorder_job = None
        self._status_query_worker_started = False
        self._status_scanned = set()
        self._status_online = {}
        self._status_offline_strikes = {}
        self._saved_id_groups = {}
        self._status_fg_focus_group = None
        self._status_fg_scan_ids = None
        self._status_fg_scan_idx = 0
        self._status_ui_q = queue.Queue()
        self._saved_list_open_flag = False
        self._saved_collapsed_snapshot = set()
        self._status_ui_pump_started = False
        self._status_wake = threading.Event()

    def import_saved_computers(self):
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            parent=self,
            title=_("Nhập khẩu danh sách máy tính"),
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")]
        )
        if filepath:
            try:
                import shutil
                dest = get_computers_xml_path()
                shutil.copy2(filepath, dest)
                msg = f"{_('Đã nhập khẩu danh sách máy tính thành công!')}\n\n{_('Tệp')}: {os.path.basename(filepath)}\n{_('Đường dẫn')}: {filepath}"
                InfoDialog(self, _("Thành công"), msg)
            except Exception as e:
                messagebox.showerror(_("Lỗi"), f"Không thể nhập khẩu: {e}")

    def export_saved_computers(self):
        from tkinter import filedialog
        filepath = filedialog.asksaveasfilename(
            parent=self,
            title=_("Xuất khẩu danh sách máy tính"),
            defaultextension=".xml",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
            initialfile="saved_computers.xml"
        )
        if filepath:
            try:
                import shutil
                src = get_computers_xml_path()
                if os.path.exists(src):
                    shutil.copy2(src, filepath)
                    msg = f"{_('Đã xuất khẩu danh sách máy tính thành công!')}\n\n{_('Tệp')}: {os.path.basename(filepath)}\n{_('Đường dẫn')}: {filepath}"
                    InfoDialog(self, _("Thành công"), msg)
                else:
                    messagebox.showwarning(_("Cảnh báo"), _("Không tìm thấy danh sách máy tính để xuất khẩu."))
            except Exception as e:
                messagebox.showerror(_("Lỗi"), f"Không thể xuất khẩu: {e}")


    def show_saved_computers_dialog(self):
        if not hasattr(self, 'collapsed_groups'):
            self.collapsed_groups = set()
        self.drag_card_id = None
        
        if hasattr(self, 'saved_computers_dialog') and self.saved_computers_dialog.winfo_exists():
            if self.saved_computers_dialog.state() == 'withdrawn':
                if hasattr(self.saved_computers_dialog, 'refresh_list_func'):
                    self.saved_computers_dialog.refresh_list_func()
                # Re-bind mousewheel khi mở lại dialog
                if hasattr(self.saved_computers_dialog, '_bind_mousewheel'):
                    self.saved_computers_dialog._bind_mousewheel()
                self.saved_computers_dialog.attributes("-alpha", 0.0)
                self.saved_computers_dialog.deiconify()
                def _show_reopen():
                    if self.saved_computers_dialog.winfo_exists():
                        self.saved_computers_dialog.attributes("-alpha", 1.0)
                        self.saved_computers_dialog.lift()
                        self.saved_computers_dialog.focus_force()
                    self._sync_saved_status_ui_flags()
                self.after(50, _show_reopen)
                self._sync_saved_status_ui_flags()
                self._wake_saved_status_workers()
                return
            self.saved_computers_dialog.lift()
            self.saved_computers_dialog.focus_force()
            self._sync_saved_status_ui_flags()
            self._wake_saved_status_workers()
            return
            
        dialog = tk.Toplevel(self)
        dialog.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy ở góc trên bên trái màn hình
        self.saved_computers_dialog = dialog
        dialog.title(_("Danh sách Máy tính"))
        dialog.resizable(False, False)
        dialog.configure(bg=self.bg_color)
        dialog.transient(self)

        # Center dialog
        dialog.update_idletasks()
        w = 480
        h = 400
        x = self.winfo_x() + (self.winfo_width() - w) // 2
        y = self.winfo_y() + (self.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        # Top title
        lbl_title = tk.Label(dialog, text=_("DANH SÁCH MÁY TÍNH ĐÃ LƯU"), font=(APP_FONT_NAME, 12, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_title.pack(pady=(15, 10))

        # Thanh Tìm kiếm
        search_frame = tk.Frame(dialog, bg=self.bg_color)
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        search_inner = tk.Frame(search_frame, bg="#2A2A3D", highlightthickness=1, highlightbackground=self.divider_color)
        search_inner.pack(fill=tk.X)
        
        lbl_search_icon = tk.Label(search_inner, text=E("🔍"), font=EMOJI_FONT, fg=self.text_gray, bg="#2A2A3D")
        lbl_search_icon.pack(side=tk.LEFT, padx=(8, 5), pady=4)
        
        search_var = tk.StringVar()
        entry_search = tk.Entry(search_inner, textvariable=search_var, font=(APP_FONT_NAME, 9), fg=self.text_white, bg="#2A2A3D", bd=0, insertbackground=self.text_white)
        entry_search.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4, padx=(0, 8))
        
        # Thiết lập Placeholder chuyên nghiệp
        entry_search.insert(0, _("Tìm kiếm theo tên hoặc ID..."))
        entry_search.configure(fg=self.text_gray)
        
        def on_focus_in(event):
            if entry_search.get() == _("Tìm kiếm theo tên hoặc ID..."):
                entry_search.delete(0, tk.END)
                entry_search.configure(fg=self.text_white)
                
        def on_focus_out(event):
            if entry_search.get() == "":
                entry_search.insert(0, _("Tìm kiếm theo tên hoặc ID..."))
                entry_search.configure(fg=self.text_gray)
                
        entry_search.bind("<FocusIn>", on_focus_in)
        entry_search.bind("<FocusOut>", on_focus_out)
        
        def on_search_change(*args):
            val = search_var.get()
            if val == _("Tìm kiếm theo tên hoặc ID..."):
                return
            job = getattr(dialog, "_search_job", None)
            if job:
                try:
                    dialog.after_cancel(job)
                except Exception:
                    pass
            dialog._search_job = dialog.after(180, refresh_list)
            
        search_var.trace_add("write", on_search_change)

        def load_computers():
            return self.load_saved_computers()

        def save_computers(lst):
            self.save_saved_computers(lst)

        # Container for the list (Sẽ pack ở cuối cùng sau khi đã pack bottom_frame để tránh bị đè/cắt nút)
        list_container = tk.Frame(dialog, bg=self.card_color)

        # Canvas & Scrollbar for scrollable area
        canvas = tk.Canvas(list_container, bg=self.card_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_container, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.card_color)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: None if getattr(dialog, "_building_list", False) else canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW)
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(canvas_frame, width=e.width)
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mouse wheel support
        def _on_mousewheel(event):
            try:
                if not dialog.winfo_exists() or not canvas.winfo_exists():
                    return
                # Chỉ scroll khi con trỏ chuột nằm trong dialog
                mx, my = dialog.winfo_pointerxy()
                dx = dialog.winfo_rootx()
                dy = dialog.winfo_rooty()
                dw = dialog.winfo_width()
                dh = dialog.winfo_height()
                if dx <= mx <= dx + dw and dy <= my <= dy + dh:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

        def _bind_mousewheel():
            """Gắn mousewheel binding."""
            try:
                if canvas.winfo_exists():
                    canvas.bind_all("<MouseWheel>", _on_mousewheel)
            except Exception:
                pass

        def _unbind_mousewheel():
            """Gỡ mousewheel binding khi dialog đóng."""
            try:
                canvas.unbind_all("<MouseWheel>")
            except Exception:
                pass

        # Gắn lên dialog object để có thể gọi lại khi reopen
        dialog._bind_mousewheel = _bind_mousewheel
        dialog._unbind_mousewheel = _unbind_mousewheel

        # Kích hoạt scroll ngay lập tức
        _bind_mousewheel()

        def on_dialog_destroy():
            _unbind_mousewheel()
            dialog.withdraw()
            self._status_fg_focus_group = None
            self._saved_list_open_flag = False
            try:
                dialog.update_idletasks()
            except Exception:
                pass
            self._sync_saved_status_ui_flags()
            self._wake_saved_status_workers()
            
        dialog.protocol("WM_DELETE_WINDOW", on_dialog_destroy)

        def connect_computer(item):
            now = time.time()
            if getattr(self, '_last_saved_connect_time', 0) > now - 0.8:
                return
            self._last_saved_connect_time = now
            print(f"[PCLIST] connect_computer: {item.get('name')} ({item.get('id')})")
            self.partner_id_var.set(item["id"])
            self.partner_pass_var.set(item["password"])
            # Giữ cửa sổ Danh sách Máy tính tiếp tục hiển thị theo yêu cầu người dùng
            # Trigger connection immediately
            self.click_connect()

        def delete_computer(item):
            if self.show_custom_question(_("Xóa máy tính"), _("Bạn có chắc muốn xóa") + f" '{item['name']}' " + _("khỏi danh sách?"), parent=dialog):
                computers = load_computers()
                computers = [c for c in computers if not (c["id"] == item["id"] and c["name"] == item["name"])]
                save_computers(computers)
                refresh_list()

        self.auto_scroll_job = None

        def check_auto_scroll():
            drag_id = getattr(self, 'drag_card_id', None)
            if not drag_id:
                self.auto_scroll_job = None
                return

            try:
                x, y = canvas.winfo_pointerxy()
                cy = canvas.winfo_rooty()
                ch = canvas.winfo_height()
                rel_y = y - cy
                
                if rel_y < 40:
                    canvas.yview_scroll(-1, "units")
                elif rel_y > ch - 40:
                    canvas.yview_scroll(1, "units")
                    
                self.auto_scroll_job = dialog.after(50, check_auto_scroll)
            except Exception:
                self.auto_scroll_job = None

        def on_drag_motion(event):
            drag_id = getattr(self, 'drag_card_id', None)
            if not drag_id:
                return

            # Check threshold (6px) to distinguish single click/mouse jitter from actual dragging
            start_x = getattr(self, '_drag_start_x', event.x_root)
            start_y = getattr(self, '_drag_start_y', event.y_root)
            if not getattr(self, '_is_dragging', False):
                if abs(event.x_root - start_x) < 6 and abs(event.y_root - start_y) < 6:
                    return
                self._is_dragging = True

            if not getattr(self, 'auto_scroll_job', None):
                check_auto_scroll()
            
            try:
                x, y = event.x_root, event.y_root
                target_widget = dialog.winfo_containing(x, y)
                target_group = None
                if target_widget:
                    w = target_widget
                    while w:
                        if getattr(w, 'is_group_header', False):
                            target_group = w.group_name
                            break
                        if hasattr(w, 'comp_group'):
                            target_group = w.comp_group
                            break
                        if str(w) == str(dialog):
                            break
                        parent_str = w.winfo_parent()
                        if not parent_str: break
                        w = w._nametowidget(parent_str)
                
                if scrollable_frame.winfo_exists():
                    for c in scrollable_frame.winfo_children():
                        if getattr(c, 'is_group_header', False):
                            if target_group is not None and c.group_name == target_group:
                                c["fg"] = self.btn_color
                            else:
                                c["fg"] = self.text_gray
            except Exception:
                pass

        def on_drop(event):
            if getattr(self, 'auto_scroll_job', None):
                try:
                    dialog.after_cancel(self.auto_scroll_job)
                except Exception:
                    pass
                self.auto_scroll_job = None
                
            try:
                if scrollable_frame.winfo_exists():
                    for c in scrollable_frame.winfo_children():
                        if getattr(c, 'is_group_header', False):
                            c["fg"] = self.text_gray
            except Exception:
                pass
                
            was_dragging = getattr(self, '_is_dragging', False)
            self._is_dragging = False
            drag_id = getattr(self, 'drag_card_id', None)
            comp_data = getattr(self, 'drag_comp_data', None)
            self.drag_card_id = None
            self.drag_comp_data = None
            self._drag_start_x = None
            self._drag_start_y = None
            if not drag_id: return
            
            # If user clicked without dragging, immediately connect to the computer!
            if not was_dragging:
                if comp_data:
                    connect_computer(comp_data)
                return
            
            x, y = event.x_root, event.y_root
            target_widget = dialog.winfo_containing(x, y)
            if not target_widget: return
            
            target_group = None
            w = target_widget
            while w:
                if getattr(w, 'is_group_header', False):
                    target_group = w.group_name
                    break
                if hasattr(w, 'comp_group'):
                    target_group = w.comp_group
                    break
                if str(w) == str(dialog):
                    break
                parent_str = w.winfo_parent()
                if not parent_str: break
                w = w._nametowidget(parent_str)
                
            if target_group is not None:
                comps = load_computers()
                updated = False
                for c in comps:
                    if c["id"].replace(" ", "") == drag_id:
                        if c.get("group", "").strip() != target_group:
                            c["group"] = target_group
                            updated = True
                        break
                if updated:
                    save_computers(comps)
                    refresh_list()

        def rename_group_dialog(old_group_name):
            rn_win = tk.Toplevel(dialog)
            rn_win.withdraw()
            rn_win.title(_("Đổi tên nhóm"))
            rn_win.resizable(False, False)
            rn_win.configure(bg=self.bg_color)
            rn_win.transient(dialog)
            rn_win.grab_set()

            rn_win.update_idletasks()
            rw, rh = 300, 160
            rx = dialog.winfo_x() + (dialog.winfo_width() - rw) // 2
            ry = dialog.winfo_y() + (dialog.winfo_height() - rh) // 2
            rn_win.geometry(f"{rw}x{rh}+{rx}+{ry}")
            rn_win.deiconify()

            display_group = old_group_name if old_group_name else _("Chưa phân nhóm")
            lbl = tk.Label(rn_win, text=_("Nhập tên mới cho nhóm:") + f"\n({display_group})", font=(APP_FONT_NAME, 9), fg=self.text_white, bg=self.bg_color)
            lbl.pack(pady=(15, 10))

            entry_var = tk.StringVar(value=old_group_name)
            entry = tk.Entry(rn_win, textvariable=entry_var, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
            entry.pack(fill=tk.X, padx=20, pady=(0, 15))
            entry.focus()
            entry.select_range(0, tk.END)

            def do_rename():
                new_name = entry_var.get().strip()
                if new_name != old_group_name:
                    comps = load_computers()
                    for c in comps:
                        if c.get("group", "").strip() == old_group_name:
                            c["group"] = new_name
                    save_computers(comps)
                    if old_group_name in getattr(self, 'collapsed_groups', set()):
                        self.collapsed_groups.remove(old_group_name)
                        self.collapsed_groups.add(new_name)
                    refresh_list()
                rn_win.destroy()

            btn_frame = tk.Frame(rn_win, bg=self.bg_color)
            btn_frame.pack(fill=tk.X, padx=20)
            
            btn_save = tk.Button(btn_frame, text=_("Lưu"), font=(APP_FONT_NAME, 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=do_rename)
            btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
            
            btn_cancel = tk.Button(btn_frame, text=_("Hủy"), font=(APP_FONT_NAME, 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35", relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=rn_win.destroy)
            btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

        def reorder_list():
            if not scrollable_frame.winfo_exists(): return
            children = scrollable_frame.winfo_children()
            headers = [c for c in children if getattr(c, 'is_group_header', False)]
            cards = [c for c in children if hasattr(c, 'comp_id')]
            if not cards and not headers: return
            
            def get_is_online(c):
                known = getattr(self, "_status_online", {}) or {}
                cid = self._canonical_saved_id(getattr(c, "comp_id", ""))
                if cid and cid in known:
                    return bool(known[cid])
                if c.comp_id in known:
                    return bool(known[c.comp_id])
                if c.comp_id in self.status_dots_widgets:
                    widgets = self.status_dots_widgets[c.comp_id]
                    if widgets and widgets[0].winfo_exists():
                        return widgets[0].cget("fg") == "#00F5D4"
                return False

            dialog._building_list = True
            try:
                for c in children:
                    c.pack_forget()

                grouped_cards = {}
                for c in cards:
                    grp = getattr(c, 'comp_group', '')
                    if grp not in grouped_cards:
                        grouped_cards[grp] = []
                    grouped_cards[grp].append(c)

                def group_sort_key(g):
                    return (1, g) if not g else (0, g.lower())
                
                sorted_groups = sorted(grouped_cards.keys(), key=group_sort_key)
                header_map = {h.group_name: h for h in headers}

                for grp in sorted_groups:
                    if grp in header_map:
                        header_map[grp].pack(fill=tk.X, pady=(15, 5), padx=15)
                    
                    if grp not in self.collapsed_groups:
                        grp_cards = grouped_cards.get(grp, [])
                        grp_cards.sort(key=lambda c: (not get_is_online(c), c.comp_name.lower()))
                        for c in grp_cards:
                            c.pack(fill=tk.X, pady=0, padx=(0, 10))
            finally:
                dialog._building_list = False
                try:
                    canvas.configure(scrollregion=canvas.bbox("all"))
                except Exception:
                    pass

        def schedule_reorder():
            job = getattr(self, "_saved_list_reorder_job", None)
            if job:
                try:
                    dialog.after_cancel(job)
                except Exception:
                    pass
            self._saved_list_reorder_job = dialog.after(200, reorder_list)

        self._reorder_saved_computers_func = schedule_reorder

        def refresh_list(force=False):
            def _refresh_task():
                try:
                    _refresh_list_inner(force)
                except Exception:
                    pass
            dialog.after(1, _refresh_task)
            
        def _refresh_list_inner(force=False):
            query = search_var.get().strip().lower()
            if query == _("Tìm kiếm theo tên hoặc ID...").lower() or query == _("tìm kiếm theo tên hoặc id...").lower():
                query = ""

            computers = load_computers()
            
            # Filter
            if query:
                computers = [c for c in computers if query in c["name"].lower() or query in c["id"].replace(" ", "")]

            if force:
                self._status_scanned = set()
                self._status_online = {}
                self._status_offline_strikes = {}

            current_hash = json.dumps(computers, sort_keys=True)
            if not force and getattr(dialog, '_last_rendered_hash', None) == current_hash:
                reorder_list()
                return
            dialog._last_rendered_hash = current_hash

            current_online = {}
            for cid, widgets in self.status_dots_widgets.items():
                if widgets and widgets[0].winfo_exists():
                    try:
                        fg = widgets[0].cget("fg")
                    except Exception:
                        continue
                    if fg != "#8A8A9A":
                        current_online[cid] = (fg == "#00F5D4")

            dialog._building_list = True
            try:
                for widget in scrollable_frame.winfo_children():
                    widget.destroy()
                self.status_dots_widgets.clear()
                self._saved_id_groups = {}

                if not computers:
                    txt = _("Không tìm thấy máy tính phù hợp.") if query else _("Chưa có máy tính nào được lưu.\nBấm nút thêm bên dưới để tạo mới.")
                    lbl_empty = tk.Label(scrollable_frame, text=txt, font=(APP_FONT_NAME, 9, "italic"), fg=self.text_gray, bg=self.card_color, justify=tk.CENTER)
                    lbl_empty.pack(pady=40, fill=tk.X, expand=True)
                    return

                unique_groups = set()
                for c in computers:
                    unique_groups.add(c.get("group", "").strip())
                
                for grp in unique_groups:
                    grp_display = grp if grp else _("Chưa phân nhóm")
                    icon = "▶" if grp in self.collapsed_groups else "▼"
                    header_text = f"{icon} {grp_display.upper()}"
                    
                    header = tk.Label(scrollable_frame, text=header_text, font=(APP_FONT_NAME, 9, "bold"), fg=self.text_gray, bg=self.card_color, anchor=tk.W, cursor="hand2")
                    header.is_group_header = True
                    header.group_name = grp
                    
                    def toggle_group(event, g=grp):
                        if g in self.collapsed_groups:
                            self.collapsed_groups.remove(g)
                            just_expanded = True
                        else:
                            self.collapsed_groups.add(g)
                            just_expanded = False
                        new_icon = "▶" if g in self.collapsed_groups else "▼"
                        g_display = g if g else _("Chưa phân nhóm")
                        event.widget.config(text=f"{new_icon} {g_display.upper()}")
                        reorder_list()
                        self.save_group_states_only()
                        self._sync_saved_status_ui_flags()
                        if just_expanded:
                            # Chỉ đánh dấu nhóm + wake worker — burst trên UI thread
                            # sẽ chặn Tk (send nhiều check_online) và dễ làm UI đứng.
                            self._status_fg_focus_group = g
                            self._status_fg_scan_ids = None
                            self._status_fg_scan_idx = 0
                            self._wake_saved_status_workers()
                        
                    header.bind("<Button-1>", toggle_group)
                    header.bind("<ButtonRelease-1>", on_drop)

                    grp_context_menu = tk.Menu(header, tearoff=0, bg=self.entry_bg, fg=self.text_white, bd=0, activebackground=self.btn_hover)
                    grp_context_menu.add_command(label=_("Đổi tên nhóm"), command=lambda g=grp: rename_group_dialog(g))

                    def show_grp_context(event, menu=grp_context_menu):
                        menu.tk_popup(event.x_root, event.y_root)

                    header.bind("<ButtonRelease-3>", show_grp_context)

                for comp in computers:
                    card = tk.Frame(scrollable_frame, bg=self.card_color)
                    card.comp_id = comp["id"].replace(" ", "")
                    card.comp_name = comp["name"]
                    card.comp_group = comp.get("group", "").strip()

                    content_frame = tk.Frame(card, bg=self.card_color, pady=5, padx=12)
                    content_frame.pack(fill=tk.X)
                    
                    separator = tk.Frame(card, bg=self.divider_color, height=2)
                    separator.pack(fill=tk.X, padx=10)

                    info_frame = tk.Frame(content_frame, bg=self.card_color)
                    info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

                    clean_id = card.comp_id
                    canon_id = self._canonical_saved_id(clean_id)
                    known = getattr(self, "_status_online", {})
                    if clean_id in current_online:
                        is_online = current_online[clean_id]
                        self._status_scanned.add(clean_id)
                        dot_color = "#00F5D4" if is_online else "#E05252"
                    elif canon_id in current_online:
                        is_online = current_online[canon_id]
                        self._status_scanned.add(canon_id)
                        dot_color = "#00F5D4" if is_online else "#E05252"
                    elif canon_id in known:
                        is_online = bool(known[canon_id])
                        self._status_scanned.add(canon_id)
                        dot_color = "#00F5D4" if is_online else "#E05252"
                    elif clean_id in known:
                        is_online = bool(known[clean_id])
                        self._status_scanned.add(clean_id)
                        dot_color = "#00F5D4" if is_online else "#E05252"
                    else:
                        is_online = False
                        dot_color = "#8A8A9A"
                    dot_lbl = tk.Label(info_frame, text="●", font=(APP_FONT_NAME, 13, "bold"), fg=dot_color, bg=self.card_color)
                    dot_lbl.pack(side=tk.LEFT, padx=(0, 5))

                    raw_cid = str(comp.get('id', '')).strip()
                    c_digits = "".join(c for c in raw_cid if c.isdigit())
                    disp_cid = " ".join(c_digits[i:i+3] for i in range(0, len(c_digits), 3)) if (c_digits and len(c_digits) == len(raw_cid.replace(" ", ""))) else raw_cid
                    id_lbl = tk.Label(info_frame, text=f"ID: {disp_cid}", font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.card_color, anchor=tk.E)
                    id_lbl.pack(side=tk.RIGHT, padx=(0, 10))

                    name_lbl = tk.Label(info_frame, text=comp["name"], font=(APP_FONT_NAME, 10, "bold"), fg=self.text_white, bg=self.card_color, anchor=tk.W)
                    name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

                    context_menu = tk.Menu(card, tearoff=0, bg=self.entry_bg, fg=self.text_white, bd=0, activebackground=self.btn_hover)
                    context_menu.add_command(label=_("Kết nối"), command=lambda c=comp: connect_computer(c))
                    context_menu.add_separator()
                    context_menu.add_command(label=_("Thay đổi thông tin"), command=lambda c=comp: self.open_edit_computer_dialog(c, dialog, refresh_list))
                    context_menu.add_command(label=_("Xóa máy tính"), command=lambda c=comp: delete_computer(c))

                    def show_context_menu(event, menu=context_menu):
                        menu.tk_popup(event.x_root, event.y_root)
                            
                    def start_drag(event, c_id=clean_id, c_data=comp):
                        self.drag_card_id = c_id
                        self.drag_comp_data = c_data
                        self._drag_start_x = event.x_root
                        self._drag_start_y = event.y_root
                        self._is_dragging = False

                    for w in [card, content_frame, separator, info_frame, dot_lbl, name_lbl, id_lbl]:
                        w.bind("<Double-Button-1>", lambda e, c=comp: connect_computer(c))
                        w.bind("<ButtonRelease-3>", show_context_menu)
                        w.bind("<ButtonPress-1>", lambda e, c_id=clean_id, c_data=comp: start_drag(e, c_id, c_data))
                        w.bind("<B1-Motion>", on_drag_motion)
                        w.bind("<ButtonRelease-1>", on_drop)
                        try:
                            w.config(cursor="hand2")
                        except Exception:
                            pass

                    if clean_id not in self.status_dots_widgets:
                        self.status_dots_widgets[clean_id] = []
                    self.status_dots_widgets[clean_id].append(dot_lbl)
                    dot_lbl._row_root = card
                    if dot_color == "#E05252":
                        try:
                            from gui.components import apply_row_online_state
                            apply_row_online_state(card, False, self.card_color, (self.text_white, self.text_gray))
                        except Exception:
                            pass
                    self._saved_id_groups[clean_id] = card.comp_group
            finally:
                dialog._building_list = False
                
            reorder_list()

        # Bottom buttons panel
        bottom_frame = tk.Frame(dialog, bg=self.bg_color)
        bottom_frame.pack(fill=tk.X, padx=20, pady=(10, 15))

        def open_add_dialog():
            self.open_add_computer_dialog_with_vals("", "", parent_win=dialog, on_save=refresh_list)

        def start_refresh_cooldown():
            seconds_left = 30
            
            def update_timer():
                nonlocal seconds_left
                if seconds_left > 0:
                    btn_refresh.config(text=E(_("🔄 Làm mới")) + f" ({seconds_left}s)")
                    seconds_left -= 1
                    if dialog.winfo_exists():
                        dialog.after(1000, update_timer)
                else:
                    if dialog.winfo_exists():
                        btn_refresh.config(
                            state="normal", text=E(_("🔄 Làm mới")),
                            fg=self.text_white, bg="#2ECC71",
                            cursor="hand2"
                        )
                        
            btn_refresh.config(state="disabled", text=E(_("🔄 Làm mới (30s)")), bg="#2A2A35", fg="#8A8A9A", cursor="arrow")
            update_timer()

        btn_add = tk.Button(
            bottom_frame, text=_("+ Thêm Mới"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2", command=open_add_dialog
        )
        btn_add.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

        btn_refresh = tk.Button(
            bottom_frame, text=E(_("🔄 Làm mới")), font=EMOJI_FONT_BOLD,
            fg=self.text_white, bg="#2ECC71", activebackground="#27AE60",
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2",
            command=lambda: [refresh_list(force=True), start_refresh_cooldown()]
        )
        btn_refresh.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)

        btn_close = tk.Button(
            bottom_frame, text=_("Đóng"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, pady=6, cursor="hand2", command=on_dialog_destroy
        )
        btn_close.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))

        # Pack list_container sau cùng để lấp đầy phần diện tích còn lại ở giữa Search Bar và Bottom Buttons!
        list_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        dialog.refresh_list_func = refresh_list
        refresh_list()

        # Hiển thị mượt mà bằng cách ẩn độ mờ trước, đợi Tk vẽ xong rồi mới hiện lên
        dialog.attributes("-alpha", 0.0)
        dialog.deiconify()
        def _show_initial():
            if dialog.winfo_exists():
                dialog.attributes("-alpha", 1.0)
                dialog.lift()
                dialog.focus_force()
            self._sync_saved_status_ui_flags()
        dialog.after(50, _show_initial)
        self._sync_saved_status_ui_flags()
        self._wake_saved_status_workers()


    def add_current_partner_to_saved(self):
        curr_id = self.partner_id_var.get().strip()
        curr_pass = self.partner_pass_var.get().strip()
        self.open_add_computer_dialog_with_vals(curr_id, curr_pass)


    def open_add_computer_dialog_with_vals(self, initial_id="", initial_pass="", parent_win=None, on_save=None):
        parent = parent_win if parent_win else self
        
        add_win = tk.Toplevel(parent)
        add_win.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy
        add_win.title(_("Thêm Máy tính"))
        add_win.resizable(False, False)
        add_win.configure(bg=self.bg_color)
        add_win.transient(parent)
        add_win.grab_set()

        # Center add window
        add_win.update_idletasks()
        aw = 320
        ah = 360
        ax = parent.winfo_x() + (parent.winfo_width() - aw) // 2
        ay = parent.winfo_y() + (parent.winfo_height() - ah) // 2
        add_win.geometry(f"{aw}x{ah}+{ax}+{ay}")
        add_win.deiconify()  # Chỉ hiển thị sau khi đã tính toán căn giữa hoàn hảo!

        lbl_add_title = tk.Label(add_win, text=_("THÊM MÁY TÍNH MỚI"), font=(APP_FONT_NAME, 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_add_title.pack(pady=(12, 10))

        lbl_name = tk.Label(add_win, text=_("Tên gọi gợi nhớ:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_name.pack(anchor=tk.W, padx=20)
        entry_name = tk.Entry(add_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_name.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_name.focus()

        lbl_comp_id = tk.Label(add_win, text=_("ID đối tác:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_id.pack(anchor=tk.W, padx=20)
        entry_comp_id = tk.Entry(add_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_id.pack(fill=tk.X, padx=20, pady=(3, 8))
        if initial_id:
            entry_comp_id.insert(0, initial_id)

        lbl_comp_pass = tk.Label(add_win, text=_("Mật khẩu:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_pass.pack(anchor=tk.W, padx=20)
        entry_comp_pass = tk.Entry(add_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_pass.pack(fill=tk.X, padx=20, pady=(3, 8))
        if initial_pass:
            entry_comp_pass.insert(0, initial_pass)

        lbl_group = tk.Label(add_win, text=_("Nhóm (Tùy chọn):"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_group.pack(anchor=tk.W, padx=20)
        entry_group = tk.Entry(add_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_group.pack(fill=tk.X, padx=20, pady=(3, 12))

        def load_computers():
            return self.load_saved_computers()

        def save_computers(lst):
            self.save_saved_computers(lst)

        def save_new():
            name = entry_name.get().strip()
            cid = entry_comp_id.get().strip()
            cpass = entry_comp_pass.get().strip()
            cgroup = entry_group.get().strip()

            if not name or not cid or not cpass:
                self.show_custom_error(_("Lỗi nhập liệu"), _("Vui lòng điền đầy đủ các thông tin!"), parent=add_win)
                return

            computers = load_computers()
            for c in computers:
                if c["id"] == cid and c["name"] == name:
                    self.show_custom_error(_("Trùng lặp"), _("Máy tính này đã tồn tại trong danh sách!"), parent=add_win)
                    return

            computers.append({
                "name": name,
                "id": cid,
                "password": cpass,
                "group": cgroup
            })
            save_computers(computers)
            if on_save:
                on_save()
            if not parent_win:
                self.show_custom_info(_("Thành công"), _("Đã lưu máy tính '{name}' vào danh sách thành công!").replace("{name}", name), parent=add_win)
            add_win.destroy()

        btn_add_frame = tk.Frame(add_win, bg=self.bg_color)
        btn_add_frame.pack(fill=tk.X, padx=20, pady=5)

        btn_save = tk.Button(
            btn_add_frame, text=_("Lưu lại"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=save_new
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_add_frame, text=_("Hủy bỏ"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=add_win.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))


    def open_edit_computer_dialog(self, item, parent_win, on_save):
        parent = parent_win
        
        edit_win = tk.Toplevel(parent)
        edit_win.withdraw()  # Ẩn ngay khi khởi tạo để tránh bị nháy
        edit_win.title(_("Sửa thông tin"))
        edit_win.resizable(False, False)
        edit_win.configure(bg=self.bg_color)
        edit_win.transient(parent)
        edit_win.grab_set()

        # Center edit window
        edit_win.update_idletasks()
        ew = 320
        eh = 360
        ex = parent.winfo_x() + (parent.winfo_width() - ew) // 2
        ey = parent.winfo_y() + (parent.winfo_height() - eh) // 2
        edit_win.geometry(f"{ew}x{eh}+{ex}+{ey}")
        edit_win.deiconify()  # Chỉ hiển thị sau khi đã tính toán căn giữa hoàn hảo!

        lbl_edit_title = tk.Label(edit_win, text=_("CẬP NHẬT THÔNG TIN"), font=(APP_FONT_NAME, 10, "bold"), fg=self.btn_color, bg=self.bg_color)
        lbl_edit_title.pack(pady=(12, 10))

        lbl_name = tk.Label(edit_win, text=_("Tên gọi gợi nhớ:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_name.pack(anchor=tk.W, padx=20)
        entry_name = tk.Entry(edit_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_name.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_name.insert(0, item["name"])
        entry_name.focus()

        lbl_comp_id = tk.Label(edit_win, text=_("ID đối tác:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_id.pack(anchor=tk.W, padx=20)
        entry_comp_id = tk.Entry(edit_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_id.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_comp_id.insert(0, item["id"])

        lbl_comp_pass = tk.Label(edit_win, text=_("Mật khẩu mới:"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_comp_pass.pack(anchor=tk.W, padx=20)
        entry_comp_pass = tk.Entry(edit_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_comp_pass.pack(fill=tk.X, padx=20, pady=(3, 8))
        entry_comp_pass.insert(0, item["password"])

        lbl_group = tk.Label(edit_win, text=_("Nhóm (Tùy chọn):"), font=(APP_FONT_NAME, 9), fg=self.text_gray, bg=self.bg_color)
        lbl_group.pack(anchor=tk.W, padx=20)
        entry_group = tk.Entry(edit_win, font=(APP_FONT_NAME, 10), fg=self.entry_fg, bg=self.entry_bg, relief=tk.FLAT, bd=3, insertbackground=self.text_white)
        entry_group.pack(fill=tk.X, padx=20, pady=(3, 12))
        entry_group.insert(0, item.get("group", ""))

        def load_computers():
            return self.load_saved_computers()

        def save_computers(lst):
            self.save_saved_computers(lst)

        def save_edit():
            name = entry_name.get().strip()
            new_id = entry_comp_id.get().strip()
            cpass = entry_comp_pass.get().strip()
            cgroup = entry_group.get().strip()

            if not name or not new_id or not cpass:
                self.show_custom_error(_("Lỗi nhập liệu"), _("Vui lòng điền đầy đủ các thông tin!"), parent=edit_win)
                return

            computers = load_computers()
            updated = False
            for c in computers:
                if c["id"] == item["id"] and c["name"] == item["name"]:
                    c["name"] = name
                    c["id"] = new_id
                    c["password"] = cpass
                    c["group"] = cgroup
                    updated = True
                    break
            
            if updated:
                save_computers(computers)
                if on_save:
                    on_save()
                edit_win.destroy()
            else:
                self.show_custom_error(_("Lỗi"), _("Không tìm thấy máy tính tương ứng để sửa!"), parent=edit_win)

        btn_edit_frame = tk.Frame(edit_win, bg=self.bg_color)
        btn_edit_frame.pack(fill=tk.X, padx=20, pady=5)

        btn_save = tk.Button(
            btn_edit_frame, text=_("Lưu lại"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover,
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=save_edit
        )
        btn_save.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_cancel = tk.Button(
            btn_edit_frame, text=_("Hủy bỏ"), font=(APP_FONT_NAME, 9, "bold"),
            fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, activebackground="#2A2A35",
            relief=tk.FLAT, bd=0, padx=15, pady=5, cursor="hand2", command=edit_win.destroy
        )
        btn_cancel.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))


    def load_saved_computers(self):
        computers_file = get_computers_xml_path()
        try:
            mtime = os.path.getmtime(computers_file) if os.path.exists(computers_file) else None
        except Exception:
            mtime = None
        if (
            getattr(self, "_saved_computers_cache", None) is not None
            and mtime is not None
            and mtime == getattr(self, "_saved_computers_mtime", None)
        ):
            return [dict(c) for c in self._saved_computers_cache]

        import xml.etree.ElementTree as ET
        lst = []
        if os.path.exists(computers_file):
            try:
                tree = ET.parse(computers_file)
                root = tree.getroot()
                for comp_node in root.findall("computer"):
                    name_node = comp_node.find("name")
                    id_node = comp_node.find("id")
                    pass_node = comp_node.find("password")
                    group_node = comp_node.find("group")
                    
                    name = decrypt_text(name_node.text) if name_node is not None else ""
                    cid = decrypt_text(id_node.text) if id_node is not None else ""
                    cpass = decrypt_text(pass_node.text) if pass_node is not None else ""
                    cgroup = decrypt_text(group_node.text) if group_node is not None else ""
                    
                    if cid:
                        lst.append({
                            "name": name,
                            "id": cid,
                            "password": cpass,
                            "group": cgroup
                        })
                        
                if not hasattr(self, 'collapsed_groups_loaded'):
                    self.collapsed_groups = set()
                    self.collapsed_groups_loaded = True
                    gs_node = root.find("group_states")
                    if gs_node is not None:
                        for g_node in gs_node.findall("collapsed_group"):
                            self.collapsed_groups.add(decrypt_text(g_node.text) if g_node.text else "")
                    self._saved_collapsed_snapshot = set(self.collapsed_groups)
            except Exception as e:
                print(f"[Config] Lỗi tải XML: {e}")
        self._saved_computers_cache = lst
        self._saved_computers_mtime = mtime
        return [dict(c) for c in lst]


    def save_saved_computers(self, lst):
        computers_file = get_computers_xml_path()
        import xml.etree.ElementTree as ET
        try:
            fixed_node = None
            zalo_node = None
            old_gs_node = None
            if os.path.exists(computers_file):
                try:
                    tree = ET.parse(computers_file)
                    root = tree.getroot()
                    fixed_node = root.find("fixed_password")
                    zalo_node = root.find("zalo_phone")
                    old_gs_node = root.find("group_states")
                except:
                    pass

            root = ET.Element("computers")

            if fixed_node is not None:
                root.append(fixed_node)
            if zalo_node is not None:
                root.append(zalo_node)

            if hasattr(self, 'collapsed_groups'):
                gs_node = ET.SubElement(root, "group_states")
                for grp in self.collapsed_groups:
                    g_node = ET.SubElement(gs_node, "collapsed_group")
                    g_node.text = encrypt_text(grp)
            elif old_gs_node is not None:
                root.append(old_gs_node)
                

            for comp in lst:
                comp_node = ET.SubElement(root, "computer")
                name_node = ET.SubElement(comp_node, "name")
                name_node.text = encrypt_text(comp["name"])
                
                id_node = ET.SubElement(comp_node, "id")
                id_node.text = encrypt_text(comp["id"])
                
                pass_node = ET.SubElement(comp_node, "password")
                pass_node.text = encrypt_text(comp["password"])
                
                group_node = ET.SubElement(comp_node, "group")
                group_node.text = encrypt_text(comp.get("group", ""))
                
            if hasattr(ET, "indent"):
                ET.indent(root, space="  ")
                
            tree = ET.ElementTree(root)
            tree.write(computers_file, encoding="utf-8", xml_declaration=True)
            self._saved_computers_cache = [dict(c) for c in lst]
            try:
                self._saved_computers_mtime = os.path.getmtime(computers_file)
            except Exception:
                self._saved_computers_mtime = None

            try:
                installed_p = r"C:\Program Files (x86)\Easy Remote Desktop\saved_computers.xml"
                if os.path.abspath(computers_file) != os.path.abspath(installed_p):
                    if os.path.exists(os.path.dirname(installed_p)) and os.access(os.path.dirname(installed_p), os.W_OK):
                        shutil.copy2(computers_file, installed_p)
            except Exception:
                pass

            try:
                self._ensure_status_query_worker()
            except Exception:
                pass
        except Exception as e:
            print(f"[Config] Lỗi lưu XML: {e}")
            if hasattr(self, 'show_custom_error'):
                self.after(0, lambda err=str(e): self.show_custom_error(_("Lỗi lưu file"), _("Không thể lưu danh sách máy tính. Vui lòng kiểm tra quyền ghi tệp (Administrator/Root)!\nChi tiết: {err}").format(err=err)))


    def save_group_states_only(self):
        computers_file = get_computers_xml_path()
        if not os.path.exists(computers_file):
            return
        import xml.etree.ElementTree as ET
        try:
            tree = ET.parse(computers_file)
            root = tree.getroot()
            old_gs = root.find("group_states")
            if old_gs is not None:
                root.remove(old_gs)
            if hasattr(self, 'collapsed_groups'):
                gs_node = ET.SubElement(root, "group_states")
                for grp in self.collapsed_groups:
                    g_node = ET.SubElement(gs_node, "collapsed_group")
                    g_node.text = encrypt_text(grp)
            if hasattr(ET, "indent"):
                ET.indent(root, space="  ")
            tree.write(computers_file, encoding="utf-8", xml_declaration=True)
            try:
                self._saved_computers_mtime = os.path.getmtime(computers_file)
            except Exception:
                pass
        except Exception:
            pass

    def _saved_list_is_open(self):
        # Worker không gọi Tk — dùng cờ main thread cập nhật.
        try:
            if threading.current_thread() is not threading.main_thread():
                return bool(getattr(self, "_saved_list_open_flag", False))
        except Exception:
            return bool(getattr(self, "_saved_list_open_flag", False))
        return self._read_saved_list_open_tk()

    def _read_saved_list_open_tk(self):
        dlg = getattr(self, "saved_computers_dialog", None)
        try:
            return bool(dlg and dlg.winfo_exists() and dlg.state() != "withdrawn")
        except Exception:
            return False

    def _saved_collapsed_set(self):
        try:
            if threading.current_thread() is not threading.main_thread():
                snap = getattr(self, "_saved_collapsed_snapshot", None)
                if snap is not None:
                    return set(snap)
        except Exception:
            pass
        return set(getattr(self, "collapsed_groups", set()) or [])

    def _sync_saved_status_ui_flags(self):
        """Main thread: snapshot list mở/đóng và nhóm thu gọn cho worker."""
        self._saved_list_open_flag = self._read_saved_list_open_tk()
        self._saved_collapsed_snapshot = set(getattr(self, "collapsed_groups", set()) or [])

    def _wake_saved_status_workers(self):
        ev = getattr(self, "_status_wake", None)
        if ev is not None:
            ev.set()

    def _drain_status_ui_q(self):
        q = getattr(self, "_status_ui_q", None)
        if q is None:
            return
        n = 0
        while n < 80:
            try:
                cid, online = q.get_nowait()
            except Exception:
                break
            n += 1
            try:
                self._apply_saved_computer_status(cid, online)
            except Exception:
                pass

    def _pump_saved_status_ui(self):
        self._sync_saved_status_ui_flags()
        self._drain_status_ui_q()
        try:
            self._expire_stale_online_probes()
        except Exception:
            pass
        try:
            self._ensure_open_groups_loop_alive()
        except Exception:
            pass
        try:
            self.after(80, self._pump_saved_status_ui)
        except Exception:
            pass

    def _saved_id_is_expanded(self, clean_id):
        if not self._saved_list_is_open():
            return False
        groups = getattr(self, "_saved_id_groups", {}) or {}
        grp = groups.get(clean_id, "")
        if not grp:
            grp = groups.get(self._canonical_saved_id(clean_id), "")
        return grp not in self._saved_collapsed_set()

    @staticmethod
    def _saved_group_sort_key(grp):
        return (1, grp) if not grp else (0, str(grp).lower())

    def _iter_saved_computer_ids(self):
        for cid, grp, _name in self._list_saved_computers_meta():
            yield cid, grp

    def _list_saved_computers_meta(self):
        """[(clean_id, group, name), ...] — luôn đọc XML/cache, kể cả khi list đang đóng."""
        out = []
        try:
            computers = self.load_saved_computers()
        except Exception:
            return out
        groups = getattr(self, "_saved_id_groups", None)
        if groups is None:
            self._saved_id_groups = {}
            groups = self._saved_id_groups
        for comp in computers:
            cid = str(comp.get("id") or "").replace(" ", "")
            if not cid:
                continue
            grp = (comp.get("group") or "").strip()
            name = str(comp.get("name") or "")
            groups[cid] = grp
            out.append((cid, grp, name))
        return out

    def _saved_status_partitions(self):
        """Tách máy theo trạng thái list: expanded (thứ tự nhóm trên→dưới), collapsed, all."""
        rows = self._list_saved_computers_meta()
        all_ids = [cid for cid, _g, _n in rows]
        if not self._saved_list_is_open():
            return [], [], all_ids
        collapsed = self._saved_collapsed_set()
        by_grp = {}
        for cid, grp, name in rows:
            by_grp.setdefault(grp, []).append((cid, name))
        expanded = []
        collapsed_ids = []
        focus = getattr(self, "_status_fg_focus_group", None)
        if not focus:
            focus = getattr(self, "_status_last_active_group", None)
        grp_order = sorted(by_grp.keys(), key=self._saved_group_sort_key)
        if focus in by_grp and focus not in collapsed:
            grp_order = [focus] + [g for g in grp_order if g != focus]
        for grp in grp_order:
            items = by_grp[grp]
            items.sort(key=lambda it: it[1].lower())
            ids = [cid for cid, _n in items]
            if grp in collapsed:
                collapsed_ids.extend(ids)
            else:
                expanded.extend(ids)
        return expanded, collapsed_ids, all_ids

    def _start_saved_status_bg(self):
        if getattr(self, "is_headless", False) or getattr(self, "is_host_only", False) or getattr(self, "_status_bg_started", False):
            return
        self._status_bg_started = True
        self._ensure_status_query_worker()
        if not getattr(self, "_status_ui_pump_started", False):
            self._status_ui_pump_started = True
            if getattr(self, "_status_ui_q", None) is None:
                self._status_ui_q = queue.Queue()
            self._pump_saved_status_ui()

    def query_computer_status(self, clean_id, priority=None):
        self._ensure_status_query_worker()
        self._start_saved_status_probe(clean_id)

    def _ids_in_saved_group(self, grp):
        want = (grp or "").strip()
        ids = []
        seen = set()

        def add(cid):
            cid = str(cid or "").replace(" ", "")
            if not cid:
                return
            key = self._canonical_saved_id(cid) or cid
            if key in seen:
                return
            seen.add(key)
            ids.append(cid)

        try:
            for cid, g, _n in self._list_saved_computers_meta():
                if (g or "").strip() == want:
                    add(cid)
        except Exception:
            pass
        groups = getattr(self, "_saved_id_groups", {}) or {}
        for cid, g in list(groups.items()):
            if (g or "").strip() == want:
                add(cid)
        return ids

    def _burst_saved_group_status(self, grp):
        """Hỏi check_online cả nhóm ngay (force) — dùng khi vừa bung nhóm."""
        self._ensure_status_query_worker()
        ids = self._ids_in_saved_group(grp)
        if not ids:
            return
        # Burst trên worker thread; giới hạn để không giữ signaling quá lâu.
        for i, cid in enumerate(ids):
            self._start_saved_status_probe(cid, force=True)
            if i + 1 < len(ids):
                time.sleep(0.02)

    def _canonical_saved_id(self, cid):
        from utils.hwid import canonical_hwid
        return canonical_hwid(str(cid or "").replace(" ", ""))

    def _is_live_saved_session(self, cid):
        """Máy của chính mình luôn online. Viewer treo sau khi host tắt không được ghim xanh."""
        cid = self._canonical_saved_id(cid)
        if not cid:
            return False
        return cid == self._canonical_saved_id(getattr(self, "my_id_clean", "") or "")

    def _next_online_gen(self, cid):
        gens = getattr(self, "_online_gen", None)
        if gens is None:
            self._online_gen = {}
            gens = self._online_gen
        n = int(gens.get(cid, 0) or 0) + 1
        gens[cid] = n
        return n

    def _clear_online_vote(self, cid):
        self._online_expect.pop(cid, None)
        self._online_got.pop(cid, None)
        self._online_any.pop(cid, None)
        deadlines = getattr(self, "_online_deadline", None)
        if deadlines is not None:
            deadlines.pop(cid, None)

    def _online_probe_pending(self, cid):
        cid = self._canonical_saved_id(cid)
        if not cid:
            return False
        lock = getattr(self, "_online_vote_lock", None)
        if lock is None:
            return False
        with lock:
            return cid in getattr(self, "_online_expect", {})

    def _start_saved_status_probe(self, cid, force=False):
        """Gửi 1 check_online, không chờ — kết quả/timeout cập nhật sau.

        force=True: hủy probe cũ và hỏi lại (burst khi bung nhóm).
        """
        cid = self._canonical_saved_id(cid)
        if not cid:
            return None
        if self._is_live_saved_session(cid):
            self.update_saved_computer_status(cid, True)
            return None
        lock = getattr(self, "_online_vote_lock", None)
        if lock is None:
            return None
        # Chỉ lấy ref socket dưới signaling_lock — KHÔNG giữ lock khi send.
        # Giữ signaling_lock suốt sendall dễ deadlock với luồng reconnect signaling.
        try:
            with self.signaling_lock:
                sock = getattr(self, "primary_signaling_socket", None)
        except Exception:
            sock = getattr(self, "primary_signaling_socket", None)
        if not sock:
            return None
        try:
            with lock:
                if cid in getattr(self, "_online_expect", {}):
                    if not force:
                        return None
                    self._clear_online_vote(cid)
                gen = self._next_online_gen(cid)
                self._online_expect[cid] = 1
                self._online_got[cid] = 0
                self._online_any[cid] = False
                if getattr(self, "_online_deadline", None) is None:
                    self._online_deadline = {}
                self._online_deadline[cid] = time.time() + 0.9
            req = json.dumps({"action": "check_online", "target": cid})
            ok = send_msg(sock, req.encode("utf-8"), APP_KEY)
            if ok is False:
                raise OSError("check_online send failed")
            return gen
        except Exception as e:
            if lock is not None:
                with lock:
                    self._clear_online_vote(cid)
            try:
                self.update_saved_computer_status(cid, False)
            except Exception:
                pass
            now = time.time()
            last = float(getattr(self, "_status_probe_err_log_at", 0) or 0)
            if now - last > 5.0:
                self._status_probe_err_log_at = now
                print(f"[StatusScan] check_online failed for {cid}: {e}")
            return None

    def _expire_stale_online_probes(self):
        lock = getattr(self, "_online_vote_lock", None)
        deadlines = getattr(self, "_online_deadline", None)
        if lock is None or not deadlines:
            return
        now = time.time()
        expired = []
        with lock:
            for cid, due in list(deadlines.items()):
                if now < due:
                    continue
                gen = getattr(self, "_online_gen", {}).get(cid)
                if cid in getattr(self, "_online_expect", {}):
                    expired.append((cid, gen))
                else:
                    deadlines.pop(cid, None)
        for cid, gen in expired:
            self.check_and_default_offline(cid, gen)

    def _pace_status_probe(self, started, gap, abort_on_open_burst=False):
        """Chờ đủ gap giữa 2 lần probe. True = cần restart vòng (vừa bung nhóm)."""
        while True:
            remain = gap - (time.time() - started)
            if remain <= 0:
                return False
            if abort_on_open_burst and getattr(self, "_status_fg_focus_group", None) is not None:
                return True
            slice_s = min(0.1, remain)
            ev = getattr(self, "_status_wake", None)
            if ev is None:
                time.sleep(slice_s)
                continue
            if ev.wait(timeout=slice_s):
                ev.clear()
                if abort_on_open_burst and getattr(self, "_status_fg_focus_group", None) is not None:
                    return True

    def _wait_probe_slot(self, cid, timeout_s=1.0, abort_on_open_burst=False):
        """Chờ probe trước xong (hoặc timeout) rồi mới hỏi máy này — tránh skip cả vòng."""
        deadline = time.time() + max(0.05, float(timeout_s or 0))
        while time.time() < deadline:
            try:
                self._expire_stale_online_probes()
            except Exception:
                pass
            if not self._online_probe_pending(cid):
                return True
            if abort_on_open_burst and getattr(self, "_status_fg_focus_group", None) is not None:
                return False
            time.sleep(0.05)
        try:
            self._expire_stale_online_probes()
        except Exception:
            pass
        return not self._online_probe_pending(cid)

    def _probe_one_saved_id(self, cid, gap, abort_on_open_burst=False, force=False):
        """Hỏi check_online 1 máy rồi pace theo gap. True = restart vòng."""
        # Open-groups: force hỏi lại để vòng quét nhanh không kẹt chờ vote cũ
        wait_s = 0.05 if force else 1.0
        self._wait_probe_slot(cid, timeout_s=wait_s, abort_on_open_burst=abort_on_open_burst)
        if self._online_probe_pending(cid):
            if force:
                pass  # _start_saved_status_probe(force=True) sẽ xóa vote cũ
            else:
                try:
                    self.check_and_default_offline(self._canonical_saved_id(cid))
                except Exception:
                    pass
        started = time.time()
        self._start_saved_status_probe(cid, force=force)
        return self._pace_status_probe(started, gap, abort_on_open_burst=abort_on_open_burst)

    def _touch_open_groups_heartbeat(self):
        self._status_open_loop_heartbeat = time.time()

    def _ensure_open_groups_loop_alive(self):
        """UI pump: nếu vòng open-groups im >5s thì khởi động lại thread."""
        if not getattr(self, "_status_query_worker_started", False):
            return
        if getattr(self, "is_headless", False) or getattr(self, "is_host_only", False):
            return
        now = time.time()
        hb = float(getattr(self, "_status_open_loop_heartbeat", 0) or 0)
        # Chưa từng đập (thread mới) — cho 3s khởi động
        if hb <= 0:
            self._status_open_loop_heartbeat = now
            return
        if now - hb < 5.0:
            return
        last_restart = float(getattr(self, "_status_open_loop_restart_at", 0) or 0)
        if now - last_restart < 5.0:
            return
        self._status_open_loop_restart_at = now
        self._status_open_loop_heartbeat = now
        self._status_open_loop_gen = int(getattr(self, "_status_open_loop_gen", 0) or 0) + 1
        print("[StatusScan] open-groups loop stalled — restarting thread")
        threading.Thread(
            target=self._saved_status_open_groups_loop,
            daemon=True,
            name="SavedStatusOpenGroups",
        ).start()

    def _saved_status_open_groups_loop(self):
        """Luôn chạy riêng: quét máy trong nhóm đang mở — round-robin nhanh, đáp ứng ngay khi máy online."""
        gap = 0.08
        my_gen = int(getattr(self, "_status_open_loop_gen", 0) or 0)
        self._touch_open_groups_heartbeat()
        while True:
            try:
                if int(getattr(self, "_status_open_loop_gen", 0) or 0) != my_gen:
                    return  # bị thread mới thay thế
                self._touch_open_groups_heartbeat()
                if getattr(self, "is_headless", False):
                    time.sleep(1.0)
                    continue

                focus = getattr(self, "_status_fg_focus_group", None)
                if focus is not None:
                    self._status_fg_focus_group = None
                    self._status_last_active_group = focus
                    if self._saved_list_is_open():
                        self._burst_saved_group_status(focus)
                        self._status_fg_scan_ids = list(self._ids_in_saved_group(focus))
                        self._status_fg_scan_idx = 0
                    self._touch_open_groups_heartbeat()
                    time.sleep(0.1)
                    continue

                if not self._saved_list_is_open():
                    self._status_fg_scan_ids = None
                    self._status_fg_scan_idx = 0
                    time.sleep(0.25)
                    continue

                try:
                    self._expire_stale_online_probes()
                except Exception:
                    pass

                expanded, _collapsed, _all_ids = self._saved_status_partitions()
                scan_ids = getattr(self, "_status_fg_scan_ids", None)
                if not scan_ids:
                    scan_ids = list(expanded)
                    self._status_fg_scan_ids = scan_ids
                    self._status_fg_scan_idx = 0

                if not scan_ids:
                    self._status_fg_scan_ids = None
                    self._status_fg_scan_idx = 0
                    time.sleep(0.25)
                    continue

                n = len(scan_ids)
                idx = int(getattr(self, "_status_fg_scan_idx", 0) or 0) % n
                cid = scan_ids[idx]
                nxt = (idx + 1) % n
                self._status_fg_scan_idx = nxt
                if nxt == 0:
                    # Hết vòng → lấy lại danh sách expanded (có thể đổi khi bung/thu)
                    self._status_fg_scan_ids = None
                    # Nghỉ 1.5s giữa các chu kỳ quét mở — nếu có bung nhóm mới sẽ được wake ngay lập tức
                    if self._pace_status_probe(time.time(), 1.5, abort_on_open_burst=True):
                        continue

                if not self._saved_id_is_expanded(cid):
                    # Máy đã thu nhóm — bỏ qua, không spin CPU
                    time.sleep(0.01)
                    continue

                if self._probe_one_saved_id(cid, gap, abort_on_open_burst=True, force=True):
                    continue
            except Exception as e:
                self._touch_open_groups_heartbeat()
                now = time.time()
                last = float(getattr(self, "_status_open_loop_err_at", 0) or 0)
                if now - last > 5.0:
                    self._status_open_loop_err_at = now
                    print(f"[StatusScan] open-groups loop error: {e}")
                time.sleep(0.5)

    def _saved_status_full_list_loop(self):
        """Luôn chạy riêng: list đóng → mọi máy 2s/máy; list mở → nhóm thu gọn 5s/máy."""
        gap_closed = 2.0
        gap_collapsed_open = 5.0
        while True:
            try:
                if getattr(self, "is_headless", False):
                    time.sleep(1.0)
                    continue
                list_open = self._saved_list_is_open()
                _expanded, collapsed_ids, all_ids = self._saved_status_partitions()
                if list_open:
                    targets = collapsed_ids
                    gap = gap_collapsed_open
                else:
                    targets = all_ids
                    gap = gap_closed
                if not targets:
                    time.sleep(0.4)
                    continue
                for cid in targets:
                    if getattr(self, "is_headless", False):
                        break
                    now_open = self._saved_list_is_open()
                    if now_open != list_open:
                        break
                    # List mở: máy đang ở nhóm bung do open-groups loop lo.
                    if now_open and self._saved_id_is_expanded(cid):
                        continue
                    try:
                        self._expire_stale_online_probes()
                    except Exception:
                        pass
                    if self._probe_one_saved_id(cid, gap, abort_on_open_burst=False, force=False):
                        break
            except Exception as e:
                now = time.time()
                last = float(getattr(self, "_status_full_loop_err_at", 0) or 0)
                if now - last > 5.0:
                    self._status_full_loop_err_at = now
                    print(f"[StatusScan] full-list loop error: {e}")
                time.sleep(0.5)

    def _ensure_status_query_worker(self):
        if getattr(self, "_status_query_worker_started", False):
            return
        self._status_query_worker_started = True
        self._online_vote_lock = threading.Lock()
        self._online_expect = {}
        self._online_got = {}
        self._online_any = {}
        self._online_gen = {}
        self._online_deadline = {}
        self._status_fg_scan_ids = None
        self._status_fg_scan_idx = 0
        self._status_open_loop_heartbeat = time.time()
        self._status_open_loop_gen = int(getattr(self, "_status_open_loop_gen", 0) or 0)
        if getattr(self, "_status_wake", None) is None:
            self._status_wake = threading.Event()
        if not hasattr(self, "_status_offline_strikes"):
            self._status_offline_strikes = {}

        threading.Thread(
            target=self._saved_status_open_groups_loop,
            daemon=True,
            name="SavedStatusOpenGroups",
        ).start()
        threading.Thread(
            target=self._saved_status_full_list_loop,
            daemon=True,
            name="SavedStatusFullList",
        ).start()
        try:
            if threading.current_thread() is threading.main_thread() and not getattr(self, "_status_ui_pump_started", False):
                self._status_ui_pump_started = True
                if getattr(self, "_status_ui_q", None) is None:
                    self._status_ui_q = queue.Queue()
                self._pump_saved_status_ui()
        except Exception:
            pass

    def _on_check_online_result(self, target, online):
        base = self._canonical_saved_id(target)
        if not base:
            return
        lock = getattr(self, "_online_vote_lock", None)
        if lock is None or not hasattr(self, "_online_expect"):
            self.update_saved_computer_status(base, online)
            return
        apply_now = False
        final = False
        with lock:
            if base not in self._online_expect:
                # Trả lời trễ / sau timeout — vẫn cập nhật UI (shutdown mềm về offline ngay).
                apply_now = True
                final = bool(online)
            elif online:
                self._online_any[base] = True
                apply_now = True
                final = True
                self._clear_online_vote(base)
            else:
                self._online_got[base] = self._online_got.get(base, 0) + 1
                if self._online_got[base] >= self._online_expect.get(base, 1):
                    apply_now = True
                    final = bool(self._online_any.get(base))
                    self._clear_online_vote(base)
        if apply_now:
            self.update_saved_computer_status(base, final)


    def check_and_default_offline(self, clean_id, gen=None):
        clean_id = self._canonical_saved_id(clean_id)
        lock = getattr(self, "_online_vote_lock", None)
        still_waiting = False
        any_on = False
        if lock is not None and hasattr(self, "_online_expect"):
            with lock:
                if gen is not None and getattr(self, "_online_gen", {}).get(clean_id) != gen:
                    return
                if clean_id in self._online_expect:
                    still_waiting = True
                    any_on = bool(self._online_any.get(clean_id))
                    self._clear_online_vote(clean_id)
        if not still_waiting:
            return
        if any_on or self._is_live_saved_session(clean_id):
            self.update_saved_computer_status(clean_id, True)
            return
        self.update_saved_computer_status(clean_id, False)


    def update_saved_computer_status(self, partner_id, is_online):
        if threading.current_thread() is not threading.main_thread():
            q = getattr(self, "_status_ui_q", None)
            if q is not None:
                try:
                    q.put((partner_id, bool(is_online)))
                    return
                except Exception:
                    pass
        self._apply_saved_computer_status(partner_id, is_online)

    def _apply_saved_computer_status(self, partner_id, is_online):
        from utils.hwid import canonical_hwid
        clean_id = canonical_hwid(partner_id)
        if not clean_id:
            return
        if self._is_live_saved_session(clean_id):
            is_online = True
        known = getattr(self, "_status_online", None)
        prev = None
        if known is not None:
            prev = known.get(clean_id)
            if prev is None:
                raw = str(partner_id or "").replace(" ", "")
                prev = known.get(raw)
            known[clean_id] = bool(is_online)
            raw = str(partner_id or "").replace(" ", "")
            if raw and raw != clean_id:
                known[raw] = bool(is_online)
        getattr(self, "_status_scanned", set()).add(clean_id)
        status_changed = (prev is None) or (bool(prev) != bool(is_online))
        new_color = "#00F5D4" if is_online else "#E05252"
        dots = getattr(self, "status_dots_widgets", None) or {}
        for key, widgets in list(dots.items()):
            if key != clean_id and self._canonical_saved_id(key) != clean_id:
                continue
            for dot_widget in widgets:
                try:
                    if dot_widget.winfo_exists() and dot_widget.cget("fg") != new_color:
                        dot_widget.config(fg=new_color)
                        from gui.components import apply_row_online_state
                        apply_row_online_state(getattr(dot_widget, "_row_root", None), bool(is_online), self.card_color, (self.text_white, self.text_gray))
                except Exception:
                    pass
        if status_changed and hasattr(self, '_reorder_saved_computers_func'):
            self.after(50, self._reorder_saved_computers_func)

