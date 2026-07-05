import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

search = """                                            if cm:
                                                cm.target_save_dir = target_dir
                                                cm.batch_total_size = total_size
                                                cm.batch_received_size = 0
                                                cm.active_batch = True

                                                display_name = files_to_download[0][0]
                                                if len(files_to_download) > 1:
                                                    display_name += f" and {len(files_to_download)-1} more"

                                                cm.show_dialog("Đang tải file về...", display_name, total_size)"""

replace = """                                            if cm:
                                                cm.target_save_dir = target_dir
                                                cm.batch_total_size = total_size
                                                cm.batch_received = 0
                                                cm.active_batch = True

                                                display_name = files_to_download[0][0]
                                                if len(files_to_download) > 1:
                                                    display_name += f" and {len(files_to_download)-1} more"

                                                def _cancel():
                                                    cm.cancel_active_transfer(remote_triggered=False)
                                                    
                                                dialog = ProgressDialog(top, "Nhận về", display_name, total_size, on_cancel=_cancel)
                                                cm.active_dialog = dialog"""

if search in content:
    content = content.replace(search, replace)
    print("Replaced download dialog logic")
else:
    print("Not found download dialog logic")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
