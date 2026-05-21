from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QListWidget, QTabWidget,
                            QWidget, QCheckBox, QMessageBox, QInputDialog, QComboBox,
                            QGroupBox, QPlainTextEdit, QScrollArea, QFormLayout)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import json
import os
from font_dialog import FontSelectionDialog
from theme_manager import ThemeManager
from translation_manager import (
    _,
    format_language_label,
    get_available_languages,
    is_rtl_language,
    set_language
)

class SettingsDialog(QDialog):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        language = self.settings_manager.get_setting("language", "en_US")
        set_language(language)
        self.ui_font = QFont(self.settings_manager.get_font("ui"))
        self.setFont(self.ui_font)
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if is_rtl_language(language)
            else Qt.LayoutDirection.LeftToRight
        )
        self.setWindowTitle(_("Settings"))
        self.setMinimumSize(680, 480)
        self.resize(760, 560)
        
        self.setup_ui()

    def setup_ui(self):
        """Setup the UI components"""
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)
        
        # Create tab widget
        tabs = QTabWidget()
        tabs.setDocumentMode(False)
        
        # Appearance tab
        appearance_tab = QWidget()
        appearance_layout = QVBoxLayout(appearance_tab)
        appearance_layout.setContentsMargins(12, 12, 12, 12)
        appearance_layout.setSpacing(10)

        general_box = QGroupBox(_("General"))
        general_layout = QFormLayout(general_box)
        general_layout.setContentsMargins(12, 10, 12, 12)
        general_layout.setSpacing(8)
        language_label = QLabel(_("Language:"))
        self.language_combo = QComboBox()
        self.load_language_options()
        general_layout.addRow(language_label, self.language_combo)
        
        ui_theme_label = QLabel(_("Main UI Theme:"))
        self.ui_theme_combo = QComboBox()
        self.refresh_theme_combo(self.ui_theme_combo)
        self.ui_theme_combo.setCurrentText(self.settings_manager.get_ui_theme())
        general_layout.addRow(ui_theme_label, self.ui_theme_combo)

        editor_theme_label = QLabel(_("Editor Theme:"))
        self.editor_theme_combo = QComboBox()
        self.refresh_theme_combo(self.editor_theme_combo)
        self.editor_theme_combo.setCurrentText(self.settings_manager.get_theme())
        general_layout.addRow(editor_theme_label, self.editor_theme_combo)

        icon_label = QLabel(_("Icon Contrast:"))
        self.icon_contrast_combo = QComboBox()
        self.icon_contrast_combo.addItems(["auto", "light", "dark", "accent"])
        self.icon_contrast_combo.setCurrentText(
            self.settings_manager.get_setting("icon_contrast", "auto")
        )
        general_layout.addRow(icon_label, self.icon_contrast_combo)

        self.enable_animations_check = QCheckBox(_("Enable smooth animations"))
        self.enable_animations_check.setChecked(
            self.settings_manager.get_setting("enable_animations", True)
        )
        general_layout.addRow(QLabel(_("Motion:")), self.enable_animations_check)

        font_label = QLabel(_("Main UI Font:"))
        self.ui_font_button = self.create_font_button(
            self.ui_font,
            self.choose_ui_font
        )
        general_layout.addRow(font_label, self.ui_font_button)
        appearance_layout.addWidget(general_box)

        theme_box = QGroupBox(_("Custom App Themes"))
        theme_box_layout = QVBoxLayout(theme_box)
        standard_label = QLabel(
            _("Themes control app chrome, editor colors, panels, menus, and selection states.")
        )
        standard_label.setStyleSheet("color: gray; font-size: 10px;")
        theme_box_layout.addWidget(standard_label)

        self.custom_theme_list = QListWidget()
        self.custom_theme_list.currentItemChanged.connect(self.load_selected_custom_theme)
        self.custom_theme_list.setMaximumHeight(95)
        theme_box_layout.addWidget(self.custom_theme_list)

        json_label = QLabel(_("Theme JSON:"))
        json_label.setStyleSheet("color: gray; font-size: 10px;")
        theme_box_layout.addWidget(json_label)
        self.theme_json_edit = QPlainTextEdit()
        self.theme_json_edit.setPlaceholderText(json.dumps(ThemeManager.get_theme_standard(), indent=2))
        self.theme_json_edit.setMinimumHeight(130)
        theme_box_layout.addWidget(self.theme_json_edit)

        theme_buttons = QHBoxLayout()
        save_theme = QPushButton(_("Save Theme"))
        delete_theme = QPushButton(_("Delete Theme"))
        use_theme = QPushButton(_("Use Selected"))
        format_json = QPushButton(_("Format JSON"))
        save_theme.clicked.connect(self.save_custom_theme)
        delete_theme.clicked.connect(self.delete_custom_theme)
        use_theme.clicked.connect(self.use_selected_custom_theme)
        format_json.clicked.connect(self.format_theme_json)
        theme_buttons.addWidget(save_theme)
        theme_buttons.addWidget(delete_theme)
        theme_buttons.addWidget(use_theme)
        theme_buttons.addWidget(format_json)
        theme_box_layout.addLayout(theme_buttons)
        appearance_layout.addWidget(theme_box, 1)
        self.load_custom_theme_list()

        editor_box = QGroupBox(_("Editor"))
        editor_layout = QVBoxLayout(editor_box)
        editor_layout.setContentsMargins(12, 10, 12, 12)
        editor_layout.setSpacing(8)
        self.markdown_scroll_sync_check = QCheckBox(_("Sync markdown editor and preview scrolling"))
        self.markdown_scroll_sync_check.setChecked(
            self.settings_manager.get_setting('markdown_scroll_sync', True)
        )
        editor_layout.addWidget(self.markdown_scroll_sync_check)

        mermaid_layout = QHBoxLayout()
        mermaid_label = QLabel(_("Mermaid Runtime:"))
        self.mermaid_runtime_combo = QComboBox()
        self.mermaid_runtime_combo.addItem(_("Bundled (offline, stable)"), "bundled")
        self.mermaid_runtime_combo.addItem(_("Latest from CDN"), "latest")
        current_mermaid_runtime = self.settings_manager.get_setting("mermaid_runtime", "bundled")
        mermaid_index = self.mermaid_runtime_combo.findData(current_mermaid_runtime)
        self.mermaid_runtime_combo.setCurrentIndex(max(0, mermaid_index))
        mermaid_layout.addWidget(mermaid_label)
        mermaid_layout.addWidget(self.mermaid_runtime_combo)
        editor_layout.addLayout(mermaid_layout)

        self.editor_line_numbers_check = QCheckBox(_("Show editor line numbers"))
        self.editor_line_numbers_check.setChecked(
            self.settings_manager.get_setting('editor_line_numbers', True)
        )
        editor_layout.addWidget(self.editor_line_numbers_check)

        self.double_click_empty_tab_bar_new_tab_check = QCheckBox(
            _("Double-click empty tab bar to open a new tab")
        )
        self.double_click_empty_tab_bar_new_tab_check.setChecked(
            self.settings_manager.get_setting("double_click_empty_tab_bar_new_tab", True)
        )
        editor_layout.addWidget(self.double_click_empty_tab_bar_new_tab_check)

        self.double_click_tab_closes_tab_check = QCheckBox(
            _("Double-click existing tab to close it")
        )
        self.double_click_tab_closes_tab_check.setChecked(
            self.settings_manager.get_setting("double_click_tab_closes_tab", True)
        )
        editor_layout.addWidget(self.double_click_tab_closes_tab_check)
        appearance_layout.addWidget(editor_box)

        autosave_box = QGroupBox(_("Autosave"))
        autosave_layout = QVBoxLayout(autosave_box)
        autosave_layout.setContentsMargins(12, 10, 12, 12)
        autosave_layout.setSpacing(8)
        self.autosave_enabled_check = QCheckBox(_("Automatically save changed files"))
        self.autosave_enabled_check.setChecked(
            self.settings_manager.get_setting('autosave_enabled', False)
        )
        autosave_layout.addWidget(self.autosave_enabled_check)

        autosave_interval_layout = QHBoxLayout()
        autosave_interval_label = QLabel(_("Save changed files every:"))
        self.autosave_interval_combo = QComboBox()
        self.autosave_interval_combo.setEditable(True)
        self.autosave_interval_combo.addItems([str(seconds) for seconds in self.common_autosave_intervals()])
        self.set_autosave_interval(
            self.settings_manager.get_setting('autosave_interval_seconds', 30)
        )
        self.autosave_interval_unit_label = QLabel(_("Seconds"))
        autosave_interval_layout.addWidget(autosave_interval_label)
        autosave_interval_layout.addWidget(self.autosave_interval_combo)
        autosave_interval_layout.addWidget(self.autosave_interval_unit_label)
        autosave_layout.addLayout(autosave_interval_layout)
        appearance_layout.addWidget(autosave_box)
        appearance_layout.addStretch()
        
        # Add appearance tab
        tabs.addTab(self.create_scrollable_tab(appearance_tab), _("Appearance"))
        
        # Browser tab
        browser_tab = QWidget()
        browser_layout = QVBoxLayout(browser_tab)
        browser_layout.setSpacing(10)
        
        # Homepage setting
        homepage_layout = QHBoxLayout()
        homepage_label = QLabel(_("Homepage:"))
        self.homepage_edit = QLineEdit()
        self.homepage_edit.setText(self.settings_manager.get_setting('homepage', 'https://www.apnews.com/'))
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
        
        # Dictionary tab
        dict_tab = QWidget()
        dict_layout = QVBoxLayout(dict_tab)
        dict_layout.setSpacing(10)
        
        dict_label = QLabel(_("User Dictionary:"))
        dict_layout.addWidget(dict_label)
        
        self.dict_list = QListWidget()
        self.load_user_dict()
        dict_layout.addWidget(self.dict_list)
        
        # Dictionary buttons
        dict_buttons = QHBoxLayout()
        add_word = QPushButton(_("Add Word"))
        delete_word = QPushButton(_("Delete Word"))
        add_word.clicked.connect(self.add_dict_word)
        delete_word.clicked.connect(self.delete_dict_word)
        dict_buttons.addWidget(add_word)
        dict_buttons.addWidget(delete_word)
        dict_layout.addLayout(dict_buttons)
        
        # Add tabs
        tabs.addTab(browser_tab, _("Browser"))
        tabs.addTab(dict_tab, _("Dictionary"))
        
        layout.addWidget(tabs)
        
        # Dialog buttons
        buttons = QHBoxLayout()
        ok_button = QPushButton(_("OK"))
        cancel_button = QPushButton(_("Cancel"))
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)
        self.apply_dialog_style()

    def apply_dialog_style(self):
        theme = ThemeManager.get_theme(
            self.ui_theme_combo.currentText() if hasattr(self, "ui_theme_combo") else self.settings_manager.get_ui_theme(),
            self.settings_manager.get_custom_themes()
        )
        self.setStyleSheet(ThemeManager.build_dialog_stylesheet(theme, self.ui_font))

    def create_scrollable_tab(self, content):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(content)
        return scroll_area

    def create_font_button(self, font, callback):
        button = QPushButton()
        button.setObjectName("fontSettingButton")
        button.clicked.connect(callback)
        self.update_font_button(button, font)
        return button

    def update_font_button(self, button, font):
        button.setText(self.font_summary(font))

    def font_summary(self, font):
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
        dialog = FontSelectionDialog(self.ui_font, self, title=_("Choose Main UI Font"))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_font = dialog.selectedFont()
            self.ui_font = selected_font
            self.setFont(self.ui_font)
            self.apply_dialog_style()
            self.update_font_button(self.ui_font_button, selected_font)

    def common_autosave_intervals(self):
        return [1, 5, 10, 15, 30, 45, 60, 120, 300, 600, 900, 1800, 3600]

    def set_autosave_interval(self, seconds):
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            seconds = 30
        seconds = min(3600, max(1, seconds))
        text = str(seconds)
        index = self.autosave_interval_combo.findText(text)
        if index >= 0:
            self.autosave_interval_combo.setCurrentIndex(index)
        else:
            self.autosave_interval_combo.setCurrentText(text)

    def autosave_interval_seconds(self):
        try:
            seconds = int(self.autosave_interval_combo.currentText())
        except ValueError:
            seconds = 30
        return min(3600, max(1, seconds))

    def load_language_options(self):
        current_language = self.settings_manager.get_setting("language", "en_US")
        languages = get_available_languages()
        if current_language not in languages:
            languages.insert(0, current_language)
        self.language_combo.clear()
        for language in languages:
            self.language_combo.addItem(format_language_label(language), language)
        current_index = self.language_combo.findData(current_language)
        if current_index >= 0:
            self.language_combo.setCurrentIndex(current_index)

    def refresh_theme_combo(self, combo):
        current = combo.currentText()
        combo.clear()
        combo.addItems(ThemeManager.get_themes(self.get_custom_themes()).keys())
        if current:
            combo.setCurrentText(current)

    def refresh_theme_combos(self):
        if hasattr(self, "ui_theme_combo"):
            self.refresh_theme_combo(self.ui_theme_combo)
        if hasattr(self, "editor_theme_combo"):
            self.refresh_theme_combo(self.editor_theme_combo)
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
            QMessageBox.warning(self, _("Theme"), _("Use a unique custom theme name."))
            return
        if not theme:
            QMessageBox.warning(self, _("Theme"), _("Theme JSON must be valid and include a name."))
            return

        themes = self.get_custom_themes()
        themes[name] = theme
        self.set_custom_themes(themes)
        self.refresh_theme_combos()
        self.editor_theme_combo.setCurrentText(name)

    def delete_custom_theme(self):
        name = self.get_selected_custom_theme_name()
        themes = self.get_custom_themes()
        if name in themes:
            ui_was_selected = self.ui_theme_combo.currentText() == name
            was_selected = self.editor_theme_combo.currentText() == name
            del themes[name]
            self.set_custom_themes(themes)
            self.refresh_theme_combos()
            self.theme_json_edit.clear()
            if ui_was_selected:
                self.ui_theme_combo.setCurrentText("Light")
            if was_selected:
                self.editor_theme_combo.setCurrentText("Light")

    def use_selected_custom_theme(self):
        current = self.custom_theme_list.currentItem()
        if current:
            self.ui_theme_combo.setCurrentText(current.text())
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
            QMessageBox.warning(self, _("Theme"), _("Theme JSON is not valid."))
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
        word, ok = QInputDialog.getText(self, _("Add Word"), _("Enter word:"))
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
            'ui_theme': self.ui_theme_combo.currentText(),
            'theme': self.editor_theme_combo.currentText(),
            'custom_themes': self.get_custom_themes(),
            'language': self.language_combo.currentData() or self.language_combo.currentText(),
            'icon_contrast': self.icon_contrast_combo.currentText(),
            'enable_animations': self.enable_animations_check.isChecked(),
            'ui_font': QFont(self.ui_font),
            'markdown_scroll_sync': self.markdown_scroll_sync_check.isChecked(),
            'mermaid_runtime': self.mermaid_runtime_combo.currentData() or "bundled",
            'editor_line_numbers': self.editor_line_numbers_check.isChecked(),
            'double_click_empty_tab_bar_new_tab': self.double_click_empty_tab_bar_new_tab_check.isChecked(),
            'double_click_tab_closes_tab': self.double_click_tab_closes_tab_check.isChecked(),
            'autosave_enabled': self.autosave_enabled_check.isChecked(),
            'autosave_interval_seconds': self.autosave_interval_seconds()
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
        self.setWindowTitle(_("Search Site"))
        
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
        help_label.setStyleSheet("color: gray; font-size: 10px;")
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
