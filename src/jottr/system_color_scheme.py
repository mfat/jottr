"""Resolve the desktop's light/dark preference, sandboxes included.

``QStyleHints.colorScheme()`` is authoritative whenever Qt's platform theme
knows the answer, but it reports ``Unknown`` when the plugin cannot read the
host configuration. That is the normal case for the Flatpak build: the
``org.kde.Platform`` runtime loads a KDE/generic platform theme that looks for
``kdeglobals`` inside the sandbox, so a GNOME host in dark mode still resolves
as light and the chrome stays light while the rest of the desktop is dark.

So fall back the way portals intend: read ``color-scheme`` from the
``org.freedesktop.appearance`` namespace of ``org.freedesktop.portal.Settings``,
which xdg-desktop-portal exposes to every Flatpak without extra permissions and
which GNOME, Plasma and wlroots portals all implement. If no portal answers,
fall back to the host GTK settings files.

The portal is the operative path inside Flatpak: Flathub's linter rejects every
``--filesystem=xdg-config/<subdir>`` grant but ``kdeglobals:ro``, so the GTK
settings files below are simply not reachable there. They cover unsandboxed
runs on desktops without a portal.
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, pyqtSlot

PORTAL_SERVICE = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
PORTAL_SETTINGS_INTERFACE = "org.freedesktop.portal.Settings"
APPEARANCE_NAMESPACE = "org.freedesktop.appearance"
COLOR_SCHEME_KEY = "color-scheme"

# org.freedesktop.appearance color-scheme values.
PORTAL_NO_PREFERENCE = 0
PORTAL_PREFER_DARK = 1
PORTAL_PREFER_LIGHT = 2

# Portal reads cost a blocking D-Bus round trip; cache until something says the
# preference changed (SettingChanged, or an explicit cache clear in tests).
_portal_scheme_cache: Qt.ColorScheme | None = None
_portal_watcher = None
# What Jottr forced onto QStyleHints, so a read-back of our own override is not
# mistaken for the platform theme having an opinion of its own.
_pinned_scheme: Qt.ColorScheme = Qt.ColorScheme.Unknown


def clear_system_color_scheme_cache():
    """Drop the cached portal answer (SettingChanged, tests, on-disk edits)."""
    global _portal_scheme_cache
    _portal_scheme_cache = None


def note_pinned_color_scheme(scheme):
    """Record a scheme Jottr pinned onto QStyleHints (Unknown clears it).

    ``QStyleHints.colorScheme()`` reports an explicit override in place of the
    platform theme's answer, so without this the pin would be read back as if
    the platform had resolved it — and a later desktop switch would be ignored.
    """
    global _pinned_scheme
    _pinned_scheme = scheme or Qt.ColorScheme.Unknown
    return _pinned_scheme


def pinned_color_scheme():
    """The scheme Jottr pinned onto QStyleHints, or Unknown."""
    return _pinned_scheme


def _scheme_from_portal_value(value):
    """Map an ``org.freedesktop.appearance`` color-scheme value to Qt."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return Qt.ColorScheme.Unknown
    if number == PORTAL_PREFER_DARK:
        return Qt.ColorScheme.Dark
    if number == PORTAL_PREFER_LIGHT:
        return Qt.ColorScheme.Light
    return Qt.ColorScheme.Unknown


def _unwrap_dbus_variant(value, depth=4):
    """Unwrap nested ``QDBusVariant`` payloads (Read returns v<v<u>>)."""
    for _ in range(depth):
        inner = getattr(value, "variant", None)
        if not callable(inner):
            break
        value = inner()
    return value


def portal_color_scheme():
    """Read ``color-scheme`` from the desktop portal (Unknown when absent)."""
    global _portal_scheme_cache
    if _portal_scheme_cache is not None:
        return _portal_scheme_cache

    scheme = Qt.ColorScheme.Unknown
    try:
        from PyQt6.QtDBus import QDBusConnection, QDBusInterface
    except ImportError:
        _portal_scheme_cache = scheme
        return scheme

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        _portal_scheme_cache = scheme
        return scheme

    interface = QDBusInterface(
        PORTAL_SERVICE, PORTAL_PATH, PORTAL_SETTINGS_INTERFACE, bus
    )
    if not interface.isValid():
        _portal_scheme_cache = scheme
        return scheme

    # ReadOne is the version 2 entry point; Read is the older one and returns
    # the value wrapped in an extra variant.
    for method in ("ReadOne", "Read"):
        reply = interface.call(method, APPEARANCE_NAMESPACE, COLOR_SCHEME_KEY)
        arguments = reply.arguments() if reply is not None else []
        if not arguments:
            continue
        scheme = _scheme_from_portal_value(_unwrap_dbus_variant(arguments[0]))
        if scheme != Qt.ColorScheme.Unknown:
            break

    _portal_scheme_cache = scheme
    return scheme


