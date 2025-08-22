import json
import os
from utils.path_helper import resource_path

class SettingsManager:
    def __init__(self, settings_file=None):
        # default settings
        self.default_settings = {
            "resolution": {
                "width": 1024,
                "height": 768,
                "index": 0
            },
            "fullscreen": False,
            "show_fps": False,
            "volume": 50,  # Keep this for backward compatibility
            "audio": {
                "master_volume": 50,
                "music_volume": 70,
                "effects_volume": 60,
                "menu_volume": 50
            },
            "auto_rotate": True,
            "auto_rotate_speed": 0.2,
            "background": "skybox",
            "difficulty_skyboxes": {
                "freeplay": "utils/skyboxes/skybox_freeplay.png",
                "easy": "utils/skyboxes/skybox_easy.jpg",
                "medium": "utils/skyboxes/skybox_medium.jpg",
                "hard": "utils/skyboxes/skybox_hard.jpg"
            }
        }

        # Always use a single fixed settings file in src/
        if settings_file is None:
            self.settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
        else:
            self.settings_file = settings_file

        # Load settings from file or use defaults
        self.load_settings()

    def load_settings(self):
        """Load settings from the JSON file, or use default settings if file does not exist."""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as file:
                    self.settings = json.load(file)
                
                # Ensure audio settings exist for backward compatibility
                if "audio" not in self.settings:
                    self.settings["audio"] = self.default_settings["audio"].copy()
                    # Migrate old volume setting if it exists
                    if "volume" in self.settings:
                        self.settings["audio"]["master_volume"] = self.settings["volume"]
                    self.save_settings()
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
    
    def get_skybox_by_difficulty(self, difficulty):
        """Get the skybox path for a specific difficulty level"""
        difficulty_skyboxes = self.settings.get("difficulty_skyboxes", self.default_settings["difficulty_skyboxes"])
        return difficulty_skyboxes.get(difficulty, difficulty_skyboxes["medium"])  # Default to medium if difficulty not found
    
    def get_current_skybox_path(self):
        """Get the file path of the currently selected skybox texture - deprecated, use get_skybox_by_difficulty instead"""
        # For backward compatibility, return the medium difficulty skybox
        return self.get_skybox_by_difficulty("medium")
    
    def get_audio_volume(self, volume_type):
        """Get specific audio volume setting (0-100)"""
        audio_settings = self.settings.get("audio", self.default_settings["audio"])
        return audio_settings.get(volume_type, 50)
    
    def set_audio_volume(self, volume_type, value):
        """Set specific audio volume setting (0-100)"""
        if "audio" not in self.settings:
            self.settings["audio"] = self.default_settings["audio"].copy()
        self.settings["audio"][volume_type] = int(value)
    
    def get_master_volume(self):
        """Get master volume (0-100)"""
        return self.get_audio_volume("master_volume")
    
    def get_music_volume(self):
        """Get music volume (0-100)"""
        return self.get_audio_volume("music_volume")
    
    def get_effects_volume(self):
        """Get effects volume (0-100)"""
        return self.get_audio_volume("effects_volume")
    
    def get_menu_volume(self):
        """Get menu volume (0-100)"""
        return self.get_audio_volume("menu_volume")