import re

with open('d:/Data/AG/remote_desktop/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Restore the fallback copy icon
content = content.replace('"📋": "»"', '"📋": "❐"')

# 2. Add wait cursor to refresh_list
# We will do a simple string replace for the definition of refresh_list.
# The original starts with:
old_def = '''        def refresh_list(force=False):
            query = search_var.get().strip().lower()'''

new_def = '''        def refresh_list(force=False):
            dialog.config(cursor="wait")
            dialog.update_idletasks()
            
            def _actual_refresh():
                try:
                    query = search_var.get().strip().lower()'''

content = content.replace(old_def, new_def)

# Now we need to indent everything inside refresh_list
# refresh_list ends at `reorder_list()` before `bottom_frame = tk.Frame...`
lines = content.split('\n')
in_refresh = False
for i, line in enumerate(lines):
    if line.startswith('                query = search_var.get().strip().lower()'):
        in_refresh = True
        
    if in_refresh:
        # Check if we reached the end of refresh_list
        if line.startswith('        # Bottom buttons panel'):
            in_refresh = False
            # Insert the finally block before this line
            # The previous line is `            reorder_list()`
            # We need to add the finally block there.
            pass
        else:
            if line.strip() != "":
                lines[i] = '    ' + line

content = '\n'.join(lines)

old_end = '''                self.query_computer_status(clean_id)
                
            reorder_list()

        # Bottom buttons panel'''

new_end = '''                self.query_computer_status(clean_id)
                
            reorder_list()
            
        finally:
            dialog.config(cursor="")
            
    dialog.after(10, _actual_refresh)

        # Bottom buttons panel'''

content = content.replace(old_end, new_end)

with open('d:/Data/AG/remote_desktop/app.py', 'w', encoding='utf-8') as f:
    f.write(content)

