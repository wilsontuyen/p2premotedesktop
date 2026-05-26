@echo off
title Easy Remote Desktop Uninstaller

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo ========================================================
    echo  Administrator privileges are required to uninstall.
    echo  Relaunching as Administrator...
    echo ========================================================
    powershell -Command "Start-Process -FilePath '%0' -Verb RunAs"
    exit /b
)

echo.
echo ========================================================
echo  Uninstalling Easy Remote Desktop...
echo ========================================================
echo.

set "INSTALL_DIR=C:\Apps\P2P"

echo [+] Stopping and deleting scheduled task...
schtasks /end /tn "EasyRemoteDesktopAgent" >nul 2>&1
schtasks /delete /tn "EasyRemoteDesktopAgent" /f >nul 2>&1

echo [+] Removing Windows Firewall exceptions...
netsh advfirewall firewall delete rule name="EasyRemoteDesktopAgent" >nul 2>&1
netsh advfirewall firewall delete rule name="EasyRemoteDesktopService" >nul 2>&1

echo [+] Closing running application processes...
taskkill /F /IM RemoteDesktopService.exe >nul 2>&1
taskkill /F /IM RemoteDesktopP2P.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo.
echo ========================================================
echo  UNINSTALLATION COMPLETED SUCCESSFULLY!
echo ========================================================
echo.
pause
exit /b
