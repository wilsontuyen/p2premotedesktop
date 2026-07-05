import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

search = """                                            for name, full_remote, size in files_to_download:
                                                write_transfer_log("DOWNLOAD", name, size, target_dir)
                                                req = {"type": "request_file_download", "path": full_remote, "target_dir_local": target_dir}
                                                send_event(req)
                                                
                                                    def auto_refresh_local():"""

replace = """                                            for name, full_remote, size in files_to_download:
                                                write_transfer_log("DOWNLOAD", name, size, target_dir)
                                                req = {"type": "request_file_download", "path": full_remote, "target_dir_local": target_dir}
                                                send_event(req)
                                                
                                            def auto_refresh_local():"""

if search in content:
    content = content.replace(search, replace)
    print("Fixed indent")
else:
    print("Not found indent to fix")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
