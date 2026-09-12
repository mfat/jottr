#!/usr/bin/env bash
# Build, install, and run Jottr Flatpak from the working tree.
#
# Uses the in-tree io.github.mfat.jottr.yml (type: dir / path: .), same pattern
# as sshpilot's scripts/test-flatpak.sh.
set -euo pipefail

APP_ID="io.github.mfat.jottr"
MANIFEST="io.github.mfat.jottr.yml"

cd "$(dirname "$0")/.."

echo "=== Uninstall existing $APP_ID (if any) ==="
mapfile -t refs < <(
  flatpak list --user --app --columns=ref 2>/dev/null \
    | awk -v id="$APP_ID" '$0 ~ ("^app/" id "/") { print }'
  flatpak list --system --app --columns=ref 2>/dev/null \
    | awk -v id="$APP_ID" '$0 ~ ("^app/" id "/") { print }'
)
if [ "${#refs[@]}" -eq 0 ]; then
  echo "(none installed)"
else
  for ref in "${refs[@]}"; do
    echo "uninstalling $ref"
    flatpak uninstall -y --user "$ref" 2>/dev/null \
      || flatpak uninstall -y --system "$ref" 2>/dev/null \
      || true
  done
fi

# Older runs may have left a non-OSTree directory named repo.
if [ -e repo ] && [ ! -d repo/objects ]; then
  rm -rf repo
fi

echo "=== Build Flatpak from working tree ==="
flatpak run --command=flathub-build org.flatpak.Builder \
  --install \
  --disable-rofiles-fuse \
  --force-clean \
  "$MANIFEST"

echo ""
echo "=== Running $APP_ID ==="
flatpak run "$APP_ID"
