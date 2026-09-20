"""Document tab bar with in-place title editing, drawn by the widget style."""
from __future__ import annotations

import sys

from PyQt6.QtCore import QEvent, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QLineEdit,
    QProxyStyle,
    QStyle,
    QStyleFactory,
    QTabBar,
    QTabWidget,
    QToolTip,
)

# Qt macOS style objectName / factory keys that paint a hardcoded tab strip.
_MACOS_QT_STYLE_KEYS = frozenset({"macos", "macintosh"})


def is_macos_qt_style(style_key) -> bool:
    """True when *style_key* is Qt's native macOS widget style."""
    return (style_key or "").strip().casefold() in _MACOS_QT_STYLE_KEYS


def macos_document_tab_strip_fix_applies(style_key=None) -> bool:
    """True only on macOS when the active widget style is Qt's macOS style.

    Other platforms and Fusion/Windows/… keep their native tab painting.
    """
    if sys.platform != "darwin":
        return False
    if style_key is None:
        application = QApplication.instance()
        if application is not None:
            style_key = application.property("_jottr_style_key")
            if not style_key and application.style() is not None:
                style_key = application.style().objectName()
    return is_macos_qt_style(style_key)


class MacDocumentTabBarStyle(QProxyStyle):
    """Palette-driven document tab strip and shapes under Qt's macOS style.

    Qt's macOS style fills the tab strip and tab shapes with fixed system grays
    that ignore the application palette. Match Fusion: strip and inactive tabs
    use ``Window`` (same chrome as the rest of the window), selected tabs use
    ``Base``. Labels, icons, and close buttons stay native.
    """

    @classmethod
    def tab_strip_color(cls, palette):
        """Chrome strip color — exact Window, like Fusion document tabs."""
        return palette.color(QPalette.ColorRole.Window)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_FrameTabBarBase:
            painter.fillRect(option.rect, self.tab_strip_color(option.palette))
            return
        super().drawPrimitive(element, option, painter, widget)

    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.ControlElement.CE_TabBarTabShape:
            selected = bool(option.state & QStyle.StateFlag.State_Selected)
            strip = self.tab_strip_color(option.palette)
            bg = (
                option.palette.color(QPalette.ColorRole.Base)
                if selected
                else strip
            )
            painter.save()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawRect(option.rect)
            mid = option.palette.color(QPalette.ColorRole.Mid)
            painter.setPen(mid)
            rect = option.rect
            if selected:
                # Three-sided frame; open bottom so the tab joins the pane.
                right = rect.right()
                painter.drawLine(rect.left(), rect.top(), right, rect.top())
                painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
                painter.drawLine(right, rect.top(), right, rect.bottom())
            else:
                # Light separator between inactive tabs / trailing edge.
                painter.drawLine(
                    rect.right(),
                    rect.top() + 4,
                    rect.right(),
                    rect.bottom() - 4,
                )
            painter.restore()
            return
        super().drawControl(element, option, painter, widget)


def find_macos_document_tab_style(style):
    """Return our proxy even when QSS wraps it in QStyleSheetStyle."""
    seen: set[int] = set()
    while style is not None and id(style) not in seen:
        seen.add(id(style))
        if isinstance(style, MacDocumentTabBarStyle):
            return style
        base = getattr(style, "baseStyle", None)
        style = base() if callable(base) else None
    return None


_MACOS_TAB_STRIP_PROPERTY = "_jottr_macos_tab_strip"


def sync_macos_document_tab_strip_style(tab_widget, style_key=None):
    """Install or clear the macOS tab-strip fix on *tab_widget*'s tab bar.

    No-op on non-macOS platforms and when the widget style is not macOS, so
    Fusion and other styles are never wrapped. Only the tab bar is wrapped —
    that is where tab shapes and ``PE_FrameTabBarBase`` are painted.
    """
    if tab_widget is None:
        return False
    tab_bar = tab_widget.tabBar()
    if macos_document_tab_strip_fix_applies(style_key):
        application = QApplication.instance()
        key = style_key or (
            application.property("_jottr_style_key") if application else None
        )
        if not key and application is not None and application.style() is not None:
            key = application.style().objectName()
        base = QStyleFactory.create(key) if key else None
        if base is None:
            return False
        # setStyle takes ownership of the proxy (and its base style).
        # App QSS may wrap this; keep a property so clear stays reliable.
        tab_bar.setStyle(MacDocumentTabBarStyle(base))
        tab_bar.setProperty(_MACOS_TAB_STRIP_PROPERTY, True)
        return True

    # Drop only our proxy so unrelated widget styles stay untouched.
    if tab_bar.property(_MACOS_TAB_STRIP_PROPERTY) or find_macos_document_tab_style(
        tab_bar.style()
    ):
        tab_bar.setStyle(None)
        tab_bar.setProperty(_MACOS_TAB_STRIP_PROPERTY, False)
    return False


