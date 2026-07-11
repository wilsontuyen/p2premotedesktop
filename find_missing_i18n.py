"""Script to find all Vietnamese strings not wrapped in _() in app.py"""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

def has_vietnamese(s):
    return any(ord(c) > 127 for c in s)

missing = []
for i, line in enumerate(lines, 1):
    stripped = line.strip()
    if stripped.startswith('#') or not stripped:
        continue
    
    for m in re.finditer(r'"([^"]*)"', line):
        val = m.group(1)
        if not has_vietnamese(val):
            continue
        start = m.start()
        prefix = line[max(0, start-2):start]
        if '_(' in prefix:
            continue
        # Skip template dict entries
        if stripped.startswith('"') and '": "' in stripped:
            continue
        # Skip print/log
        if 'print(' in line or 'log(' in line.lower():
            continue
        # Skip comments
        if stripped.startswith('#'):
            continue
        missing.append((i, val, line.rstrip()))

with open('missing_i18n.txt', 'w', encoding='utf-8') as f:
    f.write(f"Found {len(missing)} missing translations:\n")
    f.write("=" * 80 + "\n")
    for num, val, context in missing:
        f.write(f"Line {num}: \"{val}\"\n")
        f.write(f"  Context: {context.strip()[:150]}\n\n")

print(f"Found {len(missing)} missing translations. See missing_i18n.txt")
