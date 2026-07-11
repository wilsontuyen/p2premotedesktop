import re
import os

log_path = r"C:\Apps\P2P\clipboard_agent.log"
out_path = r"d:\Data\AG\remote_desktop\scratch\unique_messages.txt"
if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    
    unique_messages = set()
    for line in lines:
        line_clean = line.strip()
        # Remove date, time, PID
        match = re.match(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\s+\[PID \d+\]\s+(.*)$", line_clean)
        if match:
            msg = match.group(1)
        else:
            msg = line_clean
            
        # Filter out startup noise
        if any(x in msg for x in [_("Khởi động"), _("Thư mục ứng dụng"), _("Window ẩn"), _("Đang chờ kết nối"), "===="]):
            continue
        # Also check unicode escaped forms
        if any(x in msg for x in ["Kh\\u1edfi \\u0111\\u1ed9ng", "Th\\u01b0 m\\u1ee5c", "Window \\u1ea5n", "\\u0110ang ch\\u1edd"]):
            continue
            
        unique_messages.add(msg)
        
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"Total lines: {len(lines)}\n")
        f.write(f"Unique interesting messages ({len(unique_messages)}):\n")
        for u in sorted(list(unique_messages)):
            f.write(u + "\n")
    print("Successfully wrote to unique_messages.txt")
else:
    print("Log file not found.")
