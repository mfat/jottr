"""Jottr application entry point."""
import sys

if sys.version_info < (3, 10):
    print("Error: Python 3.10 or higher is required")
    sys.exit(1)

# Support `python src/jottr/main.py` without an editable install.
if __package__ is None:
    from pathlib import Path

    _src_root = Path(__file__).resolve().parents[1]
    if str(_src_root) not in sys.path:
        sys.path.insert(0, str(_src_root))

import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox
from PyQt6.QtGui import QFont
from PyQt6.QtOpenGLWidgets import QOpenGLWidget

from jottr.font_dialog import FontSelectionDialog
from jottr.icon_manager import load_app_icon
from jottr.qt_style import capture_platform_qt_style, register_bundled_qt_plugins
from jottr.theme_manager import ThemeManager
from jottr.ui import LeftAlignedDocumentTabBar, WorkspaceFileSystemModel, WorkspaceTreeView
from jottr.window import (
    APP_HOMEPAGE,
    APP_NAME,
    APP_VERSION,
    TextEditorApp,
)


def warmup_opengl(parent):
    """Switch the window into OpenGL compositing before it is mapped.

    Qt6 blanks the whole UI the first time a visible QWebEngineView forces an
    OpenGL compositor path. A tiny off-screen QOpenGLWidget does that switch
    cheaply — without starting a second Chromium process at startup.
    """
    warmup = QOpenGLWidget(parent)
    warmup.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    warmup.resize(1, 1)
    warmup.show()
    parent._opengl_gl_warmup = warmup

    def cleanup():
        view = getattr(parent, "_opengl_gl_warmup", None)
        if view is None:
            return
        parent._opengl_gl_warmup = None
        view.deleteLater()

    QTimer.singleShot(0, cleanup)


def main():
    # Share GL contexts for Qt WebEngine (must be set before QApplication).
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    # Register bundled Qt style plugins (Adwaita) before any style lookup.
    register_bundled_qt_plugins()

    # Create application instance
    app = QApplication(sys.argv)
    # Remember the platform style before any user override is applied.
    capture_platform_qt_style(app)
    
    # Set application metadata
    app.setApplicationName("Jottr")
    app.setApplicationDisplayName("Jottr")
    app.setDesktopFileName("jottr")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationDomain("github.com/mfat/jottr")
    app.setWindowIcon(load_app_icon())
    
    # Get file paths from command-line arguments
    file_paths = []
    if len(sys.argv) > 1:
        file_paths = [arg for arg in sys.argv[1:] if os.path.isfile(arg)]
    
    # Create main window and prime OpenGL compositing before mapping.
    window = TextEditorApp()
    warmup_opengl(window)
    window.show()
    
    # Open files from command line
    for file_path in file_paths:
        window.open_file(file_path)
    
    return app.exec()

if __name__ == "__main__":
    main()
