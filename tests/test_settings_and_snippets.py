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
from PyQt6.QtWidgets import QApplication, QStyle

from jottr.bundled_fonts import BUNDLED_FONT_FAMILY, register_bundled_fonts
from jottr.settings_manager import (
    UI_FONT_CUSTOM, UI_FONT_DEFAULT, UI_FONT_SYSTEM, SettingsManager,
)
from jottr.snippet_manager import SnippetManager
from jottr.theme_manager import ThemeManager
import jottr.translation_manager as translation_manager


_APP = None


def app():
    global _APP
    if _APP is None:
        _APP = QApplication.instance() or QApplication(["jottr-tests"])
        # As at startup, so defaults don't depend on the machine's fonts.
        register_bundled_fonts()
    return _APP


class SettingsAndSnippetTests(unittest.TestCase):
    def setUp(self):
        app()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp_dir.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_interface_look_setting_and_organic_chrome(self):
        from PyQt6.QtGui import QColor

        manager = SettingsManager()
        self.addCleanup(ThemeManager.set_interface_look, "native")
        self.addCleanup(ThemeManager.clear_ui_theme_cache)
        # New installs start on Organic with the Marigold accent.
        self.assertEqual(manager.get_interface_look(), "organic")
        self.assertEqual(ThemeManager.interface_look(), "organic")
        self.assertEqual(manager.get_accent(), "marigold")
        self.assertEqual(ThemeManager.accent(), "marigold")

        manager.save_interface_look("native")
        self.assertEqual(manager.get_interface_look(), "native")
        self.assertEqual(ThemeManager.interface_look(), "native")

        manager.save_interface_look("Organic")
        self.assertEqual(manager.get_interface_look(), "organic")
        self.assertEqual(ThemeManager.interface_look(), "organic")
        self.assertEqual(
            ThemeManager.get_ui_theme("Light")["app"]["background"], "#f5ead8"
        )
        self.assertEqual(
            ThemeManager.get_ui_theme("Dark")["app"]["background"], "#2e2e32"
        )
        self.assertIn("organic", ThemeManager.get_ui_theme("Dark"))

        # A fresh manager publishes the saved look again.
        ThemeManager.set_interface_look("native")
        self.assertEqual(SettingsManager().get_interface_look(), "organic")
        self.assertEqual(ThemeManager.interface_look(), "organic")

        manager.save_interface_look("native")
        manager.save_interface_look("bogus")
        self.assertEqual(manager.get_interface_look(), "organic")
        manager.save_interface_look("native")
        self.assertNotIn("organic", ThemeManager.get_ui_theme("Light"))

        self.assertEqual(
            ThemeManager.css_color("rgba(1, 2, 3, 40)"), QColor(1, 2, 3, 40)
        )
        self.assertEqual(ThemeManager.css_color("#c67139"), QColor("#c67139"))
        self.assertFalse(ThemeManager.css_color("rgba(bad)").isValid())

    def test_settings_manager_uses_isolated_config_and_defaults(self):
        manager = SettingsManager()

        self.assertEqual(Path(manager.config_dir), Path(self.temp_dir.name) / "Jottr")
        self.assertTrue(Path(manager.snippets_dir).is_dir())
        self.assertEqual(manager.get_setting("font_size"), 12)
        self.assertEqual(manager.get_setting("font_family"), BUNDLED_FONT_FAMILY)
        self.assertTrue(manager.get_setting("spell_check"))
        self.assertEqual(manager.get_setting("spell_languages"), ["en_US"])
        self.assertEqual(manager.get_setting("document_language"), "auto")
        self.assertEqual(manager.get_setting("icon_contrast"), "auto")
        self.assertEqual(manager.get_icon_theme(), "qlementine")
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
        self.assertEqual(manager.ui_font_source(), UI_FONT_DEFAULT)

        ui_font = QFont("Sans", 11)
        editor_font = QFont("Mono", 14)
        manager.save_font(ui_font, "ui")
        manager.save_font(editor_font, "editor")

        reloaded = SettingsManager()
        self.assertEqual(reloaded.ui_font_source(), UI_FONT_CUSTOM)
        self.assertEqual(reloaded.get_font("ui").family(), "Sans")
        self.assertEqual(reloaded.get_font("ui").pointSize(), 11)
        self.assertEqual(reloaded.get_font("editor").family(), "Mono")
        self.assertEqual(reloaded.get_font("editor").pointSize(), 14)

        manager.save_font(ui_font, "ui", source=UI_FONT_SYSTEM)
        self.assertEqual(SettingsManager().ui_font_source(), UI_FONT_SYSTEM)
        system = SettingsManager.system_ui_font()
        self.assertEqual(manager.get_font("ui").family(), system.family())

        manager.save_font(ui_font, "ui", source=UI_FONT_DEFAULT)
        self.assertEqual(SettingsManager().ui_font_source(), UI_FONT_DEFAULT)
        self.assertEqual(manager.get_font("ui").family(), BUNDLED_FONT_FAMILY)
        # Custom starts from the face the chosen source resolved to.
        self.assertEqual(manager.get_setting("ui_font_family"), BUNDLED_FONT_FAMILY)

    def test_settings_manager_defaults_ui_font_to_bundled_and_coerces_qt5_weight(self):
        manager = SettingsManager()
        system = SettingsManager.system_ui_font()
        ui = manager.get_font("ui")
        self.assertEqual(manager.ui_font_source(), UI_FONT_DEFAULT)
        self.assertEqual(ui.family(), BUNDLED_FONT_FAMILY)
        self.assertEqual(ui.pointSize(), SettingsManager.font_point_size(system, 10))
        self.assertGreaterEqual(int(ui.weight()), 100)
        self.assertEqual(SettingsManager.coerce_font_weight(50), int(QFont.Weight.Normal))
        self.assertEqual(SettingsManager.coerce_font_weight(400), 400)

        # Persisted legacy DejaVu UI default migrates to the bundled font.
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
        self.assertEqual(reloaded.ui_font_source(), UI_FONT_DEFAULT)
        self.assertEqual(reloaded.get_font("ui").family(), BUNDLED_FONT_FAMILY)
        self.assertGreaterEqual(int(reloaded.get_font("ui").weight()), 100)
        self.assertEqual(int(reloaded.get_font("editor").weight()), int(QFont.Weight.Normal))
        # The legacy DejaVu editor default migrates to the system fixed font,
        # keeping the saved size.
        self.assertEqual(
            reloaded.get_font("editor").family(),
            SettingsManager.system_fixed_font().family(),
        )
        self.assertEqual(reloaded.get_font("editor").pointSize(), 12)

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
        self.assertEqual(custom.ui_font_source(), UI_FONT_CUSTOM)
        self.assertEqual(custom.get_font("ui").family(), "Liberation Sans")
        self.assertEqual(custom.get_font("ui").pointSize(), 13)

        # The retired on/off flag maps onto a source: following the desktop
        # (the old default) moves to the bundled face, a chosen face stays.
        for follow, expected in ((True, UI_FONT_DEFAULT), (False, UI_FONT_CUSTOM)):
            Path(manager.settings_file).write_text(
                json.dumps({"ui_font_follow_system": follow, "ui_font_family": "Liberation Sans"}),
                encoding="utf-8",
            )
            migrated = SettingsManager()
            self.assertEqual(migrated.ui_font_source(), expected)
            self.assertNotIn("ui_font_follow_system", migrated.settings)
            self.assertEqual(SettingsManager().ui_font_source(), expected)

    def test_editor_font_defaults_to_bundled_and_keeps_chosen_face(self):
        manager = SettingsManager()
        self.assertEqual(manager.get_font("editor").family(), BUNDLED_FONT_FAMILY)

        # A face the user picked after the migration is never overwritten,
        # even when it matches the retired DejaVu default.
        chosen = QFont("DejaVu Sans Mono", 12)
        manager.save_font(chosen, "editor")
        for _ in range(2):
            reloaded = SettingsManager()
            self.assertEqual(reloaded.get_font("editor").family(), "DejaVu Sans Mono")
            self.assertEqual(reloaded.get_font("editor").pointSize(), 12)

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
        # Color Scheme is a user choice; Light/Dark survive a reload.
        self.assertEqual(reloaded.get_ui_theme(), "Dark")
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

    def test_settings_manager_drops_retired_scheme_and_style_settings(self):
        manager = SettingsManager()
        self.assertNotIn("window_color_scheme", manager.settings)
        self.assertNotIn("qt_style", manager.settings)

        # A named KDE scheme becomes the Light or Dark it looked like.
        for scheme_id, expected in (("BreezeDark", "Dark"), ("BreezeLight", "Light")):
            manager.settings.update(
                {"window_color_scheme": scheme_id, "qt_style": "Windows", "ui_theme": "System"}
            )
            manager.save_settings()
            migrated = SettingsManager()
            self.assertEqual(migrated.get_ui_theme(), expected)
            self.assertNotIn("window_color_scheme", migrated.settings)
            self.assertNotIn("qt_style", migrated.settings)
            manager = migrated

        # Default ("") keeps the Color Scheme as it was.
        manager.settings.update({"window_color_scheme": "", "ui_theme": "System"})
        manager.save_settings()
        self.assertEqual(SettingsManager().get_ui_theme(), "System")

    def test_settings_manager_persists_icon_theme(self):
        from jottr.icon_manager import DEFAULT_ICON_THEME, list_bundled_icon_themes

        themes = list_bundled_icon_themes()
        self.assertEqual(
            [theme["id"] for theme in themes],
            ["bootstrap", "material", "qlementine", "symbolic"],
        )

        manager = SettingsManager()
        self.assertEqual(manager.get_icon_theme(), DEFAULT_ICON_THEME)

        manager.save_icon_theme("Adwaita")
        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_icon_theme(), "symbolic")

        manager.save_icon_theme("Material Symbols")
        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_icon_theme(), "material")

        manager.save_icon_theme("Qlementine")
        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_icon_theme(), "qlementine")

        manager.save_icon_theme("Bootstrap")
        reloaded = SettingsManager()
        self.assertEqual(reloaded.get_icon_theme(), "bootstrap")

        manager.save_icon_theme("NotARealTheme")
        self.assertEqual(manager.get_icon_theme(), DEFAULT_ICON_THEME)

    def test_settings_manager_persists_menubar_visibility(self):
        from jottr.settings_manager import SettingsManager

        manager = SettingsManager()
        self.assertTrue(manager.get_menubar_visible())

        manager.save_menubar_visible(False)
        self.assertFalse(SettingsManager().get_menubar_visible())

        manager.save_menubar_visible(True)
        self.assertTrue(SettingsManager().get_menubar_visible())

    def test_apply_qt_style_installs_fusion_once(self):
        from jottr.qt_style import APP_QT_STYLE, apply_qt_style

        application = app()
        application.setProperty("_jottr_style_key", None)
        self.assertEqual(APP_QT_STYLE, "Fusion")
        self.assertTrue(apply_qt_style(application))
        self.assertEqual(application.style().baseStyle().name().casefold(), "fusion")
        self.assertEqual(application.property("_jottr_style_key"), "Fusion")
        # Dialog buttons never carry icons, whatever the platform theme says.
        self.assertEqual(
            application.style().styleHint(QStyle.StyleHint.SH_DialogButtonBox_ButtonsHaveIcons),
            0,
        )
        # Already installed: no second swap (and no repolish).
        self.assertFalse(apply_qt_style(application))

    def test_menus_enable_translucent_background_for_rounded_corners(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QImage, QPainter
        from PyQt6.QtWidgets import QMenu

        from jottr.qt_style import apply_qt_style
        from jottr.theme_manager import ThemeManager

        application = app()
        apply_qt_style(application)

        menu = QMenu()
        menu.addAction("Test Item")
        # The style sets it at polish, which show() runs before the popup's
        # native window exists.
        menu.ensurePolished()
        self.assertTrue(
            menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        )

        # In Organic look, corners outside the 14px border radius must render transparent (alpha == 0)
        t = ThemeManager.ORGANIC_THEMES["Dark"]["organic"]
        menu.setStyleSheet(
            f"QMenu {{ background: {t['pane']}; border: 1px solid {t['line']}; border-radius: 14px; padding: 6px; }}"
        )
        menu.adjustSize()
        img = QImage(menu.size(), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        menu.render(p)
        p.end()

        # Corner pixel (0, 0) must be transparent so it doesn't show sharp corners against the editor
        self.assertEqual(img.pixelColor(0, 0).alpha(), 0)
        # Inside the menu (e.g. (15, 15)) must be opaque
        self.assertEqual(img.pixelColor(15, 15).alpha(), 255)

    def test_combo_popups_follow_the_organic_look(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QComboBox

        from jottr.qt_style import ComboItemDelegate, apply_qt_style
        from jottr.theme_manager import ThemeManager

        application = app()
        apply_qt_style(application)
        previous_look = ThemeManager.interface_look()
        previous_sheet = application.styleSheet()
        self.addCleanup(ThemeManager.set_interface_look, previous_look)
        self.addCleanup(application.setStyleSheet, previous_sheet)
        ThemeManager.set_interface_look("organic")
        application.setStyleSheet(
            ThemeManager.build_app_stylesheet(ThemeManager.organic_theme(True))
        )

        combo = QComboBox()
        combo.addItems(["Bootstrap", "Qlementine"])
        combo.ensurePolished()
        self.assertIsInstance(combo.itemDelegate(), ComboItemDelegate)
        # Its popup is a top-level window like QMenu's, so its corners
        # outside the rounded list must be see-through.
        container = combo.view().window()
        container.ensurePolished()
        self.assertTrue(
            container.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        )
        # Padding on the rows must not trip Qt's menu-item sizing, which
        # makes each row thousands of pixels tall.
        self.assertLess(combo.view().sizeHintForRow(0), 60)

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

        self.assertEqual(reloaded.get_setting("font_family"), BUNDLED_FONT_FAMILY)

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
        self.assertIn("Catppuccin Latte", themes)
        self.assertIn("Nord", themes)
        self.assertNotIn("Darkly", themes)
        # Darkly was replaced by Nord; a saved Darkly pick moves over.
        self.assertEqual(ThemeManager.normalize_editor_theme_name("Darkly"), "Nord")
        self.assertEqual(ThemeManager.get_theme("Nord")["editor"]["background"], "#2e3440")
        self.assertFalse(ThemeManager.theme_is_dark(ThemeManager.get_theme("Catppuccin Latte")))
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
        # The chrome checks below are for the Native look.
        ThemeManager.set_interface_look("native")
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
        self.assertIn("#0a0a0a", style)
        self.assertIn("#e6e6e6", style)
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
        # The main window stylesheet carries layout only: left-aligned tabs
        # plus borderless chrome, never colors or fonts.
        app_style = ThemeManager.build_app_stylesheet()
        self.assertNotIn("QToolBar#mainToolBar", app_style)
        self.assertIn("alignment: left", app_style)
        self.assertIn("QMenuBar", app_style)
        self.assertIn("border: none", app_style)
        for property_name in ("background", "color", "font"):
            self.assertNotIn(property_name, app_style)
        for selector in ("QMenu {", "QMenu::", "QStatusBar", "QTreeView", "QSplitter"):
            self.assertNotIn(selector, app_style)
        # Organic is the one look that paints colors, from its theme tokens.
        organic = ThemeManager.organic_theme(False)
        organic_style = ThemeManager.build_app_stylesheet(theme=organic)
        self.assertTrue(organic_style.startswith(app_style))
        self.assertIn("background: #f5ead8", organic_style)
        self.assertIn("QMenu {", organic_style)
        self.assertEqual(ThemeManager.build_app_stylesheet(theme=dracula), app_style)
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
