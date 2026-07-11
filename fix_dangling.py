import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the dangling code from UPnP replacement error
pattern = re.compile(
    r"\n        \n    print\(f\"\[UPnP\] Found router XML description at: \{location_url\}\"\).*?    return False\n",
    re.DOTALL
)

content, n = pattern.subn("", content)
print(f"Removed dangling UPnP code: {n} match(es)")

with open(app_py, "w", encoding="utf-8") as f:
    f.write(content)
