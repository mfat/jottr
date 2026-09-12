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

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStyleHints
from PyQt6.QtWidgets import QApplication, QStyleFactory

import jottr.system_color_scheme as system_color_scheme_module
from jottr.system_color_scheme import (
    _scheme_from_portal_value,
    _unwrap_dbus_variant,
    clear_system_color_scheme_cache,
    gtk_color_scheme,
    system_color_scheme,
    system_prefers_dark,
)
from jottr.theme_manager import ThemeManager


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


class _FakeVariant:
    """Stand-in for QDBusVariant, which nests one level per Read() wrapper."""

    def __init__(self, value):
        self._value = value

    def variant(self):
        return self._value


class PortalValueTests(unittest.TestCase):
    def test_color_scheme_values_map_to_qt(self):
        self.assertEqual(_scheme_from_portal_value(1), Qt.ColorScheme.Dark)
        self.assertEqual(_scheme_from_portal_value(2), Qt.ColorScheme.Light)
        self.assertEqual(_scheme_from_portal_value(0), Qt.ColorScheme.Unknown)
        self.assertEqual(_scheme_from_portal_value(None), Qt.ColorScheme.Unknown)
        self.assertEqual(_scheme_from_portal_value("nope"), Qt.ColorScheme.Unknown)

    def test_nested_variants_are_unwrapped(self):
        self.assertEqual(_unwrap_dbus_variant(_FakeVariant(_FakeVariant(1))), 1)
        self.assertEqual(_unwrap_dbus_variant(2), 2)


class GtkSettingsFallbackTests(unittest.TestCase):
    def setUp(self):
        self._config = tempfile.TemporaryDirectory()
        self._env = patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": self._config.name, "GTK_THEME": ""},
        )
        self._env.start()
        self.addCleanup(self._env.stop)
        self.addCleanup(self._config.cleanup)

    def _write_settings(self, toolkit, body):
        directory = Path(self._config.name) / toolkit
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "settings.ini").write_text(body, encoding="utf-8")

    def test_prefer_dark_theme_flag(self):
        self._write_settings("gtk-4.0", "[Settings]\ngtk-application-prefer-dark-theme=1\n")
        self.assertEqual(gtk_color_scheme(), Qt.ColorScheme.Dark)

    def test_prefer_dark_theme_flag_off_is_light(self):
        self._write_settings("gtk-3.0", "[Settings]\ngtk-application-prefer-dark-theme=0\n")
        self.assertEqual(gtk_color_scheme(), Qt.ColorScheme.Light)

    def test_dark_theme_name(self):
        self._write_settings("gtk-3.0", "[Settings]\ngtk-theme-name=Adwaita-dark\n")
        self.assertEqual(gtk_color_scheme(), Qt.ColorScheme.Dark)

    def test_no_settings_has_no_opinion(self):
        self.assertEqual(gtk_color_scheme(), Qt.ColorScheme.Unknown)

    def test_gtk_theme_env_var(self):
        with patch.dict(os.environ, {"GTK_THEME": "Adwaita:dark"}):
            self.assertEqual(gtk_color_scheme(), Qt.ColorScheme.Dark)


class SystemColorSchemeTests(unittest.TestCase):
    def setUp(self):
        app()
        clear_system_color_scheme_cache()
        self.addCleanup(clear_system_color_scheme_cache)

    def test_platform_theme_wins_when_it_knows(self):
        with patch.object(QStyleHints, "colorScheme", lambda _self: Qt.ColorScheme.Light):
            with patch.object(
                system_color_scheme_module,
                "portal_color_scheme",
                return_value=Qt.ColorScheme.Dark,
            ):
                self.assertEqual(system_color_scheme(app()), Qt.ColorScheme.Light)

    def test_portal_answers_when_platform_theme_is_unknown(self):
        """The Flatpak case: the sandboxed platform theme has no opinion."""
        with patch.object(QStyleHints, "colorScheme", lambda _self: Qt.ColorScheme.Unknown):
            with patch.object(
                system_color_scheme_module,
                "portal_color_scheme",
                return_value=Qt.ColorScheme.Dark,
            ):
                self.assertEqual(system_color_scheme(app()), Qt.ColorScheme.Dark)
                self.assertTrue(system_prefers_dark(app()))

    def test_gtk_settings_answer_when_portal_is_silent(self):
        with patch.object(QStyleHints, "colorScheme", lambda _self: Qt.ColorScheme.Unknown):
            with patch.object(
                system_color_scheme_module,
                "portal_color_scheme",
                return_value=Qt.ColorScheme.Unknown,
            ):
                with patch.object(
                    system_color_scheme_module,
                    "gtk_color_scheme",
                    return_value=Qt.ColorScheme.Dark,
                ):
                    self.assertEqual(system_color_scheme(app()), Qt.ColorScheme.Dark)

    def test_portal_read_without_a_session_bus_is_unknown(self):
        self.assertIn(
            system_color_scheme_module.portal_color_scheme(),
            (Qt.ColorScheme.Unknown, Qt.ColorScheme.Dark, Qt.ColorScheme.Light),
        )


