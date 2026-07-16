@echo off
echo === FIX UAC + DEPLOY ===

REM 1. Fix registry immediately
echo [1/5] Setting PromptOnSecureDesktop = 0...
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v PromptOnSecureDesktop /t REG_DWORD /d 0 /f
if errorlevel 1 (
    echo FAILED! Please right-click this file and "Run as administrator"
    pause
    exit /b 1
)

REM 2. Stop everything
echo [2/5] Stopping service and agents...
schtasks /end /tn "EasyRemoteDesktopAgent" 2>nul
taskkill /F /IM RemoteDesktopService.exe 2>nul
taskkill /F /IM RemoteDesktopP2P.exe 2>nul
timeout /t 3 /nobreak >nul

REM 3. Deploy new build
echo [3/5] Deploying new build...
xcopy /E /Y /Q "d:\Data\AG\remote_desktop\dist_nuitka\app.dist\*" "C:\Apps\P2P\" >nul 2>&1
if errorlevel 1 (
    echo Retry deploy...
    timeout /t 2 /nobreak >nul
    taskkill /F /IM RemoteDesktopService.exe 2>nul
    taskkill /F /IM RemoteDesktopP2P.exe 2>nul
    timeout /t 2 /nobreak >nul
    xcopy /E /Y /Q "d:\Data\AG\remote_desktop\dist_nuitka\app.dist\*" "C:\Apps\P2P\"
)

REM 4. Restart service
echo [4/5] Restarting service...
schtasks /change /tn "EasyRemoteDesktopAgent" /enable 2>nul
schtasks /run /tn "EasyRemoteDesktopAgent" 2>nul
timeout /t 5 /nobreak >nul

REM 5. Launch GUI app
echo [5/5] Launching app...
start "" "C:\Apps\P2P\RemoteDesktopP2P.exe"

echo.
echo === DONE! Registry PromptOnSecureDesktop = 0 ===
echo UAC dialogs will now appear on normal desktop (no secure desktop freeze).
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" /v PromptOnSecureDesktop
echo.
pause
