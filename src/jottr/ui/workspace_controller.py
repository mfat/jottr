"""Workspace explorer setup and session persistence for TextEditorApp."""
import os
import shutil

from PyQt6.QtCore import Qt, QDir, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMenu,
    QMessageBox, QInputDialog, QApplication,
)

from jottr.translation_manager import _
from jottr.icon_manager import ask_themed_question
from jottr.file_dialogs import get_existing_directory
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

    def restore_workspace(self, open_files=True):
        """Restore the last workspace and, with *open_files*, its open files."""
        path = self.settings_manager.get_setting("workspace_path", "")
        if path and os.path.isdir(path):
            self.set_workspace_path(path, save=False)
            if open_files:
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
        self.update_workspace_actions()
        self.statusBar.showMessage(_("Workspace: {path}").format(path=path))
        return True

    def open_workspace_dialog(self):
        """Choose a directory to use as the current workspace."""
        start_dir = self.workspace_path or os.path.expanduser("~")
        directory = get_existing_directory(self, _("Open Workspace"), start_dir)
        if directory:
            self.switch_workspace(directory)

    def close_workspace(self):
        """Save the session, close workspace tabs, and hide the explorer."""
        if not self.workspace_path:
            return True
        self.save_current_workspace_session()
        if not self.close_current_workspace_tabs():
            return False

        self.workspace_path = ""
        self.workspace_title.setText(_("Workspace"))
        self.workspace_title.setToolTip(_("Switch workspace"))
        self.workspace_path_label.setText(_("No folder open"))
        self.workspace_path_label.setToolTip("")
        self.animate_widget_visibility(self.workspace_widget, False)
        self.settings_manager.save_setting("workspace_path", "")
        self.settings_manager.save_setting("workspace_open_files", [])
        self.settings_manager.save_setting("workspace_markdown_files", [])
        self.update_workspace_actions()
        self.statusBar.showMessage(_("Workspace closed"))
        if self.tab_widget.count() == 0:
            self.new_editor_tab()
        return True

    def update_workspace_actions(self):
        """Enable workspace-dependent menubar actions."""
        has_workspace = bool(getattr(self, "workspace_path", ""))
        if hasattr(self, "close_workspace_action"):
            self.close_workspace_action.setEnabled(has_workspace)
        if hasattr(self, "new_workspace_folder_action"):
            self.new_workspace_folder_action.setEnabled(has_workspace)

    def workspace_display_label(self, path, candidates):
        """Prefer basename; disambiguate when multiple entries share it."""
        base = os.path.basename(path) or path
        collisions = [
            candidate for candidate in candidates
            if (os.path.basename(candidate) or candidate) == base
        ]
        if len(collisions) > 1:
            parent = os.path.dirname(path)
            if parent:
                return f"{base} — {parent}"
        return base

    def populate_recent_workspace_actions(self, menu):
        """Add current + recent workspace switcher actions to a menu."""
        recent = self.get_recent_workspaces()
        candidates = list(recent)
        if self.workspace_path and self.workspace_path not in candidates:
            candidates.insert(0, self.workspace_path)

        if self.workspace_path:
            current_action = menu.addAction(
                self.workspace_display_label(self.workspace_path, candidates)
            )
            current_action.setEnabled(False)
            current_action.setToolTip(self.workspace_path)
            menu.addSeparator()

        added = False
        for workspace in recent:
            if workspace == self.workspace_path:
                continue
            action = menu.addAction(self.workspace_display_label(workspace, candidates))
            action.setToolTip(workspace)
            action.setEnabled(os.path.isdir(workspace))
            action.triggered.connect(
                lambda checked=False, path=workspace: self.switch_workspace(path)
            )
            added = True
        return added

    def show_workspace_navigator(self):
        """Show recent workspace switcher under the workspace title."""
        menu = QMenu(self)
        added = self.populate_recent_workspace_actions(menu)
        if added or self.workspace_path:
            menu.addSeparator()
        menu.addAction(_("Open Workspace..."), self.open_workspace_dialog)
        menu.addAction(_("Clear Missing Workspaces"), self.clear_missing_workspaces)
        if self.workspace_path:
            menu.addAction(_("Close Workspace"), self.close_workspace)
        menu.exec(self.workspace_title.mapToGlobal(self.workspace_title.rect().bottomLeft()))

    def refresh_workspace_menu(self):
        """Rebuild the Workspace menubar with current recent entries."""
        menu = getattr(self, "workspace_menu", None)
        if menu is None:
            return

        menu.clear()
        menu.addAction(self.open_workspace_action)

        recent = self.get_recent_workspaces()
        if self.workspace_path or recent:
            menu.addSeparator()
            self.populate_recent_workspace_actions(menu)

        menu.addSeparator()
        menu.addAction(self.new_workspace_file_action)
        menu.addAction(self.new_workspace_folder_action)
        menu.addSeparator()
        menu.addAction(self.close_workspace_action)
        menu.addAction(self.clear_missing_workspaces_action)
        self.update_workspace_actions()

    def get_recent_workspaces(self):
        """Return recent workspaces, preserving order and deduplicating."""
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
        recent = self.get_recent_workspaces()
        existing = [path for path in recent if os.path.isdir(path)]
        removed = len(recent) - len(existing)
        self.settings_manager.save_setting("recent_workspaces", existing)
        if removed:
            self.statusBar.showMessage(
                _("Removed {count} missing workspace(s)").format(count=removed)
            )
        else:
            self.statusBar.showMessage(_("No missing workspaces"))

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
                    reply = ask_themed_question(
                        self,
                        _("Unsaved Changes"),
                        _("{filename} has unsaved changes. Save before switching workspaces?").format(
                            filename=os.path.basename(tab.current_file)
                        ),
                        QMessageBox.StandardButton.Save
                        | QMessageBox.StandardButton.Discard
                        | QMessageBox.StandardButton.Cancel,
                        QMessageBox.StandardButton.Save,
                        getattr(self, "settings_manager", None),
                    )
                    if reply == QMessageBox.StandardButton.Save and not tab.save_file():
                        return False
                    if reply == QMessageBox.StandardButton.Cancel:
                        return False
                release_swap_file = getattr(tab, "release_swap_file", None)
                if release_swap_file is not None:
                    release_swap_file()
                self.tab_widget.removeTab(index)
                tab.deleteLater()
            index -= 1
        self.save_session()
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

    def path_is_within(self, path, root):
        """Return True when path is root or nested under root."""
        if not path or not root:
            return False
        path = os.path.abspath(path)
        root = os.path.abspath(root)
        try:
            return os.path.commonpath([path, root]) == root
        except ValueError:
            return False

    def remap_open_tabs_for_path_change(self, old_path, new_path=None):
        """Update or close tabs after a workspace rename or delete."""
        old_path = os.path.abspath(old_path)
        index = self.tab_widget.count() - 1
        while index >= 0:
            tab = self.tab_widget.widget(index)
            current = getattr(tab, "current_file", None)
            if not current:
                index -= 1
                continue
            current = os.path.abspath(current)
            if not self.path_is_within(current, old_path):
                index -= 1
                continue
            if new_path is None:
                release_swap_file = getattr(tab, "release_swap_file", None)
                if release_swap_file is not None:
                    release_swap_file()
                self.tab_widget.removeTab(index)
                tab.deleteLater()
            else:
                if current == old_path:
                    tab.current_file = os.path.abspath(new_path)
                else:
                    relative = os.path.relpath(current, old_path)
                    tab.current_file = os.path.abspath(os.path.join(new_path, relative))
                # Move unsaved changes to the swap file of the new name.
                write_swap_file = getattr(tab, "write_swap_file", None)
                if write_swap_file is not None:
                    write_swap_file()
                tab_index = self.tab_widget.indexOf(tab)
                if tab_index >= 0:
                    title = os.path.basename(tab.current_file)
                    if hasattr(tab, "editor") and tab.editor.document().isModified():
                        title += "*"
                    self.tab_widget.setTabText(tab_index, title)
            index -= 1

    def save_workspace_open_files(self):
        """Persist the open tabs session and the active workspace's open files."""
        self.save_session()
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
        index = self.workspace_tree.indexAt(position)
        path = ""
        if index.isValid():
            path = self.workspace_model.filePath(index)
            if os.path.isfile(path):
                menu.addAction(_("Open"), lambda: self.open_workspace_index(index))
                menu.addSeparator()

        menu.addAction(_("New File"), self.create_workspace_file)
        menu.addAction(_("New Folder"), self.create_workspace_folder)

        if path and (os.path.isfile(path) or os.path.isdir(path)):
            is_root = os.path.abspath(path) == os.path.abspath(self.workspace_path)
            if not is_root:
                menu.addSeparator()
                menu.addAction(_("Rename..."), lambda checked=False, p=path: self.rename_workspace_item(p))
                menu.addAction(_("Delete..."), lambda checked=False, p=path: self.delete_workspace_item(p))
            menu.addSeparator()
            menu.addAction(_("Copy Path"), lambda checked=False, p=path: self.copy_workspace_path(p))
            menu.addAction(
                _("Reveal in File Manager"),
                lambda checked=False, p=path: self.reveal_workspace_item(p),
            )
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
            self.open_workspace_dialog()
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

    def rename_workspace_item(self, path):
        """Rename a file or folder inside the workspace."""
        path = os.path.abspath(path)
        if not self.workspace_path or not self.is_path_in_workspace(path):
            return
        if path == os.path.abspath(self.workspace_path):
            return
        name, ok = QInputDialog.getText(
            self,
            _("Rename"),
            _("New name:"),
            text=os.path.basename(path),
        )
        if not ok or not name.strip():
            return
        target = os.path.abspath(os.path.join(os.path.dirname(path), name.strip()))
        if target == path:
            return
        if not self.is_path_in_workspace(target):
            QMessageBox.warning(self, _("Workspace"), _("Item must stay inside the workspace."))
            return
        if os.path.exists(target):
            QMessageBox.warning(self, _("Workspace"), _("A file or folder with that name already exists."))
            return
        try:
            os.rename(path, target)
        except OSError as exc:
            QMessageBox.critical(self, _("Workspace"), _("Could not rename: {error}").format(error=exc))
            return
        self.remap_open_tabs_for_path_change(path, target)
        self.save_workspace_markdown_files()
        self.save_workspace_open_files()

    def delete_workspace_item(self, path):
        """Delete a file or folder inside the workspace."""
        path = os.path.abspath(path)
        if not self.workspace_path or not self.is_path_in_workspace(path):
            return
        if path == os.path.abspath(self.workspace_path):
            return
        label = os.path.basename(path) or path
        if os.path.isdir(path):
            message = _("Delete folder '{name}' and all of its contents?").format(name=label)
        else:
            message = _("Delete '{name}'?").format(name=label)
        reply = ask_themed_question(
            self,
            _("Delete"),
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
            getattr(self, "settings_manager", None),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except OSError as exc:
            QMessageBox.critical(self, _("Workspace"), _("Could not delete: {error}").format(error=exc))
            return
        self.remap_open_tabs_for_path_change(path, None)
        self.save_workspace_markdown_files()
        self.save_workspace_open_files()
        if self.tab_widget.count() == 0:
            self.new_editor_tab()

    def copy_workspace_path(self, path):
        """Copy an absolute path to the clipboard."""
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return
        clipboard.setText(os.path.abspath(path))
        self.statusBar.showMessage(_("Copied path"))

    def reveal_workspace_item(self, path):
        """Open the item's folder in the system file manager."""
        path = os.path.abspath(path)
        target = path if os.path.isdir(path) else os.path.dirname(path)
        if not target or not os.path.isdir(target):
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(target))
