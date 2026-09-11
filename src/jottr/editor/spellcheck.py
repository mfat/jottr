"""Spell-checking helpers and markdown/syntax highlighter."""
import re

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtCore import Qt

from jottr.theme_manager import ThemeManager

try:
    from spellchecker import SpellChecker
except (ImportError, ModuleNotFoundError):
    SpellChecker = None

# Words may include internal apostrophes (shouldn't / don’t)
_WORD_PATTERN = re.compile(r"\w+(?:['’]\w+)*", re.UNICODE)
_LOCALE_TAG = re.compile(r"^[a-z]{2}(?:_[A-Z]{2})?$")


def find_word_bounds(text, pos):
    """Return [start, end) for the word at pos, keeping contractions intact."""
    if not text:
        return 0, 0

    pos = max(0, min(pos, len(text)))

    def locate(index):
        for match in _WORD_PATTERN.finditer(text):
            if match.start() <= index < match.end():
                return match.start(), match.end()
        return None

    if pos < len(text):
        found = locate(pos)
        if found:
            return found
    if pos > 0:
        found = locate(pos - 1)
        if found:
            return found
    return pos, pos


class FallbackSpellChecker:
    def __init__(self):
        self.word_frequency = self

    def __contains__(self, word):
        return True

    def check(self, word):
        return True

    def suggest(self, word):
        return []

    def candidates(self, word):
        return set()

    def add(self, word):
        return None

try:
    from enchant import Dict, DictNotFoundError
    import enchant as _enchant
    USE_ENCHANT = True
except (ImportError, ModuleNotFoundError) as e:
    print("Enchant not available, falling back to pyspellchecker:", str(e))
    Dict = None
    DictNotFoundError = Exception
    _enchant = None
    USE_ENCHANT = False

if SpellChecker is None:
    SpellChecker = FallbackSpellChecker


def list_available_spell_languages():
    """Return installed Enchant locale tags suitable for the settings UI."""
    if not USE_ENCHANT or _enchant is None:
        return ["en_US"]
    languages = []
    for tag in _enchant.list_languages():
        normalized = str(tag).replace("-", "_")
        if _LOCALE_TAG.match(normalized) and normalized not in languages:
            languages.append(normalized)
    return sorted(languages) if languages else ["en_US"]


def normalize_spell_languages(languages, available=None):
    """Deduplicate and keep only usable language tags."""
    if available is None:
        available = set(list_available_spell_languages())
    else:
        available = set(available)

    normalized = []
    for language in languages or []:
        tag = str(language).replace("-", "_")
        if tag in available and tag not in normalized:
            normalized.append(tag)
    return normalized or (["en_US"] if "en_US" in available else sorted(available)[:1] or ["en_US"])


def resolve_spell_languages(settings_manager):
    """Active spell languages from settings, falling back to UI language."""
    available = list_available_spell_languages()
    configured = settings_manager.get_setting("spell_languages", None)
    if configured:
        return normalize_spell_languages(configured, available)

    ui_language = str(settings_manager.get_setting("language", "en_US")).replace("-", "_")
    if ui_language in available:
        return [ui_language]
    language_code = ui_language.split("_", 1)[0]
    for tag in available:
        if tag == language_code or tag.startswith(f"{language_code}_"):
            return [tag]
    return normalize_spell_languages(["en_US"], available)


def _build_enchant_dicts(languages):
    dicts = []
    for language in languages:
        try:
            dicts.append(Dict(language))
        except Exception as exc:
            print(f"Could not load Enchant dictionary {language}: {exc}")
    return dicts


class SpellCheckHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.spell_check_enabled = True
        self.USE_ENCHANT = USE_ENCHANT
        self.spells = []
        self.spell_languages = []
        self.markdown_formats = {}
        self.set_theme(
            self.settings_manager.get_theme(),
            self.settings_manager.get_custom_themes(),
            rehighlight=False
        )
        self.apply_spell_settings(rehighlight=False)

    def set_theme(self, theme_name=None, custom_themes=None, rehighlight=True):
        """Refresh Markdown syntax colors from the active editor theme."""
        theme = ThemeManager.get_theme(
            theme_name or self.settings_manager.get_theme(),
            custom_themes if custom_themes is not None else self.settings_manager.get_custom_themes()
        )
        self.markdown_formats = self.build_markdown_formats(theme)
        if rehighlight:
            self.rehighlight()

    def build_markdown_formats(self, theme):
        syntax = theme["syntax"]
        editor = theme["editor"]

        def make_format(color, bold=False, italic=False, monospace=False, background=None):
            text_format = QTextCharFormat()
            text_format.setForeground(QColor(color))
            if background:
                text_format.setBackground(QColor(background))
            if bold:
                text_format.setFontWeight(QFont.Weight.Bold)
            if italic:
                text_format.setFontItalic(True)
            if monospace:
                text_format.setFontFamily("Monospace")
            return text_format

        return {
            "heading": make_format(syntax["keyword"], bold=True),
            "marker": make_format(syntax["comment"], bold=True),
            "emphasis": make_format(syntax["type"], italic=True),
            "strong": make_format(syntax["function"], bold=True),
            "code": make_format(syntax.get("constant", syntax["number"]), monospace=True, background=editor["current_line"]),
            "link": make_format(syntax["function"]),
            "url": make_format(syntax["string"]),
            "quote": make_format(syntax["comment"], italic=True),
            "list": make_format(syntax["keyword"], bold=True),
            "table": make_format(syntax["type"]),
            "html": make_format(syntax["type"]),
            "rule": make_format(syntax["comment"])
        }

    def apply_spell_settings(self, rehighlight=True):
        """Reload enable flag and active dictionaries from settings."""
        self.spell_check_enabled = bool(self.settings_manager.get_setting("spell_check", True))
        self.spell_languages = resolve_spell_languages(self.settings_manager)
        self._rebuild_spell_backends()
        if rehighlight:
            self.rehighlight()

    def set_spell_languages(self, languages, rehighlight=True):
        """Replace active dictionaries and optionally rehighlight."""
        self.spell_languages = normalize_spell_languages(languages)
        self._rebuild_spell_backends()
        if rehighlight:
            self.rehighlight()

    def _rebuild_spell_backends(self):
        self.spells = []
        self.USE_ENCHANT = USE_ENCHANT
        if self.USE_ENCHANT:
            self.spells = _build_enchant_dicts(self.spell_languages)
            if self.spells:
                return
            print("No Enchant dictionaries loaded, falling back to pyspellchecker")
            self.USE_ENCHANT = False

        try:
            self.spells = [SpellChecker()]
        except Exception as exc:
            print(f"Spell checker initialization error: {exc}, using permissive fallback")
            self.spells = [FallbackSpellChecker()]
            self.USE_ENCHANT = False

    def user_dictionary_words(self):
        return self.settings_manager.get_setting("user_dictionary", []) or []

    def word_in_user_dictionary(self, word):
        needle = word.lower()
        return any(entry.lower() == needle for entry in self.user_dictionary_words())

    def check_word(self, word):
        """Return True if the word is accepted by the user dict or any active dictionary."""
        if not self.spell_check_enabled:
            return True
        if self.word_in_user_dictionary(word):
            return True

        if self.USE_ENCHANT:
            return any(spell.check(word) for spell in self.spells)

        # pyspellchecker considers unknown words misspelled
        lowered = word.lower()
        return any(lowered in spell for spell in self.spells)

    def suggest(self, word):
        """Get suggestions for a word from the user dictionary and all active dictionaries."""
        if not self.spell_check_enabled:
            return []

        suggestions = [
            dict_word for dict_word in self.user_dictionary_words()
            if dict_word.lower().startswith(word.lower())
        ]

        try:
            for spell in self.spells:
                if self.USE_ENCHANT:
                    spell_suggestions = spell.suggest(word) or []
                else:
                    spell_suggestions = spell.candidates(word) or []
                suggestions.extend(
                    suggestion for suggestion in spell_suggestions
                    if suggestion.lower() != word.lower()
                )
        except UnicodeEncodeError:
            pass

        return list(dict.fromkeys(suggestions))

    def add_to_dictionary(self, word):
        """Add word to active backends and persist it in the user dictionary."""
        for spell in self.spells:
            try:
                if self.USE_ENCHANT:
                    spell.add(word)
                elif hasattr(spell, "word_frequency"):
                    spell.word_frequency.add(word)
            except Exception:
                pass

        user_dict = list(self.user_dictionary_words())
        if not any(entry.lower() == word.lower() for entry in user_dict):
            user_dict.append(word)
            self.settings_manager.save_setting("user_dictionary", user_dict)

        self.rehighlight()

    def highlight_markdown(self, text):
        skip_ranges = []
        self.setCurrentBlockState(0)

        fence_match = re.match(r'^\s*(`{3,}|~{3,})', text)
        if self.previousBlockState() == 1:
            self.setFormat(0, len(text), self.markdown_formats["code"])
            skip_ranges.append((0, len(text)))
            if not fence_match:
                self.setCurrentBlockState(1)
            return skip_ranges

        if fence_match:
            self.setFormat(0, len(text), self.markdown_formats["code"])
            self.setCurrentBlockState(1)
            skip_ranges.append((0, len(text)))
            return skip_ranges

        heading_match = re.match(r'^(#{1,6})(\s+.*)$', text)
        if heading_match:
            self.setFormat(heading_match.start(1), len(heading_match.group(1)), self.markdown_formats["marker"])
            self.setFormat(heading_match.start(2), len(heading_match.group(2)), self.markdown_formats["heading"])

        quote_match = re.match(r'^(\s*>+)(.*)$', text)
        if quote_match:
            self.setFormat(quote_match.start(1), len(quote_match.group(1)), self.markdown_formats["marker"])
            self.setFormat(quote_match.start(2), len(quote_match.group(2)), self.markdown_formats["quote"])

        list_match = re.match(r'^(\s*(?:[-+*]|\d+[.)])\s+(?:\[[ xX]\]\s+)?)', text)
        if list_match:
            self.setFormat(list_match.start(1), len(list_match.group(1)), self.markdown_formats["list"])

        if re.match(r'^\s*[-*_](?:\s*[-*_]){2,}\s*$', text):
            self.setFormat(0, len(text), self.markdown_formats["rule"])

        if "|" in text and re.search(r'\S\s*\|\s*\S', text):
            for match in re.finditer(r'\|', text):
                self.setFormat(match.start(), 1, self.markdown_formats["table"])

        for match in re.finditer(r'(`+)([^`]+)(\1)', text):
            self.setFormat(match.start(), match.end() - match.start(), self.markdown_formats["code"])
            skip_ranges.append((match.start(), match.end()))

        for match in re.finditer(r'(!?\[)([^\]]+)(\]\()([^)]+)(\))', text):
            self.setFormat(match.start(1), len(match.group(1)), self.markdown_formats["marker"])
            self.setFormat(match.start(2), len(match.group(2)), self.markdown_formats["link"])
            self.setFormat(match.start(3), len(match.group(3)), self.markdown_formats["marker"])
            self.setFormat(match.start(4), len(match.group(4)), self.markdown_formats["url"])
            self.setFormat(match.start(5), len(match.group(5)), self.markdown_formats["marker"])
            skip_ranges.append((match.start(4), match.end(4)))

        for match in re.finditer(r'(\*\*|__)(.+?)\1', text):
            self.setFormat(match.start(), match.end() - match.start(), self.markdown_formats["strong"])

        for match in re.finditer(r'(?<!\*)\*([^*\n]+)\*(?!\*)|(?<!_)_([^_\n]+)_(?!_)', text):
            self.setFormat(match.start(), match.end() - match.start(), self.markdown_formats["emphasis"])

        for match in re.finditer(r'</?[A-Za-z][^>]*>', text):
            self.setFormat(match.start(), match.end() - match.start(), self.markdown_formats["html"])

        return skip_ranges

    def is_in_ranges(self, index, ranges):
        return any(start <= index < end for start, end in ranges)

    def highlightBlock(self, text):
        skip_ranges = self.highlight_markdown(text)
        if not self.spell_check_enabled:
            return

        format = QTextCharFormat()
        format.setUnderlineColor(Qt.GlobalColor.red)
        format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)

        for match in _WORD_PATTERN.finditer(text):
            index = match.start()
            word = match.group(0)
            length = len(word)

            if self.is_in_ranges(index, skip_ranges):
                continue
            if word.isdigit():
                continue

            try:
                if not self.check_word(word):
                    self.setFormat(index, length, format)
            except UnicodeEncodeError:
                pass
