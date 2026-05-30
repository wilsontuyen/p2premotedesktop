import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace setup_delayed_rendering and _execute_setup_delayed_rendering with handle_shnotify_create and setup_virtual_files
old_methods = '''    def setup_delayed_rendering(self):
        log_debug(f"[setup_delayed_rendering] Bắt đầu. self.listener={self.listener}")
        if self.listener and self.listener.hwnd:
            ctypes.windll.user32.PostMessageW(ctypes.c_void_p(self.listener.hwnd), 0x0400 + 101, 0, 0)
            log_debug("[setup_delayed_rendering] Đã PostMessageW WM_SETUP_DELAYED_RENDERING")
        else:
            log_debug("[setup_delayed_rendering] Lỗi: listener hoặc hwnd chưa sẵn sàng.")

    def _execute_setup_delayed_rendering(self):
        if not self.listener or not self.listener.hwnd:
            log_debug("[_execute_setup_delayed_rendering] Lỗi: hwnd chưa sẵn sàng.")
            return
            
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        opened = False
        log_debug(f"[_execute_setup_delayed_rendering] Đang cố gắng OpenClipboard với HWND: {self.listener.hwnd}")
        for _ in range(10):
            if user32.OpenClipboard(ctypes.c_void_p(self.listener.hwnd)):
                opened = True
                break
            time.sleep(0.05)
            
        if opened:
            log_debug("[_execute_setup_delayed_rendering] OpenClipboard thành công. Đang EmptyClipboard...")
            self.ignore_destroy_clipboard = True
            try:
                user32.EmptyClipboard()
            finally:
                self.ignore_destroy_clipboard = False
                
            # Đăng ký các format để tránh Clipboard History / Cloud Clipboard tự động quét gây mất delayed rendering
            cf_exclude = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
            cf_history = user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")
            cf_cloud = user32.RegisterClipboardFormatW("CanUploadToCloudClipboard")
            
            def set_dword_data(cf_format, value):
                hMem = kernel32.GlobalAlloc(0x0002, 4) # GMEM_MOVEABLE = 0x0002
                if hMem:
                    ptr = kernel32.GlobalLock(hMem)
                    if ptr:
                        ctypes.memmove(ptr, ctypes.byref(wintypes.DWORD(value)), 4)
                        kernel32.GlobalUnlock(hMem)
                        if not user32.SetClipboardData(cf_format, hMem):
                            kernel32.GlobalFree(hMem)
                            log_debug(f"[set_dword_data] Thất bại SetClipboardData cho format {cf_format}")
                        else:
                            log_debug(f"[set_dword_data] Đã thiết lập format {cf_format} = {value}")
                    else:
                        kernel32.GlobalFree(hMem)
                else:
                    log_debug("[set_dword_data] GlobalAlloc thất bại")
                            
            if cf_exclude: set_dword_data(cf_exclude, 1)
            if cf_history: set_dword_data(cf_history, 0)
            if cf_cloud: set_dword_data(cf_cloud, 0)
            
            res = fn_SetClipboardData(15, None) # CF_HDROP với delayed rendering (None handle)
            err = ctypes.GetLastError()
            log_debug(f"[_execute_setup_delayed_rendering] SetClipboardData CF_HDROP trả về: {res}, GetLastError: {err}")
            user32.CloseClipboard()
            print("[Clipboard] Đã thiết lập delayed rendering (CF_HDROP) trên Clipboard và loại trừ Clipboard History.")
        else:
            err = ctypes.GetLastError()
            log_debug(f"[_execute_setup_delayed_rendering] OpenClipboard THẤT BẠI. GetLastError: {err}")
            print("[Clipboard] Không thể OpenClipboard để thiết lập delayed rendering.")'''

