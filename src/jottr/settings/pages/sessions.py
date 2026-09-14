"""Sessions page: swap file backup and restoring new unsaved files."""
from PyQt6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QRadioButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from jottr.session_recovery import (
    SESSION_RESTORE_ALWAYS,
    SESSION_RESTORE_SETTING,
    SESSION_RESTORE_UNSAVED,
    STASH_NEW_FILES_SETTING,
    SWAP_FILE_SETTING,
    SWAP_SYNC_DEFAULT_SECONDS,
    SWAP_SYNC_INTERVAL_SETTING,
    SWAP_SYNC_MAX_SECONDS,
    SWAP_SYNC_MIN_SECONDS,
)
from jottr.translation_manager import _


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
        for radio, mode in (
            (self.restore_session_always_radio, SESSION_RESTORE_ALWAYS),
            (self.restore_session_unsaved_radio, SESSION_RESTORE_UNSAVED),
        ):
            radio.toggled.connect(
                lambda checked, mode=mode: self._on_session_restore_mode_toggled(mode, checked)
            )
            startup_layout.addWidget(radio)
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
            "next time Jottr starts, even after a crash. Closing Jottr does not "
            "ask to save them."
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
        return SESSION_RESTORE_ALWAYS

    def _on_session_restore_mode_toggled(self, mode, checked):
        # Only read on startup, so there is nothing to apply now.
        if checked:
            self._save_only(
                lambda: self.settings_manager.save_setting(SESSION_RESTORE_SETTING, mode)
            )

    def sync_sessions_page(self):
        sm = self.settings_manager
        if sm.get_setting(SESSION_RESTORE_SETTING, SESSION_RESTORE_ALWAYS) == SESSION_RESTORE_UNSAVED:
            self.restore_session_unsaved_radio.setChecked(True)
        else:
            self.restore_session_always_radio.setChecked(True)
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
