#!/usr/bin/env bash
# Interactive release helper for Jottr.
#
# Writes curated AppStream release notes into io.github.mfat.jottr.metainfo.xml,
# then commits with a Release-As footer and pushes to main so Release Please
# opens (or updates) the release PR. Version bumps in __init__.py, CHANGELOG,
# rpm.spec, and the manifest still come from Release Please after you merge
# that PR.
#
# Usage:
#   ./scripts/release.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

METAINFO_FILE="io.github.mfat.jottr.metainfo.xml"
INIT_FILE="src/jottr/__init__.py"
DEFAULT_BRANCH="main"

echo "Jottr release helper"
echo

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh (GitHub CLI) is required. Install: https://cli.github.com/" >&2
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: gh is not authenticated. Run: gh auth login" >&2
  exit 1
fi
if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is required." >&2
  exit 1
fi

BRANCH=$(git branch --show-current)
if [[ "$BRANCH" != "$DEFAULT_BRANCH" ]]; then
  echo "WARNING: you are on '$BRANCH', not '$DEFAULT_BRANCH'." >&2
  read -rp "Continue anyway? [y/N]: " CONT
  CONT=${CONT:-N}
  if [[ ! "$CONT" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
  fi
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree is dirty. Commit or stash first." >&2
  git status --short >&2
  exit 1
fi

# Heredoc must not sit inside $(...): bash still counts quotes/parens in the body.
read_current_version() {
  python3 - "$1" <<'PY'
import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r"""__version__\s*=\s*['"]([^'"]+)['"]""", text)
print(match.group(1) if match else "0.0.0")
PY
}
CURRENT_VERSION=$(read_current_version "$INIT_FILE")

echo "Current version: v$CURRENT_VERSION"
read -rp "New version (semver, e.g. 2.5.3): " VERSION
VERSION=${VERSION#v}
VERSION=${VERSION#V}
if [[ -z "$VERSION" ]]; then
  echo "ERROR: Version is required." >&2
  exit 1
fi
if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.+-].+)?$ ]]; then
  echo "ERROR: '$VERSION' does not look like semver (X.Y.Z)." >&2
  exit 1
fi

python3 - "$CURRENT_VERSION" "$VERSION" <<'PY'
import re
import sys


def parse_version(value: str):
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


current = parse_version(sys.argv[1])
new = parse_version(sys.argv[2])
if current is None or new is None:
    raise SystemExit("ERROR: Could not parse version numbers for comparison.")
if new <= current:
    raise SystemExit(
        f"ERROR: New version {sys.argv[2]} must be greater than current {sys.argv[1]}."
    )
PY

CHANGELOG_FILE=$(mktemp)
cleanup_changelog() { rm -f "$CHANGELOG_FILE"; }
trap cleanup_changelog EXIT

cat >"$CHANGELOG_FILE" <<EOF
# AppStream / Flathub release notes for v$VERSION
# One change per line. Do not prefix with '-' (added automatically in metainfo).
# Keep it short and user-facing (Flathub quality guidelines).
# Save and close the editor when done.
EOF

EDITOR_CMD="${VISUAL:-${EDITOR:-}}"
if [[ -z "$EDITOR_CMD" ]]; then
  for candidate in nano vim vi; do
    if command -v "$candidate" >/dev/null 2>&1; then
      EDITOR_CMD=$candidate
      break
    fi
  done
fi

echo
if [[ -n "$EDITOR_CMD" && -t 0 ]]; then
  echo "Opening $EDITOR_CMD for AppStream release notes..."
  # shellcheck disable=SC2086
  $EDITOR_CMD "$CHANGELOG_FILE"
else
  echo "Enter AppStream release notes for v$VERSION (plain lines; no '-')."
  echo "End with Ctrl-D:"
  : >"$CHANGELOG_FILE"
  cat >"$CHANGELOG_FILE"
fi

CHANGELOG=$(sed '/^#/d' "$CHANGELOG_FILE")
if [[ -z "${CHANGELOG//[[:space:]]/}" ]]; then
  echo "ERROR: Release notes are empty. Flathub needs user-facing notes." >&2
  exit 1
