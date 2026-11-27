# -*- coding: utf-8 -*-
"""
xp_host/build_xp_host.py
Script tự động kiểm tra cú pháp, đóng gói thực thi 32-bit cho Windows XP SP2/SP3,
loại bỏ triệt để dữ liệu cá nhân của máy lập trình viên và vá PE Header Subsystem về 5.01
để nhân Windows XP (NT 5.1) không bao giờ từ chối chạy file .exe ("is not a valid Win32 application").

Cách dùng trên môi trường Python 32-bit XP-backport (ví dụ .venv_xp32):
    .venv_xp32\\Scripts\\python.exe xp_host\\build_xp_host.py
"""

import os
import py_compile
import shutil
import struct
import subprocess
import sys

XP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(XP_DIR)
DIST_DIR = os.path.join(ROOT_DIR, "dist_xp_host")

PERSONAL_FILES_BLACKLIST = (
    "saved_computers.xml",
    "lan_peers.json",
    "config.json",
    "app.ini",
    "window_config.json",
    "custom_ip_range.json",
    "session_pass.txt",
    "host_hwid.txt",
    "xp_prefs.json",
)


def verify_xp_syntax():
    print("[1/4] Kiểm tra cú pháp toàn bộ module xp_host/...")
    py_files = [os.path.join(XP_DIR, f) for f in sorted(os.listdir(XP_DIR)) if f.endswith(".py")]
    for fpath in py_files:
        py_compile.compile(fpath, doraise=True)
        print(f"  OK: {os.path.basename(fpath)}")
    return True


def patch_pe_subsystem_for_xp(pe_path):
    """
    Hạ MajorOperatingSystemVersion & MajorSubsystemVersion trong PE OptionalHeader về 5.01 (Windows XP).
    Đây là bước bắt buộc vì linker MSVC hiện đại mặc định ghi 6.00 (Vista+), làm Windows XP
    báo lỗi '%1 is not a valid Win32 application' ngay khi nhấp đúp!
    """
    if not os.path.isfile(pe_path):
        return False
    with open(pe_path, "r+b") as f:
        mz = f.read(64)
        if len(mz) < 64 or mz[:2] != b"MZ":
            return False
        e_lfanew = struct.unpack_from("<I", mz, 0x3C)[0]
        f.seek(e_lfanew)
        pe_sig = f.read(24)
        if len(pe_sig) < 24 or pe_sig[:4] != b"PE\x00\x00":
            return False
        opt_offset = e_lfanew + 24
        f.seek(opt_offset)
        magic_bytes = f.read(2)
        if len(magic_bytes) < 2:
            return False
        magic = struct.unpack("<H", magic_bytes)[0]
        if magic not in (0x10B, 0x20B):  # PE32 (0x10B) hoặc PE32+ (0x20B)
            return False
        # Trong cả PE32 và PE32+:
        #   MajorOperatingSystemVersion ở offset +40 (uint16), Minor ở +42 (uint16)
        #   MajorSubsystemVersion       ở offset +48 (uint16), Minor ở +50 (uint16)
        #   CheckSum                    ở offset +64 (uint32) -> đặt 0 để OS không bắt lỗi checksum
        f.seek(opt_offset + 40)
        f.write(struct.pack("<HH", 5, 1))
        f.seek(opt_offset + 48)
        f.write(struct.pack("<HH", 5, 1))
        f.seek(opt_offset + 64)
        f.write(struct.pack("<I", 0))
    return True


def scrub_personal_data(target_folder):
    if not os.path.isdir(target_folder):
        return
    for root, dirs, files in os.walk(target_folder):
        if os.path.basename(root).lower() in ("data", "logs"):
            shutil.rmtree(root, ignore_errors=True)
            dirs[:] = []
            continue
        for fn in files:
            if fn.lower() in PERSONAL_FILES_BLACKLIST or fn.lower().endswith(".log"):
                try:
                    os.remove(os.path.join(root, fn))
                except Exception:
                    pass


def main():
    verify_xp_syntax()

    is_32bit = (struct.calcsize("P") * 8) == 32
    if not is_32bit:
        print(
            "\n[CẢNH BÁO] Trình thông dịch Python hiện tại là 64-bit!\n"
            "Để chạy trên máy Windows XP 32-bit, hãy kích hoạt môi trường Python 32-bit (x86)\n"
            "trước khi đóng gói phân phối."
        )

    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR, ignore_errors=True)
    os.makedirs(DIST_DIR, exist_ok=True)

    icon_file = os.path.join(ROOT_DIR, "app_icon.ico")
    entry_script = os.path.join(XP_DIR, "app_xp.py")

    print("[2/4] Đóng gói RemoteDesktopXPHost.exe bằng PyInstaller (onedir nhẹ, khởi động tức thì trên HDD XP)...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name", "RemoteDesktopXPHost",
        "--distpath", DIST_DIR,
        "--workpath", os.path.join(ROOT_DIR, "build_xp_tmp"),
        "--specpath", XP_DIR,
        "--exclude-module", "cv2",
        "--exclude-module", "numpy",
        "--exclude-module", "pygame",
        "--exclude-module", "cryptography",
        "--exclude-module", "dxcam",
        "--exclude-module", "psutil",
        "--exclude-module", "unittest",
        "--exclude-module", "sqlite3",
    ]
    if os.path.isfile(icon_file):
        cmd.extend(["--icon", icon_file])
    cmd.append(entry_script)

    res = subprocess.run(cmd, cwd=ROOT_DIR)
    if res.returncode != 0:
        print("[LỖI] PyInstaller chưa được cài trong venv hoặc gặp lỗi biên dịch.")
        sys.exit(res.returncode)

    app_out = os.path.join(DIST_DIR, "RemoteDesktopXPHost")
    if os.path.isfile(icon_file):
        shutil.copy2(icon_file, os.path.join(app_out, "app_icon.ico"))
    for disc in ("disclaimer_vi.txt", "disclaimer_en.txt"):
        src_d = os.path.join(ROOT_DIR, disc)
        if os.path.isfile(src_d):
            shutil.copy2(src_d, os.path.join(app_out, disc))

    print("[3/4] Vá PE Header Subsystem 5.01 (tương thích nhân Windows XP NT 5.1)...")
    patched_count = 0
    for r, _d, files in os.walk(app_out):
        for fn in files:
            if fn.lower().endswith((".exe", ".dll", ".pyd")):
                if patch_pe_subsystem_for_xp(os.path.join(r, fn)):
                    patched_count += 1
    print(f"  Đã vá Subsystem 5.01 cho {patched_count} tệp nhị phân.")

    print("[4/4] Làm sạch tuyệt đối dữ liệu cá nhân khỏi thư mục phân phối...")
    scrub_personal_data(app_out)
    shutil.rmtree(os.path.join(ROOT_DIR, "build_xp_tmp"), ignore_errors=True)
    spec_f = os.path.join(XP_DIR, "RemoteDesktopXPHost.spec")
    if os.path.isfile(spec_f):
        os.remove(spec_f)

    print(f"\n[HOÀN TẤT] Bản build Windows XP sẵn sàng tại: {app_out}")


if __name__ == "__main__":
    main()
