import codecs

old = """                                                    def upload_thread(path, n, sz, t_dir):
                                                        try:
                                                            send_event({"type": "file_start", "name": n, "size": sz, "target_dir": t_dir})
                                                            time.sleep(0.5)
                                                            with open(path, "rb") as f:
                                                                while True:
                                                                    chunk = f.read(65536)
                                                                    if not chunk: break
                                                                    send_event({
                                                                        "type": "file_chunk",
                                                                        "name": n,
                                                                        "data": base64.b64encode(chunk).decode('utf-8')
                                                                    })
                                                                    time.sleep(0.01)
                                                            send_event({"type": "file_end"})
                                                            
                                                            def delayed_refresh():
                                                                time.sleep(1)
                                                                top.after(0, lambda: request_remote_dir(t_dir))
                                                            threading.Thread(target=delayed_refresh, daemon=True).start()
                                                        except Exception as e:
                                                            print(f"Upload error: {e}")"""

new_code = """                                                    def upload_thread(path, n, sz, t_dir):
                                                        is_cancelled = False
                                                        def on_upload_cancel():
                                                            nonlocal is_cancelled
                                                            is_cancelled = True
                                                        
                                                        dialog = None
                                                        def create_dialog():
                                                            nonlocal dialog
                                                            try:
                                                                dialog = ProgressDialog(top, "Upload files...", n, sz, on_cancel=on_upload_cancel)
                                                                dialog.update_progress(0)
                                                            except Exception as e:
                                                                import traceback
                                                                with open('C:/Apps/P2P/client_error.log', 'a', encoding='utf-8') as f:
                                                                    f.write(f"Exception in create_dialog (upload): {e}\\n")
                                                                    f.write(traceback.format_exc() + "\\n")
                                                        top.after(0, create_dialog)
                                                        
                                                        try:
                                                            send_event({"type": "file_start", "name": n, "size": sz, "target_dir": t_dir})
                                                            time.sleep(0.5)
                                                            sent = 0
                                                            with open(path, "rb") as f:
                                                                while True:
                                                                    if is_cancelled:
                                                                        break
                                                                    chunk = f.read(65536)
                                                                    if not chunk: break
                                                                    send_event({
                                                                        "type": "file_chunk",
                                                                        "name": n,
                                                                        "data": base64.b64encode(chunk).decode('utf-8')
                                                                    })
                                                                    sent += len(chunk)
                                                                    if dialog:
                                                                        top.after(0, lambda s=sent: dialog.update_progress(s))
                                                                    time.sleep(0.01)
                                                            send_event({"type": "file_end"})
                                                            
                                                            if dialog and not is_cancelled:
                                                                top.after(0, dialog.destroy)
                                                                
                                                            def delayed_refresh():
                                                                time.sleep(1)
                                                                top.after(0, lambda: request_remote_dir(t_dir))
                                                            threading.Thread(target=delayed_refresh, daemon=True).start()
                                                        except Exception as e:
                                                            print(f"Upload error: {e}")"""

content = codecs.open('app.py', 'r', 'utf-8').read()
idx = content.find('def upload_thread(path, n, sz, t_dir):')
if idx != -1:
    end_idx = content.find('except Exception as e:', idx)
    end_idx = content.find('\\n', end_idx)
    end_idx = content.find('\\n', end_idx + 1)
    
    # Let's just replace it using string methods since we found it
    # I will replace the exact old string
    pass

if old in content:
    content = content.replace(old, new_code)
    codecs.open('app.py', 'w', 'utf-8').write(content)
    print("Replaced nicely")
else:
    print("Could not find exact string. Here is the block in the file:")
    print(content[idx:idx+1000])
