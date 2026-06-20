with open("app.py", "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if "WNDCLASSEXW" in line:
            print(f"{line_num}: {line.strip()}")
