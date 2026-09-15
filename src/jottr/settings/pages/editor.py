"""Editor page: tab-bar mouse behavior, markdown preview, saving, and autosave."""
from datetime import date

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QComboBox, QGroupBox, QFormLayout,
    QSpinBox, QWidget,
)

from jottr.settings_manager import (
    SAVE_NAME_DATE_FORMAT_DEFAULT,
    SAVE_NAME_DATE_FORMATS,
    format_save_name_date,
)
from jottr.translation_manager import _

AUTOSAVE_MIN_SECONDS = 1
AUTOSAVE_MAX_SECONDS = 3600
AUTOSAVE_DEFAULT_SECONDS = 30


class EditorPageMixin:
    """Builds the Editor page and its helpers. Expects SettingsDialog host."""

    def build_editor_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tabs_box = QGroupBox(_("Tabs"))
        tabs_layout = QVBoxLayout(tabs_box)
        tabs_layout.setContentsMargins(12, 10, 12, 12)
        tabs_layout.setSpacing(8)
        self.double_click_empty_tab_bar_new_tab_check = QCheckBox(
            _("Double-click empty tab bar to open a new tab")
        )
        self.double_click_empty_tab_bar_new_tab_check.toggled.connect(
            lambda checked: self._save_only(
                lambda: self.settings_manager.save_setting(
                    "double_click_empty_tab_bar_new_tab", bool(checked))
            )
        )
        tabs_layout.addWidget(self.double_click_empty_tab_bar_new_tab_check)
        self.middle_click_tab_closes_tab_check = QCheckBox(
            _("Middle-click existing tab to close it")
        )
        self.middle_click_tab_closes_tab_check.toggled.connect(
            lambda checked: self._save_only(
                lambda: self.settings_manager.save_setting(
                    "middle_click_tab_closes_tab", bool(checked))
            )
        )
        tabs_layout.addWidget(self.middle_click_tab_closes_tab_check)
        layout.addWidget(tabs_box)

        markdown_box = QGroupBox(_("Markdown"))
        markdown_layout = QVBoxLayout(markdown_box)
        markdown_layout.setContentsMargins(12, 10, 12, 12)
        markdown_layout.setSpacing(8)
        self.markdown_scroll_sync_check = QCheckBox(
            _("Sync markdown editor and preview scrolling")
        )
        self.markdown_scroll_sync_check.toggled.connect(
            lambda checked: self._save_only(
                lambda: self.settings_manager.save_setting(
                    "markdown_scroll_sync", bool(checked))
            )
        )
        markdown_layout.addWidget(self.markdown_scroll_sync_check)
        layout.addWidget(markdown_box)

        saving_box = QGroupBox(_("Saving"))
        saving_layout = QFormLayout(saving_box)
        saving_layout.setContentsMargins(12, 10, 12, 12)
        saving_layout.setSpacing(8)
        self.save_name_date_check = QCheckBox(_("Add the date to suggested file names"))
        self.save_name_date_check.toggled.connect(self._on_save_name_date_toggled)
        saving_layout.addRow(self.save_name_date_check)
        self.save_name_date_format_combo = QComboBox()
        today = date.today()
        for date_format in SAVE_NAME_DATE_FORMATS:
            example = format_save_name_date(date_format, today)
            self.save_name_date_format_combo.addItem(f"{date_format} ({example})", date_format)
        # Connected after filling, so adding the first item saves nothing.
        self.save_name_date_format_combo.currentIndexChanged.connect(
            self._on_save_name_date_format_changed
        )
        self.save_name_date_format_label = QLabel(_("Date format:"))
        saving_layout.addRow(self.save_name_date_format_label, self.save_name_date_format_combo)
        layout.addWidget(saving_box)

        autosave_box = QGroupBox(_("Autosave"))
        autosave_layout = QFormLayout(autosave_box)
        autosave_layout.setContentsMargins(12, 10, 12, 12)
        autosave_layout.setSpacing(8)
        self.autosave_enabled_check = QCheckBox(_("Automatically save changed files"))
        self.autosave_enabled_check.toggled.connect(self._on_autosave_toggled)
        autosave_layout.addRow(self.autosave_enabled_check)

        interval_row = QHBoxLayout()
        self.autosave_interval_spin = QSpinBox()
        self.autosave_interval_spin.setRange(AUTOSAVE_MIN_SECONDS, AUTOSAVE_MAX_SECONDS)
        self.autosave_interval_spin.valueChanged.connect(self._on_autosave_interval_changed)
        self.autosave_interval_unit_label = QLabel(_("Seconds"))
        interval_row.addWidget(self.autosave_interval_spin)
        interval_row.addWidget(self.autosave_interval_unit_label)
        interval_row.addStretch()
        self.autosave_interval_label = QLabel(_("Save changed files every:"))
        autosave_layout.addRow(self.autosave_interval_label, interval_row)
        layout.addWidget(autosave_box)
        layout.addStretch()

        self.sync_editor_page()
        return page

    def sync_editor_page(self):
        sm = self.settings_manager
        self.double_click_empty_tab_bar_new_tab_check.setChecked(
            bool(sm.get_setting("double_click_empty_tab_bar_new_tab", True))
        )
        self.middle_click_tab_closes_tab_check.setChecked(
            bool(sm.get_setting("middle_click_tab_closes_tab", True))
        )
        self.markdown_scroll_sync_check.setChecked(
            bool(sm.get_setting("markdown_scroll_sync", True))
        )
        self.save_name_date_check.setChecked(
            bool(sm.get_setting("save_name_append_date", False))
        )
        format_index = self.save_name_date_format_combo.findData(
            sm.get_setting("save_name_date_format", SAVE_NAME_DATE_FORMAT_DEFAULT)
        )
        self.save_name_date_format_combo.setCurrentIndex(max(0, format_index))
        self._update_save_name_date_format_enabled()
        self.autosave_enabled_check.setChecked(
            bool(sm.get_setting("autosave_enabled", False))
        )
        self.set_autosave_interval(
            sm.get_setting("autosave_interval_seconds", AUTOSAVE_DEFAULT_SECONDS)
        )
        self._update_autosave_interval_enabled()

    def _update_save_name_date_format_enabled(self):
        enabled = self.save_name_date_check.isChecked()
        self.save_name_date_format_label.setEnabled(enabled)
        self.save_name_date_format_combo.setEnabled(enabled)

    def _on_save_name_date_toggled(self, checked):
        self._update_save_name_date_format_enabled()
        self._save_only(
            lambda: self.settings_manager.save_setting("save_name_append_date", bool(checked))
        )

    def _on_save_name_date_format_changed(self, _index=None):
        date_format = self.save_name_date_format_combo.currentData()
        if date_format:
            self._save_only(
                lambda: self.settings_manager.save_setting("save_name_date_format", date_format)
            )

    def _update_autosave_interval_enabled(self):
        enabled = self.autosave_enabled_check.isChecked()
        self.autosave_interval_label.setEnabled(enabled)
        self.autosave_interval_spin.setEnabled(enabled)
        self.autosave_interval_unit_label.setEnabled(enabled)

    def _on_autosave_toggled(self, checked):
        self._update_autosave_interval_enabled()
        self._commit(
            "autosave",
            lambda: self.settings_manager.save_setting("autosave_enabled", bool(checked)),
        )

    def _on_autosave_interval_changed(self, _value=None):
        self._commit(
            "autosave",
            lambda: self.settings_manager.save_setting(
                "autosave_interval_seconds", self.autosave_interval_seconds()
            ),
        )

    def set_autosave_interval(self, seconds):
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            seconds = AUTOSAVE_DEFAULT_SECONDS
        self.autosave_interval_spin.setValue(
            min(AUTOSAVE_MAX_SECONDS, max(AUTOSAVE_MIN_SECONDS, seconds))
        )

    def autosave_interval_seconds(self):
        return self.autosave_interval_spin.value()
