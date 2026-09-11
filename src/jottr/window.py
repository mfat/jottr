"""Main application window."""
import os
import json

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QSplitter,
    QMenu, QToolBar, QMessageBox, QLabel, QDialog, QSizePolicy,
    QDialogButtonBox, QFileDialog, QToolButton, QTabBar,
    QGraphicsOpacityEffect, QApplication,
)
from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QEvent, QPropertyAnimation,
    QEasingCurve, QParallelAnimationGroup, QSize,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import (
    QAction, QShortcut, QIcon, QDesktopServices,
    QKeySequence, QFont,
)

from jottr.editor_tab import EditorTab
from jottr.snippet_manager import SnippetManager
from jottr.rss_tab import RSSTab
from jottr.theme_manager import ThemeManager
from jottr.settings_manager import SettingsManager
from jottr.settings_dialog import SettingsDialog
from jottr.translation_manager import _, is_rtl_language, set_language
from jottr.font_dialog import FontSelectionDialog
from jottr.plugin_manager import PluginManager
from jottr.icon_manager import (
    apply_dialog_window_icon,
    ask_themed_question,
    build_themed_icon as render_bundled_icon,
    load_bundled_icon_paths,
    resolve_icon_color,
)
from jottr.paths import find_data_file
from jottr import __version__
from jottr.ui.workspace_controller import WorkspaceControllerMixin
from jottr.ui.document_tab_bar import LeftAlignedDocumentTabBar

APP_NAME = "Jottr"
APP_VERSION = __version__
APP_HOMEPAGE = "https://github.com/mfat/jottr"


