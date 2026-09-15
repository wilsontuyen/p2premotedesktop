[Setup]
AppId={{8F3A2C1D-9B47-4E6A-A1D0-7C5E2B9F4A10}
AppName=Easy Remote Desktop Host
AppVersion=AI Pro Version
AppPublisher=P2P Remote Desktop
AppCopyright=Copyright (C) 2026 P2P Remote Desktop
VersionInfoVersion=2026
VersionInfoTextVersion=AI Pro Version
VersionInfoCompany=P2P Remote Desktop
VersionInfoDescription=Easy Remote Desktop Host Installer
VersionInfoProductName=Easy Remote Desktop Host
VersionInfoCopyright=Copyright (C) 2026 P2P Remote Desktop
DefaultDirName={pf32}\Easy Remote Desktop Host
DisableDirPage=no
DisableWelcomePage=yes
DisableReadyPage=yes
UsePreviousAppDir=no
DirExistsWarning=yes
DefaultGroupName=Easy Remote Desktop Host
PrivilegesRequired=admin
OutputDir=.
OutputBaseFilename=EasyRemoteDesktopHost_Installer
Compression=lzma2/ultra
SolidCompression=yes
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\RemoteDesktopHost.exe
DisableProgramGroupPage=yes
ShowLanguageDialog=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "disclaimer_en.txt"
Name: "vietnamese"; MessagesFile: "Vietnamese.isl"; LicenseFile: "disclaimer_vi.txt"
[CustomMessages]
english.RunProgram=Start Easy Remote Desktop Host
vietnamese.RunProgram=Chạy Easy Remote Desktop Host

[Dirs]
Name: "{app}"; Permissions: users-modify

[Files]
Source: "dist_nuitka_host\app.dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "disclaimer_vi.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "disclaimer_en.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Easy Remote Desktop Host"; Filename: "{app}\RemoteDesktopHost.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall Easy Remote Desktop Host"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Easy Remote Desktop Host"; Filename: "{app}\RemoteDesktopHost.exe"; WorkingDir: "{app}"

[Run]
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopHostAgent"""; Flags: runhidden
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopHostService"""; Flags: runhidden
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""EasyRemoteDesktopHostAgent"" dir=in action=allow program=""{app}\RemoteDesktopHost.exe"" enable=yes profile=any"; Flags: runhidden
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""EasyRemoteDesktopHostService"" dir=in action=allow program=""{app}\RemoteDesktopHostService.exe"" enable=yes profile=any"; Flags: runhidden
Filename: "cmd.exe"; Parameters: "/c schtasks.exe /create /tn ""EasyRemoteDesktopHostAgent"" /tr ""\""{app}\RemoteDesktopHostService.exe\"""" /sc onstart /ru ""NT AUTHORITY\SYSTEM"" /rl highest /f > ""{app}\task_creation.log"" 2>&1"; Flags: runhidden
Filename: "cmd.exe"; Parameters: "/c schtasks.exe /run /tn ""EasyRemoteDesktopHostAgent"" > ""{app}\task_run.log"" 2>&1"; Flags: runhidden
Filename: "powershell.exe"; Parameters: "-Command ""Start-Sleep -Seconds 5"""; Flags: runhidden
Filename: "{app}\RemoteDesktopHost.exe"; WorkingDir: "{app}"; Description: "{cm:RunProgram}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "schtasks.exe"; Parameters: "/end /tn ""EasyRemoteDesktopHostAgent"""; Flags: runhidden waituntilterminated
Filename: "schtasks.exe"; Parameters: "/delete /tn ""EasyRemoteDesktopHostAgent"" /f"; Flags: runhidden waituntilterminated
Filename: "taskkill.exe"; Parameters: "/F /IM RemoteDesktopHostService.exe"; Flags: runhidden waituntilterminated
Filename: "taskkill.exe"; Parameters: "/F /IM RemoteDesktopHost.exe"; Flags: runhidden waituntilterminated
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopHostAgent"""; Flags: runhidden waituntilterminated
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""EasyRemoteDesktopHostService"""; Flags: runhidden waituntilterminated

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    Exec('schtasks.exe', '/end /tn "EasyRemoteDesktopHostAgent"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('taskkill.exe', '/F /IM RemoteDesktopHostService.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('taskkill.exe', '/F /IM RemoteDesktopHost.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
