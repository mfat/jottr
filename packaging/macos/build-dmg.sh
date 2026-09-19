#!/bin/bash
# Build an ad-hoc-signed Jottr.app and pack it into an unsigned DMG.
# Run from CI or a macOS machine with PyInstaller deps already installed.
#
# Usage:
#   packaging/macos/build-dmg.sh <version-label> [output-dir]
#
# Example:
#   packaging/macos/build-dmg.sh v2.3.3 release-assets
#
# Optional env:
#   EXPECTED_FILE_ARCH  — fail if the binary is not this arch (arm64 or x86_64)

set -euo pipefail

cd "$(dirname "$0")/../.."

VERSION_LABEL="${1:?version label required (example: v2.3.3)}"
OUTPUT_DIR="${2:-release-assets}"

HOST_ARCH="$(uname -m)"
case "$HOST_ARCH" in
  arm64)
    ARCH_NAME="aarch64"
    FILE_ARCH="arm64"
    ;;
  x86_64)
    ARCH_NAME="x86_64"
    FILE_ARCH="x86_64"
    ;;
  *)
    echo "Unsupported macOS architecture: $HOST_ARCH"
    exit 1
    ;;
esac

if [ -n "${EXPECTED_FILE_ARCH:-}" ] && [ "$FILE_ARCH" != "$EXPECTED_FILE_ARCH" ]; then
  echo "Runner arch is $FILE_ARCH, expected $EXPECTED_FILE_ARCH"
  exit 1
fi

python -m pip install -e ".[build]"

# Intel runners skip Homebrew enchant (Homebrew Tier 3). Without libenchant,
# PyInstaller's enchant hook fails at build time, so leave the module out; the
# app falls back to pyspellchecker.
EXTRA_PYINSTALLER_ARGS=()
if ! python -c "import enchant" >/dev/null 2>&1; then
  echo "libenchant not found; building without enchant (pyspellchecker fallback)"
  EXTRA_PYINSTALLER_ARGS+=(--exclude-module enchant)
fi

# ${arr[@]+...} keeps an empty array safe under set -u in macOS's bash 3.2.
pyinstaller \
  --noconfirm \
  --windowed \
  --name Jottr \
  --icon src/jottr/jottr_icon.icns \
  --paths src \
  ${EXTRA_PYINSTALLER_ARGS[@]+"${EXTRA_PYINSTALLER_ARGS[@]}"} \
  --collect-submodules jottr \
  --collect-data spellchecker \
  --hidden-import ctypes \
  --hidden-import ctypes.util \
  --hidden-import jottr \
  --hidden-import jottr.editor_tab \
  --hidden-import jottr.editor \
  --hidden-import jottr.editor.browser \
  --hidden-import jottr.editor.find_replace \
  --hidden-import jottr.editor.focus_mode \
  --hidden-import jottr.editor.markdown \
  --hidden-import jottr.editor.spellcheck \
  --hidden-import jottr.editor.tab \
  --hidden-import jottr.editor.text_edit \
  --hidden-import jottr.ui \
  --hidden-import jottr.ui.document_tab_bar \
  --hidden-import jottr.ui.workspace \
  --hidden-import jottr.ui.workspace_controller \
  --hidden-import jottr.window \
  --hidden-import jottr.font_dialog \
  --hidden-import jottr.file_dialogs \
  --hidden-import jottr.icon_manager \
  --hidden-import jottr.resources \
  --hidden-import jottr.paths \
  --hidden-import jottr.plugin_manager \
  --hidden-import jottr.qt_style \
  --hidden-import jottr.window_color_scheme \
  --hidden-import jottr.settings_dialog \
  --hidden-import jottr.settings_manager \
  --hidden-import jottr.snippet_editor_dialog \
  --hidden-import jottr.snippet_manager \
  --hidden-import jottr.theme_manager \
  --hidden-import jottr.translation_manager \
  --hidden-import pyenchant \
  --hidden-import pyspellchecker \
  --hidden-import spellchecker \
  --hidden-import feedparser \
  --hidden-import requests \
  --hidden-import certifi \
  --collect-data certifi \
  --add-data "src/jottr/help:jottr/help" \
  --add-data "src/jottr/icons:jottr/icons" \
  --add-data "src/jottr/resources:jottr/resources" \
  --add-data "icons:icons" \
  --add-data "translations:translations" \
  src/jottr/main.py

APP_BIN="dist/Jottr.app/Contents/MacOS/Jottr"
if [ ! -f "$APP_BIN" ]; then
  echo "Expected app binary at $APP_BIN"
  find dist -maxdepth 4 -type f -perm -111 || true
  exit 1
fi

file "$APP_BIN"
if ! file "$APP_BIN" | grep -q "$FILE_ARCH"; then
  echo "Architecture mismatch: expected $FILE_ARCH"
  exit 1
fi

# Ad-hoc sign after the bundle is final. No Developer ID, so Gatekeeper still
# treats it as unidentified, but a valid ad-hoc signature avoids the
# "app is damaged" dead-end on downloaded copies.
codesign --sign - --force --deep --timestamp=none dist/Jottr.app
codesign --verify --strict --verbose=2 dist/Jottr.app

rm -rf dmg-root
mkdir -p "$OUTPUT_DIR" dmg-root
cp -R dist/Jottr.app dmg-root/
ln -s /Applications dmg-root/Applications

DMG_PATH="${OUTPUT_DIR}/jottr-${VERSION_LABEL}-macos-${ARCH_NAME}-unsigned.dmg"
hdiutil create \
  -volname "Jottr" \
  -srcfolder dmg-root \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Created $DMG_PATH"
