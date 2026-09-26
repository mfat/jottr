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
from PyQt6.QtWidgets import QApplication

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
        # A pin left by another test would be mistaken for our own override.
        system_color_scheme_module.note_pinned_color_scheme(Qt.ColorScheme.Unknown)
        self.addCleanup(
            system_color_scheme_module.note_pinned_color_scheme, Qt.ColorScheme.Unknown
        )

    def test_portal_wins_when_platform_theme_disagrees(self):
        """Native GNOME: Qt reports Light from GTK settings while the portal is Dark."""
        with patch.object(QStyleHints, "colorScheme", lambda _self: Qt.ColorScheme.Light):
            with patch.object(
                system_color_scheme_module,
                "portal_color_scheme",
                return_value=Qt.ColorScheme.Dark,
            ):
                self.assertEqual(system_color_scheme(app()), Qt.ColorScheme.Dark)

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

    def test_platform_theme_used_when_desktop_is_silent(self):
        with patch.object(QStyleHints, "colorScheme", lambda _self: Qt.ColorScheme.Dark):
            with patch.object(
                system_color_scheme_module,
                "portal_color_scheme",
                return_value=Qt.ColorScheme.Unknown,
            ):
                with patch.object(
                    system_color_scheme_module,
                    "gtk_color_scheme",
                    return_value=Qt.ColorScheme.Unknown,
                ):
                    self.assertEqual(system_color_scheme(app()), Qt.ColorScheme.Dark)

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
        ThemeManager.clear_ui_theme_cache()
        self.addCleanup(ThemeManager.clear_ui_theme_cache)

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
        with self._resolver(Qt.ColorScheme.Light):
            light = ThemeManager.get_ui_theme("System", app())
        with self._resolver(Qt.ColorScheme.Dark):
            dark = ThemeManager.get_ui_theme("System", app())
        self.assertFalse(ThemeManager.theme_is_dark(light))
        self.assertTrue(ThemeManager.theme_is_dark(dark))

    def test_explicit_light_and_dark_ignore_the_desktop(self):
        with self._resolver(Qt.ColorScheme.Dark):
            self.assertFalse(ThemeManager.theme_is_dark(ThemeManager.get_ui_theme("Light", app())))
        with self._resolver(Qt.ColorScheme.Light):
            self.assertTrue(ThemeManager.theme_is_dark(ThemeManager.get_ui_theme("Dark", app())))


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

    def test_desktop_scheme_is_pinned_even_when_platform_disagrees(self):
        """GNOME Wayland: Qt Light must not block pinning portal Dark."""
        requested = self._apply("System", Qt.ColorScheme.Light, Qt.ColorScheme.Dark)
        self.assertEqual(requested, [Qt.ColorScheme.Dark])
        self.assertEqual(
            system_color_scheme_module.pinned_color_scheme(), Qt.ColorScheme.Dark
        )

    def test_system_stays_unknown_when_desktop_is_silent(self):
        requested = self._apply("System", Qt.ColorScheme.Dark, Qt.ColorScheme.Unknown)
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

    def test_refused_light_pin_keeps_light_chrome(self):
        """GNOME's portal platform theme can refuse a Light pin while the
        desktop is dark. Fusion paints from the palette, so Light must stay
        Light instead of following the refusal."""
        from jottr.qt_style import apply_qt_color_scheme

        with patch.object(QStyleHints, "colorScheme", lambda _self: Qt.ColorScheme.Dark):
            apply_qt_color_scheme("Light", app())
            theme = ThemeManager.get_ui_theme("Light", app())
        self.assertFalse(ThemeManager.theme_is_dark(theme))

if __name__ == "__main__":
    unittest.main()
