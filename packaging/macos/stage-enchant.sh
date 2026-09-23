#!/bin/bash
# Stage a relocatable Enchant prefix for the macOS .app bundle.
#
# PyInstaller's stock enchant hook does not ship Homebrew's libenchant into the
# DMG, so frozen builds only worked when the end user also had enchant installed.
# This script copies (or builds) libenchant + the AppleSpell provider + their
# non-system dylib deps, then rewrites install names to @loader_path so the
# tree works from inside Jottr.app.
#
# AppleSpell uses macOS system dictionaries, so we do not ship hunspell word
# lists. Languages Apple does not cover still fall back to pyspellchecker.
#
# Usage (from repo root, or via build-dmg.sh):
#   packaging/macos/stage-enchant.sh [output-prefix]
#
# Default output: build/enchant-prefix
# Prints the prefix path on stdout (last line); progress goes to stderr.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PREFIX="${1:-$ROOT/build/enchant-prefix}"
SRC_BUILD="$ROOT/build/enchant-src"
ENCHANT_VERSION="${ENCHANT_VERSION:-2.8.21}"
ENCHANT_URL="${ENCHANT_URL:-https://github.com/rrthomas/enchant/releases/download/v${ENCHANT_VERSION}/enchant-${ENCHANT_VERSION}.tar.gz}"
ENCHANT_SHA256="${ENCHANT_SHA256:-dd2a762697c463148a8f59867089a5ebf2dd1449d869f93764b76c12bcf8acc0}"

log() { printf '%s\n' "$*" >&2; }

