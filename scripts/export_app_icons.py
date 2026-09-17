#!/usr/bin/env python3
"""Rasterize ``icons/jottr.svg`` into PNG sizes, macOS ICNS, and Windows ICO.

Linux packaging installs the SVG under ``hicolor/scalable/apps``. These PNGs
and the macOS/Windows bundle icons remain available for packages that want rasters.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PyQt6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "icons" / "jottr.svg"
SIZES = (16, 32, 48, 64, 128, 256, 512)


def export_size(renderer: QSvgRenderer, size: int, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    if not image.save(str(destination)):
        raise SystemExit(f"Failed to write {destination}")


def export_icns(renderer: QSvgRenderer, destination: Path) -> None:
    try:
        from PIL import Image
    except ImportError:
        print("Pillow not installed; skipping ICNS generation", file=sys.stderr)
        return

    image = QImage(1024, 1024, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, 1024, 1024))
    painter.end()

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.ReadWrite)
    if not image.save(buffer, "PNG"):
        raise SystemExit(f"Failed to encode PNG for {destination}")

    pil_image = Image.open(io.BytesIO(buffer.data().data()))
    destination.parent.mkdir(parents=True, exist_ok=True)
    pil_image.save(str(destination), format="ICNS")
    print(f"Wrote {destination.relative_to(ROOT)}")


def _render_pil_image(renderer: QSvgRenderer, size: int):
    from PIL import Image

    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.ReadWrite)
    if not image.save(buffer, "PNG"):
        raise SystemExit(f"Failed to encode PNG at {size}px")
    return Image.open(io.BytesIO(buffer.data().data())).convert("RGBA")


def export_ico(renderer: QSvgRenderer, destination: Path) -> None:
    try:
        import PIL.Image  # noqa: F401
    except ImportError:
        print("Pillow not installed; skipping ICO generation", file=sys.stderr)
        return

    # Windows explorers and installers use these sizes; 256 is the ICO maximum.
    # Pillow's ICO writer downscales from one source image (append_images is ignored).
    ico_sizes = (16, 32, 48, 64, 128, 256)
    source = _render_pil_image(renderer, 256)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.save(
        str(destination),
        format="ICO",
        sizes=[(size, size) for size in ico_sizes],
    )
    print(f"Wrote {destination.relative_to(ROOT)}")


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

    pkg_icon = ROOT / "src" / "jottr" / "icons" / "jottr.png"
    export_size(renderer, 256, pkg_icon)
    print(f"Wrote {pkg_icon.relative_to(ROOT)}")

    icns_path = ROOT / "src" / "jottr" / "jottr_icon.icns"
    export_icns(renderer, icns_path)

    ico_path = ROOT / "src" / "jottr" / "jottr_icon.ico"
    export_ico(renderer, ico_path)

    _ = app
    return 0


if __name__ == "__main__":
    sys.exit(main())
