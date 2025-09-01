from __future__ import annotations

from typing import Iterable

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QTabWidget, QWidget, QHBoxLayout, QToolButton, QAction


class RibbonBar(QTabWidget):
    """Simple ribbon-style tab widget."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDocumentMode(True)

    def add_page(self, title: str, widgets: Iterable[QWidget | QAction]) -> None:
        """Add a ribbon page comprised of widgets or actions."""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(8, 4, 8, 4)
        for item in widgets:
            if isinstance(item, QAction):
                btn = QToolButton()
                btn.setDefaultAction(item)
                btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                btn.setIconSize(QSize(32, 32))
                layout.addWidget(btn)
            else:
                layout.addWidget(item)
        layout.addStretch()
        self.addTab(page, title)
