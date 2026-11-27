; Cấu hình Inno Setup 5.6.1 Unicode dành riêng cho Windows XP SP2/SP3 trở lên (32-bit x86)
; Lưu ý: Biên dịch file này bằng Inno Setup 5.6.1 (phiên bản cuối cùng hỗ trợ chính thức Windows XP).
; TUYỆT ĐỐI không gọi powershell.exe hay cmd.exe /c để tránh cảnh báo Antivirus Heuristic.

[Setup]
AppName=Easy Remote Desktop XP Host
AppVersion=1.0.0
AppPublisher=P2P Remote Desktop
AppCopyright=Copyright (C) 2026 P2P Remote Desktop
VersionInfoVersion=1.0.0.0
VersionInfoCompany=P2P Remote Desktop
VersionInfoDescription=Easy Remote Desktop Host for Windows XP
VersionInfoProductName=Easy Remote Desktop XP Host
DefaultDirName={pf}\Easy Remote Desktop XP
DefaultGroupName=Easy Remote Desktop XP
PrivilegesRequired=admin
MinVersion=0,5.01sp2
OutputDir=..
OutputBaseFilename=EasyRemoteDesktopXPHost_Installer
Compression=lzma/ultra
SolidCompression=yes
SetupIconFile=..\app_icon.ico
UninstallDisplayIcon={app}\RemoteDesktopXPHost.exe
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "..\disclaimer_en.txt"

[Dirs]
Name: "{app}"; Permissions: users-modify
Name: "{app}\Data"; Permissions: users-modify
Name: "{app}\Logs"; Permissions: users-modify

[Files]
Source: "..\dist_xp_host\RemoteDesktopXPHost\*"; DestDir: "{app}"; Excludes: "Data\*,Logs\*,saved_computers.xml,lan_peers.json,config.json,app.ini,window_config.json,custom_ip_range.json,session_pass.txt,host_hwid.txt,xp_prefs.json,*.log"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Easy Remote Desktop XP Host"; Filename: "{app}\RemoteDesktopXPHost.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall Easy Remote Desktop XP Host"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Easy Remote Desktop XP Host"; Filename: "{app}\RemoteDesktopXPHost.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\RemoteDesktopXPHost.exe"; Parameters: "--install-service"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated
Filename: "{app}\RemoteDesktopXPHost.exe"; WorkingDir: "{app}"; Description: "Start Easy Remote Desktop XP Host"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\RemoteDesktopXPHost.exe"; Parameters: "--uninstall-service"; WorkingDir: "{app}"; RunOnceId: "UninstallERDServiceXP"; Flags: runhidden waituntilterminated
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM RemoteDesktopXPHost.exe"; Flags: runhidden waituntilterminated
