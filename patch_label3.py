import os

def fix_mac_widgets():
    path = "app.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # We will replace all instances of:
    # if k == 'bg': style_kw['background'] = v
    # with
    # if k == 'bg': pass
    
    # And for entry:
    # if k == 'bg': style_kw['fieldbackground'] = v
    # with
    # if k == 'bg': pass

    content = content.replace("if k == 'bg': style_kw['background'] = v", "if k == 'bg': pass")
    content = content.replace("if k == 'bg': style_kw['fieldbackground'] = v", "if k == 'bg': pass")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    fix_mac_widgets()
    print("Done")
