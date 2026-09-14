"""Sessions page: startup restore, swap file backup and restoring new unsaved files."""
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QRadioButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from jottr.file_dialogs import get_existing_directory
from jottr.session_recovery import (
    SESSION_RESTORE_ALWAYS,
    SESSION_RESTORE_SETTING,
    SESSION_RESTORE_UNSAVED,
    SESSION_RESTORE_WORKSPACE,
    STARTUP_WORKSPACE_SETTING,
    STASH_NEW_FILES_SETTING,
    SWAP_FILE_SETTING,
    SWAP_SYNC_DEFAULT_SECONDS,
    SWAP_SYNC_INTERVAL_SETTING,
    SWAP_SYNC_MAX_SECONDS,
    SWAP_SYNC_MIN_SECONDS,
)
from jottr.translation_manager import _

# Item data of the workspace dropdown entry that opens a folder picker.
_CHOOSE_FOLDER = "\0choose-folder"


class SessionsPageMixin:
    """Builds the Sessions page. Expects SettingsDialog host."""

    def build_sessions_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        startup_box = QGroupBox(_("Session restore behavior on startup"))
        startup_layout = QVBoxLayout(startup_box)
        startup_layout.setContentsMargins(12, 10, 12, 12)
        startup_layout.setSpacing(8)
        self.restore_session_always_radio = QRadioButton(_("Always restore previous session"))
        self.restore_session_unsaved_radio = QRadioButton(
            _("Only restore if unsaved changes are detected")
        )
        self.restore_session_workspace_radio = QRadioButton(_("Open a workspace:"))
        self.startup_workspace_combo = QComboBox()
        self.startup_workspace_combo.activated.connect(self._on_startup_workspace_activated)
        for radio, mode in (
            (self.restore_session_always_radio, SESSION_RESTORE_ALWAYS),
            (self.restore_session_unsaved_radio, SESSION_RESTORE_UNSAVED),
            (self.restore_session_workspace_radio, SESSION_RESTORE_WORKSPACE),
        ):
            radio.toggled.connect(
                lambda checked, mode=mode: self._on_session_restore_mode_toggled(mode, checked)
            )
        startup_layout.addWidget(self.restore_session_always_radio)
        startup_layout.addWidget(self.restore_session_unsaved_radio)
        workspace_row = QHBoxLayout()
        workspace_row.addWidget(self.restore_session_workspace_radio)
        workspace_row.addWidget(self.startup_workspace_combo, 1)
        startup_layout.addLayout(workspace_row)
        startup_layout.addWidget(self._sessions_hint_label(_(
            "Opens the workspace with its tabs, and reopens documents with unsaved "
            "changes from last time."
        )))
        layout.addWidget(startup_box)

        box = QGroupBox(_("Unsaved Files"))
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(12, 10, 12, 12)
        box_layout.setSpacing(8)

        self.swap_file_enabled_check = QCheckBox(_("Back up unsaved files to swap files"))
        self.swap_file_enabled_check.toggled.connect(
            lambda checked: self._commit(
                "sessions",
                lambda: self.settings_manager.save_setting(SWAP_FILE_SETTING, bool(checked)),
            )
        )
        box_layout.addWidget(self.swap_file_enabled_check)
        box_layout.addWidget(self._sessions_hint_label(_(
            "While a file has unsaved changes, a copy is kept so the changes "
            "can be recovered if Jottr does not close properly."
        )))

        self.restore_unsaved_new_files_check = QCheckBox(
            _("Restore newly-created unsaved files on startup")
        )
        self.restore_unsaved_new_files_check.toggled.connect(
            lambda checked: self._commit(
                "sessions",
                lambda: self.settings_manager.save_setting(
                    STASH_NEW_FILES_SETTING, bool(checked)),
            )
        )
        box_layout.addWidget(self.restore_unsaved_new_files_check)
        box_layout.addWidget(self._sessions_hint_label(_(
            "Untitled documents are backed up while you type and reopened the "
            "next time Jottr starts if Jottr does not close properly. Closing "
            "Jottr asks to save them."
        )))

        interval_row = QHBoxLayout()
        self.backup_interval_label = QLabel(_("Back up unsaved text every:"))
        self.backup_interval_spin = QSpinBox()
        self.backup_interval_spin.setRange(SWAP_SYNC_MIN_SECONDS, SWAP_SYNC_MAX_SECONDS)
        self.backup_interval_spin.valueChanged.connect(self._on_backup_interval_changed)
        self.backup_interval_unit_label = QLabel(_("Seconds"))
        interval_row.addWidget(self.backup_interval_label)
        interval_row.addWidget(self.backup_interval_spin)
        interval_row.addWidget(self.backup_interval_unit_label)
        interval_row.addStretch()
        box_layout.addLayout(interval_row)
        self.swap_file_enabled_check.toggled.connect(self._update_backup_interval_enabled)
        self.restore_unsaved_new_files_check.toggled.connect(
            self._update_backup_interval_enabled
        )

        layout.addWidget(box)
        layout.addStretch()

        self.sync_sessions_page()
        return page

    @staticmethod
    def _sessions_hint_label(text):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setEnabled(False)
        return label

    def selected_session_restore_mode(self):
        if self.restore_session_unsaved_radio.isChecked():
            return SESSION_RESTORE_UNSAVED
        if self.restore_session_workspace_radio.isChecked():
            return SESSION_RESTORE_WORKSPACE
        return SESSION_RESTORE_ALWAYS

    def _on_session_restore_mode_toggled(self, mode, checked):
        if mode == SESSION_RESTORE_WORKSPACE:
            self.startup_workspace_combo.setEnabled(checked)
        # Only read on startup, so there is nothing to apply now.
        if not checked:
            return
        self._save_only(
            lambda: self.settings_manager.save_setting(SESSION_RESTORE_SETTING, mode)
        )
        if mode == SESSION_RESTORE_WORKSPACE:
            # The dropdown already shows a workspace: that is the one to open.
            path = self.startup_workspace_combo.currentData()
            if path and path != _CHOOSE_FOLDER:
                self._save_only(
                    lambda: self.settings_manager.save_setting(STARTUP_WORKSPACE_SETTING, path)
                )

    def saved_startup_workspace(self):
        path = self.settings_manager.get_setting(STARTUP_WORKSPACE_SETTING, "")
        return os.path.abspath(path) if isinstance(path, str) and path else ""

    def populate_startup_workspace_combo(self):
        """List the chosen and recent workspaces, then "Choose Folder…"."""
        selected = self.saved_startup_workspace()
        recent = self.settings_manager.get_setting("recent_workspaces", [])
        paths = [selected] if selected else []
        for path in recent if isinstance(recent, list) else []:
            path = os.path.abspath(str(path))
            if path not in paths:
                paths.append(path)
        names = [os.path.basename(path) or path for path in paths]

        combo = self.startup_workspace_combo
        combo.blockSignals(True)
        try:
            combo.clear()
            if not selected:
                combo.addItem(_("No workspace selected"), "")
            for path, name in zip(paths, names):
                # Folders with the same name are told apart by their parent.
                label = f"{name} — {os.path.dirname(path)}" if names.count(name) > 1 else name
                combo.addItem(label, path)
                combo.setItemData(combo.count() - 1, path, Qt.ItemDataRole.ToolTipRole)
            combo.addItem(_("Choose Folder…"), _CHOOSE_FOLDER)
            combo.setCurrentIndex(max(0, combo.findData(selected)))
        finally:
            combo.blockSignals(False)

    def _on_startup_workspace_activated(self, index):
        path = self.startup_workspace_combo.itemData(index)
        if path == _CHOOSE_FOLDER:
            start = self.saved_startup_workspace() or os.path.expanduser("~")
            directory = get_existing_directory(self, _("Choose Workspace Folder"), start)
            path = os.path.abspath(directory) if directory else ""
        if path:
            self._save_only(
                lambda: self.settings_manager.save_setting(STARTUP_WORKSPACE_SETTING, path)
            )
        # Rebuild, so a chosen folder is listed and a cancelled choice is undone.
        self.populate_startup_workspace_combo()

    def sync_sessions_page(self):
        sm = self.settings_manager
        mode = sm.get_setting(SESSION_RESTORE_SETTING, SESSION_RESTORE_UNSAVED)
        {
            SESSION_RESTORE_UNSAVED: self.restore_session_unsaved_radio,
            SESSION_RESTORE_WORKSPACE: self.restore_session_workspace_radio,
        }.get(mode, self.restore_session_always_radio).setChecked(True)
        self.populate_startup_workspace_combo()
        self.startup_workspace_combo.setEnabled(
            self.restore_session_workspace_radio.isChecked()
        )
        self.swap_file_enabled_check.setChecked(
            bool(sm.get_setting(SWAP_FILE_SETTING, True))
        )
        self.restore_unsaved_new_files_check.setChecked(
            bool(sm.get_setting(STASH_NEW_FILES_SETTING, True))
        )
        try:
            seconds = int(sm.get_setting(SWAP_SYNC_INTERVAL_SETTING, SWAP_SYNC_DEFAULT_SECONDS))
        except (TypeError, ValueError):
            seconds = SWAP_SYNC_DEFAULT_SECONDS
        # setValue clamps to the spin box range.
        self.backup_interval_spin.setValue(seconds)
        self._update_backup_interval_enabled()

    def _update_backup_interval_enabled(self, _checked=None):
        enabled = (
            self.swap_file_enabled_check.isChecked()
            or self.restore_unsaved_new_files_check.isChecked()
        )
        self.backup_interval_label.setEnabled(enabled)
        self.backup_interval_spin.setEnabled(enabled)
        self.backup_interval_unit_label.setEnabled(enabled)

    def _on_backup_interval_changed(self, value):
        self._commit(
            "sessions",
            lambda: self.settings_manager.save_setting(SWAP_SYNC_INTERVAL_SETTING, int(value)),
        )
