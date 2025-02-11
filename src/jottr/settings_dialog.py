from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QListWidget, QTabWidget,
                            QWidget, QCheckBox, QMessageBox, QInputDialog)
from PyQt5.QtCore import Qt
import json
import os

class SettingsDialog(QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        
        self.setup_ui()

    def setup_ui(self):
        """Setup the UI components"""
        # Create layout
        layout = QVBoxLayout(self)
        
        # Create tab widget
        tabs = QTabWidget()
        
        # Browser tab
        browser_tab = QWidget()
        browser_layout = QVBoxLayout(browser_tab)
        
        # Homepage setting
        homepage_layout = QHBoxLayout()
        homepage_label = QLabel("Homepage:")
        self.homepage_edit = QLineEdit()
        self.homepage_edit.setText(self.settings_manager.get_setting('homepage', 'https://www.apnews.com/'))
        homepage_layout.addWidget(homepage_label)
        homepage_layout.addWidget(self.homepage_edit)
        browser_layout.addLayout(homepage_layout)
        
        # Search sites
        search_label = QLabel("Site-specific searches:")
        browser_layout.addWidget(search_label)
        
        self.search_list = QListWidget()
        self.load_search_sites()
        browser_layout.addWidget(self.search_list)
        
        # Search site buttons
        search_buttons = QHBoxLayout()
        add_search = QPushButton("Add")
        edit_search = QPushButton("Edit")
        delete_search = QPushButton("Delete")
        add_search.clicked.connect(self.add_search_site)
        edit_search.clicked.connect(self.edit_search_site)
        delete_search.clicked.connect(self.delete_search_site)
        search_buttons.addWidget(add_search)
        search_buttons.addWidget(edit_search)
        search_buttons.addWidget(delete_search)
        browser_layout.addLayout(search_buttons)
        
        # Dictionary tab
        dict_tab = QWidget()
        dict_layout = QVBoxLayout(dict_tab)
        
        dict_label = QLabel("User Dictionary:")
        dict_layout.addWidget(dict_label)
        
        self.dict_list = QListWidget()
        self.load_user_dict()
        dict_layout.addWidget(self.dict_list)
        
        # Dictionary buttons
        dict_buttons = QHBoxLayout()
        add_word = QPushButton("Add Word")
        delete_word = QPushButton("Delete Word")
        add_word.clicked.connect(self.add_dict_word)
        delete_word.clicked.connect(self.delete_dict_word)
        dict_buttons.addWidget(add_word)
        dict_buttons.addWidget(delete_word)
        dict_layout.addLayout(dict_buttons)
        
        # Add tabs
        tabs.addTab(browser_tab, "Browser")
        tabs.addTab(dict_tab, "Dictionary")
        
        layout.addWidget(tabs)
        
        # Dialog buttons
        buttons = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def load_search_sites(self):
        """Load search sites from settings"""
        sites = self.settings_manager.get_setting('search_sites', {
            'AP News': 'site:apnews.com',
            'Reuters': 'site:reuters.com',
            'BBC News': 'site:bbc.com/news'
        })
        for name, site in sites.items():
            self.search_list.addItem(f"{name}: {site}")

    def load_user_dict(self):
        """Load user dictionary words"""
        words = self.settings_manager.get_setting('user_dictionary', [])
        self.dict_list.addItems(words)

    def add_search_site(self):
        """Add new search site"""
        dialog = SearchSiteDialog(self)
        if dialog.exec_():
            name, site = dialog.get_data()
            self.search_list.addItem(f"{name}: {site}")

    def edit_search_site(self):
        """Edit selected search site"""
        current = self.search_list.currentItem()
        if current:
            name, site = current.text().split(': ', 1)
            dialog = SearchSiteDialog(self, name, site)
            if dialog.exec_():
                new_name, new_site = dialog.get_data()
                current.setText(f"{new_name}: {new_site}")

    def delete_search_site(self):
        """Delete selected search site"""
        current = self.search_list.currentRow()
        if current >= 0:
            self.search_list.takeItem(current)

    def add_dict_word(self):
        """Add word to user dictionary"""
        word, ok = QInputDialog.getText(self, "Add Word", "Enter word:")
        if ok and word:
            self.dict_list.addItem(word)

    def delete_dict_word(self):
        """Delete word from user dictionary"""
        current = self.dict_list.currentRow()
        if current >= 0:
            self.dict_list.takeItem(current)

    def get_data(self):
        """Get dialog data"""
        return {
            'homepage': self.homepage_edit.text(),
            'search_sites': self.get_search_sites(),
            'user_dictionary': self.get_user_dictionary()
        }

    def get_search_sites(self):
        """Get search sites from list widget"""
        sites = {}
        for i in range(self.search_list.count()):
            name, site = self.search_list.item(i).text().split(': ', 1)
            sites[name] = site
        return sites

    def get_user_dictionary(self):
        """Get words from dictionary list widget"""
        words = []
        for i in range(self.dict_list.count()):
            words.append(self.dict_list.item(i).text())
        return words

class SearchSiteDialog(QDialog):
    def __init__(self, parent=None, name='', site=''):
        super().__init__(parent)
        self.setWindowTitle("Search Site")
        
        # Remove 'site:' prefix if it exists for display
        if site.startswith('site:'):
            site = site[5:]
        
        layout = QVBoxLayout(self)
        
        # Name field
        name_layout = QHBoxLayout()
        name_label = QLabel("Name:")
        self.name_edit = QLineEdit(name)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Site field
        site_layout = QHBoxLayout()
        site_label = QLabel("Website:")
        self.site_edit = QLineEdit(site)
        self.site_edit.setPlaceholderText("example.com")
        site_layout.addWidget(site_label)
        site_layout.addWidget(self.site_edit)
        layout.addLayout(site_layout)
        
        # Add help text
        help_label = QLabel("Enter the website domain without 'http://' or 'www.'")
        help_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(help_label)
        
        # Buttons
        buttons = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
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