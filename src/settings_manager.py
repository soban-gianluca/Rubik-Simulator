import json
import os

class SettingsManager:
    def __init__(self, settings_file="settings.json"):
        #default settings
        self.default_settings = {
            "resolution": {
                "width": 1024,
                "height": 768,
                "index": 0 # Index for resolution presets
            },
            "fullscreen": False,
            "show_fps": False,
            "volume": 50,
            "auto_rotate": True,
            "auto_rotate_speed": 0.2,
        }

        #Path to settings file - store in the src directory
        self.settings_file = os.path.join(os.path.dirname(__file__), settings_file)

        #Load settings from file or use defaults
        self.load_settings()

    def load_settings(self):
        """Load settings from the JSON file, or use default settings if file does not exist."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as file:
                    self.settings = json.load(file)
            else:
                self.settings = self.default_settings.copy()
                self.save_settings()

        except Exception as e:
            print(f"Error loading settings: {e}")
            self.settings = self.default_settings.copy()

    def save_settings(self):
        """Save current settings to JSON file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")