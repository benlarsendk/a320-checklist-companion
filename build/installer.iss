; Inno Setup Script for A320 Checklist Companion
; Download Inno Setup from: https://jrsoftware.org/isinfo.php

#define MyAppName "A320 Checklist Companion"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MSFS Community"
#define MyAppURL "https://github.com/benlarsendk/a320-checklist-companion"
#define MyAppExeName "A320 Checklist Companion.exe"

[Setup]
AppId={{A320-CHECKLIST-COMPANION-2549}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Output directory and filename
OutputDir=installer_output
OutputBaseFilename=A320_Checklist_Companion_Setup
; Compression
Compression=lzma
SolidCompression=yes
; Windows version requirements
MinVersion=10.0
; Require admin for Program Files installation
PrivilegesRequired=admin
; UI settings
WizardStyle=modern
SetupIconFile=
; Uninstall settings
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start automatically with Windows"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; Main application files from PyInstaller output
Source: "dist\A320 Checklist Companion\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Auto-start with Windows if selected
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Check if MSFS is installed (optional, just shows a warning)
function InitializeSetup(): Boolean;
begin
  Result := True;
  // Could add MSFS detection here if needed
end;
