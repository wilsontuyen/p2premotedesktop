# PowerShell script to register EasyRemoteDesktopAgent in Windows Task Scheduler as SYSTEM

# Require Administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Please run this script as an Administrator."
    Exit
}

$WorkspaceDir = Get-Location
$PythonwExe = "$WorkspaceDir\.venv\Scripts\pythonw.exe"
$ScriptPy = "$WorkspaceDir\windows_service_loop.py"

if (-not (Test-Path $PythonwExe)) {
    Write-Error "Could not find pythonw.exe at: $PythonwExe"
    Exit
}
if (-not (Test-Path $ScriptPy)) {
    Write-Error "Could not find script at: $ScriptPy"
    Exit
}

$TaskName = "EasyRemoteDesktopAgent"

# 1. Unregister existing task if any
Write-Host "Checking for existing task..."
$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Existing) {
    Write-Host "Stopping and removing existing task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# 2. Configure new task
Write-Host "Configuring task action and trigger..."
$Action = New-ScheduledTaskAction -Execute "$PythonwExe" -Argument "`"$ScriptPy`""
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Compatibility Win8

# 3. Register task
Write-Host "Registering task in Task Scheduler..."
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force

# 4. Start task immediately
Write-Host "Starting task immediately..."
Start-ScheduledTask -TaskName $TaskName

Write-Host "Success! EasyRemoteDesktopAgent is now registered and running in the background as SYSTEM."
Write-Host "It will automatically start at boot, before any user logs in."
