import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

keywords = ["clipboard", "file", "copy", "paste", "transfer", "agent", "run_clipboard", "send_file"]
lines = content.splitlines()

results = []
for i, line in enumerate(lines, 1):
    for kw in keywords:
        if re.search(r'\b' + re.escape(kw) + r'\b', line, re.IGNORECASE):
            results.append((i, line.strip()))
            break

with open("scratch/search_results.txt", "w", encoding="utf-8") as f_out:
    for line_num, text in results:
        f_out.write(f"Line {line_num}: {text}\n")

print(f"Search complete. Found {len(results)} matches.")
