from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QListWidget, QTabWidget,
                            QWidget, QCheckBox, QMessageBox, QInputDialog, QComboBox,
                            QGroupBox, QPlainTextEdit)
from PyQt6.QtCore import Qt
import json
import os
from theme_manager import ThemeManager

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
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)
        
        # Create tab widget
        tabs = QTabWidget()
        tabs.setDocumentMode(False)
        
        # Appearance tab
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout(appearance_tab)
        appearance_layout.setSpacing(12)
        
        editor_theme_layout = QHBoxLayout()
        editor_theme_label = QLabel("Theme:")
        self.editor_theme_combo = QComboBox()
        self.refresh_editor_theme_combo()
        self.editor_theme_combo.setCurrentText(self.settings_manager.get_theme())
        editor_theme_layout.addWidget(editor_theme_label)
        editor_theme_layout.addWidget(self.editor_theme_combo)
        appearance_layout.addLayout(editor_theme_layout)

        icon_layout = QHBoxLayout()
        icon_label = QLabel("Icon Contrast:")
        self.icon_contrast_combo = QComboBox()
        self.icon_contrast_combo.addItems(["auto", "light", "dark", "accent"])
        self.icon_contrast_combo.setCurrentText(
            self.settings_manager.get_setting("icon_contrast", "auto")
        )
        icon_layout.addWidget(icon_label)
        icon_layout.addWidget(self.icon_contrast_combo)
        appearance_layout.addLayout(icon_layout)

        theme_box = QGroupBox("Custom App Themes")
        theme_box_layout = QVBoxLayout(theme_box)
        standard_label = QLabel(
            "Themes control app chrome, editor colors, panels, menus, and selection states."
        )
        standard_label.setStyleSheet("color: gray; font-size: 10px;")
        theme_box_layout.addWidget(standard_label)

        self.custom_theme_list = QListWidget()
        self.custom_theme_list.currentItemChanged.connect(self.load_selected_custom_theme)
        theme_box_layout.addWidget(self.custom_theme_list)

        json_label = QLabel("Theme JSON:")
        json_label.setStyleSheet("color: gray; font-size: 10px;")
        theme_box_layout.addWidget(json_label)
        self.theme_json_edit = QPlainTextEdit()
        self.theme_json_edit.setPlaceholderText(json.dumps(ThemeManager.get_theme_standard(), indent=2))
        self.theme_json_edit.setMinimumHeight(170)
        theme_box_layout.addWidget(self.theme_json_edit)

        theme_buttons = QHBoxLayout()
        save_theme = QPushButton("Save Theme")
        delete_theme = QPushButton("Delete Theme")
        use_theme = QPushButton("Use Selected")
        format_json = QPushButton("Format JSON")
        save_theme.clicked.connect(self.save_custom_theme)
        delete_theme.clicked.connect(self.delete_custom_theme)
        use_theme.clicked.connect(self.use_selected_custom_theme)
        format_json.clicked.connect(self.format_theme_json)
        theme_buttons.addWidget(save_theme)
        theme_buttons.addWidget(delete_theme)
        theme_buttons.addWidget(use_theme)
        theme_buttons.addWidget(format_json)
        theme_box_layout.addLayout(theme_buttons)
        appearance_layout.addWidget(theme_box)
        self.load_custom_theme_list()

        self.markdown_scroll_sync_check = QCheckBox("Sync markdown editor and preview scrolling")
        self.markdown_scroll_sync_check.setChecked(
            self.settings_manager.get_setting('markdown_scroll_sync', True)
        )
        appearance_layout.addWidget(self.markdown_scroll_sync_check)

        self.editor_line_numbers_check = QCheckBox("Show editor line numbers")
        self.editor_line_numbers_check.setChecked(
            self.settings_manager.get_setting('editor_line_numbers', True)
        )
        appearance_layout.addWidget(self.editor_line_numbers_check)
        appearance_layout.addStretch()
        
        # Add appearance tab
        tabs.addTab(appearance_tab, "Appearance")
        
        # Browser tab
        browser_tab = QWidget()
        browser_layout = QVBoxLayout(browser_tab)
        browser_layout.setSpacing(10)
        
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
        dict_layout.setSpacing(10)
        
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
        self.apply_dialog_style()

    def apply_dialog_style(self):
        theme = ThemeManager.get_theme(
            self.settings_manager.get_theme(),
            self.settings_manager.get_custom_themes()
        )
        self.setStyleSheet(ThemeManager.build_dialog_stylesheet(theme))

    def refresh_editor_theme_combo(self):
        current = self.editor_theme_combo.currentText() if hasattr(self, "editor_theme_combo") else ""
        self.editor_theme_combo.clear()
        self.editor_theme_combo.addItems(ThemeManager.get_themes(self.get_custom_themes()).keys())
        if current:
            self.editor_theme_combo.setCurrentText(current)
        self.load_custom_theme_list()

    def load_custom_theme_list(self):
        if not hasattr(self, "custom_theme_list"):
            return
        self.custom_theme_list.clear()
        self.custom_theme_list.addItems(self.get_custom_themes().keys())

    def load_selected_custom_theme(self, current, previous=None):
        if not current:
            return
        name = current.text()
        theme = self.get_custom_themes().get(name)
        if theme:
            export_theme = {key: theme[key] for key in ("app", "editor", "syntax")}
            export_theme["name"] = theme.get("name", name)
            self.theme_json_edit.setPlainText(json.dumps(
                export_theme,
                indent=2
            ))

    def save_custom_theme(self):
        theme = self.read_theme_json()
        name = theme.get("name", "").strip() if theme else ""

        if not name or name in ThemeManager.DEFAULT_THEMES:
            QMessageBox.warning(self, "Theme", "Use a unique custom theme name.")
            return
        if not theme:
            QMessageBox.warning(self, "Theme", "Theme JSON must be valid and include a name.")
            return

        themes = self.get_custom_themes()
        themes[name] = theme
        self.set_custom_themes(themes)
        self.refresh_editor_theme_combo()
        self.editor_theme_combo.setCurrentText(name)

    def delete_custom_theme(self):
        name = self.get_selected_custom_theme_name()
        themes = self.get_custom_themes()
        if name in themes:
            was_selected = self.editor_theme_combo.currentText() == name
            del themes[name]
            self.set_custom_themes(themes)
            self.refresh_editor_theme_combo()
            self.theme_json_edit.clear()
            if was_selected:
                self.editor_theme_combo.setCurrentText("Light")

    def use_selected_custom_theme(self):
        current = self.custom_theme_list.currentItem()
        if current:
            self.editor_theme_combo.setCurrentText(current.text())

    def get_selected_custom_theme_name(self):
        current = self.custom_theme_list.currentItem()
        if current:
            return current.text()
        theme = self.read_theme_json()
        return theme.get("name", "").strip() if theme else ""

    def get_custom_themes(self):
        if hasattr(self, "_custom_themes"):
            return dict(self._custom_themes)
        self._custom_themes = self.settings_manager.get_custom_themes()
        return dict(self._custom_themes)

    def set_custom_themes(self, themes):
        self._custom_themes = ThemeManager.normalize_custom_themes(themes)

    def read_theme_json(self):
        text = self.theme_json_edit.toPlainText().strip()
        if not text:
            return None
        try:
            return ThemeManager.normalize_theme(json.loads(text))
        except json.JSONDecodeError:
            return None

    def format_theme_json(self):
        theme = self.read_theme_json()
        if not theme:
            QMessageBox.warning(self, "Theme", "Theme JSON is not valid.")
            return
        self.theme_json_edit.setPlainText(json.dumps(
            {key: theme[key] for key in ("name", "app", "editor", "syntax")},
            indent=2
        ))

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
        if dialog.exec():
            name, site = dialog.get_data()
            self.search_list.addItem(f"{name}: {site}")

    def edit_search_site(self):
        """Edit selected search site"""
        current = self.search_list.currentItem()
        if current:
            name, site = current.text().split(': ', 1)
            dialog = SearchSiteDialog(self, name, site)
            if dialog.exec():
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
            'user_dictionary': self.get_user_dictionary(),
            'theme': self.editor_theme_combo.currentText(),
            'custom_themes': self.get_custom_themes(),
            'icon_contrast': self.icon_contrast_combo.currentText(),
            'markdown_scroll_sync': self.markdown_scroll_sync_check.isChecked(),
            'editor_line_numbers': self.editor_line_numbers_check.isChecked()
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
