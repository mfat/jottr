"""Document tab bar with centered label painting and a full-width chrome rail."""
from PyQt6.QtWidgets import (
    QLineEdit, QTabBar, QTabWidget, QStyle, QStyleOptionTab, QStylePainter, QToolTip,
)
from PyQt6.QtCore import Qt, QEvent, QPoint, QRect, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QPen


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
    """Document tab bar that keeps labels centered in the tab area."""

    tabs_changed = pyqtSignal()

    label_left_padding = 8
    label_right_padding = 30
    icon_text_gap = 5
    icon_vertical_offset = -1
    underline_height = 2
    title_editor_min_width = 120

    title_editor = None
    _committing_title = False

    def __init__(self, parent=None):
        super().__init__(parent)
        # Tab positions change under an open title editor.
        self.tabMoved.connect(self.finish_title_edit)
        self.tabs_changed.connect(self.finish_title_edit)

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

    def document_tab_widget(self):
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QTabWidget):
            parent = parent.parentWidget()
        return parent

    def sync_rail_width(self):
        """Stretch the bar across the tab widget so the rail fills empty space."""
        tab_widget = self.document_tab_widget()
        if tab_widget is None:
            return
        width = max(0, tab_widget.width())
        if self.minimumWidth() != width:
            self.setMinimumWidth(width)

    def theme_app_colors(self):
        window = self.window()
        settings_manager = getattr(window, "settings_manager", None)
        if settings_manager is None:
            return None
        from jottr.window_color_scheme import effective_chrome_theme

        return effective_chrome_theme(
            settings_manager.get_window_color_scheme(),
            settings_manager.get_ui_theme(),
        )["app"]

    def rail_color(self):
        app = self.theme_app_colors()
        if app is None:
            return self.palette().window().color()
        # Match toolbar/menubar chrome so the rail reads against page background.
        return QColor(app["surface"])

    def rail_border_color(self):
        app = self.theme_app_colors()
        if app is None:
            return self.palette().mid().color()
        return QColor(app["border"])

    def accent_color(self):
        app = self.theme_app_colors()
        if app is None:
            return self.palette().highlight().color()
        return QColor(app["accent"])

    def paintEvent(self, event):
        painter = QStylePainter(self)
        painter.fillRect(self.rect(), self.rail_color())
        border_y = self.rect().bottom()
        painter.setPen(QPen(self.rail_border_color(), 1))
        painter.drawLine(self.rect().left(), border_y, self.rect().right(), border_y)

        option = QStyleOptionTab()
        for index in range(self.count()):
            self.initStyleOption(option, index)
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabShape, option)
            self.draw_left_aligned_label(painter, option, index)
            if option.state & QStyle.StateFlag.State_Selected:
                self.draw_active_top_strip(painter, option.rect)

    def draw_active_top_strip(self, painter, tab_rect):
        strip = QRect(
            tab_rect.left(),
            tab_rect.top(),
            tab_rect.width(),
            self.underline_height,
        )
        painter.fillRect(strip, self.accent_color())

    def tab_text_color(self, selected=False):
        app = self.theme_app_colors()
        if app is None:
            return self.palette().windowText().color()
        return QColor(app["text" if selected else "muted"])

    def label_contents_rect(self, tab_rect):
        return tab_rect.adjusted(
            self.label_left_padding,
            self.underline_height,
            -self.label_right_padding,
            0,
        )

    def draw_left_aligned_label(self, painter, option, index):
        label_rect = self.label_contents_rect(option.rect)
        icon = self.tabIcon(index)
        icon_size = self.iconSize() if not icon.isNull() else QSize(0, 0)
        icon_width = icon_size.width() if not icon.isNull() else 0
        gap = self.icon_text_gap if icon_width else 0
        available_text_width = max(0, label_rect.width() - icon_width - gap)
        text = painter.fontMetrics().elidedText(
            self.tabText(index),
            Qt.TextElideMode.ElideRight,
            available_text_width
        )
        text_width = painter.fontMetrics().horizontalAdvance(text)
        content_width = min(label_rect.width(), icon_width + gap + text_width)
        start_x = label_rect.left() + max(0, (label_rect.width() - content_width) // 2)

        if icon_width:
            icon_rect = QRect(
                start_x,
                label_rect.top() + (label_rect.height() - icon_size.height()) // 2 + self.icon_vertical_offset,
                icon_size.width(),
                icon_size.height()
            )
            icon.paint(painter, icon_rect, Qt.AlignmentFlag.AlignCenter)
            start_x = icon_rect.right() + 1 + gap

        text_rect = QRect(
            start_x,
            label_rect.top(),
            max(0, label_rect.right() - start_x + 1),
            label_rect.height()
        )
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.setPen(self.tab_text_color(selected))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine,
            text
        )


class DocumentTabWidget(QTabWidget):
    """QTabWidget that keeps the document tab rail full-width."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(LeftAlignedDocumentTabBar())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        tab_bar = self.tabBar()
        if isinstance(tab_bar, LeftAlignedDocumentTabBar):
            tab_bar.sync_rail_width()
