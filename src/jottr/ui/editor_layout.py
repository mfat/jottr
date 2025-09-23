"""Reusable UI components for the editor layout."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QLineEdit,
)


class EditorPane(QWidget):
    """Container widget that hosts the main text editor."""

    def __init__(self, editor_widget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(editor_widget)


class SnippetPane(QWidget):
    """Side pane that lists available snippets."""

    close_requested = pyqtSignal()
    snippet_activated = pyqtSignal(str)
    context_menu_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget(self)
        header.setFixedHeight(28)
        header.setStyleSheet("""
            QWidget {
                background-color: palette(window);
                padding: 0px;
                margin: 0px;
            }
            QPushButton {
                border: none;
                padding: 0px;
                margin: 0px;
                color: palette(text);
            }
            QPushButton:hover {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
        """)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 2, 4, 2)
        header_layout.setSpacing(4)

        title = QLabel("Snippets", header)
        title.setStyleSheet("font-weight: bold; padding: 0px; margin: 0px;")
        header_layout.addWidget(title)

        close_button = QPushButton("×", header)
        close_button.setFixedSize(20, 20)
        close_button.clicked.connect(self.close_requested)
        header_layout.addWidget(close_button)

        layout.addWidget(header)

        self._list_widget = QListWidget(self)
        self._list_widget.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: palette(base);
            }
            QListWidget::item {
                padding: 4px;
                border-radius: 2px;
            }
            QListWidget::item:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
            QListWidget::item:selected:hover {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
            QListWidget::item:hover:!selected {
                background-color: palette(alternate-base);
            }
        """)
        self._list_widget.itemDoubleClicked.connect(self._emit_snippet_activated)
        self._list_widget.customContextMenuRequested.connect(
            lambda pos: self.context_menu_requested.emit(
                pos, self._list_widget.mapToGlobal(pos)
            )
        )
        layout.addWidget(self._list_widget)

    def _emit_snippet_activated(self, item):
        if item:
            self.snippet_activated.emit(item.text())

    def set_snippets(self, snippets):
        """Populate the pane with snippet titles."""
        self._list_widget.clear()
        self._list_widget.addItems(snippets)

    def current_snippet(self):
        """Return the currently selected snippet title if any."""
        current_item = self._list_widget.currentItem()
        return current_item.text() if current_item else None

    def map_to_global(self, position):
        """Translate a local position to a global screen position."""
        return self._list_widget.mapToGlobal(position)

    def set_current_snippet(self, title):
        """Select the first snippet matching *title*."""
        matching_items = self._list_widget.findItems(title, Qt.MatchExactly)
        if matching_items:
            self._list_widget.setCurrentItem(matching_items[0])


class BrowserPane(QWidget):
    """Side pane that embeds the web browser widget."""

    close_requested = pyqtSignal()
    navigate_requested = pyqtSignal(str)
    back_requested = pyqtSignal()
    forward_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QWidget(self)
        toolbar.setFixedHeight(32)
        toolbar.setStyleSheet("""
            QWidget {
                background: palette(window);
                border-bottom: 1px solid palette(mid);
            }
            QLineEdit {
                border: 1px solid palette(mid);
                border-radius: 3px;
                padding: 2px 8px;
                background: palette(base);
                selection-background-color: palette(highlight);
                margin: 4px;
            }
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 3px;
                padding: 4px;
                margin: 2px;
                color: palette(text);
            }
            QPushButton:hover {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
        """)

        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 0, 4, 0)
        toolbar_layout.setSpacing(2)

        self._back_btn = QPushButton("←", toolbar)
        self._back_btn.setFixedSize(24, 24)
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(self.back_requested)
        toolbar_layout.addWidget(self._back_btn)

        self._forward_btn = QPushButton("→", toolbar)
        self._forward_btn.setFixedSize(24, 24)
        self._forward_btn.setEnabled(False)
        self._forward_btn.clicked.connect(self.forward_requested)
        toolbar_layout.addWidget(self._forward_btn)

        self._url_bar = QLineEdit(toolbar)
        self._url_bar.setPlaceholderText("Search or enter address")
        self._url_bar.returnPressed.connect(self._emit_navigation)
        toolbar_layout.addWidget(self._url_bar)

        close_btn = QPushButton("×", toolbar)
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.close_requested)
        toolbar_layout.addWidget(close_btn)

        layout.addWidget(toolbar)

        self._container = QWidget(self)
        container_layout = QVBoxLayout(self._container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        layout.addWidget(self._container)

    @property
    def container_layout(self):
        return self._container.layout()

    def _emit_navigation(self):
        self.navigate_requested.emit(self.url())

    def url(self):
        return self._url_bar.text().strip()

    def set_url(self, url):
        self._url_bar.setText(url)

    def set_url_enabled(self, enabled):
        self._url_bar.setEnabled(enabled)

    def set_navigation_enabled(self, back_enabled, forward_enabled):
        self._back_btn.setEnabled(back_enabled)
        self._forward_btn.setEnabled(forward_enabled)

    def set_web_view(self, web_view):
        self.clear_web_view()
        self.container_layout.addWidget(web_view)

    def clear_web_view(self):
        layout = self.container_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def has_web_view(self):
        return self.container_layout.count() > 0

    def focus_url_bar(self):
        self._url_bar.setFocus()

