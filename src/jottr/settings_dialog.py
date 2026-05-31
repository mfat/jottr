from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QLineEdit, QPushButton, QListWidget, QListWidgetItem, QTabWidget,
                            QWidget, QCheckBox, QMessageBox, QInputDialog, QComboBox,
                            QGroupBox, QPlainTextEdit, QScrollArea, QFormLayout,
                            QFileDialog, QFrame, QStackedWidget)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor
import json
import os
from font_dialog import FontSelectionDialog
from plugin_manager import PluginManager, REMOTE_WARNING
from theme_manager import ThemeManager
from translation_manager import (
    _,
    format_language_label,
    get_available_languages,
    is_rtl_language,
    set_language
)

class SettingsDialog(QDialog):
    @staticmethod
    def theme_rgba(color, alpha):
        qcolor = QColor(color)
        if not qcolor.isValid():
            qcolor = QColor(127, 127, 127)
        return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {alpha})"

    def __init__(self, settings_manager, parent=None, embedded=False, apply_callback=None, close_callback=None):
        super().__init__(parent)
        self.embedded = embedded
        self.apply_callback = apply_callback
        self.close_callback = close_callback
        if self.embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
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
        if self.embedded:
            self.setMinimumSize(0, 0)
        else:
            self.setMinimumSize(680, 480)
            self.resize(760, 560)
        self.plugin_manager = PluginManager(self.settings_manager)
        self.plugin_manager.refresh()
        
        self.setup_ui()

    def reject(self):
        if self.embedded:
            return
        super().reject()

    def keyPressEvent(self, event):
        if self.embedded and event.key() == Qt.Key.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    def setup_ui(self):
        """Setup the UI components"""
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)
        
        settings_body = QHBoxLayout()
        settings_body.setSpacing(12)
        self.settings_nav = QListWidget()
        self.settings_nav.setObjectName("settingsNavList")
        self.settings_nav.setFixedWidth(180)
        self.settings_nav.setSpacing(4)
        self.settings_stack = QStackedWidget()
        self.settings_stack.setObjectName("settingsStack")
        self.settings_nav.currentRowChanged.connect(self.settings_stack.setCurrentIndex)
        self.settings_divider = QWidget()
        self.settings_divider.setObjectName("settingsContentDivider")
        self.settings_divider.setFixedWidth(1)
        settings_body.addWidget(self.settings_nav)
        settings_body.addWidget(self.settings_divider)
        settings_body.addWidget(self.settings_stack, 1)
        
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
        self.add_settings_page(_("Appearance"), self.create_scrollable_tab(appearance_tab))
        
        # Browser tab
        browser_tab = QWidget()
        self.browser_settings_page = browser_tab
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
        if self.browser_settings_available():
            self.add_settings_page(_("Browser"), browser_tab)
        self.add_settings_page(_("Dictionary"), dict_tab)
        self.add_settings_page(_("Plugins"), self.create_plugins_tab())
        if self.settings_nav.count():
            self.settings_nav.setCurrentRow(0)
        
        layout.addLayout(settings_body, 1)
        
        buttons = QHBoxLayout()
        buttons.addStretch()
        if self.embedded:
            apply_button = QPushButton(_("Apply"))
            close_button = QPushButton(_("Close"))
            apply_button.clicked.connect(self.apply_embedded_settings)
            close_button.clicked.connect(self.close_embedded_settings)
            buttons.addWidget(apply_button)
            buttons.addWidget(close_button)
        else:
            ok_button = QPushButton(_("OK"))
            cancel_button = QPushButton(_("Cancel"))
            ok_button.clicked.connect(self.accept)
            cancel_button.clicked.connect(self.reject)
            buttons.addWidget(ok_button)
            buttons.addWidget(cancel_button)
        layout.addLayout(buttons)
        self.apply_dialog_style()

    def add_settings_page(self, title, widget):
        self.settings_nav.addItem(title)
        self.settings_stack.addWidget(widget)

    def settings_page_index(self, widget):
        return self.settings_stack.indexOf(widget)

    def remove_settings_page(self, widget):
        index = self.settings_page_index(widget)
        if index < 0:
            return
        item = self.settings_nav.takeItem(index)
        del item
        self.settings_stack.removeWidget(widget)
        if self.settings_nav.count() and self.settings_nav.currentRow() < 0:
            self.settings_nav.setCurrentRow(0)

    def browser_settings_available(self):
        plugin = self.plugin_manager.plugins.get("browser-panel")
        return bool(plugin and plugin.enabled)

    def sync_plugin_dependent_settings_pages(self):
        if not hasattr(self, "browser_settings_page"):
            return
        browser_index = self.settings_page_index(self.browser_settings_page)
        if self.browser_settings_available() and browser_index < 0:
            self.add_settings_page(_("Browser"), self.browser_settings_page)
        elif not self.browser_settings_available() and browser_index >= 0:
            self.remove_settings_page(self.browser_settings_page)

    def apply_embedded_settings(self):
        if callable(self.apply_callback):
            self.apply_callback(self)

    def close_embedded_settings(self):
        if callable(self.close_callback):
            self.close_callback(self)

    def apply_dialog_style(self):
        theme = ThemeManager.get_theme(
            self.ui_theme_combo.currentText() if hasattr(self, "ui_theme_combo") else self.settings_manager.get_ui_theme(),
            self.settings_manager.get_custom_themes()
        )
        app = theme["app"]
        selected_bg = self.theme_rgba(app["accent"], 0.18)
        divider_color = self.theme_rgba(app["border"], 0.75)
        item_divider_color = self.theme_rgba(app["border"], 0.65)
        self.setStyleSheet(ThemeManager.build_dialog_stylesheet(theme, self.ui_font) + f"""
            QListWidget#settingsNavList {{
                border: none;
                padding: 6px;
                background: transparent;
                outline: none;
            }}
            QWidget#settingsContentDivider {{
                background: {divider_color};
                border: none;
                border-radius: 0px;
                min-width: 1px;
                max-width: 1px;
            }}
            QListWidget#settingsNavList::item {{
                padding: 9px 10px;
                border-radius: 0px;
                border-bottom: 1px solid {item_divider_color};
            }}
            QListWidget#settingsNavList::item:selected {{
                background: {selected_bg};
                border-radius: 0px;
                font-weight: 700;
            }}
        """)

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
            'editor_line_numbers': self.editor_line_numbers_check.isChecked(),
            'double_click_empty_tab_bar_new_tab': self.double_click_empty_tab_bar_new_tab_check.isChecked(),
            'double_click_tab_closes_tab': self.double_click_tab_closes_tab_check.isChecked(),
            'autosave_enabled': self.autosave_enabled_check.isChecked(),
            'autosave_interval_seconds': self.autosave_interval_seconds(),
            'plugins_directory': self.plugins_directory_edit.text().strip(),
            'plugin_registry_url': self.plugin_registry_url_edit.text().strip(),
            'plugin_registry_checksum_url': self.plugin_registry_checksum_url_edit.text().strip(),
            'plugin_channels': list(self.plugin_channels),
            'plugin_channel_filter': self.plugin_channel_filter_combo.currentData() or "all",
            'plugin_state': self.plugin_manager.plugin_state()
        }

    def create_plugins_tab(self):
        plugins_tab = QWidget()
        plugins_tab.setObjectName("pluginsSettingsTab")
        layout = QVBoxLayout(plugins_tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        source_box = QGroupBox(_("Plugin Sources"))
        source_layout = QVBoxLayout(source_box)
        source_layout.setContentsMargins(12, 10, 12, 12)
        source_layout.setSpacing(8)
        local_layout = QHBoxLayout()
        local_layout.addWidget(QLabel(_("Local plugins folder:")))
        self.plugins_directory_edit = QLineEdit(
            self.settings_manager.get_setting("plugins_directory", self.plugin_manager.plugins_dir)
        )
        browse_plugins = QPushButton(_("Browse"))
        browse_plugins.clicked.connect(self.browse_plugins_directory)
        local_layout.addWidget(self.plugins_directory_edit, 1)
        local_layout.addWidget(browse_plugins)
        source_layout.addLayout(local_layout)

        self.plugin_channels = self.plugin_manager.plugin_channels()
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel(_("Show channel:")))
        self.plugin_channel_filter_combo = QComboBox()
        self.populate_plugin_channel_filter()
        self.plugin_channel_filter_combo.currentIndexChanged.connect(self.change_plugin_channel_filter)
        filter_layout.addWidget(self.plugin_channel_filter_combo, 1)
        update_registry = QPushButton(_("Update Channel(s)"))
        update_registry.clicked.connect(self.update_plugin_registry)
        self.remove_plugin_channel_button = QPushButton(_("Remove Channel"))
        self.remove_plugin_channel_button.clicked.connect(self.remove_plugin_channel)
        filter_layout.addWidget(update_registry)
        filter_layout.addWidget(self.remove_plugin_channel_button)
        source_layout.addLayout(filter_layout)

        registry_layout = QHBoxLayout()
        registry_layout.addWidget(QLabel(_("Add channel:")))
        self.plugin_channel_name_edit = QLineEdit()
        self.plugin_channel_name_edit.setPlaceholderText(_("Name"))
        self.plugin_registry_url_edit = QLineEdit()
        self.plugin_registry_url_edit.setPlaceholderText(self.plugin_manager.registry_url() or _("Channel URL"))
        self.plugin_registry_checksum_url_edit = QLineEdit()
        self.plugin_registry_checksum_url_edit.setPlaceholderText(
            self.plugin_manager.registry_checksum_url() or _("Checksum URL")
        )
        add_channel = QPushButton(_("Add Channel"))
        add_channel.clicked.connect(self.add_plugin_channel)
        registry_layout.addWidget(self.plugin_channel_name_edit, 1)
        registry_layout.addWidget(self.plugin_registry_url_edit, 2)
        registry_layout.addWidget(self.plugin_registry_checksum_url_edit, 2)
        registry_layout.addWidget(add_channel)
        source_layout.addLayout(registry_layout)
        layout.addWidget(source_box)

        manager_frame = QFrame()
        manager_frame.setObjectName("pluginManagerSurface")
        manager_layout = QHBoxLayout(manager_frame)
        manager_layout.setContentsMargins(0, 0, 0, 0)
        manager_layout.setSpacing(12)

        list_panel = QFrame()
        list_panel.setObjectName("pluginListPanel")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(8)
        list_header = QLabel(_("Plugins"))
        list_header.setObjectName("pluginPanelTitle")
        list_layout.addWidget(list_header)
        self.plugin_list = QListWidget()
        self.plugin_list.setObjectName("pluginCardList")
        self.plugin_list.setSpacing(8)
        self.plugin_list.setUniformItemSizes(False)
        self.plugin_list.currentItemChanged.connect(self.show_plugin_details)
        list_layout.addWidget(self.plugin_list, 1)
        manager_layout.addWidget(list_panel, 2)

        detail_panel = QFrame()
        detail_panel.setObjectName("pluginDetailPanel")
        detail_layout = QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(14, 12, 14, 12)
        detail_layout.setSpacing(10)

        title_row = QHBoxLayout()
        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        self.plugin_detail_title = QLabel(_("Select a plugin"))
        self.plugin_detail_title.setObjectName("pluginDetailTitle")
        self.plugin_detail_subtitle = QLabel("")
        self.plugin_detail_subtitle.setObjectName("pluginDetailSubtitle")
        title_stack.addWidget(self.plugin_detail_title)
        title_stack.addWidget(self.plugin_detail_subtitle)
        self.plugin_status_badge = QLabel("")
        self.plugin_status_badge.setObjectName("pluginStatusBadge")
        self.plugin_status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addLayout(title_stack, 1)
        title_row.addWidget(self.plugin_status_badge)
        detail_layout.addLayout(title_row)

        self.plugin_details = QLabel()
        self.plugin_details.setObjectName("pluginDetailText")
        self.plugin_details.setWordWrap(True)
        self.plugin_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail_layout.addWidget(self.plugin_details)

        version_layout = QHBoxLayout()
        version_label = QLabel(_("Version"))
        version_label.setObjectName("pluginFieldLabel")
        self.plugin_version_combo = QComboBox()
        self.plugin_version_combo.currentTextChanged.connect(self.change_selected_plugin_version)
        version_layout.addWidget(version_label)
        version_layout.addWidget(self.plugin_version_combo, 1)
        detail_layout.addLayout(version_layout)

        self.plugin_permissions_label = QLabel()
        self.plugin_permissions_label.setObjectName("pluginPermissions")
        self.plugin_permissions_label.setWordWrap(True)
        self.plugin_permissions_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        detail_layout.addWidget(self.plugin_permissions_label)
        detail_layout.addStretch()

        plugin_buttons = QHBoxLayout()
        self.toggle_plugin_button = QPushButton(_("Enable"))
        self.update_plugin_button = QPushButton(_("Update"))
        self.remove_plugin_button = QPushButton(_("Remove"))
        self.toggle_plugin_button.clicked.connect(self.toggle_selected_plugin)
        self.update_plugin_button.clicked.connect(self.update_selected_plugin)
        self.remove_plugin_button.clicked.connect(self.remove_selected_plugin)
        plugin_buttons.addWidget(self.toggle_plugin_button)
        plugin_buttons.addWidget(self.update_plugin_button)
        plugin_buttons.addWidget(self.remove_plugin_button)
        detail_layout.addLayout(plugin_buttons)
        manager_layout.addWidget(detail_panel, 3)
        layout.addWidget(manager_frame, 1)

        warning = QLabel(_("Remote plugins require permission review before they can run code."))
        warning.setObjectName("pluginWarningText")
        warning.setWordWrap(True)
        layout.addWidget(warning)
        theme = ThemeManager.get_theme(
            self.ui_theme_combo.currentText() if hasattr(self, "ui_theme_combo") else self.settings_manager.get_ui_theme(),
            self.settings_manager.get_custom_themes()
        )
        app = theme["app"]
        selected_bg = self.theme_rgba(app["accent"], 0.18)
        hover_bg = self.theme_rgba(app["accent"], 0.10)
        badge_bg = self.theme_rgba(app["accent"], 0.16)
        panel_border = self.theme_rgba(app["border"], 0.85)
        card_border = self.theme_rgba(app["border"], 0.78)
        selected_border = self.theme_rgba(app["accent"], 0.95)
        subtle_surface = self.theme_rgba(app["border"], 0.14)
        plugin_text_muted = app["muted"]
        plugins_tab.setStyleSheet(f"""
            QFrame#pluginManagerSurface {{
                background: transparent;
            }}
            QLabel#pluginPanelTitle {{
                font-size: 13px;
                font-weight: 700;
                padding: 0 2px;
            }}
            QListWidget#pluginCardList {{
                border: 1px solid {panel_border};
                border-radius: 0px;
                padding: 8px;
                background: {subtle_surface};
                outline: none;
            }}
            QListWidget#pluginCardList::item {{
                border-radius: 0px;
                margin: 0;
                padding: 0;
            }}
            QListWidget#pluginCardList::item:selected {{
                background: transparent;
            }}
            QFrame#pluginCard {{
                border: 1px solid {card_border};
                border-left: 4px solid transparent;
                border-radius: 0px;
                background: {app['surface']};
            }}
            QFrame#pluginCard:hover {{
                border-color: {selected_border};
                border-left: 4px solid {selected_border};
                background: {hover_bg};
            }}
            QFrame#pluginCard[selected="true"] {{
                border-color: {selected_border};
                border-left: 4px solid {selected_border};
                background: {selected_bg};
            }}
            QLabel#pluginCardTitle {{
                font-weight: 700;
                font-size: 12px;
            }}
            QLabel#pluginCardChannel {{
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 700;
                background: {subtle_surface};
                color: {plugin_text_muted};
                border: 1px solid {card_border};
            }}
            QLabel#pluginCardMeta, QLabel#pluginCardDescription, QLabel#pluginDetailSubtitle,
            QLabel#pluginDetailText, QLabel#pluginPermissions, QLabel#pluginWarningText {{
                color: {plugin_text_muted};
            }}
            QLabel#pluginBadge, QLabel#pluginStatusBadge {{
                border-radius: 0px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: 700;
                background: {badge_bg};
            }}
            QFrame#pluginDetailPanel {{
                border: 1px solid {panel_border};
                border-radius: 0px;
                background: {subtle_surface};
            }}
            QLabel#pluginDetailTitle {{
                font-size: 17px;
                font-weight: 800;
            }}
            QLabel#pluginFieldLabel {{
                font-weight: 700;
            }}
        """)
        self.refresh_plugin_list()
        return plugins_tab

    def populate_plugin_channel_filter(self):
        if not hasattr(self, "plugin_channel_filter_combo"):
            return
        current = self.plugin_manager.plugin_channel_filter()
        self.plugin_channel_filter_combo.blockSignals(True)
        self.plugin_channel_filter_combo.clear()
        self.plugin_channel_filter_combo.addItem(_("All channels"), "all")
        for channel in self.plugin_channels:
            label = channel.get("name", "")
            if channel.get("verified"):
                label = f"{label} ✓"
            self.plugin_channel_filter_combo.addItem(label, channel.get("name", ""))
        index = self.plugin_channel_filter_combo.findData(current)
        self.plugin_channel_filter_combo.setCurrentIndex(index if index >= 0 else 0)
        self.plugin_channel_filter_combo.blockSignals(False)
        self.update_plugin_channel_action_state()

    def selected_plugin_channel(self):
        selected = self.plugin_channel_filter_combo.currentData() if hasattr(self, "plugin_channel_filter_combo") else "all"
        if selected == "all":
            return None
        return next((channel for channel in self.plugin_channels if channel.get("name") == selected), None)

    def update_plugin_channel_action_state(self):
        if not hasattr(self, "remove_plugin_channel_button"):
            return
        channel = self.selected_plugin_channel()
        can_remove = bool(channel and not channel.get("verified"))
        self.remove_plugin_channel_button.setEnabled(can_remove)

    def add_plugin_channel(self):
        url = self.plugin_registry_url_edit.text().strip()
        if not url:
            return
        name = self.plugin_channel_name_edit.text().strip() or url
        channel = self.plugin_manager.normalize_plugin_channel({
            "name": name,
            "url": url,
            "checksumUrl": self.plugin_registry_checksum_url_edit.text().strip(),
            "enabled": True,
        })
        existing = [item for item in self.plugin_channels if item.get("url") != channel["url"]]
        existing.append(channel)
        self.plugin_channels = existing
        self.plugin_manager.save_plugin_channels(self.plugin_channels)
        self.populate_plugin_channel_filter()
        channel_index = self.plugin_channel_filter_combo.findData(channel["name"])
        if channel_index >= 0:
            self.plugin_channel_filter_combo.setCurrentIndex(channel_index)
        self.plugin_manager.refresh()
        self.refresh_plugin_list()

    def remove_plugin_channel(self):
        channel = self.selected_plugin_channel()
        if not channel or channel.get("verified"):
            self.update_plugin_channel_action_state()
            return
        self.plugin_channels = [
            item for item in self.plugin_channels
            if item.get("name") != channel.get("name") or item.get("url") != channel.get("url")
        ]
        self.plugin_manager.save_plugin_channels(self.plugin_channels)
        self.plugin_manager.set_plugin_channel_filter("all")
        self.populate_plugin_channel_filter()
        self.plugin_manager.refresh()
        self.refresh_plugin_list()

    def change_plugin_channel_filter(self):
        if not hasattr(self, "plugin_channel_filter_combo"):
            return
        self.plugin_manager.set_plugin_channel_filter(self.plugin_channel_filter_combo.currentData() or "all")
        self.update_plugin_channel_action_state()
        self.plugin_manager.refresh()
        self.refresh_plugin_list()

    def plugin_source_label(self, plugin):
        if plugin.source == "remote":
            return _("Remote")
        if plugin.source == "registry":
            channel = plugin.channel_name or _("Registry")
            return f"{channel} ✓" if plugin.channel_verified else channel
        return _("Local")

    def plugin_status_label(self, plugin):
        return _("Enabled") if plugin.enabled else _("Disabled")

    def create_plugin_list_card(self, plugin):
        card = QFrame()
        card.setObjectName("pluginCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setProperty("selected", False)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(5)

        top_row = QHBoxLayout()
        title = QLabel(plugin.display_name)
        title.setObjectName("pluginCardTitle")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        channel_label = QLabel(self.plugin_source_label(plugin))
        channel_label.setObjectName("pluginCardChannel")
        channel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        channel_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        badge = QLabel(self.plugin_status_label(plugin))
        badge.setObjectName("pluginBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top_row.addWidget(title, 1)
        top_row.addWidget(channel_label)
        top_row.addWidget(badge)
        card_layout.addLayout(top_row)

        description = QLabel(plugin.description or plugin.name)
        description.setObjectName("pluginCardDescription")
        description.setWordWrap(True)
        description.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(description)

        meta = QLabel(plugin.version)
        meta.setObjectName("pluginCardMeta")
        meta.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        card_layout.addWidget(meta)
        card.mousePressEvent = lambda event, name=plugin.name: self.select_plugin_by_name(name)
        return card

    def browse_plugins_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            _("Choose Plugins Folder"),
            self.plugins_directory_edit.text()
        )
        if directory:
            self.plugins_directory_edit.setText(directory)
            self.plugin_manager.set_plugins_directory(directory)
            self.plugin_manager.refresh()
            self.refresh_plugin_list()

    def update_plugin_registry(self):
        try:
            selected_channel = self.plugin_channel_filter_combo.currentData() or "all"
            self.plugin_manager.save_plugin_channels(self.plugin_channels)
            self.settings_manager.save_setting("plugin_registry_url", self.plugin_registry_url_edit.text().strip())
            self.settings_manager.save_setting("plugin_registry_checksum_url", self.plugin_registry_checksum_url_edit.text().strip())
            self.plugin_manager.update_plugin_registry(channel_name=selected_channel)
            self.plugin_manager.refresh()
            self.refresh_plugin_list()
        except Exception as exc:
            QMessageBox.warning(self, _("Plugins"), _("Could not update plugin index: {error}").format(error=exc))

    def selected_plugin(self):
        current = self.plugin_list.currentItem()
        if not current:
            return None
        return self.plugin_manager.plugins.get(current.data(Qt.ItemDataRole.UserRole))

    def select_plugin_by_name(self, plugin_name):
        for index in range(self.plugin_list.count()):
            item = self.plugin_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == plugin_name:
                self.plugin_list.setCurrentItem(item)
                return

    def update_plugin_card_states(self):
        current_item = self.plugin_list.currentItem()
        for index in range(self.plugin_list.count()):
            item = self.plugin_list.item(index)
            card = self.plugin_list.itemWidget(item)
            if not card:
                continue
            card.setProperty("selected", item is current_item)
            card.style().unpolish(card)
            card.style().polish(card)
            card.update()

    def set_plugin_action_state(self, plugin):
        has_plugin = plugin is not None
        self.toggle_plugin_button.setEnabled(has_plugin)
        self.toggle_plugin_button.setText(_("Disable") if has_plugin and plugin.enabled else _("Enable"))
        self.update_plugin_button.setEnabled(has_plugin)
        self.remove_plugin_button.setEnabled(has_plugin)

    def refresh_plugin_list(self):
        current = self.selected_plugin()
        current_name = current.name if current else None
        self.plugin_list.clear()
        for plugin in self.plugin_manager.plugins.values():
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, plugin.name)
            item.setSizeHint(QSize(240, 92))
            self.plugin_list.addItem(item)
            self.plugin_list.setItemWidget(item, self.create_plugin_list_card(plugin))
            if plugin.name == current_name:
                self.plugin_list.setCurrentItem(item)
        if self.plugin_list.count() and not self.plugin_list.currentItem():
            self.plugin_list.setCurrentRow(0)
        self.show_plugin_details(self.plugin_list.currentItem())

    def show_plugin_details(self, current, previous=None):
        self.update_plugin_card_states()
        plugin = self.selected_plugin()
        if not plugin:
            self.plugin_detail_title.setText(_("Select a plugin"))
            self.plugin_detail_subtitle.clear()
            self.plugin_status_badge.clear()
            self.plugin_details.clear()
            self.plugin_permissions_label.clear()
            self.plugin_version_combo.blockSignals(True)
            self.plugin_version_combo.clear()
            self.plugin_version_combo.setEnabled(False)
            self.plugin_version_combo.blockSignals(False)
            self.set_plugin_action_state(None)
            return

        self.plugin_detail_title.setText(plugin.display_name)
        self.plugin_detail_subtitle.setText(f"{self.plugin_source_label(plugin)} · {plugin.name}")
        self.plugin_status_badge.setText(self.plugin_status_label(plugin))
        self.plugin_version_combo.blockSignals(True)
        self.plugin_version_combo.clear()
        versions = self.plugin_manager.plugin_versions(plugin.name)
        self.plugin_version_combo.addItems(versions)
        selected_version = self.plugin_manager.selected_plugin_version(plugin.name) or plugin.version
        if selected_version and selected_version in versions:
            self.plugin_version_combo.setCurrentText(selected_version)
        self.plugin_version_combo.setEnabled(bool(versions))
        self.plugin_version_combo.blockSignals(False)

        source = plugin.source_url or plugin.path
        details = (
            f"{plugin.description}\n"
            f"{_('Installed')}: {plugin.version}\n"
            f"{_('Source')}: {source}"
        )
        if plugin.error:
            details = f"{details}\n{_('Error')}: {plugin.error}"
        self.plugin_details.setText(details)

        permissions = ", ".join(plugin.permissions) if plugin.permissions else _("None")
        remote_note = f"\n{REMOTE_WARNING}" if plugin.source in {"remote", "registry"} and not plugin.trusted else ""
        self.plugin_permissions_label.setText(f"{_('Permissions')}: {permissions}{remote_note}")
        self.set_plugin_action_state(plugin)

    def enable_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin:
            return
        trusted = plugin.source in {"local", "registry"}
        if plugin.source == "remote":
            permissions = ", ".join(plugin.permissions) if plugin.permissions else _("None")
            reply = QMessageBox.warning(
                self,
                _("Enable Remote Plugin"),
                _("Enable this remote plugin?\n\nPermissions: {permissions}\n\n{warning}").format(
                    permissions=permissions,
                    warning=REMOTE_WARNING
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            trusted = True
        try:
            self.plugin_manager.set_enabled(plugin.name, True, trusted=trusted)
            self.sync_plugin_dependent_settings_pages()
            self.refresh_plugin_list()
        except PermissionError as exc:
            QMessageBox.warning(self, _("Plugins"), str(exc))


    def toggle_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin:
            return
        if plugin.enabled:
            self.disable_selected_plugin()
        else:
            self.enable_selected_plugin()

    def change_selected_plugin_version(self, version):
        plugin = self.selected_plugin()
        if not plugin or not version:
            return
        if self.plugin_manager.set_plugin_version(plugin.name, version):
            try:
                self.plugin_manager.install_plugin_from_registry(plugin.name)
            except Exception as exc:
                QMessageBox.warning(self, _("Plugins"), _("Could not install plugin version: {error}").format(error=exc))
            self.refresh_plugin_list()

    def disable_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin:
            return
        self.plugin_manager.set_enabled(plugin.name, False)
        self.sync_plugin_dependent_settings_pages()
        self.refresh_plugin_list()

    def update_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin:
            return
        try:
            if plugin.source in {"remote", "registry"}:
                self.plugin_manager.update_plugin(plugin.name)
            else:
                self.plugin_manager.refresh()
            self.sync_plugin_dependent_settings_pages()
            self.refresh_plugin_list()
        except Exception as exc:
            QMessageBox.warning(self, _("Plugins"), _("Could not update plugin: {error}").format(error=exc))

    def remove_selected_plugin(self):
        plugin = self.selected_plugin()
        if not plugin:
            return
        reply = QMessageBox.question(
            self,
            _("Remove Plugin"),
            _("Remove {plugin}?").format(plugin=plugin.display_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.plugin_manager.remove_plugin(plugin.name)
            self.sync_plugin_dependent_settings_pages()
            self.refresh_plugin_list()
        except Exception as exc:
            QMessageBox.warning(self, _("Plugins"), _("Could not remove plugin: {error}").format(error=exc))

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
