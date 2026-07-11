import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"
components_py = "d:/Data/AG/remote_desktop/gui/components.py"

with open(app_py, "r", encoding="utf-8") as f:
    content = f.read()

# Extract ToolTip
tt_pattern = re.compile(
    r"class ToolTip\(object\):.*?\n        if self\.tw:\n            self\.tw\.destroy\(\)\n            self\.tw = None\n",
    re.DOTALL
)

match = tt_pattern.search(content)
if match:
    tt_code = match.group(0)
    # Remove from app.py
    content = content[:match.start()] + content[match.end():]
    
    # Append to components.py
    with open(components_py, "a", encoding="utf-8") as f:
        f.write("\n" + tt_code)
        
    with open(app_py, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Moved ToolTip to gui/components.py")
else:
    print("ToolTip not found!")
