import os
import sys
import subprocess
import shutil
import time

workspace_dir = os.path.dirname(os.path.abspath(__file__))
target_dir = r"C:\Apps\P2P"
log_path = os.path.join(workspace_dir, "build_deploy.log")

def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {msg}\n"
    try:
        print(log_line, end="")
    except UnicodeEncodeError:
        print(log_line.encode("ascii", "replace").decode("ascii"), end="")
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
    
    # 2. Terminate running instances to release file locks
    log("Terminating any running instances of agent and service...")
    subprocess.run("taskkill /F /IM RemoteDesktopP2P.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run("taskkill /F /IM RemoteDesktopService.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

    # Metadata for Anti-Virus (Reduces False Positives)
    company_name = "P2P Remote Desktop"
    version_string = "1.0.0.0"
    
    # Calculate jobs to limit CPU usage to ~80%
    cpu_count = os.cpu_count() or 4
    jobs_limit = max(1, int(cpu_count * 0.8))
    
    # 3. Build Service using Nuitka (standalone)
    log("Building RemoteDesktopService via Nuitka (standalone)...")
    python_path = os.path.join(workspace_dir, ".venv", "Scripts", "python.exe")
    service_product_name = "P2P Remote Desktop Service"
    service_desc = "Background Service for P2P Remote Desktop"
    nuitka_service_cmd = (
        f'"{python_path}" -m nuitka --standalone --windows-disable-console --windows-uac-admin '
        f'--assume-yes-for-downloads '
        f'--windows-icon-from-ico=app_icon.ico '
        f'--windows-company-name="{company_name}" --windows-product-name="{service_product_name}" '
        f'--windows-file-version={version_string} --windows-product-version={version_string} '
        f'--windows-file-description="{service_desc}" '
        f'--jobs={jobs_limit} '
        f'--output-dir=dist_nuitka_service windows_service_loop.py'
    )
    if not run_cmd(nuitka_service_cmd):
        log("ERROR: Nuitka service build failed. Aborting deployment.")
        return

    # 4. Build Agent using Nuitka
    log("Building RemoteDesktopP2P via Nuitka (standalone)...")
    app_product_name = "P2P Remote Desktop Client"
    app_desc = "Client GUI for P2P Remote Desktop"
    nuitka_cmd = (
        f'"{python_path}" -m nuitka --standalone --windows-disable-console --enable-plugin=tk-inter '
        f'--assume-yes-for-downloads '
        f'--windows-icon-from-ico=app_icon.ico --nofollow-import-to=pygame.tests,unittest,sqlite3 --include-module=cv2 --include-module=numpy --include-module=psutil --include-module=ntsecuritycon --include-module=dxcam --include-module=comtypes '
        f'--no-deployment-flag=excluded-module-usage '
        f'--windows-company-name="{company_name}" --windows-product-name="{app_product_name}" '
        f'--windows-file-version={version_string} --windows-product-version={version_string} '
        f'--windows-file-description="{app_desc}" '
        f'--jobs={jobs_limit} '
        f'--output-dir=dist_nuitka app.py'
    )
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
            try_authenticode_sign(new_exe)
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

    shorten_openblas_dll(app_dist_dir)

    # Copy icons, install.bat, uninstall.bat and readme.txt to app.dist
    files_to_copy = ["app_icon.png", "app_icon.ico", "install.bat", "uninstall.bat", "readme.txt", "disclaimer_vi.txt", "disclaimer_en.txt"]
    for file_name in files_to_copy:
        src = os.path.join(workspace_dir, file_name)
        dst = os.path.join(app_dist_dir, file_name)
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
                log(f"Copied {file_name} to app.dist")
            except Exception as e:
                log(f"Failed to copy {file_name}: {e}")

    # Copy lang directory to app.dist
    lang_src = os.path.join(workspace_dir, "lang")
    lang_dst = os.path.join(app_dist_dir, "lang")
    if os.path.exists(lang_src):
        try:
            if os.path.exists(lang_dst):
                shutil.rmtree(lang_dst)
            shutil.copytree(lang_src, lang_dst)
            log("Copied lang directory to app.dist")
        except Exception as e:
            log(f"Failed to copy lang directory: {e}")

    # Make zip archive
    log("Creating RemoteDesktopP2P.zip archive...")
    zip_path = os.path.join(workspace_dir, "RemoteDesktopP2P")
    try:
        shutil.make_archive(zip_path, 'zip', app_dist_dir)
        log("Archive created successfully.")
    except Exception as e:
        log(f"Warning: Failed to create zip archive: {e}")

    # Build Inno Setup Installer
    log("Building Installer via Inno Setup...")
    iscc_path = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if not os.path.exists(iscc_path):
        iscc_path = r"C:\Program Files\Inno Setup 6\ISCC.exe"
    
    if os.path.exists(iscc_path):
        iss_file = os.path.join(workspace_dir, "installer.iss")
        if os.path.exists(iss_file):
            cmd = f'"{iscc_path}" "{iss_file}"'
            if not run_cmd(cmd):
                log("WARNING: Inno Setup build failed.")
            else:
                log("Successfully built setup.exe using Inno Setup.")
                try_authenticode_sign(os.path.join(workspace_dir, "EasyRemoteDesktop_Installer.exe"))
        else:
            log("WARNING: installer.iss not found. Skipping installer build.")
    else:
        # Fallback to checking if iscc is in PATH
        cmd = f'iscc "{os.path.join(workspace_dir, "installer.iss")}"'
        try:
            if not run_cmd(cmd):
                log("WARNING: Inno Setup build failed.")
            else:
                log("Successfully built setup.exe using Inno Setup.")
                try_authenticode_sign(os.path.join(workspace_dir, "EasyRemoteDesktop_Installer.exe"))
        except Exception:
            log("WARNING: Inno Setup compiler (ISCC.exe) not found. Skipping installer build.")

    # 6. Show Popup Notification
    try:
        import ctypes
        MB_OK = 0x00000000
        MB_ICONINFORMATION = 0x00000040
        MB_SERVICE_NOTIFICATION = 0x00200000
        MB_TOPMOST = 0x00040000
        ctypes.windll.user32.MessageBoxW(
            0, 
            "Đã build xong Easy Remote Desktop! Hãy kiểm tra thư mục dự án.", 
            "Build Thành Công", 
            MB_OK | MB_ICONINFORMATION | MB_SERVICE_NOTIFICATION | MB_TOPMOST
        )
        log("Shown success popup to user.")
    except Exception as e:
        log(f"Failed to show popup: {e}")

    log("=== BUILD AND DEPLOYMENT FINISHED ===")

def shorten_openblas_dll(app_dist_dir):
    """Đổi tên DLL OpenBLAS do NumPy đóng gói (tên hash dài) thành libopenblas.dll và vá import trong .pyd."""
    import re
    short_name = "libopenblas.dll"
    long_path = None
    long_name = None
    try:
        names = os.listdir(app_dist_dir)
    except Exception as e:
        log(f"Không đọc được {app_dist_dir}: {e}")
        return
    for name in names:
        if re.match(r"libopenblas\..+\.dll$", name, re.I) and name.lower() != short_name:
            long_path = os.path.join(app_dist_dir, name)
            long_name = name
            break
    if not long_path:
        log("No hashed libopenblas DLL found to rename.")
        return
    old_bytes = long_name.encode("ascii")
    short_bytes = short_name.encode("ascii")
    if len(short_bytes) >= len(old_bytes):
        log(f"Short name {short_name} is not shorter; skip.")
        return
    padded = short_bytes + b"\x00" * (len(old_bytes) - len(short_bytes))
    patched = 0
    for root, _dirs, files in os.walk(app_dist_dir):
        for f in files:
            if not f.lower().endswith((".dll", ".pyd", ".exe")):
                continue
            path = os.path.join(root, f)
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
            except Exception:
                continue
            if old_bytes not in data:
                continue
            data = data.replace(old_bytes, padded)
            with open(path, "wb") as fh:
                fh.write(data)
            patched += 1
            log(f"Patched OpenBLAS import in {os.path.relpath(path, app_dist_dir)}")
    dest = os.path.join(app_dist_dir, short_name)
    if os.path.abspath(dest) != os.path.abspath(long_path):
        if os.path.exists(dest):
            try:
                os.remove(dest)
            except Exception as e:
                log(f"Could not remove old {short_name}: {e}")
                return
        os.rename(long_path, dest)
    log(f"Renamed {long_name} -> {short_name} (patched {patched} files).")

def try_authenticode_sign(exe_path):
    """Ký Authenticode nếu máy có signtool + chứng chỉ code signing (cách đúng để giảm Defender ML)."""
    if not os.path.exists(exe_path):
        return
    signtool = None
    kit = os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Windows Kits", "10", "bin")
    if os.path.isdir(kit):
        for root, _dirs, files in os.walk(kit):
            if "signtool.exe" in files and os.path.basename(root).lower() == "x64":
                signtool = os.path.join(root, "signtool.exe")
    if not signtool:
        log("Không tìm thấy signtool.exe — bỏ qua ký Authenticode. Defender ML có thể vẫn cảnh báo installer chưa ký.")
        log("Cách xử lý: chứng chỉ code signing, hoặc gửi file lên https://www.microsoft.com/en-us/wdsi/filesubmission")
        return
    cmd = f'"{signtool}" sign /a /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "{exe_path}"'
    if run_cmd(cmd):
        log(f"Đã ký Authenticode: {exe_path}")
    else:
        log("Không ký được (chưa có chứng chỉ code signing). Gửi Microsoft WDSI nếu Defender cảnh báo.")

if __name__ == "__main__":
    main()
