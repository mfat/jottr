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
        from jottr import main
        from jottr import settings_dialog
        from jottr import settings_manager
        from jottr import snippet_editor_dialog
        from jottr import snippet_manager
        from jottr import theme_manager

        self.assertEqual(main.APP_NAME, "Jottr")
        from jottr import __version__

        self.assertEqual(main.APP_VERSION, __version__)

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
            "font_dialog",
            "icon_manager",
            "plugin_manager",
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
            "/release-assets-build/",
            "/squashfs-root/",
            "packaging/debian/jottr/",
            "/deb_dist",
            "src/jottr/jottr.spec",
        ):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, gitignore)

    def test_adwaita_qt_is_not_vendored(self):
        self.assertFalse((PROJECT_ROOT / "vendor" / "adwaita-qt").exists())
        self.assertFalse((PROJECT_ROOT / "scripts" / "build-adwaita-qt.sh").exists())
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn("qt_plugins/**/*", pyproject)
        flatpak = (PROJECT_ROOT / "io.github.mfat.jottr.yml").read_text(encoding="utf-8")
        self.assertNotIn("adwaita-qt", flatpak)
        self.assertNotIn("vendor/adwaita-qt", flatpak)
        rpm_spec = (PROJECT_ROOT / "rpm.spec").read_text(encoding="utf-8")
        self.assertNotIn("build-adwaita-qt.sh", rpm_spec)
        self.assertIn("BuildArch:      noarch", rpm_spec)
        debian_control = (PROJECT_ROOT / "packaging" / "debian" / "control").read_text(
            encoding="utf-8"
        )
        self.assertIn("Architecture: all", debian_control)
        self.assertNotIn("qt6-base-dev", debian_control)

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
            "jottr.font_dialog",
            "jottr.file_dialogs",
            "jottr.icon_manager",
            "jottr.resources",
            "jottr.paths",
            "jottr.plugin_manager",
            "jottr.qt_style",
            "jottr.window_color_scheme",
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

        # The rss-feed plugin imports these from the host app; nothing in
        # jottr does, so PyInstaller would otherwise leave them out.
        for module in ("feedparser", "requests"):
            with self.subTest(module=module):
                self.assertIn(f"--hidden-import {module}", workflow)
                self.assertIn(f"--hidden-import {module}", appimage_script)

        self.assertIn("--paths src", workflow)
        self.assertIn("--paths src", appimage_script)
        # pyspellchecker has no PyInstaller hook; without this its dictionaries
        # are missing and spell checking silently does nothing in frozen builds.
        dmg_script = (PROJECT_ROOT / "packaging" / "macos" / "build-dmg.sh").read_text(
            encoding="utf-8"
        )
        for text in (workflow, appimage_script, dmg_script):
            self.assertIn("--collect-data spellchecker", text)
            # Frozen bundles carry no system CA store; without certifi's
            # cacert.pem plugin downloads fail to verify any certificate.
            self.assertIn("--hidden-import certifi", text)
            self.assertIn("--collect-data certifi", text)
        self.assertIn("src/jottr/main.py", workflow)
        self.assertIn("src/jottr/main.py", appimage_script)
        self.assertNotIn("src/jottr/__main__.py", workflow)
        self.assertNotIn("src/jottr/__main__.py", appimage_script)
        self.assertIn("APPIMAGE_EXTRACT_AND_RUN=1", appimage_script)
        self.assertIn('--add-data "src/jottr/resources:jottr/resources"', workflow)
        self.assertIn('--add-data "src/jottr/resources:jottr/resources"', appimage_script)
        self.assertIn('--add-data "icons:icons"', workflow)
        self.assertIn('--add-data "icons:icons"', appimage_script)
        self.assertIn('--add-data "translations:translations"', workflow)
        self.assertIn('--add-data "translations:translations"', appimage_script)
        self.assertNotIn("qt_plugins", workflow)
        self.assertNotIn("qt_plugins", appimage_script)
        self.assertNotIn("build-adwaita-qt.sh", workflow)
        self.assertNotIn("build-adwaita-qt.sh", appimage_script)

    def test_windows_release_packaging(self):
        windows_script = (
            PROJECT_ROOT / "packaging" / "windows" / "build-installer.ps1"
        ).read_text(encoding="utf-8")
        inno_script = (PROJECT_ROOT / "packaging" / "windows" / "jottr.iss").read_text(
            encoding="utf-8"
        )
        dispatch = (PROJECT_ROOT / ".github" / "workflows" / "build-windows.yml").read_text(
            encoding="utf-8"
        )
        release = (PROJECT_ROOT / ".github" / "workflows" / "release-please.yml").read_text(
            encoding="utf-8"
        )
        debian_rules = (PROJECT_ROOT / "packaging" / "debian" / "rules").read_text(
            encoding="utf-8"
        )
        rpm_spec = (PROJECT_ROOT / "rpm.spec").read_text(encoding="utf-8")

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
            "jottr.font_dialog",
            "jottr.file_dialogs",
            "jottr.icon_manager",
            "jottr.resources",
            "jottr.paths",
            "jottr.plugin_manager",
            "jottr.qt_style",
            "jottr.window_color_scheme",
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
            "pyenchant",
            "feedparser",
            "requests",
        )
        for module in package_modules:
            with self.subTest(module=module):
                self.assertIn(f"--hidden-import={module}", windows_script)

        self.assertIn("--paths=src", windows_script)
        self.assertIn("--collect-data=spellchecker", windows_script)
        self.assertIn("--hidden-import=certifi", windows_script)
        self.assertIn("--collect-data=certifi", windows_script)
        self.assertIn("--exclude-module=enchant", windows_script)
        self.assertIn("--icon=src/jottr/jottr_icon.ico", windows_script)
        self.assertIn("src/jottr/main.py", windows_script)
        self.assertNotIn("src/jottr/__main__.py", windows_script)
        for spec in (
            "src/jottr/help:jottr/help",
            "src/jottr/icons:jottr/icons",
            "src/jottr/resources:jottr/resources",
            "icons:icons",
            "translations:translations",
        ):
            with self.subTest(spec=spec):
                self.assertIn(f"--add-data={spec}", windows_script)
        self.assertIn("QtWebEngineProcess.exe", windows_script)
        self.assertIn("jottr.iss", windows_script)
        self.assertNotIn("qt_plugins", windows_script)

        self.assertTrue((PACKAGE_DIR / "jottr_icon.ico").is_file())
        self.assertIn("SetupIconFile", inno_script)
        self.assertIn("jottr_icon.ico", inno_script)
        self.assertIn("dist\\Jottr\\*", inno_script)
        self.assertIn("PrivilegesRequired=lowest", inno_script)
        self.assertIn("windows-x86_64-unsigned", inno_script)
        self.assertIn("windows-x86_64-unsigned", windows_script)

        self.assertIn("workflow_dispatch", dispatch)
        self.assertIn("packaging/windows/build-installer.ps1", dispatch)
        self.assertIn("packaging/windows/build-installer.ps1", release)
        self.assertIn("build-windows:", release)
        self.assertIn("choco install innosetup", dispatch)
        self.assertIn("choco install innosetup", release)

        self.assertIn("jottr_icon.ico", debian_rules)
        self.assertIn("jottr_icon.ico", rpm_spec)

    def test_flathub_release_workflow_updates_manifest(self):
        workflow = (PROJECT_ROOT / ".github" / "workflows" / "flathub.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("flathub/io.github.mfat.jottr", workflow)
        self.assertIn("secrets.FLATHUB_TOKEN", workflow)
        self.assertIn("peter-evans/create-pull-request@v6", workflow)
        self.assertIn("io.github.mfat.jottr.yml", workflow)
        self.assertIn("Update pinned commit in manifest", workflow)
        self.assertNotIn("pypi-dependencies.yaml", workflow)
        self.assertNotIn("io.github.mfat.jottr.metainfo.xml", workflow)
        self.assertNotIn("type: dir", workflow)

    def test_symbolic_icons_use_qt_resources(self):
        from PyQt6.QtWidgets import QApplication

        from jottr.icon_manager import (
            DEFAULT_ICON_THEME,
            build_themed_icon,
            list_bundled_icon_themes,
            load_bundled_icon_paths,
            normalize_icon_theme,
            resolve_icon_mode_colors,
        )

        # Keep a strong reference; QPixmap requires a live QGuiApplication.
        app = QApplication.instance()
        if app is None:
            app = QApplication(["jottr-tests"])

        themes = list_bundled_icon_themes()
        self.assertEqual(
            [theme["id"] for theme in themes],
            ["bootstrap", "material", "qlementine", "symbolic"],
        )
        self.assertEqual(themes[0]["label"], "Bootstrap")
        self.assertEqual(themes[1]["label"], "Material Symbols")
        self.assertEqual(themes[2]["label"], "Qlementine")
        self.assertEqual(themes[3]["label"], "Adwaita")
        self.assertEqual(normalize_icon_theme("Adwaita"), "symbolic")
        self.assertEqual(normalize_icon_theme("Bootstrap"), "bootstrap")
        self.assertEqual(normalize_icon_theme("Material Symbols"), "material")
        self.assertEqual(normalize_icon_theme("material"), "material")
        self.assertEqual(normalize_icon_theme("Qlementine"), "qlementine")
        self.assertEqual(normalize_icon_theme("qlementine"), "qlementine")
        self.assertEqual(normalize_icon_theme("missing"), DEFAULT_ICON_THEME)
        self.assertEqual(DEFAULT_ICON_THEME, "qlementine")

        icons = load_bundled_icon_paths("symbolic")

        self.assertIn("save", icons)
        self.assertIn("tab-close", icons)
        self.assertIn("theme", icons)
        self.assertIn("brush-monitor-symbolic", icons)
        self.assertTrue(icons["save"].startswith(":/icons/symbolic/"))
        self.assertTrue(icons["tab-close"].startswith(":/icons/symbolic/"))
        self.assertEqual(icons["theme"], ":/icons/symbolic/theme.svg")
        self.assertEqual(
            icons["brush-monitor-symbolic"],
            ":/icons/symbolic/brush-monitor-symbolic.svg",
        )
        self.assertNotEqual(icons["save"], icons["menu"])

        tinted = build_themed_icon(icons["save"], "#f8f8f2", size=16)
        self.assertFalse(tinted.isNull())
        selected_color, disabled_color = resolve_icon_mode_colors(None)
        self.assertIsNone(selected_color)
        self.assertIsNone(disabled_color)
        selected = build_themed_icon(
            icons["save"],
            "#17202a",
            size=16,
            selected_color="#ffffff",
            disabled_color="#566273",
        )
        from PyQt6.QtGui import QIcon

        self.assertFalse(selected.pixmap(16, QIcon.Mode.Selected).isNull())
        self.assertFalse(selected.pixmap(16, QIcon.Mode.Disabled).isNull())
        self.assertTrue((PROJECT_ROOT / "icons" / "symbolic.qrc").is_file())
        self.assertTrue(
            (PACKAGE_DIR / "resources" / "icons_symbolic.rcc").is_file()
        )

        bootstrap = load_bundled_icon_paths("bootstrap")
        self.assertIn("save", bootstrap)
        self.assertIn("snippets", bootstrap)
        self.assertIn("markdown", bootstrap)
        self.assertIn("theme", bootstrap)
        self.assertIn("brush", bootstrap)
        self.assertIn("palette", bootstrap)
        self.assertTrue(bootstrap["save"].startswith(":/icons/bootstrap/"))
        self.assertTrue(bootstrap["tab-close"].startswith(":/icons/bootstrap/"))
        self.assertEqual(bootstrap["theme"], ":/icons/bootstrap/theme.svg")
        self.assertEqual(bootstrap["brush"], ":/icons/bootstrap/brush.svg")
        self.assertEqual(bootstrap["palette"], ":/icons/bootstrap/palette.svg")
        self.assertNotEqual(bootstrap["save"], icons["save"])
        self.assertNotEqual(bootstrap["theme"], icons["theme"])
        bootstrap_tinted = build_themed_icon(bootstrap["theme"], "#f8f8f2", size=16)
        self.assertFalse(bootstrap_tinted.isNull())
        self.assertTrue((PROJECT_ROOT / "icons" / "bootstrap.qrc").is_file())
        self.assertTrue(
            (PACKAGE_DIR / "resources" / "icons_bootstrap.rcc").is_file()
        )

        material = load_bundled_icon_paths("material")
        self.assertIn("save", material)
        self.assertIn("snippets", material)
        self.assertIn("markdown", material)
        self.assertIn("theme", material)
        self.assertIn("brush", material)
        self.assertIn("palette", material)
        self.assertTrue(material["save"].startswith(":/icons/material/"))
        self.assertTrue(material["tab-close"].startswith(":/icons/material/"))
        self.assertEqual(material["theme"], ":/icons/material/theme.svg")
        self.assertEqual(material["brush"], ":/icons/material/brush.svg")
        self.assertEqual(material["palette"], ":/icons/material/palette.svg")
        self.assertNotEqual(material["save"], icons["save"])
        self.assertNotEqual(material["save"], bootstrap["save"])
        material_tinted = build_themed_icon(material["theme"], "#f8f8f2", size=16)
        self.assertFalse(material_tinted.isNull())
        self.assertTrue((PROJECT_ROOT / "icons" / "material.qrc").is_file())
        self.assertTrue(
            (PACKAGE_DIR / "resources" / "icons_material.rcc").is_file()
        )

        qlementine = load_bundled_icon_paths("qlementine")
        self.assertIn("save", qlementine)
        self.assertIn("snippets", qlementine)
        self.assertIn("markdown", qlementine)
        self.assertIn("theme", qlementine)
        self.assertIn("brush", qlementine)
        self.assertIn("palette", qlementine)
        self.assertTrue(qlementine["save"].startswith(":/icons/qlementine/"))
        self.assertTrue(qlementine["tab-close"].startswith(":/icons/qlementine/"))
        self.assertEqual(qlementine["theme"], ":/icons/qlementine/theme.svg")
        self.assertEqual(qlementine["brush"], ":/icons/qlementine/brush.svg")
        self.assertEqual(qlementine["palette"], ":/icons/qlementine/palette.svg")
        self.assertNotEqual(qlementine["save"], icons["save"])
        self.assertNotEqual(qlementine["save"], bootstrap["save"])
        qlementine_tinted = build_themed_icon(qlementine["theme"], "#f8f8f2", size=16)
        self.assertFalse(qlementine_tinted.isNull())
        self.assertTrue((PROJECT_ROOT / "icons" / "qlementine.qrc").is_file())
        self.assertTrue(
            (PACKAGE_DIR / "resources" / "icons_qlementine.rcc").is_file()
        )
        self.assertIsNotNone(app)

    def test_app_icon_loads_from_jottr_svg(self):
        from PyQt6.QtWidgets import QApplication

        from jottr.icon_manager import load_app_icon, resolve_app_icon_path

        app = QApplication.instance()
        if app is None:
            app = QApplication(["jottr-tests"])

        path = resolve_app_icon_path()
        self.assertIsNotNone(path)
        self.assertTrue(path.endswith("jottr.svg"))
        self.assertTrue((PROJECT_ROOT / "icons" / "jottr.svg").is_file())

        icon = load_app_icon()
        self.assertFalse(icon.isNull())
        self.assertFalse(icon.pixmap(64, 64).isNull())
        self.assertIsNotNone(app)

    def test_linux_packaging_installs_scalable_svg_icon(self):
        rpm_spec = (PROJECT_ROOT / "rpm.spec").read_text(encoding="utf-8")
        debian_rules = (PROJECT_ROOT / "packaging" / "debian" / "rules").read_text(
            encoding="utf-8"
        )
        flatpak = (PROJECT_ROOT / "io.github.mfat.jottr.yml").read_text(encoding="utf-8")
        appimage = (PROJECT_ROOT / "scripts" / "build-appimage-local.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn("hicolor/scalable/apps", rpm_spec)
        self.assertIn("icons/jottr.svg", rpm_spec)
        self.assertIn("io.github.mfat.jottr.desktop", rpm_spec)
        self.assertIn("io.github.mfat.jottr.svg", rpm_spec)
        self.assertNotIn("hicolor/256x256/apps/%{name}.png", rpm_spec)

        self.assertIn("hicolor/scalable/apps", debian_rules)
        self.assertIn("io.github.mfat.jottr.desktop", debian_rules)
        self.assertIn("io.github.mfat.jottr.svg", debian_rules)

        self.assertIn(
            "hicolor/scalable/apps/io.github.mfat.jottr.svg",
            flatpak,
        )
        self.assertNotIn("jottr_icon_256x256.png", flatpak)

        self.assertIn("hicolor/scalable/apps", appimage)
        self.assertIn("icons/jottr.svg", appimage)
        self.assertIn("io.github.mfat.jottr.desktop", appimage)
        self.assertNotIn("icons/jottr.png", appimage)

        self.assertTrue((PROJECT_ROOT / "icons" / "jottr-symbolic.svg").is_file())
        symbolic = "hicolor/symbolic/apps/io.github.mfat.jottr-symbolic.svg"
        for packaging in (rpm_spec, debian_rules, flatpak, appimage):
            self.assertIn(symbolic, packaging)

        desktop = (PROJECT_ROOT / "io.github.mfat.jottr.desktop").read_text(
            encoding="utf-8"
        )
        self.assertIn("Icon=io.github.mfat.jottr", desktop)
        self.assertIn("StartupWMClass=Jottr", desktop)

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
            self.assertTrue(icons[name].startswith(":/icons/qlementine/"))

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
