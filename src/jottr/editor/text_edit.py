"""Editor text widgets with completer and line numbers."""
from PyQt6.QtWidgets import QFrame, QTextEdit, QWidget
from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import QColor, QPainter, QTextCursor

from jottr.editor.spellcheck import find_word_bounds
from jottr.translation_manager import localize_digits

class CustomTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.parent_tab = parent
        self.completer = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        if parent:
            self.customContextMenuRequested.connect(parent.show_context_menu)

    def setCompleter(self, completer):
        if self.completer:
            self.completer.activated.disconnect()
        
        self.completer = completer
        if self.completer:
            self.completer.setWidget(self)
            self.completer.activated[str].connect(self.insertCompletion)

    def insertCompletion(self, completion):
        """Insert the selected snippet"""
        if not self.completer:
            return
            
        # Get the current cursor
        tc = self.textCursor()
        
        # Delete the partially typed word
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.MoveOperation.Left)
        tc.movePosition(QTextCursor.MoveOperation.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)
        
        # Get and insert the full snippet content
        if self.parent_tab:
            snippet_content = self.parent_tab.snippet_manager.get_snippet(completion)
            if snippet_content:
                tc = self.textCursor()
                tc.movePosition(
                    QTextCursor.MoveOperation.Left,
                    QTextCursor.MoveMode.KeepAnchor,
                    len(completion),
                )
                tc.insertText(snippet_content)

    def keyPressEvent(self, event):
        if self.completer and self.completer.popup().isVisible():
            # Handle keys for autocompletion
            if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Tab):
                # Get the current completion
                current = self.completer.currentCompletion()
                if current:
                    # Insert the completion
                    self.insertCompletion(current)
                self.completer.popup().hide()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Escape:
                self.completer.popup().hide()
                event.accept()
                return
                
        super().keyPressEvent(event)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class CompletingTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.parent_tab = parent
        self.completion_text = ""
        self.completion_start = None
        self.suppress_completion = False
        self.line_numbers_visible = False
        self._zoom_wheel_delta = 0
        self.line_number_area = LineNumberArea(self)
        self.line_number_area.hide()
        self.document().blockCountChanged.connect(self.update_line_number_area_width)
        self.verticalScrollBar().valueChanged.connect(self.update_line_number_area)
        self.textChanged.connect(self.update_line_number_area)

    def line_number_area_width(self):
        digits = max(2, len(str(max(1, self.document().blockCount()))))
        return 10 + self.fontMetrics().horizontalAdvance('9') * digits

    def line_number_area_on_right(self):
        return self.layoutDirection() == Qt.LayoutDirection.RightToLeft

    def line_number_alignment(self):
        return Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter

    def line_number_background_color(self):
        return self.palette().color(self.backgroundRole())

    def line_number_language(self):
        if self.parent_tab and hasattr(self.parent_tab, "settings_manager"):
            return self.parent_tab.settings_manager.get_setting("language", "en_US")
        return None

    def format_line_number(self, number):
        return localize_digits(number, self.line_number_language())

    def set_line_numbers_visible(self, visible):
        self.line_numbers_visible = visible
        self.line_number_area.setVisible(visible)
        self.update_line_number_area_width()
        self.update_line_number_area()

    def update_line_number_area_width(self):
        width = self.line_number_area_width() if self.line_numbers_visible else 0
        if self.line_number_area_on_right():
            self.setViewportMargins(0, 0, width, 0)
        else:
            self.setViewportMargins(width, 0, 0, 0)
        self.update_line_number_area_geometry()

    def update_line_number_area(self):
        if self.line_numbers_visible:
            self.line_number_area.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_line_number_area_geometry()

    def update_line_number_area_geometry(self):
        viewport_rect = self.viewport().geometry()
        width = self.line_number_area_width()
        if self.line_number_area_on_right():
            left = viewport_rect.right() + 1
        else:
            left = viewport_rect.left() - width
        self.line_number_area.setGeometry(QRect(left, viewport_rect.top(), width, viewport_rect.height()))

    def paint_line_numbers(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), self.line_number_background_color())
        painter.setPen(QColor(120, 120, 120))

        block = self.document().firstBlock()
        layout = self.document().documentLayout()
        viewport_top = self.viewport().rect().top()
        viewport_bottom = self.viewport().rect().bottom()
        scroll_offset = self.verticalScrollBar().value()

        while block.isValid():
            block_rect = layout.blockBoundingRect(block)
            top = int(block_rect.top() - scroll_offset)
            bottom = int(block_rect.bottom() - scroll_offset)

            if bottom >= viewport_top and top <= viewport_bottom:
                number = self.format_line_number(block.blockNumber() + 1)
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width(),
                    self.fontMetrics().height(),
                    self.line_number_alignment(),
                    number
                )

            if top > viewport_bottom:
                break
            block = block.next()

    def keyPressEvent(self, event):
        """Handle key events"""
        # Handle suggestion navigation if parent has suggestions
        if (self.parent_tab and 
            self.parent_tab.suggestion_tooltip and 
            self.parent_tab.current_suggestions):
            
            if event.key() == Qt.Key.Key_Down:
                self.parent_tab.select_next_suggestion()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Up:
                self.parent_tab.select_previous_suggestion()
                event.accept()
                return
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.parent_tab.selected_suggestion_index >= 0:
                    suggestion_type, text = self.parent_tab.current_suggestions[self.parent_tab.selected_suggestion_index]
                    self.parent_tab.apply_suggestion(text)
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Tab:
                # If there's only one suggestion, apply it
                if len(self.parent_tab.current_suggestions) == 1:
                    suggestion_type, text = self.parent_tab.current_suggestions[0]
                    self.parent_tab.apply_suggestion(text)
                # If there are multiple suggestions, cycle through them
                else:
                    self.parent_tab.select_next_suggestion()
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Escape:
                self.parent_tab.hide_suggestions()
                event.accept()
                return

        super().keyPressEvent(event)

    def wheelEvent(self, event):
        """Ctrl+wheel zooms (ControlModifier is the Command key on macOS)."""
        main_window = getattr(self.parent_tab, "main_window", None)
        if main_window and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Trackpads send small deltas; zoom one step per 120 units (one wheel notch).
            self._zoom_wheel_delta += event.angleDelta().y()
            steps = int(self._zoom_wheel_delta / 120)
            self._zoom_wheel_delta -= steps * 120
            zoom = main_window.zoom_in if steps > 0 else main_window.zoom_out
            for _ in range(abs(steps)):
                zoom()
            event.accept()
            return
        super().wheelEvent(event)

    def insertFromMimeData(self, source):
        """Override paste to always use plain text"""
        if source.hasText():
            cursor = self.textCursor()
            cursor.insertText(source.text())
        
    def paintEvent(self, event):
        super().paintEvent(event)
        # Remove old completion painting code

    def check_for_completion(self):
        """Check current word against both user dictionary and snippets"""
        # This method is now handled by EditorTab's handle_text_changed
        pass

    def show_suggestions_menu(self, suggestions, start_pos):
        """Show popup menu with suggestions"""
        # This method is now replaced by EditorTab's show_suggestion_tooltip
        pass

    def apply_suggestion(self, suggestion):
        """Apply the clicked suggestion"""
        if not self.suggestion_tooltip:
            return
            
        cursor = self.editor.textCursor()
        block = cursor.block()
        text = block.text()
        pos = cursor.positionInBlock()
        
        # Replace from start of current word (including contractions) to cursor
        if pos > 0 and (text[pos - 1].isalnum() or text[pos - 1] in "_'’"):
            start, _ = find_word_bounds(text, pos - 1)
        else:
            start = pos
        
        # Find if this is a snippet or word suggestion
        is_snippet = False
        for suggestion_type, title in self.current_suggestions:
            if title == suggestion:
                is_snippet = (suggestion_type == 'snippet')
                break
        
        # Replace the current word
        cursor.movePosition(QTextCursor.MoveOperation.StartOfBlock)
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.MoveAnchor,
            start,
        )
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.KeepAnchor,
            pos - start,
        )
        
        if is_snippet:
            # Get and insert snippet content
            content = self.snippet_manager.get_snippet(suggestion)
            if content:
                cursor.insertText(content)
        else:
            # Insert the word suggestion directly
            cursor.insertText(suggestion)
        
        # Hide tooltip
        self.hide_suggestions()
        
        # Set focus back to editor
        self.editor.setFocus()

