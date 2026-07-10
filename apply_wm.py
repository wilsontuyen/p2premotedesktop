import os
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """            elif is_menu == "BACKGROUND":
                agent_print("[ClipboardAgent] Phát hiện truy vấn nền (VM Tools). Bỏ qua hoàn toàn.")
                return 0

            _is_rendering = True"""

replacement = """            elif is_menu == "BACKGROUND":
                agent_print("[ClipboardAgent] Phát hiện truy vấn nền (VM Tools). Bỏ qua hoàn toàn.")
                return 0

            # Khắc phục race condition với _agent_mouse_poll_loop (chạy mỗi 50ms):
            # Kiểm tra trạng thái phím/chuột TRỰC TIẾP tại thời điểm WM_RENDERFORMAT được gọi (tức thì).
            t_now = time.time()
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
                return 0
                
            # 2. Must have occurred after metadata arrival
            if _agent_last_paste_ready_time < _agent_meta_arrival_time - 0.1:
                agent_print("[ClipboardAgent] Bỏ qua truy vấn clipboard nền (paste_ready signal happened before metadata arrived)")
                return 0

            _is_rendering = True"""

if target in content:
    content = content.replace(target, replacement)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched WM_RENDERFORMAT successfully")
else:
    print("Could not find WM_RENDERFORMAT target block")
