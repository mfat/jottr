"""Main application window."""
import os
import json
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSplitter, QToolBar, QMessageBox, QLabel, QDialog, QSizePolicy, QMenu,
    QDialogButtonBox, QToolButton, QTabBar, QWidgetAction, QFrame,
    QGraphicsOpacityEffect, QApplication, QComboBox,
)
from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QEvent, QPropertyAnimation,
    QEasingCurve, QParallelAnimationGroup, QSize, pyqtSignal,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import (
    QAction, QActionGroup, QIcon, QDesktopServices,
    QKeySequence, QFont, QPalette,
)

from jottr.editor_tab import EditorTab
from jottr.snippet_manager import SnippetManager
from jottr.rss_tab import RSSTab
from jottr.theme_manager import ThemeManager
from jottr.qt_style import apply_qt_color_scheme, apply_qt_style, refresh_styled_widgets, resolve_qt_style_key
from jottr.settings_manager import SettingsManager
from jottr.settings_dialog import SettingsDialog
from jottr.translation_manager import _, format_language_label, is_rtl_language, set_language
from jottr.font_dialog import FontSelectionDialog
from jottr.plugin_manager import PluginManager
from jottr.file_dialogs import get_open_file_name
from jottr.editor.case_transform import (
    apply_capitalize,
    apply_lowercase,
    apply_uppercase,
)
from jottr.editor.spellcheck import (
    DOCUMENT_LANGUAGE_AUTO,
    get_document_language,
    list_document_language_choices,
    match_dictionary_for_language,
    missing_dictionary_message,
    resolve_document_language,
)
from jottr.icon_manager import (
    apply_dialog_window_icon,
    ask_themed_question,
    build_themed_icon as render_bundled_icon,
    load_app_icon,
    load_bundled_icon_paths,
    resolve_icon_color,
    resolve_icon_mode_colors,
)
from jottr.paths import find_data_file
from jottr import __version__
from jottr.ui.workspace_controller import WorkspaceControllerMixin
from jottr.ui.document_tab_bar import DocumentTabWidget

APP_NAME = "Jottr"
APP_VERSION = __version__
APP_HOMEPAGE = "https://github.com/mfat/jottr"


