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
import json
import hashlib
from PyQt6.QtWidgets import (
                            QApplication, QMainWindow, QTabWidget, QWidget,
                            QVBoxLayout, QHBoxLayout, QSplitter, QMenu, QToolBar,
                            QMessageBox, QLabel, QDialog, QSizePolicy,
                            QDialogButtonBox, QTabBar, QFileDialog, QToolButton,
                            QTreeView, QInputDialog, QPushButton, QGraphicsOpacityEffect,
                            QStyle, QStyleOptionTab, QStylePainter)
from PyQt6.QtCore import (
    Qt, QUrl, QTimer, QEvent, QDir, QPropertyAnimation,
    QEasingCurve, QParallelAnimationGroup, QRect
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QAction, QShortcut, QFileSystemModel, QPen
from jottr.editor_tab import EditorTab
from jottr.snippet_manager import SnippetManager
from jottr.rss_tab import RSSTab
import feedparser
from PyQt6.QtGui import QIcon, QDesktopServices, QKeySequence, QColor
from jottr.theme_manager import ThemeManager
from jottr.settings_manager import SettingsManager
from jottr.settings_dialog import SettingsDialog
from jottr.translation_manager import _, is_rtl_language, set_language
from PyQt6.QtGui import QFont
from PyQt6.QtCore import QSize
from jottr.font_dialog import FontSelectionDialog
from jottr.plugin_manager import PluginManager
from jottr.icon_manager import build_themed_icon as render_bundled_icon, load_bundled_icon_paths
from jottr.paths import find_data_file
from jottr import __version__
# Add vendor directory to path
vendor_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor')
if os.path.exists(vendor_dir):
    sys.path.insert(0, vendor_dir)

# Application constants
APP_NAME = "Jottr"
APP_VERSION = __version__
APP_HOMEPAGE = "https://github.com/mfat/jottr"

class WorkspaceFileSystemModel(QFileSystemModel):
    """File model that exposes full paths as tooltips."""

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.ToolTipRole and index.isValid():
            return self.filePath(index)
        return super().data(index, role)


class WorkspaceTreeView(QTreeView):
    """Tree view with subtle branch guides for workspace hierarchy."""

    def drawBranches(self, painter, rect, index):
        super().drawBranches(painter, rect, index)
        if not index.isValid() or rect.width() <= 0:
            return

        color = self.palette().mid().color()
        color.setAlpha(130)
        painter.save()
        painter.setPen(QPen(color, 1))
        center_x = rect.right() - max(8, self.indentation() // 2)
        center_y = rect.center().y()
        painter.drawLine(center_x, rect.top(), center_x, rect.bottom())
        painter.drawLine(center_x, center_y, rect.right(), center_y)
        painter.restore()


class LeftAlignedDocumentTabBar(QTabBar):
    """Document tab bar that keeps labels centered in the tab area."""

    label_left_padding = 8
    label_right_padding = 30
    icon_text_gap = 5
    icon_vertical_offset = -1
    underline_height = 2

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionTab()
        for index in range(self.count()):
            self.initStyleOption(option, index)
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabShape, option)
            self.draw_left_aligned_label(painter, option, index)

    def tab_text_color(self, selected=False):
        window = self.window()
        settings_manager = getattr(window, "settings_manager", None)
        if settings_manager is None:
            return self.palette().windowText().color()
        theme = ThemeManager.get_theme(
            settings_manager.get_ui_theme(),
            settings_manager.get_custom_themes()
        )
        return QColor(theme["app"]["text" if selected else "muted"])

    def label_contents_rect(self, tab_rect):
        return tab_rect.adjusted(
            self.label_left_padding,
            0,
            -self.label_right_padding,
            -self.underline_height
        )

    def draw_left_aligned_label(self, painter, option, index):
        label_rect = self.label_contents_rect(option.rect)
        icon = self.tabIcon(index)
        icon_size = self.iconSize() if not icon.isNull() else QSize(0, 0)
        icon_width = icon_size.width() if not icon.isNull() else 0
        gap = self.icon_text_gap if icon_width else 0
        available_text_width = max(0, label_rect.width() - icon_width - gap)
        text = painter.fontMetrics().elidedText(
            self.tabText(index),
            Qt.TextElideMode.ElideRight,
            available_text_width
        )
        text_width = painter.fontMetrics().horizontalAdvance(text)
        content_width = min(label_rect.width(), icon_width + gap + text_width)
        start_x = label_rect.left() + max(0, (label_rect.width() - content_width) // 2)

        if icon_width:
            icon_rect = QRect(
                start_x,
                label_rect.top() + (label_rect.height() - icon_size.height()) // 2 + self.icon_vertical_offset,
                icon_size.width(),
                icon_size.height()
            )
            icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)
            start_x = icon_rect.right() + 1 + gap

        text_rect = QRect(
            start_x,
            label_rect.top(),
            max(0, label_rect.right() - start_x + 1),
            label_rect.height()
        )
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(self.tab_text_color(selected))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine,
            text
        )