def _gtk_settings_files():
    """Candidate GTK settings.ini paths, newest toolkit version first."""
    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    root = Path(config_home)
    return (root / "gtk-4.0" / "settings.ini", root / "gtk-3.0" / "settings.ini")


def gtk_color_scheme():
    """Infer light/dark from GTK settings (host config, then ``GTK_THEME``)."""
    for path in _gtk_settings_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        prefer_dark = None
        theme_name = ""
        for raw in text.splitlines():
            key, _, value = raw.partition("=")
            key = key.strip().casefold()
            value = value.strip()
            if key == "gtk-application-prefer-dark-theme":
                prefer_dark = value.casefold() in {"1", "true", "yes"}
            elif key == "gtk-theme-name":
                theme_name = value.casefold()
        if prefer_dark is not None:
            return Qt.ColorScheme.Dark if prefer_dark else Qt.ColorScheme.Light
        if theme_name:
            return (
                Qt.ColorScheme.Dark
                if theme_name.endswith(("-dark", ":dark"))
                else Qt.ColorScheme.Light
            )

    theme = os.environ.get("GTK_THEME", "").casefold()
    if theme:
        return (
            Qt.ColorScheme.Dark
            if theme.endswith(("-dark", ":dark"))
            else Qt.ColorScheme.Light
        )
    return Qt.ColorScheme.Unknown


def desktop_color_scheme():
    """Light/dark straight from the desktop: portal first, then GTK settings."""
    scheme = portal_color_scheme()
    if scheme != Qt.ColorScheme.Unknown:
        return scheme
    return gtk_color_scheme()


def system_color_scheme(application=None):
    """Return the desktop's Qt.ColorScheme, falling back past the platform theme."""
    from PyQt6.QtGui import QGuiApplication

    app = application or QGuiApplication.instance()
    platform_scheme = Qt.ColorScheme.Unknown
    if app is not None and hasattr(app, "styleHints"):
        platform_scheme = app.styleHints().colorScheme()
    # A scheme we pinned ourselves says nothing new, and would go stale the
    # moment the desktop switched, so re-derive instead of reading it back.
    if platform_scheme not in (Qt.ColorScheme.Unknown, pinned_color_scheme()):
        return platform_scheme

    scheme = desktop_color_scheme()
    if scheme != Qt.ColorScheme.Unknown:
        return scheme
    return platform_scheme


def system_prefers_dark(application=None):
    """True when the desktop asks for dark appearance."""
    return system_color_scheme(application) == Qt.ColorScheme.Dark


def _make_portal_settings_watcher():
    """Build the ``SettingChanged`` receiver (needs QtDBus for the slot type)."""
    from PyQt6.QtDBus import QDBusVariant

    class PortalSettingsWatcher(QObject):
        """Turn portal ``SettingChanged`` broadcasts into Python callbacks."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self._callbacks = []

        def add_callback(self, callback):
            if callback not in self._callbacks:
                self._callbacks.append(callback)

        @pyqtSlot(str, str, QDBusVariant)
        def on_setting_changed(self, namespace, key, _value):
            if namespace != APPEARANCE_NAMESPACE or key != COLOR_SCHEME_KEY:
                return
            clear_system_color_scheme_cache()
            for callback in list(self._callbacks):
                callback()

    return PortalSettingsWatcher()


def connect_system_color_scheme_changed(callback, application=None):
    """Call *callback* when the desktop light/dark preference changes.

    Connects Qt's own signal and, because the platform theme may never see the
    change in a sandbox, the portal's ``SettingChanged`` broadcast as well.
    Returns the sources that were connected.
    """
    global _portal_watcher
    from PyQt6.QtGui import QGuiApplication

    connected = []

    app = application or QGuiApplication.instance()
    if app is not None and hasattr(app, "styleHints"):
        signal = getattr(app.styleHints(), "colorSchemeChanged", None)
        if signal is not None:
            def on_qt_scheme_changed(*_args):
                clear_system_color_scheme_cache()
                callback()

            signal.connect(on_qt_scheme_changed)
            connected.append("styleHints")

    try:
        from PyQt6.QtDBus import QDBusConnection
    except ImportError:
        return connected

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return connected

    if _portal_watcher is None:
        watcher = _make_portal_settings_watcher()
        if not bus.connect(
            "",
            PORTAL_PATH,
            PORTAL_SETTINGS_INTERFACE,
            "SettingChanged",
            watcher.on_setting_changed,
        ):
            return connected
        _portal_watcher = watcher
    _portal_watcher.add_callback(callback)
    connected.append("portal")
    return connected
