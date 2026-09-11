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

from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox
from PyQt6.QtGui import QFont

from jottr.font_dialog import FontSelectionDialog
from jottr.theme_manager import ThemeManager
from jottr.ui import LeftAlignedDocumentTabBar, WorkspaceFileSystemModel, WorkspaceTreeView
from jottr.window import (
    APP_HOMEPAGE,
    APP_NAME,
    APP_VERSION,
    TextEditorApp,
)


def main():
    # Enable high DPI scaling
    # Qt 6 enables high-DPI scaling by default.
    
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
    
    # Create main window
    window = TextEditorApp()
    window.show()
    
    # Open files from command line
    for file_path in file_paths:
        window.open_file(file_path)
    
    return app.exec()

if __name__ == "__main__":
    main() 
