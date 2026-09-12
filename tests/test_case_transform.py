"""Tests for Kate-style case transforms."""
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

from jottr.editor.case_transform import (
    apply_capitalize,
    apply_lowercase,
    apply_uppercase,
    capitalize_words,
    to_lowercase,
    to_uppercase,
)


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or _APP or QApplication(["jottr-tests"])
    return _APP


class CaseTransformTests(unittest.TestCase):
    def setUp(self):
        app()

    def test_pure_transforms(self):
        self.assertEqual(to_uppercase("Hello"), "HELLO")
        self.assertEqual(to_lowercase("Hello"), "hello")
        self.assertEqual(capitalize_words("hello WORLD"), "Hello World")
        self.assertEqual(capitalize_words("déjà VU"), "Déjà Vu")

    def test_uppercase_selection_and_character(self):
        editor = QTextEdit()
        self.addCleanup(editor.deleteLater)
        editor.setPlainText("abc")
        cursor = editor.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(2, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

        self.assertTrue(apply_uppercase(editor))
        self.assertEqual(editor.toPlainText(), "ABc")
        self.assertEqual(editor.textCursor().selectedText(), "AB")

        cursor = editor.textCursor()
        cursor.clearSelection()
        cursor.setPosition(2)
        editor.setTextCursor(cursor)
        self.assertTrue(apply_uppercase(editor))
        self.assertEqual(editor.toPlainText(), "ABC")

        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        editor.setTextCursor(cursor)
        self.assertFalse(apply_uppercase(editor))

    def test_lowercase_and_capitalize_selection(self):
        editor = QTextEdit()
        self.addCleanup(editor.deleteLater)
        editor.setPlainText("HELLO WORLD")
        editor.selectAll()
        self.assertTrue(apply_lowercase(editor))
        self.assertEqual(editor.toPlainText(), "hello world")

        editor.selectAll()
        self.assertTrue(apply_capitalize(editor))
        self.assertEqual(editor.toPlainText(), "Hello World")

    def test_capitalize_word_under_cursor(self):
        editor = QTextEdit()
        self.addCleanup(editor.deleteLater)
        editor.setPlainText("say HELLO there")
        cursor = editor.textCursor()
        cursor.setPosition(editor.toPlainText().index("E"))
        editor.setTextCursor(cursor)
        self.assertTrue(apply_capitalize(editor))
        self.assertEqual(editor.toPlainText(), "say Hello there")


if __name__ == "__main__":
    unittest.main()