system_lib() {
  case "$1" in
    /usr/lib/*|/System/*|/Library/Frameworks/*) return 0 ;;
    *) return 1 ;;
  esac
}

find_brew_enchant_lib() {
  python3 - <<'PY'
import os, sys
try:
    # Prefer an already-working import (Homebrew / earlier stage).
    os.environ.pop("PYENCHANT_LIBRARY_PATH", None)
    os.environ.pop("PYENCHANT_ENCHANT_PREFIX", None)
    from enchant._enchant import enchant_lib_path
except Exception:
    sys.exit(1)
print(enchant_lib_path)
PY
}

ensure_brew_build_deps() {
  if ! command -v brew >/dev/null 2>&1; then
    log "Homebrew is required to build Enchant (needs glib)"
    return 1
  fi
  local pkgs=()
  for pkg in glib gettext pkgconf; do
    if ! brew list --versions "$pkg" >/dev/null 2>&1; then
      pkgs+=("$pkg")
    fi
  done
  if [ "${#pkgs[@]}" -gt 0 ]; then
    log "Installing Homebrew build deps: ${pkgs[*]}"
    brew install "${pkgs[@]}"
  fi
  # pkg-config must see Homebrew glib/gettext on Intel (/usr/local) and Apple
  # Silicon (/opt/homebrew).
  local brew_prefix
  brew_prefix="$(brew --prefix)"
  export PATH="$brew_prefix/bin:$PATH"
  export PKG_CONFIG_PATH="${brew_prefix}/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
  export CPPFLAGS="-I${brew_prefix}/include ${CPPFLAGS:-}"
  export LDFLAGS="-L${brew_prefix}/lib ${LDFLAGS:-}"
}

build_enchant_from_source() {
  ensure_brew_build_deps
  mkdir -p "$SRC_BUILD"
  local tarball="$SRC_BUILD/enchant-${ENCHANT_VERSION}.tar.gz"
  local srcdir="$SRC_BUILD/enchant-${ENCHANT_VERSION}"
  local install_root="$SRC_BUILD/enchant-install"

  if [ ! -f "$tarball" ]; then
    log "Downloading Enchant ${ENCHANT_VERSION}"
    curl -fsSL "$ENCHANT_URL" -o "$tarball"
  fi
  local actual_sha
  actual_sha="$(shasum -a 256 "$tarball" | awk '{ print $1 }')"
  if [ "$actual_sha" != "$ENCHANT_SHA256" ]; then
    log "Enchant tarball checksum mismatch:"
    log "  expected $ENCHANT_SHA256"
    log "  actual   $actual_sha"
    exit 1
  fi
  rm -rf "$srcdir" "$install_root"
  mkdir -p "$install_root"
  tar -xzf "$tarball" -C "$SRC_BUILD"

  log "Configuring Enchant ${ENCHANT_VERSION} (--enable-relocatable)"
  (
    cd "$srcdir"
    # Do not require aspell/hunspell: on macOS the AppleSpell provider is
    # enough, and it uses system dictionaries (no word lists to ship).
    ./configure \
      --prefix="$install_root" \
      --enable-relocatable \
      --disable-static
    make -j"$(sysctl -n hw.ncpu 2>/dev/null || echo 2)"
    make install
  )
  printf '%s\n' "$install_root/lib/libenchant-2.dylib"
}

resolve_enchant_lib() {
  local lib=""
  if lib="$(find_brew_enchant_lib 2>/dev/null)" && [ -n "$lib" ] && [ -f "$lib" ]; then
    log "Using existing Enchant library: $lib"
    printf '%s\n' "$lib"
    return 0
  fi
  if command -v brew >/dev/null 2>&1; then
    log "Trying Homebrew enchant"
    if brew install enchant >/dev/null 2>&1; then
      if lib="$(find_brew_enchant_lib 2>/dev/null)" && [ -n "$lib" ] && [ -f "$lib" ]; then
        log "Using Homebrew Enchant library: $lib"
        printf '%s\n' "$lib"
        return 0
      fi
    else
      log "Homebrew enchant install failed; will build from source"
    fi
  fi
  build_enchant_from_source
}

collect_deps() {
  local stage_lib="$1"
  local path dep dest
  local -a queue=()
  while IFS= read -r path; do
    queue+=("$path")
  done < <(find "$stage_lib" -type f \( -name '*.dylib' -o -name '*.so' \))

  local i=0
  while [ "$i" -lt "${#queue[@]}" ]; do
    path="${queue[$i]}"
    i=$((i + 1))
    while IFS= read -r dep; do
      [ -z "$dep" ] && continue
      case "$dep" in
        @*|*:*) continue ;;
      esac
      if system_lib "$dep"; then
        continue
      fi
      if [ ! -f "$dep" ]; then
        log "WARNING: missing dependency $dep (from $path)"
        continue
      fi
      dest="$stage_lib/$(basename "$dep")"
      if [ ! -f "$dest" ]; then
        log "Collecting $(basename "$dep")"
        cp -f "$dep" "$dest"
        queue+=("$dest")
      fi
    done < <(otool -L "$path" | awk 'NR > 1 { print $1 }')
  done
}

rewrite_loader_paths() {
  local stage_lib="$1"
  local path old name new
  while IFS= read -r path; do
    if [[ "$path" == *.dylib ]] || [[ "$path" == *.so ]]; then
      install_name_tool -id "@loader_path/$(basename "$path")" "$path" 2>/dev/null || true
    fi
    while IFS= read -r old; do
      [ -z "$old" ] && continue
      case "$old" in
        @loader_path/*|@rpath/*|@executable_path/*) continue ;;
      esac
      if system_lib "$old"; then
        continue
      fi
      name="$(basename "$old")"
      if [ "$(basename "$(dirname "$path")")" = "enchant-2" ]; then
        new="@loader_path/../$name"
      else
        new="@loader_path/$name"
      fi
      if [ "$old" != "$new" ]; then
        install_name_tool -change "$old" "$new" "$path" 2>/dev/null || true
      fi
    done < <(otool -L "$path" | awk 'NR > 1 { print $1 }')
    codesign --sign - --force --timestamp=none "$path" >/dev/null 2>&1 || true
  done < <(find "$stage_lib" -type f \( -name '*.dylib' -o -name '*.so' \))
}

stage_from_lib() {
  local enchant_lib="$1"
  local libdir provider_dir provider stage_lib real_lib

  libdir="$(cd "$(dirname "$enchant_lib")" && pwd)"
  real_lib="$(python3 -c "import os; print(os.path.realpath('$enchant_lib'))")"
  provider_dir=""
  for candidate in "$libdir/enchant-2" "$libdir/enchant"; do
    if [ -d "$candidate" ]; then
      provider_dir="$candidate"
      break
    fi
  done
  if [ -z "$provider_dir" ]; then
    log "No enchant provider directory next to $enchant_lib"
    exit 1
  fi

  provider=""
  for candidate in enchant_applespell.so enchant_applespell.dylib; do
    if [ -f "$provider_dir/$candidate" ]; then
      provider="$provider_dir/$candidate"
      break
    fi
  done
  if [ -z "$provider" ]; then
    log "AppleSpell provider not found in $provider_dir"
    log "Install enchant with AppleSpell support (Homebrew enchant includes it)."
    exit 1
  fi

  rm -rf "$PREFIX"
  stage_lib="$PREFIX/lib"
  mkdir -p "$stage_lib/enchant-2"

  cp -f "$real_lib" "$stage_lib/$(basename "$real_lib")"
  # Stable soname symlink / copy that pyenchant looks up.
  cp -f "$stage_lib/$(basename "$real_lib")" "$stage_lib/libenchant-2.dylib"
  cp -f "$provider" "$stage_lib/enchant-2/$(basename "$provider")"

  collect_deps "$stage_lib"
  rewrite_loader_paths "$stage_lib"

  # Drop static archives if any slipped in.
  find "$PREFIX" -name '*.a' -delete
}

verify_stage() {
  local lib="$PREFIX/lib/libenchant-2.dylib"
  if [ ! -f "$lib" ]; then
    log "Staged library missing: $lib"
    exit 1
  fi
  if [ ! -f "$PREFIX/lib/enchant-2/enchant_applespell.so" ] \
    && [ ! -f "$PREFIX/lib/enchant-2/enchant_applespell.dylib" ]; then
    log "Staged AppleSpell provider missing under $PREFIX/lib/enchant-2"
    exit 1
  fi

  log "Verifying staged Enchant via PYENCHANT_LIBRARY_PATH"
  # AppleSpell + glib sometimes SIGSEGV during interpreter teardown after a
  # successful check. Treat a written sentinel as success either way.
  local status
  status="$(mktemp)"
  set +e
  PYENCHANT_LIBRARY_PATH="$lib" python3 - "$status" <<'PY'
import sys
import enchant

status_path = sys.argv[1]
providers = [p.name for p in enchant.Broker().describe()]
if "AppleSpell" not in providers:
    print("AppleSpell provider not loaded; got:", providers, file=sys.stderr)
    sys.exit(1)
langs = enchant.list_languages()
if not langs:
    print("No dictionaries from AppleSpell", file=sys.stderr)
    sys.exit(1)
tag = "en_US" if "en_US" in langs else langs[0]
d = enchant.Dict(tag)
if not d.check("enchant"):
    print("Dictionary check failed for 'enchant'", file=sys.stderr)
    sys.exit(1)
with open(status_path, "w", encoding="utf-8") as fh:
    fh.write("ok")
print(
    f"OK Enchant {enchant.get_enchant_version()} providers={providers} "
    f"languages={len(langs)}",
    file=sys.stderr,
)
PY
  local rc=$?
  set -e
  if [ "$(cat "$status" 2>/dev/null || true)" = "ok" ]; then
    rm -f "$status"
    if [ "$rc" -ne 0 ]; then
      log "Enchant verified (interpreter exited with $rc after success)"
    fi
    return 0
  fi
  rm -f "$status"
  log "Staged Enchant failed verification (exit $rc)"
  exit 1
}

main() {
  log "Staging Enchant into $PREFIX"
  local enchant_lib
  enchant_lib="$(resolve_enchant_lib)"
  stage_from_lib "$enchant_lib"
  verify_stage
  # Last line of stdout is the prefix path for callers.
  printf '%s\n' "$PREFIX"
}

main "$@"
