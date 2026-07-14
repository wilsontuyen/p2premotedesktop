import re

with open('utils/file_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    # Top title
    (r'top\.title\(f"P2P Remote Desktop - Trình Quản Lý Tệp \(File Manager\)\{host_title\}"\)',
     r'top.title(_("P2P Remote Desktop - Trình Quản Lý Tệp (File Manager){host_title}").format(host_title=host_title))'),
    
    # Disp strings
    (r'src_disp = f"\{src_title\}\\n- Thư mục: \{src_path\}\\n- Dung lượng: \{src_sz\}\\n- Ngày sửa đổi: \{src_mtime\}"',
     r'src_disp = _("{src_title}\n- Thư mục: {src_path}\n- Dung lượng: {src_sz}\n- Ngày sửa đổi: {src_mtime}").format(src_title=src_title, src_path=src_path, src_sz=src_sz, src_mtime=src_mtime)'),
    (r'dst_disp = f"\{dst_title\}\\n- Thư mục: \{dst_path\}\\n- Dung lượng: \{dst_sz\}\\n- Ngày sửa đổi: \{dst_mtime\}"',
     r'dst_disp = _("{dst_title}\n- Thư mục: {dst_path}\n- Dung lượng: {dst_sz}\n- Ngày sửa đổi: {dst_mtime}").format(dst_title=dst_title, dst_path=dst_path, dst_sz=dst_sz, dst_mtime=dst_mtime)'),
     
    # More strings
    (r'display_name \+= f" và \{len\(items_to_upload\)-1\} mục khác"',
     r'display_name += _(" và {count} mục khác").format(count=len(items_to_upload)-1)'),
    (r'display_name \+= f" và \{len\(display_names\)-1\} mục khác"',
     r'display_name += _(" và {count} mục khác").format(count=len(display_names)-1)'),
    
    # Local deletion messages
    (r'msg = f"Bạn có chắc muốn xóa \'\{local_tree\.item\(sel\[0\]\)\[\'text\'\]\}\' không\?"',
     r'msg = _("Bạn có chắc muốn xóa \'{item_name}\' không?").format(item_name=local_tree.item(sel[0])[\'text\'])'),
    (r'msg = f"Bạn có chắc muốn xóa \{len\(sel\)\} mục đã chọn không\?"',
     r'msg = _("Bạn có chắc muốn xóa {count} mục đã chọn không?").format(count=len(sel))'),
     
    # Remote deletion messages
    (r'msg = f"Bạn có chắc muốn xóa \'\{remote_tree\.item\(sel\[0\]\)\[\'text\'\]\}\' khỏi máy điều khiển không\?"',
     r'msg = _("Bạn có chắc muốn xóa \'{item_name}\' khỏi máy điều khiển không?").format(item_name=remote_tree.item(sel[0])[\'text\'])'),
    (r'msg = f"Bạn có chắc muốn xóa \{len\(sel\)\} mục đã chọn khỏi máy điều khiển không\?"',
     r'msg = _("Bạn có chắc muốn xóa {count} mục đã chọn khỏi máy điều khiển không?").format(count=len(sel))'),
    
    # Mkdir / Rename prompts
    (r'new_name = simpledialog\.askstring\("Thư mục mới", "Nhập tên thư mục mới:", parent=top\)',
     r'new_name = simpledialog.askstring(_("Thư mục mới"), _("Nhập tên thư mục mới:"), parent=top)'),
    (r'new_name = simpledialog\.askstring\("Đổi tên", f"Nhập tên mới cho \'\{name\}\':", initialvalue=name, parent=top\)',
     r'new_name = simpledialog.askstring(_("Đổi tên"), _("Nhập tên mới cho \'{name}\':").format(name=name), initialvalue=name, parent=top)'),
    
    # MessageBox warnings/errors
    (r'messagebox\.showinfo\(_\("Lỗi"\), f\'Thư mục "\{new_name\}" đã tồn tại trên "\{current_dir\}"\', parent=top\)',
     r'messagebox.showinfo(_("Lỗi"), _(\'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"\').format(new_name=new_name, current_dir=current_dir), parent=top)'),
    (r'messagebox\.showwarning\(_\("Cảnh báo"\), f"Không thể xem thư mục \'\{name\}\' bằng Notepad!", parent=top\)',
     r'messagebox.showwarning(_("Cảnh báo"), _("Không thể xem thư mục \'{name}\' bằng Notepad!").format(name=name), parent=top)'),
    (r'messagebox\.showerror\(_\("Lỗi"\), f"Lỗi xóa \{name\}: \{e\}", parent=top\)',
     r'messagebox.showerror(_("Lỗi"), _("Lỗi xóa {name}: {e}").format(name=name, e=e), parent=top)'),
    (r'messagebox\.showerror\(_\("Lỗi"\), f"Không thể lưu: \{e\}", parent=win\)',
     r'messagebox.showerror(_("Lỗi"), _("Không thể lưu: {e}").format(e=e), parent=win)'),
    (r'messagebox\.showerror\(_\("Lỗi Code"\), f"Lỗi tạo Notepad: \{ex\}", parent=top\)',
     r'messagebox.showerror(_("Lỗi Code"), _("Lỗi tạo Notepad: {ex}").format(ex=ex), parent=top)'),
    (r'messagebox\.showerror\(_\("Lỗi"\), f"Không thể gửi lệnh: \{ex\}", parent=top\)',
     r'messagebox.showerror(_("Lỗi"), _("Không thể gửi lệnh: {ex}").format(ex=ex), parent=top)'),
    (r'messagebox\.showinfo\(_\("Thông báo"\), f"Đã gửi yêu cầu mở file \{ext\} bằng ứng dụng mặc định trên máy bị điều khiển\.", parent=top\)',
     r'messagebox.showinfo(_("Thông báo"), _("Đã gửi yêu cầu mở file {ext} bằng ứng dụng mặc định trên máy bị điều khiển.").format(ext=ext), parent=top)'),
    
    # Notepad titles
    (r'np_win\.title\(f"Soạn thảo \(Local\) - \{name\}"\)',
     r'np_win.title(_("Soạn thảo (Local) - {name}").format(name=name))'),
    (r'np_win\.title\(f"Soạn thảo \(Remote\) - \{name\}"\)',
     r'np_win.title(_("Soạn thảo (Remote) - {name}").format(name=name))'),
    
    # Labels
    (r'lbl_title = tk\.Label\(frame, text=f"\{item_type\} với tên \\"\{c\[\'name\'\]\}\\" " \+ _\("đã tồn tại\."\), font=\("Segoe UI", 11, "bold"\), bg="white", anchor="w"\)',
     r'lbl_title = tk.Label(frame, text=_("{item_type} với tên \"{item_name}\" đã tồn tại.").format(item_type=item_type, item_name=c[\'name\']), font=("Segoe UI", 11, "bold"), bg="white", anchor="w")'),
     
    # Menu actions string replaces
    (r'local_menu\.add_command\(label="Xem file", command=lambda: local_action\("view"\)\)',
     r'local_menu.add_command(label=_("Xem file"), command=lambda: local_action("view"))'),
    (r'remote_menu\.add_command\(label="Xem file", command=lambda: remote_action\("view"\)\)',
     r'remote_menu.add_command(label=_("Xem file"), command=lambda: remote_action("view"))'),
    
    # Simple strings already handled like _("..."), but I must wrap unwrapped ones.
    (r'tk\.Button\(mid_frame, text="Chuyển qua\\n>>"',
     r'tk.Button(mid_frame, text=_("Chuyển qua\n>>")'),
    (r'tk\.Button\(mid_frame, text="Nhận về\\n<<"',
     r'tk.Button(mid_frame, text=_("Nhận về\n<<")')
]

for old, new in replacements:
    content = re.sub(old, new, content)

with open('utils/file_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
