import hashlib
import json
import os
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, List, Any

# Supabase configuration
SUPABASE_URL = "https://veqhopyjcwayewxtigfc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZlcWhvcHlqY3dheWV3eHRpZ2ZjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg0NDc1NzgsImV4cCI6MjA4NDAyMzU3OH0.xswKUcXLleLHiMXGfhEG8spstIp3Qw24jo-UXs2vmvo"


def generate_user_hash(user_id: str, created_at: str) -> str:
    """
    Generate a unique hash for a user based on their stable identifier.
    This hash won't change when username or region changes.
    
    Args:
        user_id: Stable unique identifier for the user
        created_at: When the user account was created
    """
    unique_string = f"{user_id}:{created_at}"
    return hashlib.sha256(unique_string.encode()).hexdigest()[:32]


class SupabaseManager:
    """Manages all Supabase operations for the global leaderboard."""
    
    def __init__(self):
        self.base_url = SUPABASE_URL
        self.api_key = SUPABASE_KEY
        self.headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        self._user_hash = None
        self._user_id = None
        self._is_configured = self._check_configuration()
    
    def _check_configuration(self) -> bool:
        """Check if Supabase is properly configured."""
        return (
            self.base_url != "https://your-project.supabase.co" and
            self.api_key != "your-anon-key" and
            "supabase.co" in self.base_url
        )
    
    def is_configured(self) -> bool:
        """Check if Supabase credentials are configured."""
        return self._is_configured
    
    def set_user_hash(self, user_id: str, created_at: str):
        """Set the user hash for the current user using stable identifiers."""
        self._user_hash = generate_user_hash(user_id, created_at)
        self._user_id = user_id
    
    def get_user_hash(self) -> Optional[str]:
        """Get the current user's hash."""
        return self._user_hash
    
    def _make_request(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> Optional[Any]:
        """Make an HTTP request to the Supabase REST API."""
        if not self._is_configured:
            return None
        
        url = f"{self.base_url}/rest/v1/{endpoint}"
        
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"
        
        try:
            if data:
                json_data = json.dumps(data).encode('utf-8')
            else:
                json_data = None
            
            request = urllib.request.Request(
                url,
                data=json_data,
                headers=self.headers,
                method=method
            )
            
            with urllib.request.urlopen(request, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                if response_data:
                    return json.loads(response_data)
                return []
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ""
            print(f"Supabase HTTP error {e.code}: {error_body}")
            return None
        except urllib.error.URLError as e:
            print(f"Supabase URL error: {e.reason}")
            return None
        except json.JSONDecodeError as e:
            print(f"Supabase JSON decode error: {e}")
            return None
        except Exception as e:
            print(f"Supabase request error: {e}")
            return None
    
    def submit_record(self, username: str, region: str, game_mode: str, 
                      best_time: float = None, best_moves: int = None, 
                      best_tps: float = None, total_solves: int = 0,
                      wins: int = 0, losses: int = 0) -> bool:
        """
        Submit or update a record to the global leaderboard.
        Uses upsert to update if exists or insert if new.
        """
        if not self._is_configured or not self._user_hash:
            return False
        
        data = {
            "username": username,
            "region": region,
            "game_mode": game_mode,
            "user_hash": self._user_hash,
            "user_id": self._user_id,
            "updated_at": datetime.now().isoformat()
        }
        
        # Only include non-None values
        if best_time is not None:
            data["best_time"] = round(best_time, 3)
        if best_moves is not None:
            data["best_moves"] = best_moves
        if best_tps is not None:
            data["best_tps"] = round(best_tps, 3)
        if total_solves > 0:
            data["total_solves"] = total_solves
        if wins > 0:
            data["wins"] = wins
        if losses > 0:
            data["losses"] = losses
        
        # Use upsert with on_conflict - specify the unique constraint columns
        headers = self.headers.copy()
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
        
        # Add on_conflict parameter to specify which columns to use for conflict detection
        url = f"{self.base_url}/rest/v1/leaderboard?on_conflict=user_hash,game_mode"
        
        try:
            json_data = json.dumps(data).encode('utf-8')
            request = urllib.request.Request(
                url,
                data=json_data,
                headers=headers,
                method="POST"
            )
            
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status in [200, 201]
                
        except Exception as e:
            print(f"Error submitting record: {e}")
            return False
    
    def update_user_profile(self, new_username: str, new_region: str) -> bool:
        """
        Update username and region for all existing records belonging to the current user.
        This should be called BEFORE changing the user_hash when a user edits their profile.
        
        Args:
            new_username: The new username to set
            new_region: The new region to set
        
        Returns:
            True if update successful, False otherwise
        """
        if not self._is_configured or not self._user_hash:
            print("Cannot update profile: Supabase not configured or no user hash")
            return False
        
        # Use PATCH to update all records matching the current user_hash
        url = f"{self.base_url}/rest/v1/leaderboard?user_hash=eq.{self._user_hash}"
        
        data = {
            "username": new_username,
            "region": new_region,
            "updated_at": datetime.now().isoformat()
        }
        
        try:
            headers = self.headers.copy()
            headers["Prefer"] = "return=representation"
            
            json_data = json.dumps(data).encode('utf-8')
            request = urllib.request.Request(
                url,
                data=json_data,
                headers=headers,
                method="PATCH"
            )
            
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status in [200, 204]
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ""
            print(f"HTTP error updating user profile: {e.code} - {error_body}")
            return False
        except Exception as e:
            print(f"Error updating user profile: {e}")
            return False
    
    def get_leaderboard(self, game_mode: str = None, region: str = None, 
                        sort_by: str = "best_time", limit: int = 50,
                        ascending: bool = True) -> List[Dict]:
        """
        Fetch leaderboard entries with optional filters.
        
        Args:
            game_mode: Filter by game mode (easy, medium, hard, limited_time, limited_moves)
            region: Filter by region
            sort_by: Column to sort by (best_time, best_moves, best_tps, total_solves)
            limit: Maximum number of entries to return
            ascending: Sort order (True for ascending, False for descending)
        
        Returns:
            List of leaderboard entries
        """
        if not self._is_configured:
            return []
        
        # Build query parameters
        params = {
            "select": "username,region,game_mode,best_time,best_moves,best_tps,total_solves,wins,losses,updated_at",
            "limit": str(limit)
        }
        
        # Add filters
        filters = []
        if game_mode:
            filters.append(f"game_mode=eq.{game_mode}")
        if region and region != "All Regions":
            filters.append(f"region=eq.{region}")
        
        # Only include entries with the sorted field populated
        if sort_by == "best_time":
            filters.append("best_time=not.is.null")
        elif sort_by == "best_moves":
            filters.append("best_moves=not.is.null")
        elif sort_by == "best_tps":
            filters.append("best_tps=not.is.null")
        
        # Build URL with filters
        url = f"{self.base_url}/rest/v1/leaderboard"
        
        # Add filters as query params
        query_parts = []
        for f in filters:
            query_parts.append(f)
        
        # Add ordering
        order_direction = "asc" if ascending else "desc"
        # For best_time and best_moves, lower is better (ascending)
        # For best_tps and total_solves, higher is better (descending by default)
        if sort_by in ["best_tps", "total_solves"]:
            order_direction = "desc" if ascending else "asc"
        
        query_parts.append(f"order={sort_by}.{order_direction}.nullslast")
        query_parts.append(f"limit={limit}")
        
        if query_parts:
            url = f"{url}?{'&'.join(query_parts)}"
        
        try:
            request = urllib.request.Request(url, headers=self.headers, method="GET")
            
            with urllib.request.urlopen(request, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                if response_data:
                    return (json.loads(response_data), False)  # (data, is_offline)
                return ([], False)
                
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            # Network-related errors (no connection, timeout, DNS failure, etc.)
            print(f"Network error fetching leaderboard: {e}")
            return ([], True)  # (empty data, is_offline=True)
        except Exception as e:
            print(f"Error fetching leaderboard: {e}")
            return ([], False)  # Other errors, not necessarily offline
    
    def get_user_ranks(self, game_mode: str = None) -> Dict[str, int]:
        """
        Get the current user's rank in the leaderboard for each category.
        Returns a dict with rank positions.
        """
        if not self._is_configured or not self._user_hash:
            return {}
        
        # This is a simplified implementation
        # A full implementation would use Supabase functions or multiple queries
        leaderboard = self.get_leaderboard(game_mode=game_mode, limit=1000)
        
        ranks = {
            "time_rank": None,
            "moves_rank": None,
            "tps_rank": None
        }
        
        # Sort by each metric and find user position
        for i, entry in enumerate(sorted(leaderboard, key=lambda x: x.get("best_time") or float('inf'))):
            if entry.get("user_hash") == self._user_hash:
                ranks["time_rank"] = i + 1
                break
        
        for i, entry in enumerate(sorted(leaderboard, key=lambda x: x.get("best_moves") or float('inf'))):
            if entry.get("user_hash") == self._user_hash:
                ranks["moves_rank"] = i + 1
                break
        
        for i, entry in enumerate(sorted(leaderboard, key=lambda x: -(x.get("best_tps") or 0))):
            if entry.get("user_hash") == self._user_hash:
                ranks["tps_rank"] = i + 1
                break
        
        return ranks
    
    def is_username_taken(self, username: str, exclude_user_hash: str = None) -> bool:
        """
        Check if a username is already in use by another user.
        
        Args:
            username: The username to check
            exclude_user_hash: Optional user hash to exclude (for editing own username)
        
        Returns:
            True if the username is taken by another user, False otherwise
        """
        if not self._is_configured:
            return False
        
        # Query the leaderboard for any entries with this username (case-insensitive)
        # Use ilike for case-insensitive matching
        encoded_username = urllib.parse.quote(username, safe='')
        url = f"{self.base_url}/rest/v1/leaderboard?username=ilike.{encoded_username}&select=user_hash,username&limit=1"
        
        try:
            request = urllib.request.Request(url, headers=self.headers, method="GET")
            
            with urllib.request.urlopen(request, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                if response_data:
                    results = json.loads(response_data)
                    if results:
                        # If we're excluding a user hash (editing own profile),
                        # check if the found user is different
                        if exclude_user_hash:
                            for result in results:
                                if result.get("user_hash") != exclude_user_hash:
                                    return True
                            return False
                        return True
                return False
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ""
            print(f"HTTP error checking username availability: {e.code} - {error_body}")
            return False
        except Exception as e:
            print(f"Error checking username availability: {e}")
            return False  # On error, allow the operation to proceed
    
    def sync_all_records(self, username: str, region: str, records: dict) -> bool:
        """
        Sync all local personal best records to the global leaderboard.
        
        Args:
            username: User's display name
            region: User's region
            records: Dict of all personal best records from PersonalBestManager
        
        Returns:
            True if all syncs successful, False otherwise
        """
        if not self._is_configured or not self._user_hash:
            return False
        
        success = True
        
        for game_mode, record in records.items():
            if game_mode == "freeplay":
                continue
            
            # Only submit if there are actual records
            if record.get("total_solves", 0) > 0 or record.get("best_time") is not None:
                result = self.submit_record(
                    username=username,
                    region=region,
                    game_mode=game_mode,
                    best_time=record.get("best_time"),
                    best_moves=record.get("best_moves"),
                    best_tps=record.get("best_tps"),
                    total_solves=record.get("total_solves", 0),
                    wins=record.get("wins", 0),
                    losses=record.get("losses", 0)
                )
                if not result:
                    success = False
        
        return success
    
    def get_today_date_utc(self) -> str:
        """Get today's date in UTC as YYYY-MM-DD string."""
        from datetime import timezone
        utc_now = datetime.now(timezone.utc)
        return utc_now.strftime("%Y-%m-%d")
    
    def submit_daily_record(self, username: str, region: str, 
                           solve_time: float, moves: int, tps: float) -> bool:
        """
        Submit a daily cube record. Each user can only have one record per day.
        Uses the current UTC date to identify the daily challenge.
        """
        if not self._is_configured or not self._user_hash:
            return False
        
        daily_date = self.get_today_date_utc()
        
        data = {
            "username": username,
            "region": region,
            "user_hash": self._user_hash,
            "user_id": self._user_id,
            "daily_date": daily_date,
            "solve_time": round(solve_time, 3),
            "moves": moves,
            "tps": round(tps, 3),
            "submitted_at": datetime.now().isoformat()
        }
        
        # Use upsert with on_conflict - one record per user per day
        headers = self.headers.copy()
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
        
        url = f"{self.base_url}/rest/v1/daily_leaderboard?on_conflict=user_hash,daily_date"
        
        try:
            json_data = json.dumps(data).encode('utf-8')
            request = urllib.request.Request(
                url,
                data=json_data,
                headers=headers,
                method="POST"
            )
            
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status in [200, 201]
                
        except Exception as e:
            print(f"Error submitting daily record: {e}")
            return False
    
    def get_daily_leaderboard(self, region: str = None, limit: int = 50) -> List[Dict]:
        """
        Fetch the daily leaderboard for today's date (UTC).
        
        Args:
            region: Optional filter by region
            limit: Maximum number of entries to return
        
        Returns:
            List of daily leaderboard entries sorted by solve_time (fastest first)
        """
        if not self._is_configured:
            return []
        
        daily_date = self.get_today_date_utc()
        
        # Build filters
        filters = [f"daily_date=eq.{daily_date}", "solve_time=not.is.null"]
        
        if region and region != "All Regions":
            filters.append(f"region=eq.{region}")
        
        # Build URL
        url = f"{self.base_url}/rest/v1/daily_leaderboard"
        query_parts = filters.copy()
        query_parts.append("order=solve_time.asc")
        query_parts.append(f"limit={limit}")
        
        url = f"{url}?{'&'.join(query_parts)}"
        
        try:
            request = urllib.request.Request(url, headers=self.headers, method="GET")
            
            with urllib.request.urlopen(request, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                if response_data:
                    return (json.loads(response_data), False)  # (data, is_offline)
                return ([], False)
                
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            # Network-related errors (no connection, timeout, DNS failure, etc.)
            print(f"Network error fetching daily leaderboard: {e}")
            return ([], True)  # (empty data, is_offline=True)
        except Exception as e:
            print(f"Error fetching daily leaderboard: {e}")
            return ([], False)  # Other errors, not necessarily offline
    
    def has_user_completed_daily(self) -> bool:
        """
        Check if the current user has already completed today's daily cube.
        
        Returns:
            True if user has a record for today, False otherwise
        """
        if not self._is_configured or not self._user_hash:
            return False
        
        daily_date = self.get_today_date_utc()
        
        url = f"{self.base_url}/rest/v1/daily_leaderboard?user_hash=eq.{self._user_hash}&daily_date=eq.{daily_date}&select=id&limit=1"
        
        try:
            request = urllib.request.Request(url, headers=self.headers, method="GET")
            
            with urllib.request.urlopen(request, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                if response_data:
                    results = json.loads(response_data)
                    return len(results) > 0
                return False
                
        except Exception as e:
            print(f"Error checking daily completion: {e}")
            return False
    
    def get_user_daily_record(self) -> Optional[Dict]:
        """
        Get the current user's record for today's daily cube.
        
        Returns:
            Dict with user's daily record or None if not found
        """
        if not self._is_configured or not self._user_hash:
            return None
        
        daily_date = self.get_today_date_utc()
        
        url = f"{self.base_url}/rest/v1/daily_leaderboard?user_hash=eq.{self._user_hash}&daily_date=eq.{daily_date}&limit=1"
        
        try:
            request = urllib.request.Request(url, headers=self.headers, method="GET")
            
            with urllib.request.urlopen(request, timeout=10) as response:
                response_data = response.read().decode('utf-8')
                if response_data:
                    results = json.loads(response_data)
                    return results[0] if results else None
                return None
                
        except Exception as e:
            print(f"Error fetching user daily record: {e}")
            return None


# Global instance for easy access
_supabase_manager = None


def get_supabase_manager() -> SupabaseManager:
    """Get the global SupabaseManager instance."""
    global _supabase_manager
    if _supabase_manager is None:
        _supabase_manager = SupabaseManager()
    return _supabase_manager
