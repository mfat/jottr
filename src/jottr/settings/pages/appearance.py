"""Appearance page: language, UI font, motion, and color/icon themes."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox, QCheckBox,
    QPushButton, QWidget, QDialog,
)

from jottr.font_dialog import FontSelectionDialog
from jottr.icon_manager import list_bundled_icon_themes
from jottr.settings_manager import (
    DEFAULT_INTERFACE_LOOK, INTERFACE_LOOK_NATIVE, INTERFACE_LOOK_ORGANIC, UI_FONT_DEFAULT,
    UI_FONT_SYSTEM,
)
from jottr.theme_manager import ThemeManager
from jottr.translation_manager import _, format_language_label, get_available_languages

from ..widgets import ColorSwatchPicker, SegmentedControl, ThemeSwatchGrid


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
        appearance_layout.setContentsMargins(0, 0, 0, 0)
        appearance_layout.setSpacing(24)

        self.interface_look_control = SegmentedControl()
        self.interface_look_control.addOption(_("Native"), INTERFACE_LOOK_NATIVE)
        self.interface_look_control.addOption(_("Organic"), INTERFACE_LOOK_ORGANIC)
        self.interface_look_control.setToolTip(
            _("Native is a plain, familiar look. "
              "Organic uses Jottr's own rounded, warm look in light and dark.")
        )
        self.interface_look_control.currentDataChanged.connect(
            self._on_interface_look_changed
        )
        appearance_layout.addLayout(self.settings_choice_row(
            _("Interface look"),
            _("Plain and familiar, or Jottr's own rounded look"),
            self.interface_look_control,
        ))

        self.color_scheme_control = SegmentedControl()
        for scheme in ThemeManager.UI_THEME_NAMES:
            self.color_scheme_control.addOption(_(scheme), scheme)
        self.color_scheme_control.setToolTip(
            _("Light or dark menus, toolbars and panels. "
              "System matches the desktop.")
        )
        self.color_scheme_control.currentDataChanged.connect(
            self._on_color_scheme_changed
        )
        appearance_layout.addLayout(self.settings_choice_row(
            _("Color scheme"),
            _("Menus, toolbars and panels"),
            self.color_scheme_control,
        ))

        self.accent_color_control = ColorSwatchPicker()
        self.accent_color_control.addOption(
            _("Default"), ThemeManager.ACCENT_DEFAULT,
            lambda: ThemeManager.accent_swatch_color(
                ThemeManager.ACCENT_DEFAULT, self.accent_swatches_dark()
            ),
        )
        for key, (label, *_ramp) in ThemeManager.ACCENTS.items():
            self.accent_color_control.addOption(
                _(label), key,
                lambda key=key: ThemeManager.accent_swatch_color(key, self.accent_swatches_dark()),
            )
        self.accent_color_control.currentDataChanged.connect(self._on_accent_color_changed)
        appearance_layout.addLayout(self.settings_choice_row(
            _("Accent color"),
            _("Highlights and main buttons"),
            self.accent_color_control,
        ))

        themes = ThemeManager.get_themes()
        # Light pages first, then dark, each in their usual order.
        ordered = sorted(
            themes,
            key=lambda name: QColor(themes[name]["editor"]["background"]).lightnessF() < 0.5,
        )
        self.editor_theme_grid = ThemeSwatchGrid(
            (name, themes[name]["editor"]["background"], themes[name]["editor"]["foreground"])
            for name in ordered
        )
        self.editor_theme_grid.themeChanged.connect(self._on_editor_theme_changed)
        appearance_layout.addLayout(
            self.settings_field(_("Editor theme"), self.editor_theme_grid)
        )

        self.icon_theme_combo = QComboBox()
        for icon_theme in list_bundled_icon_themes():
            self.icon_theme_combo.addItem(icon_theme["label"], icon_theme["id"])
        self.icon_theme_combo.setToolTip(
            _("Lists icon packs bundled with Jottr only. "
              "Desktop/system icon themes are not used.")
        )
        self.icon_theme_combo.currentIndexChanged.connect(self._on_icon_theme_changed)

        self.icon_contrast_combo = QComboBox()
        for label, value in (
            (_("Auto"), "auto"),
            (_("Light"), "light"),
            (_("Dark"), "dark"),
            (_("Accent"), "accent"),
        ):
            self.icon_contrast_combo.addItem(label, value)
        self.icon_contrast_combo.currentIndexChanged.connect(self._on_icon_contrast_changed)

        self.ui_font_button = self.create_font_button(
            self.ui_font,
            self.choose_ui_font,
            ui_font_source=self.ui_font_source,
        )

        self.language_combo = QComboBox()
        self.load_language_options()
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)

        fields = QGridLayout()
        fields.setHorizontalSpacing(14)
        fields.setVerticalSpacing(20)
        fields.setColumnStretch(0, 1)
        fields.setColumnStretch(1, 1)
        fields.addLayout(self.settings_field(_("Icon theme"), self.icon_theme_combo), 0, 0)
        fields.addLayout(
            self.settings_field(_("Icon contrast"), self.icon_contrast_combo), 0, 1
        )
        fields.addLayout(
            self.settings_field(_("User interface font"), self.ui_font_button), 1, 0
        )
        fields.addLayout(self.settings_field(_("Language"), self.language_combo), 1, 1)
        appearance_layout.addLayout(fields)

        self.enable_animations_check = QCheckBox(_("Enable smooth animations"))
        self.enable_animations_check.toggled.connect(self._on_animations_toggled)
        appearance_layout.addWidget(self.enable_animations_check)
        appearance_layout.addStretch()

        self.sync_appearance_page()
        return appearance_tab

    def settings_choice_row(self, title, hint, control):
        """A bold title over a muted hint on the left, its control on the right."""
        row = QHBoxLayout()
        row.setSpacing(16)
        text = QVBoxLayout()
        text.setSpacing(3)
        text.addWidget(self.settings_field_title(title))
        hint_label = QLabel(hint)
        hint_label.setObjectName("settingsFieldHint")
        hint_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        hint_label.setWordWrap(True)
        text.addWidget(hint_label)
        row.addLayout(text, 1)
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        return row

    def settings_field(self, title, control):
        """A bold title above its control."""
        field = QVBoxLayout()
        field.setSpacing(10)
        title_label = self.settings_field_title(title)
        title_label.setBuddy(control)
        field.addWidget(title_label)
        field.addWidget(control)
        return field

    def settings_field_title(self, title):
        label = QLabel(title)
        label.setObjectName("settingsFieldTitle")
        return label

    def sync_appearance_page(self):
        sm = self.settings_manager
        select_combo_data(self.language_combo, sm.get_setting("language", "en_US"))
        self.enable_animations_check.setChecked(
            bool(sm.get_setting("enable_animations", True))
        )
        if not self.interface_look_control.setCurrentData(sm.get_interface_look()):
            self.interface_look_control.setCurrentData(DEFAULT_INTERFACE_LOOK)
        # Blocked like the scheme below: an accent change restyles this window.
        self.accent_color_control.blockSignals(True)
        self.accent_color_control.setCurrentData(sm.get_accent())
        self.accent_color_control.blockSignals(False)
        self.accent_color_control.update()
        # Blocked: a scheme change also restyles this window.
        self.color_scheme_control.blockSignals(True)
        if not self.color_scheme_control.setCurrentData(sm.get_ui_theme()):
            self.color_scheme_control.setCurrentData("System")
        self.color_scheme_control.blockSignals(False)
        if not self.editor_theme_grid.setCurrentTheme(sm.get_theme()):
            self.editor_theme_grid.setCurrentTheme(ThemeManager.DEFAULT_THEME_NAME)
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

    def _on_color_scheme_changed(self):
        if self._loading:
            return
        # Applied immediately, like a palette swap.
        scheme = self.color_scheme_control.currentData()
        self._commit_now(
            "style", lambda: self.settings_manager.save_ui_theme(scheme)
        )
        if self.host is None:
            # With a host, its restyle already refreshes this window.
            self.apply_dialog_style()

    def _on_interface_look_changed(self):
        if self._loading:
            return
        look = self.interface_look_control.currentData()
        self._commit_now(
            "look", lambda: self.settings_manager.save_interface_look(look)
        )
        if self.host is None:
            self.apply_dialog_style()

    def accent_swatches_dark(self):
        """Swatches show each accent as it looks in the current color scheme."""
        return ThemeManager.theme_is_dark(
            ThemeManager.get_ui_theme(self.settings_manager.get_ui_theme())
        )

    def _on_accent_color_changed(self):
        if self._loading:
            return
        accent = self.accent_color_control.currentData()
        self._commit_now("style", lambda: self.settings_manager.save_accent(accent))
        if self.host is None:
            self.apply_dialog_style()

    def _on_editor_theme_changed(self):
        self._commit(
            "editor_theme",
            lambda: self.settings_manager.save_theme(self.editor_theme_grid.currentTheme()),
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

    def create_font_button(self, font, callback, ui_font_source=None):
        button = QPushButton()
        button.setObjectName("fontSettingButton")
        button.clicked.connect(callback)
        self.update_font_button(button, font, ui_font_source=ui_font_source)
        return button

    def update_font_button(self, button, font, ui_font_source=None):
        button.setText(self.font_summary(font, ui_font_source=ui_font_source))

    def font_summary(self, font, ui_font_source=None):
        if ui_font_source == UI_FONT_DEFAULT:
            return _("Default font")
        if ui_font_source == UI_FONT_SYSTEM:
            return _("System font")
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
            ui_font_source=self.ui_font_source,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            source = dialog.selected_source()
            selected_font = dialog.selectedFont()
            self.ui_font_source = source
            self.apply_ui_font(selected_font)
            self.update_font_button(
                self.ui_font_button,
                selected_font,
                ui_font_source=source,
            )
            self._commit(
                "style",
                lambda: self.settings_manager.save_font(selected_font, "ui", source=source),
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
