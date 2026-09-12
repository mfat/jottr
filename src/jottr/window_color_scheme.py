"""KDE Window Color Scheme support (Kate / KColorSchemeManager equivalent).

Discovers ``*.colors`` files from XDG data dirs, builds a QPalette like
``KColorScheme::createApplicationPalette``, and provides preview icons like
``KColorSchemeMenu``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QStandardPaths, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import QApplication

DEFAULT_WINDOW_COLOR_SCHEME = ""  # Kate "Default" — follow system / automatic

# Process-lifetime cache: scheme files rarely change while the app is open, and
# find/effective_chrome_theme used to re-scan every .colors file per icon tint.
_schemes_cache: tuple[WindowColorSchemeInfo, ...] | None = None
_effective_chrome_cache: dict[tuple[str, str], dict] = {}


def clear_window_color_scheme_caches():
    """Drop cached scheme lists / chrome themes (tests or on-disk changes)."""
    global _schemes_cache
    _schemes_cache = None
    _effective_chrome_cache.clear()


def clear_effective_chrome_theme_cache():
    """Drop chrome QSS theme cache after palette / UI theme changes."""
    _effective_chrome_cache.clear()


@dataclass(frozen=True)
class WindowColorSchemeInfo:
    """One entry in the Window Color Scheme menu."""

    scheme_id: str  # e.g. "BreezeDark"; empty for Default
    name: str
    path: str  # empty for Default


def _parse_rgb(value, fallback=None):
    text = str(value or "").strip()
    if not text:
        return QColor(fallback) if fallback is not None else QColor()
    parts = [part.strip() for part in text.split(",")]
    if len(parts) >= 3:
        try:
            color = QColor(int(parts[0]), int(parts[1]), int(parts[2]))
            if color.isValid():
                return color
        except ValueError:
            pass
    color = QColor(text)
    if color.isValid():
        return color
    return QColor(fallback) if fallback is not None else QColor()


def _read_colors_file(path):
    """Parse a KDE ``.colors`` file into section → key → value maps."""
    sections: dict[str, dict[str, str]] = {}
    current = None
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return sections
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            sections.setdefault(current, {})
            continue
        if current is None or "=" not in line:
            continue
        key, _, value = line.partition("=")
        sections[current][key.strip()] = value.strip()
    return sections


def _group_color(sections, group, key, fallback):
    return _parse_rgb(sections.get(group, {}).get(key), fallback)


def discover_window_color_schemes():
    """Return Default + all ``*.colors`` schemes (user overrides system)."""
    global _schemes_cache
    if _schemes_cache is not None:
        return list(_schemes_cache)

    found: dict[str, WindowColorSchemeInfo] = {}
    roots = QStandardPaths.locateAll(
        QStandardPaths.StandardLocation.GenericDataLocation,
        "color-schemes",
        QStandardPaths.LocateOption.LocateDirectory,
    )
    for root in roots:
        directory = Path(root)
        if not directory.is_dir():
            continue
        try:
            files = sorted(directory.glob("*.colors"))
        except OSError:
            continue
        for path in files:
            scheme_id = path.stem
            sections = _read_colors_file(path)
            name = sections.get("General", {}).get("Name") or scheme_id
            # Later roots (e.g. $HOME) override earlier system copies.
            found[scheme_id] = WindowColorSchemeInfo(
                scheme_id=scheme_id,
                name=name,
                path=str(path),
            )
    schemes = sorted(found.values(), key=lambda item: item.name.casefold())
    result = [
        WindowColorSchemeInfo(
            scheme_id=DEFAULT_WINDOW_COLOR_SCHEME,
            name="Default",
            path="",
        ),
        *schemes,
    ]
    _schemes_cache = tuple(result)
    return result


def find_window_color_scheme(scheme_id):
    """Return scheme info for *scheme_id*, or Default if missing/empty."""
    wanted = (scheme_id or DEFAULT_WINDOW_COLOR_SCHEME).strip()
    for scheme in discover_window_color_schemes():
        if scheme.scheme_id == wanted:
            return scheme
        if wanted and scheme.scheme_id.casefold() == wanted.casefold():
            return scheme
    return WindowColorSchemeInfo(
        scheme_id=DEFAULT_WINDOW_COLOR_SCHEME,
        name="Default",
        path="",
    )


def normalize_window_color_scheme(scheme_id):
    """Map a saved id to a known scheme id (empty string = Default)."""
    return find_window_color_scheme(scheme_id).scheme_id


def scheme_is_dark(path):
    """True when Window BackgroundNormal is dark."""
    if not path:
        return False
    sections = _read_colors_file(path)
    background = _group_color(
        sections, "Colors:Window", "BackgroundNormal", "#eff0f1"
    )
    return background.isValid() and background.lightnessF() < 0.5


def scheme_preview_colors(path):
    """Return (window, button, view, selection) for Kate-style swatches."""
    resolved = path
    if not resolved:
        auto = automatic_scheme_for_system()
        resolved = auto.path if auto and auto.path else ""
    if not resolved:
        return (
            QColor("#eff0f1"),
            QColor("#fcfcfc"),
            QColor("#fcfcfc"),
            QColor("#3daee9"),
        )
    sections = _read_colors_file(resolved)
    window = _group_color(sections, "Colors:Window", "BackgroundNormal", "#eff0f1")
    button = _group_color(sections, "Colors:Button", "BackgroundNormal", "#fcfcfc")
    view = _group_color(sections, "Colors:View", "BackgroundNormal", "#fcfcfc")
    selection = _group_color(
        sections, "Colors:Selection", "BackgroundNormal", "#3daee9"
    )
    return window, button, view, selection


def create_preview_icon(path, sizes=(16, 24)):
    """4-quadrant preview icon (Window/Button/View/Selection), Kate-style."""
    if not path:
        return QIcon.fromTheme("edit-undo")
    window, button, view, selection = scheme_preview_colors(path)
    icon = QIcon()
    for size in sizes:
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.black)
        painter = QPainter(pix)
        half = size // 2 - 1
        painter.fillRect(1, 1, half, half, window)
        painter.fillRect(1 + half, 1, half, half, button)
        painter.fillRect(1, 1 + half, half, half, view)
        painter.fillRect(1 + half, 1 + half, half, half, selection)
        painter.end()
        icon.addPixmap(pix)
    return icon


def _set_role(palette, group, role, color):
    if color is not None and color.isValid():
        palette.setColor(group, role, color)


def create_application_palette(path):
    """Build a QPalette from a ``.colors`` file (Active/Inactive/Disabled)."""
    sections = _read_colors_file(path)
    palette = QPalette()

    window_bg = _group_color(sections, "Colors:Window", "BackgroundNormal", "#eff0f1")
    window_fg = _group_color(sections, "Colors:Window", "ForegroundNormal", "#232629")
    window_alt = _group_color(
        sections, "Colors:Window", "BackgroundAlternate", window_bg.name()
    )
    view_bg = _group_color(sections, "Colors:View", "BackgroundNormal", "#fcfcfc")
    view_fg = _group_color(sections, "Colors:View", "ForegroundNormal", "#232629")
    view_alt = _group_color(
        sections, "Colors:View", "BackgroundAlternate", view_bg.name()
    )
    view_inactive = _group_color(
        sections, "Colors:View", "ForegroundInactive", "#7f8c8d"
    )
    view_link = _group_color(sections, "Colors:View", "ForegroundLink", "#2980b9")
    view_visited = _group_color(
        sections, "Colors:View", "ForegroundVisited", "#7f8c8d"
    )
    button_bg = _group_color(sections, "Colors:Button", "BackgroundNormal", "#fcfcfc")
    button_fg = _group_color(sections, "Colors:Button", "ForegroundNormal", "#232629")
    selection_bg = _group_color(
        sections, "Colors:Selection", "BackgroundNormal", "#3daee9"
    )
    selection_fg = _group_color(
        sections, "Colors:Selection", "ForegroundNormal", "#fcfcfc"
    )
    tooltip_bg = _group_color(
        sections, "Colors:Tooltip", "BackgroundNormal", "#232629"
    )
    tooltip_fg = _group_color(
        sections, "Colors:Tooltip", "ForegroundNormal", "#fcfcfc"
    )

    light = window_bg.lighter(115)
    midlight = window_bg.lighter(107)
    mid = window_alt if window_alt.isValid() else window_bg.darker(110)
    dark = window_fg.darker(150) if window_fg.lightnessF() > 0.5 else window_bg.darker(150)
    shadow = QColor(0, 0, 0)

    for group in (
        QPalette.ColorGroup.Active,
        QPalette.ColorGroup.Inactive,
        QPalette.ColorGroup.Disabled,
    ):
        fg = window_fg
        text = view_fg
        button_text = button_fg
        highlighted = selection_fg
        if group == QPalette.ColorGroup.Disabled:
            fg = view_inactive
            text = view_inactive
            button_text = view_inactive
            highlighted = view_inactive
        _set_role(palette, group, QPalette.ColorRole.Window, window_bg)
        _set_role(palette, group, QPalette.ColorRole.WindowText, fg)
        _set_role(palette, group, QPalette.ColorRole.Base, view_bg)
        _set_role(palette, group, QPalette.ColorRole.AlternateBase, view_alt)
        _set_role(palette, group, QPalette.ColorRole.Text, text)
        _set_role(palette, group, QPalette.ColorRole.Button, button_bg)
        _set_role(palette, group, QPalette.ColorRole.ButtonText, button_text)
        _set_role(palette, group, QPalette.ColorRole.Highlight, selection_bg)
        _set_role(palette, group, QPalette.ColorRole.HighlightedText, highlighted)
        _set_role(palette, group, QPalette.ColorRole.ToolTipBase, tooltip_bg)
        _set_role(palette, group, QPalette.ColorRole.ToolTipText, tooltip_fg)
        _set_role(palette, group, QPalette.ColorRole.PlaceholderText, view_inactive)
        _set_role(palette, group, QPalette.ColorRole.Link, view_link)
        _set_role(palette, group, QPalette.ColorRole.LinkVisited, view_visited)
        _set_role(palette, group, QPalette.ColorRole.Light, light)
        _set_role(palette, group, QPalette.ColorRole.Midlight, midlight)
        _set_role(palette, group, QPalette.ColorRole.Mid, mid)
        _set_role(palette, group, QPalette.ColorRole.Dark, dark)
        _set_role(palette, group, QPalette.ColorRole.Shadow, shadow)
        if hasattr(QPalette.ColorRole, "Accent"):
            _set_role(palette, group, QPalette.ColorRole.Accent, selection_bg)
    return palette


def chrome_theme_from_scheme(path):
    """Build a jottr theme dict for app QSS from a ``.colors`` file."""
    from jottr.theme_manager import ThemeManager

    sections = _read_colors_file(path)
    window_bg = _group_color(sections, "Colors:Window", "BackgroundNormal", "#eff0f1")
    window_fg = _group_color(sections, "Colors:Window", "ForegroundNormal", "#232629")
    window_alt = _group_color(
        sections, "Colors:Window", "BackgroundAlternate", window_bg.name()
    )
    view_bg = _group_color(sections, "Colors:View", "BackgroundNormal", "#fcfcfc")
    view_fg = _group_color(sections, "Colors:View", "ForegroundNormal", "#232629")
    view_inactive = _group_color(
        sections, "Colors:View", "ForegroundInactive", "#7f8c8d"
    )
    selection_bg = _group_color(
        sections, "Colors:Selection", "BackgroundNormal", "#3daee9"
    )
    selection_fg = _group_color(
        sections, "Colors:Selection", "ForegroundNormal", "#fcfcfc"
    )
    border = window_alt if window_alt.isValid() else window_bg.darker(112)
    dark = scheme_is_dark(path)
    base = ThemeManager.get_theme("Black" if dark else "White")
    theme = {
        "name": sections.get("General", {}).get("Name") or Path(path).stem,
        "app": {
            **base["app"],
            "background": window_bg.name(),
            "surface": view_bg.name(),
            "surface_alt": window_alt.name(),
            "surface_active": selection_bg.name(),
            "text": window_fg.name(),
            "muted": view_inactive.name(),
            "accent": selection_bg.name(),
            "accent_text": selection_fg.name(),
            "border": border.name(),
        },
        "editor": {
            **base["editor"],
            "background": view_bg.name(),
            "foreground": view_fg.name(),
            "selection": selection_bg.name(),
        },
        "syntax": base.get("syntax", {}),
    }
    return ThemeManager.normalize_theme(theme) or base


def automatic_scheme_for_system():
    """Kate non-Plasma Default: Breeze Light/Dark when available."""
    from jottr.system_color_scheme import system_prefers_dark

    prefer_dark = system_prefers_dark(QGuiApplication.instance())
    target = "BreezeDark" if prefer_dark else "BreezeLight"
    scheme = find_window_color_scheme(target)
    if scheme.path:
        return scheme
    # Fall back to any dark/light scheme name heuristic.
    for scheme in discover_window_color_schemes():
        if not scheme.path:
            continue
        if scheme_is_dark(scheme.path) == prefer_dark:
            return scheme
    return WindowColorSchemeInfo(
        scheme_id=DEFAULT_WINDOW_COLOR_SCHEME, name="Default", path=""
    )


def activate_window_color_scheme(scheme_id, application=None):
    """Apply Default or a named scheme palette. Returns the resolved info."""
    app = application or QApplication.instance()
    scheme = find_window_color_scheme(scheme_id)
    if app is None:
        return scheme

    if not scheme.path:
        auto = automatic_scheme_for_system()
        if auto.path:
            app.setProperty("KDE_COLOR_SCHEME_PATH", auto.path)
            app.setPalette(create_application_palette(auto.path))
        else:
            app.setProperty("KDE_COLOR_SCHEME_PATH", "")
            style = app.style()
            if style is not None:
                app.setPalette(style.standardPalette())
            else:
                app.setPalette(QPalette())
        return scheme

    app.setProperty("KDE_COLOR_SCHEME_PATH", scheme.path)
    app.setPalette(create_application_palette(scheme.path))
    return scheme


def effective_chrome_theme(scheme_id, ui_theme_name, application=None):
    """Theme dict for jottr chrome QSS under the active Window Color Scheme."""
    from jottr.qt_style import (
        actual_qt_color_scheme,
        reconcile_chrome_theme_with_color_scheme,
    )
    from jottr.system_color_scheme import system_color_scheme
    from jottr.theme_manager import ThemeManager

    normalized = ThemeManager.normalize_ui_theme(ui_theme_name)
    # System resolves through the desktop preference, so key the cache on it
    # too: a host light/dark switch must not be served a stale theme.
    resolved = (
        system_color_scheme(application) if normalized == "System" else None
    )
    # Explicit Light/Dark may be overridden when the platform refuses
    # setColorScheme; cache must follow the scheme styles actually paint with.
    pinned_actual = (
        actual_qt_color_scheme(application)
        if normalized in {"Light", "Dark"}
        else None
    )
    cache_key = (
        (scheme_id or DEFAULT_WINDOW_COLOR_SCHEME).strip(),
        normalized,
        resolved,
        pinned_actual,
    )
    cached = _effective_chrome_cache.get(cache_key)
    if cached is not None:
        return cached

    scheme = find_window_color_scheme(scheme_id)
    if scheme.path:
        theme = chrome_theme_from_scheme(scheme.path)
    else:
        auto = automatic_scheme_for_system()
        if auto.path and normalized == "System":
            theme = chrome_theme_from_scheme(auto.path)
        else:
            theme = ThemeManager.get_ui_theme(ui_theme_name, application)
        # Default scheme + explicit Light/Dark: align with immutable ColorScheme
        # so tab rail / icons do not keep Light surfaces on a dark Adwaita shell.
        theme = reconcile_chrome_theme_with_color_scheme(
            theme, ui_theme_name, application
        )
    _effective_chrome_cache[cache_key] = theme
    return theme
