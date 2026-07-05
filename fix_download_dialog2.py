import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

search = content[content.find("                                        def do_download():"):content.find("                                                    def auto_refresh_local():")]

replace = """                                        def do_download():
                                            sel = remote_tree.selection()
                                            if not sel: return

                                            target_dir = local_entry.get()
                                            cm = globals().get('clipboard_sync_manager')
                                            
                                            total_size = 0
                                            files_to_download = []
                                            
                                            for s in sel:
                                                item = remote_tree.item(s)
                                                name = item['text']
                                                vals = item.get('values', [])
                                                is_file = (len(vals) > 1 and vals[1] == "Tệp")
                                                
                                                if is_file:
                                                    target_path = os.path.join(target_dir, name)
                                                    if os.path.exists(target_path):
                                                        if not messagebox.askyesno("Xác nhận ghi đè", f"Tệp '{name}' đã tồn tại ở máy Local.\\nBạn có muốn ghi đè không?", parent=top):
                                                            continue
                                                    
                                                    p = remote_entry.get()
                                                    sep = "/" if "/" in p else ("\\\\" if "\\\\" in p else "/")
                                                    if not p.endswith(sep): p += sep
                                                    full_remote = p + name
                                                    size = vals[2] if len(vals) > 2 else 0
                                                    
                                                    total_size += size
                                                    files_to_download.append((name, full_remote, size))
                                                    
                                            if not files_to_download: return
                                            
                                            if cm:
                                                cm.target_save_dir = target_dir
                                                cm.batch_total_size = total_size
                                                cm.batch_received_size = 0
                                                cm.active_batch = True
                                                
                                                display_name = files_to_download[0][0]
                                                if len(files_to_download) > 1:
                                                    display_name += f" and {len(files_to_download)-1} more"
                                                    
                                                cm.show_dialog("Đang tải file về...", display_name, total_size)
                                                
                                            for name, full_remote, size in files_to_download:
                                                write_transfer_log("DOWNLOAD", name, size, target_dir)
                                                req = {"type": "request_file_download", "path": full_remote, "target_dir_local": target_dir}
                                                send_event(req)
                                                
"""

content = content.replace(search, replace)
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
