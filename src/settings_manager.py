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
            "skybox_texture": {
                "current": 0,
                "options": [
                    {
                        "name": "Skybox",
                        "file": "utils/skyboxes/skybox_sky.jpg"
                    },
                    {
                        "name": "Venice",
                        "file": "utils/skyboxes/skybox_venice.jpg"
                    },
                    {
                        "name": "Park",
                        "file": "utils/skyboxes/skybox_park.jpg"
                    },
                    {
                        "name": "Hall",
                        "file": "utils/skyboxes/skybox_hall.jpg"
                    }
                ]
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
    
    def get_current_skybox_path(self):
        """Get the file path of the currently selected skybox texture"""
        skybox_settings = self.settings.get("skybox_texture", self.default_settings["skybox_texture"])
        current_index = skybox_settings.get("current", 0)
        options = skybox_settings.get("options", self.default_settings["skybox_texture"]["options"])
        
        if 0 <= current_index < len(options):
            return options[current_index]["file"]
        else:
            # Fallback to first option if index is invalid
            return options[0]["file"] if options else "utils/skybox.jpg"
    
    def get_skybox_options(self):
        """Get all available skybox texture options"""
        skybox_settings = self.settings.get("skybox_texture", self.default_settings["skybox_texture"])
        return skybox_settings.get("options", self.default_settings["skybox_texture"]["options"])
    
    def get_current_skybox_index(self):
        """Get the index of the currently selected skybox texture"""
        skybox_settings = self.settings.get("skybox_texture", self.default_settings["skybox_texture"])
        return skybox_settings.get("current", 0)
    
    def set_skybox_texture(self, index):
        """Set the current skybox texture by index"""
        if "skybox_texture" not in self.settings:
            self.settings["skybox_texture"] = self.default_settings["skybox_texture"].copy()
        
        options = self.settings["skybox_texture"].get("options", [])
        if 0 <= index < len(options):
            self.settings["skybox_texture"]["current"] = index
            self.save_settings()
            return True
        return False