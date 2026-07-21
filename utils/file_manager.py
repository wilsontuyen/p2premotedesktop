from core.i18n import _
import os
import time
import base64
import threading
import pygame
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from gui.components import ProgressDialog

def inline_ask_string(parent, title, prompt, initialvalue=""):
    import tkinter as tk
    from tkinter import ttk
    var = tk.StringVar(parent, value="")
    result = [None]
    import sys
    use_dim = (sys.platform == "win32")
    
    if use_dim:
        dim = tk.Toplevel(parent)
        dim.attributes("-alpha", 0.4)
        dim.attributes("-topmost", True)
        dim.configure(bg="black")
        dim.overrideredirect(True)
        dim.geometry(f"{parent.winfo_width()}x{parent.winfo_height()}+0+0")
        dim.update_idletasks()
        try:
            import ctypes
            parent_hwnd = int(parent.frame(), 16)
            dim_hwnd = int(dim.frame(), 16)
            try: ctypes.windll.user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
            except: pass
            style = ctypes.windll.user32.GetWindowLongW(dim_hwnd, -16)
            style = (style | 0x40000000) & ~0x80000000
            ctypes.windll.user32.SetWindowLongW(dim_hwnd, -16, style)
            ctypes.windll.user32.SetParent(dim_hwnd, parent_hwnd)
            ctypes.windll.user32.SetWindowPos(dim_hwnd, 0, 0, 0, parent.winfo_width(), parent.winfo_height(), 0x0004)
        except: pass
    else:
        dim = None
    
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.transient(parent)
    dlg.attributes("-topmost", True)
    dlg.configure(bg="#F0F0F0")
    dlg.resizable(False, False)
    
    if sys.platform == "win32":
        dlg.geometry(f"400x150")
        dlg.update_idletasks()
        try:
            import ctypes
            parent_hwnd = int(parent.frame(), 16)
            dlg_hwnd = int(dlg.frame(), 16)
            try: ctypes.windll.user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
            except: pass
            style = ctypes.windll.user32.GetWindowLongW(dlg_hwnd, -16)
            style = (style | 0x40000000) & ~0x80000000
            ctypes.windll.user32.SetWindowLongW(dlg_hwnd, -16, style)
            ctypes.windll.user32.SetParent(dlg_hwnd, parent_hwnd)
            
            x = (parent.winfo_width() - 400) // 2
            y = (parent.winfo_height() - 150) // 2
            ctypes.windll.user32.SetWindowPos(dlg_hwnd, 0, x, y, 400, 150, 0x0004)
        except: pass
    else:
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        if px == 0 and py == 0:
            sw = parent.winfo_screenwidth()
            sh = parent.winfo_screenheight()
            x = (sw - 400) // 2
            y = (sh - 150) // 2
        else:
            x = px + (parent.winfo_width() - 400) // 2
            y = py + (parent.winfo_height() - 150) // 2
        dlg.geometry(f"400x150+{x}+{y}")
    
    lbl_title = tk.Label(dlg, text=title, font=("Segoe UI", 10, "bold"), bg="#F0F0F0")
    lbl_title.pack(pady=(10, 5), padx=20, anchor=tk.W)
    
    lbl_msg = tk.Label(dlg, text=prompt, font=("Segoe UI", 9), bg="#F0F0F0")
    lbl_msg.pack(pady=(0, 5), padx=20, anchor=tk.W)
    
    entry = ttk.Entry(dlg, font=("Segoe UI", 9), width=35)
    entry.pack(padx=20, pady=(0, 10))
    if initialvalue:
        entry.insert(0, initialvalue)
        entry.select_range(0, tk.END)
    entry.focus_force()
    
    btn_frame = tk.Frame(dlg, bg="#F0F0F0")
    btn_frame.pack(fill=tk.X, padx=20, pady=(0, 10), side=tk.BOTTOM)
    
    def _ok(e=None):
        result[0] = entry.get()
        var.set("done")
        
    def _cancel(e=None):
        result[0] = None
        var.set("done")
        
    entry.bind("<Return>", _ok)
    entry.bind("<Escape>", _cancel)
    dlg.protocol("WM_DELETE_WINDOW", _cancel)
    
    btn_ok = ttk.Button(btn_frame, text=_("Đồng ý"), command=_ok, width=10)
    btn_ok.pack(side=tk.LEFT, padx=(0, 5))
    
    btn_cancel = ttk.Button(btn_frame, text=_("Hủy"), command=_cancel, width=10)
    btn_cancel.pack(side=tk.RIGHT, padx=(5, 0))
    
    dlg.grab_set()
    parent.update_idletasks()
    
    parent.wait_variable(var)
    if dim:
        dim.destroy()
    dlg.destroy()
    return result[0]


