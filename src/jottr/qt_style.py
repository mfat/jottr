"""Helpers for selecting built-in Qt widget styles (Fusion, Windows, Darkly, …)."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QCoreApplication, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QStyleOptionMenuItem,
)

SYSTEM_QT_STYLE = "System"

# Breeze sizes submenu rows so tightly that the ▶ overlaps the label.
_BREEZE_SUBMENU_EXTRA_WIDTH = 16


class _BreezeSubmenuPadStyle(QProxyStyle):
    """Widen Breeze submenu items so the arrow clears the label text."""

    def sizeFromContents(self, ct, opt, size, widget=None):
        size = super().sizeFromContents(ct, opt, size, widget)
        if (
            ct == QStyle.ContentsType.CT_MenuItem
            and isinstance(opt, QStyleOptionMenuItem)
            and opt.menuItemType == QStyleOptionMenuItem.MenuItemType.SubMenu
        ):
            size.setWidth(size.width() + _BREEZE_SUBMENU_EXTRA_WIDTH)
        return size

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
    for key in creatable_qt_style_keys():
        if key.casefold() == current.casefold():
            _platform_style_key = key
            break
    else:
        _platform_style_key = current or "Fusion"
    return _platform_style_key


def _canonical_style_key(candidate):
    """Return a display key if Qt can create the style, else None."""
    name = (candidate or "").strip()
    if not name:
        return None
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
    for key in creatable_qt_style_keys():
        if key.casefold() == name.casefold():
            return key
    created = _canonical_style_key(name)
    return created or SYSTEM_QT_STYLE


def apply_qt_color_scheme(scheme_name, application=None):
    """Apply Qt::ColorScheme from a System/Light/Dark UI setting.

    ``System`` maps to ``Qt.ColorScheme.Unknown``, which follows the platform
    appearance (see QStyleHints::setColorScheme).
    """
    from jottr.theme_manager import ThemeManager

    app = application or QGuiApplication.instance()
    if app is None:
        return None

    hints = app.styleHints()
    if not hasattr(hints, "setColorScheme"):
        return None

    scheme = ThemeManager.ui_theme_color_scheme(scheme_name)
    hints.setColorScheme(scheme)
    return hints.colorScheme()


def match_style_variant_to_theme(style_key, dark_theme):
    """Map paired light/dark style keys to the variant matching a theme."""
    key = (style_key or "").strip()
    if not key:
        return key

    available = {name.casefold(): name for name in creatable_qt_style_keys()}
    for light_name, dark_name in STYLE_VARIANT_PAIRS:
        light_key = available.get(light_name.casefold())
        dark_key = available.get(dark_name.casefold())
        if key.casefold() not in {light_name.casefold(), dark_name.casefold()}:
            continue
        preferred = dark_key if dark_theme else light_key
        return preferred or light_key or dark_key or key
    return key


def resolve_qt_style_key(style_name, theme=None):
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

    key = resolve_qt_style_key(style_name, theme=theme)
    # style().objectName() is not reliable across platforms (often empty),
    # so remember the key we applied on the application object itself.
    if app.property("_jottr_style_key") == key:
        # Re-apply when a prior setStyle("Breeze") dropped our submenu pad proxy.
        if key.casefold() != "breeze" or isinstance(
            getattr(app, "_jottr_style_proxy", None), _BreezeSubmenuPadStyle
        ):
            return key
    # Prefer the QString overload like KStyleManager::initStyle
    # (QApplication::setStyle(styleToUse)). Probe creatable first so we
    # do not leave the app on a failed override.
    style = QStyleFactory.create(key)
    if style is None:
        return None
    # Breeze under-reserves width for submenu arrows; pad only that style.
    # Keep a Python reference: setStyle takes C++ ownership, but PyQt still
    # GC's the wrapper and then virtual overrides (sizeFromContents) vanish.
    if key.casefold() == "breeze":
        proxy = _BreezeSubmenuPadStyle(style)
        app._jottr_style_proxy = proxy
        app.setStyle(proxy)
    else:
        app._jottr_style_proxy = None
        app.setStyle(key)
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
