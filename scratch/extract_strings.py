import re
import json

with open('../app.py', 'r', encoding='utf-8') as f:
    content = f.read()

labels = re.findall(r'label="([^"]+)"', content)
texts = re.findall(r'text="([^"]+)"', content)
titles = re.findall(r'\.title\("([^"]+)"\)', content)
messageboxes = re.findall(r'messagebox\.[a-z]+\("([^"]+)", "([^"]+)"\)', content)

all_strings = set(labels + texts + titles)
for m in messageboxes:
    all_strings.add(m[0])
    all_strings.add(m[1])

# Filter out empty, very short strings that are likely not UI text
all_strings = {s for s in all_strings if len(s) > 1 and not s.isdigit()}

out = {s: s for s in sorted(list(all_strings))}

with open('lang_vi.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print("Extracted strings count:", len(out))
