#!/usr/bin/env bash
set -euo pipefail

APPIMAGE_TOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

usage() {
  cat <<'EOF'
Usage: scripts/build-appimage-local.sh [options]

Build and optionally smoke-test the Jottr AppImage locally.

Options:
  --version VERSION       Version string for the output file. Default: local
  --clean                 Remove previous PyInstaller, AppDir, and local release output first
  --skip-pip-install      Reuse build-venv without installing/updating Python packages
  --run-bundle            Run the PyInstaller bundle before creating the AppImage
  --run-appimage          Run the finished AppImage
  -h, --help              Show this help

System packages expected on Ubuntu/Debian:
  sudo apt-get install desktop-file-utils file libfuse2 patchelf python3-venv wget
EOF
}

version="local"
clean=false
skip_pip_install=false
run_bundle=false
run_appimage=false

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version)
      if [ "$#" -lt 2 ]; then
        echo "Missing value for --version" >&2
        exit 2
      fi
      version="$2"
      shift 2
      ;;
    --clean)
      clean=true
      shift
      ;;
    --skip-pip-install)
      skip_pip_install=true
      shift
      ;;
    --run-bundle)
      run_bundle=true
      shift
      ;;
    --run-appimage)
      run_appimage=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
app_dir="$repo_root/AppDir"
release_dir="$repo_root/release-assets-local"
venv_dir="$repo_root/build-venv"
pyinstaller="$venv_dir/bin/pyinstaller"
output="$release_dir/jottr-${version}-linux-x86_64.AppImage"

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

need_file() {
  if [ ! -e "$1" ]; then
    echo "Missing required file or directory: $1" >&2
    exit 1
  fi
}

echo "==> Checking local tools"
need_command python3
need_command wget
need_command sed
need_command chmod
need_command cp
need_command mkdir
need_command readlink
need_command sha256sum
need_command desktop-file-validate

need_file "$repo_root/requirements.txt"
need_file "$repo_root/src/jottr/main.py"
need_file "$repo_root/icons/jottr.png"
need_file "$repo_root/io.github.mfat.jottr.desktop"

if [ "$clean" = true ]; then
  echo "==> Cleaning local AppImage build output"
  rm -rf \
    "$repo_root/src/jottr/build" \
    "$repo_root/src/jottr/dist" \
    "$repo_root/src/jottr/jottr.spec" \
    "$app_dir" \
    "$release_dir"
fi

if [ ! -x "$venv_dir/bin/python" ]; then
  echo "==> Creating build virtualenv"
  python3 -m venv "$venv_dir"
fi

if [ "$skip_pip_install" = false ]; then
  echo "==> Installing Python build dependencies"
  "$venv_dir/bin/python" -m pip install --upgrade pip
  "$venv_dir/bin/python" -m pip install -r "$repo_root/requirements.txt"
fi

echo "==> Building PyInstaller bundle"
(
  cd "$repo_root/src/jottr"
  "$pyinstaller" \
    --noconfirm \
    --windowed \
    --name jottr \
    --paths "." \
    --hidden-import ctypes \
    --hidden-import ctypes.util \
    --hidden-import editor_tab \
    --hidden-import feed_manager_dialog \
    --hidden-import font_dialog \
    --hidden-import rss_reader \
    --hidden-import rss_tab \
    --hidden-import settings_dialog \
    --hidden-import settings_manager \
    --hidden-import snippet_editor_dialog \
    --hidden-import snippet_manager \
    --hidden-import theme_manager \
    --hidden-import translation_manager \
    --hidden-import pyenchant \
    --hidden-import pyspellchecker \
    --hidden-import spellchecker \
    --add-data "editor_tab.py:." \
    --add-data "feed_manager_dialog.py:." \
    --add-data "font_dialog.py:." \
    --add-data "rss_reader.py:." \
    --add-data "rss_tab.py:." \
    --add-data "settings_dialog.py:." \
    --add-data "settings_manager.py:." \
    --add-data "snippet_editor_dialog.py:." \
    --add-data "snippet_manager.py:." \
    --add-data "theme_manager.py:." \
    --add-data "translation_manager.py:." \
    --add-data "icons:icons" \
    --add-data "help:help" \
    main.py
)

bundle_exe="$repo_root/src/jottr/dist/jottr/jottr"
need_file "$bundle_exe"

if [ "$run_bundle" = true ]; then
  echo "==> Running PyInstaller bundle"
  QTWEBENGINE_DISABLE_SANDBOX=1 "$bundle_exe"
fi

echo "==> Building AppDir"
rm -rf "$app_dir"
mkdir -p \
  "$app_dir/usr/bin" \
  "$app_dir/usr/share/jottr" \
  "$app_dir/usr/share/applications" \
  "$app_dir/usr/share/icons/hicolor/256x256/apps"

cp -r "$repo_root/src/jottr/dist/jottr/." "$app_dir/usr/share/jottr/"
cp "$repo_root/icons/jottr.png" "$app_dir/usr/share/icons/hicolor/256x256/apps/jottr.png"
cp "$repo_root/icons/jottr.png" "$app_dir/jottr.png"
cp "$repo_root/io.github.mfat.jottr.desktop" "$app_dir/usr/share/applications/jottr.desktop"
cp "$repo_root/io.github.mfat.jottr.desktop" "$app_dir/jottr.desktop"
sed -i 's/^Icon=.*/Icon=jottr/' "$app_dir/usr/share/applications/jottr.desktop"
sed -i 's/^Icon=.*/Icon=jottr/' "$app_dir/jottr.desktop"

cat > "$app_dir/AppRun" <<'EOF'
#!/bin/sh
APPDIR="${APPDIR:-$(dirname "$(readlink -f "$0")")}"
export QTWEBENGINE_DISABLE_SANDBOX=1
exec "$APPDIR/usr/share/jottr/jottr" "$@"
EOF
chmod +x "$app_dir/AppRun"

cat > "$app_dir/usr/bin/jottr" <<'EOF'
#!/bin/sh
SELF="$(readlink -f "$0")"
APPDIR="${APPDIR:-$(dirname "$(dirname "$(dirname "$SELF")")")}"
exec "$APPDIR/AppRun" "$@"
EOF
chmod +x "$app_dir/usr/bin/jottr"

desktop-file-validate "$app_dir/usr/share/applications/jottr.desktop"

echo "==> Building AppImage"
mkdir -p "$release_dir"
appimagetool="$repo_root/appimagetool"
if [ ! -x "$appimagetool" ]; then
  wget -O "$appimagetool" "$APPIMAGE_TOOL_URL"
  chmod +x "$appimagetool"
fi

ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$appimagetool" "$app_dir" "$output"
chmod +x "$output"
sha256sum "$output" > "$output.sha256"

echo "==> Built $output"
echo "==> Checksum written to $output.sha256"

if [ "$run_appimage" = true ]; then
  echo "==> Running AppImage"
  APPIMAGE_EXTRACT_AND_RUN=1 "$output"
fi
