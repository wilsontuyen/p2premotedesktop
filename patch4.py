import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_temp = '''temp_dir = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), "RemoteDesktopTransfers", "VirtualStaging")'''
new_temp = '''# Sử dụng thư mục Public để User thường có quyền read (bắt buộc để Explorer có thể Paste)
        temp_dir = os.path.join(os.environ.get("PUBLIC", r"C:\\Users\\Public"), "Downloads", "RemoteDesktopTransfers", "VirtualStaging")'''
content = content.replace(old_temp, new_temp)

old_ctypes = '''            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            # Format DROPFILES structure'''

new_ctypes = '''            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            
            kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
            kernel32.GlobalAlloc.restype = ctypes.c_void_p
            kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
            kernel32.GlobalLock.restype = ctypes.c_void_p
            kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
            user32.SetClipboardData.restype = ctypes.c_void_p
            
            # Format DROPFILES structure'''
content = content.replace(old_ctypes, new_ctypes)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Patch 4 done")
