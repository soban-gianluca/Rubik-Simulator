import os
import json
import uuid
from utils.path_helper import resource_path

def get_user_data_path() -> str:
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    user_dir = os.path.join(base, "RubiksCubeSimulator")
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, "user.json")

# Available regions
REGIONS = ["Europe", "Americas", "Asia", "Oceania", "Africa"]

class UserManager:
    def __init__(self):
        self.user_file = get_user_data_path()
        self.default_user = {
            "username": None,
            "region": None,
            "created_at": None,
            "user_id": None,  # Stable unique identifier for the user
            "setup_completed": False
        }
        self.user_data = self.load_user_data()
    
    def load_user_data(self) -> dict:
        """Load user data from file"""
        try:
            if os.path.exists(self.user_file):
                with open(self.user_file, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                
                # Ensure all fields exist for backward compatibility
                for field in self.default_user:
                    if field not in loaded_data:
                        loaded_data[field] = self.default_user[field]
                
                return loaded_data
            else:
                return self.default_user.copy()
        except Exception as e:
            print(f"Error loading user data: {e}")
            return self.default_user.copy()
    
    def save_user_data(self):
        """Save user data to file"""
        try:
            with open(self.user_file, "w", encoding="utf-8") as f:
                json.dump(self.user_data, f, indent=4)
        except Exception as e:
            print(f"Error saving user data: {e}")
    
    def is_setup_completed(self) -> bool:
        """Check if user has completed initial setup"""
        return self.user_data.get("setup_completed", False)
    
    def get_username(self) -> str:
        """Get the username"""
        return self.user_data.get("username", "")
    
    def get_region(self) -> str:
        """Get the region"""
        return self.user_data.get("region", "")
    
    def get_user_id(self) -> str:
        """Get the stable user ID"""
        user_id = self.user_data.get("user_id")
        # Generate a user_id if it doesn't exist (for backward compatibility)
        if not user_id and self.is_setup_completed():
            user_id = str(uuid.uuid4())
            self.user_data["user_id"] = user_id
            self.save_user_data()
        return user_id or ""
    
    def set_username(self, username: str):
        """Set the username"""
        self.user_data["username"] = username
        self.save_user_data()
    
    def set_region(self, region: str):
        """Set the region"""
        if region in REGIONS:
            self.user_data["region"] = region
            self.save_user_data()
    
    def complete_setup(self, username: str, region: str):
        """Complete the initial user setup"""
        from datetime import datetime
        self.user_data["username"] = username
        self.user_data["region"] = region
        self.user_data["setup_completed"] = True
        self.user_data["created_at"] = datetime.now().isoformat()
        # Generate a stable unique user ID that won't change when username changes
        self.user_data["user_id"] = str(uuid.uuid4())
        self.save_user_data()
    
    def update_user(self, username: str, region: str):
        """Update user information"""
        self.user_data["username"] = username
        self.user_data["region"] = region
        self.save_user_data()
    
    @staticmethod
    def get_available_regions() -> list:
        """Get list of available regions"""
        return REGIONS.copy()
