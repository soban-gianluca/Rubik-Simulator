import pygame
import sys
import time
import random
import os
import threading
import numpy as np
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from src.menu import Menu
from src.renderer import Renderer
from src.settings_manager import SettingsManager
from src.sound_manager import SoundManager
from src.results_window import ResultsWindow
from src.mouse_interaction import MouseInteraction
from src.game_menu_button import GameMenuButton
from src import display_manager
from src import hdr as hdr_output
from src import ui_style as ui
from src.personal_best_manager import PersonalBestManager
from src.achievements_manager import AchievementsManager, ACHIEVEMENTS
from src.supabase_manager import get_supabase_manager
from utils.path_helper import resource_path
from src.rubiks_cube import RubiksCube
from src.pykociemba.search import Search as KociembaSearch
from src.pykociemba.cubiecube import CubieCube, moveCube
from src.pykociemba.facecube import FaceCube

""" Puts the application in the taskbar with a custom icon on Windows."""
import ctypes
myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

class Game:
    def __init__(self, existing_screen=None):
        # Load settings
        self.settings = SettingsManager()
        self.show_fps = self.settings.settings.get("show_fps", False)

        # Resolve display mode, monitor and size against the connected monitors
        self.display_mode, self.display_index, size = display_manager.resolve(self.settings.settings)
        self.is_fullscreen = self.display_mode != "windowed"

        # Reuse the window created by the loading screen (same OpenGL context)
        if existing_screen:
            self.screen = existing_screen
        else:
            self.screen = display_manager.open_window(self.display_mode, self.display_index, size,
                                                      hdr=self._hdr_wanted(self.display_index))
        self.width, self.height = self.screen.get_size()
        ui.set_screen(self.width, self.height)
        self.hdr_presenter = None
        self._setup_hdr()
        pygame.display.set_caption("Rubik's Cube Simulator")
        self.clock = pygame.time.Clock()
        
        # Enable key repeat for text input (delay=300ms, interval=50ms)
        pygame.key.set_repeat(300, 50)
        
        # Initialize music
        self.playlist = [
            resource_path("utils/soundtrack/dark_bar.mp3"),
            resource_path("utils/soundtrack/lounge_layers.mp3"),
            resource_path("utils/soundtrack/midnight_simmetry.mp3"),
            resource_path("utils/soundtrack/the_fifth_color.mp3")
        ]
        self.current_song = random.randint(0, len(self.playlist) - 1)  # Start with random song
        self.MUSIC_END_EVENT = pygame.USEREVENT + 1
        self.MUSIC_RESTORE_EVENT = pygame.USEREVENT + 10  # Event for restoring music volume after ducking
        
        # --- Continue music from loading animation without restarting ---
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            # Set volume and end event for music
            music_volume = self.settings.get_music_volume() / 100
            master_volume = self.settings.get_master_volume() / 100
            pygame.mixer.music.set_volume(music_volume * master_volume)
            pygame.mixer.music.set_endevent(self.MUSIC_END_EVENT)
            # If not playing, start a random song (happens if loading music ended or didn't start)
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.load(self.playlist[self.current_song])
                pygame.mixer.music.play()
        except Exception as e:
            print(f"Background music error: {e}")
    
        try:
            icon = pygame.image.load(resource_path("utils/rubiksCube_Icon.ico"))
            pygame.display.set_icon(icon)
        except:
            print("Icon not found")

        # Initialize renderer
        self.renderer = Renderer(self.width, self.height)
        
        # Set initial camera position: 45° to the right horizontally and 45° up
        self.renderer.rotation_y = -45  # 45° to the right (azimuth)
        self.renderer.rotation_x = 35  # 45° up (elevation)
        
        # Initialize sound manager
        self.sound_manager = SoundManager()
        
        # Load audio settings from settings manager
        self.sound_manager.load_volumes_from_settings(self.settings)
        
        # Load audio settings into sound manager
        self.sound_manager.load_volumes_from_settings(self.settings)
        
        # Initialize mouse cube interaction system
        self.mouse_interaction = MouseInteraction(self.renderer)
        self.mouse_interaction.set_game_reference(self)
        
        # Initialize menu
        self.menu = Menu(self.width, self.height)
        self.menu.set_game_instance(self)
        
        # Initialize personal best manager
        self.personal_best_manager = PersonalBestManager()
        
        # Initialize achievements manager
        self.achievements_manager = AchievementsManager()
        
        # Initialize Supabase manager for global leaderboard
        self.supabase_manager = get_supabase_manager()
        
        # Connect managers for cloud sync
        self.personal_best_manager.set_supabase_manager(self.supabase_manager)
        self.personal_best_manager.set_user_manager(self.menu.user_manager)
        
        # Set the Supabase manager in the menu for leaderboard display
        self.menu.supabase_manager = self.supabase_manager
        
        # Set the personal best manager in the menu to use the same instance
        self.menu.personal_best_manager = self.personal_best_manager
        
        # Set the achievements manager in the menu to use the same instance
        self.menu.achievements_manager = self.achievements_manager
        
        # Load audio settings into menu's sound manager
        self.menu.sound_manager.load_volumes_from_settings(self.settings)
        
        # Set initial auto-rotation based on default difficulty
        default_difficulty = self.menu.get_selected_difficulty()
        self.set_auto_rotation_by_difficulty(default_difficulty)
        
        self.menu.toggle()  # Start with menu active
        
        # Initialize results window
        self.results_window = ResultsWindow(self.width, self.height)
        self.results_window.set_game_callback(self.handle_results_callback)
        self.results_window.set_sound_manager(self.sound_manager)
        self.results_window.set_personal_best_manager(self.personal_best_manager)
        self.results_window.set_achievements_manager(self.achievements_manager)
        
        # Initialize menu button
        self.menu_button = GameMenuButton(self.width, self.height)
        self.menu_button.set_game_callback(self.handle_overlay_callback)
        
        # Game state
        self.running = True
        self.auto_rotate = False  # Default to False, will be set based on difficulty
        self.game_started = False  # Track if game has started
        self.new_game_requested = False  # Track if user explicitly requested a new game
        self.difficulty_change_count = 0  # Track how many times difficulty has changed in this session
        
        # Control variables
        self.mouse_rotating = False
        self.mouse_cube_moving = False  # New variable for cube move detection
        self.prev_mouse_x = 0
        self.prev_mouse_y = 0
        self.rotation_sensitivity = 0.5
        self.vertical_sensitivity = 0.5
        self.debug_mode = False
        self.auto_rotation_speed = 0.2
        self.manual_rotation_speed = 180.0  # degrees per second for manual camera rotation
        
        # Movement system variables
        self.move_counter = 0
        self.start_time = None
        self.cube_solved = False
        
        # Challenge mode variables
        self.time_limit = None  # Time limit in seconds for limited time mode
        self.move_limit = None  # Move limit for limited moves mode
        self.game_over = False  # Track if game is over due to limits
        self.game_over_reason = None  # Reason for game over ("time_up", "moves_exceeded")
        
        # Solver cooldown to prevent duplicate triggers from key repeat
        self.solver_last_called = 0
        self.solver_cooldown = 0.5  # seconds
        self.solver_is_running = False  # Flag to prevent concurrent solver calls
        
        # Banner notification system
        self.banner_active = False
        self.banner_text = ""
        self.banner_start_time = 0
        self.banner_duration = 5.0  # 3 seconds total display time
        self.banner_fade_duration = 0.2  # 0.5 seconds for fade in/out
        self.banner_alpha = 0.0

        # Achievement notification queue (side banner)
        # Items are shown sequentially and become eligible after a short delay.
        self._achievement_notifications = []  # list[dict]: {id: str, ready_at: float}
        self._achievement_notification_active = False
        self._achievement_notification_id = None
        self._achievement_notification_start_time = 0.0
        self._achievement_notification_total_duration = 5.0
        self._achievement_notification_fade_duration = 0.25
        self._achievement_notification_alpha = 0.0
        self._achievement_icon_cache = {}  # (achievement_id, size) -> pygame.Surface|None
        
        # Hint system
        self.last_move_time = time.time()  # Track time of last move
        self.hint_inactivity_threshold = 30.0  # Show hint after 30 seconds of inactivity
        self.hint_banner_active = False  # Small hint banner visible
        self.hint_expanded = False  # Expanded hint popup visible
        self.hint_banner_alpha = 0.0
        self.hint_banner_fade_in_time = 0.3
        self.hint_banner_start_time = 0
        self.hint_current_suggestion = None  # Store the current hint suggestion
        self.hint_banner_rect = None  # Store rect for click detection
        self.hint_close_rect = None  # Store rect for close button detection
        self.hints_enabled = self.settings.get_hints_enabled()  # Load from settings
        
        # Visual hint system
        self.show_visual_hint = False  # Whether to show 3D arrow on cube
        self.visual_hint_face = None  # Face to highlight (R, L, U, D, F, B)
        self.visual_hint_clockwise = True  # Rotation direction
        self.visual_hint_pulse_time = 0  # For pulsing animation
        self.hint_moves_sequence = []  # Store the sequence of hint moves
        self.hint_moves_completed = 0  # Track how many hint moves completed
        
        # Solution caching for hints (prevent recomputation)
        self._cached_solution_moves = None
        self._solution_computing = False
        self._solution_lock = threading.Lock()
        
        # Load hint icons
        self._load_hint_icons()
         
        print("\nMovement Controls:")
        print("  Ctrl + B: Debug mode")
        print("  G: Get all hints")
        print("  Z: Undo last move")
        print("  X: Scramble cube (freeplay mode only)")

    def set_auto_rotation_by_difficulty(self, difficulty):
        """Set auto-rotation based on difficulty level"""
        # Auto-rotation disabled for all difficulties including freeplay
        self.auto_rotate = False

    def request_new_game(self):
        """Request a new game to be started (triggers scrambling)"""
        self.new_game_requested = True
        self.game_started = False  # Reset game state for new game
        self.move_counter = 0  # Reset move counter
        self.start_time = None  # Reset timer
        self.cube_solved = False  # Reset solved state
        
        # Reset challenge mode variables
        self.time_limit = None
        self.move_limit = None
        self.game_over = False
        self.game_over_reason = None
        
        # Reset hint and visual hint system
        self.hint_banner_active = False
        self.hint_expanded = False
        self.hint_banner_alpha = 0.0
        self.hint_current_suggestion = None
        self.show_visual_hint = False
        self.visual_hint_face = None
        self.hint_moves_sequence = []
        self.hint_moves_completed = 0
        self.last_move_time = time.time()
        with self._solution_lock:
            self._cached_solution_moves = None
        
        # Set limits based on current difficulty
        current_difficulty = self.menu.get_selected_difficulty()
        game_mode_config = self.menu.get_game_mode_config(current_difficulty)
        
        if "time_limit" in game_mode_config:
            self.time_limit = game_mode_config["time_limit"]
            self.debug_print(f"Time limit set to {self.time_limit} seconds")
        
        if "move_limit" in game_mode_config:
            self.move_limit = game_mode_config["move_limit"]
            self.debug_print(f"Move limit set to {self.move_limit} moves")

    def increment_difficulty_change_count(self):
        """Increment the difficulty change count"""
        self.difficulty_change_count += 1
        self.debug_print(f"Difficulty change count: {self.difficulty_change_count}")

    def get_difficulty_change_count(self):
        """Get the current difficulty change count"""
        return self.difficulty_change_count

    def has_game_progress(self):
        """Check if the current game has any progress (moves made)"""
        return self.move_counter > 0 or self.start_time is not None

    def debug_print(self, message):
        if self.debug_mode:
            print(message)

    def _cube_to_facelets(self):
        """Convert current `RubiksCube` state to a facelet string for pykociemba.

        CRITICAL FIX: The scramble includes slice moves (M, E, S) which move centers.
        We must map based on WHICH PHYSICAL FACE each sticker is on, not the color value.
        """
        c = self.renderer.rubiks_cube
        
        # Read the center color of each physical face to determine orientation
        center_top = int(c.faces['top'][1, 1])
        center_right = int(c.faces['right'][1, 1])
        center_front = int(c.faces['front'][1, 1])
        center_bottom = int(c.faces['bottom'][1, 1])
        center_left = int(c.faces['left'][1, 1])
        center_back = int(c.faces['back'][1, 1])
        
        # Create color mapping based on current center positions
        # Map: color_value -> which face letter it represents
        color_to_face = {}
        color_to_face[center_top] = 'U'
        color_to_face[center_right] = 'R'
        color_to_face[center_front] = 'F'
        color_to_face[center_bottom] = 'D'
        color_to_face[center_left] = 'L'
        color_to_face[center_back] = 'B'
        
        result = []
        
        # Read each face in the order expected by pykociemba: U, R, F, D, L, B
        for face_name in ['top', 'right', 'front', 'bottom', 'left', 'back']:
            for row in range(3):
                for col in range(3):
                    color_idx = int(c.faces[face_name][row, col])
                    result.append(color_to_face[color_idx])
        
        facelet_str = ''.join(result)
        return facelet_str

    def suggest_next_move_threaded(self):
        """Wrapper to call suggest_next_move in a background thread safely."""
        try:
            self.solver_is_running = True
            self.suggest_next_move()
        finally:
            self.solver_is_running = False

    def suggest_next_move(self):
        """Compute a full solution using pykociemba and print the next move to terminal.

        This validates the solution using pykociemba's own move semantics to ensure
        the suggestion is correct and will actually solve the cube.
        """
        try:
            # Don't run during animations or scrambles
            if getattr(self.renderer, 'is_animating', False) or getattr(self, 'is_scrambling', False):
                print("Please wait for animations/scramble to finish before requesting a suggestion.")
                return None

            # Build facelet string from current cube state
            facelets = self._cube_to_facelets()

            # Diagnostic: verify it's a solved cube if we think it should be
            if self.renderer.rubiks_cube.is_solved():
                expected_solved = "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"
                if facelets != expected_solved:
                    print(f"WARNING: Cube reports as solved but facelet string doesn't match!")
                    print(f"Expected: {expected_solved}")
                    print(f"Got:      {facelets}")

            # Call solver
            solver = KociembaSearch()
            solution = solver.solution(facelets, maxDepth=21, timeOut=5, useSeparator=False)

            if solution.startswith('Error'):
                print(f"Solver error: {solution}")
                print(f"Facelet string: {facelets}")
                print(f"Cube is_solved: {self.renderer.rubiks_cube.is_solved()}")
                return None

            solution = solution.strip()
            if not solution:
                print("Cube already solved — no moves needed.")
                return None
            try:
                # Convert current cube state to CubieCube using pykociemba's parser
                test_cubie = FaceCube(facelets).toCubieCube()

                # Apply each move using pykociemba's moveCube table (not RubiksCube.execute_move!)
                # moveCube indices: 0=U, 1=R, 2=F, 3=D, 4=L, 5=B
                move_map = {
                    'U': 0, "U'": 0, 'U2': 0,
                    'R': 1, "R'": 1, 'R2': 1,
                    'F': 2, "F'": 2, 'F2': 2,
                    'D': 3, "D'": 3, 'D2': 3,
                    'L': 4, "L'": 4, 'L2': 4,
                    'B': 5, "B'": 5, 'B2': 5,
                }

                for move_str in solution.split():
                    if move_str not in move_map:
                        print(f"Unknown move in solution: {move_str}")
                        return None

                    move_idx = move_map[move_str]

                    # Apply the move 1, 2, or 3 times depending on notation
                    if move_str.endswith('2'):
                        test_cubie.multiply(moveCube[move_idx])
                        test_cubie.multiply(moveCube[move_idx])
                    elif move_str.endswith("'"):
                        # Prime = 3 times clockwise
                        test_cubie.multiply(moveCube[move_idx])
                        test_cubie.multiply(moveCube[move_idx])
                        test_cubie.multiply(moveCube[move_idx])
                    else:
                        # Normal = 1 time
                        test_cubie.multiply(moveCube[move_idx])

                # Check if solved by converting back to facelet and checking all same
                result_fc = test_cubie.toFaceCube()
                result_str = result_fc.to_String()

                # A solved cube has all U's in positions 0-8, all R's in 9-17, etc.
                is_solved = (
                    all(result_str[i] == 'U' for i in range(9)) and
                    all(result_str[i] == 'R' for i in range(9, 18)) and
                    all(result_str[i] == 'F' for i in range(18, 27)) and
                    all(result_str[i] == 'D' for i in range(27, 36)) and
                    all(result_str[i] == 'L' for i in range(36, 45)) and
                    all(result_str[i] == 'B' for i in range(45, 54))
                )

                if not is_solved:
                    print(f"Solver produced solution that doesn't solve the cube when validated with pykociemba moves. Rejecting.")
                    print(f"Input facelets: {facelets}")
                    print(f"Solution: {solution}")
                    print(f"Result after applying: {result_str}")
                    return None

            except Exception as e:
                print(f"Error validating solution: {e}")
                return None

            # First token (space separated) is the next move
            first_move = solution.split()[0]
            print(f"Suggested next move: {first_move}  (Full solution: {solution})")
            return first_move
        except Exception as e:
            print(f"Error computing suggestion: {e}")
            return None

    def show_banner(self, message):
        """Show a notification banner with fade in/out animation"""
        self.banner_text = message
        self.banner_active = True
        self.banner_start_time = time.time()
        self.banner_alpha = 0.0

    def enqueue_achievement_notifications(self, achievement_ids, delay_seconds=0.0):
        """Queue achievement notifications.

        Notifications are shown one at a time. If `delay_seconds` is provided,
        each item becomes eligible after that delay from the moment it was queued.
        """
        if not achievement_ids:
            return

        now = time.time()
        delay = float(delay_seconds)
        for achievement_id in achievement_ids:
            if not achievement_id:
                continue
            self._achievement_notifications.append({
                'id': achievement_id,
                'ready_at': now + delay,
            })

    def update_achievement_notifications(self):
        """Advance queued achievement notifications (delayed + sequential)."""
        now = time.time()

        if self._achievement_notification_active:
            elapsed = now - self._achievement_notification_start_time
            fade = self._achievement_notification_fade_duration
            total = self._achievement_notification_total_duration

            if elapsed < 0:
                self._achievement_notification_alpha = 0.0
            elif elapsed < fade:
                self._achievement_notification_alpha = elapsed / fade
            elif elapsed < total - fade:
                self._achievement_notification_alpha = 1.0
            elif elapsed < total:
                self._achievement_notification_alpha = 1.0 - ((elapsed - (total - fade)) / fade)
            else:
                self._achievement_notification_active = False
                self._achievement_notification_id = None
                self._achievement_notification_alpha = 0.0

        # Start next notification if none active
        if (not self._achievement_notification_active) and self._achievement_notifications:
            next_item = self._achievement_notifications[0]
            if now >= float(next_item.get('ready_at', 0.0)):
                self._achievement_notifications.pop(0)
                self._achievement_notification_id = next_item.get('id')
                self._achievement_notification_active = True
                self._achievement_notification_start_time = now
                self._achievement_notification_alpha = 0.0

                # Play SFX when the banner actually appears
                if hasattr(self, 'sound_manager') and self.sound_manager:
                    self.sound_manager.play('achievement')

    def _get_achievement_icon(self, achievement_id, size):
        """Load & cache an achievement icon Surface scaled to (size, size)."""
        key = (achievement_id, int(size))
        if key in self._achievement_icon_cache:
            return self._achievement_icon_cache[key]

        achievement = ACHIEVEMENTS.get(achievement_id, {})
        icon_path = achievement.get('icon', '')
        if not icon_path:
            self._achievement_icon_cache[key] = None
            return None

        full_icon_path = resource_path(icon_path)
        if not os.path.exists(full_icon_path):
            self._achievement_icon_cache[key] = None
            return None

        try:
            icon_img = pygame.image.load(full_icon_path).convert_alpha()
            icon_img = pygame.transform.smoothscale(icon_img, (int(size), int(size)))
            self._achievement_icon_cache[key] = icon_img
            return icon_img
        except Exception:
            self._achievement_icon_cache[key] = None
            return None

    def _render_achievement_notification_opengl(self):
        """Achievement toast at the top center"""
        if (not self._achievement_notification_active) or self._achievement_notification_alpha <= 0:
            return
        achievement_id = self._achievement_notification_id
        achievement = ACHIEVEMENTS.get(achievement_id, {}) if achievement_id else {}
        try:
            a = float(self._achievement_notification_alpha)
            pad = ui.px(18)
            icon_size = ui.px(64)
            caption_f = ui.body_font(ui.SIZE_CAPTION, bold=True)
            name_f = ui.body_font(ui.SIZE_BODY, bold=True)
            name = achievement.get('name', 'Unknown achievement')
            text_w = max(caption_f.size("Achievement unlocked")[0], name_f.size(name)[0])
            width = min(self.width - ui.px(48), pad * 2 + icon_size + ui.px(18) + text_w + ui.px(8))
            height = icon_size + pad * 2

            surf = pygame.Surface((width, height), pygame.SRCALPHA)
            ui.fill_rect(surf, (*ui.SURFACE, 248), surf.get_rect(), ui.radius(14))
            ui.fill_rect(surf, ui.ACCENT, surf.get_rect(), ui.radius(14), width=max(1, ui.px(2)))
            icon = self._get_achievement_icon(achievement_id, icon_size)
            if icon is not None:
                surf.blit(icon, (pad, pad))
            else:
                ui.cube_mark(surf, (pad + icon_size // 2, pad + icon_size // 2), icon_size // 2, body=ui.SURFACE)
            tx = pad + icon_size + ui.px(18)
            ui.draw_text(surf, "Achievement unlocked", caption_f, ui.ACCENT, (tx, height // 2 - ui.px(2)), "bottomleft")
            ui.draw_text(surf, ui.ellipsize(name, name_f, width - tx - pad), name_f, ui.TEXT,
                         (tx, height // 2 + ui.px(2)), "topleft")
            surf.set_alpha(int(255 * a))
            y = self._hud_margin() + int((1.0 - a) * -ui.px(16))
            self._blit_gl(surf, (self.width - width) // 2, max(0, y))
        except Exception as e:
            if self.debug_mode:
                print(f"Achievement banner render error: {e}")

    def update_banner(self):
        """Update banner animation and visibility"""
        if not self.banner_active:
            return

        current_time = time.time()
        elapsed = current_time - self.banner_start_time

        if elapsed < self.banner_fade_duration:
            # Fade in
            self.banner_alpha = elapsed / self.banner_fade_duration
        elif elapsed < self.banner_duration - self.banner_fade_duration:
            # Full visibility
            self.banner_alpha = 1.0
        elif elapsed < self.banner_duration:
            # Fade out
            fade_out_elapsed = elapsed - (self.banner_duration - self.banner_fade_duration)
            self.banner_alpha = 1.0 - (fade_out_elapsed / self.banner_fade_duration)
        else:
            # Banner finished
            self.banner_active = False
            self.banner_alpha = 0.0

    def _load_hint_icons(self):
        """Load hint and close button icons"""
        try:
            # Load hint icon
            self.hint_icon = pygame.image.load(resource_path("utils/icons/hint.png"))
            self.hint_icon = pygame.transform.smoothscale(self.hint_icon, (32, 32))
        except Exception as e:
            print(f"Could not load hint icon: {e}")
            self.hint_icon = None
        
        try:
            # Load close icon
            self.close_icon = pygame.image.load(resource_path("utils/icons/close.png"))
            self.close_icon = pygame.transform.smoothscale(self.close_icon, (24, 24))
        except Exception as e:
            print(f"Could not load close icon: {e}")
            self.close_icon = None

    def reset_hint_timer(self, hint_move_matched=False):
        """Reset the hint inactivity timer - called when user makes a move
        
        Args:
            hint_move_matched: True if the move matched the expected hint move
        """
        self.last_move_time = time.time()
        
        # Clear cached solution since cube state changed
        with self._solution_lock:
            self._cached_solution_moves = None
        
        # Hide hint banner if visible
        if self.hint_banner_active and not self.hint_expanded:
            self.hint_banner_active = False
            self.hint_banner_alpha = 0.0
        
        # Update visual hint only if the move matched the hint suggestion
        if self.hint_expanded and len(self.hint_moves_sequence) > 0 and hint_move_matched:
            self.hint_moves_completed += 1
            self.debug_print(f"Hint moves completed: {self.hint_moves_completed}/{len(self.hint_moves_sequence)}")
            
            # Check if all hint moves are completed
            if self.hint_moves_completed >= len(self.hint_moves_sequence):
                self.debug_print("All hint moves completed! Closing popup.")
                self.close_hint_popup()
            else:
                # Update to show next move
                self._enable_visual_hint()

    def update_hint_system(self):
        """Update the hint system - check for inactivity and manage hint display"""
        if not self.hints_enabled:
            return
        
        # Don't show hints in menu, results screen, during scrambling, or when cube is solved
        if (self.menu.is_active() or 
            self.results_window.active or 
            (hasattr(self, 'is_scrambling') and self.is_scrambling) or 
            self.cube_solved or
            self.game_over or
            not self.game_started):
            return
        
        # Don't show hints in freeplay, limited_time, or limited_moves modes
        current_difficulty = self.menu.get_selected_difficulty()
        if current_difficulty in ["freeplay", "limited_time", "limited_moves"]:
            return
        
        current_time = time.time()
        
        # Check for inactivity
        if not self.hint_banner_active and not self.hint_expanded:
            time_since_last_move = current_time - self.last_move_time
            if time_since_last_move >= self.hint_inactivity_threshold:
                # Show hint banner
                self.hint_banner_active = True
                self.hint_banner_start_time = current_time
                self.hint_banner_alpha = 0.0
                self.debug_print("Showing hint banner due to inactivity")
                
                # Play hint sound effect
                self.sound_manager.play("hint")
                
                # Start precomputing solution in background
                self._precompute_solution()
        
        # Update hint banner fade-in animation
        if self.hint_banner_active and not self.hint_expanded:
            elapsed = current_time - self.hint_banner_start_time
            if elapsed < self.hint_banner_fade_in_time:
                self.hint_banner_alpha = elapsed / self.hint_banner_fade_in_time
            else:
                self.hint_banner_alpha = 1.0
        
        # Update expanded hint if solution becomes available
        if self.hint_expanded and self.hint_current_suggestion and "Analyzing the cube" in self.hint_current_suggestion:
            with self._solution_lock:
                if self._cached_solution_moves and not self._solution_computing:
                    # Solution is now available, update the hint
                    solution_moves = self._cached_solution_moves
                    
                    # Expand moves to handle double moves
                    expanded_moves = []
                    for move in solution_moves:
                        if '2' in move:
                            base_move = move.replace('2', '')
                            expanded_moves.append(base_move)
                            expanded_moves.append(base_move)
                        else:
                            expanded_moves.append(move)
                        if len(expanded_moves) >= 3:
                            break
                    
                    self.hint_moves_sequence = expanded_moves[:3]
                    self.hint_moves_completed = 0
                    self.hint_current_suggestion = self._format_hint_suggestion(solution_moves)
                    
                    # Enable visual hint now that we have moves
                    if self.hint_moves_sequence:
                        self._enable_visual_hint()
                    
                    self.debug_print("Hint updated with computed solution")
    
    def _precompute_solution(self):
        """Precompute the solution in a background thread"""
        with self._solution_lock:
            # Don't start multiple computation threads
            if self._solution_computing:
                return
            self._solution_computing = True
        
        def compute():
            try:
                # Compute solution
                solution = self._get_solution_moves()
                with self._solution_lock:
                    self._cached_solution_moves = solution
                    self._solution_computing = False
                self.debug_print("Solution precomputed in background")
            except Exception as e:
                self.debug_print(f"Error precomputing solution: {e}")
                with self._solution_lock:
                    self._solution_computing = False
        
        # Start background thread
        thread = threading.Thread(target=compute, daemon=True)
        thread.start()

    def show_hint_expanded(self):
        """Show the expanded hint popup with algorithm suggestion"""
        self.hint_expanded = True
        self.hint_banner_active = False
        
        # Use cached solution (should be ready from background precomputation)
        # If not ready yet, show loading message
        with self._solution_lock:
            solution_moves = self._cached_solution_moves
            is_computing = self._solution_computing
        
        if solution_moves:
            # Determine number of hint moves based on difficulty
            current_difficulty = self.menu.get_selected_difficulty()
            hint_move_counts = {
                "easy": 1,
                "medium": 2,
                "hard": 5
            }
            max_hint_moves = hint_move_counts.get(current_difficulty, 3)  # Default to 3 if not found
            
            # Expand moves to handle double moves (B2 -> B, B)
            expanded_moves = []
            for move in solution_moves:
                if '2' in move:
                    # Double move - add it twice
                    base_move = move.replace('2', '')
                    expanded_moves.append(base_move)
                    expanded_moves.append(base_move)
                else:
                    expanded_moves.append(move)
                
                # Stop after we have enough moves
                if len(expanded_moves) >= max_hint_moves:
                    break
            
            self.hint_moves_sequence = expanded_moves[:max_hint_moves]  # Store hint moves based on difficulty
            self.hint_moves_completed = 0
            
            # Get the hint suggestion with cached solution
            self.hint_current_suggestion = self._format_hint_suggestion(solution_moves)
        elif is_computing:
            # Still computing in background
            self.hint_moves_sequence = []
            self.hint_moves_completed = 0
            self.hint_current_suggestion = "Analyzing the cube\nOne moment while the solver works."
        else:
            # No solution available
            self.hint_moves_sequence = []
            self.hint_moves_completed = 0
            self.hint_current_suggestion = "Try analyzing the cube pattern..."
        
        self.debug_print(f"Showing expanded hint: {self.hint_current_suggestion}")
        
        # Enable visual hint with first move (only if we have moves)
        if self.hint_moves_sequence:
            self._enable_visual_hint()

    def close_hint_popup(self):
        """Close the hint popup and reset the timer"""
        self.hint_expanded = False
        self.hint_banner_active = False
        self.hint_banner_alpha = 0.0
        self.hint_current_suggestion = None
        self.last_move_time = time.time()  # Reset timer so hint doesn't immediately reappear
        
        # Disable visual hint and clear tracking
        self.show_visual_hint = False
        self.visual_hint_face = None
        self.hint_moves_sequence = []
        self.hint_moves_completed = 0
        
        # Clear cached solution since hint is closed
        with self._solution_lock:
            self._cached_solution_moves = None

    def _format_hint_suggestion(self, solution_moves):
        """Format hint suggestion from pre-computed solution moves"""
        import random
        
        # Phrases to make hints more engaging
        hint_phrases = [
            "Have you tried using",
            "Maybe you should try",
            "Consider performing",
            "How about doing",
            "Try executing",
            "You could use",
            "Perhaps attempt"
        ]
        
        # Format the solution moves
        if solution_moves:
            try:
                # Determine number of hint moves based on difficulty
                current_difficulty = self.menu.get_selected_difficulty()
                hint_move_counts = {
                    "easy": 1,
                    "medium": 2,
                    "hard": 5
                }
                max_hint_moves = hint_move_counts.get(current_difficulty, 3)  # Default to 3 if not found
                
                # Get first few moves for display based on difficulty
                display_moves = []
                move_count = 0
                
                for move in solution_moves:
                    display_moves.append(move)
                    # Count actual move steps (B2 counts as 2 steps)
                    if '2' in move:
                        move_count += 2
                    else:
                        move_count += 1
                    
                    # Stop when we have enough moves based on difficulty
                    if move_count >= max_hint_moves:
                        break
                
                # Limit display moves based on difficulty
                display_moves = display_moves[:max_hint_moves]
                moves_str = " ".join(display_moves)
                
                phrase = random.choice(hint_phrases)
                
                # Add explanation about the visual arrow
                first_move = display_moves[0]
                direction = "clockwise" if "'" not in first_move else "counterclockwise"
                face_name = self._get_face_name(first_move[0])
                
                return f"{phrase} these moves:\n{moves_str}\n\nWatch the {face_name} face. The yellow arrow shows a {direction} turn."
            except Exception as e:
                self.debug_print(f"Error formatting hint: {e}")
        
        # Fallback generic hints
        generic_hints = [
            "Try solving the white cross first",
            "Focus on the first layer corners",
            "Work on the middle layer edges",
            "Look for patterns in the last layer",
            "Try the R U R' U' algorithm",
            "Consider rotating the cube to see it from different angles"
        ]
        return random.choice(generic_hints)
    
    def _enable_visual_hint(self):
        """Enable visual hint by parsing the current move from the hint sequence"""
        try:
            # Use stored hint sequence if available
            if len(self.hint_moves_sequence) > 0 and self.hint_moves_completed < len(self.hint_moves_sequence):
                current_move = self.hint_moves_sequence[self.hint_moves_completed]
                
                # Parse the move (e.g., "R", "L'", "U2", etc.)
                face = current_move[0]  # First character is the face
                clockwise = "'" not in current_move  # Prime moves are counterclockwise
                
                # Enable visual hint
                self.show_visual_hint = True
                self.visual_hint_face = face
                self.visual_hint_clockwise = clockwise
                self.visual_hint_pulse_time = time.time()
                
                self.debug_print(f"Visual hint enabled: {current_move} - {face} {'clockwise' if clockwise else 'counterclockwise'}")
            else:
                self.show_visual_hint = False
        except Exception as e:
            self.debug_print(f"Error enabling visual hint: {e}")
            self.show_visual_hint = False
    
    def _get_face_name(self, face_letter):
        """Convert face letter to readable name"""
        face_names = {
            'R': 'Right',
            'L': 'Left',
            'U': 'Top',
            'D': 'Bottom',
            'F': 'Front',
            'B': 'Back',
            'M': 'Middle',
            'E': 'Equatorial',
            'S': 'Standing'
        }
        return face_names.get(face_letter, face_letter)
    
    def _get_solution_moves(self):
        """Get the solution moves from the solver as a list"""
        try:
            # Don't run during animations or scrambles
            if getattr(self.renderer, 'is_animating', False) or getattr(self, 'is_scrambling', False):
                return None

            # Build facelet string from current cube state
            facelets = self._cube_to_facelets()

            # Call solver
            solver = KociembaSearch()
            solution = solver.solution(facelets, maxDepth=21, timeOut=5, useSeparator=False)

            if solution.startswith('Error'):
                self.debug_print(f"Solver error: {solution}")
                return None

            solution = solution.strip()
            if not solution:
                return None

            # Return list of moves
            return solution.split()
        except Exception as e:
            self.debug_print(f"Error getting solution: {e}")
            return None

    def handle_hint_click(self, mouse_pos):
        """Handle click on hint banner/popup. Returns True if click was handled."""
        # Check if clicking on expanded popup's close button
        if self.hint_expanded and self.hint_close_rect:
            if self.hint_close_rect.collidepoint(mouse_pos):
                self.close_hint_popup()
                return True
        
        # Check if clicking on small hint banner's close button
        if self.hint_banner_active and not self.hint_expanded and hasattr(self, 'hint_banner_close_rect'):
            if self.hint_banner_close_rect.collidepoint(mouse_pos):
                self.close_hint_popup()
                return True
        
        # Check if clicking on small hint banner (to expand it)
        if self.hint_banner_active and not self.hint_expanded and self.hint_banner_rect:
            if self.hint_banner_rect.collidepoint(mouse_pos):
                self.show_hint_expanded()
                return True
        
        return False

    def _hdr_wanted(self, display_index, enabled=None):
        """HDR output is used when it is switched on and the monitor runs Windows HDR."""
        if enabled is None:
            enabled = bool(self.settings.settings.get("hdr_enabled", False))
        return enabled and hdr_output.display_hdr_info(display_index)[0]

    def _setup_hdr(self):
        """Create the HDR presenter for the current window (None for SDR windows)."""
        self.hdr_presenter = None
        if self.settings.settings.get("hdr_enabled", False):
            paper_white = self.settings.settings.get("hdr_paper_white", hdr_output.PAPER_WHITE_DEFAULT)
            self.hdr_presenter = hdr_output.create_presenter(self.width, self.height, paper_white)

    def toggle_fullscreen(self):
        """F11: switch between a window and borderless fullscreen on the current monitor"""
        if self.display_mode == "windowed":
            mode = "borderless"
            size = display_manager.desktop_size(self.display_index)
        else:
            mode = "windowed"
            saved = self.settings.settings.get("resolution") or {}
            wanted = (int(saved.get("width", 0) or 0), int(saved.get("height", 0) or 0))
            options = display_manager.windowed_resolutions(self.display_index)
            size = display_manager.nearest(wanted, options) if wanted[0] > 0 else display_manager.default_window_size(self.display_index)
        self.apply_display(mode, self.display_index, size)

    def change_resolution(self, width, height):
        """Change the window size while keeping the current display mode"""
        return self.apply_display(self.display_mode, self.display_index, (width, height))

    def apply_display(self, mode, display_index, size, hdr=None):
        """Switch display mode, monitor, resolution and HDR, keeping the game state"""
        if hdr is None:
            hdr = bool(self.settings.settings.get("hdr_enabled", False))
        self.debug_print(f"Applying display: {mode} on monitor {display_index + 1} at {size[0]}x{size[1]}")
        try:
            # Save cube, camera, animation and game state; the OpenGL context is recreated
            cube_state = None
            camera_rotation = (0, 0)
            animation_state = None
            game_state = None
            if hasattr(self, 'renderer') and self.renderer:
                try:
                    cube_state = self.renderer.rubiks_cube.get_state()
                    camera_rotation = (self.renderer.rotation_x, self.renderer.rotation_y)
                    animation_state = {
                        'is_animating': self.renderer.is_animating,
                        'animation_start_time': self.renderer.animation_start_time,
                        'animating_face': self.renderer.animating_face,
                        'animation_axis': self.renderer.animation_axis,
                        'animation_angle_total': self.renderer.animation_angle_total,
                        'animation_clockwise': self.renderer.animation_clockwise,
                        'pending_move': self.renderer.pending_move
                    }
                    game_state = {
                        'game_started': self.game_started,
                        'new_game_requested': self.new_game_requested,
                        'move_counter': self.move_counter,
                        'start_time': self.start_time,
                        'cube_solved': self.cube_solved,
                        '_ever_started': getattr(self, '_ever_started', False)
                    }
                except Exception as e:
                    self.debug_print(f"Could not save cube state: {e}")

            # Recreate the window from scratch (needed to move between monitors).
            # GL objects die with the old context, so just drop the references.
            self.hdr_presenter = None
            self.settings.settings["hdr_enabled"] = bool(hdr)
            pygame.display.quit()
            pygame.display.init()
            try:
                pygame.display.set_icon(pygame.image.load(resource_path("utils/rubiksCube_Icon.ico")))
            except Exception:
                pass
            self.screen = display_manager.open_window(mode, display_index, size,
                                                      hdr=self._hdr_wanted(display_index, hdr))
            pygame.display.set_caption("Rubik's Cube Simulator")

            self.display_mode = mode
            self.display_index = display_index
            self.is_fullscreen = mode != "windowed"
            self.width, self.height = self.screen.get_size()
            ui.set_screen(self.width, self.height)
            ui.clear_caches()
            self.debug_print(f"Actual screen size: {self.width}x{self.height}")

            # New OpenGL context: rebuild the renderer and restore the cube
            self._overlay_tex = None
            self._setup_hdr()
            self.renderer = Renderer(self.width, self.height)
            skybox_mode = self.menu.get_selected_difficulty() if hasattr(self, 'menu') else None
            if skybox_mode and self.difficulty_change_count > 0:
                self.renderer.reload_skybox_texture(skybox_mode)
            if hasattr(self, 'mouse_interaction'):
                self.mouse_interaction.update_renderer(self.renderer)
            if cube_state is not None:
                try:
                    self.renderer.rubiks_cube.set_state(cube_state)
                    self.renderer.update_cube_colors()
                    self.renderer.rotation_x, self.renderer.rotation_y = camera_rotation
                    if animation_state is not None:
                        for key, value in animation_state.items():
                            setattr(self.renderer, key, value)
                    if game_state is not None:
                        self.game_started = game_state['game_started']
                        self.new_game_requested = game_state['new_game_requested']
                        self.move_counter = game_state['move_counter']
                        self.start_time = game_state['start_time']
                        self.cube_solved = game_state['cube_solved']
                        self._ever_started = game_state['_ever_started']
                except Exception as e:
                    self.debug_print(f"Could not restore cube state: {e}")

            # Save before rebuilding the menu, so it reads the new state
            self.settings.settings["display_mode"] = mode
            self.settings.settings["display_index"] = display_index
            self.settings.settings["fullscreen"] = self.is_fullscreen
            if mode != "borderless":
                # Borderless always uses the native size; keep the window size for later
                self.settings.settings["resolution"] = {"width": self.width, "height": self.height}
            self.settings.save_settings()

            # Rebuild every 2D layer for the new size
            self._achievement_icon_cache = {}
            if hasattr(self, 'menu'):
                self.menu.debug_mode = self.debug_mode
                self.menu._load_display_state()
                self.menu.width, self.menu.height = self.width, self.height
                self.menu._create_menus()
            if hasattr(self, 'results_window'):
                self.results_window.update_dimensions(self.width, self.height)
            if hasattr(self, 'menu_button'):
                self.menu_button.update_dimensions(self.width, self.height)

            self.debug_print(f"Display change complete: {self.width}x{self.height}")
            return True

        except Exception as e:
            print(f"Display change error: {e}")
            self._fallback_resolution()
            return False

    def handle_events(self):
        events = []
        for event in pygame.event.get():
            events.append(event)
            
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == self.MUSIC_END_EVENT:
                # Pick a random song from the playlist
                self.current_song = random.randint(0, len(self.playlist) - 1)
                self.debug_print(f"Playing random song: {self.playlist[self.current_song]}")
                
                # Load and play the random song
                try:
                    pygame.mixer.music.load(self.playlist[self.current_song])
                    pygame.mixer.music.play()
                except Exception as e:
                    self.debug_print(f"Music error: {e}")
            
            elif event.type == self.MUSIC_RESTORE_EVENT:
                # Restore music volume after ducking
                if hasattr(self, 'sound_manager'):
                    self.sound_manager.restore_music_volume()
                # Cancel the timer to prevent repeated calls
                pygame.time.set_timer(self.MUSIC_RESTORE_EVENT, 0)
            
            # F11 works everywhere: menu, results and in game
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self.toggle_fullscreen()

            # IMPORTANT: Pass events to menu FIRST when menu is active
            # This allows text inputs in menus to receive keyboard events
            elif self.menu.is_active():
                # Let menu handle the event first
                if self.menu.handle_event(event):
                    continue
                # Only handle ESC here for menu toggle (F11 handled below for all states)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    # Menu's handle_event already deals with ESC
                    pass
                
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # Don't allow closing results window with ESC - user must choose an option
                    if not self.results_window.active:
                        # Only allow ESC to toggle menu if difficulty has been changed at least once
                        if self.difficulty_change_count >= 1:
                            menu_was_active = self.menu.is_active()
                            self.menu.toggle()
                            if menu_was_active:
                                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
                                # Reset hint timer when closing menu
                                self.last_move_time = time.time()
                            self.debug_print(f"Menu: {'ON' if self.menu.is_active() else 'OFF'}")
                        else:
                            # ESC is disabled when difficulty_change_count is 0 (no banner shown)
                            self.debug_print("ESC disabled: Select a difficulty first")
                elif not self.menu.is_active() and not self.results_window.active and event.key == pygame.K_SPACE:
                    self.auto_rotate = not self.auto_rotate
                    self.debug_print(f"Auto-rotate: {'ON' if self.auto_rotate else 'OFF'}")
                elif not self.menu.is_active() and not self.results_window.active and event.key == pygame.K_b and event.mod & pygame.KMOD_CTRL:
                    self.debug_mode = not self.debug_mode
                    self.debug_print(f"Debug mode: {'ON' if self.debug_mode else 'OFF'}")
                elif not self.menu.is_active() and not self.results_window.active and event.key == pygame.K_t:
                    self.renderer.rotation_x = 0
                    self.renderer.rotation_y = 0
                    self.debug_print("Rotation reset")

                # Cube movement controls using standard notation
                elif not self.menu.is_active() and not self.results_window.active and not (hasattr(self, 'is_scrambling') and self.is_scrambling):
                    # R moves
                    if event.key == pygame.K_r:
                        if event.mod & pygame.KMOD_SHIFT:
                            self.execute_cube_move("R'")
                        else:
                            self.execute_cube_move('R')
                    # L moves
                    elif event.key == pygame.K_l:
                        if event.mod & pygame.KMOD_SHIFT:
                            self.execute_cube_move("L'")
                        else:
                            self.execute_cube_move('L')
                    # U moves
                    elif event.key == pygame.K_u:
                        if event.mod & pygame.KMOD_SHIFT:
                            self.execute_cube_move("U'")
                        else:
                            self.execute_cube_move('U')
                    # D moves
                    elif event.key == pygame.K_d:
                        if event.mod & pygame.KMOD_SHIFT:
                            self.execute_cube_move("D'")
                        else:
                            self.execute_cube_move('D')
                    # F moves
                    elif event.key == pygame.K_f:
                        if event.mod & pygame.KMOD_SHIFT:
                            self.execute_cube_move("F'")
                        else:
                            self.execute_cube_move('F')
                    # B moves
                    elif event.key == pygame.K_b:
                        if event.mod & pygame.KMOD_SHIFT:
                            self.execute_cube_move("B'")
                        else:
                            self.execute_cube_move('B')
                    # M moves (Middle slice)
                    elif event.key == pygame.K_m:
                        if event.mod & pygame.KMOD_SHIFT:
                            self.execute_cube_move("M'")
                        else:
                            self.execute_cube_move('M')
                    # E moves (Equatorial slice)
                    elif event.key == pygame.K_e:
                        if event.mod & pygame.KMOD_SHIFT:
                            self.execute_cube_move("E'")
                        else:
                            self.execute_cube_move('E')
                    # S moves (Standing slice)
                    elif event.key == pygame.K_s:
                        if event.mod & pygame.KMOD_SHIFT:
                            self.execute_cube_move("S'")
                        else:
                            self.execute_cube_move('S')
                    elif event.key == pygame.K_z:
                        self.undo_move()
                    elif event.key == pygame.K_x:
                        # Only allow scrambling in freeplay mode
                        current_difficulty = self.menu.get_selected_difficulty()
                        if current_difficulty == "freeplay":
                            self.scramble_cube()
                        else:
                            self.show_banner("Scrambling is only available in Free Play")
                    elif event.key == pygame.K_g:
                        # Suggest next move (solver) - with cooldown and concurrent run prevention
                        if not self.solver_is_running:
                            current_time = time.time()
                            if current_time - self.solver_last_called >= self.solver_cooldown:
                                self.solver_last_called = current_time
                                # Run solver in background thread
                                solver_thread = threading.Thread(target=self.suggest_next_move_threaded, daemon=True)
                                solver_thread.start()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Left click: first check hint system, then menu button, else cube moves
                if self.handle_hint_click(event.pos):
                    continue
                if not self.results_window.active and self.menu_button.handle_click(event.pos):
                    continue
                # If not handled by menu button, and not in menu/results, do cube moves
                if not self.menu.is_active() and not self.results_window.active:
                    self.mouse_cube_moving = True
                    self.mouse_interaction.start_drag(event.pos)
                    self.auto_rotate = False
                    self.debug_print(f"Mouse cube interaction started at {event.pos}")

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                # Then handle other mouse interactions only if menu/results not active
                if not self.menu.is_active() and not self.results_window.active:
                    # Right mouse button - camera rotation
                    self.mouse_rotating = True
                    self.prev_mouse_x, self.prev_mouse_y = event.pos
                    self.auto_rotate = False
                    self.debug_print(f"Mouse rotation started at {event.pos}")

            elif not self.menu.is_active() and not self.results_window.active and event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left mouse button - cube moves
                    self.mouse_cube_moving = True
                    self.mouse_interaction.start_drag(event.pos)
                    self.auto_rotate = False
                    self.debug_print(f"Mouse cube interaction started at {event.pos}")
                    
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 3 and not self.menu.is_active() and not self.results_window.active:
                    self.mouse_rotating = False
                    self.debug_print("Mouse rotation ended")
                elif event.button == 1 and not self.menu.is_active() and not self.results_window.active:
                    self.mouse_cube_moving = False
                    self.mouse_interaction.end_drag()
                    self.debug_print("Mouse cube interaction ended")
                
            elif not self.menu.is_active() and not self.results_window.active and event.type == pygame.MOUSEMOTION:
                # Handle camera rotation with right mouse button
                if self.mouse_rotating:
                    current_x, current_y = event.pos
                    dx = current_x - self.prev_mouse_x
                    dy = current_y - self.prev_mouse_y
                    
                    horizontal_rotation = dx * self.rotation_sensitivity
                    vertical_rotation = dy * self.vertical_sensitivity
                    
                    self.renderer.rotate_camera(
                        azimuth=horizontal_rotation, 
                        elevation=vertical_rotation
                    )
                    
                    self.debug_print(f"Rotating camera: dx={dx}, dy={dy}")
                    
                    self.prev_mouse_x = current_x
                    self.prev_mouse_y = current_y
                
                # Handle cube moves with left mouse button
                elif self.mouse_cube_moving:
                    detected_move = self.mouse_interaction.update_drag(event.pos)
                    if detected_move:
                        self.debug_print(f"Revolutionary move detected: {detected_move}")
                        # Show revolutionary debug info
                        debug_info = self.mouse_interaction.get_debug_info()
                        self.debug_print(f"   Face: {debug_info['detected_face']}, Zone: {debug_info['detected_zone']}")
                        self.execute_cube_move(detected_move)
                    # If move is not valid, it will be handled by execute_cube_move's can_make_move check
                
                # Update hover detection when not doing anything else
                else:
                    self.mouse_interaction.update_hover(event.pos)
                    # Show hover debug info
                    if self.debug_mode:
                        debug_info = self.mouse_interaction.get_debug_info()
                        if debug_info['hovered_face'] and debug_info['hovered_zone']:
                            zone_type = debug_info['zone_type']
                            self.debug_print(f"Hovering: {debug_info['hovered_face']} face, {debug_info['hovered_zone']} ({zone_type})")
        
        # Handle results window events
        if self.results_window.active:
            self.results_window.handle_events(events)

    def update(self):
        """Update game state"""        
        # Update menu animation
        if hasattr(self, 'menu'):
            self.menu.update()
        
        # Update results window animation and effects
        if hasattr(self, 'results_window'):
            was_active = self.results_window.active
            self.results_window.update()
            if was_active != self.results_window.active:
                self.debug_print(f"Results window state changed: {was_active} -> {self.results_window.active}")
            
        # Update sound manager music fade
        if hasattr(self, 'sound_manager'):
            self.sound_manager.update_music_fade()
        
        # Update cursor based on menu/results window state
        mouse_pos = pygame.mouse.get_pos()
        if hasattr(self, 'menu') and self.menu.is_active():
            self.menu.update_cursor(mouse_pos)
        elif hasattr(self, 'results_window') and self.results_window.active:
            self.results_window.update_cursor(mouse_pos)
        elif getattr(self, 'mouse_rotating', False):
            # Show grab cursor when rotating camera
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_SIZEALL)
        else:
            # Update menu button hover state and set appropriate cursor
            if hasattr(self, 'menu_button'):
                hover_changed = self.menu_button.update_hover(mouse_pos)
                if self.menu_button.is_hovering_menu:
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                # Check if hovering over hint banner's close button (highest priority)
                elif (self.hint_banner_active and hasattr(self, 'hint_banner_close_rect') and 
                      self.hint_banner_close_rect.collidepoint(mouse_pos)):
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                # Check if hovering over hint banner or close button
                elif (self.hint_banner_active and self.hint_banner_rect and 
                      self.hint_banner_rect.collidepoint(mouse_pos)):
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                elif (self.hint_expanded and self.hint_close_rect and 
                      self.hint_close_rect.collidepoint(mouse_pos)):
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
                else:
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            else:
                # Default cursor when in game
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
        
        # Update banner animation
        self.update_banner()

        # Update achievement notification queue
        self.update_achievement_notifications()
        
        # Update hint system
        self.update_hint_system()
        
        # Update animated scrambling
        self.update_animated_scramble()
        
        # Check time limit in limited time mode (only for modes that actually have time limits)
        current_difficulty = self.menu.get_selected_difficulty()
        game_mode_config = self.menu.get_game_mode_config(current_difficulty)
        
        if (self.time_limit is not None and 
            self.start_time is not None and 
            not self.cube_solved and 
            game_mode_config.get("timer_enabled", True) and  # Only check if timer is enabled for this mode
            "time_limit" in game_mode_config):  # Only check if mode has explicit time limit
            elapsed_time = time.time() - self.start_time
            if elapsed_time >= self.time_limit:
                if not self.game_over:
                    self.game_over = True
                    self.game_over_reason = "time_up"
                    self.show_banner("Time's up")
                    # Show game over screen
                    self.results_window.show_game_over(
                        self.move_counter, 
                        elapsed_time, 
                        "time_up", 
                        self.menu.get_selected_difficulty()
                    )
                    
        # Check move limit in limited moves mode (only for modes that actually have move limits)
        if (self.move_limit is not None and 
            self.start_time is not None and 
            not self.cube_solved and 
            not self.game_over and
            self.move_counter >= self.move_limit and
            "move_limit" in game_mode_config and
            not (hasattr(self.renderer, 'is_animating') and self.renderer.is_animating)):  # Don't check during animation
            
            # Double-check that cube is not solved after any pending moves have been executed
            if not self.renderer.rubiks_cube.is_solved():
                self.game_over = True
                self.game_over_reason = "moves_exceeded"
                self.show_banner("Out of moves")
                # Show game over screen
                solve_time = time.time() - self.start_time
                self.results_window.show_game_over(
                    self.move_counter, 
                    solve_time, 
                    "moves_exceeded", 
                    self.menu.get_selected_difficulty()
                )
        
        # Check for game start (when menu becomes inactive for the first time OR new game is requested)
        if not self.menu.is_active():
            if not self.game_started or self.new_game_requested:
                self.game_started = True
                difficulty = self.menu.get_selected_difficulty()
                self.debug_print(f"Game starting with difficulty: {difficulty}")
                
                # Set auto-rotation based on difficulty
                self.set_auto_rotation_by_difficulty(difficulty)
                
                # Only scramble if this is a new game request or the very first start
                if self.new_game_requested or not hasattr(self, '_ever_started'):
                    if not hasattr(self, '_ever_started'):
                        # The menu turntable moved the camera; start from the default view
                        self.renderer.rotation_y = -45
                        self.renderer.rotation_x = 35
                    self.scramble_cube_by_difficulty(difficulty)
                    self._ever_started = True
                
                self.new_game_requested = False  # Reset the flag
                
        if hasattr(self, 'menu') and self.menu.resolution_changed():
            try:
                # Reset first: the menu is rebuilt while the display changes
                self.menu.reset_resolution_changed()
                mode, display_index, size, hdr = self.menu.get_display_request()
                same_size = mode == "borderless" or tuple(size) == (self.width, self.height)
                same_hdr = bool(hdr) == bool(self.settings.settings.get("hdr_enabled", False))
                if (mode, display_index) != (self.display_mode, self.display_index) or not same_size or not same_hdr:
                    self.apply_display(mode, display_index, size, hdr)
                
                # Use both music_volume and master_volume for correct volume after resolution change
                music_volume = self.settings.get_audio_volume("music_volume") / 100
                master_volume = self.settings.get_audio_volume("master_volume") / 100
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.set_volume(music_volume * master_volume)
                
                # Reset the flag after successfully applying settings
                self.menu.reset_resolution_changed()
            except Exception as e:
                self.debug_print(f"Error during resolution change: {e}")
                # Reset the flag even on error to prevent continuous attempts
                self.menu.reset_resolution_changed()

        if not self.menu.is_active() and self.auto_rotate:
            self.renderer.rotate_camera(azimuth=self.auto_rotation_speed, elevation=0)
        elif self.menu.is_active() and self.difficulty_change_count == 0:
            # Slow turntable behind the main menu before the first game
            dt = self.clock.get_time() / 1000.0
            self.renderer.rotate_camera(azimuth=12.0 * min(dt, 0.1), elevation=0)
        
        # Frame-rate independent keyboard controls for camera rotation
        if not self.menu.is_active() and not self.results_window.active:
            dt = self.clock.get_time() / 1000.0  # Convert to seconds
            keys = pygame.key.get_pressed()
            rotation_amount = self.manual_rotation_speed * dt  # degrees per frame based on time
            
            if keys[pygame.K_LEFT]:
                self.renderer.rotate_camera(azimuth=-rotation_amount)
                self.auto_rotate = False
            if keys[pygame.K_RIGHT]:
                self.renderer.rotate_camera(azimuth=rotation_amount)
                self.auto_rotate = False
            if keys[pygame.K_UP]:
                self.renderer.rotate_camera(elevation=-rotation_amount)
                self.auto_rotate = False
            if keys[pygame.K_DOWN]:
                self.renderer.rotate_camera(elevation=rotation_amount)
                self.auto_rotate = False
        
        # Update cube colors after animation completes
        if hasattr(self.renderer, 'is_animating'):
            if not hasattr(self.renderer, '_last_animation_state'):
                self.renderer._last_animation_state = self.renderer.is_animating
            
            # Check if animation just finished
            if self.renderer._last_animation_state and not self.renderer.is_animating:
                # Check if solved after move (move is already executed in renderer)
                cube_is_solved = self.renderer.rubiks_cube.is_solved()
                
                if cube_is_solved and not self.cube_solved:
                    # Get current difficulty to determine if we should show results
                    current_difficulty = self.menu.get_selected_difficulty()
                    
                    # Only mark as solved and show win messages if not in freeplay mode
                    if current_difficulty != "freeplay":
                        self.cube_solved = True
                        solve_time = time.time() - self.start_time if self.start_time else 0
                        tps = self.move_counter / solve_time if solve_time > 0 else 0

                        self.debug_print(f"Cube solved within time/move limits!")

                        # No in-game "cube solved" banner; results window handles the feedback.
                        # Keep terminal output for debug purposes.
                        print("CUBE SOLVED!")

                        # Show results window
                        self.results_window.show_results(self.move_counter, solve_time, tps, current_difficulty)

                        # Queue achievement notifications if any were unlocked by this solve
                        try:
                            unlocked = []
                            if hasattr(self.results_window, 'results_data') and self.results_window.results_data:
                                unlocked = self.results_window.results_data.get('newly_unlocked_achievements', []) or []
                            if unlocked:
                                self.enqueue_achievement_notifications(unlocked, delay_seconds=0.0)
                        except Exception:
                            pass
            
            # Update animation state
            self.renderer._last_animation_state = self.renderer.is_animating
    
    def render(self):
        # With HDR output the frame is drawn offscreen and converted when presenting
        if self.hdr_presenter:
            self.hdr_presenter.begin()

        # Create debug callback that includes both mouse interaction debug and visual hints
        def combined_callback():
            if self.debug_mode:
                self.mouse_interaction.render_debug_faces()
            
            # Render visual hint if active
            if self.show_visual_hint and self.visual_hint_face:
                self.renderer.render_visual_hint(
                    self.visual_hint_face, 
                    self.visual_hint_clockwise, 
                    self.visual_hint_pulse_time
                )
        
        # Behind the main menu, shift the view so the cube sits in the free area right of the panel
        target_shift = 0.0
        if self.menu.is_active() and self.menu.current_menu is self.menu.main_menu:
            target_shift = (self.menu.L.panel_w / self.width) * self.menu.get_current_alpha()
        dt = min(0.1, self.clock.get_time() / 1000.0)
        shift = getattr(self, '_lens_shift', 0.0)
        shift += (target_shift - shift) * min(1.0, dt * 12.0)
        self._lens_shift = 0.0 if abs(shift) < 0.0005 else shift

        if self._lens_shift:
            glMatrixMode(GL_PROJECTION)
            glPushMatrix()
            glLoadIdentity()
            glTranslatef(self._lens_shift, 0.0, 0.0)
            gluPerspective(getattr(self.renderer, 'fov', 45), self.width / self.height, 0.1, 50.0)
            glMatrixMode(GL_MODELVIEW)

        # Render 3D cube with combined callback
        self.renderer.render_frame(debug_callback=combined_callback)

        if self._lens_shift:
            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
        
        # Notify menu that game has rendered (for blur background capture)
        if hasattr(self, 'menu') and not self.menu.game_rendered:
            self.menu.notify_game_rendered()
        
        # Render 2D overlays (menu and FPS)
        # Switch to 2D orthographic projection
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, self.width, self.height, 0, -1, 1)
        
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()
        
        # Disable depth testing for 2D rendering
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        
        # Enable blending for transparency
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        # HUD fades out while the menu is open
        menu_alpha = self.menu.get_current_alpha()
        hud_alpha = 1.0 - menu_alpha
        if hud_alpha > 0.01 and not self.results_window.active:
            if self.show_fps:
                self._render_fps_counter(hud_alpha)
            self._render_game_stats(hud_alpha)

        # Render notification banner if active
        if self.banner_active:
            self._render_banner_opengl()

        # Render hint pill or expanded hint panel
        if (self.hint_banner_active or self.hint_expanded) and not self.menu.is_active():
            self._render_hint_system()

        # Render menu overlay if active (including during animation)
        if menu_alpha > 0.0:
            overlay = self._get_overlay_surface()
            self.menu.draw(overlay)
            self._draw_overlay(overlay, menu_alpha)

        # Render results window overlay if active
        elif self.results_window.active:
            overlay = self._get_overlay_surface()
            self.results_window.render_to_surface(overlay)
            self._draw_overlay(overlay, 1.0)

        # Achievement notifications always appear on top
        if self._achievement_notification_active:
            self._render_achievement_notification_opengl()

        # Menu button when not in menu or results
        if not self.menu.is_active() and not self.results_window.active:
            button = self.menu_button
            surf = button.menu_button_surface_hover if button.is_hovering_menu else button.menu_button_surface
            self._blit_gl(surf, button.menu_button_rect.x, button.menu_button_rect.y)

        # Restore 3D state
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        
        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        
        # Update window caption
        pygame.display.set_caption("Rubik's Cube Simulator")

        if self.hdr_presenter:
            self.hdr_presenter.end()
        pygame.display.flip()

    def _blit_gl(self, surface, x, y):
        """Draw a pygame surface on the 2D overlay with its top left at (x, y)."""
        w, h = surface.get_size()
        if w <= 0 or h <= 0:
            return
        x = max(0, min(int(x), self.width - 1))
        y = max(0, int(y))
        texture_data = pygame.image.tostring(surface, 'RGBA', True)
        glRasterPos2f(x, min(self.height, y + h))
        glPixelZoom(1, 1)
        glDrawPixels(w, h, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)

    def _get_overlay_surface(self):
        """Full screen transparent surface reused every frame for menus and results."""
        surf = getattr(self, '_overlay_surface', None)
        if surf is None or surf.get_size() != (self.width, self.height):
            surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self._overlay_surface = surf
        surf.fill((0, 0, 0, 0))
        return surf

    def _draw_overlay(self, surface, alpha):
        """Upload a full screen surface to a texture and draw it as one quad.

        Much faster than tostring + glDrawPixels at high resolutions: the
        surface's BGRA pixels are uploaded without an extra copy."""
        w, h = surface.get_size()
        if getattr(self, '_overlay_tex', None) is None or getattr(self, '_overlay_tex_size', None) != (w, h):
            self._overlay_tex = glGenTextures(1)
            self._overlay_tex_size = (w, h)
            glBindTexture(GL_TEXTURE_2D, self._overlay_tex)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_BGRA, GL_UNSIGNED_BYTE, None)
        glBindTexture(GL_TEXTURE_2D, self._overlay_tex)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 4)
        glPixelStorei(GL_UNPACK_ROW_LENGTH, surface.get_pitch() // 4)
        view = surface.get_view('1')
        pixels = np.frombuffer(view, dtype=np.uint8)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_BGRA, GL_UNSIGNED_BYTE, pixels)
        del pixels, view  # unlock the surface
        glPixelStorei(GL_UNPACK_ROW_LENGTH, 0)

        glEnable(GL_TEXTURE_2D)
        glColor4f(1.0, 1.0, 1.0, max(0.0, min(1.0, alpha)))
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(0, 0)
        glTexCoord2f(1, 0); glVertex2f(w, 0)
        glTexCoord2f(1, 1); glVertex2f(w, h)
        glTexCoord2f(0, 1); glVertex2f(0, h)
        glEnd()
        glColor4f(1.0, 1.0, 1.0, 1.0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glDisable(GL_TEXTURE_2D)

    def _hud_margin(self):
        return ui.px(24)

    def _render_fps_counter(self, alpha=1.0):
        """FPS pill in the top left corner"""
        try:
            fps = self.clock.get_fps()
            fnt = ui.mono_font(ui.SIZE_SMALL, bold=True)
            label = f"{fps:.0f} FPS" if fps > 0 else "-- FPS"
            text = fnt.render(label, True, ui.MUTED)
            pad_x, pad_y = ui.px(14), ui.px(8)
            surf = pygame.Surface((text.get_width() + pad_x * 2, text.get_height() + pad_y * 2), pygame.SRCALPHA)
            ui.fill_rect(surf, (*ui.SURFACE, 225), surf.get_rect(), ui.radius(10))
            ui.fill_rect(surf, ui.LINE, surf.get_rect(), ui.radius(10), width=max(1, ui.px(1.5)))
            surf.blit(text, (pad_x, pad_y))
            if alpha < 1.0:
                surf.set_alpha(int(255 * alpha))
            m = self._hud_margin()
            self._blit_gl(surf, m, m)
        except Exception as e:
            if self.debug_mode:
                print(f"FPS counter rendering error: {e}")

    def _render_game_stats(self, alpha=1.0):
        """Bottom center bar: mode, timer and moves"""
        try:
            current_difficulty = self.menu.get_selected_difficulty()
            game_mode_config = self.menu.get_game_mode_config(current_difficulty)
            timer_enabled = game_mode_config.get("timer_enabled", True)

            segments = []  # (label, value, color, width sample)
            if timer_enabled:
                elapsed = time.time() - self.start_time if self.start_time is not None else 0.0
                if self.time_limit is not None:
                    remaining = max(0.0, self.time_limit - elapsed)
                    color = ui.DANGER if remaining <= 30 else ui.TEXT
                    segments.append(("Time left", ui.format_clock(remaining), color, "00:00"))
                else:
                    segments.append(("Time", ui.format_clock(elapsed), ui.TEXT, "00:00"))
            if self.move_limit is not None:
                remaining_moves = max(0, self.move_limit - self.move_counter)
                color = ui.DANGER if remaining_moves <= 3 else ui.TEXT
                segments.append(("Moves", f"{self.move_counter} / {self.move_limit}", color, f"00 / {self.move_limit}"))
            else:
                segments.append(("Moves", str(self.move_counter), ui.TEXT, "000"))

            label_f = ui.body_font(ui.SIZE_CAPTION)
            value_f = ui.mono_font(ui.SIZE_H3 - 2, bold=True)
            mode_f = ui.display_font(ui.SIZE_H3)
            pad_x = ui.px(26)
            gap = ui.px(26)
            bar_h = label_f.get_height() + value_f.get_height() + ui.px(22)

            mode_name = ui.MODE_NAMES.get(current_difficulty, current_difficulty.replace("_", " ").title())
            mode_surf = ui.render(mode_name, mode_f, ui.TEXT)
            square = ui.px(28)
            mode_w = square + ui.px(12) + mode_surf.get_width()

            # Reserve width for a wide value so the bar does not jitter while the numbers change
            widths = [max(label_f.size(label)[0], value_f.size(sample)[0], value_f.size(value)[0])
                      for label, value, _, sample in segments]
            total_w = pad_x * 2 + mode_w + sum(gap * 2 + w for w in widths)
            surf = pygame.Surface((total_w, bar_h), pygame.SRCALPHA)
            ui.fill_rect(surf, (*ui.SURFACE, 232), surf.get_rect(), ui.radius(14))
            ui.fill_rect(surf, ui.LINE, surf.get_rect(), ui.radius(14), width=max(1, ui.px(1.5)))

            x = pad_x
            mark = ui.mode_icon(current_difficulty, square)
            if mark:
                surf.blit(mark, (x, bar_h // 2 - square // 2))
            surf.blit(mode_surf, (x + square + ui.px(12), bar_h // 2 - mode_surf.get_height() // 2 + ui.px(2)))
            x += mode_w
            for (label, value, color, _), width in zip(segments, widths):
                x += gap
                pygame.draw.line(surf, ui.LINE, (x, ui.px(14)), (x, bar_h - ui.px(14)), max(1, ui.px(1.5)))
                x += gap
                ui.draw_text(surf, label, label_f, ui.MUTED, (x, ui.px(10)))
                ui.draw_text(surf, value, value_f, color, (x, ui.px(10) + label_f.get_height()))
                x += width

            if alpha < 1.0:
                surf.set_alpha(int(255 * alpha))
            m = self._hud_margin()
            self._blit_gl(surf, (self.width - total_w) // 2, self.height - bar_h - m)
        except Exception as e:
            if self.debug_mode:
                print(f"Game stats rendering error: {e}")

    def _toast_surface(self, text, alpha):
        fnt = ui.body_font(ui.SIZE_BODY, bold=True)
        t = fnt.render(text, True, ui.TEXT)
        pad_x, pad_y = ui.px(26), ui.px(16)
        surf = pygame.Surface((t.get_width() + pad_x * 2, t.get_height() + pad_y * 2), pygame.SRCALPHA)
        ui.fill_rect(surf, (*ui.SURFACE, 240), surf.get_rect(), ui.radius(12))
        ui.fill_rect(surf, ui.LINE, surf.get_rect(), ui.radius(12), width=max(1, ui.px(1.5)))
        surf.blit(t, (pad_x, pad_y))
        surf.set_alpha(int(255 * alpha))
        return surf

    def _render_banner_opengl(self):
        """Short notification toast at the top center"""
        if not self.banner_active or self.banner_alpha <= 0:
            return
        try:
            surf = self._toast_surface(self.banner_text, self.banner_alpha)
            y = self._hud_margin() + int((1.0 - self.banner_alpha) * -ui.px(12))
            if self.hint_banner_active or self.hint_expanded:
                # Stack below the hint so the two never overlap
                y = max(y, getattr(self, '_hint_bottom', 0) + ui.px(12))
            self._blit_gl(surf, (self.width - surf.get_width()) // 2, max(0, y))
        except Exception as e:
            if self.debug_mode:
                print(f"Banner rendering error: {e}")

    def _render_hint_system(self):
        """Render hint pill or expanded hint panel"""
        try:
            if self.hint_expanded:
                self._render_expanded_hint()
            elif self.hint_banner_active:
                self._render_small_hint_banner()
        except Exception as e:
            if self.debug_mode:
                print(f"Hint system rendering error: {e}")

    def _close_button(self, surf, rect):
        ui.fill_rect(surf, ui.SURFACE_2, rect, ui.radius(8))
        ic = ui.icon("close", int(rect.width * 0.55), ui.MUTED)
        if ic:
            surf.blit(ic, ic.get_rect(center=rect.center))

    def _render_small_hint_banner(self):
        """Pill asking whether the player wants a hint"""
        a = max(0.0, min(1.0, self.hint_banner_alpha))
        fnt = ui.body_font(ui.SIZE_BODY, bold=True)
        text = fnt.render("Need a hint?", True, ui.TEXT)
        action = ui.body_font(ui.SIZE_SMALL, bold=True).render("Show me", True, ui.ON_ACCENT)
        icon_size = ui.px(28)
        close = ui.px(36)
        pad = ui.px(14)
        pill_h = max(text.get_height(), close) + pad * 2
        action_w = action.get_width() + ui.px(28)
        width = pad + icon_size + ui.px(12) + text.get_width() + ui.px(20) + action_w + ui.px(10) + close + pad
        surf = pygame.Surface((width, pill_h), pygame.SRCALPHA)
        ui.fill_rect(surf, (*ui.SURFACE, 245), surf.get_rect(), ui.radius(14))
        ui.fill_rect(surf, ui.LINE, surf.get_rect(), ui.radius(14), width=max(1, ui.px(1.5)))

        x = pad
        ic = ui.icon("hint", icon_size, ui.ACCENT)
        if ic:
            surf.blit(ic, (x, (pill_h - icon_size) // 2))
        x += icon_size + ui.px(12)
        surf.blit(text, (x, (pill_h - text.get_height()) // 2))
        x += text.get_width() + ui.px(20)
        btn = pygame.Rect(x, (pill_h - close) // 2, action_w, close)
        ui.fill_rect(surf, ui.ACCENT, btn, ui.radius(8))
        surf.blit(action, action.get_rect(center=btn.center))
        close_local = pygame.Rect(btn.right + ui.px(10), (pill_h - close) // 2, close, close)
        self._close_button(surf, close_local)

        bx = (self.width - width) // 2
        by = self._hud_margin()
        self.hint_banner_rect = pygame.Rect(bx, by, close_local.x - ui.px(4), pill_h)
        self.hint_banner_close_rect = close_local.move(bx, by)
        self._hint_bottom = by + pill_h
        surf.set_alpha(int(255 * a))
        self._blit_gl(surf, bx, by)

    def _render_expanded_hint(self):
        """Panel with the suggested moves"""
        import re
        hint_text = self.hint_current_suggestion or "Try analyzing the cube pattern"
        lines = hint_text.split('\n')
        width = min(ui.px(600), self.width - ui.px(48))
        pad = ui.px(24)
        inner = width - pad * 2
        title_f = ui.display_font(ui.SIZE_H3)
        body_f = ui.body_font(ui.SIZE_BODY)
        muted_f = ui.body_font(ui.SIZE_SMALL)
        moves_f = ui.mono_font(ui.SIZE_H2, bold=True)
        move_re = re.compile(r"^[RLUDFBMES]['2]?$")

        # Lay out content first to size the panel
        blocks = []
        for i, line in enumerate(lines):
            tokens = line.split()
            if i == 1 and tokens and all(move_re.match(t) for t in tokens):
                blocks.append(("moves", line))
            elif not line.strip():
                blocks.append(("gap", ""))
            else:
                f = body_f if i == 0 else muted_f
                for wrapped in ui.wrap(line, f, inner):
                    blocks.append(("body" if i == 0 else "muted", wrapped))

        close = ui.px(36)
        header_h = max(title_f.get_height(), close)
        height = pad + header_h + ui.px(14)
        for kind, _ in blocks:
            height += {"moves": moves_f.get_height() + ui.px(16), "gap": ui.px(8),
                       "body": body_f.get_linesize(), "muted": muted_f.get_linesize()}[kind]
        if self.hint_moves_sequence:
            height += muted_f.get_linesize() + ui.px(6)
        height += pad

        surf = pygame.Surface((width, height), pygame.SRCALPHA)
        ui.fill_rect(surf, (*ui.SURFACE, 248), surf.get_rect(), ui.radius(16))
        ui.fill_rect(surf, ui.LINE, surf.get_rect(), ui.radius(16), width=max(1, ui.px(1.5)))
        ui.fill_rect(surf, ui.ACCENT, (pad, 0, ui.px(64), ui.px(4)), ui.px(2))

        icon_size = ui.px(28)
        ic = ui.icon("hint", icon_size, ui.ACCENT)
        x = pad
        if ic:
            surf.blit(ic, (x, pad + (header_h - icon_size) // 2))
            x += icon_size + ui.px(12)
        ui.draw_text(surf, "Hint", title_f, ui.TEXT, (x, pad + header_h // 2 + ui.px(2)), "midleft")
        close_local = pygame.Rect(width - pad - close, pad + (header_h - close) // 2, close, close)
        self._close_button(surf, close_local)

        y = pad + header_h + ui.px(14)
        for kind, text in blocks:
            if kind == "moves":
                # Highlight the move the player should do next
                done = self.hint_moves_completed
                cx = pad
                for ti, tok in enumerate(text.split()):
                    color = ui.ACCENT if ti == done else (ui.DIM if ti < done else ui.TEXT)
                    r = ui.draw_text(surf, tok, moves_f, color, (cx, y + ui.px(4)))
                    cx = r.right + ui.px(18)
                y += moves_f.get_height() + ui.px(16)
            elif kind == "gap":
                y += ui.px(8)
            elif kind == "body":
                ui.draw_text(surf, text, body_f, ui.TEXT, (pad, y))
                y += body_f.get_linesize()
            else:
                ui.draw_text(surf, text, muted_f, ui.MUTED, (pad, y))
                y += muted_f.get_linesize()
        if self.hint_moves_sequence:
            step = min(self.hint_moves_completed + 1, len(self.hint_moves_sequence))
            ui.draw_text(surf, f"Step {step} of {len(self.hint_moves_sequence)}", muted_f, ui.DIM, (pad, y + ui.px(6)))

        px_, py_ = (self.width - width) // 2, self._hud_margin()
        self.hint_close_rect = close_local.move(px_, py_)
        self._hint_bottom = py_ + height
        self._blit_gl(surf, px_, py_)

    def can_make_move(self):
        """Check if the player is allowed to make a move (considering move limits)"""
        # Don't allow new moves while animating or if game is over
        if self.renderer.is_animating or self.game_over:
            return False
        
        # Allow moves during scrambling
        if hasattr(self, 'is_scrambling') and self.is_scrambling:
            return True
        
        # Check if cube is already solved
        if self.cube_solved:
            return False
        
        # Check move limit
        if self.move_limit is not None and self.move_counter >= self.move_limit:
            return False
        
        return True
    
    def execute_cube_move(self, move_notation):
        """Execute a Rubik's cube move with animation"""
        # Check if move is allowed before executing
        if not self.can_make_move():
            return
        
        # Check if this move matches the expected hint move
        hint_move_matches = False
        if self.hint_expanded and len(self.hint_moves_sequence) > 0:
            if self.hint_moves_completed < len(self.hint_moves_sequence):
                expected_move = self.hint_moves_sequence[self.hint_moves_completed]
                if move_notation == expected_move:
                    hint_move_matches = True
                    self.debug_print(f"Hint move matched! {move_notation}")
                else:
                    self.debug_print(f"Move {move_notation} doesn't match expected hint move {expected_move}")
        
        # Reset hint timer when making a move (pass whether it matched)
        self.reset_hint_timer(hint_move_matches)
        
        # Only start timer if not scrambling
        if not hasattr(self, 'is_scrambling') or not self.is_scrambling:
            if self.start_time is None:
                self.start_time = time.time()
        
        # Start animation first
        face_name = move_notation.replace("'", "") # FIX AND REMOVE THIS LINES
        clockwise = "'" not in move_notation
        
        if self.renderer.start_face_animation(face_name, clockwise):
            # Play random cube movement sound
            self.sound_manager.play_random_cube_sound()
            
            # Store the move to execute when animation completes
            self.renderer.pending_move = move_notation
            
            # Only increment move counter if not scrambling
            if not hasattr(self, 'is_scrambling') or not self.is_scrambling:
                self.move_counter += 1
                self.debug_print(f"Move {self.move_counter}: {move_notation} (animating)")
                
                # Check if we've reached the move limit after incrementing
                if (self.move_limit is not None and 
                    self.move_counter >= self.move_limit and 
                    not self.cube_solved):
                    # Show warning when reaching move limit
                    self.show_banner(f"Move limit reached ({self.move_counter} of {self.move_limit})")
            else:
                self.debug_print(f"Scramble move: {move_notation} (animating)")
    
    def undo_move(self):
        """Undo the last move"""
        # Don't allow undo if animating
        if self.renderer.is_animating:
            return
        
        # Allow undo in limited moves mode even when limit is reached (gives player a chance to recover)
        # But don't allow undo if game is over for other reasons (time limit, etc.)
        if self.game_over and hasattr(self, 'game_over_reason') and self.game_over_reason != "moves_exceeded":
            self.debug_print("Cannot undo: Game is over")
            return
        
        if self.renderer.rubiks_cube.undo_last_move():
            # Play random cube movement sound for undo
            self.sound_manager.play_random_cube_sound()
            
            self.renderer.update_cube_colors()
            self.move_counter = max(0, self.move_counter - 1)
            self.debug_print(f"Move undone. Move count: {self.move_counter}")
            
            # If we were in game over state due to move limit, reset it since we now have moves available
            if (self.game_over and hasattr(self, 'game_over_reason') and 
                self.game_over_reason == "moves_exceeded" and 
                self.move_limit is not None and self.move_counter < self.move_limit):
                self.game_over = False
                self.game_over_reason = None
                # Close results window if it's open
                if self.results_window.active:
                    self.results_window.close_results()
                self.show_banner(f"Undo gave you a move back ({self.move_counter} of {self.move_limit})")
        else:
            self.debug_print("No moves to undo")
    
    def scramble_cube(self):
        """Scramble the cube"""
        # Play a cube sound for scrambling
        self.sound_manager.play_random_cube_sound()
        
        self.renderer.rubiks_cube.scramble(25)
        self.renderer.update_cube_colors()
        self.move_counter = 0
        self.start_time = None
        self.cube_solved = False
        self.debug_print("Cube scrambled!")
        
        # Record scramble for achievements and show notifications if any unlocked
        newly_unlocked = self.achievements_manager.record_scramble()
        if newly_unlocked:
            self.enqueue_achievement_notifications(newly_unlocked, delay_seconds=0.0)
    
    def animated_scramble_cube(self, num_moves):
        """Scramble the cube with animated moves for visual effect"""
        import random
        
        # Available moves for scrambling
        moves = ['R', "R'", 'L', "L'", 'U', "U'", 'D', "D'", 'F', "F'", 'B', "B'", 'M', "M'", 'E', "E'", 'S', "S'"]
        
        # Generate the scramble sequence
        scramble_sequence = []
        for _ in range(num_moves):
            move = random.choice(moves)
            scramble_sequence.append(move)
        
        # Store original animation duration and set faster duration for scrambling
        self.original_animation_duration = self.renderer.animation_duration
        self.renderer.animation_duration = 0.1  # Faster animation (100ms instead of 300ms)
        
        # Store the scramble sequence for animated execution
        self.scramble_queue = scramble_sequence.copy()
        self.is_scrambling = True
        self.scramble_start_time = time.time()
        
        self.debug_print(f"Starting fast animated scramble with {num_moves} moves: {' '.join(scramble_sequence)}")
    
    def animated_daily_scramble_cube(self, num_moves=20):
        """Scramble the cube with the daily deterministic scramble (animated).
        All players get the same scramble for the current UTC date."""
        
        # Get the daily scramble sequence from the cube
        scramble_sequence = self.renderer.rubiks_cube.get_daily_scramble_sequence(num_moves)
        
        # Store original animation duration and set faster duration for scrambling
        self.original_animation_duration = self.renderer.animation_duration
        self.renderer.animation_duration = 0.1  # Faster animation (100ms instead of 300ms)
        
        # Store the scramble sequence for animated execution
        self.scramble_queue = scramble_sequence.copy()
        self.is_scrambling = True
        self.scramble_start_time = time.time()
        
        self.debug_print(f"Starting daily scramble with {num_moves} moves: {' '.join(scramble_sequence)}")
    
    def update_animated_scramble(self):
        """Update the animated scrambling process"""
        if not hasattr(self, 'is_scrambling') or not self.is_scrambling:
            return
        
        # Don't execute next move if animation is still running
        if self.renderer.is_animating:
            return
        
        # Check if we have more moves to execute
        if hasattr(self, 'scramble_queue') and self.scramble_queue:
            # Execute the next move
            next_move = self.scramble_queue.pop(0)
            self.execute_cube_move(next_move)
            self.debug_print(f"Scramble move: {next_move} ({len(self.scramble_queue)} moves remaining)")
        else:
            # Scrambling complete
            self.is_scrambling = False
            self.move_counter = 0  # Reset move counter after scrambling
            self.start_time = None  # Reset timer
            
            # Restore original animation duration
            if hasattr(self, 'original_animation_duration'):
                self.renderer.animation_duration = self.original_animation_duration
                delattr(self, 'original_animation_duration')
            
            self.debug_print("Fast animated scrambling complete!")
            
            # Clear move history to prevent undoing scramble moves
            if hasattr(self.renderer.rubiks_cube, 'move_history'):
                self.renderer.rubiks_cube.move_history.clear()
    
    def scramble_cube_by_difficulty(self, difficulty):
        """Scramble the cube based on difficulty level"""
        # Play a cube sound for scrambling
        self.sound_manager.play_random_cube_sound()
        
        # Get difficulty configuration from menu
        game_mode_config = self.menu.get_game_mode_config(difficulty)
        
        # ALWAYS reset the cube to solved state first before applying any difficulty-specific scrambling
        self.renderer.rubiks_cube = RubiksCube()
        self.debug_print("Cube reset to solved state")
        
        # Reset challenge mode variables
        self.time_limit = None
        self.move_limit = None
        self.game_over = False
        self.game_over_reason = None
        
        # Reset hint system
        self.hint_banner_active = False
        self.hint_expanded = False
        self.hint_banner_alpha = 0.0
        self.hint_current_suggestion = None
        self.last_move_time = time.time()
        
        # Reset visual hint (3D arrow) state
        self.show_visual_hint = False
        self.visual_hint_face = None
        self.hint_moves_sequence = []
        self.hint_moves_completed = 0
        with self._solution_lock:
            self._cached_solution_moves = None
        
        # Set up challenge limits based on game mode
        if "time_limit" in game_mode_config:
            self.time_limit = game_mode_config["time_limit"]
            self.debug_print(f"Time limit set to {self.time_limit} seconds")
        
        if "move_limit" in game_mode_config:
            self.move_limit = game_mode_config["move_limit"]
            self.debug_print(f"Move limit set to {self.move_limit} moves")
        
        if difficulty == "freeplay":
            # Free play: Keep cube solved (no scrambling)
            self.debug_print("Free play mode: Cube ready for practice!")
        elif difficulty == "easy":
            # Easy: 5 moves scramble
            self.animated_scramble_cube(5)
            self.debug_print("Easy mode: Scramble with 5 moves!")
        elif difficulty == "medium":
            # Medium: 10 moves scramble
            self.animated_scramble_cube(10)
            self.debug_print("Medium mode: Scramble with 10 moves!")
        elif difficulty == "hard":
            # Hard: Random scramble with >30 moves
            import random
            scramble_moves = random.randint(30, 70)  # Generate random number between 30-70
            self.animated_scramble_cube(scramble_moves)
            self.debug_print(f"Hard mode: Completely random scramble!")
        elif difficulty == "limited_time":
            # Limited Time: Medium scramble with time pressure
            self.animated_scramble_cube(15)
            self.debug_print(f"Limited Time mode: Scramble with 15 moves!")
        elif difficulty == "limited_moves":
            # Limited Moves: Medium scramble with move restriction
            self.animated_scramble_cube(15)
            self.debug_print(f"Limited Moves mode: Scramble with 15 moves!")
        elif difficulty == "daily_cube":
            # Daily Cube: Same scramble for all players today
            self.animated_daily_scramble_cube(20)
            self.debug_print(f"Daily Cube mode: Using today's daily scramble!")
        else:
            # Default case (fallback)
            self.animated_scramble_cube(20)
            self.debug_print(f"Unknown difficulty '{difficulty}', using default animated scramble!")
        
        # Update cube colors and reset game state
        self.renderer.update_cube_colors()
        self.move_counter = 0
        self.start_time = None
        self.cube_solved = False
    
    def handle_results_callback(self, action):
        """Handle callbacks from the results window"""
        if action == 'play_again':
            # Scramble the cube for a new game using the current difficulty
            current_difficulty = self.menu.get_selected_difficulty()
            self.scramble_cube_by_difficulty(current_difficulty)
        elif action == 'main_menu':
            # Open the main menu (not the mode screen)
            if not self.menu.is_active():
                self.menu.toggle()
        # 'continue_playing' is handled by just closing the results window
    
    def handle_overlay_callback(self, action):
        """Handle callbacks from the help overlay (UI buttons)"""
        if action == 'toggle_menu':
            # Toggle the main menu
            if self.menu.is_active():
                self.menu.toggle()  # Close menu
                # Reset hint timer when closing menu
                self.last_move_time = time.time()
            else:
                self.menu.toggle()  # Opens on the main menu
    
    def _render_game_info(self):
        """Render game information (FPS, moves, time)"""
        try:
            # Import pygame_menu to access the font
            import pygame_menu
            
            # Create font if not exists - use same font as menu
            if not hasattr(self, '_info_font'):
                self._info_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 35)
            
            info_lines = []
            
            # Add FPS if enabled
            if self.show_fps:
                fps = self.clock.get_fps()
                info_lines.append(f"FPS: {fps:.1f}")
            
            # Add move counter and timer
            if self.move_counter > 0:
                info_lines.append(f"Moves: {self.move_counter}")
                
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    info_lines.append(f"Time: {elapsed:.1f}s")
                    
                    if elapsed > 0:
                        tps = self.move_counter / elapsed
                        info_lines.append(f"TPS: {tps:.2f}")
            
            # Render status if solved
            if self.cube_solved:
                info_lines.append("SOLVED!")
            
            # Render each line
            y_offset = 10
            for line in info_lines:
                text_surface = self._info_font.render(line, True, (255, 255, 255))
                text_width, text_height = text_surface.get_size()
                
                # Background
                bg_surface = pygame.Surface((text_width + 20, text_height + 6), pygame.SRCALPHA)
                bg_surface.fill((0, 0, 0, 128))
                bg_surface.blit(text_surface, (10, 3))
                
                # Render to screen
                texture_data = pygame.image.tostring(bg_surface, 'RGBA', True)
                glRasterPos2f(10, y_offset + text_height + 6)
                glPixelZoom(1, 1)
                glDrawPixels(text_width + 20, text_height + 6, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
                
                y_offset += text_height + 12
                
        except Exception as e:
            if self.debug_mode:
                print(f"Game info rendering error: {e}")

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick()
            
        # Before exiting, save settings (borderless keeps the last window size)
        if self.display_mode != "borderless":
            self.settings.settings["resolution"] = {"width": self.width, "height": self.height}
        self.settings.settings["display_mode"] = self.display_mode
        self.settings.settings["display_index"] = self.display_index
        self.settings.settings["fullscreen"] = self.is_fullscreen
        self.settings.settings["show_fps"] = self.show_fps
        self.settings.settings["volume"] = int(pygame.mixer.music.get_volume() * 100)
        self.settings.save_settings()
        
        self.renderer.close()
        pygame.quit()
        sys.exit()

    def _fallback_resolution(self):
        """Fall back to a safe window on the primary monitor if a display change fails"""
        try:
            print("Attempting fallback to safe resolution")
            pygame.display.quit()
            pygame.display.init()
            size = display_manager.default_window_size(0)
            self.hdr_presenter = None
            self.screen = display_manager.open_window("windowed", 0, size, hdr=False)
            self.display_mode, self.display_index, self.is_fullscreen = "windowed", 0, False
            self.width, self.height = self.screen.get_size()
            ui.set_screen(self.width, self.height)
            ui.clear_caches()
            self._overlay_tex = None
            self.renderer = Renderer(self.width, self.height)
            if hasattr(self, 'mouse_interaction'):
                self.mouse_interaction.update_renderer(self.renderer)
            if hasattr(self, 'menu'):
                self.menu._load_display_state()
                self.menu.width, self.menu.height = self.width, self.height
                self.menu._create_menus()
            if hasattr(self, 'results_window'):
                self.results_window.update_dimensions(self.width, self.height)
            if hasattr(self, 'menu_button'):
                self.menu_button.update_dimensions(self.width, self.height)
            print(f"Restored a safe window: {self.width}x{self.height}")
        except Exception as e:
            print(f"Critical error in fallback resolution: {e}")
            self.running = False
