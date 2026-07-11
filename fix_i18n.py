import re

with open('d:/Data/AG/remote_desktop/core/network_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

reps = [
    (r'self\.update_status\(_\("Đã gửi Wake-On-Lan tới MAC "\) \+ str\(m\)\)', r'self.update_status(_("Đã gửi Wake-On-Lan tới MAC {mac}").format(mac=m))'),
    (r'self\.update_status\(_\("Đang kết nối LAN trực tiếp tới "\) \+ str\(peer_info\[\'computer_name\'\]\) \+ "\.\.\."\)', r'self.update_status(_("Đang kết nối LAN trực tiếp tới {name}...").format(name=peer_info[\'computer_name\']))'),
    (r'self\.after\(0, lambda: self\.show_custom_error\(_\("Lỗi kết nối LAN"\), _\("Không thể kết nối tới "\) \+ str\(peer_info\[\'computer_name\'\]\) \+ " \(" \+ str\(ip\) \+ ":" \+ str\(port\) \+ _\("\)\\nKiểm tra Tường lửa \(Firewall\) hoặc đảm bảo máy đích đang chạy ứng dụng\."\)\)\)', r'self.after(0, lambda: self.show_custom_error(_("Lỗi kết nối LAN"), _("Không thể kết nối tới {name} ({ip}:{port}).\nKiểm tra Tường lửa (Firewall) hoặc đảm bảo máy đích đang chạy ứng dụng.").format(name=peer_info[\'computer_name\'], ip=ip, port=port)))'),
    (r'self\.after\(0, lambda: self\.show_custom_error\(_\("Từ chối kết nối"\), f"Kết nối bị từ chối:\\n\{msg\}"\)\)', r'self.after(0, lambda: self.show_custom_error(_("Từ chối kết nối"), _("Kết nối bị từ chối:\n{msg}").format(msg=msg)))'),
    (r'self\.after\(0, lambda err=str\(e\): self\.show_custom_error\(_\("Lỗi bắt tay LAN"\), f"Lỗi xác thực handshake:\\n\{err\}"\)\)', r'self.after(0, lambda err=str(e): self.show_custom_error(_("Lỗi bắt tay LAN"), _("Lỗi xác thực handshake:\n{err}").format(err=err)))'),
    (r'self\.update_status\(f"Đang kết nối tới các Signaling Server\.\.\."\)', r'self.update_status(_("Đang kết nối tới các Signaling Server..."))'),
    (r'self\.update_status\(_\("Đang kết nối Signaling Server\.\.\. \("\) \+ str\(8 - int\(timeout\)\) \+ "s\)"\)', r'self.update_status(_("Đang kết nối Signaling Server... ({sec}s)").format(sec=8 - int(timeout)))'),
    (r'self\.update_status\(_\("Kết nối Signaling & Mở cổng Router thành công \(Cổng "\) \+ str\(BOUND_PORT\) \+ "\)!" \+ suffix\)', r'self.update_status(_("Kết nối Signaling & Mở cổng Router thành công (Cổng {port})!{suffix}").format(port=BOUND_PORT, suffix=suffix))'),
    (r'self\.update_status\(_\("Kết nối Signaling thành công \(Cổng "\) \+ str\(BOUND_PORT\) \+ _\("\)! Sẵn sàng kết nối\."\) \+ suffix\)', r'self.update_status(_("Kết nối Signaling thành công (Cổng {port})! Sẵn sàng kết nối.{suffix}").format(port=BOUND_PORT, suffix=suffix))'),
    (r'self\.update_status\(_\("Chưa kết nối Signaling Server\. Đang thử lại ở chế độ nền\.\.\. "\) \+ suffix\)', r'self.update_status(_("Chưa kết nối Signaling Server. Đang thử lại ở chế độ nền... {suffix}").format(suffix=suffix))'),
    (r'self\.update_status\(f"Đang hiển thị cửa sổ điều khiển đã kết nối của \{partner_id\}\.\.\."\)', r'self.update_status(_("Đang hiển thị cửa sổ điều khiển đã kết nối của {partner_id}...").format(partner_id=partner_id))'),
    (r'self\.update_status\(f"Mất kết nối\. Đang thử kết nối lại lần \{retry_count \+ 1\}/30\.\.\."\)', r'self.update_status(_("Mất kết nối. Đang thử kết nối lại lần {count}/30...").format(count=retry_count + 1))'),
    (r'self\.update_status\(f"Đang quét kết nối nội bộ \(LAN\)\.\.\."\)', r'self.update_status(_("Đang quét kết nối nội bộ (LAN)..."))'),
    (r'self\.update_status\(f"Đang đục lỗ Tường lửa \(TCP Hole Punching\) tới \{public_ip\}:\{port\}\.\.\."\)', r'self.update_status(_("Đang đục lỗ Tường lửa (TCP Hole Punching) tới {ip}:{port}...").format(ip=public_ip, port=port))'),
    (r'status_text = f"Đo tốc độ \(Lớn nhất 2 lần\): Ping \{avg_ping:\.1f\}ms, Băng thông \{bandwidth:\.2f\} Mbps\. Chất lượng: \{net_class_viet\}\."', r'status_text = _("Đo tốc độ (Lớn nhất 2 lần): Ping {ping:.1f}ms, Băng thông {bw:.2f} Mbps. Chất lượng: {quality}.").format(ping=avg_ping, bw=bandwidth, quality=net_class_viet)'),
    (r'self\.after\(0, lambda err=str\(e\): self\.show_custom_error\(_\("Lỗi bắt tay"\), f"Lỗi xác thực handshake:\\n\{err\}"\)\)', r'self.after(0, lambda err=str(e): self.show_custom_error(_("Lỗi bắt tay"), _("Lỗi xác thực handshake:\n{err}").format(err=err)))'),
    (r'self\.after\(0, lambda: self\.update_status\(f"Đang tự động kết nối lại\.\.\."\)\)', r'self.after(0, lambda: self.update_status(_("Đang tự động kết nối lại...")))')
]

for old, new in reps:
    content = re.sub(old, new, content)

with open('d:/Data/AG/remote_desktop/core/network_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done replacing network manager strings")
