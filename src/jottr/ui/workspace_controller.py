"""Workspace explorer setup and session persistence for TextEditorApp."""
import os

from PyQt6.QtCore import Qt, QDir
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMenu,
    QFileDialog, QMessageBox, QInputDialog,
)

from jottr.translation_manager import _
from jottr.ui.workspace import WorkspaceFileSystemModel, WorkspaceTreeView


class WorkspaceControllerMixin:
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
            if (
                hasattr(tab, "editor")
                and hasattr(tab, "current_file")
                and self.is_path_in_workspace(tab.current_file)
            ):
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
