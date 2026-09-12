"""Settings dialog shell: nav/stack layout, page registration, instant-apply plumbing.

Page content lives in settings.pages.* mixins; plugin behavior is unchanged.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QWidget, QPushButton, QComboBox, QStackedWidget, QScrollArea,
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QFont

from jottr.icon_manager import (
    apply_dialog_window_icon,
    normalize_icon_theme,
    themed_symbolic_icon,
)
from jottr.plugin_manager import PluginManager
from jottr.theme_manager import ThemeManager
from jottr.translation_manager import _, is_rtl_language, set_language

from .pages.appearance import AppearancePageMixin
from .pages.browser import BrowserPageMixin
from .pages.dictionary import DictionaryPageMixin
from .pages.plugins import PluginsTabMixin
from .search_site import SearchSiteDialog

__all__ = ["SettingsDialog", "SearchSiteDialog"]


class SettingsDialog(
    AppearancePageMixin, BrowserPageMixin, DictionaryPageMixin, PluginsTabMixin, QDialog
):
    def __init__(self, settings_manager, parent=None, embedded=False, close_callback=None):
        super().__init__(parent)
        self.embedded = embedded
        self.close_callback = close_callback
        # Host window for instant-apply (set when embedded in the main window).
        self.host = parent if hasattr(parent, "apply_settings_domain") else None
        # While True, widget signals must not persist or notify (initial setup).
        self._loading = True
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
        apply_dialog_window_icon(self, "settings", self.settings_manager)
        if self.embedded:
            self.setMinimumSize(0, 0)
        else:
            self.setMinimumSize(680, 480)
            self.resize(760, 560)
        self.plugin_manager = PluginManager(self.settings_manager)
        self.plugin_manager.refresh()

        self.setup_ui()
        self._loading = False

    # Instant-apply plumbing.
    #
    # Saves run synchronously so SettingsManager is always fresh; host
    # rebuilds (restyle, rehighlight) are debounced per domain so scrolling
    # through a combo coalesces into one apply instead of one per item.
    _NOTIFY_DELAY_MS = 150

    def _commit(self, domain, save):
        """Persist a control change and notify the host window.

        During initial setup this is a no-op so populating widgets neither
        writes settings nor triggers host rebuilds.
        """
        if getattr(self, "_loading", False):
            return
        save()
        self._notify(domain)

    def _flush_pending_domains(self):
        """Deliver coalesced domain notifications to the host window."""
        pending = getattr(self, "_pending_domains", set())
        self._pending_domains = set()
        host = getattr(self, "host", None)
        if host is None:
            return
        for domain in sorted(pending):
            host.apply_settings_domain(domain)

    def _save_only(self, save):
        """Persist a control change without notifying the host."""
        if getattr(self, "_loading", False):
            return
        save()

    def _notify(self, domain):
        """Notify the host of a change whose save already happened (debounced)."""
        if getattr(self, "_loading", False):
            return
        if getattr(self, "host", None) is None:
            return
        pending = getattr(self, "_pending_domains", None)
        if pending is None:
            pending = self._pending_domains = set()
        pending.add(domain)
        timer = getattr(self, "_notify_timer", None)
        if timer is None:
            timer = self._notify_timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._flush_pending_domains)
        if not timer.isActive():
            timer.start(self._NOTIFY_DELAY_MS)

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
        self.settings_nav.setIconSize(QSize(16, 16))
        self.settings_stack = QStackedWidget()
        self.settings_stack.setObjectName("settingsStack")
        self.settings_nav.currentRowChanged.connect(self.settings_stack.setCurrentIndex)
        self.settings_divider = QWidget()
        self.settings_divider.setObjectName("settingsContentDivider")
        self.settings_divider.setFixedWidth(1)
        settings_body.addWidget(self.settings_nav)
        settings_body.addWidget(self.settings_divider)
        settings_body.addWidget(self.settings_stack, 1)

        # Pages (one builder per tab; plugins tab behavior unchanged).
        self.add_settings_page(
            _("Appearance"),
            self.create_scrollable_tab(self.build_appearance_page()),
            "preferences-desktop-theme-applications",
        )
        browser_page = self.build_browser_page()
        if self.browser_settings_available():
            self.add_settings_page(_("Browser"), browser_page, "browser")
        self.add_settings_page(_("Spellcheck"), self.build_dictionary_page(), "insert-text")
        self.add_settings_page(_("Plugins"), self.create_plugins_tab(), "applications-system")
        if self.settings_nav.count():
            self.settings_nav.setCurrentRow(0)

        layout.addLayout(settings_body, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        # Settings apply instantly; Close only dismisses the UI.
        close_button = QPushButton(_("Close"))
        if self.embedded:
            close_button.clicked.connect(self.close_embedded_settings)
        else:
            close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        self.apply_dialog_style()

    def add_settings_page(self, title, widget, icon_name=None):
        item = QListWidgetItem(title)
        if icon_name:
            item.setData(Qt.ItemDataRole.UserRole, icon_name)
            item.setIcon(self.settings_nav_icon(icon_name))
        self.settings_nav.addItem(item)
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
            self.add_settings_page(_("Browser"), self.browser_settings_page, "browser")
        elif not self.browser_settings_available() and browser_index >= 0:
            self.remove_settings_page(self.browser_settings_page)

    def close_embedded_settings(self):
        # Flush any debounced applies so a quick change + Close still lands.
        timer = getattr(self, "_notify_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
            self._flush_pending_domains()
        if callable(self.close_callback):
            self.close_callback(self)

    def selected_ui_theme(self):
        if hasattr(self, "ui_theme_combo"):
            return (
                self.ui_theme_combo.currentData()
                or self.settings_manager.get_ui_theme()
            )
        return self.settings_manager.get_ui_theme()

    def selected_icon_theme(self):
        if hasattr(self, "icon_theme_combo"):
            return normalize_icon_theme(
                self.icon_theme_combo.currentData()
                or self.settings_manager.get_icon_theme()
            )
        return self.settings_manager.get_icon_theme()

    def apply_dialog_style(self):
        # Palette + QStyle for colors; font-only QSS so group titles / labels
        # follow Main UI Font without restyling controls.
        from jottr.qt_style import apply_qt_color_scheme

        scheme = self.selected_ui_theme()
        apply_qt_color_scheme(scheme)
        theme = ThemeManager.get_ui_theme(scheme)
        ThemeManager.apply_app_palette(self, theme)
        self.apply_ui_font()
        apply_dialog_window_icon(self, "settings", self.settings_manager)
        self.refresh_settings_nav_icons()

    def apply_ui_font(self, font=None):
        """Apply Main UI Font to the dialog, sidebar, combos, and popups."""
        ui_font = QFont(font) if font is not None else QFont(self.ui_font)
        self.ui_font = QFont(ui_font)
        self.setFont(ui_font)
        # setFont alone is not enough: Fusion/Breeze paint QGroupBox titles and
        # some form labels from the style, so set a font-only stylesheet too.
        font_style = ThemeManager.build_font_stylesheet(ui_font)
        self.setStyleSheet(
            f"""
            QWidget {{
                {font_style}
            }}
            QGroupBox {{
                {font_style}
            }}
            QGroupBox::title {{
                {font_style}
            }}
            """
        )
        for child in self.findChildren(QWidget):
            child.setFont(ui_font)
        for combo in self.findChildren(QComboBox):
            view = combo.view()
            if view is not None:
                view.setFont(ui_font)

    def settings_nav_icon(self, icon_name):
        """Symbolic nav glyph tinted from the dialog palette (flat Selected mode)."""
        # Prefer Icon Contrast when not auto, so the setting still applies.
        if hasattr(self, "icon_contrast_combo"):
            contrast = self.icon_contrast_combo.currentText()
        else:
            contrast = self.settings_manager.get_setting("icon_contrast", "auto")
        color = None
        if contrast and contrast != "auto":
            # Resolve against Light/Dark UI chrome only.
            theme = ThemeManager.get_ui_theme(self.selected_ui_theme())
            app = theme["app"]
            if contrast == "light":
                color = "#f8f8f2"
            elif contrast == "dark":
                color = "#17202a"
            elif contrast == "accent":
                color = app["accent"]
        return themed_symbolic_icon(
            icon_name,
            self.settings_manager,
            color=color,
            size=16,
            palette=self.palette(),
            theme_id=self.selected_icon_theme(),
        )

    def refresh_settings_nav_icons(self):
        if not hasattr(self, "settings_nav"):
            return
        for index in range(self.settings_nav.count()):
            item = self.settings_nav.item(index)
            icon_name = item.data(Qt.ItemDataRole.UserRole)
            if icon_name:
                item.setIcon(self.settings_nav_icon(icon_name))

    def create_scrollable_tab(self, content):
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(content)
        return scroll_area

    def get_data(self):
        """Get dialog data"""
        return {
            'homepage': self.homepage_edit.text(),
            'search_sites': self.get_search_sites(),
            'user_dictionary': self.get_user_dictionary(),
            'spell_check': self.spell_check_enabled.isChecked(),
            'document_language': self.get_document_language(),
            'spell_languages': self._spell_languages_for_document(),
            'ui_theme': self.selected_ui_theme(),
            'theme': self.editor_theme_combo.currentText(),
            'qt_style': self.qt_style_combo.currentText(),
            'custom_themes': self.get_custom_themes(),
            'language': self.language_combo.currentData() or self.language_combo.currentText(),
            'icon_theme': self.selected_icon_theme(),
            'icon_contrast': self.icon_contrast_combo.currentText(),
            'enable_animations': self.enable_animations_check.isChecked(),
            'ui_font': QFont(self.ui_font),
            'markdown_scroll_sync': self.markdown_scroll_sync_check.isChecked(),
            'editor_line_numbers': self.editor_line_numbers_check.isChecked(),
            'double_click_empty_tab_bar_new_tab': self.double_click_empty_tab_bar_new_tab_check.isChecked(),
            'middle_click_tab_closes_tab': self.middle_click_tab_closes_tab_check.isChecked(),
            'autosave_enabled': self.autosave_enabled_check.isChecked(),
            'autosave_interval_seconds': self.autosave_interval_seconds(),
            'plugins_directory': self.plugins_directory_edit.text().strip(),
            'plugin_registry_url': self.plugin_registry_url_edit.text().strip(),
            'plugin_registry_checksum_url': self.plugin_registry_checksum_url_edit.text().strip(),
            'plugin_channels': list(self.plugin_channels),
            'plugin_channel_filter': self.plugin_channel_filter_combo.currentData() or "all",
            'plugin_state': self.plugin_manager.plugin_state()
        }
