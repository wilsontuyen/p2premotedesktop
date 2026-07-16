# Stop Scheduled Task
Stop-ScheduledTask -TaskName 'EasyRemoteDesktopAgent' -ErrorAction SilentlyContinue

# Kill active instances
taskkill /F /IM RemoteDesktopP2P.exe /T
taskkill /F /IM RemoteDesktopService.exe /T
Start-Sleep -Seconds 2

# Copy files
$Src = "D:\Data\AG\remote_desktop\dist_nuitka\app.dist"
$Dst = "C:\Apps\P2P"

if (!(Test-Path $Dst)) {
    New-Item -ItemType Directory -Force -Path $Dst
}

# Use Robocopy or Copy-Item to copy files
# robocopy is more robust and handles overwriting locked files better
robocopy $Src $Dst /E /IS /IT /R:3 /W:1

# Start Scheduled Task
Start-ScheduledTask -TaskName 'EasyRemoteDesktopAgent' -ErrorAction SilentlyContinue

# Start Client Application
Start-Process -FilePath "C:\Apps\P2P\RemoteDesktopP2P.exe" -WorkingDirectory $Dst
