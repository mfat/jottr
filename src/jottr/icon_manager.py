"""Load and tint bundled UI icon themes.

Only icon packs shipped with Jottr are supported (no host desktop themes).
Each pack is a subdirectory under ``icons/`` with a matching Qt resource prefix
(for example ``icons/symbolic.qrc`` → ``:/icons/symbolic/…``).

``QIcon(":/…svg")`` would use QtSvg's icon engine for scaling, but does not
recolor glyphs for light/dark themes. Monochrome symbolic icons are therefore
rendered with ``QSvgRenderer`` and tinted via ``CompositionMode_SourceIn``.
"""

from __future__ import annotations

import os
from typing import TypedDict

from PyQt6.QtCore import QByteArray, QDir, QFile, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QMessageBox

from jottr.paths import data_roots, find_data_dir, find_data_file

# Logical sizes used by the UI (tabs 16, toolbar 22, menus ~16–24).
_ICON_SIZES = (16, 22, 24, 32)
_APP_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
_ICON_PATH_CACHE: dict[str, dict[str, str]] = {}
_APP_ICON_CACHE: QIcon | None = None
_RESOURCES_LOADED: set[str] = set()

# Logical name aliases applied when a theme does not ship explicit aliases.
_ICON_ALIASES = (
    ("tab-close", "cross-large-square-outline-symbolic"),
    ("snippets", "star-large-symbolic"),
    ("markdown", "eye-outline-filled-symbolic"),
    ("eye", "eye-outline-filled-symbolic"),
    ("font", "large-text-symbolic"),
    ("theme", "preferences-desktop-theme-applications"),
)


class BundledIconTheme(TypedDict):
    id: str
    label: str
    subdir: str
    resource_prefix: str
    resource_module: str


# Only packs listed here appear in Settings. Do not scan the host icon theme.
BUNDLED_ICON_THEMES: tuple[BundledIconTheme, ...] = (
    {
        "id": "bootstrap",
        "label": "Bootstrap",
        "subdir": "bootstrap",
        "resource_prefix": ":/icons/bootstrap",
        "resource_module": "jottr.resources.rc_bootstrap_icons",
    },
    {
        "id": "symbolic",
        "label": "Adwaita",
        "subdir": "symbolic",
        "resource_prefix": ":/icons/symbolic",
        "resource_module": "jottr.resources.rc_symbolic_icons",
    },
)
DEFAULT_ICON_THEME = BUNDLED_ICON_THEMES[0]["id"]


def list_bundled_icon_themes() -> list[BundledIconTheme]:
    """Return the bundled icon themes available in Settings (copy)."""
    return [dict(theme) for theme in BUNDLED_ICON_THEMES]


def bundled_icon_theme(theme_id: str | None = None) -> BundledIconTheme:
    """Return the theme record for *theme_id*, or the default pack."""
    return dict(_theme_record(theme_id))


def normalize_icon_theme(theme_id: str | None) -> str:
    """Map a saved value to a known bundled theme id."""
    wanted = (theme_id or DEFAULT_ICON_THEME).strip()
    if not wanted:
        return DEFAULT_ICON_THEME
    for theme in BUNDLED_ICON_THEMES:
        if theme["id"].casefold() == wanted.casefold():
            return theme["id"]
        if theme["label"].casefold() == wanted.casefold():
            return theme["id"]
    return DEFAULT_ICON_THEME


def resolve_icon_theme_id(settings_manager=None, theme_id: str | None = None) -> str:
    """Resolve the active bundled icon theme from an explicit id or settings."""
    if theme_id is not None:
        return normalize_icon_theme(theme_id)
    if settings_manager is None:
        return DEFAULT_ICON_THEME
    getter = getattr(settings_manager, "get_icon_theme", None)
    if callable(getter):
        return normalize_icon_theme(getter())
    return normalize_icon_theme(
        settings_manager.get_setting("icon_theme", DEFAULT_ICON_THEME)
    )


def _theme_record(theme_id: str | None = None) -> BundledIconTheme:
    resolved = normalize_icon_theme(theme_id)
    for theme in BUNDLED_ICON_THEMES:
        if theme["id"] == resolved:
            return theme
    return BUNDLED_ICON_THEMES[0]


def resolve_app_icon_path() -> str | None:
    """Return the filesystem path of the branded app icon (SVG preferred)."""
    for name in ("jottr.svg", "jottr.png"):
        found = find_data_file("icons", name)
        if found is not None:
            return str(found)
    return None


def load_app_icon() -> QIcon:
    """Load the Jottr application icon for the window and task switcher.

    Prefers ``icons/jottr.svg`` and registers common pixmap sizes so window
    managers pick a sharp raster instead of a tiny default.
    """
    global _APP_ICON_CACHE
    if _APP_ICON_CACHE is not None:
        return QIcon(_APP_ICON_CACHE)

    path = resolve_app_icon_path()
    if not path:
        _APP_ICON_CACHE = QIcon()
        return QIcon(_APP_ICON_CACHE)

    icon = QIcon(path)
    if path.endswith(".svg"):
        renderer = QSvgRenderer(path)
        if renderer.isValid():
            dpr = _device_pixel_ratio()
            for logical in _APP_ICON_SIZES:
                physical = max(1, int(round(logical * dpr)))
                pixmap = QPixmap(physical, physical)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                renderer.render(painter, QRectF(0, 0, physical, physical))
                painter.end()
                pixmap.setDevicePixelRatio(dpr)
                icon.addPixmap(pixmap)

    _APP_ICON_CACHE = icon
    return QIcon(_APP_ICON_CACHE)


