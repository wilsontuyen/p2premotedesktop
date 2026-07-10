import os
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\r\n', '\n')

# 1. Patch _agent_mouse_poll_loop
target_poll = """    def _agent_mouse_poll_loop():
        nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_ctrl_v_time
        import time
        user32 = ctypes.windll.user32
        while True:
            try:
                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    _agent_last_lbutton_time = time.time()
                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    _agent_last_rbutton_time = time.time()
                if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):
                    _agent_last_ctrl_v_time = time.time()
                if (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000):
                    _agent_last_ctrl_v_time = time.time()
            except:
                pass
            time.sleep(0.05)"""

replace_poll = """    def _agent_mouse_poll_loop():
        nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_ctrl_v_time, _agent_last_paste_ready_time
        import time
        user32 = ctypes.windll.user32
        while True:
            try:
                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    _agent_last_lbutton_time = time.time()
                    _agent_last_paste_ready_time = time.time()
                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    _agent_last_rbutton_time = time.time()
                    _agent_last_paste_ready_time = time.time()
                if (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000):
                    _agent_last_ctrl_v_time = time.time()
                    _agent_last_paste_ready_time = time.time()
                if (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000):
                    _agent_last_ctrl_v_time = time.time()
                    _agent_last_paste_ready_time = time.time()
            except:
                pass
            time.sleep(0.05)"""

if target_poll in content:
    content = content.replace(target_poll, replace_poll)
    print("Patched poll loop")
else:
    print("Could not find poll loop")

# 2. Patch WM_RENDERFORMAT race condition
target_race = """            # Refined paste check using formal paste ready signal
            t_now = time.time()
            # 1. Must be within 5.0 seconds of a PASTE_READY signal
            if t_now - _agent_last_paste_ready_time > 5.0:
                agent_print(f"[ClipboardAgent] Bỏ qua truy vấn clipboard nền (no recent paste_ready signal, age={t_now - _agent_last_paste_ready_time:.3f}s)")
                return 0"""

replace_race = """            # Refined paste check using formal paste ready signal
            t_now = time.time()
            
            # Khắc phục race condition với _agent_mouse_poll_loop (chạy mỗi 50ms):
            # Kiểm tra trạng thái phím/chuột TRỰC TIẾP tại thời điểm WM_RENDERFORMAT được gọi (tức thì).
            user32 = ctypes.windll.user32
            is_ctrl_v_now = (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000)
            is_shift_ins_now = (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000)
            is_lbutton_now = (user32.GetAsyncKeyState(0x01) & 0x8000)
            is_rbutton_now = (user32.GetAsyncKeyState(0x02) & 0x8000)
            if is_ctrl_v_now or is_shift_ins_now or is_lbutton_now or is_rbutton_now:
                _agent_last_paste_ready_time = t_now
                
            # 1. Must be within 5.0 seconds of a PASTE_READY signal
            if t_now - _agent_last_paste_ready_time > 5.0:
                agent_print(f"[ClipboardAgent] Bỏ qua truy vấn clipboard nền (no recent paste_ready signal, age={t_now - _agent_last_paste_ready_time:.3f}s)")
                return 0"""

if target_race in content:
    content = content.replace(target_race, replace_race)
    print("Patched race condition")
else:
    print("Could not find race condition block")

# 3. Patch handle_received_packet grace period
target_focus = """        # Chọn nhận clipboard từ Host nếu cửa sổ Client Viewer không được kích hoạt
        if ptype in ("clipboard_text", "files_copied_meta"):
            if getattr(self, 'pygame_hwnd', None):
                user32 = ctypes.windll.user32
                user32.GetForegroundWindow.restype = ctypes.c_void_p
                fg_hwnd = user32.GetForegroundWindow()
                if fg_hwnd != self.pygame_hwnd:
                    log_debug(f"[handle_received_packet] Bỏ qua gói tin {ptype} do cửa sổ Viewer không được kích hoạt (Giữ clipboard cho máy thật).")
                    return"""

replace_focus = """        # Chọn nhận clipboard từ Host nếu cửa sổ Client Viewer không được kích hoạt
        if ptype in ("clipboard_text", "files_copied_meta"):
            if getattr(self, 'pygame_hwnd', None):
                user32 = ctypes.windll.user32
                user32.GetForegroundWindow.restype = ctypes.c_void_p
                fg_hwnd = user32.GetForegroundWindow()
                last_active = getattr(self, 'last_viewer_active_time', 0.0)
                import time
                # Nếu viewer mất focus nhưng vừa active trong vòng 2.0s qua, vẫn chấp nhận (giải quyết vụ delay 200-300ms lúc copy)
                if fg_hwnd != self.pygame_hwnd and (time.time() - last_active > 2.0):
                    log_debug(f"[handle_received_packet] Bỏ qua gói tin {ptype} do cửa sổ Viewer không được kích hoạt (Giữ clipboard cho máy thật).")
                    return"""

if target_focus in content:
    content = content.replace(target_focus, replace_focus)
    print("Patched focus grace period")
else:
    print("Could not find focus block")

# 4. Patch client_loop to record viewer active time
target_active = """                # Cập nhật event loop của Tkinter để các hộp thoại (dialog truyền file) vẫn hoạt động trong subprocess
                try:
                    hidden_root.update()
                except Exception:
                    pass"""

replace_active = """                # Cập nhật event loop của Tkinter để các hộp thoại (dialog truyền file) vẫn hoạt động trong subprocess
                try:
                    hidden_root.update()
                except Exception:
                    pass
                    
                # Ghi nhận thời gian hoạt động của Viewer
                if clipboard_sync_manager and getattr(clipboard_sync_manager, 'pygame_hwnd', None):
                    import ctypes, time
                    if ctypes.windll.user32.GetForegroundWindow() == clipboard_sync_manager.pygame_hwnd:
                        clipboard_sync_manager.last_viewer_active_time = time.time()"""

if target_active in content:
    content = content.replace(target_active, replace_active)
    print("Patched active time")
else:
    print("Could not find active time block")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
