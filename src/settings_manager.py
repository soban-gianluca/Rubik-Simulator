import os
import json
from utils.path_helper import resource_path

def get_user_settings_path() -> str:
    """
    Path where user-modifiable settings are stored.
    Example: C:/Users/<User>/AppData/Roaming/RubiksCube/settings.json
    """
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    user_dir = os.path.join(base, "RubiksCube")
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, "settings.json")

def load_settings() -> dict:
    """
    Load user settings if available, otherwise load defaults from bundled JSON.
    """
    user_settings = get_user_settings_path()
    if os.path.exists(user_settings):
        with open(user_settings, "r", encoding="utf-8") as f:
            return json.load(f)

    # fallback: load bundled default settings
    default_path = resource_path("src/settings.json")
    with open(default_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings(data: dict) -> None:
    """
    Save settings to the user's local AppData folder (never to the bundled file).
    """
    with open(get_user_settings_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

class SettingsManager:
    def __init__(self, settings_file=None):
        # default settings - keep for backward compatibility methods
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
            "auto_rotate": False,
            "auto_rotate_speed": 0.2,
            "background": "skybox",
            "difficulty_skyboxes": {
                "freeplay": "utils/skyboxes/skybox_freeplay.png",
                "easy": "utils/skyboxes/skybox_easy.jpg",
                "medium": "utils/skyboxes/skybox_medium.jpg",
                "hard": "utils/skyboxes/skybox_hard.jpg",
                "limited_time": "utils/skyboxes/skybox_hard.jpg",  # Use hard skybox for challenge
                "limited_moves": "utils/skyboxes/skybox_medium.jpg"  # Use medium skybox for challenge
            }
        }

        # Load settings using new logic
        self.load_settings()

    def load_settings(self):
        """Load settings using the new read logic."""
        try:
            self.settings = load_settings()
            
            # Ensure audio settings exist for backward compatibility
            if "audio" not in self.settings:
                self.settings["audio"] = self.default_settings["audio"].copy()
                # Migrate old volume setting if it exists
                if "volume" in self.settings:
                    self.settings["audio"]["master_volume"] = self.settings["volume"]
                self.save_settings()
                
            # Ensure difficulty_skyboxes exist for backward compatibility
            if "difficulty_skyboxes" not in self.settings:
                self.settings["difficulty_skyboxes"] = self.default_settings["difficulty_skyboxes"].copy()
                self.save_settings()

        except Exception as e:
            print(f"Error loading settings: {e}")
            self.settings = self.default_settings.copy()

    def save_settings(self):
        """Save current settings using the new write logic."""
        try:
            save_settings(self.settings)
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