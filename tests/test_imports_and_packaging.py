import os
import py_compile
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
PACKAGE_DIR = SRC_ROOT / "jottr"
sys.path.insert(0, str(SRC_ROOT))


class ImportAndPackagingTests(unittest.TestCase):
    def test_source_files_compile(self):
        for path in PACKAGE_DIR.rglob("*.py"):
            with self.subTest(path=str(path.relative_to(PACKAGE_DIR))):
                py_compile.compile(str(path), doraise=True)

    def test_core_modules_import(self):
        from jottr import editor_tab
        from jottr import feed_manager_dialog
        from jottr import main
        from jottr import rss_reader
        from jottr import settings_dialog
        from jottr import settings_manager
        from jottr import snippet_editor_dialog
        from jottr import snippet_manager
        from jottr import theme_manager

        self.assertEqual(main.APP_NAME, "Jottr")
        self.assertEqual(main.APP_VERSION, "2.2.1")

    def test_package_entry_points_exist(self):
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('jottr = "jottr.main:main"', pyproject)
        self.assertIn('package-dir = {"" = "src"}', pyproject)
        self.assertTrue((PACKAGE_DIR / "__main__.py").is_file())

    def test_no_qt5_compatibility_references_remain(self):
        offenders = []
        for path in PACKAGE_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for marker in ("PyQt5", "qt_compat", "install_qt5_aliases"):
                if marker in text:
                    offenders.append(f"{path.relative_to(PACKAGE_DIR)}: {marker}")

        self.assertEqual(offenders, [])

    def test_no_flat_internal_imports_remain(self):
        offenders = []
        flat_modules = (
            "editor_tab",
            "feed_manager_dialog",
            "font_dialog",
            "icon_manager",
            "plugin_manager",
            "rss_reader",
            "rss_tab",
            "settings_dialog",
            "settings_manager",
            "snippet_editor_dialog",
            "snippet_manager",
            "theme_manager",
            "translation_manager",
            "paths",
        )
        for path in PACKAGE_DIR.rglob("*.py"):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                for module in flat_modules:
                    if stripped.startswith(f"from {module} import ") or stripped == f"import {module}":
                        offenders.append(f"{path.relative_to(PACKAGE_DIR)}:{line_no}: {stripped}")
        self.assertEqual(offenders, [])

    def test_generated_artifacts_are_ignored(self):
        gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

        for pattern in (
            "__pycache__/",
            "*.pyc",
            "*.egg-info/",
            "/AppDir/",
            "/appimagetool",
            "/release-assets-local/",
            "/squashfs-root/",
            "packaging/debian/jottr/",
            "/deb_dist",
            "src/jottr/jottr.spec",
            "src/jottr/qt_plugins/",
            "vendor/adwaita-qt/build/",
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, gitignore)

    def test_vendored_adwaita_qt_is_present(self):
        vendor = PROJECT_ROOT / "vendor" / "adwaita-qt"
        self.assertTrue((vendor / "CMakeLists.txt").is_file())
        self.assertTrue((vendor / "ATTRIBUTION.md").is_file())
        self.assertTrue((PROJECT_ROOT / "scripts" / "build-adwaita-qt.sh").is_file())
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("qt_plugins/**/*", pyproject)
        flatpak = (PROJECT_ROOT / "io.github.mfat.jottr.yml").read_text(encoding="utf-8")
        self.assertIn("adwaita-qt", flatpak)
        self.assertIn("vendor/adwaita-qt", flatpak)

    def test_register_bundled_qt_plugins_is_noop_without_tree(self):
        from jottr.qt_style import register_bundled_qt_plugins

        # Missing styles/ directories are ignored; must not raise.
        registered = register_bundled_qt_plugins()
        self.assertIsInstance(registered, list)

    def test_release_pyinstaller_bundles_package_modules(self):
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "release-please.yml").read_text(
            encoding="utf-8"
        )
        appimage_script = (PROJECT_ROOT / "scripts" / "build-appimage-local.sh").read_text(
            encoding="utf-8"
        )

        package_modules = (
            "jottr",
            "jottr.editor",
            "jottr.editor.browser",
            "jottr.editor.find_replace",
            "jottr.editor.focus_mode",
            "jottr.editor.markdown",
            "jottr.editor.spellcheck",
            "jottr.editor.tab",
            "jottr.editor.text_edit",
            "jottr.editor_tab",
            "jottr.feed_manager_dialog",
            "jottr.font_dialog",
            "jottr.icon_manager",
            "jottr.resources",
            "jottr.resources.rc_symbolic_icons",
            "jottr.paths",
            "jottr.plugin_manager",
            "jottr.qt_style",
            "jottr.rss_reader",
            "jottr.rss_tab",
            "jottr.settings_dialog",
            "jottr.settings_manager",
            "jottr.snippet_editor_dialog",
            "jottr.snippet_manager",
            "jottr.theme_manager",
            "jottr.translation_manager",
            "jottr.ui",
            "jottr.ui.document_tab_bar",
            "jottr.ui.workspace",
            "jottr.ui.workspace_controller",
            "jottr.window",
            "spellchecker",
        )

        for module in package_modules:
            with self.subTest(module=module):
                self.assertIn(f"--hidden-import {module}", workflow)
                self.assertIn(f"--hidden-import {module}", appimage_script)

        self.assertIn("--paths src", workflow)
        self.assertIn("--paths src", appimage_script)
        self.assertIn("src/jottr/__main__.py", workflow)
        self.assertIn("src/jottr/__main__.py", appimage_script)
        self.assertIn("APPIMAGE_EXTRACT_AND_RUN=1", appimage_script)
        self.assertIn('--add-data "icons:icons"', workflow)
        self.assertIn('--add-data "icons:icons"', appimage_script)
        self.assertIn('--add-data "translations:translations"', workflow)
        self.assertIn('--add-data "translations:translations"', appimage_script)
        self.assertIn('--add-data "src/jottr/qt_plugins:jottr/qt_plugins"', workflow)
        self.assertIn('--add-data "src/jottr/qt_plugins:jottr/qt_plugins"', appimage_script)
        self.assertIn("build-adwaita-qt.sh", workflow)
        self.assertIn("build-adwaita-qt.sh", appimage_script)

    def test_symbolic_icons_use_qt_resources(self):
        from PyQt6.QtWidgets import QApplication

        from jottr.icon_manager import build_themed_icon, load_bundled_icon_paths

        # Keep a strong reference; QPixmap requires a live QGuiApplication.
        app = QApplication.instance()
        if app is None:
            app = QApplication(["jottr-tests"])

        icons = load_bundled_icon_paths()

        self.assertIn("save", icons)
        self.assertIn("tab-close", icons)
        self.assertTrue(icons["save"].startswith(":/icons/symbolic/"))
        self.assertTrue(icons["tab-close"].startswith(":/icons/symbolic/"))
        self.assertNotEqual(icons["save"], icons["menu"])

        tinted = build_themed_icon(icons["save"], "#f8f8f2", size=16)
        self.assertFalse(tinted.isNull())
        self.assertTrue((PROJECT_ROOT / "icons" / "symbolic.qrc").is_file())
        self.assertTrue(
            (PACKAGE_DIR / "resources" / "rc_symbolic_icons.py").is_file()
        )
        self.assertIsNotNone(app)

    def test_message_box_uses_bundled_button_icons(self):
        from PyQt6.QtCore import QSize
        from PyQt6.QtWidgets import QApplication, QMessageBox

        from jottr.icon_manager import apply_message_box_icons, load_bundled_icon_paths

        app = QApplication.instance()
        if app is None:
            app = QApplication(["jottr-tests"])

        icons = load_bundled_icon_paths()
        for name in ("dialog-question", "user-trash", "window-close", "save"):
            self.assertIn(name, icons)
            self.assertTrue(icons[name].startswith(":/icons/symbolic/"))

        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        apply_message_box_icons(box)

        self.assertFalse(box.iconPixmap().isNull())
        self.assertEqual(box.iconPixmap().size(), QSize(48, 48))
        for standard in (
            QMessageBox.StandardButton.Save,
            QMessageBox.StandardButton.Discard,
            QMessageBox.StandardButton.Cancel,
        ):
            button = box.button(standard)
            self.assertIsNotNone(button)
            self.assertFalse(button.icon().isNull())
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
