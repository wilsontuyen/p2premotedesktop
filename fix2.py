with open('utils/file_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("\\'", "'")

with open('utils/file_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
