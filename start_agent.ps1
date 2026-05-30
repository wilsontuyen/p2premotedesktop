# Khởi chạy Clipboard Agent không hiện cửa sổ (ẩn)
$scriptPath = Join-Path $PSScriptRoot "clipboard_agent.py"
$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $pythonExe)) {
    $pythonExe = "pythonw.exe" # Fallback to system Python if venv is missing
}

Start-Process -FilePath $pythonExe -ArgumentList "`"$scriptPath`"" -WindowStyle Hidden
Write-Host "Clipboard Agent started."
