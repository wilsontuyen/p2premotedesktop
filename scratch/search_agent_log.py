import os

log_path = r"C:\Apps\P2P\clipboard_agent.log"
output_lines = []

if os.path.exists(log_path):
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            # Look for errors, warnings, empty clipboard, or clear/skip clear messages
            lower_line = line.lower()
            if any(k in lower_line for k in [_("lỗi"), "error", "exception", _("cảnh báo"), _("bỏ qua dọn dẹp"), _("hết thời gian"), _("bị hủy"), _("openclipboard thất bại"), "emptyclipboard"]):
                output_lines.append(line)
else:
    output_lines.append("Log file not found.")

with open("scratch/search_agent_log.txt", "w", encoding="utf-8") as f:
    f.writelines(output_lines[-150:])  # last 150 matching lines
