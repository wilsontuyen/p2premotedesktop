import subprocess
out = subprocess.check_output('wmic process where "name like \'%RemoteDesktop%\'" get ProcessID,CommandLine', shell=True)
print(out.decode('utf-8', errors='ignore'))
