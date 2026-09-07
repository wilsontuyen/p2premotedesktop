@echo off
setlocal EnableExtensions
title Easy Remote Desktop Installer
cd /d "%~dp0"

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo ========================================================
    echo  Administrator privileges are required to install.
    echo  Relaunching as Administrator...
    echo ========================================================
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo ========================================================
echo  Installing Easy Remote Desktop Agent and Service...
echo ========================================================
echo.

set "INSTALL_DIR=C:\Program Files (x86)\Easy Remote Desktop"
set "EXE_APP=%INSTALL_DIR%\RemoteDesktopP2P.exe"
set "EXE_SVC=%INSTALL_DIR%\RemoteDesktopService.exe"
set "TASK_NAME=EasyRemoteDesktopAgent"

echo [+] Installation directory: "%INSTALL_DIR%"

echo [+] Stopping existing instances and services...
schtasks /end /tn "%TASK_NAME%" >nul 2>&1
taskkill /F /IM RemoteDesktopService.exe >nul 2>&1
taskkill /F /IM RemoteDesktopP2P.exe >nul 2>&1
timeout /t 2 /nobreak >nul

if exist "%INSTALL_DIR%" goto :do_copy
echo [+] Creating directory: "%INSTALL_DIR%"
mkdir "%INSTALL_DIR%"
if errorlevel 1 goto :fail_mkdir

:do_copy
echo [+] Copying installation files to "%INSTALL_DIR%"...
xcopy /E /I /Y /H /Q "%~dp0*" "%INSTALL_DIR%\"
if errorlevel 1 goto :fail_copy

if not exist "%EXE_APP%" goto :fail_missing_app
if not exist "%EXE_SVC%" goto :fail_missing_svc

:: Allow the logged-on user to write session_pass.txt and logs
icacls "%INSTALL_DIR%" /grant *S-1-5-32-545:(OI)(CI)M >nul 2>&1

echo [+] Configuring Windows Firewall exceptions...
netsh advfirewall firewall delete rule name="EasyRemoteDesktopAgent" >nul 2>&1
netsh advfirewall firewall delete rule name="EasyRemoteDesktopService" >nul 2>&1
netsh advfirewall firewall add rule name="EasyRemoteDesktopAgent" dir=in action=allow program="%EXE_APP%" enable=yes profile=any
netsh advfirewall firewall add rule name="EasyRemoteDesktopService" dir=in action=allow program="%EXE_SVC%" enable=yes profile=any

echo [+] Registering background system service (Scheduled Task)...
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1
schtasks /create /tn "%TASK_NAME%" /tr "\"%EXE_SVC%\"" /sc onstart /ru "NT AUTHORITY\SYSTEM" /rl highest /f
if errorlevel 1 goto :fail_task

echo [+] Starting background service...
schtasks /run /tn "%TASK_NAME%"

echo [+] Creating shortcuts...
set "START_MENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs\Easy Remote Desktop"
if not exist "%START_MENU%" mkdir "%START_MENU%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$dir = 'C:\Program Files (x86)\Easy Remote Desktop'; $exe = Join-Path $dir 'RemoteDesktopP2P.exe'; $ws = New-Object -ComObject WScript.Shell; $desk = Join-Path $env:PUBLIC 'Desktop\Easy Remote Desktop.lnk'; $s1 = $ws.CreateShortcut($desk); $s1.TargetPath = $exe; $s1.WorkingDirectory = $dir; $s1.IconLocation = $exe; $s1.Save(); $menu = Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs\Easy Remote Desktop\Easy Remote Desktop.lnk'; $s2 = $ws.CreateShortcut($menu); $s2.TargetPath = $exe; $s2.WorkingDirectory = $dir; $s2.IconLocation = $exe; $s2.Save();"

echo [+] Waiting for service to initialize...
timeout /t 5 /nobreak >nul

echo [+] Starting Easy Remote Desktop...
start "" /D "%INSTALL_DIR%" "%EXE_APP%"

echo.
echo ========================================================
echo  INSTALLATION COMPLETED SUCCESSFULLY!
echo  Folder: "%INSTALL_DIR%"
echo ========================================================
echo.
timeout /t 3
exit /b 0

:fail_mkdir
echo [!] Failed to create "%INSTALL_DIR%"
pause
exit /b 1

:fail_copy
echo [!] File copy failed.
pause
exit /b 1

:fail_missing_app
echo [!] Missing RemoteDesktopP2P.exe after copy.
pause
exit /b 1

:fail_missing_svc
echo [!] Missing RemoteDesktopService.exe after copy.
pause
exit /b 1

:fail_task
echo [!] Failed to create scheduled task "%TASK_NAME%".
pause
exit /b 1
