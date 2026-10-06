import os, re
count = 0
for r, d, files in os.walk('.'):
    if '.venv' in r or 'dist' in r or 'build' in r:
        continue
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(r, f)
            try:
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
            except Exception:
                continue
            
            lines = content.split('\n')
            changed = False
            for i, line in enumerate(lines):
                if 'open(' in line and 'log' in line.lower() and 'utf-8' in line and 'utf-8-sig' not in line:
                    new_line = line.replace('encoding="utf-8"', 'encoding="utf-8-sig"')
                    new_line = new_line.replace("encoding='utf-8'", "encoding='utf-8-sig'")
                    if new_line != line:
                        lines[i] = new_line
                        changed = True
                        count += 1
                        
            if changed:
                with open(path, 'w', encoding='utf-8', newline='') as file:
                    file.write('\n'.join(lines))
                print(f"Patched {path}")

print(f"Total lines patched: {count}")