class TextEditorApp(QMainWindow):
    def __init__(self, file_path=None): 
        super().__init__()
        
        # Create settings manager first
        self.settings_manager = SettingsManager()
        language = self.settings_manager.get_setting("language", "en_US")
        set_language(language)
        self.apply_layout_direction(language)
        
        # Create snippet manager with settings manager
        self.snippet_manager = SnippetManager(self.settings_manager)
        
        # Logical name -> bundled symbolic SVG path (icons/symbolic/)
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
        mode = self.settings_manager.get_setting("icon_contrast", "auto")
        theme = ThemeManager.get_theme(
            self.settings_manager.get_ui_theme(),
            self.settings_manager.get_custom_themes()
        )
        app = theme["app"]

        if mode == "light":
            return "#f8f8f2"
        if mode == "dark":
            return "#17202a"
        if mode == "accent":
            return app["accent"]
        return app["text"]

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

    def setup_workspace_explorer(self):
        """Create the persisted workspace file explorer."""
        self.workspace_widget = QWidget()
        self.workspace_widget.setObjectName("workspaceExplorer")
        workspace_layout = QVBoxLayout(self.workspace_widget)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("workspaceHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 8, 8)
        header_layout.setSpacing(8)

        self.workspace_title = QPushButton(_("Workspace"))
        self.workspace_title.setObjectName("workspaceTitle")
        self.workspace_title.setFlat(True)
        self.workspace_title.setToolTip(_("Switch workspace"))
        self.workspace_title.clicked.connect(self.show_workspace_navigator)
        self.workspace_path_label = QLabel(_("No folder open"))
        self.workspace_path_label.setObjectName("workspacePath")

        title_stack = QWidget()
        title_stack.setObjectName("workspaceIdentity")
        title_stack_layout = QVBoxLayout(title_stack)
        title_stack_layout.setContentsMargins(0, 0, 0, 0)
        title_stack_layout.setSpacing(1)
        title_stack_layout.addWidget(self.workspace_title)
        title_stack_layout.addWidget(self.workspace_path_label)
        header_layout.addWidget(title_stack, 1)

        new_file_button = QPushButton("+")
        new_file_button.setObjectName("workspaceToolButton")
        new_file_button.setFixedSize(24, 24)
        new_file_button.setToolTip(_("New file in workspace"))
        new_file_button.clicked.connect(self.create_workspace_file)
        header_layout.addWidget(new_file_button)

        workspace_layout.addWidget(header)

        self.workspace_model = WorkspaceFileSystemModel(self)
        self.workspace_model.setFilter(
            QDir.Filter.AllDirs |
            QDir.Filter.Files |
            QDir.Filter.NoDotAndDotDot
        )

        self.workspace_tree = WorkspaceTreeView()
        self.workspace_tree.setObjectName("workspaceTree")
        self.workspace_tree.setModel(self.workspace_model)
        self.workspace_tree.setHeaderHidden(True)
        self.workspace_tree.setAnimated(True)
        self.workspace_tree.setAlternatingRowColors(True)
        self.workspace_tree.setAllColumnsShowFocus(True)
        self.workspace_tree.setExpandsOnDoubleClick(True)
        self.workspace_tree.setIndentation(18)
        self.workspace_tree.setRootIsDecorated(True)
        self.workspace_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.workspace_tree.doubleClicked.connect(self.open_workspace_index)
        self.workspace_tree.customContextMenuRequested.connect(self.show_workspace_context_menu)
        for column in range(1, 4):
            self.workspace_tree.hideColumn(column)
        workspace_layout.addWidget(self.workspace_tree)
        self.workspace_widget.hide()
        self.ui_animations = {}

    def animations_enabled(self):
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return False
        return bool(self.settings_manager.get_setting("enable_animations", True))

    def animate_widget_visibility(self, widget, visible, duration=260):
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

        effect = widget.graphicsEffect()
        if not isinstance(effect, QGraphicsOpacityEffect):
            effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(effect)

        group = QParallelAnimationGroup(self)
        opacity_animation = QPropertyAnimation(effect, b"opacity", group)
        opacity_animation.setDuration(duration)
        opacity_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        opacity_animation.setStartValue(0.0 if visible else 1.0)
        opacity_animation.setEndValue(1.0 if visible else 0.0)

        width_animation = QPropertyAnimation(widget, b"maximumWidth", group)
        width_animation.setDuration(duration)
        width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        width_animation.setStartValue(0 if visible else target_width)
        width_animation.setEndValue(target_width if visible else 0)

        group.addAnimation(opacity_animation)
        group.addAnimation(width_animation)
        self.ui_animations[widget] = group

        if visible:
            widget.setMaximumWidth(0)
            effect.setOpacity(0.0)
            widget.setVisible(True)
        else:
            widget.setMaximumWidth(target_width)
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

    def restore_workspace(self):
        """Restore the last workspace and open workspace files."""
        path = self.settings_manager.get_setting("workspace_path", "")
        if path and os.path.isdir(path):
            self.set_workspace_path(path, save=False)
            self.restore_workspace_session(path)

    def set_workspace_path(self, path, save=True):
        """Set and display the active workspace directory."""
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return False

        self.workspace_path = path
        root_index = self.workspace_model.setRootPath(path)
        self.workspace_tree.setRootIndex(root_index)
        self.workspace_title.setText(os.path.basename(path) or path)
        self.workspace_title.setToolTip(_("Switch workspace\n{path}").format(path=path))
        self.workspace_path_label.setText(os.path.dirname(path) or path)
        self.workspace_path_label.setToolTip(path)
        self.animate_widget_visibility(self.workspace_widget, True)
        self.workspace_tree.expand(root_index)
        if save:
            self.settings_manager.save_setting("workspace_path", path)
            self.add_recent_workspace(path)
            self.save_workspace_markdown_files()
        self.statusBar.showMessage(_("Workspace: {path}").format(path=path))
        return True

    def open_workspace_dialog(self):
        """Choose a directory to use as the current workspace."""
        start_dir = self.workspace_path or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, _("Open Workspace"), start_dir)
        if directory:
            self.switch_workspace(directory)

    def show_workspace_navigator(self):
        """Show recent workspace switcher under the workspace title."""
        menu = QMenu(self)
        recent_workspaces = self.get_recent_workspaces()
        if self.workspace_path:
            current_action = menu.addAction(os.path.basename(self.workspace_path) or self.workspace_path)
            current_action.setEnabled(False)
            menu.addSeparator()

        for workspace in recent_workspaces:
            if workspace == self.workspace_path:
                continue
            label = os.path.basename(workspace) or workspace
            action = menu.addAction(label)
            action.setToolTip(workspace)
            action.setEnabled(os.path.isdir(workspace))
            action.triggered.connect(lambda checked=False, path=workspace: self.switch_workspace(path))

        if recent_workspaces:
            menu.addSeparator()
        menu.addAction(_("Open Workspace..."), self.open_workspace_dialog)
        menu.addAction(_("Clear Missing Workspaces"), self.clear_missing_workspaces)
        menu.exec(self.workspace_title.mapToGlobal(self.workspace_title.rect().bottomLeft()))

    def get_recent_workspaces(self):
        """Return existing recent workspaces, preserving order."""
        workspaces = self.settings_manager.get_setting("recent_workspaces", [])
        if not isinstance(workspaces, list):
            return []
        clean = []
        for workspace in workspaces:
            path = os.path.abspath(str(workspace))
            if path not in clean:
                clean.append(path)
        return clean

    def add_recent_workspace(self, path):
        """Put a workspace at the top of the recent list."""
        path = os.path.abspath(path)
        recent = [item for item in self.get_recent_workspaces() if item != path]
        recent.insert(0, path)
        self.settings_manager.save_setting("recent_workspaces", recent[:12])

    def clear_missing_workspaces(self):
        """Remove recent workspaces that no longer exist."""
        self.settings_manager.save_setting(
            "recent_workspaces",
            [path for path in self.get_recent_workspaces() if os.path.isdir(path)]
        )

    def get_workspace_sessions(self):
        """Return stored per-workspace sessions."""
        sessions = self.settings_manager.get_setting("workspace_sessions", {})
        return sessions if isinstance(sessions, dict) else {}

    def save_workspace_sessions(self, sessions):
        self.settings_manager.save_setting("workspace_sessions", sessions)

    def workspace_relative_path(self, path, workspace=None):
        """Store workspace files relative to their workspace root."""
        workspace = workspace or self.workspace_path
        try:
            return os.path.relpath(os.path.abspath(path), workspace)
        except ValueError:
            return os.path.abspath(path)

    def workspace_absolute_path(self, path, workspace=None):
        """Resolve session paths, accepting older absolute paths too."""
        workspace = workspace or self.workspace_path
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(workspace, path))

    def save_current_workspace_session(self):
        """Save the current workspace's open files and Markdown inventory."""
        if not self.workspace_path:
            return
        sessions = self.get_workspace_sessions()
        workspace = self.workspace_path
        open_files = [
            self.workspace_relative_path(path, workspace)
            for path in self.get_open_files()
            if self.is_path_in_workspace(path)
        ]
        markdown_files = [
            self.workspace_relative_path(path, workspace)
            for path in self.get_workspace_markdown_files()
        ]
        sessions[workspace] = {
            "open_files": open_files,
            "markdown_files": markdown_files
        }
        self.save_workspace_sessions(sessions)
        self.settings_manager.save_setting("workspace_open_files", [
            self.workspace_absolute_path(path, workspace)
            for path in open_files
        ])
        self.settings_manager.save_setting("workspace_markdown_files", [
            self.workspace_absolute_path(path, workspace)
            for path in markdown_files
        ])

    def restore_workspace_session(self, workspace):
        """Open files remembered for a workspace."""
        sessions = self.get_workspace_sessions()
        session = sessions.get(os.path.abspath(workspace), {})
        open_files = session.get("open_files")
        if not open_files:
            open_files = self.settings_manager.get_setting("workspace_open_files", [])

        for file_path in open_files:
            absolute_path = self.workspace_absolute_path(file_path, workspace)
            if self.is_path_in_workspace(absolute_path) and os.path.isfile(absolute_path):
                self.open_file(absolute_path)

    def switch_workspace(self, path):
        """Switch to a workspace and restore its session."""
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            QMessageBox.warning(self, _("Workspace"), _("Workspace directory does not exist."))
            return False
        if path == self.workspace_path:
            return True
        self.save_current_workspace_session()
        if not self.close_current_workspace_tabs():
            return False
        self.set_workspace_path(path, save=True)
        self.restore_workspace_session(path)
        if self.tab_widget.count() == 0:
            self.new_editor_tab()
        return True

    def close_current_workspace_tabs(self):
        """Close tabs owned by the current workspace before switching."""
        if not self.workspace_path:
            return True
        index = self.tab_widget.count() - 1
        while index >= 0:
            tab = self.tab_widget.widget(index)
            if isinstance(tab, EditorTab) and self.is_path_in_workspace(tab.current_file):
                if tab.editor.document().isModified():
                    reply = QMessageBox.question(
                        self,
                        _("Unsaved Changes"),
                        _("{filename} has unsaved changes. Save before switching workspaces?").format(
                            filename=os.path.basename(tab.current_file)
                        ),
                        QMessageBox.StandardButton.Save |
                        QMessageBox.StandardButton.Discard |
                        QMessageBox.StandardButton.Cancel
                    )
                    if reply == QMessageBox.StandardButton.Save and not tab.save_file():
                        return False
                    if reply == QMessageBox.StandardButton.Cancel:
                        return False
                self.tab_widget.removeTab(index)
                tab.deleteLater()
            index -= 1
        return True

    def is_path_in_workspace(self, path):
        """Return True when a file belongs to the active workspace."""
        if not self.workspace_path or not path:
            return False
        try:
            return os.path.commonpath([
                os.path.abspath(path),
                self.workspace_path
            ]) == self.workspace_path
        except ValueError:
            return False

    def save_workspace_open_files(self):
        """Persist open files that are inside the active workspace."""
        if not self.workspace_path:
            self.settings_manager.save_setting("workspace_open_files", [])
            return
        workspace = self.workspace_path
        files = [
            path for path in self.get_open_files()
            if self.is_path_in_workspace(path)
        ]
        self.settings_manager.save_setting("workspace_open_files", files)
        sessions = self.get_workspace_sessions()
        session = sessions.get(workspace, {})
        session["open_files"] = [
            self.workspace_relative_path(path, workspace)
            for path in files
        ]
        sessions[workspace] = session
        self.save_workspace_sessions(sessions)

    def get_workspace_markdown_files(self):
        """Return all Markdown files under the active workspace."""
        if not self.workspace_path:
            return []
        markdown_files = []
        markdown_extensions = (".md", ".markdown", ".mdown", ".mkd")
        for root, _dirs, files in os.walk(self.workspace_path):
            for filename in files:
                if filename.lower().endswith(markdown_extensions):
                    markdown_files.append(os.path.join(root, filename))
        return sorted(markdown_files)

    def save_workspace_markdown_files(self):
        """Persist the current workspace Markdown inventory."""
        markdown_files = self.get_workspace_markdown_files()
        self.settings_manager.save_setting("workspace_markdown_files", markdown_files)
        if self.workspace_path:
            workspace = self.workspace_path
            sessions = self.get_workspace_sessions()
            session = sessions.get(workspace, {})
            session["markdown_files"] = [
                self.workspace_relative_path(path, workspace)
                for path in markdown_files
            ]
            sessions[workspace] = session
            self.save_workspace_sessions(sessions)

    def selected_workspace_directory(self):
        """Return the selected folder, or containing folder for a selected file."""
        if not self.workspace_path:
            return ""
        index = self.workspace_tree.currentIndex()
        if index.isValid():
            path = self.workspace_model.filePath(index)
            if os.path.isdir(path):
                return path
            if os.path.isfile(path):
                return os.path.dirname(path)
        return self.workspace_path

    def open_workspace_index(self, index):
        """Open a file from the workspace tree."""
        path = self.workspace_model.filePath(index)
        if os.path.isfile(path):
            self.open_file(path)

    def show_workspace_context_menu(self, position):
        """Show workspace file operations."""
        if not self.workspace_path:
            return
        menu = QMenu(self)
        menu.addAction(_("New File"), self.create_workspace_file)
        menu.addAction(_("New Folder"), self.create_workspace_folder)
        menu.addSeparator()
        index = self.workspace_tree.indexAt(position)
        if index.isValid() and os.path.isfile(self.workspace_model.filePath(index)):
            menu.addAction(_("Open"), lambda: self.open_workspace_index(index))
        menu.exec(self.workspace_tree.mapToGlobal(position))

    def create_workspace_file(self):
        """Create any file inside the active workspace."""
        if not self.workspace_path:
            self.open_workspace_dialog()
            if not self.workspace_path:
                return
        directory = self.selected_workspace_directory()
        name, ok = QInputDialog.getText(self, _("New File"), _("File name:"))
        if not ok or not name.strip():
            return
        target = os.path.abspath(os.path.join(directory, name.strip()))
        if not self.is_path_in_workspace(target):
            QMessageBox.warning(self, _("Workspace"), _("File must be inside the workspace."))
            return
        if os.path.exists(target):
            QMessageBox.warning(self, _("Workspace"), _("A file or folder with that name already exists."))
            return
        os.makedirs(os.path.dirname(target), exist_ok=True)
        try:
            with open(target, "w", encoding="utf-8"):
                pass
        except OSError as exc:
            QMessageBox.critical(self, _("Workspace"), _("Could not create file: {error}").format(error=exc))
            return
        self.save_workspace_markdown_files()
        self.open_file(target)

    def create_workspace_folder(self):
        """Create a folder inside the active workspace."""
        if not self.workspace_path:
            return
        directory = self.selected_workspace_directory()
        name, ok = QInputDialog.getText(self, _("New Folder"), _("Folder name:"))
        if not ok or not name.strip():
            return
        target = os.path.abspath(os.path.join(directory, name.strip()))
        if not self.is_path_in_workspace(target):
            QMessageBox.warning(self, _("Workspace"), _("Folder must be inside the workspace."))
            return
        try:
            os.makedirs(target, exist_ok=False)
        except OSError as exc:
            QMessageBox.critical(self, _("Workspace"), _("Could not create folder: {error}").format(error=exc))
            return
        self.save_workspace_markdown_files()
        
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
            reply = QMessageBox.question(
                self,
                _("Unsaved Changes"),
                _("This document has unsaved changes. Do you want to save them?"),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
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
            reply = QMessageBox.question(
                self,
                _("Unsaved Changes"),
                _("You have unsaved changes. Do you want to save them before closing?"),
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
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
