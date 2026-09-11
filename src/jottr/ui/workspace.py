"""Workspace explorer widgets."""
from PyQt6.QtWidgets import QTreeView
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFileSystemModel, QPen


class WorkspaceFileSystemModel(QFileSystemModel):
    """File model that exposes full paths as tooltips."""

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.ToolTipRole and index.isValid():
            return self.filePath(index)
        return super().data(index, role)


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
