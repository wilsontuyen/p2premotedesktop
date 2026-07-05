import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

# 1. Remove self.withdraw()
content = content.replace("super().__init__(parent)\\n        self.withdraw()", "super().__init__(parent)")

# 2. Add transient logic at the end instead of deiconify
search_geo = """        geo = f"{dialog_w}x{dialog_h}+{x}+{y}"
        self.geometry(geo)
        self.deiconify()
        try:
            with open("C:/Apps/P2P/client_error.log", "a") as f:
                f.write(f"ProgressDialog created! Geometry: {geo}\\n")
        except: pass"""

replace_geo = """        geo = f"{dialog_w}x{dialog_h}+{x}+{y}"
        self.geometry(geo)
        if parent and parent.state() != "withdrawn":
            self.transient(parent)
        else:
            self.deiconify()
            self.lift()
            self.focus_force()
        self.update()"""

search_orig = """        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        self.deiconify()"""

replace_orig = """        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        if parent and parent.state() != "withdrawn":
            self.transient(parent)
        else:
            self.deiconify()
            self.lift()
            self.focus_force()
        self.update()"""

if search_geo in content:
    content = content.replace(search_geo, replace_geo)
    print("Replaced geometry block")
elif search_orig in content:
    content = content.replace(search_orig, replace_orig)
    print("Replaced original geometry block")
else:
    print("Not found")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
