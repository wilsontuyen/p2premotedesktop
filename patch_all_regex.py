import os, re
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Patch _agent_mouse_poll_loop
content = re.sub(
    r"def _agent_mouse_poll_loop\(\):\s*nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_ctrl_v_time\s*import time",
    r"def _agent_mouse_poll_loop():\n        nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_ctrl_v_time, _agent_last_paste_ready_time\n        import time",
    content
)

content = re.sub(
    r"_agent_last_lbutton_time = time\.time\(\)",
    r"_agent_last_lbutton_time = time.time()\n                    _agent_last_paste_ready_time = time.time()",
    content
)

content = re.sub(
    r"_agent_last_rbutton_time = time\.time\(\)",
    r"_agent_last_rbutton_time = time.time()\n                    _agent_last_paste_ready_time = time.time()",
    content
)

# 2. Patch WM_RENDERFORMAT race condition
content = re.sub(
    r"t_now = time\.time\(\)\s*# 1\. Must be within 5\.0 seconds of a PASTE_READY signal\s*if t_now - _agent_last_paste_ready_time > 5\.0:",
    r"""t_now = time.time()
            
            # Khắc phục race condition với _agent_mouse_poll_loop (chạy mỗi 50ms):
            user32 = ctypes.windll.user32
            is_ctrl_v_now = (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000)
            is_shift_ins_now = (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000)
            is_lbutton_now = (user32.GetAsyncKeyState(0x01) & 0x8000)
            is_rbutton_now = (user32.GetAsyncKeyState(0x02) & 0x8000)
            if is_ctrl_v_now or is_shift_ins_now or is_lbutton_now or is_rbutton_now:
                _agent_last_paste_ready_time = t_now
                
            # 1. Must be within 5.0 seconds of a PASTE_READY signal
            if t_now - _agent_last_paste_ready_time > 5.0:""",
    content
)

# 3. Patch handle_received_packet grace period
content = re.sub(
    r"fg_hwnd = user32\.GetForegroundWindow\(\)\s*if fg_hwnd != self\.pygame_hwnd:\s*log_debug\(f\"\[handle_received_packet\] Bỏ qua gói tin \{ptype\} do cửa sổ Viewer không được kích hoạt",
    r"""fg_hwnd = user32.GetForegroundWindow()
                last_active = getattr(self, 'last_viewer_active_time', 0.0)
                import time
                if fg_hwnd != self.pygame_hwnd and (time.time() - last_active > 2.0):
                    log_debug(f"[handle_received_packet] Bỏ qua gói tin {ptype} do cửa sổ Viewer không được kích hoạt""",
    content
)

# 4. Patch client_loop to record viewer active time
content = re.sub(
    r"hidden_root\.update\(\)\s*except Exception:\s*pass\s*global client_host_resolution",
    r"""hidden_root.update()
                except Exception:
                    pass
                    
                if clipboard_sync_manager and getattr(clipboard_sync_manager, 'pygame_hwnd', None):
                    import ctypes, time
                    if ctypes.windll.user32.GetForegroundWindow() == clipboard_sync_manager.pygame_hwnd:
                        clipboard_sync_manager.last_viewer_active_time = time.time()
                        
                global client_host_resolution""",
    content
)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Regex patch applied successfully")
