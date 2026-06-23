import codecs
import re

def patch_app():
    with codecs.open('app.py', 'r', 'utf-8') as f:
        content = f.read()

    # Match check_is_menu_query function definition until the end of its body
    # It starts with 'def check_is_menu_query' and ends before 'class ClipboardSyncManager:'
    
    pattern = re.compile(r'def check_is_menu_query\(.*?\)(.*?)(?=class ClipboardSyncManager:)', re.DOTALL)
    
    new_func = r'''def check_is_menu_query(last_lbutton, last_rbutton, meta_arrival_time, last_lbutton_class="", last_paste_key=0.0):
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
    return True


'''
    
    content = pattern.sub(new_func, content, count=1)
    
    with codecs.open('app.py', 'w', 'utf-8') as f:
        f.write(content)

    print("Patched check_is_menu_query successfully.")

if __name__ == "__main__":
    patch_app()
