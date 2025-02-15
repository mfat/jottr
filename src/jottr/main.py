import sys
if sys.version_info < (3, 10):
    print("Error: Python 3.10 or higher is required")
    sys.exit(1)

import os
import json
import hashlib
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, 
                            QVBoxLayout, QHBoxLayout, QSplitter, QMenu, QToolBar, QAction, QStyle, QMessageBox, QFontDialog, QStyleFactory, QLabel, QDialog, QSizePolicy, QDialogButtonBox)
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
from PyQt5.QtGui import QFont
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtGui import QPainter
from PyQt5.QtCore import QSize

# Add vendor directory to path
vendor_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor')
if os.path.exists(vendor_dir):
    sys.path.insert(0, vendor_dir)

# Application constants
APP_NAME = "Jottr"
APP_VERSION = "1.1.0"
APP_HOMEPAGE = "https://github.com/mfat/jottr"

class TextEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize managers first
        self.settings_manager = SettingsManager()
        self.snippet_manager = SnippetManager()
        
        # Apply UI theme from settings
        self.apply_ui_theme(self.settings_manager.get_ui_theme())
        
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
        # Prevent toolbar from being hidden
        self.toolbar.setContextMenuPolicy(Qt.PreventContextMenu)
        
        # Helper function to create themed action
        def create_action(icon_name, fallback_icon, text, shortcut=None, handler=None):
            # Create icon from SVG file in project root icons directory
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            icon_path = os.path.join(project_root, 'icons', f'{icon_name}.svg')
            
            if os.path.exists(icon_path):
                # Load SVG directly
                icon = QIcon(icon_path)
            else:
                icon = self.style().standardIcon(fallback_icon)
            
            action = QAction(icon, text, self)
            if shortcut:
                action.setShortcut(shortcut)
            if handler:
                action.triggered.connect(handler)
            
            return action

        # Set toolbar properties for better icon rendering
        self.toolbar.setIconSize(QSize(24, 24))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

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
        
        # Add Save As button with same icon as Save
        save_as_action = create_action("save-as", QStyle.SP_DialogSaveButton,  # Use "save" instead of "save-as"
                                     "Save As", "Ctrl+Shift+S", self.save_file_as)
        self.toolbar.addAction(save_as_action)
        
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
        focus_action = create_action("focus-mode", QStyle.SP_ComputerIcon,
                                   "Focus Mode", 
                                   "Ctrl+Shift+D" if sys.platform != 'darwin' else "⌘+Shift+D",
                                   self.toggle_focus_mode)
        focus_action.setToolTip("Toggle distraction-free writing mode\n"
                               "Shortcut: Ctrl+Shift+D" if sys.platform != 'darwin' 
                               else "Toggle distraction-free writing mode\n"
                               "Shortcut: ⌘+Shift+D")
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
        
        # Add search button
        search_action = create_action("find", QStyle.SP_FileDialogContentsView,
                                    "Find/Replace", "Ctrl+F", self.toggle_find)
        self.toolbar.addAction(search_action)
        
        # Add flexible space
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar.addWidget(spacer)
        
        # Create menu button with dropdown
        menu_button = create_action("menu", QStyle.SP_TitleBarMenuButton,
                                  "Menu", handler=self.show_menu_dropdown)
        self.toolbar.addAction(menu_button)
        
        # Create the dropdown menu (but don't show it yet)
        self.menu_dropdown = QMenu(self)
        
        # Move settings, help, and about actions to the dropdown
        settings_action = create_action("settings", QStyle.SP_FileDialogDetailedView,
                                      "Settings", handler=self.show_settings)
        self.menu_dropdown.addAction(settings_action)
        
        self.menu_dropdown.addSeparator()
        
        help_action = create_action("help", QStyle.SP_MessageBoxQuestion,
                                  "Help", handler=self.show_help)
        self.menu_dropdown.addAction(help_action)
        
        about_action = create_action("about", QStyle.SP_MessageBoxInformation,
                                   "About", handler=self.show_about)
        self.menu_dropdown.addAction(about_action)
        
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
        """Show theme selection menu"""
        menu = QMenu(self)
        
        # Add editor themes
        for theme_name in ThemeManager.get_themes():
            action = menu.addAction(theme_name)
            action.triggered.connect(lambda checked, tn=theme_name: self.apply_theme(tn))
        
        # Show menu under theme button
        button = self.toolbar.widgetForAction(self.sender())
        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))

    def apply_ui_theme(self, theme):
        """Apply UI theme to application"""
        self.settings_manager.apply_ui_theme(theme)
        
        # Update all widgets
        QApplication.setStyle(QStyleFactory.create(theme))
        self.update()

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
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle(f"About {APP_NAME}")
        about_dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(about_dialog)
        layout.setSpacing(10)
        
        # App name
        title_label = QLabel(APP_NAME)
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Version
        version_label = QLabel(f"Version {APP_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        # Description
        desc_label = QLabel("A simple text editor for writers, journalists and researchers")
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)
        
        # Add some spacing
        layout.addSpacing(10)
        
        # Developer
        dev_label = QLabel("Developed by mFat")
        dev_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(dev_label)
        
        # License
        license_label = QLabel("Licensed under GNU GPL v3.0")
        license_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(license_label)
        
        # Homepage link
        link_label = QLabel(f'<a href="{APP_HOMEPAGE}">Project Homepage</a>')
        link_label.setOpenExternalLinks(True)
        link_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(link_label)
        
        # Add button box
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(about_dialog.accept)
        button_box.setCenterButtons(True)  # Center the OK button
        layout.addWidget(button_box)
        
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
            current_font = current_tab.current_font  # Use stored font
            new_font = QFont(current_font)  # Create new font based on current
            new_font.setPointSize(current_font.pointSize() + 1)
            current_tab.update_font(new_font)

    def zoom_out(self):
        """Decrease editor font size"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_font = current_tab.current_font  # Use stored font
            size = current_font.pointSize()
            if size > 1:  # Prevent font from becoming too small
                new_font = QFont(current_font)  # Create new font based on current
                new_font.setPointSize(size - 1)
                current_tab.update_font(new_font)

    def zoom_reset(self):
        """Reset editor font to default size"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            default_font = self.settings_manager.get_font()
            # Preserve current font properties except size
            new_font = QFont(current_tab.current_font)
            new_font.setPointSize(default_font.pointSize())
            current_tab.update_font(new_font)

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
            self.settings_manager.save_setting('ui_theme', settings['ui_theme'])
            self.apply_ui_theme(settings['ui_theme'])  # Apply the new theme immediately

    def toggle_browser(self):
        """Toggle browser pane in current tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.toggle_pane("browser")

    def toggle_find(self):
        """Toggle find/replace in current editor tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.toggle_find()

    def save_file_as(self):
        """Save current file with a new name"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.save_file(force_dialog=True)

    def show_menu_dropdown(self):
        """Show the menu dropdown under the menu button"""
        # Find the menu button
        menu_button = None
        for action in self.toolbar.actions():
            if action.text() == "Menu":
                menu_button = self.toolbar.widgetForAction(action)
                break
        
        if menu_button:
            # Show menu below the button
            pos = menu_button.mapToGlobal(menu_button.rect().bottomLeft())
            self.menu_dropdown.popup(pos)

def main():
    # Enable high DPI scaling
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL)
    
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