import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

start = content.find('                                                    write_transfer_log("UPLOAD", name, size, target_dir)')
end = content.find('                                        def do_download():')

if start != -1 and end != -1:
    new_block = """                                                    write_transfer_log("UPLOAD", name, size, target_dir)

                                                    class UploadState:
                                                        is_cancelled = False
                                                    state = UploadState()
                                                    
                                                    def on_upload_cancel(st=state):
                                                        st.is_cancelled = True
                                                        
                                                    dialog = ProgressDialog(top, "Chuyển qua", name, size, on_cancel=lambda: on_upload_cancel())
                                                    dialog.update_progress(0)
                                                    
                                                    def upload_thread(path, n, sz, t_dir, dlg, st):
                                                        try:
                                                            send_event({"type": "file_start", "name": n, "size": sz, "target_dir": t_dir})
                                                            time.sleep(0.5)
                                                            sent = 0
                                                            with open(path, "rb") as f:
                                                                while True:
                                                                    if st.is_cancelled:
                                                                        break
                                                                    chunk = f.read(65536)
                                                                    if not chunk: break
                                                                    send_event({
                                                                        "type": "file_chunk",
                                                                        "name": n,
                                                                        "data": base64.b64encode(chunk).decode('utf-8')
                                                                    })
                                                                    sent += len(chunk)
                                                                    dlg.update_progress(sent)
                                                                    time.sleep(0.01)
                                                            send_event({"type": "file_end"})
                                                            
                                                            if not st.is_cancelled:
                                                                dlg.safe_destroy()
                                                                
                                                            def delayed_refresh():
                                                                time.sleep(1)
                                                                top.after(0, lambda: request_remote_dir(t_dir))
                                                            threading.Thread(target=delayed_refresh, daemon=True).start()
                                                        except Exception as e:
                                                            print(f"Upload error: {e}")
                                                            dlg.safe_destroy()
                                                
                                                    threading.Thread(target=upload_thread, args=(fpath, name, size, target_dir, dialog, state), daemon=True).start()

"""
    content = content[:start] + new_block + content[end:]
    print("Replaced successfully via index")
else:
    print("Not found indices")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
