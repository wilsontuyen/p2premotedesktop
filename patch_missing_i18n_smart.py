import os
import re

def has_vietnamese(s):
    vn_chars = set(_("áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ"))
    return any(c in vn_chars for c in s)

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = []
    changed = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            new_lines.append(line)
            continue
        if 'print(' in line or 'log' in line.lower() or 'traceback' in line.lower() or 'Exception' in line:
            new_lines.append(line)
            continue

        new_line = line
        
        # Double quotes
        for m in reversed(list(re.finditer(r'(?<!")"([^"\\]+)"(?!")', new_line))):
            start = m.start()
            end = m.end()
            val = m.group(1)
            
            if not has_vietnamese(val): continue
            if start > 0 and new_line[start-1] in 'fbr': continue
            if start >= 2 and new_line[start-2:start] == '_(': continue
            
            new_line = new_line[:start] + f'_("{val}")' + new_line[end:]
            changed = True
            
        # Single quotes
        for m in reversed(list(re.finditer(r"(?<!')'([^'\\]+)'(?!')", new_line))):
            start = m.start()
            end = m.end()
            val = m.group(1)
            
            if not has_vietnamese(val): continue
            if start > 0 and new_line[start-1] in 'fbr': continue
            if start >= 2 and new_line[start-2:start] == '_(': continue
            
            new_line = new_line[:start] + f"_('{val}')" + new_line[end:]
            changed = True
            
        new_lines.append(new_line)
        
    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
        print(f"Patched {filepath}")

for root, dirs, files in os.walk('.'):
    if any(x in root for x in ['.venv', 'build', 'dist', 'dist_nuitka', '__pycache__', 'pyinstaller', 'env', 'Lib', 'lang']):
        continue
    for file in files:
        if file.endswith('.py') and not file.startswith('temp_') and not file.startswith('old_') and not file.startswith('original_') and 'app_old' not in file and 'app_head' not in file:
            filepath = os.path.join(root, file)
            try:
                process_file(filepath)
            except Exception as e:
                print(f"Error {filepath}: {e}")
