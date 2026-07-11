"""
Update all language JSON files with new keys from lang_template.json.
New keys will have empty string values (to be translated).
"""
import json, os

# Load template
with open('lang/lang_template.json', 'r', encoding='utf-8') as f:
    template = json.load(f)

lang_dir = 'lang'
updated = []

for fname in os.listdir(lang_dir):
    if fname.endswith('.json') and fname != 'lang_template.json':
        fpath = os.path.join(lang_dir, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            lang_data = json.load(f)
        
        new_keys = set(template.keys()) - set(lang_data.keys())
        if new_keys:
            for key in sorted(new_keys):
                lang_data[key] = ""  # Empty = needs translation
            
            # Sort and write back
            sorted_data = dict(sorted(lang_data.items(), key=lambda x: x[0].lower()))
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(sorted_data, f, ensure_ascii=False, indent=2)
            
            updated.append((fname, len(new_keys)))

if updated:
    with open('lang_update_report.txt', 'w', encoding='utf-8') as f:
        f.write("Language files updated:\n")
        for fname, count in updated:
            f.write(f"  {fname}: {count} new keys added\n")
    print("Updated language files. See lang_update_report.txt")
else:
    print("All language files are up to date.")
