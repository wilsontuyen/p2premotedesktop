import os
import sys
import subprocess
import shutil
import time
import glob

from build_and_deploy import log, run_cmd, shorten_openblas_dll, try_authenticode_sign

workspace_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(workspace_dir, "dist_nuitka_host")
service_output_dir = os.path.join(workspace_dir, "dist_nuitka_host_service")
flag_path = os.path.join(workspace_dir, "host_build_flag.py")
log_path = os.path.join(workspace_dir, "build_host.log")
INSTALLER_NAME = "EasyRemoteDesktopHost_Installer.exe"


def write_host_flag():
    with open(flag_path, "w", encoding="utf-8") as f:
        f.write("HOST_ONLY_BUILD = True\n")


def remove_host_flag():
    try:
        if os.path.exists(flag_path):
            os.remove(flag_path)
    except Exception:
        pass


def strip_host_unused(app_dist_dir):
    """Drop outgoing-viewer / ffmpeg bulk Host never needs."""
    removed = []
    for pattern in (
        os.path.join(app_dist_dir, "cv2", "opencv_videoio_ffmpeg*.dll"),
        os.path.join(app_dist_dir, "opencv_videoio_ffmpeg*.dll"),
    ):
        for path in glob.glob(pattern):
            try:
                os.remove(path)
                removed.append(os.path.basename(path))
            except Exception as e:
                log(f"Could not remove {path}: {e}")
    pygame_dir = os.path.join(app_dist_dir, "pygame")
    if os.path.isdir(pygame_dir):
        try:
            shutil.rmtree(pygame_dir)
            removed.append("pygame/")
        except Exception as e:
            log(f"Could not remove pygame: {e}")
    for name in os.listdir(app_dist_dir):
        lower = name.lower()
        if lower.startswith("sdl") and lower.endswith(".dll"):
            try:
                os.remove(os.path.join(app_dist_dir, name))
                removed.append(name)
            except Exception:
                pass
    viewer_bits = (
        os.path.join(app_dist_dir, "core", "viewer.py"),
        os.path.join(app_dist_dir, "core", "viewer.pyc"),
    )
    for path in viewer_bits:
        if os.path.exists(path):
            try:
                os.remove(path)
                removed.append(os.path.basename(path))
            except Exception:
                pass
    if removed:
        log("Stripped unused Host files: " + ", ".join(removed))
    else:
        log("No unused pygame/ffmpeg files to strip.")


def compile_host_installer():
    iss_file = os.path.join(workspace_dir, "installer_host.iss")
    iscc_path = r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    if not os.path.exists(iscc_path):
        iscc_path = r"C:\Program Files\Inno Setup 6\ISCC.exe"
    if not os.path.exists(iscc_path):
        log("WARNING: ISCC.exe not found, skipping installer.")
        return False
    if not run_cmd(f'"{iscc_path}" "{iss_file}"'):
        log("ERROR: Host installer compile failed.")
        return False
    installer = os.path.join(workspace_dir, INSTALLER_NAME)
    try_authenticode_sign(installer)
    if os.path.exists(installer):
        mb = os.path.getsize(installer) / (1024 * 1024)
        log(f"Installer: {installer} ({mb:.1f} MB)")
    return True


def show_build_done_popup(ok, detail=""):
    try:
        import ctypes
        MB_OK = 0x00000000
        MB_ICONINFORMATION = 0x00000040
        MB_ICONERROR = 0x00000010
        MB_SERVICE_NOTIFICATION = 0x00200000
        MB_TOPMOST = 0x00040000
        if ok:
            msg = "Đã build xong Easy Remote Desktop Host!\nHãy kiểm tra thư mục dự án:\n" + os.path.join(workspace_dir, INSTALLER_NAME)
            if detail:
                msg += "\n" + detail
            title = "Build Thành Công"
            flags = MB_OK | MB_ICONINFORMATION | MB_SERVICE_NOTIFICATION | MB_TOPMOST
        else:
            msg = "Build Easy Remote Desktop Host thất bại.\nXem build_host.log trong thư mục dự án."
            if detail:
                msg += "\n" + detail
            title = "Build Thất Bại"
            flags = MB_OK | MB_ICONERROR | MB_SERVICE_NOTIFICATION | MB_TOPMOST
        ctypes.windll.user32.MessageBoxW(0, msg, title, flags)
        log("Shown build popup to user.")
    except Exception as e:
        log(f"Failed to show popup: {e}")


