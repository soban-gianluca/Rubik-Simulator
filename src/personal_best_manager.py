import os
import json
from datetime import datetime
from utils.path_helper import resource_path

def get_personal_best_path() -> str:
    """
    Path where personal best records are stored.
    Example: C:/Users/<User>/AppData/Roaming/RubiksCube/personal_bests.json
    """
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    user_dir = os.path.join(base, "RubiksCube")
    os.makedirs(user_dir, exist_ok=True)
    return os.path.join(user_dir, "personal_bests.json")

class PersonalBestManager:
    def __init__(self):
        self.records_file = get_personal_best_path()
        self.default_records = {
            "easy": {
                "best_time": None,
                "best_moves": None,
                "best_tps": None,
                "total_solves": 0,
                "average_time": None,
                "average_moves": None,
                "last_solve_date": None
            },
            "medium": {
                "best_time": None,
                "best_moves": None,
                "best_tps": None,
                "total_solves": 0,
                "average_time": None,
                "average_moves": None,
                "last_solve_date": None
            },
            "hard": {
                "best_time": None,
                "best_moves": None,
                "best_tps": None,
                "total_solves": 0,
                "average_time": None,
                "average_moves": None,
                "last_solve_date": None
            },
            "limited_time": {
                "best_time": None,
                "best_moves": None,
                "best_tps": None,
                "total_solves": 0,
                "average_time": None,
                "average_moves": None,
                "last_solve_date": None,
                "wins": 0,
                "losses": 0
            },
            "limited_moves": {
                "best_time": None,
                "best_moves": None,
                "best_tps": None,
                "total_solves": 0,
                "average_time": None,
                "average_moves": None,
                "last_solve_date": None,
                "wins": 0,
                "losses": 0
            }
        }
        self.records = self.load_records()
    
    def load_records(self) -> dict:
        """Load personal best records from file"""
        try:
            if os.path.exists(self.records_file):
                with open(self.records_file, "r", encoding="utf-8") as f:
                    loaded_records = json.load(f)
                
                # Ensure all difficulties exist with proper structure
                for difficulty in self.default_records:
                    if difficulty not in loaded_records:
                        loaded_records[difficulty] = self.default_records[difficulty].copy()
                    else:
                        # Ensure all fields exist for backward compatibility
                        for field in self.default_records[difficulty]:
                            if field not in loaded_records[difficulty]:
                                loaded_records[difficulty][field] = self.default_records[difficulty][field]
                
                return loaded_records
            else:
                return self.default_records.copy()
        except Exception as e:
            print(f"Error loading personal best records: {e}")
            return self.default_records.copy()
    
    def save_records(self):
        """Save personal best records to file"""
        try:
            with open(self.records_file, "w", encoding="utf-8") as f:
                json.dump(self.records, f, indent=4)
        except Exception as e:
            print(f"Error saving personal best records: {e}")
    
    def update_record(self, difficulty: str, solve_time: float, moves: int, tps: float = None):
        """Update personal best records for a difficulty"""
        if difficulty not in self.records:
            self.records[difficulty] = self.default_records["easy"].copy()
        
        record = self.records[difficulty]
        
        # Calculate TPS if not provided
        if tps is None and solve_time > 0:
            tps = moves / solve_time
        
        # Update best time
        if record["best_time"] is None or solve_time < record["best_time"]:
            record["best_time"] = solve_time
        
        # Update best moves (fewest moves)
        if record["best_moves"] is None or moves < record["best_moves"]:
            record["best_moves"] = moves
        
        # Update best TPS
        if record["best_tps"] is None or (tps and tps > record["best_tps"]):
            record["best_tps"] = tps
        
        # Update total solves and averages
        record["total_solves"] += 1
        
        # For limited_time and limited_moves, also record as a win
        if difficulty in ["limited_time", "limited_moves"]:
            if "wins" not in record:
                record["wins"] = 0
            record["wins"] += 1
        
        # Calculate running averages
        if record["average_time"] is None:
            record["average_time"] = solve_time
        else:
            # Simple running average (could be improved with weighted average)
            record["average_time"] = (record["average_time"] * (record["total_solves"] - 1) + solve_time) / record["total_solves"]
        
        if record["average_moves"] is None:
            record["average_moves"] = moves
        else:
            record["average_moves"] = (record["average_moves"] * (record["total_solves"] - 1) + moves) / record["total_solves"]
        
        # Update last solve date
        record["last_solve_date"] = datetime.now().isoformat()
        
        # Save to file
        self.save_records()
        
        return {
            "is_best_time": record["best_time"] == solve_time,
            "is_best_moves": record["best_moves"] == moves,
            "is_best_tps": record["best_tps"] == tps
        }
    
    def record_loss(self, difficulty: str, moves: int = 0, solve_time: float = 0):
        """Record a loss (game over) for challenge modes"""
        if difficulty not in self.records:
            self.records[difficulty] = self.default_records["easy"].copy()
        
        record = self.records[difficulty]
        
        # Only record losses for challenge modes
        if difficulty in ["limited_time", "limited_moves"]:
            if "losses" not in record:
                record["losses"] = 0
            record["losses"] += 1
            
            # Update last attempt date
            record["last_solve_date"] = datetime.now().isoformat()
            
            # Save to file
            self.save_records()
    
    def get_records(self, difficulty: str = None) -> dict:
        """Get personal best records for a specific difficulty or all difficulties"""
        if difficulty:
            return self.records.get(difficulty, self.default_records["easy"].copy())
        return self.records
    
    def get_best_time(self, difficulty: str) -> float:
        """Get the best time for a difficulty"""
        return self.records.get(difficulty, {}).get("best_time")
    
    def get_best_moves(self, difficulty: str) -> int:
        """Get the best moves for a difficulty"""
        return self.records.get(difficulty, {}).get("best_moves")
    
    def get_best_tps(self, difficulty: str) -> float:
        """Get the best TPS for a difficulty"""
        return self.records.get(difficulty, {}).get("best_tps")
    
    def get_total_solves(self, difficulty: str = None) -> int:
        """Get total solves for a difficulty or all difficulties"""
        if difficulty:
            return self.records.get(difficulty, {}).get("total_solves", 0)
        
        total = 0
        for diff_record in self.records.values():
            total += diff_record.get("total_solves", 0)
        return total
    
    def get_wins(self, difficulty: str) -> int:
        """Get total wins for a difficulty"""
        return self.records.get(difficulty, {}).get("wins", 0)
    
    def get_losses(self, difficulty: str) -> int:
        """Get total losses for a difficulty"""
        return self.records.get(difficulty, {}).get("losses", 0)
    
    def get_win_rate(self, difficulty: str) -> float:
        """Get win rate percentage for a difficulty"""
        wins = self.get_wins(difficulty)
        losses = self.get_losses(difficulty)
        total_games = wins + losses
        
        if total_games == 0:
            return 0.0
        
        return (wins / total_games) * 100
    
    def has_records(self, difficulty: str = None) -> bool:
        """Check if there are any records for a difficulty or any difficulty"""
        if difficulty:
            record = self.records.get(difficulty, {})
            return record.get("total_solves", 0) > 0
        
        for diff_record in self.records.values():
            if diff_record.get("total_solves", 0) > 0:
                return True
        return False
    
    def format_time(self, time_seconds: float) -> str:
        """Format time in seconds to a readable string"""
        if time_seconds is None:
            return "N/A"
        
        if time_seconds < 60:
            return f"{time_seconds:.2f}s"
        else:
            minutes = int(time_seconds // 60)
            seconds = time_seconds % 60
            return f"{minutes}:{seconds:05.2f}"
    
    def format_date(self, iso_date: str) -> str:
        """Format ISO date to a readable string"""
        if not iso_date:
            return "Never"
        
        try:
            dt = datetime.fromisoformat(iso_date)
            return dt.strftime("%Y-%m-%d %H:%M")
        except:
            return "Unknown"
    
    def reset_records(self, difficulty: str = None):
        """Reset records for a specific difficulty or all difficulties"""
        if difficulty:
            if difficulty in self.records:
                self.records[difficulty] = self.default_records["easy"].copy()
        else:
            self.records = self.default_records.copy()
        
        self.save_records()
