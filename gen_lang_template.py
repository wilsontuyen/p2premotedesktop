"""
Auto-generate lang_template.json by scanning all .py files for all _() calls.
"""
import os
import re
import json

strings = set()

# Scan all python files in the directory
for root, dirs, files in os.walk('.'):
    # skip virtual environments and build directories
    if any(x in root for x in ['.venv', 'build', 'dist', 'dist_nuitka', '__pycache__', 'pyinstaller', 'env', 'Lib']):
        continue
    for file in files:
        if file.endswith('.py') and not file.startswith(('original_', 'temp_', 'old_', 'patch_', 'do_patch_', 'fix_')) and file != 'temp.py' and 'app_old' not in file and 'app_head' not in file:
            filepath = os.path.join(root, file)
            try:
                # Need to read as latin-1 or try-except utf-8 if the files are broken, but utf-8 is preferred for our own files
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Match _("...") but do not cross newlines
                for m in re.finditer(r'_\("([^"\n\r]+)"\)', content):
                    strings.add(m.group(1))
                
                # Match _('...') but do not cross newlines 
                for m in re.finditer(r"_\('([^'\n\r]+)'\)", content):
                    strings.add(m.group(1))
            except Exception as e:
                pass

# Sort for consistent output
sorted_strings = sorted(strings, key=lambda s: s.lower())

template = {}
for s in sorted_strings:
    template[s] = s  # value = key (Vietnamese is the default)

# Write template
with open('lang/lang_template.json', 'w', encoding='utf-8') as f:
    json.dump(template, f, ensure_ascii=False, indent=2)

print(f"Generated lang_template.json with {len(template)} entries.")

# Also show newly added entries
try:
    with open('lang/en.json', 'r', encoding='utf-8') as f:
        en = json.load(f)
    
    new_keys = set(template.keys()) - set(en.keys())
    if new_keys:
        print(f"\n{len(new_keys)} NEW keys not in en.json:")
        for k in sorted(new_keys):
            print(f"  - {k}")
except Exception as e:
    pass

