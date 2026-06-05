@echo off
title Easy Remote Desktop Installer

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo ========================================================
    echo  Administrator privileges are required to install.
    echo  Relaunching as Administrator...
    echo ========================================================
    powershell -Command "Start-Process -FilePath '%0' -Verb RunAs"
    exit /b
)

echo.
echo ========================================================
echo  Installing Easy Remote Desktop Agent and Service...
echo ========================================================
echo.

set "INSTALL_DIR=C:\Apps\P2P"
echo [+] Installation directory: %INSTALL_DIR%
if not exist "%INSTALL_DIR%" (
    echo [+] Creating directory: %INSTALL_DIR%
    mkdir "%INSTALL_DIR%"
)

echo [+] Stopping existing instances and services...
schtasks /end /tn "EasyRemoteDesktopAgent" >nul 2>&1
taskkill /F /IM RemoteDesktopService.exe >nul 2>&1
taskkill /F /IM RemoteDesktopP2P.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [+] Copying installation files to %INSTALL_DIR%...
xcopy /E /I /Y /H "%~dp0*" "%INSTALL_DIR%\"

echo [+] Configuring Windows Firewall exceptions...
netsh advfirewall firewall delete rule name="EasyRemoteDesktopAgent" >nul 2>&1
netsh advfirewall firewall delete rule name="EasyRemoteDesktopService" >nul 2>&1
netsh advfirewall firewall add rule name="EasyRemoteDesktopAgent" dir=in action=allow program="%INSTALL_DIR%\RemoteDesktopP2P.exe" enable=yes profile=any >nul 2>&1
netsh advfirewall firewall add rule name="EasyRemoteDesktopService" dir=in action=allow program="%INSTALL_DIR%\RemoteDesktopService.exe" enable=yes profile=any >nul 2>&1

echo [+] Registering background system service (Scheduled Task)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$Action = New-ScheduledTaskAction -Execute '%INSTALL_DIR%\RemoteDesktopService.exe';" ^
    "$Trigger = New-ScheduledTaskTrigger -AtStartup;" ^
    "$Principal = New-ScheduledTaskPrincipal -UserId 'NT AUTHORITY\SYSTEM' -LogonType ServiceAccount -RunLevel Highest;" ^
    "$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -Compatibility Win8;" ^
    "Register-ScheduledTask -TaskName 'EasyRemoteDesktopAgent' -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Force;"

echo [+] Starting background service...
schtasks /run /tn "EasyRemoteDesktopAgent"

echo [+] Launching Remote Desktop GUI Agent...
explorer.exe "%INSTALL_DIR%\RemoteDesktopP2P.exe"

echo.
echo ========================================================
echo  INSTALLATION COMPLETED SUCCESSFULLY!
echo ========================================================
echo.
timeout /t 5
exit /b
