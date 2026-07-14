import sys, re
with open('utils/file_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

upload_pattern = r'tk\.Button\(mid_frame,\s*text=_\(\"Chuyển qua\\n>>\"\).*?\.pack\(.*?\)'
download_pattern = r'tk\.Button\(mid_frame,\s*text=_\(\"Nhận về\\n<<\"\).*?\.pack\(.*?\)'

upload_repl = '''
    btn_upload = tk.Button(mid_frame, text=_("Chuyển qua\\n>>"), font=("Segoe UI", 10, "bold"), bg="#2196F3", fg="white", width=10, command=do_upload)
    btn_upload.pack(pady=(100, 10))
'''
download_repl = '''
    btn_download = tk.Button(mid_frame, text=_("Nhận về\\n<<"), font=("Segoe UI", 10, "bold"), bg="#4CAF50", fg="white", width=10, command=do_download)
    btn_download.pack(pady=10)
'''

content = re.sub(upload_pattern, upload_repl.strip(), content)
content = re.sub(download_pattern, download_repl.strip(), content)

local_dir_func = '''
        def on_local_dir_selected(event=None):
            path = local_entry.get()
            try:
                if path == "This PC":
                    btn_download.config(state=tk.DISABLED)
                else:
                    btn_download.config(state=tk.NORMAL)
            except:
                pass
            
            for item in local_tree.get_children():
                local_tree.delete(item)
'''

content = re.sub(r'def on_local_dir_selected\(event=None\):\s*path = local_entry\.get\(\)\s*for item in local_tree\.get_children\(\):\s*local_tree\.delete\(item\)', local_dir_func.strip('\n'), content)

download_func = '''
        def do_download():
            sel = remote_tree.selection()
            if not sel: return
            
            def do_download_thread():
                target_dir = local_entry.get()
                if target_dir == "This PC":
                    return
                for s in sel:
                    item = remote_tree.item(s)
                    name = item['text']
                    full_path = remote_entry.get()
                    sep = "/" if "/" in full_path else ("\\\\" if "\\\\" in full_path else "/")
                    if not full_path.endswith(sep): full_path += sep
                    full_path += name
                    req = {"type": "request_download_item", "path": full_path, "target_dir": target_dir}
                    send_event(req)
                    time.sleep(0.5)
                time.sleep(1)
                fm_event_queue.put({"type": "trigger_local_refresh"})
            
            threading.Thread(target=do_download_thread, daemon=True).start()
'''

content = re.sub(r'def do_download\(\):.*?(?=btn_upload = tk\.Button)', download_func.strip('\n') + '\n\n        ', content, flags=re.DOTALL)

with open('utils/file_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
