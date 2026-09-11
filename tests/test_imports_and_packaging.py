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
        for path in PACKAGE_DIR.glob("*.py"):
            with self.subTest(path=path.name):
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
        for path in PACKAGE_DIR.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for marker in ("PyQt5", "qt_compat", "install_qt5_aliases"):
                if marker in text:
                    offenders.append(f"{path.name}: {marker}")

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
        for path in PACKAGE_DIR.glob("*.py"):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                for module in flat_modules:
                    if stripped.startswith(f"from {module} import ") or stripped == f"import {module}":
                        offenders.append(f"{path.name}:{line_no}: {stripped}")
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
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, gitignore)

    def test_release_pyinstaller_bundles_package_modules(self):
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "release-please.yml").read_text(
            encoding="utf-8"
        )
        appimage_script = (PROJECT_ROOT / "scripts" / "build-appimage-local.sh").read_text(
            encoding="utf-8"
        )

        package_modules = (
            "jottr",
            "jottr.editor_tab",
            "jottr.feed_manager_dialog",
            "jottr.font_dialog",
            "jottr.icon_manager",
            "jottr.paths",
            "jottr.plugin_manager",
            "jottr.rss_reader",
            "jottr.rss_tab",
            "jottr.settings_dialog",
            "jottr.settings_manager",
            "jottr.snippet_editor_dialog",
            "jottr.snippet_manager",
            "jottr.theme_manager",
            "jottr.translation_manager",
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


if __name__ == "__main__":
    unittest.main()
