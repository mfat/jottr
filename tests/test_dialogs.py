import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QGroupBox, QLabel, QMessageBox, QScrollArea, QWidget

from jottr.settings_dialog import SearchSiteDialog, SettingsDialog
from jottr.settings.search_site import search_site_url
from jottr.plugin_manager import PluginManager
from jottr.settings_manager import SettingsManager
from jottr.snippet_editor_dialog import SnippetEditorDialog
from jottr.theme_manager import ThemeManager
import jottr.translation_manager as translation_manager


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


def seed_official_plugin_registry(manager):
    registry = {
        "schemaVersion": 1,
        "plugins": [
            {
                "id": "rss-feed",
                "displayName": "RSS Feed Reader",
                "description": "Adds the RSS feed reader tab.",
                "latestVersion": "0.3.1",
                "defaultEnabled": True,
                "versions": [
                    {"version": "0.3.1", "package": {"downloadUrl": "https://example.test/rss-0.3.1.zip", "sha256": "abc"}},
                    {"version": "0.1.0", "package": {"downloadUrl": "https://example.test/rss-0.1.0.zip", "sha256": "abc"}},
                ],
            },
        ],
    }
    channel = manager.official_plugin_channel()
    registry_path = manager.cached_registry_file(channel)
    checksum_path = manager.cached_registry_checksum_file(channel)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    checksum_path.write_text(f"{manager.sha256_file(registry_path)}  plugins.json\n", encoding="utf-8")


