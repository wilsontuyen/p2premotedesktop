[Setup]
AppId={{8F3A2C1D-9B47-4E6A-A1D0-7C5E2B9F4A10}
AppName=Easy Remote Desktop Host
AppVersion=AI Pro Version
AppPublisher=P2P Remote Desktop
AppCopyright=Copyright (C) 2026 P2P Remote Desktop
VersionInfoVersion=1.0.0.0
VersionInfoTextVersion=1.0.0.0
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
CloseApplications=force
RestartApplications=no
OutputDir=.
OutputBaseFilename=EasyRemoteDesktopHost_Installer
Compression=lzma2/ultra
SolidCompression=yes
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\RemoteDesktopHost.exe
DisableProgramGroupPage=yes
ShowLanguageDialog=yes
#ifdef SIGN_INSTALLER
SignTool=mysign
SignToolRetryCount=4
SignToolRetryDelay=1500
SignedUninstaller=yes
#endif

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "disclaimer_en.txt"
Name: "vietnamese"; MessagesFile: "Vietnamese.isl"; LicenseFile: "disclaimer_vi.txt"
[CustomMessages]
english.RunProgram=Start Easy Remote Desktop Host
vietnamese.RunProgram=Chạy Easy Remote Desktop Host
english.InstallingKB=Installing Windows 7 Security Update (KB3063858)...
vietnamese.InstallingKB=Đang cài đặt bản cập nhật bảo mật Windows 7 (KB3063858)...
english.InstallingVCRedist=Installing Microsoft Visual C++ Runtime...
vietnamese.InstallingVCRedist=Đang cài đặt Microsoft Visual C++ Runtime...
english.FinishedRestartCustom=Setup has finished installing Easy Remote Desktop Host. To ensure all background services, network drivers, and system components work properly, a computer restart is recommended.%n%nWould you like to restart your computer now?
vietnamese.FinishedRestartCustom=Đã hoàn tất cài đặt Easy Remote Desktop Host. Để đảm bảo dịch vụ chạy ngầm, driver mạng và các thành phần hệ thống hoạt động ổn định nhất, khuyến nghị bạn nên khởi động lại máy tính.%n%nBạn có muốn khởi động lại ngay bây giờ không?
english.RestartLaterWarning=Notice: You chose to restart later. Please restart your computer before use to ensure all background services run stably.
vietnamese.RestartLaterWarning=Lưu ý: Bạn đã chọn khởi động lại sau. Vui lòng khởi động lại máy tính trước khi sử dụng để các dịch vụ chạy ngầm và tính năng điều khiển từ xa hoạt động ổn định nhất.

[Messages]
FinishedRestartLabel={cm:FinishedRestartCustom}
FinishedRestartMessage={cm:FinishedRestartCustom}

[Dirs]
Name: "{app}"; Permissions: users-modify
Name: "{app}\Data"; Permissions: users-modify
Name: "{app}\Logs"; Permissions: users-modify

[Files]
; Windows 7 & Visual C++ Prerequisite redistributables (only extracted when needed)
Source: "redist\Windows6.1-KB3063858-x86.msu"; DestDir: "{tmp}"; Check: IsWin7_32_NeedKB; Flags: deleteafterinstall
Source: "redist\Windows6.1-KB3063858-x64.msu"; DestDir: "{tmp}"; Check: IsWin7_64_NeedKB; Flags: deleteafterinstall
Source: "redist\vc_redist.x86.exe"; DestDir: "{tmp}"; Check: NeedsVCRedist; Flags: deleteafterinstall
Source: "dist_nuitka_host\app.dist\*"; DestDir: "{app}"; Excludes: "Data\*,saved_computers.xml,lan_peers.json,config.json,app.ini,window_config.json,custom_ip_range.json,session_pass.txt,host_hwid.txt,fm_config.json,install.bat,uninstall.bat,*.log"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "disclaimer_vi.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "disclaimer_en.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Easy Remote Desktop Host"; Filename: "{app}\RemoteDesktopHost.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall Easy Remote Desktop Host"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Easy Remote Desktop Host"; Filename: "{app}\RemoteDesktopHost.exe"; WorkingDir: "{app}"

[Run]
Filename: "{sys}\wusa.exe"; Parameters: """{tmp}\Windows6.1-KB3063858-x86.msu"" /quiet /norestart"; Check: IsWin7_32_NeedKB; AfterInstall: MarkKBPatchInstalled; StatusMsg: "{cm:InstallingKB}"; Flags: runhidden waituntilterminated
Filename: "{sys}\wusa.exe"; Parameters: """{tmp}\Windows6.1-KB3063858-x64.msu"" /quiet /norestart"; Check: IsWin7_64_NeedKB; AfterInstall: MarkKBPatchInstalled; StatusMsg: "{cm:InstallingKB}"; Flags: runhidden waituntilterminated
Filename: "{tmp}\vc_redist.x86.exe"; Parameters: "/install /quiet /norestart"; Check: NeedsVCRedist; AfterInstall: MarkVCRedistInstalled; StatusMsg: "{cm:InstallingVCRedist}"; Flags: waituntilterminated
Filename: "{app}\RemoteDesktopHostService.exe"; Parameters: "--install-service"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; Check: CanRunAppNow
Filename: "{app}\RemoteDesktopHost.exe"; WorkingDir: "{app}"; Description: "{cm:RunProgram}"; Flags: nowait postinstall skipifsilent runasoriginaluser; Check: CanRunAppNow

[UninstallRun]
Filename: "{app}\RemoteDesktopHostService.exe"; Parameters: "--uninstall-service"; WorkingDir: "{app}"; RunOnceId: "UninstallERDHostService"; Flags: runhidden waituntilterminated

[Code]
var
  GRedistInstalled: Boolean;

function GetModuleHandleW(lpModuleName: String): THandle;
  external 'GetModuleHandleW@kernel32.dll stdcall';
function GetProcAddress(hModule: THandle; lpProcName: AnsiString): LongWord;
  external 'GetProcAddress@kernel32.dll stdcall';

function IsWindows7: Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  // Windows 7 and Windows Server 2008 R2 are NT 6.1
  Result := (Version.Major = 6) and (Version.Minor = 1);
end;

function NeedsKernel32Patch: Boolean;
var
  hKernel: THandle;
begin
  Result := False;
  if IsWindows7 then
  begin
    hKernel := GetModuleHandleW('kernel32.dll');
    if hKernel <> 0 then
    begin
      // KB2533623 / KB3063858 adds SetDefaultDllDirectories to kernel32.dll
      if GetProcAddress(hKernel, 'SetDefaultDllDirectories') = 0 then
        Result := True;
    end;
  end;
end;

function IsWin7_32_NeedKB: Boolean;
begin
  Result := NeedsKernel32Patch and (not IsWin64);
end;

function IsWin7_64_NeedKB: Boolean;
begin
  Result := NeedsKernel32Patch and IsWin64;
end;

function NeedsVCRedist: Boolean;
var
  Installed: Cardinal;
  BVersion: String;
begin
  Result := True;
  // 1. Check standard 32-bit registry view
  if RegQueryDWordValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X86', 'Installed', Installed) then
  begin
    if Installed = 1 then
    begin
      if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X86', 'Version', BVersion) then
      begin
        if CompareStr(BVersion, 'v14.20') >= 0 then
          Result := False;
      end
      else
        Result := False;
    end;
  end;
  // 2. Check 64-bit WOW6432Node fallback if on 64-bit Windows
  if Result and IsWin64 then
  begin
    if RegQueryDWordValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X86', 'Installed', Installed) then
    begin
      if Installed = 1 then
      begin
        if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X86', 'Version', BVersion) then
        begin
          if CompareStr(BVersion, 'v14.20') >= 0 then
            Result := False;
        end
        else
          Result := False;
      end;
    end;
  end;
end;

procedure MarkKBPatchInstalled();
begin
  GRedistInstalled := True;
end;

procedure MarkVCRedistInstalled();
begin
  GRedistInstalled := True;
end;

function CanRunAppNow: Boolean;
begin
  // Only suppress immediate start if system updates or VC++ runtime were just installed
  Result := not GRedistInstalled;
end;

function NeedRestart(): Boolean;
begin
  // Chỉ yêu cầu khởi động lại máy tính khi có cài các gói update hệ thống (KB3063858) hoặc VC++ Redistributable
  Result := GRedistInstalled;
end;

type
  TServiceStatus = record
    dwServiceType: DWORD;
    dwCurrentState: DWORD;
    dwControlsAccepted: DWORD;
    dwWin32ExitCode: DWORD;
    dwServiceSpecificExitCode: DWORD;
    dwCheckPoint: DWORD;
    dwWaitHint: DWORD;
  end;

  TLuid = record
    LowPart: DWORD;
    HighPart: Longint;
  end;

  TTokenPrivileges = record
    PrivilegeCount: DWORD;
    Luid: TLuid;
    Attributes: DWORD;
  end;

  TPidArray = array[0..8191] of DWORD;

const
  SC_MANAGER_CONNECT = $0001;
  SERVICE_STOP = $0020;
  SERVICE_QUERY_STATUS = $0004;
  SERVICE_CONTROL_STOP = $00000001;
  SERVICE_STOPPED = $00000001;

  TOKEN_ADJUST_PRIVILEGES = $0020;
  TOKEN_QUERY = $0008;
  SE_PRIVILEGE_ENABLED = $00000002;

  PROCESS_TERMINATE = $0001;
  PROCESS_QUERY_LIMITED_INFORMATION = $1000;
  SYNCHRONIZE = $00100000;

function OpenSCManagerW(lpMachineName, lpDatabaseName: String; dwDesiredAccess: DWORD): THandle;
  external 'OpenSCManagerW@advapi32.dll stdcall';
function OpenServiceW(hSCManager: THandle; lpServiceName: String; dwDesiredAccess: DWORD): THandle;
  external 'OpenServiceW@advapi32.dll stdcall';
function ControlService(hService: THandle; dwControl: DWORD; var lpServiceStatus: TServiceStatus): Boolean;
  external 'ControlService@advapi32.dll stdcall';
function QueryServiceStatus(hService: THandle; var lpServiceStatus: TServiceStatus): Boolean;
  external 'QueryServiceStatus@advapi32.dll stdcall';
function CloseServiceHandle(hSCObject: THandle): Boolean;
  external 'CloseServiceHandle@advapi32.dll stdcall';

function GetCurrentProcess(): THandle;
  external 'GetCurrentProcess@kernel32.dll stdcall';
function GetCurrentProcessId(): DWORD;
  external 'GetCurrentProcessId@kernel32.dll stdcall';
function OpenProcessToken(ProcessHandle: THandle; DesiredAccess: DWORD; var TokenHandle: THandle): Boolean;
  external 'OpenProcessToken@advapi32.dll stdcall';
function LookupPrivilegeValueW(lpSystemName, lpName: String; var lpLuid: TLuid): Boolean;
  external 'LookupPrivilegeValueW@advapi32.dll stdcall';
function AdjustTokenPrivileges(TokenHandle: THandle; DisableAllPrivileges: Boolean; var NewState: TTokenPrivileges; BufferLength: DWORD; PreviousState, ReturnLength: Cardinal): Boolean;
  external 'AdjustTokenPrivileges@advapi32.dll stdcall';

function K32EnumProcesses(var pProcessIds: TPidArray; cb: DWORD; var pBytesReturned: DWORD): Boolean;
  external 'K32EnumProcesses@kernel32.dll stdcall';
function OpenProcess(dwDesiredAccess: DWORD; bInheritHandle: Boolean; dwProcessId: DWORD): THandle;
  external 'OpenProcess@kernel32.dll stdcall';
function QueryFullProcessImageNameW(hProcess: THandle; dwFlags: DWORD; lpExeName: String; var lpdwSize: DWORD): Boolean;
  external 'QueryFullProcessImageNameW@kernel32.dll stdcall';
function TerminateProcess(hProcess: THandle; uExitCode: UINT): Boolean;
  external 'TerminateProcess@kernel32.dll stdcall';
function WaitForSingleObject(hHandle: THandle; dwMilliseconds: DWORD): DWORD;
  external 'WaitForSingleObject@kernel32.dll stdcall';
function CloseHandle(hObject: THandle): Boolean;
  external 'CloseHandle@kernel32.dll stdcall';

procedure EnableDebugPrivilege();
var
  hToken: THandle;
  Luid: TLuid;
  TP: TTokenPrivileges;
begin
  hToken := 0;
  if OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES or TOKEN_QUERY, hToken) then
  begin
    try
      if LookupPrivilegeValueW('', 'SeDebugPrivilege', Luid) then
      begin
        TP.PrivilegeCount := 1;
        TP.Luid := Luid;
        TP.Attributes := SE_PRIVILEGE_ENABLED;
        AdjustTokenPrivileges(hToken, False, TP, 16, 0, 0);
      end;
    finally
      CloseHandle(hToken);
    end;
  end;
