"""Widget style and color-scheme helpers.

Jottr draws its chrome with Qt's Fusion style on every platform. Fusion ships
with Qt and paints purely from the palette, so Jottr's Light/Dark palettes
(and the Organic look) show the same everywhere.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QMenu, QProxyStyle, QStyle, QStyleFactory

APP_QT_STYLE = "Fusion"


class JottrStyle(QProxyStyle):
    """Fusion with Jottr's app-wide rules.

    Dialog buttons never carry icons. Fusion asks the platform theme, and
    some (KDE) put style icons on OK/Cancel/Save; this answers no everywhere,
    for every QDialogButtonBox and QMessageBox.

    Menus get a translucent window. Their popup is its own top-level window,
    and an opaque one fills the corners outside the stylesheet's
    border-radius with the palette's window color: invisible over the chrome,
    sharp corners where a menu overlaps the editor. Polish runs before the
    popup's native window is created, so this reaches every menu.
    """

    def styleHint(self, hint, option=None, widget=None, return_data=None):
        if hint == QStyle.StyleHint.SH_DialogButtonBox_ButtonsHaveIcons:
            return 0
        return super().styleHint(hint, option, widget, return_data)

    def polish(self, target):
        if isinstance(target, QMenu):
            target.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        return super().polish(target)


def apply_qt_color_scheme(scheme_name, application=None):
    """Ask Qt for the Light/Dark appearance of a System/Light/Dark setting.

    This tints what the palette does not reach (window decorations, native
    dialogs). ``System`` follows the desktop portal (then GTK), not Qt's
    platform theme: native GNOME Wayland and the Flatpak KDE runtime both
    mis-report Light or Unknown while the session is dark. Some platform
    themes refuse the request; Fusion paints from the palette, so the chrome
    still shows the chosen scheme.
    """
    from jottr.system_color_scheme import (
        desktop_color_scheme,
        note_pinned_color_scheme,
    )
    from jottr.theme_manager import ThemeManager

    app = application or QGuiApplication.instance()
    if app is None:
        return None

    hints = app.styleHints()
    if not hasattr(hints, "setColorScheme"):
        return None

    scheme = ThemeManager.ui_theme_color_scheme(scheme_name)
    pinned = Qt.ColorScheme.Unknown
    if scheme == Qt.ColorScheme.Unknown:
        pinned = desktop_color_scheme()
        if pinned != Qt.ColorScheme.Unknown:
            scheme = pinned
    note_pinned_color_scheme(pinned)
    hints.setColorScheme(scheme)
    return hints.colorScheme()


def apply_qt_style(application=None):
    """Install Fusion (as JottrStyle) once. Returns True when the style was swapped."""
    app = application or QApplication.instance()
    if app is None:
        return False
    # style().objectName() is not reliable across platforms (often empty),
    # so remember the style we applied on the application object itself.
    if app.property("_jottr_style_key") == APP_QT_STYLE:
        return False
    base = QStyleFactory.create(APP_QT_STYLE)
    if base is None:
        return False
    app.setStyle(JottrStyle(base))
    app.setProperty("_jottr_style_key", APP_QT_STYLE)
    return True


def refresh_styled_widgets(application=None):
    """Force existing widgets to repaint with the active QStyle and palette."""
    app = application or QApplication.instance()
    if app is None or app.style() is None:
        return
    style = app.style()
    for widget in app.allWidgets():
        style.unpolish(widget)
        style.polish(widget)
        widget.update()


def apply_startup_app_chrome(application, settings_manager):
    """Apply Fusion, color scheme, palette, and chrome QSS before the main window.

    Doing this on the QApplication means the window is born into the right
    style and avoids a second full stylesheet/repolish pass in
    ``TextEditorApp.apply_app_style``.
    """
    from jottr.theme_manager import ThemeManager

    if application is None or settings_manager is None:
        return None

    scheme_setting = settings_manager.get_ui_theme()
    apply_qt_color_scheme(scheme_setting, application)
    theme = ThemeManager.get_ui_theme(scheme_setting, application)
    apply_qt_style(application)
    ThemeManager.apply_app_palette(application, theme)

    app_font = settings_manager.get_font("ui")
    application.setFont(app_font)
    stylesheet = ThemeManager.build_app_stylesheet(theme=theme)
    application.setStyleSheet(stylesheet)
    application.setProperty("_jottr_startup_stylesheet", stylesheet)
    return stylesheet
