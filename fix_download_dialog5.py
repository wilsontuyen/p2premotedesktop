import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if i == 4759:
        new_lines.append("""                                            if cm:
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
                                                dialog.update_progress(0)
                                                cm.active_dialog = dialog
""")
        skip = True
    elif i == 4771:
        skip = False
        new_lines.append(line)
    elif not skip:
        new_lines.append(line)

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Done")
