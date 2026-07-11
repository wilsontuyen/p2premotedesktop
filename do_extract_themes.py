import os
import re

app_py = "d:/Data/AG/remote_desktop/app.py"
theme_py = "d:/Data/AG/remote_desktop/utils/themes.py"

with open(app_py, "r", encoding="utf-8") as f:
    app_content = f.read()

# Extract the get_theme_palette function
pattern = re.compile(r"(\s*)def get_theme_palette\(self, theme_name\):.*?(?=\n\s*def change_theme\(self\):)", re.DOTALL)
match = pattern.search(app_content)

if match:
    func_code = match.group(0)
    
    # Remove from app.py
    app_content = app_content.replace(func_code, "")
    
    # Also replace calls to self.get_theme_palette with get_theme_palette
    app_content = app_content.replace("self.get_theme_palette", "get_theme_palette")
    
    # Add import
    app_content = app_content.replace("from utils.hwid", "from utils.themes import get_theme_palette\nfrom utils.hwid")
    
    with open(app_py, "w", encoding="utf-8") as f:
        f.write(app_content)
        
    # Re-indent and clean up func_code for standalone
    func_code_lines = func_code.split("\n")
    cleaned_lines = []
    for line in func_code_lines:
        if line.startswith("    "):
            cleaned_lines.append(line[4:])
        else:
            cleaned_lines.append(line)
            
    # Remove 'self, ' from def get_theme_palette(self, theme_name):
    cleaned_code = "\n".join(cleaned_lines)
    cleaned_code = cleaned_code.replace("def get_theme_palette(self, theme_name):", "def get_theme_palette(theme_name):")
    
    with open(theme_py, "w", encoding="utf-8") as f:
        f.write(cleaned_code.strip() + "\n")
        
    print("Successfully extracted get_theme_palette to utils/themes.py")
else:
    print("Could not find get_theme_palette in app.py")
