"""Compatibility module for jottr.editor_tab imports."""

from PyQt6.QtWidgets import QMessageBox, QFileDialog
from PyQt6.QtCore import QTimer

from jottr.editor import (
    CompletingTextEdit,
    CustomTextEdit,
    EditorTab,
    FallbackSpellChecker,
    LineNumberArea,
    MarkdownPreviewPage,
    SpellCheckHighlighter,
    find_word_bounds,
)
from jottr.editor.spellcheck import SpellChecker, USE_ENCHANT, Dict, DictNotFoundError

__all__ = [
    "CompletingTextEdit",
    "CustomTextEdit",
    "Dict",
    "DictNotFoundError",
    "EditorTab",
    "FallbackSpellChecker",
    "LineNumberArea",
    "MarkdownPreviewPage",
    "QFileDialog",
    "QMessageBox",
    "QTimer",
    "SpellCheckHighlighter",
    "SpellChecker",
    "USE_ENCHANT",
    "find_word_bounds",
]
