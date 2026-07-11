import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"

with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the rest of dangling code
pattern = re.compile(
    r"\n        parsed_loc = urllib.parse.urlparse\(location_url\).*?    return False\n",
    re.DOTALL
)

content, n = pattern.subn("", content)
print(f"Removed rest of dangling UPnP code: {n} match(es)")

with open(app_py, "w", encoding="utf-8") as f:
    f.write(content)
