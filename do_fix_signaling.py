import os
import re

for filepath in ["d:/Data/AG/remote_desktop/app.py", "d:/Data/AG/remote_desktop/core/network_manager.py"]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace reading instances (ignoring the ones already prefixed with core.config.)
    content = re.sub(r"(?<!core\.config\.)SIGNALING_SERVER_HOSTS", "core.config.SIGNALING_SERVER_HOSTS", content)
    content = re.sub(r"(?<!core\.config\.)SIGNALING_SERVER_PORT", "core.config.SIGNALING_SERVER_PORT", content)
    # also add import core.config if not present
    if "import core.config" not in content:
        content = content.replace("from core.config import *", "from core.config import *\nimport core.config")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print("Fixed SIGNALING_SERVER_HOSTS and SIGNALING_SERVER_PORT references")
