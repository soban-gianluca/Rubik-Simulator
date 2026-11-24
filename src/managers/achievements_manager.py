import os
import copy
import json
from datetime import datetime, timedelta, timezone
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
    "solve_250": {
        "name": "Cube Veteran",
        "description": "Solve 250 cubes in any mode",
        "icon": "utils/icons/achievements/progression/solve-250.png",
        "category": "progression",
        "condition_type": "total_solves",
        "target": 250,
        "secret": False
    },
    "solve_500": {
        "name": "Living Legend",
        "description": "Solve 500 cubes in any mode",
        "icon": "utils/icons/achievements/progression/solve-500.png",
        "category": "progression",
        "condition_type": "total_solves",
        "target": 500,
        "secret": False
    },
    "hard_10": {
        "name": "Hardened",
        "description": "Solve 10 cubes on Hard difficulty",
        "icon": "utils/icons/achievements/progression/hard-10.png",
        "category": "progression",
        "condition_type": "solve_hard",
        "target": 10,
        "secret": False
    },
    
    # Speed achievements
    "speed_under_30s": {
        "name": "Lightning Fast",
        "description": "Solve an Easy cube in under 30 seconds",
        "icon": "utils/icons/achievements/speed/under-30sec.png",
        "category": "speed",
        "condition_type": "time_under",
        "time_threshold": 30,
        "difficulty": "easy",
        "secret": False
    },
    "speed_under_1min": {
        "name": "Speed Demon",
        "description": "Solve a Medium cube in under 1 minute",
        "icon": "utils/icons/achievements/speed/under-1min.png",
        "category": "speed",
        "condition_type": "time_under",
        "time_threshold": 60,
        "difficulty": "medium",
        "secret": False
    },
    "speed_under_2min": {
        "name": "Speedrunner",
        "description": "Solve a Hard cube in under 2 minutes",
        "icon": "utils/icons/achievements/speed/under-2min.png",
        "category": "speed",
        "condition_type": "time_under",
        "time_threshold": 120,
        "difficulty": "hard",
        "secret": False
    },
    "speed_easy_10s": {
        "name": "Blink",
        "description": "Solve an Easy cube in under 10 seconds",
        "icon": "utils/icons/achievements/speed/blink.png",
        "category": "speed",
        "condition_type": "time_under",
        "time_threshold": 10,
        "difficulty": "easy",
        "secret": False
    },
    "speed_medium_30s": {
        "name": "Quick Study",
        "description": "Solve a Medium cube in under 30 seconds",
        "icon": "utils/icons/achievements/speed/quick-study.png",
        "category": "speed",
        "condition_type": "time_under",
        "time_threshold": 30,
        "difficulty": "medium",
        "secret": False
    },
    "speed_hard_60s": {
        "name": "Iron Nerves",
        "description": "Solve a Hard cube in under 1 minute",
        "icon": "utils/icons/achievements/speed/iron-nerves.png",
        "category": "speed",
        "condition_type": "time_under",
        "time_threshold": 60,
        "difficulty": "hard",
        "secret": False
    },
    "fast_fingers": {
        "name": "Fast Fingers",
        "description": "Make 3 or more moves per second on a Medium or Hard solve",
        "icon": "utils/icons/achievements/speed/fast-fingers.png",
        "category": "speed",
        "condition_type": "solve_event",
        "event": "fast_fingers",
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
    "limited_time_10": {
        "name": "Marathoner",
        "description": "Win 10 Limited Time challenges",
        "icon": "utils/icons/achievements/challenge-mode/limited-time-10.png",
        "category": "challenge",
        "condition_type": "solve_limited_time",
        "target": 10,
        "secret": False
    },
    "limited_moves_10": {
        "name": "Accountant",
        "description": "Win 10 Limited Moves challenges",
        "icon": "utils/icons/achievements/challenge-mode/limited-moves-10.png",
        "category": "challenge",
        "condition_type": "solve_limited_moves",
        "target": 10,
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
    "daily_30": {
        "name": "Monthly Regular",
        "description": "Complete 30 Daily Cubes",
        "icon": "utils/icons/achievements/daily/daily-30.png",
        "category": "daily",
        "condition_type": "solve_daily",
        "target": 30,
        "secret": False
    },
    "daily_streak_7": {
        "name": "On a Roll",
        "description": "Complete the Daily Cube 7 days in a row",
        "icon": "utils/icons/achievements/daily/daily-streak-7.png",
        "category": "daily",
        "condition_type": "daily_streak",
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
        "moves_threshold": 10,
        "difficulty": "easy",
        "secret": False
    },
    "efficient_medium": {
        "name": "Optimal Solver",
        "description": "Solve a Medium cube in 20 moves or less",
        "icon": "utils/icons/achievements/efficiency/efficient-medium.png",
        "category": "efficiency",
        "condition_type": "moves_under",
        "moves_threshold": 20,
        "difficulty": "medium",
        "secret": False
    },
    "efficient_hard": {
        "name": "Master of Moves",
        "description": "Solve a Hard cube in 30 moves or less",
        "icon": "utils/icons/achievements/efficiency/efficient-hard.png",
        "category": "efficiency",
        "condition_type": "moves_under",
        "moves_threshold": 30,
        "difficulty": "hard",
        "secret": False
    },
    
    # Mastery achievements
    "all_rounder": {
        "name": "All-Rounder",
        "description": "Win at least once in every game mode",
        "icon": "utils/icons/achievements/mastery/all-rounder.png",
        "category": "mastery",
        "condition_type": "all_modes",
        "target": 6,
        "secret": False
    },
    "no_help_needed": {
        "name": "No Help Needed",
        "description": "Solve a Hard cube without opening a hint",
        "icon": "utils/icons/achievements/mastery/no-help-needed.png",
        "category": "mastery",
        "condition_type": "solve_event",
        "event": "no_hint_hard",
        "secret": False
    },
    "self_taught": {
        "name": "Self-Taught",
        "description": "Solve 25 cubes without opening a hint",
        "icon": "utils/icons/achievements/mastery/self-taught.png",
        "category": "mastery",
        "condition_type": "hintless_solves",
        "target": 25,
        "secret": False
    },

    # Secret achievements
    "secret_scrambler": {
        "name": "Chaos Theory",
        "description": "Scramble the cube 10 times",
        "icon": "utils/icons/achievements/secret/secret-scrambler.png",
        "category": "secret",
        "condition_type": "scramble_count",
        "target": 10,
        "secret": True
    },
    "night_owl": {
        "name": "Night Owl",
        "description": "Solve a cube between midnight and 4 AM",
        "icon": "utils/icons/achievements/secret/night-owl.png",
        "category": "secret",
        "condition_type": "solve_event",
        "event": "night_owl",
        "secret": True
    },
    "last_second": {
        "name": "Last Second",
        "description": "Win a Limited Time challenge with less than 3 seconds left",
        "icon": "utils/icons/achievements/secret/last-second.png",
        "category": "secret",
        "condition_type": "solve_event",
        "event": "last_second",
        "secret": True
    },
    "down_to_the_wire": {
        "name": "Down to the Wire",
        "description": "Win a Limited Moves challenge on the very last allowed move",
        "icon": "utils/icons/achievements/secret/down-to-the-wire.png",
        "category": "secret",
        "condition_type": "solve_event",
        "event": "last_move",
        "secret": True
    },
    "perfectionist": {
        "name": "Perfectionist",
        "description": "Solve an Easy cube in 5 moves or fewer",
        "icon": "utils/icons/achievements/secret/perfectionist.png",
        "category": "secret",
        "condition_type": "solve_event",
        "event": "perfect_easy",
        "secret": True
    },
    "indecisive": {
        "name": "Indecisive",
        "description": "Switch game mode 10 times without solving a cube",
        "icon": "utils/icons/achievements/secret/indecisive.png",
        "category": "secret",
        "condition_type": "mode_switches",
        "target": 10,
        "secret": True
    },
    "undo_addict": {
        "name": "Undo Addict",
        "description": "Undo 100 moves",
        "icon": "utils/icons/achievements/secret/undo-addict.png",
        "category": "secret",
        "condition_type": "undo_count",
        "target": 100,
        "secret": True
    },
    "tourist": {
        "name": "Tourist",
        "description": "Try every background style",
        "icon": "utils/icons/achievements/secret/tourist.png",
        "category": "secret",
        "condition_type": "backgrounds_tried",
        "target": 9,
        "secret": True
    },
    "marathon_session": {
        "name": "Marathon Session",
        "description": "Play for one hour in a single session",
        "icon": "utils/icons/achievements/secret/marathon-session.png",
        "category": "secret",
        "condition_type": "session_minutes",
        "target": 60,
        "secret": True
    },
    "comeback_kid": {
        "name": "Comeback Kid",
        "description": "Win a Limited Moves challenge after hitting the move limit and undoing",
        "icon": "utils/icons/achievements/secret/comeback-kid.png",
        "category": "secret",
        "condition_type": "solve_event",
        "event": "comeback",
        "secret": True
    },
}


# Condition types whose progress is a number read from the stats
STAT_CONDITIONS = {
    "total_solves": lambda s: s.get("total_solves", 0),
    "solve_easy": lambda s: s.get("easy_solves", 0),
    "solve_medium": lambda s: s.get("medium_solves", 0),
    "solve_hard": lambda s: s.get("hard_solves", 0),
    "solve_limited_time": lambda s: s.get("limited_time_wins", 0),
    "solve_limited_moves": lambda s: s.get("limited_moves_wins", 0),
    "solve_daily": lambda s: s.get("daily_solves", 0),
    "scramble_count": lambda s: s.get("scramble_count", 0),
    "daily_streak": lambda s: s.get("best_daily_streak", 0),
    "all_modes": lambda s: sum(1 for k in ("easy_solves", "medium_solves", "hard_solves", "limited_time_wins",
                                           "limited_moves_wins", "daily_solves") if s.get(k, 0) > 0),
    "hintless_solves": lambda s: s.get("hintless_solves", 0),
    "mode_switches": lambda s: s.get("mode_switches_since_solve", 0),
    "undo_count": lambda s: s.get("undo_count", 0),
    "backgrounds_tried": lambda s: len(s.get("backgrounds_tried", [])),
    "session_minutes": lambda s: s.get("longest_session_minutes", 0),
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
                "best_moves": {},  # difficulty: best_moves
                "hintless_solves": 0,
                "mode_switches_since_solve": 0,
                "undo_count": 0,
                "backgrounds_tried": [],
                "longest_session_minutes": 0,
                "last_daily_date": None,  # UTC date of the last Daily Cube solve
                "daily_streak": 0,
                "best_daily_streak": 0
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
                        loaded_data[key] = copy.deepcopy(self.default_data[key])
                
                # Ensure all stats fields exist
                for stat_key in self.default_data["stats"]:
                    if stat_key not in loaded_data["stats"]:
                        loaded_data["stats"][stat_key] = copy.deepcopy(self.default_data["stats"][stat_key])
                
                return loaded_data
            else:
                return copy.deepcopy(self.default_data)
        except Exception as e:
            print(f"Error loading achievements: {e}")
            return copy.deepcopy(self.default_data)
    
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
        
        if condition_type in STAT_CONDITIONS:
            current = STAT_CONDITIONS[condition_type](self.data["stats"])
        elif condition_type in ["time_under", "moves_under", "solve_event"]:
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
            
            if condition_type in STAT_CONDITIONS:
                unlocked = STAT_CONDITIONS[condition_type](self.data["stats"]) >= target
            elif condition_type == "time_under":
                difficulty = achievement.get("difficulty", "hard")
                time_threshold = achievement.get("time_threshold", target)  # Fallback to target for compatibility
                best_time = self.data["stats"].get("best_times", {}).get(difficulty)
                if best_time is not None:
                    unlocked = best_time < time_threshold
            elif condition_type == "moves_under":
                difficulty = achievement.get("difficulty", "easy")
                moves_threshold = achievement.get("moves_threshold", target)  # Fallback to target for compatibility
                best_moves = self.data["stats"].get("best_moves", {}).get(difficulty)
                if best_moves is not None:
                    unlocked = best_moves <= moves_threshold
            
            if unlocked:
                if self.unlock_achievement(achievement_id):
                    newly_unlocked.append(achievement_id)
        
        return newly_unlocked
    
    def record_solve(self, difficulty: str, solve_time: float, moves: int, context: dict = None):
        """Record a solve and check for achievements.

        context (from the game): hint_used, time_limit, move_limit, undo_at_limit.
        """
        stats = self.data["stats"]
        ctx = context or {}
        
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
            # The Daily Cube changes at midnight UTC
            today = datetime.now(timezone.utc).date()
            last = stats.get("last_daily_date")
            if last != today.isoformat():
                yesterday = (today - timedelta(days=1)).isoformat()
                stats["daily_streak"] = stats.get("daily_streak", 0) + 1 if last == yesterday else 1
                stats["last_daily_date"] = today.isoformat()
                stats["best_daily_streak"] = max(stats.get("best_daily_streak", 0), stats["daily_streak"])

        if not ctx.get("hint_used"):
            stats["hintless_solves"] = stats.get("hintless_solves", 0) + 1
        stats["mode_switches_since_solve"] = 0
        
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
        
        # Achievements decided by this solve alone
        tps = moves / solve_time if solve_time > 0 else 0
        time_limit, move_limit = ctx.get("time_limit"), ctx.get("move_limit")
        events = {
            "fast_fingers": difficulty in ("medium", "hard") and tps >= 3,
            "no_hint_hard": difficulty == "hard" and not ctx.get("hint_used"),
            "night_owl": datetime.now().hour < 4,
            "last_second": difficulty == "limited_time" and time_limit is not None and time_limit - solve_time < 3,
            "last_move": difficulty == "limited_moves" and move_limit is not None and moves >= move_limit,
            "perfect_easy": difficulty == "easy" and 0 < moves <= 5,
            "comeback": difficulty == "limited_moves" and bool(ctx.get("undo_at_limit")),
        }
        newly_unlocked = [aid for aid, a in ACHIEVEMENTS.items()
                          if a.get("condition_type") == "solve_event" and events.get(a.get("event"))
                          and self.unlock_achievement(aid)]

        self.save_data()

        # Check for newly unlocked achievements
        return newly_unlocked + self.check_and_unlock()

    def _add_to_stat(self, key, amount=1):
        self.data["stats"][key] = self.data["stats"].get(key, 0) + amount
        self.save_data()
        return self.check_and_unlock()

    def record_undo(self):
        """The player undid a move. Returns list of newly unlocked achievements."""
        return self._add_to_stat("undo_count")

    def record_mode_switch(self):
        """The player switched to another game mode. Returns list of newly unlocked achievements."""
        return self._add_to_stat("mode_switches_since_solve")

    def record_background(self, style):
        """The player picked a background style. Returns list of newly unlocked achievements."""
        tried = self.data["stats"].setdefault("backgrounds_tried", [])
        if style in tried:
            return []
        tried.append(style)
        self.save_data()
        return self.check_and_unlock()

    def record_session(self, minutes):
        """Length of the current session so far. Returns list of newly unlocked achievements."""
        if minutes <= self.data["stats"].get("longest_session_minutes", 0):
            return []
        self.data["stats"]["longest_session_minutes"] = minutes
        self.save_data()
        return self.check_and_unlock()

    def record_scramble(self):
        """Record a scramble action. Returns list of newly unlocked achievements."""
        self.data["stats"]["scramble_count"] = self.data["stats"].get("scramble_count", 0) + 1
        self.save_data()
        return self.check_and_unlock()
    
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
    
    def sync_with_personal_records(self, personal_best_manager):
        """Retroactively check and unlock achievements based on existing personal records."""
        from personal_best_manager import PersonalBestManager
        
        if not isinstance(personal_best_manager, PersonalBestManager):
            print("Invalid personal_best_manager provided")
            return []
        
        # Get all personal records
        records = personal_best_manager.records
        
        # Update stats from personal records
        stats = self.data["stats"]
        
        # Update total solves
        total_solves = 0
        for difficulty in ["easy", "medium", "hard", "limited_time", "limited_moves", "daily_cube"]:
            if difficulty in records:
                total_solves += records[difficulty].get("total_solves", 0)
        
        stats["total_solves"] = max(stats.get("total_solves", 0), total_solves)
        
        # Update difficulty-specific solves
        for difficulty in ["easy", "medium", "hard"]:
            if difficulty in records:
                key = f"{difficulty}_solves"
                stats[key] = max(stats.get(key, 0), records[difficulty].get("total_solves", 0))
        
        # Update challenge mode stats
        if "limited_time" in records:
            stats["limited_time_wins"] = max(
                stats.get("limited_time_wins", 0),
                records["limited_time"].get("wins", 0)
            )
        
        if "limited_moves" in records:
            stats["limited_moves_wins"] = max(
                stats.get("limited_moves_wins", 0),
                records["limited_moves"].get("wins", 0)
            )
        
        # Update daily solves
        if "daily_cube" in records:
            stats["daily_solves"] = max(
                stats.get("daily_solves", 0),
                records["daily_cube"].get("total_solves", 0)
            )
        
        # Update best times
        if "best_times" not in stats:
            stats["best_times"] = {}
        
        for difficulty in ["easy", "medium", "hard", "limited_time", "limited_moves", "daily_cube"]:
            if difficulty in records and records[difficulty].get("best_time") is not None:
                best_time = records[difficulty]["best_time"]
                if difficulty not in stats["best_times"] or best_time < stats["best_times"][difficulty]:
                    stats["best_times"][difficulty] = best_time
        
        # Update best moves
        if "best_moves" not in stats:
            stats["best_moves"] = {}
        
        for difficulty in ["easy", "medium", "hard", "limited_time", "limited_moves", "daily_cube"]:
            if difficulty in records and records[difficulty].get("best_moves") is not None:
                best_moves = records[difficulty]["best_moves"]
                if difficulty not in stats["best_moves"] or best_moves < stats["best_moves"][difficulty]:
                    stats["best_moves"][difficulty] = best_moves
        
        self.save_data()
        
        # Check for newly unlocked achievements
        return self.check_and_unlock()
    
    def reset_achievements(self):
        """Reset all achievements (for testing or user request)"""
        self.data = copy.deepcopy(self.default_data)
        self.save_data()
