import json
import os
from PyQt5.QtGui import QFont
import time

class SettingsManager:
    def __init__(self):
        self.settings_file = os.path.join(os.path.expanduser("~"), ".editor_settings.json")
        self.settings = self.load_settings()
        
        # Create autosave directory
        self.autosave_dir = os.path.join(os.path.expanduser("~"), ".ap_editor_autosave")
        os.makedirs(self.autosave_dir, exist_ok=True)
        
        # Create running flag file
        self.running_flag = os.path.join(self.autosave_dir, "editor_running")
        # Set running flag
        with open(self.running_flag, 'w') as f:
            f.write(str(os.getpid()))

        # Setup backup and recovery directories
        self.backup_dir = os.path.join(os.path.expanduser("~"), ".ap_editor", "backups")
        self.recovery_dir = os.path.join(os.path.expanduser("~"), ".ap_editor", "recovery")
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.recovery_dir, exist_ok=True)
        
        # Create session file
        self.session_file = os.path.join(self.recovery_dir, "session.json")
        self.create_session_file()

        # Create session state file
        self.session_state_file = os.path.join(self.recovery_dir, "session_state.json")
        
        # Initialize with unclean state
        self.initialize_session_state()

        # Clean up old session files if last exit was clean
        if os.path.exists(self.session_state_file):
            try:
                with open(self.session_state_file, 'r') as f:
                    state = json.load(f)
                    if state.get('clean_exit', False):
                        self.cleanup_old_sessions()
            except:
                pass

    def load_settings(self):
        """Load all settings with defaults"""
        default_settings = {
            "theme": "Light",
            "font_family": "Consolas" if os.name == 'nt' else "DejaVu Sans Mono",
            "font_size": 10,
            "font_weight": 50,
            "font_italic": False,
            "show_snippets": True,
            "show_browser": True,
            "last_files": [],
            "homepage": "https://www.apnews.com/",
            "search_sites": {
                "AP News": "site:apnews.com",
                "Reuters": "site:reuters.com",
                "BBC News": "site:bbc.com/news"
            },
            "user_dictionary": [],
            "start_focus_mode": False,
            "pane_states": {
                "snippets_visible": False,
                "browser_visible": False,
                "sizes": [700, 300, 300]
            }
        }
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    saved_settings = json.load(f)
                    # Merge saved settings with defaults
                    return {**default_settings, **saved_settings}
        except Exception as e:
            print(f"Failed to load settings: {str(e)}")
        
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

    def get_autosave_dir(self):
        """Get the directory for autosave files"""
        return self.autosave_dir

    def cleanup_autosave_dir(self):
        """Clean up old autosave files"""
        if os.path.exists(self.autosave_dir):
            try:
                # Remove files older than 7 days
                for filename in os.listdir(self.autosave_dir):
                    filepath = os.path.join(self.autosave_dir, filename)
                    if os.path.getmtime(filepath) < time.time() - 7 * 86400:
                        os.remove(filepath)
            except:
                pass

    def clear_running_flag(self):
        """Clear the running flag on clean exit"""
        try:
            if os.path.exists(self.running_flag):
                os.remove(self.running_flag)
        except:
            pass

    def was_previous_crash(self):
        """Check if previous session crashed"""
        if os.path.exists(self.running_flag):
            try:
                with open(self.running_flag, 'r') as f:
                    old_pid = int(f.read().strip())
                # Check if the process is still running
                try:
                    os.kill(old_pid, 0)
                    # If we get here, the process is still running
                    return False
                except OSError:
                    # Process is not running, was a crash
                    return True
            except:
                return True
        return False

    def create_session_file(self):
        """Create a session file to track clean/dirty exits"""
        session_data = {
            'pid': os.getpid(),
            'timestamp': time.time(),
            'clean_exit': False
        }
        try:
            with open(self.session_file, 'w') as f:
                json.dump(session_data, f)
        except Exception as e:
            print(f"Failed to create session file: {str(e)}")

    def mark_clean_exit(self):
        """Mark that the editor exited cleanly"""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r') as f:
                    session_data = json.load(f)
                session_data['clean_exit'] = True
                with open(self.session_file, 'w') as f:
                    json.dump(session_data, f)
        except Exception as e:
            print(f"Failed to mark clean exit: {str(e)}")

    def needs_recovery(self):
        """Check if we need to recover from a crash"""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r') as f:
                    session_data = json.load(f)
                return not session_data.get('clean_exit', True)
            return True  # If no session file, assume we need recovery
        except Exception as e:
            print(f"Error checking recovery status: {str(e)}")
            return True  # If we can't read the session file, assume we need recovery

    def get_backup_dir(self):
        return self.backup_dir

    def get_recovery_dir(self):
        return self.recovery_dir

    def initialize_session_state(self):
        """Initialize or update session state"""
        try:
            state = {
                'clean_exit': False,
                'timestamp': time.time(),
                'open_tabs': []
            }
            with open(self.session_state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            print(f"Failed to initialize session state: {str(e)}")

    def save_session_state(self, tab_ids, clean_exit=False):
        """Save the list of currently open tab IDs"""
        try:
            state = {
                'open_tabs': tab_ids,
                'clean_exit': clean_exit,
                'timestamp': time.time()
            }
            with open(self.session_state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            print(f"Failed to save session state: {str(e)}")

    def get_session_state(self):
        """Get list of tab IDs that were open in last session"""
        try:
            if os.path.exists(self.session_state_file):
                with open(self.session_state_file, 'r') as f:
                    state = json.load(f)
                    return state.get('open_tabs', [])
        except Exception as e:
            print(f"Failed to load session state: {str(e)}")
        return []

    def cleanup_old_sessions(self):
        """Clean up session files from previous clean exits"""
        # Don't clean up by default - let the session restore handle it
        pass

    def get_setting(self, key, default=None):
        """Get a setting value with a default fallback"""
        try:
            settings = self.load_settings()
            return settings.get(key, default)
        except Exception as e:
            print(f"Failed to get setting {key}: {str(e)}")
            return default

    def save_setting(self, key, value):
        """Save a single setting"""
        try:
            settings = self.load_settings()
            settings[key] = value
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"Failed to save setting {key}: {str(e)}") 