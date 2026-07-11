import os
import shutil

# Paths
base_dir = "d:/Data/AG/remote_desktop"
gui_fm = os.path.join(base_dir, "gui", "file_manager.py")
utils_fm = os.path.join(base_dir, "utils", "file_manager.py")

utils_themes = os.path.join(base_dir, "utils", "themes.py")
gui_themes = os.path.join(base_dir, "gui", "themes.py")

# Move files
if os.path.exists(gui_fm):
    shutil.move(gui_fm, utils_fm)

if os.path.exists(utils_themes):
    shutil.move(utils_themes, gui_themes)

# Update app.py
app_py = os.path.join(base_dir, "app.py")
with open(app_py, "r", encoding="utf-8") as f:
    app_content = f.read()
    
app_content = app_content.replace("from utils.themes import", "from gui.themes import")
with open(app_py, "w", encoding="utf-8") as f:
    f.write(app_content)

# Update viewer.py
viewer_py = os.path.join(base_dir, "core", "viewer.py")
with open(viewer_py, "r", encoding="utf-8") as f:
    viewer_content = f.read()

viewer_content = viewer_content.replace("from gui.file_manager import", "from utils.file_manager import")
with open(viewer_py, "w", encoding="utf-8") as f:
    f.write(viewer_content)

print("Swapped file_manager and themes locations and updated imports!")
