import sys
import re

with open('app.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. check_is_menu_query signature
text = re.sub(
    r'def check_is_menu_query\(last_lbutton, last_rbutton, meta_arrival_time\):',
    r'def check_is_menu_query(last_lbutton, last_rbutton, meta_arrival_time, last_menu_time=0.0):',
    text
)

# 2. check_is_menu_query logic
pattern2 = r'(\s*# 4\. Nếu vừa click chuột trái.*?)(?=class ClipboardSyncManager:)'
def repl2(m):
    return '''
    time_since_menu = t_now - last_menu_time
    if time_since_menu < 1.5 and time_since_lbutton < 1.5:
        log_debug(f"[check_is_menu_query] Tra ve False: Vua click chuot trai sau khi menu dong")
        return False
        
    log_debug(f"[check_is_menu_query] Tra ve True: Mac dinh coi la nen hoac truy van tu dong")
    return True

'''
text = re.sub(pattern2, repl2, text, flags=re.DOTALL)

# 3. _mouse_poll_loop
pattern3 = r'(self\.manager\.last_rbutton_time = time\.time\(\)\n\s*)(time\.sleep\(0\.05\))'
text = re.sub(
    pattern3,
    r'\1if user32.FindWindowW("#32768", None):\n                if self.manager:\n                    self.manager.last_menu_time = time.time()\n            \2',
    text
)

# 4. ClipboardSyncManager init
pattern4 = r'(self\.last_lbutton_time = 0\n\s*)(if ENABLE_CLIPBOARD_SYNC:)'
text = re.sub(
    pattern4,
    r'\1self.last_menu_time = 0\n        \2',
    text
)

# 5. render_format call
pattern5 = r'(last_r = getattr\(self, \'last_rbutton_time\', 0\.0\)\n\s*)(meta_time = getattr\(self, \'meta_arrival_time\', 0\.0\)\n\s*)(is_menu = check_is_menu_query\(last_l, last_r, meta_time\))'
text = re.sub(
    pattern5,
    r'\1\2last_m = getattr(self, "last_menu_time", 0.0)\n        is_menu = check_is_menu_query(last_l, last_r, meta_time, last_m)',
    text
)

# 6. handle_received_packet clipboard_text
pattern6 = r'(self\.last_received_text = text\n\s*)(self\.ignore_destroy_clipboard = True)'
text = re.sub(
    pattern6,
    r'\1self.last_sent_text = text\n            \2',
    text
)

# 7. _agent_mouse_poll_loop
pattern7_vars = r'(_agent_last_rbutton_time = 0\.0\n\s*)(_agent_meta_arrival_time = 0\.0)'
text = re.sub(
    pattern7_vars,
    r'\1_agent_last_menu_time = 0.0\n    \2',
    text
)

pattern7_loop = r'(nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time\n\s*user32 = ctypes\.windll\.user32)'
text = re.sub(
    pattern7_loop,
    r'nonlocal _agent_last_lbutton_time, _agent_last_rbutton_time, _agent_last_menu_time\n        user32 = ctypes.windll.user32',
    text
)

pattern7_loop_logic = r'(_agent_last_rbutton_time = time\.time\(\)\n\s*)(except:)'
text = re.sub(
    pattern7_loop_logic,
    r'\1if user32.FindWindowW("#32768", None):\n                    _agent_last_menu_time = time.time()\n            \2',
    text
)

# 8. agent call check_is_menu_query
pattern8 = r'is_menu = check_is_menu_query\(_agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time\)'
text = re.sub(
    pattern8,
    r'is_menu = check_is_menu_query(_agent_last_lbutton_time, _agent_last_rbutton_time, _agent_meta_arrival_time, _agent_last_menu_time)',
    text
)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("All replacements done!")
