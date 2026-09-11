"""Editor package: tab widget and supporting helpers."""

from jottr.editor.spellcheck import (
    FallbackSpellChecker,
    SpellCheckHighlighter,
    find_word_bounds,
    list_available_spell_languages,
    normalize_spell_languages,
    resolve_spell_languages,
)
from jottr.editor.text_edit import CompletingTextEdit, CustomTextEdit, LineNumberArea
from jottr.editor.markdown import MarkdownPreviewPage
from jottr.editor.tab import EditorTab

__all__ = [
    "CompletingTextEdit",
    "CustomTextEdit",
    "EditorTab",
    "FallbackSpellChecker",
    "LineNumberArea",
    "MarkdownPreviewPage",
    "SpellCheckHighlighter",
    "find_word_bounds",
    "list_available_spell_languages",
    "normalize_spell_languages",
    "resolve_spell_languages",
]
