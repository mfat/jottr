"""Utilities for driving inline completion suggestions in the editor."""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

from PyQt5.QtCore import QObject, Qt
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

Suggestion = Tuple[str, str]


class SuggestionPopup(QWidget):
    """Lightweight widget that renders completion suggestions."""

    def __init__(self, parent: QWidget, click_handler: Callable[[Suggestion], None]):
        super().__init__(parent, Qt.ToolTip)
        self._click_handler = click_handler
        self._containers: List[QWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.setStyleSheet(
            """
            QWidget {
                background-color: palette(window);
                border: 1px solid palette(mid);
                border-radius: 3px;
            }
            QLabel {
                padding: 2px 8px;
                color: palette(text);
                border-radius: 2px;
                margin: 1px;
                font-family: "Courier New", "DejaVu Sans Mono", monospace;
            }
            """
        )

    def set_suggestions(self, suggestions: Sequence[Suggestion], snippet_resolver: Callable[[str], Optional[str]]) -> None:
        """Populate the popup with the provided suggestions."""
        layout = self.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._containers.clear()

        for suggestion_type, text in suggestions:
            container = QWidget(self)
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(1)

            if suggestion_type == "snippet":
                content = snippet_resolver(text)
                if content:
                    preview = content.split("\n")[0][:50]
                    if len(preview) < len(content):
                        preview += "..."
                    label = QLabel(preview, container)
                else:
                    label = QLabel(text, container)
            else:
                label = QLabel(text, container)

            container_layout.addWidget(label)
            container.mousePressEvent = lambda _, s=(suggestion_type, text): self._click_handler(s)
            container.setCursor(Qt.PointingHandCursor)

            layout.addWidget(container)
            self._containers.append(container)

        self.adjustSize()

    def highlight(self, index: int) -> None:
        """Update the highlighted suggestion."""
        for current_index, container in enumerate(self._containers):
            if current_index == index:
                container.setStyleSheet(
                    """
                    background-color: palette(highlight);
                    border-radius: 2px;
                    QLabel { color: palette(highlighted-text); }
                    """
                )
            else:
                container.setStyleSheet("")


class CompletionController(QObject):
    """Controller that drives completion suggestions for a ``QTextEdit``."""

    def __init__(
        self,
        text_edit,
        snippet_manager=None,
        settings_manager=None,
    ):
        super().__init__(text_edit)
        self._text_edit = text_edit
        self._snippet_manager = snippet_manager
        self._settings_manager = settings_manager
        self._popup: Optional[SuggestionPopup] = None
        self._current_suggestions: List[Suggestion] = []
        self._selected_index = -1

        if self._text_edit is not None:
            self._text_edit.textChanged.connect(self.handle_text_changed)

    # ------------------------------------------------------------------
    # Public API used by the widgets
    # ------------------------------------------------------------------
    def handle_text_changed(self) -> None:
        """Compute suggestions whenever the text changes."""
        self.hide_suggestions()

        if self._text_edit is None:
            return

        cursor = self._text_edit.textCursor()
        block = cursor.block()
        text = block.text()
        pos = cursor.positionInBlock()

        start = pos
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] in "_-"):
            start -= 1
        current_word = text[start:pos]

        if len(current_word) < 2:
            return

        lowered = current_word.lower()
        suggestions: List[Suggestion] = []

        if self._snippet_manager:
            for title in self._snippet_manager.get_snippets():
                if title.lower().startswith(lowered):
                    suggestions.append(("snippet", title))

        if self._settings_manager:
            user_dict = self._settings_manager.get_setting("user_dictionary", [])
            for word in user_dict:
                candidate = word.lower()
                if candidate.startswith(lowered) and candidate != lowered:
                    suggestions.append(("word", word))

        if suggestions:
            self.show_suggestions(suggestions[:7], cursor)

    def handle_key_press(self, event) -> bool:
        """Allow the controller to consume navigation keys."""
        if not self._current_suggestions:
            return False

        key = event.key()
        if key == Qt.Key_Down:
            self.select_next_suggestion()
            return True
        if key == Qt.Key_Up:
            self.select_previous_suggestion()
            return True
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self._selected_index >= 0:
                self.apply_suggestion(self._current_suggestions[self._selected_index])
            return True
        if key == Qt.Key_Tab:
            if len(self._current_suggestions) == 1:
                self.apply_suggestion(self._current_suggestions[0])
            else:
                self.select_next_suggestion()
            return True
        if key == Qt.Key_Escape:
            self.hide_suggestions()
            return True

        return False

    def hide_suggestions(self) -> None:
        """Hide the suggestion popup if it is visible."""
        if self._popup:
            self._popup.hide()
            self._popup.deleteLater()
            self._popup = None
        self._current_suggestions = []
        self._selected_index = -1

    def has_suggestions(self) -> bool:
        """Return whether the controller is currently showing suggestions."""
        return bool(self._current_suggestions)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def show_suggestions(self, suggestions: Sequence[Suggestion], cursor: QTextCursor) -> None:
        self.hide_suggestions()

        self._current_suggestions = list(suggestions)
        self._selected_index = -1

        self._popup = SuggestionPopup(self._text_edit, self.apply_suggestion)
        self._popup.set_suggestions(self._current_suggestions, self._resolve_snippet)

        rect = self._text_edit.cursorRect(cursor)
        pos = self._text_edit.mapToGlobal(rect.bottomLeft())
        pos.setY(pos.y() + 5)
        self._popup.move(pos)
        self._popup.show()
        self._popup.raise_()

    def select_next_suggestion(self) -> None:
        if not self._current_suggestions:
            return
        self._selected_index = (self._selected_index + 1) % len(self._current_suggestions)
        self._update_highlighting()

    def select_previous_suggestion(self) -> None:
        if not self._current_suggestions:
            return
        self._selected_index = (self._selected_index - 1) % len(self._current_suggestions)
        self._update_highlighting()

    def _update_highlighting(self) -> None:
        if self._popup and self._selected_index >= 0:
            self._popup.highlight(self._selected_index)

    def apply_suggestion(self, suggestion: Suggestion) -> None:
        if not self._text_edit:
            return

        suggestion_type, text = suggestion

        cursor = self._text_edit.textCursor()
        block = cursor.block()
        block_text = block.text()
        pos = cursor.positionInBlock()

        start = pos
        while start > 0 and (block_text[start - 1].isalnum() or block_text[start - 1] == "_"):
            start -= 1

        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, start)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, pos - start)

        if suggestion_type == "snippet":
            content = self._resolve_snippet(text)
            if content:
                cursor.insertText(content)
            else:
                cursor.insertText(text)
        else:
            cursor.insertText(text)

        self.hide_suggestions()
        self._text_edit.setFocus()

    def _resolve_snippet(self, title: str) -> Optional[str]:
        if not self._snippet_manager:
            return None
        return self._snippet_manager.get_snippet(title)
