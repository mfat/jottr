# Build an unsigned Jottr.exe onedir bundle and wrap it in an Inno Setup installer.
# Run from CI or a Windows machine with PyInstaller deps already installed.
#
# Usage:
#   packaging/windows/build-installer.ps1 <version-label> [output-dir]
#
# Example:
#   packaging/windows/build-installer.ps1 v2.3.3 release-assets
#
# Optional env:
#   EXPECTED_FILE_ARCH  — fail if the runner is not this arch (x64)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot

if ($args.Count -lt 1 -or [string]::IsNullOrWhiteSpace($args[0])) {
    throw "version label required (example: v2.3.3)"
}

$VersionLabel = $args[0]
$OutputDir = if ($args.Count -ge 2 -and -not [string]::IsNullOrWhiteSpace($args[1])) {
    $args[1]
} else {
    "release-assets"
}

$Arch = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
if ($Arch -eq "X64") {
    $FileArch = "x64"
} else {
    throw "Unsupported Windows architecture: $Arch"
}

if ($env:EXPECTED_FILE_ARCH -and $env:EXPECTED_FILE_ARCH -ne $FileArch) {
    throw "Runner arch is $FileArch, expected $($env:EXPECTED_FILE_ARCH)"
}

$AppVersion = $VersionLabel.TrimStart("v")
if ($AppVersion -notmatch '^[0-9]+\.[0-9]+\.[0-9]+') {
    throw "Could not parse dotted version from '$VersionLabel'"
}

$IcoPath = Join-Path $RepoRoot "src\jottr\jottr_icon.ico"
if (-not (Test-Path $IcoPath)) {
    throw "Missing Windows icon: $IcoPath"
}

python -m pip install -e ".[build]"
if ($LASTEXITCODE -ne 0) {
    throw "pip install -e .[build] failed"
}

# libenchant is not bundled. PyInstaller's enchant hook fails without the C
# library, so leave the module out; the app falls back to pyspellchecker.
$PyInstallerArgs = @(
    "--noconfirm",
    "--windowed",
    "--name=Jottr",
    "--icon=src/jottr/jottr_icon.ico",
    "--paths=src",
    "--exclude-module=enchant",
    "--collect-submodules=jottr",
    "--collect-data=spellchecker",
    "--hidden-import=ctypes",
    "--hidden-import=ctypes.util",
    "--hidden-import=jottr",
    "--hidden-import=jottr.editor_tab",
    "--hidden-import=jottr.editor",
    "--hidden-import=jottr.editor.browser",
    "--hidden-import=jottr.editor.find_replace",
    "--hidden-import=jottr.editor.focus_mode",
    "--hidden-import=jottr.editor.markdown",
    "--hidden-import=jottr.editor.spellcheck",
    "--hidden-import=jottr.editor.tab",
    "--hidden-import=jottr.editor.text_edit",
    "--hidden-import=jottr.ui",
    "--hidden-import=jottr.ui.document_tab_bar",
    "--hidden-import=jottr.ui.workspace",
    "--hidden-import=jottr.ui.workspace_controller",
    "--hidden-import=jottr.window",
    "--hidden-import=jottr.font_dialog",
    "--hidden-import=jottr.file_dialogs",
    "--hidden-import=jottr.icon_manager",
    "--hidden-import=jottr.resources",
    "--hidden-import=jottr.paths",
    "--hidden-import=jottr.plugin_manager",
    "--hidden-import=jottr.qt_style",
    "--hidden-import=jottr.window_color_scheme",
    "--hidden-import=jottr.settings_dialog",
    "--hidden-import=jottr.settings_manager",
    "--hidden-import=jottr.snippet_editor_dialog",
    "--hidden-import=jottr.snippet_manager",
    "--hidden-import=jottr.theme_manager",
    "--hidden-import=jottr.translation_manager",
    "--hidden-import=pyenchant",
    "--hidden-import=pyspellchecker",
    "--hidden-import=spellchecker",
    "--hidden-import=feedparser",
    "--hidden-import=requests",
    "--hidden-import=certifi",
    "--collect-data=certifi",
    "--add-data=src/jottr/help:jottr/help",
    "--add-data=src/jottr/icons:jottr/icons",
    "--add-data=src/jottr/resources:jottr/resources",
    "--add-data=icons:icons",
    "--add-data=translations:translations",
    "src/jottr/main.py"
)

Write-Host "Building PyInstaller onedir bundle"
python -m PyInstaller @PyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed"
}

$AppExe = Join-Path $RepoRoot "dist\Jottr\Jottr.exe"
if (-not (Test-Path $AppExe)) {
    throw "Expected app binary at $AppExe"
}

$WebEngine = Get-ChildItem -Path (Join-Path $RepoRoot "dist\Jottr") -Recurse -Filter "QtWebEngineProcess.exe" -ErrorAction SilentlyContinue
if (-not $WebEngine) {
    throw "QtWebEngineProcess.exe missing from the PyInstaller bundle"
}

$Iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $Iscc) {
    throw "ISCC.exe not found. Install Inno Setup 6 (choco install innosetup)."
}

$StagingDir = Join-Path $RepoRoot "release-assets-build"
if (Test-Path $StagingDir) {
    Remove-Item -Recurse -Force $StagingDir
}
New-Item -ItemType Directory -Path $StagingDir | Out-Null

$IssPath = Join-Path $PSScriptRoot "jottr.iss"
$RepoRootForIss = $RepoRoot -replace "\\", "/"
Write-Host "Building Inno Setup installer with $Iscc"
& $Iscc `
    "/DAppVersion=$AppVersion" `
    "/DVersionLabel=$VersionLabel" `
    "/DRepoRoot=$RepoRootForIss" `
    $IssPath
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compile failed"
}

$BuiltInstaller = Join-Path $StagingDir "jottr-$VersionLabel-windows-x86_64-unsigned.exe"
if (-not (Test-Path $BuiltInstaller)) {
    throw "Expected installer at $BuiltInstaller"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$Destination = Join-Path $OutputDir (Split-Path $BuiltInstaller -Leaf)
Copy-Item -Force $BuiltInstaller $Destination
Write-Host "Created $Destination"