class DialogTests(unittest.TestCase):
    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        seed_official_plugin_registry(PluginManager(SettingsManager()))

    def test_search_site_dialog_normalizes_site_queries(self):
        dialog = SearchSiteDialog(name="Example", site="https://www.example.com/")

        self.assertEqual(dialog.get_data(), ("Example", "site:example.com"))
        ok_button = dialog.button_box.button(dialog.button_box.StandardButton.Ok)
        self.assertTrue(ok_button.isEnabled())
        dialog.site_edit.clear()
        self.assertFalse(ok_button.isEnabled())

    def test_search_site_dialog_sets_optional_timeframe(self):
        weekly = {"query": "site:news.example", "timeframe": "w"}
        dialog = SearchSiteDialog(name="News", site=weekly)

        self.assertEqual(dialog.timeframe_combo.currentData(), "w")
        self.assertEqual(dialog.get_data(), ("News", weekly))
        dialog.timeframe_combo.setCurrentIndex(0)
        self.assertEqual(dialog.get_data(), ("News", "site:news.example"))

        self.assertEqual(
            search_site_url("red herring", {"query": "site:news.example", "timeframe": "d"}),
            "https://www.google.com/search?q=red%20herring+site:news.example&tbs=qdr:d",
        )
        self.assertEqual(
            search_site_url("x", "site:news.example"),
            "https://www.google.com/search?q=x+site:news.example",
        )

    def test_settings_dialog_round_trips_settings(self):
        manager = SettingsManager()
        manager.save_setting("search_sites", {"News": "site:news.example"})
        manager.save_setting("user_dictionary", ["jottr"])
        manager.save_setting("autosave_enabled", True)
        manager.save_setting("autosave_interval_seconds", 12)
        manager.save_setting("plugin_registry_url", "https://example.test/plugins.json")
        manager.save_setting("plugin_registry_checksum_url", "https://example.test/plugins.json.sha256")
        manager.save_theme("Dracula")
        manager.save_ui_theme("Dark")

        dialog = SettingsDialog(manager)
        self.assertFalse(dialog.windowIcon().isNull())
        for index in range(dialog.settings_nav.count()):
            self.assertFalse(
                dialog.settings_nav.item(index).icon().isNull(),
                msg=f"missing icon for {dialog.settings_nav.item(index).text()}",
            )
        self.assertEqual(dialog.editor_theme_combo.currentText(), "Dracula")
        dialog.homepage_edit.setText("https://home.example")
        self.assertEqual(dialog.search_open_in_combo.currentData(), "builtin")
        dialog.search_open_in_combo.setCurrentIndex(
            dialog.search_open_in_combo.findData("default")
        )
        dialog.editor_theme_combo.setCurrentText("Monokai")
        self.assertGreaterEqual(dialog.window_color_scheme_combo.count(), 1)
        self.assertEqual(dialog.window_color_scheme_combo.itemData(0), "")
        self.assertEqual(dialog.selected_ui_theme(), "Dark")
        self.assertIn("Dracula", [
            dialog.editor_theme_combo.itemText(i)
            for i in range(dialog.editor_theme_combo.count())
        ])
        fusion = next(
            (name for name in (
                dialog.qt_style_combo.itemText(i)
                for i in range(dialog.qt_style_combo.count())
            ) if name.casefold() == "fusion"),
            None,
        )
        self.assertIsNotNone(fusion)
        from PyQt6.QtWidgets import QStyleFactory

        combo_styles = {
            dialog.qt_style_combo.itemText(i)
            for i in range(dialog.qt_style_combo.count())
        }
        self.assertIn("System", combo_styles)
        for key in QStyleFactory.keys():
            self.assertTrue(
                any(name.casefold() == key.casefold() for name in combo_styles),
                msg=f"settings combo missing style {key!r}",
            )
        dialog.qt_style_combo.setCurrentText(fusion)
        self.assertEqual(
            [
                dialog.icon_theme_combo.itemData(i)
                for i in range(dialog.icon_theme_combo.count())
            ],
            ["bootstrap", "material", "qlementine", "symbolic"],
        )
        self.assertEqual(dialog.icon_theme_combo.currentData(), "bootstrap")
        dialog.icon_theme_combo.setCurrentIndex(
            dialog.icon_theme_combo.findData("bootstrap")
        )
        dialog.icon_contrast_combo.setCurrentIndex(
            dialog.icon_contrast_combo.findData("light")
        )
        dialog.markdown_scroll_sync_check.setChecked(False)
        dialog.settings_manager.save_setting("editor_line_numbers", False)
        dialog.double_click_empty_tab_bar_new_tab_check.setChecked(False)
        dialog.middle_click_tab_closes_tab_check.setChecked(False)
        dialog.enable_animations_check.setChecked(False)
        dialog.autosave_enabled_check.setChecked(True)
        dialog.autosave_interval_spin.setValue(15)
        dialog.plugins_directory_edit.setText(str(Path(self.temp_dir.name) / "plugins"))
        dialog.spell_check_enabled.setChecked(False)

        nav_labels = [
            dialog.settings_nav.item(index).text()
            for index in range(dialog.settings_nav.count())
        ]
        self.assertIn("Spellcheck", nav_labels)
        self.assertGreater(dialog.detected_dictionaries_list.count(), 0)

        data = dialog.get_data()

        self.assertEqual(data["homepage"], "https://home.example")
        self.assertEqual(data["search_open_in"], "default")
        self.assertEqual(manager.get_setting("search_open_in"), "default")
        self.assertEqual(data["language"], "en_US")
        self.assertGreaterEqual(dialog.language_combo.count(), 1)
        self.assertEqual(data["search_sites"], {"News": "site:news.example"})
        self.assertEqual(data["user_dictionary"], ["jottr"])
        self.assertFalse(data["spell_check"])
        self.assertNotIn("document_language", data)
        self.assertNotIn("spell_languages", data)
        self.assertFalse(hasattr(dialog, "document_language_combo"))
        self.assertEqual(data["ui_theme"], "Dark")
        self.assertEqual(data["window_color_scheme"], "")
        self.assertEqual(data["theme"], "Monokai")
        self.assertEqual(manager.get_theme(), "Monokai")
        self.assertEqual(data["qt_style"], fusion)
        self.assertEqual(data["icon_theme"], "bootstrap")
        self.assertEqual(data["icon_contrast"], "light")
        self.assertFalse(data["enable_animations"])
        self.assertEqual(data["ui_font"].family(), manager.get_font("ui").family())
        self.assertNotIn("editor_font", data)
        self.assertNotIn("preview_font", data)
        self.assertTrue(dialog.findChildren(QScrollArea))
        # Settings nav icons are flat symbolic glyphs with an explicit Selected mode.
        from PyQt6.QtGui import QIcon

        appearance = dialog.settings_nav.item(0)
        self.assertFalse(appearance.icon().isNull())
        normal = appearance.icon().pixmap(16, QIcon.Mode.Normal)
        selected = appearance.icon().pixmap(16, QIcon.Mode.Selected)
        self.assertFalse(normal.isNull())
        self.assertFalse(selected.isNull())
        normal_image = normal.toImage()
        selected_image = selected.toImage()
        sample = None
        for y in range(normal_image.height()):
            for x in range(normal_image.width()):
                if normal_image.pixelColor(x, y).alpha() > 200:
                    sample = (x, y)
                    break
            if sample is not None:
                break
        self.assertIsNotNone(sample)
        self.assertNotEqual(
            normal_image.pixelColor(*sample).name(),
            selected_image.pixelColor(*sample).name(),
        )
        self.assertFalse(data["markdown_scroll_sync"])
        self.assertFalse(data["editor_line_numbers"])
        self.assertFalse(data["double_click_empty_tab_bar_new_tab"])
        self.assertFalse(data["middle_click_tab_closes_tab"])
        self.assertTrue(data["autosave_enabled"])
        self.assertEqual(data["autosave_interval_seconds"], 15)
        self.assertEqual(data["plugins_directory"], str(Path(self.temp_dir.name) / "plugins"))
        self.assertEqual(data["plugin_registry_url"], "")
        self.assertEqual(data["plugin_registry_checksum_url"], "")
        self.assertIn("https://raw.githubusercontent.com/Jottrhq/plugins/main/plugins.json", dialog.plugin_registry_url_edit.placeholderText())
        self.assertIn("https://raw.githubusercontent.com/Jottrhq/plugins/main/plugins.json.sha256", dialog.plugin_registry_checksum_url_edit.placeholderText())
        self.assertEqual(data["plugin_channel_filter"], "all")
        self.assertTrue(any(channel["name"] == "Official" and channel["verified"] for channel in data["plugin_channels"]))
        self.assertEqual(data["plugin_state"], {})
        plugin_tab = dialog.findChild(QWidget, "pluginsSettingsTab")
        self.assertIsNotNone(plugin_tab)
        self.assertEqual(plugin_tab.styleSheet(), "")
        # Dialog may carry font-only QSS for Main UI Font; no color chrome.
        self.assertNotIn("background", dialog.styleSheet())
        self.assertNotIn("color:", dialog.styleSheet())
        self.assertGreater(dialog.plugin_list.count(), 0)
        current_card = dialog.plugin_list.itemWidget(dialog.plugin_list.currentItem())
        self.assertEqual(current_card.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertTrue(current_card.property("selected"))
        channel_label = current_card.findChild(QLabel, "pluginCardChannel")
        self.assertIsNotNone(channel_label)
        self.assertIn("Official", channel_label.text())
        self.assertIn("✓", channel_label.text())


    def test_settings_can_add_and_filter_plugin_channel(self):
        manager = SettingsManager()
        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)

        dialog.plugin_channel_name_edit.setText("Community")
        dialog.plugin_registry_url_edit.setText("https://example.test/community/plugins.json")
        dialog.plugin_registry_checksum_url_edit.setText("https://example.test/community/plugins.json.sha256")
        dialog.add_plugin_channel()

        self.assertGreaterEqual(dialog.plugin_channel_filter_combo.findData("Community"), 0)
        self.assertEqual(dialog.plugin_channel_filter_combo.currentData(), "Community")
        listed = lambda: [
            dialog.plugin_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(dialog.plugin_list.count())
        ]
        # Filtering hides other channels in the list without dropping them.
        self.assertNotIn("rss-feed", listed())
        self.assertIn("rss-feed", dialog.plugin_manager.plugins)
        data = dialog.get_data()
        self.assertEqual(data["plugin_channel_filter"], "Community")
        self.assertTrue(any(channel["name"] == "Community" for channel in data["plugin_channels"]))
        official_label = dialog.plugin_channel_filter_combo.itemText(dialog.plugin_channel_filter_combo.findData("Official"))
        self.assertIn("✓", official_label)
        self.assertTrue(dialog.remove_plugin_channel_button.isEnabled())

        dialog.remove_plugin_channel()
        self.assertEqual(dialog.plugin_channel_filter_combo.currentData(), "all")
        self.assertIn("rss-feed", listed())
        self.assertEqual(dialog.plugin_channel_filter_combo.findData("Community"), -1)
        self.assertFalse(any(channel["name"] == "Community" for channel in dialog.get_data()["plugin_channels"]))

        official_index = dialog.plugin_channel_filter_combo.findData("Official")
        dialog.plugin_channel_filter_combo.setCurrentIndex(official_index)
        self.assertFalse(dialog.remove_plugin_channel_button.isEnabled())
        dialog.remove_plugin_channel()
        self.assertGreaterEqual(dialog.plugin_channel_filter_combo.findData("Official"), 0)

    def wait_for_plugin_task(self, dialog, timeout=10.0):
        deadline = time.monotonic() + timeout
        while dialog.plugin_task_running() and time.monotonic() < deadline:
            QApplication.processEvents()
            time.sleep(0.01)
        self.assertFalse(dialog.plugin_task_running(), "plugin task did not finish")

    def test_plugin_update_runs_in_background_and_reports_the_result(self):
        manager = SettingsManager()
        plugin_manager = PluginManager(manager)
        sources = {}
        for version in ("0.1.0", "0.2.0"):
            plugin_dir = Path(self.temp_dir.name) / f"source-{version}" / "versioned-tool"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "plugin.json").write_text(json.dumps({
                "name": "versioned-tool", "displayName": "Versioned Tool", "version": version,
                "description": "Test", "permissions": [], "contributes": {},
            }), encoding="utf-8")
            sources[version] = plugin_dir
        channel = plugin_manager.official_plugin_channel()
        registry_path = plugin_manager.cached_registry_file(channel)
        registry_path.write_text(json.dumps({"schemaVersion": 1, "plugins": [{
            "id": "versioned-tool",
            "displayName": "Versioned Tool",
            "latestVersion": "0.2.0",
            "versions": [
                {"version": version, "source": {"type": "path", "path": str(path)}}
                for version, path in sorted(sources.items(), reverse=True)
            ],
        }]}), encoding="utf-8")
        plugin_manager.cached_registry_checksum_file(channel).write_text(
            f"{plugin_manager.sha256_file(registry_path)}  plugins.json\n", encoding="utf-8"
        )

        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)
        pm = dialog.plugin_manager
        self.assertTrue(pm.install_plugin_from_registry("versioned-tool", "0.1.0"))
        dialog.refresh_plugin_list()
        dialog.select_plugin_by_name("versioned-tool")

        started, release = threading.Event(), threading.Event()
        real_stage = pm.stage_plugin_package

        def slow_stage(name, entry):
            started.set()
            release.wait(10)
            return real_stage(name, entry)

        with patch.object(pm, "download_plugin_registries", return_value=[]), \
                patch.object(pm, "stage_plugin_package", side_effect=slow_stage):
            dialog.update_selected_plugin()
            # The download runs on a worker while the GUI thread stays free.
            self.assertTrue(started.wait(10))
            self.assertTrue(dialog.plugin_task_running())
            self.assertFalse(dialog.update_plugin_button.isEnabled())
            self.assertFalse(dialog.update_registry_button.isEnabled())
            self.assertFalse(dialog.plugin_task_progress.isHidden())
            self.assertEqual(dialog.plugin_task_status.text(), "Updating Versioned Tool…")
            release.set()
            self.wait_for_plugin_task(dialog)

        self.assertEqual(pm.plugins["versioned-tool"].version, "0.2.0")
        self.assertEqual(dialog.plugin_task_status.text(), "Versioned Tool updated to 0.2.0.")
        self.assertTrue(dialog.update_plugin_button.isEnabled())
        self.assertTrue(dialog.plugin_task_progress.isHidden())

        with patch.object(pm, "download_plugin_registries", return_value=[]):
            dialog.update_selected_plugin()
            self.wait_for_plugin_task(dialog)
        self.assertEqual(dialog.plugin_task_status.text(), "Versioned Tool is up to date (0.2.0).")

        with patch.object(pm, "download_plugin_registries", side_effect=OSError("offline")), \
                patch.object(QMessageBox, "warning") as warning:
            dialog.update_selected_plugin()
            self.wait_for_plugin_task(dialog)
        warning.assert_called_once()
        self.assertIn("offline", warning.call_args.args[2])
        self.assertTrue(dialog.update_plugin_button.isEnabled())

        with patch.object(pm, "download_plugin_registries", return_value=[]):
            dialog.update_plugin_registry()
            self.wait_for_plugin_task(dialog)
        self.assertEqual(
            dialog.plugin_task_status.text(),
            "Plugin index updated. All installed plugins are up to date.",
        )

    def test_settings_always_shows_browser_page(self):
        manager = SettingsManager()
        # State left over from the retired browser-panel plugin must not hide the page.
        manager.save_setting("plugin_state", {
            "browser-panel": {"enabled": False, "trusted": True, "version": "0.1.0"}
        })

        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)

        nav_items = [
            dialog.settings_nav.item(index).text()
            for index in range(dialog.settings_nav.count())
        ]
        self.assertIn("Browser and Search", nav_items)
        self.assertEqual(nav_items.index("Browser and Search"), nav_items.index("Editor") + 1)
        listed = [
            dialog.plugin_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(dialog.plugin_list.count())
        ]
        self.assertNotIn("browser-panel", listed)

    def test_browser_page_privacy_controls(self):
        manager = SettingsManager()
        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)
        restart = MagicMock()
        dialog.host = SimpleNamespace(
            apply_settings_domain=MagicMock(), restart_application=restart
        )
        self.assertFalse(dialog.browser_remember_data_check.isChecked())

        # Turning remembering on applies at once and leaves saved data alone.
        with patch.object(QMessageBox, "question") as question:
            dialog.browser_remember_data_check.setChecked(True)
        self.assertTrue(manager.get_setting("browser_remember_data"))
        dialog.host.apply_settings_domain.assert_called_once_with("browser")
        question.assert_not_called()
        self.assertFalse(manager.get_setting("browser_wipe_pending", False))

        # Turning it off schedules a wipe and offers a restart.
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.No
        ) as question:
            dialog.browser_remember_data_check.setChecked(False)
        self.assertFalse(manager.get_setting("browser_remember_data"))
        self.assertTrue(manager.get_setting("browser_wipe_pending"))
        question.assert_called_once()
        restart.assert_not_called()

        manager.save_setting("browser_wipe_pending", False)
        with patch("jottr.editor.web_profile.clear_browsing_data") as clear, \
                patch.object(QMessageBox, "question",
                             return_value=QMessageBox.StandardButton.Yes):
            dialog.clear_browsing_data()
        self.assertEqual(dialog.browser_clear_status.text(), "Clearing…")
        self.assertTrue(manager.get_setting("browser_wipe_pending"))
        restart.assert_called_once_with()
        settings_manager, finished = clear.call_args.args
        self.assertIs(settings_manager, manager)
        finished()
        self.assertEqual(
            dialog.browser_clear_status.text(),
            "Cookies and cache cleared. Other site data is deleted when Jottr closes.",
        )

    def test_uninstalled_registry_plugin_offers_enable(self):
        manager = SettingsManager()
        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)

        rss_rows = [
            index for index in range(dialog.plugin_list.count())
            if dialog.plugin_list.item(index).data(Qt.ItemDataRole.UserRole) == "rss-feed"
        ]
        self.assertTrue(rss_rows)
        dialog.plugin_list.setCurrentRow(rss_rows[0])
        self.assertEqual(dialog.plugin_status_badge.text(), "Not installed")
        self.assertEqual(dialog.toggle_plugin_button.text(), "Install")
        self.assertFalse(dialog.update_plugin_button.isEnabled())
        self.assertFalse(dialog.remove_plugin_button.isEnabled())
        self.assertIn("Available: 0.3.1", dialog.plugin_details.text())

    def test_settings_dialog_autosave_interval_is_a_clamped_spinbox(self):
        manager = SettingsManager()
        manager.save_setting("autosave_interval_seconds", 45)

        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.autosave_interval_spin.value(), 45)
        self.assertFalse(dialog.autosave_interval_spin.isEnabled())
        dialog.autosave_enabled_check.setChecked(True)
        self.assertTrue(dialog.autosave_interval_spin.isEnabled())

        dialog.autosave_interval_spin.setValue(7200)
        self.assertEqual(dialog.get_data()["autosave_interval_seconds"], 3600)
        self.assertEqual(manager.get_setting("autosave_interval_seconds"), 3600)

        dialog.set_autosave_interval("bad")
        self.assertEqual(dialog.get_data()["autosave_interval_seconds"], 30)
        # Settings uses font-only QSS so titles follow Main UI Font; no color chrome.
        stylesheet = dialog.styleSheet()
        self.assertIn("QGroupBox::title", stylesheet)
        self.assertIn("font-family:", stylesheet)
        self.assertNotIn("background", stylesheet)
        self.assertNotIn("color:", stylesheet)
        self.assertIsNotNone(dialog.findChild(QWidget, "settingsContentDivider"))

    def test_settings_dialog_applies_ui_font_to_sidebar_and_controls(self):
        manager = SettingsManager()
        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)

        ui_font = QFont("Liberation Sans", 13)
        dialog.apply_ui_font(ui_font)

        self.assertEqual(dialog.font().family(), "Liberation Sans")
        self.assertEqual(dialog.font().pointSize(), 13)
        self.assertEqual(dialog.settings_nav.font().family(), "Liberation Sans")
        self.assertEqual(dialog.settings_nav.font().pointSize(), 13)
        self.assertEqual(dialog.window_color_scheme_combo.font().family(), "Liberation Sans")
        self.assertEqual(dialog.qt_style_combo.font().family(), "Liberation Sans")
        self.assertEqual(
            dialog.window_color_scheme_combo.view().font().family(), "Liberation Sans"
        )
        self.assertEqual(dialog.ui_font.family(), "Liberation Sans")
        stylesheet = dialog.styleSheet()
        self.assertIn('font-family: "Liberation Sans"', stylesheet)
        self.assertIn("QGroupBox::title", stylesheet)
        self.assertIn("font-size: 13pt", stylesheet)
        general = next(
            box for box in dialog.findChildren(QGroupBox)
            if box.title() == "General"
        )
        self.assertEqual(general.font().family(), "Liberation Sans")

    def test_settings_dialog_translates_autosave_seconds_label(self):
        translations_dir = Path(self.temp_dir.name) / "translations"
        translations_dir.mkdir()
        (translations_dir / "zz_ZZ.po").write_text(
            'msgid ""\n'
            'msgstr ""\n'
            '"Language: zz_ZZ\\n"\n\n'
            'msgid "Seconds"\n'
            'msgstr "Translated Seconds"\n',
            encoding="utf-8"
        )
        manager = SettingsManager()
        manager.save_setting("language", "zz_ZZ")

        with patch.object(translation_manager, "get_translations_dir", return_value=translations_dir):
            dialog = SettingsDialog(manager)
            self.addCleanup(dialog.deleteLater)

            self.assertEqual(dialog.autosave_interval_unit_label.text(), "Translated Seconds")

        translation_manager.set_language("en_US")

    def test_settings_dialog_offers_only_builtin_editor_themes(self):
        manager = SettingsManager()
        manager.settings["theme"] = "Ink"
        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)

        names = [
            dialog.editor_theme_combo.itemText(i)
            for i in range(dialog.editor_theme_combo.count())
        ]
        self.assertEqual(names, list(ThemeManager.get_themes()))
        self.assertEqual(dialog.editor_theme_combo.currentText(), ThemeManager.DEFAULT_THEME_NAME)
        self.assertFalse(hasattr(dialog, "theme_json_edit"))
        self.assertFalse(dialog.editor_theme_combo.itemIcon(0).isNull())

    def test_settings_window_remembers_page_and_syncs_external_changes(self):
        manager = SettingsManager()
        manager.save_setting("search_sites", {"Ops: Daily": "site:ops.example"})
        dialog = SettingsDialog(manager)

        # Names containing ": " survive a round trip.
        self.assertEqual(dialog.get_search_sites(), {"Ops: Daily": "site:ops.example"})
        dialog.upsert_search_site("Ops: Daily", "site:ops2.example")
        dialog.upsert_search_site("Wiki", "site:wiki.example")
        self.assertEqual(manager.get_setting("search_sites"), {
            "Ops: Daily": "site:ops2.example",
            "Wiki": "site:wiki.example",
        })
        dialog.upsert_search_site("Wiki", "site:wiki2.example", row=0)
        self.assertEqual(manager.get_setting("search_sites"), {"Wiki": "site:wiki2.example"})

        dialog.add_dict_word(" jottr ")
        dialog.add_dict_word("jottr")
        self.assertEqual(manager.get_setting("user_dictionary"), ["jottr"])

        self.assertTrue(dialog.show_settings_page("spellcheck"))
        dialog.reject()
        self.assertIn("geometry", manager.get_setting("settings_window_state"))

        reopened = SettingsDialog(manager)
        self.addCleanup(reopened.deleteLater)
        self.assertEqual(reopened.settings_nav.currentItem().text(), "Spellcheck")

        manager.save_setting("spell_check", False)
        manager.save_setting("user_dictionary", ["jottr", "kate"])
        manager.save_theme("Monokai")
        reopened.sync_from_settings()
        self.assertFalse(reopened.spell_check_enabled.isChecked())
        self.assertEqual(reopened.get_user_dictionary(), ["jottr", "kate"])
        self.assertEqual(reopened.editor_theme_combo.currentText(), "Monokai")

    def test_settings_dialog_is_close_only_and_persists_plugins_directory(self):
        manager = SettingsManager()
        dialog = SettingsDialog(manager)
        from PyQt6.QtWidgets import QPushButton

        labels = [btn.text() for btn in dialog.findChildren(QPushButton)]
        self.assertIn("Close", labels)
        self.assertNotIn("Apply", labels)
        self.assertNotIn("OK", labels)
        self.assertNotIn("Cancel", labels)

        target = Path(self.temp_dir.name) / "more-plugins"
        target.mkdir()
        dialog.plugins_directory_edit.setText(str(target))
        dialog.plugins_directory_edit.editingFinished.emit()
        self.assertEqual(manager.get_setting("plugins_directory"), str(target))

    def test_sessions_page_controls_swap_files_and_restoring_new_files(self):
        manager = SettingsManager()
        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)

        self.assertTrue(dialog.show_settings_page("sessions"))
        self.assertEqual(dialog.settings_nav.currentItem().text(), "Sessions")
        self.assertTrue(dialog.swap_file_enabled_check.isChecked())
        self.assertTrue(dialog.restore_unsaved_new_files_check.isChecked())

        dialog.swap_file_enabled_check.setChecked(False)
        dialog.restore_unsaved_new_files_check.setChecked(False)
        self.assertFalse(manager.get_setting("swap_file_enabled"))
        self.assertFalse(manager.get_setting("restore_unsaved_new_files"))
        data = dialog.get_data()
        self.assertFalse(data["swap_file_enabled"])
        self.assertFalse(data["restore_unsaved_new_files"])

        # Both backups off: the sync interval has nothing to control.
        self.assertFalse(dialog.backup_interval_spin.isEnabled())

        manager.save_setting("swap_file_enabled", True)
        dialog.sync_from_settings()
        self.assertTrue(dialog.swap_file_enabled_check.isChecked())
        self.assertTrue(dialog.backup_interval_spin.isEnabled())

        self.assertEqual(dialog.backup_interval_spin.value(), 15)
        dialog.backup_interval_spin.setValue(900)
        self.assertEqual(manager.get_setting("swap_sync_interval_seconds"), 600)
        self.assertEqual(dialog.get_data()["swap_sync_interval_seconds"], 600)

        # Fresh installs only restore the session when unsaved changes are detected.
        self.assertTrue(dialog.restore_session_unsaved_radio.isChecked())
        self.assertEqual(dialog.get_data()["session_restore_mode"], "unsaved_changes")
        dialog.restore_session_always_radio.setChecked(True)
        self.assertFalse(dialog.restore_session_unsaved_radio.isChecked())
        self.assertEqual(manager.get_setting("session_restore_mode"), "always")
        self.assertEqual(dialog.get_data()["session_restore_mode"], "always")
        manager.save_setting("session_restore_mode", "unsaved_changes")
        dialog.sync_from_settings()
        self.assertTrue(dialog.restore_session_unsaved_radio.isChecked())

    def test_sessions_page_picks_a_startup_workspace(self):
        first = Path(self.temp_dir.name) / "notes"
        second = Path(self.temp_dir.name) / "other" / "notes"
        chosen = Path(self.temp_dir.name) / "chosen"
        for folder in (first, second, chosen):
            folder.mkdir(parents=True)
        manager = SettingsManager()
        manager.save_setting("recent_workspaces", [str(first), str(second)])
        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)
        combo = dialog.startup_workspace_combo

        self.assertFalse(combo.isEnabled())
        self.assertEqual(
            [combo.itemText(index) for index in range(combo.count())],
            [
                "No workspace selected",
                f"notes — {first.parent}",
                f"notes — {second.parent}",
                "Choose Folder…",
            ],
        )

        dialog.restore_session_workspace_radio.setChecked(True)
        self.assertTrue(combo.isEnabled())
        self.assertEqual(manager.get_setting("session_restore_mode"), "workspace")
        self.assertEqual(manager.get_setting("startup_workspace"), "")

        combo.activated.emit(combo.findData(str(second)))
        self.assertEqual(manager.get_setting("startup_workspace"), str(second))
        self.assertEqual(combo.currentData(), str(second))
        self.assertEqual(combo.findText("No workspace selected"), -1)

        with patch(
            "jottr.settings.pages.sessions.get_existing_directory", return_value=str(chosen)
        ):
            combo.activated.emit(combo.count() - 1)
        self.assertEqual(manager.get_setting("startup_workspace"), str(chosen))
        self.assertEqual(combo.currentText(), "chosen")
        self.assertEqual(dialog.get_data()["startup_workspace"], str(chosen))

        # Cancelling the folder picker keeps the workspace that was chosen.
        with patch("jottr.settings.pages.sessions.get_existing_directory", return_value=""):
            combo.activated.emit(combo.count() - 1)
        self.assertEqual(manager.get_setting("startup_workspace"), str(chosen))
        self.assertEqual(combo.currentData(), str(chosen))

        dialog.restore_session_always_radio.setChecked(True)
        self.assertFalse(combo.isEnabled())

    def test_editor_page_adds_the_date_to_suggested_file_names(self):
        manager = SettingsManager()
        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)
        check = dialog.save_name_date_check
        combo = dialog.save_name_date_format_combo

        self.assertFalse(check.isChecked())
        self.assertFalse(combo.isEnabled())
        self.assertEqual(
            [combo.itemData(index) for index in range(combo.count())],
            ["YYYYMMDD", "YYYYDDMM"],
        )
        self.assertEqual(combo.currentData(), "YYYYMMDD")
        self.assertRegex(combo.itemText(0), r"^YYYYMMDD \(\d{8}\)$")

        check.setChecked(True)
        self.assertTrue(combo.isEnabled())
        self.assertTrue(manager.get_setting("save_name_append_date"))
        combo.setCurrentIndex(combo.findData("YYYYDDMM"))
        self.assertEqual(manager.get_setting("save_name_date_format"), "YYYYDDMM")
        data = dialog.get_data()
        self.assertTrue(data["save_name_append_date"])
        self.assertEqual(data["save_name_date_format"], "YYYYDDMM")

        # A reopened window shows the saved choice.
        reopened = SettingsDialog(manager)
        self.addCleanup(reopened.deleteLater)
        self.assertTrue(reopened.save_name_date_check.isChecked())
        self.assertEqual(reopened.save_name_date_format_combo.currentData(), "YYYYDDMM")

    def test_snippet_editor_dialog_returns_entered_data(self):
        dialog = SnippetEditorDialog("Title", "Body")
        dialog.title_edit.setText("Updated")
        dialog.content_edit.setPlainText("Updated body")

        self.assertEqual(dialog.get_data(), {"title": "Updated", "content": "Updated body"})


if __name__ == "__main__":
    unittest.main()
