import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QGroupBox, QLabel, QMessageBox, QScrollArea, QWidget

from jottr.feed_manager_dialog import FeedManagerDialog
from jottr.rss_reader import RSSReader
from jottr.settings_dialog import SearchSiteDialog, SettingsDialog
from jottr.plugin_manager import PluginManager
from jottr.settings_manager import SettingsManager
from jottr.snippet_editor_dialog import SnippetEditorDialog
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
                "id": "browser-panel",
                "displayName": "Browser Panel",
                "description": "Adds the integrated browser side panel and browser search commands.",
                "latestVersion": "0.1.0",
                "defaultEnabled": True,
                "versions": [{"version": "0.1.0", "package": {"downloadUrl": "https://example.test/browser.zip", "sha256": "abc"}}],
            },
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


class DialogAndRssTests(unittest.TestCase):
    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        seed_official_plugin_registry(PluginManager(SettingsManager()))

    def test_search_site_dialog_normalizes_site_queries(self):
        dialog = SearchSiteDialog(name="Example", site="https://www.example.com")

        self.assertEqual(dialog.get_data(), ("Example", "site:example.com"))

    def test_settings_dialog_round_trips_settings(self):
        manager = SettingsManager()
        manager.save_setting("search_sites", {"News": "site:news.example"})
        manager.save_setting("user_dictionary", ["jottr"])
        manager.save_setting("autosave_enabled", True)
        manager.save_setting("autosave_interval_seconds", 12)
        manager.save_setting("plugin_registry_url", "https://example.test/plugins.json")
        manager.save_setting("plugin_registry_checksum_url", "https://example.test/plugins.json.sha256")
        manager.save_custom_themes({
            "Forest": {
                "bg": "#102018",
                "text": "#e8f5e9",
                "selection": "#355e3b"
            }
        })
        manager.save_theme("Forest")
        manager.save_ui_theme("Dark")

        dialog = SettingsDialog(manager)
        self.assertFalse(dialog.windowIcon().isNull())
        for index in range(dialog.settings_nav.count()):
            self.assertFalse(
                dialog.settings_nav.item(index).icon().isNull(),
                msg=f"missing icon for {dialog.settings_nav.item(index).text()}",
            )
        dialog.homepage_edit.setText("https://home.example")
        dialog.ui_theme_combo.setCurrentIndex(dialog.ui_theme_combo.findData("Dark"))
        dialog.editor_theme_combo.setCurrentText("Forest")
        self.assertEqual(
            [dialog.ui_theme_combo.itemData(i) for i in range(dialog.ui_theme_combo.count())],
            ["System", "Light", "Dark"],
        )
        self.assertIn("Forest", [
            dialog.editor_theme_combo.itemText(i)
            for i in range(dialog.editor_theme_combo.count())
        ])
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
            ["bootstrap", "symbolic"],
        )
        self.assertEqual(dialog.icon_theme_combo.currentData(), "bootstrap")
        dialog.icon_theme_combo.setCurrentIndex(
            dialog.icon_theme_combo.findData("bootstrap")
        )
        dialog.icon_contrast_combo.setCurrentText("light")
        dialog.markdown_scroll_sync_check.setChecked(False)
        dialog.editor_line_numbers_check.setChecked(False)
        dialog.double_click_empty_tab_bar_new_tab_check.setChecked(False)
        dialog.middle_click_tab_closes_tab_check.setChecked(False)
        dialog.enable_animations_check.setChecked(False)
        dialog.autosave_enabled_check.setChecked(True)
        dialog.autosave_interval_combo.setCurrentText("15")
        dialog.plugins_directory_edit.setText(str(Path(self.temp_dir.name) / "plugins"))
        dialog.spell_check_enabled.setChecked(False)

        data = dialog.get_data()

        self.assertEqual(data["homepage"], "https://home.example")
        self.assertEqual(data["language"], "en_US")
        self.assertGreaterEqual(dialog.language_combo.count(), 1)
        self.assertEqual(data["search_sites"], {"News": "site:news.example"})
        self.assertEqual(data["user_dictionary"], ["jottr"])
        self.assertFalse(data["spell_check"])
        self.assertEqual(data["document_language"], "auto")
        self.assertEqual(data["spell_languages"], [])
        self.assertEqual(data["ui_theme"], "Dark")
        self.assertEqual(data["theme"], "Forest")
        self.assertEqual(data["qt_style"], fusion)
        self.assertEqual(data["custom_themes"]["Forest"]["editor"]["background"], "#102018")
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
        data = dialog.get_data()
        self.assertEqual(data["plugin_channel_filter"], "Community")
        self.assertTrue(any(channel["name"] == "Community" for channel in data["plugin_channels"]))
        official_label = dialog.plugin_channel_filter_combo.itemText(dialog.plugin_channel_filter_combo.findData("Official"))
        self.assertIn("✓", official_label)
        self.assertTrue(dialog.remove_plugin_channel_button.isEnabled())

        dialog.remove_plugin_channel()
        self.assertEqual(dialog.plugin_channel_filter_combo.currentData(), "all")
        self.assertEqual(dialog.plugin_channel_filter_combo.findData("Community"), -1)
        self.assertFalse(any(channel["name"] == "Community" for channel in dialog.get_data()["plugin_channels"]))

        official_index = dialog.plugin_channel_filter_combo.findData("Official")
        dialog.plugin_channel_filter_combo.setCurrentIndex(official_index)
        self.assertFalse(dialog.remove_plugin_channel_button.isEnabled())
        dialog.remove_plugin_channel()
        self.assertGreaterEqual(dialog.plugin_channel_filter_combo.findData("Official"), 0)

    def test_settings_hides_browser_page_when_browser_plugin_is_disabled(self):
        manager = SettingsManager()
        manager.save_setting("plugin_state", {
            "browser-panel": {"enabled": False, "trusted": True, "version": "0.1.0"}
        })

        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)

        nav_items = [
            dialog.settings_nav.item(index).text()
            for index in range(dialog.settings_nav.count())
        ]
        self.assertNotIn("Browser", nav_items)

    def test_disabling_browser_plugin_removes_browser_settings_page(self):
        manager = SettingsManager()
        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)

        browser_rows = [
            index for index in range(dialog.plugin_list.count())
            if dialog.plugin_list.item(index).data(Qt.ItemDataRole.UserRole) == "browser-panel"
        ]
        self.assertTrue(browser_rows)
        self.assertIn("Browser", [dialog.settings_nav.item(index).text() for index in range(dialog.settings_nav.count())])

        dialog.plugin_list.setCurrentRow(browser_rows[0])
        self.assertEqual(dialog.toggle_plugin_button.text(), "Disable")
        dialog.toggle_selected_plugin()

        nav_items = [dialog.settings_nav.item(index).text() for index in range(dialog.settings_nav.count())]
        self.assertNotIn("Browser", nav_items)
        self.assertEqual(dialog.toggle_plugin_button.text(), "Enable")

    def test_settings_dialog_autosave_seconds_uses_dropdown_values(self):
        manager = SettingsManager()
        manager.save_setting("autosave_interval_seconds", 45)

        dialog = SettingsDialog(manager)
        self.addCleanup(dialog.deleteLater)

        self.assertEqual(dialog.autosave_interval_combo.currentText(), "45")
        self.assertIn("30", [dialog.autosave_interval_combo.itemText(i) for i in range(dialog.autosave_interval_combo.count())])

        dialog.autosave_interval_combo.setCurrentText("7200")
        self.assertEqual(dialog.get_data()["autosave_interval_seconds"], 3600)

        dialog.autosave_interval_combo.setCurrentText("bad")
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
        self.assertEqual(dialog.ui_theme_combo.font().family(), "Liberation Sans")
        self.assertEqual(dialog.qt_style_combo.font().family(), "Liberation Sans")
        self.assertEqual(dialog.ui_theme_combo.view().font().family(), "Liberation Sans")
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

    def test_settings_dialog_creates_and_deletes_custom_theme(self):
        manager = SettingsManager()
        dialog = SettingsDialog(manager)

        dialog.theme_json_edit.setPlainText(json.dumps({
            "name": "Ink",
            "app": {
                "background": "#fafafa",
                "surface": "#ffffff",
                "text": "#111111"
            },
            "editor": {
                "background": "#fafafa",
                "foreground": "#111111",
                "selection": "#cccccc"
            },
            "syntax": {}
        }))
        dialog.save_custom_theme()

        self.assertIn("Ink", dialog.get_data()["custom_themes"])
        self.assertEqual(dialog.ui_theme_combo.currentData(), "System")
        self.assertEqual(dialog.editor_theme_combo.currentText(), "Ink")

        dialog.custom_theme_list.setCurrentRow(0)
        dialog.delete_custom_theme()

        self.assertNotIn("Ink", dialog.get_data()["custom_themes"])

    def test_settings_dialog_saves_advanced_theme_json(self):
        manager = SettingsManager()
        dialog = SettingsDialog(manager)

        dialog.theme_json_edit.setPlainText(json.dumps({
            "name": "Dracula Local",
            "app": {
                "background": "#282a36",
                "surface": "#343746",
                "accent": "#bd93f9"
            },
            "editor": {
                "background": "#282a36",
                "foreground": "#f8f8f2",
                "selection": "#44475a"
            },
            "syntax": {
                "keyword": "#ff79c6"
            }
        }))
        dialog.save_custom_theme()

        theme = dialog.get_data()["custom_themes"]["Dracula Local"]
        self.assertEqual(theme["app"]["background"], "#282a36")
        self.assertEqual(theme["editor"]["foreground"], "#f8f8f2")
        self.assertEqual(theme["syntax"]["keyword"], "#ff79c6")

    def test_snippet_editor_dialog_returns_entered_data(self):
        dialog = SnippetEditorDialog("Title", "Body")
        dialog.title_edit.setText("Updated")
        dialog.content_edit.setPlainText("Updated body")

        self.assertEqual(dialog.get_data(), {"title": "Updated", "content": "Updated body"})

    def test_feed_manager_dialog_edits_copy_without_mutating_original_until_read(self):
        original = {"A": "https://a.example/rss"}
        dialog = FeedManagerDialog(original)

        dialog.feeds["B"] = "https://b.example/rss"
        dialog.refresh_table()

        self.assertEqual(original, {"A": "https://a.example/rss"})
        self.assertEqual(dialog.get_feeds()["B"], "https://b.example/rss")
        self.assertEqual(dialog.table.rowCount(), 2)

    def test_feed_manager_test_feed_url_accepts_valid_feed(self):
        dialog = FeedManagerDialog({})
        response = Mock(text="<rss></rss>")
        response.raise_for_status.return_value = None
        feed = SimpleNamespace(entries=[SimpleNamespace(title="Item")])

        with patch("jottr.feed_manager_dialog.requests.get", return_value=response) as get, \
                patch("jottr.feed_manager_dialog.feedparser.parse", return_value=feed):
            self.assertTrue(dialog.test_feed_url("https://example.test/rss"))

        get.assert_called_once_with("https://example.test/rss", timeout=10)

    def test_feed_manager_test_feed_url_rejects_empty_feed(self):
        dialog = FeedManagerDialog({})
        response = Mock(text="<rss></rss>")
        response.raise_for_status.return_value = None
        feed = SimpleNamespace(entries=[])

        with patch("jottr.feed_manager_dialog.requests.get", return_value=response), \
                patch("jottr.feed_manager_dialog.feedparser.parse", return_value=feed), \
                patch("jottr.feed_manager_dialog.QMessageBox.warning") as warning:
            self.assertFalse(dialog.test_feed_url("https://example.test/rss"))

        warning.assert_called_once()

    def test_rss_reader_loads_default_and_custom_feeds(self):
        with tempfile.TemporaryDirectory() as cwd:
            Path(cwd, "rss_feeds.json").write_text(
                json.dumps({"Local": "https://local.example/rss"}),
                encoding="utf-8",
            )
            old_cwd = Path.cwd()
            os.chdir(cwd)
            try:
                reader = RSSReader()
            finally:
                os.chdir(old_cwd)

        self.assertIn("BBC World", reader.feeds)
        self.assertEqual(reader.feeds["Local"], "https://local.example/rss")
        self.assertGreater(reader.feed_selector.count(), 0)

    def test_rss_reader_refresh_populates_entries_and_content(self):
        with tempfile.TemporaryDirectory() as cwd:
            old_cwd = Path.cwd()
            os.chdir(cwd)
            try:
                reader = RSSReader()
                reader.feeds = {"Local": "https://local.example/rss"}
                reader.update_feed_selector()
                response = Mock(text="<rss></rss>")
                response.raise_for_status.return_value = None
                entry = SimpleNamespace(
                    title="Headline",
                    published="Today",
                    description="Summary",
                    link="https://example.test/story",
                )
                feed = SimpleNamespace(entries=[entry])
                with patch("jottr.rss_reader.requests.get", return_value=response), \
                        patch("jottr.rss_reader.feedparser.parse", return_value=feed):
                    reader.refresh_current_feed()
                    reader.entries_list.setCurrentRow(0)
            finally:
                os.chdir(old_cwd)

        self.assertEqual(reader.entries_list.count(), 1)
        self.assertIn("Headline", reader.content_viewer.toHtml())

    def test_rss_reader_remove_feed_respects_confirmation(self):
        with tempfile.TemporaryDirectory() as cwd:
            old_cwd = Path.cwd()
            os.chdir(cwd)
            try:
                reader = RSSReader()
                reader.feeds = {"Local": "https://local.example/rss"}
                reader.update_feed_selector()
                with patch(
                    "jottr.rss_reader.QMessageBox.question",
                    return_value=QMessageBox.StandardButton.Yes,
                ):
                    reader.remove_feed()
            finally:
                os.chdir(old_cwd)

        self.assertEqual(reader.feeds, {})


if __name__ == "__main__":
    unittest.main()
