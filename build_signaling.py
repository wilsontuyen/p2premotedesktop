import os
import subprocess
import shutil
import time

workspace_dir = os.path.dirname(os.path.abspath(__file__))
python_path = os.path.join(workspace_dir, ".venv", "Scripts", "python.exe")
signaling_script = os.path.join(workspace_dir, "signaling_server.py")
output_dir = os.path.join(workspace_dir, "dist_signaling")

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def main():
    log("=== STARTING SIGNALING SERVER BUILD ===")
    
    if os.path.exists(output_dir):
        log(f"Cleaning up old output directory: {output_dir}")
        try:
            shutil.rmtree(output_dir)
        except Exception as e:
            log(f"Warning: failed to delete old output directory: {e}")

    # Build using Nuitka
    log("Building signaling_server via Nuitka (standalone)...")
    cmd = f'"{python_path}" -m nuitka --standalone --output-dir=dist_signaling signaling_server.py'
    log(f"Running: {cmd}")
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=workspace_dir)
    
    while True:
        line = p.stdout.readline()
        if not line:
            break
        print(line, end="")
    p.wait()
    
    if p.returncode != 0:
        log(f"ERROR: Nuitka build failed with exit code {p.returncode}")
        return

    # Check for output dist folder
    dist_folder = os.path.join(output_dir, "signaling_server.dist")
    if not os.path.exists(dist_folder):
        log(f"ERROR: Standalone folder not found at {dist_folder}")
        return

    # Zip the archive
    log("Creating signaling_server.zip...")
    zip_base = os.path.join(workspace_dir, "signaling_server")
    try:
        shutil.make_archive(zip_base, 'zip', dist_folder)
        log("Zip archive created successfully!")
    except Exception as e:
        log(f"ERROR: Failed to create zip archive: {e}")
        return

    log("=== BUILD SIGNALING SERVER FINISHED ===")

if __name__ == "__main__":
    main()
