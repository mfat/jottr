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
SRC_DIR = PROJECT_ROOT / "src" / "jottr"
sys.path.insert(0, str(SRC_DIR))

from PyQt6.QtWidgets import QApplication, QMessageBox

from feed_manager_dialog import FeedManagerDialog
from rss_reader import RSSReader
from settings_dialog import SearchSiteDialog, SettingsDialog
from settings_manager import SettingsManager
from snippet_editor_dialog import SnippetEditorDialog


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


class DialogAndRssTests(unittest.TestCase):
    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_search_site_dialog_normalizes_site_queries(self):
        dialog = SearchSiteDialog(name="Example", site="https://www.example.com")

        self.assertEqual(dialog.get_data(), ("Example", "site:example.com"))

    def test_settings_dialog_round_trips_settings(self):
        manager = SettingsManager()
        manager.save_setting("search_sites", {"News": "site:news.example"})
        manager.save_setting("user_dictionary", ["jottr"])
        manager.save_custom_themes({
            "Forest": {
                "bg": "#102018",
                "text": "#e8f5e9",
                "selection": "#355e3b"
            }
        })
        manager.save_theme("Forest")

        dialog = SettingsDialog(manager)
        dialog.homepage_edit.setText("https://home.example")
        dialog.editor_theme_combo.setCurrentText("Forest")
        dialog.icon_contrast_combo.setCurrentText("light")
        dialog.markdown_scroll_sync_check.setChecked(False)
        dialog.editor_line_numbers_check.setChecked(False)

        data = dialog.get_data()

        self.assertEqual(data["homepage"], "https://home.example")
        self.assertEqual(data["search_sites"], {"News": "site:news.example"})
        self.assertEqual(data["user_dictionary"], ["jottr"])
        self.assertEqual(data["theme"], "Forest")
        self.assertEqual(data["custom_themes"]["Forest"]["editor"]["background"], "#102018")
        self.assertEqual(data["icon_contrast"], "light")
        self.assertFalse(data["markdown_scroll_sync"])
        self.assertFalse(data["editor_line_numbers"])

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

        with patch("feed_manager_dialog.requests.get", return_value=response) as get, \
                patch("feed_manager_dialog.feedparser.parse", return_value=feed):
            self.assertTrue(dialog.test_feed_url("https://example.test/rss"))

        get.assert_called_once_with("https://example.test/rss", timeout=10)

    def test_feed_manager_test_feed_url_rejects_empty_feed(self):
        dialog = FeedManagerDialog({})
        response = Mock(text="<rss></rss>")
        response.raise_for_status.return_value = None
        feed = SimpleNamespace(entries=[])

        with patch("feed_manager_dialog.requests.get", return_value=response), \
                patch("feed_manager_dialog.feedparser.parse", return_value=feed), \
                patch("feed_manager_dialog.QMessageBox.warning") as warning:
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
                with patch("rss_reader.requests.get", return_value=response), \
                        patch("rss_reader.feedparser.parse", return_value=feed):
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
                    "rss_reader.QMessageBox.question",
                    return_value=QMessageBox.StandardButton.Yes,
                ):
                    reader.remove_feed()
            finally:
                os.chdir(old_cwd)

        self.assertEqual(reader.feeds, {})


if __name__ == "__main__":
    unittest.main()
