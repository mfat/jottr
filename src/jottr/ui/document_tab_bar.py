"""Document tab bar with centered label painting."""
from PyQt6.QtWidgets import QTabBar, QStyle, QStyleOptionTab, QStylePainter
from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal
from PyQt6.QtGui import QColor

from jottr.theme_manager import ThemeManager


class LeftAlignedDocumentTabBar(QTabBar):
    """Document tab bar that keeps labels centered in the tab area."""

    tabs_changed = pyqtSignal()

    label_left_padding = 8
    label_right_padding = 30
    icon_text_gap = 5
    icon_vertical_offset = -1
    underline_height = 2

    def tabInserted(self, index):
        super().tabInserted(index)
        self.tabs_changed.emit()

    def tabRemoved(self, index):
        super().tabRemoved(index)
        self.tabs_changed.emit()

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionTab()
        for index in range(self.count()):
            self.initStyleOption(option, index)
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabShape, option)
            self.draw_left_aligned_label(painter, option, index)

    def tab_text_color(self, selected=False):
        window = self.window()
        settings_manager = getattr(window, "settings_manager", None)
        if settings_manager is None:
            return self.palette().windowText().color()
        theme = ThemeManager.get_ui_theme(
            settings_manager.get_ui_theme()
        )
        return QColor(theme["app"]["text" if selected else "muted"])

    def label_contents_rect(self, tab_rect):
        return tab_rect.adjusted(
            self.label_left_padding,
            0,
            -self.label_right_padding,
            -self.underline_height
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
