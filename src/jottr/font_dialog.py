from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)
from PyQt6.QtGui import QColor, QFont, QPalette

from theme_manager import ThemeManager
from translation_manager import _


class FontSelectionDialog(QDialog):
    """App-owned font picker so all visible strings use Jottr translations."""

    def __init__(self, current_font, parent=None, title=None):
        super().__init__(parent)
        self.setObjectName("fontSelectionDialog")
        self.setWindowTitle(title or _("Choose Editor Font"))
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
            if hasattr(parent, "ui_theme_combo"):
                theme_name = parent.ui_theme_combo.currentText()
            return ThemeManager.get_theme(
                theme_name,
                settings_manager.get_custom_themes()
            )
        return ThemeManager.get_theme(ThemeManager.DEFAULT_THEME_NAME)

    def apply_style(self, font):
        theme = self.active_theme()
        self.setStyleSheet(ThemeManager.build_font_dialog_stylesheet(theme, font))
        app = theme["app"]
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(app["background"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(app["text"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(app["surface"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(app["text"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(app["surface"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(app["text"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(app["surface_active"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(app["text"]))
        self.setPalette(palette)
        for combo in (self.font_combo, self.style_combo):
            combo.setPalette(palette)
            if combo.view():
                combo.view().setPalette(palette)
        self.size_combo.setPalette(palette)
        if self.size_combo.view():
            self.size_combo.view().setPalette(palette)

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
        self.preview_text.setFont(self.selectedFont())
