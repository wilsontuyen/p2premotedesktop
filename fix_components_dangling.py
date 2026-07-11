import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# Remove dangling part of ProgressDialog and ConfirmDialog
pattern = re.compile(
    r"\n            self\.deiconify\(\).*?# --- NATIVE CLIPBOARD EVENT LISTENER ---\n",
    re.DOTALL
)

content, n = pattern.subn("\n# --- NATIVE CLIPBOARD EVENT LISTENER ---\n", content)
print(f"Removed dangling components code: {n} match(es)")

with open(app_py, "w", encoding="utf-8") as f:
    f.write(content)
