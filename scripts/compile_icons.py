#!/usr/bin/env python3
"""Compile ``icons/symbolic.qrc`` into a PyQt6 resource module.

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
QRC = ROOT / "icons" / "symbolic.qrc"
OUTPUT = ROOT / "src" / "jottr" / "resources" / "rc_symbolic_icons.py"

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT,
        help=f"Output module (default: {OUTPUT})",
    )
    args = parser.parse_args(argv)

    if not QRC.is_file():
        raise SystemExit(f"Missing resource collection: {QRC}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rcc = find_rcc()
    cmd = [
        rcc,
        "-g",
        "python",
        "--compress-algo",
        "zlib",
        "-o",
        str(args.output),
        str(QRC),
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)
    rewrite_for_pyqt6(args.output)
    print(f"Wrote {args.output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
