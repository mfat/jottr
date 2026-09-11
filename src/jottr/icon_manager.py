"""Load and theme bundled symbolic UI icons.

Icons are shipped under ``icons/symbolic/`` (copied from Adwaita symbolic
set). Runtime lookup uses only those files — never the host icon theme.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from jottr.paths import data_roots, find_data_dir

# Logical sizes used by the UI (tabs 16, toolbar 22, menus ~16–24).
_ICON_SIZES = (16, 22, 24, 32)


def resolve_icons_dir() -> str:
    """Return the directory that contains bundled UI icons."""
    for root in data_roots():
        candidate = root / "icons"
        if (candidate / "symbolic").is_dir():
            return str(candidate)
    found = find_data_dir("icons")
    return str(found) if found is not None else os.path.join(os.getcwd(), "icons")


def load_bundled_icon_paths() -> dict[str, str]:
    """Map logical icon names to absolute SVG paths under ``icons/symbolic``."""
    symbolic_dir = os.path.join(resolve_icons_dir(), "symbolic")
    icons: dict[str, str] = {}
    if not os.path.isdir(symbolic_dir):
        return icons

    for filename in os.listdir(symbolic_dir):
        if not filename.endswith(".svg"):
            continue
        name = filename[:-4]
        icons[name] = os.path.join(symbolic_dir, filename)
    return icons


def _device_pixel_ratio() -> float:
    app = QGuiApplication.instance()
    if app is None:
        return 1.0
    return float(app.devicePixelRatio())


def _render_tinted_pixmap(
    renderer: QSvgRenderer,
    logical_size: int,
    color: str,
    dpr: float,
) -> QPixmap:
    """Render SVG at an exact logical size with correct HiDPI backing store."""
    physical = max(1, int(round(logical_size * dpr)))
    pixmap = QPixmap(physical, physical)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    # Prefer sharp edges for symbolic glyphs at small sizes.
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    renderer.render(painter, QRectF(0, 0, physical, physical))
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), QColor(color))
    painter.end()

    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def build_themed_icon(icon_path: str, color: str, size: int | None = None) -> QIcon:
    """Render a monochrome symbolic SVG tinted to ``color``.

    Pixmaps are generated at the UI's logical sizes (and HiDPI DPR) so Qt does
    not soft-scale a single oversized bitmap.
    """
    if not icon_path or not os.path.isfile(icon_path):
        return QIcon()

    with open(icon_path, "rb") as handle:
        svg_data = QByteArray(handle.read())

    renderer = QSvgRenderer(svg_data)
    if not renderer.isValid():
        return QIcon()

    dpr = _device_pixel_ratio()
    sizes = (size,) if size else _ICON_SIZES

    icon = QIcon()
    for logical_size in sizes:
        icon.addPixmap(
            _render_tinted_pixmap(renderer, logical_size, color, dpr),
            QIcon.Mode.Normal,
            QIcon.State.Off,
        )
    return icon
