import os
import sys
import subprocess
import shutil
import time

workspace_dir = r"C:\Users\Tuyen\.gemini\antigravity\scratch\remote_desktop"
target_dir = r"C:\Apps\P2P"
log_path = os.path.join(workspace_dir, "build_deploy.log")

def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}\n"
    print(log_line, end="")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"Failed to write log: {e}")

def run_cmd(cmd, cwd=workspace_dir):
    log(f"Running command: {cmd}")
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=cwd)
    output_lines = []
    while True:
        line = p.stdout.readline()
        if not line:
            break
        output_lines.append(line)
        # log in real time
        print(line, end="")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except:
            pass
    p.wait()
    if p.returncode != 0:
        log(f"Command failed with exit code {p.returncode}")
        return False
    return True

def main():
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except: pass

    log("=== STARTING BUILD AND DEPLOYMENT ===")

    # 1. Stop Scheduled Task
    log("Stopping scheduled task 'EasyRemoteDesktopAgent'...")
    subprocess.run("schtasks /end /tn \"EasyRemoteDesktopAgent\"", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("powershell -Command \"Stop-ScheduledTask -TaskName 'EasyRemoteDesktopAgent' -ErrorAction SilentlyContinue\"", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 2. Terminate running instances to release file locks
    log("Terminating any running instances of agent or service...")
    subprocess.run("taskkill /F /IM RemoteDesktopP2P.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("taskkill /F /IM RemoteDesktopService.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

    # 3. Build Service using Nuitka (standalone)
    log("Building RemoteDesktopService via Nuitka (standalone)...")
    python_path = os.path.join(workspace_dir, ".venv", "Scripts", "python.exe")
    nuitka_service_cmd = f'"{python_path}" -m nuitka --standalone --windows-disable-console --windows-uac-admin --windows-icon-from-ico=app_icon.ico --output-dir=dist_nuitka_service windows_service_loop.py'
    if not run_cmd(nuitka_service_cmd):
        log("ERROR: Nuitka service build failed. Aborting deployment.")
        return

    # 4. Build Agent using Nuitka
    log("Building RemoteDesktopP2P via Nuitka (standalone)...")
    python_path = os.path.join(workspace_dir, ".venv", "Scripts", "python.exe")
    nuitka_cmd = f'"{python_path}" -m nuitka --standalone --windows-disable-console --enable-plugin=tk-inter --windows-icon-from-ico=app_icon.ico --nofollow-import-to=pygame.tests,unittest,sqlite3,numpy,cv2 --output-dir=dist_nuitka app.py'
    if not run_cmd(nuitka_cmd):
        log("ERROR: Nuitka build failed. Aborting deployment.")
        return

    # 5. Post-build renaming and asset preparation
    log("Preparing build outputs...")
    app_dist_dir = os.path.join(workspace_dir, "dist_nuitka", "app.dist")
    
    # Rename app.exe -> RemoteDesktopP2P.exe
    old_exe = os.path.join(app_dist_dir, "app.exe")
    new_exe = os.path.join(app_dist_dir, "RemoteDesktopP2P.exe")
    if os.path.exists(old_exe):
        try:
            if os.path.exists(new_exe):
                os.remove(new_exe)
            os.rename(old_exe, new_exe)
            log("Successfully renamed app.exe to RemoteDesktopP2P.exe")
        except Exception as e:
            log(f"Failed to rename app.exe: {e}")
            return
            
    # Copy Nuitka Service standalone files into app.dist (merging them)
    service_dist_dir = os.path.join(workspace_dir, "dist_nuitka_service", "windows_service_loop.dist")
    if os.path.exists(service_dist_dir):
        log("Merging RemoteDesktopService standalone files into app.dist...")
        for item in os.listdir(service_dist_dir):
            s = os.path.join(service_dist_dir, item)
            d = os.path.join(app_dist_dir, item)
            if item.lower() == "windows_service_loop.exe":
                d = os.path.join(app_dist_dir, "RemoteDesktopService.exe")
            try:
                if os.path.isdir(s):
                    if os.path.exists(d):
                        shutil.rmtree(d)
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
            except Exception as e:
                log(f"Warning: Failed to merge service file {item}: {e}")
    else:
        log("ERROR: Compiled RemoteDesktopService standalone directory not found!")
        return

    # Copy icons, install.bat, uninstall.bat and readme.txt to app.dist
    files_to_copy = ["app_icon.png", "app_icon.ico", "install.bat", "uninstall.bat", "readme.txt"]
    for file_name in files_to_copy:
        src = os.path.join(workspace_dir, file_name)
        dst = os.path.join(app_dist_dir, file_name)
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
                log(f"Copied {file_name} to app.dist")
            except Exception as e:
                log(f"Failed to copy {file_name}: {e}")

    # Make zip archive
    log("Creating RemoteDesktopP2P.zip archive...")
    zip_path = os.path.join(workspace_dir, "RemoteDesktopP2P")
    try:
        shutil.make_archive(zip_path, 'zip', app_dist_dir)
        log("Archive created successfully.")
    except Exception as e:
        log(f"Warning: Failed to create zip archive: {e}")

    # 6. Deploy to D:\Apps\P2P
    log("Ensuring all running instances are terminated right before deployment to release file locks...")
    subprocess.run("taskkill /F /IM RemoteDesktopP2P.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("taskkill /F /IM RemoteDesktopService.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

    log(f"Deploying files to {target_dir}...")
    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir)
            log(f"Created target directory {target_dir}")
        except Exception as e:
            log(f"Failed to create target directory: {e}")
            return

    # Copy Nuitka app.dist contents (overwrite existing)
    log(f"Copying all agent, service and installation files to {target_dir}...")
    errors = 0
    for item in os.listdir(app_dist_dir):
        s = os.path.join(app_dist_dir, item)
        d = os.path.join(target_dir, item)
        try:
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
        except Exception as e:
            log(f"Error copying {item}: {e}")
            errors += 1

    if errors > 0:
        log(f"Deployment completed with {errors} errors.")
    else:
        log("Deployment completed successfully!")

    # 7. Start Scheduled Task
    log("Starting scheduled task 'EasyRemoteDesktopAgent'...")
    subprocess.run("powershell -Command \"Start-ScheduledTask -TaskName 'EasyRemoteDesktopAgent' -ErrorAction SilentlyContinue\"", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 8. Start GUI Agent
    log("Starting GUI Agent on user desktop...")
    gui_exe = os.path.join(target_dir, "RemoteDesktopP2P.exe")
    if os.path.exists(gui_exe):
        try:
            # Start GUI agent in a non-blocking way
            subprocess.Popen(f'"{gui_exe}"', shell=True, cwd=target_dir)
            log("GUI Agent started successfully.")
        except Exception as e:
            log(f"Failed to start GUI Agent: {e}")

    log("=== BUILD AND DEPLOYMENT FINISHED ===")

if __name__ == "__main__":
    main()
