"""Spell-checking helpers and markdown/syntax highlighter."""
import re

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtCore import Qt

from jottr.theme_manager import ThemeManager

try:
    from spellchecker import SpellChecker
except (ImportError, ModuleNotFoundError):
    SpellChecker = None

# Words may include internal apostrophes (shouldn't / don’t) and Arabic-script
# joiners (ZWNJ/ZWJ) used in Persian orthography (می‌روم, کتاب‌ها).
_WORD_CHARS = r"[\w\u200c\u200d]"
_WORD_PATTERN = re.compile(
    rf"(?={_WORD_CHARS}*\w){_WORD_CHARS}+(?:['’]{_WORD_CHARS}+)*",
    re.UNICODE,
)
_LOCALE_TAG = re.compile(r"^[a-z]{2}(?:_[A-Z]{2})?$")

_ARABIC_SCRIPT_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)
_LATIN_SCRIPT_RE = re.compile(r"[A-Za-z\u00C0-\u024F\u1E00-\u1EFF]")
_CYRILLIC_SCRIPT_RE = re.compile(r"[\u0400-\u04FF\u0500-\u052F]")
_HEBREW_SCRIPT_RE = re.compile(r"[\u0590-\u05FF]")

# ISO 639-1 prefixes → scripts those Enchant dictionaries typically cover.
_LANGUAGE_SCRIPTS = {
    "ar": frozenset({"arabic"}),
    "fa": frozenset({"arabic"}),
    "ur": frozenset({"arabic"}),
    "ps": frozenset({"arabic"}),
    "sd": frozenset({"arabic"}),
    "ckb": frozenset({"arabic"}),
    "ku": frozenset({"arabic", "latin"}),
    "he": frozenset({"hebrew"}),
    "yi": frozenset({"hebrew"}),
    "ru": frozenset({"cyrillic"}),
    "uk": frozenset({"cyrillic"}),
    "bg": frozenset({"cyrillic"}),
    "sr": frozenset({"cyrillic", "latin"}),
    "mk": frozenset({"cyrillic"}),
    "be": frozenset({"cyrillic"}),
}


def find_word_bounds(text, pos):
    """Return [start, end) for the word at pos, keeping contractions/ZWNJ intact."""
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


def word_scripts(word):
    """Return Unicode scripts present in word (latin/arabic/cyrillic/hebrew)."""
    scripts = set()
    if _LATIN_SCRIPT_RE.search(word):
        scripts.add("latin")
    if _ARABIC_SCRIPT_RE.search(word):
        scripts.add("arabic")
    if _CYRILLIC_SCRIPT_RE.search(word):
        scripts.add("cyrillic")
    if _HEBREW_SCRIPT_RE.search(word):
        scripts.add("hebrew")
    return scripts


def language_scripts(language):
    """Scripts covered by an Enchant/Hunspell locale tag."""
    code = str(language).replace("-", "_").split("_", 1)[0].lower()
    return _LANGUAGE_SCRIPTS.get(code, frozenset({"latin"}))


def dictionaries_cover_word(word, languages):
    """True if at least one active dictionary is meant for this word's script."""
    scripts = word_scripts(word)
    if not scripts:
        return True
    covered = set()
    for language in languages or ():
        covered |= language_scripts(language)
    return bool(scripts & covered)


def _preferred_dictionary_tags(available):
    """One locale tag per language code, preferring xx_YY over bare xx."""
    preferred = {}
    for tag in sorted(available):
        code = tag.split("_", 1)[0]
        current = preferred.get(code)
        if current is None:
            preferred[code] = tag
        elif "_" not in current and "_" in tag:
            preferred[code] = tag
    return [preferred[code] for code in sorted(preferred)]


def ensure_script_dictionaries(languages, available, disabled=None):
    """Add installed non-Latin dictionaries for scripts not yet covered.

    Installing myspell-fa should enable Persian checking without a manual
    settings visit. Tags listed in ``disabled`` stay off.
    """
    available = list(available or [])
    disabled = {str(tag).replace("-", "_") for tag in (disabled or [])}
    result = list(languages or [])
    covered = set()
    for language in result:
        covered |= language_scripts(language)

    for tag in _preferred_dictionary_tags(available):
        if tag in disabled or tag in result:
            continue
        scripts = language_scripts(tag)
        missing_non_latin = (scripts - covered) - {"latin"}
        if not missing_non_latin:
            continue
        result.append(tag)
        covered |= scripts
    return result


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
    """Active spell languages from settings, falling back to UI language.

    Also enables installed dictionaries for scripts not covered by the
    current selection (for example Persian after installing myspell-fa),
    unless the user explicitly disabled them.
    """
    available = list_available_spell_languages()
    configured = settings_manager.get_setting("spell_languages", None)
    disabled = settings_manager.get_setting("spell_languages_disabled", []) or []

    if configured:
        languages = normalize_spell_languages(configured, available)
    else:
        languages = []
        ui_language = str(settings_manager.get_setting("language", "en_US")).replace("-", "_")
        if ui_language in available:
            languages = [ui_language]
        else:
            language_code = ui_language.split("_", 1)[0]
            for tag in available:
                if tag == language_code or tag.startswith(f"{language_code}_"):
                    languages = [tag]
                    break
        languages = normalize_spell_languages(languages or ["en_US"], available)

    return ensure_script_dictionaries(languages, available, disabled=disabled)


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
        resolved = resolve_spell_languages(self.settings_manager)
        configured = self.settings_manager.get_setting("spell_languages", []) or []
        if list(resolved) != list(configured):
            # Persist auto-enabled script dictionaries (e.g. fa_IR after install).
            self.settings_manager.save_setting("spell_languages", resolved)
        self.spell_languages = resolved
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

    def _dictionary_tag(self, spell):
        """Locale tag for an Enchant dict, or a Latin default for fallbacks."""
        tag = getattr(spell, "tag", None)
        if tag:
            return str(tag).replace("-", "_")
        return "en_US"

    def _spells_for_word(self, word):
        """Backends whose script matches the word (skip English junk for Farsi)."""
        matched = [
            spell for spell in self.spells
            if dictionaries_cover_word(word, [self._dictionary_tag(spell)])
        ]
        return matched or list(self.spells)

    def check_word(self, word):
        """Return True if the word is accepted by the user dict or any active dictionary."""
        if not self.spell_check_enabled:
            return True
        if self.word_in_user_dictionary(word):
            return True
        # Don't flag Persian/Arabic/etc. against Latin-only dictionaries.
        if not dictionaries_cover_word(word, self.spell_languages):
            return True

        spells = self._spells_for_word(word)
        if self.USE_ENCHANT:
            return any(spell.check(word) for spell in spells)

        # pyspellchecker considers unknown words misspelled
        lowered = word.lower()
        return any(lowered in spell for spell in spells)

    def suggest(self, word):
        """Get suggestions for a word from the user dictionary and matching dictionaries."""
        if not self.spell_check_enabled:
            return []
        if not dictionaries_cover_word(word, self.spell_languages):
            return [
                dict_word for dict_word in self.user_dictionary_words()
                if dict_word.lower().startswith(word.lower())
            ]

        suggestions = [
            dict_word for dict_word in self.user_dictionary_words()
            if dict_word.lower().startswith(word.lower())
        ]

        try:
            for spell in self._spells_for_word(word):
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
            # Strip joiners for digit-only checks already handled; skip bare joiners.
            if not any(ch.isalnum() for ch in word):
                continue

            try:
                if not self.check_word(word):
                    self.setFormat(index, length, format)
            except UnicodeEncodeError:
                pass
