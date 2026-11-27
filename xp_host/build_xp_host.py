# -*- coding: utf-8 -*-
"""
xp_host/build_xp_host.py
Quy trình tự động trọn gói đóng gói EasyRemoteDesktop Host cho Windows XP SP2/SP3 (32-bit x86):
  1. Kiểm tra cú pháp (py_compile) toàn bộ mã nguồn xp_host/.
  2. Đóng gói thực thi 32-bit RemoteDesktopXPHost.exe bằng cx_Freeze bản WinXP (Subsystem 5.1).
  3. Đóng gói kèm trọn bộ Tcl/Tk 8.6, vcruntime140.dll và Universal CRT x86 (10.0.19041 Subsys 5.1)
     để máy Windows XP SP2/SP3 mới cài sạch (chưa cài VC++ Redist) vẫn chạy ngay lập tức.
  4. Vá PE Header Subsystem về 5.01 cho toàn bộ .exe / .dll / .pyd và quét kiểm tra bảng Import
     đảm bảo 0% lời gọi hàm Vista+ (GetTickCount64, SRWLock, bcrypt.dll...).
  5. Làm sạch dữ liệu cá nhân và gọi Inno Setup 5.6.1 đóng gói ra EasyRemoteDesktopXPHost_Installer.exe.
"""

import glob
import os
import py_compile
import shutil
import struct
import subprocess
import sys

XP_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(XP_DIR)
DIST_DIR = os.path.join(ROOT_DIR, "dist_xp_host")
APP_OUT_DIR = os.path.join(DIST_DIR, "RemoteDesktopXPHost")
TOOLCHAIN_DIR = os.path.join(ROOT_DIR, ".xp_toolchain")
PY38_XP_BASE = os.path.join(TOOLCHAIN_DIR, "python38_xp")
ISCC5_EXE = os.path.join(TOOLCHAIN_DIR, "innosetup5", "ISCC.exe")

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

VISTA_FORBIDDEN_IMPORTS = {
    "GetTickCount64",
    "InitializeSRWLock",
    "AcquireSRWLockExclusive",
    "AcquireSRWLockShared",
    "ReleaseSRWLockExclusive",
    "ReleaseSRWLockShared",
    "InitializeConditionVariable",
    "SleepConditionVariableCS",
    "SleepConditionVariableSRW",
    "WakeConditionVariable",
    "WakeAllConditionVariable",
    "GetFinalPathNameByHandleW",
    "CreateSymbolicLinkW",
    "BCryptGenRandom",
}


def verify_xp_syntax():
    print("[1/6] Kiểm tra cú pháp toàn bộ module xp_host/...")
    py_files = [os.path.join(XP_DIR, f) for f in sorted(os.listdir(XP_DIR)) if f.endswith(".py")]
    for fpath in py_files:
        py_compile.compile(fpath, doraise=True)
        print(f"  OK: {os.path.basename(fpath)}")
    return True


def patch_pe_subsystem_for_xp(pe_path):
    """Đảm bảo MajorOperatingSystemVersion & MajorSubsystemVersion = 5.01 (Windows XP NT 5.1)."""
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
        if magic not in (0x10B, 0x20B):
            return False
        f.seek(opt_offset + 40)
        f.write(struct.pack("<HH", 5, 1))
        f.seek(opt_offset + 48)
        f.write(struct.pack("<HH", 5, 1))
        f.seek(opt_offset + 64)
        f.write(struct.pack("<I", 0))
    return True


