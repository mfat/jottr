"""Main application window."""
import os
import json
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSplitter, QToolBar, QMessageBox, QLabel, QDialog, QSizePolicy, QMenu,
    QDialogButtonBox, QToolButton, QTabBar, QWidgetAction, QFrame,
    QGraphicsOpacityEffect, QApplication, QComboBox, QScrollArea,
)
from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QEvent, QPropertyAnimation,
    QEasingCurve, QParallelAnimationGroup, QSize, QSignalBlocker, pyqtSignal,
)
from PyQt6.QtGui import (
    QAction, QActionGroup, QIcon, QDesktopServices,
    QKeySequence, QFont, QPalette, QPainter, QColor,
)

from jottr.editor_tab import EditorTab
from jottr.snippet_manager import SnippetManager
from jottr.theme_manager import ThemeManager
from jottr.qt_style import apply_qt_color_scheme, apply_qt_style, refresh_styled_widgets, resolve_qt_style_key
from jottr.settings_manager import SettingsManager
from jottr.session_recovery import (
    SESSION_RESTORE_SETTING,
    SESSION_RESTORE_UNSAVED,
    SESSION_RESTORE_WORKSPACE,
    STARTUP_WORKSPACE_SETTING,
    STASH_NEW_FILES_SETTING,
    claim_session,
    is_valid_stash_id,
    swap_file_has_changes,
    read_session,
    read_stash_file,
    release_session,
    stash_file_path,
    stash_ids_on_disk,
    write_session,
)
from jottr.translation_manager import _, format_language_label, is_rtl_language, set_language
from jottr.font_dialog import FontSelectionDialog
from jottr.plugin_manager import PluginManager
from jottr.file_dialogs import get_open_file_name
from jottr.file_manager import show_in_file_manager
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


class WindowColorSchemeSwatch(QWidget):
    """Kate-style 4-quadrant Window/Button/View/Selection preview."""

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.setObjectName("windowColorSchemeSwatch")
        self._colors = colors
        self.setFixedSize(52, 52)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))
        half_w = self.width() // 2 - 1
        half_h = self.height() // 2 - 1
        painter.fillRect(1, 1, half_w, half_h, self._colors[0])
        painter.fillRect(1 + half_w, 1, half_w, half_h, self._colors[1])
        painter.fillRect(1, 1 + half_h, half_w, half_h, self._colors[2])
        painter.fillRect(1 + half_w, 1 + half_h, half_w, half_h, self._colors[3])
        painter.end()


