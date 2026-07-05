import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('\\r\\n', '\\n')

search = """        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        self.deiconify()"""

replace = """        geo = f"{dialog_w}x{dialog_h}+{x}+{y}"
        self.geometry(geo)
        self.deiconify()
        try:
            with open("C:/Apps/P2P/client_error.log", "a") as f:
                f.write(f"ProgressDialog created! Geometry: {geo}\\n")
        except: pass"""

if search in content:
    content = content.replace(search, replace)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success")
else:
    print("Not found")
