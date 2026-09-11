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
from PyQt6.QtWebEngineWidgets import QWebEngineView

from jottr.font_dialog import FontSelectionDialog
from jottr.theme_manager import ThemeManager
from jottr.ui import LeftAlignedDocumentTabBar, WorkspaceFileSystemModel, WorkspaceTreeView
from jottr.window import (
    APP_HOMEPAGE,
    APP_NAME,
    APP_VERSION,
    TextEditorApp,
)


def warmup_webengine(parent):
    """Force WebEngine/OpenGL init before the window is mapped.

    Qt6 switches the window into an OpenGL-compatible compositing path the first
    time a QWebEngineView becomes visible. Doing that after show() briefly blanks
    the whole UI (felt as a reload). Warming up off-screen avoids that flash on
    the first browser search / markdown preview.
    """
    warmup = QWebEngineView(parent)
    warmup.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    warmup.resize(1, 1)
    warmup.show()
    parent._webengine_gl_warmup = warmup

    def cleanup():
        view = getattr(parent, "_webengine_gl_warmup", None)
        if view is None:
            return
        parent._webengine_gl_warmup = None
        view.deleteLater()

    QTimer.singleShot(0, cleanup)


def main():
    # Share GL contexts for Qt WebEngine (must be set before QApplication).
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    # Create application instance
    app = QApplication(sys.argv)
    
    # Set application metadata
    app.setApplicationName("Jottr")
    app.setApplicationDisplayName("Jottr")
    app.setDesktopFileName("jottr")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationDomain("github.com/mfat/jottr")
    
    # Get file paths from command-line arguments
    file_paths = []
    if len(sys.argv) > 1:
        file_paths = [arg for arg in sys.argv[1:] if os.path.isfile(arg)]
    
    # Create main window and warm WebEngine before mapping the window.
    window = TextEditorApp()
    warmup_webengine(window)
    window.show()
    
    # Open files from command line
    for file_path in file_paths:
        window.open_file(file_path)
    
    return app.exec()

if __name__ == "__main__":
    main() 
