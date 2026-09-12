"""Kate/KTextEditor-style uppercase, lowercase, and capitalize transforms."""

from PyQt6.QtGui import QTextCursor

from jottr.editor.spellcheck import find_word_bounds


def is_word_char(ch):
    """Return True if ch is inside a word (Kate isInWord-ish for plain text)."""
    return bool(ch) and (ch.isalnum() or ch in "_\u200c\u200d")


def to_uppercase(text):
    return text.upper()


def to_lowercase(text):
    return text.lower()


def capitalize_words(text):
    """Uppercase each character that starts a word (after lowercasing).

    Matches KTextEditor Capitalize applied to an already-lowercased selection.
    """
    chars = list(text.lower())
    for i, ch in enumerate(chars):
        if i == 0 or not is_word_char(chars[i - 1]):
            chars[i] = ch.upper()
    return "".join(chars)


def _replace_selection(cursor, new_text):
    start = cursor.selectionStart()
    cursor.insertText(new_text)
    end = cursor.position()
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)


def apply_uppercase(editor):
    """Uppercase the selection, or the character to the right of the cursor."""
    if editor is None or editor.isReadOnly():
        return False
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    try:
        if cursor.hasSelection():
            _replace_selection(cursor, to_uppercase(cursor.selectedText()))
            editor.setTextCursor(cursor)
            return True
        if not cursor.movePosition(
            QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor
        ):
            return False
        selected = cursor.selectedText()
        if not selected:
            return False
        start = cursor.selectionStart()
        cursor.insertText(to_uppercase(selected))
        cursor.setPosition(start + 1)
        editor.setTextCursor(cursor)
        return True
    finally:
        cursor.endEditBlock()


def apply_lowercase(editor):
    """Lowercase the selection, or the character to the right of the cursor."""
    if editor is None or editor.isReadOnly():
        return False
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    try:
        if cursor.hasSelection():
            _replace_selection(cursor, to_lowercase(cursor.selectedText()))
            editor.setTextCursor(cursor)
            return True
        if not cursor.movePosition(
            QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor
        ):
            return False
        selected = cursor.selectedText()
        if not selected:
            return False
        start = cursor.selectionStart()
        cursor.insertText(to_lowercase(selected))
        cursor.setPosition(start + 1)
        editor.setTextCursor(cursor)
        return True
    finally:
        cursor.endEditBlock()


def apply_capitalize(editor):
    """Capitalize words in the selection, or the word under the cursor.

    Kate runs lowercase then capitalize on the target range.
    """
    if editor is None or editor.isReadOnly():
        return False
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    try:
        if cursor.hasSelection():
            _replace_selection(cursor, capitalize_words(cursor.selectedText()))
            editor.setTextCursor(cursor)
            return True

        block = cursor.block()
        block_text = block.text()
        start_in_block, end_in_block = find_word_bounds(
            block_text, cursor.positionInBlock()
        )
        if start_in_block >= end_in_block:
            return False
        word = block_text[start_in_block:end_in_block]
        capitalized = capitalize_words(word)
        if capitalized == word:
            return False
        abs_start = block.position() + start_in_block
        abs_end = block.position() + end_in_block
        cursor.setPosition(abs_start)
        cursor.setPosition(abs_end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(capitalized)
        editor.setTextCursor(cursor)
        return True
    finally:
        cursor.endEditBlock()
