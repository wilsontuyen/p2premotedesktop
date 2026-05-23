# PowerShell script to unregister EasyRemoteDesktopAgent from Windows Task Scheduler

# Require Administrator
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Error "Please run this script as an Administrator."
    Exit
}

$TaskName = "EasyRemoteDesktopAgent"

$Existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Existing) {
    Write-Host "Stopping and removing task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Success! EasyRemoteDesktopAgent task has been removed."
} else {
    Write-Host "Task '$TaskName' does not exist."
}
