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
        
        if display:
            is_our_user = (p_user == user or str(uid) in p_user)
            has_our_auth = auth and (f"/run/user/{uid}/" in auth or f"/home/{user}/" in auth or f"/var/run/lightdm/{user}/" in auth)
            log_debug(f"is_our_user: {is_our_user}, has_our_auth: {has_our_auth}")
            
            if is_our_user or has_our_auth:
                log_debug(f"MATCH FOUND in ps! display: {display}, auth: {auth}")
                if not auth:
                    for p in [f"/home/{user}/.Xauthority", f"/run/user/{uid}/gdm/Xauthority", f"/run/user/{uid}/Xauthority"]:
                        if os.path.exists(p):
                            auth = p
                            log_debug(f"Guessed auth from standard paths: {auth}")
                            break
                if auth and os.path.exists(auth):
                    log_debug(f"Returning from ps: {display}, {auth}")
                    return display, auth
                else:
                    log_debug(f"Auth file {auth} does not exist!")

    # 3. Fallback: if X server hides -auth or we couldn't match, guess standard paths
    display = run_cmd(f"loginctl show-session {session_id} -p Display --value")
    log_debug(f"Fallback loginctl display: {display}")
    if not display:
        display = ":0"
        log_debug(f"Defaulting fallback display to :0")
    
    auth_paths = [
        f"/home/{user}/.Xauthority",
        f"/run/user/{uid}/gdm/Xauthority",
        f"/run/user/{uid}/Xauthority",
        f"/var/run/lightdm/{user}/xauthority"
    ]
    for p in auth_paths:
        if os.path.exists(p):
            log_debug(f"Returning from fallback: {display}, {p}")
            return display, p

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
