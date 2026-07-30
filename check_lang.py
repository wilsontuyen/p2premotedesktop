import os
import re
import json

missing = set()
try:
    with open('lang/en.json', 'r', encoding='utf-8') as f:
        en_dict = json.load(f)
except Exception as e:
    print(e)
    en_dict = {}

for root, _, files in os.walk('.'):
    if 'dist' in root or 'build' in root or '.git' in root or 'lang' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            with open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            matches = re.findall(r'_\(\"(.*?)\"\)', content)
            matches.extend(re.findall(r'_\(\'(.*?)\'\)', content))
            for m in matches:
                if m not in en_dict:
                    missing.add(m)

import json
with open('missing_langs.json', 'w', encoding='utf-8') as f:
    json.dump(list(missing), f, ensure_ascii=False, indent=4)