class SystemUiThemeTests(unittest.TestCase):
    """System must follow the desktop even when Qt's platform theme cannot."""

    def setUp(self):
        app()
        clear_system_color_scheme_cache()
        self.addCleanup(clear_system_color_scheme_cache)
        from jottr.window_color_scheme import clear_window_color_scheme_caches

        clear_window_color_scheme_caches()
        self.addCleanup(clear_window_color_scheme_caches)

    def _resolver(self, scheme):
        return patch.object(
            system_color_scheme_module, "system_color_scheme", return_value=scheme
        )

    def test_effective_ui_theme_follows_resolved_scheme(self):
        with self._resolver(Qt.ColorScheme.Dark):
            self.assertEqual(
                ThemeManager.effective_ui_theme_name("System", app()), "Dark"
            )
        with self._resolver(Qt.ColorScheme.Light):
            self.assertEqual(
                ThemeManager.effective_ui_theme_name("System", app()), "Light"
            )

    def test_explicit_ui_theme_ignores_the_desktop(self):
        with self._resolver(Qt.ColorScheme.Dark):
            self.assertEqual(ThemeManager.effective_ui_theme_name("Light", app()), "Light")

    def test_chrome_theme_cache_is_keyed_on_the_resolved_scheme(self):
        from jottr.window_color_scheme import effective_chrome_theme

        with self._resolver(Qt.ColorScheme.Light):
            light = effective_chrome_theme("", "System", app())
        with self._resolver(Qt.ColorScheme.Dark):
            dark = effective_chrome_theme("", "System", app())
        self.assertFalse(ThemeManager.theme_is_dark(light))
        self.assertTrue(ThemeManager.theme_is_dark(dark))

    def test_automatic_window_scheme_follows_the_desktop(self):
        from jottr.window_color_scheme import (
            automatic_scheme_for_system,
            discover_window_color_schemes,
            scheme_is_dark,
        )

        if not any(scheme.path for scheme in discover_window_color_schemes()):
            self.skipTest("no KDE .colors schemes installed")
        with patch.object(
            system_color_scheme_module, "system_prefers_dark", return_value=True
        ):
            auto = automatic_scheme_for_system()
        if not auto.path:
            self.skipTest("no dark .colors scheme installed")
        self.assertTrue(scheme_is_dark(auto.path))

