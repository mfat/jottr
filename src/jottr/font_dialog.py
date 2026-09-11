from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)
from PyQt6.QtGui import QFont

from jottr.icon_manager import apply_dialog_window_icon
from jottr.theme_manager import ThemeManager
from jottr.translation_manager import _


class FontSelectionDialog(QDialog):
    """App-owned font picker so all visible strings use Jottr translations."""

    def __init__(self, current_font, parent=None, title=None):
        super().__init__(parent)
        self.setObjectName("fontSelectionDialog")
        self.setWindowTitle(title or _("Choose Editor Font"))
        apply_dialog_window_icon(self, "font")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        self.font_label = QLabel(_("Font:"))
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(current_font)
        form.addRow(self.font_label, self.font_combo)

        self.size_label = QLabel(_("Size:"))
        self.size_combo = QComboBox()
        self.size_combo.setEditable(True)
        self.size_combo.addItems([str(size) for size in self.common_font_sizes()])
        self.set_current_size(current_font.pointSize() if current_font.pointSize() > 0 else 12)
        form.addRow(self.size_label, self.size_combo)

        self.style_label = QLabel(_("Style:"))
        self.style_combo = QComboBox()
        self.style_combo.addItem(_("Regular"), "regular")
        self.style_combo.addItem(_("Bold"), "bold")
        self.style_combo.addItem(_("Italic"), "italic")
        self.style_combo.addItem(_("Bold Italic"), "bold_italic")
        self.style_combo.setCurrentIndex(self.initial_style_index(current_font))
        form.addRow(self.style_label, self.style_combo)

        layout.addLayout(form)

        self.preview_label = QLabel(_("Preview:"))
        layout.addWidget(self.preview_label)
        self.preview_text = QLabel(_("The quick brown fox jumps over the lazy dog."))
        self.preview_text.setObjectName("fontPreview")
        self.preview_text.setMinimumHeight(54)
        self.preview_text.setWordWrap(True)
        layout.addWidget(self.preview_text)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(_("OK"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(_("Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.font_combo.currentFontChanged.connect(self.update_preview)
        self.size_combo.currentTextChanged.connect(self.update_preview)
        self.style_combo.currentIndexChanged.connect(self.update_preview)
        self.apply_style(current_font)
        self.update_preview()

    def common_font_sizes(self):
        return [6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 22, 24, 28, 32, 36, 48, 64, 72, 96]

    def set_current_size(self, size):
        size = min(96, max(6, int(size)))
        text = str(size)
        index = self.size_combo.findText(text)
        if index >= 0:
            self.size_combo.setCurrentIndex(index)
        else:
            self.size_combo.setCurrentText(text)

    def active_theme(self):
        parent = self.parent()
        settings_manager = getattr(parent, "settings_manager", None)
        if settings_manager:
            theme_name = settings_manager.get_ui_theme()
            if hasattr(parent, "selected_ui_theme"):
                theme_name = parent.selected_ui_theme()
            elif hasattr(parent, "ui_theme_combo"):
                theme_name = (
                    parent.ui_theme_combo.currentData()
                    or parent.ui_theme_combo.currentText()
                )
            return ThemeManager.get_ui_theme(theme_name)
        return ThemeManager.get_ui_theme(ThemeManager.DEFAULT_THEME_NAME)

    def apply_style(self, font):
        theme = self.active_theme()
        ThemeManager.apply_app_palette(self, theme)
        self.setStyleSheet(ThemeManager.build_font_dialog_stylesheet(theme, font))
        for combo in (self.font_combo, self.style_combo, self.size_combo):
            combo.setPalette(self.palette())
            if hasattr(combo, "view") and combo.view():
                combo.view().setPalette(self.palette())

    def initial_style_index(self, font):
        if font.bold() and font.italic():
            return 3
        if font.bold():
            return 1
        if font.italic():
            return 2
        return 0

    def selectedFont(self):
        font = QFont(self.font_combo.currentFont())
        try:
            point_size = int(self.size_combo.currentText())
        except ValueError:
            point_size = 12
        font.setPointSize(min(96, max(6, point_size)))
        style = self.style_combo.currentData()
        font.setBold(style in ("bold", "bold_italic"))
        font.setItalic(style in ("italic", "bold_italic"))
        return font

    def update_preview(self, *_args):
        font = self.selectedFont()
        self.preview_text.setFont(font)
        # Stylesheet font on #fontPreview wins over setFont; refresh it so
        # face/size/style changes show up in the preview.
        self.setStyleSheet(
            ThemeManager.build_font_dialog_stylesheet(self.active_theme(), font)
        )