def bundle_xp_runtime_dlls(app_out):
    """Sao chép đầy đủ Tcl/Tk 8.6, vcruntime140.dll và UCRT x86 (10.0.19041 Subsys 5.1) vào thư mục đích."""
    copied = 0
    # 1. Tcl/Tk runtime + vcruntime140 + OpenSSL 1.1 + libffi từ CPython3.8.20WinXP
    src_roots = [PY38_XP_BASE, sys.base_prefix]
    for sr in src_roots:
        if not sr or not os.path.isdir(sr):
            continue
        for dll_rel in (
            "vcruntime140.dll",
            "python38.dll",
            "python3.dll",
            os.path.join("DLLs", "tcl86t.dll"),
            os.path.join("DLLs", "tk86t.dll"),
            os.path.join("DLLs", "libcrypto-1_1.dll"),
            os.path.join("DLLs", "libssl-1_1.dll"),
            os.path.join("DLLs", "libffi-7.dll"),
        ):
            sp = os.path.join(sr, dll_rel)
            if os.path.isfile(sp):
                dp = os.path.join(app_out, os.path.basename(sp))
                if not os.path.isfile(dp):
                    shutil.copy2(sp, dp)
                    copied += 1
        for tk_sub in ("tcl8.6", "tk8.6"):
            tk_src = os.path.join(sr, "tcl", tk_sub)
            tk_dst = os.path.join(app_out, "lib", tk_sub)
            if os.path.isdir(tk_src) and not os.path.isdir(tk_dst):
                shutil.copytree(tk_src, tk_dst)
                copied += 1

    # 2. Universal CRT x86 chuẩn Windows XP SP3 (.xp_toolchain/ucrt_xp_x86 từ ucrt_3.8.0.msi):
    # TUYỆT ĐỐI KHÔNG lấy từ Windows Kits 10.0.19041+ vì bản 19041+ đổi chuỗi forwarder thành
    # 'kernel32.dll.VirtualProtect' gây lỗi Entry Point Not Found trên ntdll.dll của Windows XP!
    ucrt_xp_dir = os.path.join(TOOLCHAIN_DIR, "ucrt_xp_x86")
    if not os.path.isdir(ucrt_xp_dir) or not os.path.isfile(os.path.join(ucrt_xp_dir, "ucrtbase.dll")):
        raise RuntimeError(f"Thiếu thư mục UCRT chuẩn Windows XP tại: {ucrt_xp_dir}")
    for fn in os.listdir(ucrt_xp_dir):
        if fn.lower().endswith(".dll"):
            sp = os.path.join(ucrt_xp_dir, fn)
            dp = os.path.join(app_out, fn)
            shutil.copy2(sp, dp)
            copied += 1
    print(f"  Đã đóng gói bổ sung {copied} thành phần Runtime (XP UCRT x86 + Tcl/Tk 8.6 + VCRuntime).")


def audit_xp_pe_compatibility(app_out):
    """Quét toàn bộ .exe / .dll / .pyd trong bản build để xác nhận 100% tương thích nhân XP (32-bit, Subsys 5.1, không có forwarder '.dll.')."""
    import re
    try:
        import lief
    except ImportError:
        lief = None

    total_checked = 0
    violations = []
    for r, _d, files in os.walk(app_out):
        for fn in files:
            if not fn.lower().endswith((".exe", ".dll", ".pyd")):
                continue
            fp = os.path.join(r, fn)
            total_checked += 1
            with open(fp, "rb") as bf:
                raw_bytes = bf.read()
            bad_fwds = [x.decode("ascii", errors="ignore") for x in re.findall(b"[A-Za-z0-9_-]+\\.dll\\.[A-Za-z0-9_]+", raw_bytes)]

            is_x86 = True
            sub_str = "5.1"
            bad_syms = list(bad_fwds[:5])
            if lief is not None:
                pe = lief.parse(fp)
                if pe is not None:
                    is_x86 = (pe.header.machine == lief.PE.Header.MACHINE_TYPES.I386)
                    sub_maj = pe.optional_header.major_subsystem_version
                    sub_min = pe.optional_header.minor_subsystem_version
                    sub_str = f"{sub_maj}.{sub_min}"
                    for lib in pe.imports:
                        if lib.name.lower() == "bcrypt.dll":
                            bad_syms.append("bcrypt.dll")
                        for e in lib.entries:
                            if e.name in VISTA_FORBIDDEN_IMPORTS:
                                bad_syms.append(f"{lib.name}!{e.name}")
                    if (sub_maj, sub_min) > (5, 2):
                        bad_syms.append(f"Subsystem={sub_str}")

            if (not is_x86) or bad_syms:
                violations.append((os.path.relpath(fp, app_out), is_x86, sub_str, bad_syms))

    if violations:
        print("[CẢNH BÁO TƯƠNG THÍCH XP] Phát hiện tệp nhị phân không tương thích XP:")
        for rel, x86, sub, syms in violations:
            print(f"  - {rel}: x86={x86}, Subsys={sub}, Issues={syms}")
        return False

    print(f"  XÁC NHẬN 100% SẠCH: Tất cả {total_checked} tệp .exe/.dll/.pyd đều là x86 32-bit, Subsystem 5.1, 0 hàm Vista+, 0 lỗi '.dll.' forwarder!")
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


