"""Portal-aware file dialogs for Flatpak and other sandboxed desktops.

Do **not** call ``org.freedesktop.portal.FileChooser`` over D-Bus directly.
Qt's xdg-desktop-portal platform theme does that when ``QFileDialog`` uses the
native dialog (the default). Forcing ``DontUseNativeDialog`` bypasses the
portal and breaks sandboxed open/save.

See Flatpak's Qt portal guidance:
https://docs.flatpak.org/en/latest/portals.html
"""

from __future__ import annotations

from PyQt6.QtWidgets import QFileDialog, QWidget


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
