import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

search = """        if is_parent_minimized or parent is None:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = (screen_w - dialog_w) // 2
            y = (screen_h - dialog_h) // 2
        else:
            parent_x = parent.winfo_x()
            parent_y = parent.winfo_y()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            x = parent_x + (parent_w - dialog_w) // 2
            y = parent_y + (parent_h - dialog_h) // 2

        geo = f"{dialog_w}x{dialog_h}+{x}+{y}"
        self.geometry(geo)
        if parent and parent.state() != "withdrawn":
            self.transient(parent)
        else:
            self.deiconify()
            self.lift()
            self.focus_force()
        self.update()"""

replace = """        if is_parent_minimized or parent is None:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = (screen_w - dialog_w) // 2
            y = (screen_h - dialog_h) // 2
            self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
            self.deiconify()
            self.lift()
            self.focus_force()
        else:
            self.transient(parent)
            try:
                import ctypes
                parent_hwnd = int(parent.frame(), 16)
                tk_hwnd = int(self.frame(), 16)
                
                style = ctypes.windll.user32.GetWindowLongW(tk_hwnd, -16)
                style = (style | 0x40000000) & ~0x80000000
                ctypes.windll.user32.SetWindowLongW(tk_hwnd, -16, style)
                ctypes.windll.user32.SetParent(tk_hwnd, parent_hwnd)
                
                parent_w = parent.winfo_width()
                parent_h = parent.winfo_height()
                x = max(0, (parent_w - dialog_w) // 2)
                y = max(0, (parent_h - dialog_h) // 2)
                
                ctypes.windll.user32.SetWindowPos(tk_hwnd, 0, x, y, dialog_w, dialog_h, 0x0004)
            except Exception as e:
                parent_x = parent.winfo_rootx()
                parent_y = parent.winfo_rooty()
                parent_w = parent.winfo_width()
                parent_h = parent.winfo_height()
                x = parent_x + (parent_w - dialog_w) // 2
                y = parent_y + (parent_h - dialog_h) // 2
                self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
                self.lift()
                self.focus_force()
            
        self.update()"""

if search in content:
    content = content.replace(search, replace)
    print("Replaced logic")
else:
    print("Not found logic")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
