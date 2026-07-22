import os
import sys

def patch_app_py():
    path = "app.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Add APP_FONT_NAME definition
    if 'APP_FONT_NAME = "Segoe UI"' not in content:
        import_sys = "import sys"
        font_def = """import sys\nAPP_FONT_NAME = "Segoe UI" if sys.platform == "win32" else "Helvetica"\n"""
        content = content.replace(import_sys, font_def, 1)
    
    # Replace all literal "Segoe UI" with APP_FONT_NAME
    content = content.replace('"Segoe UI"', 'APP_FONT_NAME')
    content = content.replace("'Segoe UI'", 'APP_FONT_NAME')

    # Fix E() function
    old_e = """def E(text):
    import sys
    if sys.platform != "win32" or platform.release() in ["7", "8", "8.1"]:"""
    new_e = """def E(text):
    import sys
    if sys.platform == "darwin":
        return text
    if sys.platform != "win32" or platform.release() in ["7", "8", "8.1"]:"""
    content = content.replace(old_e, new_e)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    patch_app_py()
    print("Done")
