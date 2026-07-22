import os

def patch_entry():
    path = "app.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    target = "tk.Toplevel.geometry = _scaled_toplevel_geometry"
    patch = """
_orig_tk_entry = tk.Entry
def _mac_tk_entry(master=None, cnf={}, **kw):
    if "highlightthickness" not in kw:
        kw["highlightthickness"] = 1
    if "highlightbackground" not in kw:
        kw["highlightbackground"] = "#3A3A4A"
    return _orig_tk_entry(master, cnf, **kw)
if sys.platform == "darwin":
    tk.Entry = _mac_tk_entry
"""
    if "_mac_tk_entry" not in content:
        content = content.replace(target, target + "\n" + patch, 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    patch_entry()
    print("Done")
