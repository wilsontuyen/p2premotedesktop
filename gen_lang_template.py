"""
Auto-generate lang_template.json by scanning app.py for all _() calls.
"""
import re, json

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all _("...") and _('...') calls
strings = set()

# Match _("...")
for m in re.finditer(r'_\("([^"]+)"\)', content):
    strings.add(m.group(1))

# Match _('...')    
for m in re.finditer(r"_\('([^']+)'\)", content):
    strings.add(m.group(1))

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
with open('lang/en.json', 'r', encoding='utf-8') as f:
    en = json.load(f)

new_keys = set(template.keys()) - set(en.keys())
if new_keys:
    print(f"\n{len(new_keys)} NEW keys not in en.json:")
    for k in sorted(new_keys):
        print(f"  - {k}")
