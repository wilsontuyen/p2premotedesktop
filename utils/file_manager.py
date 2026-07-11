import os
import time
import base64
import threading
import pygame
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from gui.components import ProgressDialog

def open_transfer_window(computer_name, is_android, send_event):
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
        import threading, os, time, base64

        top = tk.Tk()
        globals()['fm_top'] = top
        top.attributes('-alpha', 0.0) # Ẩn đi để tránh nháy khi tạo

        host_title = f" - {computer_name}" if computer_name else ""
        top.title(f"P2P Remote Desktop - Trình Quản Lý Tệp (File Manager){host_title}")

        hwnd = pygame.display.get_wm_info().get("window")
        if hwnd:
            import ctypes
            from ctypes import wintypes
            rect = wintypes.RECT()
            ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(rect))
            py_w = rect.right - rect.left
            py_h = rect.bottom - rect.top

            # Try to get screen coordinates of the Pygame window
            pt = wintypes.POINT(0, 0)
            ctypes.windll.user32.ClientToScreen(hwnd, ctypes.byref(pt))

            if host_w >= 1920 and host_h >= 1080:
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
                x = max(0, pt.x + (py_w - 900) // 2)
                y = max(0, pt.y + (py_h - 600) // 2)
                top.geometry(f"900x600+{x}+{y}")
        else:
            top.geometry("900x600")

        top.attributes('-topmost', True)
        top.attributes('-alpha', 1.0) # Hiện lại sau khi set geometry
        top.configure(bg="#E5E5E5")

        left_frame = tk.Frame(top, bg="#E5E5E5")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        mid_frame = tk.Frame(top, width=60, bg="#E5E5E5")
        mid_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

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
            else: return f"{s/(1024*1024):.1f} MB"

        def refresh_local():
            for item in local_tree.get_children():
                local_tree.delete(item)
            try:
                path = local_entry.get()
                if path == "This PC":
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
                parent = "This PC"

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
        local_tree.bind("<Double-1>", local_double_click)
        local_tree.bind("<BackSpace>", lambda e: go_up_local())

        local_menu = tk.Menu(top, tearoff=0)
        def local_action(action):
            try:
                current_dir = local_entry.get()
                sel = local_tree.selection()
                if action == "mkdir":
                    from tkinter import simpledialog
                    new_name = simpledialog.askstring("Thư mục mới", "Nhập tên thư mục mới:", parent=top)
                    top.focus_force()
                    if new_name:
                        try:
                            folder_path = os.path.join(current_dir, new_name)
                            if os.path.exists(folder_path):
                                messagebox.showinfo(_("Lỗi"), f'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"', parent=top)
                            else:
                                os.makedirs(folder_path, exist_ok=True)
                                refresh_local()
                        except Exception as e:
                            with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f: f.write(f"Error mkdir: {str(e)}\n")
                    return
                if not sel: return

                if action == "delete":
                    if len(sel) == 1:
                        msg = f"Bạn có chắc muốn xóa '{local_tree.item(sel[0])['text']}' không?"
                    else:
                        msg = f"Bạn có chắc muốn xóa {len(sel)} mục đã chọn không?"
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
                                messagebox.showerror(_("Lỗi"), f"Lỗi xóa {name}: {e}", parent=top)
                        refresh_local()
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
                            messagebox.showwarning(_("Cảnh báo"), f"Không thể xem thư mục '{name}' bằng Notepad!", parent=top)
                        else:
                            text_exts = {'.txt', '.log', '.md', '.py', '.json', '.xml', '.ini', '.cfg', '.csv', '.html', '.css', '.js', '.kt', '.java', '.c', '.cpp', '.h', '.bat', '.sh', ''}
                            _, ext = os.path.splitext(name.lower())
                            if ext in text_exts:
                                try:
                                    with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                        f.write(f"{ts} [Local] Opening {full_path}...\n")
                                    with open(full_path, "r", encoding="utf-8") as f:
                                        file_content = f.read(5 * 1024 * 1024)
                                    with open("C:\\Apps\\P2P\\debug_view.txt", "a", encoding="utf-8") as f:
                                        f.write(f"{ts} [Local] Read successful, creating window...\n")
                                    np_win = tk.Toplevel(top)
                                    np_win.title(f"Soạn thảo (Local) - {name}")
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
                                                messagebox.showerror(_("Lỗi"), f"Không thể lưu: {e}", parent=win)
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
                        from tkinter import simpledialog
                        new_name = simpledialog.askstring("Đổi tên", f"Nhập tên mới cho '{name}':", initialvalue=name, parent=top)
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
                local_menu.add_command(label="Xem file", command=lambda: local_action("view"))
            local_menu.add_command(label=_("Tạo thư mục mới"), command=lambda: local_action("mkdir"))
            local_menu.add_command(label=_("Đổi tên"), command=lambda: local_action("rename"))
            local_menu.add_separator()
            local_menu.add_command(label=_("Xóa"), command=lambda: local_action("delete"))

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
        remote_entry.insert(0, "/sdcard/" if is_android else "C:\\")

        def request_remote_dir(path):
            # send list_dir request
            req = {"type": "request_list_dir", "path": path}
            send_event(req)

        def on_remote_dir_result(event):
            evt_type = event.get("type", "list_dir_result")
            if evt_type == "list_dir_result":
                if event.get("path") != remote_entry.get():
                    return
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
                        np_win.title(f"Soạn thảo (Remote) - {name}")
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
                        messagebox.showerror(_("Lỗi Code"), f"Lỗi tạo Notepad: {ex}", parent=top)
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
        globals()['file_manager_callback'] = lambda e: fm_event_queue.put(e)

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
        remote_tree.bind("<Double-1>", remote_double_click)
        remote_tree.bind("<BackSpace>", lambda e: go_up_remote())

        remote_menu = tk.Menu(top, tearoff=0)
        def remote_action(action):
            current_dir = remote_entry.get()
            sep = "/" if "/" in current_dir else ("\\" if "\\" in current_dir else "/")
            if not current_dir.endswith(sep): current_dir += sep
            sel = remote_tree.selection()
            if action == "mkdir":
                from tkinter import simpledialog
                new_name = simpledialog.askstring("Thư mục mới", "Nhập tên thư mục mới:", parent=top)
                top.focus_force()
                if new_name:
                    exists = False
                    for child in remote_tree.get_children():
                        if remote_tree.item(child, "text") == new_name:
                            exists = True
                            break
                    if exists:
                        messagebox.showinfo(_("Lỗi"), f'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"', parent=top)
                    else:
                        req = {"type": "request_create_folder", "parent_path": current_dir, "folder_name": new_name}
                        send_event(req)
                return
            if not sel: return

            if action == "delete":
                if len(sel) == 1:
                    msg = f"Bạn có chắc muốn xóa '{remote_tree.item(sel[0])['text']}' khỏi máy điều khiển không?"
                else:
                    msg = f"Bạn có chắc muốn xóa {len(sel)} mục đã chọn khỏi máy điều khiển không?"
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
                        messagebox.showwarning(_("Cảnh báo"), f"Không thể xem thư mục '{name}' bằng Notepad!", parent=top)
                    else:
                        text_exts = {'.txt', '.log', '.md', '.py', '.json', '.xml', '.ini', '.cfg', '.csv', '.html', '.css', '.js', '.kt', '.java', '.c', '.cpp', '.h', '.bat', '.sh', ''}
                        _, ext = os.path.splitext(name.lower())
                        if ext in text_exts:
                            req = {"type": "request_read_text_file", "path": full_path}
                        else:
                            req = {"type": "request_open_file", "path": full_path}
                            messagebox.showinfo(_("Thông báo"), f"Đã gửi yêu cầu mở file {ext} bằng ứng dụng mặc định trên máy bị điều khiển.", parent=top)
                        try:
                            open("C:\\Apps\\P2P\\agent.log", "a", encoding="utf-8").write(f"{ts} [Remote] Sending file read request: {req}\n")
                            send_event(req)
                        except Exception as ex:
                            messagebox.showerror(_("Lỗi"), f"Không thể gửi lệnh: {ex}", parent=top)
                elif action == "rename":
                    from tkinter import simpledialog
                    new_name = simpledialog.askstring("Đổi tên", f"Nhập tên mới cho '{name}':", initialvalue=name, parent=top)
                    top.focus_force()
                    if new_name and new_name != name:
                        req = {"type": "request_rename_item", "old_path": full_path, "new_name": new_name}
                        send_event(req)
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
                remote_menu.add_command(label="Xem file", command=lambda: remote_action("view"))
            remote_menu.add_command(label=_("Tạo thư mục mới"), command=lambda: remote_action("mkdir"))
            remote_menu.add_command(label=_("Đổi tên"), command=lambda: remote_action("rename"))
            remote_menu.add_separator()
            remote_menu.add_command(label=_("Xóa"), command=lambda: remote_action("delete"))

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
        local_tree.bind("<BackSpace>", lambda e: "break" if go_up_local() or True else "")
        remote_tree.bind("<BackSpace>", lambda e: "break" if go_up_remote() or True else "")

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
                lbl_title = tk.Label(frame, text=f"{item_type} với tên \"{c['name']}\" " + _("đã tồn tại."), font=("Segoe UI", 11, "bold"), bg="white", anchor="w")
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

                src_disp = f"{src_title}\n- Thư mục: {src_path}\n- Dung lượng: {src_sz}\n- Ngày sửa đổi: {src_mtime}"
                dst_disp = f"{dst_title}\n- Thư mục: {dst_path}\n- Dung lượng: {dst_sz}\n- Ngày sửa đổi: {dst_mtime}"

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
                    sz = os.path.getsize(fpath) if os.path.isfile(fpath) else 0
                    is_dir = os.path.isdir(fpath)
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
                        "dst_size": remote_items[name]["size"], "dst_is_dir": remote_items[name]["is_dir"],
                        "dst_path": dpath, "dst_mtime": _("Không xác định (Remote)")
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
                display_name += f" và {len(items_to_upload)-1} mục khác"

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

            target_dir = local_entry.get()

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
                        "dst_size": dst_sz, "dst_is_dir": dst_is_dir, "dst_path": fpath, "dst_mtime": mtime
                    })

            if conflicts:
                decisions = resolve_conflicts(conflicts, top, is_upload=False)
                if decisions is None: return
            else:
                decisions = {}

            cm = globals().get('clipboard_sync_manager')

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
                    display_name += f" và {len(display_names)-1} mục khác"

                def _cancel():
                    cm.cancel_active_transfer(remote_triggered=False)

                dialog = ProgressDialog(top, "Nhận về", display_name, total_size, on_cancel=_cancel)
                dialog.update_progress(0)
                cm.active_dialog = dialog

            write_transfer_log("DOWNLOAD", display_names[0] + (" (batch)" if len(display_names) > 1 else ""), total_size, target_dir)
            req = {"type": "request_download_batch", "paths": files_to_download, "target_dir_local": target_dir}
            send_event(req)

        tk.Button(mid_frame, text="Chuyển qua\n>>", font=("Segoe UI", 10, "bold"), bg="#2196F3", fg="white", width=10, command=do_upload).pack(pady=(100, 10))
        tk.Button(mid_frame, text="Nhận về\n<<", font=("Segoe UI", 10, "bold"), bg="#4CAF50", fg="white", width=10, command=do_download).pack(pady=10)

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
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, err, _("Lỗi File Manager"), 0x10)
        except: pass