end;

procedure KillPidAndWait(Pid: DWORD);
var
  hKill: THandle;
begin
  if (Pid = 0) or (Pid = 4) or (Pid = GetCurrentProcessId()) then
    Exit;
  hKill := OpenProcess(PROCESS_TERMINATE or SYNCHRONIZE, False, Pid);
  if hKill <> 0 then
  begin
    try
      TerminateProcess(hKill, 0);
      WaitForSingleObject(hKill, 3000);
    finally
      CloseHandle(hKill);
    end;
  end;
end;

procedure TerminateHostProcesses();
var
  Locator, WbemSvc, ProcSet, Item: Variant;
  Count, I: Integer;
  Pid: DWORD;
  WmiOk: Boolean;
  Pids: TPidArray;
  BytesReturned, NumPids, J, MyPid, BufLen: DWORD;
  hQuery: THandle;
  ExeBuf, ExeName: String;
begin
  EnableDebugPrivilege();
  WmiOk := False;

  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    WbemSvc := Locator.ConnectServer('.', 'root\cimv2');
    ProcSet := WbemSvc.ExecQuery('SELECT ProcessId, Name FROM Win32_Process WHERE Name="RemoteDesktopHostService.exe" OR Name="RemoteDesktopHost.exe"');
    Count := ProcSet.Count;
    for I := 0 to Count - 1 do
    begin
      Item := ProcSet.ItemIndex(I);
      Pid := Item.Properties_.Item('ProcessId').Value;
      KillPidAndWait(Pid);
      try
        Item.Terminate();
      except
      end;
    end;
    WmiOk := True;
  except
  end;

  if not WmiOk then
  begin
    MyPid := GetCurrentProcessId();
    BytesReturned := 0;
    if K32EnumProcesses(Pids, 32768, BytesReturned) then
    begin
      NumPids := BytesReturned div 4;
      if NumPids > 8192 then
        NumPids := 8192;
      for J := 0 to NumPids - 1 do
      begin
        if (Pids[J] = 0) or (Pids[J] = 4) or (Pids[J] = MyPid) then
          Continue;
        hQuery := OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, Pids[J]);
        if hQuery <> 0 then
        begin
          ExeName := '';
          try
            BufLen := 1024;
            SetLength(ExeBuf, BufLen);
            if QueryFullProcessImageNameW(hQuery, 0, ExeBuf, BufLen) and (BufLen > 0) then
              ExeName := Lowercase(ExtractFileName(Copy(ExeBuf, 1, BufLen)));
          finally
            CloseHandle(hQuery);
          end;
          if (ExeName = 'remotedesktophostservice.exe') or (ExeName = 'remotedesktophost.exe') then
            KillPidAndWait(Pids[J]);
        end;
      end;
    end;
  end;
