import sys
import os
from PyQt5.QtWidgets import QApplication, QStyleFactory

class MainWindow(QApplication):
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
            # Let the system handle styling
            self.setStyle(QApplication.style())
            
            # Only set minimal toolbar spacing
            self.toolbar.setStyleSheet("""
                QToolBar {
                    spacing: 2px;
                }
            """)
            
            # Try to use the system style if available
            if QStyleFactory.keys():
                # Try to detect the current desktop environment
                desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
                
                if 'kde' in desktop:
                    # Use Breeze on KDE
                    if 'breeze' in QStyleFactory.keys():
                        QApplication.setStyle('Breeze')
                elif 'gnome' in desktop:
                    # Use Adwaita on GNOME
                    if 'adwaita' in QStyleFactory.keys():
                        QApplication.setStyle('Adwaita')
                else:
                    # Fallback to system default
                    pass 