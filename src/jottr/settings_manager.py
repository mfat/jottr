import json
import os
from contextlib import contextmanager
from PyQt6.QtGui import QFont, QFontDatabase, QGuiApplication
import time
import sys

DEFAULT_ENABLED_PLUGIN_NAMES = {"browser-panel", "rss-feed"}
DEFAULT_PLUGIN_REGISTRY_URL = "https://raw.githubusercontent.com/Jottrhq/plugins/main/plugins.json"
DEFAULT_PLUGIN_REGISTRY_CHECKSUM_URL = "https://raw.githubusercontent.com/Jottrhq/plugins/main/plugins.json.sha256"
DEFAULT_PLUGIN_CHANNELS = [
    {
        "name": "Official",
        "url": DEFAULT_PLUGIN_REGISTRY_URL,
        "checksumUrl": DEFAULT_PLUGIN_REGISTRY_CHECKSUM_URL,
        "enabled": True,
        "verified": True,
    }
]
TOOLBAR_STYLE_COMFY = "comfy"
TOOLBAR_STYLE_COMPACT = "compact"
TOOLBAR_STYLES = (TOOLBAR_STYLE_COMFY, TOOLBAR_STYLE_COMPACT)
# Legacy saved value / import alias for Compact.
TOOLBAR_STYLE_DEFAULT = TOOLBAR_STYLE_COMPACT
# Former baked-in UI default (Qt5 Normal weight=50). Migrate to the system UI font.
_LEGACY_DEFAULT_UI_FONT = ("DejaVu Sans", 10, 50, False)


