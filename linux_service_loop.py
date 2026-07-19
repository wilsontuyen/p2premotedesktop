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

def get_active_session_info():
    """
    Finds the active X11 display and XAUTHORITY file.
    Works for both GDM (login screen) and logged-in user sessions.
    """
    # 1. Try process inspection (very robust for typical setups, gets exact -auth path)
    output = run_cmd("ps -eo pid,user,command | grep -E 'Xorg|Xwayland' | grep -v grep")
    for line in output.splitlines():
        parts = line.split()
        display = None
        auth = None
        for i, part in enumerate(parts):
            if part.startswith(":") and part[1:].isdigit():
                display = part
            if part == "-auth" and i + 1 < len(parts):
                auth = parts[i+1]
        if display and auth and os.path.exists(auth):
            return display, auth

    # 2. Fallback to active seat via loginctl
    active_session_line = run_cmd("loginctl show-seat seat0 | grep ActiveSession")
    if active_session_line:
        session_id = active_session_line.split("=")[-1].strip()
        if session_id:
            user = run_cmd(f"loginctl show-session {session_id} -p Name --value")
            display = run_cmd(f"loginctl show-session {session_id} -p Display --value")
            if not display:
                display = ":0" # Fallback if loginctl doesn't report display
            
            uid = run_cmd(f"id -u {user}")
            if uid:
                # Typical Xauthority paths (standard first)
                auth_paths = [
                    f"/home/{user}/.Xauthority",
                    f"/run/user/{uid}/gdm/Xauthority",
                    f"/run/user/{uid}/Xauthority",
                    f"/var/run/lightdm/{user}/xauthority"
                ]
                for p in auth_paths:
                    if os.path.exists(p):
                        return display, p

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
