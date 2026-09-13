"""Appearance page: language, UI font, motion, and color/icon themes."""
from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QComboBox, QCheckBox, QPushButton, QGroupBox,
    QWidget, QDialog, QFormLayout,
)

from jottr.font_dialog import FontSelectionDialog
from jottr.icon_manager import list_bundled_icon_themes
from jottr.qt_style import available_qt_styles
from jottr.theme_manager import ThemeManager
from jottr.translation_manager import _, format_language_label, get_available_languages


def select_combo_data(combo, value):
    """Select the item whose data equals value; leave the combo alone if absent."""
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)
    return index >= 0


class AppearancePageMixin:
    """Builds the Appearance page and its helpers. Expects SettingsDialog host."""

    def build_appearance_page(self):
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout(appearance_tab)
        appearance_layout.setContentsMargins(12, 12, 12, 12)
        appearance_layout.setSpacing(10)

        general_box = QGroupBox(_("General"))
        general_layout = QFormLayout(general_box)
        general_layout.setContentsMargins(12, 10, 12, 12)
        general_layout.setSpacing(8)

        self.language_combo = QComboBox()
        self.load_language_options()
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        general_layout.addRow(QLabel(_("Language:")), self.language_combo)

        self.ui_font_button = self.create_font_button(
            self.ui_font,
            self.choose_ui_font,
            follow_system=self.ui_font_follow_system,
        )
        general_layout.addRow(QLabel(_("Main UI Font:")), self.ui_font_button)

        self.enable_animations_check = QCheckBox(_("Enable smooth animations"))
        self.enable_animations_check.toggled.connect(self._on_animations_toggled)
        general_layout.addRow(QLabel(_("Motion:")), self.enable_animations_check)
        appearance_layout.addWidget(general_box)

        theme_box = QGroupBox(_("Theme"))
        theme_layout = QFormLayout(theme_box)
        theme_layout.setContentsMargins(12, 10, 12, 12)
        theme_layout.setSpacing(8)

        self.window_color_scheme_combo = QComboBox()
        self._populate_window_color_scheme_combo()
        self.window_color_scheme_combo.setToolTip(
            _("Kate-style window palette from installed KDE .colors schemes. "
              "Default follows the system (Breeze Light/Dark when available).")
        )
        self.window_color_scheme_combo.currentIndexChanged.connect(
            self._on_window_color_scheme_changed
        )
        theme_layout.addRow(QLabel(_("Window Color Scheme:")), self.window_color_scheme_combo)

        self.qt_style_combo = QComboBox()
        self.qt_style_combo.addItems(available_qt_styles())
        self.qt_style_combo.setToolTip(
            _("Lists every Qt widget style available on this system "
              "(Fusion, Windows, Darkly, desktop styles, and plugins). "
              "System keeps the platform default. "
              "Paired light/dark styles follow Window Color Scheme when both "
              "variants are installed.")
        )
        self.qt_style_combo.currentTextChanged.connect(self._on_qt_style_changed)
        theme_layout.addRow(QLabel(_("Widget Style:")), self.qt_style_combo)

        self.editor_theme_combo = QComboBox()
        for name, theme in ThemeManager.get_themes().items():
            self.editor_theme_combo.addItem(
                ThemeManager.build_theme_tile_icon(theme), name
            )
        self.editor_theme_combo.currentTextChanged.connect(self._on_editor_theme_changed)
        theme_layout.addRow(QLabel(_("Editor Theme:")), self.editor_theme_combo)

        self.icon_theme_combo = QComboBox()
        for icon_theme in list_bundled_icon_themes():
            self.icon_theme_combo.addItem(icon_theme["label"], icon_theme["id"])
        self.icon_theme_combo.setToolTip(
            _("Lists icon packs bundled with Jottr only. "
              "Desktop/system icon themes are not used.")
        )
        self.icon_theme_combo.currentIndexChanged.connect(self._on_icon_theme_changed)
        theme_layout.addRow(QLabel(_("Icon Theme:")), self.icon_theme_combo)

        self.icon_contrast_combo = QComboBox()
        for label, value in (
            (_("Auto"), "auto"),
            (_("Light"), "light"),
            (_("Dark"), "dark"),
            (_("Accent"), "accent"),
        ):
            self.icon_contrast_combo.addItem(label, value)
        self.icon_contrast_combo.currentIndexChanged.connect(self._on_icon_contrast_changed)
        theme_layout.addRow(QLabel(_("Icon Contrast:")), self.icon_contrast_combo)
        appearance_layout.addWidget(theme_box)
        appearance_layout.addStretch()

        self.sync_appearance_page()
        return appearance_tab

    def sync_appearance_page(self):
        sm = self.settings_manager
        select_combo_data(self.language_combo, sm.get_setting("language", "en_US"))
        self.enable_animations_check.setChecked(
            bool(sm.get_setting("enable_animations", True))
        )
        # Blocked: a scheme change also restyles this window.
        self.window_color_scheme_combo.blockSignals(True)
        if not select_combo_data(
            self.window_color_scheme_combo, sm.get_window_color_scheme()
        ):
            self.window_color_scheme_combo.setCurrentIndex(0)
        self.window_color_scheme_combo.blockSignals(False)
        self.qt_style_combo.setCurrentText(sm.get_qt_style())
        self.editor_theme_combo.setCurrentText(sm.get_theme())
        if not select_combo_data(self.icon_theme_combo, sm.get_icon_theme()):
            self.icon_theme_combo.setCurrentIndex(0)
        if not select_combo_data(
            self.icon_contrast_combo, sm.get_setting("icon_contrast", "auto")
        ):
            self.icon_contrast_combo.setCurrentIndex(0)

    # Instant-apply handlers (no-ops while the window is being built or synced).
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
        combo.blockSignals(True)
        combo.clear()
        for scheme in discover_window_color_schemes():
            label = (
                _("Default")
                if scheme.scheme_id == DEFAULT_WINDOW_COLOR_SCHEME
                else scheme.name
            )
            combo.addItem(create_preview_icon(scheme.path), label, scheme.scheme_id)
        combo.blockSignals(False)

    def selected_window_color_scheme(self):
        if hasattr(self, "window_color_scheme_combo"):
            data = self.window_color_scheme_combo.currentData()
            if data is not None:
                return data
        return self.settings_manager.get_window_color_scheme()

    def _on_window_color_scheme_changed(self):
        if self._loading:
            return
        # Kate applies Window Color Scheme immediately (palette swap).
        self._commit_now(
            "style",
            lambda: self.settings_manager.save_window_color_scheme(
                self.selected_window_color_scheme()
            ),
        )
        if self.host is None:
            # With a host, its restyle already refreshes this window.
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
        self.refresh_settings_nav_icons()

    def _on_icon_contrast_changed(self):
        self._commit(
            "chrome",
            lambda: self.settings_manager.save_setting(
                "icon_contrast", self.icon_contrast_combo.currentData() or "auto"
            ),
        )
        self.refresh_settings_nav_icons()

    def _on_animations_toggled(self, checked):
        self._commit(
            "style",
            lambda: self.settings_manager.save_setting("enable_animations", bool(checked)),
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

    def load_language_options(self):
        current_language = self.settings_manager.get_setting("language", "en_US")
        languages = get_available_languages()
        if current_language not in languages:
            languages.insert(0, current_language)
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        for language in languages:
            self.language_combo.addItem(format_language_label(language), language)
        self.language_combo.blockSignals(False)
