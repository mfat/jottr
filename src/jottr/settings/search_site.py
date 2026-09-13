"""Search-site editor dialog used by the Browser settings page."""
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)

from jottr.icon_manager import apply_dialog_window_icon
from jottr.translation_manager import _


def normalize_site_domain(site):
    """Reduce user input like 'https://www.example.com/' to 'example.com'."""
    site = (site or "").strip().removeprefix("site:")
    for prefix in ("https://", "http://"):
        site = site.removeprefix(prefix)
    return site.removeprefix("www.").rstrip("/")


class SearchSiteDialog(QDialog):
    def __init__(self, parent=None, name='', site=''):
        super().__init__(parent)
        self.setWindowTitle(_("Search Site"))
        apply_dialog_window_icon(self, "find")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        form.addRow(QLabel(_("Name:")), self.name_edit)
        self.site_edit = QLineEdit(normalize_site_domain(site))
        self.site_edit.setPlaceholderText(_("example.com"))
        form.addRow(QLabel(_("Website:")), self.site_edit)
        layout.addLayout(form)

        help_label = QLabel(_("Enter the website domain without 'http://' or 'www.'"))
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.name_edit.textChanged.connect(self._update_ok_button)
        self.site_edit.textChanged.connect(self._update_ok_button)
        self._update_ok_button()

    def _update_ok_button(self):
        name, site = self.get_data()
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool(name) and site != "site:"
        )

    def get_data(self):
        """Return (name, 'site:<domain>')."""
        return self.name_edit.text().strip(), f"site:{normalize_site_domain(self.site_edit.text())}"
