import pygame
import sys
import time
import random
import threading
from OpenGL.GL import *
from OpenGL.GLU import *
from src.ui.menu import Menu
from src.rendering.renderer import Renderer
from src.managers.settings_manager import SettingsManager
from src.managers.sound_manager import SoundManager, MUSIC_FADE_MS
from src.ui.results_window import ResultsWindow
from src.mouse_interaction import MouseInteraction
from src.ui.game_menu_button import GameMenuButton
from src.rendering import display_manager
from src.ui import ui_style as ui
from src.managers.personal_best_manager import PersonalBestManager
from src.managers.achievements_manager import AchievementsManager
from src.managers.supabase_manager import get_supabase_manager
from utils.path_helper import resource_path
from src import solver
from src.game.hints import HintsMixin
from src.game.hud import HudMixin
from src.game.display import DisplayMixin
from src.game.moves import MovesMixin

""" Puts the application in the taskbar with a custom icon on Windows."""
import ctypes
myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

class Game(HintsMixin, HudMixin, DisplayMixin, MovesMixin):
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
            resource_path("utils/soundtrack/the_fifth_color.mp3"),
            resource_path("utils/soundtrack/Botanica.mp3"),
            resource_path("utils/soundtrack/udineCentro.mp3"),
        ]
        self.current_song = random.randint(0, len(self.playlist) - 1)  # Start with random song
        self.track_lengths = {}  # seconds, filled in the background; needed to time the fade out
        self.music_fading_out = False
        threading.Thread(target=self._measure_track_lengths, daemon=True).start()
        self.MUSIC_END_EVENT = pygame.USEREVENT + 1
        self.MUSIC_RESTORE_EVENT = pygame.USEREVENT + 10  # Event for restoring music volume after ducking
        
        # --- Start the soundtrack now that loading is done ---
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            # Set volume and end event for music
            music_volume = self.settings.get_music_volume() / 100
            master_volume = self.settings.get_master_volume() / 100
            pygame.mixer.music.set_volume(music_volume * master_volume)
            pygame.mixer.music.set_endevent(self.MUSIC_END_EVENT)
            pygame.mixer.music.load(self.playlist[self.current_song])
            pygame.mixer.music.play(fade_ms=MUSIC_FADE_MS)
        except Exception as e:
            print(f"Background music error: {e}")
    
        try:
            icon = pygame.image.load(resource_path("utils/rubiksCube_Icon.ico"))
            pygame.display.set_icon(icon)
        except:
            print("Icon not found")

        # Initialize renderer
        self.renderer = Renderer(self.width, self.height)
        self.apply_graphics_settings()
        
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
        # The saved skin was applied before achievements were loaded: check it is still unlocked
        self.renderer.set_skin(self.equipped_skin_id())

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
        solver.start()  # the hint solver's process loads its tables while the player starts

        # Achievement tracking for the current game and session
        self.hint_used_this_game = False
        self.undo_at_limit = False  # undid a move after reaching the Limited Moves limit
        self._last_mode = None
        self.session_start = time.time()
        self._session_minutes = 0

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
        mode = self.menu.get_selected_difficulty()
        if mode != self._last_mode:
            first_pick = self._last_mode is None  # the first mode of the session is not a switch
            self._last_mode = mode
            if not first_pick:
                self.enqueue_achievement_notifications(self.achievements_manager.record_mode_switch())

    def get_difficulty_change_count(self):
        """Get the current difficulty change count"""
        return self.difficulty_change_count

    def has_game_progress(self):
        """Check if the current game has any progress (moves made)"""
        return self.move_counter > 0 or self.start_time is not None

    def _measure_track_lengths(self):
        """Decode each track once to learn its length (pygame.mixer.music cannot report it)."""
        for path in self.playlist:
            try:
                self.track_lengths[path] = pygame.mixer.Sound(path).get_length()
            except Exception as e:
                print(f"Could not measure {path}: {e}")

    def update_track_fade_out(self):
        """Fade the current track out so it ends quietly; the end event then starts the next one."""
        if self.music_fading_out or not pygame.mixer.get_init() or not pygame.mixer.music.get_busy():
            return
        length = self.track_lengths.get(self.playlist[self.current_song])
        if length and pygame.mixer.music.get_pos() >= length * 1000 - MUSIC_FADE_MS:
            pygame.mixer.music.fadeout(MUSIC_FADE_MS)
            self.music_fading_out = True

    def debug_print(self, message):
        if self.debug_mode:
            print(message)

    def handle_events(self):
        events = []
        for event in pygame.event.get():
            events.append(event)
            
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == self.MUSIC_END_EVENT:
                # Pick a random song, never the one that just played
                others = [i for i in range(len(self.playlist)) if i != self.current_song]
                self.current_song = random.choice(others) if others else self.current_song
                self.debug_print(f"Playing random song: {self.playlist[self.current_song]}")

                try:
                    pygame.mixer.music.load(self.playlist[self.current_song])
                    pygame.mixer.music.play(fade_ms=MUSIC_FADE_MS)
                    self.music_fading_out = False
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

            # The achievement toast is on top of everything: a click opens the achievements page
            elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                  and self.achievement_toast_at(event.pos)):
                events.pop()  # not for the results window either
                self.open_achievements_from_toast()

            # IMPORTANT: Pass events to menu FIRST when menu is active
            # This allows text inputs in menus to receive keyboard events
            elif self.menu.is_active():
                # Let menu handle the event first
                if self.menu.handle_event(event):
                    continue
                # The menu ignores input while it animates closed: ESC then reopens it
                # instead of being swallowed
                if (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                        and self.menu.is_animating and not self.menu.is_opening
                        and not self.results_window.active
                        and self.difficulty_change_count >= 1):
                    self.menu.toggle()
                    self.debug_print("Menu: reopened during close animation")
                
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
                                self.hint_used_this_game = True
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
        self.update_track_fade_out()
        
        # Update cursor based on menu/results window state
        mouse_pos = pygame.mouse.get_pos()
        if self.achievement_toast_at(mouse_pos):
            pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_HAND)
        elif hasattr(self, 'menu') and self.menu.is_active():
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

        # Session length, for the Marathon Session achievement (checked once a minute)
        minutes = int((time.time() - self.session_start) // 60)
        if minutes != self._session_minutes:
            self._session_minutes = minutes
            self.enqueue_achievement_notifications(self.achievements_manager.record_session(minutes))

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
                
                # The menu's idle shuffle ends here; the scramble below resets the cube
                self.stop_menu_idle_shuffle()

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
            # ...while the solved cube slowly mixes itself
            self.update_menu_idle_shuffle()
        
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
                
                # Scramble moves can pass through the solved state; only the player's own moves count
                player_solved = not getattr(self, 'is_scrambling', False) and self.start_time is not None
                if cube_is_solved and not self.cube_solved and player_solved:
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
                        context = {"hint_used": self.hint_used_this_game, "time_limit": self.time_limit,
                                   "move_limit": self.move_limit, "undo_at_limit": self.undo_at_limit}
                        self.results_window.show_results(self.move_counter, solve_time, tps, current_difficulty,
                                                         context)

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

        # Render 3D cube with combined callback, through the anti-aliasing buffer
        offscreen = self.scene_target.begin(self.width, self.height)
        self.renderer.viewport_size = self.scene_target.scene_size if offscreen else (self.width, self.height)
        self.renderer.render_frame(debug_callback=combined_callback)
        self.scene_target.end()

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
            for surface, alpha, offset, changed in self.menu.layers(overlay):
                # The old page of a page change is a still image with its own texture
                texture = "_overlay_tex" if surface is overlay else "_snapshot_tex"
                self._draw_overlay(surface, alpha, offset, texture, upload=changed)

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

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            key = "fps_limit_menu" if self.menu.is_active() else "fps_limit_game"
            self.clock.tick(int(self.settings.settings.get(key, 60 if key == "fps_limit_menu" else 0) or 0))

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
        solver.shutdown()
        pygame.quit()
        sys.exit()
