"""Selection formatting transforms for the editor context menu."""

from PyQt6.QtGui import QTextCursor


def wrap_in_quotes(text):
    return f'"{text}"'


def apply_wrap_in_quotes(editor):
    """Wrap the selection in double quotes and keep the quoted text selected."""
    if editor is None or editor.isReadOnly():
        return False
    cursor = editor.textCursor()
    if not cursor.hasSelection():
        return False
    cursor.beginEditBlock()
    try:
        start = cursor.selectionStart()
        cursor.insertText(wrap_in_quotes(cursor.selectedText()))
        end = cursor.position()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        return True
    finally:
        cursor.endEditBlock()
