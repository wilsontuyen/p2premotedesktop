[Setup]
AppName=Test
AppVersion=1
DefaultDirName={autopf}\Test
DirExistsWarning=no
OutputDir=.

[Code]
function NextButtonClick(CurPageID: Integer): Boolean;
var
  Dir: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    Dir := ExpandConstant('{app}');
    if DirExists(Dir) then
    begin
      if TaskDialogMsgBox(SetupMessage(msgDirExistsTitle), FmtMessage(SetupMessage(msgDirExists), [Dir]), mbConfirmation, MB_YESNO, [SetupMessage(msgButtonYes), SetupMessage(msgButtonNo)], 0) = IDNO then
        Result := False;
    end;
  end;
end;