class TabTitleEditor(QLineEdit):
    """Line edit shown over a tab label while the tab is renamed."""

    cancelled = pyqtSignal()

    def event(self, event):
        # Take Escape before window shortcuts (such as leaving focus mode) do.
        if (
            event.type() == QEvent.Type.ShortcutOverride
            and event.key() == Qt.Key.Key_Escape
        ):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.cancelled.emit()


class LeftAlignedDocumentTabBar(QTabBar):
    """Document tab bar whose tab titles can be edited in place."""

    tabs_changed = pyqtSignal()

    label_left_padding = 8
    label_right_padding = 30
    title_editor_min_width = 120
    # Extra vertical room without QSS colors — style still paints the tab.
    tab_height_extra = 6
    min_tab_height = 36

    title_editor = None
    _committing_title = False

    def tabSizeHint(self, index):
        hint = super().tabSizeHint(index)
        if hint.isValid():
            return QSize(
                hint.width(),
                max(hint.height() + self.tab_height_extra, self.min_tab_height),
            )
        return hint

    def minimumTabSizeHint(self, index):
        hint = super().minimumTabSizeHint(index)
        if hint.isValid():
            return QSize(
                hint.width(),
                max(hint.height() + self.tab_height_extra, self.min_tab_height),
            )
        return hint

    def __init__(self, parent=None):
        super().__init__(parent)
        # Tab positions change under an open title editor.
        self.tabMoved.connect(self.finish_title_edit)
        self.tabs_changed.connect(self.finish_title_edit)

    def paintEvent(self, event):
        # macOS proxy only covers PE_FrameTabBarBase (a thin bottom band);
        # fill the full bar so selected Base tabs contrast against the strip.
        # Use the sync property: app QSS wraps styles so isinstance/baseStyle
        # often cannot see MacDocumentTabBarStyle from Python.
        if self.property(_MACOS_TAB_STRIP_PROPERTY):
            painter = QPainter(self)
            painter.fillRect(
                self.rect(),
                MacDocumentTabBarStyle.tab_strip_color(self.palette()),
            )
            painter.end()
        super().paintEvent(event)

    def edit_tab_title(self, index, text, commit, select_length=None):
        """Edit the title of tab *index* in place, starting from *text*.

        Enter passes the text to *commit*, which returns an error message to
        keep editing, or None when done. Escape, clicking elsewhere, and tabs
        being added, closed or moved cancel the edit.
        """
        self.finish_title_edit()
        rect = self.label_contents_rect(self.tabRect(index))
        rect.setWidth(max(rect.width(), self.title_editor_min_width))
        editor = TabTitleEditor(text, self)
        editor.setGeometry(rect)
        editor.setSelection(0, len(text) if select_length is None else select_length)
        editor.returnPressed.connect(lambda: self._commit_title_edit(editor, commit))
        editor.cancelled.connect(self.finish_title_edit)
        self.title_editor = editor
        editor.show()
        editor.setFocus()
        return editor

    def _commit_title_edit(self, editor, commit):
        if editor is not self.title_editor:
            return
        self._committing_title = True
        try:
            error = commit(editor.text())
        finally:
            self._committing_title = False
        if editor is not self.title_editor:
            return
        if error:
            editor.setFocus()
            QToolTip.showText(editor.mapToGlobal(QPoint(0, editor.height())), error, editor)
            return
        self.finish_title_edit()

    def finish_title_edit(self, *_args):
        """Close the title editor without renaming, if one is open."""
        editor = self.title_editor
        if editor is None or self._committing_title:
            return
        self.title_editor = None
        QToolTip.hideText()
        editor.hide()
        editor.deleteLater()

    def tabInserted(self, index):
        super().tabInserted(index)
        self.tabs_changed.emit()

    def tabRemoved(self, index):
        super().tabRemoved(index)
        self.tabs_changed.emit()

    def label_contents_rect(self, tab_rect):
        """Where a tab's title sits, clear of its icon and close button."""
        return tab_rect.adjusted(self.label_left_padding, 0, -self.label_right_padding, 0)


class DocumentTabWidget(QTabWidget):
    """QTabWidget for documents, with in-place tab renaming."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(LeftAlignedDocumentTabBar())
        self.setDocumentMode(True)
        self.sync_macos_tab_strip_style()

    def sync_macos_tab_strip_style(self, style_key=None):
        """Apply or clear the macOS-only tab-strip palette fix."""
        return sync_macos_document_tab_strip_style(self, style_key=style_key)
