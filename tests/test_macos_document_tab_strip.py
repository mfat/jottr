"""macOS document tab strip palette fix — gated to darwin + macOS style only."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from PyQt6.QtGui import QColor, QPalette, QPainter, QImage
from PyQt6.QtWidgets import (
    QApplication,
    QStyle,
    QStyleFactory,
    QStyleOption,
    QLabel,
)

from jottr.theme_manager import ThemeManager
from jottr.ui.document_tab_bar import (
    DocumentTabWidget,
    MacDocumentTabBarStyle,
    is_macos_qt_style,
    macos_document_tab_strip_fix_applies,
    sync_macos_document_tab_strip_style,
)


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tab-strip-tests"])
    return _APP


class MacOSDocumentTabStripTests(unittest.TestCase):
    def setUp(self):
        app()

    def test_style_key_detection(self):
        self.assertTrue(is_macos_qt_style("macOS"))
        self.assertTrue(is_macos_qt_style("macos"))
        self.assertTrue(is_macos_qt_style("Macintosh"))
        self.assertFalse(is_macos_qt_style("Fusion"))
        self.assertFalse(is_macos_qt_style("Windows"))
        self.assertFalse(is_macos_qt_style(None))
        self.assertFalse(is_macos_qt_style(""))

    def test_fix_gated_off_non_darwin(self):
        with patch(
            "jottr.ui.document_tab_bar.sys.platform", "linux"
        ):
            self.assertFalse(macos_document_tab_strip_fix_applies("macOS"))
            self.assertFalse(macos_document_tab_strip_fix_applies("Fusion"))

    def test_fix_gated_on_darwin_macos_style_only(self):
        with patch(
            "jottr.ui.document_tab_bar.sys.platform", "darwin"
        ):
            self.assertTrue(macos_document_tab_strip_fix_applies("macOS"))
            self.assertFalse(macos_document_tab_strip_fix_applies("Fusion"))
            self.assertFalse(macos_document_tab_strip_fix_applies("Windows"))

    def test_proxy_fills_frame_from_window_palette(self):
        if "macOS" not in QStyleFactory.keys() and "macos" not in [
            k.casefold() for k in QStyleFactory.keys()
        ]:
            self.skipTest("macOS Qt style not available")
        key = next(k for k in QStyleFactory.keys() if k.casefold() == "macos")
        base = QStyleFactory.create(key)
        self.assertIsNotNone(base)
        proxy = MacDocumentTabBarStyle(base)

        option = QStyleOption()
        option.rect.setRect(0, 0, 40, 20)
        option.palette = QPalette()
        option.palette.setColor(QPalette.ColorRole.Window, QColor("#f4f6f8"))
        expected = MacDocumentTabBarStyle.tab_strip_color(option.palette)

        image = QImage(40, 20, QImage.Format.Format_RGB32)
        image.fill(QColor("#000000"))
        painter = QPainter(image)
        proxy.drawPrimitive(
            QStyle.PrimitiveElement.PE_FrameTabBarBase, option, painter, None
        )
        painter.end()
        self.assertEqual(image.pixelColor(20, 10).name(), "#f4f6f8")
        self.assertEqual(expected.name(), "#f4f6f8")

    def test_proxy_selected_tab_uses_base_against_strip(self):
        if "macOS" not in QStyleFactory.keys() and "macos" not in [
            k.casefold() for k in QStyleFactory.keys()
        ]:
            self.skipTest("macOS Qt style not available")
        from PyQt6.QtWidgets import QStyleOptionTab

        key = next(k for k in QStyleFactory.keys() if k.casefold() == "macos")
        proxy = MacDocumentTabBarStyle(QStyleFactory.create(key))
        option = QStyleOptionTab()
        option.rect.setRect(0, 0, 80, 24)
        option.state = QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_Enabled
        option.palette = QPalette()
        option.palette.setColor(QPalette.ColorRole.Window, QColor("#f4f6f8"))
        option.palette.setColor(QPalette.ColorRole.Mid, QColor("#dfe4ea"))
        option.palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))

        image = QImage(80, 24, QImage.Format.Format_RGB32)
        image.fill(QColor("#000000"))
        painter = QPainter(image)
        proxy.drawControl(
            QStyle.ControlElement.CE_TabBarTabShape, option, painter, None
        )
        painter.end()
        # Interior of selected tab is Base, not the strip mix.
        self.assertEqual(image.pixelColor(40, 12).name(), "#ffffff")
        strip = MacDocumentTabBarStyle.tab_strip_color(option.palette)
        self.assertNotEqual(strip.name(), "#ffffff")

    def test_sync_is_noop_on_linux_even_for_macos_key(self):
        tabs = DocumentTabWidget()
        self.addCleanup(tabs.deleteLater)
        tabs.addTab(QLabel("a"), "A")
        with patch(
            "jottr.ui.document_tab_bar.sys.platform", "linux"
        ):
            applied = sync_macos_document_tab_strip_style(tabs, "macOS")
        self.assertFalse(applied)
        self.assertNotIsInstance(tabs.tabBar().style(), MacDocumentTabBarStyle)

    def test_sync_clears_proxy_when_style_is_fusion(self):
        if "macOS" not in QStyleFactory.keys() and "macos" not in [
            k.casefold() for k in QStyleFactory.keys()
        ]:
            self.skipTest("macOS Qt style not available")
        key = next(k for k in QStyleFactory.keys() if k.casefold() == "macos")
        tabs = DocumentTabWidget()
        self.addCleanup(tabs.deleteLater)
        tabs.addTab(QLabel("a"), "A")
        with patch(
            "jottr.ui.document_tab_bar.sys.platform", "darwin"
        ):
            self.assertTrue(sync_macos_document_tab_strip_style(tabs, key))
            self.assertTrue(tabs.tabBar().property("_jottr_macos_tab_strip"))
            cleared = sync_macos_document_tab_strip_style(tabs, "Fusion")
        self.assertFalse(cleared)
        self.assertFalse(bool(tabs.tabBar().property("_jottr_macos_tab_strip")))

    def test_document_mode_enabled(self):
        tabs = DocumentTabWidget()
        self.addCleanup(tabs.deleteLater)
        self.assertTrue(tabs.documentMode())

    def test_sync_on_darwin_macos_uses_chrome_window_not_editor(self):
        if sys.platform != "darwin":
            self.skipTest("requires macOS host")
        if "macOS" not in QStyleFactory.keys() and "macos" not in [
            k.casefold() for k in QStyleFactory.keys()
        ]:
            self.skipTest("macOS Qt style not available")
        key = next(k for k in QStyleFactory.keys() if k.casefold() == "macos")
        application = app()
        application.setStyle(QStyleFactory.create(key))
        ThemeManager.apply_app_palette(application, ThemeManager.get_theme("White"))
        window_color = application.palette().color(QPalette.ColorRole.Window).name()
        editor_sepia = ThemeManager.get_theme("Sepia")["editor"]["background"].lower()
        self.assertNotEqual(window_color, editor_sepia)

        tabs = DocumentTabWidget()
        self.addCleanup(tabs.deleteLater)
        tabs.setDocumentMode(True)
        tabs.addTab(QLabel("a"), "Ayatollah*")
        tabs.addTab(QLabel("b"), "Document 2")
        tabs.resize(500, 80)
        tabs.show()
        application.processEvents()

        with patch(
            "jottr.ui.document_tab_bar.sys.platform", "darwin"
        ):
            sync_macos_document_tab_strip_style(tabs, key)
        application.processEvents()

        bar = tabs.tabBar()
        pix = bar.grab().toImage()
        last = bar.tabRect(1)
        x = min(pix.width() - 5, last.right() + 40)
        y = max(1, bar.height() // 2)
        empty = pix.pixelColor(x, y).name()
        strip = MacDocumentTabBarStyle.tab_strip_color(application.palette()).name()
        self.assertEqual(empty, strip)
        self.assertTrue(bar.property("_jottr_macos_tab_strip"))
        # Selected-tab Base fill is covered by
        # test_proxy_selected_tab_uses_base_against_strip (direct drawControl).
        # Full widget grabs under offscreen/QSS do not reliably exercise the
        # macOS style's tab-shape path.


if __name__ == "__main__":
    unittest.main()
