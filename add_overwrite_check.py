import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

upload_search = """                                                if is_file:
                                                    try: size = os.path.getsize(fpath)"""

upload_replace = """                                                if is_file:
                                                    # --- OVERWRITE CHECK ---
                                                    remote_exists = False
                                                    for child in remote_tree.get_children():
                                                        if remote_tree.item(child)['text'] == name:
                                                            remote_exists = True
                                                            break
                                                    if remote_exists:
                                                        if not messagebox.askyesno("Xác nhận ghi đè", f"Tệp '{name}' đã tồn tại ở đích.\\nBạn có muốn ghi đè không?", parent=top):
                                                            continue
                                                    # -----------------------
                                                    
                                                    try: size = os.path.getsize(fpath)"""

download_search = """                                                if is_file:
                                                    p = remote_entry.get()"""

download_replace = """                                                if is_file:
                                                    # --- OVERWRITE CHECK ---
                                                    target_path = os.path.join(target_dir, name)
                                                    if os.path.exists(target_path):
                                                        if not messagebox.askyesno("Xác nhận ghi đè", f"Tệp '{name}' đã tồn tại ở máy Local.\\nBạn có muốn ghi đè không?", parent=top):
                                                            continue
                                                    # -----------------------
                                                    
                                                    p = remote_entry.get()"""

c = 0
if upload_search in content:
    content = content.replace(upload_search, upload_replace)
    c += 1
else:
    print("upload_search not found")

if download_search in content:
    content = content.replace(download_search, download_replace)
    c += 1
else:
    print("download_search not found")

if c > 0:
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success")
