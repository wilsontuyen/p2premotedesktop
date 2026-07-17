import os
import re
import json

base_dir = 'd:/Data/AG/remote_desktop'
files_to_scan = [
    'app.py',
    'core/host.py',
    'core/viewer.py',
    'core/network_manager.py',
    'gui/components.py'
]

all_strings = set()

for file in files_to_scan:
    path = os.path.join(base_dir, file)
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # find all _("...") and _('...')
    matches1 = re.findall(r'_\(\s*"(.*?)"\s*\)', content)
    matches2 = re.findall(r"_\(\s*'(.*?)'\s*\)", content)
    
    all_strings.update(matches1)
    all_strings.update(matches2)

# filter out empty
all_strings = {s for s in all_strings if len(s.strip()) > 0}

out = {s: s for s in sorted(list(all_strings))}

lang_dir = os.path.join(base_dir, 'lang')
os.makedirs(lang_dir, exist_ok=True)
template_path = os.path.join(lang_dir, 'lang_template.json')

existing = {}
if os.path.exists(template_path):
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    except:
        pass

for k in existing:
    out[k] = existing[k]

with open(template_path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print('Extracted', len(out), 'strings into', template_path)
