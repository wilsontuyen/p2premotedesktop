import codecs
import re

def patch_app():
    with codecs.open('app.py', 'r', 'utf-8') as f:
        content = f.read()

    # 1. Patch ClipboardEventListener._mouse_poll_loop
    # Find ClipboardEventListener class and its _mouse_poll_loop
    old_loop1_pattern = re.compile(r'    def _mouse_poll_loop\(self\):.*?time\.sleep\(0\.05\)', re.DOTALL)
    new_loop1 = r'''    def _mouse_poll_loop(self):
        user32 = ctypes.windll.user32
        from ctypes import wintypes
        import time
        while self.running:
            try:
                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    if self.manager:
                        self.manager.last_lbutton_time = time.time()
                        pt = wintypes.POINT()
                        user32.GetCursorPos(ctypes.byref(pt))
                        hwnd = user32.WindowFromPoint(pt)
                        buf = ctypes.create_unicode_buffer(256)
                        user32.GetClassNameW(hwnd, buf, 256)
                        self.manager.last_lbutton_class = buf.value
                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    if self.manager:
                        self.manager.last_rbutton_time = time.time()
                
                is_ctrl = user32.GetAsyncKeyState(0x11) & 0x8000
                is_v = user32.GetAsyncKeyState(0x56) & 0x8000
                is_shift = user32.GetAsyncKeyState(0x10) & 0x8000
                is_ins = user32.GetAsyncKeyState(0x2D) & 0x8000
                is_enter = user32.GetAsyncKeyState(0x0D) & 0x8000
                if (is_ctrl and is_v) or (is_shift and is_ins) or is_enter:
                    if self.manager:
                        self.manager.last_paste_key_time = time.time()
            except:
                pass
            time.sleep(0.05)'''
            
    match1 = old_loop1_pattern.search(content)
    if match1:
        # Check if it belongs to ClipboardEventListener
        content = content[:match1.start()] + new_loop1 + content[match1.end():]
        print("Patched ClipboardEventListener._mouse_poll_loop")
    
    # 2. Patch _agent_mouse_poll_loop
    old_loop2_pattern = re.compile(r'    _agent_last_lbutton_time = 0\.0.*?    def _agent_mouse_poll_loop\(\):.*?time\.sleep\(0\.05\)', re.DOTALL)
    new_loop2 = r'''    _agent_last_lbutton_time = 0.0
    _agent_last_rbutton_time = 0.0
    _agent_meta_arrival_time = 0.0
    _agent_last_lbutton_class = ""
    _agent_last_paste_key_time = 0.0

    def _agent_mouse_poll_loop():
        nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_lbutton_class, _agent_last_paste_key_time
        user32 = ctypes.windll.user32
        from ctypes import wintypes
        while True:
            try:
                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    _agent_last_lbutton_time = time.time()
                    pt = wintypes.POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    hwnd = user32.WindowFromPoint(pt)
                    buf = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, buf, 256)
                    _agent_last_lbutton_class = buf.value
                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    _agent_last_rbutton_time = time.time()
                
                is_ctrl = user32.GetAsyncKeyState(0x11) & 0x8000
                is_v = user32.GetAsyncKeyState(0x56) & 0x8000
                is_shift = user32.GetAsyncKeyState(0x10) & 0x8000
                is_ins = user32.GetAsyncKeyState(0x2D) & 0x8000
                is_enter = user32.GetAsyncKeyState(0x0D) & 0x8000
                if (is_ctrl and is_v) or (is_shift and is_ins) or is_enter:
                    _agent_last_paste_key_time = time.time()
            except:
                pass
            time.sleep(0.05)'''
            
    match2 = old_loop2_pattern.search(content)
    if match2:
        content = content[:match2.start()] + new_loop2 + content[match2.end():]
        print("Patched _agent_mouse_poll_loop")
        
    # 3. Patch agent_wndproc definition to include nonlocal _agent_last_paste_key_time
    # This might already be there or we can just replace it to be sure
    old_wndproc_pattern = re.compile(r'    def agent_wndproc\(hwnd, msg, wparam, lparam\):\s+nonlocal _is_rendering, _files_ready_paths, _files_ready_event, _ignore_destroy, _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_lbutton_class')
    new_wndproc = r'''    def agent_wndproc(hwnd, msg, wparam, lparam):
        nonlocal _is_rendering, _files_ready_paths, _files_ready_event, _ignore_destroy, _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_lbutton_class, _agent_last_paste_key_time'''
    
    if old_wndproc_pattern.search(content):
        content = old_wndproc_pattern.sub(new_wndproc, content, count=1)
        print("Patched agent_wndproc")

    with codecs.open('app.py', 'w', 'utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    patch_app()