new_methods = '''    def handle_shnotify_create(self, path):
        import os
        import json
        if not self.pending_remote_files: return
        if getattr(self, "is_paste_triggered", False): return # Already downloading
        
        fname = os.path.basename(path)
        matching = False
        for m in self.pending_remote_files:
            if m["name"] == fname:
                matching = True
                break
                
        if matching:
            print(f"[VirtualStaging] Phát hiện Paste file: {path}")
            self.is_paste_triggered = True
            self.target_save_dir = os.path.dirname(path)
            print(f"[VirtualStaging] Thư mục đích: {self.target_save_dir}. Đang yêu cầu tải file gốc...")
            if self.sock:
                try:
                    pkt = json.dumps({"type": "request_files", "files": [m["path"] for m in self.pending_remote_files]}).encode('utf-8')
                    send_msg(self.sock, pkt)
                except Exception as e:
                    print(f"Lỗi gửi request_files: {e}")

    def setup_virtual_files(self, metadata):
        import os
        import ctypes
        from ctypes import wintypes
        print(f"[VirtualStaging] Đang tạo {len(metadata)} file ảo (0 bytes)...")
        temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers", "VirtualStaging")
        try:
            os.makedirs(temp_dir, exist_ok=True)
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if os.path.isfile(item_path):
                    try: os.remove(item_path)
                    except: pass
        except Exception as e:
            print(f"[VirtualStaging] Lỗi dọn dẹp: {e}")
            
        dummy_paths = []
        for m in metadata:
            fpath = os.path.join(temp_dir, m["name"])
            try:
                with open(fpath, "wb") as f:
                    pass # create empty 0-byte file
                dummy_paths.append(fpath)
            except Exception as e:
                print(f"[VirtualStaging] Lỗi tạo file {fpath}: {e}")
                
        # Nạp các file ảo này vào Clipboard
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            # Format DROPFILES structure
            class DROPFILES(ctypes.Structure):
                _fields_ = [("pFiles", wintypes.DWORD),
                            ("pt", wintypes.POINT),
                            ("fNC", wintypes.BOOL),
                            ("fWide", wintypes.BOOL)]
            
            # Khởi tạo buffer Unicode
            file_buffer = "\\0".join(dummy_paths) + "\\0\\0"
            file_buffer_bytes = file_buffer.encode("utf-16-le")
            
            size = ctypes.sizeof(DROPFILES) + len(file_buffer_bytes)
            hGlobal = kernel32.GlobalAlloc(0x0042, size) # GHND = GMEM_MOVEABLE | GMEM_ZEROINIT
            
            pGlobal = kernel32.GlobalLock(hGlobal)
            dropfiles = DROPFILES()
            dropfiles.pFiles = ctypes.sizeof(DROPFILES)
            dropfiles.fWide = True
            
            ctypes.memmove(pGlobal, ctypes.byref(dropfiles), ctypes.sizeof(DROPFILES))
            ctypes.memmove(pGlobal + ctypes.sizeof(DROPFILES), file_buffer_bytes, len(file_buffer_bytes))
            
            kernel32.GlobalUnlock(hGlobal)
            
            if user32.OpenClipboard(None):
                self.ignore_destroy_clipboard = True
                user32.EmptyClipboard()
                user32.SetClipboardData(15, hGlobal) # 15 is CF_HDROP
                user32.CloseClipboard()
                self.ignore_destroy_clipboard = False
                print(f"[VirtualStaging] Đã đẩy {len(dummy_paths)} file ảo vào Clipboard thành công.")
            else:
                print("[VirtualStaging] Không thể OpenClipboard(None)!")
                kernel32.GlobalFree(hGlobal)
        except Exception as e:
            print(f"[VirtualStaging] Lỗi nạp Clipboard: {e}")'''

content = content.replace(old_methods, new_methods)

# Replace 'self.setup_delayed_rendering()' in files_copied_meta handler
old_meta = '''            # Đăng ký delayed rendering để Windows gửi WM_RENDERFORMAT khi người dùng Paste
            self.setup_delayed_rendering()'''
new_meta = '''            # Nạp file ảo (Virtual Staging) vào Clipboard
            self.is_paste_triggered = False
            self.setup_virtual_files(self.pending_remote_files)'''
content = content.replace(old_meta, new_meta)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Patch 3 done')