class WindowColorSchemeCard(QFrame):
    """Preview card for View → Window Color Scheme."""

    SELECT_COLOR = "#2563eb"

    def __init__(self, scheme_id, label, colors, selected=False, parent=None):
        super().__init__(parent)
        self.scheme_id = scheme_id
        self._selected = False
        self.setObjectName("windowColorSchemeCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(148, 100)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        self._name_label = QLabel(label, self)
        self._name_label.setObjectName("windowColorSchemeCardName")
        name_font = QFont(self._name_label.font())
        name_font.setBold(True)
        name_font.setPointSize(max(9, name_font.pointSize()))
        self._name_label.setFont(name_font)
        header.addWidget(self._name_label, 1)

        self._check = QLabel("✓", self)
        self._check.setObjectName("windowColorSchemeCardCheck")
        self._check.setFixedSize(18, 18)
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self._check, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self._swatch = WindowColorSchemeSwatch(colors, self)
        root.addWidget(self._swatch, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addStretch(1)

        self.set_selected(selected)

    def is_selected(self):
        return self._selected

    def set_selected(self, selected):
        self._selected = bool(selected)
        border = self.SELECT_COLOR if self._selected else "#888888"
        border_width = 3 if self._selected else 1
        self.setStyleSheet(
            f"""
            QFrame#windowColorSchemeCard {{
                background-color: palette(window);
                border: {border_width}px solid {border};
                border-radius: 8px;
            }}
            QLabel#windowColorSchemeCardName {{
                color: palette(window-text);
                background: transparent;
            }}
            QLabel#windowColorSchemeCardCheck {{
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
            while parent is not None and not isinstance(parent, WindowColorSchemeGrid):
                parent = parent.parentWidget()
            if isinstance(parent, WindowColorSchemeGrid):
                parent.scheme_chosen.emit(self.scheme_id)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class WindowColorSchemeGrid(QWidget):
    """Palette grid of Window Color Scheme preview cards."""

    COLUMNS = 3
    scheme_chosen = pyqtSignal(str)

    def __init__(self, schemes, current, parent=None):
        super().__init__(parent)
        self.setObjectName("windowColorSchemeGrid")
        self._cards = {}

        layout = QGridLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)

        from jottr.window_color_scheme import (
            DEFAULT_WINDOW_COLOR_SCHEME,
            scheme_preview_colors,
        )

        for index, scheme in enumerate(schemes):
            label = (
                _("Default")
                if scheme.scheme_id == DEFAULT_WINDOW_COLOR_SCHEME
                else scheme.name
            )
            colors = scheme_preview_colors(scheme.path)
            card = WindowColorSchemeCard(
                scheme.scheme_id,
                label,
                colors,
                selected=(scheme.scheme_id == current),
                parent=self,
            )
            row, column = divmod(index, self.COLUMNS)
            layout.addWidget(card, row, column, Qt.AlignmentFlag.AlignCenter)
            self._cards[scheme.scheme_id] = card

    def set_current(self, scheme_id):
        for card_id, card in self._cards.items():
            card.set_selected(card_id == scheme_id)


# Kate's File > Open Recent keeps ten entries by default.
MAX_RECENT_FILES = 10


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
        app = QApplication.instance()
        app_icon = app.windowIcon() if app is not None else QIcon()
        self.setWindowIcon(app_icon if not app_icon.isNull() else load_app_icon())
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize managers first
        self.plugin_manager = PluginManager(self.settings_manager)
        self.plugin_manager.refresh()
        self.plugin_manager.activate_enabled_plugins()

        # Logical name -> Qt resource path for the selected bundled icon theme
        self.icons = load_bundled_icon_paths(self.settings_manager.get_icon_theme())
        self.workspace_path = ""
        self._startup_content_pending = True
        self._pending_startup_file = file_path
        self._session_claimed = False
        self._instant_tab = None
        # Startup stages: "pending" (shell only) -> "tab" (instant editor
        # exists) -> "editor" (icons + upgrade done) -> "done" (restored).
        self._startup_stage = "pending"

        # Shared QActions power both toolbar and menubar (one action, many surfaces).
        # Icons are filled after first paint (see _upgrade_startup_editor).
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
        self.document_language_combo.currentIndexChanged.connect(
            self._on_status_document_language_changed
        )
        self.statusBar.addPermanentWidget(QLabel(_("Language:")))
        self.statusBar.addPermanentWidget(self.document_language_combo)
        self.document_language_status = QLabel()
        self.document_language_status.setObjectName("documentLanguageStatus")
        self.statusBar.addPermanentWidget(self.document_language_status)
        
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
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setUsesScrollButtons(True)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setIconSize(QSize(0, 0))
        self.tab_widget.tabBar().setExpanding(False)
        self.tab_widget.tabBar().setDrawBase(False)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.update_document_language_status)
        self.tab_widget.currentChanged.connect(self.update_edit_actions)
        self.tab_widget.currentChanged.connect(self.save_session)
        self.tab_widget.tabBar().tabMoved.connect(self.save_session)
        self.tab_widget.tabBar().tabs_changed.connect(self.refresh_tab_close_buttons)
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.dataChanged.connect(self.update_edit_actions)
        
        # Install event filters on both the tab bar and its containing tab strip.
        self.tab_widget.tabBar().installEventFilter(self)
        self.tab_widget.installEventFilter(self)
        self.tab_widget.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_widget.tabBar().customContextMenuRequested.connect(self.show_tab_context_menu)
        
        self.main_splitter.addWidget(self.workspace_widget)
        self.main_splitter.addWidget(self.tab_widget)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setSizes([260, 940])
        layout.addWidget(self.main_splitter)

        # Bare instant editor first: typing works from first paint while the
        # heavier panes, icons, and session restore follow in idle chunks.
        self._create_instant_tab()

        # Claim the session lock before first paint; tab restore stays deferred.
        self._session_claimed = claim_session(self.settings_manager)
        if not self._session_claimed:
            # Another running Jottr owns the last session: start empty, and
            # save the session only once that instance has exited.
            self._session_loaded = True

        self.apply_app_style()
        self.watch_system_color_scheme()

        # Tests (and JOTTR_SYNC_STARTUP=1) finish content before __init__ returns
        # so existing callers can assume a ready tab. Production upgrades the
        # instant editor and restores the session in idle chunks past show().
        if self._startup_runs_sync():
            self._ensure_startup_content()
        else:
            QTimer.singleShot(0, self._upgrade_startup_editor)

    @staticmethod
    def _startup_runs_sync():
        """True when deferred startup must finish before __init__ returns."""
        # Opt into the production deferred path under pytest (timing tests).
        if os.environ.get("JOTTR_DEFER_STARTUP") == "1":
            return False
        return bool(
            os.environ.get("PYTEST_CURRENT_TEST")
            or os.environ.get("JOTTR_SYNC_STARTUP") == "1"
        )

    def _ensure_startup_content(self):
        """Finish all pending startup stages immediately (inline)."""
        if getattr(self, "_startup_stage", "done") == "pending":
            self._create_instant_tab()
        if getattr(self, "_startup_stage", "done") == "tab":
            self._upgrade_startup_editor(schedule_next=False)
        if getattr(self, "_startup_stage", "done") == "editor":
            self._finish_restored_startup()

    def _create_instant_tab(self):
        """Build the bare instant editor (chunk 0: before/during first paint)."""
        if getattr(self, "_startup_stage", "done") != "pending":
            return
        self._startup_stage = "tab"
        try:
            tab = EditorTab(self.snippet_manager, self.settings_manager, instant=True)
        except TypeError:
            tab = EditorTab(self.snippet_manager, self.settings_manager)
        tab.set_main_window(self)
        tab.untitled_title = _("Document {number}").format(
            number=self.tab_widget.count() + 1
        )
        with QSignalBlocker(self.tab_widget):
            self.tab_widget.addTab(tab, QIcon(), tab.untitled_title)
            self.tab_widget.setCurrentWidget(tab)
        self._instant_tab = tab
        self.refresh_tab_close_buttons()
        self.update_edit_actions()

    def _take_alive_instant_tab(self):
        """Return the instant tab when it is still open, else None."""
        tab = self._instant_tab
        if tab is None:
            return None
        try:
            if self.tab_widget.indexOf(tab) < 0:
                self._instant_tab = None
                return None
        except RuntimeError:
            self._instant_tab = None
            return None
        return tab

    def _instant_tab_has_user_text(self):
        """Whether the user typed into the instant tab before the upgrade."""
        tab = self._take_alive_instant_tab()
        if tab is None:
            return False
        if getattr(tab, "current_file", None):
            return False
        editor = getattr(tab, "editor", None)
        if editor is None:
            return False
        doc = getattr(editor, "document", None)
        doc_obj = doc() if callable(doc) else None
        is_modified = (
            doc_obj.isModified()
            if doc_obj is not None and hasattr(doc_obj, "isModified")
            else False
        )
        plain_text = getattr(editor, "toPlainText", None)
        text = plain_text() if callable(plain_text) else ""
        return bool(text or is_modified)

    def _focus_editor_for_typing(self):
        """Focus the current tab's editor unless the user moved focus."""
        current = self.tab_widget.currentWidget()
        editor = getattr(current, "editor", None)
        if editor is None:
            return
        focused = QApplication.focusWidget()
        if focused is None or focused is editor:
            editor.setFocus()

    def _upgrade_startup_editor(self, schedule_next=True):
        """Tint icons and finish the instant tab (chunk 1: typing works)."""
        if getattr(self, "_startup_stage", "done") != "tab":
            return
        self._startup_stage = "editor"

        self.update_action_icons()
        self._populate_document_language_combo(self.document_language_combo)

        instant = self._take_alive_instant_tab()
        if instant is not None:
            if hasattr(instant, "finish_instant_upgrade"):
                instant.finish_instant_upgrade()
            index = self.tab_widget.indexOf(instant)
            if index >= 0:
                self.update_tab_icon(index)
            self.refresh_tab_close_buttons()

        self.update_edit_actions()
        self._focus_editor_for_typing()
        if schedule_next and not self._startup_runs_sync():
            QTimer.singleShot(0, self._finish_restored_startup)

    def _drop_redundant_instant_tab(self):
        """Remove the instant tab when restored content made it redundant.

        A pristine instant tab is dropped once other tabs exist; one the user
        typed into is always kept.
        """
        instant = self._take_alive_instant_tab()
        if instant is None or self.tab_widget.count() < 2:
            return
        if getattr(instant, "current_file", None):
            return
        editor = getattr(instant, "editor", None)
        if editor is not None:
            doc = getattr(editor, "document", None)
            doc_obj = doc() if callable(doc) else None
            is_modified = (
                doc_obj.isModified()
                if doc_obj is not None and hasattr(doc_obj, "isModified")
                else False
            )
            plain_text = getattr(editor, "toPlainText", None)
            text = plain_text() if callable(plain_text) else ""
            if text or is_modified:
                return
        index = self.tab_widget.indexOf(instant)
        if index < 0:
            self._instant_tab = None
            return
        for cleanup in ("release_swap_file", "remove_stash_file"):
            handler = getattr(instant, cleanup, None)
            if callable(handler):
                handler()
        self.tab_widget.removeTab(index)
        instant.deleteLater()
        self._instant_tab = None
        self.save_workspace_open_files()

    def _finish_restored_startup(self):
        """Restore the session / open the startup file (chunk 2: full ready)."""
        if getattr(self, "_startup_stage", "done") != "editor":
            return
        self._startup_stage = "done"
        self._startup_content_pending = False

        if self._session_claimed:
            self.restore_last_run()

        if self.tab_widget.count() == 0:
            self.new_editor_tab()

        self._drop_redundant_instant_tab()

        pending = self._pending_startup_file
        self._pending_startup_file = None
        if pending:
            self.open_file_path(pending)

        if self._instant_tab_has_user_text():
            self.tab_widget.setCurrentWidget(self._instant_tab)
        self.update_edit_actions()
        self.update_document_language_status()
        self._focus_editor_for_typing()

    def restore_last_run(self):
        """Reopen the workspace and tabs of the previous run."""
        startup_workspace = self.startup_workspace()
        if startup_workspace:
            self.set_workspace_path(startup_workspace, save=True)
        else:
            self.restore_workspace(open_files=False)
        # Read before the session reopens tabs: each one saves the workspace's
        # open files again, which would drop the tabs not reopened yet.
        workspace_files = (
            self.workspace_session_files(self.workspace_path) if self.workspace_path else []
        )
        # Opening a chosen workspace still brings back unsaved work from last time.
        self.restore_session(only_unsaved=bool(startup_workspace))
        if self.workspace_path:
            # An open workspace always gets its tabs back, whichever session
            # restore mode is chosen; tabs the session reopened are kept as is.
            self.restore_workspace_session(self.workspace_path, workspace_files)

    def watch_system_color_scheme(self):
        """Re-theme chrome when the desktop switches between light and dark."""
        from jottr.system_color_scheme import (
            connect_system_color_scheme_changed,
            system_color_scheme,
        )

        self._system_color_scheme = system_color_scheme(QApplication.instance())
        return connect_system_color_scheme_changed(
            self._on_system_color_scheme_changed, QApplication.instance()
        )

    def _on_system_color_scheme_changed(self):
        """Reapply chrome when the desktop light/dark preference changes.

        Runs for Appearance System *or* Window Color Scheme Default: Default
        resolves Breeze Light/Dark from the host, and Flatpak may also remap
        explicit Light/Dark chrome when ColorScheme is pinned by the platform.
        Named .colors schemes stay put.
        """
        from jottr.system_color_scheme import system_color_scheme
        from jottr.window_color_scheme import find_window_color_scheme

        ui_theme = self.settings_manager.get_ui_theme()
        window_scheme_id = self.settings_manager.get_window_color_scheme()
        normalized = ThemeManager.normalize_ui_theme(ui_theme)
        named_scheme = bool(find_window_color_scheme(window_scheme_id).path)
        follows_desktop = normalized == "System" or not named_scheme
        scheme = system_color_scheme(QApplication.instance())
        prev = getattr(self, "_system_color_scheme", None)
        if not follows_desktop:
            return
        # Pinning Qt's scheme makes it echo colorSchemeChanged straight back;
        # only a genuinely different appearance is worth a restyle.
        if scheme == prev:
            return
        self._system_color_scheme = scheme
        # apply_app_style drops the chrome-theme cache before it resolves.
        self.apply_app_style()

    def changeEvent(self, event):
        super().changeEvent(event)
        if (
            event.type() == QEvent.Type.StyleChange
            and not getattr(self, "_applying_app_style", True)
        ):
            # QStyleSheetStyle restores the palette this window had when it was
            # first polished on every repolish (a widget style swap, the
            # deferred stylesheet restore), so put the current one back.
            self.apply_window_palette()

    def apply_window_palette(self):
        """Set this window's palette from the active Window Color Scheme."""
        from jottr.qt_style import reconcile_chrome_theme_with_color_scheme
        from jottr.window_color_scheme import (
            effective_chrome_theme,
            find_window_color_scheme,
        )

        application = QApplication.instance()
        window_scheme_id = self.settings_manager.get_window_color_scheme()
        if find_window_color_scheme(window_scheme_id).path:
            if application is not None:
                self.setPalette(application.palette())
            self.apply_tab_dimming()
            return
        ui_theme = self.settings_manager.get_ui_theme()
        theme = reconcile_chrome_theme_with_color_scheme(
            effective_chrome_theme(window_scheme_id, ui_theme, application),
            ui_theme,
            application,
        )
        ThemeManager.apply_app_palette(self, theme)
        self.apply_tab_dimming(theme)

    def apply_tab_dimming(self, theme=None):
        """Dim inactive document tabs using the chrome theme's text/muted colors.

        The active tab keeps the full text color while inactive tabs use the
        muted color. Tabs stay drawn by the widget style; only per-tab text
        colors are overridden so native styles (Breeze, Adwaita, Fusion, …)
        keep working, including named Window Color Schemes.
        """
        tab_widget = getattr(self, "tab_widget", None)
        if tab_widget is None:
            return
        setter = getattr(tab_widget, "set_tab_text_colors", None)
        if not callable(setter):
            return
        if theme is None:
            from jottr.window_color_scheme import effective_chrome_theme

            theme = effective_chrome_theme(
                self.settings_manager.get_window_color_scheme(),
                self.settings_manager.get_ui_theme(),
                QApplication.instance(),
            )
        app = theme.get("app", {}) if isinstance(theme, dict) else {}
        setter(app.get("text"), app.get("muted"))

    def apply_app_style(self, font=None):
        """Apply widget style, Qt color scheme, UI font, and matching chrome.

        Widget-style swaps follow Kate/KStyleManager: QApplication.setStyle
        first. Qt already repolishes on setStyle, so we skip a second full
        all-widgets refresh in that case.

        Window Color Scheme (Kate / KColorSchemeManager) installs a QPalette
        from a ``.colors`` file when selected; Default follows System/Light/Dark.
        """
        # changeEvent skips its palette refresh while this runs; the window
        # palette is set last below.
        self._applying_app_style = True
        try:
            self._apply_app_style(font)
        finally:
            self._applying_app_style = False

    def _apply_app_style(self, font=None):
        from jottr.qt_style import reconcile_chrome_theme_with_color_scheme
        from jottr.window_color_scheme import (
            activate_window_color_scheme,
            clear_effective_chrome_theme_cache,
            effective_chrome_theme,
            find_window_color_scheme,
            scheme_is_dark,
        )

        # Palette / System theme may have changed; keep icon chrome colors fresh.
        clear_effective_chrome_theme_cache()

        scheme_setting = self.settings_manager.get_ui_theme()
        window_scheme_id = self.settings_manager.get_window_color_scheme()
        app_font = QFont(font) if font is not None else self.settings_manager.get_font("ui")
        application = QApplication.instance()
        style_swapped = False
        window_scheme = find_window_color_scheme(window_scheme_id)
        stylesheet = ThemeManager.build_app_stylesheet(
            toolbar_style=self.settings_manager.get_toolbar_style(),
        )
        startup_sheet = (
            application.property("_jottr_startup_stylesheet") if application else None
        )
        # main() may already have applied matching chrome; skip the expensive
        # style/QSS path once on first apply. The sheet is layout-only (no
        # colors), so it still matches after a light/dark switch — never treat
        # that as "already themed" or System appearance changes stay partial.
        chrome_preapplied = (
            font is None
            and application is not None
            and not getattr(self, "_app_style_applied", False)
            and startup_sheet
            and startup_sheet == stylesheet
            and application.styleSheet() == startup_sheet
            and application.property("_jottr_style_key") is not None
        )
        if chrome_preapplied:
            # Consume the one-shot marker so later apply_app_style calls (System
            # dark mode, Settings, …) run the full color-scheme/palette path.
            application.setProperty("_jottr_startup_stylesheet", None)
        if application:
            # Only drop stylesheets when the widget style actually swaps;
            # the clears each force a full repolish, while palette/font/theme
            # switches just need the sheets re-applied below.
            theme = effective_chrome_theme(
                window_scheme_id, scheme_setting, application
            )
            # Qt ColorScheme hint: explicit Window Color Scheme forces Light/Dark;
            # Default uses the Appearance System/Light/Dark setting.
            if not chrome_preapplied:
                if window_scheme.path:
                    color_scheme_setting = (
                        "Dark" if scheme_is_dark(window_scheme.path) else "Light"
                    )
                    apply_qt_color_scheme(color_scheme_setting, application)
                else:
                    color_scheme_setting = scheme_setting
                    apply_qt_color_scheme(scheme_setting, application)
                    # Only Default chrome may be remapped when the platform refuses
                    # Light/Dark pins. Named .colors schemes keep their own palette;
                    # reconciling them to Dark would paint dark QSS over a light
                    # Breeze Classic (etc.) palette.
                    theme = reconcile_chrome_theme_with_color_scheme(
                        theme, color_scheme_setting, application
                    )
                next_key = resolve_qt_style_key(
                    self.settings_manager.get_qt_style(),
                    theme=theme,
                    application=application,
                )
                if application.property("_jottr_style_key") != next_key:
                    # Drop stylesheets before setStyle so the widget style can take effect.
                    # Forget the cached sheet too — otherwise an unchanged theme/font
                    # skips re-apply and chrome stays unstyled (compact toolbars).
                    application.setStyleSheet("")
                    self.setStyleSheet("")
                    self._applied_app_stylesheet = None
                    application.setProperty("_jottr_startup_stylesheet", None)
                previous_key = application.property("_jottr_style_key")
                apply_qt_style(
                    self.settings_manager.get_qt_style(),
                    application,
                    theme=theme,
                )
                style_swapped = previous_key != application.property("_jottr_style_key")
                activate_window_color_scheme(window_scheme_id, application)
                if not window_scheme.path:
                    ThemeManager.apply_app_palette(application, theme)
                application.setFont(app_font)
            else:
                self._applied_app_stylesheet = stylesheet
        else:
            theme = effective_chrome_theme(window_scheme_id, scheme_setting)
        self.setFont(app_font)
        if application and not chrome_preapplied:
            # The window inherits the application stylesheet; keep a
            # window-level override only to clear a stale one, so a repeat
            # apply costs one repolish instead of two. Qt normalizes the
            # sheet on set, so compare against the string we applied.
            if self.styleSheet():
                self.setStyleSheet("")
            if stylesheet != getattr(self, "_applied_app_stylesheet", None):
                application.setStyleSheet(stylesheet)
                self._applied_app_stylesheet = stylesheet
                # Only main.apply_startup_app_chrome owns this property.
                application.setProperty("_jottr_startup_stylesheet", None)
        elif not application and self.styleSheet() != stylesheet:
            self.setStyleSheet(stylesheet)
        if application:
            # setStyle already unpolish/polish; only repolish for palette/font/
            # QSS-only updates (Kate does nothing beyond setStyle).
            if not style_swapped and not chrome_preapplied:
                refresh_styled_widgets(application)
            self.apply_chrome_ui_font(app_font, application)
        # Last, because QStyleSheetStyle remembers the palette a widget had
        # when it first polished it and restores that on every later repolish:
        # set before the stylesheet, the window would keep its first theme's
        # colors forever and palette-tinted icons would stay light.
        if not window_scheme.path:
            ThemeManager.apply_app_palette(self, theme)
        else:
            self.setPalette(application.palette() if application else self.palette())
        self.apply_tab_dimming(theme)
        # Rebuild icons so styles cannot keep synthesized Selected/Disabled tints.
        # During deferred startup, icons are filled in _upgrade_startup_editor.
        if getattr(self, "_app_style_applied", False):
            self._themed_icon_cache = {}
        self._app_style_applied = True
        if not getattr(self, "_startup_content_pending", False):
            self.update_action_icons()
            self.refresh_tab_icons()
        # The Settings window is top-level, so it does not inherit this
        # window's palette; refresh it the same way.
        settings_dialog = getattr(self, "_settings_dialog", None)
        if settings_dialog is not None:
            settings_dialog.apply_dialog_palette()

    def apply_widget_style(self):
        """Kate/KStyleManager path: QApplication.setStyle without stylesheet wrap.

        An application QSS makes Qt wrap the style in QStyleSheetStyle, and
        polish then dominates with a large widget tree. Kate has no app QSS,
        so setStyle stays cheap. Clear QSS around setStyle, then restore
        chrome styles on the next event-loop tick.
        """
        application = QApplication.instance()
        if application is None:
            return None
        from jottr.qt_style import reconcile_chrome_theme_with_color_scheme
        from jottr.window_color_scheme import (
            effective_chrome_theme,
            find_window_color_scheme,
        )

        window_scheme_id = self.settings_manager.get_window_color_scheme()
        ui_theme = self.settings_manager.get_ui_theme()
        theme = effective_chrome_theme(window_scheme_id, ui_theme, application)
        if not find_window_color_scheme(window_scheme_id).path:
            theme = reconcile_chrome_theme_with_color_scheme(
                theme, ui_theme, application
            )
        previous_key = application.property("_jottr_style_key")
        saved_sheet = application.styleSheet()
        if saved_sheet:
            application.setStyleSheet("")
            self._applied_app_stylesheet = None
        key = apply_qt_style(
            self.settings_manager.get_qt_style(),
            application,
            theme=theme,
        )
        swapped = previous_key != application.property("_jottr_style_key")
        if saved_sheet:
            # Restore after paint so setStyle is not wrapped in QStyleSheetStyle.
            QTimer.singleShot(
                0, lambda sheet=saved_sheet: self._restore_app_stylesheet(sheet)
            )
        if swapped:
            QTimer.singleShot(0, self._refresh_icons_after_widget_style)
        return key

    def _restore_app_stylesheet(self, sheet):
        """Re-apply chrome QSS after a Kate-like widget-style swap."""
        application = QApplication.instance()
        if application is None or not sheet:
            return
        if application.styleSheet() == sheet:
            self._applied_app_stylesheet = sheet
            return
        application.setStyleSheet(sheet)
        self._applied_app_stylesheet = sheet

    def _refresh_icons_after_widget_style(self):
        """Rebuild action/tab icons after a deferred widget-style swap."""
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
                try:
                    from PyQt6 import sip
                    if sip.isdeleted(child):
                        continue
                except Exception:
                    pass
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

        settings_dialog = getattr(self, "_settings_dialog", None)
        if settings_dialog is not None:
            settings_dialog.apply_ui_font(app_font)

        if hasattr(self, "tab_widget") and self.tab_widget is not None:
            for index in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(index)
                apply_ui = getattr(tab, "apply_ui_font", None)
                if callable(apply_ui):
                    apply_ui(app_font)

    def get_icon_color(self):
        """Return the configured icon color for the active app theme."""
        return resolve_icon_color(self.settings_manager)

    def build_themed_icon(
        self,
        icon_name,
        color=None,
        selected_color=None,
        disabled_color=None,
        *,
        quick=True,
    ):
        """Tint a bundled symbolic SVG with explicit modes (cached).

        Selected/Disabled pixmaps are required so QStyle.generatedIconPixmap
        does not invent a style-specific tint after widget-style switches.
        """
        if color is None:
            color = self.get_icon_color()
        if selected_color is None and disabled_color is None:
            selected_color, disabled_color = resolve_icon_mode_colors(
                self.settings_manager
            )
        key = (icon_name, color, selected_color, disabled_color, quick)
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
                quick=quick,
            )
            cache[key] = icon
        return QIcon(icon)

    def update_action_icons(self):
        if not hasattr(self, "icon_actions"):
            return
        color = self.get_icon_color()
        selected_color, disabled_color = resolve_icon_mode_colors(
            self.settings_manager
        )
        for action, icon_name in self.icon_actions:
            action.setIcon(
                self.build_themed_icon(
                    icon_name,
                    color=color,
                    selected_color=selected_color,
                    disabled_color=disabled_color,
                    quick=True,
                )
            )

    def tab_icon_name_for_widget(self, tab):
        return ""

    def update_tab_icon(self, index):
        if index < 0 or not hasattr(self, "tab_widget"):
            return
        self.tab_widget.setTabIcon(index, QIcon())

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
        """Native QStyle close buttons are drawn by the widget style (Kate-style).

        QTabBar paints borderless close indicators itself when tabs are
        closable, so no custom QToolButton is injected. Kept as a no-op for
        existing tabs_changed/refresh call sites.
        """

    def _on_tab_close_button_clicked(self):
        """Legacy custom-button slot; native buttons use tabCloseRequested."""

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
        action = QAction(translated_text, self)
        if icon_name and icon_name in self.icons:
            # Icons are tinted in update_action_icons() after first paint.
            self.icon_actions.append((action, icon_name))
            # Keep menus text-only while toolbar still shows the icon.
            action.setIconVisibleInMenu(False)
        action.setProperty("text_key", text)
        tip = tooltip or text
        action.setProperty("tooltip_key", tip)
        action.setProperty("accessibility_label", tip)
        self._set_action_tooltip(action, tip)
        action.setCheckable(checkable)
        if isinstance(shortcut, list):
            # Platform standard bindings can repeat an explicit one; duplicates make shortcuts ambiguous.
            unique = {seq.toString(): seq for seq in shortcut if not seq.isEmpty()}
            action.setShortcuts(list(unique.values()))
        elif shortcut is not None:
            action.setShortcut(shortcut)
        if handler:
            action.triggered.connect(handler)
        self.translatable_actions.append(action)
        # Also attach to the window so shortcuts still fire while the menubar is hidden.
        self.addAction(action)
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
            tooltip="Convert the selection to uppercase, or the word under the cursor",
        )
        self.lowercase_action = self._make_action(
            "Lowercase",
            self.lowercase,
            shortcut=QKeySequence("Ctrl+Shift+U"),
            tooltip="Convert the selection to lowercase, or the word under the cursor",
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
        self.browser_action = self._make_action(
            "Toggle Browser Pane",
            self.toggle_browser,
            icon_name="browser",
            shortcut=QKeySequence("Ctrl+Shift+B"),
            tooltip="Toggle Browser Pane",
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
        self.line_numbers_action = self._make_action(
            "Show Line Numbers",
            self.toggle_line_numbers,
            tooltip="Show or hide editor line numbers",
            checkable=True,
        )
        self.line_numbers_action.setChecked(
            bool(self.settings_manager.get_setting("editor_line_numbers", True))
        )
        self.show_menubar_action = self._make_action(
            "Show Menubar",
            self.toggle_menubar,
            shortcut=QKeySequence("Ctrl+M"),
            tooltip="Show or hide the menubar",
            checkable=True,
        )
        self.show_menubar_action.setChecked(self.settings_manager.get_menubar_visible())
        self.show_toolbar_action = self._make_action(
            "Show Toolbar",
            self.toggle_toolbar,
            tooltip="Show or hide the toolbar",
            checkable=True,
        )
        self.show_toolbar_action.setChecked(self.settings_manager.get_toolbar_visible())
        # Hamburger at the far right of the toolbar, shown while the menubar is hidden.
        self.menu_button_action = self._make_action(
            "Menu", self.show_menu_button_popup, icon_name="menu", tooltip="Menu"
        )
        self.menu_button_menu = QMenu(self)
        self.menu_button_menu.aboutToShow.connect(self.populate_menu_button_menu)
        self.zoom_in_action = self._make_action(
            "Zoom In",
            self.zoom_in,
            icon_name="zoom-in",
            # Ctrl+= is unshifted on US layouts; the standard binding adds Ctrl++ and keypad plus.
            shortcut=[
                QKeySequence("Ctrl+="),
                *QKeySequence.keyBindings(QKeySequence.StandardKey.ZoomIn),
            ],
            tooltip="Zoom In (Ctrl+=)",
        )
        self.zoom_out_action = self._make_action(
            "Zoom Out",
            self.zoom_out,
            icon_name="zoom-out",
            shortcut=[
                QKeySequence("Ctrl+-"),
                *QKeySequence.keyBindings(QKeySequence.StandardKey.ZoomOut),
            ],
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
        self.toolbar.addAction(self.editor_theme_action)
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
        self.toolbar.addAction(self.snippets_action)
        self.toolbar.addAction(self.browser_action)
        self.toolbar.addAction(self.menu_button_action)

        def update_overflow_button():
            try:
                overflow_button = self.toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
            except RuntimeError:
                return
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
        Capitalization stays available whenever an editor is present.
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
        # Capitalization acts on selection or caret (like Formatting); not selection-gated.
        capitalization = getattr(self, "capitalization_menu_action", None)
        if capitalization is not None:
            capitalization.setEnabled(editor is not None)

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
            QIcon(),
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

        release_swap_file = getattr(tab, "release_swap_file", None)
        if release_swap_file is not None:
            release_swap_file()
        remove_stash_file = getattr(tab, "remove_stash_file", None)
        if remove_stash_file is not None:
            remove_stash_file()
        self.tab_widget.removeTab(index)
        self.save_workspace_open_files()
        
        # Create new tab if last tab was closed
        if self.tab_widget.count() == 0:
            self.new_editor_tab()
            
    def plugin_chrome_signature(self):
        """Plugin toolbar/menu contributions, to detect when chrome must rebuild."""
        import json

        registry = getattr(self.plugin_manager, "registry", None)
        return json.dumps(
            [
                getattr(registry, name, [])
                for name in ("toolbar_actions", "commands", "panels", "sidebar_items")
            ],
            sort_keys=True,
            default=repr,
        )

    def create_menu_bar(self):
        # Toolbar and menus are always rebuilt together (see rebuild_chrome).
        self._plugin_chrome_signature = self.plugin_chrome_signature()
        menubar = self.menuBar()
        menubar.clear()
        menubar.setObjectName("appMenuBar")
        menubar.setAccessibleName(_("Application menu"))
        # Native bar on macOS (HIG); in-window elsewhere so it can be hidden.
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
        self.open_recent_menu = file_menu.addMenu(_("Open &Recent"))
        self.open_recent_menu.setAccessibleName(
            _("{title} menu").format(title=_("Open &Recent").replace("&", ""))
        )
        self.open_recent_menu.menuAction().setProperty("text_key", "Open &Recent")
        self.translatable_actions.append(self.open_recent_menu.menuAction())
        self.translatable_menus.append((self.open_recent_menu, "Open &Recent"))
        # Rebuilt when shown: clearing the menu from one of its own actions
        # would delete the action that is still running.
        self.open_recent_menu.aboutToShow.connect(self.refresh_recent_files_menu)
        self.refresh_recent_files_menu()
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
        self.capitalization_menu_action = capitalization_menu.menuAction()
        self.capitalization_menu_action.setProperty("text_key", "Capitalization")
        self.capitalization_menu_action.setEnabled(False)
        self.translatable_actions.append(self.capitalization_menu_action)
        self.translatable_menus.append((capitalization_menu, "Capitalization"))
        capitalization_menu.addAction(self.uppercase_action)
        capitalization_menu.addAction(self.lowercase_action)
        capitalization_menu.addAction(self.capitalize_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.find_action)

        # View menu
        view_menu = add_menu("&View")
        self.view_menu = view_menu
        view_menu.addAction(self.snippets_action)
        view_menu.addAction(self.browser_action)
        view_menu.addAction(self.markdown_action)
        view_menu.addAction(self.focus_mode_action)
        view_menu.addAction(self.line_numbers_action)
        view_menu.addAction(self.show_toolbar_action)
        view_menu.addAction(self.show_menubar_action)
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

        # Kate: Settings → Application Style (KStyleManager::createConfigureAction).
        widget_style_menu = view_menu.addMenu(_("Widget Style"))
        widget_style_menu.setAccessibleName(
            _("{title} menu").format(title=_("Widget Style"))
        )
        widget_style_menu.menuAction().setProperty("text_key", "Widget Style")
        self.translatable_actions.append(widget_style_menu.menuAction())
        self.translatable_menus.append((widget_style_menu, "Widget Style"))
        self.widget_style_menu = widget_style_menu
        self.widget_style_actions = QActionGroup(self)
        self.widget_style_actions.setExclusive(True)
        self.widget_style_actions.triggered.connect(self._on_widget_style_menu_triggered)
        # Listing styles creates every installed style plugin, so the menu is
        # filled when opened instead of during startup.
        widget_style_menu.aboutToShow.connect(self.sync_widget_style_menu)

        color_scheme_menu = view_menu.addMenu(_("Window Color Scheme"))
        color_scheme_menu.setAccessibleName(
            _("{title} menu").format(title=_("Window Color Scheme"))
        )
        color_scheme_menu.menuAction().setProperty("text_key", "Window Color Scheme")
        self.translatable_actions.append(color_scheme_menu.menuAction())
        self.translatable_menus.append((color_scheme_menu, "Window Color Scheme"))
        self.color_scheme_menu = color_scheme_menu
        self.color_scheme_grid = None
        color_scheme_menu.aboutToShow.connect(self.refresh_window_color_scheme_menu)

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

        self.apply_menubar_visibility()
        self.apply_toolbar_visibility()

    def toggle_menubar(self, _checked=False):
        """Persist Show Menubar and apply it."""
        self.settings_manager.save_menubar_visible(self.show_menubar_action.isChecked())
        self.apply_menubar_visibility()

    def toggle_toolbar(self, _checked=False):
        """Persist Show Toolbar and apply it."""
        self.settings_manager.save_toolbar_visible(self.show_toolbar_action.isChecked())
        self.apply_toolbar_visibility()

    def apply_toolbar_visibility(self):
        """Show or hide the main toolbar from the View menu setting."""
        visible = self.settings_manager.get_toolbar_visible()
        if hasattr(self, "show_toolbar_action"):
            self.show_toolbar_action.blockSignals(True)
            self.show_toolbar_action.setChecked(visible)
            self.show_toolbar_action.blockSignals(False)
        if hasattr(self, "toolbar") and self.toolbar is not None:
            # Focus mode hides all chrome and restores the toolbar itself on exit.
            current_tab = self.tab_widget.currentWidget() if hasattr(self, "tab_widget") else None
            if not getattr(current_tab, "focus_mode", False):
                self.toolbar.setVisible(visible)

    def apply_menubar_visibility(self):
        """Show or hide the menubar; the toolbar hamburger stands in while it is hidden."""
        visible = self.settings_manager.get_menubar_visible()
        # The native macOS menubar lives outside the window and cannot be hidden.
        if self.menuBar().isNativeMenuBar():
            visible = True
        if hasattr(self, "show_menubar_action"):
            self.show_menubar_action.blockSignals(True)
            self.show_menubar_action.setChecked(visible)
            self.show_menubar_action.blockSignals(False)
        if hasattr(self, "menu_button_action"):
            self.menu_button_action.setVisible(not visible)
        # Focus mode hides all chrome and restores the menubar itself on exit.
        current_tab = self.tab_widget.currentWidget() if hasattr(self, "tab_widget") else None
        if not getattr(current_tab, "focus_mode", False):
            self.menuBar().setVisible(visible)

    def populate_menu_button_menu(self):
        """Mirror the menubar menus inside the toolbar hamburger."""
        menu = self.menu_button_menu
        menu.clear()
        for action in self.menuBar().actions():
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(self.show_menubar_action)

    def show_menu_button_popup(self, _checked=False):
        """Open the hamburger menu under its toolbar button."""
        button = self.toolbar.widgetForAction(self.menu_button_action)
        if button is not None:
            self.menu_button_menu.popup(button.mapToGlobal(button.rect().bottomLeft()))
        else:
            from PyQt6.QtGui import QCursor

            self.menu_button_menu.popup(QCursor.pos())

    def createPopupMenu(self):
        """Right-click on the menubar: Show Toolbar plus Show Menubar.

        Qt's default popup already contains the toolbar's toggleViewAction;
        swap it for the persisted Show Toolbar action so View menu,
        menubar right-click, and settings stay in sync.
        """
        menu = super().createPopupMenu() or QMenu(self)
        toolbar_toggle = None
        if hasattr(self, "toolbar") and self.toolbar is not None:
            toolbar_toggle = self.toolbar.toggleViewAction()
        for action in list(menu.actions()):
            if toolbar_toggle is not None and action is toolbar_toggle:
                menu.removeAction(action)
        if hasattr(self, "show_toolbar_action"):
            menu.addAction(self.show_toolbar_action)
        if hasattr(self, "show_menubar_action"):
            menu.addSeparator()
            menu.addAction(self.show_menubar_action)
        return menu

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
        self._ensure_startup_content()
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.save_file()

    def new_editor_tab(self):
        """Create a new empty editor tab"""
        self._ensure_startup_content()
        editor_tab = EditorTab(self.snippet_manager, self.settings_manager)
        editor_tab.set_main_window(self)  # Set reference to main window
        
        # Named "Document N" until its first line gives it a title.
        editor_tab.untitled_title = _("Document {number}").format(
            number=self.tab_widget.count() + 1
        )
        self.tab_widget.addTab(
            editor_tab,
            self.build_themed_icon("document"),
            editor_tab.untitled_title,
        )
        self.tab_widget.setCurrentWidget(editor_tab)
        editor_tab.editor.setFocus()
        self.save_workspace_open_files()
        return editor_tab
        
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

        themes = ThemeManager.get_themes()
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
            self.refresh_editor_theme_menu()
            return
        current = self.settings_manager.get_theme()
        if current not in grid._cards:
            self.refresh_editor_theme_menu()
            return
        grid.set_current(current)

    def sync_color_scheme_menu(self):
        """Compatibility alias for Window Color Scheme menu sync."""
        self.sync_window_color_scheme_menu()

    def sync_window_color_scheme_menu(self):
        """Mark the active Window Color Scheme card without rebuilding the grid."""
        grid = getattr(self, "color_scheme_grid", None)
        if grid is None:
            self.refresh_window_color_scheme_menu()
            return
        current = self.settings_manager.get_window_color_scheme()
        if current not in grid._cards:
            self.refresh_window_color_scheme_menu()
            return
        grid.set_current(current)

    def refresh_window_color_scheme_menu(self):
        """Rebuild View → Window Color Scheme as a Kate-style preview grid."""
        from jottr.window_color_scheme import discover_window_color_schemes

        menu = getattr(self, "color_scheme_menu", None)
        if menu is None:
            return
        menu.clear()
        self.color_scheme_grid = None

        schemes = discover_window_color_schemes()
        current = self.settings_manager.get_window_color_scheme()
        grid = WindowColorSchemeGrid(schemes, current)
        grid.scheme_chosen.connect(self._on_window_color_scheme_grid_chosen)

        scroll = QScrollArea()
        scroll.setObjectName("windowColorSchemeScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(grid)
        # Keep tall scheme lists usable inside a popup menu.
        scroll.setMinimumWidth(grid.sizeHint().width() + 24)
        scroll.setMaximumHeight(420)

        action = QWidgetAction(self)
        action.setDefaultWidget(scroll)
        menu.addAction(action)
        self.color_scheme_grid = grid

    def _on_window_color_scheme_grid_chosen(self, scheme_id):
        self.set_window_color_scheme(scheme_id)
        if self.color_scheme_menu is not None:
            self.color_scheme_menu.close()

    def setup_toolbar_style_actions(self):
        """Exclusive Comfy / Compact actions shared by View and toolbar menus."""
        from jottr.settings_manager import TOOLBAR_STYLE_COMFY, TOOLBAR_STYLE_COMPACT

        if getattr(self, "toolbar_style_actions", None) is not None:
            return
        self.toolbar_style_actions = QActionGroup(self)
        self.toolbar_style_actions.setExclusive(True)
        current = self.settings_manager.get_toolbar_style()
        for style_id, label_key in (
            (TOOLBAR_STYLE_COMFY, "Comfy"),
            (TOOLBAR_STYLE_COMPACT, "Compact"),
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

    def sync_widget_style_menu(self):
        """Rebuild View → Widget Style like KStyleManager's menu."""
        from jottr.qt_style import SYSTEM_QT_STYLE, available_qt_styles

        menu = getattr(self, "widget_style_menu", None)
        group = getattr(self, "widget_style_actions", None)
        if menu is None or group is None:
            return
        menu.clear()
        for action in list(group.actions()):
            group.removeAction(action)
            action.deleteLater()
        current = self.settings_manager.get_qt_style()
        for style_name in available_qt_styles():
            label = _("Default") if style_name == SYSTEM_QT_STYLE else style_name
            action = QAction(label, self)
            action.setCheckable(True)
            action.setData(style_name)
            action.setChecked(style_name == current)
            group.addAction(action)
            menu.addAction(action)

    def _on_widget_style_menu_triggered(self, action):
        style_name = action.data()
        if not style_name:
            return
        self.settings_manager.save_qt_style(style_name)
        self.apply_widget_style()
        self.sync_widget_style_menu()
        self.refresh_settings_dialog()

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
        """Right-click on the main toolbar: density, Show Toolbar, Show Menubar."""
        self.setup_toolbar_style_actions()
        self.sync_toolbar_style_menu()
        menu = QMenu(self)
        menu.setTitle(_("Toolbar Style"))
        for action in self.toolbar_style_actions.actions():
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(self.show_toolbar_action)
        menu.addAction(self.show_menubar_action)
        menu.exec(self.toolbar.mapToGlobal(pos))

    def show_tab_context_menu(self, pos):
        """Right-click on a document tab: Rename or Change Title, Show in Folder, and Close."""
        tab_bar = self.tab_widget.tabBar()
        tab = self.tab_widget.widget(tab_bar.tabAt(pos))
        if not isinstance(tab, EditorTab):
            return
        menu = QMenu(self)
        action_text = _("Rename") if tab.current_file else _("Change Title")
        menu.addAction(
            action_text,
            lambda checked=False, tab=tab: self.rename_tab(self.tab_widget.indexOf(tab)),
        )
        path = tab.current_file
        if path and os.path.exists(path):
            menu.addAction(
                _("Show in Folder"), lambda checked=False, path=path: show_in_file_manager(path)
            )
        menu.addSeparator()

        def _close_tab(checked=False, tab=tab):
            index = self.tab_widget.indexOf(tab)
            if index >= 0:
                self.close_tab(index)

        menu.addAction(_("Close"), _close_tab)
        menu.exec(tab_bar.mapToGlobal(pos))

    def rename_tab(self, index):
        """Rename a document tab in place; a saved file is renamed on disk."""
        tab = self.tab_widget.widget(index)
        if not isinstance(tab, EditorTab):
            return False
        if tab.current_file:
            text = os.path.basename(tab.current_file)
            # Select the name without its extension.
            select_length = len(os.path.splitext(text)[0]) or len(text)
        else:
            text = self.tab_widget.tabText(index).removesuffix("*")
            select_length = len(text)
        self.tab_widget.tabBar().edit_tab_title(
            index, text, lambda name, tab=tab: self.apply_tab_title(tab, name), select_length
        )
        return True

    def apply_tab_title(self, tab, name):
        """Rename *tab* to *name*; returns an error message, or None when done.

        An untitled document keeps *name* as its title instead of following
        its first line. A saved file is renamed in its folder, never over
        another file.
        """
        index = self.tab_widget.indexOf(tab)
        if index < 0:
            return None
        name = name.strip()
        if name in ("", ".", ".."):
            return _("Enter a name.")
        if "/" in name or os.sep in name:
            return _('A name cannot contain "/".')

        if not tab.current_file:
            tab.untitled_title = ""
            modified = tab.editor.document().isModified()
            self.tab_widget.setTabText(index, name + ("*" if modified else ""))
            write_backup = getattr(tab, "write_backup", None)
            if modified and write_backup is not None:
                write_backup()
            self.save_session()
            return None

        old_path = os.path.abspath(tab.current_file)
        new_path = os.path.join(os.path.dirname(old_path), name)
        if new_path == old_path:
            return None
        try:
            # A case-only rename on a case-insensitive disk names the same file.
            same_file = os.path.exists(old_path) and os.path.samefile(old_path, new_path)
        except OSError:
            same_file = False
        if os.path.lexists(new_path) and not same_file:
            return _('A file named "{name}" already exists.').format(name=name)
        try:
            os.rename(old_path, new_path)
        except OSError as error:
            return _("Could not rename: {error}").format(error=error)
        self.remap_open_tabs_for_path_change(old_path, new_path)
        self.save_workspace_markdown_files()
        self.save_workspace_open_files()
        return None

    def set_window_color_scheme(self, scheme_id):
        """Persist Window Color Scheme (Kate) and restyle the app."""
        from jottr.window_color_scheme import normalize_window_color_scheme

        scheme_id = normalize_window_color_scheme(scheme_id)
        if scheme_id == self.settings_manager.get_window_color_scheme():
            self.sync_window_color_scheme_menu()
            return
        self.settings_manager.save_window_color_scheme(scheme_id)
        self.apply_app_style()
        self.sync_window_color_scheme_menu()
        self.sync_toolbar_style_menu()
        self.refresh_settings_dialog()

    def set_editor_theme(self, theme_name):
        """Persist Editor Theme from the View menu and apply it to open tabs."""
        themes = ThemeManager.get_themes()
        if theme_name not in themes:
            theme_name = ThemeManager.DEFAULT_THEME_NAME
        if theme_name == self.settings_manager.get_theme():
            self.sync_editor_theme_menu()
            return
        self.settings_manager.save_theme(theme_name)
        self.apply_editor_theme_to_tabs(theme_name)
        self.sync_editor_theme_menu()
        self.refresh_settings_dialog()

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
        self.refresh_settings_dialog()
        if language != DOCUMENT_LANGUAGE_AUTO and not match_dictionary_for_language(language):
            QMessageBox.warning(
                self,
                _("Dictionary Not Installed"),
                missing_dictionary_message(language),
            )

    def sync_spell_check_ui(self, enabled):
        """Keep the Tools menu action and an open Settings window in sync."""
        enabled = bool(enabled)
        if hasattr(self, "spell_check_action") and self.spell_check_action is not None:
            self.spell_check_action.blockSignals(True)
            self.spell_check_action.setChecked(enabled)
            self.spell_check_action.blockSignals(False)
        self.refresh_settings_dialog()
        self.update_document_language_status()

    def toggle_spell_check(self, checked=None):
        """Toggle automatic spell checking from Tools."""
        if checked is None:
            checked = not bool(self.settings_manager.get_setting("spell_check", True))
        enabled = bool(checked)
        self.settings_manager.save_setting("spell_check", enabled)
        self.sync_spell_check_ui(enabled)
        self.apply_spell_check_to_tabs()

    def toggle_line_numbers(self, checked=None):
        """Toggle editor line numbers from View."""
        if checked is None:
            checked = not bool(
                self.settings_manager.get_setting("editor_line_numbers", True)
            )
        visible = bool(checked)
        self.settings_manager.save_setting("editor_line_numbers", visible)
        if hasattr(self, "line_numbers_action") and self.line_numbers_action is not None:
            self.line_numbers_action.blockSignals(True)
            self.line_numbers_action.setChecked(visible)
            self.line_numbers_action.blockSignals(False)
        self.apply_editor_line_numbers(visible)

    def toggle_snippets(self):
        """Toggle snippets pane in current tab"""
        self._ensure_startup_content()
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
        if getattr(self, "_close_accepted", False):
            # Already closed once; the session must not change any more.
            event.accept()
            return
        # Cancelling the prompt keeps untitled documents backed up as they are now.
        self.stash_new_unsaved_files()
        if self.handle_unsaved_changes():
            settings_dialog = getattr(self, "_settings_dialog", None)
            if settings_dialog is not None:
                # Flushes pending applies and remembers window geometry.
                settings_dialog.close()
            self.save_workspace_markdown_files()
            # Also saves the session the next start reopens.
            self.save_workspace_open_files()
            self._close_accepted = True
            release_session(self.settings_manager)
            self.release_backups()
            # Save window state
            self.settings_manager.save_setting('window_state', {
                'geometry': self.saveGeometry().toBase64().data().decode(),
                'state': self.saveState().toBase64().data().decode()
            })
            event.accept()
        else:
            event.ignore()

    def stash_new_unsaved_files(self):
        """Write untitled documents to the stash now."""
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab):
                tab.write_stash_file()

    def release_backups(self):
        """Documents are closing: drop backups nobody needs to recover.

        Closing already asked to save or discard every document, so untitled
        stashes only survive a crash.
        """
        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            release_swap_file = getattr(tab, "release_swap_file", None)
            if release_swap_file is not None:
                release_swap_file()
            remove_stash_file = getattr(tab, "remove_stash_file", None)
            if remove_stash_file is not None:
                remove_stash_file()

    def session_tab_entry(self, tab):
        """Session entry that reopens *tab*, or None when it is not kept."""
        if not isinstance(tab, EditorTab):
            return None
        if tab.current_file:
            return {"file": os.path.abspath(tab.current_file)}
        stash_id = getattr(tab, "stash_id", None)
        if stash_id and self.settings_manager.get_setting(STASH_NEW_FILES_SETTING, True):
            title = self.tab_widget.tabText(self.tab_widget.indexOf(tab))
            return {"untitled": stash_id, "title": title.removesuffix("*")}
        return None

    def save_session(self, *_args):
        """Remember the open tabs, so the next start reopens them even after a crash."""
        if not getattr(self, "_session_loaded", False) or getattr(self, "_close_accepted", False):
            return
        if not claim_session(self.settings_manager):
            return
        tabs = []
        current = -1
        for index in range(self.tab_widget.count()):
            entry = self.session_tab_entry(self.tab_widget.widget(index))
            if entry is None:
                continue
            if index == self.tab_widget.currentIndex():
                current = len(tabs)
            tabs.append(entry)
        session = {"tabs": tabs, "current": current}
        if session == getattr(self, "_saved_session", None):
            return
        try:
            write_session(self.settings_manager, tabs, current)
        except OSError as error:
            print(f"Could not save the session: {error}")
            return
        self._saved_session = session

    def startup_workspace(self):
        """Workspace the "Open a workspace" startup option opens, if it still exists."""
        sm = self.settings_manager
        if sm.get_setting(SESSION_RESTORE_SETTING, SESSION_RESTORE_UNSAVED) != SESSION_RESTORE_WORKSPACE:
            return ""
        path = sm.get_setting(STARTUP_WORKSPACE_SETTING, "")
        if not isinstance(path, str) or not path or not os.path.isdir(path):
            return ""
        return os.path.abspath(path)

    def restore_session(self, only_unsaved=False):
        """Reopen the tabs of the last run, whether it closed or crashed.

        Stash files the session does not list (a crash before it was saved,
        or an older Jottr) are reopened too. With the "unsaved changes"
        restore mode the session is only reopened when backups hold unsaved
        text; *only_unsaved* reopens just the tabs with unsaved changes.
        Returns False when no session was saved yet.
        """
        session = read_session(self.settings_manager)
        entries = session["tabs"] if session is not None else []
        restore_mode = self.settings_manager.get_setting(
            SESSION_RESTORE_SETTING, SESSION_RESTORE_UNSAVED
        )
        if restore_mode == SESSION_RESTORE_UNSAVED and not self.session_has_unsaved_changes(entries):
            entries = []
        referenced = {
            entry.get("untitled") for entry in entries if isinstance(entry, dict)
        }
        current_tab = None
        for position, entry in enumerate(entries):
            if only_unsaved and not self.session_entry_has_unsaved_changes(entry):
                continue
            tab = self.restore_session_tab(entry)
            if tab is not None and position == session.get("current"):
                current_tab = tab
        for stash_id in stash_ids_on_disk(self.settings_manager):
            if stash_id not in referenced:
                self.restore_untitled_document(stash_id)
        if current_tab is not None:
            self.tab_widget.setCurrentWidget(current_tab)
        self._session_loaded = True
        self.save_session()
        return session is not None

    def session_has_unsaved_changes(self, entries):
        """Whether backups hold unsaved text for the session *entries*.

        Any readable stash counts, since every stashed document is reopened.
        """
        for stash_id in stash_ids_on_disk(self.settings_manager):
            if read_stash_file(stash_file_path(self.settings_manager, stash_id)) is not None:
                return True
        return any(self.session_entry_has_unsaved_changes(entry) for entry in entries)

    def session_entry_has_unsaved_changes(self, entry):
        """Whether reopening the session *entry* would bring back unsaved text."""
        if not isinstance(entry, dict):
            return False
        if isinstance(entry.get("file"), str):
            return swap_file_has_changes(self.settings_manager, entry["file"])
        stash_id = entry.get("untitled")
        return (
            is_valid_stash_id(stash_id)
            and read_stash_file(stash_file_path(self.settings_manager, stash_id)) is not None
        )

    def restore_session_tab(self, entry):
        if not isinstance(entry, dict):
            return None
        file_path = entry.get("file")
        if isinstance(file_path, str):
            if os.path.isfile(file_path) and self.open_file(file_path, add_to_recent=False):
                return self.tab_widget.currentWidget()
            return None
        stash_id = entry.get("untitled")
        if not is_valid_stash_id(stash_id):
            return None
        return self.restore_untitled_document(stash_id)

    def restore_untitled_document(self, stash_id):
        """Reopen a stashed untitled document; None when its stash is gone.

        Like any untitled tab, it is named after its first line.
        """
        data = read_stash_file(stash_file_path(self.settings_manager, stash_id))
        if data is None:
            return None
        tab = self.new_editor_tab()
        tab.stash_id = stash_id
        tab.editor.setPlainText(data["text"])
        tab.editor.document().setModified(True)
        return tab

    def restart_application(self):
        """Close Jottr and start it again once this process has exited."""
        self.restart_requested = True
        # Closing can still be cancelled from the unsaved changes prompt.
        if not self.close():
            self.restart_requested = False

    def open_external_url(self, url):
        """Open URL in system's default browser"""
        QDesktopServices.openUrl(QUrl(url))

    def show_help(self):
        """Show help documentation"""
        help_tab = self.new_editor_tab()
        # Titled "Help" rather than after the first line of the help text.
        help_tab.untitled_title = ""

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
        app_icon = load_app_icon()
        if not app_icon.isNull():
            about_dialog.setWindowIcon(app_icon)
        else:
            apply_dialog_window_icon(about_dialog, "about", self.settings_manager)
        
        layout = QVBoxLayout(about_dialog)
        layout.setSpacing(10)

        # App icon
        if not app_icon.isNull():
            icon_label = QLabel()
            icon_label.setPixmap(app_icon.pixmap(64, 64))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(icon_label)
        
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
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setIcon(QIcon())
        button_box.accepted.connect(about_dialog.accept)
        button_box.setCenterButtons(True)  # Center the OK button
        layout.addWidget(button_box)
        
        about_dialog.exec()

    def toggle_focus_mode(self):
        """Toggle focus mode for current editor tab"""
        self._ensure_startup_content()
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
        # Shared actions are recreated below; detach the old ones to avoid ambiguous shortcuts.
        for action in self.actions():
            self.removeAction(action)
        self.removeToolBar(self.toolbar)
        self.toolbar.deleteLater()
        self.setup_toolbar()
        self.create_menu_bar()

    def apply_settings_domain(self, domain):
        """Apply one settings domain immediately (instant-apply path).

        The Settings window persists each control to SettingsManager first,
        then calls here so only the affected subsystem rebuilds.
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
        elif domain == "widget_style":
            self.apply_widget_style()
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
            visible = bool(sm.get_setting("editor_line_numbers", True))
            if hasattr(self, "line_numbers_action") and self.line_numbers_action is not None:
                self.line_numbers_action.blockSignals(True)
                self.line_numbers_action.setChecked(visible)
                self.line_numbers_action.blockSignals(False)
            self.apply_editor_line_numbers(visible)
        elif domain == "autosave":
            self.apply_autosave_settings()
        elif domain == "sessions":
            self.apply_session_settings()
        elif domain == "browser":
            for index in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(index)
                if isinstance(tab, EditorTab):
                    tab.apply_browser_profile()
        elif domain == "plugins":
            # The Settings window shares this PluginManager and has already
            # refreshed it; run newly enabled entries in place, then rebuild
            # chrome only if the plugin toolbar/menu items differ from the
            # ones it was built with.
            self.plugin_manager.activate_enabled_plugins()
            if self.plugin_chrome_signature() != getattr(self, "_plugin_chrome_signature", None):
                self.rebuild_chrome()
                self.apply_app_style()
                self.sync_color_scheme_menu()
                self.sync_toolbar_style_menu()

    def show_settings(self):
        """Open the Settings window, or raise it when it is already open."""
        from jottr.settings_dialog import SettingsDialog

        dialog = getattr(self, "_settings_dialog", None)
        if dialog is None:
            dialog = SettingsDialog(self.settings_manager, self)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.finished.connect(self._on_settings_dialog_finished)
            self._settings_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        return dialog

    def _on_settings_dialog_finished(self, _result=None):
        # WA_DeleteOnClose deletes the window; a later open builds a fresh one.
        self._settings_dialog = None

    def refresh_settings_dialog(self):
        """Reload an open Settings window after a change made elsewhere."""
        dialog = getattr(self, "_settings_dialog", None)
        if dialog is not None:
            dialog.sync_from_settings()

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
            from PyQt6.QtWebEngineWidgets import QWebEngineView

            from jottr.editor.web_profile import new_browser_page

            view = QWebEngineView()
            view.setPage(new_browser_page(self.settings_manager, view))
            url = panel.get("url") or panel.get("homepage") or "about:blank"
            view.load(QUrl(url))
            return view
        label = QLabel(panel.get("content") or panel.get("description") or _("Plugin panel"))
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        return label

    def toggle_browser(self):
        """Toggle browser pane in current tab"""
        self._ensure_startup_content()
        current_tab = self.tab_widget.currentWidget()
        if current_tab:
            current_tab.toggle_pane("browser")

    def apply_editor_line_numbers(self, visible):
        """Apply line number visibility to all open editor tabs."""
        self._ensure_startup_content()
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, EditorTab):
                tab.set_line_numbers_visible(visible)

    def apply_autosave_settings(self):
        """Apply autosave settings to all open editor tabs."""
        self._ensure_startup_content()
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, EditorTab):
                tab.configure_autosave_timer()

    def apply_session_settings(self):
        """Apply swap file and untitled document backup to all open editor tabs."""
        self._ensure_startup_content()
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            if isinstance(tab, EditorTab):
                tab.apply_backup_settings()

    def toggle_markdown_preview(self):
        """Toggle markdown preview in current editor tab"""
        self._ensure_startup_content()
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.toggle_markdown_preview()

    def toggle_find(self):
        """Toggle find/replace in current editor tab"""
        self._ensure_startup_content()
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.toggle_find()

    def save_file_as(self):
        """Save current file with a new name"""
        self._ensure_startup_content()
        current_tab = self.tab_widget.currentWidget()
        if current_tab and isinstance(current_tab, EditorTab):
            current_tab.save_file(force_dialog=True)

    def export_pdf(self):
        """Export the current editor tab as a PDF."""
        self._ensure_startup_content()
        current_tab = self.tab_widget.currentWidget()
        if current_tab and hasattr(current_tab, "export_pdf"):
            current_tab.export_pdf()


    def eventFilter(self, obj, event):
        """Handle middle-click close, double-click rename and double-click new tab."""
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
                if tab_index >= 0:
                    return self.rename_tab(tab_index)
                if self.settings_manager.get_setting("double_click_empty_tab_bar_new_tab", True):
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

    def open_file(self, file_path=None, add_to_recent=True):
        """Open a file immediately, reusing an empty untitled tab when possible.

        The file goes to the top of File > Open Recent unless *add_to_recent*
        is False, as when a session reopens its tabs.
        """
        self._ensure_startup_content()
        if file_path is None:
            # Show file dialog if no path provided
            file_path, _selected_filter = get_open_file_name(
                self,
                _("Open File"),
                "",
                _("All Files (*);;Markdown Files (*.md *.markdown);;Text Files (*.txt)")
            )
            if not file_path:  # User cancelled
                return

        file_path = os.path.abspath(file_path)

        for index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(index)
            if getattr(tab, "current_file", None) and os.path.abspath(tab.current_file) == file_path:
                self.tab_widget.setCurrentIndex(index)
                tab.editor.setFocus()
                if add_to_recent:
                    self.add_recent_file(file_path)
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
            # The reused tab is named after the file, not the file's first line.
            editor_tab.untitled_title = ""
            current_index = self.tab_widget.indexOf(editor_tab)
            self.tab_widget.setTabText(current_index, os.path.basename(file_path))
            self.update_tab_icon(current_index)

        editor_tab.editor.setPlainText(content)
        editor_tab.current_file = file_path
        editor_tab.editor.document().setModified(False)
        if hasattr(editor_tab, "load_swap_file"):
            editor_tab.load_swap_file(content)
        if editor_tab.is_markdown_file(file_path):
            editor_tab.set_markdown_preview_visible(True)
        else:
            editor_tab.set_markdown_preview_visible(False)
        
        self.tab_widget.setCurrentWidget(editor_tab)
        editor_tab.editor.setFocus()
        self.save_workspace_open_files()
        if add_to_recent:
            self.add_recent_file(file_path)
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

    def get_recent_files(self):
        """Return recently opened files, newest first, without duplicates."""
        files = self.settings_manager.get_setting("recent_files", [])
        if not isinstance(files, list):
            return []
        clean = []
        for path in files:
            if isinstance(path, str) and path:
                path = os.path.abspath(path)
                if path not in clean:
                    clean.append(path)
        return clean[:MAX_RECENT_FILES]

    def save_recent_files(self, files):
        """Store the recent files list; Open Recent is greyed out while it is empty."""
        clean = []
        for path in files:
            if path not in clean:
                clean.append(path)
        clean = clean[:MAX_RECENT_FILES]
        self.settings_manager.save_setting("recent_files", clean)
        menu = getattr(self, "open_recent_menu", None)
        if menu is not None:
            menu.menuAction().setEnabled(bool(clean))

    def add_recent_file(self, path):
        """Put a file at the top of File > Open Recent."""
        path = os.path.abspath(path)
        self.save_recent_files([path] + self.get_recent_files())

    def remove_recent_file(self, path):
        """Drop a file from File > Open Recent."""
        path = os.path.abspath(path)
        self.save_recent_files([item for item in self.get_recent_files() if item != path])

    def clear_recent_files(self):
        """Empty File > Open Recent."""
        self.save_recent_files([])

    def remap_recent_files(self, old_path, new_path):
        """Follow a renamed file, or files in a renamed folder, in Open Recent."""
        old_path = os.path.abspath(old_path)
        files = []
        for path in self.get_recent_files():
            if self.path_is_within(path, old_path):
                path = os.path.abspath(os.path.join(new_path, os.path.relpath(path, old_path)))
            files.append(path)
        self.save_recent_files(files)

    @staticmethod
    def recent_file_label(path):
        """Kate's "name [folder]" menu label, with the home folder shortened to ~."""
        folder = os.path.dirname(path)
        home = os.path.expanduser("~")
        if home != os.sep and (folder == home or folder.startswith(home + os.sep)):
            folder = "~" + folder[len(home):]
        # A lone "&" in a menu label would be taken for a mnemonic.
        return f"{os.path.basename(path)} [{folder}]".replace("&", "&&")

    def refresh_recent_files_menu(self):
        """List recent files in File > Open Recent, then Clear List."""
        menu = getattr(self, "open_recent_menu", None)
        if menu is None:
            return
        menu.clear()
        files = self.get_recent_files()
        for path in files:
            action = menu.addAction(self.recent_file_label(path))
            action.setData(path)
            action.setToolTip(path)
            action.triggered.connect(
                lambda checked=False, path=path: self.open_recent_file(path)
            )
        if files:
            menu.addSeparator()
            menu.addAction(_("Clear List"), self.clear_recent_files)
        menu.menuAction().setEnabled(bool(files))

    def open_recent_file(self, path):
        """Open a file from Open Recent, dropping it from the list when it is gone."""
        if not os.path.isfile(path):
            self.remove_recent_file(path)
            QMessageBox.critical(
                self,
                _("Error"),
                _('"{path}" no longer exists and was removed from the recent files list.').format(
                    path=path
                ),
            )
            return False
        return self.open_file(path)

    # Add a new method to set up the find shortcut

    def handle_unsaved_changes(self):
        """Handle unsaved changes before closing."""
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