end;

procedure StopExistingHostServiceAndProcesses();
var
  hSCM, hSvc: THandle;
  Status: TServiceStatus;
  I: Integer;
  Sched, Folder, Task: Variant;
begin
  hSCM := OpenSCManagerW('', 'ServicesActive', SC_MANAGER_CONNECT);
  if hSCM <> 0 then
  begin
    try
      hSvc := OpenServiceW(hSCM, 'EasyRemoteDesktopHostService', SERVICE_STOP or SERVICE_QUERY_STATUS);
      if hSvc <> 0 then
      begin
        try
          ControlService(hSvc, SERVICE_CONTROL_STOP, Status);
          for I := 1 to 25 do
          begin
            if QueryServiceStatus(hSvc, Status) and (Status.dwCurrentState = SERVICE_STOPPED) then
              Break;
            Sleep(200);
          end;
        finally
          CloseServiceHandle(hSvc);
        end;
      end;
    finally
      CloseServiceHandle(hSCM);
    end;
  end;

  try
    Sched := CreateOleObject('Schedule.Service');
    Sched.Connect();
    Folder := Sched.GetFolder('\');
    Task := Folder.GetTask('EasyRemoteDesktopHostAgent');
    try
      Task.Stop(0);
    except
    end;
    try
      Folder.DeleteTask('EasyRemoteDesktopHostAgent', 0);
    except
    end;
    Sleep(300);
  except
  end;

  TerminateHostProcesses();
  Sleep(400);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopExistingHostServiceAndProcesses();
  // Nhận diện trước nếu máy cần cài đặt gói update Windows (KB) hoặc Visual C++ runtime
  if IsWin7_32_NeedKB or IsWin7_64_NeedKB or NeedsVCRedist then
    GRedistInstalled := True
  else
    GRedistInstalled := False;
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    StopExistingHostServiceAndProcesses();
  if CurStep = ssPostInstall then
  begin
    if GRedistInstalled then
    begin
      RegWriteStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce', 'InstallERDHostService', ExpandConstant('"{app}\RemoteDesktopHostService.exe" --install-service'));
    end;
  end;
  if CurStep = ssDone then
  begin
    if GRedistInstalled then
    begin
      try
        if (WizardForm.YesRadio <> nil) and (not WizardForm.YesRadio.Checked) then
        begin
          // Người dùng chọn khởi động lại sau -> Hiện hộp thoại nhắc nhở
          MsgBox(CustomMessage('RestartLaterWarning'), mbInformation, MB_OK);
        end;
      except
      end;
    end;
  end;
end;
