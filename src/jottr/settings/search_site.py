"""Search-site editor dialog (moved verbatim from settings_dialog)."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
)

from jottr.icon_manager import apply_dialog_window_icon
from jottr.translation_manager import _


class SearchSiteDialog(QDialog):
    def __init__(self, parent=None, name='', site=''):
        super().__init__(parent)
        self.setWindowTitle(_("Search Site"))
        apply_dialog_window_icon(self, "find")

        # Remove 'site:' prefix if it exists for display
        if site.startswith('site:'):
            site = site[5:]

        layout = QVBoxLayout(self)

        # Name field
        name_layout = QHBoxLayout()
        name_label = QLabel(_("Name:"))
        self.name_edit = QLineEdit(name)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # Site field
        site_layout = QHBoxLayout()
        site_label = QLabel(_("Website:"))
        self.site_edit = QLineEdit(site)
        self.site_edit.setPlaceholderText(_("example.com"))
        site_layout.addWidget(site_label)
        site_layout.addWidget(self.site_edit)
        layout.addLayout(site_layout)

        # Add help text
        help_label = QLabel(_("Enter the website domain without 'http://' or 'www.'"))
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # Buttons
        buttons = QHBoxLayout()
        ok_button = QPushButton(_("OK"))
        cancel_button = QPushButton(_("Cancel"))
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def get_data(self):
        """Get dialog data with 'site:' prefix automatically added"""
        name = self.name_edit.text()
        site = self.site_edit.text().strip()

        # Remove any existing 'site:' prefix
        if site.startswith('site:'):
            site = site[5:]

        # Remove http://, https://, and www. if present
        site = site.replace('http://', '').replace('https://', '').replace('www.', '')

        # Add 'site:' prefix
        site = f'site:{site}'

        return name, site
