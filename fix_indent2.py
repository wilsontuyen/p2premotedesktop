import codecs

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\\r\\n', '\\n')

search = """                                            def auto_refresh_local():
                                                        time.sleep(2)
                                                        fm_event_queue.put({"type": "trigger_local_refresh"})
                                                    threading.Thread(target=auto_refresh_local, daemon=True).start()"""

replace = """                                            def auto_refresh_local():
                                                time.sleep(2)
                                                fm_event_queue.put({"type": "trigger_local_refresh"})
                                            threading.Thread(target=auto_refresh_local, daemon=True).start()"""

if search in content:
    content = content.replace(search, replace)
    print("Fixed indent 2")
else:
    print("Not found indent 2")

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Done")