def open_transfer_window(computer_name, is_android, send_event, host_hwnd=None, host_w=1920, host_h=1080):
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        import threading, os, time, base64

        top = tk.Tk()
        globals()['fm_top'] = top
        top.attributes('-alpha', 0.0) # Ẩn đi để tránh nháy khi tạo

        host_title = f" - {computer_name}" if computer_name else ""
        top.title(_("P2P Remote Desktop - Trình Quản Lý Tệp (File Manager){host_title}").format(host_title=host_title))

        hwnd = pygame.display.get_wm_info().get("window")
        import sys
        if hwnd and sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
            py_w = rect.right - rect.left
            py_h = rect.bottom - rect.top

            # Try to get screen coordinates of the Pygame window
            pt = wintypes.POINT(0, 0)
            ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))

            top.update_idletasks()
            tk_hwnd = int(top.frame(), 16)
            try: ctypes.windll.user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
            except: pass
            style = ctypes.windll.user32.GetWindowLongW(tk_hwnd, -16)
            style = (style | 0x40000000) & ~0x80000000
            ctypes.windll.user32.SetWindowLongW(tk_hwnd, -16, style)
            ctypes.windll.user32.SetParent(tk_hwnd, hwnd)
            x = max(0, (py_w - 900) // 2)
            y = max(0, (py_h - 600) // 2)
            top.geometry("900x600")
            top.update_idletasks()
            ctypes.windll.user32.SetWindowPos(tk_hwnd, 0, x, y, 900, 600, 0x0004)
        else:
            top.update_idletasks()
            sw = top.winfo_screenwidth()
            sh = top.winfo_screenheight()
            top.geometry(f"900x600+{(sw - 900) // 2}+{(sh - 600) // 2}")

        top.attributes('-topmost', True)
        top.attributes('-alpha', 1.0) # Hiện lại sau khi set geometry
        top.configure(bg="#E5E5E5")

        left_frame = tk.Frame(top, bg="#E5E5E5")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        mid_frame = tk.Frame(top, width=60, bg="#E5E5E5")
        mid_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        btn_upload = tk.Button(mid_frame, text=_("Chuyển qua\n>>"), font=("Segoe UI", 10, "bold"), bg="#2196F3", fg="white", width=10)
        btn_upload.pack(pady=(100, 10))
        btn_download = tk.Button(mid_frame, text=_("Nhận về\n<<"), font=("Segoe UI", 10, "bold"), bg="#4CAF50", fg="white", width=10)
        btn_download.pack(pady=10)

        right_frame = tk.Frame(top, bg="#E5E5E5")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Left Pane (Local) ---
        tk.Label(left_frame, text=_("Máy của bạn (Local)"), font=("Segoe UI", 10, "bold"), bg="#E5E5E5").pack()
        local_nav = tk.Frame(left_frame, bg="#E5E5E5")
        local_nav.pack(fill=tk.X, pady=2)

        local_entry = tk.Entry(local_nav)
        local_entry.insert(0, os.path.abspath(os.path.expanduser("~")))

        def format_size(s):
            if s < 1024: return f"{s} B"
            elif s < 1024*1024: return f"{s/1024:.1f} KB"
            elif s < 1024*1024*1024: return f"{s/(1024*1024):.1f} MB"
            elif s < 1024*1024*1024*1024: return f"{s/(1024*1024*1024):.2f} GB"
            else: return f"{s/(1024*1024*1024*1024):.2f} TB"

        def show_properties_dialog(name, item_type, location, size_bytes, file_count=None, folder_count=None, modified_time=None):
            """Show a properties dialog for a file or folder."""
            dlg = tk.Toplevel(top)
            dlg.title(_("Thuộc tính"))
            dlg.transient(top)
            dlg.configure(bg="#F0F0F0")
            dlg.resizable(False, False)

            w, h = 400, 380
            import sys
            if sys.platform == "win32":
                dlg.geometry(f"{w}x{h}")
                dlg.update_idletasks()
                dlg_hwnd = int(dlg.frame(), 16)
                import ctypes
                try: ctypes.windll.user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
                except: pass
                style = ctypes.windll.user32.GetWindowLongW(dlg_hwnd, -16)
                style = (style | 0x40000000) & ~0x80000000
                ctypes.windll.user32.SetWindowLongW(dlg_hwnd, -16, style)
                
                top.update_idletasks()
                top_hwnd = int(top.frame(), 16)
                ctypes.windll.user32.SetParent(dlg_hwnd, top_hwnd)
                
                x = max(0, (top.winfo_width() - w) // 2)
                y = max(0, (top.winfo_height() - h) // 2)
                ctypes.windll.user32.SetWindowPos(dlg_hwnd, 0, x, y, w, h, 0x0004)
            else:
                dlg.attributes('-topmost', True)
                top.update_idletasks()
                px, py_ = top.winfo_rootx(), top.winfo_rooty()
                pw, ph = top.winfo_width(), top.winfo_height()
                dlg.geometry(f"{w}x{h}+{px + (pw - w)//2}+{py_ + (ph - h)//2}")

            # Title bar
            title_frame = tk.Frame(dlg, bg="#0078D7", height=40)
            title_frame.pack(fill=tk.X)
            title_frame.pack_propagate(False)
            tk.Label(title_frame, text=f"  📋 {name}", font=("Segoe UI", 11, "bold"), bg="#0078D7", fg="white", anchor="w").pack(fill=tk.X, padx=5, pady=8)

            # Content
            content_frame = tk.Frame(dlg, bg="#F0F0F0")
            content_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

            row = 0
            def add_row(label_text, value_text, bold_value=False):
                nonlocal row
                tk.Label(content_frame, text=label_text, font=("Segoe UI", 9, "bold"), bg="#F0F0F0", fg="#333", anchor="w").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 10))
                font_style = ("Segoe UI", 9, "bold") if bold_value else ("Segoe UI", 9)
                lbl = tk.Label(content_frame, text=value_text, font=font_style, bg="#F0F0F0", fg="#111", anchor="w", wraplength=250, justify="left")
                lbl.grid(row=row, column=1, sticky="w", pady=4)
                row += 1
                return lbl

            add_row(_("Tên:"), name)

            # Separator
            sep1 = tk.Frame(content_frame, bg="#CCC", height=1)
            sep1.grid(row=row, column=0, columnspan=2, sticky="ew", pady=6)
            row += 1

            add_row(_("Loại:"), item_type)
            add_row(_("Vị trí:"), location)

            sep2 = tk.Frame(content_frame, bg="#CCC", height=1)
            sep2.grid(row=row, column=0, columnspan=2, sticky="ew", pady=6)
            row += 1

            size_label = add_row(_("Kích thước:"), format_size(size_bytes) + f"  ({size_bytes:,} bytes)" if size_bytes >= 0 else _("Đang tính..."), bold_value=True)

            if file_count is not None:
                add_row(_("Chứa:"), _("Tệp: {file_count}, Thư mục: {folder_count}").format(file_count=file_count, folder_count=folder_count))

            if modified_time:
                sep3 = tk.Frame(content_frame, bg="#CCC", height=1)
                sep3.grid(row=row, column=0, columnspan=2, sticky="ew", pady=6)
                row += 1
                add_row(_("Sửa đổi:"), modified_time)

            # Close button
            btn_frame = tk.Frame(dlg, bg="#F0F0F0")
            btn_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
            ttk.Button(btn_frame, text=_("Đóng"), command=dlg.destroy, width=12).pack(side=tk.RIGHT)

            try: dlg.grab_set()
            except: pass
            
            return dlg, size_label

        def refresh_local():
            for item in local_tree.get_children():
                local_tree.delete(item)
            try:
                import sys
                path = local_entry.get()
                if path == "This PC":
                    if sys.platform != "win32":
                        local_entry.delete(0, tk.END)
                        local_entry.insert(0, "/")
                        path = "/"
                    else:
                        btn_upload.config(state=tk.DISABLED)
                        btn_download.config(state=tk.DISABLED)
                        import string
                        import ctypes
                        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
                        drives = []
                        for letter in string.ascii_uppercase:
                            if bitmask & 1:
                                drives.append(f"{letter}:\\")
                            bitmask >>= 1
                        for d in drives:
                            local_tree.insert("", "end", text=d, values=("", _("Ổ đĩa"), 0))
                        return
                
                if path != "This PC":
                    btn_upload.config(state=tk.NORMAL)
                    btn_download.config(state=tk.NORMAL)

                items = os.listdir(path)
                # Folders first, then files
                dirs = []
                files = []
                for item in items:
                    full = os.path.join(path, item)
                    if os.path.isdir(full):
                        dirs.append(item)
                    else:
                        files.append(item)
                dirs.sort(key=str.lower)
                files.sort(key=str.lower)

                for d in dirs:
                    local_tree.insert("", "end", text=d, values=("", _("Thư mục")))
                for f in files:
                    full = os.path.join(path, f)
                    size = os.path.getsize(full)
                    local_tree.insert("", "end", text=f, values=(format_size(size), _("Tệp"), size))
            except Exception as e:
                pass

        def go_up_local():
            current = local_entry.get()
            if current == "This PC": return
            parent = os.path.dirname(current)
            if parent and parent == current:
                import sys
                if sys.platform == "win32":
                    parent = "This PC"
                else:
                    return

            local_entry.delete(0, tk.END)
            local_entry.insert(0, parent)
            refresh_local()

        tk.Button(local_nav, text=_("⬆ Lên"), command=go_up_local).pack(side=tk.LEFT)
        local_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Button(local_nav, text=_("Đi"), command=refresh_local).pack(side=tk.LEFT)

        local_tree_frame = tk.Frame(left_frame, bd=1, relief=tk.SUNKEN)
        local_tree_frame.pack(fill=tk.BOTH, expand=True)
        local_scrollbar = tk.Scrollbar(local_tree_frame, orient="vertical", width=16)
        local_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        local_tree = ttk.Treeview(local_tree_frame, columns=("size", "type", "raw_size"), show="tree headings", yscrollcommand=local_scrollbar.set)
        local_tree.heading("#0", text=_("Tên"))
        local_tree.heading("size", text=_("Kích thước"))
        local_tree.heading("type", text=_("Loại"))
        local_tree.column("#0", width=200)
        local_tree.column("size", width=80)
        local_tree.column("type", width=70)
        local_tree.column("raw_size", width=0, stretch=False)
        local_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        local_scrollbar.config(command=local_tree.yview)

        def local_double_click(event):
            sel = local_tree.selection()
            if sel:
                item = local_tree.item(sel[0])
                vals = item.get('values', [])
                name = item['text']
                if local_entry.get() == "This PC":
                    fpath = name
                else:
                    fpath = os.path.join(local_entry.get(), name)
                is_dir = (len(vals) > 1 and vals[1] in (_("Thư mục"), _("Ổ đĩa")))
                if not is_dir:
                    try: is_dir = os.path.isdir(fpath)
                    except: pass
                if is_dir:
                    new_path = fpath
                    local_entry.delete(0, tk.END)
                    local_entry.insert(0, new_path)
                    refresh_local()
                else:
                    local_action("view")
        def _handle_bs_local(e):
            go_up_local()
            return "break"
        local_tree.bind("<Double-1>", local_double_click)
        local_tree.bind("<BackSpace>", _handle_bs_local)

        local_menu = tk.Menu(top, tearoff=0)
        def local_action(action):
            try:
                current_dir = local_entry.get()
                sel = local_tree.selection()
                if action == "mkdir":
                    
                    new_name = inline_ask_string(top, _("Thư mục mới"), _("Nhập tên thư mục mới:"))
                    top.focus_force()
                    if new_name:
                        try:
                            folder_path = os.path.join(current_dir, new_name)
                            if os.path.exists(folder_path):
                                messagebox.showinfo(_("Lỗi"), _('Thư mục "{new_name}" đã tồn tại trên "{current_dir}"').format(new_name=new_name, current_dir=current_dir), parent=top)
                            else:
                                os.makedirs(folder_path, exist_ok=True)
                                refresh_local()
                        except Exception as e:
                            with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f: f.write(f"Error mkdir: {str(e)}\n")
                    return
                if not sel: return

                if action == "delete":
                    if len(sel) == 1:
                        msg = _("Bạn có chắc muốn xóa '{item_name}' không?").format(item_name=local_tree.item(sel[0])['text'])
                    else:
                        msg = _("Bạn có chắc muốn xóa {count} mục đã chọn không?").format(count=len(sel))
                    confirm = messagebox.askyesno(_("Xác nhận"), msg, parent=top)
                    top.focus_force()
                    if confirm:
                        for s in sel:
                            item = local_tree.item(s)
                            name = item['text']
                            full_path = os.path.join(current_dir, name)
                            vals = item.get('values', [])
                            is_dir = (len(vals) > 1 and vals[1] == _("Thư mục"))
                            try:
                                if is_dir:
                                    import shutil
                                    shutil.rmtree(full_path)
                                else:
                                    os.remove(full_path)
                            except Exception as e:
                                messagebox.showerror(_("Lỗi"), _("Lỗi xóa {name}: {e}").format(name=name, e=e), parent=top)
                        refresh_local()
                    return

                if action == "properties":
                    # Properties for first selected item
                    item = local_tree.item(sel[0])
                    name = item['text']
                    full_path = os.path.join(current_dir, name)
                    vals = item.get('values', [])
                    is_dir = (len(vals) > 1 and vals[1] in (_("Thư mục"), _("Ổ đĩa")))

                    from datetime import datetime
                    try:
                        mtime = os.path.getmtime(full_path)
                        mod_time = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        mod_time = _("Không xác định")

                    if is_dir:
                        # Show dialog immediately with "calculating..." then update in background
                        dlg, size_label = show_properties_dialog(
                            name, _("Thư mục"), current_dir, -1,
                            file_count=0, folder_count=0, modified_time=mod_time
                        )
                        size_label.config(text=_("Đang tính..."))

                        def calc_dir_size(fp, lbl, dialog):
                            total_size = 0
                            file_count = 0
                            folder_count = 0
                            try:
                                for dirpath, dirnames, filenames in os.walk(fp):
                                    folder_count += len(dirnames)
                                    for f in filenames:
                                        file_count += 1
                                        try:
                                            total_size += os.path.getsize(os.path.join(dirpath, f))
                                        except:
                                            pass
                            except:
                                pass
                            try:
                                if dialog.winfo_exists():
                                    dialog.after(0, lambda: _update_props_labels(lbl, dialog, total_size, file_count, folder_count))
                            except:
                                pass

                        def _update_props_labels(lbl, dialog, total_size, file_count, folder_count):
                            try:
                                if dialog.winfo_exists():
                                    lbl.config(text=format_size(total_size) + f"  ({total_size:,} bytes)")
                                    # Find and update the "Chứa" label
                                    for widget in dialog.winfo_children():
                                        for child in widget.winfo_children():
                                            try:
                                                if hasattr(child, 'cget') and child.cget('text').startswith(_("Tệp:")):
                                                    child.config(text=_("Tệp: {file_count}, Thư mục: {folder_count}").format(file_count=file_count, folder_count=folder_count))
                                            except:
                                                pass
                            except:
                                pass

                        threading.Thread(target=calc_dir_size, args=(full_path, size_label, dlg), daemon=True).start()
                    else:
                        try:
                            size = os.path.getsize(full_path)
                        except:
                            size = 0
                        show_properties_dialog(name, _("Tệp"), current_dir, size, modified_time=mod_time)
                    return

                for s in sel:
                    item = local_tree.item(s)
                    name = item['text']
                    full_path = os.path.join(current_dir, name)
                    vals = item.get('values', [])
                    is_dir = (len(vals) > 1 and vals[1] == _("Thư mục"))

                    if action == "view":
                        from datetime import datetime
                        ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
                        with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                            f.write(f"{ts} [Local] Action 'view' started for '{name}', is_dir={is_dir}\n")
                        if is_dir:
                            messagebox.showwarning(_("Cảnh báo"), _("Không thể xem thư mục '{name}' bằng Notepad!").format(name=name), parent=top)
                        else:
                            text_exts = {'.txt', '.log', '.md', '.py', '.json', '.xml', '.ini', '.cfg', '.csv', '.html', '.css', '.js', '.kt', '.java', '.c', '.cpp', '.h', '.bat', '.sh', ''}
                            _base, ext = os.path.splitext(name.lower())
                            if ext in text_exts:
                                try:
                                    with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                        f.write(f"{ts} [Local] Opening {full_path}...\n")
                                    with open(full_path, "r", encoding="utf-8") as f:
                                        file_content = f.read(5 * 1024 * 1024)
                                    with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                        f.write(f"{ts} [Local] Read successful, creating window...\n")
                                    np_win = tk.Toplevel(top)
                                    np_win.title(_("Soạn thảo (Local) - {name}").format(name=name))
                                    np_win.geometry("800x600")
                                    np_win.transient(top)
                                    np_win.attributes('-topmost', True)
                                    np_win.update_idletasks()
                                    w, h = 800, 600
                                    px, py = top.winfo_rootx(), top.winfo_rooty()
                                    pw, ph = top.winfo_width(), top.winfo_height()
                                    np_win.geometry(f"800x600+{px + (pw-w)//2}+{py + (ph-h)//2}")
                                    text_area = tk.Text(np_win, wrap="word", font=("Consolas", 11))
                                    text_area.pack(expand=True, fill="both")
                                    text_area.insert("1.0", file_content)
                                    def make_save(fp, ta, win):
                                        def save_file():
                                            try:
                                                with open(fp, "w", encoding="utf-8") as fw:
                                                    fw.write(ta.get("1.0", "end-1c"))
                                                messagebox.showinfo(_("Thành công"), _("Đã lưu tệp!"), parent=win)
                                            except Exception as e:
                                                messagebox.showerror(_("Lỗi"), _("Không thể lưu: {e}").format(e=e), parent=win)
                                        return save_file
                                    tk.Button(np_win, text=_("Lưu"), command=make_save(full_path, text_area, np_win), bg="green", fg="white", font=("Arial", 10, "bold")).pack(pady=5)
                                    with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                        f.write(f"{ts} [Local] Window created successfully.\n")
                                except Exception as ex:
                                    import traceback
                                    with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                        f.write(f"{ts} [Local] CRASH during view: {traceback.format_exc()}\n")
                                    messagebox.showerror(_("Lỗi"), str(ex), parent=top)
                            else:
                                try:
                                    import sys, subprocess
                                    if sys.platform == "win32": os.startfile(full_path)
                                    else: subprocess.call(["xdg-open", full_path])
                                except Exception as e:
                                    messagebox.showerror(_("Lỗi"), str(e), parent=top)
                    elif action == "rename":
                        
                        new_name = inline_ask_string(top, _("Đổi tên"), _("Nhập tên mới cho '{name}':").format(name=name), initialvalue=name)
                        top.focus_force()
                        if new_name and new_name != name:
                            try:
                                os.rename(full_path, os.path.join(current_dir, new_name))
                            except Exception as e:
                                messagebox.showerror(_("Lỗi"), str(e), parent=top)
                if action == "rename":
                    refresh_local()
            except Exception as outer_e:
                import traceback
                from datetime import datetime
                ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
                with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                    f.write(f"{ts} [Local] OUTER CRASH: {traceback.format_exc()}\n")
                messagebox.showerror(_("Lỗi"), str(outer_e), parent=top)
        def show_local_menu(event):
            local_menu.delete(0, 'end')
            row = local_tree.identify_row(event.y)
            if not row:
                local_menu.add_command(label=_("Tạo thư mục mới"), command=lambda: local_action("mkdir"))
                local_menu.add_separator()
                local_menu.add_command(label=_("Làm mới"), command=refresh_local)
                local_menu.tk_popup(event.x_root, event.y_root)
                return

            if row not in local_tree.selection():
                local_tree.selection_set(row)

            vals = local_tree.item(row, "values")
            is_dir = (len(vals) > 1 and vals[1] == _("Thư mục"))

            if not is_dir:
                local_menu.add_command(label=_("Xem tệp"), command=lambda: local_action("view"))
            local_menu.add_command(label=_("Tạo thư mục mới"), command=lambda: local_action("mkdir"))
            local_menu.add_command(label=_("Đổi tên"), command=lambda: local_action("rename"))
            local_menu.add_separator()
            local_menu.add_command(label=_("Xóa"), command=lambda: local_action("delete"))
            local_menu.add_separator()
            local_menu.add_command(label=_("Thuộc tính"), command=lambda: local_action("properties"))

            try:
                local_menu.tk_popup(event.x_root, event.y_root)
            finally:
                local_menu.grab_release()
        local_tree.bind("<Button-3>", show_local_menu)

        def select_all_local(event):
            local_tree.selection_set(local_tree.get_children())
            return "break"
        local_tree.bind("<Control-a>", select_all_local)
        local_tree.bind("<Control-A>", select_all_local)

        # --- Right Pane (Remote) ---
        tk.Label(right_frame, text=_("Máy điều khiển (Remote Host)"), font=("Segoe UI", 10, "bold"), bg="#E5E5E5").pack()
        remote_nav = tk.Frame(right_frame, bg="#E5E5E5")
        remote_nav.pack(fill=tk.X, pady=2)

        remote_entry = tk.Entry(remote_nav)
        
        try:
            import core.viewer
            host_os = getattr(core.viewer, 'client_host_os_release', '10')
            is_host_win = host_os in ["7", "8", "8.1", "10", "11", "XP", "Vista"] or "Server" in host_os
        except Exception:
            is_host_win = True
            
        if is_android:
            default_path = "/sdcard/"
        elif not is_host_win:
            default_path = "/"
        else:
            default_path = "C:\\"
            
        remote_entry.insert(0, default_path)

        def request_remote_dir(path):
            # send list_dir request
            req = {"type": "request_list_dir", "path": path}
            send_event(req)

        def on_remote_dir_result(event):
            evt_type = event.get("type", "list_dir_result")
            if evt_type == "list_dir_result":
                if event.get("path") != remote_entry.get():
                    return
                if remote_entry.get() == "This PC":
                    btn_upload.config(state=tk.DISABLED)
                    btn_download.config(state=tk.DISABLED)
                elif local_entry.get() != "This PC":
                    btn_upload.config(state=tk.NORMAL)
                    btn_download.config(state=tk.NORMAL)
                for item in remote_tree.get_children():
                    remote_tree.delete(item)
                items = event.get("items", [])
                dirs = [i for i in items if i.get("is_dir")]
                files = [i for i in items if not i.get("is_dir")]
                dirs.sort(key=lambda x: str(x.get("name")).lower())
                files.sort(key=lambda x: str(x.get("name")).lower())

                for d in dirs:
                    remote_tree.insert("", "end", text=d.get("name"), values=("", _("Thư mục")))
                for f in files:
                    sz = f.get("size", 0)
                    remote_tree.insert("", "end", text=f.get("name"), values=(format_size(sz), _("Tệp"), sz))
            elif evt_type == "get_properties_result":
                success = event.get("success")
                if success:
                    name = event.get("name", "")
                    item_type = _("Thư mục") if event.get("is_dir") else _("Tệp")
                    location = event.get("location", "")
                    size_bytes = event.get("size", 0)
                    file_count = event.get("file_count")
                    folder_count = event.get("folder_count")
                    mod_time = event.get("modified_time", _("Không xác định"))
                    show_properties_dialog(name, item_type, location, size_bytes,
                                          file_count=file_count, folder_count=folder_count,
                                          modified_time=mod_time)
                else:
                    messagebox.showerror(_("Lỗi"), event.get("error", _("Không thể lấy thuộc tính")), parent=top)
            elif evt_type in ("delete_item_result", "rename_item_result", "create_folder_result", "open_file_result"):
                success = event.get("success")
                error = event.get("error")
                if not success:
                    messagebox.showerror(_("Lỗi"), error or _("Thao tác thất bại"), parent=top)
                else:
                    request_remote_dir(remote_entry.get())
            elif evt_type == "read_text_file_result":
                success = event.get("success")
                if success:
                    try:
                        from datetime import datetime
                        ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
                        open("C:\\Apps\\P2P\\agent.log", "a", encoding="utf-8").write(f"{ts} [Remote] Remote read success, creating Toplevel Notepad\n")
                        content = event.get("content", "")
                        path = event.get("path", "")
                        name = path.split("/")[-1] if "/" in path else path.split("\\")[-1]
                        np_win = tk.Toplevel(top)
                        np_win.title(_("Soạn thảo (Remote) - {name}").format(name=name))
                        np_win.geometry("800x600")
                        np_win.transient(top)
                        np_win.attributes('-topmost', True)
                        np_win.update_idletasks()
                        w, h = 800, 600
                        px, py = top.winfo_rootx(), top.winfo_rooty()
                        pw, ph = top.winfo_width(), top.winfo_height()
                        np_win.geometry(f"800x600+{px + (pw-w)//2}+{py + (ph-h)//2}")
                        text_area = tk.Text(np_win, wrap="word", font=("Consolas", 11))
                        text_area.pack(expand=True, fill="both")
                        text_area.insert("1.0", content)
                    except Exception as ex:
                        messagebox.showerror(_("Lỗi Code"), _("Lỗi tạo Notepad: {ex}").format(ex=ex), parent=top)
                        return
                    def save_remote_file():
                        req = {"type": "request_write_text_file", "path": path, "content": text_area.get("1.0", "end-1c")}
                        send_event(req)
                        messagebox.showinfo(_("Thông báo"), _("Đã gửi yêu cầu lưu tệp tới thiết bị điều khiển."), parent=np_win)
                    tk.Button(np_win, text=_("Lưu"), command=save_remote_file, bg="green", fg="white", font=("Arial", 10, "bold")).pack(pady=5)
                else:
                    messagebox.showerror(_("Lỗi"), event.get("error", _("Không thể đọc tệp")), parent=top)
            elif evt_type == "write_text_file_result":
                success = event.get("success")
                if not success:
                    messagebox.showerror(_("Lỗi"), event.get("error", _("Lỗi lưu tệp từ xa")), parent=top)
            elif evt_type in ("batch_start", "file_start", "file_chunk", "file_end"):
                try:
                    from core.clipboard_agent import clipboard_sync_manager as cm
                    if cm:
                        cm.process_clipboard_event(event)
                except Exception:
                    pass
            elif evt_type == "batch_end":
                try:
                    from core.clipboard_agent import clipboard_sync_manager as cm
                    if cm:
                        cm.process_clipboard_event(event)
                except Exception:
                    pass
                top.after(500, refresh_local)

        import queue
        fm_event_queue = queue.Queue()
        def process_fm_queue():
            try:
                while True:
                    evt = fm_event_queue.get_nowait()
                    if evt.get("type") == "trigger_local_refresh":
                        refresh_local()
                    else:
                        on_remote_dir_result(evt)
            except queue.Empty:
                pass
            if top.winfo_exists():
                top.after(100, process_fm_queue)

        top.after(100, process_fm_queue)
        import core.viewer
        core.viewer.file_manager_callback = lambda e: fm_event_queue.put(e)

        def go_up_remote():
            p = remote_entry.get().replace("\\", "/").rstrip("/")
            if "/" in p:
                parent = p.rsplit("/", 1)[0]
                if not parent: parent = "/"
                if not is_android and len(parent) == 2 and parent.endswith(":"):
                    parent += "/"
                remote_entry.delete(0, tk.END)
                remote_entry.insert(0, parent)
                request_remote_dir(parent)

        tk.Button(remote_nav, text=_("⬆ Lên"), command=go_up_remote).pack(side=tk.LEFT)
        remote_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        tk.Button(remote_nav, text=_("Đi"), command=lambda: request_remote_dir(remote_entry.get())).pack(side=tk.LEFT)

        remote_tree_frame = tk.Frame(right_frame, bd=1, relief=tk.SUNKEN)
        remote_tree_frame.pack(fill=tk.BOTH, expand=True)
        remote_scrollbar = tk.Scrollbar(remote_tree_frame, orient="vertical", width=16)
        remote_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        remote_tree = ttk.Treeview(remote_tree_frame, columns=("size", "type", "raw_size"), show="tree headings", yscrollcommand=remote_scrollbar.set)
        remote_tree.heading("#0", text=_("Tên"))
        remote_tree.heading("size", text=_("Kích thước"))
        remote_tree.heading("type", text=_("Loại"))
        remote_tree.column("#0", width=200)
        remote_tree.column("size", width=80)
        remote_tree.column("type", width=70)
        remote_tree.column("raw_size", width=0, stretch=False)
        remote_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        remote_scrollbar.config(command=remote_tree.yview)

        def remote_double_click(event):
            sel = remote_tree.selection()
            if sel:
                item = remote_tree.item(sel[0])
                vals = item.get('values', [])
                is_dir = (len(vals) > 1 and vals[1] == _("Thư mục"))
                if is_dir:
                    p = remote_entry.get()
                    sep = "/" if "/" in p else ("\\" if "\\" in p else "/")
                    if not p.endswith(sep): p += sep
                    new_path = p + item['text']
                    remote_entry.delete(0, tk.END)
                    remote_entry.insert(0, new_path)
                    request_remote_dir(new_path)
                else:
                    remote_action("view")
        def _handle_bs_remote(e):
            go_up_remote()
            return "break"
        remote_tree.bind("<Double-1>", remote_double_click)
        remote_tree.bind("<BackSpace>", _handle_bs_remote)

        remote_menu = tk.Menu(top, tearoff=0)
        def remote_action(action):
            current_dir = remote_entry.get()
            sep = "/" if "/" in current_dir else ("\\" if "\\" in current_dir else "/")
            if not current_dir.endswith(sep): current_dir += sep
            sel = remote_tree.selection()
            if action == "mkdir":
                
                new_name = inline_ask_string(top, _("Thư mục mới"), _("Nhập tên thư mục mới:"))
                top.focus_force()
                if new_name:
                    exists = False
                    for child in remote_tree.get_children():
                        if remote_tree.item(child, "text") == new_name:
                            exists = True
                            break
                    if exists:
                        messagebox.showinfo(_("Lỗi"), _('Thư mục "{new_name}" đã tồn tại trên "{current_dir}"').format(new_name=new_name, current_dir=current_dir), parent=top)
                    else:
                        req = {"type": "request_create_folder", "parent_path": current_dir, "folder_name": new_name}
                        send_event(req)
                return
            if not sel: return

            if action == "delete":
                if len(sel) == 1:
                    msg = _("Bạn có chắc muốn xóa '{item_name}' khỏi máy điều khiển không?").format(item_name=remote_tree.item(sel[0])['text'])
                else:
                    msg = _("Bạn có chắc muốn xóa {count} mục đã chọn khỏi máy điều khiển không?").format(count=len(sel))
                confirm = messagebox.askyesno(_("Xác nhận"), msg, parent=top)
                top.focus_force()
                if confirm:
                    for s in sel:
                        item = remote_tree.item(s)
                        name = item['text']
                        full_path = current_dir + name
                        req = {"type": "request_delete_item", "path": full_path}
                        send_event(req)
                return

            for s in sel:
                item = remote_tree.item(s)
                name = item['text']
                full_path = current_dir + name
                vals = item.get('values', [])
                is_dir = (len(vals) > 1 and vals[1] == _("Thư mục"))
                if action == "view":
                    from datetime import datetime
                    ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
                    open("C:\\Apps\\P2P\\agent.log", "a", encoding="utf-8").write(f"{ts} [Remote] Action 'view' on '{name}', is_dir={is_dir}\n")
                    if is_dir:
                        messagebox.showwarning(_("Cảnh báo"), _("Không thể xem thư mục '{name}' bằng Notepad!").format(name=name), parent=top)
                    else:
                        text_exts = {'.txt', '.log', '.md', '.py', '.json', '.xml', '.ini', '.cfg', '.csv', '.html', '.css', '.js', '.kt', '.java', '.c', '.cpp', '.h', '.bat', '.sh', ''}
                        _base, ext = os.path.splitext(name.lower())
                        if ext in text_exts:
                            req = {"type": "request_read_text_file", "path": full_path}
                        else:
                            req = {"type": "request_open_file", "path": full_path}
                            messagebox.showinfo(_("Thông báo"), _("Đã gửi yêu cầu mở file {ext} bằng ứng dụng mặc định trên máy bị điều khiển.").format(ext=ext), parent=top)
                        try:
                            open("C:\\Apps\\P2P\\agent.log", "a", encoding="utf-8").write(f"{ts} [Remote] Sending file read request: {req}\n")
                            send_event(req)
                        except Exception as ex:
                            messagebox.showerror(_("Lỗi"), _("Không thể gửi lệnh: {ex}").format(ex=ex), parent=top)
                elif action == "rename":
                    
                    new_name = inline_ask_string(top, _("Đổi tên"), _("Nhập tên mới cho '{name}':").format(name=name), initialvalue=name)
                    top.focus_force()
                    if new_name and new_name != name:
                        req = {"type": "request_rename_item", "old_path": full_path, "new_name": new_name}
                        send_event(req)
                elif action == "properties":
                    req = {"type": "request_get_properties", "path": full_path}
                    send_event(req)
                    return
        def show_remote_menu(event):
            remote_menu.delete(0, 'end')
            row = remote_tree.identify_row(event.y)
            if not row:
                remote_menu.add_command(label=_("Tạo thư mục mới"), command=lambda: remote_action("mkdir"))
                remote_menu.add_separator()
                remote_menu.add_command(label=_("Làm mới"), command=lambda: request_remote_dir(remote_entry.get()))
                remote_menu.post(event.x_root, event.y_root)
                return

            if row not in remote_tree.selection():
                remote_tree.selection_set(row)
            remote_tree.focus(row)

            vals = remote_tree.item(row, "values")
            is_dir = (len(vals) > 1 and vals[1] == _("Thư mục"))

            if not is_dir:
                remote_menu.add_command(label=_("Xem tệp"), command=lambda: remote_action("view"))
            remote_menu.add_command(label=_("Tạo thư mục mới"), command=lambda: remote_action("mkdir"))
            remote_menu.add_command(label=_("Đổi tên"), command=lambda: remote_action("rename"))
            remote_menu.add_separator()
            remote_menu.add_command(label=_("Xóa"), command=lambda: remote_action("delete"))
            remote_menu.add_separator()
            remote_menu.add_command(label=_("Thuộc tính"), command=lambda: remote_action("properties"))

            remote_menu.post(event.x_root, event.y_root)
        remote_tree.bind("<Button-3>", show_remote_menu)

        def select_all_remote(event):
            remote_tree.selection_set(remote_tree.get_children())
            return "break"
        remote_tree.bind("<Control-a>", select_all_remote)
        remote_tree.bind("<Control-A>", select_all_remote)

        def on_tree_keypress(event, tree):
            if not event.char or not event.char.isprintable():
                return
            char = event.char.lower()
            items = tree.get_children()
            if not items: return "break"

            start_idx = 0
            current_sel = tree.selection()
            if current_sel:
                try:
                    start_idx = items.index(current_sel[0]) + 1
                except ValueError:
                    start_idx = 0

            for idx in list(range(start_idx, len(items))) + list(range(0, start_idx)):
                item = items[idx]
                text = tree.item(item, 'text').lower()
                if text.startswith(char):
                    tree.selection_set(item)
                    tree.focus(item)
                    tree.see(item)
                    return "break"
            return "break"

        local_tree.bind("<KeyPress>", lambda e: on_tree_keypress(e, local_tree))
        remote_tree.bind("<KeyPress>", lambda e: on_tree_keypress(e, remote_tree))

        local_tree.bind("<F2>", lambda e: local_action("rename"))
        remote_tree.bind("<F2>", lambda e: remote_action("rename"))

        local_tree.bind("<F5>", lambda e: refresh_local())
        remote_tree.bind("<F5>", lambda e: request_remote_dir(remote_entry.get()))

        def tree_go_home(event, tree):
            items = tree.get_children()
            if items:
                tree.selection_set(items[0])
                tree.focus(items[0])
                tree.see(items[0])
            return "break"

        def tree_go_end(event, tree):
            items = tree.get_children()
            if items:
                tree.selection_set(items[-1])
                tree.focus(items[-1])
                tree.see(items[-1])
            return "break"

        def tree_page_up(event, tree):
            items = tree.get_children()
            if not items: return "break"
            sel = tree.selection()
            new_idx = max(0, items.index(sel[0]) - 15) if sel else 0
            tree.selection_set(items[new_idx])
            tree.focus(items[new_idx])
            tree.see(items[new_idx])
            return "break"

        def tree_page_down(event, tree):
            items = tree.get_children()
            if not items: return "break"
            sel = tree.selection()
            new_idx = min(len(items) - 1, items.index(sel[-1]) + 15) if sel else len(items) - 1
            tree.selection_set(items[new_idx])
            tree.focus(items[new_idx])
            tree.see(items[new_idx])
            return "break"

        for t in (local_tree, remote_tree):
            t.bind("<Home>", lambda e, tr=t: tree_go_home(e, tr))
            t.bind("<End>", lambda e, tr=t: tree_go_end(e, tr))
            t.bind("<Prior>", lambda e, tr=t: tree_page_up(e, tr))
            t.bind("<Next>", lambda e, tr=t: tree_page_down(e, tr))

        # --- Transfer Actions ---
        def get_dir_stats(path):
            total_size = 0
            file_count = 0
            folder_count = 0
            try:
                for root, dirs, files in os.walk(path):
                    folder_count += len(dirs)
                    file_count += len(files)
                    for f in files:
                        try:
                            total_size += os.path.getsize(os.path.join(root, f))
                        except:
                            pass
            except:
                pass
            return total_size, file_count, folder_count

        def resolve_conflicts(conflicts, parent, is_upload):
            results = {}
            overwrite_all = False

            for c in conflicts:
                if overwrite_all:
                    results[c['name']] = 'overwrite'
                    continue

                dlg = tk.Frame(parent, bg="#FFFFFF", highlightbackground="#0078D7", highlightthickness=2)
                dlg.place(relx=0.5, rely=0.5, anchor="center", width=650, height=380)
                dlg.lift()
                dlg.focus_force()

                try:
                    dlg.grab_set()
                except: pass

                title_bar = tk.Frame(dlg, bg="#F3F3F3", height=30)
                title_bar.pack(fill=tk.X, side=tk.TOP)
                title_bar.pack_propagate(False)
                tk.Label(title_bar, text=_("Xác nhận"), bg="#F3F3F3", fg="#333333", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=10, pady=5)

                frame = tk.Frame(dlg, bg="white")
                frame.pack(fill="both", expand=True)

                # Pack btn_frame first at the bottom so it never gets clipped
                btn_frame = tk.Frame(frame, bg="white")
                btn_frame.pack(fill="x", side="bottom", pady=20, padx=20)

                item_type = _("Thư mục") if c.get('src_is_dir') else _("Tập tin")
                lbl_title = tk.Label(frame, text=_("{item_type} với tên \"{item_name}\" đã tồn tại.").format(item_type=item_type, item_name=c['name']), font=("Segoe UI", 11, "bold"), bg="white", anchor="w")
                lbl_title.pack(fill="x", padx=20, pady=(20, 10))

                try:
                    src_sz_val = int(float(c.get('src_size', 0)))
                except:
                    src_sz_val = 0
                try:
                    dst_sz_val = int(float(c.get('dst_size', 0)))
                except:
                    dst_sz_val = 0

                src_sz = format_size(src_sz_val)
                dst_sz = format_size(dst_sz_val)

                src_path = c.get('src_path', _('Không rõ'))
                dst_path = c.get('dst_path', _('Không rõ'))
                src_mtime = c.get('src_mtime', _('Không xác định'))
                dst_mtime = c.get('dst_mtime', _('Không xác định'))

                if is_upload:
                    src_title = _("Nguồn (Máy bạn):")
                    dst_title = _("Đích (Máy từ xa):")
                else:
                    src_title = _("Nguồn (Máy từ xa):")
                    dst_title = _("Đích (Máy bạn):")

                src_fc = c.get('src_file_count')
                if src_fc is not None:
                    src_extra = _("\n- Chứa: {fc} tệp, {dc} thư mục").format(fc=src_fc, dc=c.get('src_folder_count', 0))
                elif c.get('src_is_dir'):
                    src_extra = _("\n- Chứa: Không rõ (Remote)")
                else:
                    src_extra = ""

                dst_fc = c.get('dst_file_count')
                if dst_fc is not None:
                    dst_extra = _("\n- Chứa: {fc} tệp, {dc} thư mục").format(fc=dst_fc, dc=c.get('dst_folder_count', 0))
                elif c.get('dst_is_dir'):
                    dst_extra = _("\n- Chứa: Không rõ (Remote)")
                else:
                    dst_extra = ""

                src_disp = _("""{src_title}
- Vị trí: {src_path}
- Dung lượng: {src_sz}{src_extra}
- Ngày sửa đổi: {src_mtime}""").format(src_title=src_title, src_path=src_path, src_sz=src_sz, src_extra=src_extra, src_mtime=src_mtime)
                dst_disp = _("""{dst_title}
- Vị trí: {dst_path}
- Dung lượng: {dst_sz}{dst_extra}
- Ngày sửa đổi: {dst_mtime}""").format(dst_title=dst_title, dst_path=dst_path, dst_sz=dst_sz, dst_extra=dst_extra, dst_mtime=dst_mtime)

                tk.Label(frame, text=src_disp, font=("Segoe UI", 10), bg="white", anchor="w", fg="#333333", justify="left").pack(fill="x", padx=20, pady=2)
                tk.Label(frame, text=dst_disp, font=("Segoe UI", 10), bg="white", anchor="w", fg="#333333", justify="left").pack(fill="x", padx=20, pady=(2, 10))
                tk.Label(frame, text=_("Bạn muốn làm gì?"), font=("Segoe UI", 10, "bold"), bg="white", anchor="w").pack(fill="x", padx=20, pady=(5, 15))

                decision = ["cancel"]
                def make_decision(d):
                    decision[0] = d
                    try: dlg.grab_release()
                    except: pass
                    dlg.destroy()

                btn_cancel = tk.Button(btn_frame, text=_("Hủy"), font=("Segoe UI", 10, "bold"), bg="#e0e0e0", fg="black", width=8, relief="raised", borderwidth=2, command=lambda: make_decision("cancel"))
                btn_cancel.pack(side="right", padx=5)

                btn_skip = tk.Button(btn_frame, text=_("Bỏ qua"), font=("Segoe UI", 10), bg="#e0e0e0", fg="black", width=10, relief="raised", borderwidth=2, command=lambda: make_decision("skip"))
                btn_skip.pack(side="right", padx=10)

                btn_ow = tk.Button(btn_frame, text=_("Ghi đè"), font=("Segoe UI", 10), bg="#e0e0e0", fg="black", width=10, relief="raised", borderwidth=2, command=lambda: make_decision("overwrite"))
                btn_ow.pack(side="right", padx=10)

                btn_ow_all = tk.Button(btn_frame, text=_("Ghi đè toàn bộ"), font=("Segoe UI", 10, "bold"), bg="#e0e0e0", fg="black", width=15, relief="raised", borderwidth=2, command=lambda: make_decision("overwrite_all"))
                btn_ow_all.pack(side="right", padx=10)

                parent.wait_window(dlg)
                if decision[0] == "cancel": return None
                elif decision[0] == "overwrite_all":
                    overwrite_all = True
                    results[c['name']] = 'overwrite'
                else: results[c['name']] = decision[0]

            return results

        def write_transfer_log(direction, file_name, file_size, dest_dir):
            try:
                import datetime
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_line = f"[{now}] {direction} | File: {file_name} | Size: {format_size(file_size)} | To: {dest_dir}\n"
                with open("transfer.log", "a", encoding="utf-8") as lf:
                    lf.write(log_line)
            except Exception as e:
                print("Log error:", e)

        def do_upload():
            sel = local_tree.selection()
            if not sel: return

            target_dir = remote_entry.get()

            # Check conflicts
            remote_items = {}
            for child in remote_tree.get_children():
                txt = remote_tree.item(child, "text")
                vals = remote_tree.item(child, "values")
                is_dir = True if len(vals) > 1 and vals[1] == _("Thư mục") else False
                sz = vals[2] if len(vals) > 2 else 0
                remote_items[txt] = {"is_dir": is_dir, "size": sz}

            conflicts = []
            for s in sel:
                name = local_tree.item(s, "text")
                if name in remote_items:
                    fpath = os.path.join(local_entry.get(), name)
                    is_dir = os.path.isdir(fpath)
                    
                    src_file_count = None
                    src_folder_count = None
                    if is_dir:
                        sz, src_file_count, src_folder_count = get_dir_stats(fpath)
                    else:
                        sz = os.path.getsize(fpath) if os.path.isfile(fpath) else 0

                    try:
                        import datetime
                        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M:%S')
                    except: mtime = _("Không xác định")
                    dpath = remote_entry.get()
                    if not dpath.endswith('/'): dpath += '/'
                    dpath += name
                    conflicts.append({
                        "name": name,
                        "src_size": sz, "src_is_dir": is_dir, "src_path": fpath, "src_mtime": mtime,
                        "src_file_count": src_file_count, "src_folder_count": src_folder_count,
                        "dst_size": remote_items[name]["size"], "dst_is_dir": remote_items[name]["is_dir"],
                        "dst_path": dpath, "dst_mtime": _("Không xác định (Remote)"),
                        "dst_file_count": None, "dst_folder_count": None
                    })

            if conflicts:
                decisions = resolve_conflicts(conflicts, top, is_upload=True)
                if decisions is None: return
            else:
                decisions = {}

            items_to_upload = [] # List of (local_path, remote_name, size)
            total_size = 0

            for s in sel:
                item = local_tree.item(s)
                name = item['text']

                if name in decisions and decisions[name] == 'skip':
                    continue
                fpath = os.path.join(local_entry.get(), name)

                if os.path.isfile(fpath):
                    sz = os.path.getsize(fpath)
                    items_to_upload.append((fpath, name, sz, False))
                    total_size += sz
                elif os.path.isdir(fpath):
                    # Recursive walk for folders
                    base_name = name
                    for root, dirs, files in os.walk(fpath):
                        rel_path = os.path.relpath(root, os.path.dirname(fpath))
                        if not dirs and not files:
                            remote_name = rel_path.replace('\\', '/')
                            items_to_upload.append((None, remote_name, 0, True))
                        for d in dirs:
                            remote_name = os.path.join(rel_path, d).replace('\\', '/')
                        for f in files:
                            full_file = os.path.join(root, f)
                            if os.path.isfile(full_file):
                                sz = os.path.getsize(full_file)
                                remote_name = os.path.join(rel_path, f).replace('\\', '/')
                                items_to_upload.append((full_file, remote_name, sz, False))
                                total_size += sz

            if not items_to_upload: return

            display_name = items_to_upload[0][1]
            if len(items_to_upload) > 1:
                display_name += _(" và {count} mục khác").format(count=len(items_to_upload)-1)

            class UploadState:
                is_cancelled = False
            state = UploadState()

            dialog = ProgressDialog(top, "Chuyển qua", display_name, total_size, on_cancel=lambda: setattr(state, 'is_cancelled', True))
            dialog.update_progress(0)

            def upload_batch_thread(items, t_dir, dlg, st):
                try:
                    sent_total = 0
                    for path, n, sz, is_empty_dir in items:
                        if st.is_cancelled: break

                        if is_empty_dir:
                            final_target_dir = t_dir
                            if not final_target_dir.endswith("/"): final_target_dir += "/"

                            parts = n.strip('/').rsplit('/', 1)
                            if len(parts) == 2:
                                parent_path = final_target_dir + parts[0]
                                folder_name = parts[1]
                            else:
                                parent_path = final_target_dir
                                if parent_path.endswith("/"): parent_path = parent_path[:-1]
                                folder_name = parts[0]

                            send_event({"type": "request_create_folder", "parent_path": parent_path, "folder_name": folder_name})
                            time.sleep(0.1)
                            continue

                        write_transfer_log("UPLOAD", n, sz, t_dir)

                        parts = n.split('/')
                        file_name = parts[-1]
                        sub_dir = "/".join(parts[:-1])

                        final_target_dir = t_dir
                        if not final_target_dir.endswith("/"): final_target_dir += "/"
                        if sub_dir:
                            final_target_dir += sub_dir

                        send_event({"type": "file_start", "name": file_name, "size": sz, "target_dir": final_target_dir})
                        time.sleep(0.5)

                        with open(path, "rb") as f:
                            while True:
                                if st.is_cancelled: break
                                chunk = f.read(65536)
                                if not chunk: break
                                send_event({
                                    "type": "file_chunk",
                                    "name": file_name,
                                    "data": base64.b64encode(chunk).decode('utf-8')
                                })
                                sent_total += len(chunk)
                                dlg.update_progress(sent_total)
                                time.sleep(0.01)

                        send_event({"type": "file_end"})
                        time.sleep(0.1) 

                    if not st.is_cancelled:
                        dlg.safe_destroy()

                    def delayed_refresh():
                        time.sleep(2)
                        top.after(0, lambda: request_remote_dir(t_dir))
                    threading.Thread(target=delayed_refresh, daemon=True).start()
                except Exception as e:
                    print(f"Upload error: {e}")
                    dlg.safe_destroy()

            threading.Thread(target=upload_batch_thread, args=(items_to_upload, target_dir, dialog, state), daemon=True).start()

        def do_download():
            sel = remote_tree.selection()
            if not sel: return

            target_dir = os.path.abspath(local_entry.get())

            # Check conflicts
            conflicts = []
            for s in sel:
                name = remote_tree.item(s, "text")
                vals = remote_tree.item(s, "values")
                src_is_dir = True if len(vals) > 1 and vals[1] == _("Thư mục") else False
                src_sz = vals[2] if len(vals) > 2 else 0

                fpath = os.path.join(target_dir, name)
                if os.path.exists(fpath):
                    dst_is_dir = os.path.isdir(fpath)
                    dst_file_count = None
                    dst_folder_count = None
                    if dst_is_dir:
                        dst_sz, dst_file_count, dst_folder_count = get_dir_stats(fpath)
                    else:
                        dst_sz = os.path.getsize(fpath) if not dst_is_dir else 0
                    try:
                        import datetime
                        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M:%S')
                    except: mtime = _("Không xác định")
                    spath = remote_entry.get()
                    sep = "/" if "/" in spath else ("\\" if "\\" in spath else "/")
                    if not spath.endswith(sep): spath += sep
                    spath += name
                    conflicts.append({
                        "name": name,
                        "src_size": src_sz, "src_is_dir": src_is_dir, "src_path": spath, "src_mtime": _("Không xác định (Remote)"),
                        "src_file_count": None, "src_folder_count": None,
                        "dst_size": dst_sz, "dst_is_dir": dst_is_dir, "dst_path": fpath, "dst_mtime": mtime,
                        "dst_file_count": dst_file_count, "dst_folder_count": dst_folder_count
                    })

            if conflicts:
                decisions = resolve_conflicts(conflicts, top, is_upload=False)
                if decisions is None: return
            else:
                decisions = {}

            try:
                from core.clipboard_agent import clipboard_sync_manager as cm
            except Exception:
                cm = None

            total_size = 0
            files_to_download = []
            display_names = []

            for s in sel:
                item = remote_tree.item(s)
                name = item['text']

                if name in decisions and decisions[name] == 'skip':
                    continue
                vals = item.get('values', [])

                src_is_dir = True if len(vals) > 1 and vals[1] == _("Thư mục") else False
                if src_is_dir:
                    os.makedirs(os.path.join(target_dir, name), exist_ok=True)

                p = remote_entry.get()
                sep = "/" if "/" in p else ("\\" if "\\" in p else "/")
                if not p.endswith(sep): p += sep
                full_remote = p + name

                size = vals[2] if len(vals) > 2 else 0
                total_size += size

                files_to_download.append(full_remote)
                display_names.append(name)

            if not files_to_download: return

            if cm:
                cm.target_save_dir = target_dir
                cm.batch_total_size = total_size
                cm.batch_received = 0
                cm.active_batch = True
                cm._receive_cancelled = False

                display_name = display_names[0]
                if len(display_names) > 1:
                    display_name += _(" và {count} mục khác").format(count=len(display_names)-1)

                def _cancel():
                    cm.cancel_active_transfer(remote_triggered=False)

                dialog = ProgressDialog(top, "Nhận về", display_name, total_size, on_cancel=_cancel)
                dialog.update_progress(0)
                cm.active_dialog = dialog

            write_transfer_log("DOWNLOAD", display_names[0] + (" (batch)" if len(display_names) > 1 else ""), total_size, target_dir)
            req = {"type": "request_download_batch", "paths": files_to_download, "target_dir_local": target_dir}
            send_event(req)

        btn_upload.config(command=do_upload)
        btn_download.config(command=do_download)

        def on_close():
            globals()['fm_is_open'] = False
            try: top.withdraw()
            except: pass

        top.protocol("WM_DELETE_WINDOW", on_close)

        # init
        refresh_local()
        request_remote_dir(remote_entry.get())

        top.focus_force()
        local_entry.focus()
        top.mainloop()
    except Exception as ex:
        globals()['fm_is_open'] = False
        import traceback
        err = traceback.format_exc()
        try:
            import sys
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, err, _("Lỗi File Manager"), 0x10)
            else:
                messagebox.showerror(_("Lỗi File Manager"), err)
        except: pass

