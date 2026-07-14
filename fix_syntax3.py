with open('utils/file_manager.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('_("{src_title}\n', '_("""{src_title}\n')
text = text.replace('\n- Ngày sửa đổi: {src_mtime}").format', '\n- Ngày sửa đổi: {src_mtime}""").format')
text = text.replace('_("{dst_title}\n', '_("""{dst_title}\n')
text = text.replace('\n- Ngày sửa đổi: {dst_mtime}").format', '\n- Ngày sửa đổi: {dst_mtime}""").format')

with open('utils/file_manager.py', 'w', encoding='utf-8') as f:
    f.write(text)
