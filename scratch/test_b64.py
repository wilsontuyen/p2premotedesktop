import base64

cmd_host = (
    "$t = Get-ScheduledTask -TaskName 'EasyRemoteDesktopHostAgent' -ErrorAction SilentlyContinue; "
    "if ($t) { "
    "$t.Settings.DisallowStartIfOnBatteries = $false; "
    "$t.Settings.StopIfGoingOnBatteries = $false; "
    "$t.Settings.ExecutionTimeLimit = 'PT0S'; "
    "Set-ScheduledTask -InputObject $t "
    "}"
)

cmd_full = (
    "$t = Get-ScheduledTask -TaskName 'EasyRemoteDesktopAgent' -ErrorAction SilentlyContinue; "
    "if ($t) { "
    "$t.Settings.DisallowStartIfOnBatteries = $false; "
    "$t.Settings.StopIfGoingOnBatteries = $false; "
    "$t.Settings.ExecutionTimeLimit = 'PT0S'; "
    "Set-ScheduledTask -InputObject $t "
    "}"
)

b64_host = base64.b64encode(cmd_host.encode('utf-16le')).decode('ascii')
b64_full = base64.b64encode(cmd_full.encode('utf-16le')).decode('ascii')

print("B64_HOST:", b64_host)
print("B64_FULL:", b64_full)
