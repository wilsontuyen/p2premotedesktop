import ctypes, win32api, win32security, win32con, win32process, os, time, sys, subprocess

def find_winlogon_pid():
    try:
        import psutil
        # Get active session ID
        try:
            active_session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
        except:
            active_session_id = 1
        for p in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                if p.info['name'].lower() == 'winlogon.exe':
                    # Check if session ID matches
                    p_session = ctypes.c_ulong()
                    if ctypes.windll.kernel32.ProcessIdToSessionId(p.info['pid'], ctypes.byref(p_session)):
                        if p_session.value == active_session_id:
                            return p.info['pid']
            except:
                pass
    except Exception as e:
        print("Error finding winlogon PID:", e)
    return None

def run_test_as_system():
    winlogon_pid = find_winlogon_pid()
    if not winlogon_pid:
        print("Could not find winlogon.exe. Are you running as Admin?")
        return
    print(f"Found winlogon PID: {winlogon_pid}")
    
    h_winlogon = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, winlogon_pid)
    h_token = win32security.OpenProcessToken(h_winlogon, win32con.TOKEN_DUPLICATE | win32con.TOKEN_QUERY | win32con.TOKEN_ASSIGN_PRIMARY)
    h_token_dup = win32security.DuplicateTokenEx(h_token, win32security.SecurityImpersonation, win32con.TOKEN_ALL_ACCESS, win32security.TokenPrimary)
    
    si = win32process.STARTUPINFO()
    si.lpDesktop = 'winsta0\\winlogon'
    
    py_code = """
import ctypes, time, threading, os

log_file = r"C:\\Apps\\P2P\\uac_switch_test_log.txt"
if os.path.exists(log_file):
    try: os.remove(log_file)
    except: pass

def log(msg):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {msg}\\n")
    print(f"{timestamp} {msg}")

def get_desktop_name(h_desk=None):
    try:
        if h_desk is None:
            h_desk = ctypes.windll.user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
        name = ctypes.create_unicode_buffer(256)
        size = ctypes.c_ulong(256)
        if ctypes.windll.user32.GetUserObjectInformationW(h_desk, 2, name, size, None):
            return name.value.lower()
    except Exception as e:
        return f"err_{e}"
    return "unknown"

def open_active_input_desktop():
    for mask in [0x02000000, 0x10000000, 0x0101, 0x80000000, 0x0001]:
        h = ctypes.windll.user32.OpenInputDesktop(0, False, mask)
        if h:
            return h
    return 0

def check_desktop_change():
    h_input = open_active_input_desktop()
    if not h_input:
        err = ctypes.windll.kernel32.GetLastError()
        return None, f"Failed to open input desktop. GetLastError: {err}"
    
    input_name = get_desktop_name(h_input)
    ctypes.windll.user32.CloseDesktop(h_input)
    
    thread_name = get_desktop_name()
    if input_name != thread_name:
        return input_name, None
    return None, None

def test_thread_loop():
    log(f"Test thread started. Initial desktop: {get_desktop_name()}")
    
    # Try switching to default desktop initially (since we spawned on winlogon)
    h_default = ctypes.windll.user32.OpenDesktopW("default", 0, False, 0x02000000)
    if h_default:
        res = ctypes.windll.user32.SetThreadDesktop(h_default)
        err = ctypes.windll.kernel32.GetLastError()
        log(f"Initial SetThreadDesktop to default: {res}, GetLastError: {err}, Current desktop: {get_desktop_name()}")
        ctypes.windll.user32.CloseDesktop(h_default)
    else:
        err = ctypes.windll.kernel32.GetLastError()
        log(f"Failed to open default desktop: {err}")

    # Loop to check for UAC switch
    for i in range(40): # Run for 20 seconds
        time.sleep(0.5)
        target_desktop, err_msg = check_desktop_change()
        if err_msg:
            log(f"Check error: {err_msg}")
            continue
        if target_desktop:
            log(f"Desktop change detected! Active desktop is: {target_desktop}. Thread is on: {get_desktop_name()}")
            # Attempt switch
            h_target = ctypes.windll.user32.OpenDesktopW(target_desktop, 0, False, 0x02000000)
            if h_target:
                res = ctypes.windll.user32.SetThreadDesktop(h_target)
                err = ctypes.windll.kernel32.GetLastError()
                log(f"SetThreadDesktop to {target_desktop}: {res}, GetLastError: {err}, New desktop: {get_desktop_name()}")
                ctypes.windll.user32.CloseDesktop(h_target)
            else:
                err = ctypes.windll.kernel32.GetLastError()
                log(f"Failed to open target desktop {target_desktop}: {err}")

log("Starting test process inner...")
t = threading.Thread(target=test_thread_loop)
t.start()
t.join()
log("Test process inner finished.")
"""
    inner_script = r"C:\Apps\P2P\test_uac_switch_inner.py"
    with open(inner_script, 'w', encoding='utf-8') as f:
        f.write(py_code)
    
    python_exe = sys.executable
    h_process, h_thread, process_id, thread_id = win32process.CreateProcessAsUser(
        h_token_dup, 
        python_exe, 
        f'python "{inner_script}"', 
        None, None, False, 0, None, r'C:\Apps\P2P', si
    )
    print(f"Spawned process ID {process_id} under winlogon desktop as SYSTEM.")
    
    # Wait 3 seconds, then trigger UAC
    time.sleep(3.0)
    print("Triggering UAC prompt...")
    # Trigger UAC via powershell RunAs
    subprocess.Popen('powershell -Command "Start-Process cmd.exe -Verb RunAs"', shell=True)
    
    # Wait for completion or timeout
    for _ in range(30):
        time.sleep(1.0)
        exit_code = win32process.GetExitCodeProcess(h_process)
        if exit_code != win32con.STILL_ACTIVE:
            break
            
    win32api.CloseHandle(h_process)
    win32api.CloseHandle(h_thread)
    
    # Dismiss any leftover UAC prompts
    subprocess.run('taskkill /F /IM consent.exe', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    print("\n--- TEST LOG ---")
    log_file = r"C:\Apps\P2P\uac_switch_test_log.txt"
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            print(f.read())
    else:
        print("Log file not found.")

if __name__ == "__main__":
    run_test_as_system()
