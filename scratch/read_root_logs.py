import os
import glob

output_lines = []
log_files = glob.glob("*.log")
for lf in log_files:
    output_lines.append(f"=== {lf} ===\n")
    with open(lf, "r", encoding="utf-8", errors="ignore") as f:
        # read last 200 lines
        lines = f.readlines()
        output_lines.extend(lines[-200:])
        output_lines.append("\n\n")

with open("scratch/root_logs_output.txt", "w", encoding="utf-8") as f:
    f.writelines(output_lines)