def merge_host_service(app_dist_dir):
    service_dist_dir = os.path.join(service_output_dir, "windows_service_loop.dist")
    if not os.path.exists(service_dist_dir):
        log("ERROR: Compiled Host service directory not found!")
        return False
    log("Merging RemoteDesktopHostService into Host dist...")
    # Only bring the service exe + its unique deps; do not overwrite Host DLLs wholesale.
    svc_src = os.path.join(service_dist_dir, "windows_service_loop.exe")
    svc_dst = os.path.join(app_dist_dir, "RemoteDesktopHostService.exe")
    if not os.path.exists(svc_src):
        log("ERROR: windows_service_loop.exe missing in service dist.")
        return False
    shutil.copy2(svc_src, svc_dst)
    # Copy non-overlapping runtime files the service needs (pywin32 extras, etc.).
    for item in os.listdir(service_dist_dir):
        if item.lower() in ("windows_service_loop.exe",):
            continue
        s = os.path.join(service_dist_dir, item)
        d = os.path.join(app_dist_dir, item)
        if os.path.exists(d):
            continue
        try:
            if os.path.isdir(s):
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
        except Exception as e:
            log(f"Warning: Failed to merge service file {item}: {e}")
    if os.path.exists(svc_dst):
        try_authenticode_sign(svc_dst)
        log("Added RemoteDesktopHostService.exe")
        return True
    log("ERROR: RemoteDesktopHostService.exe missing after merge.")
    return False


