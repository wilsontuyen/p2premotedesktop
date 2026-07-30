import json
import os

missing_en = {
    '{item_type} với tên "{item_name}" đã tồn tại.': '{item_type} named "{item_name}" already exists.',
    '{dst_title}\\n- Vị trí: {dst_path}\\n- Dung lượng: {dst_sz}{dst_extra}\\n- Ngày sửa đổi: {dst_mtime}': '{dst_title}\\n- Location: {dst_path}\\n- Size: {dst_sz}{dst_extra}\\n- Modified: {dst_mtime}',
    '{src_title}\\n- Vị trí: {src_path}\\n- Dung lượng: {src_sz}{src_extra}\\n- Ngày sửa đổi: {src_mtime}': '{src_title}\\n- Location: {src_path}\\n- Size: {src_sz}{src_extra}\\n- Modified: {src_mtime}',
    'P2P Remote Desktop Viewer': 'P2P Remote Desktop Viewer',
    'P2P REMOTE DESKTOP': 'P2P REMOTE DESKTOP',
    'Options': 'Options',
    'Help': 'Help',
    'File': 'File',
    'Zalo': 'Zalo',
    'Cam': 'Cam',
    'About': 'About',
    'AI Pro Version': 'AI Pro Version',
    'OK': 'OK'
}

# Update en.json
with open('lang/en.json', 'r', encoding='utf-8') as f:
    en_dict = json.load(f)
for k, v in missing_en.items():
    if k not in en_dict:
        en_dict[k] = v
with open('lang/en.json', 'w', encoding='utf-8') as f:
    json.dump(en_dict, f, ensure_ascii=False, indent=4)

# Update lang_template.json
with open('lang/lang_template.json', 'r', encoding='utf-8') as f:
    tmpl_dict = json.load(f)
for k in missing_en.keys():
    if k not in tmpl_dict:
        tmpl_dict[k] = k
with open('lang/lang_template.json', 'w', encoding='utf-8') as f:
    json.dump(tmpl_dict, f, ensure_ascii=False, indent=4)
