from copy import deepcopy

from PyQt6.QtGui import QColor, QPalette


class ThemeManager:
    """Theme schema and stylesheet generation for Jottr."""

    DEFAULT_THEME_NAME = "Light"

    BASE_APP = {
        "background": "#F7F7F5",
        "surface": "#FFFFFF",
        "surface_alt": "#F0F0EE",
        "surface_hover": "#E8E8E6",
        "surface_active": "#E7F0FF",
        "text": "#202124",
        "muted": "#6B6F76",
        "border": "#DADCE0",
        "border_active": "#8AB4F8",
        "accent": "#2F6FED",
        "accent_text": "#0B57D0",
        "danger": "#B42318"
    }

    BASE_EDITOR = {
        "background": "#FFFFFF",
        "foreground": "#202124",
        "selection": "#D7E7FF",
        "current_line": "#F6F8FA",
        "border": "#E5E7EB"
    }

    DEFAULT_THEMES = {
        "Light": {
            "app": BASE_APP,
            "editor": BASE_EDITOR,
            "syntax": {
                "comment": "#64748b",
                "keyword": "#2563eb",
                "string": "#15803d",
                "number": "#b45309",
                "function": "#0f766e",
                "type": "#7c3aed",
                "error": "#dc2626"
            }
        },
        "Dark": {
            "app": {
                "background": "#1E1E1E",
                "surface": "#252526",
                "surface_alt": "#181818",
                "surface_hover": "#2A2D2E",
                "surface_active": "#263B5E",
                "text": "#E6E6E6",
                "muted": "#A0A0A0",
                "border": "#3C3C3C",
                "border_active": "#4C8DFF",
                "accent": "#4C8DFF",
                "accent_text": "#DDEBFF",
                "danger": "#F87171"
            },
            "editor": {
                "background": "#1E1E1E",
                "foreground": "#E6E6E6",
                "selection": "#264F78",
                "current_line": "#252526",
                "border": "#3C3C3C"
            },
            "syntax": {
                "comment": "#94a3b8",
                "keyword": "#93c5fd",
                "string": "#86efac",
                "number": "#fdba74",
                "function": "#67e8f9",
                "type": "#c4b5fd",
                "error": "#f87171"
            }
        },
        "Sepia": {
            "app": {
                "background": "#F1E7D2",
                "surface": "#FBF6EA",
                "surface_alt": "#E9DCC4",
                "surface_hover": "#E2D2B4",
                "surface_active": "#E5D0B2",
                "text": "#3A2D20",
                "muted": "#8B7358",
                "border": "#DDC9AA",
                "border_active": "#D9B98E",
                "accent": "#8F5E35",
                "accent_text": "#3A2D20",
                "danger": "#B42318"
            },
            "editor": {
                "background": "#FBF6EA",
                "foreground": "#3A2D20",
                "selection": "#D9B98E",
                "current_line": "#F5ECD9",
                "border": "#DDC9AA"
            },
            "syntax": {
                "comment": "#8a7560",
                "keyword": "#8b4513",
                "string": "#6b7f24",
                "number": "#9a5f2a",
                "function": "#37635f",
                "type": "#7654a3",
                "error": "#b42318"
            }
        },
        "Dracula": {
            "app": {
                "background": "#282a36",
                "surface": "#343746",
                "surface_alt": "#424450",
                "surface_hover": "#44475a",
                "surface_active": "#6272a4",
                "text": "#f8f8f2",
                "muted": "#c6c8d1",
                "border": "#6272a4",
                "border_active": "#815cd6",
                "accent": "#bd93f9",
                "accent_text": "#f8f8f2",
                "danger": "#ff5555"
            },
            "editor": {
                "background": "#282a36",
                "foreground": "#f8f8f2",
                "selection": "#44475a",
                "current_line": "#353747",
                "border": "#6272a4"
            },
            "syntax": {
                "comment": "#6272a4",
                "keyword": "#ff79c6",
                "string": "#f1fa8c",
                "number": "#ffb86c",
                "function": "#50fa7b",
                "type": "#8be9fd",
                "constant": "#bd93f9",
                "error": "#ff5555"
            }
        },
        "Monokai": {
            "app": {
                "background": "#272822",
                "surface": "#303126",
                "surface_alt": "#3e3d32",
                "surface_hover": "#49483e",
                "surface_active": "#75715e",
                "text": "#f8f8f2",
                "muted": "#cfcfc2",
                "border": "#49483e",
                "border_active": "#a6e22e",
                "accent": "#a6e22e",
                "accent_text": "#272822",
                "danger": "#f92672"
            },
            "editor": {
                "background": "#272822",
                "foreground": "#f8f8f2",
                "selection": "#49483e",
                "current_line": "#3e3d32",
                "border": "#49483e"
            },
            "syntax": {
                "comment": "#75715e",
                "keyword": "#f92672",
                "string": "#e6db74",
                "number": "#ae81ff",
                "function": "#a6e22e",
                "type": "#66d9ef",
                "constant": "#fd971f",
                "error": "#f92672"
            }
        },
        "Monaspace": {
            "app": {
                "background": "#10151f",
                "surface": "#18202f",
                "surface_alt": "#202a3c",
                "surface_hover": "#26334a",
                "surface_active": "#33415d",
                "text": "#f0f3f8",
                "muted": "#aeb9c9",
                "border": "#33415d",
                "border_active": "#7dd3fc",
                "accent": "#7dd3fc",
                "accent_text": "#08111f",
                "danger": "#fb7185"
            },
            "editor": {
                "background": "#10151f",
                "foreground": "#f0f3f8",
                "selection": "#33415d",
                "current_line": "#18202f",
                "border": "#33415d"
            },
            "syntax": {
                "comment": "#7f8da3",
                "keyword": "#f472b6",
                "string": "#a3e635",
                "number": "#fbbf24",
                "function": "#7dd3fc",
                "type": "#c084fc",
                "constant": "#fb923c",
                "error": "#fb7185"
            }
        },
        "Tokyo Night": {
            "app": {
                "background": "#1a1b26",
                "surface": "#24283b",
                "surface_alt": "#292e42",
                "surface_hover": "#343a52",
                "surface_active": "#3b4261",
                "text": "#c0caf5",
                "muted": "#9aa5ce",
                "border": "#3b4261",
                "border_active": "#7aa2f7",
                "accent": "#7aa2f7",
                "accent_text": "#16161e",
                "danger": "#f7768e"
            },
            "editor": {
                "background": "#1a1b26",
                "foreground": "#c0caf5",
                "selection": "#3b4261",
                "current_line": "#24283b",
                "border": "#3b4261"
            },
            "syntax": {
                "comment": "#565f89",
                "keyword": "#bb9af7",
                "string": "#9ece6a",
                "number": "#ff9e64",
                "function": "#7aa2f7",
                "type": "#2ac3de",
                "constant": "#e0af68",
                "error": "#f7768e"
            }
        },
        "Matcha": {
            "app": {
                "background": "#f3f7ed",
                "surface": "#ffffff",
                "surface_alt": "#e8f0de",
                "surface_hover": "#d9e8c8",
                "surface_active": "#bfd8a3",
                "text": "#24331f",
                "muted": "#64735d",
                "border": "#c9d9bd",
                "border_active": "#6f9f52",
                "accent": "#6f9f52",
                "accent_text": "#10200b",
                "danger": "#b42318"
            },
            "editor": {
                "background": "#fbfdf7",
                "foreground": "#24331f",
                "selection": "#cfe5bc",
                "current_line": "#eef5e6",
                "border": "#c9d9bd"
            },
            "syntax": {
                "comment": "#71816b",
                "keyword": "#497b32",
                "string": "#7a8f22",
                "number": "#9c6b1f",
                "function": "#31766b",
                "type": "#6f5ca8",
                "constant": "#b36b24",
                "error": "#b42318"
            }
        }
    }

    @staticmethod
    def get_theme_standard():
        return {
            "name": "My Theme",
            "app": deepcopy(ThemeManager.BASE_APP),
            "editor": deepcopy(ThemeManager.BASE_EDITOR),
            "syntax": {
                "comment": "#6272a4",
                "keyword": "#ff79c6",
                "string": "#f1fa8c",
                "number": "#ffb86c",
                "function": "#50fa7b",
                "type": "#8be9fd",
                "constant": "#bd93f9",
                "error": "#ff5555"
            }
        }

    @staticmethod
    def is_valid_color(value):
        return isinstance(value, str) and value.startswith("#") and QColor(value).isValid()

    @staticmethod
    def normalize_color(value, fallback):
        clean_value = str(value or "").strip()
        if ThemeManager.is_valid_color(clean_value):
            return QColor(clean_value).name()
        return fallback

    @staticmethod
    def normalize_section(section, defaults):
        source = section if isinstance(section, dict) else {}
        normalized = {}
        for key, fallback in defaults.items():
            normalized[key] = ThemeManager.normalize_color(source.get(key), fallback)
        return normalized

    @staticmethod
    def normalize_theme(theme):
        if not isinstance(theme, dict):
            return None

        if all(key in theme for key in ("bg", "text", "selection")):
            if not all(ThemeManager.is_valid_color(theme.get(key)) for key in ("bg", "text", "selection")):
                return None
            theme = {
                "app": {
                    **ThemeManager.BASE_APP,
                    "background": theme.get("bg"),
                    "surface": theme.get("bg"),
                    "surface_alt": theme.get("bg"),
                    "surface_active": theme.get("selection"),
                    "text": theme.get("text"),
                    "accent": theme.get("selection"),
                    "accent_text": theme.get("text")
                },
                "editor": {
                    **ThemeManager.BASE_EDITOR,
                    "background": theme.get("bg"),
                    "foreground": theme.get("text"),
                    "selection": theme.get("selection")
                },
                "syntax": theme.get("syntax", {})
            }

        editor = ThemeManager.normalize_section(theme.get("editor"), ThemeManager.BASE_EDITOR)
        app = ThemeManager.normalize_section(theme.get("app"), ThemeManager.BASE_APP)
        syntax = ThemeManager.normalize_section(theme.get("syntax"), ThemeManager.get_theme_standard()["syntax"])
        normalized = {
            "name": str(theme.get("name", "")).strip(),
            "app": app,
            "editor": editor,
            "syntax": syntax,
            "bg": editor["background"],
            "text": editor["foreground"],
            "selection": editor["selection"]
        }
        return normalized

    @staticmethod
    def normalize_custom_themes(custom_themes):
        if not isinstance(custom_themes, dict):
            return {}

        normalized = {}
        for name, theme in custom_themes.items():
            clean_name = str(name).strip()
            clean_theme = ThemeManager.normalize_theme(theme)
            if clean_theme and clean_theme.get("name"):
                clean_name = clean_theme["name"]
            if clean_name and clean_theme and clean_name not in ThemeManager.DEFAULT_THEMES:
                clean_theme["name"] = clean_name
                normalized[clean_name] = clean_theme
        return normalized

    @staticmethod
    def get_themes(custom_themes=None):
        themes = {
            name: ThemeManager.normalize_theme(theme)
            for name, theme in ThemeManager.DEFAULT_THEMES.items()
        }
        themes.update(ThemeManager.normalize_custom_themes(custom_themes))
        return themes

    @staticmethod
    def get_theme(theme_name, custom_themes=None):
        themes = ThemeManager.get_themes(custom_themes)
        return themes.get(theme_name) or themes[ThemeManager.DEFAULT_THEME_NAME]

    @staticmethod
    def build_editor_stylesheet(editor, theme, font=None):
        editor_theme = theme["editor"]
        editor_font = font or editor.font()
        font_family = editor_font.family().replace("\\", "\\\\").replace('"', '\\"')
        point_size = editor_font.pointSizeF() if editor_font.pointSizeF() > 0 else editor_font.pointSize()
        if point_size <= 0:
            point_size = 10
        return f"""
            /* legacy-dark: #111827 #e5e7eb */
            QTextEdit#writingEditor {{
                background-color: {editor_theme['background']};
                color: {editor_theme['foreground']};
                selection-background-color: {editor_theme['selection']};
                border: 1px solid {editor_theme['border']};
                border-radius: 0px;
                padding: 18px 24px;
                font-family: "{font_family}";
                font-size: {point_size:g}pt;
                font-weight: normal;
                font-style: {('italic' if editor_font.italic() else 'normal')};
            }}
        """

    @staticmethod
    def build_font_stylesheet(font):
        if font is None:
            return ""
        font_family = font.family().replace("\\", "\\\\").replace('"', '\\"')
        point_size = font.pointSizeF() if font.pointSizeF() > 0 else font.pointSize()
        if point_size <= 0:
            point_size = 10
        return f"""
                font-family: "{font_family}";
                font-size: {point_size:g}pt;
        """

    @staticmethod
    def build_app_stylesheet(theme, font=None):
        app = theme["app"]
        font_style = ThemeManager.build_font_stylesheet(font)
        branch_color = app["text"].replace("#", "%23")

        branch_open_icon = (
            "data:image/svg+xml;utf8,"
            f"<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'>"
            f"<path d='M4 6l4 4 4-4' fill='none' stroke='{branch_color}' stroke-width='1.6' "
            "stroke-linecap='square' stroke-linejoin='miter'/></svg>"
        )
        branch_closed_icon = (
            "data:image/svg+xml;utf8,"
            f"<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 16 16'>"
            f"<path d='M6 4l4 4-4 4' fill='none' stroke='{branch_color}' stroke-width='1.6' "
            "stroke-linecap='square' stroke-linejoin='miter'/></svg>"
        )
        return f"""
            QMainWindow, QWidget#mainSurface {{
                background: {app['background']};
                color: {app['text']};
                {font_style}
            }}
            QMainWindow#appWindow {{
                border: 1px solid {app['accent']};
                border-radius: 0px;
            }}
            QMainWindow#appWindow[chromeMaximized="true"] {{
                border: 1px solid {app['accent']};
            }}
            QWidget#mainSurface {{
                border: 1px solid {app['accent']};
                border-radius: 0px;
            }}
            QWidget#mainSurface[chromeMaximized="true"] {{
                border: 1px solid {app['accent']};
            }}
            QToolBar#mainToolBar {{
                background: {app['surface_alt']};
                border: none;
                border-left: 1px solid {app['accent']};
                border-right: 1px solid {app['accent']};
                border-bottom: 1px solid {app['border']};
                padding: 0px;
                spacing: 0px;
                min-height: 40px;
                max-height: 40px;
            }}
            QMainWindow#appWindow[chromeMaximized="true"] QToolBar#mainToolBar {{
                border-left: 1px solid {app['accent']};
                border-right: 1px solid {app['accent']};
                border-bottom: 1px solid {app['border']};
            }}
            QLabel#appWordmark {{
                background: transparent;
                color: {app['text']};
                border-left: 3px solid {app['accent']};
                font-size: 14px;
                font-weight: 800;
                padding: 4px 10px 4px 9px;
            }}
            QLabel#workspaceBreadcrumb {{
                background: transparent;
                color: {app['muted']};
                border: none;
                border-left: 1px solid {app['border']};
                padding: 4px 10px;
            }}
            QLabel#documentBreadcrumb {{
                background: transparent;
                color: {app['text']};
                border: none;
                border-left: 1px solid {app['border']};
                font-weight: 600;
                padding: 4px 10px;
            }}
            QLineEdit#titleBarCommandCenter {{
                background: {app['surface_alt']};
                color: {app['text']};
                border: 1px solid {app['border_active']};
                border-radius: 3px;
                padding: 2px 18px;
                min-width: 0px;
                max-width: 16777215px;
                min-height: 18px;
                max-height: 18px;
                selection-background-color: {app['surface_active']};
                selection-color: {app['text']};
            }}
            QLineEdit#titleBarCommandCenter:focus {{
                background: {app['surface']};
                border-color: {app['accent']};
            }}
            QToolBar#mainToolBar QToolButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 0px;
                color: {app['text']};
                margin: 0px 0px;
                padding: 0px 7px;
                min-width: 26px;
                min-height: 34px;
                max-height: 34px;
            }}
            QToolBar#mainToolBar QToolButton:hover {{
                background: {app['surface_hover']};
                border-color: {app['border']};
            }}
            QToolBar#mainToolBar QToolButton:focus {{
                background: {app['surface_hover']};
                border-color: {app['accent']};
            }}
            QToolBar#mainToolBar QToolButton:pressed,
            QToolBar#mainToolBar QToolButton:checked {{
                background: {app['surface_active']};
                border-color: {app['border_active']};
                color: {app['text']};
            }}
            QToolBar#mainToolBar QToolButton:disabled {{
                color: {app['muted']};
                background: transparent;
                border-color: transparent;
            }}
            QToolBar#mainToolBar::separator {{
                background: {app['border']};
                width: 1px;
                margin: 6px 8px;
            }}
            QWidget#customTitleBar {{
                background: {app['surface']};
                border-left: 1px solid {app['accent']};
                border-right: 1px solid {app['accent']};
                border-top: 1px solid {app['accent']};
                border-bottom: 1px solid {app['border']};
            }}
            QMainWindow#appWindow[chromeMaximized="true"] QWidget#customTitleBar {{
                border-left: 1px solid {app['accent']};
                border-right: 1px solid {app['accent']};
                border-top: 1px solid {app['accent']};
                border-bottom: 1px solid {app['border']};
            }}
            QLabel#titleBarAppIcon {{
                background: transparent;
            }}
            QLabel#titleBarAppName {{
                color: {app['text']};
                font-weight: 700;
                padding: 0px 10px 0px 5px;
            }}
            QWidget#titleBarMenuSlot {{
                background: transparent;
            }}
            QWidget#titleBarDragArea {{
                background: transparent;
            }}
            QWidget#titleBarWindowControls {{
                background: transparent;
            }}
            QToolButton#titleBarWindowButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 0px;
                color: {app['text']};
                font-size: 16px;
                font-weight: 700;
                margin: 0px;
                padding: 0px;
                min-width: 40px;
                max-width: 40px;
                min-height: 30px;
                max-height: 30px;
            }}
            QToolButton#titleBarWindowButton:hover {{
                background: {app['surface_hover']};
                border-color: transparent;
            }}
            QToolButton#titleBarWindowButton:pressed {{
                background: {app['surface_active']};
                border-color: transparent;
            }}
            QToolButton#titleBarWindowButton[role="close"]:hover {{
                background: #C42B1C;
                border-color: #C42B1C;
                color: #FFFFFF;
            }}
            QPushButton#titleBarMenuButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 0px;
                color: {app['text']};
                margin: 0px;
                padding: 0px 6px;
                min-width: 0px;
                min-height: 30px;
                max-height: 30px;
                font-size: 12px;
                text-align: center;
                {font_style}
            }}
            QPushButton#titleBarMenuButton:hover {{
                background: {app['surface_hover']};
                border-color: {app['border']};
            }}
            QPushButton#titleBarMenuButton:pressed,
            QPushButton#titleBarMenuButton:checked {{
                background: {app['surface_active']};
                border-color: {app['border_active']};
                color: {app['text']};
            }}
            QMenuBar#appMenuBar {{
                background: transparent;
                border: none;
                color: {app['text']};
                padding: 0px;
                spacing: 0px;
                {font_style}
            }}
            QMenuBar#appMenuBar::item {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 0px;
                color: {app['text']};
                margin: 0px 1px;
                padding: 5px 9px;
            }}
            QMenuBar#appMenuBar::item:selected {{
                background: {app['surface_hover']};
                border-color: {app['border_active']};
                color: {app['text']};
            }}
            QMenuBar#appMenuBar::item:pressed {{
                background: {app['surface_active']};
                border-color: {app['accent']};
                color: {app['accent_text']};
            }}
            QMenuBar#appMenuBar:focus {{
                border-bottom: 2px solid {app['accent']};
            }}
            QTabWidget#documentTabs {{
                border-right: 1px solid {app['accent']};
            }}
            QTabWidget#documentTabs::pane {{
                border: none;
                border-top: 1px solid {app['border']};
                margin: 0px;
                padding: 0px;
            }}
            QTabWidget#documentTabs::tab-bar {{
                alignment: left;
            }}
            QSplitter#mainSplitter::handle {{
                background: {app['border']};
                width: 1px;
            }}
            QWidget#activityRibbon {{
                background: {app['surface_alt']};
                border-left: 1px solid {app['accent']};
                border-right: 1px solid {app['border']};
            }}
            QWidget#activityRibbon[side="right"] {{
                border-right: 1px solid {app['accent']};
                border-left: 1px solid {app['border']};
            }}
            QMainWindow#appWindow[chromeMaximized="true"] QWidget#activityRibbon {{
                border-left: 1px solid {app['accent']};
            }}
            QMainWindow#appWindow[chromeMaximized="true"] QWidget#activityRibbon[side="right"] {{
                border-right: 1px solid {app['accent']};
            }}
            QToolButton#activityButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 0px;
                color: {app['muted']};
                padding: 6px;
            }}
            QToolButton#activityButton:hover {{
                background: {app['surface_hover']};
                border-color: {app['border']};
                color: {app['text']};
            }}
            QToolButton#activityButton:checked,
            QToolButton#activityButton:pressed {{
                background: {app['surface']};
                border-color: {app['border_active']};
                color: {app['accent']};
            }}
            QWidget#workspaceExplorer {{
                background: {app['surface_alt']};
                border-right: 1px solid {app['border']};
            }}
            QWidget#workspaceExplorer[side="right"] {{
                border-right: none;
                border-left: 1px solid {app['border']};
            }}
            QWidget#workspaceHeader {{
                background: {app['surface_alt']};
                border: none;
                border-bottom: 1px solid {app['border']};
                margin: 0px;
            }}
            QWidget#workspaceIdentity {{
                background: transparent;
            }}
            QPushButton#workspaceTitle {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 0px;
                color: {app['text']};
                font-weight: 700;
                padding: 2px 5px;
                text-align: center;
            }}
            QPushButton#workspaceTitle:hover {{
                background: {app['surface_hover']};
                border-color: {app['border_active']};
            }}
            QPushButton#workspaceTitle:pressed {{
                background: {app['surface_active']};
                color: {app['accent_text']};
            }}
            QLabel#workspacePath {{
                color: {app['muted']};
                font-size: 11px;
                padding-left: 3px;
            }}
            QPushButton#workspaceToolButton {{
                background: {app['surface']};
                border: 1px solid {app['border']};
                border-radius: 0px;
                color: {app['text']};
                font-size: 15px;
                font-weight: 700;
            }}
            QPushButton#workspaceToolButton:hover {{
                background: {app['surface_hover']};
                border-color: {app['border_active']};
                color: {app['accent_text']};
            }}
            QPushButton#workspaceToolButton:pressed {{
                background: {app['surface_active']};
            }}
            QTreeView#workspaceTree {{
                background: {app['surface_alt']};
                alternate-background-color: {app['surface_alt']};
                color: {app['text']};
                border: none;
                padding: 4px 0px;
                selection-background-color: {app['surface_active']};
                selection-color: {app['accent_text']};
                outline: 0px;
                show-decoration-selected: 1;
            }}
            QTreeView#workspaceTree::item {{
                min-height: 24px;
                border-radius: 0px;
                padding: 2px 5px;
                margin: 0px;
            }}
            QTreeView#workspaceTree::item:hover {{
                background: {app['surface_hover']};
                color: {app['text']};
            }}
            QTreeView#workspaceTree::item:selected {{
                background: {app['surface_active']};
                color: {app['accent_text']};
                border: 0px solid transparent;
                outline: none;
            }}
            QTreeView#workspaceTree::item:focus {{
                border: 0px solid transparent;
                outline: none;
            }}
            QTreeView#workspaceTree::branch {{
                background: {app['surface_alt']};
                border: none;
                image: none;
                width: 14px;
            }}
            QTreeView#workspaceTree::branch:has-siblings:!adjoins-item,
            QTreeView#workspaceTree::branch:has-siblings:adjoins-item,
            QTreeView#workspaceTree::branch:!has-children:!has-siblings:adjoins-item {{
                border: none;
                image: none;
            }}
            QTreeView#workspaceTree::branch:has-children:closed {{
                image: url("{branch_closed_icon}");
            }}
            QTreeView#workspaceTree::branch:has-children:open {{
                image: url("{branch_open_icon}");
            }}
            QTabWidget#documentTabs QTabBar::tab {{
                background: transparent;
                color: {app['muted']};
                border: none;
                border-bottom: 2px solid transparent;
                height: 38px;
                min-width: 118px;
                margin: 0px;
                padding: 0px 30px 0px 14px;
                text-align: center;
            }}
            QTabWidget#documentTabs QTabBar::tab:selected {{
                background: {app['surface']};
                color: {app['text']};
                border-bottom: 2px solid {app['accent']};
            }}
            QTabWidget#documentTabs QTabBar::tab:hover:!selected {{
                background: {app['surface_hover']};
                color: {app['text']};
            }}
            QTabWidget#documentTabs QTabBar::close-button {{
                subcontrol-position: center right;
                width: 14px;
                height: 14px;
                margin-right: 8px;
                margin-top: 0px;
                margin-bottom: 2px;
            }}
            QTabWidget#documentTabs QTabBar::close-button:hover {{
                background: {app['surface_hover']};
                border-radius: 0px;
            }}
            QStatusBar#statusBar {{
                background: {app['background']};
                border-left: 1px solid {app['accent']};
                border-right: 1px solid {app['accent']};
                border-bottom: 1px solid {app['accent']};
                border-top: 1px solid {app['border']};
                color: {app['muted']};
                padding: 0px;
                min-height: 22px;
                max-height: 22px;
            }}
            QMainWindow#appWindow[chromeMaximized="true"] QStatusBar#statusBar {{
                border-left: 1px solid {app['accent']};
                border-right: 1px solid {app['accent']};
                border-bottom: 1px solid {app['accent']};
                border-top: 1px solid {app['border']};
            }}
            QStatusBar#statusBar QLabel#bottomDocumentStatus {{
                color: {app['muted']};
                background: transparent;
                padding: 2px 10px;
                font-size: 11px;
            }}
            QMenu {{
                background: {app['surface']};
                border: 1px solid {app['border']};
                border-radius: 0px;
                padding: 4px;
                color: {app['text']};
                {font_style}
            }}
            QMenu::item {{
                color: {app['text']};
                padding: 6px 28px 6px 24px;
                border: 1px solid transparent;
                border-radius: 0px;
                {font_style}
            }}
            QMenu::item:selected {{
                background: {app['surface_hover']};
                border-color: {app['border_active']};
                color: {app['text']};
            }}
            QMenu::item:checked {{
                background: {app['surface_active']};
                color: {app['accent_text']};
                border-color: {app['accent']};
            }}
            QMenu::item:disabled {{
                color: {app['muted']};
            }}
            QMenu::separator {{
                background: {app['border']};
                height: 1px;
                margin: 6px 8px;
            }}
            QMenu::icon {{
                padding-left: 6px;
            }}
            QComboBox {{
                background: {app['surface']};
                color: {app['text']};
                border: 1px solid {app['border']};
                border-radius: 0px;
                padding: 5px 28px 5px 9px;
                selection-background-color: {app['surface_active']};
                selection-color: {app['text']};
                {font_style}
            }}
            QComboBox:hover {{
                background: {app['surface_hover']};
                border-color: {app['border_active']};
            }}
            QComboBox:focus {{
                border-color: {app['border_active']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView,
            QAbstractItemView {{
                background: {app['surface']};
                color: {app['text']};
                border: 1px solid {app['border']};
                selection-background-color: {app['surface_active']};
                selection-color: {app['text']};
                outline: 0px;
                {font_style}
            }}
            QToolTip {{
                background: {app['surface']};
                color: {app['text']};
                border: 1px solid {app['border']};
                padding: 5px 8px;
                {font_style}
            }}
            QScrollBar:vertical {{
                background: {app['surface_alt']};
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {app['muted']};
                min-height: 32px;
                border-radius: 0px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar:horizontal {{
                background: {app['surface_alt']};
                height: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {app['muted']};
                min-width: 32px;
                border-radius: 0px;
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0px;
            }}
        """

    @staticmethod
    def build_workspace_stylesheet(theme):
        app = theme["app"]
        editor = theme["editor"]
        return f"""
            QWidget#editorPane {{
                background: {app['background']};
            }}
            QWidget#writingCanvas {{
                background: transparent;
            }}
            QLabel#editorStatusStrip {{
                color: {app['muted']};
                background: {app['background']};
                border: none;
                border-top: 1px solid {app['border']};
                padding: 2px 10px;
                font-size: 11px;
            }}
            QTextEdit#writingEditor {{
                background: {editor['background']};
                color: {editor['foreground']};
                border: none;
                border-left: 1px solid {editor['border']};
                border-right: 1px solid {editor['border']};
                border-radius: 0px;
                padding: 18px 24px;
                selection-background-color: {editor['selection']};
            }}
            QSplitter#workspaceSplitter::handle,
            QSplitter#markdownSplitter::handle {{
                background: transparent;
                width: 2px;
                height: 2px;
            }}
            QWidget#sidePanel {{
                background: {app['surface_alt']};
                border-left: 1px solid {app['border']};
            }}
            QWidget#panelHeader {{
                background: {app['surface_alt']};
                border-bottom: 1px solid {app['border']};
            }}
            QLabel#panelTitle {{
                color: {app['text']};
                font-weight: 700;
            }}
            QPushButton#panelCloseButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 0px;
                color: {app['muted']};
            }}
            QPushButton#panelCloseButton:hover {{
                background: {app['surface_hover']};
                border-color: {app['border_active']};
                color: {app['accent_text']};
            }}
            QListWidget#snippetList {{
                background: {app['surface_alt']};
                border: none;
                padding: 6px;
                color: {app['text']};
            }}
            QListWidget#snippetList::item {{
                padding: 6px 8px;
                border-radius: 0px;
            }}
            QListWidget#snippetList::item:selected {{
                background: {app['surface_active']};
                color: {app['text']};
            }}
            QListWidget#snippetList::item:hover:!selected {{
                background: {app['surface_hover']};
            }}
            QWidget#findToolbar,
            QWidget#browserToolbar {{
                background: {app['surface_alt']};
                border-bottom: 1px solid {app['border']};
            }}
            QWidget#findToolbar QLineEdit,
            QWidget#browserToolbar QLineEdit {{
                background: {app['surface']};
                color: {app['text']};
                border: 1px solid {app['border']};
                border-radius: 0px;
                padding: 5px 8px;
                selection-background-color: {editor['selection']};
            }}
            QWidget#findToolbar QLineEdit:focus,
            QWidget#browserToolbar QLineEdit:focus {{
                border-color: {app['border_active']};
            }}
            QWidget#findToolbar QPushButton,
            QWidget#browserToolbar QPushButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 0px;
                padding: 5px 7px;
                color: {app['text']};
            }}
            QWidget#findToolbar QPushButton:hover,
            QWidget#browserToolbar QPushButton:hover {{
                background: {app['surface_hover']};
                border-color: {app['border_active']};
            }}
        """

    @staticmethod
    def build_dialog_stylesheet(theme, font=None):
        app = theme["app"]
        editor = theme["editor"]
        font_style = ThemeManager.build_font_stylesheet(font)
        return f"""
            /* legacy-dialog-radius: border-radius: 0px */
            QDialog {{
                background: {app['background']};
                color: {app['text']};
                {font_style}
            }}
            QTabWidget::pane {{
                background: {app['surface']};
                border: 1px solid {app['border']};
                border-radius: 0px;
                top: 0px;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {app['muted']};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 9px 17px;
                margin: 2px;
                border-radius: 0px;
            }}
            QTabBar::tab:selected {{
                background: {app['surface_active']};
                color: {app['text']};
                border-bottom: 2px solid {app['accent']};
            }}
            QScrollArea {{
                background: {app['background']};
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: {app['background']};
            }}
            QLineEdit,
            QPlainTextEdit,
            QFontComboBox,
            QComboBox,
            QSpinBox,
            QListWidget {{
                background: {app['surface_alt']};
                color: {app['text']};
                border: 1px solid {app['border']};
                border-radius: 0px;
                padding: 7px 9px;
                selection-background-color: {editor['selection']};
                selection-color: {app['text']};
                {font_style}
            }}
            QLineEdit:focus,
            QPlainTextEdit:focus,
            QFontComboBox:focus,
            QComboBox:focus,
            QSpinBox:focus,
            QListWidget:focus {{
                border-color: {app['border_active']};
            }}
            QFontComboBox,
            QComboBox {{
                padding-right: 28px;
            }}
            QFontComboBox:hover,
            QComboBox:hover {{
                background: {app['surface_hover']};
                border-color: {app['border_active']};
            }}
            QFontComboBox::drop-down,
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QFontComboBox QAbstractItemView,
            QComboBox QAbstractItemView,
            QAbstractItemView {{
                background: {app['surface']};
                color: {app['text']};
                border: 1px solid {app['border']};
                selection-background-color: {app['surface_active']};
                selection-color: {app['text']};
                outline: 0px;
                {font_style}
            }}
            QListWidget::item {{
                border-radius: 0px;
                padding: 7px 9px;
            }}
            QListWidget::item:selected {{
                background: {app['surface_active']};
                color: {app['text']};
            }}
            QLabel#fontPreview {{
                background: {editor['background']};
                color: {editor['foreground']};
                border: 1px solid {editor['border']};
                border-radius: 0px;
                padding: 10px;
            }}
            QPushButton {{
                background: {app['surface']};
                border: 1px solid {app['border']};
                border-radius: 0px;
                padding: 7px 11px;
                color: {app['text']};
                {font_style}
            }}
            QPushButton:hover {{
                background: {app['surface_hover']};
                border-color: {app['border_active']};
            }}
            QPushButton:pressed {{
                background: {app['surface_active']};
                border-color: {app['border_active']};
            }}
            QPushButton#fontSettingButton {{
                text-align: left;
            }}
            QCheckBox {{
                spacing: 8px;
                color: {app['text']};
                {font_style}
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {app['border_active']};
                background: {app['surface_alt']};
                border-radius: 0px;
            }}
            QCheckBox::indicator:checked {{
                background: {app['accent']};
                border-color: {app['accent']};
            }}
            QLabel {{
                color: {app['text']};
                {font_style}
            }}
        """

    @staticmethod
    def build_font_dialog_stylesheet(theme, font=None):
        app = theme["app"]
        editor = theme["editor"]
        font_style = ThemeManager.build_font_stylesheet(font)
        indicator_color = app["accent"]
        return f"""
            QDialog#fontSelectionDialog {{
                background: {app['background']};
                color: {app['text']};
                {font_style}
            }}
            QLabel {{
                color: {app['text']};
                {font_style}
            }}
            QFontComboBox,
            QComboBox {{
                background: {app['surface_alt']};
                color: {app['text']};
                border: 1px solid {app['border']};
                border-radius: 0px;
                min-height: 30px;
                padding: 5px 34px 5px 9px;
                selection-background-color: {app['surface_active']};
                selection-color: {app['text']};
            }}
            QFontComboBox:hover,
            QComboBox:hover {{
                background: {app['surface_hover']};
                border-color: {app['border_active']};
            }}
            QFontComboBox:focus,
            QComboBox:focus {{
                border-color: {app['accent']};
            }}
            QFontComboBox::drop-down,
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                background: {app['surface']};
                border-left: 1px solid {app['border']};
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                width: 30px;
            }}
            QFontComboBox::down-arrow,
            QComboBox::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid {indicator_color};
                margin-right: 9px;
            }}
            QFontComboBox QAbstractItemView,
            QComboBox QAbstractItemView,
            QAbstractItemView {{
                background: {app['surface']};
                color: {app['text']};
                border: 1px solid {app['border_active']};
                selection-background-color: {app['surface_active']};
                selection-color: {app['text']};
                outline: 0px;
            }}
            QAbstractItemView::item {{
                min-height: 28px;
                padding: 4px 8px;
            }}
            QLabel#fontPreview {{
                background: {editor['background']};
                color: {editor['foreground']};
                border: 1px solid {editor['border']};
                border-radius: 0px;
                padding: 10px;
            }}
            QPushButton {{
                background: {app['surface']};
                color: {app['text']};
                border: 1px solid {app['border']};
                border-radius: 0px;
                min-width: 76px;
                padding: 6px 12px;
                {font_style}
            }}
            QPushButton:hover {{
                background: {app['surface_hover']};
                border-color: {app['border_active']};
            }}
            QPushButton:pressed {{
                background: {app['surface_active']};
            }}
            QPushButton#titleBarMenuButton {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: 0px;
                color: {app['text']};
                margin: 0px;
                padding: 0px 6px;
                min-width: 0px;
                min-height: 30px;
                max-height: 30px;
                font-size: 12px;
                text-align: center;
                {font_style}
            }}
            QPushButton#titleBarMenuButton:hover {{
                background: {app['surface_hover']};
                border-color: {app['border']};
            }}
            QPushButton#titleBarMenuButton:pressed {{
                background: {app['surface_active']};
                border-color: {app['border_active']};
                color: {app['text']};
            }}
        """

    @staticmethod
    def apply_theme(editor, theme_name, custom_themes=None, font=None):
        theme = ThemeManager.get_theme(theme_name, custom_themes)
        editor_theme = theme["editor"]
        palette = editor.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(editor_theme["background"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(editor_theme["foreground"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(editor_theme["selection"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(editor_theme["foreground"]))
        editor.setPalette(palette)
        editor.setStyleSheet(ThemeManager.build_editor_stylesheet(editor, theme, font))
