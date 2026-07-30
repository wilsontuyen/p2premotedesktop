import os
import ast
import json

missing = set()

def extract_strings(node):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == '_':
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            missing.add(node.args[0].value)
    for child in ast.iter_child_nodes(node):
        extract_strings(child)

for root, _, files in os.walk('.'):
    if 'dist' in root or 'build' in root or 'venv' in root or '.git' in root or 'lang' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                try:
                    tree = ast.parse(f.read())
                    extract_strings(tree)
                except:
                    pass

try:
    with open('lang/en.json', 'r', encoding='utf-8') as f:
        en_dict = json.load(f)
except:
    en_dict = {}

actually_missing = [m for m in missing if m not in en_dict]
import io
with io.open('missing_langs.json', 'w', encoding='utf-8') as f:
    json.dump(actually_missing, f, ensure_ascii=False, indent=4)