fi

echo
echo "Will:"
echo "  1. Prepend AppStream <release version=\"$VERSION\"> into $METAINFO_FILE"
echo "  2. Commit and push to origin/$BRANCH with Release-As: $VERSION"
echo "  3. Let Release Please open/update the release PR"
echo
echo "  Notes:"
sed 's/^/    /' <<<"$CHANGELOG"
echo
read -rp "Continue? [y/N]: " CONFIRM
CONFIRM=${CONFIRM:-N}
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo "Aborted; nothing was committed."
  exit 1
fi

python3 - "$METAINFO_FILE" "$VERSION" "$CHANGELOG" <<'PY'
import html
import re
import sys
from datetime import date
from pathlib import Path

path, version, changelog = sys.argv[1], sys.argv[2], sys.argv[3]
text = Path(path).read_text(encoding="utf-8")


def normalize_line(line: str):
    line = re.sub(r"^[-*]\s*", "", line.strip())
    return html.escape(line) if line else None


changelog_lines = [
    item
    for item in (normalize_line(line) for line in changelog.strip().split("\n"))
    if item
]
if not changelog_lines:
    raise SystemExit("ERROR: No usable release-note lines after cleanup.")

description = "\n".join(f"        <p>{line}</p>" for line in changelog_lines)
today = date.today().isoformat()
new_release = (
    f'    <release version="{version}" date="{today}">\n'
    f"      <description>\n"
    f"{description}\n"
    f"      </description>\n"
    f"    </release>\n"
)

first = re.search(
    r'<release\s+[^>]*version="([^"]+)"[^>]*>',
    text,
    flags=re.M,
)
if first and first.group(1) == version:
    # Notes for this version already exist (e.g. re-run): replace that block.
    pattern = re.compile(
        rf'(    <release version="{re.escape(version)}"[^>]*>\n)'
        r"      <description>.*?</description>\n"
        r"(    </release>\n)",
        flags=re.S,
    )
    replacement = (
        rf"\1"
        f"      <description>\n{description}\n      </description>\n"
        rf"\2"
    )
    text, count = pattern.subn(replacement, text, count=1)
    if not count:
        raise SystemExit(f"ERROR: Could not update existing {version} release in {path}")
    # Keep date current on rewrite.
    text = re.sub(
        rf'(<release version="{re.escape(version)}")(\s+date="[^"]*")?',
        rf'\1 date="{today}"',
        text,
        count=1,
    )
else:
    text, count = re.subn(
        r"(<releases>\s*\n)",
        r"\1" + new_release,
        text,
        count=1,
        flags=re.M,
    )
    if not count:
        raise SystemExit(f"ERROR: Could not insert a <release> into {path}")

Path(path).write_text(text, encoding="utf-8")
print(f"Updated {path}")
PY

git add "$METAINFO_FILE"
git commit -m "chore: release ${VERSION}" -m "Release-As: ${VERSION}"
git push -u origin "HEAD:${BRANCH}"

echo
echo "Pushed Release-As commit for v$VERSION."
echo "Waiting for the Release Please workflow..."

RUN_ID=""
for _ in $(seq 1 12); do
  sleep 3
  RUN_ID=$(gh run list --workflow release-please.yml --branch "$BRANCH" \
    --limit 1 --json databaseId,status,event,displayTitle \
    --jq '.[0] | select(.status != "completed") | .databaseId' || true)
  [[ -n "$RUN_ID" ]] && break
done

if [[ -n "$RUN_ID" ]]; then
  echo "Watching run $RUN_ID (Ctrl-C detaches; the workflow keeps running)..."
  gh run watch "$RUN_ID" --exit-status || true
else
  echo "Could not find a new workflow run yet; check: gh run list --workflow release-please.yml"
fi

echo
echo "Next: review and merge the Release Please PR, then packaging/Flathub run from the tag."
gh pr list --search "head:release-please--branches--${BRANCH}" --state open \
  --json number,title,url --jq '.[] | "#\(.number) \(.title)\n\(.url)"' 2>/dev/null || true
