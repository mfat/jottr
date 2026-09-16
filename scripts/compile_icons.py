#!/usr/bin/env python3
"""Compile bundled icon ``*.qrc`` files into PyQt6 resource modules.

Uses Qt's ``rcc -g python`` (official Qt Resource System workflow). PyQt6 does
not ship ``pyrcc6``, so this script prefers the system Qt6 ``rcc`` binary and
rewrites the generated import from PySide6 to PyQt6 when needed.

Compression uses zlib for cross-platform portability (see Qt rcc docs).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS_DIR = ROOT / "icons"
RESOURCES_DIR = ROOT / "src" / "jottr" / "resources"

# theme id -> (qrc path, output module path)
ICON_THEME_RESOURCES = (
    ("symbolic", ICONS_DIR / "symbolic.qrc", RESOURCES_DIR / "rc_symbolic_icons.py"),
    ("bootstrap", ICONS_DIR / "bootstrap.qrc", RESOURCES_DIR / "rc_bootstrap_icons.py"),
    ("material", ICONS_DIR / "material.qrc", RESOURCES_DIR / "rc_material_icons.py"),
    ("qlementine", ICONS_DIR / "qlementine.qrc", RESOURCES_DIR / "rc_qlementine_icons.py"),
)

RCC_CANDIDATES = (
    Path("/usr/lib/qt6/libexec/rcc"),
    Path("/usr/lib64/qt6/libexec/rcc"),
    Path("/usr/lib/qt6/bin/rcc"),
)


def find_rcc() -> str:
    for candidate in RCC_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    for name in ("rcc", "pyside6-rcc"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit(
        "Could not find Qt rcc. Install qt6-base-dev-tools "
        "(provides /usr/lib/qt6/libexec/rcc) or PySide6."
    )


def rewrite_for_pyqt6(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    updated = text.replace("from PySide6 import QtCore", "from PyQt6 import QtCore", 1)
    if updated == text and "from PyQt6 import QtCore" not in text:
        raise SystemExit(f"Unexpected rcc output (no QtCore import) in {path}")
    path.write_text(updated, encoding="utf-8")


def compile_qrc(rcc: str, qrc: Path, output: Path) -> None:
    if not qrc.is_file():
        raise SystemExit(f"Missing resource collection: {qrc}")
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        rcc,
        "-g",
        "python",
        "--compress-algo",
        "zlib",
        "-o",
        str(output),
        str(qrc),
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)
    rewrite_for_pyqt6(output)
    print(f"Wrote {output.relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "themes",
        nargs="*",
        help="Theme ids to compile (default: all). Known: symbolic, bootstrap, material, qlementine",
    )
    args = parser.parse_args(argv)

    wanted = {name.casefold() for name in args.themes} if args.themes else None
    rcc = find_rcc()
    compiled = 0
    for theme_id, qrc, output in ICON_THEME_RESOURCES:
        if wanted is not None and theme_id.casefold() not in wanted:
            continue
        compile_qrc(rcc, qrc, output)
        compiled += 1

    if wanted is not None and compiled == 0:
        known = ", ".join(theme_id for theme_id, *_ in ICON_THEME_RESOURCES)
        raise SystemExit(f"No matching themes. Known: {known}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
