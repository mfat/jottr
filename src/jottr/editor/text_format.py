"""Quote and Markdown formatting transforms for the editor context menu.

Inline formats act on the selection, or the word under the caret without one.
Line formats act on every line touched by the selection, or the current line.
"""

import re

from PyQt6.QtGui import QTextCursor

from jottr.editor.spellcheck import find_word_bounds

_HEADING_RE = re.compile(r"^#{1,6}\s+")
# Line markers "Clear Formatting" removes, repeatedly (e.g. "> - item").
_LINE_MARKER_RE = re.compile(
    r"^(\s*)(?:#{1,6}\s+|>\s?|[-*+]\s+\[[ xX]\]\s+|[-*+]\s+|\d+[.)]\s+)"
)
_FENCE_RE = re.compile(r"^\s*(?:```|~~~)\s*\w*\s*$")
# Paired inline markers only, so plain text (snake_case, 2 * 3) survives.
_INLINE_MARKERS = (
    (re.compile(r"!?\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\*\*\*(\S(?:.*?\S)?)\*\*\*"), r"\1"),
    (re.compile(r"\*\*(\S(?:.*?\S)?)\*\*"), r"\1"),
    (re.compile(r"(?<!\w)__(\S(?:.*?\S)?)__(?!\w)"), r"\1"),
    (re.compile(r"~~(\S(?:.*?\S)?)~~"), r"\1"),
    (re.compile(r"\*(\S(?:.*?\S)?)\*"), r"\1"),
    (re.compile(r"(?<!\w)_(\S(?:.*?\S)?)_(?!\w)"), r"\1"),
    (re.compile(r"`([^`]+)`"), r"\1"),
)


def wrap_in_quotes(text):
    return f'"{text}"'


def _select(cursor, start, end):
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)


def inline_target(editor):
    """Return a cursor selecting the selection or the word under the caret, else None."""
    cursor = editor.textCursor()
    if cursor.hasSelection():
        return cursor
    block = cursor.block()
    start, end = find_word_bounds(block.text(), cursor.positionInBlock())
    if start >= end:
        return None
    _select(cursor, block.position() + start, block.position() + end)
    return cursor


def _editable(editor):
    return editor is not None and not editor.isReadOnly()


def apply_wrap(editor, prefix, suffix=None):
    """Wrap the inline target in prefix/suffix and select the wrapped text."""
    if not _editable(editor):
        return False
    cursor = inline_target(editor)
    if cursor is None:
        return False
    suffix = prefix if suffix is None else suffix
    cursor.beginEditBlock()
    try:
        start = cursor.selectionStart()
        cursor.insertText(f"{prefix}{cursor.selectedText()}{suffix}")
        _select(cursor, start, cursor.position())
        editor.setTextCursor(cursor)
        return True
    finally:
        cursor.endEditBlock()


def apply_wrap_in_quotes(editor):
    return apply_wrap(editor, '"')


def apply_link(editor):
    """Turn the inline target into [text](url) and select the url placeholder."""
    if not _editable(editor):
        return False
    cursor = inline_target(editor)
    if cursor is None:
        return False
    cursor.beginEditBlock()
    try:
        cursor.insertText(f"[{cursor.selectedText()}](url)")
        end = cursor.position() - 1
        _select(cursor, end - len("url"), end)
        editor.setTextCursor(cursor)
        return True
    finally:
        cursor.endEditBlock()


def _target_blocks(editor):
    """Return the blocks touched by the selection, or the caret's block."""
    cursor = editor.textCursor()
    doc = editor.document()
    first = doc.findBlock(cursor.selectionStart())
    last = doc.findBlock(cursor.selectionEnd())
    # A selection ending at the start of a line does not include that line.
    if last != first and cursor.selectionEnd() == last.position():
        last = last.previous()
    blocks = [first]
    while blocks[-1] != last:
        blocks.append(blocks[-1].next())
    return blocks


def _prefix_lines(editor, make_prefix, strip_re=None):
    if not _editable(editor):
        return False
    blocks = _target_blocks(editor)
    cursor = editor.textCursor()
    start = blocks[0].position()
    lines = []
    for index, block in enumerate(blocks):
        text = block.text()
        if strip_re is not None:
            text = strip_re.sub("", text, count=1)
        lines.append(make_prefix(index) + text)
    cursor.beginEditBlock()
    try:
        last = blocks[-1]
        _select(cursor, start, last.position() + last.length() - 1)
        cursor.insertText("\n".join(lines))
        _select(cursor, start, cursor.position())
        editor.setTextCursor(cursor)
        return True
    finally:
        cursor.endEditBlock()


def apply_heading(editor, level):
    """Make target lines headings, replacing any existing heading marker."""
    return _prefix_lines(editor, lambda _index: "#" * level + " ", _HEADING_RE)


def apply_line_prefix(editor, prefix):
    return _prefix_lines(editor, lambda _index: prefix)


def apply_numbered_list(editor):
    return _prefix_lines(editor, lambda index: f"{index + 1}. ")


def apply_code_block(editor):
    """Fence the target lines in a ``` code block."""
    if not _editable(editor):
        return False
    blocks = _target_blocks(editor)
    cursor = editor.textCursor()
    start = blocks[0].position()
    last = blocks[-1]
    cursor.beginEditBlock()
    try:
        _select(cursor, start, last.position() + last.length() - 1)
        body = cursor.selectedText().replace(" ", "\n")
        cursor.insertText(f"```\n{body}\n```")
        _select(cursor, start, cursor.position())
        editor.setTextCursor(cursor)
        return True
    finally:
        cursor.endEditBlock()


def clear_markdown(text):
    """Return *text* without Markdown markers (fence lines are dropped)."""
    lines = []
    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            continue
        while True:
            stripped = _LINE_MARKER_RE.sub(r"\1", line, count=1)
            if stripped == line:
                break
            line = stripped
        for pattern, replacement in _INLINE_MARKERS:
            line = pattern.sub(replacement, line)
        lines.append(line)
    return "\n".join(lines)


def apply_clear_formatting(editor):
    """Strip Markdown markers from the selection, or from the current line."""
    if not _editable(editor):
        return False
    original = editor.textCursor()
    cursor = editor.textCursor()
    if cursor.hasSelection():
        start = cursor.selectionStart()
    else:
        blocks = _target_blocks(editor)
        start = blocks[0].position()
        last = blocks[-1]
        _select(cursor, start, last.position() + last.length() - 1)
    # selectedText() separates blocks with U+2029, not a newline.
    source = cursor.selectedText().replace("\u2029", "\n")
    cleaned = clear_markdown(source)
    if cleaned == source:
        # Nothing to strip: leave the document and the undo stack alone.
        editor.setTextCursor(original)
        return False
    cursor.beginEditBlock()
    try:
        cursor.insertText(cleaned)
        _select(cursor, start, cursor.position())
        editor.setTextCursor(cursor)
        return True
    finally:
        cursor.endEditBlock()
