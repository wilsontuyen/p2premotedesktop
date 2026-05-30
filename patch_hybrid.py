import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace setup_virtual_files to use delayed rendering
old_virtual = '''    def setup_virtual_files(self, metadata):
        import os
        import ctypes
        from ctypes import wintypes
        print(f"[VirtualStaging] Đang tạo {len(metadata)} file ảo (0 bytes)...")'''

new_virtual = '''    def setup_virtual_files(self, metadata):
        import os
        import ctypes
        from ctypes import wintypes
        print(f"[VirtualStaging] Đang thiết lập Delayed Rendering (Hybrid Mode) cho {len(metadata)} file...")
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            user32.OpenClipboard.argtypes = [ctypes.c_void_p]
            
            opened = False
            for _ in range(10):
                if user32.OpenClipboard(ctypes.c_void_p(self.listener.hwnd)):
                    opened = True
                    break
                import time; time.sleep(0.05)
                
            if opened:
                self.ignore_destroy_clipboard = True
                user32.EmptyClipboard()
                
                cf_exclude = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
                cf_history = user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")
                cf_cloud = user32.RegisterClipboardFormatW("CanUploadToCloudClipboard")
                def set_dword_data(cf_format, value):
                    hMem = kernel32.GlobalAlloc(0x0002, 4)
                    if hMem:
                        ptr = kernel32.GlobalLock(hMem)
                        if ptr:
                            ctypes.memmove(ptr, ctypes.byref(wintypes.DWORD(value)), 4)
                            kernel32.GlobalUnlock(hMem)
                            if not user32.SetClipboardData(cf_format, hMem): kernel32.GlobalFree(hMem)
                        else: kernel32.GlobalFree(hMem)
                if cf_exclude: set_dword_data(cf_exclude, 1)
                if cf_history: set_dword_data(cf_history, 0)
                if cf_cloud: set_dword_data(cf_cloud, 0)

                user32.SetClipboardData(15, None)
                user32.CloseClipboard()
                self.ignore_destroy_clipboard = False
                print("[VirtualStaging] Hybrid Delayed Rendering thiết lập thành công.")
            else:
                print("[VirtualStaging] Lỗi: Không thể OpenClipboard()")
        except Exception as e:
            print(f"[VirtualStaging] Lỗi setup Hybrid: {e}")
            
    def render_format_hybrid(self, fmt_id):
        # We received WM_RENDERFORMAT. The clipboard is ALREADY open by Explorer!
        print("[VirtualStaging] Nhận yêu cầu Paste từ Windows Explorer!")
        import os
        import ctypes
        import json
        from ctypes import wintypes
        
        self.target_save_dir = self.get_active_explorer_path()
        print(f"[VirtualStaging] Thư mục Paste: {self.target_save_dir}")
        
        temp_dir = os.path.join(os.environ.get("PUBLIC", r"C:\\Users\\Public"), "Downloads", "RemoteDesktopTransfers", "VirtualStaging")
        try:
            os.makedirs(temp_dir, exist_ok=True)
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if os.path.isfile(item_path):
                    try: os.remove(item_path)
                    except: pass
        except: pass
        
        dummy_paths = []
        for m in self.pending_remote_files:
            fpath = os.path.join(temp_dir, m["name"])
            try:
                with open(fpath, "wb") as f: pass
                dummy_paths.append(fpath)
            except: pass
            
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        
        class DROPFILES(ctypes.Structure):
            _fields_ = [("pFiles", wintypes.DWORD), ("pt", wintypes.POINT), ("fNC", wintypes.BOOL), ("fWide", wintypes.BOOL)]
            
        file_buffer = "\\0".join(dummy_paths) + "\\0\\0"
        file_buffer_bytes = file_buffer.encode("utf-16-le")
        size = ctypes.sizeof(DROPFILES) + len(file_buffer_bytes)
        hGlobal = kernel32.GlobalAlloc(0x0042, size)
        pGlobal = kernel32.GlobalLock(hGlobal)
        dropfiles = DROPFILES()
        dropfiles.pFiles = ctypes.sizeof(DROPFILES)
        dropfiles.fWide = True
        ctypes.memmove(pGlobal, ctypes.byref(dropfiles), ctypes.sizeof(DROPFILES))
        ctypes.memmove(pGlobal + ctypes.sizeof(DROPFILES), file_buffer_bytes, len(file_buffer_bytes))
        kernel32.GlobalUnlock(hGlobal)
        
        user32.SetClipboardData(15, hGlobal)
        
        self.is_paste_triggered = True
        if self.sock:
            pkt = json.dumps({"type": "request_files", "files": [m["path"] for m in self.pending_remote_files]}).encode('utf-8')
            try:
                # App uses global send_msg
                import sys
                send_msg = sys.modules['__main__'].send_msg
                send_msg(self.sock, pkt)
            except Exception as e:
                print("Loi send request:", e)
            
    def setup_virtual_files_old(self, metadata):
        import os
        import ctypes
        from ctypes import wintypes
        print(f"[VirtualStaging] Đang tạo {len(metadata)} file ảo (0 bytes)...")'''

content = content.replace(old_virtual, new_virtual)

# Restore render_format call in wndproc
old_render = '''        elif msg == WM_RENDERFORMAT:
            log_debug(f"[WndProc] Nhận WM_RENDERFORMAT. wparam={wparam}")
            if wparam == 15: # CF_HDROP
                if self.manager:
                    self.manager.render_format(15)
                return 0'''

new_render = '''        elif msg == WM_RENDERFORMAT:
            log_debug(f"[WndProc] Nhận WM_RENDERFORMAT. wparam={wparam}")
            if wparam == 15: # CF_HDROP
                if self.manager:
                    if hasattr(self.manager, 'render_format_hybrid'):
                        self.manager.render_format_hybrid(15)
                    elif hasattr(self.manager, 'render_format'):
                        self.manager.render_format(15)
                return 0'''
content = content.replace(old_render, new_render)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Patch Hybrid applied!')
