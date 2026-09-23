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

# Relocatable Enchant + AppleSpell for the DMG (same idea as Flatpak compiling
# enchant into the sandbox). Without this, pyenchant only works if the end
# user already has Homebrew enchant installed.
chmod +x packaging/macos/stage-enchant.sh
ENCHANT_PREFIX="$(packaging/macos/stage-enchant.sh build/enchant-prefix | tail -n 1)"
export PYENCHANT_LIBRARY_PATH="${ENCHANT_PREFIX}/lib/libenchant-2.dylib"
# AppleSpell + glib can SIGSEGV on interpreter teardown after a successful
# import; use a sentinel so that does not fail the DMG build.
ENCHANT_STATUS="$(mktemp)"
set +e
python - "$ENCHANT_STATUS" <<'PY'
import sys
import enchant

status_path = sys.argv[1]
providers = [p.name for p in enchant.Broker().describe()]
if "AppleSpell" not in providers:
    raise SystemExit(f"AppleSpell missing; got {providers}")
with open(status_path, "w", encoding="utf-8") as fh:
    fh.write("ok")
print(f"Staged Enchant OK ({enchant.get_enchant_version()}; {providers})")
PY
ENCHANT_RC=$?
set -e
if [ "$(cat "$ENCHANT_STATUS" 2>/dev/null || true)" != "ok" ]; then
  rm -f "$ENCHANT_STATUS"
  echo "Staged Enchant is not importable via PYENCHANT_LIBRARY_PATH=$PYENCHANT_LIBRARY_PATH (exit $ENCHANT_RC)"
  exit 1
fi
rm -f "$ENCHANT_STATUS"
if [ "$ENCHANT_RC" -ne 0 ]; then
  echo "Staged Enchant OK (interpreter exited with $ENCHANT_RC after success)"
fi

ENCHANT_BINARIES=()
while IFS= read -r path; do
  rel="${path#"${ENCHANT_PREFIX}/"}"
  dest_dir="$(dirname "enchant/${rel}")"
  ENCHANT_BINARIES+=(--add-binary "${path}:${dest_dir}")
done < <(find "${ENCHANT_PREFIX}" -type f \( -name '*.dylib' -o -name '*.so' \) | sort)

# ${arr[@]+...} keeps an empty array safe under set -u in macOS's bash 3.2.
pyinstaller \
  --noconfirm \
  --windowed \
  --name Jottr \
  --icon src/jottr/jottr_icon.icns \
  --paths src \
  --runtime-hook packaging/macos/pyi_rth_jottr_enchant.py \
  ${ENCHANT_BINARIES[@]+"${ENCHANT_BINARIES[@]}"} \
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
  --hidden-import enchant \
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
  --add-data "src/jottr/editor/data:jottr/editor/data" \
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

BUNDLED_ENCHANT="$(find dist/Jottr.app -path '*/enchant/lib/libenchant-2.dylib' | head -n 1 || true)"
if [ -z "$BUNDLED_ENCHANT" ]; then
  echo "Bundled libenchant-2.dylib missing from Jottr.app"
  find dist/Jottr.app -iname '*enchant*' || true
  exit 1
fi
echo "Bundled Enchant at $BUNDLED_ENCHANT"

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
