"""Fonts shipped with Jottr (JetBrains Mono and IBM Plex Sans, SIL Open Font License 1.1)."""
import os

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QFontDatabase

BUNDLED_EDITOR_FONT_FAMILY = "JetBrains Mono"
BUNDLED_UI_FONT_FAMILY = "IBM Plex Sans"
_FONTS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
# Variable-weight files: one upright, one italic per family.
# family → (folder, CSS weight range, ((file name, CSS font-style), ...))
_BUNDLED_FACES = {
    BUNDLED_EDITOR_FONT_FAMILY: (
        "JetBrainsMono",
        "100 800",
        (("JetBrainsMono.ttf", "normal"), ("JetBrainsMono-Italic.ttf", "italic")),
    ),
    BUNDLED_UI_FONT_FAMILY: (
        "IBMPlexSans",
        "100 700",
        (("IBMPlexSans.ttf", "normal"), ("IBMPlexSans-Italic.ttf", "italic")),
    ),
}


def _face_files():
    """(family, path, CSS weight range, CSS font-style) for every bundled file."""
    for family, (folder, weights, files) in _BUNDLED_FACES.items():
        for name, style in files:
            yield family, os.path.join(_FONTS_ROOT, folder, name), weights, style


def bundled_font_paths():
    return [path for _family, path, _weights, _style in _face_files()]


_registered = set()


def register_bundled_fonts():
    """Add the bundled faces to the application font database. Needs a QGuiApplication."""
    for family, path, _weights, _style in _face_files():
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id < 0:
            print(f"Could not load bundled font: {path}")
        elif family in QFontDatabase.applicationFontFamilies(font_id):
            _registered.add(family)


def bundled_font_available(family):
    # Not QFontDatabase.families(): with a system copy installed too, Qt lists
    # both under foundry-qualified names like "JetBrains Mono [JB]".
    return family in _registered


def bundled_font_face_css():
    """@font-face rules so web views (which ignore Qt's app fonts) can use the faces."""
    rules = []
    for family, path, weights, style in _face_files():
        url = QUrl.fromLocalFile(path).toString(QUrl.ComponentFormattingOption.FullyEncoded)
        rules.append(
            f'@font-face {{ font-family: "{family}"; src: url("{url}") format("truetype"); '
            f"font-weight: {weights}; font-style: {style}; }}"
        )
    return "\n".join(rules)
