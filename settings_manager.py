import json
import os
from PyQt5.QtGui import QFont

class SettingsManager:
    def __init__(self):
        self.settings_file = os.path.join(os.path.expanduser("~"), ".editor_settings.json")
        self.settings = self.load_settings()

    def load_settings(self):
        default_settings = {
            "theme": "Light",
            "font_family": "Consolas" if os.name == 'nt' else "DejaVu Sans Mono",
            "font_size": 10,
            "font_weight": 50,
            "font_italic": False,
            "show_snippets": True,
            "show_browser": True,
            "last_files": []
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    return {**default_settings, **json.load(f)}
        except:
            pass
        return default_settings

    def save_settings(self):
        with open(self.settings_file, 'w') as f:
            json.dump(self.settings, f)

    def get_font(self):
        font = QFont(
            self.settings["font_family"],
            self.settings["font_size"],
            self.settings["font_weight"]
        )
        font.setItalic(self.settings["font_italic"])
        return font

    def save_font(self, font):
        self.settings.update({
            "font_family": font.family(),
            "font_size": font.pointSize(),
            "font_weight": font.weight(),
            "font_italic": font.italic()
        })
        self.save_settings()

    def get_theme(self):
        return self.settings["theme"]

    def save_theme(self, theme):
        self.settings["theme"] = theme
        self.save_settings()

    def get_pane_visibility(self):
        return (self.settings["show_snippets"], self.settings["show_browser"])

    def save_pane_visibility(self, show_snippets, show_browser):
        self.settings.update({
            "show_snippets": show_snippets,
            "show_browser": show_browser
        })
        self.save_settings()

    def save_last_files(self, files):
        """Save list of last opened files"""
        self.settings["last_files"] = files
        self.save_settings()

    def get_last_files(self):
        """Get list of last opened files"""
        return self.settings.get("last_files", []) 