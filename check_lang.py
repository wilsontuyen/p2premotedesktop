import json, re

with open('lang/en.json', 'r', encoding='utf-8') as f:
    en_dict = json.load(f)

with open('gui/mac_ui.py', 'r', encoding='utf-8') as f:
    content = f.read()

keys = re.findall(r'_\(["\'](.*?)["\']\)', content)
missing = [k for k in set(keys) if k not in en_dict]
print('Missing translations in en.json:')
for m in missing:
    print('-', m)
