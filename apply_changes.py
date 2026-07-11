import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace local_action
start_marker1 = "                                                if not sel: return\n                                                item = local_tree.item(sel[0])"
end_marker1 = "                                        local_menu.add_command(label=\"Xem file\""

new_local_action = """                                                if not sel: return
                                                
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
                                                        with open("C:\\\\Apps\\\\P2P\\\\debug_view.txt", "a", encoding="utf-8") as f:
                                                            f.write(f"{ts} [Local] Action 'view' started for '{name}', is_dir={is_dir}\\n")
                                                        if is_dir:
                                                            messagebox.showwarning(_("Cảnh báo"), f"Không thể xem thư mục '{name}' bằng Notepad!", parent=top)
                                                        else:
                                                            text_exts = {'.txt', '.log', '.md', '.py', '.json', '.xml', '.ini', '.cfg', '.csv', '.html', '.css', '.js', '.kt', '.java', '.c', '.cpp', '.h', '.bat', '.sh', ''}
                                                            _, ext = os.path.splitext(name.lower())
                                                            if ext in text_exts:
                                                                try:
                                                                    with open("C:\\\\Apps\\\\P2P\\\\debug_view.txt", "a", encoding="utf-8") as f:
                                                                        f.write(f"{ts} [Local] Opening {full_path}...\\n")
                                                                    with open(full_path, "r", encoding="utf-8") as f:
                                                                        file_content = f.read(5 * 1024 * 1024)
                                                                    with open("C:\\\\Apps\\\\P2P\\\\debug_view.txt", "a", encoding="utf-8") as f:
                                                                        f.write(f"{ts} [Local] Read successful, creating window...\\n")
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
                                                                    with open("C:\\\\Apps\\\\P2P\\\\debug_view.txt", "a", encoding="utf-8") as f:
                                                                        f.write(f"{ts} [Local] Window created successfully.\\n")
                                                                except Exception as ex:
                                                                    import traceback
                                                                    with open("C:\\\\Apps\\\\P2P\\\\debug_view.txt", "a", encoding="utf-8") as f:
                                                                        f.write(f"{ts} [Local] CRASH during view: {traceback.format_exc()}\\n")
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
                                                with open("C:\\\\Apps\\\\P2P\\\\debug_view.txt", "a", encoding="utf-8") as f:
                                                    f.write(f"{ts} [Local] OUTER CRASH: {traceback.format_exc()}\\n")
                                                messagebox.showerror(_("Lỗi"), str(outer_e), parent=top)
"""
idx1 = content.find(start_marker1)
idx2 = content.find(end_marker1)
if idx1 != -1 and idx2 != -1:
    content = content[:idx1] + new_local_action + content[idx2:]
else:
    print("Could not find local_action markers!")

# Replace show_local_menu
start_marker3 = """                                        def show_local_menu(event):
                                            row = local_tree.identify_row(event.y)
                                            if row:
                                                local_tree.selection_set(row)"""
end_marker3 = """                                                try:
                                                    local_menu.tk_popup(event.x_root, event.y_root)"""

new_show_local = """                                        def show_local_menu(event):
                                            row = local_tree.identify_row(event.y)
                                            if row:
                                                if row not in local_tree.selection():
                                                    local_tree.selection_set(row)
"""
idx5 = content.find(start_marker3)
idx6 = content.find(end_marker3)
if idx5 != -1 and idx6 != -1:
    content = content[:idx5] + new_show_local + content[idx6:]
else:
    print("Could not find show_local_menu markers!")

# Replace remote_action
start_marker2 = "                                                if not sel: return\n                                                item = remote_tree.item(sel[0])"
end_marker2 = "                                        remote_menu.add_command(label=\"Xem file\""

new_remote_action = """                                                if not sel: return
                                                
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
                                                            full_path = current_dir + name if current_dir.endswith('/') or current_dir.endswith('\\\\') else current_dir + '/' + name
                                                            req = {"type": "request_delete_item", "path": full_path}
                                                            send_event(req)
                                                    return
                                                    
                                                for s in sel:
                                                    item = remote_tree.item(s)
                                                    name = item['text']
                                                    full_path = current_dir + name if current_dir.endswith('/') or current_dir.endswith('\\\\') else current_dir + '/' + name
                                                    vals = item.get('values', [])
                                                    is_dir = (len(vals) > 1 and vals[1] == _("Thư mục"))
                                                    
                                                    if action == "view":
                                                        from datetime import datetime
                                                        ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
                                                        with open("C:\\\\Apps\\\\P2P\\\\agent.log", "a", encoding="utf-8") as f:
                                                            f.write(f"{ts} [Remote] Action 'view' started for '{name}', is_dir={is_dir}\\n")
                                                        if is_dir:
                                                            messagebox.showwarning(_("Cảnh báo"), f"Không thể xem thư mục '{name}' bằng Notepad!", parent=top)
                                                            continue
                                                        text_exts = {'.txt', '.log', '.md', '.py', '.json', '.xml', '.ini', '.cfg', '.csv', '.html', '.css', '.js', '.kt', '.java', '.c', '.cpp', '.h', '.bat', '.sh', ''}
                                                        _, ext = os.path.splitext(name.lower())
                                                        if ext in text_exts:
                                                            req = {"type": "request_read_text_file", "path": full_path}
                                                        else:
                                                            req = {"type": "request_open_file", "path": full_path}
                                                            messagebox.showinfo(_("Thông báo"), f"Đã gửi yêu cầu mở file {ext} bằng ứng dụng mặc định trên máy bị điều khiển.", parent=top)
                                                        try:
                                                            open("C:\\\\Apps\\\\P2P\\\\agent.log", "a", encoding="utf-8").write(f"{ts} [Remote] Sending file read request: {req}\\n")
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
                                            except Exception as outer_e:
                                                import traceback
                                                from datetime import datetime
                                                ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
                                                with open("C:\\\\Apps\\\\P2P\\\\agent.log", "a", encoding="utf-8") as f:
                                                    f.write(f"{ts} [Remote] OUTER CRASH: {traceback.format_exc()}\\n")
                                                messagebox.showerror(_("Lỗi"), str(outer_e), parent=top)
"""
idx3 = content.find(start_marker2)
idx4 = content.find(end_marker2)
if idx3 != -1 and idx4 != -1:
    content = content[:idx3] + new_remote_action + content[idx4:]
else:
    print("Could not find remote_action markers!")

# Add Ctrl+A bindings
bind_marker = "local_tree.bind(\"<Button-3>\", show_local_menu)"
new_bindings_local = """local_tree.bind("<Button-3>", show_local_menu)
                                        
                                        def select_all_local(event):
                                            local_tree.selection_set(local_tree.get_children())
                                            return "break"
                                        local_tree.bind("<Control-a>", select_all_local)
                                        local_tree.bind("<Control-A>", select_all_local)"""
content = content.replace(bind_marker, new_bindings_local)

bind_marker2 = "remote_tree.bind(\"<Button-3>\", show_remote_menu)"
new_bindings_remote = """remote_tree.bind("<Button-3>", show_remote_menu)
                                        
                                        def select_all_remote(event):
                                            remote_tree.selection_set(remote_tree.get_children())
                                            return "break"
                                        remote_tree.bind("<Control-a>", select_all_remote)
                                        remote_tree.bind("<Control-A>", select_all_remote)"""
content = content.replace(bind_marker2, new_bindings_remote)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Applied successfully")
