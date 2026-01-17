import pygame
import sys
import time
import random
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
from src.personal_best_manager import PersonalBestManager
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
        self.width = self.settings.settings["resolution"]["width"]
        self.height = self.settings.settings["resolution"]["height"]
        self.is_fullscreen = self.settings.settings["fullscreen"]
        self.show_fps = self.settings.settings["show_fps"]
        
        # Use existing OpenGL screen or create new one
        if existing_screen:
            current_size = existing_screen.get_size()
            
            # Check if we need to change size or fullscreen mode
            if current_size == (self.width, self.height) and not self.is_fullscreen:
                # Perfect match - reuse the existing OpenGL context
                self.screen = existing_screen
            else:
                # Need to recreate for different size/fullscreen
                display_flags = DOUBLEBUF | OPENGL
                if self.is_fullscreen:
                    display_flags |= FULLSCREEN
                self.screen = pygame.display.set_mode((self.width, self.height), display_flags)
        else:
            # Create new OpenGL window
            display_flags = DOUBLEBUF | OPENGL
            if self.is_fullscreen:
                display_flags |= FULLSCREEN
            self.screen = pygame.display.set_mode((self.width, self.height), display_flags)
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
        
        # Initialize Supabase manager for global leaderboard
        self.supabase_manager = get_supabase_manager()
        
        # Connect managers for cloud sync
        self.personal_best_manager.set_supabase_manager(self.supabase_manager)
        self.personal_best_manager.set_user_manager(self.menu.user_manager)
        
        # Set the Supabase manager in the menu for leaderboard display
        self.menu.supabase_manager = self.supabase_manager
        
        # Set the personal best manager in the menu to use the same instance
        self.menu.personal_best_manager = self.personal_best_manager
        
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
        
        # Banner notification system
        self.banner_active = False
        self.banner_text = ""
        self.banner_start_time = 0
        self.banner_duration = 5.0  # 3 seconds total display time
        self.banner_fade_duration = 0.2  # 0.5 seconds for fade in/out
        self.banner_alpha = 0.0
        
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
        
        # Load hint icons
        self._load_hint_icons()
        
        print("Controls:")
        print("  Space: Toggle auto-rotation")
        print("  Arrow keys: Manual rotation")
        print("  Left Mouse + Drag: Rotate cube view")
        print("  Right Mouse + Drag: Execute move cube")
        print("  Ctrl+B: Toggle debug mode")
        print("  T: Reset rotation")
        print("  ESC: Toggle menu")        
        print("\nMovement Controls:")
        print("  R: R move       Shift+R: R' move")
        print("  L: L move       Shift+L: L' move") 
        print("  U: U move       Shift+U: U' move")
        print("  D: D move       Shift+D: D' move")
        print("  F: F move       Shift+F: F' move")
        print("  B: B move       Shift+B: B' move")
        print("Slice Moves:")
        print("  M: M move       Shift+M: M' move (Middle)")
        print("  E: E move       Shift+E: E' move (Equatorial)")
        print("  S: S move       Shift+S: S' move (Standing)")
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

            # CRITICAL: Validate solution using pykociemba's own move semantics
            # This ensures the moves will actually solve the cube as the solver expects
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
        
        # Don't show hints in freeplay mode
        current_difficulty = self.menu.get_selected_difficulty()
        if current_difficulty == "freeplay":
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
        
        # Update hint banner fade-in animation
        if self.hint_banner_active and not self.hint_expanded:
            elapsed = current_time - self.hint_banner_start_time
            if elapsed < self.hint_banner_fade_in_time:
                self.hint_banner_alpha = elapsed / self.hint_banner_fade_in_time
            else:
                self.hint_banner_alpha = 1.0

    def show_hint_expanded(self):
        """Show the expanded hint popup with algorithm suggestion"""
        self.hint_expanded = True
        self.hint_banner_active = False
        
        # Get the hint moves sequence
        solution_moves = self._get_solution_moves()
        if solution_moves:
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
                
                # Stop after we have 3 moves worth
                if len(expanded_moves) >= 3:
                    break
            
            self.hint_moves_sequence = expanded_moves[:3]  # Store first 3 moves
            self.hint_moves_completed = 0
        else:
            self.hint_moves_sequence = []
            self.hint_moves_completed = 0
        
        # Get the hint suggestion
        self.hint_current_suggestion = self._get_hint_suggestion()
        self.debug_print(f"Showing expanded hint: {self.hint_current_suggestion}")
        
        # Enable visual hint with first move
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

    def _get_hint_suggestion(self):
        """Get a hint suggestion for the next 4 moves"""
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
        
        # Try to get actual solver suggestion - get full solution
        try:
            # Get the full solution
            solution_moves = self._get_solution_moves()
            if solution_moves:
                # Get first few moves (considering double moves)
                display_moves = []
                for move in solution_moves:
                    display_moves.append(move)
                    # Count how many actual moves this represents
                    if '2' in move:
                        # Double move counts as 2
                        if len(display_moves) >= 2:
                            break
                    else:
                        if len(display_moves) >= 3:
                            break
                
                # Limit to show at most 3 original moves
                display_moves = display_moves[:3]
                moves_str = " ".join(display_moves)
                
                phrase = random.choice(hint_phrases)
                
                # Add explanation about the visual arrow
                first_move = display_moves[0]
                direction = "clockwise" if "'" not in first_move else "counterclockwise"
                face_name = self._get_face_name(first_move[0])
                
                return f"{phrase} these moves:\n{moves_str}\n\n⚠️ Watch the {face_name} face!\nThe yellow arrow shows {direction} rotation"
        except Exception as e:
            self.debug_print(f"Could not get solver suggestion: {e}")
        
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

    def toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode with proper resolution handling"""
        if self.is_fullscreen:
            # Switch to windowed mode
            self.screen = pygame.display.set_mode((self.width, self.height), DOUBLEBUF | OPENGL)
            self.renderer.setup_opengl()
            self.renderer.create_display_list()
        else:
            # Switch to fullscreen mode
            display_info = pygame.display.Info()
            fullscreen_width = display_info.current_w
            fullscreen_height = display_info.current_h
            
            self.screen = pygame.display.set_mode((fullscreen_width, fullscreen_height), DOUBLEBUF | OPENGL | FULLSCREEN)
            self.renderer.setup_opengl()
            self.renderer.create_display_list()
            
            # Update dimensions for fullscreen
            self.width = fullscreen_width
            self.height = fullscreen_height
            
            # Update all components with new dimensions
            if hasattr(self, 'menu'):
                self.menu.width = self.width
                self.menu.height = self.height
                if hasattr(self, 'debug_mode'):
                    self.menu.debug_mode = self.debug_mode
                self.menu._create_menus()
            
            if hasattr(self, 'results_window'):
                self.results_window.update_dimensions(self.width, self.height)
                
            if hasattr(self, 'menu_button'):
                self.menu_button.update_dimensions(self.width, self.height)
            
            # Update mouse interaction system for fullscreen dimensions
            if hasattr(self, 'mouse_interaction'):
                self.mouse_interaction.update_renderer(self.renderer)
            
            self.debug_print(f"Switched to fullscreen: {fullscreen_width}x{fullscreen_height}")
        
        self.is_fullscreen = not self.is_fullscreen
    
    def change_resolution(self, width, height):
        """Change screen resolution"""
        self.debug_print(f"Changing resolution to {width}x{height}")
        
        try:
            # Store current fullscreen state
            fullscreen = self.menu.fullscreen if hasattr(self, 'menu') else self.is_fullscreen
            
            # Save the current cube state before recreating renderer
            cube_state = None
            camera_rotation = (0, 0)
            animation_state = None
            game_state = None
            if hasattr(self, 'renderer') and self.renderer:
                try:
                    # Save the cube state
                    cube_state = self.renderer.rubiks_cube.get_state()
                    # Save camera rotation
                    camera_rotation = (self.renderer.rotation_x, self.renderer.rotation_y)
                    # Save animation state
                    animation_state = {
                        'is_animating': self.renderer.is_animating,
                        'animation_start_time': self.renderer.animation_start_time,
                        'animating_face': self.renderer.animating_face,
                        'animation_axis': self.renderer.animation_axis,
                        'animation_angle_total': self.renderer.animation_angle_total,
                        'animation_clockwise': self.renderer.animation_clockwise,
                        'pending_move': self.renderer.pending_move
                    }
                    # Save game state to prevent unwanted scrambling
                    game_state = {
                        'game_started': self.game_started,
                        'new_game_requested': self.new_game_requested,
                        'move_counter': self.move_counter,
                        'start_time': self.start_time,
                        'cube_solved': self.cube_solved,
                        '_ever_started': getattr(self, '_ever_started', False)
                    }
                    self.debug_print("Saved cube, animation, and game state during resolution change")
                except Exception as e:
                    self.debug_print(f"Could not save cube state: {e}")
            
            # First completely recreate the pygame display without OpenGL
            pygame.display.quit()
            pygame.display.init()
            
            # Set display flags
            display_flags = DOUBLEBUF | OPENGL
            if fullscreen:
                display_flags |= FULLSCREEN
                self.is_fullscreen = True
            else:
                self.is_fullscreen = False
            
            # Update internal dimensions
            self.width = width
            self.height = height
            
            # Set the new display mode with a fresh pygame instance
            self.screen = pygame.display.set_mode((width, height), display_flags)
            pygame.display.set_caption("Rubik's Cube Simulator")
            
            # Verify the actual dimensions
            actual_width, actual_height = pygame.display.get_surface().get_size()
            self.debug_print(f"Actual screen size: {actual_width}x{actual_height}")
            
            # If actual size differs significantly from requested size, update dimensions
            if abs(actual_width - width) > 5 or abs(actual_height - height) > 5:
                self.width = actual_width
                self.height = actual_height
    
            # Now recreate the OpenGL context with correct dimensions
            self.renderer = Renderer(self.width, self.height)
            
            # Update mouse interaction system with new renderer
            if hasattr(self, 'mouse_interaction'):
                self.mouse_interaction.update_renderer(self.renderer)
            
            # Restore the saved cube state
            if cube_state is not None:
                try:
                    self.renderer.rubiks_cube.set_state(cube_state)
                    # Update the renderer's visual representation to match the restored state
                    self.renderer.update_cube_colors()
                    # Restore camera rotation
                    self.renderer.rotation_x, self.renderer.rotation_y = camera_rotation
                    # Restore animation state
                    if animation_state is not None:
                        self.renderer.is_animating = animation_state['is_animating']
                        self.renderer.animation_start_time = animation_state['animation_start_time']
                        self.renderer.animating_face = animation_state['animating_face']
                        self.renderer.animation_axis = animation_state['animation_axis']
                        self.renderer.animation_angle_total = animation_state['animation_angle_total']
                        self.renderer.animation_clockwise = animation_state['animation_clockwise']
                        self.renderer.pending_move = animation_state['pending_move']
                        # Note: animation_cubes will be recreated when needed
                    # Restore game state
                    if game_state is not None:
                        self.game_started = game_state['game_started']
                        self.new_game_requested = game_state['new_game_requested']
                        self.move_counter = game_state['move_counter']
                        self.start_time = game_state['start_time']
                        self.cube_solved = game_state['cube_solved']
                        self._ever_started = game_state['_ever_started']
                    self.debug_print("Restored cube, animation, and game state after resolution change")
                except Exception as e:
                    self.debug_print(f"Could not restore cube state: {e}")
    
            # Update menu with the actual dimensions
            if hasattr(self, 'menu'):
                self.menu.width = self.width
                self.menu.height = self.height
                if hasattr(self, 'debug_mode'):
                    self.menu.debug_mode = self.debug_mode
                self.menu._create_menus()
            
            # Update results window with new dimensions
            if hasattr(self, 'results_window'):
                self.results_window.update_dimensions(self.width, self.height)
                
            if hasattr(self, 'menu_button'):
                self.menu_button.update_dimensions(self.width, self.height)
    
            # Try to restore icon
            try:
                icon = pygame.image.load("utils/rubiksCube_Icon.ico")
                pygame.display.set_icon(icon)
            except Exception:
                pass
    
            # Save settings
            self.settings.settings["resolution"]["width"] = self.width
            self.settings.settings["resolution"]["height"] = self.height
            self.settings.settings["fullscreen"] = self.is_fullscreen
            self.settings.save_settings()
    
            self.debug_print(f"Resolution change complete: {self.width}x{self.height}")
            return True
    
        except Exception as e:
            print(f"Resolution change error: {e}")
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
                elif event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                
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
                            self.show_banner(f"Scramble is only available in freeplay mode")
                    elif event.key == pygame.K_g:
                        # Suggest next move (solver) - with cooldown to prevent duplicate triggers
                        current_time = time.time()
                        if current_time - self.solver_last_called >= self.solver_cooldown:
                            self.solver_last_called = current_time
                            self.suggest_next_move()

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Left click: first check hint system, then menu button, else cube moves
                if self.handle_hint_click(event.pos):
                    continue
                if self.menu_button.handle_click(event.pos):
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
                    self.show_banner("Time's up! Game Over!")
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
                self.show_banner("Game Over! Move limit exceeded!")
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
                    self.scramble_cube_by_difficulty(difficulty)
                    self._ever_started = True
                
                self.new_game_requested = False  # Reset the flag
                
        if hasattr(self, 'menu') and self.menu.resolution_changed():
            try:
                new_width, new_height = self.menu.get_current_resolution()
                fullscreen = self.menu.get_setting('fullscreen')
                
                if (new_width, new_height) != (self.width, self.height) or fullscreen != self.is_fullscreen:
                    self.change_resolution(new_width, new_height)
                
                show_fps = self.menu.get_setting('show_fps')
                if show_fps is not None:
                    self.show_fps = show_fps
                
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

                        # Special messages for challenge modes
                        if current_difficulty == "limited_time":
                            remaining_time = max(0, self.time_limit - solve_time)
                            self.show_banner(f"SOLVED! With {remaining_time:.1f}s to spare!")
                        elif current_difficulty == "limited_moves":
                            remaining_moves = max(0, self.move_limit - self.move_counter)
                            self.show_banner(f"SOLVED! With {remaining_moves} moves to spare!")
                        else:
                            self.show_banner("CUBE SOLVED!")

                        # Print to terminal for debug purposes
                        print(f"CUBE SOLVED!")

                        # Show results window
                        self.results_window.show_results(self.move_counter, solve_time, tps, current_difficulty)
            
            # Update animation state
            self.renderer._last_animation_state = self.renderer.is_animating
    
    def render(self):
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
        
        # Render 3D cube with combined callback
        self.renderer.render_frame(debug_callback=combined_callback)
        
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
        
        # Render FPS counter if enabled
        if self.show_fps:
            self._render_fps_counter()
        
        # Render game stats (timer and moves) if game is in progress
        # Show stats even when menu is active, but with reduced opacity
        if not self.results_window.active:
            menu_alpha = self.menu.get_current_alpha()
            stats_alpha = 1.0 - (menu_alpha * 0.7)  # Reduce opacity when menu is visible
            self._render_game_stats(stats_alpha)
        
        # Render notification banner if active
        if self.banner_active:
            self._render_banner_opengl()
        
        # Render hint banner or expanded hint popup
        if self.hint_banner_active or self.hint_expanded:
            self._render_hint_system()
        
        # Render menu overlay if active (including during animation)
        menu_alpha = self.menu.get_current_alpha()
        if menu_alpha > 0.0:
            # Create menu surface and render to it
            menu_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.menu.draw(menu_surface)
            
            # Apply alpha to entire menu surface if needed
            if menu_alpha < 1.0:
                # Create alpha overlay surface
                alpha_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                alpha_surface.fill((255, 255, 255, int(255 * menu_alpha)))
                menu_surface.blit(alpha_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            
            # Convert pygame surface to OpenGL texture
            texture_data = pygame.image.tostring(menu_surface, 'RGBA', True)
            
            glRasterPos2f(0, self.height)
            glPixelZoom(1, 1)  # Flip vertically
            glDrawPixels(self.width, self.height, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        
        # Render results window overlay if active
        elif self.results_window.active:
            # Create results surface and render the modern effects to it
            results_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            
            # Let the results window render its modern effects to the surface
            self.results_window.render_to_surface(results_surface)
            
            # Convert pygame surface to OpenGL texture
            texture_data = pygame.image.tostring(results_surface, 'RGBA', True)
            
            glRasterPos2f(0, self.height)
            glPixelZoom(1, 1)  # Flip vertically
            glDrawPixels(self.width, self.height, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
    
        # Render menu button when not in menu or results
        if (hasattr(self, 'menu_button') and 
              not self.menu.is_active() and 
              not self.results_window.active):
            
            # Calculate area needed for the button
            button_margin = 10
            total_width = self.menu_button.button_size + (button_margin * 2)
            button_area_height = self.menu_button.button_size + (button_margin * 2)
            button_surface = pygame.Surface((total_width, button_area_height), pygame.SRCALPHA)
            
            # Draw menu button
            menu_x = button_margin
            menu_y = button_margin
            if self.menu_button.is_hovering_menu:
                button_surface.blit(self.menu_button.menu_button_surface_hover, (menu_x, menu_y))
            else:
                button_surface.blit(self.menu_button.menu_button_surface, (menu_x, menu_y))
            
            # Convert surface to OpenGL
            texture_data = pygame.image.tostring(button_surface, 'RGBA', True)
            
            # Position correctly
            buttons_x = self.menu_button.menu_button_rect.x - button_margin
            buttons_y = self.menu_button.menu_button_rect.y - button_margin
            
            glRasterPos2f(buttons_x, buttons_y + button_area_height)
            glPixelZoom(1, 1)
            glDrawPixels(total_width, button_area_height, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
    
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
        
        pygame.display.flip()

    def _render_fps_counter(self):
        """Render FPS counter in the top-left corner"""
        try:
            # Import pygame_menu to access the font
            import pygame_menu
            
            # Get current FPS
            fps = self.clock.get_fps()
            
            # Create font if not exists - use same font as menu
            if not hasattr(self, '_fps_font'):
                self._fps_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 30)
            
            # Create FPS text surface
            fps_text = f"FPS: {fps:.0f}"
            text_surface = self._fps_font.render(fps_text, True, (255, 255, 255))
            
            # Add a semi-transparent rounded background for better readability
            text_width, text_height = text_surface.get_size()
            bg_surface = pygame.Surface((text_width + 20, text_height + 10), pygame.SRCALPHA)
            bg_surface.fill((0, 0, 0, 0))  # Fully transparent first
            # Draw rounded rectangle background
            pygame.draw.rect(bg_surface, (0, 0, 0, 128), (0, 0, text_width + 20, text_height + 10), border_radius=10)
            # Optional: accent border
            pygame.draw.rect(bg_surface, (100, 150, 255, 100), (0, 0, text_width + 20, text_height + 10), width=2, border_radius=10)
            # Blit text onto background
            bg_surface.blit(text_surface, (10, 5))
            # Convert to OpenGL texture and render
            texture_data = pygame.image.tostring(bg_surface, 'RGBA', True)
            # Position in top-left corner (10 pixels from edges)
            glRasterPos2f(10, text_height + 15)
            glPixelZoom(1, 1)
            glDrawPixels(text_width + 20, text_height + 10, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
            
        except Exception as e:
            # Fallback: if there's an error, just print to console
            if self.debug_mode:
                print(f"FPS counter rendering error: {e}")

    def _render_game_stats(self, alpha=1.0):
        """Render timer and moves counter in the bottom-left corner"""
        try:
            # Import pygame_menu to access the font
            import pygame_menu
            
            # Create font if not exists - use same font as menu
            if not hasattr(self, '_stats_font'):
                self._stats_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 35)
            
            # Prepare text lines
            text_lines = []
            urgent_color = False  # Flag for urgent coloring (red text)
            
            # Get current game mode configuration
            current_difficulty = self.menu.get_selected_difficulty()
            game_mode_config = self.menu.get_game_mode_config(current_difficulty)
            
            # Add moves counter with limit info if applicable
            if self.move_limit is not None:
                remaining_moves = max(0, self.move_limit - self.move_counter)
                if remaining_moves == 0:
                    text_lines.append(f"Moves: {self.move_counter}/{self.move_limit} (LIMIT REACHED)")
                    urgent_color = True
                else:
                    text_lines.append(f"Moves: {self.move_counter}/{self.move_limit} ({remaining_moves} left)")
                    if remaining_moves <= 3:  # Show red when only 3 moves left
                        urgent_color = True
            else:
                text_lines.append(f"Moves: {self.move_counter}")
            
            # Check if timer is enabled for current game mode
            timer_enabled = game_mode_config.get("timer_enabled", True)  # Default to True for compatibility
            
            # Add timer with countdown if applicable
            if timer_enabled:
                if self.start_time is not None:
                    elapsed = time.time() - self.start_time
                    
                    if self.time_limit is not None:
                        # Countdown mode for limited time
                        remaining_time = max(0, self.time_limit - elapsed)
                        if remaining_time <= 0:
                            # Time's up! Show the display but don't set game_over here
                            # The main update() method will handle setting game_over and showing the fail screen
                            text_lines.append("Time: 00:00 (TIME UP!)")
                            urgent_color = True
                        else:
                            minutes = int(remaining_time // 60)
                            seconds = int(remaining_time % 60)
                            text_lines.append(f"Time: {minutes:02d}:{seconds:02d} remaining")
                            if remaining_time <= 30:  # Show red when 30 seconds or less
                                urgent_color = True
                    else:
                        # Regular timer mode
                        minutes = int(elapsed // 60)
                        seconds = int(elapsed % 60)
                        text_lines.append(f"Time: {minutes:02d}:{seconds:02d}")
                else:
                    if self.time_limit is not None:
                        # Show initial time limit
                        minutes = int(self.time_limit // 60)
                        seconds = int(self.time_limit % 60)
                        text_lines.append(f"Time: {minutes:02d}:{seconds:02d} remaining")
                    else:
                        text_lines.append("Time: 00:00")
            
            # Calculate dimensions for background
            text_surfaces = []
            max_width = 0
            total_height = 0
            line_height = 0
            
            # Choose text color based on urgency
            text_color = (255, 80, 80) if urgent_color else (255, 255, 255)  # Red if urgent, white otherwise
            
            for line in text_lines:
                text_surface = self._stats_font.render(line, True, text_color)
                text_surfaces.append(text_surface)
                width, height = text_surface.get_size()
                max_width = max(max_width, width)
                total_height += height
                line_height = height
            
            # Add padding and spacing
            padding = 10
            line_spacing = 5
            bg_width = max_width + (padding * 2)
            bg_height = total_height + (padding * 2) + (line_spacing * (len(text_lines) - 1))
            
            # Create background surface with alpha and rounded corners
            bg_surface = pygame.Surface((bg_width, bg_height), pygame.SRCALPHA)
            bg_surface.fill((0, 0, 0, 0))
            bg_alpha = int(128 * alpha)  # Apply alpha to background
            # Draw rounded rectangle background
            pygame.draw.rect(bg_surface, (0, 0, 0, bg_alpha), (0, 0, bg_width, bg_height), border_radius=10)
            # Optional: accent border
            pygame.draw.rect(bg_surface, (100, 150, 255, int(80 * alpha)), (0, 0, bg_width, bg_height), width=2, border_radius=10)
            # Blit text lines onto background with alpha
            y_offset = padding
            for text_surface in text_surfaces:
                if alpha < 1.0:
                    # Apply alpha to text surface
                    text_surface = text_surface.copy()
                    text_surface.set_alpha(int(255 * alpha))
                bg_surface.blit(text_surface, (padding, y_offset))
                y_offset += line_height + line_spacing
            # Convert to OpenGL texture and render
            texture_data = pygame.image.tostring(bg_surface, 'RGBA', True)
            # Position in bottom-left corner (10 pixels from edges)
            y_position = self.height - bg_height - 10
            glRasterPos2f(10, y_position + bg_height)
            glPixelZoom(1, 1)
            glDrawPixels(bg_width, bg_height, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
            
        except Exception as e:
            if self.debug_mode:
                print(f"Game stats rendering error: {e}")

    def _render_banner_opengl(self):
        """Render notification banner using OpenGL-compatible method"""
        if not self.banner_active or self.banner_alpha <= 0:
            return

        try:
            # Import pygame_menu to access the font
            import pygame_menu
            
            # Create font if not exists - use same font as menu
            if not hasattr(self, '_banner_font'):
                self._banner_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 35)

            # Create text surface
            text_surface = self._banner_font.render(self.banner_text, True, (255, 255, 255))
            
            # Calculate banner dimensions and position
            text_width, text_height = text_surface.get_size()
            banner_width = text_width + 40  # 20px padding on each side
            banner_height = text_height + 20  # 10px padding top/bottom
            banner_x = (self.width - banner_width) // 2
            banner_y = 50  # Distance from top of screen

            # Create banner surface with alpha and rounded corners
            banner_surface = pygame.Surface((banner_width, banner_height), pygame.SRCALPHA)
            banner_surface.fill((0, 0, 0, 0))
            # Banner background (semi-transparent black, rounded)
            background_alpha = int(180 * self.banner_alpha)
            pygame.draw.rect(banner_surface, (0, 0, 0, background_alpha), (0, 0, banner_width, banner_height), border_radius=10)
            # Banner border (subtle white border, rounded)
            border_alpha = int(100 * self.banner_alpha)
            pygame.draw.rect(banner_surface, (255, 255, 255, border_alpha), (0, 0, banner_width, banner_height), width=2, border_radius=10)
            # Apply alpha to text
            text_alpha = int(255 * self.banner_alpha)
            text_surface_alpha = text_surface.copy()
            text_surface_alpha.set_alpha(text_alpha)
            # Blit text to banner
            text_x = (banner_width - text_width) // 2
            text_y = (banner_height - text_height) // 2
            banner_surface.blit(text_surface_alpha, (text_x, text_y))
            # Convert to OpenGL texture and render
            texture_data = pygame.image.tostring(banner_surface, 'RGBA', True)
            glRasterPos2f(banner_x, banner_y + banner_height)
            glPixelZoom(1, 1)
            glDrawPixels(banner_width, banner_height, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
            
        except Exception as e:
            if self.debug_mode:
                print(f"Banner rendering error: {e}")
            
        except Exception as e:
            # Fallback: if there's an error, just print to console
            if self.debug_mode:
                print(f"Game stats rendering error: {e}")

    def _render_hint_system(self):
        """Render hint banner or expanded hint popup"""
        try:
            import pygame_menu
            
            # Create fonts if not exist
            if not hasattr(self, '_hint_font'):
                self._hint_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 28)
            if not hasattr(self, '_hint_title_font'):
                self._hint_title_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 32)
            
            if self.hint_expanded:
                # Render expanded hint popup
                self._render_expanded_hint()
            elif self.hint_banner_active:
                # Render small hint banner
                self._render_small_hint_banner()
                
        except Exception as e:
            if self.debug_mode:
                print(f"Hint system rendering error: {e}")

    def _render_small_hint_banner(self):
        """Render the small 'Need a hint? Click me' banner"""
        try:
            import pygame_menu
            
            if not hasattr(self, '_hint_font'):
                self._hint_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 28)
            
            # Banner text
            banner_text = "Need a hint? Click me!"
            text_surface = self._hint_font.render(banner_text, True, (255, 255, 255))
            text_width, text_height = text_surface.get_size()
            
            # Calculate banner dimensions (include space for icon and close button)
            icon_size = 32
            icon_spacing = 10
            close_btn_size = 24
            close_btn_spacing = 10
            padding_h = 20
            padding_v = 12
            
            total_content_width = icon_size + icon_spacing + text_width if self.hint_icon else text_width
            # Add space for close button
            total_content_width += close_btn_spacing + close_btn_size
            banner_width = total_content_width + (padding_h * 2)
            banner_height = max(text_height, icon_size, close_btn_size) + (padding_v * 2)
            
            # Position at top center of screen
            banner_x = (self.width - banner_width) // 2
            banner_y = 15
            
            # Store rect for click detection (for expanding, but not including close button)
            # We'll calculate the clickable area excluding the close button
            close_btn_x_local = banner_width - padding_h - close_btn_size
            clickable_width = close_btn_x_local - padding_h
            self.hint_banner_rect = pygame.Rect(banner_x + padding_h, banner_y, clickable_width, banner_height)
            
            # Store close button rect for click detection (in screen coordinates)
            close_btn_y_local = (banner_height - close_btn_size) // 2
            self.hint_banner_close_rect = pygame.Rect(
                banner_x + close_btn_x_local,
                banner_y + close_btn_y_local,
                close_btn_size,
                close_btn_size
            )
            
            # Create banner surface
            banner_surface = pygame.Surface((banner_width, banner_height), pygame.SRCALPHA)
            
            # Background with gradient effect (golden/amber color for hint)
            background_alpha = int(220 * self.hint_banner_alpha)
            pygame.draw.rect(banner_surface, (50, 40, 20, background_alpha), 
                           (0, 0, banner_width, banner_height), border_radius=12)
            
            # Accent border (golden)
            border_alpha = int(180 * self.hint_banner_alpha)
            pygame.draw.rect(banner_surface, (255, 200, 80, border_alpha), 
                           (0, 0, banner_width, banner_height), width=2, border_radius=12)
            
            # Calculate content positions
            content_start_x = padding_h
            content_y = (banner_height - max(text_height, icon_size)) // 2
            
            # Draw hint icon if available
            if self.hint_icon:
                icon_y = (banner_height - icon_size) // 2
                icon_alpha_surface = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
                icon_alpha_surface.blit(self.hint_icon, (0, 0))
                icon_alpha_surface.set_alpha(int(255 * self.hint_banner_alpha))
                banner_surface.blit(icon_alpha_surface, (content_start_x, icon_y))
                text_x = content_start_x + icon_size + icon_spacing
            else:
                text_x = content_start_x
            
            # Draw text
            text_y = (banner_height - text_height) // 2
            text_surface.set_alpha(int(255 * self.hint_banner_alpha))
            banner_surface.blit(text_surface, (text_x, text_y))
            
            # Draw close button
            close_btn_bg_alpha = int(150 * self.hint_banner_alpha)
            pygame.draw.rect(banner_surface, (60, 50, 30, close_btn_bg_alpha),
                           (close_btn_x_local, close_btn_y_local, close_btn_size, close_btn_size),
                           border_radius=4)
            pygame.draw.rect(banner_surface, (255, 100, 100, int(150 * self.hint_banner_alpha)),
                           (close_btn_x_local, close_btn_y_local, close_btn_size, close_btn_size),
                           width=1, border_radius=4)
            
            # Draw close icon
            if self.close_icon:
                close_icon_size = 16
                close_icon_scaled = pygame.transform.smoothscale(self.close_icon, (close_icon_size, close_icon_size))
                icon_x = close_btn_x_local + (close_btn_size - close_icon_size) // 2
                icon_y = close_btn_y_local + (close_btn_size - close_icon_size) // 2
                close_icon_alpha = pygame.Surface((close_icon_size, close_icon_size), pygame.SRCALPHA)
                close_icon_alpha.blit(close_icon_scaled, (0, 0))
                close_icon_alpha.set_alpha(int(255 * self.hint_banner_alpha))
                banner_surface.blit(close_icon_alpha, (icon_x, icon_y))
            else:
                # Draw X manually
                x_text = "✕"
                x_surface = self._hint_font.render(x_text, True, (255, 100, 100))
                x_surface.set_alpha(int(255 * self.hint_banner_alpha))
                x_x = close_btn_x_local + (close_btn_size - x_surface.get_width()) // 2
                x_y = close_btn_y_local + (close_btn_size - x_surface.get_height()) // 2
                banner_surface.blit(x_surface, (x_x, x_y))
            
            # Render to OpenGL
            texture_data = pygame.image.tostring(banner_surface, 'RGBA', True)
            glRasterPos2f(banner_x, banner_y + banner_height)
            glPixelZoom(1, 1)
            glDrawPixels(banner_width, banner_height, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
            
        except Exception as e:
            if self.debug_mode:
                print(f"Small hint banner rendering error: {e}")

    def _render_expanded_hint(self):
        """Render the expanded hint popup with algorithm suggestion"""
        try:
            import pygame_menu
            
            if not hasattr(self, '_hint_font'):
                self._hint_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 28)
            if not hasattr(self, '_hint_title_font'):
                self._hint_title_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 36)
            if not hasattr(self, '_hint_moves_font'):
                self._hint_moves_font = pygame.font.Font(pygame_menu.font.FONT_FRANCHISE, 32)
            
            # Get hint text to calculate required height
            hint_text = self.hint_current_suggestion or "Try analyzing the cube pattern..."
            
            # Split hint into lines (handle \n in the text)
            hint_lines = hint_text.split('\n')
            
            # Calculate required height based on content
            title_height = 50
            separator_height = 25
            line_height = 35
            padding_bottom = 20
            
            # Calculate height for all lines
            content_height = title_height + separator_height + (len(hint_lines) * line_height) + padding_bottom
            
            # Popup dimensions
            popup_width = min(500, int(self.width * 0.5))
            popup_height = max(180, content_height)  # Dynamic height based on content
            popup_x = (self.width - popup_width) // 2
            popup_y = 30
            
            # Create popup surface
            popup_surface = pygame.Surface((popup_width, popup_height), pygame.SRCALPHA)
            
            # Background (darker, more prominent)
            pygame.draw.rect(popup_surface, (30, 25, 15, 240), 
                           (0, 0, popup_width, popup_height), border_radius=15)
            
            # Border (golden)
            pygame.draw.rect(popup_surface, (255, 200, 80, 200), 
                           (0, 0, popup_width, popup_height), width=3, border_radius=15)
            
            # Title section
            title_text = "💡 Hint"
            title_surface = self._hint_title_font.render(title_text, True, (255, 220, 100))
            title_x = 20
            title_y = 15
            
            # Draw hint icon next to title if available
            if self.hint_icon:
                icon_y = title_y + (title_surface.get_height() - 32) // 2
                popup_surface.blit(self.hint_icon, (title_x, icon_y))
                title_x += 40
            
            popup_surface.blit(title_surface, (title_x, title_y))
            
            # Separator line
            separator_y = title_y + title_surface.get_height() + 10
            pygame.draw.line(popup_surface, (255, 200, 80, 100), 
                           (15, separator_y), (popup_width - 15, separator_y), 2)
            
            # Render hint text lines
            text_y = separator_y + 15
            for i, line in enumerate(hint_lines):
                # Use different font for moves line (the second line with actual moves)
                if i == 1 and any(move in line for move in ["R", "L", "U", "D", "F", "B", "M", "E", "S", "'"]):
                    # This is the moves line - use larger, bolder font
                    line_surface = self._hint_moves_font.render(line, True, (255, 220, 100))
                else:
                    line_surface = self._hint_font.render(line, True, (255, 255, 255))
                
                # Center the line if it's the moves line
                if i == 1 and any(move in line for move in ["R", "L", "U", "D", "F", "B", "M", "E", "S", "'"]):
                    line_x = (popup_width - line_surface.get_width()) // 2
                else:
                    line_x = 20
                
                popup_surface.blit(line_surface, (line_x, text_y))
                text_y += line_height
            
            # Close button (top right)
            close_btn_size = 30
            close_btn_x = popup_width - close_btn_size - 10
            close_btn_y = 10
            
            # Store close button rect for click detection (in screen coordinates)
            self.hint_close_rect = pygame.Rect(
                popup_x + close_btn_x, 
                popup_y + close_btn_y, 
                close_btn_size, 
                close_btn_size
            )
            
            # Draw close button background
            pygame.draw.rect(popup_surface, (80, 60, 40, 200), 
                           (close_btn_x, close_btn_y, close_btn_size, close_btn_size), 
                           border_radius=6)
            pygame.draw.rect(popup_surface, (255, 100, 100, 180), 
                           (close_btn_x, close_btn_y, close_btn_size, close_btn_size), 
                           width=2, border_radius=6)
            
            # Draw close icon or X
            if self.close_icon:
                icon_x = close_btn_x + (close_btn_size - 24) // 2
                icon_y = close_btn_y + (close_btn_size - 24) // 2
                popup_surface.blit(self.close_icon, (icon_x, icon_y))
            else:
                # Draw X manually
                x_font = self._hint_font
                x_surface = x_font.render("✕", True, (255, 100, 100))
                x_x = close_btn_x + (close_btn_size - x_surface.get_width()) // 2
                x_y = close_btn_y + (close_btn_size - x_surface.get_height()) // 2
                popup_surface.blit(x_surface, (x_x, x_y))
            
            # Render to OpenGL
            texture_data = pygame.image.tostring(popup_surface, 'RGBA', True)
            glRasterPos2f(popup_x, popup_y + popup_height)
            glPixelZoom(1, 1)
            glDrawPixels(popup_width, popup_height, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
            
        except Exception as e:
            if self.debug_mode:
                print(f"Expanded hint rendering error: {e}")

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
                    self.show_banner(f"Move limit reached! ({self.move_counter}/{self.move_limit})")
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
                self.show_banner(f"Moves available again! ({self.move_counter}/{self.move_limit})")
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
            # Clear the old blurred background to force a fresh capture of current cube state
            self.menu.background_capture = None
            self.menu.blurred_background = None
            
            # Show the main menu (ensure we're at main menu, not difficulty selection)
            self.menu.current_menu = self.menu.main_menu
            self.menu.active = True
            
            # Force a new background capture with the current cube state
            self.menu.force_background_recapture()
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
                # Clear the old blurred background to force a fresh capture of current cube state
                self.menu.background_capture = None
                self.menu.blurred_background = None
                
                # Show the main menu (ensure we're at main menu, not difficulty selection)
                self.menu.current_menu = self.menu.main_menu
                self.menu.toggle()  # Open menu
                
                # Force a new background capture with the current cube state
                self.menu.force_background_recapture()
    
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
            
        # Before exiting, save settings
        self.settings.settings["resolution"]["width"] = self.width
        self.settings.settings["resolution"]["height"] = self.height
        self.settings.settings["fullscreen"] = self.is_fullscreen
        self.settings.settings["show_fps"] = self.show_fps
        self.settings.settings["volume"] = int(pygame.mixer.music.get_volume() * 100)
        self.settings.save_settings()
        
        self.renderer.close()
        pygame.quit()
        sys.exit()

    def _fallback_resolution(self):
        """Fallback to a safe resolution if change fails"""
        try:
            print("Attempting fallback to safe resolution")
            
            # First completely recreate the pygame display
            pygame.display.quit()
            pygame.display.init()
            
            # Try a standard resolution that should work
            fallback_width, fallback_height = 1280, 720
            self.width = fallback_width
            self.height = fallback_height
            
            # Reset to windowed mode for safety
            self.is_fullscreen = False
            
            # Set the display mode with safe settings
            self.screen = pygame.display.set_mode((fallback_width, fallback_height), DOUBLEBUF | OPENGL)
            
            # Recreate the renderer from scratch
            self.renderer = Renderer(fallback_width, fallback_height)
            
            # Update menu dimensions if it exists
            if hasattr(self, 'menu'):
                self.menu.width = fallback_width
                self.menu.height = fallback_height
                self.menu._create_menus()
            
            # Update results window dimensions if it exists
            if hasattr(self, 'results_window'):
                self.results_window.update_dimensions(fallback_width, fallback_height)
                
            if hasattr(self, 'menu_button'):
                self.menu_button.update_dimensions(fallback_width, fallback_height)
            
            print(f"Successfully restored to fallback resolution: {fallback_width}x{fallback_height}")
        except Exception as e:
            print(f"Critical error in fallback resolution: {e}")
            # Nothing more we can do at this point
            self.running = False