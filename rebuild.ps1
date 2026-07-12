$ErrorActionPreference = "Stop"
Write-Host "Removing old .venv..."
if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }
Write-Host "Creating new .venv with Python 3.8..."
& "$Env:LocalAppData\Programs\Python\Python38\python.exe" -m venv .venv
Write-Host "Upgrading pip..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
Write-Host "Installing requirements..."
.\.venv\Scripts\pip.exe install -r requirements.txt
Write-Host "Running build_and_deploy.py..."
.\.venv\Scripts\python.exe build_and_deploy.py
