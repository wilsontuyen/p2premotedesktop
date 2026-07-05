import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

start = content.find("                                            if cm:\\n                                                cm.target_save_dir = target_dir")
end = content.find("                                            for name, full_remote, size in files_to_download:")

if start != -1 and end != -1:
    old_block = content[start:end]
    new_block = """                                            if cm:
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
                                                cm.active_dialog = dialog

"""
    content = content[:start] + new_block + content[end:]
    print("Replaced download dialog logic via index")
else:
    print("Not found indices")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
