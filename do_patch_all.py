import os

print('Patching core\clipboard_agent.py...')
with open(r'core\clipboard_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'from core.i18n import _' not in content:
    if 'import ' in content:
        content = content.replace('import os', 'import os\nfrom core.i18n import _', 1)
    else:
        content = 'from core.i18n import _\n' + content

# TODO MANUAL F-STRING: Truyền file: {self.batch_display_name} - Thất bại
# Context: log_activity(_("Truyền file: ") + str(self.batch_display_name) + _(" - Thất bại"))
# content = content.replace(..., ...)
# Context: self.app.after(0, lambda: self.app.update_status(_("Đã hủy truyền tải file.")))
content = content.replace(_('_("Đã hủy truyền tải file.")'), _('_("Đã hủy truyền tải file.")'))
# TODO MANUAL F-STRING: {len(files)} tệp tin
# Context: display_name = str(len(files)) + _(" tệp tin") if len(files) > 1 else files[0].get("name", "Unknown")
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Truyền file: {self.batch_display_name} - {total_size} byte - Thành công
# Context: try: log_activity(_("Truyền file: ") + str(self.batch_display_name) + " - " + str(total_size) + _(" byte - Thành công"))
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Truyền file: {self.batch_display_name} - {total_size} byte - Thất bại
# Context: log_activity(f"Truyền file: {self.batch_display_name} - {total_size} byte - Thất bại")
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Nhận file: {self.batch_display_name} - {self.batch_total_size} byte - Thành công
# Context: try: log_activity(_("Nhận file: ") + str(self.batch_display_name) + " - " + str(self.batch_total_size) + _(" byte - Thành công"))
# content = content.replace(..., ...)
# Context: """Gửi chuỗi REQUEST_FILES cho host qua UpPipe."""
content = content.replace(_('_("Gửi chuỗi REQUEST_FILES cho host qua UpPipe.")'), _('_("Gửi chuỗi REQUEST_FILES cho host qua UpPipe.")'))
# Context: """Chạy trong WndProc thread: mở clipboard, đăng ký deferred CF_HDROP."""
content = content.replace(_('_("Chạy trong WndProc thread: mở clipboard, đăng ký deferred CF_HDROP.")'), _('_("Chạy trong WndProc thread: mở clipboard, đăng ký deferred CF_HDROP.")'))
# Context: """WndProc cho hidden window của agent. Xử lý WM_RENDERFORMAT (Paste xảy ra)."""
content = content.replace(_('_("WndProc cho hidden window của agent. Xử lý WM_RENDERFORMAT (Paste xảy ra).")'), _('_("WndProc cho hidden window của agent. Xử lý WM_RENDERFORMAT (Paste xảy ra).")'))
# Context: """Tạo hidden Win32 window cho agent, chạy trong luồng riêng với message loop."""
content = content.replace(_('_("Tạo hidden Win32 window cho agent, chạy trong luồng riêng với message loop.")'), _('_("Tạo hidden Win32 window cho agent, chạy trong luồng riêng với message loop.")'))
# Context: """Giải phóng luồng chờ WM_RENDERFORMAT và xóa trạng thái pending."""
content = content.replace(_('_("Giải phóng luồng chờ WM_RENDERFORMAT và xóa trạng thái pending.")'), _('_("Giải phóng luồng chờ WM_RENDERFORMAT và xóa trạng thái pending.")'))
# Context: """Nút Hủy trong dialog → gửi Win32 Event để host service dừng gửi."""
content = content.replace(_('"Nút Hủy trong dialog → gửi Win32 Event để host service dừng gửi."'), _('_("Nút Hủy trong dialog → gửi Win32 Event để host service dừng gửi.")'))
# Context: root, _("Đang tải file về..."), display_name, total_size,
content = content.replace(_('_("Đang tải file về...")'), _('_("Đang tải file về...")'))

with open(r'core\clipboard_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patching core\host.py...')
with open(r'core\host.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'from core.i18n import _' not in content:
    if 'import ' in content:
        content = content.replace('import os', 'import os\nfrom core.i18n import _', 1)
    else:
        content = 'from core.i18n import _\n' + content

# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi hệ thống"), _("Không thể chạy server! Các cổng mạng đều bị chiếm dụng hoặc bị chặn bởi Tường lửa.\nVui
content = content.replace(_('_(")Lỗi hệ thống")'), _('_(_("Lỗi hệ thống"))_('))
# Context: self.after(0, lambda: self.show_custom_error("Lỗi hệ thống", "Không thể chạy server! Các cổng mạng đều bị chiếm dụng hoặc bị chặn bởi Tường lửa.\nVui
# Context: self.update_status("Lỗi khởi động Server")
content = content.replace(_(')_("Lỗi khởi động Server")'), _('_(_("Lỗi khởi động Server"))_('))
# Context: client_id = data.get("client_id", "Không rõ")
content = content.replace(_(')_("Không rõ")'), _('_("Không rõ")'))
# Context: client_comp = data.get("computer_name", _("Không rõ"))
content = content.replace(_('_("Không rõ")'), _('_("Không rõ")'))
# Context: if client_comp != _("Không rõ"):
content = content.replace(_('_("Không rõ")'), _('_("Không rõ")'))
# TODO MANUAL F-STRING: Máy tính [{client_comp}] đang điều khiển máy bạn
# Context: msg_text = _("Máy tính [") + str(client_comp) + _("] đang điều khiển máy bạn")
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Máy tính có ID [{fmt_client_id}] đang điều khiển máy bạn
# Context: msg_text = _("Máy tính có ID [") + str(fmt_client_id) + _("] đang điều khiển máy bạn")
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Chấp nhận kết nối từ ID {fmt_client_id} ({client_comp})
# Context: try: log_activity(_("Chấp nhận kết nối từ ID ") + str(fmt_client_id) + " (" + str(client_comp) + ")")
# content = content.replace(..., ...)
# Context: self.after(0, lambda: self.show_custom_info("Kết nối từ xa", msg_text))
content = content.replace(_('_("Kết nối từ xa")'), _('_("Kết nối từ xa")'))
# TODO MANUAL F-STRING: Đang dùng máy chủ {addrs_str}
# Context: self.update_status(f"Đang dùng máy chủ {addrs_str}_(")
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Ngắt kết nối với ID {fmt_client_id} ({client_comp})
# Context: try: log_activity(f")Ngắt kết nối với ID {fmt_client_id} ({client_comp})_(")
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Đang bị điều khiển bởi {addrs_str}
# Context: self.update_status(f")Đang bị điều khiển bởi {addrs_str}_(")
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Đã đóng kết nối với Client {addr[0]} lúc {time.strftime(
# Context: self.update_status(f")Đã đóng kết nối với Client {addr[0]} lúc {time.strftime('%H:%M:%S')} (Sẵn sàng kết nối)")
# content = content.replace(..., ...)
# Context: self.update_status(f"Đã đóng kết nối với Client {addr[0]} lúc {time.strftime('%H:%M:%S')} (Sẵn sàng kết nối)_(")
# TODO MANUAL F-STRING: Lỗi xảy ra trên máy Host:\n{e}
# Context: ")message": f"Lỗi xảy ra trên máy Host:\n{e}_("
# content = content.replace(..., ...)

with open(r'core\host.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patching core\network_manager.py...')
with open(r'core\network_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'from core.i18n import _' not in content:
    if 'import ' in content:
        content = content.replace('import os', 'import os\nfrom core.i18n import _', 1)
    else:
        content = 'from core.i18n import _\n' + content

# TODO MANUAL F-STRING: Đã gửi Wake-On-Lan tới MAC {m}
# Context: self.update_status(f")Đã gửi Wake-On-Lan tới MAC {m}")
# content = content.replace(..., ...)
# Context: ""_("Khởi chạy 2 luồng: beacon broadcaster và beacon listener cho LAN Discovery.")""
content = content.replace(_('_("Khởi chạy 2 luồng: beacon broadcaster và beacon listener cho LAN Discovery.")'), _('_("Khởi chạy 2 luồng: beacon broadcaster và beacon listener cho LAN Discovery.")'))
# Context: ""_("Phát UDP broadcast beacon mỗi LAN_BEACON_INTERVAL giây.")""
content = content.replace(_('_("Phát UDP broadcast beacon mỗi LAN_BEACON_INTERVAL giây.")'), _('_("Phát UDP broadcast beacon mỗi LAN_BEACON_INTERVAL giây.")'))
# Context: ""_("Lắng nghe UDP broadcast beacon từ các máy khác trong LAN.")""
content = content.replace(_('_("Lắng nghe UDP broadcast beacon từ các máy khác trong LAN.")'), _('_("Lắng nghe UDP broadcast beacon từ các máy khác trong LAN.")'))
# Context: ""_("Hiển thị dialog danh sách các máy tính phát hiện được trong mạng LAN.")""
content = content.replace('"Hiển thị dialog danh sách các máy tính phát hiện được trong mạng LAN."', '_("Hiển thị dialog danh sách các máy tính phát hiện được trong mạng LAN.")')
# Context: dialog.title("Máy tính trong mạng LAN")
content = content.replace(_('_("Máy tính trong mạng LAN")'), _('_("Máy tính trong mạng LAN")'))
# Context: lbl_title = tk.Label(dialog, text=_("📡 MÁY TÍNH TRONG MẠNG LAN"), font=("Segoe UI", 11, "bold"), fg=self.btn_color, bg=self.bg_color)
content = content.replace(_('_("📡 MÁY TÍNH TRONG MẠNG LAN")'), _('_("📡 MÁY TÍNH TRONG MẠNG LAN")'))
# Context: lbl_desc = tk.Label(dialog, text=_("Kết nối trực tiếp không qua Signaling Server"), font=("Segoe UI", 8, "italic"), fg=self.text_gray, bg=self.bg_color)
content = content.replace(_('_("Kết nối trực tiếp không qua Signaling Server")'), _('_("Kết nối trực tiếp không qua Signaling Server")'))
# Context: self.update_status(_("Đang kết nối LAN trực tiếp tới ") + str(peer_info['computer_name']) + "...")
# Context: ""_("Mở dialog nhập mật khẩu rồi kết nối trực tiếp qua LAN.")""
content = content.replace('"Mở dialog nhập mật khẩu rồi kết nối trực tiếp qua LAN."', '_("Mở dialog nhập mật khẩu rồi kết nối trực tiếp qua LAN.")')
# Context: pass_dialog.title(_("Kết nối tới ") + str(peer_info['computer_name']))
# Context: tk.Label(pass_dialog, text=_("Máy: ") + str(peer_info['computer_name']), font=("Segoe UI", 10, "bold"), fg=self.text_white, bg=self.bg_color).pack(pady=(15, 2
# TODO MANUAL F-STRING: ID: {fmt_id}  •  IP: {peer_info[
# Context: tk.Label(pass_dialog, text=_("ID: ") + str(fmt_id) + _("  •  IP: ") + str(peer_info['local_ip']), font=("Segoe UI", 8), fg=self.text_gray, bg=self.bg_color).pack(pady=(0, 1
# content = content.replace(..., ...)
# Context: tk.Label(pass_dialog, text=_("Nhập mật khẩu:"), font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color).pack(anchor=tk.W, padx=30)
content = content.replace(_('_("Nhập mật khẩu:")'), _('_("Nhập mật khẩu:")'))
# Context: save_cb = tk.Checkbutton(pass_dialog, text=_("Lưu mật khẩu máy tính này"), variable=save_var, font=("Segoe UI", 9), fg=self.text_gray, bg=self.bg_color,
content = content.replace(_('_("Lưu mật khẩu máy tính này")'), _('_("Lưu mật khẩu máy tính này")'))
# Context: self.show_custom_error(_("Lỗi"), _("Vui lòng nhập mật khẩu!"), parent=pass_dialog)
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: self.show_custom_error(_("Lỗi"), _("Vui lòng nhập mật khẩu!"), parent=pass_dialog)
content = content.replace(_('_("Vui lòng nhập mật khẩu!")'), _('_("Vui lòng nhập mật khẩu!")'))
# Context: self.update_status(_("Đang kết nối LAN trực tiếp tới ") + str(peer_info['computer_name']) + "...")
# Context: tk.Button(btn_frame, text="Kết nối", font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.F
content = content.replace(_('_("Kết nối")'), _('_("Kết nối")'))
# Context: tk.Button(btn_frame, text=_("Hủy"), font=("Segoe UI", 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, relief=tk.FLAT, bd=0, pady=4, cursor="han
content = content.replace(_('_("Hủy")'), _('_(_("Hủy"))_('))
# Context: tk.Label(scroll_frame, text="Không tìm thấy máy tính nào trong mạng LAN.\nĐảm bảo các máy đều đang chạy Easy Remote Desktop.", font=("Segoe UI", 9), f
content = content.replace(')"Không tìm thấy máy tính nào trong mạng LAN.\\nĐảm bảo các máy đều đang chạy Easy Remote Desktop."', '_("Không tìm thấy máy tính nào trong mạng LAN.\\nĐảm bảo các máy đều đang chạy Easy Remote Desktop.")')
# Context: status_label.config(text="Đang quét... (0 máy)")
content = content.replace(_('_("Đang quét... (0 máy)")'), _('_("Đang quét... (0 máy)_(")'))
# TODO MANUAL F-STRING: Tìm thấy {len(peers)} máy trong mạng LAN
# Context: status_label.config(text=f")Tìm thấy {len(peers)} máy trong mạng LAN")
# content = content.replace(..., ...)
# Context: tk.Label(row, text=_("●"), font=("Segoe UI", 10), fg=dot_color, bg=self.card_color).pack(side=tk.LEFT, padx=(10, 5))
content = content.replace(_('"●"'), _('_("●")'))
# Context: btn = tk.Button(row, text=_("Kết nối"), font=("Segoe UI", 9, "bold"), fg=self.text_white, bg=self.btn_color, activebackground=self.btn_hover, relief=tk.F
content = content.replace(_('_("Kết nối")'), _('_("Kết nối")'))
# Context: btn = tk.Button(row, text=_("Bật nguồn (WOL)"), font=("Segoe UI", 9, "bold"), fg=self.text_white, bg="#D35400", activebackground="#E67E22", relief=tk.FLA
content = content.replace(_('_("Bật nguồn (WOL)")'), _('_("Bật nguồn (WOL)")'))
# TODO MANUAL F-STRING: ID: {fmt_id}  •  IP: {display_ip}:{info[
# Context: lbl_details = tk.Label(info_frame, text=_("ID: ") + str(fmt_id) + _("  •  IP: ") + str(display_ip) + ":" + str(info['port']), font=("Segoe UI", 8), fg=self.text_gray, bg=self.card_col
# content = content.replace(..., ...)
# Context: tk.Button(btn_frame, text=_("🔄 Làm mới"), font=("Segoe UI", 9, "bold"), fg=self.text_white, bg="#007ACC", activebackground="#005A9E", relief=tk.FLAT, bd=
content = content.replace(_('_("🔄 Làm mới")'), _('_("🔄 Làm mới")'))
# Context: tk.Button(btn_frame, text=_("Đóng"), font=("Segoe UI", 9, "bold"), fg=self.btn_cancel_fg, bg=self.btn_cancel_bg, relief=tk.FLAT, bd=0, pady=4, padx=15, c
content = content.replace(_('_("Đóng")'), _('_("Đóng")'))
# Context: """Kết nối TCP trực tiếp tới máy trong LAN (không qua Signaling Server)."""
content = content.replace(_('_("Kết nối TCP trực tiếp tới máy trong LAN (không qua Signaling Server).")'), _('_("Kết nối TCP trực tiếp tới máy trong LAN (không qua Signaling Server).")'))
# Context: self.update_status(_("Kết nối LAN thất bại!"))
content = content.replace(_('_("Kết nối LAN thất bại!")'), _('_("Kết nối LAN thất bại!")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi kết nối LAN"), f"Không thể kết nối tới {peer_info['computer_name']} ({ip}:{port}).\nKiểm tra Tường lử
content = content.replace(_('_("Lỗi kết nối LAN")'), _('_("Lỗi kết nối LAN")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi kết nối LAN"), f"Không thể kết nối tới {peer_info['computer_name']} ({ip}:{port}).\nKiểm tra Tường lử
# TODO MANUAL F-STRING: ]} ({ip}:{port}).\nKiểm tra Tường lửa (Firewall) hoặc đảm bảo máy đích đang chạy ứng dụng.
# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi kết nối LAN"), f"Không thể kết nối tới {peer_info['computer_name']} ({ip}:{port}).\nKiểm tra Tường lử
# content = content.replace(..., ...)
# Context: self.update_status(_("Sẵn sàng kết nối"))
content = content.replace(_('_("Sẵn sàng kết nối")'), _('_("Sẵn sàng kết nối")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Đối tác ngắt kết nối đột ngột!")))
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Đối tác ngắt kết nối đột ngột!")))
content = content.replace(_('_("Đối tác ngắt kết nối đột ngột!")'), _('_("Đối tác ngắt kết nối đột ngột!")'))
# Context: self.update_status(_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 1/2..."))
content = content.replace(_('_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 1/2...")'), _('_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 1/2...")'))
# Context: self.update_status(_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 2/2..."))
content = content.replace(_('_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 2/2...")'), _('_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 2/2...")'))
# Context: self.update_status(_("Kết nối LAN thành công! Đang khởi động màn hình..."))
content = content.replace(_('_("Kết nối LAN thành công! Đang khởi động màn hình...")'), _('_("Kết nối LAN thành công! Đang khởi động màn hình...")'))
# Context: msg = res.get("message", _("Sai mật khẩu!"))
content = content.replace(_('_("Sai mật khẩu!")'), _('_("Sai mật khẩu!")'))
# Context: self.update_status(_("Bị từ chối kết nối"))
content = content.replace(_('_("Bị từ chối kết nối")'), _('_("Bị từ chối kết nối")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Từ chối kết nối"), _("Kết nối bị từ chối:\n") + str(msg)))
content = content.replace(_('_("Từ chối kết nối")'), _('_(_("Từ chối kết nối"))_('))
# TODO MANUAL F-STRING: Kết nối bị từ chối:\n{msg}
# Context: self.after(0, lambda: self.show_custom_error("Từ chối kết nối", _("Kết nối bị từ chối:\n") + str(msg)))
# content = content.replace(..., ...)
# Context: self.update_status("Sẵn sàng kết nối")
content = content.replace(_(')_("Sẵn sàng kết nối")'), _('_(_("Sẵn sàng kết nối"))_('))
# Context: self.after(0, lambda err=str(e): self.show_custom_error("Lỗi bắt tay LAN", _("Lỗi xác thực handshake:\n") + str(err)))
content = content.replace(_(')_("Lỗi bắt tay LAN")'), _('_(_("Lỗi bắt tay LAN"))_('))
# TODO MANUAL F-STRING: Lỗi xác thực handshake:\n{err}
# Context: self.after(0, lambda err=str(e): self.show_custom_error("Lỗi bắt tay LAN", _("Lỗi xác thực handshake:\n") + str(err)))
# content = content.replace(..., ...)
# Context: self.update_status("Đang khởi động Server lắng nghe...")
content = content.replace(_(')_("Đang khởi động Server lắng nghe...")'), _('_("Đang khởi động Server lắng nghe...")'))
# Context: self.update_status("Đang tự động cấu hình Router (UPnP)...")
content = content.replace(_('_("Đang tự động cấu hình Router (UPnP)...")'), _('_("Đang tự động cấu hình Router (UPnP)...")'))
# Context: self.update_status("Đang lấy thông vị trí mạng...")
content = content.replace(_('_("Đang lấy thông vị trí mạng...")'), _('_("Đang lấy thông vị trí mạng...")'))
# Context: self.update_status(_("Đang kết nối tới các Signaling Server..."))
content = content.replace(_('_("Đang kết nối tới các Signaling Server...")'), _('_("Đang kết nối tới các Signaling Server..._(")'))
# TODO MANUAL F-STRING: Đang kết nối Signaling Server... ({8 - int(timeout)}s)
# Context: self.update_status(f")Đang kết nối Signaling Server... ({8 - int(timeout)}s)")
# content = content.replace(..., ...)
# Context: suffix = " (Dịch vụ hoạt động)" if getattr(self, "is_service_active", False) else ""
content = content.replace(_('_(" (Dịch vụ hoạt động)")'), _('_(" (Dịch vụ hoạt động)")'))
# TODO MANUAL F-STRING: Kết nối Signaling & Mở cổng Router thành công (Cổng {BOUND_PORT})!{suffix}
# Context: self.update_status(f"Kết nối Signaling & Mở cổng Router thành công (Cổng {BOUND_PORT})!{suffix}_(")
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Kết nối Signaling thành công (Cổng {BOUND_PORT})! Sẵn sàng kết nối.{suffix}
# Context: self.update_status(f")Kết nối Signaling thành công (Cổng {BOUND_PORT})! Sẵn sàng kết nối.{suffix}")
# content = content.replace(..., ...)
# Context: suffix = " (Dịch vụ hoạt động)" if getattr(self, "is_service_active", False) else ""
content = content.replace(_('_(" (Dịch vụ hoạt động)")'), _('_(" (Dịch vụ hoạt động)")'))
# TODO MANUAL F-STRING: Chưa kết nối Signaling Server. Đang thử lại ở chế độ nền...{suffix}
# Context: self.update_status(_("Chưa kết nối Signaling Server. Đang thử lại ở chế độ nền... ") + str(suffix))
# content = content.replace(..., ...)
# Context: self.after(0, lambda: self.update_status("Kết nối Signaling thành công! Sẵn sàng kết nối."))
content = content.replace(_('_("Kết nối Signaling thành công! Sẵn sàng kết nối.")'), _('_("Kết nối Signaling thành công! Sẵn sàng kết nối.")'))
# Context: self.after(0, lambda: self.update_status("Mất kết nối toàn bộ Signaling Server. Đang thử lại...", is_error=True, blink=True))
content = content.replace(_('_("Mất kết nối toàn bộ Signaling Server. Đang thử lại...")'), _('_("Mất kết nối toàn bộ Signaling Server. Đang thử lại...")'))
# Context: self.show_custom_error("Lỗi", _("Vui lòng nhập mã ID đối tác hợp lệ (12 chữ số)!"))
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: self.show_custom_error(_("Lỗi"), _("Vui lòng nhập mã ID đối tác hợp lệ (12 chữ số)!"))
content = content.replace(_('_("Vui lòng nhập mã ID đối tác hợp lệ (12 chữ số)!")'), _('_("Vui lòng nhập mã ID đối tác hợp lệ (12 chữ số)!")'))
# Context: self.show_custom_error(_("Lỗi"), _("Vui lòng nhập mật khẩu đối tác!"))
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: self.show_custom_error(_("Lỗi"), _("Vui lòng nhập mật khẩu đối tác!"))
content = content.replace(_('_("Vui lòng nhập mật khẩu đối tác!")'), _('_("Vui lòng nhập mật khẩu đối tác!")'))
# Context: self.update_status(_("Đang tìm địa chỉ IP của đối tác trên dịch vụ danh bạ..."))
content = content.replace(_('_("Đang tìm địa chỉ IP của đối tác trên dịch vụ danh bạ...")'), _('_("Đang tìm địa chỉ IP của đối tác trên dịch vụ danh bạ...")'))
# Context: self.after(0, lambda: self.show_custom_info(_("Thông báo"), _("Bạn không thể kết nối tới chính bạn :-)")))
content = content.replace(_('_("Thông báo")'), _('_("Thông báo")'))
# Context: self.after(0, lambda: self.show_custom_info(_("Thông báo"), _("Bạn không thể kết nối tới chính bạn :-)")))
content = content.replace(_('_("Bạn không thể kết nối tới chính bạn :-)")'), _('_("Bạn không thể kết nối tới chính bạn :-)")'))
# Context: self.update_status(_("Kết nối bị hủy."))
content = content.replace(_('_("Kết nối bị hủy.")'), _('_("Kết nối bị hủy.")'))
# TODO MANUAL F-STRING: Đang hiển thị cửa sổ điều khiển đã kết nối của {partner_id}...
# Context: self.update_status(_("Đang hiển thị cửa sổ điều khiển đã kết nối của ") + str(partner_id) + "...")
# content = content.replace(..., ...)
# Context: self.update_status("Chưa kết nối Signaling Server!")
content = content.replace(_('_("Chưa kết nối Signaling Server!")'), _('_("Chưa kết nối Signaling Server!")'))
# Context: self.after(0, lambda: self.show_custom_error("Lỗi", _("Chưa kết nối đến Server Báo hiệu. Vui lòng kiểm tra lại mạng hoặc VPS.")))
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Chưa kết nối đến Server Báo hiệu. Vui lòng kiểm tra lại mạng hoặc VPS.")))
content = content.replace(_('_("Chưa kết nối đến Server Báo hiệu. Vui lòng kiểm tra lại mạng hoặc VPS.")'), _('_("Chưa kết nối đến Server Báo hiệu. Vui lòng kiểm tra lại mạng hoặc VPS.")'))
# Context: self.update_status(_("Đang tìm và chờ đối tác phản hồi..."))
content = content.replace(_('_("Đang tìm và chờ đối tác phản hồi...")'), _('_("Đang tìm và chờ đối tác phản hồi...")'))
# TODO MANUAL F-STRING: Mất kết nối. Đang thử kết nối lại lần {retry_count + 1}/30...
# Context: self.update_status(_("Mất kết nối. Đang thử kết nối lại lần ") + str(retry_count + 1) + "/30...")
# content = content.replace(..., ...)
# Context: self.update_status("Sẵn sàng kết nối")
content = content.replace(_('_("Sẵn sàng kết nối")'), _('_("Sẵn sàng kết nối")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Không thể tìm thấy hoặc đối tác đang Offline / Từ chối kết nối.")))
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Không thể tìm thấy hoặc đối tác đang Offline / Từ chối kết nối.")))
content = content.replace(_('_("Không thể tìm thấy hoặc đối tác đang Offline / Từ chối kết nối.")'), _('_("Không thể tìm thấy hoặc đối tác đang Offline / Từ chối kết nối.")'))
# Context: self.update_status(_("Đang quét kết nối nội bộ (LAN)..."))
content = content.replace(_('_("Đang quét kết nối nội bộ (LAN)...")'), _('_("Đang quét kết nối nội bộ (LAN)...")'))
# Context: self.update_status("Sẵn sàng kết nối")
content = content.replace(_('_("Sẵn sàng kết nối")'), _('_("Sẵn sàng kết nối")'))
# TODO MANUAL F-STRING: Đang đục lỗ Tường lửa (TCP Hole Punching) tới {public_ip}:{port}...
# Context: self.update_status(_("Đang đục lỗ Tường lửa (TCP Hole Punching) tới ") + str(public_ip) + ":" + str(port) + "...")
# content = content.replace(..., ...)
# Context: self.update_status("Sẵn sàng kết nối")
content = content.replace(_('_("Sẵn sàng kết nối")'), _('_("Sẵn sàng kết nối")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi kết nối"),
content = content.replace(_('_("Lỗi kết nối")'), _('_("Lỗi kết nối")'))
# Context: f"Kỹ thuật Đục Lỗ Tường Lửa (Hole Punching) thất bại!\n\n"
content = content.replace(_('"Kỹ thuật Đục Lỗ Tường Lửa (Hole Punching) thất bại!\\n\\n"'), _('_("Kỹ thuật Đục Lỗ Tường Lửa (Hole Punching) thất bại!\\n\\n")'))
# Context: f"Lý do: Không thể thiết lập kết nối trực tiếp P2P tới đối tác."
content = content.replace(_('_("Lý do: Không thể thiết lập kết nối trực tiếp P2P tới đối tác.")'), _('_("Lý do: Không thể thiết lập kết nối trực tiếp P2P tới đối tác.")'))
# Context: self.update_status("Sẵn sàng kết nối")
content = content.replace(_('_("Sẵn sàng kết nối")'), _('_("Sẵn sàng kết nối")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Đối tác ngắt kết nối đột ngột!")))
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Lỗi"), _("Đối tác ngắt kết nối đột ngột!")))
content = content.replace(_('_("Đối tác ngắt kết nối đột ngột!")'), _('_("Đối tác ngắt kết nối đột ngột!")'))
# Context: self.update_status(_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 1/2..."))
content = content.replace(_('_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 1/2...")'), _('_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 1/2...")'))
# Context: net_class_viet = _("Trung bình (Medium)")
content = content.replace(_('_("Trung bình (Medium)")'), _('_("Trung bình (Medium)")'))
# Context: self.update_status(_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 2/2..."))
content = content.replace(_('_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 2/2...")'), _('_("Đang kiểm tra chất lượng mạng (Ping & Băng thông) lần 2/2...")'))
# Context: net_class_viet = _("Tốt (High-speed)")
content = content.replace(_('_("Tốt (High-speed)")'), _('_("Tốt (High-speed)")'))
# Context: net_class_viet = _("Yếu (Low-speed)")
content = content.replace(_('_("Yếu (Low-speed)")'), _('_("Yếu (Low-speed)")'))
# Context: net_class_viet = _("Trung bình (Medium)")
content = content.replace(_('_("Trung bình (Medium)")'), _('_("Trung bình (Medium)")'))
# TODO MANUAL F-STRING: Đo tốc độ (Lớn nhất 2 lần): Ping {avg_ping:.1f}ms, Băng thông {bandwidth:.2f} Mbps. Chất lượng: {net_class_viet}.
# Context: status_text = _("Đo tốc độ (Lớn nhất 2 lần): Ping ") + f"{avg_ping:.1f}ms" + _(", Băng thông ") + f"{bandwidth:.2f} Mbps" + _(". Chất lượng: ") + str(net_class_viet) + "."
# content = content.replace(..., ...)
# Context: self.update_status("Kết nối thành công! Đang khởi động màn hình...")
content = content.replace(_('_("Kết nối thành công! Đang khởi động màn hình...")'), _('_("Kết nối thành công! Đang khởi động màn hình...")'))
# Context: msg = res.get("message", _("Sai mật khẩu!"))
content = content.replace(_('_("Sai mật khẩu!")'), _('_("Sai mật khẩu!")'))
# Context: self.update_status(_("Bị từ chối kết nối"))
content = content.replace(_('_("Bị từ chối kết nối")'), _('_("Bị từ chối kết nối")'))
# Context: self.after(0, lambda: self.show_custom_error(_("Từ chối kết nối"), _("Kết nối bị từ chối:\n") + str(msg)))
content = content.replace(_('_("Từ chối kết nối")'), _('_(_("Từ chối kết nối"))_('))
# TODO MANUAL F-STRING: Kết nối bị từ chối:\n{msg}
# Context: self.after(0, lambda: self.show_custom_error("Từ chối kết nối", _("Kết nối bị từ chối:\n") + str(msg)))
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Mất kết nối. Đang thử kết nối lại lần {retry_count + 1}/30...
# Context: self.update_status(_("Mất kết nối. Đang thử kết nối lại lần ") + str(retry_count + 1) + "/30...")
# content = content.replace(..., ...)
# Context: self.update_status("Sẵn sàng kết nối")
content = content.replace(_(')_("Sẵn sàng kết nối")'), _('_(_("Sẵn sàng kết nối"))_('))
# Context: self.after(0, lambda err=str(e): self.show_custom_error("Lỗi bắt tay", _("Lỗi xác thực handshake:\n") + str(err)))
content = content.replace(_(')_("Lỗi bắt tay")'), _('_(_("Lỗi bắt tay"))_('))
# TODO MANUAL F-STRING: Lỗi xác thực handshake:\n{err}
# Context: self.after(0, lambda err=str(e): self.show_custom_error("Lỗi bắt tay", _("Lỗi xác thực handshake:\n") + str(err)))
# content = content.replace(..., ...)
# Context: self.after(0, lambda: self.update_status(_("Đang tự động kết nối lại...")))
content = content.replace(_(')_("Đang tự động kết nối lại...")'), _('_("Đang tự động kết nối lại...")'))
# Context: self.update_status("Đã mở một cửa sổ điều khiển mới (Sẵn sàng kết nối)")
content = content.replace(_('_("Đã mở một cửa sổ điều khiển mới (Sẵn sàng kết nối)")'), _('_("Đã mở một cửa sổ điều khiển mới (Sẵn sàng kết nối)_(")'))

with open(r'core\network_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patching core\viewer.py...')
with open(r'core\viewer.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'from core.i18n import _' not in content:
    if 'import ' in content:
        content = content.replace('import os', 'import os\nfrom core.i18n import _', 1)
    else:
        content = 'from core.i18n import _\n' + content

# TODO MANUAL F-STRING: )} - [Client] Lỗi giải mã ảnh Pillow: {ie}\n
# Context: with open(")client_error.log", "a", encoding="utf-8") as f: f.write(time.strftime('%Y-%m-%d %H:%M:%S') + _(" - [Client] Lỗi giải mã ảnh Pillow: ") + str(ie) + "\n")
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Bắt đầu điều khiển ID {partner_id} ({computer_name})
# Context: try: log_activity(_("Bắt đầu điều khiển ID ") + str(partner_id) + " (" + str(computer_name) + ")")
# content = content.replace(..., ...)
# Context: file_text_surf = btn_font.render("Chuyển tệp", True, file_text_color)
content = content.replace(_('_("Chuyển tệp")'), _('_("Chuyển tệp")'))
# Context: power_text_surf = symbol_font.render(_("¤"), True, (0, 0, 0))
content = content.replace(_('"¤"'), _('_("¤")'))
# Context: power_text_surf = btn_font.render(_("¤"), True, (0, 0, 0))
content = content.replace(_('"¤"'), _('_("¤")'))
# Context: text_msg = _("Màn hình bảo mật (UAC / Lock Screen) đang hiển thị ở máy Host...")
content = content.replace(_('_("Màn hình bảo mật (UAC / Lock Screen) đang hiển thị ở máy Host...")'), _('_("Màn hình bảo mật (UAC / Lock Screen) đang hiển thị ở máy Host...")'))
# TODO MANUAL F-STRING: Đang chuyển giao diện... Vui lòng đợi {current_countdown} giây...
# Context: text_msg = f"Đang chuyển giao diện... Vui lòng đợi {current_countdown} giây..._("
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Trạng thái: {status_msg_text}
# Context: text_surf = msg_font.render(f")Trạng thái: {status_msg_text}_(", True, (255, 165, 0))
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Thời gian chờ: {countdown} giây...
# Context: cd_surf = msg_font.render(f")Thời gian chờ: {countdown} giây..._(", True, (255, 255, 255))
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Mất kết nối. Đang thử kết nối lại... {countdown} giây...
# Context: text_surf = msg_font.render(f")Mất kết nối. Đang thử kết nối lại... {countdown} giây..._(", True, (255, 255, 255))
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: Ngừng điều khiển ID {partner_id} ({computer_name})
# Context: try: log_activity(f")Ngừng điều khiển ID {partner_id} ({computer_name})")
# content = content.replace(..., ...)

with open(r'core\viewer.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patching gui\components.py...')
with open(r'gui\components.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'from core.i18n import _' not in content:
    if 'import ' in content:
        content = content.replace('import os', 'import os\nfrom core.i18n import _', 1)
    else:
        content = 'from core.i18n import _\n' + content

# Context: lbl_arrow1 = tk.Label(link1, text="→", font=("Segoe UI", 16, "bold"), fg="#0066CC", bg="#FFFFFF")
content = content.replace(_('"→"'), _('_("→")'))
# Context: lbl_arrow2 = tk.Label(link2, text=_("→"), font=("Segoe UI", 16, "bold"), fg="#0066CC", bg="#FFFFFF")
content = content.replace(_('"→"'), _('_("→")'))
# Context: bottom_frame, text=_("Hủy"), font=("Segoe UI", 9),
content = content.replace(_('_("Hủy")'), _('_("Hủy")'))
# Context: btn_frame, text=_("Đồng ý (Yes)"), font=("Segoe UI", 9, "bold"),
content = content.replace(_('_("Đồng ý (Yes)")'), _('_("Đồng ý (Yes)")'))
# Context: btn_frame, text=_("Bỏ qua (No)"), font=("Segoe UI", 9, "bold"),
content = content.replace(_('_("Bỏ qua (No)")'), _('_("Bỏ qua (No)")'))

with open(r'gui\components.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patching network\crypto.py...')
with open(r'network\crypto.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'from core.i18n import _' not in content:
    if 'import ' in content:
        content = content.replace('import os', 'import os\nfrom core.i18n import _', 1)
    else:
        content = 'from core.i18n import _\n' + content

# Context: raise ValueError(_("Dữ liệu mã hóa không hợp lệ (kích thước quá nhỏ)"))
content = content.replace(_('_("Dữ liệu mã hóa không hợp lệ (kích thước quá nhỏ)")'), _('_("Dữ liệu mã hóa không hợp lệ (kích thước quá nhỏ)")'))
# Context: raise last_err if last_err else ValueError(_("Không giải mã được với bất kỳ mật khẩu nào"))
content = content.replace(_('_("Không giải mã được với bất kỳ mật khẩu nào")'), _('_("Không giải mã được với bất kỳ mật khẩu nào")'))

with open(r'network\crypto.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patching utils\clipboard_api.py...')
with open(r'utils\clipboard_api.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'from core.i18n import _' not in content:
    if 'import ' in content:
        content = content.replace('import os', 'import os\nfrom core.i18n import _', 1)
    else:
        content = 'from core.i18n import _\n' + content

# TODO MANUAL F-STRING: [set_dword_data] Thất bại SetClipboardData cho format {cf_format}
# Context: msg = f"[set_dword_data] Thất bại SetClipboardData cho format {cf_format}_("
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: [set_dword_data] Đã thiết lập format {cf_format} = {value}
# Context: msg = f")[set_dword_data] Đã thiết lập format {cf_format} = {value}_("
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: [set_dword_data] GlobalLock thất bại cho format {cf_format}
# Context: msg = f")[set_dword_data] GlobalLock thất bại cho format {cf_format}_("
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: [set_dword_data] GlobalAlloc thất bại cho format {cf_format}
# Context: msg = f")[set_dword_data] GlobalAlloc thất bại cho format {cf_format}_("
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: [set_dword_data] Lỗi thiết lập format {cf_format}: {e}
# Context: msg = f")[set_dword_data] Lỗi thiết lập format {cf_format}: {e}_("
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: [setup_clipboard_exclusions] Lỗi: {e}
# Context: msg = f")[setup_clipboard_exclusions] Lỗi: {e}_("
# content = content.replace(..., ...)

with open(r'utils\clipboard_api.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patching utils\file_manager.py...')
with open(r'utils\file_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'from core.i18n import _' not in content:
    if 'import ' in content:
        content = content.replace('import os', 'import os\nfrom core.i18n import _', 1)
    else:
        content = 'from core.i18n import _\n' + content

# TODO MANUAL F-STRING: P2P Remote Desktop - Trình Quản Lý Tệp (File Manager){host_title}
# Context: top.title(f")P2P Remote Desktop - Trình Quản Lý Tệp (File Manager){host_title}")
# content = content.replace(..., ...)
# Context: tk.Label(left_frame, text="Máy của bạn (Local)", font=("Segoe UI", 10, "bold"), bg="#E5E5E5").pack()
content = content.replace(_('_("Máy của bạn (Local)")'), _('_("Máy của bạn (Local)")'))
# Context: local_tree.insert("", "end", text=d, values=("", _("Ổ đĩa"), 0))
content = content.replace(_('_("Ổ đĩa")'), _('_("Ổ đĩa")'))
# Context: local_tree.insert("", "end", text=d, values=("", _("Thư mục")))
content = content.replace(_('_("Thư mục")'), _('_("Thư mục")'))
# Context: local_tree.insert("", "end", text=f, values=(format_size(size), _("Tệp"), size))
content = content.replace(_('_("Tệp")'), _('_("Tệp")'))
# Context: tk.Button(local_nav, text=_("⬆ Lên"), command=go_up_local).pack(side=tk.LEFT)
content = content.replace(_('_("⬆ Lên")'), _('_("⬆ Lên")'))
# Context: tk.Button(local_nav, text=_("Đi"), command=refresh_local).pack(side=tk.LEFT)
content = content.replace(_('_("Đi")'), _('_("Đi")'))
# Context: local_tree.heading("#0", text=_("Tên"))
content = content.replace(_('_("Tên")'), _('_("Tên")'))
# Context: local_tree.heading("size", text=_("Kích thước"))
content = content.replace(_('_("Kích thước")'), _('_("Kích thước")'))
# Context: local_tree.heading("type", text=_("Loại"))
content = content.replace(_('_("Loại")'), _('_("Loại")'))
# Context: is_dir = (len(vals) > 1 and vals[1] in (_("Thư mục"), _("Ổ đĩa")))
content = content.replace(_('_("Thư mục")'), _('_("Thư mục")'))
# Context: is_dir = (len(vals) > 1 and vals[1] in (_("Thư mục"), _("Ổ đĩa")))
content = content.replace(_('_("Ổ đĩa")'), _('_("Ổ đĩa")'))
# Context: new_name = simpledialog.askstring(_("Thư mục mới"), _("Nhập tên thư mục mới:"), parent=top)
content = content.replace(_('_("Thư mục mới")'), _('_("Thư mục mới")'))
# Context: new_name = simpledialog.askstring(_("Thư mục mới"), _("Nhập tên thư mục mới:"), parent=top)
content = content.replace(_('_("Nhập tên thư mục mới:")'), _('_("Nhập tên thư mục mới:")'))
# Context: messagebox.showinfo(_("Lỗi"), f'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"', parent=top)
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: messagebox.showinfo(_("Lỗi"), f'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"', parent=top)
# Context: messagebox.showinfo(_("Lỗi"), f'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"', parent=top)
content = content.replace(_('_(" đã tồn tại trên ")'), _('_(" đã tồn tại trên ")'))
# Context: msg = f"Bạn có chắc muốn xóa '{local_tree.item(sel[0])['text']}_(' không?"
# Context: msg = f"Bạn có chắc muốn xóa '){local_tree.item(sel[0])['text']}_(' không?"
# TODO MANUAL F-STRING: Bạn có chắc muốn xóa {len(sel)} mục đã chọn không?
# Context: msg = f"Bạn có chắc muốn xóa {len(sel)} mục đã chọn không?"
# content = content.replace(..., ...)
# Context: confirm = messagebox.askyesno("Xác nhận", msg, parent=top)
content = content.replace(_(')_("Xác nhận")'), _('_(_("Xác nhận"))_('))
# Context: is_dir = (len(vals) > 1 and vals[1] == "Thư mục")
content = content.replace(_(')_("Thư mục")'), _('_(_("Thư mục"))_('))
# Context: messagebox.showerror("Lỗi", _("Lỗi xóa ") + str(name) + ": " + str(e), parent=top)
content = content.replace(_(')_("Lỗi")'), _('_(_("Lỗi"))_('))
# TODO MANUAL F-STRING: Lỗi xóa {name}: {e}
# Context: messagebox.showerror("Lỗi", _("Lỗi xóa ") + str(name) + ": " + str(e), parent=top)
# content = content.replace(..., ...)
# Context: is_dir = (len(vals) > 1 and vals[1] == "Thư mục")
content = content.replace(_(')_("Thư mục")'), _('_(_("Thư mục"))_('))
# Context: messagebox.showwarning("Cảnh báo", f"Không thể xem thư mục '){name}_(' bằng Notepad!", parent=top)
content = content.replace(_(')_("Cảnh báo")'), _('_(_("Cảnh báo"))_('))
# Context: messagebox.showwarning("Cảnh báo", f"Không thể xem thư mục '){name}_(' bằng Notepad!", parent=top)
# Context: messagebox.showwarning("Cảnh báo", f"Không thể xem thư mục '){name}_(' bằng Notepad!", parent=top)
# TODO MANUAL F-STRING: Soạn thảo (Local) - {name}
# Context: np_win.title(_("Soạn thảo (Local) - ") + str(name))
# content = content.replace(..., ...)
# Context: messagebox.showinfo("Thành công", "Đã lưu tệp!", parent=win)
content = content.replace(_(')_("Thành công")'), _('_(_("Thành công"))_('))
# Context: messagebox.showinfo("Thành công", "Đã lưu tệp!", parent=win)
content = content.replace(_(')_("Đã lưu tệp!")'), _('_("Đã lưu tệp!")'))
# Context: messagebox.showerror("Lỗi", _("Không thể lưu: ") + str(e), parent=win)
content = content.replace(_('_("Lỗi")'), _('_(_("Lỗi"))_('))
# TODO MANUAL F-STRING: Không thể lưu: {e}
# Context: messagebox.showerror("Lỗi", _("Không thể lưu: ") + str(e), parent=win)
# content = content.replace(..., ...)
# Context: tk.Button(np_win, text="Lưu", command=make_save(full_path, text_area, np_win), bg="green", fg="white", font=("Arial", 10, "bold")).pack(pady=5)
content = content.replace(_(')_("Lưu")'), _('_(_("Lưu"))_('))
# Context: messagebox.showerror("Lỗi", str(ex), parent=top)
content = content.replace(_(')_("Lỗi")'), _('_(_("Lỗi"))_('))
# Context: messagebox.showerror("Lỗi", str(e), parent=top)
content = content.replace(_(')_("Lỗi")'), _('_(_("Lỗi"))_('))
# Context: new_name = simpledialog.askstring("Đổi tên", f"Nhập tên mới cho '){name}':", initialvalue=name, parent=top)
content = content.replace(_('_("Đổi tên")'), _('_(_("Đổi tên"))_('))
# Context: new_name = simpledialog.askstring("Đổi tên", f"Nhập tên mới cho '){name}_(':", initialvalue=name, parent=top)
# Context: messagebox.showerror("Lỗi", str(e), parent=top)
content = content.replace(_(')_("Lỗi")'), _('_(_("Lỗi"))_('))
# Context: messagebox.showerror("Lỗi", str(outer_e), parent=top)
content = content.replace(_(')_("Lỗi")'), _('_(_("Lỗi"))_('))
# Context: local_menu.add_command(label="Tạo thư mục mới", command=lambda: local_action("mkdir"))
content = content.replace(_(')_("Tạo thư mục mới")'), _('_(_("Tạo thư mục mới"))_('))
# Context: local_menu.add_command(label="Làm mới", command=refresh_local)
content = content.replace(_(')_("Làm mới")'), _('_(_("Làm mới"))_('))
# Context: is_dir = (len(vals) > 1 and vals[1] == "Thư mục")
content = content.replace(_(')_("Thư mục")'), _('_(_("Thư mục"))_('))
# Context: local_menu.add_command(label="Tạo thư mục mới", command=lambda: local_action("mkdir"))
content = content.replace(_(')_("Tạo thư mục mới")'), _('_(_("Tạo thư mục mới"))_('))
# Context: local_menu.add_command(label="Đổi tên", command=lambda: local_action("rename"))
content = content.replace(_(')_("Đổi tên")'), _('_(_("Đổi tên"))_('))
# Context: local_menu.add_command(label="Xóa", command=lambda: local_action("delete"))
content = content.replace(_(')_("Xóa")'), _('_(_("Xóa"))_('))
# Context: tk.Label(right_frame, text="Máy điều khiển (Remote Host)", font=("Segoe UI", 10, "bold"), bg="#E5E5E5").pack()
content = content.replace(_(')_("Máy điều khiển (Remote Host)")'), _('_("Máy điều khiển (Remote Host)")'))
# Context: remote_tree.insert("", "end", text=d.get("name"), values=("", _("Thư mục")))
content = content.replace(_('_("Thư mục")'), _('_("Thư mục")'))
# Context: remote_tree.insert("", "end", text=f.get("name"), values=(format_size(sz), _("Tệp"), sz))
content = content.replace(_('_("Tệp")'), _('_("Tệp")'))
# Context: messagebox.showerror(_("Lỗi"), error or _("Thao tác thất bại"), parent=top)
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: messagebox.showerror(_("Lỗi"), error or _("Thao tác thất bại"), parent=top)
content = content.replace(_('_("Thao tác thất bại")'), _('_("Thao tác thất bại")'))
# TODO MANUAL F-STRING: Soạn thảo (Remote) - {name}
# Context: np_win.title(_("Soạn thảo (Remote) - ") + str(name))
# content = content.replace(..., ...)
# Context: messagebox.showerror("Lỗi Code", _("Lỗi tạo Notepad: ") + str(ex), parent=top)
content = content.replace(_('_("Lỗi Code")'), _('_(_("Lỗi Code"))_('))
# TODO MANUAL F-STRING: Lỗi tạo Notepad: {ex}
# Context: messagebox.showerror("Lỗi Code", _("Lỗi tạo Notepad: ") + str(ex), parent=top)
# content = content.replace(..., ...)
# Context: messagebox.showinfo("Thông báo", "Đã gửi yêu cầu lưu tệp tới thiết bị điều khiển.", parent=np_win)
content = content.replace(_(')_("Thông báo")'), _('_(_("Thông báo"))_('))
# Context: messagebox.showinfo("Thông báo", "Đã gửi yêu cầu lưu tệp tới thiết bị điều khiển.", parent=np_win)
content = content.replace(_(')_("Đã gửi yêu cầu lưu tệp tới thiết bị điều khiển.")'), _('_("Đã gửi yêu cầu lưu tệp tới thiết bị điều khiển.")'))
# Context: tk.Button(np_win, text="Lưu", command=save_remote_file, bg="green", fg="white", font=("Arial", 10, "bold")).pack(pady=5)
content = content.replace(_('_("Lưu")'), _('_("Lưu")'))
# Context: messagebox.showerror(_("Lỗi"), event.get("error", _("Không thể đọc tệp")), parent=top)
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: messagebox.showerror(_("Lỗi"), event.get("error", _("Không thể đọc tệp")), parent=top)
content = content.replace(_('_("Không thể đọc tệp")'), _('_("Không thể đọc tệp")'))
# Context: messagebox.showerror(_("Lỗi"), event.get("error", _("Lỗi lưu tệp từ xa")), parent=top)
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: messagebox.showerror(_("Lỗi"), event.get("error", _("Lỗi lưu tệp từ xa")), parent=top)
content = content.replace(_('_("Lỗi lưu tệp từ xa")'), _('_("Lỗi lưu tệp từ xa")'))
# Context: tk.Button(remote_nav, text=_("⬆ Lên"), command=go_up_remote).pack(side=tk.LEFT)
content = content.replace(_('_("⬆ Lên")'), _('_("⬆ Lên")'))
# Context: tk.Button(remote_nav, text=_("Đi"), command=lambda: request_remote_dir(remote_entry.get())).pack(side=tk.LEFT)
content = content.replace(_('_("Đi")'), _('_("Đi")'))
# Context: remote_tree.heading("#0", text=_("Tên"))
content = content.replace(_('_("Tên")'), _('_("Tên")'))
# Context: remote_tree.heading("size", text=_("Kích thước"))
content = content.replace(_('_("Kích thước")'), _('_("Kích thước")'))
# Context: remote_tree.heading("type", text=_("Loại"))
content = content.replace(_('_("Loại")'), _('_("Loại")'))
# Context: is_dir = (len(vals) > 1 and vals[1] == _("Thư mục"))
content = content.replace(_('_("Thư mục")'), _('_("Thư mục")'))
# Context: new_name = simpledialog.askstring(_("Thư mục mới"), _("Nhập tên thư mục mới:"), parent=top)
content = content.replace(_('_("Thư mục mới")'), _('_("Thư mục mới")'))
# Context: new_name = simpledialog.askstring(_("Thư mục mới"), _("Nhập tên thư mục mới:"), parent=top)
content = content.replace(_('_("Nhập tên thư mục mới:")'), _('_("Nhập tên thư mục mới:")'))
# Context: messagebox.showinfo(_("Lỗi"), f'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"', parent=top)
content = content.replace(_('_("Lỗi")'), _('_("Lỗi")'))
# Context: messagebox.showinfo(_("Lỗi"), f'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"', parent=top)
# Context: messagebox.showinfo(_("Lỗi"), f'Thư mục "{new_name}" đã tồn tại trên "{current_dir}"', parent=top)
content = content.replace(_('_(" đã tồn tại trên ")'), _('_(" đã tồn tại trên ")'))
# Context: msg = f"Bạn có chắc muốn xóa '{remote_tree.item(sel[0])['text']}_(' khỏi máy điều khiển không?"
# Context: msg = f"Bạn có chắc muốn xóa '){remote_tree.item(sel[0])['text']}_(' khỏi máy điều khiển không?"
# TODO MANUAL F-STRING: Bạn có chắc muốn xóa {len(sel)} mục đã chọn khỏi máy điều khiển không?
# Context: msg = f"Bạn có chắc muốn xóa {len(sel)} mục đã chọn khỏi máy điều khiển không?"
# content = content.replace(..., ...)
# Context: confirm = messagebox.askyesno("Xác nhận", msg, parent=top)
content = content.replace(_(')_("Xác nhận")'), _('_(_("Xác nhận"))_('))
# Context: is_dir = (len(vals) > 1 and vals[1] == "Thư mục")
content = content.replace(_(')_("Thư mục")'), _('_(_("Thư mục"))_('))
# Context: messagebox.showwarning("Cảnh báo", f"Không thể xem thư mục '){name}_(' bằng Notepad!", parent=top)
content = content.replace(_(')_("Cảnh báo")'), _('_(_("Cảnh báo"))_('))
# Context: messagebox.showwarning("Cảnh báo", f"Không thể xem thư mục '){name}_(' bằng Notepad!", parent=top)
# Context: messagebox.showwarning("Cảnh báo", f"Không thể xem thư mục '){name}_(' bằng Notepad!", parent=top)
# Context: messagebox.showinfo("Thông báo", _("Đã gửi yêu cầu mở file ") + str(ext) + _(" bằng ứng dụng mặc định trên máy bị điều khiển."), parent=top)
content = content.replace(_(')_("Thông báo")'), _('_(_("Thông báo"))_('))
# TODO MANUAL F-STRING: Đã gửi yêu cầu mở file {ext} bằng ứng dụng mặc định trên máy bị điều khiển.
# Context: messagebox.showinfo("Thông báo", _("Đã gửi yêu cầu mở file ") + str(ext) + _(" bằng ứng dụng mặc định trên máy bị điều khiển."), parent=top)
# content = content.replace(..., ...)
# Context: messagebox.showerror("Lỗi", _("Không thể gửi lệnh: ") + str(ex), parent=top)
content = content.replace(_(')_("Lỗi")'), _('_(_("Lỗi"))_('))
# TODO MANUAL F-STRING: Không thể gửi lệnh: {ex}
# Context: messagebox.showerror("Lỗi", _("Không thể gửi lệnh: ") + str(ex), parent=top)
# content = content.replace(..., ...)
# Context: new_name = simpledialog.askstring("Đổi tên", f"Nhập tên mới cho '){name}':", initialvalue=name, parent=top)
content = content.replace(_('_("Đổi tên")'), _('_(_("Đổi tên"))_('))
# Context: new_name = simpledialog.askstring("Đổi tên", f"Nhập tên mới cho '){name}_(':", initialvalue=name, parent=top)
# Context: remote_menu.add_command(label="Tạo thư mục mới", command=lambda: remote_action("mkdir"))
content = content.replace(_(')_("Tạo thư mục mới")'), _('_(_("Tạo thư mục mới"))_('))
# Context: remote_menu.add_command(label="Làm mới", command=lambda: request_remote_dir(remote_entry.get()))
content = content.replace(_(')_("Làm mới")'), _('_(_("Làm mới"))_('))
# Context: is_dir = (len(vals) > 1 and vals[1] == "Thư mục")
content = content.replace(_(')_("Thư mục")'), _('_(_("Thư mục"))_('))
# Context: remote_menu.add_command(label="Tạo thư mục mới", command=lambda: remote_action("mkdir"))
content = content.replace(_(')_("Tạo thư mục mới")'), _('_(_("Tạo thư mục mới"))_('))
# Context: remote_menu.add_command(label="Đổi tên", command=lambda: remote_action("rename"))
content = content.replace(_(')_("Đổi tên")'), _('_(_("Đổi tên"))_('))
# Context: remote_menu.add_command(label="Xóa", command=lambda: remote_action("delete"))
content = content.replace(_(')_("Xóa")'), _('_(_("Xóa"))_('))
# Context: tk.Label(title_bar, text="Xác nhận", bg="#F3F3F3", fg="#333333", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT, padx=10, pady=5)
content = content.replace(_(')_("Xác nhận")'), _('_(_("Xác nhận"))_('))
# Context: item_type = "Thư mục" if c.get(')src_is_dir') else _("Tập tin")
content = content.replace(_('_("Thư mục")'), _('_("Thư mục")'))
# Context: item_type = _("Thư mục") if c.get('src_is_dir') else _("Tập tin")
content = content.replace(_('_("Tập tin")'), _('_("Tập tin")'))
# TODO MANUAL F-STRING: {item_type} với tên \
# Context: lbl_title = tk.Label(frame, text=f"{item_type} với tên \_("{c['name']}\" đã tồn tại."), font=("Segoe UI", 11, "bold"), bg="white", anchor="w")
# content = content.replace(..., ...)
# Context: lbl_title = tk.Label(frame, text=f"{item_type} với tên \_("{c['name']}\" đã tồn tại."), font=("Segoe UI", 11, "bold"), bg="white", anchor="w")
content = content.replace(_('_(" đã tồn tại.")'), _('_(" đã tồn tại.")'))
# Context: src_path = c.get('src_path', _('Không rõ'))
content = content.replace(''Không rõ'', '_('Không rõ')')
# Context: dst_path = c.get('dst_path', _('Không rõ'))
content = content.replace(''Không rõ'', '_('Không rõ')')
# Context: src_mtime = c.get('src_mtime', _('Không xác định'))
content = content.replace(''Không xác định'', '_(_('Không xác định'))')
# Context: dst_mtime = c.get('dst_mtime', _('Không xác định'))
content = content.replace(''Không xác định'', '_(_('Không xác định'))_(')
# Context: src_title = "Nguồn (Máy bạn):"
content = content.replace(_(')_("Nguồn (Máy bạn):")'), _('_("Nguồn (Máy bạn):")'))
# Context: dst_title = "Đích (Máy từ xa):"
content = content.replace(_('_("Đích (Máy từ xa):")'), _('_("Đích (Máy từ xa):")'))
# Context: src_title = "Nguồn (Máy từ xa):"
content = content.replace(_('_("Nguồn (Máy từ xa):")'), _('_("Nguồn (Máy từ xa):")'))
# Context: dst_title = "Đích (Máy bạn):"
content = content.replace(_('_("Đích (Máy bạn):")'), _('_("Đích (Máy bạn):_(")'))
# TODO MANUAL F-STRING: {src_title}\n- Thư mục: {src_path}\n- Dung lượng: {src_sz}\n- Ngày sửa đổi: {src_mtime}
# Context: src_disp = f"){src_title}\n- Thư mục: {src_path}\n- Dung lượng: {src_sz}\n- Ngày sửa đổi: {src_mtime}_("
# content = content.replace(..., ...)
# TODO MANUAL F-STRING: {dst_title}\n- Thư mục: {dst_path}\n- Dung lượng: {dst_sz}\n- Ngày sửa đổi: {dst_mtime}
# Context: dst_disp = f"){dst_title}\n- Thư mục: {dst_path}\n- Dung lượng: {dst_sz}\n- Ngày sửa đổi: {dst_mtime}"
# content = content.replace(..., ...)
# Context: tk.Label(frame, text="Bạn muốn làm gì?", font=("Segoe UI", 10, "bold"), bg="white", anchor="w").pack(fill="x", padx=20, pady=(5, 15))
content = content.replace(_('_("Bạn muốn làm gì?")'), _('_("Bạn muốn làm gì?")'))
# Context: btn_cancel = tk.Button(btn_frame, text=_("Hủy"), font=("Segoe UI", 10, "bold"), bg="#e0e0e0", fg="black", width=8, relief="raised", borderwidth=2, comman
content = content.replace(_('_("Hủy")'), _('_("Hủy")'))
# Context: btn_skip = tk.Button(btn_frame, text=_("Bỏ qua"), font=("Segoe UI", 10), bg="#e0e0e0", fg="black", width=10, relief="raised", borderwidth=2, command=lamb
content = content.replace(_('_("Bỏ qua")'), _('_("Bỏ qua")'))
# Context: btn_ow = tk.Button(btn_frame, text=_("Ghi đè"), font=("Segoe UI", 10), bg="#e0e0e0", fg="black", width=10, relief="raised", borderwidth=2, command=lambda
content = content.replace(_('_("Ghi đè")'), _('_("Ghi đè")'))
# Context: btn_ow_all = tk.Button(btn_frame, text=_("Ghi đè toàn bộ"), font=("Segoe UI", 10, "bold"), bg="#e0e0e0", fg="black", width=15, relief="raised", borderwid
content = content.replace(_('_("Ghi đè toàn bộ")'), _('_("Ghi đè toàn bộ")'))
# Context: is_dir = True if len(vals) > 1 and vals[1] == _("Thư mục") else False
content = content.replace(_('_("Thư mục")'), _('_("Thư mục")'))
# Context: except: mtime = _("Không xác định")
content = content.replace(_('_("Không xác định")'), _('_("Không xác định")'))
# TODO MANUAL F-STRING:  và {len(items_to_upload)-1} mục khác
# Context: display_name += _(" và ") + str(len(items_to_upload)-1) + _(" mục khác")
# content = content.replace(..., ...)
# Context: src_is_dir = True if len(vals) > 1 and vals[1] == _("Thư mục") else False
content = content.replace(_('_("Thư mục")'), _('_("Thư mục")'))
# Context: except: mtime = _("Không xác định")
content = content.replace(_('_("Không xác định")'), _('_("Không xác định")'))
# Context: src_is_dir = True if len(vals) > 1 and vals[1] == _("Thư mục") else False
content = content.replace(_('_("Thư mục")'), _('_("Thư mục")'))
# TODO MANUAL F-STRING:  và {len(display_names)-1} mục khác
# Context: display_name += _(" và ") + str(len(display_names)-1) + _(" mục khác")
# content = content.replace(..., ...)
# Context: tk.Button(mid_frame, text=_("Chuyển qua\n>>"), font=("Segoe UI", 10, "bold"), bg="#2196F3", fg="white", width=10, command=do_upload).pack(pady=(100, 10))
content = content.replace(_('"Chuyển qua\\n>>"'), _('_("Chuyển qua\\n>>")'))
# Context: tk.Button(mid_frame, text=_("Nhận về\n<<"), font=("Segoe UI", 10, "bold"), bg="#4CAF50", fg="white", width=10, command=do_download).pack(pady=10)
content = content.replace(_('"Nhận về\\n<<"'), _('_("Nhận về\\n<<")'))
# Context: ctypes.windll.user32.MessageBoxW(0, err, _("Lỗi File Manager"), 0x10)
content = content.replace(_('_("Lỗi File Manager")'), _('_("Lỗi File Manager")'))

with open(r'utils\file_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

