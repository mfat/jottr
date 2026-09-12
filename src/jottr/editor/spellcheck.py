"""Spell-checking helpers and markdown/syntax highlighter."""
import re
from functools import lru_cache

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtCore import Qt

from jottr.theme_manager import ThemeManager

try:
    from spellchecker import SpellChecker
except (ImportError, ModuleNotFoundError):
    SpellChecker = None

try:
    from langdetect import DetectorFactory, LangDetectException, detect_langs
    DetectorFactory.seed = 0
    USE_LANGDETECT = True
except (ImportError, ModuleNotFoundError):
    detect_langs = None
    LangDetectException = Exception
    USE_LANGDETECT = False

# Words may include internal apostrophes (shouldn't / don’t) and Arabic-script
# joiners (ZWNJ/ZWJ) used in Persian orthography (می‌روم, کتاب‌ها).
_WORD_CHARS = r"[\w\u200c\u200d]"
_WORD_PATTERN = re.compile(
    rf"(?={_WORD_CHARS}*\w){_WORD_CHARS}+(?:['’]{_WORD_CHARS}+)*",
    re.UNICODE,
)
_LOCALE_TAG = re.compile(r"^[a-z]{2}(?:_[A-Z]{2})?$")
DOCUMENT_LANGUAGE_AUTO = "auto"
# Non-Latin scripts pack more meaning per character; keep this low.
MIN_LANGUAGE_DETECT_CHARS = 12
LANGUAGE_DETECT_MIN_CONFIDENCE = 0.50
_AUTO_LANGUAGE_ALIASES = {
    "auto",
    "auto_detect",
    "autodetect",
    "automatic",
}

# Preferred locale when langdetect returns a bare ISO-639-1 code.
ISO_DEFAULT_LOCALES = {
    "en": "en_US",
    "fa": "fa_IR",
    "ar": "ar_SA",
    "de": "de_DE",
    "fr": "fr_FR",
    "es": "es_ES",
    "it": "it_IT",
    "pt": "pt_BR",
    "ru": "ru_RU",
    "tr": "tr_TR",
    "zh-cn": "zh_CN",
    "zh-tw": "zh_TW",
    "ja": "ja_JP",
    "ko": "ko_KR",
    "he": "he_IL",
    "hi": "hi_IN",
    "nl": "nl_NL",
    "pl": "pl_PL",
    "uk": "uk_UA",
    "sv": "sv_SE",
    "cs": "cs_CZ",
    "ro": "ro_RO",
    "id": "id_ID",
}

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
    return _word_scripts_cached(word)


@lru_cache(maxsize=4096)
def _word_scripts_cached(word):
    """Cached script detection (words repeat heavily within a document)."""
    scripts = set()
    if _LATIN_SCRIPT_RE.search(word):
        scripts.add("latin")
    if _ARABIC_SCRIPT_RE.search(word):
        scripts.add("arabic")
    if _CYRILLIC_SCRIPT_RE.search(word):
        scripts.add("cyrillic")
    if _HEBREW_SCRIPT_RE.search(word):
        scripts.add("hebrew")
    return frozenset(scripts)


def language_scripts(language):
    """Scripts covered by an Enchant/Hunspell locale tag."""
    return _language_scripts_cached(str(language))


@lru_cache(maxsize=None)
def _language_scripts_cached(language):
    """Cached script coverage (only a handful of distinct locale tags exist)."""
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


_available_spell_languages_cache = None


def list_available_spell_languages():
    """Return installed Enchant locale tags suitable for the settings UI.

    The broker enumeration hits every provider on each call (~0.35ms), and
    this runs dozens of times per settings pass, so the result is cached.
    Installed dictionaries do not change at runtime; tests patch this
    function itself, which bypasses the cache.
    """
    global _available_spell_languages_cache
    if _available_spell_languages_cache is None:
        _available_spell_languages_cache = _query_available_spell_languages()
    return list(_available_spell_languages_cache)


def clear_spell_language_cache():
    """Drop the cached Enchant listing (e.g. after installing dictionaries)."""
    global _available_spell_languages_cache
    _available_spell_languages_cache = None


def _query_available_spell_languages():
    if not USE_ENCHANT or _enchant is None:
        return ["en_US"]
    languages = []
    for tag in _enchant.list_languages():
        normalized = str(tag).replace("-", "_")
        if _LOCALE_TAG.match(normalized) and normalized not in languages:
            languages.append(normalized)
    return sorted(languages) if languages else ["en_US"]


