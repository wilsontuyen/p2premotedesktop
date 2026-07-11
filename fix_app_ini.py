import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"
with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# Remove the duplicated configparser block
pattern = re.compile(r"import configparser\n\n# Real-time TCP Signaling Server configuration.*?print\(f\"\[Config\] Error reading server\.ini: \{e\}\"\)\n", re.DOTALL)
content = pattern.sub("", content)

# Write back
with open(app_py, "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed app.py indentation and duplicated server.ini loading")
