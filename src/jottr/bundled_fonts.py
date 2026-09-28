"""Fonts shipped with Jottr (JetBrains Mono, SIL Open Font License 1.1)."""
import os

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QFontDatabase

BUNDLED_FONT_FAMILY = "JetBrains Mono"
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "JetBrainsMono")
# Variable-weight files: one upright, one italic. (file name, CSS font-style)
_FONT_FILES = (("JetBrainsMono.ttf", "normal"), ("JetBrainsMono-Italic.ttf", "italic"))


def bundled_font_paths():
    return [os.path.join(_FONT_DIR, name) for name, _style in _FONT_FILES]


_registered = False


def register_bundled_fonts():
    """Add the bundled faces to the application font database. Needs a QGuiApplication."""
    global _registered
    for path in bundled_font_paths():
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id < 0:
            print(f"Could not load bundled font: {path}")
        elif BUNDLED_FONT_FAMILY in QFontDatabase.applicationFontFamilies(font_id):
            _registered = True


def bundled_font_available():
    # Not QFontDatabase.families(): with a system copy installed too, Qt lists
    # both under foundry-qualified names like "JetBrains Mono [JB]".
    return _registered


def bundled_font_face_css():
    """@font-face rules so web views (which ignore Qt's app fonts) can use the face."""
    rules = []
    for name, style in _FONT_FILES:
        url = QUrl.fromLocalFile(os.path.join(_FONT_DIR, name)).toString(QUrl.ComponentFormattingOption.FullyEncoded)
        rules.append(
            f'@font-face {{ font-family: "{BUNDLED_FONT_FAMILY}"; src: url("{url}") format("truetype"); '
            f"font-weight: 100 800; font-style: {style}; }}"
        )
    return "\n".join(rules)
