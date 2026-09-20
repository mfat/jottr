"""Tests for quote and Markdown formatting transforms."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication, QTextEdit

from jottr.editor.text_format import (
    apply_clear_formatting,
    apply_code_block,
    apply_heading,
    apply_line_prefix,
    apply_link,
    apply_numbered_list,
    apply_wrap,
    apply_wrap_in_quotes,
    clear_markdown,
    wrap_in_quotes,
)


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


class TextFormatTests(unittest.TestCase):
    def setUp(self):
        app()

    def make_editor(self, text):
        editor = QTextEdit()
        self.addCleanup(editor.deleteLater)
        editor.setPlainText(text)
        return editor

    def select(self, editor, start, end):
        cursor = editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

    def place_caret(self, editor, position):
        cursor = editor.textCursor()
        cursor.setPosition(position)
        editor.setTextCursor(cursor)

    def test_wrap_in_quotes(self):
        self.assertEqual(wrap_in_quotes("hello"), '"hello"')

    def test_apply_wrap_in_quotes_selection(self):
        editor = self.make_editor("say hello there")
        self.select(editor, 4, 9)

        self.assertTrue(apply_wrap_in_quotes(editor))
        self.assertEqual(editor.toPlainText(), 'say "hello" there')
        self.assertEqual(editor.textCursor().selectedText(), '"hello"')

        editor.undo()
        self.assertEqual(editor.toPlainText(), "say hello there")

    def test_inline_wrap_uses_word_under_caret(self):
        editor = self.make_editor("say hello there")
        self.place_caret(editor, 6)
        self.assertTrue(apply_wrap(editor, "**"))
        self.assertEqual(editor.toPlainText(), "say **hello** there")

    def test_inline_wrap_needs_selection_or_word(self):
        editor = self.make_editor("")
        self.assertFalse(apply_wrap_in_quotes(editor))
        self.assertEqual(editor.toPlainText(), "")

    def test_link_selects_url_placeholder(self):
        editor = self.make_editor("see docs here")
        self.select(editor, 4, 8)
        self.assertTrue(apply_link(editor))
        self.assertEqual(editor.toPlainText(), "see [docs](url) here")
        self.assertEqual(editor.textCursor().selectedText(), "url")

    def test_heading_on_current_line_replaces_existing_marker(self):
        editor = self.make_editor("one\n## two\nthree")
        self.place_caret(editor, 6)
        self.assertTrue(apply_heading(editor, 1))
        self.assertEqual(editor.toPlainText(), "one\n# two\nthree")

    def test_line_prefix_on_selected_lines(self):
        editor = self.make_editor("one\ntwo\nthree")
        # Selection ending at the start of "three" leaves that line alone.
        self.select(editor, 1, 8)
        self.assertTrue(apply_line_prefix(editor, "- "))
        self.assertEqual(editor.toPlainText(), "- one\n- two\nthree")

        editor.undo()
        self.assertEqual(editor.toPlainText(), "one\ntwo\nthree")

    def test_numbered_list(self):
        editor = self.make_editor("one\ntwo")
        editor.selectAll()
        self.assertTrue(apply_numbered_list(editor))
        self.assertEqual(editor.toPlainText(), "1. one\n2. two")

    def test_code_block(self):
        editor = self.make_editor("a\nb\nc")
        self.select(editor, 0, 3)
        self.assertTrue(apply_code_block(editor))
        self.assertEqual(editor.toPlainText(), "```\na\nb\n```\nc")



    def test_clear_markdown_strips_markers_and_keeps_plain_text(self):
        self.assertEqual(clear_markdown("# Title"), "Title")
        self.assertEqual(clear_markdown("> - [ ] **do** it"), "do it")
        self.assertEqual(clear_markdown("1. *one* and `two`"), "one and two")
        self.assertEqual(clear_markdown("a [link](http://x)"), "a link")
        self.assertEqual(clear_markdown("~~gone~~"), "gone")
        # Lone markers in prose are not pairs, so they stay.
        self.assertEqual(clear_markdown("snake_case and 2 * 3"), "snake_case and 2 * 3")

    def test_clear_markdown_drops_code_fences(self):
        self.assertEqual(
            clear_markdown("```python\nprint(1)\n```"),
            "print(1)",
        )

    def test_apply_clear_formatting_without_selection_clears_the_line(self):
        editor = self.make_editor("## **Title**\nplain *line*")
        self.place_caret(editor, 4)

        self.assertTrue(apply_clear_formatting(editor))
        self.assertEqual(editor.toPlainText(), "Title\nplain *line*")

    def test_apply_clear_formatting_clears_only_the_selection(self):
        editor = self.make_editor("**one** and **two**")
        self.select(editor, 0, len("**one**"))

        self.assertTrue(apply_clear_formatting(editor))
        self.assertEqual(editor.toPlainText(), "one and **two**")
        self.assertEqual(editor.textCursor().selectedText(), "one")

    def test_apply_clear_formatting_spans_selected_lines(self):
        editor = self.make_editor("# One\n- two\nthree")
        self.select(editor, 0, len("# One\n- two"))

        self.assertTrue(apply_clear_formatting(editor))
        self.assertEqual(editor.toPlainText(), "One\ntwo\nthree")

    def test_apply_clear_formatting_leaves_unformatted_text_alone(self):
        editor = self.make_editor("plain text")
        self.place_caret(editor, 3)

        self.assertFalse(apply_clear_formatting(editor))
        self.assertEqual(editor.toPlainText(), "plain text")
        self.assertFalse(editor.textCursor().hasSelection())
        self.assertFalse(editor.document().isUndoAvailable())

    def test_apply_clear_formatting_skips_read_only_editor(self):
        editor = self.make_editor("# Title")
        editor.setReadOnly(True)

        self.assertFalse(apply_clear_formatting(editor))
        self.assertEqual(editor.toPlainText(), "# Title")


if __name__ == "__main__":
    unittest.main()
