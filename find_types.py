import re
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()
types = set(re.findall(r'"type"\s*:\s*"([^"]+)"', content) + re.findall(r"'type'\s*:\s*'([^']+)'", content))
print("\n".join(types))
