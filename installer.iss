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
CloseApplications=force
RestartApplications=no
OutputDir=.
OutputBaseFilename=EasyRemoteDesktop_Installer
Compression=lzma2/ultra
SolidCompression=yes
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\RemoteDesktopP2P.exe
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
english.RunProgram=Start Easy Remote Desktop
vietnamese.RunProgram=Chạy Easy Remote Desktop

[Dirs]
Name: "{app}"; Permissions: users-modify
Name: "{app}\Data"; Permissions: users-modify
Name: "{app}\Logs"; Permissions: users-modify

[Files]
Source: "dist_nuitka\app.dist\*"; DestDir: "{app}"; Excludes: "Data\*,saved_computers.xml,lan_peers.json,config.json,app.ini,window_config.json,custom_ip_range.json,session_pass.txt,host_hwid.txt,fm_config.json,install.bat,uninstall.bat,*.log"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "disclaimer_vi.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "disclaimer_en.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Easy Remote Desktop"; Filename: "{app}\RemoteDesktopP2P.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall Easy Remote Desktop"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Easy Remote Desktop"; Filename: "{app}\RemoteDesktopP2P.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\RemoteDesktopService.exe"; Parameters: "--install-service"; WorkingDir: "{app}"; Flags: runhidden waituntilterminated
Filename: "{app}\RemoteDesktopP2P.exe"; WorkingDir: "{app}"; Description: "{cm:RunProgram}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{app}\RemoteDesktopService.exe"; Parameters: "--uninstall-service"; WorkingDir: "{app}"; RunOnceId: "UninstallERDService"; Flags: runhidden waituntilterminated

[Code]
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

procedure TerminateAppProcesses();
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

  // Primary path: WMI COM query targeting ONLY our exact process names (never touches system/AV processes)
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    WbemSvc := Locator.ConnectServer('.', 'root\cimv2');
    ProcSet := WbemSvc.ExecQuery('SELECT ProcessId, Name FROM Win32_Process WHERE Name="RemoteDesktopService.exe" OR Name="RemoteDesktopP2P.exe"');
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

  // Fallback path if WMI service is disabled: query-only open first, terminate ONLY matching app binaries
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
          if (ExeName = 'remotedesktopservice.exe') or (ExeName = 'remotedesktopp2p.exe') then
            KillPidAndWait(Pids[J]);
        end;
      end;
    end;
  end;
end;

procedure StopExistingServiceAndProcesses();
var
  hSCM, hSvc: THandle;
  Status: TServiceStatus;
  I: Integer;
  Sched, Folder, Task: Variant;
begin
  // 1. Stop native Windows Service via Win32 SCM API
  hSCM := OpenSCManagerW('', 'ServicesActive', SC_MANAGER_CONNECT);
  if hSCM <> 0 then
  begin
    try
      hSvc := OpenServiceW(hSCM, 'EasyRemoteDesktopService', SERVICE_STOP or SERVICE_QUERY_STATUS);
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

  // 2. Stop & delete legacy Scheduled Task if upgrading from an older version (via COM)
  try
    Sched := CreateOleObject('Schedule.Service');
    Sched.Connect();
    Folder := Sched.GetFolder('\');
    Task := Folder.GetTask('EasyRemoteDesktopAgent');
    try
      Task.Stop(0);
    except
    end;
    try
      Folder.DeleteTask('EasyRemoteDesktopAgent', 0);
    except
    end;
    Sleep(300);
  except
  end;

  // 3. Terminate any lingering SYSTEM/User worker, broker, or GUI processes locking DLLs
  TerminateAppProcesses();
  Sleep(400);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopExistingServiceAndProcesses();
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    StopExistingServiceAndProcesses();
end;
