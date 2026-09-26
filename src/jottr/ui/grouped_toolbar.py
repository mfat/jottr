"""Toolbar that can paint a rounded pill behind each group of buttons."""

from PyQt6.QtCore import QEvent, QRect, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QApplication, QToolBar, QToolButton


class GroupedToolBar(QToolBar):
    """QToolBar whose separators split buttons into pill-backed groups.

    Groups are only painted while a group color is set (the Organic look);
    otherwise it paints like a plain QToolBar.
    """

    group_padding = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._group_color = None

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.Polish:
            # QToolBarLayout reads its margins and spacing when it is built,
            # before the object name lets "QToolBar#id" rules match, and only
            # reads them again on a style change. Send one once polished.
            QApplication.sendEvent(self, QEvent(QEvent.Type.StyleChange))
        return result

    def set_group_color(self, color):
        """Set the pill color, or None to paint no groups."""
        color = QColor(color) if color is not None else None
        if color is not None and not color.isValid():
            color = None
        self._group_color = color
        self.update()

    def button_groups(self):
        """Bounding rects of each run of visible buttons between separators."""
        groups = []
        current = QRect()
        for action in self.actions():
            widget = self.widgetForAction(action)
            if action.isSeparator() or not isinstance(widget, QToolButton):
                if not current.isNull():
                    groups.append(current)
                current = QRect()
                continue
            if widget.isVisible():
                current = current.united(widget.geometry())
        if not current.isNull():
            groups.append(current)
        return groups

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._group_color is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._group_color)
        pad = self.group_padding
        for rect in self.button_groups():
            pill = rect.adjusted(-pad, 0, pad, 0)
            radius = pill.height() / 2
            painter.drawRoundedRect(pill, radius, radius)
        painter.end()
