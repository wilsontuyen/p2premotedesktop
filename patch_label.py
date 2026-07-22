import os

def patch_label():
    path = "app.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    target = "if sys.platform == \"darwin\":\n    tk.Entry = _mac_tk_entry"
    patch = """
_orig_tk_label = tk.Label
class MacLabel(ttk.Label):
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
        super().__init__(master, **ttk_kw)

if sys.platform == "darwin":
    tk.Entry = _mac_tk_entry
    tk.Label = MacLabel
"""
    if "MacLabel" not in content:
        content = content.replace(target, patch, 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    patch_label()
    print("Done")
