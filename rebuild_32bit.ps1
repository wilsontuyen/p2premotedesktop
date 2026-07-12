$ErrorActionPreference = "Stop"

$pythonInstaller = "python-3.8.10.exe"
$pythonUrl = "https://www.python.org/ftp/python/3.8.10/python-3.8.10.exe"
$pythonDir = "$Env:LocalAppData\Programs\Python\Python38-32"
$pythonExe = "$pythonDir\python.exe"

if (-Not (Test-Path $pythonExe)) {
    Write-Host "Downloading Python 3.8.10 (32-bit)..."
    Invoke-WebRequest -Uri $pythonUrl -OutFile $pythonInstaller
    
    Write-Host "Installing Python 3.8.10 (32-bit) silently..."
    $process = Start-Process -FilePath ".\$pythonInstaller" -ArgumentList "/quiet InstallAllUsers=0 PrependPath=0 Include_test=0 TargetDir=`"$pythonDir`"" -Wait -NoNewWindow -PassThru
    
    if ($process.ExitCode -ne 0) {
        Write-Host "Python 32-bit installation failed with code $($process.ExitCode)."
        exit 1
    }
}

Write-Host "Removing old 64-bit .venv..."
if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }

Write-Host "Creating new .venv with Python 3.8 (32-bit)..."
& $pythonExe -m venv .venv

Write-Host "Upgrading pip..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip

Write-Host "Installing requirements..."
.\.venv\Scripts\pip.exe install -r requirements.txt

Write-Host "Running build_and_deploy.py for 32-bit..."
.\.venv\Scripts\python.exe build_and_deploy.py

Write-Host "Done! 32-bit build complete."
