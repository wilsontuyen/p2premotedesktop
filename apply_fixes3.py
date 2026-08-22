import os

file_path = r'os_utils\windows_clipboard.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

start_idx = -1
for i, line in enumerate(lines):
    if line.strip() == '# Nếu có thư mục đích hợp lệ, tải file trực tiếp vào đó':
        start_idx = i
        break

end_idx = -1
for i in range(start_idx, len(lines)):
    if line.strip().startswith('except Exception as e:'):
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    old_body = lines[start_idx:end_idx] # exclude except
    
    new_lines = []
    new_lines.append('            def background_download():\n')
    new_lines.append('                try:\n')
    for line in old_body:
        if line.strip() == '':
            new_lines.append(line)
        else:
            new_lines.append('    ' + line)
            
    new_lines.append('''                finally:
                    self.is_rendering = False
                    self.transfer_in_progress = False
                    self.ignore_destroy_clipboard = False
                    
            if dest_dir and os.path.isdir(dest_dir):
                self.ignore_destroy_clipboard = True
                import threading
                threading.Thread(target=background_download, daemon=True).start()
                return
            else:
                background_download()
                return
''')

    final_lines = lines[:start_idx] + new_lines + lines[end_idx:]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(final_lines)
    print("Phase 2 done.")
else:
    print(f"Failed to find markers. start={start_idx}, end={end_idx}")
