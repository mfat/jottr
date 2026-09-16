import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from jottr.settings_manager import SettingsManager
from jottr.snippet_manager import SnippetManager
from jottr.theme_manager import ThemeManager
import jottr.translation_manager as translation_manager


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
        self.assertEqual(manager.get_setting("spell_languages"), ["en_US"])
        self.assertEqual(manager.get_setting("document_language"), "auto")
        self.assertEqual(manager.get_setting("icon_contrast"), "auto")
        self.assertEqual(manager.get_icon_theme(), "bootstrap")
        self.assertEqual(manager.get_setting("language"), "en_US")
        self.assertFalse(manager.get_setting("autosave_enabled"))
        self.assertEqual(manager.get_setting("autosave_interval_seconds"), 30)
        self.assertTrue(manager.get_setting("enable_animations"))
        self.assertTrue(manager.get_setting("double_click_empty_tab_bar_new_tab"))
        self.assertTrue(manager.get_setting("middle_click_tab_closes_tab"))
        self.assertEqual(manager.get_setting("workspace_path"), "")
        self.assertEqual(manager.get_setting("recent_workspaces"), [])
        self.assertEqual(manager.get_setting("workspace_sessions"), {})
        self.assertEqual(manager.get_setting("workspace_open_files"), [])
        self.assertEqual(manager.get_setting("workspace_markdown_files"), [])
        self.assertEqual(manager.get_setting("missing", "fallback"), "fallback")

    def test_translation_manager_loads_selected_po_file(self):
        translations_dir = Path(self.temp_dir.name) / "translations"
        translations_dir.mkdir()
        (translations_dir / "zz_ZZ.po").write_text(
            'msgid ""\n'
            'msgstr ""\n'
            '"Language: zz_ZZ\\n"\n'
            '\n'
            'msgid "Settings"\n'
            'msgstr "Translated Settings"\n'
            '\n'
            'msgid "Language:"\n'
            'msgstr "Translated Language:"\n',
            encoding="utf-8"
        )

        with patch.object(translation_manager, "get_translations_dir", return_value=translations_dir):
            translation_manager.set_language("zz_ZZ")

            self.assertEqual(translation_manager.translate("Settings"), "Translated Settings")
            self.assertEqual(translation_manager.translate("Language:"), "Translated Language:")
            self.assertEqual(translation_manager.translate("Missing"), "Missing")

        translation_manager.set_language("en_US")

    def test_translation_manager_detects_rtl_languages(self):
        self.assertTrue(translation_manager.is_rtl_language("fa_IR"))
        self.assertTrue(translation_manager.is_rtl_language("ar_SA"))
        self.assertTrue(translation_manager.is_rtl_language("he_IL"))
        self.assertFalse(translation_manager.is_rtl_language("en_US"))
        self.assertFalse(translation_manager.is_rtl_language("de_DE"))

    def test_translation_manager_localizes_digits_for_persian_and_arabic(self):
        self.assertEqual(translation_manager.localize_digits(123, "en_US"), "123")
        self.assertEqual(translation_manager.localize_digits(123, "de_DE"), "123")
        self.assertEqual(translation_manager.localize_digits(123, "fa_IR"), "۱۲۳")
        self.assertEqual(translation_manager.localize_digits(123, "ar_SA"), "١٢٣")

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

    def test_settings_manager_defer_saves_writes_once(self):
        manager = SettingsManager()
        write_count = {"n": 0}
        original_write = manager._write_settings

        def counting_write():
            write_count["n"] += 1
            original_write()

        manager._write_settings = counting_write
        with manager.defer_saves():
            manager.save_setting("homepage", "https://batch.test")
            manager.save_setting("spell_check", False)
            manager.save_theme("Dark")
            manager.save_ui_theme("System")
            manager.save_setting("autosave_enabled", True)
            self.assertEqual(write_count["n"], 0)

        self.assertEqual(write_count["n"], 1)
        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_setting("homepage"), "https://batch.test")
        self.assertFalse(reloaded.get_setting("spell_check"))
        self.assertEqual(reloaded.get_theme(), "Black")
        self.assertTrue(reloaded.get_setting("autosave_enabled"))

    def test_settings_manager_persists_separate_ui_and_editor_fonts(self):
        manager = SettingsManager()
        self.assertTrue(manager.uses_system_ui_font())

        ui_font = QFont("Sans", 11)
        editor_font = QFont("Mono", 14)
        manager.save_font(ui_font, "ui")
        manager.save_font(editor_font, "editor")

        reloaded = SettingsManager()
        self.assertFalse(reloaded.uses_system_ui_font())
        self.assertEqual(reloaded.get_font("ui").family(), "Sans")
        self.assertEqual(reloaded.get_font("ui").pointSize(), 11)
        self.assertEqual(reloaded.get_font("editor").family(), "Mono")
        self.assertEqual(reloaded.get_font("editor").pointSize(), 14)

        manager.save_font(ui_font, "ui", follow_system=True)
        self.assertTrue(manager.uses_system_ui_font())
        system = SettingsManager.system_ui_font()
        self.assertEqual(manager.get_font("ui").family(), system.family())

    def test_settings_manager_defaults_ui_font_to_system_and_coerces_qt5_weight(self):
        manager = SettingsManager()
        system = SettingsManager.system_ui_font()
        ui = manager.get_font("ui")
        self.assertTrue(manager.uses_system_ui_font())
        self.assertEqual(ui.family(), system.family())
        self.assertGreaterEqual(int(ui.weight()), 100)
        self.assertEqual(SettingsManager.coerce_font_weight(50), int(QFont.Weight.Normal))
        self.assertEqual(SettingsManager.coerce_font_weight(400), 400)

        # Persisted legacy DejaVu UI default migrates to the system font.
        Path(manager.settings_file).write_text(
            json.dumps({
                "ui_font_family": "DejaVu Sans",
                "ui_font_size": 10,
                "ui_font_weight": 50,
                "ui_font_italic": False,
                "font_family": "DejaVu Sans Mono",
                "font_size": 12,
                "font_weight": 50,
                "font_italic": False,
            }),
            encoding="utf-8",
        )
        reloaded = SettingsManager()
        self.assertTrue(reloaded.uses_system_ui_font())
        self.assertEqual(reloaded.get_font("ui").family(), system.family())
        self.assertGreaterEqual(int(reloaded.get_font("ui").weight()), 100)
        self.assertEqual(int(reloaded.get_font("editor").weight()), int(QFont.Weight.Normal))
        self.assertEqual(reloaded.get_font("editor").family(), "DejaVu Sans Mono")

        # Older custom UI fonts without the follow flag stay fixed faces.
        Path(manager.settings_file).write_text(
            json.dumps({
                "ui_font_family": "Liberation Sans",
                "ui_font_size": 13,
                "ui_font_weight": 400,
                "ui_font_italic": False,
                "font_family": "DejaVu Sans Mono",
                "font_size": 12,
                "font_weight": 400,
                "font_italic": False,
            }),
            encoding="utf-8",
        )
        custom = SettingsManager()
        self.assertFalse(custom.uses_system_ui_font())
        self.assertEqual(custom.get_font("ui").family(), "Liberation Sans")
        self.assertEqual(custom.get_font("ui").pointSize(), 13)

    def test_settings_manager_drops_legacy_custom_themes(self):
        manager = SettingsManager()
        manager.save_setting("custom_themes", {
            "Forest": {
                "bg": "#102018",
                "text": "#e8f5e9",
                "selection": "#355e3b"
            }
        })
        manager.settings["theme"] = "Forest"
        manager.save_settings()
        manager.save_ui_theme("Dark")

        reloaded = SettingsManager()

        # Only built-in editor themes exist; a saved custom name falls back.
        self.assertEqual(reloaded.get_theme(), ThemeManager.DEFAULT_THEME_NAME)
        # Default Window Color Scheme follows the desktop, so a stale Light/Dark
        # ui_theme is migrated to System on load.
        self.assertEqual(reloaded.get_ui_theme(), "System")
        self.assertNotIn("custom_themes", reloaded.settings)
        reloaded.save_theme("Forest")
        self.assertEqual(reloaded.get_theme(), ThemeManager.DEFAULT_THEME_NAME)
        reloaded.save_theme("Dracula")
        self.assertEqual(reloaded.get_theme(), "Dracula")

        manager.save_ui_theme("Dracula")
        self.assertEqual(manager.get_ui_theme(), "Dark")
        manager.save_ui_theme("Sepia")
        self.assertEqual(manager.get_ui_theme(), "Light")
        manager.save_ui_theme("default")
        self.assertEqual(manager.get_ui_theme(), "System")

    def test_settings_manager_persists_window_color_scheme(self):
        from jottr.window_color_scheme import (
            DEFAULT_WINDOW_COLOR_SCHEME,
            discover_window_color_schemes,
            create_application_palette,
        )

        schemes = discover_window_color_schemes()
        self.assertEqual(schemes[0].scheme_id, DEFAULT_WINDOW_COLOR_SCHEME)
        self.assertEqual(schemes[0].name, "Default")

        manager = SettingsManager()
        self.assertEqual(manager.get_window_color_scheme(), DEFAULT_WINDOW_COLOR_SCHEME)

        named = next((s for s in schemes if s.path), None)
        if named is None:
            self.skipTest("no KDE .colors schemes installed")

        manager.save_window_color_scheme(named.scheme_id)
        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_window_color_scheme(), named.scheme_id)

        palette = create_application_palette(named.path)
        self.assertTrue(palette.color(palette.ColorRole.Window).isValid())
        self.assertTrue(palette.color(palette.ColorRole.Base).isValid())

        manager.save_window_color_scheme("NotARealScheme")
        self.assertEqual(manager.get_window_color_scheme(), DEFAULT_WINDOW_COLOR_SCHEME)

    def test_settings_manager_persists_qt_style(self):
        from PyQt6.QtWidgets import QStyleFactory

        from jottr.qt_style import SYSTEM_QT_STYLE, available_qt_styles, normalize_qt_style

        styles = available_qt_styles()
        self.assertEqual(styles[0], SYSTEM_QT_STYLE)
        for key in QStyleFactory.keys():
            self.assertTrue(
                any(name.casefold() == key.casefold() for name in styles),
                msg=f"missing style {key!r} in {styles}",
            )
        self.assertTrue(any(name.casefold() == "fusion" for name in styles))
        self.assertTrue(any(name.casefold() == "windows" for name in styles))

        manager = SettingsManager()
        self.assertEqual(manager.get_qt_style(), SYSTEM_QT_STYLE)

        fusion = normalize_qt_style("fusion")
        manager.save_qt_style("fusion")
        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_qt_style(), fusion)

        manager.save_qt_style("NotARealStyle")
        self.assertEqual(manager.get_qt_style(), SYSTEM_QT_STYLE)

    def test_settings_manager_persists_icon_theme(self):
        from jottr.icon_manager import DEFAULT_ICON_THEME, list_bundled_icon_themes

        themes = list_bundled_icon_themes()
        self.assertEqual(
            [theme["id"] for theme in themes],
            ["bootstrap", "material", "symbolic"],
        )

        manager = SettingsManager()
        self.assertEqual(manager.get_icon_theme(), DEFAULT_ICON_THEME)

        manager.save_icon_theme("Adwaita")
        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_icon_theme(), "symbolic")

        manager.save_icon_theme("Material Symbols")
        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_icon_theme(), "material")

        manager.save_icon_theme("Bootstrap")
        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_icon_theme(), "bootstrap")

        manager.save_icon_theme("NotARealTheme")
        self.assertEqual(manager.get_icon_theme(), DEFAULT_ICON_THEME)

    def test_settings_manager_persists_toolbar_style(self):
        from jottr.settings_manager import (
            TOOLBAR_STYLE_COMFY,
            TOOLBAR_STYLE_COMPACT,
            SettingsManager,
        )

        manager = SettingsManager()
        self.assertEqual(manager.get_toolbar_style(), TOOLBAR_STYLE_COMFY)

        manager.save_toolbar_style("compact")
        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_toolbar_style(), TOOLBAR_STYLE_COMPACT)

        # Legacy "default" / "native" values migrate to Compact.
        manager.save_toolbar_style("default")
        self.assertEqual(manager.get_toolbar_style(), TOOLBAR_STYLE_COMPACT)
        manager.save_toolbar_style("native")
        self.assertEqual(manager.get_toolbar_style(), TOOLBAR_STYLE_COMPACT)

        manager.save_toolbar_style("Comfy")
        self.assertEqual(manager.get_toolbar_style(), TOOLBAR_STYLE_COMFY)

        manager.save_toolbar_style("nope")
        self.assertEqual(manager.get_toolbar_style(), TOOLBAR_STYLE_COMFY)

    def test_settings_manager_persists_menubar_visibility(self):
        from jottr.settings_manager import SettingsManager

        manager = SettingsManager()
        self.assertTrue(manager.get_menubar_visible())

        manager.save_menubar_visible(False)
        self.assertFalse(SettingsManager().get_menubar_visible())

        manager.save_menubar_visible(True)
        self.assertTrue(SettingsManager().get_menubar_visible())

    def test_apply_qt_style_switches_application_style(self):
        from PyQt6.QtWidgets import QStyleFactory

        from jottr.qt_style import (
            SYSTEM_QT_STYLE,
            apply_qt_style,
            capture_platform_qt_style,
            normalize_qt_style,
            register_bundled_qt_plugins,
        )

        application = app()
        register_bundled_qt_plugins()
        capture_platform_qt_style(application)
        fusion = normalize_qt_style("Fusion")
        self.assertEqual(apply_qt_style(fusion, application), fusion)
        style_name = (application.style().objectName() or "").casefold()
        # Some Qt builds leave Fusion's objectName empty after plugin registration.
        if style_name:
            self.assertEqual(style_name, fusion.casefold())

        apply_qt_style(SYSTEM_QT_STYLE, application)
        self.assertTrue(application.style() is not None)

        if QStyleFactory.create("Adwaita") is not None:
            self.assertEqual(apply_qt_style("Adwaita", application), "Adwaita")
            adwaita_name = (application.style().objectName() or "").casefold()
            self.assertTrue(
                not adwaita_name or "adwaita" in adwaita_name,
                msg=f"unexpected Adwaita style name {adwaita_name!r}",
            )
            dark = ThemeManager.get_theme("Black")
            if QStyleFactory.create("Adwaita-Dark") is not None:
                self.assertEqual(
                    apply_qt_style("Adwaita", application, theme=dark),
                    "Adwaita-Dark",
                )
                self.assertEqual(
                    apply_qt_style("Adwaita-Dark", application, theme=ThemeManager.get_theme("White")),
                    "Adwaita",
                )
            self.assertEqual(apply_qt_style(fusion, application), fusion)

    def test_apply_qt_color_scheme_sets_style_hints(self):
        from PyQt6.QtCore import Qt

        from jottr.qt_style import apply_qt_color_scheme

        application = app()
        if not hasattr(application.styleHints(), "setColorScheme"):
            self.skipTest("QStyleHints.setColorScheme unavailable")

        applied = apply_qt_color_scheme("Dark", application)
        if applied == Qt.ColorScheme.Unknown:
            self.skipTest("platform ignores ColorScheme (e.g. offscreen)")

        self.assertEqual(applied, Qt.ColorScheme.Dark)
        self.assertEqual(
            apply_qt_color_scheme("Light", application),
            Qt.ColorScheme.Light,
        )
        # Follow system → Unknown; colorScheme() then reports the resolved appearance.
        resolved = apply_qt_color_scheme("System", application)
        self.assertIn(resolved, (Qt.ColorScheme.Light, Qt.ColorScheme.Dark))

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
        self.assertIn("White", themes)
        self.assertIn("Black", themes)
        self.assertNotIn("Light", themes)
        self.assertNotIn("Dark", themes)
        self.assertIn("Sepia", themes)
        self.assertIn("Dracula", themes)
        self.assertIn("Monokai", themes)
        self.assertIn("Monaspace", themes)
        self.assertIn("Tokyo Night", themes)
        self.assertIn("Matcha", themes)
        self.assertIn("Darkly", themes)
        darkly = ThemeManager.get_theme("Darkly")
        self.assertEqual(darkly["app"]["accent"], "#3478da")
        self.assertEqual(darkly["editor"]["background"], "#2c2c2c")
        self.assertTrue(ThemeManager.theme_is_dark(ThemeManager.get_theme("Black")))
        self.assertTrue(ThemeManager.theme_is_dark(ThemeManager.get_theme("Dracula")))
        self.assertFalse(ThemeManager.theme_is_dark(ThemeManager.get_theme("White")))
        self.assertFalse(ThemeManager.theme_is_dark(ThemeManager.get_theme("Sepia")))
        self.assertEqual(ThemeManager.normalize_editor_theme_name("Light"), "White")
        self.assertEqual(ThemeManager.normalize_editor_theme_name("Dark"), "Black")
        self.assertEqual(ThemeManager.normalize_editor_theme_name("default"), "Sepia")
        self.assertEqual(ThemeManager.normalize_ui_theme("Dracula"), "Dark")
        self.assertEqual(ThemeManager.normalize_ui_theme("Sepia"), "Light")
        self.assertEqual(ThemeManager.normalize_ui_theme("Darkly"), "Dark")
        self.assertEqual(ThemeManager.normalize_ui_theme("default"), "System")
        self.assertEqual(ThemeManager.normalize_ui_theme("System"), "System")
        self.assertEqual(ThemeManager.UI_THEME_NAMES, ("System", "Light", "Dark"))
        self.assertEqual(ThemeManager.DEFAULT_THEME_NAME, "Sepia")
        self.assertEqual(SettingsManager().get_theme(), "Sepia")
        from PyQt6.QtCore import Qt

        self.assertEqual(
            ThemeManager.ui_theme_color_scheme("System"),
            Qt.ColorScheme.Unknown,
        )
        self.assertEqual(
            ThemeManager.ui_theme_color_scheme("Light"),
            Qt.ColorScheme.Light,
        )
        self.assertEqual(
            ThemeManager.ui_theme_color_scheme("Dark"),
            Qt.ColorScheme.Dark,
        )
        # Color Scheme Light/Dark still resolve to White/Black chrome themes.
        self.assertEqual(
            ThemeManager.get_ui_theme("Light")["editor"]["background"],
            ThemeManager.get_theme("White")["editor"]["background"],
        )
        self.assertEqual(
            ThemeManager.get_ui_theme("Dark")["editor"]["background"],
            ThemeManager.get_theme("Black")["editor"]["background"],
        )
        tile = ThemeManager.build_theme_tile_icon(ThemeManager.get_theme("Dracula"), size=16)
        self.assertFalse(tile.isNull())
        image = tile.pixmap(16, 16).toImage()
        self.assertFalse(image.isNull())
        self.assertEqual(image.pixelColor(2, 2).name(), "#282a36")
        # Longer top text line and shorter bottom line in foreground color.
        self.assertEqual(image.pixelColor(8, 5).name(), "#f8f8f2")
        self.assertEqual(image.pixelColor(5, 10).name(), "#f8f8f2")
        self.assertEqual(image.pixelColor(13, 10).name(), "#282a36")
        self.assertEqual(set(ThemeManager.get_themes()), set(ThemeManager.DEFAULT_THEMES))

        from PyQt6.QtWidgets import QTextEdit

        editor = QTextEdit()
        editor.setFont(QFont("Liberation Serif", 15))
        ThemeManager.apply_theme(editor, "Black")

        style = editor.styleSheet()
        self.assertIn("#111827", style)
        self.assertIn("#e5e7eb", style)
        self.assertIn('font-family: "Liberation Serif"', style)
        self.assertIn("font-size: 15pt", style)

        # Unknown (e.g. removed custom) theme names fall back to the default.
        ThemeManager.apply_theme(editor, "Forest")
        self.assertIn(
            ThemeManager.get_theme(ThemeManager.DEFAULT_THEME_NAME)["editor"]["background"],
            editor.styleSheet(),
        )

        dracula = ThemeManager.get_theme("Dracula")
        self.assertEqual(dracula["editor"]["background"], "#282a36")
        self.assertEqual(dracula["syntax"]["keyword"], "#ff79c6")
        # The main window stylesheet carries layout only: Comfy toolbar
        # spacing and left-aligned tabs, never colors, borders or fonts.
        app_style = ThemeManager.build_app_stylesheet()
        self.assertIn("QToolBar#mainToolBar QToolButton", app_style)
        self.assertIn("padding: 6px 10px", app_style)
        self.assertIn("alignment: left", app_style)
        for property_name in ("background", "border", "color", "font"):
            self.assertNotIn(property_name, app_style)
        compact_toolbar = ThemeManager.build_app_stylesheet(toolbar_style="compact")
        self.assertNotIn("QToolBar#mainToolBar", compact_toolbar)
        self.assertIn("alignment: left", compact_toolbar)
        legacy_default = ThemeManager.build_app_stylesheet(toolbar_style="default")
        self.assertEqual(legacy_default, compact_toolbar)
        for selector in ("QMenuBar", "QMenu", "QStatusBar", "QTreeView", "QSplitter", "QMainWindow"):
            self.assertNotIn(selector, app_style)
        from PyQt6.QtGui import QPalette
        palette = ThemeManager.build_app_palette(dracula)
        self.assertEqual(palette.color(QPalette.ColorRole.Window).name(), "#282a36")
        self.assertEqual(
            palette.color(QPalette.ColorRole.Highlight).name(),
            dracula["app"]["accent"].lower(),
        )
        # Dracula's accent is light, so selected text must be dark for contrast.
        self.assertEqual(palette.color(QPalette.ColorRole.HighlightedText).name(), "#1a1a1a")
        dialog_style = ThemeManager.build_dialog_stylesheet(dracula, QFont("Liberation Serif", 15))
        self.assertNotIn("QComboBox QAbstractItemView", dialog_style)
        self.assertNotIn("QPushButton {", dialog_style)
        self.assertIn("QLabel#fontPreview", dialog_style)
        self.assertIn("#f8f8f2", dialog_style)
        self.assertIn('font-family: "Liberation Serif"', dialog_style)
        font_dialog_style = ThemeManager.build_font_dialog_stylesheet(dracula, QFont("Liberation Serif", 15))
        self.assertNotIn("QFontComboBox::drop-down", font_dialog_style)
        self.assertNotIn("QPushButton {", font_dialog_style)
        self.assertNotIn("QDialog#fontSelectionDialog", font_dialog_style)
        self.assertIn("QLabel#fontPreview", font_dialog_style)
        # Chrome colors come from the app palette, not a forced theme sheet.
        self.assertNotIn("#f8f8f2", font_dialog_style)
        self.assertNotIn("#282a36", font_dialog_style)
        self.assertIn("palette(base)", font_dialog_style)
        self.assertIn("palette(text)", font_dialog_style)
        self.assertIn('font-family: "Liberation Serif"', font_dialog_style)
        self.assertIn("font-size: 15pt", font_dialog_style)
        # Chosen face/size belong only on the preview, not every form label.
        label_block = font_dialog_style.split("QLabel#fontPreview")[0]
        self.assertNotIn("font-family:", label_block)
        self.assertNotIn("font-size:", label_block)


if __name__ == "__main__":
    unittest.main()
