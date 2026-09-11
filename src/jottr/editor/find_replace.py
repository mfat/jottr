"""Find/replace helpers for EditorTab."""
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor, QTextDocument
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox

from jottr.translation_manager import _


class FindReplaceMixin:
    def toggle_find(self):
        """Toggle find/replace toolbar visibility"""
        visible = not self.find_toolbar.isVisible()
        self.find_toolbar.setVisible(visible)
        if visible:
            self.find_input.setFocus()
            # Select text if any is selected
            cursor = self.editor.textCursor()
            if cursor.hasSelection():
                self.find_input.setText(cursor.selectedText())
                self.find_input.selectAll()
        else:
            # Clear highlighting when closing
            self.clear_highlights()
            self.editor.setFocus()

        # Update the search action state in the main toolbar if it exists
        if hasattr(self, 'main_window'):
            for action in self.main_window.toolbar.actions():
                if (
                    action.property("text_key") == "Find/Replace"
                    or action.text() == _("Find/Replace")
                ):
                    action.setChecked(visible)
                    break

    def find_text(self, direction='down'):
        """Find text in editor"""
        text = self.find_input.text()
        if not text:
            return
            
        cursor = self.editor.textCursor()
        document = self.editor.document()
        
        # Create find flags
        flags = QTextDocument.FindFlag(0)
        if direction == 'up':
            flags |= QTextDocument.FindFlag.FindBackward
            
        # Remove case sensitivity flag to make search case-insensitive
        # flags |= QTextDocument.FindFlag.FindCaseSensitively  # Commented out to make case-insensitive
            
        # Find next occurrence
        if not self.editor.find(text, flags):
            # If not found, wrap around
            cursor = QTextCursor(document)
            self.editor.setTextCursor(cursor)
            self.editor.find(text, flags)

    def replace_text(self):
        """Replace current occurrence"""
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        
        if not find_text:
            return
        
        cursor = self.editor.textCursor()
        
        # If no text is selected, find next occurrence first
        if not cursor.hasSelection():
            self.find_text()
            cursor = self.editor.textCursor()
        
        # Check if we have a valid selection that matches the search text (case-insensitive)
        if cursor.hasSelection() and cursor.selectedText().lower() == find_text.lower():
            cursor.beginEditBlock()
            cursor.insertText(replace_text)
            cursor.endEditBlock()
            # Find next occurrence
            self.find_text()

    def replace_all(self):
        """Replace all occurrences"""
        find_text = self.find_input.text()
        replace_text = self.replace_input.text()
        
        if not find_text:
            return
        
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()
        
        # Move to start
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        
        # Create find flags for case-insensitive search
        flags = QTextDocument.FindFlag(0)
        # flags |= QTextDocument.FindFlag.FindCaseSensitively  # Commented out to make case-insensitive
        
        # Replace all occurrences
        count = 0
        while self.editor.find(find_text, flags):
            cursor = self.editor.textCursor()
            cursor.insertText(replace_text)
            count += 1
        
        cursor.endEditBlock()
        
        # Show message with count
        QMessageBox.information(
            self,
            _("Replace All"),
            _("Replaced {count} occurrence(s)").format(count=count)
        )
        
        # Move cursor back to start
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)

    def clear_highlights(self):
        """Clear any search highlighting"""
        cursor = self.editor.textCursor()
        cursor.clearSelection()
        self.editor.setTextCursor(cursor)

