with open('utils/file_manager.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('_("Chuyển qua\n>>")', r'_("Chuyển qua\n>>")')
text = text.replace('_("Nhận về\n<<")', r'_("Nhận về\n<<")')

with open('utils/file_manager.py', 'w', encoding='utf-8') as f:
    f.write(text)
