import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

start_marker2 = "                                            if not sel: return\n                                            item = remote_tree.item(sel[0])"
end_marker2 = "                                        remote_menu.add_command(label=\"Xem file\""

new_remote_action = """                                            if not sel: return
                                            
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
                                                    open("C:\\\\Apps\\\\P2P\\\\agent.log", "a", encoding="utf-8").write(f"{ts} [Remote] Action 'view' on '{name}', is_dir={is_dir}\\n")
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
"""

idx3 = content.find(start_marker2)
idx4 = content.find(end_marker2)
if idx3 != -1 and idx4 != -1:
    content = content[:idx3] + new_remote_action + content[idx4:]
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Applied remote_action successfully")
else:
    print("Could not find remote_action markers!")

