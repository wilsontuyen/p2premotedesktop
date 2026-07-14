import sys, re
with open('utils/file_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

with open('temp_dialog.py', 'r', encoding='utf-8') as f:
    dialog_code = f.read()

idx = content.find('def open_transfer_window')
if 'def inline_ask_string' not in content:
    content = content[:idx] + dialog_code + '\n\n' + content[idx:]

content = content.replace('from tkinter import simpledialog', '')
content = re.sub(r'simpledialog\.askstring\(_\(\"(.*?)\"\),\s*_\(\"(.*?)\"\),\s*parent=top\)', r'inline_ask_string(top, _("\1"), _("\2"))', content)
content = re.sub(r'simpledialog\.askstring\(_\(\"(.*?)\"\),\s*_\(\"(.*?)\"\)\.format\(name=name\),\s*initialvalue=name,\s*parent=top\)', r'inline_ask_string(top, _("\1"), _("\2").format(name=name), initialvalue=name)', content)

content = content.replace('("Xem file")', '("Xem tệp")')

with open('utils/file_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
