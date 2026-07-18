#!/bin/bash
echo "Build Antigravity Remote Desktop for Linux"
pip install pyinstaller
pip install -r ../requirements.txt

# Create a modified spec for Linux
cat << 'EOF' > app_linux.spec
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['../app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['cv2', 'numpy', 'pygame', 'pynput', 'pyperclip'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['win32api', 'win32con', 'win32gui', 'win32security', 'win32event', 'win32service', 'win32serviceutil', 'win32com'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    contents_directory='app_internal',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='app',
)
EOF

pyinstaller app_linux.spec --clean
echo "Build finished. Output is in linux_deploy/dist/"
