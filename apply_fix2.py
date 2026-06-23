import codecs

def patch_app():
    with codecs.open('app.py', 'r', 'utf-8') as f:
        content = f.read()

    # 1. Update ClipboardEventListener._mouse_poll_loop
    old_poll_loop = """    def _mouse_poll_loop(self):
        user32 = ctypes.windll.user32
        while self.running:
            if user32.GetAsyncKeyState(0x01) & 0x8000:
                if self.manager:
                    self.manager.last_lbutton_time = time.time()
            if user32.GetAsyncKeyState(0x02) & 0x8000:
                if self.manager:
                    self.manager.last_rbutton_time = time.time()
            time.sleep(0.05)"""
            
    new_poll_loop = """    def _mouse_poll_loop(self):
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
            time.sleep(0.05)"""
    content = content.replace(old_poll_loop, new_poll_loop)

    # 2. Update check_is_menu_query
    old_menu_logic = """def check_is_menu_query(last_lbutton, last_rbutton, meta_arrival_time, last_lbutton_class=""):
    \"\"\"
    Kiểm tra xem yêu cầu WM_RENDERFORMAT hiện tại có phải là do menu chuột phải (context menu)
    hoặc tiến trình quét tự động trong nền truy vấn hay không, hay là thao tác Paste thực tế.
    Trả về True nếu là truy vấn menu/nền (cần từ chối tải file thực tế lúc này),
    Trả về False nếu là thao tác Paste thực sự.
    \"\"\"
    user32 = ctypes.windll.user32
    from ctypes import wintypes
    
    t_now = time.time()
    time_since_lbutton = t_now - last_lbutton
    time_since_rbutton = t_now - last_rbutton
    meta_age = t_now - meta_arrival_time
    
    # 0. Nếu cửa sổ hiện hành là chính Remote Desktop Viewer hoặc GUI của app,
    # bất kỳ truy vấn clipboard nào cũng chỉ có thể là do hệ thống/nền tự quét sau khi copy,
    # chứ không thể là thao tác Paste thực tế của người dùng lên máy client.
    try:
        import win32gui
        hwnd_fg = win32gui.GetForegroundWindow()
        if hwnd_fg:
            title = win32gui.GetWindowText(hwnd_fg)
            if title and ("Remote Desktop" in title or "Easy Remote" in title):
                log_debug(f"[check_is_menu_query] Tra ve True: Cua so hien hanh la Remote Desktop ({title})")
                return True
    except Exception as e:
        pass
        
    # 1. Kiểm tra xem cửa sổ menu (#32768) có tồn tại không (dù ẩn hay hiện)
    hwnd_menu = user32.FindWindowW("#32768", None)
    if hwnd_menu:
        log_debug(f"[check_is_menu_query] Tra ve True: Cua so menu (#32768) dang ton tai")
        return True
        
    # 2. Kiểm tra Menu Loop qua GetGUIThreadInfo
    try:
        class RECT_SIMPLE(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)
            ]
        class GUITHREADINFO_SIMPLE(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("flags", ctypes.c_ulong),
                ("hwndActive", ctypes.c_void_p),
                ("hwndFocus", ctypes.c_void_p),
                ("hwndCapture", ctypes.c_void_p),
                ("hwndMenuOwner", ctypes.c_void_p),
                ("hwndMoveSize", ctypes.c_void_p),
                ("hwndCaret", ctypes.c_void_p),
                ("rcCaret", RECT_SIMPLE)
            ]
        
        user32.GetOpenClipboardWindow.restype = ctypes.c_void_p
        hwnd_clip = user32.GetOpenClipboardWindow()
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        hwnd_fg = user32.GetForegroundWindow()
        
        for hwnd_check in (hwnd_clip, hwnd_fg):
            if hwnd_check:
                pid = wintypes.DWORD()
                tid = user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd_check), ctypes.byref(pid))
                gui_info = GUITHREADINFO_SIMPLE()
                gui_info.cbSize = ctypes.sizeof(GUITHREADINFO_SIMPLE)
                if user32.GetGUIThreadInfo(tid, ctypes.byref(gui_info)):
                    # GUI_INMENULOOP = 0x04, GUI_POPUPMENUMODE = 0x10, GUI_SYSTEMMENUMODE = 0x08
                    if gui_info.flags & (0x04 | 0x10 | 0x08):
                        log_debug(f"[check_is_menu_query] Tra ve True: Phat hien Menu Loop tu GetGUIThreadInfo flags={gui_info.flags}")
                        return True
    except Exception as e:
        pass

    # 3. Kiểm tra phím tắt Ctrl+V hoặc Shift+Insert hoặc phím Enter (chọn mục menu bằng bàn phím)
    # VK_CONTROL = 0x11, VK_V = 0x56, VK_SHIFT = 0x10, VK_INSERT = 0x2D, VK_RETURN = 0x0D
    is_ctrl_v = (user32.GetAsyncKeyState(0x11) & 0x8000) and (user32.GetAsyncKeyState(0x56) & 0x8000)
    is_shift_ins = (user32.GetAsyncKeyState(0x10) & 0x8000) and (user32.GetAsyncKeyState(0x2D) & 0x8000)
    is_enter = (user32.GetAsyncKeyState(0x0D) & 0x8000)
    if is_ctrl_v or is_shift_ins or is_enter:
        log_debug(f"[check_is_menu_query] Tra ve False: Phim dan/lenh duoc nhan (ctrl_v={is_ctrl_v}, shift_ins={is_shift_ins}, enter={is_enter})")
        return False

    # 4. Nếu vừa click chuột trái (trong vòng 1.0 giây) VÀ click chuột trái này xảy ra SAU khi nhận metadata
    if time_since_lbutton < 1.0 and (last_lbutton >= meta_arrival_time):
        # Kiểm tra xem click trái có phải vào file/folder/desktop (chọn mục) thay vì Paste
        # Các class thường gặp của danh sách file/folder trong Windows Explorer:
        ignore_classes = ["DirectUIHWND", "SysListView32", "CabinetWClass", "WorkerW", "Progman", "CtrlNotifySink"]
        if any(cls in last_lbutton_class for cls in ignore_classes):
            log_debug(f"[check_is_menu_query] Tra ve True: Vua click chuot trai vao folder/desktop (class={last_lbutton_class})")
            return True
        else:
            log_debug(f"[check_is_menu_query] Tra ve False: Vua click chuot trai (class={last_lbutton_class}), kha nang la Paste tu menu hoac Ribbon")
            return False
            
    # 5. Nếu chuột phải vừa được click gần đây (< 1.5s)
    if time_since_rbutton < 1.5:
        log_debug(f"[check_is_menu_query] Tra ve True: Vua click chuot phai gan day (age={time_since_rbutton:.3f}s)")
        return True
        
    # 6. Nếu metadata vừa mới nhận được (< 1.5s) và không có phím tắt/chuột trái hoạt động,
    # đó có thể là do công cụ tự động quét clipboard trong nền.
    if meta_age < 1.5:
        log_debug(f"[check_is_menu_query] Tra ve True: Metadata vua moi nhan (age={meta_age:.3f}s)")
        return True
        
    # 7. Fallback: Nếu không có click chuột trái gần đây (> 5.0 giây), mặc định coi là nền quét
    if time_since_lbutton > 5.0:
        log_debug(f"[check_is_menu_query] Tra ve True: Fallback vi time_since_lbutton={time_since_lbutton:.3f}s > 5.0s")
        return True
        
    log_debug(f"[check_is_menu_query] Tra ve False: Mac dinh (lbutton_age={time_since_lbutton:.3f}s, rbutton_age={time_since_rbutton:.3f}s)")
    return False"""

    new_menu_logic = """def check_is_menu_query(last_lbutton, last_rbutton, meta_arrival_time, last_lbutton_class="", last_paste_key=0.0):
    user32 = ctypes.windll.user32
    t_now = time.time()
    time_since_lbutton = t_now - last_lbutton
    time_since_rbutton = t_now - last_rbutton
    time_since_paste_key = t_now - last_paste_key
    meta_age = t_now - meta_arrival_time
    
    # 0. Nếu cửa sổ hiện hành là chính Remote Desktop Viewer
    try:
        import win32gui
        hwnd_fg = win32gui.GetForegroundWindow()
        if hwnd_fg:
            title = win32gui.GetWindowText(hwnd_fg)
            if title and ("Remote Desktop" in title or "Easy Remote" in title):
                log_debug(f"[check_is_menu_query] Tra ve True: Cua so hien hanh la Remote Desktop")
                return True
    except Exception as e:
        pass

    # 1. Bàn phím Paste (Ctrl+V hoặc Shift+Insert)
    if time_since_paste_key < 2.0:
        log_debug(f"[check_is_menu_query] Tra ve False: Phat hien phim Paste (paste_key_age={time_since_paste_key:.3f}s)")
        return False
        
    # 2. Nếu vừa right-click (< 1.5s), Windows menu đang query để hiển thị nút Paste -> TRUE
    if time_since_rbutton < 1.5:
        log_debug(f"[check_is_menu_query] Tra ve True: Vua right-click (rbutton_age={time_since_rbutton:.3f}s)")
        return True
        
    # 3. Nếu vừa left-click (< 1.5s), có thể user click Paste trên Menu/Ribbon, hoặc click chọn thư mục
    if time_since_lbutton < 1.5:
        # Nếu class là vùng chọn file/thư mục (background) thì chắc chắn không phải là nút Paste
        background_classes = ["SysListView32", "DirectUIHWND", "CabinetWClass", "WorkerW", "Progman", "CtrlNotifySink"]
        if any(cls in last_lbutton_class for cls in background_classes):
            log_debug(f"[check_is_menu_query] Tra ve True: Vua click vao background class ({last_lbutton_class})")
            return True
        else:
            log_debug(f"[check_is_menu_query] Tra ve False: Vua click vao class ({last_lbutton_class}), co the la nut Paste")
            return False

    # 4. Mặc định tất cả các trường hợp khác (không click, không phím gần đây) là nền quét -> TRUE
    log_debug(f"[check_is_menu_query] Tra ve True: Mac dinh nen quet (lbutton_age={time_since_lbutton:.3f}s)")
    return True"""
    
    content = content.replace(old_menu_logic, new_menu_logic)

    # 3. Update render_format usage
    old_call_1 = """        last_l_class = getattr(self, 'last_lbutton_class', "")
        is_menu = check_is_menu_query(last_l, last_r, meta_time, last_l_class)"""
    new_call_1 = """        last_l_class = getattr(self, 'last_lbutton_class', "")
        last_paste = getattr(self, 'last_paste_key_time', 0.0)
        is_menu = check_is_menu_query(last_l, last_r, meta_time, last_l_class, last_paste)"""
    content = content.replace(old_call_1, new_call_1)

    # 4. Update ClipboardAgent globals
    old_agent_vars = """    _agent_last_lbutton_time = 0.0
    _agent_last_rbutton_time = 0.0
    _agent_meta_arrival_time = 0.0
    _agent_last_lbutton_class = ""

    def _agent_mouse_poll_loop():
        nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_lbutton_class"""
    new_agent_vars = """    _agent_last_lbutton_time = 0.0
    _agent_last_rbutton_time = 0.0
    _agent_meta_arrival_time = 0.0
    _agent_last_lbutton_class = ""
    _agent_last_paste_key_time = 0.0

    def _agent_mouse_poll_loop():
        nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_lbutton_class, _agent_last_paste_key_time"""
    content = content.replace(old_agent_vars, new_agent_vars)

    # 5. Update agent loop keys
    old_agent_keys = """                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    _agent_last_rbutton_time = time.time()
            except:"""
    new_agent_keys = """                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    _agent_last_rbutton_time = time.time()
                is_ctrl = user32.GetAsyncKeyState(0x11) & 0x8000
                is_v = user32.GetAsyncKeyState(0x56) & 0x8000
                is_shift = user32.GetAsyncKeyState(0x10) & 0x8000
                is_ins = user32.GetAsyncKeyState(0x2D) & 0x8000
                is_enter = user32.GetAsyncKeyState(0x0D) & 0x8000
                if (is_ctrl and is_v) or (is_shift and is_ins) or is_enter:
                    _agent_last_paste_key_time = time.time()
            except:"""
    content = content.replace(old_agent_keys, new_agent_keys)

    # 6. Update agent wndproc
    old_wndproc = """    def agent_wndproc(hwnd, msg, wparam, lparam):
        nonlocal _is_rendering, _files_ready_paths, _files_ready_event, _ignore_destroy, _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_lbutton_class"""
    new_wndproc = """    def agent_wndproc(hwnd, msg, wparam, lparam):
        nonlocal _is_rendering, _files_ready_paths, _files_ready_event, _ignore_destroy, _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_lbutton_class, _agent_last_paste_key_time"""
    content = content.replace(old_wndproc, new_wndproc)

    old_agent_call = """            is_menu = check_is_menu_query(_agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_lbutton_class)"""
    new_agent_call = """            is_menu = check_is_menu_query(_agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_lbutton_class, _agent_last_paste_key_time)"""
    content = content.replace(old_agent_call, new_agent_call)

    # 7. Update host border logic
    old_border = """    def show_host_connection_border(self):
        try:
            if hasattr(self, 'host_border_win') and self.host_border_win:
                try: self.host_border_win.destroy()
                except: pass
                
            import tkinter as tk
            self.host_border_win = tk.Toplevel(self)
            self.host_border_win.attributes("-fullscreen", True)
            self.host_border_win.attributes("-topmost", True)
            self.host_border_win.attributes("-transparentcolor", "black")
            self.host_border_win.configure(bg="black")
            self.host_border_win.overrideredirect(True)
            
            canvas = tk.Canvas(self.host_border_win, bg="black", highlightthickness=0)
            canvas.pack(fill="both", expand=True)
            w = self.winfo_screenwidth()
            h = self.winfo_screenheight()
            canvas.create_rectangle(3, 3, w-3, h-3, outline="#FF69B4", width=7)
        except Exception as e:
            print(f"[Host] Lỗi tạo viền hồng kết nối: {e}")

    def hide_host_connection_border(self):
        try:
            if hasattr(self, 'host_border_win') and self.host_border_win:
                self.host_border_win.destroy()
                self.host_border_win = None
        except Exception as e:
            pass"""
            
    new_border = """    def show_host_connection_border(self):
        try:
            self.hide_host_connection_border()
            
            import tkinter as tk
            self.host_border_wins = []
            
            w = self.winfo_screenwidth()
            h = self.winfo_screenheight()
            thickness = 5
            color = "#FF0000"
            
            rects = [
                (0, 0, w, thickness),           # top
                (0, h - thickness, w, thickness), # bottom
                (0, 0, thickness, h),           # left
                (w - thickness, 0, thickness, h)  # right
            ]
            
            for x, y, rw, rh in rects:
                win = tk.Toplevel(self)
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                win.configure(bg=color)
                win.geometry(f"{rw}x{rh}+{x}+{y}")
                try:
                    import ctypes
                    hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
                    if not hwnd:
                        hwnd = win.winfo_id()
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
                    ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x00080000 | 0x00000020)
                except:
                    pass
                self.host_border_wins.append(win)
                
        except Exception as e:
            print(f"[Host] Lỗi tạo viền hồng kết nối: {e}")

    def hide_host_connection_border(self):
        try:
            if hasattr(self, 'host_border_wins'):
                for win in self.host_border_wins:
                    try: win.destroy()
                    except: pass
                self.host_border_wins = []
            if hasattr(self, 'host_border_win') and self.host_border_win:
                try: self.host_border_win.destroy()
                except: pass
                self.host_border_win = None
        except Exception as e:
            pass"""
            
    content = content.replace(old_border, new_border)

    with codecs.open('app.py', 'w', 'utf-8') as f:
        f.write(content)
    
    print("Patch app.py successfully applied.")

if __name__ == "__main__":
    patch_app()
