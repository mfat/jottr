"""Browser page (moved from settings_dialog, plus instant-apply wiring)."""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QWidget,
)

from jottr.translation_manager import _

from ..search_site import SearchSiteDialog


class BrowserPageMixin:
    """Builds the Browser tab and its helpers. Expects SettingsDialog host."""

    def build_browser_page(self):
        browser_tab = QWidget()
        self.browser_settings_page = browser_tab
        browser_layout = QVBoxLayout(browser_tab)
        browser_layout.setSpacing(10)

        # Homepage setting
        homepage_layout = QHBoxLayout()
        homepage_label = QLabel(_("Homepage:"))
        self.homepage_edit = QLineEdit()
        self.homepage_edit.setText(self.settings_manager.get_setting('homepage', 'https://www.apnews.com/'))
        self.homepage_edit.editingFinished.connect(self._on_homepage_edited)
        homepage_layout.addWidget(homepage_label)
        homepage_layout.addWidget(self.homepage_edit)
        browser_layout.addLayout(homepage_layout)

        # Search sites
        search_label = QLabel(_("Site-specific searches:"))
        browser_layout.addWidget(search_label)

        self.search_list = QListWidget()
        self.load_search_sites()
        browser_layout.addWidget(self.search_list)

        # Search site buttons
        search_buttons = QHBoxLayout()
        add_search = QPushButton(_("Add"))
        edit_search = QPushButton(_("Edit"))
        delete_search = QPushButton(_("Delete"))
        add_search.clicked.connect(self.add_search_site)
        edit_search.clicked.connect(self.edit_search_site)
        delete_search.clicked.connect(self.delete_search_site)
        search_buttons.addWidget(add_search)
        search_buttons.addWidget(edit_search)
        search_buttons.addWidget(delete_search)
        browser_layout.addLayout(search_buttons)
        return browser_tab

    def _on_homepage_edited(self):
        self._save_only(
            lambda: self.settings_manager.save_setting(
                'homepage', self.homepage_edit.text()
            )
        )

    def _save_search_sites(self):
        self._save_only(
            lambda: self.settings_manager.save_setting(
                'search_sites', self.get_search_sites()
            )
        )

    def load_search_sites(self):
        """Load search sites from settings"""
        sites = self.settings_manager.get_setting('search_sites', {
            'AP News': 'site:apnews.com',
            'Reuters': 'site:reuters.com',
            'BBC News': 'site:bbc.com/news'
        })
        for name, site in sites.items():
            self.search_list.addItem(f"{name}: {site}")

    def get_search_sites(self):
        """Get search sites from list widget"""
        sites = {}
        for i in range(self.search_list.count()):
            name, site = self.search_list.item(i).text().split(': ', 1)
            sites[name] = site
        return sites

    def add_search_site(self):
        """Add new search site"""
        dialog = SearchSiteDialog(self)
        if dialog.exec():
            name, site = dialog.get_data()
            self.search_list.addItem(f"{name}: {site}")
            self._save_search_sites()

    def edit_search_site(self):
        """Edit selected search site"""
        current = self.search_list.currentItem()
        if current:
            name, site = current.text().split(': ', 1)
            dialog = SearchSiteDialog(self, name, site)
            if dialog.exec():
                new_name, new_site = dialog.get_data()
                current.setText(f"{new_name}: {new_site}")
                self._save_search_sites()

    def delete_search_site(self):
        """Delete selected search site"""
        current = self.search_list.currentRow()
        if current >= 0:
            self.search_list.takeItem(current)
            self._save_search_sites()
