from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QStyleFactory

class ThemeManager:
    @staticmethod
    def get_themes():
        return {
            "Light": {
                "bg": "#ffffff",
                "text": "#000000",
                "selection": "#b3d4fc"
            },
            "Dark": {
                "bg": "#1e1e1e",
                "text": "#d4d4d4",
                "selection": "#264f78"
            },
            "Sepia": {
                "bg": "#f4ecd8",
                "text": "#5b4636",
                "selection": "#c4b5a0"
            }
        }

    @staticmethod
    def apply_theme(editor, theme_name):
        themes = ThemeManager.get_themes()
        if theme_name in themes:
            theme = themes[theme_name]
            editor.setStyleSheet(f"""
                QTextEdit {{
                    background-color: {theme['bg']};
                    color: {theme['text']};
                    selection-background-color: {theme['selection']};
                    font-family: {editor.font().family()};
                    font-size: {editor.font().pointSize()}pt;
                }}
            """) 