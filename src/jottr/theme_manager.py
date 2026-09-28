from copy import deepcopy

from PyQt6.QtGui import QColor, QPalette


class ThemeManager:
    """Theme schema and stylesheet generation for Jottr."""

    DEFAULT_THEME_NAME = "Sepia"
    # Qt::ColorScheme mapping: System→Unknown, Light→Light, Dark→Dark
    UI_THEME_NAMES = ("System", "Light", "Dark")
    DEFAULT_UI_THEME = "System"
    # Legacy editor theme names → current built-in names.
    EDITOR_THEME_ALIASES = {
        "Light": "White",
        "Dark": "Black",
        "default": "Sepia",
    }

    # Interface Look published by SettingsManager ("native" or "organic").
    _interface_look = "native"

    # Accent Color published by SettingsManager: "default" keeps each look's
    # own accent; the others are (label, main, soft, bright, deep) ramps, with
    # an optional {"light": {...}, "dark": {...}} of exact act, hover, soft,
    # ink and on_act colors that replace the derived ones. Terracotta,
    # Sage and Ink come from the Organic design; light schemes use main, soft
    # and deep, dark schemes the bright step and translucent fills of it.
    _accent = "default"
    ACCENT_DEFAULT = "default"
    ACCENTS = {
        "terracotta": ("Terracotta", "#c67139", "#ffe1d0", "#f6a06b", "#643312"),
        "orange": ("Orange", "#d2690f", "#ffe3c4", "#f5a04a", "#6b3408"),
        "clay": ("Clay", "#a4552d", "#e9d3c2", "#d6916a", "#5c2c14", {
            "light": {"act": "#a4552d", "hover": "#884423", "soft": "#e9d3c2",
                      "ink": "#5c2c14", "on_act": "#fffaf3"},
            "dark": {"act": "#d6916a", "hover": "#e3a986", "soft": "rgba(214, 145, 106, 56)",
                     "ink": "#f1cbb3", "on_act": "#2e2b25"},
        }),
        "marigold": ("Marigold", "#b0650f", "#f1dcb8", "#eba24a", "#5e3406", {
            "light": {"act": "#b0650f", "hover": "#93530a", "soft": "#f1dcb8",
                      "ink": "#5e3406", "on_act": "#fffaf3"},
            "dark": {"act": "#eba24a", "hover": "#f2b76b", "soft": "rgba(235, 162, 74, 56)",
                     "ink": "#f8d8a8", "on_act": "#2e2b25"},
        }),
        "sage": ("Sage", "#7a8a5e", "#e1eecc", "#aebf92", "#3d472b"),
        "ink": ("Ink", "#2e2b25", "#eee7db", "#f9f4ed", "#2e2b25"),
        "ocean": ("Ocean", "#3f6f9e", "#d6e4f2", "#7fa7d0", "#1f3a56"),
        "teal": ("Teal", "#2f8578", "#cdeae4", "#6fbfb1", "#174840"),
        "plum": ("Plum", "#8a4f7d", "#f0dcea", "#c68fb9", "#4a2442"),
        "rose": ("Rose", "#c0506a", "#fad7df", "#e88ea2", "#6b2334"),
        "ochre": ("Ochre", "#a0741f", "#f5e6c4", "#e0b660", "#5e4210"),
    }

    # Organic look tokens, from the Organic design system (cream ground,
    # graphite accent). Solid "app" colors feed QPalette; the "organic"
    # tokens (some translucent) feed the look's stylesheet.
    ORGANIC_THEMES = {
        "Light": {
            "app": {
                "background": "#f5ead8",
                "surface": "#f9f4ed",
                "surface_alt": "#eee7db",
                "surface_hover": "#e6dccb",
                "surface_active": "#dcd1bf",
                "text": "#201e1d",
                "muted": "#645c50",
                "border": "#d3c9ba",
                "border_active": "#3d3a36",
                "accent": "#3d3a36",
                "accent_text": "#201e1d",
                "danger": "#b42318"
            },
            "editor": {
                "background": "#f9f4ed",
                "foreground": "#201e1d",
                "selection": "#dcd1bf",
                "current_line": "#eee7db",
                "border": "#d3c9ba"
            },
            "organic": {
                "ground": "#f5ead8",
                "pane": "#f9f4ed",
                "paper": "#f9f4ed",
                "tab": "#f9f4ed",
                "popover": "#f9f4ed",
                "group": "#f9f4ed",
                "ink": "#201e1d",
                "muted": "#645c50",
                "faint": "#a19786",
                "line": "rgba(32, 30, 29, 41)",
                "hover": "rgba(32, 30, 29, 18)",
                "act": "#3d3a36",
                "act_hover": "#2a2825",
                "act_soft": "#dcd1bf",
                "act_ink": "#201e1d",
                "on_act": "#f5ead8",
                "selection": "#dcd1bf",
                "danger": "#b42318"
            }
        },
        # Dark follows GNOME's libadwaita (1.9) dark neutrals: header bar and
        # sidebar #2e2e32, secondary sidebar #28282c, view #1d1d20, popover
        # #36363a, white text with translucent white lines and fills.
        "Dark": {
            "app": {
                "background": "#2e2e32",
                "surface": "#1d1d20",
                "surface_alt": "#28282c",
                "surface_hover": "#3a3a3e",
                "surface_active": "#45454a",
                "text": "#ffffff",
                "muted": "#a3a3a8",
                "border": "#45454a",
                "border_active": "#e6e6e8",
                "accent": "#e6e6e8",
                "accent_text": "#ffffff",
                "danger": "#ff7b63"
            },
            "editor": {
                "background": "#1d1d20",
                "foreground": "#ffffff",
                "selection": "#45454a",
                "current_line": "#28282c",
                "border": "#45454a"
            },
            "organic": {
                "ground": "#2e2e32",
                "pane": "#28282c",
                "paper": "#1d1d20",
                "tab": "#1d1d20",
                "popover": "#36363a",
                "group": "rgba(255, 255, 255, 15)",
                "ink": "#ffffff",
                "muted": "#a3a3a8",
                "faint": "#77777c",
                "line": "rgba(255, 255, 255, 38)",
                "hover": "rgba(255, 255, 255, 20)",
                "act": "#e6e6e8",
                "act_hover": "#ffffff",
                "act_soft": "rgba(255, 255, 255, 41)",
                "act_ink": "#ffffff",
                "on_act": "#222226",
                "selection": "rgba(255, 255, 255, 51)",
                "danger": "#ff7b63"
            }
        }
    }

    BASE_APP = {
        "background": "#f4f6f8",
        "surface": "#ffffff",
        "surface_alt": "#f8fafc",
        "surface_hover": "#eaf3ff",
        "surface_active": "#dbeafe",
        "text": "#17202a",
        "muted": "#566273",
        "border": "#dfe4ea",
        "border_active": "#84b8f3",
        "accent": "#2563eb",
        "accent_text": "#0f3d73",
        "danger": "#dc2626"
    }

    BASE_EDITOR = {
        "background": "#ffffff",
        "foreground": "#17202a",
        "selection": "#dbeafe",
        "current_line": "#f8fafc",
        "border": "#dce3eb"
    }

    DEFAULT_THEMES = {
        "White": {
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
        "Black": {
            "app": {
                "background": "#151922",
                "surface": "#1f2530",
                "surface_alt": "#252c39",
                "surface_hover": "#2d3748",
                "surface_active": "#334155",
                "text": "#e5e7eb",
                "muted": "#a7b0be",
                "border": "#374151",
                "border_active": "#60a5fa",
                "accent": "#60a5fa",
                "accent_text": "#dbeafe",
                "danger": "#f87171"
            },
            "editor": {
                "background": "#111827",
                "foreground": "#e5e7eb",
                "selection": "#374151",
                "current_line": "#1f2937",
                "border": "#374151"
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
                "background": "#f3ead8",
                "surface": "#fff8ea",
                "surface_alt": "#f6ecd8",
                "surface_hover": "#eadbc1",
                "surface_active": "#e4d2b3",
                "text": "#4a3728",
                "muted": "#76614e",
                "border": "#d9c8ad",
                "border_active": "#a87844",
                "accent": "#9a5f2a",
                "accent_text": "#5b3516",
                "danger": "#b42318"
            },
            "editor": {
                "background": "#fff8ea",
                "foreground": "#4a3728",
                "selection": "#d8c4a3",
                "current_line": "#f6ecd8",
                "border": "#d9c8ad"
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
        },
        # Colors from https://github.com/Bali10050/Darkly
        "Darkly": {
            "app": {
                "background": "#222222",
                "surface": "#323232",
                "surface_alt": "#363636",
                "surface_hover": "#4d4d4d",
                "surface_active": "#1b91d5",
                "text": "#f1f1f1",
                "muted": "#c7c7c7",
                "border": "#4d4d4d",
                "border_active": "#00a1ec",
                "accent": "#3478da",
                "accent_text": "#f1f1f1",
                "danger": "#da4453"
            },
            "editor": {
                "background": "#2c2c2c",
                "foreground": "#f1f1f1",
                "selection": "#1b91d5",
                "current_line": "#363636",
                "border": "#4d4d4d"
            },
            "syntax": {
                "comment": "#c7c7c7",
                "keyword": "#3daee9",
                "string": "#24ad59",
                "number": "#f67400",
                "function": "#3478da",
                "type": "#73739e",
                "constant": "#f67400",
                "error": "#da4453"
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

    # Normalized built-in themes. DEFAULT_THEMES is a class-level constant, so
    # normalizing once (instead of on every get_themes call, each of which
    # validates thousands of colors) is safe; callers get deep copies.
    _normalized_default_themes = None

    @staticmethod
    def get_themes():
        if ThemeManager._normalized_default_themes is None:
            ThemeManager._normalized_default_themes = {
                name: ThemeManager.normalize_theme(theme)
                for name, theme in ThemeManager.DEFAULT_THEMES.items()
            }
        return deepcopy(ThemeManager._normalized_default_themes)

    @staticmethod
    def normalize_editor_theme_name(theme_name):
        """Map a saved editor theme name to a built-in theme name."""
        name = str(theme_name or ThemeManager.DEFAULT_THEME_NAME).strip()
        name = ThemeManager.EDITOR_THEME_ALIASES.get(name, name)
        # Unknown names (e.g. removed custom themes) fall back to the default.
        if name not in ThemeManager.DEFAULT_THEMES:
            return ThemeManager.DEFAULT_THEME_NAME
        return name

    @staticmethod
    def get_theme(theme_name):
        themes = ThemeManager.get_themes()
        name = ThemeManager.normalize_editor_theme_name(theme_name)
        return themes.get(name) or themes[ThemeManager.DEFAULT_THEME_NAME]

    @staticmethod
    def normalize_ui_theme(theme_name):
        """Map a saved UI setting to System, Light, or Dark (never custom themes)."""
        name = str(theme_name or ThemeManager.DEFAULT_UI_THEME).strip()
        folded = name.casefold()
        if folded in {
            "default",
            "system",
            "auto",
            "follow system",
            "followsystem",
            "unknown",
        }:
            return "System"
        if name in ThemeManager.UI_THEME_NAMES:
            return name
        # Migrate legacy UI picks (Sepia, Dracula, …) to Light/Dark.
        theme = ThemeManager.get_theme(name)
        return "Dark" if ThemeManager.theme_is_dark(theme) else "Light"

    @staticmethod
    def ui_theme_color_scheme(theme_name):
        """Return Qt.ColorScheme for a System/Light/Dark UI setting."""
        from PyQt6.QtCore import Qt

        normalized = ThemeManager.normalize_ui_theme(theme_name)
        if normalized == "System":
            return Qt.ColorScheme.Unknown
        if normalized == "Dark":
            return Qt.ColorScheme.Dark
        return Qt.ColorScheme.Light

    @staticmethod
    def effective_ui_theme_name(theme_name, application=None):
        """Resolve System/Light/Dark to Light or Dark for chrome colors."""
        from PyQt6.QtCore import Qt

        from jottr.system_color_scheme import system_color_scheme

        normalized = ThemeManager.normalize_ui_theme(theme_name)
        if normalized in {"Light", "Dark"}:
            return normalized

        # Not just styleHints(): sandboxed platform themes report Unknown, so
        # System has to reach the desktop portal to see a dark host.
        scheme = system_color_scheme(application)
        if scheme == Qt.ColorScheme.Dark:
            return "Dark"
        if scheme == Qt.ColorScheme.Light:
            return "Light"
        return "Light"

    @staticmethod
    def set_interface_look(look):
        ThemeManager._interface_look = "organic" if look == "organic" else "native"

    @staticmethod
    def normalize_accent(accent):
        name = str(accent or "").strip().casefold()
        return name if name in ThemeManager.ACCENTS else ThemeManager.ACCENT_DEFAULT

    @staticmethod
    def set_accent(accent):
        ThemeManager._accent = ThemeManager.normalize_accent(accent)

    @staticmethod
    def accent():
        return ThemeManager._accent

    @staticmethod
    def accent_swatch_color(accent, dark=False):
        """The color that stands for *accent* in a picker ("default": the look's own)."""
        accent = ThemeManager.normalize_accent(accent)
        if accent == ThemeManager.ACCENT_DEFAULT:
            if ThemeManager.interface_look() == "organic":
                return QColor(ThemeManager.ORGANIC_THEMES["Dark" if dark else "Light"]["organic"]["act"])
            name = ThemeManager.normalize_editor_theme_name("Dark" if dark else "Light")
            return QColor(ThemeManager.get_theme(name)["app"]["accent"])
        _label, main, _soft, bright, _deep, *_extra = ThemeManager.ACCENTS[accent]
        return QColor(bright if dark else main)

    @staticmethod
    def apply_accent(theme, accent, dark):
        """Recolor a chrome theme's accent roles (a copy is returned)."""
        accent = ThemeManager.normalize_accent(accent)
        if accent == ThemeManager.ACCENT_DEFAULT:
            return theme
        _label, main, soft, bright, deep, *extra = ThemeManager.ACCENTS[accent]
        exact = (extra[0] if extra else {}).get("dark" if dark else "light", {})
        theme = deepcopy(theme)
        app = theme["app"]

        def rgba(color, alpha):
            c = QColor(color)
            return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"

        def blend(color, over, amount):
            a, b = ThemeManager.css_color(color), QColor(over)
            mix = lambda x, y: round(x * amount + y * (1 - amount))
            return QColor(mix(a.red(), b.red()), mix(a.green(), b.green()),
                          mix(a.blue(), b.blue())).name()

        if dark:
            act = exact.get("act", bright)
            act_hover = exact.get("hover") or QColor(act).lighter(110).name()
            act_soft = exact.get("soft") or rgba(act, 61)
            act_ink = exact.get("ink", soft)
            selection = rgba(act, 82)
            fill = ThemeManager.css_color(act_soft).alphaF() if exact.get("soft") else 0.24
            surface_active = blend(act, app["background"], fill)
        else:
            act = exact.get("act", main)
            act_hover = exact.get("hover") or QColor(act).darker(115).name()
            act_soft = exact.get("soft", soft)
            act_ink = exact.get("ink", deep)
            selection = act_soft
            surface_active = act_soft
        app.update({
            "accent": act, "border_active": act,
            "surface_active": surface_active, "accent_text": act_ink,
        })
        tokens = theme.get("organic")
        if tokens:
            tokens.update({
                "act": act, "act_hover": act_hover, "act_soft": act_soft,
                "act_ink": act_ink, "selection": selection,
            })
            if exact.get("on_act"):
                tokens["on_act"] = exact["on_act"]
        return theme

    @staticmethod
    def interface_look():
        return ThemeManager._interface_look

    @staticmethod
    def css_color(value):
        """QColor from a "#rrggbb" or "rgba(r, g, b, a)" token (a is 0-255)."""
        text = str(value or "").strip()
        if text.startswith("rgba(") and text.endswith(")"):
            try:
                r, g, b, a = (int(part) for part in text[5:-1].split(","))
            except ValueError:
                return QColor()
            return QColor(r, g, b, a)
        return QColor(text)

    @staticmethod
    def organic_theme(dark):
        """Chrome theme dict for the Organic look, with its "organic" tokens."""
        source = ThemeManager.ORGANIC_THEMES["Dark" if dark else "Light"]
        theme = ThemeManager.normalize_theme(
            {"name": "Organic", **source, "syntax": ThemeManager.get_theme("White")["syntax"]}
        )
        theme["organic"] = dict(source["organic"])
        return theme

    @staticmethod
    def chrome_tokens(theme):
        """Organic-style color tokens for painting chrome by hand, in either look.

        Organic themes carry them; Native derives the nearest plain colors
        from the theme's "app" section, filling with the accent where Organic
        uses its soft act colors. Values are QColors.
        """
        tokens = theme.get("organic") if isinstance(theme, dict) else None
        app = theme["app"]
        if tokens:
            source = dict(tokens)
        else:
            source = {
                "ground": app["background"],
                "pane": app["surface"],
                "paper": app["surface"],
                "ink": app["text"],
                "muted": app["muted"],
                "faint": app["muted"],
                "line": app["border"],
                "hover": app["surface_hover"],
                "act": app["accent"],
                "act_soft": app["surface_active"],
                "act_ink": app["text"],
                "on_act": "#ffffff" if QColor(app["accent"]).lightnessF() < 0.55 else "#1a1a1a",
                "code": app["surface_alt"],
            }
        source.setdefault("code", source["hover"])
        source.setdefault("danger", app.get("danger", "#b42318"))
        return {key: ThemeManager.css_color(value) for key, value in source.items()}

    # (look, "Light"/"Dark") -> chrome theme; icon tinting resolves it often.
    _ui_theme_cache = {}

    @staticmethod
    def clear_ui_theme_cache():
        ThemeManager._ui_theme_cache.clear()

    @staticmethod
    def get_ui_theme(theme_name, application=None):
        """Chrome theme for a Color Scheme setting (System, Light or Dark).

        System resolves through the desktop. Native chrome uses the White or
        Black theme, the Organic look its own light or dark chrome. Every
        chrome color comes from here; callers share the returned dict.
        """
        ui_name = ThemeManager.effective_ui_theme_name(theme_name, application)
        look = ThemeManager.interface_look()
        accent = ThemeManager.accent()
        key = (look, ui_name, accent)
        cached = ThemeManager._ui_theme_cache.get(key)
        if cached is not None:
            return cached
        if look == "organic":
            theme = ThemeManager.organic_theme(ui_name == "Dark")
        else:
            theme = ThemeManager.get_theme(ThemeManager.normalize_editor_theme_name(ui_name))
        theme = ThemeManager.apply_accent(theme, accent, ui_name == "Dark")
        ThemeManager._ui_theme_cache[key] = theme
        return theme

    @staticmethod
    def theme_is_dark(theme):
        """True when chrome uses a dark background (needs a dark widget-style variant)."""
        if not isinstance(theme, dict):
            return False
        app = theme.get("app")
        if not isinstance(app, dict):
            return False
        background = QColor(app.get("background", ""))
        if background.isValid():
            return background.lightnessF() < 0.5
        text = QColor(app.get("text", ""))
        return text.isValid() and text.lightnessF() >= 0.5

    @staticmethod
    def build_editor_stylesheet(editor, theme, font=None):
        editor_theme = theme["editor"]
        editor_font = font or editor.font()
        font_family = editor_font.family().replace("\\", "\\\\").replace('"', '\\"')
        point_size = editor_font.pointSizeF() if editor_font.pointSizeF() > 0 else editor_font.pointSize()
        if point_size <= 0:
            point_size = 10
        # Organic panes are rounded cards; the padding keeps the square
        # viewport inside the rounded corners.
        radius = 22 if ThemeManager.interface_look() == "organic" else 0
        return f"""
            QTextEdit#writingEditor {{
                background-color: {editor_theme['background']};
                color: {editor_theme['foreground']};
                selection-background-color: {editor_theme['selection']};
                border: none;
                border-radius: {radius}px;
                padding: 18px 22px;
                font-family: "{font_family}";
                font-size: {point_size:g}pt;
                font-weight: normal;
                font-style: {('italic' if editor_font.italic() else 'normal')};
            }}
        """

    @staticmethod
    def build_snippet_panel_stylesheet(theme):
        """Snippets pane in the Editor Theme's colors, so it reads as part of the page."""
        editor_theme = theme["editor"]
        organic = ThemeManager.interface_look() == "organic"
        radius = 22 if organic else 0
        item_radius = 14 if organic else 0
        button_radius = 11 if organic else 3
        item_padding = "0px 6px" if organic else "3px 6px"
        return f"""
            QWidget#sidePanel {{
                background: {editor_theme['background']};
                border-radius: {radius}px;
            }}
            QWidget#panelHeader {{
                background: transparent;
            }}
            QLabel#panelTitle {{
                color: {editor_theme['foreground']};
            }}
            QPushButton#panelHeaderButton, QPushButton#panelCloseButton {{
                background: transparent;
                border: none;
                border-radius: {button_radius}px;
                color: {editor_theme['foreground']};
                padding: 0px;
            }}
            QPushButton#panelHeaderButton:hover, QPushButton#panelCloseButton:hover {{
                background: {editor_theme['current_line']};
            }}
            QListWidget#snippetList {{
                background: transparent;
                color: {editor_theme['foreground']};
                border: none;
                outline: 0;
            }}
            QListWidget#snippetList::item {{
                color: {editor_theme['foreground']};
                border-radius: {item_radius}px;
                padding: {item_padding};
            }}
            QListWidget#snippetList::item:hover {{
                background: {editor_theme['current_line']};
            }}
            QListWidget#snippetList::item:selected {{
                background: {editor_theme['selection']};
                color: {editor_theme['foreground']};
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
    def build_app_palette(theme, base_palette=None):
        """Build a QPalette from theme colors so QStyle-drawn widgets stay themed."""
        app = theme["app"]
        palette = QPalette(base_palette) if base_palette is not None else QPalette()
        background = QColor(app["background"])
        surface = QColor(app["surface"])
        surface_alt = QColor(app["surface_alt"])
        text = QColor(app["text"])
        muted = QColor(app["muted"])
        accent = QColor(app["accent"])
        border = QColor(app["border"])
        # Selection must stay vivid: some styles paint menu-bar chips and
        # focus cues from Highlight / HighlightedText (not the soft surface_active chip).
        highlight = QColor(app["accent"])
        if highlight.lightnessF() >= 0.55:
            highlighted_text = QColor("#1a1a1a")
        else:
            highlighted_text = QColor("#ffffff")

        roles = {
            QPalette.ColorRole.Window: background,
            QPalette.ColorRole.WindowText: text,
            QPalette.ColorRole.Base: surface,
            QPalette.ColorRole.AlternateBase: surface_alt,
            QPalette.ColorRole.Text: text,
            QPalette.ColorRole.Button: surface,
            QPalette.ColorRole.ButtonText: text,
            QPalette.ColorRole.BrightText: accent,
            QPalette.ColorRole.ToolTipBase: surface,
            QPalette.ColorRole.ToolTipText: text,
            QPalette.ColorRole.PlaceholderText: muted,
            QPalette.ColorRole.Highlight: highlight,
            QPalette.ColorRole.HighlightedText: highlighted_text,
            QPalette.ColorRole.Link: accent,
            QPalette.ColorRole.LinkVisited: accent,
            QPalette.ColorRole.Light: surface,
            QPalette.ColorRole.Midlight: surface_alt,
            QPalette.ColorRole.Mid: border,
            QPalette.ColorRole.Dark: muted,
            QPalette.ColorRole.Shadow: border,
        }
        for group in (
            QPalette.ColorGroup.Active,
            QPalette.ColorGroup.Inactive,
            QPalette.ColorGroup.Disabled,
        ):
            for role, color in roles.items():
                value = color
                if group == QPalette.ColorGroup.Disabled and role in (
                    QPalette.ColorRole.WindowText,
                    QPalette.ColorRole.Text,
                    QPalette.ColorRole.ButtonText,
                    QPalette.ColorRole.HighlightedText,
                ):
                    value = muted
                palette.setColor(group, role, value)
        return palette

    @staticmethod
    def apply_app_palette(target, theme):
        """Apply theme colors via QPalette so built-in Qt styles remain visible."""
        from PyQt6.QtWidgets import QApplication

        application = QApplication.instance()
        base = None
        if application is not None and application.style() is not None:
            base = application.style().standardPalette()
        palette = ThemeManager.build_app_palette(theme, base)
        target.setPalette(palette)
        if application is not None and target is application:
            application.setPalette(palette)
        return palette

    @staticmethod
    def build_app_stylesheet(theme=None):
        """Main window QSS: layout only, plus borderless chrome, never colors or fonts.

        Menus, bars, tabs and panels are drawn by the widget style from the
        palette, and Main UI Font reaches them through setFont. Tabs stay
        left-aligned on every platform.
        Menu and toolbar borders are removed so no horizontal line shows.

        The Organic look is the exception: when *theme* carries "organic"
        tokens, its colored stylesheet is appended.
        """
        stylesheet = """
            QMenuBar {
                border: none;
            }
            QToolBar {
                border: none;
            }
            QMainWindow::separator {
                border: none;
            }
            QTabWidget#documentTabs::tab-bar {
                alignment: left;
            }
        """
        if isinstance(theme, dict) and theme.get("organic"):
            stylesheet += ThemeManager.build_organic_stylesheet(theme["organic"])
        return stylesheet

    @staticmethod
    def organic_chevron_path(color):
        """Path to a down-chevron SVG in *color*, written to the cache once.

        Styling QComboBox::drop-down drops the widget style's arrow, so the
        Organic combo boxes draw this one instead.
        """
        import os

        from PyQt6.QtCore import QStandardPaths

        name = QColor(color).name().lstrip("#")
        cache = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.CacheLocation
        ) or os.path.join(os.path.expanduser("~"), ".cache", "jottr")
        path = os.path.join(cache, f"organic-chevron-{name}.svg")
        if not os.path.exists(path):
            os.makedirs(cache, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
                    f'fill="none" stroke="#{name}" stroke-width="2.75" '
                    'stroke-linecap="round" stroke-linejoin="round">'
                    '<path d="m6 9 6 6 6-6"/></svg>'
                )
        return path.replace("\\", "/")

    @staticmethod
    def build_organic_stylesheet(t):
        """Organic look chrome: pill controls, rounded panes on a warm ground.

        Qt drops a border-radius larger than half a widget's height, so each
        radius here stays under half its control's smallest height.
        """
        return f"""
            QMainWindow, QWidget#mainSurface {{
                background: {t['ground']};
            }}
            QMenuBar {{
                background: {t['ground']};
                color: {t['ink']};
                padding: 6px 8px 2px 8px;
            }}
            QMenuBar::item {{
                background: transparent;
                padding: 5px 11px;
                border-radius: 11px;
            }}
            QMenuBar::item:selected {{
                background: {t['hover']};
            }}
            /* The open menu's title matches its highlighted items. */
            QMenuBar::item:pressed {{
                background: {t['act_soft']};
                color: {t['act_ink']};
            }}
            QMenu {{
                background: {t['popover']};
                color: {t['ink']};
                border: 1px solid {t['line']};
                border-radius: 14px;
                padding: 6px;
            }}
            QMenu::item {{
                background: transparent;
                padding: 7px 28px 7px 12px;
                border-radius: 10px;
            }}
            /* Highlighted menu and dropdown items take the accent. */
            QMenu::item:selected {{
                background: {t['act_soft']};
                color: {t['act_ink']};
            }}
            QMenu::item:disabled {{
                color: {t['faint']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {t['line']};
                margin: 5px 10px;
            }}
            QToolTip {{
                background: {t['popover']};
                color: {t['ink']};
                border: 1px solid {t['line']};
                border-radius: 8px;
                padding: 4px 8px;
            }}
            /* QToolBar applies one padding value to all four sides; the
               window adds the rest of the 17px side inset as contents
               margins (see apply_interface_look_chrome). */
            QToolBar#mainToolBar, QToolBar#formatToolBar {{
                background: {t['ground']};
                padding: 6px;
                spacing: 2px;
            }}
            QToolBar::separator {{
                width: 10px;
                background: transparent;
            }}
            QToolBar#mainToolBar QToolButton, QToolBar#formatToolBar QToolButton {{
                background: transparent;
                color: {t['ink']};
                border: none;
                border-radius: 18px;
                padding: 0px;
                margin: 3px 0px;
                min-width: 36px;
                min-height: 36px;
            }}
            QToolBar#mainToolBar QToolButton:hover, QToolBar#formatToolBar QToolButton:hover {{
                background: {t['hover']};
            }}
            QToolBar#mainToolBar QToolButton:checked, QToolBar#formatToolBar QToolButton:checked,
            QToolBar#mainToolBar QToolButton:pressed, QToolBar#formatToolBar QToolButton:pressed {{
                background: {t['act_soft']};
                color: {t['act_ink']};
            }}
            QToolBar#mainToolBar QToolButton::menu-indicator {{
                image: none;
                width: 0px;
            }}
            QTabWidget#documentTabs::pane {{
                border: none;
                background: transparent;
            }}
            QTabWidget#documentTabs QTabBar {{
                background: {t['ground']};
            }}
            QTabWidget#documentTabs QTabBar::tab {{
                background: transparent;
                color: {t['muted']};
                border: none;
                border-radius: 17px;
                padding: 0px 8px 0px 14px;
                margin: 6px 0px 6px 6px;
                min-height: 34px;
            }}
            QTabWidget#documentTabs QTabBar::tab:first {{
                margin-left: 0px;
            }}
            QTabWidget#documentTabs QTabBar::tab:hover {{
                background: {t['hover']};
            }}
            QTabWidget#documentTabs QTabBar::tab:selected {{
                background: {t['tab']};
                color: {t['ink']};
                font-weight: 600;
            }}
            QToolButton#tabCloseButton {{
                background: transparent;
                border: none;
                border-radius: 9px;
                margin-right: 8px;
            }}
            QToolButton#tabCloseButton:hover {{
                background: {t['hover']};
            }}
            QSplitter#mainSplitter::handle, QSplitter#workspaceSplitter::handle,
            QSplitter#markdownSplitter::handle {{
                background: transparent;
            }}
            QWidget#editorPane {{
                background: transparent;
            }}
            QWidget#workspaceExplorer, QWidget#sidePanel, QWidget#markdownPreviewContainer {{
                background: {t['pane']};
                border-radius: 22px;
            }}
            /* The preview page is always white; the card matches it so the
               inset web view blends into the rounded corners. */
            QWidget#markdownPreviewContainer {{
                background: #ffffff;
            }}
            QWidget#workspaceExplorer {{
                margin-top: 6px;
            }}
            QWidget#workspaceHeader, QWidget#panelHeader, QWidget#browserToolbar,
            QWidget#workspaceIdentity {{
                background: transparent;
            }}
            QPushButton#workspaceTitle {{
                background: transparent;
                border: none;
                color: {t['ink']};
                text-align: left;
                padding: 2px 4px;
            }}
            QLabel#workspacePath {{
                color: {t['muted']};
                padding: 0px 4px;
            }}
            QLabel#panelTitle {{
                color: {t['ink']};
                font-weight: 600;
            }}
            QTreeView#workspaceTree, QListWidget#snippetList {{
                background: transparent;
                alternate-background-color: transparent;
                border: none;
                outline: 0;
                padding: 2px 8px 8px 8px;
            }}
            /* Plugin cards paint their own rows (PluginCardDelegate). */
            QListWidget#pluginCardList {{
                background: transparent;
                border: none;
                outline: 0;
            }}
            QTreeView#workspaceTree::item, QListWidget#snippetList::item {{
                color: {t['ink']};
                min-height: 30px;
                border-radius: 14px;
                padding: 0px 6px;
                margin: 1px 0px;
            }}
            QTreeView#workspaceTree::item:hover, QListWidget#snippetList::item:hover {{
                background: {t['hover']};
            }}
            QTreeView#workspaceTree::item:selected, QListWidget#snippetList::item:selected {{
                background: {t['act_soft']};
                color: {t['act_ink']};
            }}
            /* libadwaita's pill button (button.pill in 1.9): a 24px content
               height inside 10px 32px padding, with fully round ends. Qt
               drops a radius over half the height, so 22px stands in for
               its 9999px on the 46px-tall result. */
            QPushButton {{
                background: transparent;
                color: {t['ink']};
                border: 1px solid {t['line']};
                border-radius: 22px;
                min-height: 24px;
                padding: 10px 32px;
            }}
            QPushButton:hover {{
                background: {t['hover']};
            }}
            QPushButton:pressed, QPushButton:checked {{
                background: {t['act_soft']};
                color: {t['act_ink']};
            }}
            QPushButton:default {{
                background: {t['act']};
                border-color: {t['act']};
                color: {t['on_act']};
            }}
            QPushButton:default:hover {{
                background: {t['act_hover']};
            }}
            QPushButton:disabled {{
                color: {t['faint']};
            }}
            /* Compact and icon buttons keep their own (often fixed) sizes. */
            QWidget#findToolbar QPushButton, QWidget#browserToolbar QPushButton {{
                min-height: 0px;
                padding: 0px 10px;
                border-radius: 13px;
            }}
            QWidget#browserToolbar QPushButton#browserIconButton {{
                padding: 0px;
                border-radius: 14px;
            }}
            QPushButton#workspaceToolButton, QPushButton#panelCloseButton,
            QPushButton#panelHeaderButton {{
                background: transparent;
                border: none;
                border-radius: 11px;
                color: {t['muted']};
                min-height: 0px;
                padding: 0px;
            }}
            QPushButton#workspaceToolButton:hover, QPushButton#panelCloseButton:hover,
            QPushButton#panelHeaderButton:hover {{
                background: {t['hover']};
            }}
            QLineEdit {{
                background: {t['paper']};
                color: {t['ink']};
                border: 1px solid {t['line']};
                border-radius: 12px;
                padding: 3px 12px;
                selection-background-color: {t['selection']};
                selection-color: {t['ink']};
            }}
            QLineEdit:focus {{
                border-color: {t['act']};
            }}
            QComboBox {{
                background: {t['paper']};
                color: {t['ink']};
                border: 1px solid {t['line']};
                border-radius: 11px;
                padding: 2px 10px 2px 12px;
            }}
            QComboBox:hover {{
                border-color: {t['muted']};
            }}
            QComboBox::drop-down {{
                border: none;
                background: transparent;
                width: 24px;
            }}
            QComboBox::down-arrow {{
                image: url("{ThemeManager.organic_chevron_path(t['muted'])}");
                width: 12px;
                height: 12px;
            }}
            QComboBox:disabled, QLineEdit:disabled {{
                color: {t['faint']};
            }}
            QComboBox QAbstractItemView {{
                background: {t['popover']};
                color: {t['ink']};
                border: 1px solid {t['line']};
                selection-background-color: {t['act_soft']};
                selection-color: {t['act_ink']};
                outline: 0;
            }}
            QStatusBar#statusBar {{
                background: {t['ground']};
                color: {t['muted']};
                min-height: 38px;
                padding: 0px 14px;
            }}
            QStatusBar#statusBar::item {{
                border: none;
            }}
            QStatusBar#statusBar QLabel {{
                color: {t['muted']};
            }}
            QLabel#documentLanguageStatus {{
                background: {t['act_soft']};
                color: {t['act_ink']};
                border-radius: 10px;
                padding: 2px 10px;
                font-weight: 600;
            }}
            /* Settings: a ground-colored sidebar beside a paper content pane. */
            QWidget#settingsSidebar {{
                background: {t['ground']};
            }}
            QWidget#settingsContent {{
                background: {t['paper']};
            }}
            QWidget#settingsContentDivider {{
                background: transparent;
            }}
            QWidget#settingsContent QScrollArea,
            QWidget#settingsContent QScrollArea > QWidget > QWidget,
            QWidget#settingsContent QStackedWidget {{
                background: transparent;
            }}
            QListWidget#settingsNavList {{
                background: transparent;
                border: none;
                outline: 0;
            }}
            QListWidget#settingsNavList::item {{
                color: {t['ink']};
                min-height: 34px;
                border-radius: 17px;
                padding: 0px 8px;
            }}
            QListWidget#settingsNavList::item:hover {{
                background: {t['hover']};
            }}
            QListWidget#settingsNavList::item:selected {{
                background: {t['act_soft']};
                color: {t['act_ink']};
            }}
            QWidget#settingsContent QGroupBox {{
                border: none;
                margin-top: 22px;
                padding-top: 4px;
            }}
            QWidget#settingsContent QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 0px;
                padding: 0px;
                color: {t['ink']};
            }}
            QWidget#segmentedControl {{
                background: {t['ground']};
                border-radius: 15px;
            }}
            QWidget#segmentedControl QPushButton#segmentedOption {{
                background: transparent;
                border: none;
                border-radius: 12px;
                color: {t['muted']};
                min-height: 0px;
                padding: 4px 16px;
            }}
            QWidget#segmentedControl QPushButton#segmentedOption:hover {{
                color: {t['ink']};
            }}
            QWidget#segmentedControl QPushButton#segmentedOption:checked {{
                background: {t['paper']};
                color: {t['ink']};
            }}
            QWidget#settingsContent QComboBox,
            QWidget#settingsContent QPushButton#fontSettingButton {{
                min-height: 30px;
                border-radius: 16px;
                padding: 2px 12px 2px 16px;
            }}
            QWidget#settingsContent QPushButton#fontSettingButton {{
                background: {t['paper']};
                text-align: left;
            }}
            /* Settings > Plugins. */
            QWidget#settingsContent QLineEdit {{
                min-height: 28px;
                border-radius: 16px;
                padding: 2px 12px;
            }}
            QLineEdit#pluginSearchField {{
                background: {t['ground']};
                border-color: transparent;
            }}
            QLineEdit#pluginSearchField:focus {{
                border-color: {t['act']};
            }}
            /* Buttons packed into a row of actions are libadwaita's regular
               34px buttons rather than pills; flat ones drop the border. */
            QPushButton[compact="true"] {{
                border-radius: 16px;
                min-height: 24px;
                padding: 4px 18px;
            }}
            /* Flat actions are libadwaita's regular (34px) flat buttons. */
            QPushButton#pluginBrowseButton, QPushButton#pluginChannelAction {{
                border-color: transparent;
                border-radius: 16px;
                padding: 4px 14px;
            }}
            QPushButton#pluginBrowseButton:hover, QPushButton#pluginChannelAction:hover {{
                background: {t['hover']};
            }}
            QPushButton#pluginAddChannelButton:checked {{
                background: {t['act_soft']};
                color: {t['act_ink']};
            }}
            QPushButton[primary="true"] {{
                background: {t['act']};
                border-color: {t['act']};
                color: {t['on_act']};
            }}
            QPushButton[primary="true"]:hover {{
                background: {t['act_hover']};
            }}
            QPushButton[primary="true"]:disabled {{
                background: {t['hover']};
                border-color: transparent;
                color: {t['faint']};
            }}
            QPushButton#pluginRemoveButton {{
                border-color: transparent;
                border-radius: 16px;
                color: {t['danger']};
                padding: 4px 14px;
            }}
            QPushButton#pluginRemoveButton:hover {{
                background: {t['hover']};
            }}
            QPushButton#pluginRemoveButton:disabled {{
                color: {t['faint']};
            }}
            QFrame#pluginDetailPanel {{
                background: {t['ground']};
                border-radius: 16px;
            }}
            QLabel#pluginStatusBadge {{
                border: 1px solid {t['line']};
                border-radius: 10px;
                color: {t['muted']};
                padding: 2px 10px;
            }}
            QLabel#pluginStatusBadge[kind="enabled"] {{
                background: {t['act_soft']};
                border-color: transparent;
                color: {t['act_ink']};
            }}
            QLabel#pluginStatusBadge[kind="error"] {{
                border-color: {t['danger']};
                color: {t['danger']};
            }}
            QLabel#pluginPermissionChip {{
                border: 1px solid {t['line']};
                border-radius: 9px;
                padding: 1px 9px;
            }}
            QWidget#pluginStatusDot {{
                background: {t['act']};
                border-radius: 4px;
            }}
        """

    @staticmethod
    def build_dialog_stylesheet(theme, font=None):
        app = theme["app"]
        editor = theme["editor"]
        font_style = ThemeManager.build_font_stylesheet(font)
        # Keep dialog chrome themed; leave buttons/inputs/scrollbars to QStyle.
        return f"""
            QDialog {{
                background: {app['background']};
                color: {app['text']};
                {font_style}
            }}
            QScrollArea {{
                background: {app['background']};
                border: none;
            }}
            QScrollArea > QWidget > QWidget {{
                background: {app['background']};
            }}
            QLabel {{
                color: {app['text']};
                {font_style}
            }}
            QLabel#fontPreview {{
                background: {editor['background']};
                color: {editor['foreground']};
                border: 1px solid {editor['border']};
                border-radius: 0px;
                padding: 10px;
            }}
            QPushButton#fontSettingButton {{
                text-align: left;
            }}
        """

    @staticmethod
    def build_font_dialog_stylesheet(theme=None, font=None):
        # Match Settings / other dialogs: leave chrome to QPalette + QStyle.
        # Only the preview needs QSS (chosen face/size/style + a simple frame).
        # ``theme`` is accepted for call-site compatibility but unused.
        del theme
        preview_font_style = ThemeManager.build_font_stylesheet(font)
        if font is not None:
            preview_font_style += f"""
                font-weight: {"bold" if font.bold() else "normal"};
                font-style: {"italic" if font.italic() else "normal"};
            """
        return f"""
            QLabel#fontPreview {{
                background: palette(base);
                color: palette(text);
                border: 1px solid palette(mid);
                border-radius: 0px;
                padding: 12px;
                {preview_font_style}
            }}
        """

    @staticmethod
    def build_theme_tile_icon(theme, size=16):
        """Build a menu icon: background with two foreground text lines."""
        from PyQt6.QtCore import QPointF, Qt
        from PyQt6.QtGui import QGuiApplication, QIcon, QPainter, QPen, QPixmap

        if not isinstance(theme, dict):
            theme = ThemeManager.get_theme(ThemeManager.DEFAULT_THEME_NAME)
        else:
            theme = ThemeManager.normalize_theme(theme) or ThemeManager.get_theme(
                ThemeManager.DEFAULT_THEME_NAME
            )

        editor = theme["editor"]
        background = editor.get("background", "#ffffff")
        foreground = editor.get("foreground", "#000000")
        if not ThemeManager.is_valid_color(background):
            background = "#ffffff"
        if not ThemeManager.is_valid_color(foreground):
            foreground = "#000000"

        app = QGuiApplication.instance()
        dpr = float(app.devicePixelRatio()) if app is not None else 1.0
        dpr = dpr if dpr > 0 else 1.0
        pixel = max(1, int(round(size * dpr)))

        pixmap = QPixmap(pixel, pixel)
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # Painter uses logical coordinates when the pixmap has a devicePixelRatio.
        painter.fillRect(0, 0, size, size, QColor(background))

        inset = max(3, size // 6)
        line_width = max(2, size // 12)
        gap = max(line_width + 2, size // 5)
        center = size / 2
        painter.setPen(
            QPen(
                QColor(foreground),
                line_width,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.FlatCap,
            )
        )
        # Longer top line, shorter bottom line — like two text rows.
        painter.drawLine(
            QPointF(inset, center - gap / 2),
            QPointF(size - inset, center - gap / 2),
        )
        painter.drawLine(
            QPointF(inset, center + gap / 2),
            QPointF(inset + (size - 2 * inset) * 0.6, center + gap / 2),
        )

        border = editor.get("border")
        if not ThemeManager.is_valid_color(border):
            border = foreground if QColor(background).lightnessF() > 0.5 else "#888888"
        painter.setPen(QPen(QColor(border), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, size - 1, size - 1)
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def apply_theme(editor, theme_name, font=None):
        theme = ThemeManager.get_theme(theme_name)
        editor_theme = theme["editor"]
        palette = editor.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(editor_theme["background"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(editor_theme["foreground"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(editor_theme["selection"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(editor_theme["foreground"]))
        editor.setPalette(palette)
        editor.setStyleSheet(ThemeManager.build_editor_stylesheet(editor, theme, font))
