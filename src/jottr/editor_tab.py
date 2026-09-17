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
from jottr.editor.spellcheck import SpellChecker


def __getattr__(name):
    # The preview page imports Qt WebEngine, so it is only loaded on request.
    if name == "MarkdownPreviewPage":
        from jottr.editor.markdown import markdown_preview_page_class

        return markdown_preview_page_class()
    if name in {"Dict", "DictNotFoundError", "USE_ENCHANT"}:
        from jottr.editor import spellcheck as spellcheck_mod

        spellcheck_mod._ensure_enchant()
        return getattr(spellcheck_mod, name)
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
