"""Spell checking utilities for the editor widgets."""

import os
import sys
from typing import List, Sequence, Set

from PyQt5.QtCore import QRegExp, Qt
from PyQt5.QtGui import QTextCharFormat, QSyntaxHighlighter

# Ensure bundled vendor libraries (like pyenchant wheels) are discoverable
VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'vendor')
if os.path.exists(VENDOR_DIR) and VENDOR_DIR not in sys.path:
    sys.path.insert(0, VENDOR_DIR)


class _BaseSpellBackend:
    """Minimal interface for spell checking backends."""

    def check(self, word: str) -> bool:
        raise NotImplementedError

    def suggestions(self, word: str) -> Sequence[str]:
        raise NotImplementedError

    def add(self, word: str) -> None:
        raise NotImplementedError


class _EnchantBackend(_BaseSpellBackend):
    def __init__(self, language: str):
        from enchant import Dict, DictNotFoundError  # type: ignore

        try:
            self._dict = Dict(language)
        except DictNotFoundError:
            self._dict = Dict("en_US")

    def check(self, word: str) -> bool:
        return self._dict.check(word)

    def suggestions(self, word: str) -> Sequence[str]:
        return self._dict.suggest(word)

    def add(self, word: str) -> None:
        self._dict.add(word)


class _PySpellBackend(_BaseSpellBackend):
    def __init__(self):
        from spellchecker import SpellChecker  # type: ignore

        self._spell = SpellChecker()

    def check(self, word: str) -> bool:
        return word.lower() in self._spell

    def suggestions(self, word: str) -> Sequence[str]:
        # SpellChecker.candidates returns an unordered set – preserve deterministic order
        candidates = list(self._spell.candidates(word))
        return sorted(candidates)

    def add(self, word: str) -> None:
        self._spell.word_frequency.add(word)


class SpellCheckerHelper:
    """Factory/helper that hides spell-check backend selection and settings access."""

    def __init__(self, settings_manager, language: str = "en_US") -> None:
        self.settings_manager = settings_manager
        self.language = language
        self._backend = self._create_backend(language)
        self._using_enchant = isinstance(self._backend, _EnchantBackend)
        self._enabled = bool(self.settings_manager.get_setting('spell_check', True))
        self._user_words: List[str] = []
        self._user_words_lower: Set[str] = set()
        self._sync_user_dictionary()

    @staticmethod
    def _create_backend(language: str) -> _BaseSpellBackend:
        try:
            backend = _EnchantBackend(language)
            print("Using Enchant for spell checking")
            return backend
        except Exception as exc:  # noqa: BLE001 - ensure fallback to pyspellchecker
            print("Enchant not available, falling back to pyspellchecker:", exc)
            backend = _PySpellBackend()
            print("Using pyspellchecker for spell checking")
            return backend

    @property
    def using_enchant(self) -> bool:
        return self._using_enchant

    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self.settings_manager.save_setting('spell_check', self._enabled)

    def _sync_user_dictionary(self) -> None:
        words = self.settings_manager.get_setting('user_dictionary', []) or []
        # Preserve insertion order while removing duplicates
        seen = set()
        cleaned: List[str] = []
        for word in words:
            if not isinstance(word, str):
                continue
            normalized = word.strip()
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(normalized)
        self._user_words = cleaned
        self._user_words_lower = {word.lower() for word in cleaned}
        for word in cleaned:
            self._backend.add(word)

    def get_user_dictionary(self) -> List[str]:
        self._sync_user_dictionary()
        return list(self._user_words)

    def add_to_dictionary(self, word: str) -> None:
        if not isinstance(word, str):
            return
        normalized = word.strip()
        if not normalized:
            return
        self._sync_user_dictionary()
        if normalized.lower() not in self._user_words_lower:
            updated = list(self._user_words)
            updated.append(normalized)
            self.settings_manager.save_setting('user_dictionary', updated)
            self._user_words = updated
            self._user_words_lower = {w.lower() for w in updated}
        self._backend.add(normalized)

    def check_word(self, word: str) -> bool:
        if not self.is_enabled():
            return True
        if not word:
            return True
        if word.lower() in self._user_words_lower:
            return True
        return self._backend.check(word)

    @staticmethod
    def is_latin_word(word: str) -> bool:
        try:
            word.encode('latin-1')
            return True
        except UnicodeEncodeError:
            return False

    def suggest(self, word: str) -> List[str]:
        if not self.is_enabled():
            return []
        self._sync_user_dictionary()
        suggestions: List[str] = []
        seen_lower = set()
        for dict_word in self._user_words:
            if dict_word.lower().startswith(word.lower()):
                suggestions.append(dict_word)
                seen_lower.add(dict_word.lower())
        if self.is_latin_word(word):
            try:
                backend_suggestions = list(self._backend.suggestions(word))
            except UnicodeEncodeError:
                backend_suggestions = []
            for suggestion in backend_suggestions:
                lowered = suggestion.lower()
                if lowered == word.lower():
                    continue
                if lowered in seen_lower:
                    continue
                suggestions.append(suggestion)
                seen_lower.add(lowered)
        return suggestions


class SpellCheckHighlighter(QSyntaxHighlighter):
    """Syntax highlighter that underlines misspelled words using SpellCheckerHelper."""

    def __init__(self, parent, helper: SpellCheckerHelper) -> None:
        super().__init__(parent)
        self.helper = helper

    @property
    def spell_check_enabled(self) -> bool:
        return self.helper.is_enabled()

    @spell_check_enabled.setter
    def spell_check_enabled(self, enabled: bool) -> None:
        self.helper.set_enabled(enabled)
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API
        if not self.helper.is_enabled():
            return

        user_dict = set(word.lower() for word in self.helper.get_user_dictionary())

        format_ = QTextCharFormat()
        format_.setUnderlineColor(Qt.red)
        format_.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)

        expression = QRegExp(r"\b\w+\b")
        index = expression.indexIn(text)
        while index >= 0:
            word = expression.cap()
            length = len(word)
            if self.helper.is_latin_word(word) and word.lower() not in user_dict:
                try:
                    if not self.helper.check_word(word):
                        self.setFormat(index, length, format_)
                except UnicodeEncodeError:
                    pass
            index = expression.indexIn(text, index + length)

    def suggest(self, word: str) -> List[str]:
        return self.helper.suggest(word)

    def add_to_dictionary(self, word: str) -> None:
        self.helper.add_to_dictionary(word)
        self.rehighlight()
