"""Browser page: homepage and site-specific searches."""
from PyQt6 import sip
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget,
    QListWidgetItem, QWidget, QGroupBox, QFormLayout, QComboBox, QCheckBox,
)

from jottr.editor import web_profile
from jottr.translation_manager import _

from ..search_site import SearchSiteDialog, split_search_site, timeframe_choices
from .appearance import select_combo_data

DEFAULT_HOMEPAGE = "https://www.google.com/"
DEFAULT_SEARCH_SITES = {
    "AP News": "site:apnews.com",
    "Reuters": "site:reuters.com",
    "BBC News": "site:bbc.com/news",
}
_SITE_NAME_ROLE = Qt.ItemDataRole.UserRole
_SITE_QUERY_ROLE = Qt.ItemDataRole.UserRole + 1


class BrowserPageMixin:
    """Builds the Browser page and its helpers. Expects SettingsDialog host."""

    def build_browser_page(self):
        browser_tab = QWidget()
        self.browser_settings_page = browser_tab
        layout = QVBoxLayout(browser_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        general_box = QGroupBox(_("General"))
        general_layout = QFormLayout(general_box)
        general_layout.setContentsMargins(12, 10, 12, 12)
        general_layout.setSpacing(8)
        self.search_open_in_combo = QComboBox()
        self.search_open_in_combo.addItem(_("Built-in browser"), "builtin")
        self.search_open_in_combo.addItem(_("Default browser"), "default")
        self.search_open_in_combo.currentIndexChanged.connect(self._on_search_open_in_changed)
        general_layout.addRow(QLabel(_("Open Searches In:")), self.search_open_in_combo)
        self.homepage_edit = QLineEdit()
        self.homepage_edit.setPlaceholderText(DEFAULT_HOMEPAGE)
        self.homepage_edit.editingFinished.connect(self._on_homepage_edited)
        general_layout.addRow(QLabel(_("Homepage:")), self.homepage_edit)
        layout.addWidget(general_box)

        privacy_box = QGroupBox(_("Privacy"))
        privacy_layout = QVBoxLayout(privacy_box)
        privacy_layout.setContentsMargins(12, 10, 12, 12)
        privacy_layout.setSpacing(8)
        self.browser_remember_data_check = QCheckBox(
            _("Remember cookies and logins between sessions")
        )
        self.browser_remember_data_check.toggled.connect(
            lambda checked: self._commit_now(
                "browser",
                lambda: self.settings_manager.save_setting(
                    web_profile.REMEMBER_DATA_SETTING, bool(checked))
            )
        )
        privacy_layout.addWidget(self.browser_remember_data_check)
        remember_warning = QLabel(
            _("Cookies are stored unencrypted in Jottr's config folder. Anyone "
              "who can read your files can use them to sign in to your accounts.")
        )
        remember_warning.setWordWrap(True)
        privacy_layout.addWidget(remember_warning)
        clear_row = QHBoxLayout()
        clear_button = QPushButton(_("Clear Cookies and Cache"))
        clear_button.clicked.connect(self.clear_browsing_data)
        self.browser_clear_status = QLabel()
        clear_row.addWidget(clear_button)
        clear_row.addWidget(self.browser_clear_status, 1)
        privacy_layout.addLayout(clear_row)
        layout.addWidget(privacy_box)

        search_box = QGroupBox(_("Site-Specific Searches"))
        search_layout = QVBoxLayout(search_box)
        search_layout.setContentsMargins(12, 10, 12, 12)
        search_layout.setSpacing(8)
        search_hint = QLabel(
            _("Each site adds a Google search scoped to that site "
              "to the editor's context menu.")
        )
        search_hint.setWordWrap(True)
        search_layout.addWidget(search_hint)

        self.search_list = QListWidget()
        self.search_list.itemSelectionChanged.connect(self._update_search_site_buttons)
        self.search_list.itemDoubleClicked.connect(lambda _item: self.edit_search_site())
        search_layout.addWidget(self.search_list, 1)

        search_buttons = QHBoxLayout()
        add_search = QPushButton(_("Add"))
        self.edit_search_button = QPushButton(_("Edit"))
        self.delete_search_button = QPushButton(_("Delete"))
        add_search.clicked.connect(self.add_search_site)
        self.edit_search_button.clicked.connect(self.edit_search_site)
        self.delete_search_button.clicked.connect(self.delete_search_site)
        search_buttons.addWidget(add_search)
        search_buttons.addWidget(self.edit_search_button)
        search_buttons.addWidget(self.delete_search_button)
        search_buttons.addStretch()
        search_layout.addLayout(search_buttons)
        layout.addWidget(search_box, 1)

        self.sync_browser_page()
        return browser_tab

    def sync_browser_page(self):
        if not select_combo_data(
            self.search_open_in_combo,
            self.settings_manager.get_setting("search_open_in", "builtin"),
        ):
            self.search_open_in_combo.setCurrentIndex(0)
        self.browser_remember_data_check.setChecked(bool(
            self.settings_manager.get_setting(web_profile.REMEMBER_DATA_SETTING, False)
        ))
        if not self.homepage_edit.hasFocus():
            self.homepage_edit.setText(
                self.settings_manager.get_setting("homepage", DEFAULT_HOMEPAGE)
            )
        self.load_search_sites()

    def _on_search_open_in_changed(self):
        self._save_only(
            lambda: self.settings_manager.save_setting(
                "search_open_in", self.search_open_in_combo.currentData() or "builtin"
            )
        )

    def clear_browsing_data(self):
        self.browser_clear_status.setText(_("Clearing…"))
        web_profile.clear_browsing_data(
            self.settings_manager, self._on_browsing_data_cleared
        )

    def _on_browsing_data_cleared(self):
        # The Settings window may have been closed (and deleted) meanwhile.
        if not sip.isdeleted(self.browser_clear_status):
            self.browser_clear_status.setText(_("Cookies and cache cleared."))

    def _on_homepage_edited(self):
        text = self.homepage_edit.text().strip()
        if text == self.settings_manager.get_setting("homepage", DEFAULT_HOMEPAGE):
            return
        self._save_only(lambda: self.settings_manager.save_setting("homepage", text))

    def _save_search_sites(self):
        self._save_only(
            lambda: self.settings_manager.save_setting(
                "search_sites", self.get_search_sites()
            )
        )

    def load_search_sites(self):
        """Load search sites from settings, keeping the current selection."""
        current = self.search_list.currentItem()
        current_name = current.data(_SITE_NAME_ROLE) if current is not None else None
        sites = self.settings_manager.get_setting("search_sites", DEFAULT_SEARCH_SITES)
        self.search_list.clear()
        if isinstance(sites, dict):
            for name, site in sites.items():
                item = self._set_search_site_item(QListWidgetItem(), name, site)
                self.search_list.addItem(item)
                if name == current_name:
                    self.search_list.setCurrentItem(item)
        self._update_search_site_buttons()

    def _set_search_site_item(self, item, name, site):
        query, timeframe = split_search_site(site)
        text = f"{name} — {query.removeprefix('site:')}"
        if timeframe:
            text += f" ({dict(timeframe_choices())[timeframe]})"
        item.setText(text)
        item.setData(_SITE_NAME_ROLE, name)
        item.setData(_SITE_QUERY_ROLE, site)
        return item

    def get_search_sites(self):
        """Get search sites from the list, in display order."""
        sites = {}
        for index in range(self.search_list.count()):
            item = self.search_list.item(index)
            sites[item.data(_SITE_NAME_ROLE)] = item.data(_SITE_QUERY_ROLE)
        return sites

    def _update_search_site_buttons(self):
        has_selection = self.search_list.currentItem() is not None
        self.edit_search_button.setEnabled(has_selection)
        self.delete_search_button.setEnabled(has_selection)

    def upsert_search_site(self, name, site, row=None):
        """Add or update a site; a name already in the list is replaced."""
        for index in range(self.search_list.count()):
            if index == row:
                continue
            if self.search_list.item(index).data(_SITE_NAME_ROLE) == name:
                if row is None:
                    row = index
                else:
                    self.search_list.takeItem(index)
                    if index < row:
                        row -= 1
                break
        if row is None:
            item = QListWidgetItem()
            self.search_list.addItem(item)
        else:
            item = self.search_list.item(row)
        self._set_search_site_item(item, name, site)
        self.search_list.setCurrentItem(item)
        self._save_search_sites()

    def add_search_site(self):
        dialog = SearchSiteDialog(self)
        if dialog.exec():
            name, site = dialog.get_data()
            self.upsert_search_site(name, site)

    def edit_search_site(self):
        current = self.search_list.currentItem()
        if current is None:
            return
        dialog = SearchSiteDialog(
            self, current.data(_SITE_NAME_ROLE), current.data(_SITE_QUERY_ROLE)
        )
        if dialog.exec():
            name, site = dialog.get_data()
            self.upsert_search_site(name, site, row=self.search_list.row(current))

    def delete_search_site(self):
        row = self.search_list.currentRow()
        if row >= 0:
            self.search_list.takeItem(row)
            self._save_search_sites()
            self._update_search_site_buttons()
