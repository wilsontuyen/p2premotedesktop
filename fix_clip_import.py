import os

files = [
    "d:/Data/AG/remote_desktop/app.py",
    "d:/Data/AG/remote_desktop/core/host.py",
    "d:/Data/AG/remote_desktop/core/viewer.py"
]

for filepath in files:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 1. Update existing imports if they only import ClipboardSyncManager
    if "from core.clipboard_agent import ClipboardSyncManager\n" in content:
        content = content.replace(
            "from core.clipboard_agent import ClipboardSyncManager",
            "from core.clipboard_agent import ClipboardSyncManager, clipboard_sync_manager, run_clipboard_agent_mode"
        )
    # 2. Or if they don't have it but use clipboard_sync_manager, add it
    elif "clipboard_sync_manager" in content and "from core.clipboard_agent import" not in content:
        content = "from core.clipboard_agent import clipboard_sync_manager\n" + content
    # 3. Add to core/host.py if it was missing completely
    elif filepath.endswith("host.py") and "clipboard_sync_manager" in content and "ClipboardSyncManager" not in content:
        content = content.replace("from PIL import Image\n", "from PIL import Image\nfrom core.clipboard_agent import clipboard_sync_manager\n")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

print("Added clipboard_sync_manager imports")
