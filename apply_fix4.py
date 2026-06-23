import codecs
import re

def patch_app():
    with codecs.open('app.py', 'r', 'utf-8') as f:
        content = f.read()

    # Match show_host_connection_border and hide_host_connection_border
    pattern = re.compile(r'    def show_host_connection_border\(self\):.*?    def wake_display\(self\):', re.DOTALL)
    
    new_func = r'''    def show_host_connection_border(self):
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
            pass

    def wake_display(self):'''
    
    if pattern.search(content):
        content = pattern.sub(new_func, content, count=1)
        with codecs.open('app.py', 'w', 'utf-8') as f:
            f.write(content)
        print("Patched show_host_connection_border successfully.")
    else:
        print("Pattern not found!")

if __name__ == "__main__":
    patch_app()
