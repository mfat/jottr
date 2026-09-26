"""Toolbar that can paint a rounded pill behind each group of buttons."""

from PyQt6.QtCore import QEvent, QRect, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QApplication, QToolBar, QToolButton, QWidget


class GroupedToolBar(QToolBar):
    """QToolBar whose separators split buttons into pill-backed groups.

    Groups are only painted while a group color is set (the Organic look);
    otherwise it paints like a plain QToolBar.
    """

    group_padding = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._group_color = None
        self._side_inset = 0
        self._inset_actions = []

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.Polish:
            # QToolBarLayout reads its margins and spacing when it is built,
            # before the object name lets "QToolBar#id" rules match, and only
            # reads them again on a style change. Send one once polished.
            QApplication.sendEvent(self, QEvent(QEvent.Type.StyleChange))
        return result

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.StyleChange:
            self._update_inset_widths()

    def set_side_inset(self, inset):
        """Add *inset* px before the first and after the last item.

        QToolBar pads all four sides by the same amount, so a wider side
        inset comes from a fixed-width spacer at each end. Call it after
        the actions are added; 0 removes the spacers.
        """
        for action in self._inset_actions:
            self.removeAction(action)
        self._inset_actions = []
        self._side_inset = max(0, int(inset))
        actions = self.actions()
        if self._side_inset and actions:
            leading = self.insertWidget(actions[0], QWidget(self))
            trailing = self.addWidget(QWidget(self))
            self._inset_actions = [leading, trailing]
        self._update_inset_widths()

    def _update_inset_widths(self):
        # Each spacer adds one layout spacing gap next to it.
        width = max(0, self._side_inset - self.layout().spacing())
        for action in self._inset_actions:
            self.widgetForAction(action).setFixedWidth(width)

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
