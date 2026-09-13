"""Settings window shell: nav/stack layout, page registration, instant-apply plumbing.

A single non-modal window owned by the main window. Every control persists
and applies as soon as it changes; Close (or Esc) only dismisses the window.
Page content lives in settings.pages.* mixins.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QWidget, QPushButton, QComboBox, QStackedWidget, QScrollArea,
)
from PyQt6.QtCore import Qt, QByteArray, QEvent, QSize, QTimer
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
from .pages.editor import EditorPageMixin
from .pages.plugins import PluginsTabMixin
from .search_site import SearchSiteDialog

__all__ = ["SettingsDialog", "SearchSiteDialog"]

# Persisted window geometry and last visited page.
WINDOW_STATE_SETTING = "settings_window_state"
_PAGE_KEY_ROLE = Qt.ItemDataRole.UserRole + 1


class SettingsDialog(
    AppearancePageMixin,
    EditorPageMixin,
    BrowserPageMixin,
    DictionaryPageMixin,
    PluginsTabMixin,
    QDialog,
):
    def __init__(self, settings_manager, parent=None):
        super().__init__(parent)
        # Host window for instant-apply (the main window when opened from it).
        self.host = parent if hasattr(parent, "apply_settings_domain") else None
        # While True, widget signals must not persist or notify (setup/sync).
        self._loading = True
        self.setModal(False)
        self.settings_manager = settings_manager
        language = self.settings_manager.get_setting("language", "en_US")
        set_language(language)
        self.ui_font = QFont(self.settings_manager.get_font("ui"))
        self.ui_font_follow_system = self.settings_manager.uses_system_ui_font()
        self.setFont(self.ui_font)
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if is_rtl_language(language)
            else Qt.LayoutDirection.LeftToRight
        )
        self.setWindowTitle(_("Settings"))
        apply_dialog_window_icon(self, "settings", self.settings_manager)
        self.setMinimumSize(640, 460)
        # Share the host's PluginManager so the Plugins page and the running
        # app never disagree; standalone windows get their own.
        host_plugin_manager = getattr(self.host, "plugin_manager", None)
        self.plugin_manager = (
            host_plugin_manager
            if host_plugin_manager is not None
            else PluginManager(self.settings_manager)
        )
        self.plugin_manager.refresh()

        self.setup_ui()
        self.restore_window_state()
        self._loading = False

    # Instant-apply plumbing.
    #
    # Saves run synchronously so SettingsManager is always fresh; host
    # rebuilds (restyle, rehighlight) are debounced per domain so scrolling
    # through a combo coalesces into one apply instead of one per item.
    # Widget style follows Kate/KStyleManager: persist + apply immediately
    # (see _commit_now) — QApplication.setStyle must not wait on the timer.
    _NOTIFY_DELAY_MS = 150

    def _commit(self, domain, save):
        """Persist a control change and notify the host window.

        During setup and sync this is a no-op so populating widgets neither
        writes settings nor triggers host rebuilds.
        """
        if self._loading:
            return
        save()
        self._notify(domain)

    def _commit_now(self, domain, save):
        """Persist and notify the host immediately (no debounce).

        Matches Kate's Application Style path: write config, then apply
        QApplication.setStyle in the same turn.
        """
        if self._loading:
            return
        save()
        self._notify_now(domain)

    def _save_only(self, save):
        """Persist a control change without notifying the host."""
        if self._loading:
            return
        save()

    def _flush_pending_domains(self):
        """Deliver coalesced domain notifications to the host window."""
        pending = getattr(self, "_pending_domains", set())
        self._pending_domains = set()
        if self.host is None:
            return
        for domain in sorted(pending):
            self.host.apply_settings_domain(domain)

    def _notify(self, domain):
        """Notify the host of a change whose save already happened (debounced)."""
        if self._loading or self.host is None:
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

    def _notify_now(self, domain):
        """Notify the host immediately, flushing any pending debounced domains."""
        if self._loading or self.host is None:
            return
        pending = getattr(self, "_pending_domains", None)
        if pending is None:
            pending = self._pending_domains = set()
        pending.add(domain)
        self.flush_pending_changes()

    def flush_pending_changes(self):
        """Apply debounced changes now (a quick change + Close must still land)."""
        timer = getattr(self, "_notify_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        if getattr(self, "_pending_domains", None):
            self._flush_pending_domains()

    # Window lifecycle.

    def done(self, result):
        # Close button, Esc, and the window manager's close all end up here.
        self.flush_pending_changes()
        self.save_window_state()
        super().done(result)

    def changeEvent(self, event):
        super().changeEvent(event)
        if getattr(self, "_loading", True):
            return
        if event.type() == QEvent.Type.StyleChange:
            # QStyleSheetStyle restores the palette this window had when it was
            # first polished on every repolish (widget style swaps, a new app
            # or font stylesheet), so reapply the current one afterwards.
            self.apply_dialog_palette(pin_app_scheme=False)
        elif event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            # Menus, the status bar, and the editor context menu can change
            # settings while this window is open; pick those up on activation.
            self.sync_from_settings()

    def save_window_state(self):
        item = self.settings_nav.currentItem()
        self.settings_manager.save_setting(WINDOW_STATE_SETTING, {
            "geometry": self.saveGeometry().toBase64().data().decode(),
            "page": item.data(_PAGE_KEY_ROLE) if item is not None else "",
        })

    def restore_window_state(self):
        state = self.settings_manager.get_setting(WINDOW_STATE_SETTING, {})
        if not isinstance(state, dict):
            state = {}
        geometry = state.get("geometry")
        restored = False
        if isinstance(geometry, str) and geometry:
            restored = self.restoreGeometry(
                QByteArray.fromBase64(geometry.encode())
            )
        if not restored:
            self.resize(860, 620)
        self.show_settings_page(state.get("page") or "")

    def sync_from_settings(self):
        """Reload control values from SettingsManager without persisting."""
        self._loading = True
        try:
            self.sync_appearance_page()
            self.sync_editor_page()
            self.sync_browser_page()
            self.sync_dictionary_page()
        finally:
            self._loading = False

    # Layout and pages.

    def setup_ui(self):
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

        self.add_settings_page(
            "appearance",
            _("Appearance"),
            self.create_scrollable_tab(self.build_appearance_page()),
            "preferences-desktop-theme-applications",
        )
        self.add_settings_page(
            "editor",
            _("Editor"),
            self.create_scrollable_tab(self.build_editor_page()),
            "document",
        )
        self.build_browser_page()
        self.add_settings_page(
            "browser",
            _("Browser and Search"),
            self.browser_settings_page,
            "browser",
        )
        self.add_settings_page(
            "spellcheck",
            _("Spellcheck"),
            self.create_scrollable_tab(self.build_dictionary_page()),
            "insert-text",
        )
        self.add_settings_page(
            "plugins", _("Plugins"), self.create_plugins_tab(), "applications-system"
        )
        if self.settings_nav.count():
            self.settings_nav.setCurrentRow(0)

        layout.addLayout(settings_body, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        # Settings apply instantly; Close only dismisses the window.
        close_button = QPushButton(_("Close"))
        close_button.clicked.connect(self.reject)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        # Enter in a line edit must not trigger a button and close the window.
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
            button.setDefault(False)
        self.apply_dialog_style()

    def add_settings_page(self, key, title, widget, icon_name=None, index=None):
        item = QListWidgetItem(title)
        item.setData(_PAGE_KEY_ROLE, key)
        if icon_name:
            item.setData(Qt.ItemDataRole.UserRole, icon_name)
            item.setIcon(self.settings_nav_icon(icon_name))
        if index is None or index < 0 or index > self.settings_nav.count():
            index = self.settings_nav.count()
        self.settings_nav.insertItem(index, item)
        self.settings_stack.insertWidget(index, widget)

    def settings_page_key_index(self, key):
        for index in range(self.settings_nav.count()):
            if self.settings_nav.item(index).data(_PAGE_KEY_ROLE) == key:
                return index
        return -1

    def show_settings_page(self, key):
        index = self.settings_page_key_index(key)
        if index >= 0:
            self.settings_nav.setCurrentRow(index)
        return index >= 0

    def selected_ui_theme(self):
        # Window Color Scheme owns chrome colors; ui_theme remains the
        # System/Light/Dark hint used when the scheme is Default.
        return self.settings_manager.get_ui_theme()

    def selected_icon_theme(self):
        if hasattr(self, "icon_theme_combo"):
            return normalize_icon_theme(
                self.icon_theme_combo.currentData()
                or self.settings_manager.get_icon_theme()
            )
        return self.settings_manager.get_icon_theme()

    def apply_dialog_style(self):
        """Refresh palette, font, and icons to match the current appearance."""
        self.apply_dialog_palette()
        self.apply_ui_font()

    def apply_dialog_palette(self, pin_app_scheme=True):
        """Set this window's palette; standalone, also pin app-wide colors.

        *pin_app_scheme* False only repaints: a repolish must not push this
        window's appearance onto the rest of the application.
        """
        # Reapplying can itself repolish (the standalone color scheme pin), and
        # a repolish calls back in through changeEvent.
        if getattr(self, "_applying_palette", False):
            return
        self._applying_palette = True
        try:
            self._apply_dialog_palette(pin_app_scheme)
        finally:
            self._applying_palette = False

    def _apply_dialog_palette(self, pin_app_scheme=True):
        # A top-level window does not inherit the main window's palette, so
        # set it explicitly, the same way the main window does.
        from jottr.qt_style import (
            apply_qt_color_scheme,
            reconcile_chrome_theme_with_color_scheme,
        )
        from jottr.window_color_scheme import (
            activate_window_color_scheme,
            effective_chrome_theme,
            find_window_color_scheme,
            scheme_is_dark,
        )
        from PyQt6.QtWidgets import QApplication

        scheme = self.selected_ui_theme()
        # Saved settings, not the combo: every control saves before it notifies,
        # while a menu change restyles before the combo is synced.
        window_scheme_id = self.settings_manager.get_window_color_scheme()
        window_scheme = find_window_color_scheme(window_scheme_id)
        if window_scheme.path:
            color_scheme_setting = (
                "Dark" if scheme_is_dark(window_scheme.path) else "Light"
            )
            theme = effective_chrome_theme(window_scheme_id, scheme)
        else:
            color_scheme_setting = scheme
            theme = reconcile_chrome_theme_with_color_scheme(
                effective_chrome_theme(window_scheme_id, scheme),
                color_scheme_setting,
            )
        # The host window owns app-wide color scheme state; only apply it
        # here when running standalone.
        if self.host is None and pin_app_scheme:
            apply_qt_color_scheme(color_scheme_setting)
            activate_window_color_scheme(window_scheme_id)
        if not window_scheme.path:
            ThemeManager.apply_app_palette(self, theme)
        else:
            app = QApplication.instance()
            if app is not None:
                self.setPalette(app.palette())
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
            contrast = self.icon_contrast_combo.currentData()
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
        """Snapshot of the values shown in the window."""
        return {
            'homepage': self.homepage_edit.text(),
            'search_open_in': self.search_open_in_combo.currentData(),
            'search_sites': self.get_search_sites(),
            'user_dictionary': self.get_user_dictionary(),
            'spell_check': self.spell_check_enabled.isChecked(),
            'ui_theme': self.selected_ui_theme(),
            'window_color_scheme': self.selected_window_color_scheme(),
            'theme': self.editor_theme_combo.currentText(),
            'qt_style': self.qt_style_combo.currentText(),
            'language': self.language_combo.currentData() or self.language_combo.currentText(),
            'icon_theme': self.selected_icon_theme(),
            'icon_contrast': self.icon_contrast_combo.currentData(),
            'enable_animations': self.enable_animations_check.isChecked(),
            'ui_font': QFont(self.ui_font),
            'markdown_scroll_sync': self.markdown_scroll_sync_check.isChecked(),
            'editor_line_numbers': self.settings_manager.get_setting(
                'editor_line_numbers', True
            ),
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
