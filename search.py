import os

log_files = ["agent.log", "clipboard_debug.log", "service.log", "clipboard_agent.log"]
results = []

for filename in log_files:
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f):
                if any(x in line.lower() for x in ["clip", "openclipboard", _("lỗi"), "error", "fail"]):
                    results.append(f"{filename}:{idx+1}: {line.strip()}")

with open("search_res.txt", "w", encoding="utf-8") as out:
    out.write("\n".join(results))
