import re

with open('utils/file_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix fm_top
content = content.replace("globals()['fm_top'] = top", "import core.viewer\n        core.viewer.fm_top = top")

# Fix file_manager_callback
content = content.replace("globals()['file_manager_callback'] = lambda e: fm_event_queue.put(e)", "import core.viewer\n        core.viewer.file_manager_callback = lambda e: fm_event_queue.put(e)")

# Fix on_close fm_is_open
content = content.replace("globals()['fm_is_open'] = False", "import core.viewer\n            core.viewer.fm_is_open = False\n            core.viewer.fm_top = None\n            core.viewer.file_manager_callback = None")

# Fix clipboard_sync_manager
content = content.replace("cm = globals().get('clipboard_sync_manager')", "import core.viewer\n                cm = getattr(core.viewer, 'clipboard_sync_manager', None)")

# Fix the exception handler fm_is_open = False at the very end
content = content.replace("globals()['fm_is_open'] = False\n        import traceback", "import core.viewer; core.viewer.fm_is_open = False\n        import traceback")

# Change on_close to destroy instead of withdraw
content = content.replace("try: top.withdraw()", "try: top.quit(); top.destroy()")

with open('utils/file_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)