class SettingsManager:
    @staticmethod
    def system_ui_font():
        """Desktop UI font from the platform (Plasma/GNOME/etc.), with sane fallbacks."""
        font = QFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont))
        if font.pointSize() <= 0 and font.pointSizeF() <= 0:
            app = QGuiApplication.instance()
            if app is not None:
                font = QFont(app.font())
        if font.pointSize() <= 0 and font.pointSizeF() <= 0:
            font.setPointSize(10)
        if int(font.weight()) < 100:
            font.setWeight(QFont.Weight.Normal)
        return font

    @staticmethod
    def coerce_font_weight(weight):
        """Map legacy Qt5 0–99 weights to Qt6 100–900 (50→400 Normal)."""
        try:
            value = int(weight)
        except (TypeError, ValueError):
            return int(QFont.Weight.Normal)
        if value <= 0:
            return int(QFont.Weight.Normal)
        if value < 100:
            # Qt5 Normal=50, Bold=75 → Qt6 Normal=400, Bold≈600.
            return max(100, min(900, round(value * 8)))
        return max(1, min(1000, value))

    def __init__(self):
        ui_font = self.system_ui_font()
        ui_size = ui_font.pointSize()
        if ui_size <= 0:
            ui_size = round(ui_font.pointSizeF()) if ui_font.pointSizeF() > 0 else 10
        # Initialize default settings
        self.settings = {
            "ui_font_family": ui_font.family(),
            "ui_font_size": ui_size,
            "ui_font_weight": int(ui_font.weight()),
            "ui_font_italic": bool(ui_font.italic()),
            # True = always resolve Main UI Font from the desktop; False = fixed face.
            "ui_font_follow_system": True,
            "font_family": "DejaVu Sans Mono",
            "font_size": 12,
            "font_weight": int(QFont.Weight.Normal),
            "font_italic": False,
            "ui_theme": "System",
            "window_color_scheme": "",
            "theme": "Sepia",
            "qt_style": "System",
            "language": "en_US",
            "icon_theme": "bootstrap",
            "icon_contrast": "auto",
            "toolbar_style": TOOLBAR_STYLE_COMFY,
            "enable_animations": True,
            "spell_check": True,
            "document_language": "auto",
            "spell_languages": ["en_US"],
            "autosave_enabled": False,
            "autosave_interval_seconds": 30,
            "markdown_scroll_sync": True,
            "editor_line_numbers": True,
            "double_click_empty_tab_bar_new_tab": True,
            "middle_click_tab_closes_tab": True,
            "search_sites": {
                "AP News": "site:apnews.com",
                "Reuters": "site:reuters.com",
                "BBC News": "site:bbc.com/news"
            },
            "show_snippets": False,
            "show_browser": False,
            "workspace_path": "",
            "recent_workspaces": [],
            "workspace_sessions": {},
            "workspace_open_files": [],
            "workspace_markdown_files": [],
            "plugins_directory": "",
            "plugin_remote_sources": [],
            "plugin_registry_url": DEFAULT_PLUGIN_REGISTRY_URL,
            "plugin_registry_checksum_url": DEFAULT_PLUGIN_REGISTRY_CHECKSUM_URL,
            "plugin_channels": DEFAULT_PLUGIN_CHANNELS,
            "plugin_channel_filter": "all",
            "plugin_state": {},
            "pane_states": {
                "snippets_visible": False,
                "browser_visible": False,
                "markdown_preview_visible": False,
                "markdown_sizes": [600, 600],
                "sizes": [700, 300, 300]
            }
        }
        
        # Set up config directory based on platform
        if sys.platform == 'darwin':
            self.config_dir = os.path.join(os.path.expanduser('~/Library/Application Support'), 'Jottr')
        elif sys.platform == 'win32':
            self.config_dir = os.path.join(os.getenv('APPDATA'), 'Jottr')
        else:  # Linux/Unix
            CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
            self.config_dir = os.path.join(CONFIG_HOME, "Jottr")
        
        # Create config directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Define paths for different data types
        self.settings_file = os.path.join(self.config_dir, 'settings.json')
        self.snippets_dir = os.path.join(self.config_dir, 'snippets')
        self.dict_file = os.path.join(self.config_dir, 'user_dictionary.txt')
        self.settings["plugins_directory"] = os.path.join(self.config_dir, "plugins")
        
        # Create snippets directory
        os.makedirs(self.snippets_dir, exist_ok=True)

        self._save_depth = 0
        self._save_pending = False

        # Initialize settings
        self.load_settings()
        
        # # Create autosave directory
        # self.autosave_dir = os.path.join(os.path.expanduser("~"), ".ap_editor_autosave")
        # os.makedirs(self.autosave_dir, exist_ok=True)
        
        # # Create running flag file
        # self.running_flag = os.path.join(self.autosave_dir, "editor_running")
        # # Set running flag
        # with open(self.running_flag, 'w') as f:
        #     f.write(str(os.getpid()))

        # # Setup backup and recovery directories
        # self.backup_dir = os.path.join(os.path.expanduser("~"), ".ap_editor", "backups")
        # self.recovery_dir = os.path.join(os.path.expanduser("~"), ".ap_editor", "recovery")
        # os.makedirs(self.backup_dir, exist_ok=True)
        # os.makedirs(self.recovery_dir, exist_ok=True)
        
        # # Create session file
        # self.session_file = os.path.join(self.recovery_dir, "session.json")
        # self.create_session_file()

        # # Create session state file
        # self.session_state_file = os.path.join(self.recovery_dir, "session_state.json")
        
        # # Initialize with unclean state
        # self.initialize_session_state()

        # Clean up old session files if last exit was clean
        # if os.path.exists(self.session_state_file):
        #     try:
        #         with open(self.session_state_file, 'r') as f:
        #             state = json.load(f)
        #             if state.get('clean_exit', False):
        #                 self.cleanup_old_sessions()
        #     except:
        #         pass

    def load_settings(self):
        """Load settings from file"""
        settings_path = os.path.join(self.config_dir, 'settings.json')
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    had_follow_flag = "ui_font_follow_system" in saved_settings
                    self.settings.update(saved_settings)
                    # Custom editor themes are no longer supported.
                    self.settings.pop("custom_themes", None)
                    self.migrate_legacy_font_settings(had_follow_flag=had_follow_flag)
                    self.migrate_default_window_scheme_follows_system()
            except Exception as e:
                print(f"Error loading settings: {str(e)}")

    def migrate_default_window_scheme_follows_system(self):
        """Default Window Color Scheme must follow the desktop (System ui_theme)."""
        from jottr.window_color_scheme import find_window_color_scheme

        scheme_id = self.settings.get("window_color_scheme", "")
        if find_window_color_scheme(scheme_id).path:
            return
        if self.get_ui_theme() == "System":
            return
        self.settings["ui_theme"] = "System"
        self.save_settings()

    def migrate_legacy_font_settings(self, had_follow_flag=True):
        """Replace the old DejaVu UI default and coerce Qt5 font weights."""
        changed = False
        family = self.settings.get("ui_font_family")
        size = self.settings.get("ui_font_size")
        weight = self.settings.get("ui_font_weight")
        italic = bool(self.settings.get("ui_font_italic", False))
        legacy_family, legacy_size, legacy_weight, legacy_italic = _LEGACY_DEFAULT_UI_FONT
        is_legacy_ui = (
            family == legacy_family
            and size == legacy_size
            and weight == legacy_weight
            and italic == legacy_italic
        )
        if is_legacy_ui:
            ui_font = self.system_ui_font()
            ui_size = ui_font.pointSize()
            if ui_size <= 0:
                ui_size = round(ui_font.pointSizeF()) if ui_font.pointSizeF() > 0 else 10
            self.settings["ui_font_family"] = ui_font.family()
            self.settings["ui_font_size"] = ui_size
            self.settings["ui_font_weight"] = int(ui_font.weight())
            self.settings["ui_font_italic"] = bool(ui_font.italic())
            self.settings["ui_font_follow_system"] = True
            changed = True
        else:
            coerced = self.coerce_font_weight(weight)
            if weight != coerced:
                self.settings["ui_font_weight"] = coerced
                changed = True
            # Older installs snapped a concrete face without a follow flag —
            # keep that face until the user picks System default explicitly.
            if not had_follow_flag:
                self.settings["ui_font_follow_system"] = False
                changed = True

        editor_weight = self.settings.get("font_weight")
        coerced_editor = self.coerce_font_weight(editor_weight)
        if editor_weight != coerced_editor:
            self.settings["font_weight"] = coerced_editor
            changed = True

        if changed:
            self.save_settings()

    @contextmanager
    def defer_saves(self):
        """Coalesce nested save_setting/save_* calls into one disk write."""
        self._save_depth += 1
        try:
            yield
        finally:
            self._save_depth -= 1
            if self._save_depth == 0 and self._save_pending:
                self._save_pending = False
                self._write_settings()

    def save_settings(self):
        if self._save_depth > 0:
            self._save_pending = True
            return
        self._write_settings()

    def _write_settings(self):
        with open(self.settings_file, 'w') as f:
            json.dump(self.settings, f)

    def font_setting_prefix(self, role):
        prefixes = {
            "ui": "ui_font",
            "editor": "font",
        }
        return prefixes.get(role, "font")

    def uses_system_ui_font(self):
        """True when Main UI Font should track the desktop GeneralFont."""
        return bool(self.settings.get("ui_font_follow_system", False))

    def get_font(self, role="editor"):
        if role == "ui" and self.uses_system_ui_font():
            return self.system_ui_font()
        prefix = self.font_setting_prefix(role)
        legacy_prefix = "font"
        family = self.settings.get(f"{prefix}_family", self.settings[f"{legacy_prefix}_family"])
        size = self.settings.get(f"{prefix}_size", self.settings[f"{legacy_prefix}_size"])
        weight = self.coerce_font_weight(
            self.settings.get(f"{prefix}_weight", self.settings[f"{legacy_prefix}_weight"])
        )
        font = QFont(family, size, weight)
        font.setItalic(self.settings.get(f"{prefix}_italic", self.settings[f"{legacy_prefix}_italic"]))
        return font

    def save_font(self, font, role="editor", follow_system=None):
        prefix = self.font_setting_prefix(role)
        if role == "ui":
            # Explicit custom save clears follow-system unless asked otherwise.
            follow = bool(follow_system) if follow_system is not None else False
            self.settings["ui_font_follow_system"] = follow
            if follow:
                font = self.system_ui_font()
        point_size = font.pointSize()
        if point_size <= 0:
            point_size = round(font.pointSizeF()) if font.pointSizeF() > 0 else 10
        self.settings.update({
            f"{prefix}_family": font.family(),
            f"{prefix}_size": point_size,
            f"{prefix}_weight": self.coerce_font_weight(font.weight()),
            f"{prefix}_italic": font.italic()
        })
        self.save_settings()

    def get_theme(self):
        from jottr.theme_manager import ThemeManager

        theme = self.settings.get("theme", ThemeManager.DEFAULT_THEME_NAME)
        return ThemeManager.normalize_editor_theme_name(theme)

    def save_theme(self, theme):
        from jottr.theme_manager import ThemeManager

        self.settings["theme"] = ThemeManager.normalize_editor_theme_name(theme)
        self.save_settings()

    def get_ui_theme(self):
        from jottr.theme_manager import ThemeManager

        theme = self.settings.get("ui_theme", self.settings.get("theme", "System"))
        return ThemeManager.normalize_ui_theme(theme)

    def save_ui_theme(self, theme):
        from jottr.theme_manager import ThemeManager

        self.settings["ui_theme"] = ThemeManager.normalize_ui_theme(theme)
        self.save_settings()

    def get_window_color_scheme(self):
        from jottr.window_color_scheme import normalize_window_color_scheme

        return normalize_window_color_scheme(
            self.settings.get("window_color_scheme", "")
        )

    def save_window_color_scheme(self, scheme_id):
        from jottr.window_color_scheme import (
            find_window_color_scheme,
            normalize_window_color_scheme,
        )

        scheme_id = normalize_window_color_scheme(scheme_id)
        self.settings["window_color_scheme"] = scheme_id
        # Default follows the desktop; drop a stale Light/Dark ui_theme so
        # chrome matches GNOME/Plasma after the Appearance control was removed.
        if not find_window_color_scheme(scheme_id).path:
            self.settings["ui_theme"] = "System"
        self.save_settings()

    def get_qt_style(self):
        from jottr.qt_style import normalize_qt_style

        return normalize_qt_style(self.settings.get("qt_style", "System"))

    def save_qt_style(self, style_name):
        from jottr.qt_style import normalize_qt_style

        self.settings["qt_style"] = normalize_qt_style(style_name)
        self.save_settings()

    def get_icon_theme(self):
        from jottr.icon_manager import normalize_icon_theme

        return normalize_icon_theme(self.settings.get("icon_theme", "bootstrap"))

    def save_icon_theme(self, theme_id):
        from jottr.icon_manager import normalize_icon_theme

        self.settings["icon_theme"] = normalize_icon_theme(theme_id)
        self.save_settings()

    @staticmethod
    def normalize_toolbar_style(style_name):
        """Map a saved value to comfy (padded QSS) or compact (chrome color, native buttons)."""
        name = (style_name or TOOLBAR_STYLE_COMFY).strip().casefold()
        if name in {TOOLBAR_STYLE_COMPACT, "default", "system", "native"}:
            return TOOLBAR_STYLE_COMPACT
        return TOOLBAR_STYLE_COMFY

    def get_toolbar_style(self):
        return self.normalize_toolbar_style(
            self.settings.get("toolbar_style", TOOLBAR_STYLE_COMFY)
        )

    def save_toolbar_style(self, style_name):
        self.settings["toolbar_style"] = self.normalize_toolbar_style(style_name)
        self.save_settings()

    def get_pane_visibility(self):
        return (self.settings["show_snippets"], self.settings["show_browser"])

    def save_pane_visibility(self, show_snippets, show_browser):
        self.settings.update({
            "show_snippets": show_snippets,
            "show_browser": show_browser
        })
        self.save_settings()

    # def save_last_files(self, files):
    #     """Save list of last opened files"""
    #     self.settings["last_files"] = files
    #     self.save_settings()

    # def get_last_files(self):
    #     """Get list of last opened files"""
    #     return self.settings.get("last_files", [])

    # def get_autosave_dir(self):
    #     """Get the directory for autosave files"""
    #     return self.autosave_dir

    # def cleanup_autosave_dir(self):
    #     """Clean up old autosave files"""
    #     if os.path.exists(self.autosave_dir):
    #         try:
    #             # Remove files older than 7 days
    #             for filename in os.listdir(self.autosave_dir):
    #                 filepath = os.path.join(self.autosave_dir, filename)
    #                 if os.path.getmtime(filepath) < time.time() - 7 * 86400:
    #                     os.remove(filepath)
    #         except:
    #             pass

    # def clear_running_flag(self):
    #     """Clear the running flag on clean exit"""
    #     try:
    #         if os.path.exists(self.running_flag):
    #             os.remove(self.running_flag)
    #     except:
    #         pass

    # def was_previous_crash(self):
    #     """Check if previous session crashed"""
    #     if os.path.exists(self.running_flag):
    #         try:
    #             with open(self.running_flag, 'r') as f:
    #                 old_pid = int(f.read().strip())
    #             # Check if the process is still running
    #             try:
    #                 os.kill(old_pid, 0)
    #                 # If we get here, the process is still running
    #                 return False
    #             except OSError:
    #                 # Process is not running, was a crash
    #                 return True
    #         except:
    #             return True
    #     return False

    # def create_session_file(self):
    #     """Create a session file to track clean/dirty exits"""
    #     session_data = {
    #         'pid': os.getpid(),
    #         'timestamp': time.time(),
    #         'clean_exit': False
    #     }
    #     try:
    #         with open(self.session_file, 'w') as f:
    #             json.dump(session_data, f)
    #     except Exception as e:
    #         print(f"Failed to create session file: {str(e)}")

    # def mark_clean_exit(self):
    #     """Mark that the editor exited cleanly"""
    #     try:
    #         if os.path.exists(self.session_file):
    #             with open(self.session_file, 'r') as f:
    #                 session_data = json.load(f)
    #             session_data['clean_exit'] = True
    #             with open(self.session_file, 'w') as f:
    #                 json.dump(session_data, f)
    #     except Exception as e:
    #         print(f"Failed to mark clean exit: {str(e)}")

    # def needs_recovery(self):
    #     """Check if we need to recover from a crash"""
    #     try:
    #         if os.path.exists(self.session_file):
    #             with open(self.session_file, 'r') as f:
    #                 session_data = json.load(f)
    #             return not session_data.get('clean_exit', True)
    #         return True  # If no session file, assume we need recovery
    #     except Exception as e:
    #         print(f"Error checking recovery status: {str(e)}")
    #         return True  # If we can't read the session file, assume we need recovery

    # def get_backup_dir(self):
    #     return self.backup_dir

    # def get_recovery_dir(self):
    #     return self.recovery_dir

    # def initialize_session_state(self):
    #     """Initialize or update session state"""
    #     try:
    #         state = {
    #             'clean_exit': False,
    #             'timestamp': time.time(),
    #             'open_tabs': []
    #         }
    #         with open(self.session_state_file, 'w') as f:
    #             json.dump(state, f)
    #     except Exception as e:
    #         print(f"Failed to initialize session state: {str(e)}")

    # def save_session_state(self, tab_ids, clean_exit=False):
    #     """Save the list of currently open tab IDs"""
    #     try:
    #         state = {
    #             'open_tabs': tab_ids,
    #             'clean_exit': clean_exit,
    #             'timestamp': time.time()
    #         }
    #         with open(self.session_state_file, 'w') as f:
    #             json.dump(state, f)
    #     except Exception as e:
    #         print(f"Failed to save session state: {str(e)}")

    # def get_session_state(self):
    #     """Get list of tab IDs that were open in last session"""
    #     try:
    #         if os.path.exists(self.session_state_file):
    #             with open(self.session_state_file, 'r') as f:
    #                 state = json.load(f)
    #                 return state.get('open_tabs', [])
    #     except Exception as e:
    #         print(f"Failed to load session state: {str(e)}")
    #     return []

    # def cleanup_old_sessions(self):
    #     """Clean up session files from previous clean exits"""
    #     # Don't clean up by default - let the session restore handle it
    #     pass

    def get_setting(self, key, default=None):
        """Get a setting value with a default fallback"""
        try:
            return self.settings.get(key, default)
        except Exception as e:
            print(f"Failed to get setting {key}: {str(e)}")
            return default

    def save_setting(self, key, value):
        """Save a single setting"""
        try:
            self.settings[key] = value
            self.save_settings()
        except Exception as e:
            print(f"Failed to save setting {key}: {str(e)}")

    def is_plugin_enabled(self, plugin_name):
        state = self.settings.get("plugin_state", {}).get(plugin_name, {})
        return bool(state.get("enabled", plugin_name in DEFAULT_ENABLED_PLUGIN_NAMES))
