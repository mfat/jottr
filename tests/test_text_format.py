"""Tests for selection formatting transforms."""
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

from jottr.editor.text_format import apply_wrap_in_quotes, wrap_in_quotes


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


class TextFormatTests(unittest.TestCase):
    def setUp(self):
        app()

    def test_wrap_in_quotes(self):
        self.assertEqual(wrap_in_quotes("hello"), '"hello"')

    def test_apply_wrap_in_quotes_selection(self):
        editor = QTextEdit()
        self.addCleanup(editor.deleteLater)
        editor.setPlainText("say hello there")
        cursor = editor.textCursor()
        cursor.setPosition(4)
        cursor.setPosition(9, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

        self.assertTrue(apply_wrap_in_quotes(editor))
        self.assertEqual(editor.toPlainText(), 'say "hello" there')
        self.assertEqual(editor.textCursor().selectedText(), '"hello"')

        editor.undo()
        self.assertEqual(editor.toPlainText(), "say hello there")

    def test_apply_wrap_in_quotes_needs_selection(self):
        editor = QTextEdit()
        self.addCleanup(editor.deleteLater)
        editor.setPlainText("hello")
        self.assertFalse(apply_wrap_in_quotes(editor))
        self.assertEqual(editor.toPlainText(), "hello")


if __name__ == "__main__":
    unittest.main()
