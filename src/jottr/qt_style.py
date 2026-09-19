"""Helpers for selecting built-in Qt widget styles (Fusion, Windows, Darkly, …)."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QStyleFactory

SYSTEM_QT_STYLE = "System"

# Styles that ship paired light/dark plugins. UI themes must use the matching
# variant or light chrome can end up with dark palette text (unreadable).
STYLE_VARIANT_PAIRS = (
    ("Adwaita", "Adwaita-Dark"),
    ("Adwaita-HighContrast", "Adwaita-HighContrastInverse"),
    ("HighContrast", "HighContrastInverse"),
)

# Documented Qt built-ins plus common plugin keys. Merged with QStyleFactory.keys()
# so every creatable style is offered even if a platform omits one from keys().
KNOWN_QT_STYLE_KEYS = (
    "Fusion",
    "Windows",
    "WindowsVista",
    "windows11",
    "macos",
    "Macintosh",
    "Oxygen",
    "Breeze",
    "Darkly",  # https://github.com/Bali10050/Darkly
    "Lightly",
    "GTK+",
    "kvantum",
    "qt5ct-style",
)

_platform_style_key = None
_bundled_plugins_registered = False


def bundled_qt_plugin_roots() -> list[Path]:
    """Candidate directories that may contain styles/ for optional Qt plugins."""
    from jottr.paths import data_roots, package_dir

    roots: list[Path] = []
    for base in (package_dir(), *data_roots()):
        roots.append(base / "qt_plugins")
        roots.append(base / "plugins")
        roots.append(base)

    # Common Flatpak / prefix installs of style plugins.
    for extra in (
        Path("/app/lib/plugins"),
        Path("/app/lib/qt6/plugins"),
        Path("/app/lib64/qt6/plugins"),
    ):
        roots.append(extra)

    ordered: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered


def register_bundled_qt_plugins() -> list[str]:
    """Register package-local Qt plugin paths when present.

    Safe to call before or after QApplication; missing trees are ignored.
    """
    global _bundled_plugins_registered
    registered: list[str] = []
    existing = {Path(p) for p in QCoreApplication.libraryPaths()}
    for root in bundled_qt_plugin_roots():
        styles_dir = root / "styles"
        if not styles_dir.is_dir():
            continue
        try:
            if not any(styles_dir.iterdir()):
                continue
        except OSError:
            continue
        path = str(root)
        if Path(path) in existing:
            registered.append(path)
            continue
        QCoreApplication.addLibraryPath(path)
        existing.add(Path(path))
        registered.append(path)
    _bundled_plugins_registered = True
    return registered


def capture_platform_qt_style(application=None):
    """Remember the style Qt chose before any user override."""
    global _platform_style_key
    if _platform_style_key is not None:
        return _platform_style_key

    register_bundled_qt_plugins()

    app = application or QApplication.instance()
    if app is None or app.style() is None:
        return None

    current = (app.style().objectName() or "").strip()
    # Prefer QStyleFactory.keys() only — creatable_qt_style_keys() instantiates
    # every plugin and must stay off the startup path.
    key = _matching_style_key(current, QStyleFactory.keys()) if current else None
    _platform_style_key = key or current or "Fusion"
    return _platform_style_key


def _matching_style_key(name, keys):
    """Return the entry of *keys* equal to *name* ignoring case, else None."""
    folded = name.casefold()
    return next((key for key in keys if key.casefold() == folded), None)


# Style name -> result of _canonical_style_key. Each probe instantiates a
# style object, and the available styles do not change at runtime.
_canonical_style_key_cache = {}


def _canonical_style_key(candidate):
    """Return a display key if Qt can create the style, else None."""
    name = (candidate or "").strip()
    if not name:
        return None
    if name not in _canonical_style_key_cache:
        _canonical_style_key_cache[name] = _probe_style_key(name)
    return _canonical_style_key_cache[name]


def _probe_style_key(name):
    style = QStyleFactory.create(name)
    if style is None:
        return None
    for key in QStyleFactory.keys():
        if key.casefold() == name.casefold():
            return key
    object_name = (style.objectName() or "").strip()
    if object_name:
        for key in QStyleFactory.keys():
            if key.casefold() == object_name.casefold():
                return key
        return object_name[0].upper() + object_name[1:] if object_name else name
    return name


_creatable_style_keys_cache = None


def creatable_qt_style_keys():
    """All style keys Qt can create on this platform (built-in and plugins).

    Each probe instantiates a style object, so the result is cached; the
    available styles do not change at runtime.
    """
    global _creatable_style_keys_cache
    if _creatable_style_keys_cache is not None:
        return list(_creatable_style_keys_cache)
    found = {}
    candidates = list(QStyleFactory.keys()) + list(KNOWN_QT_STYLE_KEYS)
    for candidate in candidates:
        key = _canonical_style_key(candidate)
        if key:
            found[key.casefold()] = key
    _creatable_style_keys_cache = sorted(found.values(), key=str.casefold)
    return list(_creatable_style_keys_cache)


def available_qt_styles():
    """Return System plus every creatable Qt style on this platform."""
    return [SYSTEM_QT_STYLE, *creatable_qt_style_keys()]


def normalize_qt_style(style_name):
    """Map a saved value to System or a creatable factory key."""
    name = (style_name or SYSTEM_QT_STYLE).strip()
    if not name or name.casefold() == SYSTEM_QT_STYLE.casefold():
        return SYSTEM_QT_STYLE
    # Saved styles are nearly always keys the factory lists; probe just that
    # one instead of every installed style plugin.
    listed = _matching_style_key(name, QStyleFactory.keys())
    if listed and _canonical_style_key(listed) == listed:
        return listed
    # Probe this name alone before enumerating every installed style plugin.
    created = _canonical_style_key(name)
    if created:
        return created
    key = _matching_style_key(name, creatable_qt_style_keys())
    return key or SYSTEM_QT_STYLE


def apply_qt_color_scheme(scheme_name, application=None):
    """Apply Qt::ColorScheme from a System/Light/Dark UI setting.

    ``System`` follows the desktop portal (then GTK), not Qt's platform theme.
    Native GNOME Wayland and the Flatpak KDE runtime both mis-report Light or
    Unknown while the session is dark; pinning the portal answer keeps Adwaita
    and chrome aligned. When the desktop has no opinion, ``Unknown`` leaves
    the widget style on Qt's platform default.

    Some platform themes (notably org.kde.Platform under a dark GNOME host)
    ignore ``setColorScheme(Light)``. Callers must then align chrome and paired
    styles via ``reconcile_chrome_theme_with_color_scheme``.
    """
    from jottr.system_color_scheme import (
        desktop_color_scheme,
        note_pinned_color_scheme,
    )
    from jottr.theme_manager import ThemeManager

    app = application or QGuiApplication.instance()
    if app is None:
        return None

    hints = app.styleHints()
    if not hasattr(hints, "setColorScheme"):
        return None

    scheme = ThemeManager.ui_theme_color_scheme(scheme_name)
    pinned = Qt.ColorScheme.Unknown
    if scheme == Qt.ColorScheme.Unknown:
        pinned = desktop_color_scheme()
        if pinned != Qt.ColorScheme.Unknown:
            scheme = pinned
    note_pinned_color_scheme(pinned)
    hints.setColorScheme(scheme)
    return hints.colorScheme()


def actual_qt_color_scheme(application=None):
    """Return the ColorScheme QStyleHints currently reports, or Unknown."""
    app = application or QGuiApplication.instance()
    if app is None or not hasattr(app, "styleHints"):
        return Qt.ColorScheme.Unknown
    return app.styleHints().colorScheme()


def reconcile_chrome_theme_with_color_scheme(theme, scheme_setting, application=None):
    """Align chrome colors when the platform refuses an explicit Light/Dark pin.

    Adwaita (and other paired styles) paint from ``QStyleHints.colorScheme()``.
    If the user picks Light chrome while the platform keeps Dark — common in the
    Flatpak/KDE runtime on a dark GNOME host — light backgrounds get light text.
    Prefer the scheme the style will actually use.
    """
    from jottr.theme_manager import ThemeManager

    requested = ThemeManager.ui_theme_color_scheme(scheme_setting)
    if requested not in (Qt.ColorScheme.Light, Qt.ColorScheme.Dark):
        return theme

    actual = actual_qt_color_scheme(application)
    if actual not in (Qt.ColorScheme.Light, Qt.ColorScheme.Dark):
        return theme
    if actual == requested:
        return theme

    forced = "Dark" if actual == Qt.ColorScheme.Dark else "Light"
    return ThemeManager.get_ui_theme(forced, application)


def match_style_variant_to_theme(style_key, dark_theme):
    """Map paired light/dark style keys to the variant matching a theme."""
    key = (style_key or "").strip()
    if not key:
        return key

    folded = key.casefold()
    for light_name, dark_name in STYLE_VARIANT_PAIRS:
        if folded not in {light_name.casefold(), dark_name.casefold()}:
            continue
        # Probe only the pair — avoid creatable_qt_style_keys() on startup.
        light_key = _canonical_style_key(light_name)
        dark_key = _canonical_style_key(dark_name)
        preferred = dark_key if dark_theme else light_key
        return preferred or light_key or dark_key or key
    return key


def resolve_qt_style_key(style_name, theme=None, application=None):
    """Resolve System/user style, then pick light/dark variant for the UI theme."""
    capture_platform_qt_style()
    resolved = normalize_qt_style(style_name)
    if resolved == SYSTEM_QT_STYLE:
        key = _platform_style_key or "Fusion"
    else:
        key = resolved

    if theme is None:
        return key

    from jottr.theme_manager import ThemeManager

    return match_style_variant_to_theme(key, ThemeManager.theme_is_dark(theme))


def apply_qt_style(style_name, application=None, theme=None):
    """Apply a Qt style by name. System restores the captured platform style.

    When *theme* is provided, paired light/dark styles switch to the matching
    plugin so controls stay readable with the UI theme palette.
    """
    app = application or QApplication.instance()
    if app is None:
        return None

    key = resolve_qt_style_key(style_name, theme=theme, application=app)
    # style().objectName() is not reliable across platforms (often empty),
    # so remember the key we applied on the application object itself.
    if app.property("_jottr_style_key") == key:
        return key
    current_name = (app.style().objectName() or "").strip() if app.style() else ""
    if (
        app.property("_jottr_style_key") is None
        and _platform_style_key
        and key.casefold() == _platform_style_key.casefold()
        and (not current_name or current_name.casefold() == _platform_style_key.casefold())
    ):
        app.setProperty("_jottr_style_key", key)
        return key
    # Prefer the QString overload like KStyleManager::initStyle. setStyle
    # returns None when the key is unknown; do not pre-create the style
    # (that would instantiate it twice).
    style = app.setStyle(key)
    if style is None:
        return None
    app.setProperty("_jottr_style_key", key)
    return key


def refresh_styled_widgets(application=None):
    """Force existing widgets to repaint with the active QStyle and palette."""
    app = application or QApplication.instance()
    if app is None or app.style() is None:
        return
    style = app.style()
    for widget in app.allWidgets():
        style.unpolish(widget)
        style.polish(widget)
        widget.update()


def apply_startup_app_chrome(application, settings_manager):
    """Apply widget style, color scheme, and chrome QSS before the main window.

    Doing this on the QApplication means the window is born into the right
    style and avoids a second full stylesheet/repolish pass in
    ``TextEditorApp.apply_app_style``.
    """
    from jottr.theme_manager import ThemeManager
    from jottr.window_color_scheme import (
        activate_window_color_scheme,
        effective_chrome_theme,
        find_window_color_scheme,
        scheme_is_dark,
    )

    if application is None or settings_manager is None:
        return None

    scheme_setting = settings_manager.get_ui_theme()
    window_scheme_id = settings_manager.get_window_color_scheme()
    window_scheme = find_window_color_scheme(window_scheme_id)
    theme = effective_chrome_theme(window_scheme_id, scheme_setting, application)

    if window_scheme.path:
        color_scheme_setting = "Dark" if scheme_is_dark(window_scheme.path) else "Light"
        apply_qt_color_scheme(color_scheme_setting, application)
    else:
        color_scheme_setting = scheme_setting
        apply_qt_color_scheme(scheme_setting, application)
        theme = reconcile_chrome_theme_with_color_scheme(
            theme, color_scheme_setting, application
        )

    apply_qt_style(settings_manager.get_qt_style(), application, theme=theme)
    activate_window_color_scheme(window_scheme_id, application)
    if not window_scheme.path:
        ThemeManager.apply_app_palette(application, theme)

    app_font = settings_manager.get_font("ui")
    application.setFont(app_font)
    stylesheet = ThemeManager.build_app_stylesheet(
        toolbar_style=settings_manager.get_toolbar_style(),
    )
    application.setStyleSheet(stylesheet)
    application.setProperty("_jottr_startup_stylesheet", stylesheet)
    return stylesheet
