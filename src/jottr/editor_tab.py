"""Compatibility module for jottr.editor_tab imports."""

from PyQt6.QtWidgets import QMessageBox, QFileDialog
from PyQt6.QtCore import QTimer

from jottr.editor import (
    CompletingTextEdit,
    CustomTextEdit,
    EditorTab,
    FallbackSpellChecker,
    LineNumberArea,
    SpellCheckHighlighter,
    find_word_bounds,
)
from jottr.editor.spellcheck import SpellChecker, USE_ENCHANT, Dict, DictNotFoundError


def __getattr__(name):
    # The preview page imports Qt WebEngine, so it is only loaded on request.
    if name == "MarkdownPreviewPage":
        from jottr.editor.markdown import markdown_preview_page_class

        return markdown_preview_page_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
