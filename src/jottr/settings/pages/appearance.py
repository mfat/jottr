"""Appearance page (moved from settings_dialog, plus instant-apply wiring)."""
import json

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QCheckBox, QPushButton,
    QGroupBox, QPlainTextEdit, QListWidget, QWidget, QDialog, QMessageBox,
    QFormLayout,
)
from PyQt6.QtGui import QFont

from jottr.font_dialog import FontSelectionDialog
from jottr.icon_manager import list_bundled_icon_themes
from jottr.qt_style import available_qt_styles
from jottr.theme_manager import ThemeManager
from jottr.translation_manager import _, format_language_label, get_available_languages


class AppearancePageMixin:
    """Builds the Appearance tab and its helpers. Expects SettingsDialog host."""

    def build_appearance_page(self):
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout(appearance_tab)
        appearance_layout.setContentsMargins(12, 12, 12, 12)
        appearance_layout.setSpacing(10)

        general_box = QGroupBox(_("General"))
        general_layout = QFormLayout(general_box)
        general_layout.setContentsMargins(12, 10, 12, 12)
        general_layout.setSpacing(8)
        language_label = QLabel(_("Language:"))
        self.language_combo = QComboBox()
        self.load_language_options()
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        general_layout.addRow(language_label, self.language_combo)

        window_scheme_label = QLabel(_("Window Color Scheme:"))
        self.window_color_scheme_combo = QComboBox()
        self._populate_window_color_scheme_combo()
        self.window_color_scheme_combo.setToolTip(
            _("Kate-style window palette from installed KDE .colors schemes. "
              "Default follows the system (Breeze Light/Dark when available).")
        )
        self.window_color_scheme_combo.currentIndexChanged.connect(
            self._on_window_color_scheme_changed
        )
        general_layout.addRow(window_scheme_label, self.window_color_scheme_combo)

        editor_theme_label = QLabel(_("Editor Theme:"))
        self.editor_theme_combo = QComboBox()
        self.refresh_editor_theme_combo()
        self.editor_theme_combo.setCurrentText(self.settings_manager.get_theme())
        self.editor_theme_combo.currentTextChanged.connect(self._on_editor_theme_changed)
        general_layout.addRow(editor_theme_label, self.editor_theme_combo)

        qt_style_label = QLabel(_("Widget Style:"))
        self.qt_style_combo = QComboBox()
        self.qt_style_combo.addItems(available_qt_styles())
        self.qt_style_combo.setCurrentText(self.settings_manager.get_qt_style())
        self.qt_style_combo.setToolTip(
            _("Lists every Qt widget style available on this system "
              "(Fusion, Windows, Darkly, desktop styles, and plugins). "
              "System keeps the platform default. "
              "Paired light/dark styles follow Window Color Scheme when both "
              "variants are installed.")
        )
        self.qt_style_combo.currentTextChanged.connect(self._on_qt_style_changed)
        general_layout.addRow(qt_style_label, self.qt_style_combo)

        icon_theme_label = QLabel(_("Icon Theme:"))
        self.icon_theme_combo = QComboBox()
        for theme in list_bundled_icon_themes():
            self.icon_theme_combo.addItem(theme["label"], theme["id"])
        current_icon_theme = self.settings_manager.get_icon_theme()
        icon_theme_index = self.icon_theme_combo.findData(current_icon_theme)
        self.icon_theme_combo.setCurrentIndex(
            icon_theme_index if icon_theme_index >= 0 else 0
        )
        self.icon_theme_combo.setToolTip(
            _("Lists icon packs bundled with Jottr only. "
              "Desktop/system icon themes are not used.")
        )
        self.icon_theme_combo.currentIndexChanged.connect(self._on_icon_theme_changed)
        general_layout.addRow(icon_theme_label, self.icon_theme_combo)

        icon_label = QLabel(_("Icon Contrast:"))
        self.icon_contrast_combo = QComboBox()
        self.icon_contrast_combo.addItems(["auto", "light", "dark", "accent"])
        self.icon_contrast_combo.setCurrentText(
            self.settings_manager.get_setting("icon_contrast", "auto")
        )
        self.icon_contrast_combo.currentTextChanged.connect(self._on_icon_contrast_changed)
        general_layout.addRow(icon_label, self.icon_contrast_combo)

        self.enable_animations_check = QCheckBox(_("Enable smooth animations"))
        self.enable_animations_check.setChecked(
            self.settings_manager.get_setting("enable_animations", True)
        )
        self.enable_animations_check.toggled.connect(self._on_animations_toggled)
        general_layout.addRow(QLabel(_("Motion:")), self.enable_animations_check)

        font_label = QLabel(_("Main UI Font:"))
        self.ui_font_button = self.create_font_button(
            self.ui_font,
            self.choose_ui_font,
            follow_system=self.ui_font_follow_system,
        )
        general_layout.addRow(font_label, self.ui_font_button)
        appearance_layout.addWidget(general_box)

        theme_box = QGroupBox(_("Custom Editor Themes"))
        theme_box_layout = QVBoxLayout(theme_box)
        standard_label = QLabel(
            _("Custom themes set editor and syntax colors only. "
              "Window Color Scheme is unchanged.")
        )
        standard_label.setWordWrap(True)
        theme_box_layout.addWidget(standard_label)

        self.custom_theme_list = QListWidget()
        self.custom_theme_list.currentItemChanged.connect(self.load_selected_custom_theme)
        self.custom_theme_list.setMaximumHeight(95)
        theme_box_layout.addWidget(self.custom_theme_list)

        json_label = QLabel(_("Theme JSON:"))
        theme_box_layout.addWidget(json_label)
        self.theme_json_edit = QPlainTextEdit()
        self.theme_json_edit.setPlaceholderText(json.dumps(ThemeManager.get_theme_standard(), indent=2))
        self.theme_json_edit.setMinimumHeight(130)
        theme_box_layout.addWidget(self.theme_json_edit)

        theme_buttons = QHBoxLayout()
        save_theme = QPushButton(_("Save Theme"))
        delete_theme = QPushButton(_("Delete Theme"))
        use_theme = QPushButton(_("Use Selected"))
        format_json = QPushButton(_("Format JSON"))
        save_theme.clicked.connect(self.save_custom_theme)
        delete_theme.clicked.connect(self.delete_custom_theme)
        use_theme.clicked.connect(self.use_selected_custom_theme)
        format_json.clicked.connect(self.format_theme_json)
        theme_buttons.addWidget(save_theme)
        theme_buttons.addWidget(delete_theme)
        theme_buttons.addWidget(use_theme)
        theme_buttons.addWidget(format_json)
        theme_box_layout.addLayout(theme_buttons)
        appearance_layout.addWidget(theme_box, 1)
        self.load_custom_theme_list()

        editor_box = QGroupBox(_("Editor"))
        editor_layout = QVBoxLayout(editor_box)
        editor_layout.setContentsMargins(12, 10, 12, 12)
        editor_layout.setSpacing(8)
        self.markdown_scroll_sync_check = QCheckBox(_("Sync markdown editor and preview scrolling"))
        self.markdown_scroll_sync_check.setChecked(
            self.settings_manager.get_setting('markdown_scroll_sync', True)
        )
        self.markdown_scroll_sync_check.toggled.connect(
            lambda checked: self._save_only(
                lambda: self.settings_manager.save_setting('markdown_scroll_sync', bool(checked))
            )
        )
        editor_layout.addWidget(self.markdown_scroll_sync_check)

        self.double_click_empty_tab_bar_new_tab_check = QCheckBox(
            _("Double-click empty tab bar to open a new tab")
        )
        self.double_click_empty_tab_bar_new_tab_check.setChecked(
            self.settings_manager.get_setting("double_click_empty_tab_bar_new_tab", True)
        )
        self.double_click_empty_tab_bar_new_tab_check.toggled.connect(
            lambda checked: self._save_only(
                lambda: self.settings_manager.save_setting(
                    "double_click_empty_tab_bar_new_tab", bool(checked))
            )
        )
        editor_layout.addWidget(self.double_click_empty_tab_bar_new_tab_check)

        self.middle_click_tab_closes_tab_check = QCheckBox(
            _("Middle-click existing tab to close it")
        )
        self.middle_click_tab_closes_tab_check.setChecked(
            self.settings_manager.get_setting("middle_click_tab_closes_tab", True)
        )
        self.middle_click_tab_closes_tab_check.toggled.connect(
            lambda checked: self._save_only(
                lambda: self.settings_manager.save_setting(
                    "middle_click_tab_closes_tab", bool(checked))
            )
        )
        editor_layout.addWidget(self.middle_click_tab_closes_tab_check)
        appearance_layout.addWidget(editor_box)

        autosave_box = QGroupBox(_("Autosave"))
        autosave_layout = QVBoxLayout(autosave_box)
        autosave_layout.setContentsMargins(12, 10, 12, 12)
        autosave_layout.setSpacing(8)
        self.autosave_enabled_check = QCheckBox(_("Automatically save changed files"))
        self.autosave_enabled_check.setChecked(
            self.settings_manager.get_setting('autosave_enabled', False)
        )
        self.autosave_enabled_check.toggled.connect(self._on_autosave_toggled)
        autosave_layout.addWidget(self.autosave_enabled_check)

        autosave_interval_layout = QHBoxLayout()
        autosave_interval_label = QLabel(_("Save changed files every:"))
        self.autosave_interval_combo = QComboBox()
        self.autosave_interval_combo.setEditable(True)
        self.autosave_interval_combo.addItems([str(seconds) for seconds in self.common_autosave_intervals()])
        self.set_autosave_interval(
            self.settings_manager.get_setting('autosave_interval_seconds', 30)
        )
        self.autosave_interval_combo.activated.connect(self._on_autosave_interval_changed)
        if self.autosave_interval_combo.lineEdit() is not None:
            self.autosave_interval_combo.lineEdit().editingFinished.connect(
                self._on_autosave_interval_changed
            )
        self.autosave_interval_unit_label = QLabel(_("Seconds"))
        autosave_interval_layout.addWidget(autosave_interval_label)
        autosave_interval_layout.addWidget(self.autosave_interval_combo)
        autosave_interval_layout.addWidget(self.autosave_interval_unit_label)
        autosave_layout.addLayout(autosave_interval_layout)
        appearance_layout.addWidget(autosave_box)
        appearance_layout.addStretch()
        return appearance_tab

    # Instant-apply handlers (no-ops while the dialog is being built).
    def _on_language_changed(self):
        self._commit(
            "language",
            lambda: self.settings_manager.save_setting(
                "language",
                self.language_combo.currentData() or self.language_combo.currentText(),
            ),
        )

    def _populate_window_color_scheme_combo(self):
        from jottr.window_color_scheme import (
            DEFAULT_WINDOW_COLOR_SCHEME,
            create_preview_icon,
            discover_window_color_schemes,
        )

        combo = self.window_color_scheme_combo
        current = self.settings_manager.get_window_color_scheme()
        combo.blockSignals(True)
        combo.clear()
        for scheme in discover_window_color_schemes():
            label = (
                _("Default")
                if scheme.scheme_id == DEFAULT_WINDOW_COLOR_SCHEME
                else scheme.name
            )
            combo.addItem(create_preview_icon(scheme.path), label, scheme.scheme_id)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def selected_window_color_scheme(self):
        if hasattr(self, "window_color_scheme_combo"):
            data = self.window_color_scheme_combo.currentData()
            if data is not None:
                return data
        return self.settings_manager.get_window_color_scheme()

    def _on_window_color_scheme_changed(self):
        # Kate applies Window Color Scheme immediately (palette swap).
        self._commit_now(
            "style",
            lambda: self.settings_manager.save_window_color_scheme(
                self.selected_window_color_scheme()
            ),
        )
        self.apply_dialog_style()

    def _on_editor_theme_changed(self):
        self._commit(
            "editor_theme",
            lambda: self.settings_manager.save_theme(self.editor_theme_combo.currentText()),
        )

    def _on_qt_style_changed(self):
        # Kate/KStyleManager: write widgetStyle then QApplication.setStyle
        # in the same turn — no QSS/icon/font rebuild on the hot path.
        self._commit_now(
            "widget_style",
            lambda: self.settings_manager.save_qt_style(self.qt_style_combo.currentText()),
        )

    def _on_icon_theme_changed(self):
        self._commit(
            "chrome",
            lambda: self.settings_manager.save_icon_theme(self.selected_icon_theme()),
        )

    def _on_icon_contrast_changed(self):
        self._commit(
            "chrome",
            lambda: self.settings_manager.save_setting(
                "icon_contrast", self.icon_contrast_combo.currentText()
            ),
        )

    def _on_animations_toggled(self, checked):
        self._commit(
            "style",
            lambda: self.settings_manager.save_setting("enable_animations", bool(checked)),
        )

    def _on_autosave_toggled(self, checked):
        self._commit(
            "autosave",
            lambda: self.settings_manager.save_setting("autosave_enabled", bool(checked)),
        )

    def _on_autosave_interval_changed(self):
        self._commit(
            "autosave",
            lambda: self.settings_manager.save_setting(
                "autosave_interval_seconds", self.autosave_interval_seconds()
            ),
        )

    def create_font_button(self, font, callback, follow_system=False):
        button = QPushButton()
        button.setObjectName("fontSettingButton")
        button.clicked.connect(callback)
        self.update_font_button(button, font, follow_system=follow_system)
        return button

    def update_font_button(self, button, font, follow_system=False):
        button.setText(self.font_summary(font, follow_system=follow_system))

    def font_summary(self, font, follow_system=False):
        if follow_system:
            return _("System default")
        parts = [font.family(), f"{font.pointSize()}pt"]
        if font.bold() and font.italic():
            parts.append(_("Bold Italic"))
        elif font.bold():
            parts.append(_("Bold"))
        elif font.italic():
            parts.append(_("Italic"))
        else:
            parts.append(_("Regular"))
        return " ".join(parts)

    def choose_ui_font(self):
        dialog = FontSelectionDialog(
            self.ui_font,
            self,
            title=_("Choose Main UI Font"),
            allow_system_default=True,
            system_default=self.ui_font_follow_system,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            follow_system = dialog.uses_system_default()
            selected_font = dialog.selectedFont()
            self.ui_font_follow_system = follow_system
            self.apply_ui_font(selected_font)
            self.apply_dialog_style()
            self.update_font_button(
                self.ui_font_button,
                selected_font,
                follow_system=follow_system,
            )
            self._commit(
                "style",
                lambda: self.settings_manager.save_font(
                    selected_font, "ui", follow_system=follow_system
                ),
            )

    def common_autosave_intervals(self):
        return [1, 5, 10, 15, 30, 45, 60, 120, 300, 600, 900, 1800, 3600]

    def set_autosave_interval(self, seconds):
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            seconds = 30
        seconds = min(3600, max(1, seconds))
        text = str(seconds)
        index = self.autosave_interval_combo.findText(text)
        if index >= 0:
            self.autosave_interval_combo.setCurrentIndex(index)
        else:
            self.autosave_interval_combo.setCurrentText(text)

    def autosave_interval_seconds(self):
        try:
            seconds = int(self.autosave_interval_combo.currentText())
        except ValueError:
            seconds = 30
        return min(3600, max(1, seconds))

    def load_language_options(self):
        current_language = self.settings_manager.get_setting("language", "en_US")
        languages = get_available_languages()
        if current_language not in languages:
            languages.insert(0, current_language)
        self.language_combo.clear()
        for language in languages:
            self.language_combo.addItem(format_language_label(language), language)
        current_index = self.language_combo.findData(current_language)
        if current_index >= 0:
            self.language_combo.setCurrentIndex(current_index)

    def refresh_editor_theme_combo(self):
        current = self.editor_theme_combo.currentText() if hasattr(self, "editor_theme_combo") else ""
        self.editor_theme_combo.blockSignals(True)
        try:
            self.editor_theme_combo.clear()
            self.editor_theme_combo.addItems(ThemeManager.get_themes(self.get_custom_themes()).keys())
            if current:
                self.editor_theme_combo.setCurrentText(current)
        finally:
            self.editor_theme_combo.blockSignals(False)

    def refresh_theme_combos(self):
        if hasattr(self, "editor_theme_combo"):
            self.refresh_editor_theme_combo()
        self.load_custom_theme_list()

    def load_custom_theme_list(self):
        if not hasattr(self, "custom_theme_list"):
            return
        self.custom_theme_list.clear()
        self.custom_theme_list.addItems(self.get_custom_themes().keys())

    def load_selected_custom_theme(self, current, previous=None):
        if not current:
            return
        name = current.text()
        theme = self.get_custom_themes().get(name)
        if theme:
            export_theme = {key: theme[key] for key in ("app", "editor", "syntax")}
            export_theme["name"] = theme.get("name", name)
            self.theme_json_edit.setPlainText(json.dumps(
                export_theme,
                indent=2
            ))

    def save_custom_theme(self):
        theme = self.read_theme_json()
        name = theme.get("name", "").strip() if theme else ""

        if not name or name in ThemeManager.DEFAULT_THEMES:
            QMessageBox.warning(self, _("Theme"), _("Use a unique custom theme name."))
            return
        if not theme:
            QMessageBox.warning(self, _("Theme"), _("Theme JSON must be valid and include a name."))
            return

        themes = self.get_custom_themes()
        themes[name] = theme
        self.set_custom_themes(themes)
        self.refresh_theme_combos()
        self.editor_theme_combo.setCurrentText(name)
        # Persist custom themes; combo change also saves the active theme name.
        self._commit(
            "editor_theme",
            lambda: self.settings_manager.save_custom_themes(self.get_custom_themes()),
        )

    def delete_custom_theme(self):
        name = self.get_selected_custom_theme_name()
        themes = self.get_custom_themes()
        if name in themes:
            was_selected = self.editor_theme_combo.currentText() == name
            del themes[name]
            self.set_custom_themes(themes)
            self.refresh_theme_combos()
            self.theme_json_edit.clear()
            if was_selected:
                self.editor_theme_combo.setCurrentText("White")
            self._commit(
                "editor_theme",
                lambda: self.settings_manager.save_custom_themes(self.get_custom_themes()),
            )

    def use_selected_custom_theme(self):
        current = self.custom_theme_list.currentItem()
        if current:
            self.editor_theme_combo.setCurrentText(current.text())

    def get_selected_custom_theme_name(self):
        current = self.custom_theme_list.currentItem()
        if current:
            return current.text()
        theme = self.read_theme_json()
        return theme.get("name", "").strip() if theme else ""

    def get_custom_themes(self):
        if hasattr(self, "_custom_themes"):
            return dict(self._custom_themes)
        self._custom_themes = self.settings_manager.get_custom_themes()
        return dict(self._custom_themes)

    def set_custom_themes(self, themes):
        self._custom_themes = ThemeManager.normalize_custom_themes(themes)

    def read_theme_json(self):
        text = self.theme_json_edit.toPlainText().strip()
        if not text:
            return None
        try:
            return ThemeManager.normalize_theme(json.loads(text))
        except json.JSONDecodeError:
            return None

    def format_theme_json(self):
        theme = self.read_theme_json()
        if not theme:
            QMessageBox.warning(self, _("Theme"), _("Theme JSON is not valid."))
            return
        self.theme_json_edit.setPlainText(json.dumps(
            {key: theme[key] for key in ("name", "app", "editor", "syntax")},
            indent=2
        ))