# Common document languages offered even when their dictionary is not installed yet.
COMMON_DOCUMENT_LANGUAGES = [
    "en_US", "en_GB", "fa_IR", "ar_SA", "de_DE", "fr_FR", "es_ES", "it_IT",
    "pt_BR", "pt_PT", "ru_RU", "tr_TR", "zh_CN", "ja_JP", "ko_KR", "he_IL",
    "hi_IN", "nl_NL", "pl_PL", "uk_UA", "sv_SE", "cs_CZ", "ro_RO", "id_ID",
]


def normalize_language_tag(language):
    tag = str(language or "en_US").replace("-", "_").strip()
    collapsed = tag.lower().replace(" ", "_")
    if collapsed in _AUTO_LANGUAGE_ALIASES or collapsed.startswith("auto_"):
        return DOCUMENT_LANGUAGE_AUTO
    return tag.replace("-", "_") if "-" in tag else tag


def detect_language_code(text):
    """Detect ISO language code from text, or None if unreliable."""
    sample = " ".join((text or "").split())
    if not USE_LANGDETECT or detect_langs is None:
        return None, None
    letter_count = sum(1 for ch in sample if ch.isalpha())
    if letter_count < MIN_LANGUAGE_DETECT_CHARS and len(sample) < MIN_LANGUAGE_DETECT_CHARS:
        return None, None
    try:
        ranked = detect_langs(sample[:8000])
    except LangDetectException:
        return None, None
    if not ranked:
        return None, None
    best = ranked[0]
    code = str(getattr(best, "lang", "") or "").lower()
    confidence = float(getattr(best, "prob", 0.0) or 0.0)
    if not code or confidence < LANGUAGE_DETECT_MIN_CONFIDENCE:
        return None, confidence
    return code, confidence


def preferred_locale_for_iso(code):
    """Map langdetect ISO codes to a preferred locale tag."""
    if not code:
        return None
    normalized = str(code).replace("_", "-").lower()
    if normalized in ISO_DEFAULT_LOCALES:
        return ISO_DEFAULT_LOCALES[normalized]
    base = normalized.split("-", 1)[0]
    if base in ISO_DEFAULT_LOCALES:
        return ISO_DEFAULT_LOCALES[base]
    return base


def match_dictionary_for_language(language, available=None):
    """Return an installed Enchant tag for language, or None if missing."""
    if available is None:
        available = list_available_spell_languages()
    available = list(available)
    tag = normalize_language_tag(language)
    if tag == DOCUMENT_LANGUAGE_AUTO:
        return None
    if tag in available:
        return tag

    code = tag.split("_", 1)[0]
    country = tag.split("_", 1)[1] if "_" in tag else None
    candidates = [item for item in available if item == code or item.startswith(f"{code}_")]
    if not candidates:
        return None
    if country:
        for item in candidates:
            if item.endswith(f"_{country}"):
                return item
    with_country = [item for item in candidates if "_" in item]
    return sorted(with_country or candidates)[0]


def dictionary_install_hint(language):
    """Short package hint for installing a dictionary for language."""
    code = normalize_language_tag(language).split("_", 1)[0].lower()
    if code == DOCUMENT_LANGUAGE_AUTO:
        return "a hunspell/myspell dictionary for the detected language"
    hints = {
        "fa": "myspell-fa (Debian/Ubuntu) or hunspell-fa (Fedora)",
        "en": "hunspell-en-us",
        "ar": "hunspell-ar",
        "de": "hunspell-de-de",
        "fr": "hunspell-fr",
        "es": "hunspell-es",
        "ru": "hunspell-ru",
        "tr": "hunspell-tr",
        "he": "hunspell-he",
        "pt": "hunspell-pt-br",
        "it": "hunspell-it",
        "nl": "hunspell-nl",
        "pl": "hunspell-pl",
        "uk": "hunspell-uk",
        "cs": "hunspell-cs",
        "sv": "hunspell-sv",
        "ro": "hunspell-ro",
        "hi": "hunspell-hi",
        "id": "hunspell-id",
        "ko": "hunspell-ko",
        "ja": "hunspell-ja",
        "zh": "hunspell-zh",
    }
    return hints.get(code, f"a hunspell/myspell dictionary for {code}")


