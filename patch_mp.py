import os
import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update run_client_viewer_loop signature and body
old_loop_sig = 'def run_client_viewer_loop(app_instance, sock, host_w, host_h, computer_name=""):\\n    global client_latest_frame, client_running\\n    client_latest_frame = None\\n    client_running = True'
new_loop_sig = '''def run_client_viewer_loop(sock, host_w, host_h, computer_name=""):
    global client_latest_frame, client_running
    client_latest_frame = None
    client_running = True
    
    import tkinter as tk
    hidden_root = tk.Tk()
    hidden_root.withdraw()
    clipboard_sync_manager.register_app(hidden_root)'''
content = content.replace(old_loop_sig, new_loop_sig)

old_update = '''        # Cập nhật event loop của Tkinter để tránh đứng hình dialog tiến trình
        try:
            app_instance.update()
        except Exception:
            pass'''
new_update = '''        # Cập nhật event loop của Tkinter ẩn để các hộp thoại (dialog truyền file) vẫn hoạt động trong subprocess
        try:
            hidden_root.update()
        except Exception:
            pass'''
content = content.replace(old_update, new_update)

# 2. Update click_connect to remove the block
block_check = '''    def click_connect(self):
        if self.is_client_connected:
            self.show_custom_error(_("Cảnh báo"), "Bạn đang điều khiển một máy tính khác!\\n\\nVui lòng đóng cửa sổ điều khiển hiện tại trước khi kết nối tới máy mới (mỗi giao diện chỉ hỗ trợ mở 1 cửa sổ điều khiển).")
            return
            
        partner_id = self.partner_id_var.get().strip().replace(" ", "")'''
new_click_connect = '''    def click_connect(self):
        partner_id = self.partner_id_var.get().strip().replace(" ", "")'''
content = content.replace(block_check, new_click_connect)

# 3. Update launch_pygame_viewer to use multiprocessing
old_launch = '''    def launch_pygame_viewer(self, sock, host_w, host_h, computer_name=""):
        # Không ẩn cửa sổ chính nữa để người dùng vẫn thấy giao diện
        # self.withdraw()
        
        self.is_client_connected = True
        try:
            run_client_viewer_loop(self, sock, host_w, host_h, computer_name)
        except Exception as e:
            print(f"[Client] Exception in viewer loop: {e}")
        finally:
            self.is_client_connected = False
            try:
                sock.close()
            except:
                pass
            self.connect_btn.config(state=tk.NORMAL)
            partner_id = self.partner_id_var.get().strip().replace(" ", "")
            disconnect_msg = f"Đã đóng kết nối với đối tác {partner_id}"
            if computer_name:
                disconnect_msg += f" ({computer_name})"
            print(f"[Client] {disconnect_msg}.")
            self.update_status(f"{disconnect_msg} lúc {time.strftime('%H:%M:%S')} (Sẵn sàng kết nối)")'''

new_launch = '''    def launch_pygame_viewer(self, sock, host_w, host_h, computer_name=""):
        try:
            import multiprocessing as mp
            p = mp.Process(target=run_client_viewer_loop, args=(sock, host_w, host_h, computer_name), daemon=True)
            p.start()
            
            # Đóng bản sao socket ở tiến trình mẹ để tiến trình con toàn quyền sử dụng
            try: sock.close()
            except: pass
            
            self.connect_btn.config(state=tk.NORMAL)
            self.update_status(_("Đã mở một cửa sổ điều khiển mới (Sẵn sàng kết nối)"))
            print(f"[Client] Đã mở tiến trình điều khiển cho {computer_name or 'đối tác'}")
            
        except Exception as e:
            print(f"[Client] Lỗi khởi chạy tiến trình điều khiển: {e}")
            self.connect_btn.config(state=tk.NORMAL)
            try: sock.close()
            except: pass'''
content = content.replace(old_launch, new_launch)

# 4. Add mp.freeze_support() at the bottom
old_main = '''if __name__ == '__main__':
    app = UnifiedApp()
    app.mainloop()'''

new_main = '''if __name__ == '__main__':
    import multiprocessing as mp
    mp.freeze_support()
    app = UnifiedApp()
    app.mainloop()'''
content = content.replace(old_main, new_main)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Multiprocessing patch applied successfully.")
