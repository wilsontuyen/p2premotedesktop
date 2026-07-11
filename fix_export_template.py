"""Fix the export_lang_template function by removing hardcoded dict remnants."""

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and remove the old dict entries (lines 524 to 616) and duplicate function call
new_lines = []
skip = False
for i, line in enumerate(lines):
    line_num = i + 1
    
    # Skip lines 524-621 (the old hardcoded dict that's dangling after our edit)
    if line_num == 524:
        skip = True
    
    if skip and line_num <= 621:
        continue
    else:
        skip = False
    
    new_lines.append(line)

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Removed {len(lines) - len(new_lines)} lines of old hardcoded dict.")
print(f"File now has {len(new_lines)} lines (was {len(lines)}).")
