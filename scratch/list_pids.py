import psutil

pids = [37332, 1900]
for pid in pids:
    try:
        p = psutil.Process(pid)
        try:
            username = p.username()
            cmdline = p.cmdline()
        except Exception as e:
            username = f"AccessDenied ({e})"
            cmdline = "N/A"
        print(f"PID: {pid:<6} | Name: {p.name():<30} | User: {username:<20} | Cmd: {cmdline}")
    except Exception as e:
        print(f"PID: {pid:<6} | Error: {e}")
