import os
import json
from datetime import datetime
from utils.path_helper import resource_path


def get_achievements_path() -> str:
    """
    Path where achievements data is stored.
    Example: C:/Users/<User>/AppData/Roaming/RubiksCubeSimulator/achievements.json
    """
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    user_dir = os.path.join(base, "RubiksCubeSimulator")
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, "achievements.json")


# Achievement definitions with categories, descriptions, and unlock conditions
ACHIEVEMENTS = {
    # Beginner achievements
    "first_solve": {
        "name": "The Beginning of an Era",
        "description": "Solve your first cube on Easy difficulty",
        "icon": "utils/icons/achievements/beginner/first-solve.png",
        "category": "beginner",
        "condition_type": "solve_easy",
        "target": 1,
        "secret": False
    },
    "first_medium": {
        "name": "Rising Star",
        "description": "Solve your first cube on Medium difficulty",
        "icon": "utils/icons/achievements/beginner/first-medium.png",
        "category": "beginner",
        "condition_type": "solve_medium",
        "target": 1,
        "secret": False
    },
    "first_hard": {
        "name": "Challenge Accepted",
        "description": "Solve your first cube on Hard difficulty",
        "icon": "utils/icons/achievements/beginner/first-hard.png",
        "category": "beginner",
        "condition_type": "solve_hard",
        "target": 1,
        "secret": False
    },
    
    # Progression achievements (with progress bars)
    "solve_5": {
        "name": "Getting Started",
        "description": "Solve 5 cubes in any mode",
        "icon": "utils/icons/achievements/progression/solve-5.png",
        "category": "progression",
        "condition_type": "total_solves",
        "target": 5,
        "secret": False
    },
    "solve_10": {
        "name": "Dedicated Solver",
        "description": "Solve 10 cubes in any mode",
        "icon": "utils/icons/achievements/progression/solve-10.png",
        "category": "progression",
        "condition_type": "total_solves",
        "target": 10,
        "secret": False
    },
    "solve_25": {
        "name": "Cube Enthusiast",
        "description": "Solve 25 cubes in any mode",
        "icon": "utils/icons/achievements/progression/solve-25.png",
        "category": "progression",
        "condition_type": "total_solves",
        "target": 25,
        "secret": False
    },
    "solve_50": {
        "name": "Rubik's Apprentice",
        "description": "Solve 50 cubes in any mode",
        "icon": "utils/icons/achievements/progression/solve-50.png",
        "category": "progression",
        "condition_type": "total_solves",
        "target": 50,
        "secret": False
    },
    "solve_100": {
        "name": "Century Club",
        "description": "Solve 100 cubes in any mode",
        "icon": "utils/icons/achievements/progression/solve-100.png",
        "category": "progression",
        "condition_type": "total_solves",
        "target": 100,
        "secret": False
    },
    
    # Speed achievements
    "speed_under_2min": {
        "name": "Under Two",
        "description": "Solve a Hard cube in under 2 minutes",
        "icon": "utils/icons/achievements/speed/under-2min.png",
        "category": "speed",
        "condition_type": "time_under",
        "target": 120,
        "difficulty": "hard",
        "secret": False
    },
    "speed_under_1min": {
        "name": "Speed Demon",
        "description": "Solve a Hard cube in under 1 minute",
        "icon": "utils/icons/achievements/speed/under-1min.png",
        "category": "speed",
        "condition_type": "time_under",
        "target": 60,
        "difficulty": "hard",
        "secret": False
    },
    "speed_under_30s": {
        "name": "Lightning Fast",
        "description": "Solve a Hard cube in under 30 seconds",
        "icon": "utils/icons/achievements/speed/under-30sec.png",
        "category": "speed",
        "condition_type": "time_under",
        "target": 30,
        "difficulty": "hard",
        "secret": False
    },
    
    # Challenge mode achievements
    "limited_time_win": {
        "name": "Beat the Clock",
        "description": "Win a Limited Time challenge",
        "icon": "utils/icons/achievements/challenge-mode/limited-time-win.png",
        "category": "challenge",
        "condition_type": "solve_limited_time",
        "target": 1,
        "secret": False
    },
    "limited_moves_win": {
        "name": "Efficiency Expert",
        "description": "Win a Limited Moves challenge",
        "icon": "utils/icons/achievements/challenge-mode/limited-moves-win.png",
        "category": "challenge",
        "condition_type": "solve_limited_moves",
        "target": 1,
        "secret": False
    },
    "limited_time_5": {
        "name": "Time Keeper",
        "description": "Win 5 Limited Time challenges",
        "icon": "utils/icons/achievements/challenge-mode/limited-time-5.png",
        "category": "challenge",
        "condition_type": "solve_limited_time",
        "target": 5,
        "secret": False
    },
    "limited_moves_5": {
        "name": "Move Master",
        "description": "Win 5 Limited Moves challenges",
        "icon": "utils/icons/achievements/challenge-mode/limited-moves-5.png",
        "category": "challenge",
        "condition_type": "solve_limited_moves",
        "target": 5,
        "secret": False
    },
    
    # Daily cube achievements
    "daily_first": {
        "name": "Daily Challenger",
        "description": "Complete your first Daily Cube",
        "icon": "utils/icons/achievements/daily/daily-first.png",
        "category": "daily",
        "condition_type": "solve_daily",
        "target": 1,
        "secret": False
    },
    "daily_7": {
        "name": "Weekly Warrior",
        "description": "Complete 7 Daily Cubes",
        "icon": "utils/icons/achievements/daily/daily-7.png",
        "category": "daily",
        "condition_type": "solve_daily",
        "target": 7,
        "secret": False
    },
    
    # Efficiency achievements
    "efficient_easy": {
        "name": "Efficient Beginner",
        "description": "Solve an Easy cube in 10 moves or less",
        "icon": "utils/icons/achievements/efficiency/efficient-easy.png",
        "category": "efficiency",
        "condition_type": "moves_under",
        "target": 10,
        "difficulty": "easy",
        "secret": False
    },
    "efficient_medium": {
        "name": "Optimal Solver",
        "description": "Solve a Medium cube in 20 moves or less",
        "icon": "utils/icons/achievements/efficiency/efficient-medium.png",
        "category": "efficiency",
        "condition_type": "moves_under",
        "target": 20,
        "difficulty": "medium",
        "secret": False
    },
    
    # Secret achievements
    "secret_scrambler": {
        "name": "Just Looking",
        "description": "Scramble the cube 10 times without solving",
        "icon": "utils/icons/achievements/secret/secret-scrambler.png",
        "category": "secret",
        "condition_type": "scramble_count",
        "target": 10,
        "secret": True
    },
}


