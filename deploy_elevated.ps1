# Stop scheduled task
Stop-ScheduledTask -TaskName 'EasyRemoteDesktopAgent' -ErrorAction SilentlyContinue

# Kill all active instances of service and agent
taskkill /F /IM RemoteDesktopService.exe
taskkill /F /IM RemoteDesktopP2P.exe
Start-Sleep -Seconds 2

# Copy files
$Src = "C:\Users\Tuyen\.gemini\antigravity\scratch\remote_desktop\dist_nuitka\app.dist\*"
$Dst = "C:\Apps\P2P"
Copy-Item -Path $Src -Destination $Dst -Recurse -Force

# Start scheduled task
Start-ScheduledTask -TaskName 'EasyRemoteDesktopAgent' -ErrorAction SilentlyContinue

# Start GUI Agent on user desktop (runs as current user) using explorer
explorer.exe "C:\Apps\P2P\RemoteDesktopP2P.exe"
