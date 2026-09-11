#!/usr/bin/env python3
"""Rasterize ``icons/jottr.svg`` into optional PNG sizes.

Linux packaging installs the SVG under ``hicolor/scalable/apps``. These PNGs
remain available for non-Linux bundles that still want rasters.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "icons" / "jottr.svg"
SIZES = (16, 32, 48, 64, 128, 256, 512)


def export_size(renderer: QSvgRenderer, size: int, destination: Path) -> None:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    if not image.save(str(destination)):
        raise SystemExit(f"Failed to write {destination}")


def main() -> int:
    if not SVG.is_file():
        raise SystemExit(f"Missing app icon: {SVG}")

    app = QApplication.instance() or QApplication(["export-app-icons"])
    renderer = QSvgRenderer(str(SVG))
    if not renderer.isValid():
        raise SystemExit(f"Invalid SVG: {SVG}")

    icons_dir = ROOT / "icons"
    for size in SIZES:
        out = icons_dir / f"jottr_icon_{size}x{size}.png"
        export_size(renderer, size, out)
        print(f"Wrote {out.relative_to(ROOT)}")

    primary = icons_dir / "jottr.png"
    export_size(renderer, 256, primary)
    print(f"Wrote {primary.relative_to(ROOT)}")
    _ = app
    return 0


if __name__ == "__main__":
    sys.exit(main())
