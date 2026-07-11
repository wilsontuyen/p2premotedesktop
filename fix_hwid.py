import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"
hwid_py = "d:/Data/AG/remote_desktop/utils/hwid.py"

with open(app_py, "r", encoding="utf-8") as f:
    app_content = f.read()

# Extract get_public_ip from app.py
pattern_ip = re.compile(r"def get_public_ip\(\):.*?return \"127\.0\.0\.1\"\n", re.DOTALL)
match_ip = pattern_ip.search(app_content)

if match_ip:
    ip_code = match_ip.group(0)
    app_content = app_content.replace(ip_code, "")
    
    with open(app_py, "w", encoding="utf-8") as f:
        f.write(app_content)
        
    with open(hwid_py, "a", encoding="utf-8") as f:
        f.write("\n" + ip_code)
    print("Fixed get_public_ip")
else:
    print("get_public_ip not found in app.py")
