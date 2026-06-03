import sys

with open('d:/Data/AG/remote_desktop/app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open('d:/Data/AG/remote_desktop/scratch/lines.txt', 'w', encoding='utf-8') as out:
    for i, line in enumerate(lines):
        if "Không thể kết nối Signaling Server" in line:
            out.write(f"Line {i+1}: {line.strip()}\n")
