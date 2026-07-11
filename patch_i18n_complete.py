"""
Patch app.py: Wrap remaining hardcoded Vietnamese strings with _() 
and update the language template.
"""
import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# ===================== STEP 1: Wrap missing strings with _() =====================

replacements = [
    # --- Dialog titles ---
    ('dialog.title("Danh sách Máy tính")', 'dialog.title(_("Danh sách Máy tính"))'),
    ('rn_win.title("Đổi tên nhóm")', 'rn_win.title(_("Đổi tên nhóm"))'),
    ('dialog.title("Cài Zalo / Điện thoại")', 'dialog.title(_("Cài Zalo / Điện thoại"))'),
    ('dialog.title("Cài đặt Máy chủ (Signaling Server)")', 'dialog.title(_("Cài đặt Máy chủ (Signaling Server)"))'),
    ('dialog.title("Mật khẩu cố định")', 'dialog.title(_("Mật khẩu cố định"))'),
    ('dialog.title("Liên hệ Zalo")', 'dialog.title(_("Liên hệ Zalo"))'),
    ('dialog.title("Chọn đối tác")', 'dialog.title(_("Chọn đối tác"))'),
    ('dialog.title("Điện thoại liên hệ")', 'dialog.title(_("Điện thoại liên hệ"))'),
    ('about.title("About")', 'about.title(_("About"))'),

    # --- Menu labels missing _() ---
    ('label="4 chữ số",', 'label=_("4 chữ số"),'),
    # Note: keep value="4 chữ số" as-is since it's used for internal comparison
    ('label="Cài Zalo / Điện thoại",', 'label=_("Cài Zalo / Điện thoại"),'),
    ('label="Xuất file ngôn ngữ mẫu...", command=self.export_lang_template)', 'label=_("Xuất file ngôn ngữ mẫu..."), command=self.export_lang_template)'),
    ('label="Ngôn ngữ (Language)", menu=lang_menu)', 'label=_("Ngôn ngữ (Language)"), menu=lang_menu)'),
    ('label="About", command=self.show_about_dialog)', 'label=_("About"), command=self.show_about_dialog)'),
    # Group context menu
    ('label="Đổi tên nhóm", command=lambda g=grp: rename_group_dialog(g))', 'label=_("Đổi tên nhóm"), command=lambda g=grp: rename_group_dialog(g))'),
    
    # --- Status bar ---
    ('self.current_ip = "Đang lấy IP..."', 'self.current_ip = _("Đang lấy IP...")'),
    
    # --- Fixed password indicator ---
    ('self.fixed_pass_indicator.config(text="● Mật khẩu cố định: Đang hoạt động")', 
     'self.fixed_pass_indicator.config(text=_("● Mật khẩu cố định: Đang hoạt động"))'),
    
    # --- Empty list messages ---
    ('txt = "Không tìm thấy máy tính phù hợp." if query else "Chưa có máy tính nào được lưu.\\nBấm nút thêm bên dưới để tạo mới."',
     'txt = _("Không tìm thấy máy tính phù hợp.") if query else _("Chưa có máy tính nào được lưu.\\nBấm nút thêm bên dưới để tạo mới.")'),
    
    # --- Group name display ---
    ('grp_display = grp if grp else "Chưa phân nhóm"', 'grp_display = grp if grp else _("Chưa phân nhóm")'),
    
    # --- Question dialog for delete ---
    ('if self.show_custom_question("Xóa máy tính", f"Bạn có chắc muốn xóa \'{item[\'name\']}\' khỏi danh sách?", parent=dialog):',
     'if self.show_custom_question(_("Xóa máy tính"), _("Bạn có chắc muốn xóa") + f" \'{item[\'name\']}\' " + _("khỏi danh sách?"), parent=dialog):'),
    
    # --- Rename group dialog label ---
    ('lbl = tk.Label(rn_win, text=f"Nhập tên mới cho nhóm:\\n\'{old_group_name if old_group_name else \'Chưa phân nhóm\'}\'", font=("Segoe UI", 9), fg=self.text_white, bg=self.bg_color)',
     'lbl = tk.Label(rn_win, text=_("Nhập tên mới cho nhóm:") + f"\\n\'{old_group_name if old_group_name else _(\"Chưa phân nhóm\")}\'", font=("Segoe UI", 9), fg=self.text_white, bg=self.bg_color)'),
    
    # --- Toggle group collapse text ---
    ('event.widget.config(text=f"{new_icon} {(g if g else \'Chưa phân nhóm\').upper()}")',
     'event.widget.config(text=f"{new_icon} {(g if g else _(\"Chưa phân nhóm\")).upper()}")'),
    
    # --- Zalo/Phone dialog descriptions ---
    ('desc_text = "Nhập số điện thoại hoặc liên kết Zalo của bạn.\\nClient điều khiển máy bạn có thể click Help -> Zalo\\nđể trực tiếp nhắn tin cho bạn."',
     'desc_text = _("Nhập số điện thoại hoặc liên kết Zalo của bạn.\\nClient điều khiển máy bạn có thể click Help -> Zalo\\nđể trực tiếp nhắn tin cho bạn.")'),
    
    ('desc_text = "Nhập danh sách tên miền hoặc IP máy chủ\\n(Cách nhau bằng dấu phẩy để dự phòng)"',
     'desc_text = _("Nhập danh sách tên miền hoặc IP máy chủ\\n(Cách nhau bằng dấu phẩy để dự phòng)")'),
    
    ('desc_text = "Đặt mật khẩu cố định giúp đối tác kết nối vào\\nmáy của bạn mà không cần hỏi mật khẩu ngẫu nhiên.\\n(Để trống để tắt tính năng này)"',
     'desc_text = _("Đặt mật khẩu cố định giúp đối tác kết nối vào\\nmáy của bạn mà không cần hỏi mật khẩu ngẫu nhiên.\\n(Để trống để tắt tính năng này)")'),
    
    # --- Zalo error popup ---
    ('title_text = "LIÊN HỆ ZALO"', 'title_text = _("LIÊN HỆ ZALO")'),
    
    # --- Phone number popup ---
    ('title_text = "SỐ ĐIỆN THOẠI LIÊN HỆ"', 'title_text = _("SỐ ĐIỆN THOẠI LIÊN HỆ")'),
    
    # --- "Không rõ" fallback ---
    ('c_name = v["computer_name"] or "Không rõ"', 'c_name = v["computer_name"] or _("Không rõ")'),
    
    # --- Display text with phone ---
    # Line 2596/2689: f-string with 'Không có số'
    # These have embedded single-quoted strings, handle specially
    
    # --- Phone display ---
    ('display_text = phone_val if phone_val else "Chưa có liên lạc"', 'display_text = phone_val if phone_val else _("Chưa có liên lạc")'),
    
    # --- Status update ---
    ('self.status_var.set(f"Trạng thái: {text}")', 'self.status_var.set(_("Trạng thái:") + f" {text}")'),
    ('self.update_status("Kết nối Signaling thành công! Sẵn sàng kết nối.")', 
     'self.update_status(_("Kết nối Signaling thành công! Sẵn sàng kết nối."))'),
    
    # --- LAN error dialog technical info ---
    ('("Public IP phát hiện", public_ip if public_ip else "N/A"),',
     '(_("Public IP phát hiện"), public_ip if public_ip else "N/A"),'),
    ('("Trạng thái",          "Cùng Public IP → cùng Router/Mạng nội bộ"),',
     '(_("Trạng thái"),          _("Cùng Public IP → cùng Router/Mạng nội bộ")),'),
    ('("Phương thức thử",     "Kết nối TCP trực tiếp qua Local IP (LAN)"),',
     '(_("Phương thức thử"),     _("Kết nối TCP trực tiếp qua Local IP (LAN)")),'),
    ('("Kết quả",             "❌  Tất cả địa chỉ LAN đều không phản hồi"),',
     '(_("Kết quả"),             _("❌  Tất cả địa chỉ LAN đều không phản hồi")),'),
    
    # --- LAN troubleshooting steps ---
    ('("1", "Kiểm tra Tường lửa Windows",',
     '("1", _("Kiểm tra Tường lửa Windows"),'),
    ('("2", "Kiểm tra phần mềm diệt virus / VPN",',
     '("2", _("Kiểm tra phần mềm diệt virus / VPN"),'),
    ('("3", "Kiểm tra cổng mạng đang dùng",',
     '("3", _("Kiểm tra cổng mạng đang dùng"),'),
    ('"Vào Windows Defender Firewall → Allow an app → đảm bảo RemoteDesktopP2P.exe được phép trên Private & Public network."),',
     '_("Vào Windows Defender Firewall → Allow an app → đảm bảo RemoteDesktopP2P.exe được phép trên Private & Public network.")),'),
    ('"Tắt tạm thời các phần mềm Antivirus hoặc VPN có thể đang chặn kết nối nội bộ."),',
     '_("Tắt tạm thời các phần mềm Antivirus hoặc VPN có thể đang chặn kết nối nội bộ.")),'),
    
    # --- Export template message ---
    ('messagebox.showinfo(_(\"Lưu lại\"), f\"File ngôn ngữ mẫu đã được lưu tại:\\n{template_path}\\nBạn có thể sao chép và đổi tên thành \'en.json\' để dịch.\")',
     'messagebox.showinfo(_("Lưu lại"), _("File ngôn ngữ mẫu đã được lưu tại:") + f"\\n{template_path}\\n" + _("Bạn có thể sao chép và đổi tên thành \'en.json\' để dịch."))'),
    
    # --- Mutex message ---
    ('msg_text = "Ứng dụng P2P Remote Desktop đang chạy ở khay hệ thống"', 
     'msg_text = _("Ứng dụng P2P Remote Desktop đang chạy ở khay hệ thống")'),
    ('msg_title = "Thông báo"', 'msg_title = _("Thông báo")'),
    
    # --- Tray icon menu items ---
    ("item('Hiện (Show)', self.show_gui_from_tray, default=True),", 
     "item(_('Hiện (Show)'), self.show_gui_from_tray, default=True),"),
    ("item('Thoát (Exit)', self.exit_from_tray)", 
     "item(_('Thoát (Exit)'), self.exit_from_tray)"),
]

count = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new, 1)
        count += 1
    else:
        print(f"WARNING: Not found: {old[:80]}...")

# Handle the f-string with 'Không có số' (lines 2596, 2689) - these appear twice
content = content.replace(
    "display_text = f\"{c_name} ({p_val if p_val else 'Không có số'})\"",
    "display_text = f\"{c_name} ({p_val if p_val else _('Không có số')})\""
)

# Handle f-string for Wake-On-Lan status
content = content.replace(
    'self.update_status(f"Đã gửi Wake-On-Lan tới MAC {m}")',
    'self.update_status(_("Đã gửi Wake-On-Lan tới MAC") + f" {m}")'
)

# Handle f-string for port in LAN troubleshooting
content = content.replace(
    'f"Ứng dụng dùng cổng {BOUND_PORT}. Đảm bảo cổng này chưa bị chiếm hoặc bị chặn bởi Firewall."),',
    '_("Ứng dụng dùng cổng") + f" {BOUND_PORT}. " + _("Đảm bảo cổng này chưa bị chiếm hoặc bị chặn bởi Firewall.")),',
)

# Handle "ĐIỆN THOẠI: {comp_name.upper()}" f-string
content = content.replace(
    'title_text = f"ĐIỆN THOẠI: {comp_name.upper()}"',
    'title_text = _("ĐIỆN THOẠI:") + f" {comp_name.upper()}"'
)

# Handle "ZALO: {comp_name.upper()}" f-string
content = content.replace(
    'title_text = f"ZALO: {comp_name.upper()}"',
    'title_text = _("ZALO:") + f" {comp_name.upper()}"'
)

# Handle refresh cooldown timer
content = content.replace(
    'btn_refresh.config(text=f"🔄 Làm mới ({seconds_left}s)")',
    'btn_refresh.config(text=_("🔄 Làm mới") + f" ({seconds_left}s)")'
)

print(f"Applied {count} simple replacements + additional f-string fixes.")

# ===================== STEP 2: Save patched file =====================
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("app.py patched successfully!")
