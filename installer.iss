[Setup]
AppName=Easy Remote Desktop
AppVersion=AI Pro Version
AppPublisher=P2P Remote Desktop
AppCopyright=Copyright (C) 2026 P2P Remote Desktop
VersionInfoVersion=1.0.0.0
VersionInfoTextVersion=1.0.0.0
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
Compression=lzma2/ultra
SolidCompression=yes
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
Name: "{app}\Logs"; Permissions: users-modify

[Files]
Source: "dist_nuitka\app.dist\*"; DestDir: "{app}"; Excludes: "saved_computers.xml,lan_peers.json,config.json,app.ini,window_config.json,custom_ip_range.json,session_pass.txt,*.log"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "disclaimer_vi.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "disclaimer_en.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Easy Remote Desktop"; Filename: "{app}\RemoteDesktopP2P.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall Easy Remote Desktop"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Easy Remote Desktop"; Filename: "{app}\RemoteDesktopP2P.exe"; WorkingDir: "{app}"

[Run]
; Remove old firewall rules if they exist
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopAgent"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopService"""; Flags: runhidden

; Add new firewall rules
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""EasyRemoteDesktopAgent"" dir=in action=allow program=""{app}\RemoteDesktopP2P.exe"" enable=yes profile=any"; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""EasyRemoteDesktopService"" dir=in action=allow program=""{app}\RemoteDesktopService.exe"" enable=yes profile=any"; Flags: runhidden

; Register background system service (Scheduled Task)
Filename: "{sys}\schtasks.exe"; Parameters: "/create /tn ""EasyRemoteDesktopAgent"" /tr """"{app}\RemoteDesktopService.exe"""" /sc onstart /ru ""NT AUTHORITY\SYSTEM"" /rl highest /f"; Flags: runhidden

; Start background service
Filename: "{sys}\schtasks.exe"; Parameters: "/run /tn ""EasyRemoteDesktopAgent"""; Flags: runhidden

Filename: "{app}\RemoteDesktopP2P.exe"; WorkingDir: "{app}"; Description: "{cm:RunProgram}"; Flags: nowait postinstall skipifsilent runasoriginaluser


[UninstallRun]
; Stop existing scheduled task
Filename: "{sys}\schtasks.exe"; Parameters: "/end /tn ""EasyRemoteDesktopAgent"""; Flags: runhidden waituntilterminated
; Delete scheduled task
Filename: "{sys}\schtasks.exe"; Parameters: "/delete /tn ""EasyRemoteDesktopAgent"" /f"; Flags: runhidden waituntilterminated

; Kill running processes
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM RemoteDesktopService.exe"; Flags: runhidden waituntilterminated
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM RemoteDesktopP2P.exe"; Flags: runhidden waituntilterminated

; Remove Firewall exceptions
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopAgent"""; Flags: runhidden waituntilterminated
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopService"""; Flags: runhidden waituntilterminated

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    // Before copying files, ensure no processes are running to avoid file lock issues
    Exec(ExpandConstant('{sys}\schtasks.exe'), '/end /tn "EasyRemoteDesktopAgent"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM RemoteDesktopService.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM RemoteDesktopP2P.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
