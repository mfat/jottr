"""Search-site editor dialog used by the Browser settings page."""
from urllib.parse import quote

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)

from jottr.icon_manager import apply_dialog_window_icon
from jottr.translation_manager import _

# Google's tbs=qdr:<code> values.
_TIMEFRAME_CODES = ("h", "d", "w", "m", "y")


def normalize_site_domain(site):
    """Reduce user input like 'https://www.example.com/' to 'example.com'."""
    site = (site or "").strip().removeprefix("site:")
    for prefix in ("https://", "http://"):
        site = site.removeprefix(prefix)
    return site.removeprefix("www.").rstrip("/")


def timeframe_choices():
    """Return (code, label) pairs for the timeframe dropdown; '' means any time."""
    return [
        ("", _("Any time")),
        ("h", _("Past hour")),
        ("d", _("Past 24 hours")),
        ("w", _("Past week")),
        ("m", _("Past month")),
        ("y", _("Past year")),
    ]


def split_search_site(value):
    """Return (query, timeframe) from a stored site: a 'site:...' string or a dict."""
    if isinstance(value, dict):
        timeframe = value.get("timeframe")
        return (
            str(value.get("query") or ""),
            timeframe if timeframe in _TIMEFRAME_CODES else "",
        )
    return str(value or ""), ""


def make_search_site(query, timeframe=""):
    """Build the stored value; sites without a timeframe stay plain strings."""
    if timeframe in _TIMEFRAME_CODES:
        return {"query": query, "timeframe": timeframe}
    return query


def search_site_url(text, site):
    """Google search URL for text scoped to a stored site."""
    query, timeframe = split_search_site(site)
    url = f"https://www.google.com/search?q={quote(text)}+{query}"
    if timeframe:
        url += f"&tbs=qdr:{timeframe}"
    return url


class SearchSiteDialog(QDialog):
    def __init__(self, parent=None, name='', site=''):
        super().__init__(parent)
        self.setWindowTitle(_("Search Site"))
        apply_dialog_window_icon(self, "find")

        query, timeframe = split_search_site(site)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        form.addRow(QLabel(_("Name:")), self.name_edit)
        self.site_edit = QLineEdit(normalize_site_domain(query))
        self.site_edit.setPlaceholderText(_("example.com"))
        form.addRow(QLabel(_("Website:")), self.site_edit)
        self.timeframe_combo = QComboBox()
        for code, label in timeframe_choices():
            self.timeframe_combo.addItem(label, code)
        self.timeframe_combo.setCurrentIndex(max(0, self.timeframe_combo.findData(timeframe)))
        form.addRow(QLabel(_("Timeframe:")), self.timeframe_combo)
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
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
            bool(self.name_edit.text().strip())
            and bool(normalize_site_domain(self.site_edit.text()))
        )

    def get_data(self):
        """Return (name, stored site value): 'site:<domain>', or a dict with a timeframe."""
        query = f"site:{normalize_site_domain(self.site_edit.text())}"
        return (
            self.name_edit.text().strip(),
            make_search_site(query, self.timeframe_combo.currentData()),
        )
