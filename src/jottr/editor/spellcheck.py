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
_WORD_PATTERN = re.compile(r"\w+(?:['’]\w+)*")


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
    USE_ENCHANT = True
except (ImportError, ModuleNotFoundError) as e:
    print("Enchant not available, falling back to pyspellchecker:", str(e))
    Dict = None
    DictNotFoundError = Exception
    USE_ENCHANT = False

if SpellChecker is None:
    SpellChecker = FallbackSpellChecker

class SpellCheckHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, settings_manager):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.spell_check_enabled = True
        self.USE_ENCHANT = USE_ENCHANT  # Store the global flag
        self.markdown_formats = {}
        self.set_theme(
            self.settings_manager.get_theme(),
            self.settings_manager.get_custom_themes(),
            rehighlight=False
        )
        
        try:
            if self.USE_ENCHANT:
                self.spell = Dict("en_US")
                print("Using Enchant for spell checking")
            else:
                self.spell = SpellChecker()
                print("Using pyspellchecker for spell checking")
        except Exception as e:
            print(f"Spell checker initialization error: {str(e)}, falling back to pyspellchecker")
            self.spell = SpellChecker()
            self.USE_ENCHANT = False

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

    def check_word(self, word):
        """Check if a word is spelled correctly"""
        if not self.spell_check_enabled:
            return True
            
        if self.USE_ENCHANT:
            return self.spell.check(word)
        else:
            # pyspellchecker considers unknown words misspelled
            return word.lower() in self.spell

    def suggest(self, word):
        """Get suggestions for a word"""
        if not self.spell_check_enabled:
            return []
            
        # Get user dictionary
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        
        # Add matching words from user dictionary first
        suggestions = [dict_word for dict_word in user_dict 
                      if dict_word.lower().startswith(word.lower())]
        
        # Only get spell checker suggestions for Latin words
        if self.is_latin_word(word):
            try:
                if self.USE_ENCHANT:
                    spell_suggestions = self.spell.suggest(word)
                else:
                    spell_suggestions = self.spell.candidates(word)
                
                if spell_suggestions:
                    # Remove the word itself from suggestions
                    spell_suggestions = [s for s in spell_suggestions 
                                      if s.lower() != word.lower()]
                    suggestions.extend(spell_suggestions)
            except UnicodeEncodeError:
                pass
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(suggestions))

    def add_to_dictionary(self, word):
        """Add word to user dictionary"""
        if self.USE_ENCHANT:
            # Enchant spell checker implementation
            self.spell.add(word)
        else:
            # PySpellChecker implementation
            self.spell.word_frequency.add(word)
            # Force a recheck of the document
            self.highlighter.rehighlight()
        
        # Add to user dictionary in settings
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        if word not in user_dict:
            user_dict.append(word)
            self.settings_manager.save_setting('user_dictionary', user_dict)

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

        # Get user dictionary
        user_dict = self.settings_manager.get_setting('user_dictionary', [])
        
        format = QTextCharFormat()
        format.setUnderlineColor(Qt.GlobalColor.red)
        format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)

        # Include apostrophes so contractions like "shouldn't" / "don’t" stay whole
        for match in _WORD_PATTERN.finditer(text):
            index = match.start()
            word = match.group(0)
            length = len(word)
            
            # Only spell check Latin words
            if self.is_latin_word(word) and not self.is_in_ranges(index, skip_ranges):
                # Check if word is in user dictionary first
                if word not in user_dict:
                    try:
                        if not self.check_word(word):
                            self.setFormat(index, length, format)
                    except UnicodeEncodeError:
                        pass  # Skip words that can't be encoded

    def is_latin_word(self, word):
        """Check if word contains only Latin characters (plus apostrophes)"""
        try:
            word.replace("'", "").replace("’", "").encode('latin-1')
            return True
        except UnicodeEncodeError:
            return False

