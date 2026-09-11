"""Load and theme bundled symbolic UI icons.

Symbolic SVGs are embedded via the Qt Resource System (``icons/symbolic.qrc``
→ ``jottr.resources.rc_symbolic_icons``) and addressed as ``:/icons/symbolic/…``.
That matches Qt's recommended packaging for always-needed assets and avoids
broken relative paths when freezing or installing.

``QIcon(":/…svg")`` would use QtSvg's icon engine for scaling, but does not
recolor glyphs for light/dark themes. Monochrome symbolic icons are therefore
rendered with ``QSvgRenderer`` and tinted via ``CompositionMode_SourceIn``.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QByteArray, QDir, QFile, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QMessageBox

from jottr.paths import data_roots, find_data_dir

# Logical sizes used by the UI (tabs 16, toolbar 22, menus ~16–24).
_ICON_SIZES = (16, 22, 24, 32)
_ICON_PATH_CACHE: dict[str, str] | None = None
_RESOURCES_LOADED = False


def _ensure_resources_registered() -> None:
    """Import the compiled resource module so ``:/icons/symbolic`` is available."""
    global _RESOURCES_LOADED
    if _RESOURCES_LOADED:
        return
    try:
        from jottr.resources import rc_symbolic_icons  # noqa: F401
    except ImportError:
        pass
    else:
        _RESOURCES_LOADED = True


def resolve_icons_dir() -> str:
    """Return the directory that contains bundled UI icons (filesystem fallback)."""
    for root in data_roots():
        candidate = root / "icons"
        if (candidate / "symbolic").is_dir():
            return str(candidate)
    found = find_data_dir("icons")
    return str(found) if found is not None else os.path.join(os.getcwd(), "icons")


def _load_resource_icon_paths() -> dict[str, str]:
    """Map logical names to ``:/icons/symbolic/….svg`` resource paths."""
    _ensure_resources_registered()
    directory = QDir(":/icons/symbolic")
    if not directory.exists():
        return {}

    icons: dict[str, str] = {}
    for filename in directory.entryList(["*.svg"], QDir.Filter.Files):
        name = filename[:-4]
        icons[name] = f":/icons/symbolic/{filename}"

    # Filesystem-era alias if the .qrc tab-close alias is missing.
    if "tab-close" not in icons and "cross-large-square-outline-symbolic" in icons:
        icons["tab-close"] = icons["cross-large-square-outline-symbolic"]

    return icons


def _load_filesystem_icon_paths() -> dict[str, str]:
    """Fallback map when the compiled resource module is unavailable."""
    symbolic_dir = os.path.join(resolve_icons_dir(), "symbolic")
    icons: dict[str, str] = {}
    if not os.path.isdir(symbolic_dir):
        return icons

    for filename in os.listdir(symbolic_dir):
        if not filename.endswith(".svg"):
            continue
        name = filename[:-4]
        icons[name] = os.path.join(symbolic_dir, filename)

    if "cross-large-square-outline-symbolic" in icons:
        icons["tab-close"] = icons["cross-large-square-outline-symbolic"]

    return icons


def load_bundled_icon_paths() -> dict[str, str]:
    """Map logical icon names to resource (preferred) or filesystem SVG paths."""
    icons = _load_resource_icon_paths()
    if icons:
        return icons
    return _load_filesystem_icon_paths()


def bundled_icon_paths() -> dict[str, str]:
    """Cached map of logical icon name -> SVG path."""
    global _ICON_PATH_CACHE
    if _ICON_PATH_CACHE is None:
        _ICON_PATH_CACHE = load_bundled_icon_paths()
    return _ICON_PATH_CACHE


def resolve_icon_color(settings_manager=None) -> str:
    """Return the tint color for symbolic icons from settings / theme.

    ``icon_contrast`` modes:
    - ``auto``: theme text color (follows light/dark UI themes)
    - ``light`` / ``dark``: fixed high-contrast glyphs
    - ``accent``: theme accent color
    """
    from jottr.theme_manager import ThemeManager

    if settings_manager is None:
        theme = ThemeManager.get_theme(ThemeManager.DEFAULT_THEME_NAME)
        return theme["app"]["text"]

    mode = settings_manager.get_setting("icon_contrast", "auto")
    theme = ThemeManager.get_ui_theme(settings_manager.get_ui_theme())
    app = theme["app"]
    if mode == "light":
        return "#f8f8f2"
    if mode == "dark":
        return "#17202a"
    if mode == "accent":
        return app["accent"]
    return app["text"]


def themed_symbolic_icon(
    name: str,
    settings_manager=None,
    color: str | None = None,
    size: int | None = None,
    palette=None,
) -> QIcon:
    """Build a tinted symbolic icon by logical name for windows and dialogs.

    When *palette* is given, Selected/Disabled modes use HighlightedText and
    disabled WindowText so list/menu styles do not invent multi-tone pixmaps.
    """
    if color is None:
        if palette is not None:
            color = palette.color(QPalette.ColorRole.WindowText).name()
        else:
            color = resolve_icon_color(settings_manager)

    selected_color = None
    disabled_color = None
    if palette is not None:
        selected_color = palette.color(QPalette.ColorRole.HighlightedText).name()
        disabled_color = palette.color(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.WindowText,
        ).name()
    elif settings_manager is not None:
        # Keep Selected flat white/black for contrast on accent chips even when
        # callers do not pass a palette (toolbar stays Normal-only).
        from jottr.theme_manager import ThemeManager

        theme = ThemeManager.get_ui_theme(settings_manager.get_ui_theme())
        accent = QColor(theme["app"]["accent"])
        selected_color = "#1a1a1a" if accent.lightnessF() >= 0.55 else "#ffffff"
        disabled_color = theme["app"]["muted"]

    return build_themed_icon(
        bundled_icon_paths().get(name, ""),
        color,
        size,
        selected_color=selected_color,
        disabled_color=disabled_color,
    )


def settings_manager_from(widget) -> object | None:
    """Walk parents for a settings_manager attribute."""
    current = widget
    while current is not None:
        manager = getattr(current, "settings_manager", None)
        if manager is not None:
            return manager
        parent = getattr(current, "parent", None)
        current = parent() if callable(parent) else None
    return None


def apply_dialog_window_icon(dialog, icon_name: str, settings_manager=None) -> None:
    """Set a dialog's window icon from a bundled symbolic glyph."""
    setter = getattr(dialog, "setWindowIcon", None)
    if not callable(setter):
        return
    manager = settings_manager or settings_manager_from(dialog)
    setter(themed_symbolic_icon(icon_name, manager))


