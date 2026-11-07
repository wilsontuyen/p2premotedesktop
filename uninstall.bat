@echo off
setlocal EnableExtensions
title Easy Remote Desktop Uninstaller
cd /d "%~dp0"

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo ========================================================
    echo  Please right-click uninstall.bat and select:
    echo  "Run as administrator"
    echo ========================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  Uninstalling Easy Remote Desktop...
echo ========================================================
echo.

set "INSTALL_DIR=C:\Program Files (x86)\Easy Remote Desktop"
set "EXE_SVC=%INSTALL_DIR%\RemoteDesktopService.exe"

if exist "%EXE_SVC%" (
    echo [+] Stopping and removing Windows Service...
    "%EXE_SVC%" --uninstall-service
)

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
