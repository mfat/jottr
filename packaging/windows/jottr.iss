; Unsigned Inno Setup installer for the PyInstaller onedir bundle.
; Compiled by packaging/windows/build-installer.ps1
;
; Defines (passed by ISCC):
;   AppVersion    - dotted version, example: 2.6.0
;   VersionLabel  - release label, example: v2.6.0
;   RepoRoot      - absolute repo root (no trailing backslash)

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef VersionLabel
  #define VersionLabel "v0.0.0"
#endif
#ifndef RepoRoot
  #define RepoRoot "..\.."
#endif

[Setup]
AppId={{B9F10B41-373E-5F49-BB58-8139956693A3}
AppName=Jottr
AppVersion={#AppVersion}
AppPublisher=mFat
AppPublisherURL=https://github.com/mfat/jottr
AppSupportURL=https://github.com/mfat/jottr/issues
AppUpdatesURL=https://github.com/mfat/jottr/releases
DefaultDirName={autopf}\Jottr
DefaultGroupName=Jottr
DisableProgramGroupPage=yes
LicenseFile={#RepoRoot}\LICENSE
OutputDir={#RepoRoot}\release-assets-build
OutputBaseFilename=jottr-{#VersionLabel}-windows-x86_64-unsigned
SetupIconFile={#RepoRoot}\src\jottr\jottr_icon.ico
UninstallDisplayIcon={app}\Jottr.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
ChangesAssociations=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#RepoRoot}\dist\Jottr\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#RepoRoot}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Jottr"; Filename: "{app}\Jottr.exe"
Name: "{autodesktop}\Jottr"; Filename: "{app}\Jottr.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Jottr.exe"; Description: "Launch Jottr"; Flags: nowait postinstall skipifsilent
