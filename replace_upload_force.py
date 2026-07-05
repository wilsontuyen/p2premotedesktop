import codecs
import re

content = codecs.open('app.py', 'r', 'utf-8').read()

new_code = """def upload_thread(path, n, sz, t_dir):
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

# Find start and end indices to replace
idx_start = content.find('def upload_thread(path, n, sz, t_dir):')
idx_end = content.find('print(f"Upload error: {e}")', idx_start)
idx_end += len('print(f"Upload error: {e}")')

if idx_start != -1 and idx_end != -1:
    content = content[:idx_start] + new_code + content[idx_end:]
    codecs.open('app.py', 'w', 'utf-8').write(content)
    print("Success replacing upload_thread")
else:
    print("Not found indices")
