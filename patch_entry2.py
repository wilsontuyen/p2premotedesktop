import os

def patch_entry2():
    path = "app.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    old_mac_entry = """_orig_tk_entry = tk.Entry
def _mac_tk_entry(master=None, cnf={}, **kw):
    if "highlightthickness" not in kw:
        kw["highlightthickness"] = 1
    if "highlightbackground" not in kw:
        kw["highlightbackground"] = "#3A3A4A"
    return _orig_tk_entry(master, cnf, **kw)
if sys.platform == "darwin":
    tk.Entry = _mac_tk_entry"""

    new_mac_entry = """_orig_tk_entry = tk.Entry
class MacEntry(ttk.Entry):
    def __init__(self, master=None, **kw):
        self._style_name = f"MacEntry_{id(self)}.TEntry"
        self._style = ttk.Style()
        
        ttk_kw = {}
        style_kw = {}
        for k, v in kw.items():
            if k == 'bg': style_kw['fieldbackground'] = v
            elif k == 'fg': style_kw['foreground'] = v
            elif k == 'font': ttk_kw['font'] = v
            elif k in ('bd', 'relief', 'insertbackground', 'highlightthickness', 'highlightbackground'): pass
            else: ttk_kw[k] = v
            
        self._style.configure(self._style_name, **style_kw)
        ttk_kw['style'] = self._style_name
        super().__init__(master, **ttk_kw)
        
    def config(self, **kw):
        ttk_kw = {}
        style_kw = {}
        for k, v in kw.items():
            if k == 'bg': style_kw['fieldbackground'] = v
            elif k == 'fg': style_kw['foreground'] = v
            elif k == 'font': ttk_kw['font'] = v
            elif k in ('bd', 'relief', 'insertbackground', 'highlightthickness', 'highlightbackground'): pass
            else: ttk_kw[k] = v
        if style_kw:
            self._style.configure(self._style_name, **style_kw)
        if ttk_kw:
            super().config(**ttk_kw)
            
    def configure(self, **kw):
        self.config(**kw)

if sys.platform == "darwin":
    tk.Entry = MacEntry"""

    if old_mac_entry in content:
        content = content.replace(old_mac_entry, new_mac_entry)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

if __name__ == "__main__":
    patch_entry2()
    print("Done")
