"""Portal-aware file dialogs for Flatpak and other sandboxed desktops.

Do **not** call ``org.freedesktop.portal.FileChooser`` over D-Bus directly.
Qt's xdg-desktop-portal platform theme does that when ``QFileDialog`` uses the
native dialog (the default). Forcing ``DontUseNativeDialog`` bypasses the
portal and breaks sandboxed open/save.

See Flatpak's Qt portal guidance:
https://docs.flatpak.org/en/latest/portals.html
"""

from __future__ import annotations

import os
import sys

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QFileDialog, QWidget

PLATFORM_THEME_VARIABLE = "QT_QPA_PLATFORMTHEME"
PORTAL_PLATFORM_THEME = "xdgdesktopportal"


def use_portal_file_dialogs(environ=None, platform=None) -> bool:
    """Ask Qt for the desktop portal's file dialogs; call before QApplication.

    Qt only picks its xdgdesktopportal platform theme inside Flatpak and Snap.
    Elsewhere on GNOME it loads the GTK3 theme, which draws GTK3's older file
    chooser. The portal theme wraps the desktop's usual theme, and Qt falls
    back to that theme when the plugin is not installed. A theme the user
    chose is kept, and Plasma's own theme already shows KDE's dialogs.
    Returns True when the portal theme was requested.
    """
    environ = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    if not platform.startswith("linux") or environ.get(PLATFORM_THEME_VARIABLE):
        return False
    desktops = environ.get("XDG_CURRENT_DESKTOP", "").casefold().split(":")
    if "kde" in desktops:
        return False
    environ[PLATFORM_THEME_VARIABLE] = PORTAL_PLATFORM_THEME
    return True


def is_flatpak() -> bool:
    """Whether Jottr runs inside a Flatpak sandbox."""
    return bool(os.environ.get("FLATPAK_ID")) or os.path.exists("/.flatpak-info")


def default_save_directory() -> str:
    """Folder Save dialogs start in for documents that were never saved.

    The user's Documents folder, or home when it cannot be determined or does
    not exist. Inside Flatpak the portal file chooser picks the folder, since
    the sandbox cannot see the host's Documents folder; returns "".
    """
    if is_flatpak():
        return ""
    documents = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    if documents and os.path.isdir(documents):
        return documents
    return os.path.expanduser("~")


def get_open_file_name(
    parent: QWidget | None,
    caption: str,
    directory: str = "",
    name_filter: str = "",
    initial_filter: str = "",
) -> tuple[str, str]:
    """Open-file chooser via the native/portal dialog."""
    if initial_filter:
        return QFileDialog.getOpenFileName(
            parent, caption, directory, name_filter, initial_filter
        )
    return QFileDialog.getOpenFileName(parent, caption, directory, name_filter)


def get_save_file_name(
    parent: QWidget | None,
    caption: str,
    directory: str = "",
    name_filter: str = "",
    initial_filter: str = "",
) -> tuple[str, str]:
    """Save-file chooser via the native/portal dialog."""
    if initial_filter:
        return QFileDialog.getSaveFileName(
            parent, caption, directory, name_filter, initial_filter
        )
    return QFileDialog.getSaveFileName(parent, caption, directory, name_filter)


def get_existing_directory(
    parent: QWidget | None,
    caption: str,
    directory: str = "",
) -> str:
    """Directory chooser via the native/portal dialog."""
    return QFileDialog.getExistingDirectory(parent, caption, directory)