def missing_dictionary_message(language):
    """User-facing warning when no dictionary is installed for language."""
    tag = normalize_language_tag(language)
    try:
        from jottr.translation_manager import _, format_language_label
        label = format_language_label(tag)
        return _(
            "No spell dictionary is installed for {language}. "
            "Install {package}, then restart Jottr."
        ).format(language=label, package=dictionary_install_hint(tag))
    except Exception:
        return (
            f"No spell dictionary is installed for {tag}. "
            f"Install {dictionary_install_hint(tag)}, then restart Jottr."
        )


def list_document_language_choices(extra=None):
    """Languages shown in the document-language picker (Auto first)."""
    choices = set(COMMON_DOCUMENT_LANGUAGES)
    choices.update(list_available_spell_languages())
    try:
        from jottr.translation_manager import get_available_languages
        choices.update(get_available_languages())
    except Exception:
        pass
    for item in extra or ():
        if item:
            tag = normalize_language_tag(item)
            if tag != DOCUMENT_LANGUAGE_AUTO:
                choices.add(tag)
    ordered = sorted(tag for tag in choices if tag != DOCUMENT_LANGUAGE_AUTO)
    return [DOCUMENT_LANGUAGE_AUTO] + ordered


def get_document_language(settings_manager):
    """Configured document language (`auto` or a locale tag)."""
    configured = settings_manager.get_setting("document_language", None)
    if configured:
        return normalize_language_tag(configured)

    legacy = settings_manager.get_setting("spell_languages", None)
    if legacy:
        return normalize_language_tag(legacy[0])

    return normalize_language_tag(settings_manager.get_setting("language", "en_US"))


def resolve_document_language(settings_manager, text=""):
    """Resolve effective document language and installed dictionary tag.

    Returns
    -------
    (effective_language, dictionary_tag_or_None, detection_confidence_or_None)
    confidence is None for explicit languages; for Auto it may be a float when
    detection succeeds, or False while falling back to the UI language until
    there is enough text to detect.
    """
    available = list_available_spell_languages()
    configured = get_document_language(settings_manager)
    if configured != DOCUMENT_LANGUAGE_AUTO:
        matched = match_dictionary_for_language(configured, available)
        return configured, matched, None

    detected_code, confidence = detect_language_code(text)
    if not detected_code:
        # Until detection has enough text, provisionally use the UI language
        # (confidence stays False so the status bar can show it isn't detected yet).
        provisional = normalize_language_tag(
            settings_manager.get_setting("language", "en_US")
        )
        if provisional == DOCUMENT_LANGUAGE_AUTO:
            provisional = "en_US"
        matched = match_dictionary_for_language(provisional, available)
        return provisional, matched, False if confidence is None else confidence

    preferred = preferred_locale_for_iso(detected_code) or detected_code
    matched = match_dictionary_for_language(preferred, available)
    if matched is None:
        matched = match_dictionary_for_language(detected_code, available)
    return preferred, matched, confidence


def normalize_spell_languages(languages, available=None):
    """Deduplicate and keep only usable language tags."""
    if available is None:
        available = set(list_available_spell_languages())
    else:
        available = set(available)

    normalized = []
    for language in languages or []:
        tag = normalize_language_tag(language)
        if tag in available and tag not in normalized:
            normalized.append(tag)
    return normalized


def resolve_spell_languages(settings_manager, text=""):
    """Dictionary tags for the document language, if installed."""
    _, matched, _ = resolve_document_language(settings_manager, text=text)
    return [matched] if matched else []


