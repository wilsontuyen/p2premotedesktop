import re

with open('d:/Data/AG/remote_desktop/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Restore the fallback copy icon
content = content.replace('"📋": "»"', '"📋": "❐"')

# 2. Add wait cursor to refresh_list
old_def = "        def refresh_list(force=False):"
new_def = '''        def refresh_list(force=False):
            dialog.config(cursor="wait")
            dialog.update_idletasks()
            
            def _refresh_task():
                try:
                    _refresh_list_inner(force)
                finally:
                    dialog.config(cursor="")
            
            dialog.after(10, _refresh_task)
            
        def _refresh_list_inner(force=False):'''

content = content.replace(old_def, new_def, 1)

with open('d:/Data/AG/remote_desktop/app.py', 'w', encoding='utf-8') as f:
    f.write(content)