def _ensure_resources_registered(theme: BundledIconTheme) -> None:
    """Import the compiled resource module for a bundled icon theme."""
    theme_id = theme["id"]
    if theme_id in _RESOURCES_LOADED:
        return
    try:
        __import__(theme["resource_module"])
    except ImportError:
        return
    _RESOURCES_LOADED.add(theme_id)


def resolve_icons_dir() -> str:
    """Return the directory that contains bundled UI icons (filesystem fallback)."""
    for root in data_roots():
        candidate = root / "icons"
        if any((candidate / theme["subdir"]).is_dir() for theme in BUNDLED_ICON_THEMES):
            return str(candidate)
    found = find_data_dir("icons")
    return str(found) if found is not None else os.path.join(os.getcwd(), "icons")


def _apply_icon_aliases(icons: dict[str, str]) -> dict[str, str]:
    """Fill logical aliases when a theme only ships the source glyph names."""
    for alias, source in _ICON_ALIASES:
        if alias not in icons and source in icons:
            icons[alias] = icons[source]
    return icons


def _load_resource_icon_paths(theme: BundledIconTheme) -> dict[str, str]:
    """Map logical names to ``:/icons/<theme>/….svg`` resource paths."""
    _ensure_resources_registered(theme)
    prefix = theme["resource_prefix"]
    directory = QDir(prefix)
    if not directory.exists():
        return {}

    icons: dict[str, str] = {}
    for filename in directory.entryList(["*.svg"], QDir.Filter.Files):
        name = filename[:-4]
        icons[name] = f"{prefix}/{filename}"
    return _apply_icon_aliases(icons)


def _load_filesystem_icon_paths(theme: BundledIconTheme) -> dict[str, str]:
    """Fallback map when the compiled resource module is unavailable."""
    theme_dir = os.path.join(resolve_icons_dir(), theme["subdir"])
    icons: dict[str, str] = {}
    if not os.path.isdir(theme_dir):
        return icons

    for filename in os.listdir(theme_dir):
        if not filename.endswith(".svg"):
            continue
        name = filename[:-4]
        icons[name] = os.path.join(theme_dir, filename)
    return _apply_icon_aliases(icons)


def load_bundled_icon_paths(theme_id: str | None = None) -> dict[str, str]:
    """Map logical icon names to resource (preferred) or filesystem SVG paths."""
    theme = _theme_record(theme_id)
    icons = _load_resource_icon_paths(theme)
    if icons:
        return icons
    return _load_filesystem_icon_paths(theme)


def bundled_icon_paths(theme_id: str | None = None) -> dict[str, str]:
    """Cached map of logical icon name -> SVG path for a bundled theme."""
    resolved = normalize_icon_theme(theme_id)
    cached = _ICON_PATH_CACHE.get(resolved)
    if cached is None:
        cached = load_bundled_icon_paths(resolved)
        _ICON_PATH_CACHE[resolved] = cached
    return cached


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
    from jottr.window_color_scheme import effective_chrome_theme

    app = effective_chrome_theme(
        settings_manager.get_window_color_scheme(),
        settings_manager.get_ui_theme(),
    )["app"]
    if mode == "light":
        return "#f8f8f2"
    if mode == "dark":
        return "#17202a"
    if mode == "accent":
        return app["accent"]
    return app["text"]


def resolve_icon_mode_colors(
    settings_manager=None,
    palette=None,
) -> tuple[str | None, str | None]:
    """Return ``(selected_color, disabled_color)`` for explicit QIcon modes.

    Qt's default icon engine calls ``QStyle.generatedIconPixmap`` when a mode is
    missing, so styles re-tint Normal pixmaps (and disagree with each other).
    Supplying Selected/Disabled yourself keeps chrome tint stable across
    ``QApplication.setStyle``.
    """
    if palette is not None:
        selected = palette.color(QPalette.ColorRole.HighlightedText).name()
        disabled = palette.color(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.WindowText,
        ).name()
        return selected, disabled
    if settings_manager is None:
        return None, None

    from jottr.window_color_scheme import effective_chrome_theme

    app = effective_chrome_theme(
        settings_manager.get_window_color_scheme(),
        settings_manager.get_ui_theme(),
    )["app"]
    accent = QColor(app["accent"])
    # Flat white/black on accent chips when no widget palette is available.
    selected = "#1a1a1a" if accent.lightnessF() >= 0.55 else "#ffffff"
    return selected, app["muted"]


def themed_symbolic_icon(
    name: str,
    settings_manager=None,
    color: str | None = None,
    size: int | None = None,
    palette=None,
    theme_id: str | None = None,
) -> QIcon:
    """Build a tinted symbolic icon by logical name for windows and dialogs.

    When *palette* is given, Selected/Disabled modes use HighlightedText and
    disabled WindowText so list/menu styles do not invent multi-tone pixmaps.
    With a settings manager (toolbar/chrome), modes use accent contrast + muted.
    """
    if color is None:
        if palette is not None:
            color = palette.color(QPalette.ColorRole.WindowText).name()
        else:
            color = resolve_icon_color(settings_manager)

    selected_color, disabled_color = resolve_icon_mode_colors(
        settings_manager, palette
    )

    resolved_theme = resolve_icon_theme_id(settings_manager, theme_id)
    return build_themed_icon(
        bundled_icon_paths(resolved_theme).get(name, ""),
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
