"""Editor package: tab widget and supporting helpers."""

from jottr.editor.spellcheck import (
    DOCUMENT_LANGUAGE_AUTO,
    FallbackSpellChecker,
    SpellCheckHighlighter,
    find_word_bounds,
    list_available_spell_languages,
    normalize_spell_languages,
    resolve_document_language,
    resolve_spell_languages,
)
from jottr.editor.text_edit import CompletingTextEdit, CustomTextEdit, LineNumberArea
from jottr.editor.tab import EditorTab


def __getattr__(name):
    # The preview page imports Qt WebEngine, so it is only loaded on request.
    if name == "MarkdownPreviewPage":
        from jottr.editor.markdown import markdown_preview_page_class

        return markdown_preview_page_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "CompletingTextEdit",
    "CustomTextEdit",
    "DOCUMENT_LANGUAGE_AUTO",
    "EditorTab",
    "FallbackSpellChecker",
    "LineNumberArea",
    "MarkdownPreviewPage",
    "SpellCheckHighlighter",
    "find_word_bounds",
    "list_available_spell_languages",
    "normalize_spell_languages",
    "resolve_document_language",
    "resolve_spell_languages",
]