class TextEditorApp(WorkspaceControllerMixin, QMainWindow):
    def __init__(self, file_path=None): 
        super().__init__()
        
        # Create settings manager first
        self.settings_manager = SettingsManager()
        language = self.settings_manager.get_setting("language", "en_US")
        set_language(language)
        self.apply_layout_direction(language)
        
        # Create snippet manager with settings manager
        self.snippet_manager = SnippetManager(self.settings_manager)
        
        # Logical name -> Qt resource path (:/icons/symbolic/…)
        self.icons = load_bundled_icon_paths()


        self.setWindowTitle(APP_NAME)
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize managers first
        self.settings_manager = SettingsManager()
        self.snippet_manager = SnippetManager(self.settings_manager)
        self.plugin_manager = PluginManager(self.settings_manager)
        self.plugin_manager.refresh()
        self.plugin_manager.activate_enabled_plugins()
        
        # Create toolbar first before styling
        self.toolbar = QToolBar(_("Main Toolbar"))  # Add name here
        self.toolbar.setObjectName("mainToolBar")  # Add this line
        self.toolbar.setMovable(False)
        
        # Setup toolbar contents
        self.setup_toolbar()
        self.create_menu_bar()
        
        # Create status bar (simplified)
        self.statusBar = self.statusBar()
        
        # Set initial status message
        self.statusBar.showMessage(_("Words: 0 | Characters: 0"))
        self.statusBar.setObjectName("statusBar")
        
        # Create main widget and layout
        main_widget = QWidget()
        main_widget.setObjectName("mainSurface")
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create tab widget
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setObjectName("mainSplitter")
        self.workspace_path = ""
        self.setup_workspace_explorer()

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabBar(LeftAlignedDocumentTabBar())
        self.tab_widget.setObjectName("documentTabs")
        self.tab_widget.setDocumentMode(False)
        self.tab_widget.setMovable(True)
        self.tab_widget.setUsesScrollButtons(True)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setIconSize(QSize(16, 16))
        self.tab_widget.tabBar().setExpanding(False)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.tabBar().tabs_changed.connect(self.refresh_tab_close_buttons)
        
        # Install event filters on both the tab bar and its containing tab strip.
        self.tab_widget.tabBar().installEventFilter(self)
        self.tab_widget.installEventFilter(self)
        
        self.main_splitter.addWidget(self.workspace_widget)
        self.main_splitter.addWidget(self.tab_widget)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([260, 940])
        layout.addWidget(self.main_splitter)
        self.restore_workspace()
        
        # Create new tab if no tabs were restored
        if self.tab_widget.count() == 0:
            self.new_editor_tab()
        
        # Open file if specified
        if file_path:
            self.open_file_path(file_path)
        
        self.apply_app_style()
        self.setup_shortcuts()  # Add this line after setup_toolbar()

    def apply_app_style(self, font=None):
        """Apply the quiet writing-focused application chrome."""
        theme = ThemeManager.get_theme(
            self.settings_manager.get_ui_theme(),
            self.settings_manager.get_custom_themes()
        )
        app_font = QFont(font) if font is not None else self.settings_manager.get_font("ui")
        application = QApplication.instance()
        if application:
            application.setFont(app_font)
        self.setFont(app_font)
        stylesheet = ThemeManager.build_app_stylesheet(theme, app_font)
        if application:
            application.setStyleSheet(stylesheet)
        self.setStyleSheet(stylesheet)
        self.update_action_icons()
        self.refresh_tab_icons()

    def get_icon_color(self):
        """Return the configured icon color for the active app theme."""
        return resolve_icon_color(self.settings_manager)

    def build_themed_icon(self, icon_name):
        """Tint a bundled symbolic SVG to the active icon color."""
        return render_bundled_icon(
            self.icons.get(icon_name, ""),
            self.get_icon_color(),
        )

    def update_action_icons(self):
        if not hasattr(self, "icon_actions"):
            return
        for action, icon_name in self.icon_actions:
            action.setIcon(self.build_themed_icon(icon_name))

    def tab_icon_name_for_widget(self, tab):
        if getattr(tab, "is_settings_tab", False):
            return "settings"
        if isinstance(tab, EditorTab) or hasattr(tab, "current_file"):
            return "snippets"
        return ""

    def update_tab_icon(self, index):
        if index < 0 or not hasattr(self, "tab_widget"):
            return
        icon_name = self.tab_icon_name_for_widget(self.tab_widget.widget(index))
        icon = self.build_themed_icon(icon_name) if icon_name else QIcon()
        self.tab_widget.setTabIcon(index, icon)

    def refresh_tab_icons(self):
        if not hasattr(self, "tab_widget"):
            return
        for index in range(self.tab_widget.count()):
            self.update_tab_icon(index)
        self.refresh_tab_close_buttons()

    def tab_close_icon(self):
        """Bundled themed icon for document tab close buttons."""
        return self.build_themed_icon("tab-close")

    def refresh_tab_close_buttons(self):
        """Replace default close glyphs with the bundled cross icon."""
        if not hasattr(self, "tab_widget"):
            return
        tab_bar = self.tab_widget.tabBar()
        icon = self.tab_close_icon()
        for index in range(self.tab_widget.count()):
            button = tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
            if button is None or button.objectName() != "tabCloseButton":
                button = QToolButton(tab_bar)
                button.setObjectName("tabCloseButton")
                button.setAutoRaise(True)
                button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setToolTip(_("Close tab"))
                button.clicked.connect(self._on_tab_close_button_clicked)
                tab_bar.setTabButton(index, QTabBar.ButtonPosition.RightSide, button)
            button.setIcon(icon)
            button.setIconSize(QSize(12, 12))
            button.setFixedSize(18, 18)

    def _on_tab_close_button_clicked(self):
        button = self.sender()
        if button is None:
            return
        tab_bar = self.tab_widget.tabBar()
        for index in range(self.tab_widget.count()):
            if tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide) is button:
                self.close_tab(index)
                return

    def animations_enabled(self):
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return False
        return bool(self.settings_manager.get_setting("enable_animations", True))

    def animate_widget_visibility(self, widget, visible, duration=260, fade=True):
        if not self.animations_enabled():
            widget.setGraphicsEffect(None)
            original_width = widget.property("animation_original_max_width")
            if original_width is not None:
                widget.setMaximumWidth(int(original_width))
            widget.setVisible(visible)
            return None

        current_animation = self.ui_animations.pop(widget, None)
        if current_animation:
            current_animation.stop()

        original_width = widget.property("animation_original_max_width")
        if original_width is None or int(original_width) == 0:
            original_width = widget.maximumWidth()
            widget.setProperty("animation_original_max_width", original_width)

        target_width = max(widget.width(), widget.sizeHint().width(), 260)
        if not visible and widget.width() > 0:
            target_width = widget.width()

        group = QParallelAnimationGroup(self)

        effect = None
        if fade:
            effect = widget.graphicsEffect()
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(widget)
                widget.setGraphicsEffect(effect)

            opacity_animation = QPropertyAnimation(effect, b"opacity", group)
            opacity_animation.setDuration(duration)
            opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            opacity_animation.setStartValue(0.0 if visible else 1.0)
            opacity_animation.setEndValue(1.0 if visible else 0.0)
            group.addAnimation(opacity_animation)
        else:
            widget.setGraphicsEffect(None)

        width_animation = QPropertyAnimation(widget, b"maximumWidth", group)
        width_animation.setDuration(duration)
        width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        width_animation.setStartValue(0 if visible else target_width)
        width_animation.setEndValue(target_width if visible else 0)
        group.addAnimation(width_animation)
        self.ui_animations[widget] = group

        if visible:
            widget.setMaximumWidth(0)
            if effect is not None:
                effect.setOpacity(0.0)
            widget.setVisible(True)
        else:
            widget.setMaximumWidth(target_width)
            if effect is not None:
                effect.setOpacity(1.0)

        def finish_animation():
            if not visible:
                widget.setVisible(False)
            widget.setMaximumWidth(int(original_width))
            widget.setGraphicsEffect(None)
            self.ui_animations.pop(widget, None)

        group.finished.connect(finish_animation)
        group.start()
        return group

    def setup_toolbar(self):
        """Setup the main toolbar"""
        self.toolbar = QToolBar(_("Main Toolbar"))
        self.toolbar.setObjectName("mainToolBar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        
        # Add toolbar to main window
        self.addToolBar(self.toolbar)
        
        # Prevent toolbar from being hidden
        self.toolbar.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        
        # Set toolbar properties for better icon rendering
        self.toolbar.setIconSize(QSize(22, 22))
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.icon_actions = []
        self.translatable_actions = []

        # Helper function to create themed action
        def create_action(icon_name, text, handler=None):
            translated_text = _(text)
            if icon_name in self.icons:
                action = QAction(self.build_themed_icon(icon_name), translated_text, self)
                self.icon_actions.append((action, icon_name))
            else:
                action = QAction(translated_text, self)
            action.setProperty("text_key", text)
            action.setProperty("tooltip_key", text)
            self.translatable_actions.append(action)
            action.setToolTip(translated_text)
            action.setStatusTip(translated_text)
            if handler:
                action.triggered.connect(handler)
            return action

        def set_action_tooltip(action, text):
            action.setProperty("tooltip_key", text)
            action.setToolTip(_(text))
            action.setStatusTip(_(text))
            action.setWhatsThis(_(text))

        # Create the dropdown menu
        self.menu_dropdown = QMenu(self)
        
        # Add actions to dropdown menu
        settings_action = create_action("settings", "Settings", self.show_settings)
        set_action_tooltip(settings_action, "Open Settings")
        self.menu_dropdown.addAction(settings_action)
        self.menu_dropdown.addSeparator()
        workspace_action = create_action("document-open", "Open Workspace", self.open_workspace_dialog)
        set_action_tooltip(workspace_action, "Open Workspace")
        self.menu_dropdown.addAction(workspace_action)
        new_workspace_file_action = create_action("new", "New Workspace File", self.create_workspace_file)
        set_action_tooltip(new_workspace_file_action, "New File in Workspace")
        self.menu_dropdown.addAction(new_workspace_file_action)
        self.menu_dropdown.addSeparator()
        help_action = create_action("help", "Help", self.show_help)
        set_action_tooltip(help_action, "Open Help")
        self.menu_dropdown.addAction(help_action)
        about_action = create_action("about", "About", self.show_about)
        set_action_tooltip(about_action, "About Jottr")
        self.menu_dropdown.addAction(about_action)

        # Add all toolbar items
        new_action = create_action("new", "New", self.new_editor_tab)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        set_action_tooltip(new_action, "New (Ctrl+N)")
        self.toolbar.addAction(new_action)
        
        open_action = create_action("open", "Open", self.open_file_dialog)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        set_action_tooltip(open_action, "Open (Ctrl+O)")
        self.toolbar.addAction(open_action)

        workspace_toolbar_action = create_action("document-open", "Workspace", self.open_workspace_dialog)
        set_action_tooltip(workspace_toolbar_action, "Open Workspace")
        self.toolbar.addAction(workspace_toolbar_action)
        
        save_action = create_action("save", "Save", self.save_file)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        set_action_tooltip(save_action, "Save (Ctrl+S)")
        self.toolbar.addAction(save_action)
        
        save_as_action = create_action("save-as", "Save As", self.save_file_as)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        set_action_tooltip(save_as_action, "Save As (Ctrl+Shift+S)")
        self.menu_dropdown.insertAction(self.menu_dropdown.actions()[0], save_as_action)
        export_pdf_action = create_action("save-as", "Export PDF", self.export_pdf)
        set_action_tooltip(export_pdf_action, "Export current file as PDF")
        self.menu_dropdown.insertAction(self.menu_dropdown.actions()[1], export_pdf_action)
        self.menu_dropdown.insertSeparator(self.menu_dropdown.actions()[2])
        
        self.toolbar.addSeparator()
        
        # Undo/Redo
        undo_action = create_action("undo", "Undo", self.undo)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        set_action_tooltip(undo_action, "Undo (Ctrl+Z)")
        self.toolbar.addAction(undo_action)

        redo_action = create_action("redo", "Redo", self.redo)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        set_action_tooltip(redo_action, "Redo (Ctrl+Shift+Z)")
        self.toolbar.addAction(redo_action)
        
        self.toolbar.addSeparator()
        
        # Find/Replace and Focus Mode
        find_action = create_action("find", "Find/Replace", self.toggle_find)
        set_action_tooltip(find_action, "Find/Replace (Ctrl+F)")
        self.toolbar.addAction(find_action)
        
        focus_action = create_action("focus-mode", "Focus Mode", self.toggle_focus_mode)
        focus_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        set_action_tooltip(focus_action, "Focus Mode (Ctrl+Shift+D)")
        focus_action.setCheckable(True)
        self.toolbar.addAction(focus_action)
        self.focus_mode_action = focus_action
        
        self.toolbar.addSeparator()

        # Fonts
        editor_font_action = create_action("font", "Editor Font", self.show_editor_font_dialog)
        set_action_tooltip(editor_font_action, "Choose Editor Font")
        self.toolbar.addAction(editor_font_action)
        
        # View toggles
        snippets_action = create_action("snippets", "Snippets", lambda: self.toggle_snippets())
        snippets_action.setShortcut(QKeySequence("Ctrl+Shift+N"))
        set_action_tooltip(snippets_action, "Toggle Snippets (Ctrl+Shift+N)")
        self.toolbar.addAction(snippets_action)

        markdown_action = create_action("insert-text", "Markdown", self.toggle_markdown_preview)
        markdown_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        set_action_tooltip(markdown_action, "Toggle Markdown Preview (Ctrl+Shift+M)")
        self.toolbar.addAction(markdown_action)

        for toolbar_action in self.plugin_manager.registry.toolbar_actions:
            title = toolbar_action.get("title") or toolbar_action.get("id") or _("Plugin")
            action = create_action(
                toolbar_action.get("icon", ""),
                title,
                lambda checked=False, item=toolbar_action: self.trigger_plugin_action(item)
            )
            if toolbar_action.get("shortcut"):
                action.setShortcut(QKeySequence(toolbar_action["shortcut"]))
            set_action_tooltip(action, toolbar_action.get("tooltip", title))
            self.toolbar.addAction(action)

        self.toolbar.addSeparator()
        
        # Zoom controls
        zoom_in_action = create_action("zoom-in", "Zoom In", self.zoom_in)
        zoom_in_action.setShortcut(QKeySequence("Ctrl+="))
        set_action_tooltip(zoom_in_action, "Zoom In (Ctrl+=)")
        self.toolbar.addAction(zoom_in_action)

        zoom_out_action = create_action("zoom-out", "Zoom Out", self.zoom_out)
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        set_action_tooltip(zoom_out_action, "Zoom Out (Ctrl+-)")
        self.toolbar.addAction(zoom_out_action)
        self.menu_dropdown.insertAction(self.menu_dropdown.actions()[0], zoom_in_action)
        self.menu_dropdown.insertAction(self.menu_dropdown.actions()[1], zoom_out_action)

        zoom_reset_action = create_action("zoom-reset", "Reset Zoom", self.zoom_reset)
        zoom_reset_action.setShortcut(QKeySequence("Ctrl+0"))
        set_action_tooltip(zoom_reset_action, "Reset Zoom (Ctrl+0)")
        self.toolbar.addAction(zoom_reset_action)
        self.menu_dropdown.insertAction(self.menu_dropdown.actions()[2], zoom_reset_action)
        self.menu_dropdown.insertSeparator(self.menu_dropdown.actions()[3])
        
        # Add flexible space
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.toolbar.addWidget(spacer)
        
        # Now set the overflow button text after all items are added
        def update_overflow_button():
            overflow_button = self.toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
            if overflow_button:
                overflow_button.setText(">>")
                overflow_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        
        # Use a single-shot timer to ensure the overflow button exists
        QTimer.singleShot(0, update_overflow_button)

    def retranslate_actions(self):
        """Refresh toolbar and dropdown labels after the active language changes."""
        if not hasattr(self, "translatable_actions"):
            return
        for action in self.translatable_actions:
            text_key = action.property("text_key")
            tooltip_key = action.property("tooltip_key")
            if text_key:
                action.setText(_(text_key))
            if tooltip_key:
                translated_tooltip = _(tooltip_key)
                action.setToolTip(translated_tooltip)
                action.setStatusTip(translated_tooltip)
                action.setWhatsThis(translated_tooltip)
        if hasattr(self, "translatable_menus"):
            self.menuBar().setAccessibleName(_("Application menu"))
            for menu, title in self.translatable_menus:
                menu.setAccessibleName(_("{title} menu").format(title=_(title)))

    def apply_layout_direction(self, language):
        direction = (
            Qt.LayoutDirection.RightToLeft
            if is_rtl_language(language)
            else Qt.LayoutDirection.LeftToRight
        )
        app = QApplication.instance()
        if app:
            app.setLayoutDirection(direction)
        self.setLayoutDirection(direction)

    def apply_language_direction_to_tabs(self):
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if hasattr(tab, "apply_language_direction"):
                tab.apply_language_direction()

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
        self.tab_widget.addTab(
            editor_tab,
            self.build_themed_icon("snippets"),
            _("Document {number}").format(number=self.tab_widget.count() + 1)
        )
        self.tab_widget.setCurrentWidget(editor_tab)

    def is_editor_tab_modified(self, tab):
        """Return True only for editor tabs with unsaved document changes."""
        return (
            isinstance(tab, EditorTab) and
            hasattr(tab, "editor") and
            tab.editor.document().isModified()
        )
        
    def close_tab(self, index):
        """Handle tab close"""
        tab = self.tab_widget.widget(index)
        
        if self.is_editor_tab_modified(tab):
            reply = ask_themed_question(
                self,
                _("Unsaved Changes"),
                _("This document has unsaved changes. Do you want to save them?"),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
                self.settings_manager,
            )

            if reply == QMessageBox.StandardButton.Save:
                self.tab_widget.setCurrentIndex(index)
                if not tab.save_file():  # If save is cancelled
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        
        self.tab_widget.removeTab(index)
        self.save_workspace_open_files()
        
        # Create new tab if last tab was closed
        if self.tab_widget.count() == 0:
            self.new_editor_tab()
            
    def create_menu_bar(self):
        menubar = self.menuBar()
        menubar.clear()
        menubar.setObjectName("appMenuBar")
        menubar.setAccessibleName(_("Application menu"))
        menubar.setNativeMenuBar(False)
        menubar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.translatable_menus = []

        def add_menu(title):
            menu = menubar.addMenu(_(title))
            menu.setAccessibleName(_("{title} menu").format(title=_(title)))
            menu.menuAction().setProperty("text_key", title)
            self.translatable_actions.append(menu.menuAction())
            self.translatable_menus.append((menu, title))
            return menu

        def add_action(menu, text, handler, icon_name=None, shortcut=None, tooltip=None, checkable=False):
            action = QAction(self.build_themed_icon(icon_name) if icon_name else QIcon(), _(text), self)
            action.setProperty("text_key", text)
            action.setProperty("tooltip_key", tooltip or text)
            action.setProperty("accessibility_label", tooltip or text)
            action.setToolTip(_(tooltip or text))
            action.setStatusTip(_(tooltip or text))
            action.setWhatsThis(_(tooltip or text))
            action.setCheckable(checkable)
            if shortcut is not None:
                action.setShortcut(shortcut)
            if handler:
                action.triggered.connect(handler)
            menu.addAction(action)
            self.translatable_actions.append(action)
            if icon_name:
                self.icon_actions.append((action, icon_name))
            return action

        # File menu
        file_menu = add_menu("File")

        add_action(
            file_menu,
            "New Editor Tab",
            self.new_editor_tab,
            "new",
            QKeySequence.StandardKey.New,
            "Create a new editor tab"
        )
        file_menu.addSeparator()
        add_action(file_menu, "Open...", self.open_file_dialog, "open", QKeySequence.StandardKey.Open, "Open a file")
        add_action(file_menu, "Save", self.save_file, "save", QKeySequence.StandardKey.Save, "Save current file")
        add_action(
            file_menu,
            "Save As...",
            self.save_file_as,
            "save-as",
            QKeySequence.StandardKey.SaveAs,
            "Save current file with a new name"
        )
        add_action(file_menu, "Export as PDF...", self.export_pdf, "save-as", tooltip="Export current file as PDF")
        file_menu.addSeparator()
        add_action(file_menu, "Settings", self.show_settings, "settings", tooltip="Open Settings")
        file_menu.addSeparator()
        add_action(file_menu, "Close Tab", self.close_current_tab, shortcut=QKeySequence.StandardKey.Close, tooltip="Close current tab")
        add_action(file_menu, "Exit", self.close, shortcut=QKeySequence.StandardKey.Quit, tooltip="Exit Jottr")

        # Edit menu
        edit_menu = add_menu("Edit")
        add_action(edit_menu, "Undo", self.undo, "undo", QKeySequence.StandardKey.Undo, "Undo")
        add_action(edit_menu, "Redo", self.redo, "redo", QKeySequence.StandardKey.Redo, "Redo")
        edit_menu.addSeparator()
        add_action(edit_menu, "Cut", self.cut, shortcut=QKeySequence.StandardKey.Cut, tooltip="Cut")
        add_action(edit_menu, "Copy", self.copy, shortcut=QKeySequence.StandardKey.Copy, tooltip="Copy")
        add_action(edit_menu, "Paste", self.paste, shortcut=QKeySequence.StandardKey.Paste, tooltip="Paste")
        edit_menu.addSeparator()
        add_action(edit_menu, "Find/Replace", self.toggle_find, "find", QKeySequence.StandardKey.Find, "Find/Replace")
        add_action(edit_menu, "Editor Font", self.show_editor_font_dialog, "font", tooltip="Choose Editor Font")

        # View menu
        view_menu = add_menu("View")

        add_action(view_menu, "Toggle Snippets", self.toggle_snippets, "snippets", QKeySequence("Ctrl+Shift+N"), "Toggle Snippets")
        add_action(
            view_menu,
            "Toggle Markdown Preview",
            self.toggle_markdown_preview,
            "insert-text",
            QKeySequence("Ctrl+Shift+M"),
            "Toggle Markdown Preview"
        )
        add_action(
            view_menu,
            "Focus Mode",
            self.toggle_focus_mode,
            "focus-mode",
            QKeySequence("Ctrl+Shift+D"),
            "Focus Mode",
            True
        )
        view_menu.addSeparator()

        add_action(view_menu, "Zoom In", self.zoom_in, "zoom-in", QKeySequence("Ctrl+="), "Zoom In")
        add_action(view_menu, "Zoom Out", self.zoom_out, "zoom-out", QKeySequence("Ctrl+-"), "Zoom Out")
        add_action(view_menu, "Reset Zoom", self.zoom_reset, "zoom-reset", QKeySequence("Ctrl+0"), "Reset Zoom")

        # Workspace menu
        workspace_menu = add_menu("Workspace")
        add_action(workspace_menu, "Open Workspace...", self.open_workspace_dialog, "document-open", tooltip="Open Workspace")
        add_action(workspace_menu, "New Workspace File...", self.create_workspace_file, "new", tooltip="New File in Workspace")

        # Plugins menu
        if (
            self.plugin_manager.registry.commands
            or self.plugin_manager.registry.panels
            or self.plugin_manager.registry.sidebar_items
        ):
            plugins_menu = add_menu("Plugins")
            seen_plugin_targets = set()
            for panel in self.plugin_manager.registry.panels + self.plugin_manager.registry.sidebar_items:
                title = panel.get("title") or panel.get("id") or "Plugin Panel"
                target_key = panel.get("panel") or panel.get("panelId") or panel.get("id") or title
                if target_key in seen_plugin_targets:
                    continue
                seen_plugin_targets.add(target_key)
                handler = (
                    (lambda checked=False, item=panel: self.trigger_plugin_action(item))
                    if panel.get("builtin")
                    else (lambda checked=False, item=panel: self.open_plugin_panel(item))
                )
                add_action(
                    plugins_menu,
                    title,
                    handler,
                    tooltip=title
                )
            if self.plugin_manager.registry.commands and plugins_menu.actions():
                plugins_menu.addSeparator()
            for command in self.plugin_manager.registry.commands:
                title = command.get("title") or command.get("id") or "Plugin Command"
                shortcut = QKeySequence(command["shortcut"]) if command.get("shortcut") else None
                add_action(
                    plugins_menu,
                    title,
                    lambda checked=False, item=command: self.trigger_plugin_action(item),
                    shortcut=shortcut,
                    tooltip=title
                )

        # Help menu
        help_menu = add_menu("Help")
        add_action(help_menu, "Help", self.show_help, "help", QKeySequence.StandardKey.HelpContents, "Open Help")
        add_action(help_menu, "About", self.show_about, "about", tooltip="About Jottr")

    def close_current_tab(self):
        """Close the active document tab from the menubar or shortcut."""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            self.close_tab(current_index)

    def save_file(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.save_file()
            
    def open_file(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.open_file()

    def new_editor_tab(self):
        """Create a new empty editor tab"""
        editor_tab = EditorTab(self.snippet_manager, self.settings_manager)
        editor_tab.set_main_window(self)  # Set reference to main window
        
        # Add tab with default title
        self.tab_widget.addTab(
            editor_tab,
            self.build_themed_icon("snippets"),
            _("Document {number}").format(number=self.tab_widget.count() + 1)
        )
        self.tab_widget.setCurrentWidget(editor_tab)
        editor_tab.editor.setFocus()
        self.save_workspace_open_files()
        return editor_tab
        
    def new_rss_tab(self):
        rss_tab = RSSTab()
        self.tab_widget.addTab(rss_tab, _("RSS Reader"))
        self.tab_widget.setCurrentWidget(rss_tab)

    def apply_editor_font_to_tabs(self, font):
        """Apply the selected editor font to all open editor tabs."""
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab):
                tab.update_font(font)

    def show_editor_font_dialog(self):
        dialog = FontSelectionDialog(
            self.settings_manager.get_font("editor"),
            self,
            title=_("Choose Editor Font")
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            font = dialog.selectedFont()
            self.settings_manager.save_font(font, "editor")
            self.apply_editor_font_to_tabs(font)

    def apply_editor_theme_to_tabs(self, theme_name):
        """Apply an editor color theme to all open editor tabs."""
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab):
                tab.apply_theme(theme_name)

    def toggle_snippets(self):
        """Toggle snippets pane in current tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.toggle_pane("snippets")

    def open_file_path(self, file_path):
        """Open a file by its path"""
        return self.open_file(file_path)

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
        """Handle application close event"""
        if self.handle_unsaved_changes():
            self.save_workspace_markdown_files()
            self.save_workspace_open_files()
            # Save window state
            self.settings_manager.save_setting('window_state', {
                'geometry': self.saveGeometry().toBase64().data().decode(),
                'state': self.saveState().toBase64().data().decode()
            })
            event.accept()
        else:
            event.ignore()

    def open_external_url(self, url):
        """Open URL in system's default browser"""
        QDesktopServices.openUrl(QUrl(url))

    def show_help(self):
        """Show help documentation"""
        help_tab = self.new_editor_tab()
        
        # Load help content
        try:
            help_path = find_data_file("help", "help.md")
            if help_path is None:
                raise FileNotFoundError("help/help.md")
            with open(help_path, 'r', encoding='utf-8') as f:
                help_content = f.read()
        except Exception:
            help_content = _("Help documentation not found.")
        
        # Set content and make read-only
        help_tab.editor.setPlainText(help_content)
        help_tab.editor.setReadOnly(True)
        help_tab.set_markdown_preview_visible(True)
        
        # Set tab title
        current_index = self.tab_widget.indexOf(help_tab)
        self.tab_widget.setTabText(current_index, _("Help"))

    def show_about(self):
        """Show about dialog"""
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle(_("About {APP_NAME}").format(APP_NAME=APP_NAME))
        about_dialog.setMinimumWidth(400)
        apply_dialog_window_icon(about_dialog, "about", self.settings_manager)
        
        layout = QVBoxLayout(about_dialog)
        layout.setSpacing(10)
        
        # App name
        title_label = QLabel(APP_NAME)
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # Version
        version_label = QLabel(_("Version {APP_VERSION}").format(APP_VERSION=APP_VERSION))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        
        # Description
        desc_label = QLabel(_("A simple text editor for writers, journalists and researchers"))
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)
        
        # Add some spacing
        layout.addSpacing(10)
        
        # Developer
        dev_label = QLabel(_("Developed by mFat"))
        dev_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(dev_label)
        
        # License
        license_label = QLabel(_("Licensed under GNU GPL v3.0"))
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(license_label)
        
        # Homepage link
        link_label = QLabel(_('<a href="{APP_HOMEPAGE}">Project Homepage</a>').format(APP_HOMEPAGE=APP_HOMEPAGE))
        link_label.setOpenExternalLinks(True)
        link_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(link_label)
        
        # Add button box
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(about_dialog.accept)
        button_box.setCenterButtons(True)  # Center the OK button
        layout.addWidget(button_box)
        
        about_dialog.exec()

    def toggle_focus_mode(self):
        """Toggle focus mode for current editor tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.toggle_focus_mode()

    def update_focus_mode_action(self, checked):
        """Keep the focus toolbar action in sync with the active editor."""
        if hasattr(self, 'focus_mode_action'):
            self.focus_mode_action.setChecked(checked)

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
            default_font = self.settings_manager.get_font("editor")
            # Preserve current font properties except size
            new_font = QFont(current_tab.current_font)
            new_font.setPointSize(default_font.pointSize())
            current_tab.update_font(new_font)

    

    def apply_settings_from_view(self, settings_view):
        settings = settings_view.get_data()
        self.settings_manager.save_setting('homepage', settings['homepage'])
        self.settings_manager.save_setting('search_sites', settings['search_sites'])
        self.settings_manager.save_setting('user_dictionary', settings['user_dictionary'])
        self.settings_manager.save_custom_themes(settings['custom_themes'])
        self.settings_manager.save_ui_theme(settings['ui_theme'])
        self.settings_manager.save_theme(settings['theme'])
        self.settings_manager.save_setting('language', settings['language'])
        set_language(settings['language'])
        self.apply_layout_direction(settings['language'])
        self.apply_language_direction_to_tabs()
        self.retranslate_actions()
        self.settings_manager.save_setting('icon_contrast', settings['icon_contrast'])
        self.settings_manager.save_setting('enable_animations', settings['enable_animations'])
        self.settings_manager.save_font(settings['ui_font'], "ui")
        self.settings_manager.save_setting('markdown_scroll_sync', settings['markdown_scroll_sync'])
        self.settings_manager.save_setting('editor_line_numbers', settings['editor_line_numbers'])
        self.settings_manager.save_setting(
            'double_click_empty_tab_bar_new_tab',
            settings['double_click_empty_tab_bar_new_tab']
        )
        self.settings_manager.save_setting(
            'double_click_tab_closes_tab',
            settings['double_click_tab_closes_tab']
        )
        self.settings_manager.save_setting('autosave_enabled', settings['autosave_enabled'])
        self.settings_manager.save_setting('autosave_interval_seconds', settings['autosave_interval_seconds'])
        self.settings_manager.save_setting('plugins_directory', settings['plugins_directory'])
        self.settings_manager.save_setting('plugin_registry_url', settings['plugin_registry_url'])
        self.settings_manager.save_setting('plugin_registry_checksum_url', settings['plugin_registry_checksum_url'])
        self.settings_manager.save_setting('plugin_channels', settings.get('plugin_channels', []))
        self.settings_manager.save_setting('plugin_channel_filter', settings.get('plugin_channel_filter', 'all'))
        self.settings_manager.save_setting('plugin_state', settings['plugin_state'])
        self.plugin_manager = PluginManager(self.settings_manager)
        self.plugin_manager.refresh()
        self.plugin_manager.activate_enabled_plugins()
        self.removeToolBar(self.toolbar)
        self.toolbar.deleteLater()
        self.setup_toolbar()
        self.apply_app_style()
        self.create_menu_bar()
        self.apply_editor_theme_to_tabs(settings['theme'])
        self.apply_editor_line_numbers(settings['editor_line_numbers'])
        self.apply_autosave_settings()
        self.statusBar.showMessage(_("Settings applied"), 3000)

    def close_settings_tab(self, settings_view):
        index = self.tab_widget.indexOf(settings_view)
        if index >= 0:
            self.tab_widget.removeTab(index)
        if self.tab_widget.count() == 0:
            self.new_editor_tab()

    def show_settings(self):
        """Open settings as a workspace tab."""
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if getattr(tab, "is_settings_tab", False):
                self.tab_widget.setCurrentIndex(index)
                return tab
        settings_tab = SettingsDialog(
            self.settings_manager,
            self,
            embedded=True,
            apply_callback=self.apply_settings_from_view,
            close_callback=self.close_settings_tab,
        )
        settings_tab.is_settings_tab = True
        self.tab_widget.addTab(settings_tab, self.build_themed_icon("settings"), _("Settings"))
        self.tab_widget.setCurrentWidget(settings_tab)
        return settings_tab

    def trigger_plugin_action(self, action):
        builtin = action.get("builtin")
        if builtin and self.run_builtin_plugin_action(builtin):
            return
        command_id = action.get("command") or action.get("commandId") or action.get("id")
        if command_id in self.plugin_manager.registry.command_callbacks:
            self.plugin_manager.registry.command_callbacks[command_id]()
            return
        panel_id = action.get("panel") or action.get("panelId")
        if panel_id:
            panel = self.find_plugin_panel(panel_id)
            if panel:
                self.open_plugin_panel(panel)
                return
        message = action.get("message")
        if message:
            QMessageBox.information(self, _("Plugin"), message)

    def run_builtin_plugin_action(self, action_id):
        actions = {
            "toggle_browser": self.toggle_browser,
            "toggle_markdown_preview": self.toggle_markdown_preview,
            "new_rss_tab": self.new_rss_tab,
        }
        handler = actions.get(action_id)
        if not handler:
            return False
        handler()
        return True

    def find_plugin_panel(self, panel_id):
        for panel in self.plugin_manager.registry.panels + self.plugin_manager.registry.sidebar_items:
            if panel.get("id") == panel_id:
                return panel
        return None

    def open_plugin_panel(self, panel):
        panel_id = panel.get("id")
        title = panel.get("title") or panel_id or _("Plugin")
        if panel_id not in self.plugin_manager.registry.panel_factories and panel.get("type") == "python":
            plugin_name = panel.get("plugin")
            if plugin_name:
                try:
                    self.plugin_manager.install_plugin_from_registry(plugin_name)
                    self.plugin_manager.activate_enabled_plugins()
                except Exception as exc:
                    QMessageBox.warning(
                        self,
                        _("Plugin"),
                        _("Could not install plugin: {error}").format(error=exc)
                    )
        if panel_id in self.plugin_manager.registry.panel_factories:
            widget = self.plugin_manager.registry.panel_factories[panel_id]()
        else:
            widget = self.create_manifest_plugin_panel(panel)
        self.tab_widget.addTab(widget, title)
        self.tab_widget.setCurrentWidget(widget)

    def create_manifest_plugin_panel(self, panel):
        panel_type = panel.get("type", "text")
        if panel_type in {"browser", "web"}:
            view = QWebEngineView()
            url = panel.get("url") or panel.get("homepage") or "about:blank"
            view.load(QUrl(url))
            return view
        if panel_type == "rss":
            return RSSTab()
        label = QLabel(panel.get("content") or panel.get("description") or _("Plugin panel"))
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        return label

    def toggle_browser(self):
        """Toggle browser pane in current tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.toggle_pane("browser")

    def apply_editor_line_numbers(self, visible):
        """Apply line number visibility to all open editor tabs."""
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, EditorTab):
                tab.set_line_numbers_visible(visible)

    def apply_autosave_settings(self):
        """Apply autosave settings to all open editor tabs."""
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, EditorTab):
                tab.configure_autosave_timer()

    def toggle_markdown_preview(self):
        """Toggle markdown preview in current editor tab"""
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.toggle_markdown_preview()

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

    def export_pdf(self):
        """Export the current editor tab as a PDF."""
        current_tab = self.tab_widget.currentWidget()
        if current_tab and hasattr(current_tab, "export_pdf"):
            current_tab.export_pdf()

    def show_menu_dropdown(self):
        """Show the menu dropdown under the menu button"""
        # Find the menu button
        menu_button = None
        for action in self.toolbar.actions():
            if action.property("text_key") == "Menu" or action.text() == _("Menu"):
                menu_button = self.toolbar.widgetForAction(action)
                break
        
        if menu_button:
            # Show menu below the button
            pos = menu_button.mapToGlobal(menu_button.rect().bottomLeft())
            self.menu_dropdown.popup(pos)

    def eventFilter(self, obj, event):
        """Handle double-click on the tab bar."""
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if obj == self.tab_widget.tabBar():
                tab_index = self.tab_widget.tabBar().tabAt(event.pos())
                if tab_index >= 0 and self.settings_manager.get_setting("double_click_tab_closes_tab", True):
                    self.close_tab(tab_index)
                    return True
                if tab_index == -1 and self.settings_manager.get_setting("double_click_empty_tab_bar_new_tab", True):
                    self.new_editor_tab()
                    return True
                return False
            if (
                obj == self.tab_widget
                and self.is_tab_strip_position(event.pos())
            ):
                if self.settings_manager.get_setting("double_click_empty_tab_bar_new_tab", True):
                    self.new_editor_tab()
                    return True
                return False
        return super().eventFilter(obj, event)  # Let other events pass through

    def is_tab_strip_position(self, pos):
        """Return whether a QTabWidget-local position is in the top tab strip."""
        if hasattr(pos, "toPoint"):
            pos = pos.toPoint()
        tab_bar = self.tab_widget.tabBar()
        tab_bar_top = tab_bar.mapTo(self.tab_widget, tab_bar.rect().topLeft()).y()
        tab_bar_bottom = tab_bar_top + max(tab_bar.height(), 1)
        return tab_bar_top <= pos.y() <= tab_bar_bottom

    def open_file_dialog(self):
        """Open file from dialog"""
        self.open_file()

    def open_file(self, file_path=None):
        """Open a file immediately, reusing an empty untitled tab when possible."""
        if file_path is None:
            # Show file dialog if no path provided
            file_path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                _("Open File"),
                "",
                _("Markdown Files (*.md *.markdown);;Text Files (*.txt);;All Files (*.*)")
            )
            if not file_path:  # User cancelled
                return

        file_path = os.path.abspath(file_path)

        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if getattr(tab, "current_file", None) and os.path.abspath(tab.current_file) == file_path:
                self.tab_widget.setCurrentIndex(index)
                tab.editor.setFocus()
                return True
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, _("Error"), _("Could not open file: {error}").format(error=str(e)))
            return False

        editor_tab = self.reusable_empty_editor_tab()
        if editor_tab is None:
            editor_tab = EditorTab(self.snippet_manager, self.settings_manager)
            editor_tab.set_main_window(self)
            self.tab_widget.addTab(editor_tab, self.build_themed_icon("snippets"), os.path.basename(file_path))
        else:
            current_index = self.tab_widget.indexOf(editor_tab)
            self.tab_widget.setTabText(current_index, os.path.basename(file_path))
            self.update_tab_icon(current_index)

        editor_tab.editor.setPlainText(content)
        editor_tab.current_file = file_path
        editor_tab.editor.document().setModified(False)
        if editor_tab.is_markdown_file(file_path):
            editor_tab.set_markdown_preview_visible(True)
        else:
            editor_tab.set_markdown_preview_visible(False)
        
        self.tab_widget.setCurrentWidget(editor_tab)
        editor_tab.editor.setFocus()
        self.save_workspace_open_files()
        return True

    def reusable_empty_editor_tab(self):
        """Return an untouched untitled editor tab that can be replaced by an opened file."""
        current_tab = self.tab_widget.currentWidget()
        if not isinstance(current_tab, EditorTab):
            return None
        if getattr(current_tab, "current_file", None):
            return None
        if current_tab.editor.toPlainText():
            return None
        if current_tab.editor.document().isModified():
            return None
        return current_tab

    # Add a new method to set up the find shortcut
    def setup_shortcuts(self):
        """Set up additional keyboard shortcuts"""
        find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)  # Typically Ctrl+F
        find_shortcut.activated.connect(self.toggle_find)
        markdown_shortcut = QShortcut(QKeySequence("Ctrl+Shift+M"), self)
        markdown_shortcut.activated.connect(self.toggle_markdown_preview)

    def handle_unsaved_changes(self):
        """Handle unsaved changes before closing"""
        unsaved_tabs = []
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if self.is_editor_tab_modified(tab):
                unsaved_tabs.append(i)
        
        if unsaved_tabs:
            reply = ask_themed_question(
                self,
                _("Unsaved Changes"),
                _("You have unsaved changes. Do you want to save them before closing?"),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
                self.settings_manager,
            )

            if reply == QMessageBox.StandardButton.Save:
                for i in unsaved_tabs:
                    self.tab_widget.setCurrentIndex(i)
                    if not self.tab_widget.widget(i).save_file():  # If save is cancelled
                        return False
                return True
            elif reply == QMessageBox.StandardButton.Cancel:
                return False
            # If Discard, continue with close
        
        return True
