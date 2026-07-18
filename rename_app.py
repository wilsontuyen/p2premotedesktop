import os
import glob

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "Antigravity Remote Desktop" in content:
            new_content = content.replace("Antigravity Remote Desktop", "Easy Remote Desktop")
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Replaced in: {filepath}")
    except Exception as e:
        pass

def main():
    skip_dirs = ['.git', '.venv', 'dist', 'build', 'dist_nuitka', 'dist_service', '__pycache__', 'scratch', 'app.dist', '.agents']
    
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for file in files:
            if file.endswith(('.py', '.sh', '.iss', '.md', '.txt', '.json', '.bat', '.ps1', '.service')):
                if "temp_" in file or "scratch" in file or file == "rename_app.py" or file.startswith("search_"):
                    continue
                replace_in_file(os.path.join(root, file))

if __name__ == "__main__":
    main()
