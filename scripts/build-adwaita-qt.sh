#!/usr/bin/env bash
# Build vendored FedoraQt/adwaita-qt into src/jottr/qt_plugins/ for bundling.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
src_dir="$repo_root/vendor/adwaita-qt"
build_dir="${ADWAITA_QT_BUILD_DIR:-$src_dir/build}"
out_dir="${ADWAITA_QT_OUT_DIR:-$repo_root/src/jottr/qt_plugins}"
staging_dir="$build_dir/staging"

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

need_command cmake
if ! command -v ninja >/dev/null 2>&1 && ! command -v make >/dev/null 2>&1; then
  echo "Missing required command: ninja or make" >&2
  exit 1
fi

if [ ! -f "$src_dir/CMakeLists.txt" ]; then
  echo "Vendored adwaita-qt source not found at $src_dir" >&2
  exit 1
fi

generator=Ninja
if ! command -v ninja >/dev/null 2>&1; then
  generator="Unix Makefiles"
fi

echo "==> Configuring adwaita-qt (Qt6) in $build_dir"
rm -rf "$staging_dir"
mkdir -p "$build_dir" "$staging_dir"

# Embed relocatable RPATHs so AppImage/PyInstaller need no LD_LIBRARY_PATH.
# Style plugin looks in ../lib; shared libs look beside themselves.
cmake -S "$src_dir" -B "$build_dir" \
  -G "$generator" \
  -DCMAKE_BUILD_TYPE=Release \
  -DUSE_QT6=ON \
  -DCMAKE_INSTALL_PREFIX="$staging_dir" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
  -DCMAKE_INSTALL_RPATH='$ORIGIN:$ORIGIN/../lib' \
  -DCMAKE_INSTALL_RPATH_USE_LINK_PATH=OFF

echo "==> Building and installing adwaita-qt"
cmake --build "$build_dir" --parallel
cmake --install "$build_dir"

plugin="$(find "$staging_dir" -type f -name 'adwaita.so' | head -n 1 || true)"
if [ -z "$plugin" ]; then
  echo "adwaita.so was not installed under $staging_dir" >&2
  find "$staging_dir" -type f | head -n 50 >&2 || true
  exit 1
fi

echo "==> Assembling bundled plugin tree at $out_dir"
rm -rf "$out_dir"
mkdir -p "$out_dir/styles" "$out_dir/lib"
cp -a "$plugin" "$out_dir/styles/adwaita.so"

# Shared libraries the style plugin links against (files + SONAME symlinks).
while IFS= read -r lib; do
  cp -a "$lib" "$out_dir/lib/"
done < <(find "$staging_dir" \( -type f -o -type l \) \( -name 'libadwaitaqt6.so*' -o -name 'libadwaitaqt6priv.so*' \))

if command -v patchelf >/dev/null 2>&1; then
  patchelf --set-rpath '$ORIGIN/../lib' "$out_dir/styles/adwaita.so"
  for lib in "$out_dir"/lib/libadwaitaqt6*.so*; do
    [ -e "$lib" ] || continue
    [ -L "$lib" ] && continue
    if file "$lib" | grep -q 'ELF'; then
      patchelf --set-rpath '$ORIGIN' "$lib"
    fi
  done
else
  echo "==> patchelf not found; relying on CMake INSTALL_RPATH (\$ORIGIN)"
fi

echo "==> Bundled Adwaita-Qt plugin:"
find "$out_dir" -type f -o -type l | sort