def main():
    if os.path.exists(log_path):
        try:
            os.remove(log_path)
        except Exception:
            pass

    log("=== STARTING SLIM HOST BUILD (GUI + SYSTEM service, no viewer/pygame) ===")
    subprocess.run(
        'schtasks /end /tn "EasyRemoteDesktopHostAgent"',
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        "taskkill /F /IM RemoteDesktopHostService.exe",
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        "taskkill /F /IM RemoteDesktopHost.exe",
        shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(1)

    company_name = "P2P Remote Desktop"
    version_string = "1.0.0.0"
    cpu_count = os.cpu_count() or 4
    jobs_limit = max(1, int(cpu_count * 0.8))
    python_path = os.path.join(workspace_dir, ".venv", "Scripts", "python.exe")

    log("Building RemoteDesktopHostService via Nuitka (standalone + in-process broker)...")
    service_cmd = (
        f'"{python_path}" -m nuitka --standalone --windows-disable-console --windows-uac-admin '
        f'--assume-yes-for-downloads '
        f'--windows-icon-from-ico=app_icon.ico '
        f'--include-module=core.broker --include-module=core.config --include-module=psutil '
        f'--include-package=network --include-module=cryptography '
        f'--windows-company-name="{company_name}" --windows-product-name="P2P Remote Desktop Host Service" '
        f'--windows-file-version={version_string} --windows-product-version={version_string} '
        f'--windows-file-description="Easy Remote Desktop Host Service" '
        f'--jobs={jobs_limit} '
        f'--output-dir=dist_nuitka_host_service windows_service_loop.py'
    )
    if not run_cmd(service_cmd):
        log("ERROR: Nuitka Host service build failed.")
        show_build_done_popup(False, "Nuitka Host service build failed.")
        return 1

    product_name = "P2P Remote Desktop Host"
    desc = "Easy Remote Desktop Host"
    nofollow = ",".join([
        "pygame",
        "pygame.tests",
        "core.viewer",
        "utils.file_manager",
        "utils.keyboard_map",
        "unittest",
        "sqlite3",
        "tkmacosx",
        "gui.mac_ui",
        "gui.linux_ui",
        "os_utils.mac_clipboard",
        "os_utils.linux_clipboard",
        "os_utils.mac_input",
        "os_utils.linux_input",
        "os_utils.mac_system",
        "os_utils.linux_system",
        "os_utils.mac_ui",
        "os_utils.linux_ui",
    ])

    write_host_flag()
    try:
        log("Building slim RemoteDesktopHost via Nuitka...")
        nuitka_cmd = (
            f'"{python_path}" -m nuitka --standalone --windows-disable-console --enable-plugin=tk-inter '
            f'--assume-yes-for-downloads '
            f'--windows-icon-from-ico=app_icon.ico '
            f'--nofollow-import-to={nofollow} '
            f'--include-module=cv2 --include-module=numpy --include-module=psutil '
            f'--include-module=ntsecuritycon --include-module=dxcam --include-module=comtypes '
            f'--include-module=gui.host_ui --include-module=host_build_flag '
            f'--no-deployment-flag=excluded-module-usage '
            f'--windows-company-name="{company_name}" --windows-product-name="{product_name}" '
            f'--windows-file-version={version_string} --windows-product-version={version_string} '
            f'--windows-file-description="{desc}" '
            f'--jobs={jobs_limit} '
            f'--output-dir=dist_nuitka_host app.py'
        )
        if not run_cmd(nuitka_cmd):
            log("ERROR: Nuitka Host build failed.")
            show_build_done_popup(False, "Nuitka Host GUI build failed.")
            return 1
    finally:
        remove_host_flag()

    app_dist_dir = os.path.join(output_dir, "app.dist")
    old_exe = os.path.join(app_dist_dir, "app.exe")
    new_exe = os.path.join(app_dist_dir, "RemoteDesktopHost.exe")
    if not os.path.exists(old_exe):
        log(f"ERROR: Built exe not found: {old_exe}")
        show_build_done_popup(False, f"Missing: {old_exe}")
        return 1
    if os.path.exists(new_exe):
        os.remove(new_exe)
    os.rename(old_exe, new_exe)
    log("Renamed app.exe to RemoteDesktopHost.exe")
    try_authenticode_sign(new_exe)

    if not merge_host_service(app_dist_dir):
        show_build_done_popup(False, "Merge RemoteDesktopHostService failed.")
        return 1

    with open(os.path.join(app_dist_dir, "host.mode"), "w", encoding="utf-8") as f:
        f.write("1\n")

    shorten_openblas_dll(app_dist_dir)
    strip_host_unused(app_dist_dir)

    files_to_copy = [
        "app_icon.png", "app_icon.ico", "readme.txt",
        "disclaimer_vi.txt", "disclaimer_en.txt", "server.ini",
    ]
    for file_name in files_to_copy:
        src = os.path.join(workspace_dir, file_name)
        dst = os.path.join(app_dist_dir, file_name)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            log(f"Copied {file_name}")

    lang_src = os.path.join(workspace_dir, "lang")
    lang_dst = os.path.join(app_dist_dir, "lang")
    if os.path.exists(lang_src):
        if os.path.exists(lang_dst):
            shutil.rmtree(lang_dst)
        shutil.copytree(lang_src, lang_dst)
        log("Copied lang directory")

    if not compile_host_installer():
        show_build_done_popup(False, "Inno Setup installer compile failed.")
        return 1

    installer_path = os.path.join(workspace_dir, INSTALLER_NAME)
    installer_mb = 0.0
    if os.path.exists(installer_path):
        installer_mb = os.path.getsize(installer_path) / (1024 * 1024)

    dist_mb = 0
    try:
        dist_mb = sum(
            os.path.getsize(os.path.join(r, f))
            for r, _d, files in os.walk(app_dist_dir)
            for f in files
        ) / (1024 * 1024)
    except Exception:
        pass
    log(f"Host dist size: {dist_mb:.1f} MB")
    log("=== SLIM HOST BUILD FINISHED ===")
    log(f"Installer: {installer_path} ({installer_mb:.1f} MB)")
    show_build_done_popup(True, f"Dung lượng installer: {installer_mb:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
