import json
import re

with open('scratch/lang_vi.json', 'r', encoding='utf-8') as f:
    lang_dict = json.load(f)

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add import at the top
if 'from core.i18n import' not in content:
    content = content.replace('from core.config import *', 'from core.config import *\nfrom core.i18n import _, load_language, get_available_languages, export_template\n')

keys_to_replace = list(lang_dict.keys())
# Sort by length descending to replace longer strings first
keys_to_replace.sort(key=len, reverse=True)

def escape_regex(s):
    return re.escape(s)

for k in keys_to_replace:
    # replace text="k" -> text=_( "k" ) (spaces used temporarily to avoid double replacing if script run multiple times, actually we can just use _("{k}"))
    if 'text=_("' in content and f'"{k}")' in content: continue # prevent double replacement
    
    pattern1 = r'text\s*=\s*"' + escape_regex(k) + r'"'
    content = re.sub(pattern1, f'text=_("{k}")', content)
    
    pattern2 = r'label\s*=\s*"' + escape_regex(k) + r'"'
    content = re.sub(pattern2, f'label=_("{k}")', content)
    
    pattern3 = r'\.title\(\s*"' + escape_regex(k) + r'"\s*\)'
    content = re.sub(pattern3, f'.title(_("{k}"))', content)

    # Some messagebox calls:
    pattern4 = r'messagebox\.([a-z]+)\(\s*"' + escape_regex(k) + r'"\s*,'
    content = re.sub(pattern4, rf'messagebox.\1(_("{k}"),', content)

    pattern5 = r',\s*"' + escape_regex(k) + r'"\s*\)'
    content = re.sub(pattern5, rf', _("{k}"))', content)
    
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched app.py with i18n.")
