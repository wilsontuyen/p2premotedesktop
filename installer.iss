[Setup]
AppName=Easy Remote Desktop
AppVersion=AI Pro Version
AppPublisher=P2P Remote Desktop
AppCopyright=Copyright (C) 2026 P2P Remote Desktop
VersionInfoVersion=2026
VersionInfoTextVersion=AI Pro Version
VersionInfoCompany=P2P Remote Desktop
VersionInfoDescription=Easy Remote Desktop Installer
VersionInfoProductName=Easy Remote Desktop
VersionInfoCopyright=Copyright (C) 2026 P2P Remote Desktop
DefaultDirName={pf32}\Easy Remote Desktop
DisableDirPage=no
DisableWelcomePage=yes
DisableReadyPage=yes
UsePreviousAppDir=no
DirExistsWarning=yes
DefaultGroupName=Easy Remote Desktop
PrivilegesRequired=admin
OutputDir=.
OutputBaseFilename=EasyRemoteDesktop_Installer
Compression=zip
SolidCompression=no
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\RemoteDesktopP2P.exe
DisableProgramGroupPage=yes
ShowLanguageDialog=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "disclaimer_en.txt"
Name: "vietnamese"; MessagesFile: "Vietnamese.isl"; LicenseFile: "disclaimer_vi.txt"
[CustomMessages]
english.RunProgram=Start Easy Remote Desktop
vietnamese.RunProgram=Chạy Easy Remote Desktop

[Dirs]
Name: "{app}"; Permissions: users-modify

[Files]
Source: "dist_nuitka\app.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "disclaimer_vi.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "disclaimer_en.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Easy Remote Desktop"; Filename: "{app}\RemoteDesktopP2P.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall Easy Remote Desktop"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Easy Remote Desktop"; Filename: "{app}\RemoteDesktopP2P.exe"; WorkingDir: "{app}"

[Run]
; Remove old firewall rules if they exist
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopAgent"""; Flags: runhidden
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopService"""; Flags: runhidden

; Add new firewall rules
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""EasyRemoteDesktopAgent"" dir=in action=allow program=""{app}\RemoteDesktopP2P.exe"" enable=yes profile=any"; Flags: runhidden
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""EasyRemoteDesktopService"" dir=in action=allow program=""{app}\RemoteDesktopService.exe"" enable=yes profile=any"; Flags: runhidden

; Register background system service (Scheduled Task) using schtasks for Windows 7 compatibility
Filename: "cmd.exe"; Parameters: "/c schtasks.exe /create /tn ""EasyRemoteDesktopAgent"" /tr ""\""{app}\RemoteDesktopService.exe\"""" /sc onstart /ru ""NT AUTHORITY\SYSTEM"" /rl highest /f > ""{app}\task_creation.log"" 2>&1"; Flags: runhidden

; Start background service
Filename: "cmd.exe"; Parameters: "/c schtasks.exe /run /tn ""EasyRemoteDesktopAgent"" > ""{app}\task_run.log"" 2>&1"; Flags: runhidden

; Wait 5 seconds for service to initialize and connect to signaling server
Filename: "powershell.exe"; Parameters: "-Command ""Start-Sleep -Seconds 5"""; Flags: runhidden

; Thêm option khởi chạy ứng dụng sau khi cài đặt
Filename: "{app}\RemoteDesktopP2P.exe"; Description: "{cm:RunProgram}"; Flags: nowait postinstall skipifsilent runasoriginaluser


[UninstallRun]
; Stop existing scheduled task
Filename: "schtasks.exe"; Parameters: "/end /tn ""EasyRemoteDesktopAgent"""; Flags: runhidden waituntilterminated
; Delete scheduled task
Filename: "schtasks.exe"; Parameters: "/delete /tn ""EasyRemoteDesktopAgent"" /f"; Flags: runhidden waituntilterminated

; Kill running processes
Filename: "taskkill.exe"; Parameters: "/F /IM RemoteDesktopService.exe"; Flags: runhidden waituntilterminated
Filename: "taskkill.exe"; Parameters: "/F /IM RemoteDesktopP2P.exe"; Flags: runhidden waituntilterminated

; Remove Firewall exceptions
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopAgent"""; Flags: runhidden waituntilterminated
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopService"""; Flags: runhidden waituntilterminated

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    // Before copying files, ensure no processes are running to avoid file lock issues
    Exec('schtasks.exe', '/end /tn "EasyRemoteDesktopAgent"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('taskkill.exe', '/F /IM RemoteDesktopService.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('taskkill.exe', '/F /IM RemoteDesktopP2P.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;


