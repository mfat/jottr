"""Helpers for selecting built-in Qt widget styles (Fusion, Windows, Darkly, …)."""

from PyQt6.QtWidgets import QApplication, QStyleFactory

SYSTEM_QT_STYLE = "System"

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


def capture_platform_qt_style(application=None):
    """Remember the style Qt chose before any user override."""
    global _platform_style_key
    if _platform_style_key is not None:
        return _platform_style_key

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


def creatable_qt_style_keys():
    """All style keys Qt can create on this platform (built-in and plugins)."""
    found = {}
    candidates = list(QStyleFactory.keys()) + list(KNOWN_QT_STYLE_KEYS)
    for candidate in candidates:
        key = _canonical_style_key(candidate)
        if key:
            found[key.casefold()] = key
    return sorted(found.values(), key=str.casefold)


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


def apply_qt_style(style_name, application=None):
    """Apply a Qt style by name. System restores the captured platform style."""
    app = application or QApplication.instance()
    if app is None:
        return None

    capture_platform_qt_style(app)
    resolved = normalize_qt_style(style_name)
    if resolved == SYSTEM_QT_STYLE:
        key = _platform_style_key or "Fusion"
    else:
        key = resolved

    style = QStyleFactory.create(key)
    if style is None:
        return None
    app.setStyle(style)
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
