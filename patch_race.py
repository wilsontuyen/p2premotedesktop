import os
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """            # Refined paste check using formal paste ready signal
            t_now = time.time()
            # 1. Must be within 5.0 seconds of a PASTE_READY signal
            if t_now - _agent_last_paste_ready_time > 5.0:
                agent_print(f"[ClipboardAgent] Bỏ qua truy vấn clipboard nền (no recent paste_ready signal, age={t_now - _agent_last_paste_ready_time:.3f}s)")
                return 0"""

replacement = """            # Refined paste check using formal paste ready signal
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

if target in content:
    content = content.replace(target, replacement)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Target not found. Checking if file has different characters...")
    import re
    # Try a regex approach for robust replacement ignoring exact spaces/chars
    match = re.search(r"(\s*# Refined paste check using formal paste ready signal\s*t_now = time\.time\(\)\s*# 1\. Must be within 5\.0 seconds of a PASTE_READY signal\s*if t_now - _agent_last_paste_ready_time > 5\.0:\s*agent_print\([^\)]*\)\s*return 0)", content)
    if match:
        content = content[:match.start()] + replacement + content[match.end():]
        with open('app.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("Patched successfully using regex")
    else:
        print("Still not found")
