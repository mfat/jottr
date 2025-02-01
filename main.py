import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, 
                            QVBoxLayout, QHBoxLayout, QSplitter, QMenu, QToolBar, QAction, QStyle, QMessageBox, QFontDialog, QStyleFactory)
from PyQt5.QtCore import Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView
from editor_tab import EditorTab
from snippet_manager import SnippetManager
from rss_tab import RSSTab
import feedparser
from PyQt5.QtGui import QIcon
from theme_manager import ThemeManager
from settings_manager import SettingsManager

class TextEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Text Editor")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize managers first
        self.settings_manager = SettingsManager()
        self.snippet_manager = SnippetManager()
        
        # Set platform-specific style
        self.setup_platform_style()
        
        # Create main toolbar
        self.toolbar = self.addToolBar("Main Toolbar")
        self.setup_toolbar()
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        layout.addWidget(self.tab_widget)
        
        # Setup menu bar
        self.create_menu_bar()
        
        # Load last opened files or create new tab
        last_files = self.settings_manager.get_last_files()
        if last_files:
            for file_path in last_files:
                if os.path.exists(file_path):
                    self.open_file_path(file_path)
        if self.tab_widget.count() == 0:
            self.new_editor_tab()
        
    def setup_platform_style(self):
        """Apply platform-specific styling"""
        platform = sys.platform
        
        if platform == 'darwin':  # macOS
            self.setUnifiedTitleAndToolBarOnMac(True)
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
                preferred_styles = ['kvantum', 'breeze', 'fusion', 'gtk2', 'oxygen']
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
        # Helper function to create themed action
        def create_action(theme_name, fallback_icon, text, shortcut=None, handler=None):
            if sys.platform != 'win32':
                # Try multiple theme icon names for better compatibility
                theme_variants = {
                    'undo': ['edit-undo', 'undo-symbolic', 'gtk-undo'],
                    'redo': ['edit-redo', 'redo-symbolic', 'gtk-redo'],
                    'cut': ['edit-cut', 'cut-symbolic', 'gtk-cut'],
                    'font': ['preferences-desktop-font', 'font-x-generic', 'gtk-font'],
                    'theme': ['preferences-desktop-theme', 'preferences-desktop-color', 'gtk-preferences']
                }
                
                if theme_name in theme_variants:
                    for variant in theme_variants[theme_name]:
                        if QIcon.hasThemeIcon(variant):
                            icon = QIcon.fromTheme(variant)
                            break
                    else:
                        icon = self.style().standardIcon(fallback_icon)
                else:
                    icon = QIcon.fromTheme(theme_name, self.style().standardIcon(fallback_icon))
            else:
                icon = self.style().standardIcon(fallback_icon)
            
            action = QAction(icon, text, self)
            if shortcut:
                action.setShortcut(shortcut)
            if handler:
                action.triggered.connect(handler)
            return action

        # File operations
        new_action = create_action("document-new", QStyle.SP_FileIcon, 
                                 "New", "Ctrl+N", self.new_editor_tab)
        self.toolbar.addAction(new_action)
        
        open_action = create_action("document-open", QStyle.SP_DirOpenIcon, 
                                  "Open", "Ctrl+O", self.open_file)
        self.toolbar.addAction(open_action)
        
        save_action = create_action("document-save", QStyle.SP_DialogSaveButton, 
                                  "Save", "Ctrl+S", self.save_file)
        self.toolbar.addAction(save_action)
        
        self.toolbar.addSeparator()
        
        # Edit operations
        undo_action = create_action("undo", QStyle.SP_CommandLink, 
                                  "Undo", "Ctrl+Z", self.undo)
        self.toolbar.addAction(undo_action)
        
        redo_action = create_action("redo", QStyle.SP_CommandLink, 
                                  "Redo", "Ctrl+Shift+Z", self.redo)
        self.toolbar.addAction(redo_action)
        
        self.toolbar.addSeparator()
        
        # Cut/Copy/Paste
        cut_action = create_action("cut", QStyle.SP_DialogDiscardButton, 
                                 "Cut", "Ctrl+X", self.cut)
        self.toolbar.addAction(cut_action)
        
        copy_action = create_action("edit-copy", QStyle.SP_DialogApplyButton, 
                                  "Copy", "Ctrl+C", self.copy)
        self.toolbar.addAction(copy_action)
        
        paste_action = create_action("edit-paste", QStyle.SP_DialogOkButton, 
                                   "Paste", "Ctrl+V", self.paste)
        self.toolbar.addAction(paste_action)
        
        self.toolbar.addSeparator()
        
        # Font and Theme
        font_action = create_action("font", QStyle.SP_DesktopIcon, 
                                  "Font", handler=self.show_font_dialog)
        self.toolbar.addAction(font_action)
        
        theme_action = create_action("theme", QStyle.SP_DesktopIcon, 
                                   "Theme", handler=self.show_theme_menu)
        self.toolbar.addAction(theme_action)
        
        # View toggles
        snippets_action = create_action("view-list-text", QStyle.SP_FileDialogListView,
                                      "Snippets", handler=lambda: self.toggle_pane("snippets"))
        self.toolbar.addAction(snippets_action)
        
        browser_action = create_action("applications-internet", QStyle.SP_ComputerIcon,
                                     "Browser", handler=lambda: self.toggle_pane("browser"))
        self.toolbar.addAction(browser_action)
        
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
        if editor := self.get_current_editor():
            editor.undo()
            
    def redo(self):
        if editor := self.get_current_editor():
            editor.redo()
            
    def cut(self):
        if editor := self.get_current_editor():
            editor.cut()
            
    def copy(self):
        if editor := self.get_current_editor():
            editor.copy()
            
    def paste(self):
        if editor := self.get_current_editor():
            editor.paste()
        
    def new_tab(self):
        editor_tab = EditorTab(self.snippet_manager)
        self.tab_widget.addTab(editor_tab, f"Document {self.tab_widget.count() + 1}")
        self.tab_widget.setCurrentWidget(editor_tab)
        
    def close_tab(self, index):
        current_tab = self.tab_widget.widget(index)
        if current_tab and isinstance(current_tab, EditorTab):
            if current_tab.editor.document().isModified():
                reply = QMessageBox.question(self, 'Save Changes?',
                                           'Do you want to save your changes?',
                                           QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
                
                if reply == QMessageBox.Save:
                    current_tab.save_file()
                elif reply == QMessageBox.Cancel:
                    return
        
        self.tab_widget.removeTab(index)
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

    def toggle_pane(self, pane):
        if editor_tab := self.tab_widget.currentWidget():
            if isinstance(editor_tab, EditorTab):
                editor_tab.toggle_pane(pane)

    def open_file_path(self, file_path):
        """Open a file from path"""
        editor_tab = EditorTab(self.snippet_manager, self.settings_manager)
        editor_tab.set_main_window(self)
        self.tab_widget.addTab(editor_tab, os.path.basename(file_path))
        editor_tab.current_file = file_path
        with open(file_path, 'r') as file:
            editor_tab.editor.setPlainText(file.read())
        self.tab_widget.setCurrentWidget(editor_tab)
        editor_tab.editor.setFocus()

    def closeEvent(self, event):
        """Handle application closing"""
        # Save list of currently open files
        open_files = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, EditorTab) and tab.current_file:
                open_files.append(tab.current_file)
        self.settings_manager.save_last_files(open_files)
        
        # Handle unsaved changes
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, EditorTab):
                if tab.editor.document().isModified():
                    self.tab_widget.setCurrentIndex(i)
                    reply = QMessageBox.question(self, 'Save Changes?',
                                               f'Save changes to {self.tab_widget.tabText(i)}?',
                                               QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
                    if reply == QMessageBox.Save:
                        tab.save_file()
                        if tab.editor.document().isModified():
                            event.ignore()
                            return
                    elif reply == QMessageBox.Cancel:
                        event.ignore()
                        return
                
                # Clean up autosave files for this tab
                tab.cleanup_autosave()
        
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = TextEditorApp()
    editor.show()
    sys.exit(app.exec_()) 