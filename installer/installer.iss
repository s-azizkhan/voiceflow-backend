; VoiceFlow Installer — Inno Setup Script
; Requires Inno Setup 6+ (https://jrsoftware.org/isdl.php)
;
; Compile with:
;   iscc installer.iss
;
; Or open in Inno Setup Compiler GUI.

#define MyAppName "VoiceFlow"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "VoiceFlow"
#define MyAppExeName "voiceflow-server.exe"
#define MyAppManagerExeName "manager\voiceflow-manager.exe"

[Setup]
AppId={{8A3E4B2C-1F5D-4E6A-9C8B-3D2F1E4A5B7C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=VoiceFlow-{#MyAppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#MyAppManagerExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Start VoiceFlow when Windows starts"; GroupDescription: "Startup:"

[Files]
; Server: voiceflow-server.exe at root, _internal alongside
Source: "voiceflow-server.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
; Manager: in manager/ subfolder with its own _internal
Source: "manager\voiceflow-manager.exe"; DestDir: "{app}\manager"; Flags: ignoreversion
Source: "manager\_internal\*"; DestDir: "{app}\manager\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VoiceFlow"; Filename: "{app}\{#MyAppManagerExeName}"
Name: "{group}\VoiceFlow Dashboard"; Filename: "http://localhost:8765/__dashboard__"
Name: "{group}\Uninstall VoiceFlow"; Filename: "{uninstallexe}"
Name: "{autodesktop}\VoiceFlow"; Filename: "{app}\{#MyAppManagerExeName}"; Tasks: desktopicon

[Registry]
; Auto-start (HKCU so no admin required)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "VoiceFlow"; \
  ValueData: """{app}\{#MyAppManagerExeName}"""; Flags: uninsdeletevalue; \
  Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppManagerExeName}"; Description: "Launch VoiceFlow Manager"; Flags: nowait postinstall skipifsilent

[Code]
function IsPortInUse(Port: Integer): Boolean;
var
  TCPClient: Variant;
begin
  Result := False;
  try
    TCPClient := CreateOleObject('MSWinsock.Winsock');
    TCPClient.Protocol := 1;
    TCPClient.RemoteHost := '127.0.0.1';
    TCPClient.RemotePort := Port;
    TCPClient.Connect;
    Result := True;
    TCPClient.Close;
  except
    Result := False;
  end;
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if IsPortInUse(8765) then
    if MsgBox('VoiceFlow server may already be running on port 8765.' + #13#10 +
              'Installation will continue, but you may need to stop the running instance first.' + #13#10 +
              'Continue?', mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
end;