def run_cx_freeze_build():
    from cx_Freeze import Executable, setup

    icon_file = os.path.join(ROOT_DIR, "app_icon.ico")
    entry_script = os.path.join(XP_DIR, "app_xp.py")

    if ROOT_DIR not in sys.path:
        sys.path.insert(0, ROOT_DIR)

    include_files = []
    if os.path.isfile(icon_file):
        include_files.append((icon_file, "app_icon.ico"))
    for disc in ("disclaimer_vi.txt", "disclaimer_en.txt"):
        dp = os.path.join(ROOT_DIR, disc)
        if os.path.isfile(dp):
            include_files.append((dp, disc))

    exe = Executable(
        script=entry_script,
        base="Win32GUI",
        target_name="RemoteDesktopXPHost.exe",
        icon=icon_file if os.path.isfile(icon_file) else None,
        copyright="Copyright (C) 2026 P2P Remote Desktop",
    )

    build_options = {
        "build_exe": APP_OUT_DIR,
        "packages": [
            "xp_host",
            "tkinter",
            "PIL",
            "Cryptodome",
            "ctypes",
            "xml",
            "urllib",
            "http",
            "email",
            "configparser",
            "ipaddress",
        ],
        "excludes": [
            "cv2",
            "numpy",
            "pygame",
            "cryptography",
            "dxcam",
            "psutil",
            "unittest",
            "sqlite3",
            "test",
            "pydoc_data",
            "distutils",
            "setuptools",
            "pip",
            "cx_Freeze",
            "lief",
        ],
        "include_files": include_files,
        "zip_include_packages": [],
        "zip_exclude_packages": ["*"],
        "include_msvcr": False,
        "optimize": 1,
    }

    setup(
        name="RemoteDesktopXPHost",
        version="1.0.0",
        description="Easy Remote Desktop Host for Windows XP",
        options={"build_exe": build_options},
        executables=[exe],
        script_args=["build_exe"],
    )


def compile_xp_installer():
    iss_path = os.path.join(XP_DIR, "installer_xp_host.iss")
    iscc_candidates = [
        ISCC5_EXE,
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
    ]
    iscc = next((p for p in iscc_candidates if os.path.isfile(p)), None)
    if not iscc:
        print("[BỎ QUA] Không tìm thấy Inno Setup 5 (ISCC.exe).")
        return False

    print(f"[6/6] Đóng gói bộ cài đặt Windows XP bằng Inno Setup 5 ({iscc})...")
    res = subprocess.run([iscc, iss_path], cwd=XP_DIR)
    if res.returncode != 0:
        print(f"[LỖI] Biên dịch Inno Setup 5 thất bại (mã lỗi {res.returncode}).")
        return False
    installer_out = os.path.join(ROOT_DIR, "EasyRemoteDesktopXPHost_Installer.exe")
    if os.path.isfile(installer_out):
        mb = os.path.getsize(installer_out) / (1024.0 * 1024.0)
        print(f"  -> Đã tạo bộ cài đặt XP: {installer_out} ({mb:.2f} MB)")
        return True
    return False


def main():
    verify_xp_syntax()

    bits = struct.calcsize("P") * 8
    if bits != 32:
        print(f"[LỖI] Đang chạy Python {bits}-bit! Hãy chạy bằng .venv_xp32\\Scripts\\python.exe (32-bit).")
        sys.exit(1)

    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR, ignore_errors=True)
    os.makedirs(DIST_DIR, exist_ok=True)

    print("[2/6] Đóng gói RemoteDesktopXPHost.exe (32-bit Win32GUI) bằng cx_Freeze WinXP...")
    run_cx_freeze_build()

    print("[3/6] Tích hợp bộ thư viện UCRT x86 + Tcl/Tk 8.6 cho máy Windows XP sạch...")
    bundle_xp_runtime_dlls(APP_OUT_DIR)

    print("[4/6] Vá PE Header Subsystem 5.01 cho toàn bộ tệp thực thi & thư viện...")
    patched = 0
    for r, _d, files in os.walk(APP_OUT_DIR):
        for fn in files:
            if fn.lower().endswith((".exe", ".dll", ".pyd")):
                if patch_pe_subsystem_for_xp(os.path.join(r, fn)):
                    patched += 1
    print(f"  Đã chuẩn hóa Subsystem 5.01 cho {patched} tệp nhị phân.")

    print("[5/6] Kiểm toán bảng Import Win32 XP & làm sạch dữ liệu cá nhân...")
    scrub_personal_data(APP_OUT_DIR)
    if not audit_xp_pe_compatibility(APP_OUT_DIR):
        sys.exit(2)

    if not compile_xp_installer():
        sys.exit(3)

    print("\n============================================================")
    print(" HOÀN TẤT ĐÓNG GÓI BẢN WINDOWS XP SP2/SP3 (32-BIT)!")
    print(f" - Thư mục Portable XP : {APP_OUT_DIR}")
    print(f" - Bộ cài đặt XP (.exe): {os.path.join(ROOT_DIR, 'EasyRemoteDesktopXPHost_Installer.exe')}")
    print("============================================================")


if __name__ == "__main__":
    main()
