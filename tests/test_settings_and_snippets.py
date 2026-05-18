import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src" / "jottr"
sys.path.insert(0, str(SRC_DIR))

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from settings_manager import SettingsManager
from snippet_manager import SnippetManager
from theme_manager import ThemeManager


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


class SettingsAndSnippetTests(unittest.TestCase):
    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_settings_manager_uses_isolated_config_and_defaults(self):
        manager = SettingsManager()

        self.assertEqual(Path(manager.config_dir), Path(self.temp_dir.name) / "Jottr")
        self.assertTrue(Path(manager.snippets_dir).is_dir())
        self.assertEqual(manager.get_setting("font_size"), 12)
        self.assertTrue(manager.get_setting("spell_check"))
        self.assertEqual(manager.get_setting("icon_contrast"), "auto")
        self.assertEqual(manager.get_setting("missing", "fallback"), "fallback")

    def test_settings_manager_persists_single_settings_and_font(self):
        manager = SettingsManager()

        manager.save_setting("homepage", "https://example.test")
        font = QFont("Serif", 15)
        font.setItalic(True)
        manager.save_font(font)

        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_setting("homepage"), "https://example.test")
        self.assertEqual(reloaded.get_font().family(), "Serif")
        self.assertEqual(reloaded.get_font().pointSize(), 15)
        self.assertTrue(reloaded.get_font().italic())

    def test_settings_manager_persists_custom_themes(self):
        manager = SettingsManager()
        manager.save_custom_themes({
            "Forest": {
                "bg": "#102018",
                "text": "#e8f5e9",
                "selection": "#355e3b"
            },
            "Broken": {
                "bg": "green",
                "text": "#ffffff",
                "selection": "#000000"
            }
        })
        manager.save_theme("Forest")

        reloaded = SettingsManager()

        self.assertEqual(reloaded.get_theme(), "Forest")
        forest = reloaded.get_custom_themes()["Forest"]
        self.assertEqual(forest["editor"]["background"], "#102018")
        self.assertEqual(forest["editor"]["foreground"], "#e8f5e9")
        self.assertEqual(forest["editor"]["selection"], "#355e3b")
        self.assertNotIn("Broken", reloaded.get_custom_themes())

    def test_settings_manager_handles_invalid_json_by_keeping_defaults(self):
        manager = SettingsManager()
        Path(manager.settings_file).write_text("{not json", encoding="utf-8")

        reloaded = SettingsManager()

        self.assertEqual(reloaded.get_setting("font_family"), "DejaVu Sans Mono")

    def test_snippet_manager_persists_crud_operations(self):
        settings = SettingsManager()
        snippets = SnippetManager(settings)

        snippets.add_snippet("lede", "A concise opening paragraph.")
        snippets.add_snippet("quote", "Quote block")
        snippets.delete_snippet("quote")

        reloaded = SnippetManager(settings)
        self.assertEqual(reloaded.get_snippet("lede"), "A concise opening paragraph.")
        self.assertIsNone(reloaded.get_snippet("quote"))
        self.assertEqual(reloaded.get_snippets(), ["lede"])
        self.assertEqual(reloaded.get_all_snippet_contents(), ["A concise opening paragraph."])

    def test_snippet_manager_recovers_from_invalid_json(self):
        settings = SettingsManager()
        snippets_file = Path(settings.config_dir) / "snippets.json"
        snippets_file.write_text("{broken", encoding="utf-8")

        snippets = SnippetManager(settings)

        self.assertEqual(snippets.get_snippets(), [])

    def test_theme_manager_defines_and_applies_known_themes(self):
        themes = ThemeManager.get_themes()
        self.assertIn("Light", themes)
        self.assertIn("Dark", themes)
        self.assertIn("Sepia", themes)
        self.assertIn("Dracula", themes)
        self.assertIn("Monokai", themes)
        self.assertIn("Monaspace", themes)
        self.assertIn("Tokyo Night", themes)
        self.assertIn("Matcha", themes)
        self.assertIn(
            "Forest",
            ThemeManager.get_themes({
                "Forest": {
                    "bg": "#102018",
                    "text": "#e8f5e9",
                    "selection": "#355e3b"
                }
            })
        )

        from PyQt6.QtWidgets import QTextEdit

        editor = QTextEdit()
        ThemeManager.apply_theme(editor, "Dark")

        style = editor.styleSheet()
        self.assertIn("#111827", style)
        self.assertIn("#e5e7eb", style)

        ThemeManager.apply_theme(editor, "Forest", {
            "Forest": {
                "bg": "#102018",
                "text": "#e8f5e9",
                "selection": "#355e3b"
            }
        })
        self.assertIn("#102018", editor.styleSheet())

        dracula = ThemeManager.get_theme("Dracula")
        self.assertEqual(dracula["editor"]["background"], "#282a36")
        self.assertEqual(dracula["syntax"]["keyword"], "#ff79c6")
        self.assertIn("#282a36", ThemeManager.build_app_stylesheet(dracula))
        dialog_style = ThemeManager.build_dialog_stylesheet(dracula)
        self.assertIn("QComboBox QAbstractItemView", dialog_style)
        self.assertIn("selection-color", dialog_style)
        self.assertIn("#f8f8f2", dialog_style)


if __name__ == "__main__":
    unittest.main()
