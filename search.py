target_file = "app.py"
with open(target_file, "r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        if "hook" in line.lower() or "listener" in line.lower():
            print(f"{idx+1}: {line.strip()}")
