# Kill all running instances
taskkill /F /IM RemoteDesktopService.exe 2>$null
taskkill /F /IM RemoteDesktopP2P.exe 2>$null
Start-Sleep -Seconds 3

# Deploy from build output to target
$src = "d:\Data\AG\remote_desktop\dist_nuitka\app.dist"
$dst = "C:\Apps\P2P"

Copy-Item -Path "$src\*" -Destination $dst -Recurse -Force -ErrorAction Continue

# Restart service
schtasks /change /tn "EasyRemoteDesktopAgent" /enable
schtasks /run /tn "EasyRemoteDesktopAgent"
Start-Sleep -Seconds 5

# Launch GUI
Start-Process "$dst\RemoteDesktopP2P.exe" -WorkingDirectory $dst

"DEPLOY DONE" | Out-File "$dst\deploy_done.txt"
