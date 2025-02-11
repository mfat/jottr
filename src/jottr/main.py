import sys
if sys.version_info < (3, 10):
    print("Error: Python 3.10 or higher is required")
    sys.exit(1)

import os
import json
import hashlib
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, 
                            QVBoxLayout, QHBoxLayout, QSplitter, QMenu, QToolBar, QAction, QStyle, QMessageBox, QFontDialog, QStyleFactory, QLabel, QDialog, QSizePolicy)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from editor_tab import EditorTab
from snippet_manager import SnippetManager
from rss_tab import RSSTab
import feedparser
from PyQt5.QtGui import QIcon, QDesktopServices
from theme_manager import ThemeManager
from settings_manager import SettingsManager
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import QByteArray
from settings_dialog import SettingsDialog

# Add vendor directory to path
vendor_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor')
if os.path.exists(vendor_dir):
    sys.path.insert(0, vendor_dir)

# Application constants
APP_NAME = "Jottr"
APP_VERSION = "1.0.0"
APP_HOMEPAGE = "https://github.com/mfat/jottr"

class TextEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize managers first
        self.settings_manager = SettingsManager()
        self.snippet_manager = SnippetManager()
        
        # Create toolbar first before styling
        self.toolbar = self.addToolBar("Main Toolbar")
        
        # Now we can safely set platform style since toolbar exists
        self.setup_platform_style()
        
        # Setup toolbar contents
        self.setup_toolbar()
        
        # Create status bar (simplified)
        self.statusBar = self.statusBar()
        
        # Set initial status message
        self.statusBar.showMessage("Words: 0 | Characters: 0")
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.setStyleSheet("""
            QTabWidget::tab-bar {
                alignment: left;
            }
        """)
        layout.addWidget(self.tab_widget)
        
        # Always restore last session
        self.restore_session()
        
        # Create new tab if no tabs were restored
        if self.tab_widget.count() == 0:
            self.new_editor_tab()
        
    def setup_platform_style(self):
        """Apply platform-specific styling"""
        platform = sys.platform
        
        if platform == 'darwin':  # macOS
            self.setUnifiedTitleAndToolBarOnMac(True)
            if hasattr(self, 'toolbar'):
                self.toolbar.setMovable(False)
                style = """
                    QToolBar {
                        border: none;
                        spacing: 4px;
                        background: transparent;
                    }
                    QToolButton {
                        border: none;
                        border-radius: 4px;
                        padding: 4px;
                    }
                    QToolButton:hover {
                        background-color: rgba(0, 0, 0, 0.1);
                    }
                """
                self.setStyleSheet(style)
        
        elif platform == 'win32':  # Windows
            style = """
                QToolBar {
                    border: none;
                    background: #f0f0f0;
                    spacing: 2px;
                    padding: 2px;
                }
                QToolButton {
                    border: 1px solid transparent;
                    border-radius: 2px;
                    padding: 4px;
                    min-width: 28px;
                    min-height: 28px;
                }
                QToolButton:hover {
                    border-color: #c0c0c0;
                    background-color: #e8e8e8;
                }
            """
            self.setStyleSheet(style)
        
        else:  # Linux/Unix
            # Use minimal styling to preserve system theme
            style = """
                QToolBar {
                    spacing: 2px;
                }
                QToolButton {
                    border-radius: 2px;
                    padding: 4px;
                }
            """
            self.setStyleSheet(style)
            
            # Try to use the system style
            if QStyleFactory.keys():
                system_style = None
                available_styles = QStyleFactory.keys()
                
                # Try to find the best system style
                preferred_styles = ['breeze', 'fusion', 'gtk2', 'oxygen']
                for style_name in preferred_styles:
                    if style_name.lower() in [s.lower() for s in available_styles]:
                        system_style = QStyleFactory.create(style_name)
                        break
                
                # Fallback to the first available style if none of the preferred ones are found
                if not system_style and available_styles:
                    system_style = QStyleFactory.create(available_styles[0])
                
                if system_style:
                    QApplication.setStyle(system_style)
        
    def setup_toolbar(self):
        """Setup toolbar buttons and actions"""
        # Helper function to create themed action
        def create_action(icon_path, fallback_icon, text, shortcut=None, handler=None):
            # Create custom icons for toolbar
            icons = {
                "new": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xNCwySDZDNC44OTU0MzA1LDIgNCwyLjg5NTQzMDUgNCw0VjIwQzQsMjEuMTA0NTY5NSA0Ljg5NTQzMDUsMjIgNiwyMkgxOEMxOS4xMDQ1Njk1LDIyIDIwLDIxLjEwNDU2OTUgMjAsMjBWOEwxNCwyWiIvPjxwb2x5bGluZSBwb2ludHM9IjE0IDIgMTQgOCAyMCA4Ii8+PC9zdmc+",
                "open": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0yMiAxOWEyIDIgMCAwIDEtMiAySDRhMiAyIDAgMCAxLTItMlY1YTIgMiAwIDAgMSAyLTJoNWwyIDNoOWEyIDIgMCAwIDEgMiAyeiI+PC9wYXRoPjwvc3ZnPg==",
                "save": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xOSAyMUg1YTIgMiAwIDAgMS0yLTJWNWEyIDIgMCAwIDEgMi0yaDE0YTIgMiAwIDAgMSAyIDJ2MTRhMiAyIDAgMCAxLTIgMnoiPjwvcGF0aD48cG9seWxpbmUgcG9pbnRzPSIxNyAyMSAxNyAxMyA3IDEzIDcgMjEiPjwvcG9seWxpbmU+PHBvbHlsaW5lIHBvaW50cz0iNyAzIDcgOCAxNSA4Ij48L3BvbHlsaW5lPjwvc3ZnPg==",
                "undo": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0zIDdoNmMyLjc2IDAgNSAyLjI0IDUgNXMtMi4yNCA1LTUgNUg0Ij48L3BhdGg+PHBhdGggZD0iTTMgN2wzLTNNMyA3bDMgMyI+PC9wYXRoPjwvc3ZnPg==",
                "redo": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0yMSA3aC02Yy0yLjc2IDAtNSAyLjI0LTUgNXMyLjI0IDUgNSA1aDUiPjwvcGF0aD48cGF0aCBkPSJNMjEgN2wtMy0zTTIxIDdsLTMgMyI+PC9wYXRoPjwvc3ZnPg==",
                "cut": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxjaXJjbGUgY3g9IjYiIGN5PSI2IiByPSIzIj48L2NpcmNsZT48Y2lyY2xlIGN4PSI2IiBjeT0iMTgiIHI9IjMiPjwvY2lyY2xlPjxsaW5lIHgxPSIyMCIgeTE9IjQiIHgyPSI4LjEyIiB5Mj0iMTUuODgiPjwvbGluZT48bGluZSB4MT0iMTQuNDciIHkxPSIxNC40OCIgeDI9IjIwIiB5Mj0iMjAiPjwvbGluZT48bGluZSB4MT0iOC4xMiIgeTE9IjguMTIiIHgyPSIxMiIgeTI9IjEyIj48L2xpbmU+PC9zdmc+",
                "copy": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxyZWN0IHg9IjkiIHk9IjkiIHdpZHRoPSIxMyIgaGVpZ2h0PSIxMyIgcng9IjIiIHJ5PSIyIj48L3JlY3Q+PHBhdGggZD0iTTUgMTVINGEyIDIgMCAwIDEtMi0yVjRhMiAyIDAgMCAxIDItMmg5YTIgMiAwIDAgMSAyIDJ2MSI+PC9wYXRoPjwvc3ZnPg==",
                "paste": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xNiA0aDJhMiAyIDAgMCAxIDIgMnYxNGEyIDIgMCAwIDEtMiAySDZhMiAyIDAgMCAxLTItMlY2YTIgMiAwIDAgMSAyLTJoMiI+PC9wYXRoPjxyZWN0IHg9IjgiIHk9IjIiIHdpZHRoPSI4IiBoZWlnaHQ9IjQiIHJ4PSIxIiByeT0iMSI+PC9yZWN0Pjwvc3ZnPg==",
                "font": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwb2x5bGluZSBwb2ludHM9IjQgNyAxMCA3IDE2IDcgMjAgNyI+PC9wb2x5bGluZT48bGluZSB4MT0iMTIiIHkxPSI3IiB4Mj0iMTIiIHkyPSIyMCI+PC9saW5lPjwvc3ZnPg==",
                "theme": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xMiAyLjY5bDUuNjYgNS42NmE4IDggMCAxIDEtMTEuMzEgMHoiPjwvcGF0aD48L3N2Zz4=",
                "focus": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik04IDNINWEyIDIgMCAwIDAtMiAydjNtMTggMFY1YTIgMiAwIDAgMC0yLTJoLTNtMCAxOGgzYTIgMiAwIDAgMCAyLTJ2LTNNMyAxNnYzYTIgMiAwIDAgMCAyIDJoMyI+PC9wYXRoPjwvc3ZnPg==",
                "snippets": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxsaW5lIHgxPSI4IiB5MT0iNiIgeDI9IjIxIiB5Mj0iNiI+PC9saW5lPjxsaW5lIHgxPSI4IiB5MT0iMTIiIHgyPSIyMSIgeTI9IjEyIj48L2xpbmU+PGxpbmUgeDE9IjgiIHkxPSIxOCIgeDI9IjIxIiB5Mj0iMTgiPjwvbGluZT48bGluZSB4MT0iMyIgeTE9IjYiIHgyPSIzLjAxIiB5Mj0iNiI+PC9saW5lPjxsaW5lIHgxPSIzIiB5MT0iMTIiIHgyPSIzLjAxIiB5Mj0iMTIiPjwvbGluZT48bGluZSB4MT0iMyIgeTE9IjE4IiB4Mj0iMy4wMSIgeTI9IjE4Ij48L2xpbmU+PC9zdmc+",
                "browser": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxjaXJjbGUgY3g9IjEyIiBjeT0iMTIiIHI9IjEwIj48L2NpcmNsZT48bGluZSB4MT0iMiIgeTE9IjEyIiB4Mj0iMjIiIHkyPSIxMiI+PC9saW5lPjxwYXRoIGQ9Ik0xMiAyYTE1LjMgMTUuMyAwIDAgMSA0IDEwIDE1LjMgMTUuMyAwIDAgMS00IDEwIDE1LjMgMTUuMyAwIDAgMS00LTEwIDE1LjMgMTUuMyAwIDAgMSA0LTEweiI+PC9wYXRoPjwvc3ZnPg==",
                "help": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxjaXJjbGUgY3g9IjEyIiBjeT0iMTIiIHI9IjEwIj48L2NpcmNsZT48cGF0aCBkPSJNOS4wOSA5YTMgMyAwIDAgMSA1LjgzIDFjMCAyLTMgMy0zIDMiPjwvcGF0aD48bGluZSB4MT0iMTIiIHkxPSIxNyIgeDI9IjEyLjAxIiB5Mj0iMTciPjwvbGluZT48L3N2Zz4=",
                "about": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxjaXJjbGUgY3g9IjEyIiBjeT0iMTIiIHI9IjEwIj48L2NpcmNsZT48bGluZSB4MT0iMTIiIHkxPSIxNiIgeDI9IjEyIiB5Mj0iMTIiPjwvbGluZT48bGluZSB4MT0iMTIiIHkxPSI4IiB4Mj0iMTIuMDEiIHkyPSI4Ij48L2xpbmU+PC9zdmc+",
                "ap-newsroom": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik00IDIyaDEyYTIgMiAwIDAgMCAyLTJWOGwtNi02SDRhMiAyIDAgMCAwLTIgMnYxNmEyIDIgMCAwIDAgMiAyeiI+PC9wYXRoPjxwYXRoIGQ9Ik0xNCAydjZoNiI+PC9wYXRoPjxsaW5lIHgxPSI2IiB5MT0iMTIiIHgyPSIxOCIgeTI9IjEyIj48L2xpbmU+PGxpbmUgeDE9IjYiIHkxPSIxNiIgeDI9IjE4IiB5Mj0iMTYiPjwvbGluZT48L3N2Zz4=",
                "ap-pronto": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxwYXRoIGQ9Ik0xNyAzYTIuODI4IDIuODI4IDAgMSAxIDQgNEw3LjUgMjAuNSAyIDIybDEuNS01LjVMMTcgM3oiPjwvcGF0aD48cGF0aCBkPSJNMTUgNWwyIDIiPjwvcGF0aD48L3N2Zz4=",
                "zoom-in": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxjaXJjbGUgY3g9IjExIiBjeT0iMTEiIHI9IjgiPjwvY2lyY2xlPjxsaW5lIHgxPSIyMSIgeTE9IjIxIiB4Mj0iMTYuNjUiIHkyPSIxNi42NSI+PC9saW5lPjxsaW5lIHgxPSIxMSIgeTE9IjgiIHgyPSIxMSIgeTI9IjE0Ij48L2xpbmU+PGxpbmUgeDE9IjgiIHkxPSIxMSIgeDI9IjE0IiB5Mj0iMTEiPjwvbGluZT48L3N2Zz4=",
                "zoom-out": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxjaXJjbGUgY3g9IjExIiBjeT0iMTEiIHI9IjgiPjwvY2lyY2xlPjxsaW5lIHgxPSIyMSIgeTE9IjIxIiB4Mj0iMTYuNjUiIHkyPSIxNi42NSI+PC9saW5lPjxsaW5lIHgxPSI4IiB5MT0iMTEiIHgyPSIxNCIgeTI9IjExIj48L2xpbmU+PC9zdmc+",
                "zoom-reset": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxjaXJjbGUgY3g9IjExIiBjeT0iMTEiIHI9IjgiPjwvY2lyY2xlPjxsaW5lIHgxPSIyMSIgeTE9IjIxIiB4Mj0iMTYuNjUiIHkyPSIxNi42NSI+PC9saW5lPjxsaW5lIHgxPSIxMSIgeTE9IjgiIHgyPSIxMSIgeTI9IjE0Ij48L2xpbmU+PGxpbmUgeDE9IjgiIHkxPSIxMSIgeDI9IjE0IiB5Mj0iMTEiPjwvbGluZT48L3N2Zz4=",
                "settings": "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9ImN1cnJlbnRDb2xvciIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiPjxsaW5lIHgxPSI0IiB5MT0iNiIgeDI9IjIwIiB5Mj0iNiI+PC9saW5lPjxsaW5lIHgxPSI0IiB5MT0iMTIiIHgyPSIyMCIgeTI9IjEyIj48L2xpbmU+PGxpbmUgeDE9IjQiIHkxPSIxOCIgeDI9IjIwIiB5Mj0iMTgiPjwvbGluZT48Y2lyY2xlIGN4PSI4IiBjeT0iNiIgcj0iMiI+PC9jaXJjbGU+PGNpcmNsZSBjeD0iMTYiIGN5PSIxMiIgcj0iMiI+PC9jaXJjbGU+PGNpcmNsZSBjeD0iOCIgY3k9IjE4IiByPSIyIj48L2NpcmNsZT48L3N2Zz4="
            }
            
            if icon_path in icons:
                icon = QIcon()
                pixmap = QPixmap()
                pixmap.loadFromData(QByteArray.fromBase64(icons[icon_path].split(',')[1].encode()))
                icon.addPixmap(pixmap)
            else:
                icon = self.style().standardIcon(fallback_icon)
            
            action = QAction(icon, text, self)
            if shortcut:
                action.setShortcut(shortcut)
            if handler:
                action.triggered.connect(handler)
            return action

        # File operations
        new_action = create_action("new", QStyle.SP_FileIcon, 
                                 "New", "Ctrl+N", self.new_editor_tab)
        self.toolbar.addAction(new_action)
        
        open_action = create_action("open", QStyle.SP_DialogOpenButton,
                                  "Open", "Ctrl+O", self.open_file)
        self.toolbar.addAction(open_action)
        
        save_action = create_action("save", QStyle.SP_DialogSaveButton,
                                  "Save", "Ctrl+S", self.save_file)
        self.toolbar.addAction(save_action)
        
        self.toolbar.addSeparator()
        
        # Edit operations
        undo_action = create_action("undo", QStyle.SP_ArrowBack,
                                  "Undo", "Ctrl+Z", self.undo)
        self.toolbar.addAction(undo_action)
        
        redo_action = create_action("redo", QStyle.SP_ArrowForward,
                                  "Redo", "Ctrl+Shift+Z", self.redo)
        self.toolbar.addAction(redo_action)
        
        self.toolbar.addSeparator()
        
        # Font and Theme
        font_action = create_action("font", QStyle.SP_DesktopIcon, 
                                  "Font", handler=self.show_font_dialog)
        self.toolbar.addAction(font_action)
        
        theme_action = create_action("theme", QStyle.SP_DesktopIcon, 
                                   "Theme", handler=self.show_theme_menu)
        self.toolbar.addAction(theme_action)
        
        # Focus mode
        focus_action = create_action("focus", QStyle.SP_TitleBarMaxButton,
                                   "Focus Mode", handler=self.toggle_focus_mode)
        focus_action.setToolTip("Enter distraction-free writing mode")
        self.toolbar.addAction(focus_action)
        
        self.toolbar.addSeparator()
        
        # View toggles
        snippet_action = create_action("snippets", QStyle.SP_FileDialogListView,
                                     "Snippets", handler=lambda: self.toggle_snippets())
        self.toolbar.addAction(snippet_action)
        
        browser_action = create_action("browser", QStyle.SP_ComputerIcon,
                                     "Browser", handler=lambda: self.toggle_browser())
        self.toolbar.addAction(browser_action)
        
        self.toolbar.addSeparator()
        
        # Zoom controls
        zoom_in_action = create_action("zoom-in", QStyle.SP_TitleBarMaxButton,
                                     "Zoom In", "Ctrl++", self.zoom_in)
        self.toolbar.addAction(zoom_in_action)
        
        zoom_out_action = create_action("zoom-out", QStyle.SP_TitleBarMinButton,
                                      "Zoom Out", "Ctrl+-", self.zoom_out)
        self.toolbar.addAction(zoom_out_action)
        
        zoom_reset_action = create_action("zoom-reset", QStyle.SP_TitleBarNormalButton,
                                        "Reset Zoom", "Ctrl+0", self.zoom_reset)
        self.toolbar.addAction(zoom_reset_action)
        
        self.toolbar.addSeparator()
        
        # Settings button
        settings_action = create_action("settings", QStyle.SP_FileDialogDetailedView,
                                      "Settings", handler=self.show_settings)
        self.toolbar.addAction(settings_action)
        
        # Add flexible space
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar.addWidget(spacer)
        
        # Help and About at the end
        help_action = create_action("help", QStyle.SP_MessageBoxQuestion,
                                  "Help", handler=self.show_help)
        self.toolbar.addAction(help_action)
        
        about_action = create_action("about", QStyle.SP_MessageBoxInformation,
                                   "About", handler=self.show_about)
        self.toolbar.addAction(about_action)
        
        # Set toolbar properties based on platform
        if sys.platform == 'darwin':
            self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        else:
            self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        
    def get_current_editor(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            return current_tab.editor
        return None
        
    def undo(self):
        editor = self.get_current_editor()
        if editor:
            editor.undo()
            
    def redo(self):
        editor = self.get_current_editor()
        if editor:
            editor.redo()
            
    def cut(self):
        editor = self.get_current_editor()
        if editor:
            editor.cut()
            
    def copy(self):
        editor = self.get_current_editor()
        if editor:
            editor.copy()
            
    def paste(self):
        editor = self.get_current_editor()
        if editor:
            editor.paste()
        
    def new_tab(self):
        editor_tab = EditorTab(self.snippet_manager)
        self.tab_widget.addTab(editor_tab, f"Document {self.tab_widget.count() + 1}")
        self.tab_widget.setCurrentWidget(editor_tab)
        
    def close_tab(self, index):
        """Handle tab close"""
        tab = self.tab_widget.widget(index)
        
        if tab.editor.document().isModified():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "This document has unsaved changes. Do you want to save them?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                self.tab_widget.setCurrentIndex(index)
                if not tab.save_file():  # If save is cancelled
                    return
            elif reply == QMessageBox.Cancel:
                return
        
        # Clean up session files for this tab
        tab.cleanup_session_files()
        self.tab_widget.removeTab(index)
        
        # Create new tab if last tab was closed
        if self.tab_widget.count() == 0:
            self.new_editor_tab()
            
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        file_menu.addAction('New Editor Tab', self.new_editor_tab)
        file_menu.addAction('New RSS Tab', self.new_rss_tab)
        file_menu.addSeparator()
        file_menu.addAction('Save', self.save_file)
        file_menu.addAction('Open', self.open_file)
        file_menu.addSeparator()
        file_menu.addAction('Exit', self.close)

    def save_file(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.save_file()
            
    def open_file(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.open_file()

    def new_editor_tab(self):
        editor_tab = EditorTab(self.snippet_manager, self.settings_manager)
        editor_tab.set_main_window(self)  # Set reference to main window
        self.tab_widget.addTab(editor_tab, f"Document {self.tab_widget.count() + 1}")
        self.tab_widget.setCurrentWidget(editor_tab)
        editor_tab.editor.setFocus()  # Set focus to editor
        return editor_tab
        
    def new_rss_tab(self):
        rss_tab = RSSTab()
        self.tab_widget.addTab(rss_tab, "RSS Reader")
        self.tab_widget.setCurrentWidget(rss_tab)

    def show_font_dialog(self):
        if editor_tab := self.tab_widget.currentWidget():
            if isinstance(editor_tab, EditorTab):
                font, ok = QFontDialog.getFont(editor_tab.current_font, self)
                if ok:
                    editor_tab.update_font(font)
                    self.settings_manager.save_font(font)

    def show_theme_menu(self):
        menu = QMenu(self)
        for theme_name in ThemeManager.get_themes():
            action = menu.addAction(theme_name)
            action.triggered.connect(lambda checked, tn=theme_name: self.apply_theme(tn))
        
        # Show menu under theme button
        button = self.toolbar.widgetForAction(self.sender())
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def apply_theme(self, theme_name):
        if editor_tab := self.tab_widget.currentWidget():
            if isinstance(editor_tab, EditorTab):
                editor_tab.apply_theme(theme_name)
                self.settings_manager.save_theme(theme_name)

    def toggle_snippets(self):
        """Toggle snippets pane in current tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.toggle_pane("snippets")

    def open_file_path(self, file_path):
        """Open a file by its path"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                tab = self.new_editor_tab()
                tab.editor.setPlainText(content)
                tab.current_file = file_path
                current_index = self.tab_widget.indexOf(tab)
                self.tab_widget.setTabText(current_index, os.path.basename(file_path))
                return True
        except Exception as e:
            print(f"Failed to open file {file_path}: {str(e)}")
            return False

    def check_crash_recovery(self):
        """Check for and recover unsaved files from crash"""
        recovery_dir = self.settings_manager.get_recovery_dir()
        recovery_files = []
        
        # Find all recovery files with their metadata
        for filename in os.listdir(recovery_dir):
            if filename.endswith('.txt'):
                file_path = os.path.join(recovery_dir, filename)
                meta_path = file_path + '.json'
                
                try:
                    # Only recover if metadata exists and shows no clean exit
                    if os.path.exists(meta_path):
                        with open(meta_path, 'r') as f:
                            metadata = json.load(f)
                            
                        if not metadata.get('clean_exit', False):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                if content.strip():  # Only recover non-empty files
                                    recovery_files.append((file_path, content, metadata))
                except:
                    continue
        
        # Automatically recover files that weren't cleanly exited
        for file_path, content, metadata in recovery_files:
            tab = self.new_editor_tab()
            tab.editor.setPlainText(content)
            
            # Restore cursor and scroll position
            cursor = tab.editor.textCursor()
            cursor.setPosition(metadata.get('cursor_position', 0))
            tab.editor.setTextCursor(cursor)
            tab.editor.verticalScrollBar().setValue(
                metadata.get('scroll_position', 0)
            )
            
            # Set tab title
            original_file = metadata.get('original_file')
            title = os.path.basename(original_file) if original_file else "Recovered File"
            current_index = self.tab_widget.indexOf(tab)
            self.tab_widget.setTabText(current_index, title + " (Recovered)")
            
            # Store original file path if it existed
            if original_file:
                tab.current_file = original_file

    def get_open_files(self):
        """Get list of currently open files"""
        open_files = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, EditorTab) and tab.current_file:
                open_files.append(tab.current_file)
        return open_files

    def closeEvent(self, event):
        """Handle application close"""
        # First autosave all tabs to capture final state
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            tab.autosave()
        
        # Handle unsaved changes
        if self.handle_unsaved_changes():
            # Only mark as clean exit if all changes were handled
            self.settings_manager.save_session_state(self.get_open_tab_ids(), clean_exit=True)
            event.accept()
        else:
            # Mark as unclean exit if closing was cancelled
            self.settings_manager.save_session_state(self.get_open_tab_ids(), clean_exit=False)
            event.ignore()

    def open_external_url(self, url):
        """Open URL in system's default browser"""
        QDesktopServices.openUrl(QUrl(url))

    def show_help(self):
        """Show help documentation"""
        help_tab = self.new_editor_tab()
        
        # Load help content
        try:
            with open('help/help.md', 'r', encoding='utf-8') as f:
                help_content = f.read()
        except:
            help_content = "Help documentation not found."
        
        # Set content and make read-only
        help_tab.editor.setPlainText(help_content)
        help_tab.editor.setReadOnly(True)
        
        # Set tab title
        current_index = self.tab_widget.indexOf(help_tab)
        self.tab_widget.setTabText(current_index, "Help")

    def show_about(self):
        """Show about dialog"""
        about_text = f"""
        <div style="text-align: center;">
            <h1>{APP_NAME}</h1>
            <p style="color: #666;">Version {APP_VERSION}</p>
            
            <p>A modern text editor designed for writers and journalists.</p>
            
            <h3>Key Features:</h3>
            <ul style="list-style-type: none; padding: 0;">
                <li>✓ Smart word completion</li>
                <li>✓ Custom dictionary</li>
                <li>✓ Text snippet management</li>
                <li>✓ Integrated web browser</li>
                <li>✓ Site-specific searches</li>
                <li>✓ Distraction-free mode</li>
            </ul>

            <p><a href="{APP_HOMEPAGE}">Visit Project Homepage</a></p>
            
            <p style="font-size: small; color: #666; margin-top: 20px;">
                Made with ♥ for writers everywhere
            </p>
        </div>
        """
        
        about_dialog = QMessageBox(self)
        about_dialog.setWindowTitle(f"About {APP_NAME}")
        about_dialog.setText(about_text)
        about_dialog.setTextFormat(Qt.RichText)
        about_dialog.setStyleSheet("""
            QMessageBox {
                background-color: white;
            }
            QMessageBox QLabel {
                min-width: 400px;
            }
        """)
        
        # Make links clickable
        about_dialog.setTextInteractionFlags(Qt.TextBrowserInteraction)
        
        about_dialog.exec_()

    def toggle_focus_mode(self):
        """Toggle focus mode for current editor tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.toggle_focus_mode()

    def zoom_in(self):
        """Increase editor font size"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            font = current_tab.editor.font()
            size = font.pointSize()
            font.setPointSize(size + 1)
            current_tab.update_font(font)

    def zoom_out(self):
        """Decrease editor font size"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            font = current_tab.editor.font()
            size = font.pointSize()
            if size > 1:  # Prevent font from becoming too small
                font.setPointSize(size - 1)
                current_tab.update_font(font)

    def zoom_reset(self):
        """Reset editor font to default size"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            default_font = self.settings_manager.get_font()
            current_tab.update_font(default_font)

    def restore_session(self):
        """Restore previous session with integrity checks"""
        recovery_dir = self.settings_manager.get_recovery_dir()
        
        try:
            with open(os.path.join(recovery_dir, "session_state.json"), 'r') as f:
                state = json.load(f)
                open_tab_ids = state.get('open_tabs', [])
                if not open_tab_ids:
                    return
        except:
            return
            
        session_files = []
        corrupted_files = []
        
        # Find and verify all session files
        for tab_id in open_tab_ids:
            file_path = os.path.join(recovery_dir, f"session_{tab_id}.txt")
            meta_path = file_path + '.json'
            
            try:
                if os.path.exists(meta_path) and os.path.exists(file_path):
                    with open(meta_path, 'r') as f:
                        metadata = json.load(f)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if content.strip():
                            current_checksum = hashlib.md5(content.encode()).hexdigest()
                            if current_checksum == metadata.get('checksum'):
                                session_files.append((file_path, content, metadata))
                            else:
                                corrupted_files.append(file_path)
            except:
                corrupted_files.append(file_path)
                continue

        if not session_files:
            return

        # Sort and restore files
        session_files.sort(key=lambda x: x[2].get('tab_index', 0))
        active_index = 0
        
        for file_path, content, metadata in session_files:
            tab = self.new_editor_tab()
            tab.editor.setPlainText(content)
            
            # Restore cursor and scroll position
            cursor = tab.editor.textCursor()
            cursor.setPosition(metadata.get('cursor_position', 0))
            tab.editor.setTextCursor(cursor)
            tab.editor.verticalScrollBar().setValue(
                metadata.get('scroll_position', 0)
            )
            
            # Restore file path and state
            original_file = metadata.get('original_file')
            if original_file:
                tab.current_file = original_file
                title = os.path.basename(original_file)
            else:
                title = "Untitled"
            
            if metadata.get('modified', False):
                tab.editor.document().setModified(True)
                title += "*"
            
            current_index = self.tab_widget.indexOf(tab)
            self.tab_widget.setTabText(current_index, title)
            
            if metadata.get('active', False):
                active_index = current_index
        
        if self.tab_widget.count() > 0:
            self.tab_widget.setCurrentIndex(active_index)

    def get_open_tab_ids(self):
        """Get list of recovery IDs for all open tabs"""
        tab_ids = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, 'recovery_id'):
                tab_ids.append(tab.recovery_id)
        return tab_ids

    def handle_unsaved_changes(self):
        """Handle unsaved changes before closing"""
        unsaved_tabs = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if tab.editor.document().isModified():
                unsaved_tabs.append(i)
        
        if unsaved_tabs:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Save:
                for i in unsaved_tabs:
                    self.tab_widget.setCurrentIndex(i)
                    if not self.tab_widget.widget(i).save_file():  # If save is cancelled
                        return False
                return True
            elif reply == QMessageBox.Cancel:
                return False
            # If Discard, continue with close
        
        return True

    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self.settings_manager, self)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_data()
            
            # Save settings
            self.settings_manager.save_setting('homepage', settings['homepage'])
            self.settings_manager.save_setting('search_sites', settings['search_sites'])
            self.settings_manager.save_setting('user_dictionary', settings['user_dictionary'])

    def toggle_browser(self):
        """Toggle browser pane in current tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.toggle_pane("browser")

def main():
    # Create application instance
    app = QApplication(sys.argv)
    
    # Set application name and organization
    app.setApplicationName("Jottr")
    app.setApplicationDisplayName("Jottr")
    app.setDesktopFileName("jottr")
    app.setApplicationVersion("1.0")
    app.setOrganizationDomain("github.com/mfat/jottr")
    
    # Set window class name for proper window management
    if hasattr(app, 'setDesktopFileName'):
        app.setDesktopFileName("jottr")
    
    # Create and show main window
    window = TextEditorApp()
    window.setWindowTitle("Jottr")
    
    # Show window
    window.show()
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main()) 