def document_language_has_dictionary(settings_manager, text=""):
    """True when an Enchant dictionary exists for the effective document language."""
    return bool(resolve_spell_languages(settings_manager, text=text))


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
        self.resolved_document_language = None
        self.detection_confidence = None
        self.markdown_formats = {}
        # Edit clock: contentsChange fires on real text edits but NOT on
        # rehighlight (which only emits contentsChanged and bumps revision),
        # so it tells "text changed since last paint" apart from our own
        # repaints. Used to skip redundant rehighlights on settings applies.
        self._edit_clock = 0
        self._painted_edit_clock = -1
        document = self.document()
        if document is not None:
            document.contentsChange.connect(self._bump_edit_clock)
        self.set_theme(
            self.settings_manager.get_theme(),
            self.settings_manager.get_custom_themes(),
            rehighlight=False
        )
        self.apply_spell_settings(rehighlight=False)

    def _bump_edit_clock(self, *_args):
        self._edit_clock += 1

    def set_theme(self, theme_name=None, custom_themes=None, rehighlight=True):
        """Refresh Markdown syntax colors from the active editor theme."""
        resolved_name = theme_name or self.settings_manager.get_theme()
        if custom_themes is None:
            custom_themes = self.settings_manager.get_custom_themes()
        theme_key = (resolved_name, custom_themes)
        theme = ThemeManager.get_theme(resolved_name, custom_themes)
        self.markdown_formats = self.build_markdown_formats(theme)
        # Theme switches from settings/VIEW menu re-fire for every tab; only
        # the first pass needs a full rehighlight.
        if rehighlight and theme_key != getattr(self, "_theme_key", None):
            self._theme_key = theme_key
            self.rehighlight()
        elif getattr(self, "_theme_key", None) is None:
            self._theme_key = theme_key

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

    def document_text(self):
        document = self.document()
        return document.toPlainText() if document is not None else ""

    def _detect_sample(self, limit=8000):
        """Bounded text sample for auto language detection.

        Explicit document languages never need the text; auto mode only
        needs a prefix (detection itself caps at 8000 chars). Sampling by
        block avoids copying a large document on every settings pass.
        """
        if get_document_language(self.settings_manager) != DOCUMENT_LANGUAGE_AUTO:
            return ""
        document = self.document()
        if document is None:
            return ""
        parts = []
        total = 0
        block = document.firstBlock()
        while block.isValid() and total < limit:
            chunk = block.text()
            parts.append(chunk)
            total += len(chunk) + 1
            block = block.next()
        return "\n".join(parts)[:limit]

    def apply_spell_settings(self, rehighlight=True):
        """Reload enable flag and active dictionaries from settings/document text.

        Returns True when the backend changed (and a rehighlight happened if
        requested); no-op re-applies are skipped so settings toggles and
        typing-triggered refreshes stay cheap.
        """
        enabled = bool(self.settings_manager.get_setting("spell_check", True))
        user_words = self.user_dictionary_words()
        user_key = tuple(w.lower() for w in user_words)
        sample = self._detect_sample()
        # Auto-detect runs langdetect per call (~100ms on a large sample);
        # memoize on the sample so repeats with unchanged text skip it.
        detect_key = (sample if len(sample) < 200 else hash(sample))
        memo = getattr(self, "_detect_memo", None)
        if (
            memo is not None
            and memo[0] == enabled
            and memo[1] == user_key
            and memo[2] == detect_key
        ):
            effective, matched, confidence = memo[3]
        else:
            effective, matched, confidence = resolve_document_language(
                self.settings_manager,
                text=sample,
            )
            self._detect_memo = (enabled, user_key, detect_key, (effective, matched, confidence))
        languages = [matched] if matched else []
        key = (enabled, tuple(languages), user_key)
        # An explicit rehighlight request must still repaint when the text
        # changed even if the backend is identical (e.g. tests apply settings
        # after setPlainText). The edit clock ignores our own repaints.
        if key == getattr(self, "_spell_key", None):
            self.resolved_document_language = effective
            self.detection_confidence = confidence
            if rehighlight and self._edit_clock != self._painted_edit_clock:
                self._painted_edit_clock = self._edit_clock
                self.rehighlight()
                return True
            return False
        self.spell_check_enabled = enabled
        self.resolved_document_language = effective
        self.detection_confidence = confidence
        self.spell_languages = languages
        self._rebuild_spell_backends()
        self._spell_key = key
        self._painted_edit_clock = self._edit_clock
        if rehighlight:
            self.rehighlight()
        return True

    def refresh_detected_language(self, rehighlight=True):
        """Re-run auto language detection from the current document text."""
        if get_document_language(self.settings_manager) != DOCUMENT_LANGUAGE_AUTO:
            return False
        previous = (self.resolved_document_language, tuple(self.spell_languages))
        self.apply_spell_settings(rehighlight=False)
        changed = previous != (self.resolved_document_language, tuple(self.spell_languages))
        if changed and rehighlight:
            self.rehighlight()
        return changed

    def set_spell_languages(self, languages, rehighlight=True):
        """Replace active dictionaries and optionally rehighlight."""
        self.spell_languages = normalize_spell_languages(languages)
        self.resolved_document_language = self.spell_languages[0] if self.spell_languages else None
        self.detection_confidence = None
        self._rebuild_spell_backends()
        user_words = self.user_dictionary_words()
        self._spell_key = (
            bool(self.spell_check_enabled),
            tuple(self.spell_languages),
            tuple(w.lower() for w in user_words),
        )
        if rehighlight:
            self.rehighlight()

    def _rebuild_spell_backends(self):
        self.spells = []
        self.USE_ENCHANT = USE_ENCHANT
        if not self.spell_languages:
            # Document language has no installed dictionary; do not fall back
            # to an unrelated English pyspellchecker backend.
            self.USE_ENCHANT = False
            self._refresh_spell_caches()
            return

        if self.USE_ENCHANT:
            self.spells = _build_enchant_dicts(self.spell_languages)
            if self.spells:
                self._refresh_spell_caches()
                return
            print("No Enchant dictionaries loaded, falling back to pyspellchecker")
            self.USE_ENCHANT = False

        try:
            self.spells = [SpellChecker()]
        except Exception as exc:
            print(f"Spell checker initialization error: {exc}, using permissive fallback")
            self.spells = [FallbackSpellChecker()]
            self.USE_ENCHANT = False
        self._refresh_spell_caches()

    def _refresh_spell_caches(self, user_words=None):
        """Refresh per-word lookup caches (tags, script coverage, user words)."""
        if user_words is None:
            user_words = self.user_dictionary_words()
        self._user_words = frozenset(w.lower() for w in user_words)
        self._user_words_len = len(user_words)
        self._spell_tags = [self._dictionary_tag(spell) for spell in self.spells]
        self._spell_scripts = [_language_scripts_cached(tag) for tag in self._spell_tags]
        self._check_cache = {}

    def _sync_spell_caches(self):
        """Rebuild caches if backends were swapped directly or dict changed."""
        tags = [self._dictionary_tag(spell) for spell in self.spells]
        if tags != getattr(self, "_spell_tags", None):
            self._refresh_spell_caches()
            return
        words = self.user_dictionary_words()
        if len(words) != getattr(self, "_user_words_len", -1):
            self._refresh_spell_caches(words)

    def user_dictionary_words(self):
        return self.settings_manager.get_setting("user_dictionary", []) or []

    def word_in_user_dictionary(self, word):
        self._sync_spell_caches()
        return word.lower() in self._user_words

    def _dictionary_tag(self, spell):
        """Locale tag for an Enchant dict, or a Latin default for fallbacks."""
        tag = getattr(spell, "tag", None)
        if tag:
            return str(tag).replace("-", "_")
        return "en_US"

    def _spells_for_word(self, word):
        """Backends whose script matches the word (skip English junk for Farsi)."""
        self._sync_spell_caches()
        scripts = word_scripts(word)
        if not scripts:
            return list(self.spells)
        return [
            spell
            for spell, covered in zip(self.spells, self._spell_scripts)
            if scripts & covered
        ]

    def check_word(self, word):
        """Return True if the word is accepted by the user dict or any active dictionary."""
        if not self.spell_check_enabled:
            return True
        if self.word_in_user_dictionary(word):
            return True
        if not self.spells:
            return True
        # Don't flag other-script words against the document dictionary.
        if not dictionaries_cover_word(word, self.spell_languages):
            return True

        spells = self._spells_for_word(word)
        if not spells:
            return True
        if self.USE_ENCHANT:
            # Enchant checks are FFI calls (~20us each); words repeat heavily
            # within a document, so memoize per backend set. Cleared whenever
            # backends or the user dictionary change.
            cache = self._check_cache
            key = (word, tuple(self._spell_tags))
            hit = cache.get(key, None)
            if hit is None:
                hit = any(spell.check(word) for spell in spells)
                # Bound memory on pathological inputs (each key is one word).
                if len(cache) < 20000:
                    cache[key] = hit
            return hit

        # pyspellchecker considers unknown words misspelled
        lowered = word.lower()
        return any(lowered in spell for spell in spells)

    def suggest(self, word):
        """Get suggestions for a word from the user dictionary and matching dictionaries."""
        if not self.spell_check_enabled:
            return []
        if not self.spells or not dictionaries_cover_word(word, self.spell_languages):
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
                # Keep case-only corrections (iran → Iran); only drop an
                # exact echo of the typed word that Enchant often returns.
                suggestions.extend(
                    suggestion for suggestion in spell_suggestions
                    if suggestion != word
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
            self._refresh_spell_caches(user_dict)
            # Backend-affecting state changed; force the next apply to rebuild.
            self._spell_key = None

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
