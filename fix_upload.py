import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

search = """                                                    write_transfer_log("UPLOAD", name, size, target_dir)

                                                    def upload_thread(path, n, sz, t_dir):
                                                        is_cancelled = False
                                                        def on_upload_cancel():
                                                            nonlocal is_cancelled
                                                            is_cancelled = True

                                                        dialog = None
                                                        def create_dialog():
                                                            nonlocal dialog
                                                            try:
                                                                dialog = ProgressDialog(top, "Chuyển qua", n, sz, on_cancel=on_upload_cancel)
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
                                                                top.after(0, dialog.safe_destroy)
                                                                
                                                            def delayed_refresh():
                                                                time.sleep(1)
                                                                top.after(0, lambda: request_remote_dir(t_dir))
                                                            threading.Thread(target=delayed_refresh, daemon=True).start()
                                                        except Exception as e:
                                                            print(f"Upload error: {e}")
                                                            if dialog:
                                                                dialog.safe_destroy()
                                                
                                                    threading.Thread(target=upload_thread, args=(fpath, name, size, target_dir), daemon=True).start()"""

replace = """                                                    write_transfer_log("UPLOAD", name, size, target_dir)

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
                                                
                                                    threading.Thread(target=upload_thread, args=(fpath, name, size, target_dir, dialog, state), daemon=True).start()"""

if search in content:
    content = content.replace(search, replace)
    print("Replaced upload logic successfully")
else:
    print("Not found upload logic")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
