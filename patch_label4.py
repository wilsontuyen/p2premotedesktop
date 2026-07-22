import os
import re

def clean_and_repatch():
    path = "app.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the start of the monkey patch
    start_str = "_orig_tk_entry = tk.Entry"
    # Find the end of the monkey patch
    end_str = "if sys.platform == \"darwin\":\n    tk.Entry = _mac_tk_entry\n    tk.Label = MacLabel"
    
    if start_str in content and end_str in content:
        start_idx = content.find(start_str)
        end_idx = content.find(end_str) + len(end_str)
        
        new_patch = """_orig_tk_label = tk.Label
def _mac_tk_label(master=None, cnf={}, **kw):
    kw.pop('bg', None)
    kw.pop('background', None)
    return _orig_tk_label(master, cnf, **kw)

_orig_tk_entry = tk.Entry
def _mac_tk_entry(master=None, cnf={}, **kw):
    kw.pop('bg', None)
    kw.pop('background', None)
    return _orig_tk_entry(master, cnf, **kw)

if sys.platform == "darwin":
    tk.Label = _mac_tk_label
    tk.Entry = _mac_tk_entry"""
        
        content = content[:start_idx] + new_patch + content[end_idx:]
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Patched successfully")
    else:
        print("Patch anchors not found")

if __name__ == "__main__":
    clean_and_repatch()
