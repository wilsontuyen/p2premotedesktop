import os
import glob

temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers")
output_lines = []
if os.path.exists(temp_dir):
    files = glob.glob(os.path.join(temp_dir, "clipboard_debug_*.log"))
    for f in sorted(files, key=os.path.getmtime, reverse=True)[:10]:
        output_lines.append(f"=== {os.path.basename(f)} ===\n")
        with open(f, "r", encoding="utf-8", errors="ignore") as file:
            output_lines.append(file.read())
            output_lines.append("\n\n")
else:
    output_lines.append("Temp directory does not exist.")

with open("scratch/read_logs_output.txt", "w", encoding="utf-8") as f:
    f.writelines(output_lines)
