import os

def update_mac_label():
    path = "app.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    old_mac_label = """class MacLabel(ttk.Label):
    def __init__(self, master=None, **kw):
        style_name = f"MacLabel_{id(self)}.TLabel"
        style = ttk.Style()
        
        ttk_kw = {}
        style_kw = {}
        for k, v in kw.items():
            if k == 'bg': style_kw['background'] = v
            elif k == 'fg': style_kw['foreground'] = v
            elif k == 'font': style_kw['font'] = v
            elif k in ('bd', 'relief', 'height', 'width'): pass
            else: ttk_kw[k] = v
            
        style.configure(style_name, **style_kw)
        ttk_kw['style'] = style_name
        super().__init__(master, **ttk_kw)"""

    new_mac_label = """class MacLabel(ttk.Label):
    def __init__(self, master=None, **kw):
        self._style_name = f"MacLabel_{id(self)}.TLabel"
        self._style = ttk.Style()
        
        ttk_kw = {}
        style_kw = {}
        for k, v in kw.items():
            if k == 'bg': style_kw['background'] = v
            elif k == 'fg': style_kw['foreground'] = v
            elif k == 'font': style_kw['font'] = v
            elif k in ('bd', 'relief', 'height', 'width'): pass
            else: ttk_kw[k] = v
            
        self._style.configure(self._style_name, **style_kw)
        ttk_kw['style'] = self._style_name
        super().__init__(master, **ttk_kw)
        
    def config(self, **kw):
        ttk_kw = {}
        style_kw = {}
        for k, v in kw.items():
            if k == 'bg': style_kw['background'] = v
            elif k == 'fg': style_kw['foreground'] = v
            elif k == 'font': style_kw['font'] = v
            elif k in ('bd', 'relief', 'height', 'width'): pass
            else: ttk_kw[k] = v
        if style_kw:
            self._style.configure(self._style_name, **style_kw)
        if ttk_kw:
            super().config(**ttk_kw)
            
    def configure(self, **kw):
        self.config(**kw)
"""
    if old_mac_label in content:
        content = content.replace(old_mac_label, new_mac_label)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

if __name__ == "__main__":
    update_mac_label()
    print("Done")