class QtColorSchemePinTests(unittest.TestCase):
    """System has to pin Qt's scheme too, or the widget style stays light."""

    def setUp(self):
        app()
        clear_system_color_scheme_cache()
        system_color_scheme_module.note_pinned_color_scheme(Qt.ColorScheme.Unknown)
        self.addCleanup(clear_system_color_scheme_cache)
        self.addCleanup(
            system_color_scheme_module.note_pinned_color_scheme, Qt.ColorScheme.Unknown
        )

    def _desktop(self, scheme):
        return patch.object(
            system_color_scheme_module, "desktop_color_scheme", return_value=scheme
        )

    def _apply(self, scheme_name, platform_scheme, desktop_scheme):
        """Apply *scheme_name* and return the schemes handed to Qt."""
        from jottr.qt_style import apply_qt_color_scheme

        requested = []
        with patch.object(
            QStyleHints, "colorScheme", lambda _self: platform_scheme
        ):
            with patch.object(
                QStyleHints,
                "setColorScheme",
                lambda _self, scheme: requested.append(scheme),
            ):
                with self._desktop(desktop_scheme):
                    apply_qt_color_scheme(scheme_name, app())
        return requested

    def test_desktop_scheme_is_pinned_when_the_platform_has_no_opinion(self):
        requested = self._apply("System", Qt.ColorScheme.Unknown, Qt.ColorScheme.Dark)
        self.assertEqual(requested, [Qt.ColorScheme.Dark])
        self.assertEqual(
            system_color_scheme_module.pinned_color_scheme(), Qt.ColorScheme.Dark
        )

    def test_platform_opinion_keeps_system_following_qt(self):
        requested = self._apply("System", Qt.ColorScheme.Dark, Qt.ColorScheme.Light)
        self.assertEqual(requested, [Qt.ColorScheme.Unknown])
        self.assertEqual(
            system_color_scheme_module.pinned_color_scheme(), Qt.ColorScheme.Unknown
        )

    def test_explicit_ui_theme_is_not_recorded_as_a_pin(self):
        requested = self._apply("Dark", Qt.ColorScheme.Unknown, Qt.ColorScheme.Light)
        self.assertEqual(requested, [Qt.ColorScheme.Dark])
        self.assertEqual(
            system_color_scheme_module.pinned_color_scheme(), Qt.ColorScheme.Unknown
        )

    def test_reapplying_system_does_not_oscillate(self):
        """Qt echoes the pin back through colorScheme(); it must not unpin."""
        first = self._apply("System", Qt.ColorScheme.Unknown, Qt.ColorScheme.Dark)
        # Qt now reports the override we installed, not the platform's answer.
        second = self._apply("System", Qt.ColorScheme.Dark, Qt.ColorScheme.Dark)
        self.assertEqual(first, [Qt.ColorScheme.Dark])
        self.assertEqual(second, [Qt.ColorScheme.Dark])

    def test_desktop_switch_wins_over_a_stale_pin(self):
        self._apply("System", Qt.ColorScheme.Unknown, Qt.ColorScheme.Dark)
        # The desktop went light; styleHints still reports our dark pin.
        with patch.object(QStyleHints, "colorScheme", lambda _self: Qt.ColorScheme.Dark):
            with self._desktop(Qt.ColorScheme.Light):
                self.assertEqual(system_color_scheme(app()), Qt.ColorScheme.Light)

    def test_chrome_theme_realigns_when_platform_ignores_light_pin(self):
        """Flatpak/KDE may keep Dark after setColorScheme(Light); avoid white-on-white."""
        from jottr.qt_style import reconcile_chrome_theme_with_color_scheme
        from jottr.theme_manager import ThemeManager

        light = ThemeManager.get_ui_theme("Light", app())
        with patch.object(QStyleHints, "colorScheme", lambda _self: Qt.ColorScheme.Dark):
            reconciled = reconcile_chrome_theme_with_color_scheme(
                light, "Light", app()
            )
        self.assertTrue(ThemeManager.theme_is_dark(reconciled))
        with patch.object(QStyleHints, "colorScheme", lambda _self: Qt.ColorScheme.Light):
            unchanged = reconcile_chrome_theme_with_color_scheme(
                light, "Light", app()
            )
        self.assertFalse(ThemeManager.theme_is_dark(unchanged))

    def test_adwaita_variant_follows_immutable_color_scheme(self):
        from jottr.qt_style import (
            reconcile_chrome_theme_with_color_scheme,
            resolve_qt_style_key,
        )
        from jottr.theme_manager import ThemeManager

        if QStyleFactory.create("Adwaita") is None:
            self.skipTest("Adwaita style unavailable")
        if QStyleFactory.create("Adwaita-Dark") is None:
            self.skipTest("Adwaita-Dark style unavailable")

        light = ThemeManager.get_ui_theme("Light", app())
        with patch.object(QStyleHints, "colorScheme", lambda _self: Qt.ColorScheme.Dark):
            reconciled = reconcile_chrome_theme_with_color_scheme(
                light, "Light", app()
            )
            self.assertEqual(
                resolve_qt_style_key("Adwaita", theme=reconciled, application=app()),
                "Adwaita-Dark",
            )


if __name__ == "__main__":
    unittest.main()
