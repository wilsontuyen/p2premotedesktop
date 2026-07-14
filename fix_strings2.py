import codecs

with open('utils/file_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    ('f"P2P Remote Desktop - Trình Quản Lý Tệp (File Manager){host_title}"', '_("P2P Remote Desktop - Trình Quản Lý Tệp (File Manager){host_title}").format(host_title=host_title)'),
    ('f"{src_title}\\n- Thư mục: {src_path}\\n- Dung lượng: {src_sz}\\n- Ngày sửa đổi: {src_mtime}"', '_("{src_title}\\n- Thư mục: {src_path}\\n- Dung lượng: {src_sz}\\n- Ngày sửa đổi: {src_mtime}").format(src_title=src_title, src_path=src_path, src_sz=src_sz, src_mtime=src_mtime)'),
    ('f"{dst_title}\\n- Thư mục: {dst_path}\\n- Dung lượng: {dst_sz}\\n- Ngày sửa đổi: {dst_mtime}"', '_("{dst_title}\\n- Thư mục: {dst_path}\\n- Dung lượng: {dst_sz}\\n- Ngày sửa đổi: {dst_mtime}").format(dst_title=dst_title, dst_path=dst_path, dst_sz=dst_sz, dst_mtime=dst_mtime)'),
    ('f" và {len(items_to_upload)-1} mục khác"', '_(" và {count} mục khác").format(count=len(items_to_upload)-1)'),
    ('f" và {len(display_names)-1} mục khác"', '_(" và {count} mục khác").format(count=len(display_names)-1)'),
    ('f"Bạn có chắc muốn xóa \'{local_tree.item(sel[0])[\'text\']}\' không?"', '_("Bạn có chắc muốn xóa \'{item_name}\' không?").format(item_name=local_tree.item(sel[0])[\'text\'])'),
    ('f"Bạn có chắc muốn xóa {len(sel)} mục đã chọn không?"', '_("Bạn có chắc muốn xóa {count} mục đã chọn không?").format(count=len(sel))'),
    ('f"Bạn có chắc muốn xóa \'{remote_tree.item(sel[0])[\'text\']}\' khỏi máy điều khiển không?"', '_("Bạn có chắc muốn xóa \'{item_name}\' khỏi máy điều khiển không?").format(item_name=remote_tree.item(sel[0])[\'text\'])'),
    ('f"Bạn có chắc muốn xóa {len(sel)} mục đã chọn khỏi máy điều khiển không?"', '_("Bạn có chắc muốn xóa {count} mục đã chọn khỏi máy điều khiển không?").format(count=len(sel))'),
    ('simpledialog.askstring("Thư mục mới", "Nhập tên thư mục mới:",', 'simpledialog.askstring(_("Thư mục mới"), _("Nhập tên thư mục mới:"),'),
    ('simpledialog.askstring("Đổi tên", f"Nhập tên mới cho \'{name}\':",', 'simpledialog.askstring(_("Đổi tên"), _("Nhập tên mới cho \'{name}\':").format(name=name),'),
    ('messagebox.showinfo(_("Lỗi"), f\'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"\',', 'messagebox.showinfo(_("Lỗi"), _(\'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"\').format(new_name=new_name, current_dir=current_dir),'),
    ('messagebox.showwarning(_("Cảnh báo"), f"Không thể xem thư mục \'{name}\' bằng Notepad!",', 'messagebox.showwarning(_("Cảnh báo"), _("Không thể xem thư mục \'{name}\' bằng Notepad!").format(name=name),'),
    ('messagebox.showerror(_("Lỗi"), f"Lỗi xóa {name}: {e}",', 'messagebox.showerror(_("Lỗi"), _("Lỗi xóa {name}: {e}").format(name=name, e=e),'),
    ('messagebox.showerror(_("Lỗi"), f"Không thể lưu: {e}",', 'messagebox.showerror(_("Lỗi"), _("Không thể lưu: {e}").format(e=e),'),
    ('messagebox.showerror(_("Lỗi Code"), f"Lỗi tạo Notepad: {ex}",', 'messagebox.showerror(_("Lỗi Code"), _("Lỗi tạo Notepad: {ex}").format(ex=ex),'),
    ('messagebox.showerror(_("Lỗi"), f"Không thể gửi lệnh: {ex}",', 'messagebox.showerror(_("Lỗi"), _("Không thể gửi lệnh: {ex}").format(ex=ex),'),
    ('messagebox.showinfo(_("Thông báo"), f"Đã gửi yêu cầu mở file {ext} bằng ứng dụng mặc định trên máy bị điều khiển.",', 'messagebox.showinfo(_("Thông báo"), _("Đã gửi yêu cầu mở file {ext} bằng ứng dụng mặc định trên máy bị điều khiển.").format(ext=ext),'),
    ('f"Soạn thảo (Local) - {name}"', '_("Soạn thảo (Local) - {name}").format(name=name)'),
    ('f"Soạn thảo (Remote) - {name}"', '_("Soạn thảo (Remote) - {name}").format(name=name)'),
    ('f"{item_type} với tên \\"{c[\'name\']}\\" " + _("đã tồn tại.")', '_("{item_type} với tên \\"{item_name}\\" đã tồn tại.").format(item_type=item_type, item_name=c[\'name\'])'),
    ('local_menu.add_command(label="Xem file",', 'local_menu.add_command(label=_("Xem file"),'),
    ('remote_menu.add_command(label="Xem file",', 'remote_menu.add_command(label=_("Xem file"),'),
    ('text="Chuyển qua\\n>>"', 'text=_("Chuyển qua\\n>>")'),
    ('text="Nhận về\\n<<"', 'text=_("Nhận về\\n<<")')
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)

with open('utils/file_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
