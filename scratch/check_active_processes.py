import subprocess
import json

def get_processes():
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    cmd = ["powershell", "-Command", "Get-CimInstance Win32_Process -Filter \"Name='RemoteDesktopP2P.exe'\" | ForEach-Object { @{ ProcessId = $_.ProcessId; CommandLine = $_.CommandLine; SessionId = $_.SessionId } } | ConvertTo-Json -Compress"]
    res = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startupinfo)
    print("STDOUT:", res.stdout)
    print("STDERR:", res.stderr)

if __name__ == "__main__":
    get_processes()
