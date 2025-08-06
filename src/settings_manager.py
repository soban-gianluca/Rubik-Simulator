import json
import os

class SettingsManager:
    def __init__(self, settings_file="settings.json"):
        #default settings
        self.default_settings = {
            "resolution": {
                "width": 1024,
                "height": 768,
                "index": 0
            },
            "fullscreen": False,
            "show_fps": False,
            "volume": 50,
            "auto_rotate": True,
            "auto_rotate_speed": 0.2,
            "background": "skybox",
            "difficulty_skyboxes": {
                "freeplay": "utils/skyboxes/skybox_easy.jpg",
                "easy": "utils/skyboxes/skybox_easy.jpg",
                "medium": "utils/skyboxes/skybox_medium.jpg", 
                "hard": "utils/skyboxes/skybox_hard.jpg"
            }
        }

        #Path to settings file
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
    
    def get_skybox_by_difficulty(self, difficulty):
        """Get the skybox path for a specific difficulty level"""
        difficulty_skyboxes = self.settings.get("difficulty_skyboxes", self.default_settings["difficulty_skyboxes"])
        return difficulty_skyboxes.get(difficulty, difficulty_skyboxes["medium"])  # Default to medium if difficulty not found
    
    def get_current_skybox_path(self):
        """Get the file path of the currently selected skybox texture - deprecated, use get_skybox_by_difficulty instead"""
        # For backward compatibility, return the medium difficulty skybox
        return self.get_skybox_by_difficulty("medium")