class AchievementsManager:
    def __init__(self):
        self.achievements_file = get_achievements_path()
        self.default_data = {
            "unlocked": {},  # achievement_id: unlock_timestamp
            "progress": {},  # achievement_id: current_progress (for progress-based achievements)
            "stats": {
                "total_solves": 0,
                "easy_solves": 0,
                "medium_solves": 0,
                "hard_solves": 0,
                "limited_time_wins": 0,
                "limited_moves_wins": 0,
                "daily_solves": 0,
                "scramble_count": 0,
                "best_times": {},  # difficulty: best_time
                "best_moves": {}   # difficulty: best_moves
            }
        }
        self.data = self.load_data()
        self.newly_unlocked = []  # Track newly unlocked achievements for notifications
    
    def load_data(self) -> dict:
        """Load achievements data from file"""
        try:
            if os.path.exists(self.achievements_file):
                with open(self.achievements_file, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                
                # Ensure all fields exist for backward compatibility
                for key in self.default_data:
                    if key not in loaded_data:
                        loaded_data[key] = self.default_data[key]
                
                # Ensure all stats fields exist
                for stat_key in self.default_data["stats"]:
                    if stat_key not in loaded_data["stats"]:
                        loaded_data["stats"][stat_key] = self.default_data["stats"][stat_key]
                
                return loaded_data
            else:
                return self.default_data.copy()
        except Exception as e:
            print(f"Error loading achievements: {e}")
            return self.default_data.copy()
    
    def save_data(self):
        """Save achievements data to file"""
        try:
            with open(self.achievements_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Error saving achievements: {e}")
    
    def is_unlocked(self, achievement_id: str) -> bool:
        """Check if an achievement is unlocked"""
        return achievement_id in self.data["unlocked"]
    
    def unlock_achievement(self, achievement_id: str) -> bool:
        """Unlock an achievement. Returns True if newly unlocked."""
        if achievement_id not in ACHIEVEMENTS:
            return False
        
        if self.is_unlocked(achievement_id):
            return False
        
        self.data["unlocked"][achievement_id] = datetime.now().isoformat()
        self.newly_unlocked.append(achievement_id)
        self.save_data()
        return True
    
    def get_progress(self, achievement_id: str) -> tuple:
        """Get progress for an achievement. Returns (current, target)."""
        if achievement_id not in ACHIEVEMENTS:
            return (0, 0)
        
        achievement = ACHIEVEMENTS[achievement_id]
        target = achievement.get("target", 1)
        
        # Calculate current progress based on condition type
        condition_type = achievement.get("condition_type", "")
        
        if condition_type == "total_solves":
            current = self.data["stats"].get("total_solves", 0)
        elif condition_type == "solve_easy":
            current = self.data["stats"].get("easy_solves", 0)
        elif condition_type == "solve_medium":
            current = self.data["stats"].get("medium_solves", 0)
        elif condition_type == "solve_hard":
            current = self.data["stats"].get("hard_solves", 0)
        elif condition_type == "solve_limited_time":
            current = self.data["stats"].get("limited_time_wins", 0)
        elif condition_type == "solve_limited_moves":
            current = self.data["stats"].get("limited_moves_wins", 0)
        elif condition_type == "solve_daily":
            current = self.data["stats"].get("daily_solves", 0)
        elif condition_type == "scramble_count":
            current = self.data["stats"].get("scramble_count", 0)
        elif condition_type in ["time_under", "moves_under"]:
            # For these, we check if the condition was ever met
            current = 1 if self.is_unlocked(achievement_id) else 0
        else:
            current = self.data["progress"].get(achievement_id, 0)
        
        return (min(current, target), target)
    
    def get_progress_percentage(self, achievement_id: str) -> float:
        """Get progress as a percentage (0.0 to 1.0)"""
        current, target = self.get_progress(achievement_id)
        if target == 0:
            return 0.0
        return min(current / target, 1.0)
    
    def check_and_unlock(self) -> list:
        """Check all achievements and unlock any that are completed. Returns list of newly unlocked."""
        newly_unlocked = []
        
        for achievement_id, achievement in ACHIEVEMENTS.items():
            if self.is_unlocked(achievement_id):
                continue
            
            condition_type = achievement.get("condition_type", "")
            target = achievement.get("target", 1)
            
            unlocked = False
            
            if condition_type == "total_solves":
                unlocked = self.data["stats"].get("total_solves", 0) >= target
            elif condition_type == "solve_easy":
                unlocked = self.data["stats"].get("easy_solves", 0) >= target
            elif condition_type == "solve_medium":
                unlocked = self.data["stats"].get("medium_solves", 0) >= target
            elif condition_type == "solve_hard":
                unlocked = self.data["stats"].get("hard_solves", 0) >= target
            elif condition_type == "solve_limited_time":
                unlocked = self.data["stats"].get("limited_time_wins", 0) >= target
            elif condition_type == "solve_limited_moves":
                unlocked = self.data["stats"].get("limited_moves_wins", 0) >= target
            elif condition_type == "solve_daily":
                unlocked = self.data["stats"].get("daily_solves", 0) >= target
            elif condition_type == "scramble_count":
                unlocked = self.data["stats"].get("scramble_count", 0) >= target
            elif condition_type == "time_under":
                difficulty = achievement.get("difficulty", "hard")
                best_time = self.data["stats"].get("best_times", {}).get(difficulty)
                if best_time is not None:
                    unlocked = best_time < target
            elif condition_type == "moves_under":
                difficulty = achievement.get("difficulty", "easy")
                best_moves = self.data["stats"].get("best_moves", {}).get(difficulty)
                if best_moves is not None:
                    unlocked = best_moves <= target
            
            if unlocked:
                if self.unlock_achievement(achievement_id):
                    newly_unlocked.append(achievement_id)
        
        return newly_unlocked
    
    def record_solve(self, difficulty: str, solve_time: float, moves: int):
        """Record a solve and check for achievements"""
        stats = self.data["stats"]
        
        # Update total solves
        stats["total_solves"] = stats.get("total_solves", 0) + 1
        
        # Update difficulty-specific stats
        if difficulty == "easy":
            stats["easy_solves"] = stats.get("easy_solves", 0) + 1
        elif difficulty == "medium":
            stats["medium_solves"] = stats.get("medium_solves", 0) + 1
        elif difficulty == "hard":
            stats["hard_solves"] = stats.get("hard_solves", 0) + 1
        elif difficulty == "limited_time":
            stats["limited_time_wins"] = stats.get("limited_time_wins", 0) + 1
        elif difficulty == "limited_moves":
            stats["limited_moves_wins"] = stats.get("limited_moves_wins", 0) + 1
        elif difficulty == "daily_cube":
            stats["daily_solves"] = stats.get("daily_solves", 0) + 1
        
        # Update best times
        if "best_times" not in stats:
            stats["best_times"] = {}
        if difficulty not in stats["best_times"] or solve_time < stats["best_times"][difficulty]:
            stats["best_times"][difficulty] = solve_time
        
        # Update best moves
        if "best_moves" not in stats:
            stats["best_moves"] = {}
        if difficulty not in stats["best_moves"] or moves < stats["best_moves"][difficulty]:
            stats["best_moves"][difficulty] = moves
        
        self.save_data()
        
        # Check for newly unlocked achievements
        return self.check_and_unlock()
    
    def record_scramble(self):
        """Record a scramble action"""
        self.data["stats"]["scramble_count"] = self.data["stats"].get("scramble_count", 0) + 1
        self.save_data()
        self.check_and_unlock()
    
    def get_all_achievements(self) -> dict:
        """Get all achievements with their status"""
        result = {}
        for achievement_id, achievement in ACHIEVEMENTS.items():
            current, target = self.get_progress(achievement_id)
            result[achievement_id] = {
                **achievement,
                "unlocked": self.is_unlocked(achievement_id),
                "unlock_date": self.data["unlocked"].get(achievement_id),
                "progress": current,
                "target": target,
                "progress_percentage": self.get_progress_percentage(achievement_id)
            }
        return result
    
    def get_achievements_by_category(self) -> dict:
        """Get achievements organized by category"""
        categories = {}
        all_achievements = self.get_all_achievements()
        
        for achievement_id, achievement in all_achievements.items():
            category = achievement.get("category", "other")
            if category not in categories:
                categories[category] = []
            categories[category].append({
                "id": achievement_id,
                **achievement
            })
        
        return categories
    
    def get_unlocked_count(self) -> tuple:
        """Get count of unlocked achievements. Returns (unlocked, total)."""
        total = len(ACHIEVEMENTS)
        unlocked = len(self.data["unlocked"])
        return (unlocked, total)
    
    def get_newly_unlocked(self) -> list:
        """Get and clear list of newly unlocked achievements"""
        newly = self.newly_unlocked.copy()
        self.newly_unlocked.clear()
        return newly
    
    def get_stats(self) -> dict:
        """Get player statistics"""
        return self.data["stats"].copy()
    
    def reset_achievements(self):
        """Reset all achievements (for testing or user request)"""
        self.data = self.default_data.copy()
        self.save_data()
