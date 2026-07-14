import os
import ast
import json

keys = set()
for root, dirs, files in os.walk('.'):
    if 'venv' in root or '.git' in root or 'dist' in root or '__pycache__' in root: continue
    for f in files:
        if f.endswith('.py'):
            filepath = os.path.join(root, f)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and node.func.id == '_':
                                if node.args and isinstance(node.args[0], ast.Constant):
                                    keys.add(node.args[0].value)
                except Exception:
                    pass

with open('lang/lang_template.json', 'r', encoding='utf-8') as f:
    template = json.load(f)

# Remove bad keys from template
bad_keys = [k for k in template if k.endswith('\\') or '_(' in k or '{item_type} với tên \\' in k]
for k in bad_keys:
    del template[k]

new_keys = []
for k in keys:
    if k not in template:
        new_keys.append(k)

# Update template
for k in keys:
    if k not in template:
        template[k] = ""

with open('lang/lang_template.json', 'w', encoding='utf-8') as f:
    json.dump(template, f, ensure_ascii=False, indent=2)

print("Updated with", len(new_keys), "new keys.")
print("Removed bad keys:", len(bad_keys))
