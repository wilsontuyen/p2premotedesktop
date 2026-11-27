; Cấu hình Inno Setup 5.6.1 Unicode dành riêng cho Windows XP SP2/SP3 trở lên (32-bit x86)
; Lưu ý: Biên dịch bằng Inno Setup 5.6.1 (.xp_toolchain\innosetup5\ISCC.exe).
; TUYỆT ĐỐI không gọi powershell.exe hay cmd.exe /c để tránh cảnh báo Antivirus Heuristic.

[Setup]
AppName=Easy Remote Desktop Host
AppVersion=AI Pro version
AppVerName=Easy Remote Desktop Host AI Pro version
AppPublisher=P2P Remote Desktop
AppCopyright=Copyright (C) 2026 P2P Remote Desktop
VersionInfoVersion=1.0.0.0
VersionInfoTextVersion=AI Pro version
VersionInfoCompany=P2P Remote Desktop
VersionInfoDescription=Easy Remote Desktop Host AI Pro version
VersionInfoProductName=Easy Remote Desktop Host AI Pro version
DefaultDirName={pf}\Easy Remote Desktop Host
DisableDirPage=no
UsePreviousAppDir=no
DirExistsWarning=no
DefaultGroupName=Easy Remote Desktop Host
PrivilegesRequired=admin
MinVersion=0,5.01sp2
OutputDir=..
OutputBaseFilename=EasyRemoteDesktopXPHost_Installer
Compression=lzma/max
SolidCompression=yes
SetupIconFile=app_icon_xp.ico
UninstallDisplayIcon={app}\RemoteDesktopXPHost.exe
DisableProgramGroupPage=yes
DisableWelcomePage=yes
DisableReadyPage=yes
ShowLanguageDialog=yes

[Languages]
Name: "vietnamese"; MessagesFile: "Vietnamese_xp.islu"; LicenseFile: "..\disclaimer_vi.txt"
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "..\disclaimer_en.txt"

[CustomMessages]
vietnamese.RunProgram=Chạy Easy Remote Desktop Host AI Pro version
english.RunProgram=Start Easy Remote Desktop Host AI Pro version
vietnamese.DirOverwritePrompt=Thư mục "%1" đã tồn tại.%n%nBạn có muốn cài đặt ghi đè vào thư mục này không?%n- Chọn Yes để xác nhận ghi đè.%n- Chọn No để chọn thư mục cài đặt khác.
english.DirOverwritePrompt=The folder "%1" already exists.%n%nWould you like to overwrite and install into this folder?%n- Click Yes to confirm overwrite.%n- Click No to choose another destination folder.

[Dirs]
Name: "{app}"; Permissions: users-modify
Name: "{app}\Data"; Permissions: users-modify
Name: "{app}\Logs"; Permissions: users-modify

[Files]
Source: "..\dist_xp_host\RemoteDesktopXPHost\*"; DestDir: "{app}"; Excludes: "Data\*,Logs\*,saved_computers.xml,lan_peers.json,config.json,app.ini,window_config.json,custom_ip_range.json,session_pass.txt,host_hwid.txt,xp_prefs.json,*.log"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Easy Remote Desktop Host"; Filename: "{app}\RemoteDesktopXPHost.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall Easy Remote Desktop Host"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Easy Remote Desktop Host"; Filename: "{app}\RemoteDesktopXPHost.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\RemoteDesktopXPHost.exe"; Parameters: "--install-service"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated
Filename: "{app}\RemoteDesktopXPHost.exe"; WorkingDir: "{app}"; Description: "{cm:RunProgram}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{app}\RemoteDesktopXPHost.exe"; Parameters: "--uninstall-service"; WorkingDir: "{app}"; RunOnceId: "UninstallERDServiceXP"; Flags: runhidden waituntilterminated
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM RemoteDesktopXPHost.exe"; Flags: runhidden waituntilterminated

[Code]
procedure StopExistingXPHost();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\net.exe'), 'stop EasyRemoteDesktopXPService', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM RemoteDesktopXPHost.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  TargetDir, NewDir, MsgText: String;
begin
  Result := True;
  if (CurPageID = wpSelectDir) and (not WizardSilent) then
  begin
    TargetDir := WizardDirValue;
    if DirExists(TargetDir) then
    begin
      MsgText := FmtMessage(CustomMessage('DirOverwritePrompt'), [TargetDir]);
      if MsgBox(MsgText, mbConfirmation, MB_YESNO) <> IDYES then
      begin
        Result := False;
        NewDir := TargetDir;
        if BrowseForFolder(SetupMessage(msgBrowseDialogLabel), NewDir, True) then
          WizardForm.DirEdit.Text := NewDir;
        WizardForm.ActiveControl := WizardForm.DirEdit;
      end;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopExistingXPHost();
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    StopExistingXPHost();
end;
