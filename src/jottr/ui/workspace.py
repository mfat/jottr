"""Workspace explorer and side-panel widgets."""
from PyQt6.QtWidgets import QListWidget, QPushButton, QStyle, QStyleOptionButton, QTreeView
from PyQt6.QtCore import QEvent, QPointF, QRect, QSize, Qt
from PyQt6.QtGui import QFileSystemModel, QFont, QFontMetrics, QPainter, QPainterPath, QPalette, QPen


class WorkspaceFileSystemModel(QFileSystemModel):
    """File model that exposes full paths as tooltips."""

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.ToolTipRole and index.isValid():
            return self.filePath(index)
        return super().data(index, role)


class PanelListWidget(QListWidget):
    """List that re-lays out its rows when its style changes.

    QListView keeps row geometry from its last layout, so rows laid out
    before a stylesheet arrives keep the old height and item margins.
    """

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.StyleChange:
            self.scheduleDelayedItemsLayout()


class WorkspaceTitleButton(QPushButton):
    """Menu button that draws its title followed by a dropdown chevron.

    The style's own menu indicator is a tiny triangle that stylesheets can
    paint over the text, so the label and chevron are painted here instead.
    Long titles are elided rather than widening the explorer.
    """

    _CHEVRON_WIDTH = 9
    _GAP = 6
    _PADDING = 4

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._title_weight = QFont.Weight.Normal

    def set_title_weight(self, weight):
        """Title weight; the chrome font overrides stylesheet font-weight."""
        self._title_weight = weight
        self.updateGeometry()
        self.update()

    def _title_font(self):
        font = QFont(self.font())
        font.setWeight(self._title_weight)
        return font

    def _extra_width(self):
        # One pixel of slack for fractional text advances.
        return self._GAP + self._CHEVRON_WIDTH + 2 * self._PADDING + 1

    def sizeHint(self):
        width = QFontMetrics(self._title_font()).horizontalAdvance(self.text()) + self._extra_width()
        return QSize(width, super().sizeHint().height())

    def minimumSizeHint(self):
        width = QFontMetrics(self._title_font()).horizontalAdvance("\u2026") + self._extra_width()
        return QSize(width, super().minimumSizeHint().height())

    def paintEvent(self, event):
        painter = QPainter(self)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        option.text = ""
        option.features &= ~QStyleOptionButton.ButtonFeature.HasMenu
        self.style().drawControl(QStyle.ControlElement.CE_PushButton, option, painter, self)

        area = self.rect().adjusted(self._PADDING, 0, -self._PADDING, 0)
        font = self._title_font()
        metrics = QFontMetrics(font)
        available = max(0, area.width() - self._GAP - self._CHEVRON_WIDTH)
        text = self.text()
        # elidedText compares fractional widths, so a title sized to its
        # rounded advance would be elided without this check.
        if metrics.horizontalAdvance(text) > available:
            text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, available)
        text_width = metrics.horizontalAdvance(text)
        direction = self.layoutDirection()
        text_rect = QStyle.visualRect(
            direction, area, QRect(area.left(), area.top(), text_width, area.height())
        )
        chevron_rect = QStyle.visualRect(
            direction,
            area,
            QRect(area.left() + text_width + self._GAP, area.top(),
                  self._CHEVRON_WIDTH, area.height()),
        )

        color = self.palette().color(QPalette.ColorRole.ButtonText)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(color, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        center = QPointF(chevron_rect.center()) + QPointF(0.5, 0.5)
        half = self._CHEVRON_WIDTH / 2 - 1
        path = QPainterPath(center + QPointF(-half, -half / 2))
        path.lineTo(center + QPointF(0, half / 2))
        path.lineTo(center + QPointF(half, -half / 2))
        painter.drawPath(path)


class WorkspaceTreeView(QTreeView):
    """Tree view with subtle branch guides for workspace hierarchy."""

    def drawBranches(self, painter, rect, index):
        super().drawBranches(painter, rect, index)
        if not index.isValid() or rect.width() <= 0:
            return

        color = self.palette().mid().color()
        color.setAlpha(130)
        painter.save()
        painter.setPen(QPen(color, 1))
        center_x = rect.right() - max(8, self.indentation() // 2)
        center_y = rect.center().y()
        painter.drawLine(center_x, rect.top(), center_x, rect.bottom())
        painter.drawLine(center_x, center_y, rect.right(), center_y)
        painter.restore()
