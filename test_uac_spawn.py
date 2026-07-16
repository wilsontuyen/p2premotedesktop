import ctypes, win32api, win32security, win32con, win32process, os, time

winlogon_pid = None
try:
    import psutil
    for p in psutil.process_iter(['pid', 'name']):
        if p.info['name'].lower() == 'winlogon.exe':
            winlogon_pid = p.info['pid']
            break
except: pass

h_winlogon = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, winlogon_pid)
h_token = win32security.OpenProcessToken(h_winlogon, win32con.TOKEN_DUPLICATE | win32con.TOKEN_QUERY | win32con.TOKEN_ASSIGN_PRIMARY)
h_token_dup = win32security.DuplicateTokenEx(h_token, win32security.SecurityImpersonation, win32con.TOKEN_ALL_ACCESS, win32security.TokenPrimary)

si = win32process.STARTUPINFO()
si.lpDesktop = 'winsta0\\winlogon'

py_code = """
import ctypes, time, threading

def get_desktop_name():
    try:
        h_desk = ctypes.windll.user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
        name = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetUserObjectInformationW(h_desk, 2, name, ctypes.sizeof(name), None)
        return name.value.lower()
    except:
        return "default"

def open_active_input_desktop():
    for access_mask in [0x02000000, 0x10000000, 0x0101, 0x80000000, 0x0001]:
        h = ctypes.windll.user32.OpenInputDesktop(0, False, access_mask)
        if h: return h
    return 0

def check_desktop_change():
    h_input = open_active_input_desktop()
    if not h_input:
        with open(r"C:\\Apps\\P2P\\uac_debug_test.txt", "a") as f: f.write("Blocked\\n")
        return False, True
    name_input = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetUserObjectInformationW(h_input, 2, name_input, ctypes.sizeof(name_input), None)
    ctypes.windll.user32.CloseDesktop(h_input)
    input_name = name_input.value.lower()
    thread_name = get_desktop_name()
    if input_name != thread_name:
        with open(r"C:\\Apps\\P2P\\uac_debug_test.txt", "a") as f:
            f.write(f"Needs switch: {input_name} != {thread_name}\\n")
        return True, False
    return False, False

def sender_thread():
    check_desktop_change()

t = threading.Thread(target=sender_thread)
t.start()
t.join()
"""
with open('C:\\Apps\\P2P\\test_uac_inner.py', 'w') as f: f.write(py_code)

pid, _, _, _ = win32process.CreateProcessAsUser(h_token_dup, r'd:\Data\AG\remote_desktop\.venv\Scripts\python.exe', 'python C:\\Apps\\P2P\\test_uac_inner.py', None, None, False, 0, None, r'C:\Apps\P2P', si)
print('Spawned PID:', pid)
time.sleep(2)
