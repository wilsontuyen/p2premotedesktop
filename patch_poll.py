import os
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = """    def _agent_mouse_poll_loop():
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

replacement = """    def _agent_mouse_poll_loop():
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

if target in content:
    content = content.replace(target, replacement)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched successfully")
else:
    print("Target not found")
