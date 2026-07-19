import os
import subprocess
import time
import sys
import signal

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode('utf-8').strip()
    except:
        return ""

def log_debug(msg):
    try:
        with open("/opt/p2p_remote/service_debug.log", "a") as f:
            f.write(msg + "\n")
    except:
        pass

def get_active_session_info():
    """
    Finds the active X11 display and XAUTHORITY file by querying loginctl for the active user,
    then inspecting process lists to find the exact X server command line for that user.
    """
    log_debug("=== get_active_session_info called ===")
    
    # 1. Identify the active user/uid via loginctl
    active_session_line = run_cmd("loginctl show-seat seat0 | grep ActiveSession")
    log_debug(f"loginctl active_session_line: {active_session_line}")
    if not active_session_line:
        return None, None
        
    session_id = active_session_line.split("=")[-1].strip()
    log_debug(f"session_id: {session_id}")
    if not session_id:
        return None, None
        
    user = run_cmd(f"loginctl show-session {session_id} -p Name --value")
    uid = run_cmd(f"id -u {user}")
    log_debug(f"user: {user}, uid: {uid}")
    
    if not user or not uid:
        return None, None

    # 2. Inspect running X servers to find the one belonging to this user/uid
    output = run_cmd("ps -eo pid,user,command | grep -E 'Xorg|Xwayland' | grep -v grep")
    log_debug(f"ps output:\n{output}")
    found_auth = None
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        p_user = parts[1]
        
        display = None
        auth = None
        for i, part in enumerate(parts):
            if part.startswith(":") and part[1:].isdigit():
                display = part
            if part == "-auth" and i + 1 < len(parts):
                auth = parts[i+1]
                
        log_debug(f"Parsed ps line - user: {p_user}, display: {display}, auth: {auth}")
        
        is_our_user = (p_user == user or str(uid) in p_user)
        has_our_auth = auth and (f"/run/user/{uid}/" in auth or f"/home/{user}/" in auth or f"/var/run/lightdm/{user}/" in auth)
        
        if is_our_user or has_our_auth:
            if auth:
                found_auth = auth
            if display:
                log_debug(f"MATCH FOUND in ps! display: {display}, auth: {auth}")
                if auth and os.path.exists(auth):
                    return display, auth
                    
    # 3. If display was hidden (e.g. -displayfd), search user's processes environment
    log_debug("Display not found in ps, checking user process environments...")
    env_display = None
    try:
        pids = run_cmd(f"pgrep -u {uid}").split()
        for pid in pids:
            try:
                with open(f"/proc/{pid}/environ", "r") as env_file:
                    env_data = env_file.read()
                    for item in env_data.split('\0'):
                        if item.startswith("DISPLAY=:"):
                            env_display = item.split("=")[1]
                            break
            except:
                pass
            if env_display:
                log_debug(f"Found DISPLAY={env_display} in process {pid}")
                break
    except Exception as e:
        log_debug(f"Error checking environ: {e}")

    display = env_display
    if not display:
        display = run_cmd(f"loginctl show-session {session_id} -p Display --value")
        log_debug(f"Fallback loginctl display: {display}")
        if not display:
            display = ":0"
            log_debug(f"Defaulting fallback display to :0")
    
    # Resolve auth
    auth = found_auth
    if not auth or not os.path.exists(auth):
        auth_paths = [
            f"/home/{user}/.Xauthority",
            f"/run/user/{uid}/gdm/Xauthority",
            f"/run/user/{uid}/Xauthority",
            f"/var/run/lightdm/{user}/xauthority"
        ]
        for p in auth_paths:
            if os.path.exists(p):
                auth = p
                break

    log_debug(f"Final resolution: display={display}, auth={auth}")
    if display and auth:
        return display, auth

    log_debug("FAILED to find any valid display and auth")
    return None, None

def main():
    agent_path = "/opt/p2p_remote/EasyRemoteDesktop"
    
    current_proc = None
    last_auth = None

    def handle_exit(signum, frame):
        if current_proc and current_proc.poll() is None:
            current_proc.terminate()
            try:
                current_proc.wait(timeout=5)
            except:
                current_proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    print("[Service Loop] Starting Linux Service Loop...")

    while True:
        display, auth = get_active_session_info()
        
        if display and auth:
            # If agent crashed, or session changed (user logged in/out), relaunch!
            if current_proc is None or current_proc.poll() is not None or auth != last_auth:
                if current_proc and current_proc.poll() is None:
                    print(f"[Service Loop] Session changed to {auth}. Killing old agent...")
                    current_proc.terminate()
                    try:
                        current_proc.wait(timeout=5)
                    except:
                        current_proc.kill()
                
                print(f"[Service Loop] Launching agent with DISPLAY={display} and XAUTHORITY={auth}")
                env = os.environ.copy()
                env["DISPLAY"] = display
                env["XAUTHORITY"] = auth
                
                cmd = f"{agent_path} --headless"
                current_proc = subprocess.Popen(cmd, shell=True, env=env)
                last_auth = auth
        else:
            if current_proc and current_proc.poll() is None:
                print("[Service Loop] No active X session found (e.g. system suspending). Killing agent...")
                current_proc.terminate()
                try:
                    current_proc.wait(timeout=5)
                except:
                    current_proc.kill()
            last_auth = None
            
        time.sleep(3)

if __name__ == "__main__":
    main()
