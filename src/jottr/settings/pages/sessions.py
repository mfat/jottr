"""Sessions page: swap file backup and restoring new unsaved files."""
from PyQt6.QtWidgets import QCheckBox, QGroupBox, QLabel, QVBoxLayout, QWidget

from jottr.session_recovery import SWAP_FILE_SETTING, STASH_NEW_FILES_SETTING
from jottr.translation_manager import _


class SessionsPageMixin:
    """Builds the Sessions page. Expects SettingsDialog host."""

    def build_sessions_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

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
            lambda checked: self._save_only(
                lambda: self.settings_manager.save_setting(
                    STASH_NEW_FILES_SETTING, bool(checked))
            )
        )
        box_layout.addWidget(self.restore_unsaved_new_files_check)
        box_layout.addWidget(self._sessions_hint_label(_(
            "Untitled documents are kept when Jottr closes, without asking to "
            "save them, and reopened the next time it starts."
        )))

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

    def sync_sessions_page(self):
        sm = self.settings_manager
        self.swap_file_enabled_check.setChecked(
            bool(sm.get_setting(SWAP_FILE_SETTING, True))
        )
        self.restore_unsaved_new_files_check.setChecked(
            bool(sm.get_setting(STASH_NEW_FILES_SETTING, True))
        )
