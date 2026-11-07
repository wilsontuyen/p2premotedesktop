@echo off
setlocal EnableExtensions
title Easy Remote Desktop Installer
cd /d "%~dp0"

:: Check for Administrator privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo ========================================================
    echo  Please right-click install.bat and select:
    echo  "Run as administrator"
    echo ========================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo  Installing Easy Remote Desktop Agent and Service...
echo ========================================================
echo.

set "INSTALL_DIR=C:\Program Files (x86)\Easy Remote Desktop"
set "EXE_APP=%INSTALL_DIR%\RemoteDesktopP2P.exe"
set "EXE_SVC=%INSTALL_DIR%\RemoteDesktopService.exe"

echo [+] Installation directory: "%INSTALL_DIR%"

if exist "%EXE_SVC%" (
    echo [+] Stopping existing service...
    "%EXE_SVC%" --uninstall-service >nul 2>&1
)

if not exist "%INSTALL_DIR%" (
    echo [+] Creating directory: "%INSTALL_DIR%"
    mkdir "%INSTALL_DIR%"
    if errorlevel 1 goto :fail_mkdir
)

echo [+] Copying installation files to "%INSTALL_DIR%"...
xcopy /E /I /Y /H /Q "%~dp0*" "%INSTALL_DIR%\"
if errorlevel 1 goto :fail_copy

if not exist "%EXE_APP%" goto :fail_missing_app
if not exist "%EXE_SVC%" goto :fail_missing_svc

icacls "%INSTALL_DIR%" /grant *S-1-5-32-545:(OI)(CI)M >nul 2>&1

echo [+] Registering and starting Windows Service...
"%EXE_SVC%" --install-service
if errorlevel 1 goto :fail_svc

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

:fail_svc
echo [!] Failed to install Windows Service.
pause
exit /b 1