# Standard-button → bundled symbolic name (avoids QStyle / host theme icons).
_MESSAGE_BUTTON_ICONS = {
    QMessageBox.StandardButton.Save: "save",
    QMessageBox.StandardButton.Discard: "user-trash",
    QMessageBox.StandardButton.Cancel: "window-close",
    QMessageBox.StandardButton.Close: "window-close",
    QMessageBox.StandardButton.Open: "open",
}

_MESSAGE_ROLE_ICONS = {
    QMessageBox.Icon.Question: "dialog-question",
    QMessageBox.Icon.Information: "help",
    QMessageBox.Icon.Warning: "dialog-question",
    QMessageBox.Icon.Critical: "dialog-question",
}


def apply_message_box_icons(
    message_box: QMessageBox,
    settings_manager=None,
    *,
    role_icon: str | None = None,
    role_size: int = 48,
    button_size: int = 16,
) -> None:
    """Replace Qt/style icons on a message box with bundled symbolic glyphs."""
    manager = settings_manager or settings_manager_from(message_box)
    icon_name = role_icon or _MESSAGE_ROLE_ICONS.get(
        message_box.icon(), "dialog-question"
    )
    if icon_name:
        role = themed_symbolic_icon(icon_name, manager, size=role_size)
        message_box.setIconPixmap(role.pixmap(QSize(role_size, role_size)))

    apply_dialog_window_icon(message_box, icon_name or "dialog-question", manager)

    for standard, name in _MESSAGE_BUTTON_ICONS.items():
        button = message_box.button(standard)
        if button is not None:
            button.setIcon(themed_symbolic_icon(name, manager, size=button_size))
            button.setIconSize(QSize(button_size, button_size))


def ask_themed_question(
    parent,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton,
    default_button: QMessageBox.StandardButton | None = None,
    settings_manager=None,
) -> QMessageBox.StandardButton:
    """Show a question dialog using bundled icons instead of Qt style icons."""
    manager = settings_manager or settings_manager_from(parent)
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Question)
    box.setStandardButtons(buttons)
    if default_button is not None:
        box.setDefaultButton(default_button)
    apply_message_box_icons(box, manager, role_icon="dialog-question")
    result = box.exec()
    return QMessageBox.StandardButton(result)


def _device_pixel_ratio() -> float:
    app = QGuiApplication.instance()
    if app is None:
        return 1.0
    return float(app.devicePixelRatio())


def _read_svg_bytes(icon_path: str) -> QByteArray | None:
    """Read SVG bytes from a ``:/`` resource or filesystem path."""
    if not icon_path:
        return None

    if icon_path.startswith(":"):
        resource = QFile(icon_path)
        if not resource.open(QFile.OpenModeFlag.ReadOnly):
            return None
        data = resource.readAll()
        resource.close()
        return data if not data.isEmpty() else None

    if not os.path.isfile(icon_path):
        return None
    with open(icon_path, "rb") as handle:
        return QByteArray(handle.read())


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


def build_themed_icon(
    icon_path: str,
    color: str,
    size: int | None = None,
    *,
    selected_color: str | None = None,
    disabled_color: str | None = None,
) -> QIcon:
    """Render a monochrome symbolic SVG tinted to ``color``.

    Pixmaps are generated at the UI's logical sizes (and HiDPI DPR) so Qt does
    not soft-scale a single oversized bitmap. Works with ``:/`` resource paths
    and filesystem paths.

    When *selected_color* / *disabled_color* are set, explicit Selected and
    Disabled mode pixmaps are added so styles do not synthesize multi-tone
    icons from the Normal pixmap.
    """
    svg_data = _read_svg_bytes(icon_path)
    if svg_data is None:
        return QIcon()

    renderer = QSvgRenderer(svg_data)
    if not renderer.isValid():
        return QIcon()

    dpr = _device_pixel_ratio()
    sizes = (size,) if size else _ICON_SIZES

    icon = QIcon()
    for logical_size in sizes:
        normal = _render_tinted_pixmap(renderer, logical_size, color, dpr)
        icon.addPixmap(normal, QIcon.Mode.Normal, QIcon.State.Off)
        icon.addPixmap(normal, QIcon.Mode.Active, QIcon.State.Off)
        if selected_color:
            selected = _render_tinted_pixmap(
                renderer, logical_size, selected_color, dpr
            )
            icon.addPixmap(selected, QIcon.Mode.Selected, QIcon.State.Off)
            icon.addPixmap(selected, QIcon.Mode.Selected, QIcon.State.On)
        if disabled_color:
            disabled = _render_tinted_pixmap(
                renderer, logical_size, disabled_color, dpr
            )
            icon.addPixmap(disabled, QIcon.Mode.Disabled, QIcon.State.Off)
    return icon