class EditorThemeCard(QFrame):
    """Palette-style theme preview card for View → Editor Theme."""

    SELECT_COLOR = "#2563eb"
    SAMPLE_LINES = ("The quick brown", "fox jumps over", "the lazy dog")

    def __init__(self, name, theme, selected=False, parent=None):
        super().__init__(parent)
        self.theme_name = name
        self._theme = ThemeManager.normalize_theme(theme) or ThemeManager.get_theme(
            ThemeManager.DEFAULT_THEME_NAME
        )
        self._selected = False
        self.setObjectName("editorThemeCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(168, 112)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        self._name_label = QLabel(name, self)
        self._name_label.setObjectName("editorThemeCardName")
        name_font = QFont(self._name_label.font())
        name_font.setBold(True)
        name_font.setPointSize(max(9, name_font.pointSize()))
        self._name_label.setFont(name_font)
        header.addWidget(self._name_label, 1)

        self._check = QLabel("✓", self)
        self._check.setObjectName("editorThemeCardCheck")
        self._check.setFixedSize(18, 18)
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self._check, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self._sample = QLabel("\n".join(self.SAMPLE_LINES), self)
        self._sample.setObjectName("editorThemeCardSample")
        sample_font = QFont("DejaVu Sans Mono")
        if sample_font.family() != "DejaVu Sans Mono":
            sample_font = QFont("monospace")
        sample_font.setPointSize(9)
        self._sample.setFont(sample_font)
        self._sample.setWordWrap(False)
        root.addWidget(self._sample, 1)

        self.set_selected(selected)

    def is_selected(self):
        return self._selected

    def set_selected(self, selected):
        self._selected = bool(selected)
        editor = self._theme["editor"]
        background = editor.get("background", "#ffffff")
        foreground = editor.get("foreground", "#000000")
        idle_border = editor.get("border") or foreground
        if not ThemeManager.is_valid_color(idle_border):
            idle_border = "#888888"
        border = self.SELECT_COLOR if self._selected else idle_border
        border_width = 3 if self._selected else 1
        self.setStyleSheet(
            f"""
            QFrame#editorThemeCard {{
                background-color: {background};
                border: {border_width}px solid {border};
                border-radius: 8px;
            }}
            QLabel#editorThemeCardName,
            QLabel#editorThemeCardSample {{
                color: {foreground};
                background: transparent;
            }}
            QLabel#editorThemeCardCheck {{
                color: #ffffff;
                background-color: {self.SELECT_COLOR};
                border-radius: 9px;
                font-weight: bold;
                font-size: 11px;
            }}
            """
        )
        self._check.setVisible(self._selected)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            parent = self.parentWidget()
            while parent is not None and not isinstance(parent, EditorThemeGrid):
                parent = parent.parentWidget()
            if isinstance(parent, EditorThemeGrid):
                parent.theme_chosen.emit(self.theme_name)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class EditorThemeGrid(QWidget):
    """Palette grid of editor theme preview cards."""

    COLUMNS = 3
    theme_chosen = pyqtSignal(str)

    def __init__(self, themes, current, parent=None):
        super().__init__(parent)
        self.setObjectName("editorThemeGrid")
        self._cards = {}
        # Compatibility alias used by menu sync/tests.
        self._buttons = self._cards

        layout = QGridLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)

        for index, (name, theme) in enumerate(themes.items()):
            card = EditorThemeCard(name, theme, selected=(name == current), parent=self)
            row, column = divmod(index, self.COLUMNS)
            layout.addWidget(card, row, column, Qt.AlignmentFlag.AlignCenter)
            self._cards[name] = card

    def set_current(self, name):
        for theme_name, card in self._cards.items():
            card.set_selected(theme_name == name)


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

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(load_app_icon())
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize managers first
        self.settings_manager = SettingsManager()
        self.snippet_manager = SnippetManager(self.settings_manager)
        self.plugin_manager = PluginManager(self.settings_manager)
        self.plugin_manager.refresh()
        self.plugin_manager.activate_enabled_plugins()

        # Logical name -> Qt resource path for the selected bundled icon theme
        self.icons = load_bundled_icon_paths(self.settings_manager.get_icon_theme())
        self.workspace_path = ""

        # Shared QActions power both toolbar and menubar (one action, many surfaces).
        self.setup_toolbar()
        self.create_menu_bar()
        
        # Create status bar (simplified)
        self.statusBar = self.statusBar()
        
        # Set initial status message
        self.statusBar.showMessage(_("Words: 0 | Characters: 0"))
        self.statusBar.setObjectName("statusBar")
        self.document_language_combo = QComboBox()
        self.document_language_combo.setObjectName("documentLanguageCombo")
        self.document_language_combo.setToolTip(_("Document language for spell checking"))
        self.document_language_combo.setMinimumContentsLength(18)
        self.document_language_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        self._populate_document_language_combo(self.document_language_combo)
        self.document_language_combo.currentIndexChanged.connect(
            self._on_status_document_language_changed
        )
        self.statusBar.addPermanentWidget(QLabel(_("Language:")))
        self.statusBar.addPermanentWidget(self.document_language_combo)
        self.document_language_status = QLabel()
        self.document_language_status.setObjectName("documentLanguageStatus")
        self.statusBar.addPermanentWidget(self.document_language_status)
        self.update_document_language_status()
        
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
        self.setup_workspace_explorer()

        self.tab_widget = DocumentTabWidget()
        self.tab_widget.setObjectName("documentTabs")
        self.tab_widget.setDocumentMode(False)
        self.tab_widget.setMovable(True)
        self.tab_widget.setUsesScrollButtons(True)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setIconSize(QSize(16, 16))
        self.tab_widget.tabBar().setExpanding(False)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.update_document_language_status)
        self.tab_widget.currentChanged.connect(self.update_status_bar_visibility)
        self.tab_widget.currentChanged.connect(self.update_edit_actions)
        self.tab_widget.tabBar().tabs_changed.connect(self.refresh_tab_close_buttons)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.dataChanged.connect(self.update_edit_actions)
        
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

        self.update_edit_actions()
        self.apply_app_style()

    def apply_app_style(self, font=None):
        """Apply widget style, Qt color scheme, UI font, and matching chrome."""
        scheme_setting = self.settings_manager.get_ui_theme()
        app_font = QFont(font) if font is not None else self.settings_manager.get_font("ui")
        application = QApplication.instance()
        if application:
            # Only drop stylesheets when the widget style actually swaps;
            # the clears each force a full repolish, while palette/font/theme
            # switches just need the sheets re-applied below.
            theme = ThemeManager.get_ui_theme(scheme_setting, application)
            next_key = resolve_qt_style_key(
                self.settings_manager.get_qt_style(), theme=theme
            )
            if application.property("_jottr_style_key") != next_key:
                # Drop stylesheets before setStyle so the widget style can take effect.
                # Forget the cached sheet too — otherwise an unchanged theme/font
                # skips re-apply and chrome stays unstyled (compact toolbars).
                application.setStyleSheet("")
                self.setStyleSheet("")
                self._applied_app_stylesheet = None
            apply_qt_color_scheme(scheme_setting, application)
            apply_qt_style(
                self.settings_manager.get_qt_style(),
                application,
                theme=theme,
            )
            ThemeManager.apply_app_palette(application, theme)
            application.setFont(app_font)
        else:
            theme = ThemeManager.get_ui_theme(scheme_setting)
        ThemeManager.apply_app_palette(self, theme)
        self.setFont(app_font)
        stylesheet = ThemeManager.build_app_stylesheet(
            theme,
            app_font,
            toolbar_style=self.settings_manager.get_toolbar_style(),
        )
        if application:
            # The window inherits the application stylesheet; keep a
            # window-level override only to clear a stale one, so a repeat
            # apply costs one repolish instead of two. Qt normalizes the
            # sheet on set, so compare against the string we applied.
            if self.styleSheet():
                self.setStyleSheet("")
            if stylesheet != getattr(self, "_applied_app_stylesheet", None):
                application.setStyleSheet(stylesheet)
                self._applied_app_stylesheet = stylesheet
        elif self.styleSheet() != stylesheet:
            self.setStyleSheet(stylesheet)
        if application:
            refresh_styled_widgets(application)
            self.apply_chrome_ui_font(app_font, application)
        # Rebuild icons so styles cannot keep synthesized Selected/Disabled tints.
        self._themed_icon_cache = {}
        self.update_action_icons()
        self.refresh_tab_icons()

    def apply_chrome_ui_font(self, app_font, application=None):
        """Push Main UI Font onto menus, tabs, status, settings, and side panels."""
        app = application or QApplication.instance()
        app_font = QFont(app_font)

        menubar = self.menuBar()
        if menubar is not None:
            menubar.setFont(app_font)

        if hasattr(self, "tab_widget") and self.tab_widget is not None:
            self.tab_widget.setFont(app_font)
            tab_bar = self.tab_widget.tabBar()
            if tab_bar is not None:
                tab_bar.setFont(app_font)

        if hasattr(self, "toolbar") and self.toolbar is not None:
            self.toolbar.setFont(app_font)

        status = getattr(self, "statusBar", None)
        if callable(status):
            status = status()
        if status is not None:
            status.setFont(app_font)
            for child in status.findChildren(QWidget):
                child.setFont(app_font)
                if isinstance(child, QComboBox) and child.view() is not None:
                    child.view().setFont(app_font)

        for name in (
            "workspaceExplorer",
            "workspaceTree",
            "workspaceTitle",
            "workspacePath",
            "workspaceHeader",
        ):
            for widget in self.findChildren(QWidget, name):
                widget.setFont(app_font)
                for child in widget.findChildren(QWidget):
                    child.setFont(app_font)

        if app is not None:
            for widget in app.allWidgets():
                if isinstance(widget, QMenu):
                    widget.setFont(app_font)
                elif isinstance(widget, SettingsDialog):
                    widget.apply_ui_font(app_font)

        if hasattr(self, "tab_widget") and self.tab_widget is not None:
            for index in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(index)
                apply_ui = getattr(tab, "apply_ui_font", None)
                if callable(apply_ui):
                    apply_ui(app_font)

    def get_icon_color(self):
        """Return the configured icon color for the active app theme."""
        return resolve_icon_color(self.settings_manager)

    def build_themed_icon(self, icon_name):
        """Tint a bundled symbolic SVG with explicit modes (cached).

        Selected/Disabled pixmaps are required so QStyle.generatedIconPixmap
        does not invent a style-specific tint after widget-style switches.
        """
        color = self.get_icon_color()
        selected_color, disabled_color = resolve_icon_mode_colors(
            self.settings_manager
        )
        key = (icon_name, color, selected_color, disabled_color)
        cache = getattr(self, "_themed_icon_cache", None)
        if cache is None:
            cache = self._themed_icon_cache = {}
        icon = cache.get(key)
        if icon is None:
            icon = render_bundled_icon(
                self.icons.get(icon_name, ""),
                color,
                selected_color=selected_color,
                disabled_color=disabled_color,
            )
            cache[key] = icon
        return QIcon(icon)

    def update_action_icons(self):
        if not hasattr(self, "icon_actions"):
            return
        for action, icon_name in self.icon_actions:
            action.setIcon(self.build_themed_icon(icon_name))

    def tab_icon_name_for_widget(self, tab):
        if getattr(tab, "is_settings_tab", False):
            return "settings"
        if isinstance(tab, EditorTab) or hasattr(tab, "current_file"):
            return "document"
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

    def _set_action_tooltip(self, action, text):
        action.setProperty("tooltip_key", text)
        translated = _(text)
        action.setToolTip(translated)
        action.setStatusTip(translated)
        action.setWhatsThis(translated)

    def _make_action(
        self,
        text,
        handler=None,
        *,
        icon_name=None,
        shortcut=None,
        tooltip=None,
        checkable=False,
    ):
        """Create a QAction shared by toolbar and menubar."""
        translated_text = _(text)
        if icon_name and icon_name in self.icons:
            action = QAction(self.build_themed_icon(icon_name), translated_text, self)
            self.icon_actions.append((action, icon_name))
            # Keep menus text-only while toolbar still shows the icon.
            action.setIconVisibleInMenu(False)
        else:
            action = QAction(translated_text, self)
        action.setProperty("text_key", text)
        tip = tooltip or text
        action.setProperty("tooltip_key", tip)
        action.setProperty("accessibility_label", tip)
        self._set_action_tooltip(action, tip)
        action.setCheckable(checkable)
        if shortcut is not None:
            action.setShortcut(shortcut)
        if handler:
            action.triggered.connect(handler)
        self.translatable_actions.append(action)
        return action

    def create_shared_actions(self):
        """Define each command once for toolbar + menubar (Python GUIs QAction pattern)."""
        self.icon_actions = []
        self.translatable_actions = []

        self.new_action = self._make_action(
            "New Editor Tab",
            self.new_editor_tab,
            icon_name="new",
            shortcut=QKeySequence.StandardKey.New,
            tooltip="Create a new editor tab",
        )
        self.open_action = self._make_action(
            "Open...",
            self.open_file_dialog,
            icon_name="open",
            shortcut=QKeySequence.StandardKey.Open,
            tooltip="Open a file",
        )
        self.save_action = self._make_action(
            "Save",
            self.save_file,
            icon_name="save",
            shortcut=QKeySequence.StandardKey.Save,
            tooltip="Save current file",
        )
        self.save_as_action = self._make_action(
            "Save As...",
            self.save_file_as,
            shortcut=QKeySequence.StandardKey.SaveAs,
            tooltip="Save current file with a new name",
        )
        self.export_pdf_action = self._make_action(
            "Export as PDF...",
            self.export_pdf,
            tooltip="Export current file as PDF",
        )
        self.close_tab_action = self._make_action(
            "Close Tab",
            self.close_current_tab,
            shortcut=QKeySequence.StandardKey.Close,
            tooltip="Close current tab",
        )
        self.exit_action = self._make_action(
            "Exit",
            self.close,
            shortcut=QKeySequence.StandardKey.Quit,
            tooltip="Exit Jottr",
        )

        self.undo_action = self._make_action(
            "Undo",
            self.undo,
            icon_name="undo",
            shortcut=QKeySequence.StandardKey.Undo,
            tooltip="Undo",
        )
        self.redo_action = self._make_action(
            "Redo",
            self.redo,
            icon_name="redo",
            shortcut=QKeySequence.StandardKey.Redo,
            tooltip="Redo",
        )
        self.cut_action = self._make_action(
            "Cut", self.cut, shortcut=QKeySequence.StandardKey.Cut, tooltip="Cut"
        )
        self.copy_action = self._make_action(
            "Copy", self.copy, shortcut=QKeySequence.StandardKey.Copy, tooltip="Copy"
        )
        self.paste_action = self._make_action(
            "Paste", self.paste, shortcut=QKeySequence.StandardKey.Paste, tooltip="Paste"
        )
        # Kate/KTextEditor: cut/copy need a selection; paste needs pasteable clipboard.
        self.cut_action.setEnabled(False)
        self.copy_action.setEnabled(False)
        self.paste_action.setEnabled(False)
        self.select_all_action = self._make_action(
            "Select All",
            self.select_all,
            shortcut=QKeySequence.StandardKey.SelectAll,
            tooltip="Select All",
        )
        # Kate/KTextEditor Tools capitalization shortcuts (Selection ▸ Capitalization).
        self.uppercase_action = self._make_action(
            "Uppercase",
            self.uppercase,
            shortcut=QKeySequence("Ctrl+U"),
            tooltip="Convert the selection to uppercase, or the character to the right of the cursor",
        )
        self.lowercase_action = self._make_action(
            "Lowercase",
            self.lowercase,
            shortcut=QKeySequence("Ctrl+Shift+U"),
            tooltip="Convert the selection to lowercase, or the character to the right of the cursor",
        )
        self.capitalize_action = self._make_action(
            "Capitalize",
            self.capitalize,
            shortcut=QKeySequence("Ctrl+Alt+U"),
            tooltip="Capitalize the selection, or the word under the cursor",
        )
        self.find_action = self._make_action(
            "Find/Replace",
            self.toggle_find,
            icon_name="find",
            shortcut=QKeySequence.StandardKey.Find,
            tooltip="Find/Replace",
        )
        self.editor_font_action = self._make_action(
            "Editor Font",
            self.show_editor_font_dialog,
            icon_name="font",
            tooltip="Choose Editor Font",
        )
        self.editor_theme_action = self._make_action(
            "Editor Theme",
            self.show_editor_theme_popup,
            icon_name="theme",
            tooltip="Choose Editor Theme",
        )

        self.snippets_action = self._make_action(
            "Toggle Snippets",
            self.toggle_snippets,
            icon_name="snippets",
            shortcut=QKeySequence("Ctrl+Shift+N"),
            tooltip="Toggle Snippets",
        )
        self.markdown_action = self._make_action(
            "Toggle Markdown Preview",
            self.toggle_markdown_preview,
            icon_name="markdown",
            shortcut=QKeySequence("Ctrl+Shift+M"),
            tooltip="Toggle Markdown Preview",
        )
        self.focus_mode_action = self._make_action(
            "Focus Mode",
            self.toggle_focus_mode,
            icon_name="focus-mode",
            shortcut=QKeySequence("Ctrl+Shift+D"),
            tooltip="Focus Mode",
            checkable=True,
        )
        self.zoom_in_action = self._make_action(
            "Zoom In",
            self.zoom_in,
            icon_name="zoom-in",
            shortcut=QKeySequence("Ctrl+="),
            tooltip="Zoom In (Ctrl+=)",
        )
        self.zoom_out_action = self._make_action(
            "Zoom Out",
            self.zoom_out,
            icon_name="zoom-out",
            shortcut=QKeySequence("Ctrl+-"),
            tooltip="Zoom Out (Ctrl+-)",
        )
        self.zoom_reset_action = self._make_action(
            "Reset Zoom",
            self.zoom_reset,
            icon_name="zoom-reset",
            shortcut=QKeySequence("Ctrl+0"),
            tooltip="Reset Zoom (Ctrl+0)",
        )

        self.spell_check_action = self._make_action(
            "Automatic Spell Checking",
            self.toggle_spell_check,
            shortcut=QKeySequence("Ctrl+Shift+O"),
            tooltip="Toggle automatic spell checking",
            checkable=True,
        )
        self.spell_check_action.setChecked(
            bool(self.settings_manager.get_setting("spell_check", True))
        )
        self.settings_action = self._make_action(
            "Settings", self.show_settings, tooltip="Open Settings"
        )
        self.open_workspace_action = self._make_action(
            "Open Workspace...",
            self.open_workspace_dialog,
            tooltip="Open Workspace",
        )
        self.new_workspace_file_action = self._make_action(
            "New File...",
            self.create_workspace_file,
            tooltip="New File in Workspace",
        )
        self.new_workspace_folder_action = self._make_action(
            "New Folder...",
            self.create_workspace_folder,
            tooltip="New Folder in Workspace",
        )
        self.close_workspace_action = self._make_action(
            "Close Workspace",
            self.close_workspace,
            tooltip="Close Workspace",
        )
        self.clear_missing_workspaces_action = self._make_action(
            "Clear Missing Workspaces",
            self.clear_missing_workspaces,
            tooltip="Remove missing folders from recent workspaces",
        )
        self.update_workspace_actions()
        self.help_action = self._make_action(
            "Help",
            self.show_help,
            shortcut=QKeySequence.StandardKey.HelpContents,
            tooltip="Open Help",
        )
        self.about_action = self._make_action(
            "About", self.show_about, tooltip="About Jottr"
        )

    def setup_toolbar(self):
        """Setup the main toolbar from shared QActions."""
        self.toolbar = QToolBar(_("Main Toolbar"))
        self.toolbar.setObjectName("mainToolBar")
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.addToolBar(self.toolbar)
        self.toolbar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.toolbar.customContextMenuRequested.connect(self.show_toolbar_context_menu)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        self.create_shared_actions()
        self.setup_toolbar_style_actions()

        self.toolbar.addAction(self.new_action)
        self.toolbar.addAction(self.open_action)
        self.toolbar.addAction(self.save_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.undo_action)
        self.toolbar.addAction(self.redo_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.find_action)
        self.toolbar.addAction(self.focus_mode_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.editor_font_action)
        self.toolbar.addAction(self.markdown_action)

        for toolbar_action in self.plugin_manager.registry.toolbar_actions:
            title = toolbar_action.get("title") or toolbar_action.get("id") or _("Plugin")
            action = self._make_action(
                title,
                lambda checked=False, item=toolbar_action: self.trigger_plugin_action(item),
                icon_name=toolbar_action.get("icon") or None,
                shortcut=(
                    QKeySequence(toolbar_action["shortcut"])
                    if toolbar_action.get("shortcut")
                    else None
                ),
                tooltip=toolbar_action.get("tooltip", title),
            )
            self.toolbar.addAction(action)

        self.toolbar.addSeparator()
        self.toolbar.addAction(self.zoom_in_action)
        self.toolbar.addAction(self.zoom_out_action)
        self.toolbar.addAction(self.zoom_reset_action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.toolbar.addWidget(spacer)
        self.toolbar.addAction(self.editor_theme_action)
        self.toolbar.addAction(self.snippets_action)

        def update_overflow_button():
            overflow_button = self.toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
            if overflow_button:
                overflow_button.setText(">>")
                overflow_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        QTimer.singleShot(0, update_overflow_button)

    def retranslate_actions(self):
        """Refresh toolbar and menubar labels after the active language changes."""
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
                plain = _(title).replace("&", "")
                menu.setAccessibleName(_("{title} menu").format(title=plain))

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
            return getattr(current_tab, "editor", None)
        return None

    def update_edit_actions(self, *_args):
        """Enable cut/copy only with a selection; paste when clipboard can paste.

        Matches Kate/KTextEditor (selection gates cut/copy) and Qt's canPaste().
        """
        editor = self.get_current_editor()
        previous = getattr(self, "_edit_action_editor", None)
        if editor is not previous:
            if previous is not None:
                try:
                    previous.copyAvailable.disconnect(self._on_copy_available)
                except (TypeError, RuntimeError):
                    pass
            self._edit_action_editor = editor
            if editor is not None:
                editor.copyAvailable.connect(self._on_copy_available)

        has_selection = bool(editor is not None and editor.textCursor().hasSelection())
        can_paste = bool(editor is not None and editor.canPaste())
        self.cut_action.setEnabled(has_selection)
        self.copy_action.setEnabled(has_selection)
        self.paste_action.setEnabled(can_paste)

    def _on_copy_available(self, available):
        """QTextEdit.copyAvailable tracks selection for cut/copy."""
        self.cut_action.setEnabled(available)
        self.copy_action.setEnabled(available)
        
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
        if editor and editor.textCursor().hasSelection():
            editor.cut()
            
    def copy(self):
        editor = self.get_current_editor()
        if editor and editor.textCursor().hasSelection():
            editor.copy()
            
    def paste(self):
        editor = self.get_current_editor()
        if editor and editor.canPaste():
            editor.paste()

    def select_all(self):
        editor = self.get_current_editor()
        if editor:
            editor.selectAll()

    def uppercase(self):
        apply_uppercase(self.get_current_editor())

    def lowercase(self):
        apply_lowercase(self.get_current_editor())

    def capitalize(self):
        apply_capitalize(self.get_current_editor())
        
    def new_tab(self):
        editor_tab = EditorTab(self.snippet_manager)
        self.tab_widget.addTab(
            editor_tab,
            self.build_themed_icon("document"),
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
        # Native bar on macOS (HIG); in-window elsewhere so chrome QSS can match the toolbar.
        menubar.setNativeMenuBar(sys.platform == "darwin")
        menubar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.translatable_menus = []

        def add_menu(title):
            menu = menubar.addMenu(_(title))
            plain = _(title).replace("&", "")
            menu.setAccessibleName(_("{title} menu").format(title=plain))
            menu.menuAction().setProperty("text_key", title)
            self.translatable_actions.append(menu.menuAction())
            self.translatable_menus.append((menu, title))
            return menu

        def add_menu_only_action(menu, text, handler, shortcut=None, tooltip=None, checkable=False):
            action = self._make_action(
                text,
                handler,
                shortcut=shortcut,
                tooltip=tooltip,
                checkable=checkable,
            )
            menu.addAction(action)
            return action

        # File menu
        file_menu = add_menu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addSeparator()
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addAction(self.export_pdf_action)
        file_menu.addSeparator()
        file_menu.addAction(self.close_tab_action)
        file_menu.addAction(self.exit_action)

        # Edit menu
        edit_menu = add_menu("&Edit")
        edit_menu.aboutToShow.connect(self.update_edit_actions)
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)
        edit_menu.addAction(self.select_all_action)
        capitalization_menu = edit_menu.addMenu(_("Capitalization"))
        capitalization_menu.setAccessibleName(
            _("{title} menu").format(title=_("Capitalization"))
        )
        capitalization_menu.menuAction().setProperty("text_key", "Capitalization")
        self.translatable_actions.append(capitalization_menu.menuAction())
        self.translatable_menus.append((capitalization_menu, "Capitalization"))
        capitalization_menu.addAction(self.uppercase_action)
        capitalization_menu.addAction(self.lowercase_action)
        capitalization_menu.addAction(self.capitalize_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.find_action)

        # View menu
        view_menu = add_menu("&View")
        view_menu.addAction(self.snippets_action)
        view_menu.addAction(self.markdown_action)
        view_menu.addAction(self.focus_mode_action)
        view_menu.addSeparator()
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addAction(self.zoom_reset_action)
        view_menu.addSeparator()
        view_menu.addAction(self.editor_font_action)

        toolbar_style_menu = view_menu.addMenu(_("Toolbar Style"))
        toolbar_style_menu.setAccessibleName(
            _("{title} menu").format(title=_("Toolbar Style"))
        )
        toolbar_style_menu.menuAction().setProperty("text_key", "Toolbar Style")
        self.translatable_actions.append(toolbar_style_menu.menuAction())
        self.translatable_menus.append((toolbar_style_menu, "Toolbar Style"))
        self.setup_toolbar_style_actions()
        for action in self.toolbar_style_actions.actions():
            toolbar_style_menu.addAction(action)
        self.sync_toolbar_style_menu()

        color_scheme_menu = view_menu.addMenu(_("Color Scheme"))
        color_scheme_menu.setAccessibleName(
            _("{title} menu").format(title=_("Color Scheme"))
        )
        color_scheme_menu.menuAction().setProperty("text_key", "Color Scheme")
        self.translatable_actions.append(color_scheme_menu.menuAction())
        self.translatable_menus.append((color_scheme_menu, "Color Scheme"))
        self.color_scheme_menu = color_scheme_menu
        self.color_scheme_actions = QActionGroup(self)
        self.color_scheme_actions.setExclusive(True)
        current_scheme = self.settings_manager.get_ui_theme()
        for scheme_id, label_key in (
            ("System", "Follow system"),
            ("Light", "Light"),
            ("Dark", "Dark"),
        ):
            action = QAction(_(label_key), self)
            action.setCheckable(True)
            action.setData(scheme_id)
            action.setProperty("text_key", label_key)
            action.setChecked(scheme_id == current_scheme)
            action.triggered.connect(
                lambda checked=False, tag=scheme_id: self.set_ui_color_scheme(tag)
            )
            self.color_scheme_actions.addAction(action)
            self.translatable_actions.append(action)
            color_scheme_menu.addAction(action)

        editor_theme_menu = view_menu.addMenu(_("Editor Theme"))
        editor_theme_menu.setAccessibleName(
            _("{title} menu").format(title=_("Editor Theme"))
        )
        editor_theme_menu.menuAction().setProperty("text_key", "Editor Theme")
        self.translatable_actions.append(editor_theme_menu.menuAction())
        self.translatable_menus.append((editor_theme_menu, "Editor Theme"))
        self.editor_theme_menu = editor_theme_menu
        self.editor_theme_grid = None
        editor_theme_menu.aboutToShow.connect(self.refresh_editor_theme_menu)
        self.refresh_editor_theme_menu()

        # Tools menu
        tools_menu = add_menu("&Tools")
        tools_menu.addAction(self.spell_check_action)
        document_language_menu = tools_menu.addMenu(_("Document Language"))
        document_language_menu.setAccessibleName(
            _("{title} menu").format(title=_("Document Language"))
        )
        document_language_menu.menuAction().setProperty("text_key", "Document Language")
        self.translatable_actions.append(document_language_menu.menuAction())
        self.translatable_menus.append((document_language_menu, "Document Language"))
        self.document_language_actions = QActionGroup(self)
        self.document_language_actions.setExclusive(True)
        current_document_language = get_document_language(self.settings_manager)
        for language in list_document_language_choices(extra=[current_document_language]):
            if language == DOCUMENT_LANGUAGE_AUTO:
                label = _("Auto-detect")
            else:
                matched = match_dictionary_for_language(language)
                label = format_language_label(language)
                if not matched:
                    label = _("{language} (dictionary not installed)").format(language=label)
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(language)
            action.setChecked(language == current_document_language)
            action.triggered.connect(
                lambda checked=False, tag=language: self.set_document_language(tag)
            )
            self.document_language_actions.addAction(action)
            document_language_menu.addAction(action)

        tools_menu.addSeparator()
        tools_menu.addAction(self.settings_action)

        # Workspace menu (recent entries rebuilt on aboutToShow)
        self.workspace_menu = add_menu("&Workspace")
        self.workspace_menu.aboutToShow.connect(self.refresh_workspace_menu)
        self.refresh_workspace_menu()

        # Plugins menu
        if (
            self.plugin_manager.registry.commands
            or self.plugin_manager.registry.panels
            or self.plugin_manager.registry.sidebar_items
        ):
            plugins_menu = add_menu("&Plugins")
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
                add_menu_only_action(plugins_menu, title, handler, tooltip=title)
            if self.plugin_manager.registry.commands and plugins_menu.actions():
                plugins_menu.addSeparator()
            for command in self.plugin_manager.registry.commands:
                title = command.get("title") or command.get("id") or "Plugin Command"
                shortcut = QKeySequence(command["shortcut"]) if command.get("shortcut") else None
                add_menu_only_action(
                    plugins_menu,
                    title,
                    lambda checked=False, item=command: self.trigger_plugin_action(item),
                    shortcut=shortcut,
                    tooltip=title,
                )

        # Help menu
        help_menu = add_menu("&Help")
        help_menu.addAction(self.help_action)
        help_menu.addAction(self.about_action)

    def show_editor_theme_popup(self, _checked=False):
        """Open the Editor Theme palette under the toolbar button."""
        if not hasattr(self, "editor_theme_menu") or self.editor_theme_menu is None:
            return
        self.refresh_editor_theme_menu()
        button = None
        if hasattr(self, "toolbar"):
            for child in self.toolbar.findChildren(QToolButton):
                if child.defaultAction() is self.editor_theme_action:
                    button = child
                    break
        if button is not None:
            self.editor_theme_menu.popup(button.mapToGlobal(button.rect().bottomLeft()))
        else:
            from PyQt6.QtGui import QCursor

            self.editor_theme_menu.popup(QCursor.pos())

    def close_current_tab(self):
        """Close the active document tab from the menubar or shortcut."""
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            self.close_tab(current_index)

    def save_file(self):
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.save_file()

    def new_editor_tab(self):
        """Create a new empty editor tab"""
        editor_tab = EditorTab(self.snippet_manager, self.settings_manager)
        editor_tab.set_main_window(self)  # Set reference to main window
        
        # Add tab with default title
        self.tab_widget.addTab(
            editor_tab,
            self.build_themed_icon("document"),
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

    def apply_editor_theme_to_tabs(self, theme_name, force=False):
        """Apply an editor color theme to all open editor tabs.

        force=True re-applies even when the tab already has this theme name
        (needed when a custom theme's colors change without a rename).
        """
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if not isinstance(tab, EditorTab):
                continue
            if force or getattr(tab, "current_theme", None) != theme_name:
                tab.apply_theme(theme_name)

    def refresh_editor_theme_menu(self):
        """Rebuild View → Editor Theme as a color-tile grid."""
        if not hasattr(self, "editor_theme_menu") or self.editor_theme_menu is None:
            return

        menu = self.editor_theme_menu
        menu.clear()
        self.editor_theme_grid = None

        themes = ThemeManager.get_themes(self.settings_manager.get_custom_themes())
        current = self.settings_manager.get_theme()
        if current not in themes and themes:
            current = next(iter(themes))

        grid = EditorThemeGrid(themes, current)
        grid.theme_chosen.connect(self._on_editor_theme_grid_chosen)
        action = QWidgetAction(self)
        action.setDefaultWidget(grid)
        menu.addAction(action)
        self.editor_theme_grid = grid

    def _on_editor_theme_grid_chosen(self, theme_name):
        self.set_editor_theme(theme_name)
        if self.editor_theme_menu is not None:
            self.editor_theme_menu.close()

    def sync_editor_theme_menu(self):
        """Mark the active Editor Theme swatch without rebuilding the grid."""
        grid = getattr(self, "editor_theme_grid", None)
        if grid is None:
            return
        current = self.settings_manager.get_theme()
        if current not in grid._cards:
            self.refresh_editor_theme_menu()
            return
        grid.set_current(current)

    def sync_color_scheme_menu(self):
        """Mark the active Color Scheme entry in View → Color Scheme."""
        if not hasattr(self, "color_scheme_actions") or self.color_scheme_actions is None:
            return
        current = self.settings_manager.get_ui_theme()
        for action in self.color_scheme_actions.actions():
            action.blockSignals(True)
            action.setChecked(action.data() == current)
            action.blockSignals(False)

    def setup_toolbar_style_actions(self):
        """Exclusive Comfy / Default actions shared by View and toolbar menus."""
        from jottr.settings_manager import TOOLBAR_STYLE_COMFY, TOOLBAR_STYLE_DEFAULT

        if getattr(self, "toolbar_style_actions", None) is not None:
            return
        self.toolbar_style_actions = QActionGroup(self)
        self.toolbar_style_actions.setExclusive(True)
        current = self.settings_manager.get_toolbar_style()
        for style_id, label_key in (
            (TOOLBAR_STYLE_COMFY, "Comfy"),
            (TOOLBAR_STYLE_DEFAULT, "Default"),
        ):
            action = QAction(_(label_key), self)
            action.setCheckable(True)
            action.setData(style_id)
            action.setProperty("text_key", label_key)
            action.setChecked(style_id == current)
            action.triggered.connect(
                lambda checked=False, tag=style_id: self.set_toolbar_style(tag)
            )
            self.toolbar_style_actions.addAction(action)
            self.translatable_actions.append(action)

    def sync_toolbar_style_menu(self):
        """Mark the active Toolbar Style entry in View / context menus."""
        if getattr(self, "toolbar_style_actions", None) is None:
            return
        current = self.settings_manager.get_toolbar_style()
        for action in self.toolbar_style_actions.actions():
            action.blockSignals(True)
            action.setChecked(action.data() == current)
            action.blockSignals(False)

    def set_toolbar_style(self, style_name):
        """Persist Toolbar Style and restyle chrome."""
        from jottr.settings_manager import SettingsManager

        style_name = SettingsManager.normalize_toolbar_style(style_name)
        if style_name == self.settings_manager.get_toolbar_style():
            self.sync_toolbar_style_menu()
            return
        self.settings_manager.save_toolbar_style(style_name)
        self.apply_app_style()
        self.sync_toolbar_style_menu()

    def show_toolbar_context_menu(self, pos):
        """Right-click on the main toolbar: Comfy / Default density."""
        self.setup_toolbar_style_actions()
        self.sync_toolbar_style_menu()
        menu = QMenu(self)
        menu.setTitle(_("Toolbar Style"))
        for action in self.toolbar_style_actions.actions():
            menu.addAction(action)
        menu.exec(self.toolbar.mapToGlobal(pos))

    def set_ui_color_scheme(self, scheme):
        """Persist Color Scheme from the View menu and restyle the app."""
        scheme = ThemeManager.normalize_ui_theme(scheme)
        if scheme == self.settings_manager.get_ui_theme():
            self.sync_color_scheme_menu()
            return
        self.settings_manager.save_ui_theme(scheme)
        self.apply_app_style()
        self.sync_color_scheme_menu()
        self.sync_toolbar_style_menu()

    def set_editor_theme(self, theme_name):
        """Persist Editor Theme from the View menu and apply it to open tabs."""
        themes = ThemeManager.get_themes(self.settings_manager.get_custom_themes())
        if theme_name not in themes:
            theme_name = ThemeManager.DEFAULT_THEME_NAME
        if theme_name == self.settings_manager.get_theme():
            self.sync_editor_theme_menu()
            return
        self.settings_manager.save_theme(theme_name)
        self.apply_editor_theme_to_tabs(theme_name)
        self.sync_editor_theme_menu()

    def apply_spell_check_to_tabs(self):
        """Reload spell dictionaries and rehighlight tabs whose backend changed."""
        changed = False
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab) and hasattr(tab, "highlighter"):
                if tab.highlighter.apply_spell_settings():
                    changed = True
        if changed:
            self.update_document_language_status()
        return changed

    def _populate_document_language_combo(self, combo):
        """Fill a document-language combo without emitting change signals."""
        current = get_document_language(self.settings_manager)
        combo.blockSignals(True)
        combo.clear()
        for language in list_document_language_choices(extra=[current]):
            if language == DOCUMENT_LANGUAGE_AUTO:
                label = _("Auto-detect")
            else:
                label = format_language_label(language)
                if not match_dictionary_for_language(language):
                    label = _("{language} (no dictionary)").format(language=label)
            combo.addItem(label, language)
        index = combo.findData(current)
        if index < 0:
            combo.addItem(format_language_label(current), current)
            index = combo.findData(current)
        combo.setCurrentIndex(max(0, index))
        combo.blockSignals(False)

    def _on_status_document_language_changed(self, _index=None):
        language = self.document_language_combo.currentData()
        if language:
            self.set_document_language(language)

    def update_status_bar_visibility(self, _index=None):
        """Hide the status bar while the Settings tab is active."""
        if not hasattr(self, "statusBar") or not hasattr(self, "tab_widget"):
            return
        tab = self.tab_widget.currentWidget()
        self.statusBar.setVisible(not getattr(tab, "is_settings_tab", False))

    def update_document_language_status(self):
        """Show document language and missing-dictionary warnings in the status bar."""
        if not hasattr(self, "document_language_status"):
            return

        configured = get_document_language(self.settings_manager)
        if hasattr(self, "document_language_combo"):
            self._populate_document_language_combo(self.document_language_combo)

        current_tab = self.tab_widget.currentWidget() if hasattr(self, "tab_widget") else None
        highlighter = getattr(current_tab, "highlighter", None) if current_tab else None

        confidence = None
        if highlighter is not None and highlighter.resolved_document_language is not None:
            effective = highlighter.resolved_document_language
            matched = highlighter.spell_languages[0] if highlighter.spell_languages else None
            confidence = highlighter.detection_confidence
        else:
            # Resolving only needs document text for auto-detect; explicit
            # languages skip the copy entirely. Sample the first blocks so a
            # large open file cannot stall the status bar.
            text = ""
            if configured == DOCUMENT_LANGUAGE_AUTO:
                editor = getattr(current_tab, "editor", None) if current_tab else None
                document = editor.document() if editor is not None else None
                if document is not None:
                    parts = []
                    total = 0
                    block = document.firstBlock()
                    while block.isValid() and total < 4000:
                        chunk = block.text()
                        parts.append(chunk)
                        total += len(chunk) + 1
                        block = block.next()
                    text = "\n".join(parts)[:4000]
            effective, matched, confidence = resolve_document_language(
                self.settings_manager,
                text=text,
            )

        if configured == DOCUMENT_LANGUAGE_AUTO:
            from jottr.editor.spellcheck import USE_LANGDETECT
            if not USE_LANGDETECT:
                label = _("Auto (langdetect missing)")
            elif effective == DOCUMENT_LANGUAGE_AUTO:
                label = _("Auto")
            else:
                label = _("Auto → {language}").format(
                    language=format_language_label(effective)
                )
                if isinstance(confidence, float):
                    label = _("{label} ({confidence:.0%})").format(
                        label=label,
                        confidence=confidence,
                    )
        else:
            label = format_language_label(configured)

        if matched:
            self.document_language_status.setText(
                _("Dict: {dictionary}").format(dictionary=matched)
            )
            if configured == DOCUMENT_LANGUAGE_AUTO and confidence is False:
                self.document_language_status.setToolTip(
                    _(
                        "Using {language} until the document language is detected.\n"
                        "Dictionary: {dictionary}"
                    ).format(language=label, dictionary=matched)
                )
            else:
                self.document_language_status.setToolTip(
                    _("Document language: {language}\nUsing dictionary {dictionary}").format(
                        language=label,
                        dictionary=matched,
                    )
                )
            self.document_language_status.setStyleSheet("")
        elif configured == DOCUMENT_LANGUAGE_AUTO and effective == DOCUMENT_LANGUAGE_AUTO:
            self.document_language_status.setText(label)
            self.document_language_status.setToolTip(
                _("Auto-detect needs a bit more text, then loads a matching dictionary.")
            )
            self.document_language_status.setStyleSheet("")
        else:
            warning = missing_dictionary_message(effective)
            self.document_language_status.setText(_("No dictionary"))
            self.document_language_status.setToolTip(
                _("Document language: {language}\n{warning}").format(
                    language=label,
                    warning=warning,
                )
            )
            self.document_language_status.setStyleSheet("color: #c0392b;")
            if bool(self.settings_manager.get_setting("spell_check", True)):
                self.statusBar.showMessage(warning, 8000)

    def set_document_language(self, language):
        """Set the document language used for spell checking (`auto` or a locale)."""
        language = str(language).replace("-", "_")
        if language.lower() == DOCUMENT_LANGUAGE_AUTO:
            language = DOCUMENT_LANGUAGE_AUTO
        self.settings_manager.save_setting("document_language", language)
        if language == DOCUMENT_LANGUAGE_AUTO:
            self.settings_manager.save_setting("spell_languages", [])
        else:
            matched = match_dictionary_for_language(language)
            self.settings_manager.save_setting(
                "spell_languages",
                [matched] if matched else []
            )
        if hasattr(self, "document_language_actions"):
            for action in self.document_language_actions.actions():
                action.blockSignals(True)
                action.setChecked(action.data() == language)
                action.blockSignals(False)
        if hasattr(self, "document_language_combo"):
            self._populate_document_language_combo(self.document_language_combo)
        self.apply_spell_check_to_tabs()
        if language != DOCUMENT_LANGUAGE_AUTO and not match_dictionary_for_language(language):
            QMessageBox.warning(
                self,
                _("Dictionary Not Installed"),
                missing_dictionary_message(language),
            )

    def sync_spell_check_ui(self, enabled):
        """Keep the Tools menu action and open Settings tabs in sync."""
        enabled = bool(enabled)
        if hasattr(self, "spell_check_action") and self.spell_check_action is not None:
            self.spell_check_action.blockSignals(True)
            self.spell_check_action.setChecked(enabled)
            self.spell_check_action.blockSignals(False)
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            checkbox = getattr(tab, "spell_check_enabled", None)
            if checkbox is not None:
                checkbox.blockSignals(True)
                checkbox.setChecked(enabled)
                checkbox.blockSignals(False)
        self.update_document_language_status()

    def toggle_spell_check(self, checked=None):
        """Toggle automatic spell checking from Tools."""
        if checked is None:
            checked = not bool(self.settings_manager.get_setting("spell_check", True))
        enabled = bool(checked)
        self.settings_manager.save_setting("spell_check", enabled)
        self.sync_spell_check_ui(enabled)
        self.apply_spell_check_to_tabs()

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

    def rebuild_chrome(self):
        """Reload icons and rebuild toolbar + menu bar (extracted from full apply)."""
        self.icons = load_bundled_icon_paths(self.settings_manager.get_icon_theme())
        self._themed_icon_cache = {}
        self.removeToolBar(self.toolbar)
        self.toolbar.deleteLater()
        self.setup_toolbar()
        self.create_menu_bar()

    def apply_settings_domain(self, domain):
        """Apply one settings domain immediately (instant-apply path).

        The settings tab persists each control to SettingsManager first, then
        calls here so only the affected subsystem rebuilds.
        """
        sm = self.settings_manager
        if domain == "language":
            language = sm.get_setting("language", "en_US")
            set_language(language)
            self.apply_layout_direction(language)
            self.apply_language_direction_to_tabs()
            self.retranslate_actions()
            self.rebuild_chrome()
            self.apply_app_style()
            self.sync_color_scheme_menu()
            self.sync_toolbar_style_menu()
        elif domain == "chrome":
            self.rebuild_chrome()
            self.apply_app_style()
            self.sync_color_scheme_menu()
            self.sync_toolbar_style_menu()
        elif domain == "style":
            self.apply_app_style()
            self.sync_color_scheme_menu()
            self.sync_toolbar_style_menu()
        elif domain == "editor_theme":
            # force: custom theme JSON can change without renaming the theme.
            self.apply_editor_theme_to_tabs(sm.get_theme(), force=True)
            self.refresh_editor_theme_menu()
        elif domain == "spell":
            self.apply_spell_check_to_tabs()
            self.sync_spell_check_ui(bool(sm.get_setting("spell_check", True)))
        elif domain == "lines":
            self.apply_editor_line_numbers(bool(sm.get_setting("editor_line_numbers", True)))
        elif domain == "autosave":
            self.apply_autosave_settings()
        elif domain == "plugins":
            self.plugin_manager = PluginManager(sm)
            self.plugin_manager.refresh()
            self.plugin_manager.activate_enabled_plugins()
            self.rebuild_chrome()
            self.apply_app_style()
            self.sync_color_scheme_menu()
            self.sync_toolbar_style_menu()

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


    def eventFilter(self, obj, event):
        """Handle middle-click close and double-click new-tab on the tab bar."""
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.MiddleButton
            and obj == self.tab_widget.tabBar()
        ):
            tab_index = self.tab_widget.tabBar().tabAt(event.pos())
            if tab_index >= 0 and self.settings_manager.get_setting("middle_click_tab_closes_tab", True):
                self.close_tab(tab_index)
                return True
            return False
        if event.type() == QEvent.Type.MouseButtonDblClick:
            if obj == self.tab_widget.tabBar():
                tab_index = self.tab_widget.tabBar().tabAt(event.pos())
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
            file_path, _selected_filter = get_open_file_name(
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
            self.tab_widget.addTab(editor_tab, self.build_themed_icon("document"), os.path.basename(file_path))
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
