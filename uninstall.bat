@echo off
setlocal EnableExtensions
title Easy Remote Desktop Uninstaller
cd /d "%~dp0"

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo ========================================================
    echo  Administrator privileges are required to uninstall.
    echo  Relaunching as Administrator...
    echo ========================================================
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo ========================================================
echo  Uninstalling Easy Remote Desktop...
echo ========================================================
echo.

set "INSTALL_DIR=C:\Program Files (x86)\Easy Remote Desktop"
set "TASK_NAME=EasyRemoteDesktopAgent"

echo [+] Stopping and deleting scheduled task...
schtasks /end /tn "%TASK_NAME%" >nul 2>&1
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

echo [+] Closing running application processes...
taskkill /F /IM RemoteDesktopService.exe >nul 2>&1
taskkill /F /IM RemoteDesktopP2P.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [+] Removing Windows Firewall exceptions...
netsh advfirewall firewall delete rule name="EasyRemoteDesktopAgent" >nul 2>&1
netsh advfirewall firewall delete rule name="EasyRemoteDesktopService" >nul 2>&1

echo [+] Removing shortcuts...
del /f /q "%PUBLIC%\Desktop\Easy Remote Desktop.lnk" >nul 2>&1
rmdir /s /q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\Easy Remote Desktop" >nul 2>&1

echo [+] Removing installation files...
if not exist "%INSTALL_DIR%" goto :done
rmdir /s /q "%INSTALL_DIR%"
if exist "%INSTALL_DIR%" goto :fail_delete

:done
echo.
echo ========================================================
echo  UNINSTALLATION COMPLETED SUCCESSFULLY!
echo ========================================================
echo.
pause
exit /b 0

:fail_delete
echo [!] Some files could not be deleted. Close the app and retry.
echo     "%INSTALL_DIR%"
pause
exit /b 1
